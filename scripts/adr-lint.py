#!/usr/bin/env python3
"""Validate ADR frontmatter and PRD cross-references."""

from __future__ import annotations

import pathlib
import re
import subprocess
import sys
from typing import Any

try:
    import yaml
except ImportError:
    sys.exit("error: PyYAML not installed. Run: pdm install -G tests")


FRONTMATTER_RE = re.compile(r"\A---\n(.*?)\n---", re.DOTALL)


def repo_root() -> pathlib.Path:
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "--show-toplevel"],
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
        return pathlib.Path(out)
    except (subprocess.CalledProcessError, FileNotFoundError):
        return pathlib.Path.cwd()


def adr_dir(root: pathlib.Path) -> pathlib.Path:
    candidate = root / "docs" / "adr"
    if candidate.is_dir():
        return candidate
    sys.exit(f"error: no docs/adr directory under {root}")


def parse_frontmatter(path: pathlib.Path) -> dict[str, Any] | None:
    text = path.read_text(encoding="utf-8")
    match = FRONTMATTER_RE.match(text)
    if not match:
        return None
    try:
        data = yaml.safe_load(match.group(1))
    except yaml.YAMLError:
        return None
    return data if isinstance(data, dict) else None


def iter_adr_files(directory: pathlib.Path):
    for file in sorted(directory.glob("[0-9]*-*.md")):
        if file.is_file():
            yield file
    for subdir in sorted(directory.glob("[0-9]*-*")):
        readme = subdir / "README.md"
        if subdir.is_dir() and readme.is_file():
            yield readme


def normalize_id(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, int):
        return f"ADR-{value}"
    text = str(value).strip()
    if not text:
        return ""
    return text if text.startswith("ADR-") else f"ADR-{text}"


def main() -> int:
    root = repo_root()
    directory = adr_dir(root)
    prd_dir = root / "docs" / "prd"
    prd_corpus = prd_dir.is_dir()
    errors: list[str] = []

    def fail(path: pathlib.Path, message: str) -> None:
        errors.append(f"FAIL [{path.relative_to(root)}]: {message}")

    records: dict[str, dict[str, Any]] = {}
    for path in iter_adr_files(directory):
        fm = parse_frontmatter(path)
        if fm is None:
            fail(path, "missing or unparseable frontmatter")
            continue
        adr_id = normalize_id(fm.get("id", ""))
        if not adr_id:
            fail(path, "frontmatter.id missing")
            continue

        status = str(fm.get("status", "")).strip()
        superseded_by = normalize_id(fm.get("superseded_by"))
        supersedes = {normalize_id(v) for v in (fm.get("supersedes") or []) if normalize_id(v)}

        if status == "Superseded" and not superseded_by:
            fail(path, "status=Superseded but superseded_by is empty")

        prds = fm.get("prds")
        if prds:
            if not isinstance(prds, list):
                fail(path, f"frontmatter.prds must be a list, got {type(prds).__name__}")
            elif not prd_corpus:
                fail(path, "frontmatter.prds is set but docs/prd/ does not exist")
            else:
                for slug in prds:
                    if not isinstance(slug, str) or not slug:
                        fail(path, f"frontmatter.prds contains invalid entry: {slug!r}")
                        continue
                    if not (prd_dir / f"{slug}.md").exists():
                        fail(path, f"prds references {slug!r} but docs/prd/{slug}.md does not exist")

        records[adr_id] = {
            "path": path,
            "status": status,
            "superseded_by": superseded_by,
            "supersedes": supersedes,
        }

    for adr_id, record in records.items():
        new_id = record["superseded_by"]
        if new_id:
            other = records.get(new_id)
            if other is None:
                fail(record["path"], f"superseded_by={new_id} but no such ADR found")
            elif adr_id not in other["supersedes"]:
                fail(
                    record["path"],
                    f"superseded_by={new_id}, but {new_id}.supersedes does not include {adr_id}",
                )

        for old_id in record["supersedes"]:
            other = records.get(old_id)
            if other is None:
                fail(record["path"], f"supersedes {old_id} but no such ADR found")
            elif other["status"] != "Superseded":
                fail(
                    record["path"],
                    f"supersedes {old_id}, but {old_id}.status={other['status']!r}",
                )

    if errors:
        print("\n".join(errors), file=sys.stderr)
        print(f"adr-lint: {len(errors)} error(s)", file=sys.stderr)
        return 1
    print(f"adr-lint: OK ({len(records)} ADRs)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
