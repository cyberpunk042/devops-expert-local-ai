# Session Handoff — 2026-04-22 (resume on fresh Ubuntu 24.04)

> **Purpose**: bring a fresh session on a fresh machine fully online.
> **NOT a wiki page** — lives in `docs/`, not `wiki/`. Do not ingest.
> **Predecessor**: `docs/SESSION-2026-04-18.md` (read it for prior arc context).

## TL;DR — read this first

1. **Hard deadline**: **2026-04-27** (5 days from this handoff). PO's Claude Code subscription transition.
2. **Mission pivot**: post-Anthropic self-autonomous AI stack. Kimi K2.6 (Moonshot, MIT-licensed, 1T/32B-active MoE) replaces Opus as primary cloud agentic tier via OpenRouter (~6-7× cheaper). Anthropic demoted to last-resort fallback.
3. **Brain-assigned epic**: E011 — Routing Integration (5 modules, 15-20 tasks). AICP owns it. **Brain holds authoritative spec**, AICP holds local awareness anchors.
4. **Already shipped this session**: K2.6 callable as `aicp --backend k2_6_openrouter ...` (commit `dcf3d56`). Live verified — K2.6 self-identifies as Kimi from Moonshot.
5. **Hardware**: 64GB RAM landed. RAID 0 NVMe swap planned. 19GB VRAM (RTX 2080 8GB + RTX 2080 Ti 11GB) already operational.
6. **Brain location**: `~/devops-solutions-research-wiki/` — separate repo. Critical dependency. **Must be cloned alongside AICP on the fresh machine.**

---

## Critical context

### The mission (revised 2026-04-22)

**Original mission** (still valid as long arc): LocalAI independence — progressive offload from Claude to LocalAI across 5 stages. Stages 1-2 done; Stage 3 hardware unlocked 2026-04-17 (19GB VRAM); Stages 4-5 partial.

**New mission** (P0 critical-path, 5-day deadline): post-Anthropic self-autonomous stack. The brain authored the milestone + 6 epics on 2026-04-22 driven by these PO directives (verbatim, captured in `wiki/log/2026-04-22-k2-6-directive-and-post-anthropic-pivot.md`):

> "I dont want to have to deal with Anthropic and Claude and Opus in the future......"
>
> "We will personally stay on Claude Code for now but evolve our reasoning to be compatible with OpenCode or other real community service that wont lower quality or service with time."
>
> "In 5 days everything will most likely be happening on this computer with the 19GB VRAM and the 1TB NVME SSD for AirLLM and so on... we will make this workstation self-autonomous and also integrate the OpenRouter like the rest."
>
> "I also hear about this KIMI thing that would even highly beat Opus 4.7 and 5.4 now... Lets do our research properly"
>
> "Soon I will be at 64RAM (1 day) and we can have at least the same amount as swap on my RAID 0 NVME ssds"

### Strategic shift (5-day window)

| Tier | Before | After |
|------|--------|-------|
| Primary cloud agentic | Claude Opus 4.7 (Anthropic API) | **Kimi K2.6 (OpenRouter)** ~$0.60/$2.50 per M |
| Anthropic role | Default cloud escalation | Hard-gated last-resort fallback only |
| Local frontier | Qwen3-30B-A3B (dual-GPU) | + **K2.6 Q2 via KTransformers** (340GB GGUF on RAID 0 NVMe swap) |
| Router tier count | 4 (local → fleet → openrouter → claude) | **7** (adds K2.6-OpenRouter, K2.6-local; demotes Claude) |
| Hardware ceiling | 19GB VRAM | + **64GB RAM + RAID 0 NVMe** |
| Cost target | $0 local + Anthropic-tier cloud | $0 local + ~6-7× cheaper agentic cloud |

### Brain-assigned work for AICP (E011)

