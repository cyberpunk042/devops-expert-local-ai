.PHONY: setup setup-force setup-claude-only setup-local-only setup-low-vram check-prereqs \
        local-up local-up-multi local-up-p2p local-down local-status local-logs \
        test test-all check lint format type-check auto-config benchmark self-test capabilities offload update \
        model-download models-list model-list-remote model-qwen3 model-qwen3-8b model-qwen3-4b model-qwen3-30b benchmark-qwen3 \
        model-gemma4 model-gemma4-e2b model-gemma4-e4b model-gemma4-26b model-sd35-medium model-sd35-medium-allinone \
        build-sd-cpp build-libgosd sd35-test sd35-test-standalone sd35-server \
        monitoring-up monitoring-down monitoring-logs agent-up agent-down \
        fleet-init fleet-join fleet-status fleet-test fleet-copy fleet-firewall \
        install-aliases install-service uninstall-service db-rebuild \
        install-nvidia-toolkit extract-backend extract-backend-force extract-backend-only \
        install-statusline optimize-models \
        health-report retry-dlq dlq-status tasks extract-memories extract-memories-dry \
        help

SETUP_SCRIPT := scripts/setup.sh
PORT         ?= 8090

# Default target — show help
.DEFAULT_GOAL := help

help:
	@echo ""
	@echo "AICP — AI Control Platform"
	@echo ""
	@echo "SETUP"
	@echo "  make setup                   Full setup: venv + deps + model + LocalAI (idempotent)"
	@echo "  make setup-force             Force re-run every step even if already done"
	@echo "  make setup-claude-only       Python + Claude Code only (no LocalAI)"
	@echo "  make setup-local-only        LocalAI + GPU only (no Claude deps)"
	@echo "  make setup-low-vram          Setup with phi3-mini (3 GB VRAM)"
	@echo "  make check-prereqs           Check Python / Docker / GPU / NVIDIA toolkit"
	@echo "  make install-nvidia-toolkit  Install NVIDIA Container Toolkit (GPU → Docker)"
	@echo ""
	@echo "LOCALAI"
	@echo "  make extract-backend         Extract all backends from quay.io (idempotent)"
	@echo "  make extract-backend-force   Re-extract all backends"
	@echo "  make extract-backend-only BACKEND=whisper  Extract one backend"
	@echo "  make local-up                Start LocalAI container (standalone)"
	@echo "  make local-up-p2p            Start LocalAI with P2P federation (all nodes equal)"
	@echo "  make local-down              Stop LocalAI container"
	@echo "  make local-status            Container + API status"
	@echo "  make local-logs              Tail LocalAI container logs"
	@echo "  make local-up-multi          Start with multi-GPU compose override"
	@echo ""
	@echo "DEVELOPMENT"
	@echo "  make test                    Run unit tests (excludes integration)"
	@echo "  make test-all                Run all tests including integration"
	@echo "  make check                   aicp --check (config + backend health)"
	@echo "  make lint                    Ruff lint"
	@echo "  make format                  Ruff format"
	@echo "  make type-check              mypy static type check"
	@echo "  make auto-config             GPU-aware model config optimiser"
	@echo "  make benchmark               Benchmark the default model"
	@echo "  make self-test               Validate all AICP features against live LocalAI"
	@echo "  make capabilities            Show all AICP capabilities and integrations"
	@echo "  make offload                 LocalAI offload dashboard (progress toward 80%% goal)"
	@echo ""
	@echo "MODELS"
	@echo "  make model-list-remote       Curated catalog with VRAM/size info"
	@echo "  make model-qwen3             Download Qwen3-8B + Qwen3-4B (8GB GPU)"
	@echo "  make model-qwen3-30b         Download Qwen3-30B MoE (dual GPU only)"
	@echo "  make model-gemma4            Download Gemma 4 E2B + E4B (8GB GPU)"
	@echo "  make model-gemma4-26b        Download Gemma 4 26B MoE (dual GPU only)"
	@echo "  make model-sd35-medium       Download SD 3.5 Medium GGUF encoders (~6.8 GB)"
	@echo "  make model-sd35-safetensors  Download SD 3.5 Medium safetensors (5.1 GB, needs HF token)"
	@echo "  make build-libgosd           Rebuild libgosd.so for SD 3.5 support (auto in setup)"
	@echo "  make sd35-test               Generate SD 3.5 image via LocalAI API"
	@echo "  make sd35-test-standalone    Generate SD 3.5 image via standalone sd-cli"
	@echo "  make sd35-server             Start standalone SD 3.5 API server on port 8091"
	@echo "  make build-sd-cpp            Build standalone sd.cpp from source (CUDA)"
	@echo "  make benchmark-qwen3         Benchmark Qwen3-8B"
	@echo "  make monitoring-up           Start Prometheus + Grafana"
	@echo "  make monitoring-down         Stop monitoring stack"
	@echo "  make models-list             Models currently loaded in LocalAI"
	@echo "  make model-download MODEL=<f> URL=<url>  Download a GGUF model"
	@echo ""
	@echo "RELIABILITY (Stage 4+5)"
	@echo "  make health-report           Generate health report with trends"
	@echo "  make retry-dlq               Retry pending dead-letter queue entries"
	@echo "  make dlq-status              Show DLQ status and pending entries"
	@echo "  make tasks                   Show active and recent tasks"
	@echo "  make extract-memories        Extract facts from task history into memory"
	@echo "  make extract-memories-dry    Preview extraction without writing files"
	@echo ""
	@echo "AGENT"
	@echo "  make agent-up                Start aicp-agent daemon (port 9100)"
	@echo "  make agent-down              Stop aicp-agent daemon"
	@echo "  make install-service         Install aicp-agent as systemd user service"
	@echo "  make uninstall-service       Remove systemd service"
	@echo ""
	@echo "FLEET (multi-machine)"
	@echo "  make fleet-init              Generate fleet token + register this node"
	@echo "  make fleet-join HOST=<ip>    Add a remote machine to the fleet"
	@echo "  make fleet-status            Check connectivity of all fleet nodes"
	@echo "  make fleet-test              Run a test task on each node"
	@echo "  make fleet-copy HOST=<ip>    SCP fleet config + token to remote node"
	@echo "  make fleet-firewall          Show firewall rules (Windows/ESET/Linux)"
	@echo "  make p2p-token               Fetch P2P token from LocalAI + save to .env"
	@echo "  make wsl-forward             Forward agent+P2P ports from WSL to LAN"
	@echo "  make wsl-forward-check       Check current WSL port forwards"
	@echo "  make wsl-forward-remove      Remove all AICP WSL port forwards"
	@echo ""
	@echo "MAINTENANCE"
	@echo "  make update                  git pull + pip install"
	@echo "  make install-aliases         Add shell aliases to ~/.bashrc / ~/.zshrc"
	@echo "  make db-rebuild              Rebuild SQLite metrics DB from history JSON"
	@echo ""

