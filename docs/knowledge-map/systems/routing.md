# Routing System

## Minimal
Multi-backend task router with 4-tier ranking (local → openrouter → claude), confidence scoring, cost awareness, and dynamic model selection.

## Condensed

### Purpose
Routes each task to the optimal backend based on complexity, cost, and availability. Prevents unnecessary Claude token spend by handling simple tasks locally.

### Components
- **router.py** — classify_task(), recommend_model(), analyze_complexity(), score_response_quality(), estimate_cost()
- **controller.py** — run() orchestrates routing, failover, cache, quality escalation
- **config/default.yaml** — backend config, model assignments, routing thresholds

### Routing Flow
```
Prompt → analyze_complexity() → score 0.0-1.0
  → 0.0-0.3: local (qwen3-8b-fast, no thinking)
  → 0.3-0.6: local (qwen3-8b, thinking) or openrouter
  → 0.6-1.0: claude (opus)
```

### Model Selection (LocalAI auto_route)
- Fleet ops → qwen3-4b (lightweight)
- Code tasks → qwen3-8b (thinking enabled)
- Simple tasks → qwen3-8b-fast (no thinking)
- Complex → default model with thinking

### Failover Chain
local → fleet peer → openrouter → claude

### Quality Escalation
If response quality < 0.25, auto-retry on next tier backend.

### Key Config
```yaml
backends.local.auto_route: true    # enable model selection
backends.local.fast_model: qwen3-8b-fast
quality_threshold: 0.25            # auto-escalation trigger
cache.enabled: true                # skip inference for repeated prompts
```