| Module | Status | Brain authoritative spec |
|--------|--------|--------------------------|
| **E011-m001** Tier definitions update (router refactor 4-tier→5-tier) | **pending** (next priority) | `~/devops-solutions-research-wiki/wiki/backlog/modules/e011-m001-tier-definitions-update.md` |
| **E011-m002** K2.6 OpenRouter backend adapter | **partial DONE** (commit `dcf3d56`) — operator opt-in works; auto-routing pending M001 | `e011-m002-k2-6-openrouter-backend-adapter.md` |
| **E011-m003** K2.6 local backend adapter (KTransformers) | pending — depends on E008 (operator-owned) | `e011-m003-k2-6-local-backend-adapter.md` |
| **E011-m004** Per-backend circuit breakers + fallback chain doc | pending — pattern already shipped, needs config tuning | `e011-m004-circuit-breakers-and-fallback-chain.md` |
| **E011-m005** Routing-split metric + weekly review ritual | pending | `e011-m005-routing-metric-and-review-ritual.md` |

**Cross-epic dependencies AICP cares about** (not AICP-owned):
- **E007** OpenRouter deadline de-risk — smoke tests PASSED 2026-04-22 (✓)
- **E008** Local K2.6 offline frontier tier (KTransformers + 340GB Q2 GGUF + benchmark)
- **E010** Storage and hardware (64GB RAM ✓ landed; /dev/sdd mount + RAID 0 swap pending)

---

## What this session shipped (2026-04-19 → 2026-04-22)

7 commits on branch `main`, all pushed-equivalent (single-operator repo):

| Commit | What |
|--------|------|
| `dcf3d56` | **feat(backends)**: K2.6 wired as callable AICP backend (E011-m002 partial). 5/5 tests passing, live verified. |
| `1df479d` | **feat(mission)**: acknowledge brain-assigned K2.6 + post-Anthropic pivot. CLAUDE.md mission rewritten, milestone + epic indexes updated, directive log captured. |
| `5d12307` | **docs(wiki)**: promote 4 foundational decisions seed→growing (4-tier-router, localai-over-ollama, pretooluse-hooks, skills-as-primary). |
| `475cf6e` | **docs(wiki)**: promote 2 architectural patterns seed→growing (three-permission-modes, profile-as-coordination-bundle). |
| `c1a2557` | **docs(wiki)**: promote 3 reliability patterns seed→growing (per-backend-circuit-breaker, per-day-jsonl-dlq, single-active-backend-lru). |
| `c876ac8` | **feat(skills)**: close Phase 3 skill rewrites — evolve-internationalize, evolve-plugin-system, feature-iterate, refactor-patterns. |
| `58730f3` | (predecessor session) Refactor infra skills. |

### Cumulative state metrics

| Dimension | Status |
|-----------|--------|
| Brain compliance | **Tier 4/4 STRUCTURAL** (`python3 -m tools.gateway compliance`) |
| Wiki pages | **23/23 passing lint** (`python3 -m tools.lint`) — 11 patterns/decisions promoted to `growing`, 8 still seed (intentionally), plus indexes + log entries |
| Maturity inventory | `{growing: 9, seed: 8}` of evolve-scored content pages |
| Skills | **84 total**, **43/84 (51%) Extension Standards compliant** (Phase 2: 17 + Phase 3: 20 + 6 new ops migration skills) |
| AICP code | 61 Python modules in `aicp/`, 95 test files, 1758+ tests |
| MCP audit | 21 of 64 tools deprecated (Phases 2+3); removal pending release-paced |
| Hooks | Layer A (R01-R04 universal safety) + Layer B (R05 stage-gate) both **active** |
| Backends | 4 backend classes in `aicp/backends/`: localai, claude_code, openrouter, base. **K2.6** registered as second OpenRouterBackend instance (named `k2_6_openrouter`). |

---

## Fresh Ubuntu 24.04 setup — start here on the new machine

### 0. Sanity checks before cloning

```bash
# OS
lsb_release -a                       # Ubuntu 24.04 LTS expected
uname -r                              # kernel version

# Python
python3 --version                    # 3.10+ required (3.12 default on Ubuntu 24.04)

# Docker
docker --version                     # 20+ required
docker run --rm hello-world          # daemon working

# NVIDIA (if GPU acceleration desired)
nvidia-smi                           # driver visible
docker run --rm --gpus all nvidia/cuda:12.0-base nvidia-smi   # GPU passthrough working

# Memory + disk
free -h                              # 64GB RAM expected
lsblk                                # locate /dev/sdd or RAID 0 NVMe
df -h /                              # disk free for models (340GB Q2 GGUF if local K2.6)
```