# =============================================================================
# Setup — one command to go from zero to working
# =============================================================================

setup:
	@bash $(SETUP_SCRIPT) --mode full

setup-force:
	@bash $(SETUP_SCRIPT) --mode full --force

setup-claude-only:
	@bash $(SETUP_SCRIPT) --mode claude

setup-local-only:
	@bash $(SETUP_SCRIPT) --mode local

setup-low-vram:
	@bash $(SETUP_SCRIPT) --mode full --model phi3-mini

check-prereqs:
	@bash $(SETUP_SCRIPT) --mode check-only

install-nvidia-toolkit:
	@bash scripts/install-nvidia-toolkit.sh

install-statusline:
	@bash scripts/install-statusline.sh

optimize-models:
	@bash scripts/optimize-models.sh

# =============================================================================
# Backend extraction (run before first docker build)
# =============================================================================

extract-backend:
	@bash scripts/extract-backend.sh

extract-backend-force:
	@bash scripts/extract-backend.sh --force

extract-backend-only:
	@test -n "$(BACKEND)" || (echo "ERROR: set BACKEND=<cuda12-llama-cpp|whisper|piper>"; exit 1)
	@bash scripts/extract-backend.sh --only $(BACKEND)

# =============================================================================
# LocalAI management (day-to-day)
# =============================================================================

local-up:
	docker compose up -d
	@echo "Waiting for LocalAI API (backend install may take 2-3 min on first start)..."
	@for i in $$(seq 1 36); do \
		if curl -sf http://localhost:$(PORT)/v1/models > /dev/null 2>&1; then \
			echo "LocalAI ready at http://localhost:$(PORT)"; \
			exit 0; \
		fi; \
		echo "  waiting... ($$i/36)"; \
		sleep 5; \
	done; \
	echo "LocalAI still starting — check: make local-logs"

local-up-multi:
	docker compose -f docker-compose.yaml -f docker-compose.multi-gpu.yaml up -d

