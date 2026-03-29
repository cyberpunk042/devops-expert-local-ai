.PHONY: setup setup-force setup-claude-only setup-local-only setup-low-vram check-prereqs \
        local-up local-up-multi local-up-p2p local-down local-status local-logs \
        test test-all check lint format type-check auto-config benchmark self-test capabilities offload update \
        model-download models-list model-list-remote agent-up agent-down \
        fleet-init fleet-join fleet-status fleet-test fleet-copy fleet-firewall \
        install-aliases install-service uninstall-service db-rebuild \
        install-nvidia-toolkit extract-backend extract-backend-force extract-backend-only help

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
	@echo "  make models-list             Models currently loaded in LocalAI"
	@echo "  make model-download MODEL=<f> URL=<url>  Download a GGUF model"
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