**FLAG — known compat issue**: AICP's test suite has 4 files using Python 3.10+ `list[dict]` syntax that fail collection on Python 3.8. On Python 3.10+ this should resolve. Verify with `python3 -m pytest tests/ --collect-only 2>&1 | tail -5` after install.

### 1. Clone both repos (AICP + brain)

```bash
mkdir -p ~/dev && cd ~/dev

# AICP — this project
git clone <aicp-repo-url> devops-expert-local-ai
ln -sf ~/dev/devops-expert-local-ai ~/devops-expert-local-ai   # path used by brain references

# Second brain — REQUIRED. AICP references it via ~/devops-solutions-research-wiki
git clone <brain-repo-url> devops-solutions-research-wiki
ln -sf ~/dev/devops-solutions-research-wiki ~/devops-solutions-research-wiki
```

> **Why both**: AICP integrates with the brain via `tools/gateway.py` forwarder. Many AICP wiki pages reference brain-authoritative specs at `~/devops-solutions-research-wiki/...`. Without the brain, the integration tools (`gateway`, `evolve`, `lint`, `export`) work for AICP-only pages, but brain-side validation breaks.

### 2. AICP setup (one-shot)

```bash
cd ~/devops-expert-local-ai

# Verify prereqs first (non-destructive)
make check-prereqs                   # checks Python / Docker / GPU

# One-shot setup: .venv, deps, models/, LocalAI Docker container
make setup                           # auto-detects VRAM, picks model

# Activate venv for the shell session
source .venv/bin/activate

# Verify everything is working
make check                           # or: aicp --check
```

Setup script paths (for debugging if `make setup` fails):
- `scripts/setup.sh` — orchestrator
- `scripts/install-nvidia-toolkit.sh` — GPU passthrough
- `scripts/localai-entrypoint.sh` — container boot
- `scripts/sync-kb-to-localai.sh` — knowledge base sync

### 3. Environment variables (`.env`)

The `.env` file is **gitignored**. Manually create on the fresh machine:

```bash
cat > ~/devops-expert-local-ai/.env <<'EOF'
# OpenRouter (REQUIRED for K2.6 backend, Anthropic fallback via OpenRouter)
OPENROUTER_API_KEY=<get from https://openrouter.ai/keys>

# Anthropic (optional — used by Claude Code direct backend; transitioning out)
# ANTHROPIC_API_KEY=<...>

# HuggingFace (optional — for downloading model weights via huggingface-cli)
# HF_TOKEN=<...>

# AICP behavior overrides
# AICP_DEFAULT_MODE=think
# AICP_DEFAULT_BACKEND=local
# AICP_PROFILE=default
EOF

chmod 600 ~/devops-expert-local-ai/.env
```

Verify the key is loaded:

```bash
source ~/devops-expert-local-ai/.env
echo "OPENROUTER_API_KEY len: ${#OPENROUTER_API_KEY}"   # expect ~73 chars
```

### 4. Sister-project sync (brain)

```bash
cd ~/devops-solutions-research-wiki
# (brain has its own setup — refer to its README; minimal: Python 3.10+, no Docker required)

# Verify the AICP→brain forwarder works
cd ~/devops-expert-local-ai
python3 -m tools.gateway compliance   # should show Tier 4/4 STRUCTURAL
python3 -m tools.gateway orient        # quick orientation
```

### 5. LocalAI container (Docker)

`make setup` should have built/started this. Verify:

```bash
docker ps --filter name=localai      # container running
curl -s http://localhost:8090/v1/models | head -20   # API responding

# Models loaded
make models                          # AICP CLI: aicp --models list
```

If LocalAI container missing, manually:

```bash
cd ~/devops-expert-local-ai
docker compose up -d localai
docker logs -f $(docker ps -q --filter name=localai)
```

### 6. Smoke test the full stack

```bash
cd ~/devops-expert-local-ai
source .venv/bin/activate
source .env

# Local backend (qwen3-8b on LocalAI)
aicp --backend local "What is 2+2?"

# K2.6 via OpenRouter (the new primary cloud agentic tier)
aicp --backend k2_6_openrouter "Identify yourself."
# Expected: response mentioning Kimi/Moonshot

# Brain integration check
python3 -m tools.lint                # 23/23 should pass
python3 -m tools.evolve --score --top 5   # ranking output
python3 -m tools.gateway compliance  # Tier 4/4 STRUCTURAL
```