local-up-p2p:
	docker compose -f docker-compose.yaml -f docker-compose.p2p.yaml up -d
	@echo "Waiting for LocalAI P2P (backend install may take 2-3 min on first start)..."
	@for i in $$(seq 1 36); do \
		if curl -sf http://localhost:$(PORT)/v1/models > /dev/null 2>&1; then \
			echo "LocalAI P2P ready at http://localhost:$(PORT)"; \
			echo "  Next: run 'make p2p-token' to fetch the P2P token for fleet distribution"; \
			exit 0; \
		fi; \
		echo "  waiting... ($$i/36)"; \
		sleep 5; \
	done; \
	echo "LocalAI still starting — check: make local-logs"


local-down:
	docker compose down

local-status:
	@docker compose ps 2>/dev/null || echo "LocalAI is not running"
	@echo ""
	@curl -sf http://localhost:$(PORT)/v1/models 2>/dev/null | python3 -m json.tool || echo "API not reachable"

local-logs:
	docker compose logs -f --tail=50

# =============================================================================
# Development
# =============================================================================

test:
	.venv/bin/pytest tests/ -v --ignore=tests/test_integration.py

test-all:
	.venv/bin/pytest tests/ -v

check:
	.venv/bin/aicp --check

lint:
	.venv/bin/ruff check aicp/ tests/

format:
	.venv/bin/ruff format aicp/ tests/

type-check:
	.venv/bin/mypy aicp/

# Rebuild SQLite metrics DB from history JSON files (requires AICP_DB_FILE to be set)
db-rebuild:
	.venv/bin/python -c "from aicp.core.db import rebuild_db; n=rebuild_db(); print(f'Imported {n} records.')"

auto-config:
	.venv/bin/aicp --auto-config

benchmark:
	.venv/bin/aicp --models benchmark --models-arg hermes

self-test:
	.venv/bin/aicp --self-test

capabilities:
	.venv/bin/aicp --capabilities

offload:
	.venv/bin/aicp --offload

status:
	.venv/bin/aicp --status

# =============================================================================
# Profile management
# =============================================================================

profile-list:
	.venv/bin/aicp --profile-cmd list

profile-show:
	.venv/bin/aicp --profile-cmd show --profile $(or $(PROFILE),default)

profile-diff:
	.venv/bin/aicp --profile-cmd diff --profile $(or $(PROFILE_A),default) --profile-arg $(or $(PROFILE_B),fast)

profile-validate:
	.venv/bin/aicp --profile-cmd validate

profile-use:
	@test -n "$(PROFILE)" || (echo "ERROR: set PROFILE=<name>  (e.g. make profile-use PROFILE=fast)"; exit 1)
	.venv/bin/aicp --profile-cmd use --profile $(PROFILE)

# =============================================================================
# Model management
# =============================================================================

# Download a GGUF model into models/.
# Usage: make model-download MODEL=filename.gguf URL=https://...
model-download:
	@test -n "$(URL)"   || (echo "ERROR: set URL=<gguf download url>"; exit 1)
	@test -n "$(MODEL)" || (echo "ERROR: set MODEL=<filename.gguf>"; exit 1)
	mkdir -p models
	curl -L --progress-bar -C - -o models/$(MODEL) "$(URL)"
	@echo "Done. Restart LocalAI: make local-down && make local-up"

models-list:
	@curl -sf http://localhost:$(PORT)/v1/models 2>/dev/null | python3 -m json.tool || \
		echo "LocalAI not reachable at http://localhost:$(PORT)"

# Print curated catalog of GGUF models with VRAM requirements and download URLs.
# Filter by VRAM: make model-list-remote VRAM=8
model-list-remote:
	@bash scripts/models-catalog.sh

# Download Qwen3-8B (main reasoning model, ~4.9 GB, needs 6+ GB VRAM)
model-qwen3-8b:
	mkdir -p models
	curl -L --progress-bar -C - -o models/Qwen3-8B-Q4_K_M.gguf \
		"https://huggingface.co/Qwen/Qwen3-8B-GGUF/resolve/main/Qwen3-8B-Q4_K_M.gguf"
	@echo "Done. Restart LocalAI: make local-down && make local-up"

# Download Qwen3-4B (lightweight fleet model, ~3.3 GB, needs 4+ GB VRAM)
model-qwen3-4b:
	mkdir -p models
	curl -L --progress-bar -C - -o models/Qwen3-4B-Q6_K.gguf \
		"https://huggingface.co/Qwen/Qwen3-4B-GGUF/resolve/main/Qwen3-4B-Q6_K.gguf"
	@echo "Done. Restart LocalAI: make local-down && make local-up"

