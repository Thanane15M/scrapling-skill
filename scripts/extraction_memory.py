"""Opt-in, local, bounded extraction memory; no network access or dependency on Scrapling internals."""
from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

SCHEMA_VERSION = 1
ALLOWED_MODES = {"http", "browser", "api"}
STATUSES = {"new", "unchanged", "modified", "moved", "missing", "uncertain"}


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def safe_url(url: str) -> tuple[str, str]:
    """Drop credentials, query and fragments; reject non-web or malformed URLs."""
    u = urlsplit(url)
    if u.scheme not in ("http", "https") or not u.hostname:
        raise ValueError("only http(s) source URLs are accepted")
    host = u.hostname.lower().rstrip(".")
    if not host:
        raise ValueError("empty host")
    port = f":{u.port}" if u.port else ""
    path = u.path or "/"
    return host, urlunsplit((u.scheme, host + port, path, "", ""))


def digest_fields(fields: dict[str, object]) -> dict[str, str]:
    """Only deterministic hashes of explicitly selected scalar fields are persisted."""
    result = {}
    for key, value in fields.items():
        if not isinstance(key, str) or not key or len(key) > 128:
            raise ValueError("field keys must be nonempty strings <=128 characters")
        if not isinstance(value, (str, int, float, bool, type(None))):
            raise ValueError("only scalar values allowed")
        normalized = json.dumps(value.strip() if isinstance(value, str) else value,
                                ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        result[key] = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    return result


class ExtractionMemory:
    """Site profiles and field-hash observations; isolated by namespace and domain."""

    def __init__(self, database: str | Path, namespace: str = "default"):
        if not namespace or len(namespace) > 128:
            raise ValueError("invalid namespace")
        self.namespace = namespace
        self.db = sqlite3.connect(str(database), timeout=15)
        self.db.execute("PRAGMA busy_timeout=15000")
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS profiles(
                namespace TEXT NOT NULL, domain TEXT NOT NULL,
                mode TEXT NOT NULL, selectors TEXT NOT NULL,
                verified_at TEXT NOT NULL, expires_at TEXT NOT NULL,
                PRIMARY KEY(namespace,domain));
            CREATE TABLE IF NOT EXISTS observations(
                namespace TEXT NOT NULL, domain TEXT NOT NULL, record_key TEXT NOT NULL,
                source_url TEXT NOT NULL, hashes TEXT NOT NULL, observed_at TEXT NOT NULL,
                absent_count INTEGER NOT NULL DEFAULT 0, status TEXT NOT NULL,
                PRIMARY KEY(namespace,domain,record_key));
            CREATE TABLE IF NOT EXISTS receipts(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                namespace TEXT NOT NULL, domain TEXT NOT NULL, record_key TEXT NOT NULL,
                source_url TEXT NOT NULL, observed_at TEXT NOT NULL,
                status TEXT NOT NULL, fields_changed TEXT NOT NULL,
                scrapling_version TEXT, skill_version TEXT,
                robots_reviewed TEXT, terms_reviewed TEXT);
        """)
        self.db.commit()

    def close(self):
        self.db.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    def save_profile(self, url: str, mode: str, selectors: dict[str, str],
                     ttl_days: int = 14) -> None:
        domain, _ = safe_url(url)
        if mode not in ALLOWED_MODES or not 1 <= ttl_days <= 365:
            raise ValueError("invalid mode or ttl")
        if not isinstance(selectors, dict) or any(
            not isinstance(k, str) or not isinstance(v, str) or len(v) > 1024
            for k, v in selectors.items()
        ):
            raise ValueError("selectors must be a mapping of bounded strings")
        now = datetime.now(timezone.utc)
        with self.db:
            self.db.execute("""INSERT INTO profiles VALUES(?,?,?,?,?,?)
                ON CONFLICT(namespace,domain) DO UPDATE SET
                mode=excluded.mode,selectors=excluded.selectors,
                verified_at=excluded.verified_at,expires_at=excluded.expires_at""",
                (self.namespace, domain, mode, json.dumps(selectors, sort_keys=True),
                 now.isoformat(), (now + timedelta(days=ttl_days)).isoformat()))

    def get_profile(self, url: str) -> dict | None:
        domain, _ = safe_url(url)
        row = self.db.execute(
            "SELECT mode,selectors,verified_at,expires_at FROM profiles WHERE namespace=? AND domain=?",
            (self.namespace, domain)).fetchone()
        if not row:
            return None
        mode, selectors, verified_at, expires_at = row
        if datetime.fromisoformat(expires_at) <= datetime.now(timezone.utc):
            return None
        return {"mode": mode, "selectors": json.loads(selectors),
                "verified_at": verified_at, "expires_at": expires_at,
                "advisory_only": True}

    def observe(self, url: str, record_key: str, fields: dict[str, object], *,
                verified: bool, scrapling_version: str = "", skill_version: str = "",
                robots_reviewed: str = "unknown", terms_reviewed: str = "unknown") -> dict:
        if not record_key or len(record_key) > 256:
            raise ValueError("invalid record key")
        domain, clean_url = safe_url(url)
        # Never learn from blocked pages, ambiguous selectors or invalid records.
        if not verified:
            return {"status": "uncertain", "changed_fields": [], "persisted": False}
        if not fields:
            raise ValueError("verified observation must have at least one field")
        hashes = digest_fields(fields)
        old = self.db.execute("""SELECT source_url,hashes FROM observations
            WHERE namespace=? AND domain=? AND record_key=?""",
            (self.namespace, domain, record_key)).fetchone()
        previous = json.loads(old[1]) if old else {}
        changed = sorted(k for k in set(previous) | set(hashes)
                         if previous.get(k) != hashes.get(k))
        status = ("new" if not old else "modified" if changed else
                  "moved" if old[0] != clean_url else "unchanged")
        now = utcnow()
        with self.db:
            self.db.execute("""INSERT INTO observations VALUES(?,?,?,?,?,?,0,?)
                ON CONFLICT(namespace,domain,record_key) DO UPDATE SET
                source_url=excluded.source_url,hashes=excluded.hashes,
                observed_at=excluded.observed_at,absent_count=0,status=excluded.status""",
                (self.namespace, domain, record_key, clean_url,
                 json.dumps(hashes, sort_keys=True), now, status))
            self.db.execute("""INSERT INTO receipts
                (namespace,domain,record_key,source_url,observed_at,status,
                 fields_changed,scrapling_version,skill_version,robots_reviewed,terms_reviewed)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (self.namespace, domain, record_key, clean_url, now, status,
                 json.dumps(changed), scrapling_version, skill_version,
                 robots_reviewed, terms_reviewed))
        return {"status": status, "changed_fields": changed, "persisted": True}

    def mark_absent(self, url: str, record_key: str, *,
                    crawl_verified: bool, threshold: int = 3) -> dict:
        """Missing is never a deletion; only count trustworthy completed crawls."""
        if threshold < 2:
            raise ValueError("absence threshold must be >=2")
        domain, _ = safe_url(url)
        old = self.db.execute("""SELECT source_url,absent_count FROM observations
            WHERE namespace=? AND domain=? AND record_key=?""",
            (self.namespace, domain, record_key)).fetchone()
        if not crawl_verified or not old:
            return {"status": "uncertain", "persisted": False}
        count = old[1] + 1
        status = "missing" if count >= threshold else "uncertain"
        with self.db:
            self.db.execute("""UPDATE observations SET absent_count=?,status=?
                WHERE namespace=? AND domain=? AND record_key=?""",
                (count, status, self.namespace, domain, record_key))
            self.db.execute("""INSERT INTO receipts
                (namespace,domain,record_key,source_url,observed_at,status,fields_changed)
                VALUES (?,?,?,?,?,?,?)""",
                (self.namespace, domain, record_key, old[0], utcnow(), status, "[]"))
        return {"status": status, "absent_count": count, "persisted": True,
                "deleted": False}

    def history(self, url: str, record_key: str, limit: int = 20) -> list[dict]:
        domain, _ = safe_url(url)
        if not 1 <= limit <= 100:
            raise ValueError("limit must be 1..100")
        rows = self.db.execute("""SELECT source_url,observed_at,status,fields_changed,
            scrapling_version,skill_version,robots_reviewed,terms_reviewed
            FROM receipts WHERE namespace=? AND domain=? AND record_key=?
            ORDER BY id DESC LIMIT ?""", (self.namespace, domain, record_key, limit))
        return [dict(zip(("url", "observed_at", "status", "changed_fields",
                          "scrapling_version", "skill_version", "robots_reviewed",
                          "terms_reviewed"),
                         (url, stamp, status, json.loads(changed), sv, kv, robots, terms)))
                for url, stamp, status, changed, sv, kv, robots, terms in rows]
