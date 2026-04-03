# LocalAI v4.0.0 Capabilities Reference

**Type:** Infrastructure Reference
**Date:** 2026-04-03
**Status:** VERIFIED — inspected from running container
**Container:** devops-expert-local-ai-localai-1

---

## Version

- **LocalAI:** v4.0.0
- **Image:** `localai/localai:v4.0.0-gpu-nvidia-cuda-12`
- **Custom Dockerfile:** `Dockerfile.localai` (extracts backends from quay.io OCI)

---

## Compiled Backends

| Backend | Path | Purpose |
|---------|------|---------|
| `cuda12-llama-cpp` | `/backends/cuda12-llama-cpp/` | GPU inference (CUDA 12) |
| `whisper` | `/backends/whisper/` | Speech-to-text |
| `piper` | `/backends/piper/` | Text-to-speech |

### llama-cpp Variants

| Binary | CPU Feature | Used When |
|--------|------------|-----------|
| `llama-cpp-avx2` | AVX2 | Default on modern CPUs |
| `llama-cpp-avx512` | AVX-512 | Intel Xeon / newer |
| `llama-cpp-avx` | AVX | Older CPUs |
| `llama-cpp-fallback` | None | Universal fallback |
| `llama-cpp-grpc` | gRPC server | Multi-process mode |
| `llama-cpp-rpc-server` | RPC | Distributed inference |

---

## Supported Model Architectures (from binary inspection)

Confirmed in `llama-cpp-avx2`:

| Architecture | Models | Source File |
|-------------|--------|------------|
| qwen | Qwen 1.x | `models/qwen.cpp` |
| qwen2 | Qwen 2 / 2.5 | `models/qwen2.cpp` |
| qwen2moe | Qwen 2 MoE | `models/qwen2moe.cpp` |
| qwen2vl | Qwen 2 Vision-Language | `models/qwen2vl.cpp` |
| **qwen3** | **Qwen 3 dense** | `models/qwen3.cpp` |
| **qwen3moe** | **Qwen 3 MoE** | `models/qwen3.cpp` |
| llama | Llama 1/2/3, Hermes, etc. | (various) |
| mistral | Mistral, Hermes-Mistral | (various) |
| phi | Phi-2, Phi-3 | (various) |
| codellama | CodeLlama | (via llama arch) |
| gemma | Gemma | (various) |
| falcon | Falcon | (various) |

---

## Key Features Enabled

| Feature | Config Key | Our Setting | Notes |
|---------|-----------|-------------|-------|
| KV cache quantization | `cache_type_k`, `cache_type_v` | `q4_0` | ~4x VRAM savings on context |
| Flash attention | `flash_attention` | `true` | Faster attention, less VRAM |
| Prompt caching | `prompt_cache_path` | per-model | Reuse KV cache across requests |
| Mmap | `mmap` | `true` | Memory-mapped model loading |
| Mmlock | `mmlock` | `true` | Lock model in RAM |
| Parallel requests | `LLAMACPP_PARALLEL` | 2 | 2 concurrent slots |
| Watchdog | `LOCALAI_WATCHDOG_*` | enabled | Auto-recover stuck backends |
| LRU eviction | `LOCALAI_MAX_ACTIVE_BACKENDS` | 3 | Evict least-used models |
| Tracing | `LOCALAI_ENABLE_TRACING` | true | Request tracing |
| Metrics | `/metrics` | enabled | Prometheus endpoint |

---

## GPU Configuration

- **Device:** NVIDIA via WSL2 `/dev/dxg`
- **VRAM:** 8 GB
- **CUDA:** 12
- **Expose:** `NVIDIA_VISIBLE_DEVICES=0`
- **Container device:** `/dev/dxg:/dev/dxg`

### Dual GPU (Future)

For 8GB + 11GB setup, docker-compose needs:

```yaml
devices:
  - /dev/dxg:/dev/dxg
deploy:
  resources:
    reservations:
      devices:
        - driver: nvidia
          device_ids: ["0", "1"]
          capabilities: [gpu]
```

And model YAML needs tensor splitting:

```yaml
# Split proportional to VRAM: 8/(8+11) = 0.42, 11/(8+11) = 0.58
tensor_split: "0.42,0.58"
```

---

## Docker Environment Variables (Complete)

```yaml
THREADS: 4                          # CPU threads
LLAMACPP_PARALLEL: 2                # Concurrent request slots
CONTEXT_SIZE: 16384                 # Default context (overridden per model)
LOCALAI_PARALLEL_REQUESTS: true     # Enable parallel mode
LOCALAI_WATCHDOG_IDLE: true         # Kill idle backends
LOCALAI_WATCHDOG_IDLE_TIMEOUT: 15m
LOCALAI_WATCHDOG_BUSY: true         # Kill stuck backends
LOCALAI_WATCHDOG_BUSY_TIMEOUT: 10m
LOCALAI_SINGLE_ACTIVE_BACKEND: false
LOCALAI_MAX_ACTIVE_BACKENDS: 3      # LRU eviction threshold
LOCALAI_DATA_PATH: /data            # Persistent data
LOCALAI_ENABLE_TRACING: true
LOCALAI_LOG_FORMAT: json
LOCALAI_API_KEY: (from .env)
```

---

## Upgrade Path

Current: `v4.0.0` — supports Qwen3 already.

If future upgrade needed:
1. Edit `FROM` tag in `Dockerfile.localai`
2. Extract new backends from quay.io via `scripts/extract-backend.sh`
3. `make setup-force` to rebuild
4. Test all model configs before committing