# Download Qwen3-30B-A3B MoE (dual GPU only, ~17 GB, needs 18+ GB VRAM)
model-qwen3-30b:
	mkdir -p models
	curl -L --progress-bar -C - -o models/Qwen3-30B-A3B-Q4_K_M.gguf \
		"https://huggingface.co/Qwen/Qwen3-30B-A3B-GGUF/resolve/main/Qwen3-30B-A3B-Q4_K_M.gguf"
	@echo "Done. Restart LocalAI: make local-down && make local-up"

# Download both Qwen3 models for 8GB single GPU setup
model-qwen3: model-qwen3-8b model-qwen3-4b
	@echo "Qwen3 models ready. Restart LocalAI: make local-down && make local-up"

# ── Gemma 4 models (Google, April 2026) ──────────────────────────────────────
# Multimodal (text+image+audio), 128K-256K context, native tool calling

# Download Gemma 4 E2B (2.3B effective, ~3.1 GB, needs 4+ GB VRAM)
model-gemma4-e2b:
	mkdir -p models
	curl -L --progress-bar -C - -o models/gemma-4-E2B-it-Q4_K_M.gguf \
		"https://huggingface.co/unsloth/gemma-4-E2B-it-GGUF/resolve/main/gemma-4-E2B-it-Q4_K_M.gguf"
	@echo "Done. Restart LocalAI: make local-down && make local-up"

# Download Gemma 4 E4B (4.5B effective, ~5.0 GB, needs 6+ GB VRAM)
model-gemma4-e4b:
	mkdir -p models
	curl -L --progress-bar -C - -o models/gemma-4-E4B-it-Q4_K_M.gguf \
		"https://huggingface.co/unsloth/gemma-4-E4B-it-GGUF/resolve/main/gemma-4-E4B-it-Q4_K_M.gguf"
	@echo "Done. Restart LocalAI: make local-down && make local-up"

# Download Gemma 4 26B-A4B MoE (dual GPU only, ~16.8 GB, needs 18+ GB VRAM)
model-gemma4-26b:
	mkdir -p models
	curl -L --progress-bar -C - -o models/gemma-4-26B-A4B-it-Q4_K_M.gguf \
		"https://huggingface.co/ggml-org/gemma-4-26B-A4B-it-GGUF/resolve/main/gemma-4-26B-A4B-it-Q4_K_M.gguf"
	@echo "Done. Restart LocalAI: make local-down && make local-up"

# Download both Gemma 4 models for 8GB single GPU setup
model-gemma4: model-gemma4-e2b model-gemma4-e4b
	@echo "Gemma 4 models ready. Restart LocalAI: make local-down && make local-up"

# ── Stable Diffusion 3.5 Medium (4 files, ~6.8 GB total) ──
# Quality leap over SD 1.5: 1024x1024, text rendering, strong prompt adherence.
# Uses --clip-on-cpu + --vae-on-cpu: only ~3.2 GB GPU VRAM.
model-sd35-medium:
	mkdir -p models
	@echo "Downloading SD 3.5 Medium (4 files, ~6.8 GB total)..."
	curl -L --progress-bar -C - -o models/sd3.5_medium-Q8_0.gguf \
		"https://huggingface.co/second-state/stable-diffusion-3.5-medium-GGUF/resolve/main/sd3.5_medium-Q8_0.gguf"
	curl -L --progress-bar -C - -o models/clip_l-Q8_0.gguf \
		"https://huggingface.co/second-state/stable-diffusion-3.5-medium-GGUF/resolve/main/clip_l-Q8_0.gguf"
	curl -L --progress-bar -C - -o models/clip_g-Q8_0.gguf \
		"https://huggingface.co/second-state/stable-diffusion-3.5-medium-GGUF/resolve/main/clip_g-Q8_0.gguf"
	curl -L --progress-bar -C - -o models/t5xxl-Q4_0.gguf \
		"https://huggingface.co/second-state/stable-diffusion-3.5-medium-GGUF/resolve/main/t5xxl-Q4_0.gguf"
	@echo "Done. 4 files downloaded. Restart LocalAI: make local-down && make local-up"

# SD 3.5 Medium All-in-One (single GGUF with VAE + all encoders, ~5.3 GB)
# Simpler setup — no separate component files needed.
model-sd35-medium-allinone:
	mkdir -p models
	@echo "Downloading SD 3.5 Medium all-in-one (pure-Q4_0, ~5.3 GB)..."
	curl -L --progress-bar -C - -o models/sd3.5_medium_allinone_Q4_0.gguf \
		"https://huggingface.co/gpustack/stable-diffusion-v3-5-medium-GGUF/resolve/main/stable-diffusion-v3-5-medium-pure-Q4_0.gguf"
	@echo "Done. Restart LocalAI: make local-down && make local-up"