### 7. Hardware-specific (if applicable)

#### 64GB RAM verification

```bash
free -h                              # MemTotal should be ~63-64Gi
swapon --show                        # check current swap
```

#### RAID 0 NVMe swap (E010 territory — operator-owned)

If RAID 0 NVMe is not yet mounted as swap, the brain has the procedure:

```bash
cat ~/devops-solutions-research-wiki/wiki/backlog/modules/e010-m002-dev-sdd-mount-procedure.md
```

#### KTransformers (E008 territory — for local K2.6, blocks E011-m003)

```bash
cat ~/devops-solutions-research-wiki/wiki/backlog/modules/e008-m001-ktransformers-install-and-config.md
cat ~/devops-solutions-research-wiki/wiki/backlog/tasks/T031-create-ktransformers-venv.md
```

> **FLAG — MANUAL STEP**: KTransformers install + Q2 GGUF download (340GB) + benchmark are NOT scripted in AICP's `scripts/`. The brain owns these procedures. Once executed, AICP's E011-m003 implementation slots them in via a new `aicp/backends/k2_6_local.py` adapter.

---

## Where to resume work (next-action queue)

### Priority order

1. **E011-m001 — Router refactor** (4-tier → 5-tier with config-driven `tier_map`)
   - **Why first**: unlocks auto-routing of agentic/coding workloads to K2.6 (the actual cost-savings win). Currently operator must explicitly `--backend k2_6_openrouter`.
   - **What needs work**: `aicp/core/router.py:275 classify_task_with_reason()` is hardcoded around `local`/`claude`/`openrouter` triple. Brain spec at `~/devops-solutions-research-wiki/wiki/backlog/modules/e011-m001-tier-definitions-update.md` proposes `tier_map` config. Brain spec is shape-correct but specifics (line numbers, exact patch) need re-verification — brain explicitly said "NOT authoritative — read the file before writing the patch".
   - **Tests to maintain green**: `tests/test_router.py`, `tests/test_routing.py` (probably exist — verify before refactor).
   - **Estimated effort**: 1 careful session. Risk: routing regression for existing flows.

2. **E011-m003 — K2.6 local via KTransformers** (depends on E008)
   - **Blocked on**: operator/brain executing E008-m001 (KTransformers install) + E008-m002 (Q2 GGUF download) + E008-m003 (first-light benchmark).
   - **AICP work when unblocked**: new `aicp/backends/k2_6_local.py` (likely OpenAI-compat HTTP wrapper since KTransformers exposes that), wire into `_build_backends` in `cli/main.py`, add tests.
   - **Estimated effort**: 1 session AFTER E008 done.

3. **E011-m004 — Per-backend circuit breaker tuning**
   - Pattern already shipped (`aicp/core/circuit_breaker.py`, promoted to growing-tier 2026-04-22). Just needs per-backend config in `config/profiles/` and a fallback chain doc.
   - **Estimated effort**: 0.5 session.

4. **E011-m005 — Routing-split metric + weekly review ritual**
   - Add a metric emitter to `aicp/core/observability.py` (or wherever metrics flow). Document a weekly review ritual.
   - **Estimated effort**: 0.5-1 session.

5. **Profile YAMLs** (`config/profiles/quality.yaml`, etc.)
   - Cosmetic without router refactor. Wait until M001 done.

### Held tracks (not blocking deadline)

- **MCP migration removal** — release-paced. 21 deprecated tools in `aicp/mcp/server.py`. Remove after a release cycle.
- **Wiki content promotion remaining 8 seeds** — appropriately seed-tier (point-in-time audits, model-specific, in-flight adoptions). Promote individually as evidence warrants.
- **Step 9 long-form operational adoption** — multi-month, no urgency.

---

## Doctrine (key principles to maintain — DO NOT DRIFT)

These are PO-emphatic principles captured in user memory at `~/.claude/projects/-home-jfortin-devops-expert-local-ai/memory/`:

1. **Listen literally / fix what PO says** — when PO names a bug, FIX IT. Don't re-analyze. (`feedback_listen_literally.md`, `feedback_fix_what_po_says.md`)
2. **DO_NOT minimize/compress/conflate** — when PO names multiple separate things, keep them separate. (`feedback_do_not_minimize.md`, `.claude/rules/DO_NOT-minimize-compress-or-conflate-information.md`)
3. **Verify before writing** — read the actual code, not summaries. The brain's specs say "NOT authoritative — read the file" for a reason. (`feedback_verify_before_writing.md`)
4. **Stay on mission** — don't jump to plans. Continue means continue. (`feedback_stay_on_mission.md`)
5. **Stop rushing** — heavy tasks need heavy planning. Write idea documents FIRST. Build substance not shells. (`feedback_stop_rushing.md`, `feedback_do_not_minimize.md`)
6. **No rogue AI** — user leads, AI executes. Three corrections = stop. (`feedback_no_rogue_ai.md`)
7. **Show the work, don't diagnose** — "show the result" = QUERY the thing, not show stats. Demonstrate. (`feedback_show_the_work.md`)
8. **Conventional commits** — frequent small commits with conventional commit messages. (`feedback_conventional_commits.md`)
9. **No manual setup** — everything must be scripted IaC-style. (`feedback_no_manual_setup.md`)
10. **Brain is upstream** — accept what comes from the brain; do NOT push to brain without explicit operator greenlight. (Operator directive 2026-04-22 this session.)

---

## Handy commands (cheat sheet)

### Brain integration
```bash
python3 -m tools.gateway compliance              # Tier 1-4 status
python3 -m tools.gateway orient                  # quick project orientation
python3 -m tools.view spine                      # 16 brain models + standards
python3 -m tools.view standards                  # what "good" looks like
python3 -m tools.view lessons                    # 44 validated lessons in brain
python3 -m tools.view search <query>             # search brain
python3 -m tools.gateway contribute --type lesson --title '...'   # contribute back (with greenlight!)
```

### Wiki + evolve + lint
```bash
python3 -m tools.lint                            # validate all wiki pages
python3 -m tools.evolve --score --top 10         # rank promotion candidates
python3 -m tools.evolve --score --maturity seed  # filter by maturity
python3 -m tools.export --profile second-brain --dry-run   # see what would export
```

### AICP runtime
```bash
aicp --check                                     # verify setup
aicp --self-test                                 # full self-test
aicp --observe                                   # live state
aicp --metrics                                   # show metrics
aicp --capabilities                              # what AICP can do
aicp --models                                    # model gallery
aicp --models list                               # loaded models
aicp --profile-cmd list                          # 9 profiles available
aicp --task-cmd list                             # active workflow tasks
aicp --dlq-status                                # dead-letter queue
```

### K2.6 specifically
```bash
# Smoke test K2.6 (requires OPENROUTER_API_KEY in .env)
aicp --backend k2_6_openrouter "Identify yourself."

# Streaming
aicp --backend k2_6_openrouter --stream "Write a haiku about disk I/O."

# Tests
python3 -m pytest tests/test_k2_6_backend.py -v
```

### Common edits
```bash
# Active task tracking (for Layer B hooks)
aicp --task-cmd switch --task-arg T<NNN>         # set active task
aicp --task-cmd show                              # current active
aicp --task-cmd clear                             # clear active

# Profile switching
make profile-use PROFILE=reliable                # switch profile (writes .env)
```

---

## Risks / blockers / known issues

| Risk | Severity | Mitigation |
|------|----------|------------|
| Brain repo not on fresh machine | **HIGH** — breaks gateway, lint, evolve cross-refs | Clone alongside AICP per Step 1 above |
| OPENROUTER_API_KEY missing in .env | **HIGH** — K2.6 + Anthropic-via-OpenRouter both broken | Verify per Step 3 |
| 4 test files use Python 3.10+ syntax | LOW — fails on 3.8, works on 3.10+. Ubuntu 24.04 has 3.12 default so should resolve | Ignore on 24.04; if persists, fix the 4 files |
| KTransformers + Q2 GGUF (340GB) download | MEDIUM — manual, time-consuming, blocks E011-m003 | Brain owns procedure; AICP work blocked downstream |
| RAID 0 NVMe swap not configured | MEDIUM — needed for local K2.6 inference | Brain owns E010-m002; verify before E011-m003 |
| Router refactor risk (E011-m001) | MEDIUM — could regress existing routing | Read existing tests before edits; keep all routing tests green |
| MCP audit Phase 4 (removal) — release-paced | LOW — held intentionally | No action; await release cadence |
| 5-day deadline pressure | HIGH — limited time for careful work | Prioritize M001 (router refactor) — biggest unlock |

