# Exploration Log — Local K2.6 Empirical Behavior on Tier 0 Hardware

**Date**: 2026-04-24
**Purpose**: Empirical record. What was tried, what was measured, what was observed. **Not a decision doc.** This captures the real behavior of K2.6 Q2 local serving on operator's X299 + WSL + PCIe 3.0 hardware, so future sessions don't have to re-learn from scratch.

**Scope**: the real experimental session of 2026-04-24 afternoon where we finally got llama.cpp serving K2.6 Q2 on this hardware, ran smoke tests, and measured actual throughput.

---

## 1. Hardware under test

| Component | Spec |
|---|---|
| Platform | X299 (LGA 2066), Skylake-X era |
| CPU | Intel i7-7800X (6c/12t, AVX-512 baseline, NO AMX, no DLBoost) |
| RAM | 64 GB DDR4-2666 quad-channel (~85 GB/s theoretical) |
| GPU | RTX 2080 Ti (11 GB) + RTX 2080 (8 GB) |
| NVMe | WD_BLACK SN770 1TB (Gen4 drive on PCIe 3.0 bus → Gen3 speed ceiling) |
| OS | Windows 11 + WSL2 Ubuntu 24.04 |
| WSL memory cap | 56 GB (from `.wslconfig`) |
| WSL swap | 16 GB |

## 2. Software under test

| Component | Version |
|---|---|
| llama.cpp | b8920 (15fa3c493), built with CUDA, -DCMAKE_CUDA_ARCHITECTURES=75 |
| Model | Unsloth Kimi-K2.6-GGUF UD-Q2_K_XL (318 GB, 8 shards) |
| Weight path | `/mnt/models/kimi-k2-6-q2/UD-Q2_K_XL/` |
| Storage mount | `/dev/sdc` → `/mnt/models` (VHDX on D:\, native ext4 inside WSL) |

## 3. Timeline of attempts (this session)

### Attempt 1: llama-server with `-ngl 20` + `--chat-template deepseek`

- **Command**: `-ngl 20 --ctx-size 4096 --chat-template deepseek`
- **What happened**: fit-check showed need for ~106 GB VRAM (20 layers × ~5.3 GB/layer at Q2); available was 19 GB total across 2 GPUs.
- **Key log lines**:
  ```
  common_params_fit_impl: projected memory use with initial parameters [MiB]:
    - CUDA0 (NVIDIA GeForce RTX 2080 Ti): 11263 total, 66676 used, -56571 free vs. target of 1024
  common_fit_params: failed to fit params to free device memory: n_gpu_layers already set by user to 20, abort
  ```
- **Observation**: llama.cpp printed the error but continued loading anyway, going into a state where it would have OOM'd mid-load. Killed before completion.
- **Lesson**: for K2.6 Q2 on this hardware, `-ngl` must be very small (probably 0-2 maximum).

### Attempt 2: `--override-tensor 'blk\.\d+\.ffn_(gate|up|down)_exps\.weight=CPU'` + `-ngl 99`

- **Theory**: put everything on GPU EXCEPT MoE experts (~95% of params), which get forced to CPU.
- **What happened**: VmRSS climbed toward 53 GB within minutes, growing as llama.cpp allocated actual CPU-side tensor buffers (not just mmap). At this rate projected to exhaust the 56 GB WSL cap before load completed.
- **Key behavior**: log warned:
  ```
  llama_model_loader: tensor overrides to CPU are used with mmap enabled
  — consider using --no-mmap for better performance
  ```
- **Root cause**: `--override-tensor =CPU` tells llama.cpp to ALLOCATE CPU memory for these tensors, not just rely on mmap paging. So it was on track to load ~300 GB of expert weights into RAM that doesn't exist.
- **Action**: killed before OOM.
- **Lesson**: MoE expert offload flags are stack-specific. llama.cpp's `--override-tensor =CPU` copies tensors, doesn't just tag them. For pure mmap behavior, drop the override and use `-ngl N` with small N.

### Attempt 3: `-ngl 0` with `--chat-template deepseek`

