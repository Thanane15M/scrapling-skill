"""Offline tests for opt-in Scrapling Recall evidence memory.

No websites, browser, credentials, or private infrastructure are accessed.
"""
import contextlib
import importlib.util
import io
import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

SPEC = importlib.util.spec_from_file_location(
    "scrapling_memory", Path(__file__).resolve().parents[1] / "runtime" / "scrapling_memory.py"
)
memory = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(memory)
T = datetime(2026, 10, 23, tzinfo=timezone.utc)

class RecallTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.conn = memory.connect(Path(temp.name) / "state.sqlite")
        self.addCleanup(self.conn.close)
        self.url = "https://example.org/products/42?utm_source=ignored"

    def observe(self, data, **kwargs):
        params = {"validated": True, "clock": T}
        params.update(kwargs)
        return memory.observe(self.conn, "alpha", self.url, data, "fixture-v1", **params)

    def test_new_unchanged_changed(self):
        first = self.observe({"price": 12, "currency": "EUR"})
        same = self.observe({"currency": "EUR", "price": 12})
        changed = self.observe({"price": 13, "currency": "EUR"})
        self.assertEqual([first["event"], same["event"], changed["event"]],
                         ["new", "unchanged", "changed"])
        self.assertEqual(same["snapshot_id"], first["snapshot_id"])
        self.assertEqual(changed["changed_fields"], ["/price"])
        self.assertEqual(len(memory.history(self.conn, "alpha", self.url)), 3)
        self.assertEqual(self.conn.execute("SELECT count(*) FROM snapshots").fetchone()[0], 2)

    def test_uncertain_never_overwrites_trusted_data(self):
        self.observe({"price": 12})
        unclear = memory.observe(self.conn, "alpha", self.url, {"price": 0}, "fixture-v1")
        self.assertEqual(unclear["event"], "uncertain")
        self.assertFalse(unclear["trusted_state_changed"])
        self.assertEqual(memory.latest(self.conn, "alpha", self.url, include_data=True)["data"]["price"], 12)

    def test_invalid_empty_and_html_are_not_valid_snapshots(self):
        for payload in ({}, [], "<html>blocked</html>"):
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                self.observe(payload)

    def test_missing_needs_distinct_complete_runs(self):
        self.observe({"price": 12})
        self.assertEqual(memory.missing(self.conn, "alpha", self.url)["event"], "uncertain")
        first = memory.missing(self.conn, "alpha", self.url, complete_run=True, run_id="run-01")
        duplicate = memory.missing(self.conn, "alpha", self.url, complete_run=True, run_id="run-01")
        second = memory.missing(self.conn, "alpha", self.url, complete_run=True, run_id="run-02")
        self.assertFalse(first["confirmed"])
        self.assertTrue(duplicate["duplicate_run"])
        self.assertTrue(second["confirmed"])
        self.assertFalse(second["deleted"])
        self.assertTrue(self.observe({"price": 12})["reappeared"])
        self.assertIsNotNone(memory.latest(self.conn, "alpha", self.url))

    def test_stable_identity_detects_move(self):
        first = self.observe({"sku": "42"}, entity_id="product-42")
        moved = memory.observe(self.conn, "alpha", "https://example.org/new/42",
                               {"sku": "42"}, "fixture-v1", entity_id="product-42",
                               validated=True, clock=T)
        self.assertEqual(first["event"], "new")
        self.assertEqual(moved["event"], "moved")

    def test_cross_domain_identity_is_quarantined(self):
        self.observe({"sku": "42"}, entity_id="product-42")
        wrong = memory.observe(self.conn, "alpha", "https://different.org/42",
                               {"sku": "42"}, "fixture-v1", entity_id="product-42",
                               validated=True, clock=T)
        self.assertEqual(wrong["event"], "uncertain")
        self.assertEqual(wrong["reason"], "cross_domain_identity_collision")

    def test_move_without_identity_is_not_guessed(self):
        self.observe({"sku": "42"})
        result = memory.observe(self.conn, "alpha", "https://example.org/new/42",
                                {"sku": "42"}, "fixture-v1", validated=True, clock=T)
        self.assertEqual(result["event"], "new")

    def test_profile_expiry_and_isolation(self):
        profile = {"fetch_mode": "http", "selectors": {"price": ".price"},
                   "block_signals": ["challenge"]}
        memory.save_profile(self.conn, "alpha", self.url, profile, ttl_days=7, clock=T)
        self.assertFalse(memory.get_profile(self.conn, "alpha", self.url,
                                            T + timedelta(days=6))["stale"])
        self.assertTrue(memory.get_profile(self.conn, "alpha", self.url,
                                           T + timedelta(days=8))["stale"])
        self.assertIsNone(memory.get_profile(self.conn, "beta", self.url))
        self.assertEqual(memory.delete_profile(self.conn, "alpha", self.url), 1)

    def test_sensitive_keys_and_urls_rejected(self):
        for payload in ({"api_key": "abc"}, {"cookie": "session"},
                        {"nested": {"session_id": "abc"}}):
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                self.observe(payload)
        for url in ("https://alice:pw@x.org/", "https://x.org/?auth_token=abc",
                    "file:///etc/passwd"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                memory.normal_url(url)

    def test_benign_url_author_query_is_allowed(self):
        normalized = memory.normal_url("https://example.org/articles?author=Gael")
        self.assertEqual(normalized, "https://example.org/articles?author=Gael")

    def test_namespace_isolation_and_erasure(self):
        self.observe({"value": "left"})
        memory.observe(self.conn, "beta", self.url, {"value": "right"}, "other",
                       validated=True, clock=T)
        self.assertEqual(memory.forget(self.conn, "alpha", self.url)["deleted_subjects"], 1)
        self.assertIsNone(memory.latest(self.conn, "alpha", self.url))
        self.assertIsNotNone(memory.latest(self.conn, "beta", self.url))

    def test_diff_does_not_expose_values(self):
        a = self.observe({"price": 12})
        b = self.observe({"price": 13})
        result = memory.diff(self.conn, "alpha", self.url,
                             a["snapshot_id"], b["snapshot_id"])
        self.assertEqual(result["changed_fields"], ["/price"])
        self.assertFalse(result["field_values_exposed"])
        with self.assertRaises(ValueError):
            memory.diff(self.conn, "beta", self.url,
                        a["snapshot_id"], b["snapshot_id"])

    def test_search_only_latest_and_manual_review(self):
        self.observe({"text": "alpha"})
        final = self.observe({"text": "beta"})
        self.assertEqual(memory.find(self.conn, "alpha", "alpha"), [])
        self.assertEqual(len(memory.find(self.conn, "alpha", "beta")), 1)
        self.assertEqual(memory.find(self.conn, "alpha", "beta", only_reviewed=True), [])
        memory.review(self.conn, "alpha", final["snapshot_id"], "manually checked")
        self.assertEqual(len(memory.find(self.conn, "alpha", "beta", only_reviewed=True)), 1)

    def test_explicit_retention(self):
        self.observe({"price": 1}, clock=T - timedelta(days=100))
        self.observe({"price": 2})
        outcome = memory.prune(self.conn, "alpha", 90, T)
        self.assertEqual(outcome["deleted_snapshots"], 1)

    def test_three_synthetic_sites_twice_not_real_world(self):
        for index, domain in enumerate(("a.example.org", "b.example.org", "c.example.org")):
            url = "https://" + domain + "/"
            self.assertEqual(memory.observe(self.conn, "fixtures", url, {"v": index},
                                            "test", validated=True, clock=T)["event"], "new")
            value = index + (1 if index == 1 else 0)
            self.assertEqual(memory.observe(self.conn, "fixtures", url, {"v": value},
                                            "test", validated=True, clock=T)["event"],
                             "changed" if index == 1 else "unchanged")

    def test_cli_provenance_flags_are_caller_reported(self):
        with tempfile.TemporaryDirectory() as temp:
            record = Path(temp) / "record.json"
            record.write_text('{"price":19}', encoding="utf-8")
            db_path = Path(temp) / "proof.sqlite"
            captured = io.StringIO()
            with contextlib.redirect_stdout(captured):
                code = memory.main([
                    "--db", str(db_path), "--namespace", "sample",
                    "observe", "--url", self.url, "--file", str(record),
                    "--extractor", "test-cli", "--validated",
                    "--robots-status", "checked", "--terms-status", "not_checked",
                    "--skill-version", "memory-v0.1",
                ])
            self.assertEqual(code, 0)
            receipt = json.loads(captured.getvalue())
            self.assertEqual(receipt["provenance"]["robots_status"], "checked")
            self.assertEqual(receipt["provenance"]["terms_status"], "not_checked")
            self.assertEqual(receipt["review_state"], "unreviewed")

    def test_due_never_performs_network_requests(self):
        self.observe({"price": 1})
        self.assertEqual(memory.due(self.conn, "alpha", clock=T + timedelta(hours=23)), [])
        self.assertEqual(len(memory.due(self.conn, "alpha",
                                        clock=T + timedelta(hours=25))), 1)

if __name__ == "__main__":
    unittest.main()
