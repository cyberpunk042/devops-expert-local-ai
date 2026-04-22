---
title: "AICP acknowledges 2026-04-22 K2.6 + post-Anthropic directive from second brain"
type: note
domain: log
note_type: directive
status: synthesized
confidence: high
created: 2026-04-22
updated: 2026-04-22
sources:
  - id: brain-directive
    type: wiki
    file: ~/devops-solutions-research-wiki/raw/notes/2026-04-22-directive-kimi-k2-6-ingest.md
    description: "Brain-side verbatim operator directive on K2.6 ingest + 64GB RAM hardware update"
  - id: brain-post-anthropic-directive
    type: wiki
    file: ~/devops-solutions-research-wiki/raw/notes/2026-04-22-directive-post-anthropic-self-autonomous-plan.md
    description: "Brain-side verbatim operator directive on post-Anthropic self-autonomous plan"
  - id: brain-milestone
    type: wiki
    file: ~/devops-solutions-research-wiki/wiki/backlog/milestones/post-anthropic-self-autonomous-stack.md
    description: "Brain-side milestone: 6 epics, P0, target 2026-04-27"
  - id: brain-e011
    type: wiki
    file: ~/devops-solutions-research-wiki/wiki/backlog/epics/pre-milestone/E011-routing-integration-aicp-tiers.md
    description: "Brain-side AICP-specific epic: 5 modules, 15-20 tasks"
  - id: brain-k2-6-synthesis
    type: wiki
    file: ~/devops-solutions-research-wiki/wiki/sources/tools-integration/src-kimi-k2-6-moonshot-agent-swarm.md
    description: "Brain-side source synthesis on Kimi K2.6 (MIT-licensed, 1T/32B MoE, agentic frontier, ~6-7× cheaper than Opus via OpenRouter)"
tags: [contributed, directive, k2-6, kimi, openrouter, post-anthropic, aicp, milestone, e011, hard-deadline]
contributed_by: "aicp-self"
contribution_source: "~/devops-expert-local-ai"
contribution_date: 2026-04-22
contribution_status: pending-review
contribution_reason: "AICP-side acknowledgement of brain-assigned work — captures the new strategic direction and pointers to authoritative brain backlog. Brain remains the source of truth for milestone/epic/module detail; this log entry is AICP's local awareness anchor."
---

# AICP acknowledges 2026-04-22 K2.6 + post-Anthropic directive from second brain

## Summary

On 2026-04-22 the operator landed two coordinated directives in the second brain that reshape AICP's mission:

1. **Ingest Kimi K2.6** as a primary inference tier (cloud via OpenRouter at ~$0.80/$3.50 per M tokens, ~6-7× cheaper than Opus; local via KTransformers disk-offload once 64 GB RAM lands).
2. **Build a post-Anthropic self-autonomous AI stack** by 2026-04-27 (5-day deadline driven by the operator's Claude Code subscription transition). The principle is harness-neutral, vendor-neutral, no-quality-compromise.

The brain authored a P0 milestone (`post-anthropic-self-autonomous-stack`) coordinating 6 epics. **E011 — Routing Integration (AICP Tiers Updated for K2.6 + Local Stack)** is the AICP-specific epic — 5 modules, 15-20 tasks, mirrors AICP's existing 4-tier router into a 7-tier stack with K2.6-OpenRouter as the new default for agentic/coding workloads. Claude/Anthropic gets demoted to hard-gated last-resort fallback.

This log entry is AICP's acknowledgement that the work landed. The brain holds the authoritative milestone/epic/module/task pages — AICP does NOT duplicate them. AICP's own backlog gets a milestone-level + epic-level placeholder pointing at the brain.

## Strategic shift captured

| Dimension | Before (pre-2026-04-22) | After (this directive) |
|-----------|-------------------------|------------------------|
| Primary cloud tier for agentic/coding | Claude Opus 4.7 via Anthropic API | **Kimi K2.6 via OpenRouter** ($0.80/$3.50 per M) |
| Anthropic role | Default cloud escalation target | Hard-gated last-resort fallback only |
| Local frontier tier | Qwen3-30B-A3B (dual-GPU profile) | + **Kimi K2.6 Q2 via KTransformers** (340 GB GGUF on RAID 0 NVMe swap) |
| Router tier count | 4 (local → fleet → openrouter → claude) | **7** (adds K2.6-OpenRouter, K2.6-local, demotes Claude) |
| Hardware ceiling | 19 GB VRAM (RTX 2080 + 2080 Ti) | + **64 GB RAM + RAID 0 NVMe swap** (incoming ~1 day) |
| Cost target | $0 local + Anthropic-tier cloud | $0 local + ~6-7× cheaper agentic cloud |
| Deadline | None (steady evolution) | **2026-04-27** (Claude Code subscription transition) |

## What this means for AICP code

E011's scope (per brain authoritative epic doc):

| Module | Delivers (AICP code surface) |
|--------|------------------------------|
| E011-m001 | AICP config: 7-tier stack with K2.6-cheap-online as primary agentic |
| E011-m002 | Python adapter wrapping OpenRouter K2.6 as an AICP backend (`aicp/backends/k2_6_openrouter.py` likely) |
| E011-m003 | Python adapter wrapping KTransformers local K2.6 (`aicp/backends/k2_6_local.py` likely) |
| E011-m004 | Per-backend circuit breaker tuning + fallback chain doc (extends existing `aicp/core/circuit_breaker.py`) |
| E011-m005 | Routing-split metric emission + weekly review ritual doc |

AICP's existing infrastructure ALREADY supports much of this:
- **4-tier router** (`aicp/core/router.py`) is the foundation — needs tier-count extension, not rewrite
- **Profile system** (`aicp/core/profiles.py`, 9 profiles, 49 tests) — new K2.6 profile slots in
- **Per-backend circuit breaker** (`aicp/core/circuit_breaker.py`) — pattern-promoted to growing-tier 2026-04-22; new backends just register
- **Per-day JSONL DLQ** (`aicp/core/dlq.py`) — pattern-promoted; new backends inherit
- **OpenAI-compatible backend pattern** (`aicp/backends/localai.py` + `claude_code.py`) — K2.6 OpenRouter slots in via OpenAI-compat shape
- **Profile-as-coordination-bundle** pattern handles the cross-cutting concern of "which model + which thresholds + which Docker envs"

The work is **integration**, not greenfield. The 5-day timeline is plausible because the architectural foundations are in place.

## Where AICP's local backlog reflects this

- **Milestone placeholder**: `wiki/backlog/milestones/post-anthropic-self-autonomous-stack.md` — points to brain authoritative
- **Epic placeholder**: `wiki/backlog/epics/_index.md` — E011 added to "Active" with brain pointer
- **Module/task detail**: stays in brain at `~/devops-solutions-research-wiki/wiki/backlog/{modules,tasks}/` — AICP does NOT duplicate

## Verbatim operator words (captured from brain directives)

> "I dont want to have to deal with Anthropic and Claude and Opus in the future......"

> "We will personally stay on Claude Code for now but evolve our reasoning to be compatible with OpenCode or other real community service that wont lower quality or service with time."

> "Every .agents or .gemini or .claude can be treated as equivalent to us. Every ecosystem needs one and to us it's the same thing. We don't need to lower ourselves to lower standards — even if we need to inject our sauce to elevate it we will."

> "In 5 days everything will most likely be happening on this computer with the 19GB VRAM and the 1TB NVME SSD for AirLLM and so on... we will make this workstation self-autonomous and also integrate the OpenRouter like the rest."

> "I also hear about this KIMI thing that would even highly beat Opus 4.7 and 5.4 now... Lets do our research properly"

> "Soon I will be at 64RAM (1 day) and we can have at least the same amount as swap on my RAID 0 NVME ssds"

## Relationships

- DERIVED FROM: `~/devops-solutions-research-wiki/raw/notes/2026-04-22-directive-kimi-k2-6-ingest.md`
- DERIVED FROM: `~/devops-solutions-research-wiki/raw/notes/2026-04-22-directive-post-anthropic-self-autonomous-plan.md`
- IMPLEMENTS: `~/devops-solutions-research-wiki/wiki/backlog/epics/pre-milestone/E011-routing-integration-aicp-tiers.md`
- BUILDS ON: `wiki/patterns/02_reviewed/per-backend-circuit-breaker-with-failover-chain.md`
- BUILDS ON: `wiki/patterns/02_reviewed/profile-as-coordination-bundle.md`
- BUILDS ON: `wiki/decisions/02_reviewed/4-tier-router-with-profiles-over-hardcoded-routing.md`
- BUILDS ON: `wiki/decisions/02_reviewed/localai-over-ollama-vllm-for-multi-model-orchestration.md`
- RELATES TO: `wiki/log/aicp-stage-3-hardware-unlocked-2026-04-17-—-19gb-vram-dual-g.md` (Stage 3 19GB VRAM unlock, predecessor)