# Download SD 3.5 Medium safetensors (gated — needs HF token in .env)
model-sd35-safetensors:
	@test -f .env && grep -q HUGGINGFACE_API_KEY .env || (echo "ERROR: set HUGGINGFACE_API_KEY in .env"; exit 1)
	mkdir -p models
	@echo "Downloading SD 3.5 Medium safetensors (5.1 GB, gated)..."
	@bash -c 'source .env && curl -L --progress-bar -C - \
		-H "Authorization: Bearer $$HUGGINGFACE_API_KEY" \
		-o models/sd3.5_medium.safetensors \
		"https://huggingface.co/stabilityai/stable-diffusion-3.5-medium/resolve/main/sd3.5_medium.safetensors"'
	@echo "Done. Use with: make sd35-test"

# Rebuild libgosd.so from vendored LocalAI source with CUDA (fixes SD 3.5 support)
# The gallery OCI image ships a stale .so; this builds from pinned sd.cpp @ 8afbeb6.
# After building: make setup-force (rebuilds Docker image with patched backend)
build-libgosd:
	bash scripts/build-libgosd.sh

# Build standalone stable-diffusion.cpp from source (sidecar option, not needed if using build-libgosd)
build-sd-cpp:
	bash scripts/build-sd-cpp.sh

# Test SD 3.5 via LocalAI API (requires: make setup with SD 3.5 models + build-libgosd)
sd35-test:
	@echo "Generating SD 3.5 image via LocalAI..."
	@curl -sf http://localhost:$(PORT)/v1/images/generations \
		-H "Content-Type: application/json" \
		-d '{"model":"sd35-medium","prompt":"a red sports car on a mountain road at sunset, photorealistic","size":"512x512","step":25}' \
		| python3 -c "import sys,json; d=json.load(sys.stdin); url=d['data'][0]['url']; print(f'Image URL: {url}')" \
		|| (echo "ERROR: LocalAI not running or SD 3.5 not loaded. Run 'make setup' first."; exit 1)

# Test SD 3.5 via standalone sd-cli (alternative, no LocalAI needed)
sd35-test-standalone:
	@test -f builds/sd-cpp/sd-cli || (echo "ERROR: run 'make build-sd-cpp' first"; exit 1)
	@test -f models/sd3.5_medium.safetensors || (echo "ERROR: run 'make model-sd35-safetensors' first"; exit 1)
	builds/sd-cpp/sd-cli \
		-m models/sd3.5_medium.safetensors \
		--clip_l models/clip_l-Q8_0.gguf \
		--clip_g models/clip_g-Q8_0.gguf \
		--t5xxl models/t5xxl-Q4_0.gguf \
		--clip-on-cpu --vae-on-cpu \
		--sampling-method euler --cfg-scale 4.5 --steps 25 \
		-H 512 -W 512 \
		-p "a red sports car on a mountain road at sunset, photorealistic" \
		-o /tmp/sd35_test.png -v
	@echo "Image saved: /tmp/sd35_test.png"

# Start SD 3.5 API server (sd-server on port 8091)
sd35-server:
	@test -f builds/sd-cpp/sd-server || (echo "ERROR: run 'make build-sd-cpp' first"; exit 1)
	@test -f models/sd3.5_medium.safetensors || (echo "ERROR: run 'make model-sd35-safetensors' first"; exit 1)
	@echo "Starting SD 3.5 server on port 8091..."
	builds/sd-cpp/sd-server \
		-m models/sd3.5_medium.safetensors \
		--clip_l models/clip_l-Q8_0.gguf \
		--clip_g models/clip_g-Q8_0.gguf \
		--t5xxl models/t5xxl-Q4_0.gguf \
		--clip-on-cpu --vae-on-cpu \
		--port 8091

# Benchmark Qwen3-8B vs current default model
benchmark-qwen3:
	.venv/bin/aicp --models benchmark --models-arg qwen3-8b

# =============================================================================
# Knowledge Base — sync to LocalAI /stores/
# =============================================================================

# Build the local-store backend from source (gallery version is broken)
build-local-store:
	@bash scripts/build-local-store.sh

