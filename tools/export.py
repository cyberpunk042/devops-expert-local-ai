"""AICP wiki export pipeline — transforms wiki pages for sister projects.

Reads wiki/config/export-profiles.yaml and applies the named transform to all
matching pages, writing to the configured output_dir. Each profile defines:
  - filters (min_confidence, min_status, require_tags_any, etc.)
  - transforms (frontmatter handling, type_map, status_map, add_metadata)
  - output_dir

This implements the OPERATIONAL Tier 4 piece for export. Tier 4 STRUCTURAL was
satisfied earlier by creating wiki/config/export-profiles.yaml; this is the
runtime that consumes it.

Usage:
    python3 -m tools.export --list                       # list available profiles
    python3 -m tools.export --profile second-brain --dry-run
    python3 -m tools.export --profile second-brain       # write to target dir
    python3 -m tools.export --profile openfleet --dry-run

Exit code: 0 if success or dry-run, 1 if filter rejected all candidates, 2 if config error.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:
    print("error: PyYAML required (install: pip install pyyaml)", file=sys.stderr)
    sys.exit(2)


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PROFILES = REPO_ROOT / "wiki" / "config" / "export-profiles.yaml"
DEFAULT_WIKI = REPO_ROOT / "wiki"
SCAN_LAYERS = ("lessons", "patterns", "decisions")
CONFIDENCE_RANK = {"low": 0, "medium": 1, "high": 2, "authoritative": 3}
STATUS_RANK = {
    "raw": 0, "draft": 1, "processing": 2, "active": 3,
    "in-progress": 4, "review": 5, "synthesized": 6, "verified": 7, "done": 8,
}
FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*)$", re.DOTALL)


def parse_frontmatter(text: str) -> tuple[dict[str, Any] | None, str]:
    match = FRONTMATTER_RE.match(text)
    if not match:
        return None, text
    try:
        meta = yaml.safe_load(match.group(1)) or {}
    except yaml.YAMLError:
        return None, match.group(2)
    return meta, match.group(2)


def load_profiles(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"export-profiles.yaml not found at {path}")
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def find_candidate_pages(wiki_root: Path) -> list[Path]:
    pages: list[Path] = []
    for layer in SCAN_LAYERS:
        layer_dir = wiki_root / layer
        if not layer_dir.exists():
            continue
        for path in sorted(layer_dir.rglob("*.md")):
            if path.name == "_index.md":
                continue
            if "00_inbox" in path.parts:
                continue  # inbox is intentionally rough; skip from export
            pages.append(path)
    return pages


def passes_filters(meta: dict[str, Any], filters: dict[str, Any]) -> tuple[bool, str | None]:
    min_confidence = filters.get("min_confidence")
    if min_confidence:
        page_conf = meta.get("confidence", "low")
        if CONFIDENCE_RANK.get(page_conf, 0) < CONFIDENCE_RANK.get(min_confidence, 0):
            return False, f"confidence {page_conf} < {min_confidence}"

    min_status = filters.get("min_status")
    if min_status:
        page_status = meta.get("status", "raw")
        if STATUS_RANK.get(page_status, 0) < STATUS_RANK.get(min_status, 0):
            return False, f"status {page_status} < {min_status}"

    excluded = set(filters.get("exclude_domains", []) or [])
    if excluded and meta.get("domain") in excluded:
        return False, f"domain {meta.get('domain')} is excluded"

    domain_allowlist = set(filters.get("domains", []) or [])
    if domain_allowlist and meta.get("domain") not in domain_allowlist:
        return False, f"domain {meta.get('domain')} not in allowlist {sorted(domain_allowlist)}"

    require_tags_any = set(filters.get("require_tags_any", []) or [])
    if require_tags_any:
        page_tags = set(meta.get("tags") or [])
        if not (require_tags_any & page_tags):
            return False, f"tags {sorted(page_tags)} do not intersect required {sorted(require_tags_any)}"

    return True, None


def transform_frontmatter(meta: dict[str, Any], transforms: dict[str, Any]) -> tuple[dict[str, Any] | None, str]:
    handling = transforms.get("frontmatter", "preserve")
    type_map = transforms.get("type_map", {}) or {}
    status_map = transforms.get("status_map", {}) or {}
    add_metadata = transforms.get("add_metadata", []) or []

    out_meta = dict(meta)
    type_mapped = type_map.get(meta.get("type"), meta.get("type"))
    status_mapped = status_map.get(meta.get("status"), meta.get("status"))
    if type_mapped is not None:
        out_meta["type"] = type_mapped
    if status_mapped is not None:
        out_meta["status"] = status_mapped

    placeholders = {
        "type_mapped": type_mapped or meta.get("type", ""),
        "status_mapped": status_mapped or meta.get("status", ""),
        "updated": meta.get("updated", ""),
        "created": meta.get("created", ""),
        "title": meta.get("title", ""),
        "domain": meta.get("domain", ""),
        "source_urls": ", ".join(
            s.get("url", s.get("file", "")) for s in (meta.get("sources") or []) if isinstance(s, dict)
        ),
    }

    additions: list[tuple[str, str]] = []
    for item in add_metadata:
        if not isinstance(item, dict):
            continue
        key = item.get("key")
        value_template = item.get("value", "")
        rendered = re.sub(
            r"\{(\w+)\}",
            lambda m: str(placeholders.get(m.group(1), m.group(0))),
            value_template,
        )
        additions.append((key, rendered))

    if handling == "preserve":
        for key, value in additions:
            out_meta[key] = value
        prelude = "---\n" + yaml.safe_dump(out_meta, sort_keys=False, allow_unicode=True) + "---\n\n"
        return out_meta, prelude

    if handling == "strip":
        prelude = ""
        if additions:
            prelude += "\n".join(f"**{key}:** {value}" for key, value in additions) + "\n\n"
        return None, prelude

    if handling == "markdown-headers":
        prelude_lines: list[str] = []
        for key, value in additions:
            prelude_lines.append(f"**{key}:** {value}")
        prelude = "\n".join(prelude_lines) + ("\n\n" if prelude_lines else "")
        return None, prelude

    raise ValueError(f"unknown frontmatter handling: {handling}")


def export_page(page_path: Path, transforms: dict[str, Any], output_dir: Path, wiki_root: Path) -> Path:
    text = page_path.read_text(encoding="utf-8")
    meta, body = parse_frontmatter(text)
    if meta is None:
        meta = {}
        body = text

    _, prelude = transform_frontmatter(meta, transforms)

    relative = page_path.relative_to(wiki_root)
    target_path = output_dir / relative
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text(prelude + body, encoding="utf-8")
    return target_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--profile", help="Export profile name (from wiki/config/export-profiles.yaml)")
    parser.add_argument("--list", action="store_true", help="List available profiles")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be exported, don't write")
    parser.add_argument("--profiles-config", default=str(DEFAULT_PROFILES))
    parser.add_argument("--wiki-root", default=str(DEFAULT_WIKI))
    args = parser.parse_args(argv)

    profiles_path = Path(args.profiles_config)
    try:
        profiles = load_profiles(profiles_path)
    except FileNotFoundError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    if args.list or not args.profile:
        print(f"Available export profiles in {profiles_path}:")
        for name, conf in profiles.items():
            description = conf.get("description", "(no description)") if isinstance(conf, dict) else "(invalid)"
            target = conf.get("output_dir", "?") if isinstance(conf, dict) else "?"
            print(f"  {name:20s}  {description}")
            print(f"  {' '*20}  -> {target}")
        return 0

    profile = profiles.get(args.profile)
    if not profile:
        print(f"error: profile '{args.profile}' not found in {profiles_path}", file=sys.stderr)
        print(f"available: {sorted(profiles)}", file=sys.stderr)
        return 2

    wiki_root = Path(args.wiki_root)
    output_dir = Path(profile.get("output_dir", "")).expanduser()
    if not output_dir.is_absolute():
        output_dir = (wiki_root.parent / output_dir).resolve()

    filters = profile.get("filters", {}) or {}
    transforms = profile.get("transforms", {}) or {}

    pages = find_candidate_pages(wiki_root)
    print(f"AICP wiki export — profile '{args.profile}'")
    print(f"  Source: {wiki_root}")
    print(f"  Target: {output_dir}")
    print(f"  Candidates scanned: {len(pages)}")
    print()

    accepted: list[tuple[Path, Path | None]] = []
    rejected: list[tuple[Path, str]] = []
    for page in pages:
        text = page.read_text(encoding="utf-8")
        meta, _ = parse_frontmatter(text)
        if meta is None:
            rejected.append((page, "no frontmatter"))
            continue
        ok, reason = passes_filters(meta, filters)
        if not ok:
            rejected.append((page, reason or "filter rejected"))
            continue
        if args.dry_run:
            accepted.append((page, None))
        else:
            target = export_page(page, transforms, output_dir, wiki_root)
            accepted.append((page, target))

    if accepted:
        print(f"Accepted ({len(accepted)}):")
        for src, dst in accepted:
            rel_src = src.relative_to(REPO_ROOT) if REPO_ROOT in src.parents else src
            if dst is None:
                print(f"  {rel_src}  (DRY RUN, would write)")
            else:
                print(f"  {rel_src}  -> {dst}")
        print()

    if rejected:
        print(f"Rejected ({len(rejected)}):")
        for src, reason in rejected:
            rel_src = src.relative_to(REPO_ROOT) if REPO_ROOT in src.parents else src
            print(f"  {rel_src}  ({reason})")
        print()

    if not accepted:
        print("No pages passed filters; nothing to export.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
