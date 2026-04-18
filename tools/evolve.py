"""AICP wiki evolution scorer — ranks pages for promotion.

Replaces the earlier structural stub. Operational scope (this version):
  - Score every page in wiki/{lessons,patterns,decisions}/ across 6 signals
  - Rank candidates for maturity promotion (00_inbox -> 01_drafts -> 02_reviewed -> ...)
  - Honest reporting: shows the signal breakdown so the operator can trust the rank

Signals (weights from second brain's tools/evolve.py, adapted for AICP scale):
  1. Cross-source convergence  (0.30) — derived_from + sources count
  2. Relationship hub          (0.20) — outbound + inbound relationship density
  3. Evidence density          (0.20) — evidence items / line count
  4. Maturity gap              (0.15) — pages stuck at lower maturity than their evidence supports
  5. Staleness                 (0.10) — long-untouched pages risk drift
  6. Tag co-occurrence         (0.05) — generic-tag noise filter (down from 0.25 per
                                        the brain's tuning history — see Knowledge
                                        Evolution Standards)

Out of scope for this version (future work):
  - Generation (LLM-driven page assembly from scored candidates)
  - Maturity promotion (auto-move from 00_inbox to 01_drafts after review)
  - PageRank-style relationship-aware scoring
  - Cross-page link resolution

Usage:
    python3 -m tools.evolve --score                   # rank all pages, top 10
    python3 -m tools.evolve --score --top 5
    python3 -m tools.evolve --score --type lesson     # filter by page type
    python3 -m tools.evolve --score --json            # JSON output

Exit code: 0 always (scoring is non-blocking; promotion decisions are human).
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:
    print("error: PyYAML required (install: pip install pyyaml)", file=sys.stderr)
    sys.exit(2)


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_WIKI = REPO_ROOT / "wiki"
KNOWLEDGE_LAYERS = ("lessons", "patterns", "decisions")
MATURITY_RANK = {"seed": 0, "growing": 1, "mature": 2, "canonical": 3}
GENERIC_TAGS = {
    "concept", "knowledge", "wiki", "aicp", "model", "spine",
    "index", "draft", "inbox", "contributed",
}
SIGNAL_WEIGHTS = {
    "cross_source_convergence": 0.30,
    "relationship_hub": 0.20,
    "evidence_density": 0.20,
    "maturity_gap": 0.15,
    "staleness": 0.10,
    "tag_cooccurrence": 0.05,
}
FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*)$", re.DOTALL)
RELATIONSHIP_RE = re.compile(r"^-\s+([A-Z_]+):", re.MULTILINE)
EVIDENCE_BULLET_RE = re.compile(r"^\s*\d+\.\s+\*\*", re.MULTILINE)


@dataclass
class PageScore:
    file: Path
    page_type: str
    maturity: str
    score: float
    signals: dict[str, float] = field(default_factory=dict)


def parse_frontmatter(text: str) -> tuple[dict[str, Any] | None, str]:
    match = FRONTMATTER_RE.match(text)
    if not match:
        return None, text
    try:
        meta = yaml.safe_load(match.group(1)) or {}
    except yaml.YAMLError:
        return None, match.group(2)
    return meta, match.group(2)


def find_knowledge_pages(root: Path) -> list[Path]:
    pages: list[Path] = []
    for layer in KNOWLEDGE_LAYERS:
        layer_dir = root / layer
        if not layer_dir.exists():
            continue
        for path in sorted(layer_dir.rglob("*.md")):
            if path.name == "_index.md":
                continue
            pages.append(path)
    return pages


def score_page(page_path: Path, all_pages_meta: dict[Path, dict[str, Any]]) -> PageScore:
    text = page_path.read_text(encoding="utf-8")
    meta, body = parse_frontmatter(text)
    if meta is None:
        return PageScore(file=page_path, page_type="?", maturity="seed", score=0.0)

    page_type = meta.get("type", "?")
    maturity = meta.get("maturity", "seed")

    signals: dict[str, float] = {}

    derived_from_count = len(meta.get("derived_from") or [])
    sources_count = len(meta.get("sources") or [])
    signals["cross_source_convergence"] = min(1.0, (derived_from_count + sources_count) / 5.0)

    outbound = len(RELATIONSHIP_RE.findall(body))
    inbound = sum(
        1
        for other_path, other_meta in all_pages_meta.items()
        if other_path != page_path
        and (page_path.stem in str(other_meta) or page_path.stem in (other_meta.get("derived_from") or []))
    )
    signals["relationship_hub"] = min(1.0, (outbound + inbound) / 8.0)

    evidence_items = len(EVIDENCE_BULLET_RE.findall(body))
    line_count = max(50, body.count("\n"))
    signals["evidence_density"] = min(1.0, evidence_items / max(3.0, line_count / 80.0))

    expected_evidence_per_maturity = {"seed": 1, "growing": 3, "mature": 5, "canonical": 8}
    maturity_threshold = expected_evidence_per_maturity.get(maturity, 1)
    if evidence_items >= maturity_threshold * 1.5:
        signals["maturity_gap"] = 1.0
    elif evidence_items >= maturity_threshold:
        signals["maturity_gap"] = 0.5
    else:
        signals["maturity_gap"] = 0.0

    updated_str = meta.get("updated") or meta.get("created")
    if updated_str:
        try:
            if isinstance(updated_str, dt.date):
                updated_date = updated_str
            else:
                updated_date = dt.date.fromisoformat(str(updated_str))
            days_old = (dt.date.today() - updated_date).days
            signals["staleness"] = min(1.0, days_old / 90.0)
        except (ValueError, TypeError):
            signals["staleness"] = 0.0
    else:
        signals["staleness"] = 0.0

    tags = meta.get("tags") or []
    non_generic_tags = [t for t in tags if t.lower() not in GENERIC_TAGS]
    signals["tag_cooccurrence"] = min(1.0, len(non_generic_tags) / 5.0)

    score = sum(SIGNAL_WEIGHTS[s] * v for s, v in signals.items())
    return PageScore(file=page_path, page_type=page_type, maturity=maturity, score=score, signals=signals)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--score", action="store_true", help="Score and rank pages")
    parser.add_argument("--top", type=int, default=10, help="Top N candidates (default 10)")
    parser.add_argument("--type", help="Filter by page type (lesson, pattern, decision)")
    parser.add_argument("--maturity", help="Filter by maturity (seed, growing, mature, canonical)")
    parser.add_argument("--json", action="store_true", help="JSON output")
    parser.add_argument("--wiki-root", default=str(DEFAULT_WIKI), help=f"Wiki root (default: {DEFAULT_WIKI})")
    args = parser.parse_args(argv)

    if not args.score:
        parser.print_help()
        return 0

    wiki_root = Path(args.wiki_root)
    pages = find_knowledge_pages(wiki_root)
    if not pages:
        print(f"No knowledge pages found under {wiki_root}/{{lessons,patterns,decisions}}/")
        return 0

    all_pages_meta: dict[Path, dict[str, Any]] = {}
    for page in pages:
        text = page.read_text(encoding="utf-8")
        meta, _ = parse_frontmatter(text)
        if meta:
            all_pages_meta[page] = meta

    scores: list[PageScore] = [score_page(p, all_pages_meta) for p in pages]

    if args.type:
        scores = [s for s in scores if s.page_type == args.type]
    if args.maturity:
        scores = [s for s in scores if s.maturity == args.maturity]

    scores.sort(key=lambda s: s.score, reverse=True)
    top_scores = scores[: args.top]

    if args.json:
        print(
            json.dumps(
                {
                    "wiki_root": str(wiki_root),
                    "total_pages": len(pages),
                    "filters": {"type": args.type, "maturity": args.maturity},
                    "candidates": [
                        {
                            "file": str(s.file.relative_to(REPO_ROOT)),
                            "type": s.page_type,
                            "maturity": s.maturity,
                            "score": round(s.score, 3),
                            "signals": {k: round(v, 3) for k, v in s.signals.items()},
                        }
                        for s in top_scores
                    ],
                },
                indent=2,
            )
        )
    else:
        type_counts = Counter(s.page_type for s in scores)
        maturity_counts = Counter(s.maturity for s in scores)
        print(f"AICP wiki evolution scoring — {len(pages)} pages scanned, {len(scores)} after filter")
        print(f"  Types: {dict(type_counts)}")
        print(f"  Maturity: {dict(maturity_counts)}")
        print()
        print(f"Top {len(top_scores)} promotion candidates:")
        print()
        for i, s in enumerate(top_scores, 1):
            rel = s.file.relative_to(REPO_ROOT) if REPO_ROOT in s.file.parents else s.file
            print(f"  {i:2}. [{s.score:.3f}] {s.page_type}/{s.maturity}  {rel.name}")
            for sig, value in sorted(s.signals.items(), key=lambda x: -x[1]):
                if value > 0:
                    print(f"          {sig:30}  {value:.2f}  (weight {SIGNAL_WEIGHTS[sig]:.2f})")
            print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