# Sync KB + knowledge-map + project docs into LocalAI Collections
# Visible at http://localhost:8090/app/collections
kb-sync:
	@bash scripts/sync-kb-to-localai.sh

# Force re-sync: reset collection and re-upload everything
kb-sync-force:
	@bash scripts/sync-kb-to-localai.sh --force

# =============================================================================
# Monitoring stack (Prometheus + Grafana)
# =============================================================================

# Start monitoring stack (Prometheus on :9090, Grafana on :3000)
monitoring-up:
	docker compose --profile monitoring up -d
	@echo "Prometheus: http://localhost:9090"
	@echo "Grafana:    http://localhost:3000 (admin/aicp)"

monitoring-down:
	docker compose --profile monitoring down

monitoring-logs:
	docker compose --profile monitoring logs --tail 30

# =============================================================================
# Reliability & intelligent infrastructure (Stage 4+5)
# =============================================================================

health-report:
	.venv/bin/aicp --health-report

retry-dlq:
	.venv/bin/aicp --retry-dlq

dlq-status:
	.venv/bin/aicp --dlq-status

tasks:
	.venv/bin/aicp --tasks

extract-memories:
	.venv/bin/aicp --extract-memories

extract-memories-dry:
	.venv/bin/aicp --extract-memories-dry-run

# =============================================================================
# Agent daemon
# =============================================================================

agent-up: agent-down
	@mkdir -p .aicp
	@AGENT_TOKEN=$$(grep '^AICP_AGENT_SECRET=' .env 2>/dev/null | cut -d= -f2-); \
	if [ -n "$$AGENT_TOKEN" ]; then \
		AICP_AGENT_SECRET=$$AGENT_TOKEN nohup .venv/bin/aicp-agent > .aicp/agent.log 2>&1 & echo $$! > .aicp/agent.pid; \
	else \
		nohup .venv/bin/aicp-agent > .aicp/agent.log 2>&1 & echo $$! > .aicp/agent.pid; \
	fi; \
	sleep 1; \
	if kill -0 $$(cat .aicp/agent.pid) 2>/dev/null; then \
		echo "aicp-agent started (PID $$(cat .aicp/agent.pid)) on port 9100"; \
		if [ -n "$$AGENT_TOKEN" ]; then echo "  Auth: token from .env"; else echo "  Auth: NONE (run make fleet-init)"; fi; \
		if grep -qi microsoft /proc/version 2>/dev/null; then \
			echo "  WSL detected — checking LAN port forward for 9100..."; \
			if powershell.exe -NoProfile -Command "netsh interface portproxy show v4tov4" 2>/dev/null | tr -d '\r' | grep -q "9100"; then \
				echo "  Port forward: already configured"; \
			else \
				echo "  Port forward: NOT configured — LAN machines cannot reach this agent"; \
				echo "  Run: make wsl-forward"; \
			fi; \
		fi; \
	else \
		echo "aicp-agent failed to start:"; \
		cat .aicp/agent.log; \
	fi

agent-down:
	@if [ -f .aicp/agent.pid ]; then \
		kill $$(cat .aicp/agent.pid) 2>/dev/null && echo "aicp-agent stopped" || true; \
		rm -f .aicp/agent.pid; \
	fi
	@fuser -k 9100/tcp 2>/dev/null || true

# =============================================================================
# Fleet (multi-machine)
# =============================================================================

wsl-forward:
	@bash scripts/wsl-port-forward.sh 9100

wsl-forward-check:
	@bash scripts/wsl-port-forward.sh --check

wsl-forward-remove:
	@bash scripts/wsl-port-forward.sh --remove

fleet-init:
	@bash scripts/fleet.sh init

fleet-join:
	@bash scripts/fleet.sh join

fleet-status:
	@bash scripts/fleet.sh status

fleet-test:
	@bash scripts/fleet.sh test

fleet-copy:
	@bash scripts/fleet.sh copy

fleet-firewall:
	@bash scripts/fleet.sh firewall

p2p-token:
	@bash scripts/fleet.sh p2p-token

# =============================================================================
# Maintenance
# =============================================================================

update:
	git pull
	@if command -v uv >/dev/null 2>&1; then \
		uv pip install --python .venv/bin/python -e ".[dev]"; \
	else \
		.venv/bin/python -m pip install --quiet -e ".[dev]"; \
	fi
	@echo "Updated. If LocalAI config changed: make setup-local-only"

install-aliases:
	@bash scripts/install-aliases.sh

install-service:
	@bash scripts/install-service.sh install

uninstall-service:
	@bash scripts/install-service.sh uninstall