- **Command**: `-ngl 0 --ctx-size 4096 --chat-template deepseek`
- **Launch script**: `scripts/kt-serve.sh` (later superseded by `scripts/llama-serve.sh`)
- **Loading behavior**:
  - Process state: D (disk sleep) for ~17 min
  - VmRSS stabilized at ~53 GB during load (kernel managing page cache)
  - read_bytes grew from 0 to ~318 GB (full file scanned)
  - Rate: ~185-500 MB/s variable (cold page cache)
  - Memory managed by kernel eviction — never exceeded 54 GB RSS despite mmap of 283 GB address space
- **Load completion**:
  - Transitioned to S (sleeping, idle)
  - Port 8091 listening + `/v1/models` responding
  - `main: server is listening on http://0.0.0.0:8091`
- **Smoke test result**:
  - `curl /v1/chat/completions` with prompt "Reply with just the word HELLO" → returned: `"00\n00:00.000 --> 00"` (garbled, subtitle-like tokens)
  - Timing: 38 sec for 10 output tokens (0.3 tok/s)
- **Root cause of garbled output**: `--chat-template deepseek` overrode K2.6's embedded `chat_template.jinja`. K2.6 uses a different template (with `<|im_system|>`, `<|im_middle|>`, `<|im_end|>`, thinking tokens) than DeepSeek. The override caused input to be tokenized as non-chat content.
- **AICP smoke test**:
  - `aicp --backend k2_6_local "Identify yourself..."` — cold call
  - llama-server processed it: HTTP 200, generated 136 tokens
  - But total wall-time was 617 seconds; AICP's timeout was 600s
  - AICP flagged as failure, circuit breaker opened (`failure_threshold: 1`)
  - Failover chain triggered: `local → k2_6_local (timeout) → k2_6_openrouter (succeeded)`
  - User received coherent response from OpenRouter

### Attempt 4: `-ngl 0` without any `--chat-template` override (current working config)

- **Command** (via `scripts/llama-serve.sh`):
  ```
  --model ... --host 0.0.0.0 --port 8091 --n-gpu-layers 0 --ctx-size 4096
  --threads 4 --batch-size 512 --alias kimi-k2.6-q2
  ```
