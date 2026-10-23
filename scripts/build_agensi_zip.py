#!/usr/bin/env python3
"""Build a deterministic *consumer* ZIP. No marketplace submission.

The public repository keeps CI, scripts, evals and archived references.
Consumer ZIP ships the runnable memory companion and a self-contained skill.
"""
from __future__ import annotations

import argparse
import io
import re
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[1]
FILES = (
    "SKILL.md",
    "LICENSE",
    "VERIFICATION.md",
    "SECURITY.md",
    "UPSTREAM_VERSION",
    "references/patterns.md",
    "references/migration-v0.5.md",
    "references/memory.md",
    "references/storm-memory-evidence-2026-10-23.md",
    "runtime/scrapling_memory.py",
)
REMOVED_LINKS = (
    "evals/cases.jsonl",
    "references/SKILL.pre-2026-08-15.md",
)
SKILL_LINK = re.compile(r"\[[^\]]+\]\(([^)]+)\)")


def consumer_skill() -> str:
    content = (ROOT / "SKILL.md").read_text(encoding="utf-8")
    for line in content.splitlines():
        if any("](" + missing + ")" in line for missing in REMOVED_LINKS):
            content = content.replace(line + "\n", "")
    lines = content.splitlines()
    out = []
    in_source_qa = False
    for line in lines:
        # The source-only maintenance/CI scripts do not ship in the skill ZIP.
        if line.startswith("python scripts/") or line.startswith(
            "python -m unittest discover -s tests "
        ):
            continue
        out.append(line)
    content = "\n".join(out).rstrip() + "\n"
    # Every internal link must resolve to a packaged file, not source-only code.
    for target in SKILL_LINK.findall(content):
        if target.startswith(("http://", "https://", "#")):
            continue
        path = target.split("#", 1)[0]
        if path not in FILES and path != "SKILL.md":
            raise ValueError(f"consumer SKILL.md links to missing file: {path}")
    return content


def build(output: Path) -> None:
    if any(name.endswith(".pre-2026-08-15.md") for name in FILES):
        raise ValueError("historical snapshots cannot ship")
    if any(name.startswith((".github/", "scripts/", "tests/", "evals/")) for name in FILES):
        raise ValueError("source-only files cannot ship")
    if not (ROOT / "runtime/scrapling_memory.py").is_file():
        raise FileNotFoundError("runnable memory code must be included")

    contents = {"SKILL.md": consumer_skill().encode("utf-8")}
    for name in FILES:
        source = ROOT / name
        if not source.is_file() or source.is_symlink():
            raise FileNotFoundError(f"missing or symlinked package file: {name}")
        if name != "SKILL.md":
            contents[name] = source.read_bytes()

    output.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(output, "w", ZIP_DEFLATED) as archive:
        for name in sorted(contents):
            archive.writestr(name, contents[name])

    with ZipFile(output) as archive:
        got = set(archive.namelist())
        if got != set(FILES):
            raise AssertionError(f"manifest mismatch {got ^ set(FILES)}")
        if any(part.startswith((".github/", "scripts/", "tests/", "evals/")) for part in got):
            raise AssertionError("source-only files leaked")
        assert b"def observe(" in archive.read("runtime/scrapling_memory.py")
        assert b"references/memory.md" in archive.read("SKILL.md")
    print(f"Agensi candidate ZIP built, NOT SUBMITTED: {output} ({len(FILES)} files)")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    build(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
