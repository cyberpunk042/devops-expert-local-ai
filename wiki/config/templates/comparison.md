---
title: "{{title}}"
type: comparison
domain: {{domain}}
status: synthesized
confidence: medium
maturity: seed
created: {{date}}
updated: {{date}}
sources: []
tags: []
---

# {{title}}

## Summary

<!-- 2-3 sentences: what is being compared, and the headline conclusion.
     MIN 30 words. State the recommendation upfront — don't bury the lede.
     
     EXAMPLE: "A direct comparison of Karpathy's LLM Wiki Pattern against traditional
     Retrieval-Augmented Generation (RAG). The wiki approach uses structured markdown
     with explicit interlinks that the LLM navigates by reading indexes and following
     links. Traditional RAG uses embedding models and vector similarity to retrieve
     chunks on every query. At small to medium scale (<200 pages), the wiki wins on
     simplicity, cost, and relationship quality. At enterprise scale, RAG remains
     necessary."
     
     EXAMPLE: "OpenArms uses hooks-based enforcement (4 hooks, 215 lines, solo agent)
     while OpenFleet uses immune-system enforcement (30s doctor cycle, fleet agents).
     Both achieve near-zero process violations through infrastructure, but at different
     scales. The choice depends on your identity profile: solo agent projects need
     hooks; fleet projects need immune systems." -->

## Comparison Matrix

<!-- The core table. Columns = alternatives being compared. Rows = evaluation criteria.
     STYLING: Wrap in > [!abstract] Comparison Matrix.
     Use consistent scoring (✓/✗, High/Med/Low, or specific data points).
     
     EXAMPLE (from LLM Wiki vs RAG):
     > [!abstract] Comparison Matrix
     > | Criteria | LLM Wiki Pattern | Traditional RAG | Hybrid Search (v2) |
     > |----------|-----------------|----------------|-------------------|
     > | Retrieval mechanism | Index navigation + link following | Cosine similarity over vector embeddings | BM25 + vector + graph traversal |
     > | Infrastructure required | None (markdown files only) | Embedding model + vector database + chunking pipeline | Full stack |
     > | Setup time | 5 minutes | Hours to days | Days to weeks |
     > | Scale ceiling | ~200 pages / ~500K words | Millions of documents | Designed for scaling past 200 pages |
     > | Multi-hop reasoning | Excellent — explicit typed relationship links | Poor — chunks are decontextualized | Good — graph traversal |
     > | Hallucination risk | Low (reads synthesized, curated pages) | Medium (chunk assembly may lose context) | Low (cross-stream validation) |
     
     EXAMPLE (from enforcement comparison):
     > [!abstract] Comparison Matrix
     > | Criterion | Hooks (OpenArms) | Immune System (OpenFleet) |
     > |-----------|-----------------|--------------------------|
     > | Scale | Solo agent | Fleet (multiple agents) |
     > | Detection latency | Instant (pre-execution) | 30s cycle |
     > | Implementation cost | ~215 lines, 4 hooks | ~2000 lines, doctor + quarantine |
     > | Stage violation rate | 0% (blocks before execution) | ~2% (detect + quarantine after) |
     -->

## Key Insights

<!-- What the matrix reveals. Not a restatement of cells — interpretation.
     What patterns emerge? What trade-offs are fundamental vs incidental?
     STYLING: If a key trade-off exists, wrap in > [!warning].
     
     EXAMPLE:
     > [!tip] Wiki compiles knowledge; RAG re-derives on every query
     > The wiki compiles knowledge once and keeps it current. RAG starts from zero
     > synthesis depth on every query; the wiki starts from the accumulated height
     > of all previous sessions.
     
     EXAMPLE:
     > [!warning] Scale boundary: ~200 pages / ~500K words
     > Below this, wiki navigation is cheaper and more accurate. Above this, vector
     > search becomes necessary. The boundary is not purely about page count — it is
     > about query frequency and context window size. -->

## Deep Analysis

<!-- Per-alternative deep analysis. Each alternative gets a ### subsection.
     Include: strengths, weaknesses, ideal use case, deal-breakers.
     STYLING: Use > [!tip] for "when to choose this option."
     Use > [!warning] for "when this option fails." -->

## Recommendation

<!-- Clear recommendation with rationale. Which option, for what context.
     STYLING: > [!success] with the recommendation statement.
     Include WHEN to choose each option — context matters more than a global winner.
     
     EXAMPLE:
     > [!success] Recommendation
     >
     > **Default choice:** LLM Wiki for any actively curated knowledge base under
     > 200 pages. Zero infrastructure, zero setup friction, and it compounds — every
     > session starts from accumulated synthesis height, not zero.
     >
     > **Choose LLM Wiki when:** Knowledge base < 200 pages, multi-hop reasoning
     > needed, infrastructure budget is zero, content changes frequently.
     > **Choose Traditional RAG when:** Millions of documents that cannot be curated
     > manually, queries are primarily single-hop factual lookups.
     > **Combine both when:** Wiki approaching 200 pages. Migration path is additive:
     > add LightRAG as a query layer without touching markdown files. -->

## Open Questions

<!-- What the comparison can't resolve. What would change the recommendation. -->

## Relationships

- COMPARES TO: {{alternative_1}}, {{alternative_2}}
