#!/usr/bin/env python3
"""Scrapling Memory: opt-in local extraction know-how + evidence ledger.

Stdlib only. This module NEVER fetches URLs, executes source content, or
activates a browser. Upstream Scrapling remains responsible for extraction.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

MAX_DOCUMENT_BYTES = 1_000_000
STATUSES = frozenset({"new", "unchanged", "changed", "moved", "missing", "uncertain"})
FETCH_MODES = frozenset({"http", "browser", "api", "spider"})
EVIDENCE_STATES = frozenset({"checked", "not_checked", "unknown"})
SENSITIVE_KEYS = re.compile(r"(?:^|[_-])(password|passwd|secret|token|api[_-]?key|authorization|cookie|private[_-]?key|session[_-]?id)(?:$|[_-])", re.I)
URL_SENSITIVE_KEYS = re.compile(r"(?:^|[_-])(?:token|password|passwd|secret|api[_-]?key|authorization|session|email|auth|signature)(?:$|[_-])", re.I)
TRACKING_KEYS = frozenset({"gclid", "fbclid", "msclkid", "yclid"})
SLUG = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}\Z")
SCHEMA = """
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS site_profiles (
 namespace TEXT NOT NULL, host TEXT NOT NULL, profile_json TEXT NOT NULL,
 validated_at TEXT NOT NULL, expires_at TEXT NOT NULL,
 PRIMARY KEY(namespace, host)
);
CREATE TABLE IF NOT EXISTS subjects (
 namespace TEXT NOT NULL, entity_key TEXT NOT NULL, url TEXT NOT NULL,
 first_seen TEXT NOT NULL, last_seen TEXT NOT NULL, next_due TEXT NOT NULL,
 observations INTEGER NOT NULL DEFAULT 0, changes INTEGER NOT NULL DEFAULT 0,
 missing_streak INTEGER NOT NULL DEFAULT 0,
 PRIMARY KEY(namespace, entity_key)
);
CREATE TABLE IF NOT EXISTS snapshots (
 id INTEGER PRIMARY KEY AUTOINCREMENT, namespace TEXT NOT NULL,
 entity_key TEXT NOT NULL, url TEXT NOT NULL, observed_at TEXT NOT NULL,
 digest TEXT NOT NULL, data_json TEXT NOT NULL, extractor TEXT NOT NULL,
 fetch_mode TEXT NOT NULL, scrapling_version TEXT NOT NULL,
 skill_version TEXT NOT NULL, robots_status TEXT NOT NULL,
 terms_status TEXT NOT NULL, review_state TEXT NOT NULL DEFAULT 'unreviewed',
 FOREIGN KEY(namespace, entity_key) REFERENCES subjects(namespace, entity_key) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_snapshot_entity ON snapshots(namespace, entity_key, id DESC);
CREATE TABLE IF NOT EXISTS events (
 id INTEGER PRIMARY KEY AUTOINCREMENT, namespace TEXT NOT NULL, entity_key TEXT NOT NULL,
 url TEXT NOT NULL, observed_at TEXT NOT NULL,
 status TEXT NOT NULL CHECK(status IN ('new','unchanged','changed','moved','missing','uncertain')),
 snapshot_id INTEGER, details_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_events_entity ON events(namespace, entity_key, id DESC);
"""


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def iso(value: datetime) -> str:
    if value.tzinfo is None:
        raise ValueError("timezone-aware datetime required")
    return value.astimezone(timezone.utc).isoformat(timespec="seconds")


def check_slug(value: str, label: str = "namespace") -> None:
    if not SLUG.fullmatch(value):
        raise ValueError(f"{label} must be 1-64 safe ASCII characters")


def normal_url(url: str) -> str:
    value = url.strip()
    parsed = urlsplit(value)
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
        raise ValueError("absolute HTTP(S) URL required")
    if parsed.username or parsed.password:
        raise ValueError("credential-bearing source URL rejected")
    try:
        host = parsed.hostname.encode("idna").decode("ascii").lower()
        port = parsed.port
    except (ValueError, UnicodeError) as exc:
        raise ValueError("invalid source URL") from exc
    if ":" in host:
        host = f"[{host}]"
    scheme = parsed.scheme.lower()
    if port and (scheme, port) not in {("https", 443), ("http", 80)}:
        host += f":{port}"
    query = []
    for key, val in parse_qsl(parsed.query, keep_blank_values=True):
        if URL_SENSITIVE_KEYS.search(key):
            raise ValueError("URL query appears to contain private information")
        if key.lower().startswith("utm_") or key.lower() in TRACKING_KEYS:
            continue
        query.append((key, val))
    return urlunsplit((scheme, host, parsed.path or "/", urlencode(query), ""))


def entity_key(url: str, entity_id: str | None = None) -> str:
    if entity_id is None:
        return "url:" + normal_url(url)
    check_slug(entity_id, "entity ID")
    return "id:" + entity_id


def validate_tree(value: object, depth: int = 0) -> None:
    if depth > 20:
        raise ValueError("record nesting exceeds 20")
    if isinstance(value, dict):
        for key, child in value.items():
            if not isinstance(key, str) or SENSITIVE_KEYS.search(key):
                raise ValueError("invalid or sensitive record key")
            validate_tree(child, depth + 1)
    elif isinstance(value, list):
        for child in value:
            validate_tree(child, depth + 1)


def canonical_record(value: object) -> str:
    if not isinstance(value, (dict, list)) or not value:
        raise ValueError("nonempty typed JSON object/array required; blocked/empty pages are uncertain")
    validate_tree(value)
    rendered = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    if len(rendered.encode("utf-8")) > MAX_DOCUMENT_BYTES:
        raise ValueError("record exceeds 1 MiB")
    return rendered


def diff_fields(before: object, after: object, pointer: str = "") -> list[str]:
    if before == after:
        return []
    if isinstance(before, dict) and isinstance(after, dict):
        changes: list[str] = []
        for key in sorted(set(before) | set(after)):
            field = pointer + "/" + key.replace("~", "~0").replace("/", "~1")
            if key not in before or key not in after:
                changes.append(field)
            else:
                changes.extend(diff_fields(before[key], after[key], field))
        return changes
    # Lists have no stable entity IDs here; treat order changes atomically.
    return [pointer or "/"]


def connect(path: str | Path) -> sqlite3.Connection:
    db = Path(path).expanduser()
    db.parent.mkdir(parents=True, exist_ok=True)
    existed = db.exists()
    if db.is_symlink():
        raise ValueError("refuse symlink database path")
    connection = sqlite3.connect(db, timeout=10)
    connection.row_factory = sqlite3.Row
    connection.executescript(SCHEMA)
    if not existed and os.name == "posix":
        db.chmod(0o600)
    return connection


def record_event(conn: sqlite3.Connection, namespace: str, key: str, url: str,
                 when: str, status: str, snapshot_id: int | None,
                 details: dict[str, object]) -> int:
    if status not in STATUSES:
        raise ValueError("invalid event status")
    cur = conn.execute("INSERT INTO events(namespace,entity_key,url,observed_at,status,snapshot_id,details_json) "
                       "VALUES(?,?,?,?,?,?,?)", (namespace, key, url, when, status, snapshot_id,
                                                    json.dumps(details, sort_keys=True)))
    return int(cur.lastrowid)


def observe(conn: sqlite3.Connection, namespace: str, url: str, record: object,
            extractor: str, *, entity_id: str | None = None, validated: bool = False,
            fetch_mode: str = "http", scrapling_version: str = "0.5",
            skill_version: str = "memory-v0.1", robots_status: str = "unknown",
            terms_status: str = "unknown", interval_hours: int = 24,
            clock: datetime | None = None) -> dict[str, object]:
    """Only a caller-attested valid extraction advances trusted snapshots.

    `validated=True` is a caller attestation, NOT independently verified by
    this library. This module has no network access by design.
    """
    check_slug(namespace)
    canonical_url = normal_url(url)
    key = entity_key(canonical_url, entity_id)
    when = iso(clock or utcnow())
    if fetch_mode not in FETCH_MODES or robots_status not in EVIDENCE_STATES or terms_status not in EVIDENCE_STATES:
        raise ValueError("invalid provenance enum")
    if not extractor.strip() or len(extractor) > 128 or len(scrapling_version) > 40 or len(skill_version) > 40:
        raise ValueError("bounded extractor and versions required")
    if not 1 <= interval_hours <= 336:
        raise ValueError("interval_hours must be 1..336")
    if not validated:
        # Raw content is never retained when its quality gate has not passed.
        with conn:
            event_id = record_event(conn, namespace, key, canonical_url, when, "uncertain", None,
                                    {"reason": "quality_not_attested", "extractor": extractor})
        return {"event": "uncertain", "event_id": event_id, "reason": "quality_not_attested",
                "trusted_state_changed": False}
    rendered = canonical_record(record)
    digest = hashlib.sha256(rendered.encode("utf-8")).hexdigest()
    with conn:
        conn.execute("BEGIN IMMEDIATE")
        source = conn.execute("SELECT * FROM subjects WHERE namespace=? AND entity_key=?", (namespace, key)).fetchone()
        latest = conn.execute("SELECT * FROM snapshots WHERE namespace=? AND entity_key=? ORDER BY id DESC LIMIT 1",
                              (namespace, key)).fetchone()
        if source is not None and urlsplit(source["url"]).hostname != urlsplit(canonical_url).hostname:
            event_id = record_event(conn, namespace, key, canonical_url, when, "uncertain", None,
                                    {"reason": "cross_domain_identity_collision"})
            return {"event": "uncertain", "event_id": event_id,
                    "reason": "cross_domain_identity_collision", "trusted_state_changed": False}
        status = ("new" if latest is None else
                  "moved" if source["url"] != canonical_url else
                  "changed" if latest["digest"] != digest else "unchanged")
        changes = diff_fields(json.loads(latest["data_json"]), record) if latest and latest["digest"] != digest else []
        reappeared = bool(source and source["missing_streak"])
        due = iso((clock or utcnow()) + timedelta(hours=(max(1, interval_hours // 2) if status in {"changed", "moved"} else interval_hours)))
        if source is None:
            conn.execute("INSERT INTO subjects(namespace,entity_key,url,first_seen,last_seen,next_due,observations,changes,missing_streak) "
                         "VALUES(?,?,?,?,?,?,1,0,0)", (namespace, key, canonical_url, when, when, due))
        else:
            conn.execute("UPDATE subjects SET url=?,last_seen=?,next_due=?,observations=observations+1,"
                         "changes=changes+?,missing_streak=0 WHERE namespace=? AND entity_key=?",
                         (canonical_url, when, due, int(status in {"changed", "moved"}), namespace, key))
        if status == "unchanged":
            snapshot_id = int(latest["id"])
        else:
            cur = conn.execute("INSERT INTO snapshots(namespace,entity_key,url,observed_at,digest,data_json,extractor,fetch_mode,"
                               "scrapling_version,skill_version,robots_status,terms_status) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                               (namespace, key, canonical_url, when, digest, rendered, extractor, fetch_mode,
                                scrapling_version, skill_version, robots_status, terms_status))
            snapshot_id = int(cur.lastrowid)
        event_id = record_event(conn, namespace, key, canonical_url, when, status, snapshot_id,
                                {"changed_fields": changes, "reappeared": reappeared,
                                 "quality": "caller_attested", "missing_streak_reset": reappeared})
    return {"event": status, "event_id": event_id, "snapshot_id": snapshot_id,
            "namespace": namespace, "url": canonical_url, "entity_key": key, "sha256": digest,
            "observed_at": when, "changed_fields": changes, "reappeared": reappeared,
            "review_state": "unreviewed" if status != "unchanged" else latest["review_state"],
            "provenance": {"extractor": extractor, "fetch_mode": fetch_mode, "scrapling_version": scrapling_version,
                           "skill_version": skill_version, "robots_status": robots_status, "terms_status": terms_status},
            "quality": "caller_attested", "data_trust": "untrusted_source"}


def missing(conn: sqlite3.Connection, namespace: str, url: str, *, entity_id: str | None = None,
            complete_run: bool = False, clock: datetime | None = None,
            confirmation_threshold: int = 2, run_id: str | None = None) -> dict[str, object]:
    """A missing observation never deletes a source, even if confirmed."""
    check_slug(namespace)
    if run_id is not None:
        check_slug(run_id, "run ID")
    if not 2 <= confirmation_threshold <= 10:
        raise ValueError("confirmation threshold 2..10")
    canonical_url = normal_url(url)
    key = entity_key(canonical_url, entity_id)
    when = iso(clock or utcnow())
    with conn:
        conn.execute("BEGIN IMMEDIATE")
        source = conn.execute("SELECT missing_streak FROM subjects WHERE namespace=? AND entity_key=?", (namespace, key)).fetchone()
        if not source or not complete_run or not run_id:
            event_id = record_event(conn, namespace, key, canonical_url, when, "uncertain", None,
                                    {"reason": "source_unknown_or_run_incomplete_or_missing_run_id"})
            return {"event": "uncertain", "event_id": event_id, "confirmed": False, "trusted_state_changed": False}
        # Idempotency: a repeated report from the same completed crawl is not
        # evidence from an independent second crawl.
        previous = conn.execute("SELECT details_json FROM events WHERE namespace=? AND entity_key=? "
                                "AND status='missing'", (namespace, key)).fetchall()
        if any(json.loads(r["details_json"]).get("run_id") == run_id for r in previous):
            return {"event": "missing", "duplicate_run": True,
                    "missing_streak": int(source["missing_streak"]),
                    "confirmed": int(source["missing_streak"]) >= confirmation_threshold,
                    "deleted": False}
        streak = int(source["missing_streak"]) + 1
        conn.execute("UPDATE subjects SET missing_streak=? WHERE namespace=? AND entity_key=?", (streak, namespace, key))
        confirmed = streak >= confirmation_threshold
        event_id = record_event(conn, namespace, key, canonical_url, when, "missing", None,
                                {"missing_streak": streak, "confirmed": confirmed, "no_deletion": True, "run_id": run_id})
    return {"event": "missing", "event_id": event_id, "missing_streak": streak,
            "confirmed": confirmed, "deleted": False}


def save_profile(conn: sqlite3.Connection, namespace: str, url: str, profile: dict[str, object],
                 ttl_days: int = 14, clock: datetime | None = None) -> dict[str, object]:
    """Store caller-attested extraction know-how, not Scrapling adaptive internals."""
    check_slug(namespace)
    host = urlsplit(normal_url(url)).hostname
    if not 1 <= ttl_days <= 90:
        raise ValueError("profile TTL must be 1..90 days")
    if not isinstance(profile, dict) or set(profile) - {"fetch_mode", "selectors", "block_signals", "notes"}:
        raise ValueError("profile may only contain fetch_mode, selectors, block_signals, notes")
    mode = profile.get("fetch_mode")
    selectors = profile.get("selectors", {})
    signals = profile.get("block_signals", [])
    if mode not in FETCH_MODES:
        raise ValueError("profile fetch_mode must be http/browser/api/spider")
    if not isinstance(selectors, dict) or len(selectors) > 30 or not all(isinstance(k, str) and isinstance(v, str) and len(k) <= 80 and len(v) <= 500 for k, v in selectors.items()):
        raise ValueError("selectors must be a bounded string dictionary")
    if not isinstance(signals, list) or len(signals) > 20 or not all(isinstance(item, str) and len(item) <= 120 for item in signals):
        raise ValueError("block_signals must be bounded string list")
    notes = profile.get("notes", "")
    if not isinstance(notes, str) or len(notes) > 500:
        raise ValueError("notes too long")
    canonical = canonical_record({"fetch_mode": mode, "selectors": selectors, "block_signals": signals, "notes": notes})
    moment = clock or utcnow()
    seen, expires = iso(moment), iso(moment + timedelta(days=ttl_days))
    with conn:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute("INSERT INTO site_profiles(namespace,host,profile_json,validated_at,expires_at) VALUES(?,?,?,?,?) "
                     "ON CONFLICT(namespace,host) DO UPDATE SET profile_json=excluded.profile_json,"
                     "validated_at=excluded.validated_at,expires_at=excluded.expires_at",
                     (namespace, host, canonical, seen, expires))
    return {"host": host, "validated_at": seen, "expires_at": expires,
            "trust": "caller_attested", "not_shared_across_namespaces": True}


def delete_profile(conn: sqlite3.Connection, namespace: str, url: str) -> int:
    """Explicit per-domain erasure for stored extractor know-how."""
    check_slug(namespace)
    host = urlsplit(normal_url(url)).hostname
    with conn:
        conn.execute("BEGIN IMMEDIATE")
        return conn.execute("DELETE FROM site_profiles WHERE namespace=? AND host=?",
                            (namespace, host)).rowcount


def get_profile(conn: sqlite3.Connection, namespace: str, url: str,
                clock: datetime | None = None) -> dict[str, object] | None:
    check_slug(namespace)
    host = urlsplit(normal_url(url)).hostname
    row = conn.execute("SELECT * FROM site_profiles WHERE namespace=? AND host=?", (namespace, host)).fetchone()
    if row is None:
        return None
    expired = row["expires_at"] <= iso(clock or utcnow())
    return {"host": host, "profile": json.loads(row["profile_json"]), "validated_at": row["validated_at"],
            "expires_at": row["expires_at"], "stale": expired,
            "usable_without_revalidation": False, "trust": "caller_attested"}


def history(conn: sqlite3.Connection, namespace: str, url: str, *, entity_id: str | None = None,
            limit: int = 20) -> list[dict[str, object]]:
    check_slug(namespace)
    if not 1 <= limit <= 100:
        raise ValueError("limit must be 1..100")
    rows = conn.execute("SELECT id, observed_at, status, url, snapshot_id, details_json FROM events "
                        "WHERE namespace=? AND entity_key=? ORDER BY id DESC LIMIT ?",
                        (namespace, entity_key(url, entity_id), limit)).fetchall()
    return [{"id": row["id"], "observed_at": row["observed_at"], "status": row["status"],
             "url": row["url"], "snapshot_id": row["snapshot_id"], **json.loads(row["details_json"])} for row in rows]


def latest(conn: sqlite3.Connection, namespace: str, url: str, *, entity_id: str | None = None,
           include_data: bool = False) -> dict[str, object] | None:
    check_slug(namespace)
    row = conn.execute("SELECT * FROM snapshots WHERE namespace=? AND entity_key=? ORDER BY id DESC LIMIT 1",
                       (namespace, entity_key(url, entity_id))).fetchone()
    if not row:
        return None
    result = {k: row[k] for k in ("id", "url", "observed_at", "digest", "extractor", "fetch_mode",
                                    "scrapling_version", "skill_version", "robots_status", "terms_status", "review_state")}
    result["data_trust"] = "untrusted_source"
    if include_data:
        result["data"] = json.loads(row["data_json"])
    return result


def diff(conn: sqlite3.Connection, namespace: str, url: str, before_id: int, after_id: int,
         entity_id: str | None = None) -> dict[str, object]:
    check_slug(namespace)
    key = entity_key(url, entity_id)
    rows = conn.execute("SELECT id,digest,data_json FROM snapshots WHERE namespace=? AND entity_key=? AND id IN (?,?)",
                        (namespace, key, before_id, after_id)).fetchall()
    by_id = {row["id"]: row for row in rows}
    if before_id == after_id or before_id not in by_id or after_id not in by_id:
        raise ValueError("two distinct snapshot IDs for this entity required")
    changes = diff_fields(json.loads(by_id[before_id]["data_json"]), json.loads(by_id[after_id]["data_json"]))
    return {"from_id": before_id, "to_id": after_id, "changed_fields": changes,
            "from_digest": by_id[before_id]["digest"], "to_digest": by_id[after_id]["digest"],
            "field_values_exposed": False}


def find(conn: sqlite3.Connection, namespace: str, term: str, *, only_reviewed: bool = False,
         limit: int = 20) -> list[dict[str, object]]:
    check_slug(namespace)
    if not 1 <= len(term.strip()) <= 100 or not 1 <= limit <= 100:
        raise ValueError("bounded search term/limit required")
    escaped = term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    rows = conn.execute(
        "SELECT s.id,s.url,s.observed_at,s.digest,s.review_state FROM snapshots AS s JOIN "
        "(SELECT entity_key,MAX(id) id FROM snapshots WHERE namespace=? GROUP BY entity_key) AS t ON t.id=s.id "
        "WHERE s.namespace=? AND s.data_json LIKE ? ESCAPE '\\' "
        + ("AND s.review_state='reviewed' " if only_reviewed else "")
        + "ORDER BY s.id DESC LIMIT ?", (namespace, namespace, "%" + escaped + "%", limit)).fetchall()
    return [dict(r) for r in rows]


def review(conn: sqlite3.Connection, namespace: str, snapshot_id: int, reason: str) -> dict[str, object]:
    check_slug(namespace)
    if not 1 <= len(reason.strip()) <= 500:
        raise ValueError("bounded reason required")
    with conn:
        conn.execute("BEGIN IMMEDIATE")
        cur = conn.execute("UPDATE snapshots SET review_state='reviewed' WHERE id=? AND namespace=?",
                           (snapshot_id, namespace))
        if not cur.rowcount:
            raise ValueError("snapshot not in namespace")
    return {"snapshot_id": snapshot_id, "review_state": "reviewed", "method": "operator_attestation"}


def due(conn: sqlite3.Connection, namespace: str, *, clock: datetime | None = None,
        limit: int = 20) -> list[dict[str, object]]:
    check_slug(namespace)
    if not 1 <= limit <= 100:
        raise ValueError("limit must be 1..100")
    rows = conn.execute("SELECT entity_key,url,next_due,missing_streak FROM subjects "
                        "WHERE namespace=? AND next_due<=? ORDER BY next_due LIMIT ?",
                        (namespace, iso(clock or utcnow()), limit)).fetchall()
    return [dict(r) for r in rows]


def prune(conn: sqlite3.Connection, namespace: str, days: int,
          clock: datetime | None = None) -> dict[str, int]:
    check_slug(namespace)
    if not 1 <= days <= 3650:
        raise ValueError("retention days must be 1..3650")
    cutoff = iso((clock or utcnow()) - timedelta(days=days))
    with conn:
        conn.execute("BEGIN IMMEDIATE")
        old_events = conn.execute("DELETE FROM events WHERE namespace=? AND observed_at<?", (namespace, cutoff)).rowcount
        old_snapshots = conn.execute("DELETE FROM snapshots WHERE namespace=? AND observed_at<?", (namespace, cutoff)).rowcount
        conn.execute("UPDATE events SET snapshot_id=NULL WHERE namespace=? AND snapshot_id IS NOT NULL "
                     "AND NOT EXISTS (SELECT 1 FROM snapshots WHERE id=events.snapshot_id)", (namespace,))
        dead = conn.execute("DELETE FROM subjects WHERE namespace=? AND NOT EXISTS "
                            "(SELECT 1 FROM snapshots WHERE snapshots.namespace=subjects.namespace "
                            "AND snapshots.entity_key=subjects.entity_key)", (namespace,)).rowcount
        old_profiles = conn.execute("DELETE FROM site_profiles WHERE namespace=? AND expires_at<?",
                                    (namespace, cutoff)).rowcount
    return {"deleted_events": old_events, "deleted_snapshots": old_snapshots,
            "deleted_empty_subjects": dead, "deleted_expired_profiles": old_profiles}


def forget(conn: sqlite3.Connection, namespace: str, url: str,
           entity_id: str | None = None) -> dict[str, int]:
    check_slug(namespace)
    key = entity_key(url, entity_id)
    with conn:
        conn.execute("BEGIN IMMEDIATE")
        e = conn.execute("DELETE FROM events WHERE namespace=? AND entity_key=?", (namespace, key)).rowcount
        s = conn.execute("DELETE FROM subjects WHERE namespace=? AND entity_key=?", (namespace, key)).rowcount
    return {"deleted_subjects": s, "deleted_events": e}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Local, opt-in Scrapling Memory (never fetches URLs)")
    parser.add_argument("--db", required=True, help="private SQLite file path, outside the repository")
    parser.add_argument("--namespace", required=True, help="isolate project/site ownership")
    commands = parser.add_subparsers(dest="command", required=True)
    o = commands.add_parser("observe", help="store an explicitly validated extraction")
    o.add_argument("--url", required=True); o.add_argument("--file", required=True)
    o.add_argument("--extractor", required=True); o.add_argument("--validated", action="store_true")
    o.add_argument("--entity-id"); o.add_argument("--fetch-mode", choices=sorted(FETCH_MODES), default="http")
    o.add_argument("--scrapling-version", default="0.5")
    o.add_argument("--skill-version", default="memory-v0.1")
    o.add_argument("--robots-status", choices=sorted(EVIDENCE_STATES), default="unknown")
    o.add_argument("--terms-status", choices=sorted(EVIDENCE_STATES), default="unknown")
    m = commands.add_parser("missing", help="record absence from a complete, valid crawl")
    m.add_argument("--url", required=True); m.add_argument("--entity-id")
    m.add_argument("--complete-run", action="store_true"); m.add_argument("--run-id")
    ps = commands.add_parser("profile-set", help="write caller-attested extractor profile")
    ps.add_argument("--url", required=True); ps.add_argument("--file", required=True)
    ps.add_argument("--ttl-days", type=int, default=14)
    pg = commands.add_parser("profile-get"); pg.add_argument("--url", required=True)
    pd = commands.add_parser("profile-delete"); pd.add_argument("--url", required=True)
    h = commands.add_parser("history"); h.add_argument("--url", required=True); h.add_argument("--entity-id")
    l = commands.add_parser("latest"); l.add_argument("--url", required=True); l.add_argument("--entity-id")
    l.add_argument("--include-data", action="store_true")
    d = commands.add_parser("diff"); d.add_argument("--url", required=True); d.add_argument("--entity-id")
    d.add_argument("--before", type=int, required=True); d.add_argument("--after", type=int, required=True)
    f = commands.add_parser("find"); f.add_argument("--term", required=True); f.add_argument("--reviewed", action="store_true")
    r = commands.add_parser("review"); r.add_argument("--id", type=int, required=True); r.add_argument("--reason", required=True)
    u = commands.add_parser("due")
    p = commands.add_parser("prune"); p.add_argument("--days", type=int, required=True)
    x = commands.add_parser("forget"); x.add_argument("--url", required=True); x.add_argument("--entity-id")
    args = parser.parse_args(argv)
    try:
        if args.command in {"observe", "profile-set"}:
            file = Path(args.file)
            if file.stat().st_size > MAX_DOCUMENT_BYTES:
                raise ValueError("input too large")
            payload = json.loads(file.read_text(encoding="utf-8"))
        with connect(args.db) as conn:
            if args.command == "observe":
                result = observe(conn, args.namespace, args.url, payload, args.extractor,
                                 entity_id=args.entity_id, validated=args.validated,
                                 fetch_mode=args.fetch_mode, scrapling_version=args.scrapling_version,
                                 skill_version=args.skill_version, robots_status=args.robots_status,
                                 terms_status=args.terms_status)
            elif args.command == "missing":
                result = missing(conn, args.namespace, args.url, entity_id=args.entity_id,
                                 complete_run=args.complete_run, run_id=args.run_id)
            elif args.command == "profile-set":
                result = save_profile(conn, args.namespace, args.url, payload, ttl_days=args.ttl_days)
            elif args.command == "profile-get":
                result = get_profile(conn, args.namespace, args.url)
            elif args.command == "profile-delete":
                result = {"deleted_profiles": delete_profile(conn, args.namespace, args.url)}
            elif args.command == "history":
                result = history(conn, args.namespace, args.url, entity_id=args.entity_id)
            elif args.command == "latest":
                result = latest(conn, args.namespace, args.url, entity_id=args.entity_id, include_data=args.include_data)
            elif args.command == "diff":
                result = diff(conn, args.namespace, args.url, args.before, args.after, args.entity_id)
            elif args.command == "find":
                result = find(conn, args.namespace, args.term, only_reviewed=args.reviewed)
            elif args.command == "review":
                result = review(conn, args.namespace, args.id, args.reason)
            elif args.command == "due":
                result = due(conn, args.namespace)
            elif args.command == "prune":
                result = prune(conn, args.namespace, args.days)
            else:
                result = forget(conn, args.namespace, args.url, args.entity_id)
        print(json.dumps(result, sort_keys=True, ensure_ascii=False))
        return 0
    except (ValueError, OSError, json.JSONDecodeError, sqlite3.Error, TypeError) as exc:
        print(f"memory error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())