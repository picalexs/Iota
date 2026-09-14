#!/usr/bin/env python3
"""Check current Markdown links and referenced local npm/Python scripts."""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote, urlsplit

LOCAL_LINK_RE = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")
NPM_RUN_RE = re.compile(
    r"\bnpm(?P<prefix>\s+--prefix\s+(?P<directory>\S+))?\s+run\s+"
    r"(?P<script>[A-Za-z0-9][A-Za-z0-9:_-]*)"
)
PYTHON_SCRIPT_RE = re.compile(
    r"(?<![\w./-])(?:[\w./-]+/)?python(?:3(?:\.\d+)?)?\s+"
    r"(?:-\w+\s+)*scripts/(?P<script>[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)*\.py)\b"
)


@dataclass(frozen=True)
class Issue:
    """One invalid documentation target."""

    document: Path
    line: int
    message: str

    def __str__(self) -> str:
        return f"{self.document}:{self.line}: {self.message}"


def _documents(root: Path, paths: list[str] | None) -> list[Path]:
    candidates = (
        [root / "README.md", root / "docs"]
        if paths is None
        else [root / path for path in paths]
    )
    documents: set[Path] = set()
    for candidate in candidates:
        if candidate.is_file() and candidate.suffix.lower() == ".md":
            documents.add(candidate)
            continue
        if candidate.is_dir():
            documents.update(
                path for path in candidate.rglob("*.md")
            )
    return sorted(documents)


def _package_scripts(package_path: Path) -> dict[str, object]:
    try:
        package = json.loads(package_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    scripts = package.get("scripts", {})
    return scripts if isinstance(scripts, dict) else {}


def _destination(raw_destination: str) -> str:
    destination = raw_destination.strip()
    if destination.startswith("<") and ">" in destination:
        return destination[1 : destination.index(">")]
    return destination.split()[0]


def _check_local_link(root: Path, document: Path, raw_destination: str, line: int) -> Issue | None:
    destination = _destination(raw_destination)
    parsed = urlsplit(destination)
    if parsed.scheme or destination.startswith("//") or not parsed.path:
        return None

    relative_path = Path(unquote(parsed.path))
    target = (
        root / relative_path.lstrip("/")
        if relative_path.is_absolute()
        else document.parent / relative_path
    )
    if target.exists():
        return None
    return Issue(document, line, f"local Markdown target does not exist: {destination}")


def _check_npm_command(root: Path, document: Path, line_text: str, line: int) -> list[Issue]:
    issues: list[Issue] = []
    for match in NPM_RUN_RE.finditer(line_text):
        script = match.group("script")
        directory = match.group("directory")
        if directory:
            package_path = root / directory / "package.json"
            if script not in _package_scripts(package_path):
                issues.append(
                    Issue(document, line, f"npm script is not defined in {directory}: {script}")
                )
            continue

        package_paths = [root / "package.json", root / "frontend" / "package.json"]
        if not any(script in _package_scripts(path) for path in package_paths):
            issues.append(Issue(document, line, f"npm script is not defined: {script}"))
    return issues


def _check_python_command(root: Path, document: Path, line_text: str, line: int) -> list[Issue]:
    issues: list[Issue] = []
    for match in PYTHON_SCRIPT_RE.finditer(line_text):
        script_path = root / "scripts" / match.group("script")
        if not script_path.is_file():
            issues.append(
                Issue(document, line, f"Python script does not exist: {match.group('script')}")
            )
    return issues


def check_documents(root: Path, paths: list[str] | None = None) -> list[Issue]:
    """Return invalid local links and command references in selected documents."""
    issues: list[Issue] = []
    for document in _documents(root, paths):
        try:
            lines = document.read_text(encoding="utf-8").splitlines()
        except OSError as exc:
            issues.append(Issue(document, 1, f"cannot read document: {exc}"))
            continue

        for line_number, line_text in enumerate(lines, start=1):
            for match in LOCAL_LINK_RE.finditer(line_text):
                issue = _check_local_link(root, document, match.group(1), line_number)
                if issue:
                    issues.append(issue)
            issues.extend(_check_npm_command(root, document, line_text, line_number))
            issues.extend(_check_python_command(root, document, line_text, line_number))
    return issues


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "paths",
        nargs="*",
        help=(
            "repository-relative Markdown files or directories; defaults to "
            "README.md and docs"
        ),
    )
    args = parser.parse_args(argv)

    root = Path(__file__).resolve().parents[2]
    issues = check_documents(root, args.paths or None)
    if issues:
        for issue in issues:
            print(issue, file=sys.stderr)
        print(f"Documentation target check failed: {len(issues)} issue(s)", file=sys.stderr)
        return 1

    print(
        f"Documentation target check passed for "
        f"{len(_documents(root, args.paths or None))} document(s)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
