# AICP — Improvement Backlog

Updated 2026-03-27. Items marked ~~strikethrough~~ are done. **[QUICK]** = <1h. **[MEDIUM]** = 1-2 days. **[LARGE]** = multi-session.

---

## Setup & Onboarding

- ~~**[QUICK] `make install-aliases`**~~ — ✅ done (`scripts/install-aliases.sh` + `make install-aliases`)
- ~~**[QUICK] `make update`**~~ — ✅ done
- ~~**[QUICK] `models/hermes.yaml.example`**~~ — ✅ done (with corrected `cuda12-llama-cpp` backend)
- ~~**[QUICK] `make agent-up` / `make agent-down`**~~ — ✅ done (with PID file tracking)
- ~~**[MEDIUM] NVIDIA Container Toolkit check in `make check`**~~ — ✅ done (`_run_check()` now runs a `docker run --gpus all nvidia-smi -L` probe and reports pass/fail inline)
- ~~**[MEDIUM] systemd unit file for `aicp-agent`**~~ — ✅ done (`scripts/aicp-agent.service` + `scripts/install-service.sh` + `make install-service` / `make uninstall-service`)

---

## LocalAI / Model Management

- ~~**[QUICK] `models/` gitignore**~~ — ✅ already in `.gitignore`
- ~~**[QUICK] `make model-list-remote`**~~ — ✅ done (`scripts/models-catalog.sh`, 8-model curated catalog with VRAM filter)
- ~~**[MEDIUM] Model alias YAML generation**~~ — ✅ done via `scripts/setup.sh` (all 7 catalog models: phi3-mini, gemma-2b, hermes, mistral-7b, codellama-7b, hermes-13b, codellama-13b; auto-selected by VRAM)
- ~~**[MEDIUM] LocalAI version pinning**~~ — ✅ done (`Dockerfile.localai` pinned to `v4.0.0-gpu-nvidia-cuda-12`, upgrade path documented)
- ~~**[MEDIUM] Cold-start retry in LocalAI backend**~~ — ✅ done (`_wait_for_model()` polls `/v1/models` up to 60s, retries chat completions up to 3 times)

---

## Configuration

- ~~**[QUICK] `config/loader.py` doesn't validate `max_tokens`**~~ — ✅ done
- ~~**[QUICK] Config file auto-discovery**~~ — ✅ done (`~/.aicp/config.yaml` merged on top of defaults)
- ~~**[MEDIUM] Per-project config**~~ — ✅ done (`<project>/.aicp/config.yaml` as third layer, `load_config(project_path=...)` wired through CLI)

---

## Guardrails

- ~~**[MEDIUM] `guardrails/paths.py` is a stub**~~ — ✅ done. `is_path_allowed()` was already fully implemented; `check_forbidden_path()` now calls it from `run_preflight_checks()` for Edit/Act modes.
- ~~**[MEDIUM] Mode enforcement for LocalAI**~~ — ✅ done (`aicp/guardrails/response.py` — `scan_think_mode()` checks for shell prompts, sudo, rm -rf, file redirects, Python writes; warns after printing response in THINK mode; 8 tests in `test_guardrails.py`)
- ~~**[QUICK] Forbidden pattern check on task output**~~ — ✅ done (`scan_response_secrets()` in `aicp/guardrails/response.py`; detects AWS keys, JWTs, private key blocks, GitHub PATs, bearer tokens, generic password= patterns; warns after every response regardless of mode/backend; 6 tests)
- ~~**[MEDIUM] Project-level allowed-paths config**~~ — ✅ done (`check_forbidden_path()` reads `guardrails.allowed_paths` from merged config and passes it to `is_path_allowed()`; commented example in `config/default.yaml`)

---

## CLI / UX

- ~~**[QUICK] `aicp --version`**~~ — ✅ already wired (`--version / -v` uses `argparse action="version"`)
- ~~**[QUICK] Better error messages when LocalAI is down**~~ — ✅ done (`_connect_error_message()` inspects Docker container state to distinguish stopped vs. not-built vs. wrong URL)
- ~~**[MEDIUM] `aicp --stats` per-backend breakdown**~~ — ✅ done (summary table + single side-by-side comparison table: cols = local/claude, rows = tasks/latency/errors/tokens/cost)
- ~~**[MEDIUM] `cli/dashboard.py` — `/system` endpoint crash**~~ — ✅ done (endpoint call wrapped in try/except; gracefully falls back to OFFLINE message when endpoint is absent in LocalAI v4)
- ~~**[MEDIUM] `cli/control.py` — label + task matching bugs**~~ — ✅ done ("Open Decisions" column renamed, fragile `endswith()` project matching replaced with `Path.resolve()` equality)
- ~~**[MEDIUM] `cli/dashboard.py` — complete the TUI**~~ — ✅ done (refresh_per_second=4, last-refresh timestamp in header, right panel split into Metrics + Recent Tasks, LocalAI panel shows today/total request counts from history, GPU util/temp columns, graceful empty-state handling)
- ~~**[MEDIUM] `cli/control.py` — cross-project view polish**~~ — ✅ done (projects sorted by last activity, phase breakdown footer, milestone % in progress bar, deep-dive header shows completion %, milestones sorted in_progress→pending→done with Unicode icons)

