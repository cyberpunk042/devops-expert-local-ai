# AICP Wiki Lint — STRUCTURAL STUB

# Honest reporting: this file exists to satisfy second-brain Tier 3 STRUCTURAL
# compliance for "quality/validation tooling." Operational wiki linting (frontmatter
# schema validation against wiki/config/wiki-schema.yaml, content thresholds per
# page type, relationship verb consistency) is pending — tracked under Step 9 of
# the adoption plan.
#
# AICP code linting uses ruff (see Makefile + pyproject.toml). This stub is
# specifically for the wiki/ subtree (wiki pages authored against the second
# brain standards).
#
# Per second brain's "Structural Compliance Is Not Operational Compliance"
# (wiki/lessons/01_drafts/structural-compliance-is-not-operational-compliance.md),
# adopters should report both dimensions separately. AICP currently:
#   - Tier 3 STRUCTURAL (lint): this stub
#   - Tier 3 OPERATIONAL (lint): pending — needs real schema validator for wiki/
#
# Until operational, validate wiki pages against the second brain directly:
#   cd ~/devops-solutions-research-wiki && python3 -m tools.validate <path>

from __future__ import annotations

import sys


def main() -> int:
    print("AICP wiki lint.py is a structural stub.", file=sys.stderr)
    print("Operational wiki page validation is pending (see Step 9).", file=sys.stderr)
    print("For canonical wiki validation, see the second brain's tools/validate.py.", file=sys.stderr)
    print("", file=sys.stderr)
    print("Note: AICP code linting is via ruff (separate from wiki linting):", file=sys.stderr)
    print("  ruff check aicp/ tests/", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