---

## Memory + state files (persists across sessions)

The model has persistent memory at:
```
~/.claude/projects/-home-jfortin-devops-expert-local-ai/memory/
├── MEMORY.md                                          # index (auto-loaded each session)
├── project_aicp_brain_adoption_state.md               # brain integration state — READ THIS FIRST
├── project_session_final_state.md                     # COMPLETE inventory
├── project_session_2026_04_03.md                      # prior session state
├── feedback_*.md                                      # PO doctrine (~30 files)
├── reference_*.md                                     # external knowledge
└── user_profile.md                                    # operator profile
```

On fresh machine, this directory **may need to be transferred manually** if model memory was tied to a specific Claude Code installation. Verify on first session:

```bash
ls ~/.claude/projects/-home-jfortin-devops-expert-local-ai/memory/ 2>&1 | head -10
```

If empty, the memory was machine-local. The `MEMORY.md` index is the recovery starting point — re-author from the project state docs (`docs/SESSION-2026-04-18.md`, this file, `wiki/log/`).

AICP's runtime state files (gitignored, machine-local):
```
~/.aicp/dlq/                          # dead-letter queue (per-day JSONL)
~/.aicp/history/                      # session history
~/.aicp/config.yaml                   # operator config overlay (optional)
.aicp/state.yaml                      # active task tracking (per-project)
```

---

## Verbatim PO words from this session arc (preserve mission intent)

> "the second-brain is evolving, accept it, it will have work for you. but continue its integration in general"

> "the 64GB memory landed. you can continue"

> "lets prepare a strong handoff document. I will probably have to start a fresh session on a fresh ubuntu24.04 with for noe this project alone."

The directional principle: brain pushes work down to AICP. AICP listens, reads brain-authoritative specs, adapts to AICP code reality, ships.

---

## First actions on fresh machine (literal sequence)

```bash
# 1. Clone both repos (paths matter — brain references AICP at this path)
mkdir -p ~/dev && cd ~/dev
git clone <aicp-repo-url> devops-expert-local-ai
git clone <brain-repo-url> devops-solutions-research-wiki
ln -sf ~/dev/devops-expert-local-ai ~/devops-expert-local-ai
ln -sf ~/dev/devops-solutions-research-wiki ~/devops-solutions-research-wiki

# 2. Setup AICP
cd ~/devops-expert-local-ai
make check-prereqs                               # if anything missing, install per output
make setup                                       # creates .venv, downloads models, builds LocalAI
source .venv/bin/activate

# 3. Create .env (REQUIRED)
$EDITOR .env                                     # add OPENROUTER_API_KEY (see Step 3 above)
chmod 600 .env

# 4. Verify
make check                                       # full system check
python3 -m tools.gateway compliance              # expect Tier 4/4 STRUCTURAL
python3 -m tools.lint                            # expect 23/23 passing
python3 -m pytest tests/test_k2_6_backend.py -v  # expect 5/5 passing
source .env && aicp --backend k2_6_openrouter "Identify yourself."   # expect "Kimi from Moonshot"

# 5. Read this handoff + brain epic
cat docs/SESSION-2026-04-22-RESUME.md            # this file
cat docs/SESSION-2026-04-18.md                   # predecessor
cat ~/devops-solutions-research-wiki/wiki/backlog/milestones/post-anthropic-self-autonomous-stack.md
cat ~/devops-solutions-research-wiki/wiki/backlog/epics/pre-milestone/E011-routing-integration-aicp-tiers.md

# 6. Resume work
# Next priority: E011-m001 router refactor.
# Brain spec: ~/devops-solutions-research-wiki/wiki/backlog/modules/e011-m001-tier-definitions-update.md
# Read aicp/core/router.py:275 (classify_task_with_reason) FIRST before patching.
```

---

End of handoff. Successor session: read TL;DR → setup steps if fresh machine → next-action queue. The work continues.
