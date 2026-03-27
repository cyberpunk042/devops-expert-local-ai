# AICP — Setup Guide

This document covers everything needed to get AICP running on a fresh machine. It also flags steps that were historically done manually and should be automated further.

---

## Prerequisites

| Requirement | Check | Notes |
|-------------|-------|-------|
| Python 3.8+ | `python3 --version` | 3.12 works fine |
| Docker | `docker --version` | 20+ recommended |
| NVIDIA GPU + drivers | `nvidia-smi` | RTX 3060 Ti (8 GB) confirmed working |
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

The only value you likely need to change is `backends.local.model` — it must match the filename (without `.gguf`) of the model you download in Step 3.

---

## Step 3: Download a model

LocalAI needs at least one GGUF model in the `models/` directory.

```bash
# Example: Hermes-2-Pro-Mistral 7B (Q4_K_M quantization, ~4.4 GB)
make model-download \
  MODEL=hermes-2-pro-mistral-7b.Q4_K_M.gguf \
  URL=https://huggingface.co/NousResearch/Hermes-2-Pro-Mistral-7B-GGUF/resolve/main/Hermes-2-Pro-Mistral-7B.Q4_K_M.gguf

# The model name in config/default.yaml must match (without .gguf):
# backends.local.model: "hermes-2-pro-mistral-7b.Q4_K_M"
```

> **FLAG — MANUAL STEP:** Model selection and download URLs were chosen manually on the original machine. The `config/default.yaml` value `model: "hermes"` implies a short alias — LocalAI can use a `models/hermes.yaml` config file to map the alias to a GGUF file. That YAML file (LocalAI model config) was likely present on the original machine but is **not committed to this repo**. You need to either:
> - Use the full GGUF filename as the model name, or
> - Create `models/hermes.yaml` — see [LocalAI model config](#localai-model-config) below.

### LocalAI model config

To use a short alias like `hermes`, create `models/hermes.yaml`:

```yaml
name: hermes
backend: llama-cpp
parameters:
  model: hermes-2-pro-mistral-7b.Q4_K_M.gguf
  context_size: 4096
  gpu_layers: 35   # adjust based on VRAM — RTX 3060 Ti (8 GB) can handle ~35 layers for 7B
```

> **FLAG:** This file is gitignored (models/ is not tracked). Add `models/*.yaml` to version control, or add a `models/hermes.yaml.example` template to the repo.

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

Expected output on a healthy system:

```
  Config: OK
  GPU 0 RTX 3060 Ti: 7400/8192 MiB free (driver 560.94)

  local  OK (http://localhost:8090, models: hermes)
  claude UNAVAILABLE: claude CLI not in PATH   ← only if claude not installed

  All systems ready.
```

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
| `WARNING: model 'hermes' not found` | model file missing | Download GGUF, create `models/hermes.yaml` |
| `docker compose build` fails | `backends/cuda12-llama-cpp` missing | Fixed — see [Dockerfile.localai](Dockerfile.localai) |
| GPU not detected in container | NVIDIA Container Toolkit missing | See Step 1 prerequisites |
| `pip not found` | system pip not installed | Use `python3 -m pip` or `python3 -m ensurepip` then `make setup` |
