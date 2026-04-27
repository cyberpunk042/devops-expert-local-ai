# AICP — Setup Guide

This document covers everything needed to get AICP running on a fresh machine. It also flags steps that were historically done manually and should be automated further.

---

## Prerequisites

| Requirement | Check | Notes |
|-------------|-------|-------|
| Python 3.8+ | `python3 --version` | 3.12 works fine |
| Docker | `docker --version` | 20+ recommended |
| NVIDIA GPU + drivers | `nvidia-smi` | Tested configs: single 8GB (RTX 3060 Ti), dual-GPU 8+11GB (RTX 2080 + RTX 2080 Ti). 6GB+ minimum. |
| CUDA 12+ | `nvidia-smi` shows CUDA version | Driver 560+ |
| NVIDIA Container Toolkit | `docker run --gpus all nvidia/cuda:12.0-base nvidia-smi` | Needed for GPU passthrough to Docker |
| Claude CLI | `which claude` | At `~/.local/bin/claude` on this machine |

### Install NVIDIA Container Toolkit (if not present)

```bash
# Ubuntu/Debian
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | \
  sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
  sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list
sudo apt-get update && sudo apt-get install -y nvidia-container-toolkit
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker
```

> **FLAG — MANUAL STEP:** This toolkit installation was done manually on the original machine. It is not scripted anywhere in this repo. Consider adding a `make check-docker-gpu` target that verifies GPU passthrough and prints install instructions if missing.

---

## Step 1: Clone and install Python package

```bash
git clone <repo-url> devops-expert-local-ai
cd devops-expert-local-ai

# One-shot setup (creates .venv, installs deps, creates models/)
make setup

# Activate the venv for your shell session
source .venv/bin/activate
```

> **FLAG — MANUAL STEP:** Shell profile integration (`source .venv/bin/activate` on login, shell aliases) is documented in README but not automated. See [Shell aliases](#shell-aliases) below.

---

## Step 2: Configure

```bash
# Review defaults — change model name, port, etc.
cat config/default.yaml

# Optional: copy .env.example and set env vars
cp .env.example .env
# Edit .env as needed
```

The default backend is `qwen3-8b` (set in [config/default.yaml](config/default.yaml)). Don't change `backends.local.model` unless you're swapping to a different LocalAI-served model.

---

## Step 3: Download a model

The fastest path: use the curated Qwen3 bundle.

```bash
make model-qwen3            # Qwen3-8B (main reasoning) + Qwen3-4B (fleet lightweight), 8GB GPU
make model-list-remote      # full catalog with VRAM info
```

This downloads GGUFs to `models/` AND drops the matching LocalAI YAML config alongside, so the alias (`qwen3-8b`) resolves correctly without manual config.

For other models (Gemma 4, custom GGUFs):

```bash
make model-download MODEL=<name>.gguf URL=<huggingface-url>
# Then create models/<name>.yaml manually (see config/models/*.yaml for templates)
```

The committed `config/models/*.yaml` files are the canonical source — they declare backend, context_size, gpu_layers tuned per model. Read those before authoring new ones.

---

## Step 4: Start LocalAI

```bash
make local-up
# Builds Docker image and starts LocalAI on http://localhost:8090
# Waits up to 30s for the API to respond
```

On first run, Docker will pull `localai/localai:latest-gpu-nvidia-cuda-12` (~5 GB). This only happens once.

---

## Step 5: Verify everything

```bash
make check
# Shows: config validity, GPU status, LocalAI availability, loaded models
# If configured model is not loaded, it will warn you

make models-list
# Lists all models LocalAI currently has available
```

Expected output on a healthy system (current dual-GPU + post-mission cloud config):

```
  Config: OK
  GPU 0 NVIDIA GeForce RTX 2080 Ti: 8950/11264 MiB free
  GPU 1 NVIDIA GeForce RTX 2080:    7043/8192 MiB free

  [OK]  local: OK (http://localhost:8090, models: qwen3-8b)
  [OK]  claude: OK (Claude Code CLI available)
  [OK]  openrouter: OK (355 models, default: qwen/qwen3-32b)
  [OK]  k2_6_openrouter: OK (default: moonshotai/kimi-k2.6)
  [OK]  ollama_cloud: OK (38 models, default: kimi-k2.6)

  Failover chain: local → k2_6_openrouter → openrouter → claude
  All systems ready.
```

(`k2_6_local` shows only when `--backend k2_6_local` is opted into for sovereignty mode — see [docs/architecture/post-anthropic-mission.md](docs/architecture/post-anthropic-mission.md).)

---

## Step 6: Use it

```bash
# Single query (think mode, local backend)
aicp "What does this project do?"

# Interactive chat
aicp -i

# Claude backend for complex tasks
aicp "Refactor this module" -m edit -b claude -d /path/to/project

# Run a pipeline
aicp --pipeline examples/analyze-pipeline.yaml
```

---

## Shell aliases

Add to `~/.bashrc` or `~/.zshrc`:

```bash
# AICP shortcuts
alias think='aicp -m think -b local'
alias ask='aicp -m think -b claude'
alias edit='aicp -m edit -b claude'
alias act='aicp -m act -b claude'
alias chat='aicp -i'
```

> **FLAG — MANUAL STEP:** These are documented in README but not installed automatically. Consider adding a `make install-aliases` target that appends them to the shell profile, or a `scripts/install-aliases.sh` that can be sourced.

---

## Updating

```bash
git pull
source .venv/bin/activate
pip install -e ".[dev]"   # picks up any new dependencies
```

> **FLAG:** There is no `make update` target. The Makefile has no upgrade path. Consider adding one.

---

## Running as a daemon

The AICP agent daemon (`aicp-agent`) can be run as a background service:

```bash
# Start the agent on port 9100
aicp-agent &

# Check health
curl http://localhost:9100/health
```

> **FLAG — MANUAL STEP:** There is no systemd unit file, Docker Compose service, or `make agent-up` target for the agent daemon. It was started manually. This should be automated for persistent deployments.

---

## Troubleshooting

| Problem | Likely cause | Fix |
|---------|-------------|-----|
| `aicp: command not found` | `.venv` not activated | `source .venv/bin/activate` |
| `No module named 'httpx'` | deps not installed | `pip install -e ".[dev]"` |
| `Cannot connect to LocalAI` | Container not running | `make local-up` |
| `WARNING: model 'qwen3-8b' not found` | model GGUF + YAML missing | `make model-qwen3` (downloads weights + writes config) |
| `docker compose build` fails | `backends/cuda12-llama-cpp` missing | Fixed — see [Dockerfile.localai](Dockerfile.localai) |
| GPU not detected in container | NVIDIA Container Toolkit missing | See Step 1 prerequisites |
| `pip not found` | system pip not installed | Use `python3 -m pip` or `python3 -m ensurepip` then `make setup` |