- **Load behavior**:
  - Process state: D (disk sleep) for ~80 minutes (much slower than Attempt 3's 17 min)
  - Read rate averaged ~85 MB/s (vs 185-500 MB/s first time — page cache was invalidated after kill of Attempt 3)
  - read_bytes grew to 599 GB during load (more than file size! indicates re-reading for tensor placement passes)
  - VmRSS stable at 53-54 GB throughout
- **Load completion (stage 6-8)**:
  - Transitioned from D → R (running) as tensor load finished
  - KV cache allocation: 274.5 MiB CPU-side
  - CUDA0 compute buffer: 3204.25 MiB (GPU side, for attention only since `-ngl 0`)
  - Flash Attention auto-enabled
  - Warmup empty run triggered
  - Total from launch to `server is listening`: ~85 minutes on cold page cache
- **Chat template CORRECT** this time:
  ```
  chat template, thinking = 1
  example_format: '<|im_system|>system<|im_middle|>You are a helpful assistant<|im_end|>
  <|im_user|>user<|im_middle|>Hello<|im_end|>
  <|im_assistant|>assistant<|im_middle|><think></think>Hi there<|im_end|>'
  ```
- **Smoke test**:
  - `curl` with prompt `"Reply with exactly: HELLO"` (14 input tokens)
  - 5 minute timeout hit (curl exit 28)
  - BUT server side completed: `prompt processing done, n_tokens = 14` → `stop processing: n_tokens = 16` → `done request: POST /v1/chat/completions 127.0.0.1 200`
  - Server canceled stream write when curl disconnected
  - `read_bytes` during this 5 min: 599 GB → 965 GB (+366 GB re-read!)
- **Interpretation**:
  - Server IS functionally serving requests
  - First request on top of freshly-loaded server: most experts weren't in page cache
  - Routing dispatched to experts not yet cached → cold disk reads
  - Effective per-token latency during this cold inference: 5 min ÷ 2 output tokens ≈ 2.5 min per token during cold inference
  - Warm inference (once a given routing path is cached) would be much faster

---

## 4. Measured numbers (empirical)

### Cold load

| Metric | Attempt 3 (with deepseek template) | Attempt 4 (correct template) |
|---|---|---|
| Launch to "server is listening" | ~17 min | ~85 min |
| Average read rate | 185-500 MB/s | ~85 MB/s |
| Total bytes read | ~318 GB | ~599 GB (multi-pass) |
| Peak RSS | 53-54 GB | 53-54 GB |
| CPU state during load | D (disk sleep) | D (disk sleep) |
| Ready | yes | yes |

**Why Attempt 4 was slower despite same hardware**: Attempt 3 was launched shortly after the 318 GB weights finished downloading — NTFS cache on Windows still warm from write, WSL page cache had some residuals. Attempt 4 was launched after `kill` of Attempt 3's process; that freed all guest page cache, and NTFS cache had since evicted some of the VHDX file pages. So Attempt 4 was reading cold from physical NVMe at true hardware speed (~85-300 MB/s effective through the WSL stack).

### Warm inference (first request after load)

| Metric | Value |
|---|---|
| Prompt (input) tokens | 14 |
| Output tokens generated | 2 |
| Wall-clock time | 5+ min (timed out curl-side at 5:00) |
| Effective output tok/s | ~0.01 (cold pass) |
| read_bytes during inference | +366 GB |
| RSS delta during inference | +5 GB (47 → 52) |

### Warm inference (second request — measured later in session, Experiment C)

**Measured 2026-04-24 16:35-16:42 EDT**. Same prompt as first request ("Reply with exactly: HELLO"), on the now-warmer page cache.

From llama-server's own `timings` field in the response:

| Metric | Value |
|---|---|
| Wall-clock total | **7 min 31 sec** |
| Input tokens | 14 |
| Input tokens cached | 13 (from prior request) |
| Input tokens fresh | 1 |
| Output tokens | 20 |
| Prompt prefill time | 15.4 sec (for the 1 fresh token) |
| Generation time | **445 sec (7 min 25 sec)** for 20 tokens |
| **Steady-state generation rate** | **0.045 tok/s** |
| **Per-token generation latency** | **22.3 sec/token** |

**Response content**:
```
content: ""
reasoning_content: "The user wants me to reply with exactly: HELLO\n
                    I need to make sure I output exactly"
```

K2.6 was in thinking mode (embedded template defaults `thinking=1`). Max tokens of 20 was consumed by reasoning chain BEFORE any actual `content` was produced. So: the "useful output" was never reached in this test.

**Critical empirical correction to earlier estimates**:
- Earlier architecture doc predicted 0.3-1 tok/s on Tier 0 warm
- **Reality on this specific hardware**: 0.045 tok/s — **~10× slower than estimate**
- The 0.3-1 tok/s figure was probably for newer-gen CPU (Alder Lake / Zen 4) without WSL overhead
- On i7-7800X + DDR4-2666 + WSL: real-world Tier 0 is **~0.04-0.08 tok/s**

**Updated practical meaning of Tier 0 K2.6 Q2 — WITH THINKING (default)**:
- 1 token: ~22 sec
- 20 tokens (cut-off thinking): ~7 min
- 100 tokens: ~37 min
- 500 tokens (typical agent round): **~3 hours**
- 1000 tokens (heavy response): **~6 hours**

### Experiment H — thinking mode disabled (measured third request)

**Measured 2026-04-24 16:49-16:50 EDT**. Same prompt, added `chat_template_kwargs: {"thinking": false}` in request body to disable K2.6's reasoning chain.

| Metric | Value |
|---|---|
| Wall-clock total | **51 sec** (vs 7min 31sec with thinking) |
| Input tokens | 15 (14 cached, 1 fresh) |
| Output tokens | 3 |
| Prefill ms | 21.7 sec |
| Generation ms | 30 sec for 3 tokens |
| **Per-token generation** | **10.0 sec/token** |
| **Generation rate** | **0.10 tok/s** (~2.2× faster than thinking-on) |
| finish_reason | "stop" (natural completion) |

**Response content**:
```
content: ""
reasoning_content: "HELLO"
```

llama.cpp's OpenAI-compat endpoint accepted `chat_template_kwargs: {"thinking": false}` passthrough. K2.6 in "instant mode" produced just "HELLO" as expected. llama.cpp captured the response in `reasoning_content` field rather than `content` — this is a parsing quirk, the answer itself is correct.

**Practical implication**: on Tier 0, thinking mode is the dominant per-request cost (6-10× token multiplier). Disabling it for simple/short queries dramatically changes tok/s wall time.

### Tier 0 practical numbers — WITH and WITHOUT thinking

| Response length | Thinking ON | Thinking OFF |
|---|---|---|
| 3 tokens ("HELLO") | ~7 min (thinking chain eats tokens) | **~1 min** |
| 20 tokens | ~7 min | **~3 min** |
| 100 tokens | ~37 min | **~17 min** |
| 500 tokens (typical agent round) | ~3 hrs | **~1.4 hrs** |
| 1000 tokens (heavy response) | ~6 hrs | ~3 hrs |

**Strategy implications for Tier 0 use**:
- Default to `thinking=false` for simple tasks (factual lookup, formatting, short answers)
- Use `thinking=true` only when reasoning chain is actually needed and time allows
- For client-work sovereignty, most practical use case is thinking-off

---

## 5. Theory vs reality — comparing predictions to measurements

### Prediction 1 (from `LOCAL-HOSTING-ARCHITECTURE` doc, section 5)

> Tier 0 (X299 + dual 2080 Ti) warm inference: **0.3-1 tok/s**

**Reality**: First request after load = 0.01 tok/s effective (5 min for 2 tokens). BUT most of that 5 min was cold expert loading, not steady-state inference. The 0.3-1 tok/s estimate applies to **warm steady-state inference after page cache has seen most-used experts**, which this first request didn't reach.

**Lesson**: "Warm" has sub-tiers on this hardware:
- **Freshly loaded but never served**: effectively cold page cache for inference (much of file read during load was metadata, not all of it ends up retained)
- **After ~10 diverse requests**: most commonly-routed experts cached → closer to 0.3-1 tok/s
- **After 100+ diverse requests**: page cache fully saturated with hottest experts → sustained 0.3-1 tok/s

### Prediction 2 (from `BOTTLENECKS-COMPLETE-HUNT` doc, section 12)

> Measured throughput is layer-6-limited (WSL) at ~500 MB/s; native Linux would be 1.5 GB/s

**Reality**: Attempt 4 measured at **85 MB/s effective**. That's 6× lower than the 500 MB/s I previously stated. Recalibration:

The 500 MB/s figure was from Attempt 3 when the file was freshly on disk and NTFS cache helped. In steady-state cold operation (what Tier 0 users will hit), effective throughput is **~85-150 MB/s through the WSL + VHDX + mmap + single-threaded fault stack**. 30× slower than NVMe raw.

**Lesson**: **WSL + mmap for big files is even more punishing than I estimated**. On cold page cache, the effective bandwidth is ~3% of physical NVMe.

### Prediction 3 (from earlier analyses)

> AICP circuit breaker + failover chain handles K2.6 local failures correctly

**Reality**: Confirmed exactly. When `k2_6_local` timed out (AICP's 600s limit was less than the 617s inference actually took), the breaker opened, failover chain kicked in, and `k2_6_openrouter` served the response. **Failover design validated.**

### Prediction 4 (from `HARDWARE-BUILD-SCENARIOS`, Tier 0 assessment)

> Tier 0 (current): "technically runs, mission minimum reached, NOT usable interactively"

**Reality**: Strongly confirmed. 5 min for 14-token prompt + 2 token response is the defining data point. Anything interactive is out. Use cases:
- ✅ Overnight batch jobs (patience-tolerant)
- ✅ Sovereignty fallback for offline/privacy-critical work
- ❌ Interactive chat
- ❌ Fleet agent runtime
- ❌ Real-time response

---

## 6. Surprising findings

### Finding 1: `read_bytes` exceeds file size during load

Attempt 4 showed `read_bytes` climbing past the 318 GB file size (to 599 GB during load, 965 GB after inference). This means llama.cpp is re-reading parts of the file during:
- Tensor placement decision (walks file multiple times)
- KV cache initialization
- Warmup empty run
- Actual inference (expert routing causes re-reads)

**Practical implication**: effective storage bandwidth requirement is **3× the file size** for a single load + single inference cycle on Tier 0 hardware. NVMe wear is higher than naive estimate.

### Finding 2: Page cache holds ~15% of file at steady state

Despite the process reading ~600 GB+ during load, VmRSS only ever held ~53 GB resident. **Only ~15% of the 318 GB file can be cached** on this 56 GB WSL cap (~47 GB available after kernel/app overhead).

**Implication**: each expert routing decision has ~85% chance of cache-missing and requiring disk re-read. This is fundamental to why inference is slow — not the compute, but the page fault storm.

### Finding 3: Chat template matters massively

The `--chat-template deepseek` override from `scripts/kt-serve.sh` (originally written for the sglang+kt-kernel + Moonshot-safetensors path, where template override was correct) produced completely broken output when applied to Unsloth Q2 GGUF:

- With override: `"00\n00:00.000 --> 00"` (garbage)
- Without override: coherent K2.6 thinking-mode response (needs full 5 min to complete on cold cache, but structure is right)

**Lesson**: GGUF files have embedded chat templates (`chat_template.jinja` in GGUF metadata). Overriding with a CLI flag is only correct when you specifically need to change it. Default should be trust-the-metadata.

### Finding 4: Second load on a cold cache is SLOWER than first load

Attempt 3: 17 min load. Attempt 4: 85 min load.

**Why**: killing Attempt 3's process freed all guest page cache. Windows-side NTFS cache of the VHDX also evicted between the two attempts. So Attempt 4 read cold from physical NVMe — the true hardware speed for this workload via the WSL stack.

**Implication for reboot behavior**: after any WSL restart, a fresh load will take ~60-90 min, NOT the ~17 min of the original load. Plan accordingly.

### Finding 5: Process state `D (disk sleep)` is NORMAL

In multiple moments during this exploration, I was tempted to intervene when seeing `State: D`. But `D` is uninterruptible disk sleep — a process in mmap-driven read is SUPPOSED to be in D until the disk returns data. It's not stuck; it's doing work.

**Heuristic**: as long as `read_bytes` keeps growing in `/proc/$PID/io`, the process is making progress. State D + flat read_bytes would indicate a hang.

---

## 7. Configuration that works — canonical

For future sessions re-launching local K2.6 on this hardware:

**Command**:
```bash
bash /home/jfortin/devops-expert-local-ai/scripts/llama-serve.sh
```

**Or equivalently**:
```bash
/mnt/dev-envs/llama.cpp/build/bin/llama-server \
    --model /mnt/models/kimi-k2-6-q2/UD-Q2_K_XL/Kimi-K2.6-UD-Q2_K_XL-00001-of-00008.gguf \
    --host 0.0.0.0 --port 8091 \
    --n-gpu-layers 0 \
    --ctx-size 4096 \
    --threads 4 \
    --batch-size 512 \
    --alias kimi-k2.6-q2
```

**Critical**:
- No `--chat-template deepseek` override (use embedded)
- `-ngl 0` or very small; do NOT use `-ngl 99` + `--override-tensor CPU` combo
- Expect 60-90 min cold load on fresh WSL boot
- Expect 2-5 min per request on cold page cache

**AICP config** (in `config/default.yaml`):
```yaml
backends:
  k2_6_local:
    base_url: http://localhost:8091
    model: kimi-k2.6-q2
    max_tokens: 8192
    timeout: 1800      # raised from 600 to absorb cold inference latency
    enabled: true

circuit_breaker:
  per_backend:
    k2_6_local:
      failure_threshold: 3  # raised from 1 to tolerate cold-start apparent timeouts
      recovery_timeout: 15
```

---

## 8. What Tier 0 actually IS for local K2.6

**Usable for**:
- Overnight batch workflows where latency is OK
- Periodic sovereignty-critical queries (accept 2-5 min wait)
- Proof-of-concept / sovereignty demonstration
- Background verification of AICP routing / failover logic
- Agent workloads that can tolerate slow per-request latency

**NOT usable for**:
- Interactive chat
- Real-time fleet agents (would need per-request <30s)
- Concurrent users
- Long-context work (4K ctx already tight; 32K would require much more RAM)
- Anything that makes "Claude Opus feels slow" feel fast

**Fundamental hardware-level limits observed**:
- ~0.01-0.3 tok/s effective throughput depending on cache state
- 5+ min first-request latency after fresh load
- 60-90 min cold-boot reload after WSL restart
- ~47 GB / 318 GB = 15% expert cache hit rate

---

## 9. What experiments would be valuable next

Deferred / not-yet-tried in this session:

### Experiment A: Small `-ngl` values (1, 2, 3)
**Hypothesis**: offloading 1-2 attention layers to GPU would cut attention compute by 5-10×. Most of the time is on experts (CPU-resident anyway), but attention at CPU-only is slow.
**Expected**: 2-4× throughput improvement on steady-state warm inference.
**Risk**: OOM on 11 GB VRAM if per-layer estimate is wrong; need to measure carefully.

### Experiment B: Larger `--ctx-size`
**Hypothesis**: at 4K context, we're not testing long-context behavior (where KV cache becomes the new bottleneck).
**Expected**: at 32K ctx, KV cache = ~25 GB additional RAM; would we still fit? Cold inference already at 5 min — 32K would be significantly worse.
**Risk**: OOM on 56 GB WSL cap.

### Experiment C: Second/third requests to measure warm-cache improvement
**Hypothesis**: first request is cold-expert-dominated; later requests touching same experts would be closer to theoretical ~0.3-1 tok/s.
**Expected**: dramatic speedup after cache warms.
**Method**: run 10 diverse requests, measure per-request latency curve.

### Experiment D: Increase WSL memory cap to 60 GB
**Hypothesis**: at 60 GB, page cache could hold ~55 GB of file → 17% cache vs 15% now. Marginal improvement.
**Risk**: Windows gets only 4 GB, likely unusable.

### Experiment E: Native Linux dual-boot
**Hypothesis**: removing WSL layer would cut load time ~40%, maybe similar on warm inference.
**Cost**: dual-boot setup, separation from Windows work.
**Value**: would empirically validate the 40% WSL-tax estimate.

### Experiment F: llama.cpp with `--numa distribute` on dual-GPU pass 
**Hypothesis**: doesn't apply (single-NUMA system), skip.

### Experiment G: Longer prompts
**Hypothesis**: prefill scales different than decode. Long prompts may actually be more efficient because of better GPU utilization during prefill.
**Expected**: prompts of 2K-4K tokens might have similar wall-clock to 14-token prompts once warm.

---

## 10. Process / memory observations — raw data

### Load process trajectory

```
T=0     launch | VmRSS=~100 MB, state=R | read_bytes=0
T=30s           | VmRSS=~2 GB, state=D   | read_bytes=100 MB
T=5min          | VmRSS=~25 GB, state=D  | read_bytes=25 GB
T=40min         | VmRSS=~53 GB, state=D  | read_bytes=120 GB
T=60min         | VmRSS=~53 GB, state=D  | read_bytes=200 GB
T=80min         | VmRSS=~53 GB, state=D  | read_bytes=540 GB  ← past nominal file size
T=85min         | VmRSS=~53 GB, state=R  | read_bytes=599 GB  ← load done, transitioning
T=85min+30s     | VmRSS=~47 GB, state=S  | read_bytes=599 GB  ← server listening
```

### Inference request trajectory (on cold cache)

```
T=0     curl sent | VmRSS=~47 GB | read_bytes=599 GB
T=30s             | VmRSS=~48 GB | read_bytes=650 GB  ← reading fresh experts
T=2min            | VmRSS=~50 GB | read_bytes=780 GB
T=4min            | VmRSS=~52 GB | read_bytes=900 GB
T=5min curl timeout | VmRSS=~52 GB | read_bytes=965 GB
T=5min+10s server completes task | srv log: "done request: 200, 16 tokens"
```

---

## 11. Questions this session answered

- **Can K2.6 Q2 be served on operator's hardware?** Yes.
- **How fast with thinking?** 0.045 tok/s warm-cache steady-state.
- **How fast without thinking?** 0.10 tok/s — 2.2× faster.
- **How long does it take to start?** 17-85 min first time, 60-90 min on subsequent cold boots.
- **Does prompt caching work?** Yes — identical prompts reuse ~95% of input tokens from cache.
- **Does K2.6 thinking mode toggle via OpenAI-compat API work?** Yes, via `chat_template_kwargs: {"thinking": false}`.
- **What's the realistic use case?** With thinking off, viable for short-response sovereignty queries (1-3 min each). With thinking on, overnight only.
- **Does AICP failover work correctly?** Yes.
- **What's the specific bottleneck?** WSL HCS layer + single-threaded mmap page faults + PCIe 3.0 NVMe + limited RAM for page cache + high per-token MoE expert-routing cost.

## 12. Questions this session left open

- What's the real warm-cache steady-state throughput after many diverse requests (not same prompt)?
- Would `-ngl 1` or `-ngl 2` meaningfully improve things without OOM?
- How does native Linux compare on exactly the same hardware (without WSL)?
- Would a smaller quantization (Q3_K_M, ~250 GB) fit better in cache and improve throughput?
- What's the actual loss from killing the llama-server and restarting (vs keeping it alive)?
- Why did llama.cpp store K2.6's instant-mode response in `reasoning_content` instead of `content`? Parser bug or template interaction?
- Does AICP's k2_6_local backend adapter forward the `chat_template_kwargs` field correctly? (Would need to pass through to cleanly use thinking-off mode via AICP)

---

## 13. Artifacts produced this session

| File | Purpose |
|---|---|
| `scripts/llama-serve.sh` | Canonical launch script for llama.cpp K2.6 Q2 on this hardware |
| `scripts/kt-serve.sh` (superseded) | Old sglang+kt-kernel launch; kept as historical artifact |
| `config/default.yaml` (edited) | Timeout 600→1800, breaker threshold 1→3 for k2_6_local |
| `/mnt/dev-envs/llama.cpp/build/` | Compiled llama.cpp binaries (version b8920) |
| `/mnt/models/kimi-k2-6-q2/UD-Q2_K_XL/` | 318 GB Unsloth Q2 GGUF weights, 8 shards |

---

## 14. References to other docs

- `LOCAL-HOSTING-ARCHITECTURE-2026-04-24.md` — the 9-layer stack + tier hierarchy (theory)
- `BOTTLENECKS-COMPLETE-HUNT-2026-04-24.md` — every bottleneck per layer (theory)
- `HARDWARE-BUILD-SCENARIOS-2026-04-24.md` — what upgrading would buy you (theory)
- `CLOUD-SPEND-SCENARIOS-2026-04-24.md` — cloud alternative economics (theory)
- `SCALING-PROJECTION-5YR-2026-04-24.md` — 5-year projection (theory)
- `PERSPECTIVE-AI-INFRASTRUCTURE-DECISION-2026-04-24.md` — decision framework (theory)
- `MODEL-ECOSYSTEM-FULL-MAP-2026-04-24.md` — all provider options (theory + verified pricing)
- `POSTMORTEM-2026-04-24-k26-local-wrong-path.md` — what went wrong over 2 days
- `SESSION-2026-04-24-HANDOFF.md` — index
- `SESSION-2026-04-24-CONVERSATION-LOG.md` — chronological narrative
- **This document**: the empirical record

---

*Exploration log. Captures what we learned by doing. Reference when future sessions ask "what actually happens when you run K2.6 Q2 on Tier 0 hardware?"*
