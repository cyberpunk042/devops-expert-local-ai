# TOOLS.md — AICP operational commands

> Extracted from AGENTS.md `## How to operate the project` 2026-04-25. AGENTS.md keeps a one-line summary and routes here. Mirrors the second-brain pattern (`devops-solutions-information-hub/TOOLS.md`).

## Tests

```bash
pytest tests/                    # full suite (1,840 tests)
pytest tests/ -x --tb=short      # fail-fast for active dev
```

## Lint + format

```bash
ruff check aicp/ tests/
ruff format aicp/ tests/
```

## CLI

```bash
python -m aicp.cli               # interactive
python -m aicp.cli --help        # subcommands

# Single-shot
aicp "your prompt"                          # think + local (defaults)
aicp "agentic refactor" -b k2_6_openrouter  # Kimi K2.6 via OpenRouter (audit-safe)
aicp "research task" --profile personal     # routes through ollama_cloud (band 1)
aicp "complex" -b openrouter                # Opus / GPT / Gemini fallback
aicp "sovereignty test" -b k2_6_local       # llama.cpp local K2.6 (slow, opt-in)
aicp "help me" -b auto                      # score-banded smart routing
```

## LocalAI

```bash
docker compose up -d             # start LocalAI on :8090
curl http://localhost:8090/v1/models
```

## Local K2.6 sovereignty (opt-in)

```bash
bash scripts/llama-serve.sh      # starts llama-server on :8091 (60-90 min cold reload)
aicp --backend k2_6_local "..."  # route a query at it
```

## Profiles

```bash
make profile-list
make profile-use PROFILE=fast       # writes .env + restarts containers
make profile-show PROFILE=reliable
make profile-diff PROFILE_A=fast PROFILE_B=offline
```

11 profiles total. See [docs/architecture/profiles.md](docs/architecture/profiles.md) for the full table + when-to-use guide.

## Models

```bash
make model-qwen3                 # Qwen3-8B + Qwen3-4B (8GB GPU)
make model-list-remote           # full catalog with VRAM info
```

## Knowledge base (LocalAI Collections)

```bash
make kb-sync                     # sync docs/kb/ to LocalAI
make kb-sync-force               # reset + re-upload
```

## Observability

```bash
make monitoring-up               # Prometheus :9090 + Grafana :3000 (admin/aicp)
```

AICP own metrics at `:9101/metrics`. LocalAI built-in at `:8090/metrics`. Alerts: [config/alerts.yaml](config/alerts.yaml) (7 rules).

## Reliability

```bash
aicp --health-report             # trend report
aicp --retry-dlq                 # retry failed tasks
aicp --check                     # config + backend availability + GPU
```

## Second brain (forwarder to `~/devops-solutions-research-wiki`)

```bash
python3 -m tools.gateway status     # identity + SDLC profile
python3 -m tools.gateway compliance # adoption tier (currently 4/4 STRUCTURAL)
python3 -m tools.gateway orient     # full orientation flow
python3 -m tools.gateway contribute --type lesson --title "..."   # send a lesson back
python3 -m tools.view standards     # browse the brain's "what good looks like" pages
python3 -m tools.view search <q>    # search across all brain knowledge
```

## Cloud-backend env vars (in `.env`)

```bash
OPENROUTER_API_KEY=sk-or-...        # drives openrouter + k2_6_openrouter
OLLAMA_API_KEY=...                  # drives ollama_cloud (--profile personal)
# Anthropic auth via `claude login` — not env var
```

See [.env.example](.env.example) for full operator-config reference.