---

## Observability

- ~~**[MEDIUM] Structured log output to file**~~ — ✅ done (`AICP_LOG_FILE` env var; `save_task()` appends compact JSONL entry to file — no response body, one line per task, documented in `.env.example`)
- ~~**[MEDIUM] `aicp --stats` per-backend breakdown**~~ — ✅ done (see CLI/UX section)
- ~~**[LARGE] Metrics export — SQLite**~~ — ✅ done (`aicp/core/db.py` — `record_task()` auto-called from `save_task()` when `AICP_DB_FILE` set; `query_tasks()` with backend/date filters; `rebuild_db()` imports existing history; `make db-rebuild`; 7 tests in `test_db.py`; documented in `.env.example`)

---

## Testing

- ~~**[QUICK] Add test for `LocalAIBackend` with `max_tokens`**~~ — ✅ done (`tests/test_localai_backend.py`, 12 tests including max_tokens payload assertion, `_is_model_loaded`, `_wait_for_model` success/timeout)
- ~~**[QUICK] Add tests for `check_forbidden_path()`**~~ — ✅ done (`tests/test_guardrails.py` covers Edit/Act/Think modes, `allowed_paths` blocking, integration through `run_preflight_checks()`)
- ~~**[QUICK] Add tests for `_deep_merge()` and user config override**~~ — ✅ done (`tests/test_config.py` covers nested merge, user config override, project config override, max_tokens validation)
- ~~**[MEDIUM] LocalAI integration tests**~~ — ✅ done (`TestLocalAIIntegration` in `test_integration.py` — 6 tests: availability, status_detail, think mode response, usage metadata, `_is_model_loaded`, full Controller pipeline; auto-skipped when LocalAI not running; `pytest -k localai` to run)
- ~~**[MEDIUM] Add `mypy` to CI**~~ — ✅ done (`mypy>=1.0` in dev deps, `[tool.mypy]` config in `pyproject.toml`, `make type-check` target; auto-installed by `make setup`)

---

## Missing from Original Machine (Flagged)

These items are likely present on the machine where development started but are **not in the repo**:

| Item | Impact | Action |
|------|--------|--------|
| `models/hermes.yaml` | LocalAI can't resolve the `hermes` alias | Add `models/hermes.yaml.example` to repo |
| GGUF model files | LocalAI has nothing to serve | Document download URL in SETUP.md (done) |
| `~/.aicp/projects.yaml` | Project registry is empty | Populated on first `aicp --project-cmd register` |
| `~/.aicp/skills.yaml` | Global skills unavailable | Re-create from `docs/aicp-skills-inventory.md` |
| NVIDIA Container Toolkit | GPU passthrough in Docker won't work | See SETUP.md prerequisites |
| Shell aliases in `~/.bashrc` | Convenience commands missing | Re-add from README or `make install-aliases` (planned) |

---

## Architecture Suggestions (Longer Term)

- ~~**Streaming for LocalAI**~~ — ✅ done (`execute_stream()` on `LocalAIBackend` using SSE; `--stream` flag now works for both LocalAI and Claude Code; `aicp -i` uses streaming by default with configurable `max_tokens` from config instead of hardcoded 512)
- ~~**Session continuity for LocalAI**~~ — ✅ done (`--session NAME` persists conversation history in `~/.aicp/sessions/<name>.json`; `--session-list` and `--session-delete` commands; history injected as `messages[]` in next call; system message rebuilt fresh each turn)
- ~~**`--router-debug` flag**~~ — ✅ done (shows routing decision table: mode, prompt length, complex/simple keyword hits, backend availability, recommended backend + reason, override note if `--backend` was specified explicitly)
- **Agent daemon auto-discovery** — multiple `aicp-agent` instances on a network currently need manual IP config. Consider mDNS/Avahi for zero-config local discovery.
- **OpenClaw Fleet integration** — the architecture docs (see `docs/aicp-fleet-architecture.md`) describe AICP as the user-facing layer of a broader fleet. The boundary is defined but the actual integration (skill sharing, task delegation) is not yet implemented.
- **Prometheus metrics export** — extend `aicp/core/db.py` to expose a `/metrics` endpoint (via a tiny HTTP server or push to a Pushgateway) for Grafana/Loki integration.
