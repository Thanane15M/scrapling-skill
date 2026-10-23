"""Deterministic, offline behavior tests for the optional local memory."""
import tempfile
import unittest
from pathlib import Path
from scripts.extraction_memory import ExtractionMemory, safe_url


class MemoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "memory.sqlite"

    def tearDown(self):
        self.tmp.cleanup()

    def test_flow_across_restarts_and_changes(self):
        with ExtractionMemory(self.path) as m:
            m.save_profile("https://example.com/page?token=secret", "http", {"price": ".price"})
            self.assertEqual(m.observe("https://example.com/a?token=secret",
                "product-1", {"price": "10"}, verified=True)["status"], "new")
            self.assertEqual(m.observe("https://example.com/a",
                "product-1", {"price": "10"}, verified=True)["status"], "unchanged")
        with ExtractionMemory(self.path) as m:
            self.assertEqual(m.get_profile("https://example.com")["mode"], "http")
            self.assertEqual(m.observe("https://example.com/b", "product-1",
                {"price": "10"}, verified=True)["status"], "moved")
            change = m.observe("https://example.com/b", "product-1",
                               {"price": "12"}, verified=True)
            self.assertEqual(change["status"], "modified")
            self.assertEqual(change["changed_fields"], ["price"])
            self.assertEqual(m.mark_absent("https://example.com", "product-1",
                crawl_verified=False)["status"], "uncertain")
            for i in range(2):
                self.assertEqual(m.mark_absent("https://example.com", "product-1",
                    crawl_verified=True)["status"], "uncertain")
            self.assertEqual(m.mark_absent("https://example.com", "product-1",
                crawl_verified=True)["status"], "missing")
            self.assertFalse(m.mark_absent("https://example.com", "product-1",
                crawl_verified=True)["deleted"])
            self.assertEqual(m.observe("https://example.com/b", "product-1",
                {"price": "12"}, verified=True)["status"], "unchanged")
            history = m.history("https://example.com", "product-1")
            self.assertFalse(any("secret" in str(row) for row in history))
            self.assertFalse(any("12" in str(row) for row in history))

    def test_isolation_unknown_and_validation(self):
        with ExtractionMemory(self.path, "tenant-a") as a, ExtractionMemory(self.path, "tenant-b") as b:
            self.assertEqual(a.observe("https://a.com", "x", {"n": 1},
                           verified=False)["status"], "uncertain")
            self.assertEqual(a.history("https://a.com", "x"), [])
            a.observe("https://a.com", "x", {"n": 1}, verified=True)
            self.assertEqual(b.history("https://a.com", "x"), [])
            self.assertEqual(a.history("https://b.com", "x"), [])
            with self.assertRaises(ValueError):
                a.observe("file:///etc/passwd", "x", {"n": 1}, verified=True)
            with self.assertRaises(ValueError):
                a.observe("https://a.com", "x", {"nested": {"pii": "x"}}, verified=True)
            with self.assertRaises(ValueError):
                a.mark_absent("https://a.com", "x", crawl_verified=True, threshold=1)
            a.save_profile("https://a.com", "browser", {}, ttl_days=1)
            self.assertIsNone(b.get_profile("https://a.com"))

    def test_query_and_credentials_not_persisted(self):
        host, cleaned = safe_url("https://someone:password@example.com/p?email=x#section")
        self.assertEqual(host, "example.com")
        self.assertEqual(cleaned, "https://example.com/p")


if __name__ == "__main__":
    unittest.main()
