"""AICP wiki page linter — validates against wiki/config/wiki-schema.yaml.

Replaces the earlier structural stub. Operational scope (this version):
  - YAML frontmatter present and parseable
  - All `required_fields` from schema present
  - `type` matches an `enums.type` value (and similar for status, confidence, maturity, complexity)
  - First H1 in body matches `title` field
  - `## Summary` section exists with >=30 words
  - At least one relationship line ('- VERB: ...')
  - Skips templates/ subdirectory and *_index.md (indices are structural, not content)

Out of scope for this version (future work — see Step 9 + skills audit):
  - Per-type content thresholds (lesson needs >=3 evidence items, pattern needs
    >=2 instances, decision needs >=2 alternatives) — needs artifact-types.yaml
  - Relationship verb validation against an allowed verb list
  - Cross-page link resolution (do [[wikilinks]] target real pages?)
  - Maturity gate enforcement (seed -> growing requires 3+ relationships, etc.)

Usage:
    python3 -m tools.lint                      # validate all wiki/ pages
    python3 -m tools.lint path/to/page.md      # validate one page
    python3 -m tools.lint --json               # JSON output

Exit code: 0 if no errors, 1 if errors found.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:
    print("error: PyYAML required (install: pip install pyyaml)", file=sys.stderr)
    sys.exit(2)


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SCHEMA = REPO_ROOT / "wiki" / "config" / "wiki-schema.yaml"
DEFAULT_WIKI = REPO_ROOT / "wiki"
SUMMARY_MIN_WORDS = 30
FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*)$", re.DOTALL)
H1_RE = re.compile(r"^#\s+(.+?)\s*$", re.MULTILINE)
H2_RE = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)
RELATIONSHIP_RE = re.compile(r"^-\s+[A-Z_]+:", re.MULTILINE)


@dataclass
class LintResult:
    file: Path
    errors: list[dict[str, str]] = field(default_factory=list)
    warnings: list[dict[str, str]] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return not self.errors

    def add_error(self, code: str, message: str, field_name: str | None = None) -> None:
        entry = {"code": code, "message": message}
        if field_name:
            entry["field"] = field_name
        self.errors.append(entry)

    def add_warning(self, code: str, message: str, field_name: str | None = None) -> None:
        entry = {"code": code, "message": message}
        if field_name:
            entry["field"] = field_name
        self.warnings.append(entry)


def parse_frontmatter(text: str) -> tuple[dict[str, Any] | None, str]:
    match = FRONTMATTER_RE.match(text)
    if not match:
        return None, text
    try:
        meta = yaml.safe_load(match.group(1)) or {}
    except yaml.YAMLError:
        return None, match.group(2)
    return meta, match.group(2)


def lint_page(page_path: Path, schema: dict[str, Any]) -> LintResult:
    result = LintResult(file=page_path)
    text = page_path.read_text(encoding="utf-8")
    meta, body = parse_frontmatter(text)

    if meta is None:
        result.add_error("no_frontmatter", "Missing or unparseable YAML frontmatter")
        return result

    for required in schema.get("required_fields", []):
        if required not in meta:
            result.add_error("missing_required_field", f"Required field '{required}' is missing", required)

    enums = schema.get("enums", {})
    for field_name, allowed_values in enums.items():
        if field_name in meta and isinstance(allowed_values, list):
            value = meta[field_name]
            if value not in allowed_values:
                result.add_error(
                    "invalid_enum_value",
                    f"Field '{field_name}' value '{value}' not in {allowed_values[:5]}{'...' if len(allowed_values) > 5 else ''}",
                    field_name,
                )

    title_field = meta.get("title")
    if title_field:
        h1_match = H1_RE.search(body)
        if not h1_match:
            result.add_error("no_h1", "Body has no H1 heading")
        else:
            h1 = h1_match.group(1).strip()
            normalized_title = str(title_field).strip().strip('"').strip("'")
            if h1 != normalized_title:
                result.add_warning(
                    "title_h1_mismatch",
                    f"Frontmatter title '{normalized_title}' does not match H1 '{h1}'",
                    "title",
                )

    # Index pages get lighter checks (no Summary requirement, no relationships requirement)
    page_type = meta.get("type")
    is_index = page_type == "index" or page_path.name.endswith("_index.md") or page_path.stem == "_index"

    if not is_index:
        h2_matches = H2_RE.findall(body)
        if "Summary" not in h2_matches:
            result.add_error("missing_summary", "Body missing '## Summary' section")
        else:
            summary_text = _extract_section(body, "Summary")
            if summary_text is not None and len(summary_text.split()) < SUMMARY_MIN_WORDS:
                result.add_error(
                    "summary_too_short",
                    f"Summary has {len(summary_text.split())} words; minimum is {SUMMARY_MIN_WORDS}",
                )

        rel_count = len(RELATIONSHIP_RE.findall(body))
        if rel_count == 0:
            result.add_warning(
                "no_relationships",
                "Body has no relationship lines (expected '- VERB: target' format under '## Relationships')",
            )

    return result


def _extract_section(body: str, heading: str) -> str | None:
    pattern = re.compile(
        rf"^##\s+{re.escape(heading)}\s*$\n(.*?)(?=^##\s|\Z)",
        re.MULTILINE | re.DOTALL,
    )
    match = pattern.search(body)
    if not match:
        return None
    section = match.group(1).strip()
    section = re.sub(r"```.*?```", " ", section, flags=re.DOTALL)
    section = re.sub(r"<!--.*?-->", " ", section, flags=re.DOTALL)
    return section


def find_wiki_pages(root: Path) -> list[Path]:
    skip_dirs = {"templates", "00_inbox"}  # templates are scaffolds; 00_inbox is intentionally rough
    pages: list[Path] = []
    for path in sorted(root.rglob("*.md")):
        relative = path.relative_to(root).parts
        if any(part in skip_dirs for part in relative):
            continue
        pages.append(path)
    return pages


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("paths", nargs="*", help="Specific files to lint (default: all wiki/ pages)")
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA), help=f"Schema file (default: {DEFAULT_SCHEMA})")
    parser.add_argument("--wiki-root", default=str(DEFAULT_WIKI), help=f"Wiki root (default: {DEFAULT_WIKI})")
    parser.add_argument("--json", action="store_true", help="JSON output")
    parser.add_argument("--include-inbox", action="store_true", help="Lint 00_inbox pages too (default: skipped)")
    args = parser.parse_args(argv)

    schema_path = Path(args.schema)
    if not schema_path.exists():
        print(f"error: schema not found at {schema_path}", file=sys.stderr)
        return 2
    schema = yaml.safe_load(schema_path.read_text(encoding="utf-8")) or {}

    if args.paths:
        targets = [Path(p) for p in args.paths]
    else:
        wiki_root = Path(args.wiki_root)
        if not wiki_root.exists():
            print(f"error: wiki root not found at {wiki_root}", file=sys.stderr)
            return 2
        targets = find_wiki_pages(wiki_root)
        if args.include_inbox:
            for inbox in wiki_root.rglob("00_inbox"):
                targets.extend(sorted(inbox.glob("*.md")))

    if not targets:
        if args.json:
            print(json.dumps({"summary": {"total": 0, "passed": 0, "failed": 0}, "results": []}))
        else:
            print("No pages found to lint")
        return 0

    results = [lint_page(p, schema) for p in targets]
    passed = sum(1 for r in results if r.passed)
    failed = len(results) - passed

    if args.json:
        print(
            json.dumps(
                {
                    "summary": {"total": len(results), "passed": passed, "failed": failed},
                    "results": [
                        {"file": str(r.file), "errors": r.errors, "warnings": r.warnings}
                        for r in results
                    ],
                },
                indent=2,
            )
        )
    else:
        for result in results:
            if result.errors or result.warnings:
                rel = result.file.relative_to(REPO_ROOT) if REPO_ROOT in result.file.parents else result.file
                print(f"\n{rel}")
                for error in result.errors:
                    field = f"[{error.get('field', '?')}] " if error.get("field") else ""
                    print(f"  ERROR  {error['code']}: {field}{error['message']}")
                for warning in result.warnings:
                    field = f"[{warning.get('field', '?')}] " if warning.get("field") else ""
                    print(f"  WARN   {warning['code']}: {field}{warning['message']}")
        print(f"\nSummary: {passed}/{len(results)} passed, {failed} failed")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
