# Knowledge Map System

## Minimal
Metadata-driven context injection: analyzes prompt intent, selects injection profile based on model context window, assembles relevant knowledge from KB into prompt.

## Condensed

### Purpose
Ensure each LLM gets exactly the right knowledge — not too much (wastes tokens), not too little (misses context). Adapts injection depth to model capability.

### Components
- **navigator.py** — Navigator: match_intent(), select_profile(), assemble_context()
- **docs/knowledge-map/_schema.yaml** — metadata format for map entries
- **docs/knowledge-map/injection-profiles.yaml** — 4 tiers of injection depth
- **docs/knowledge-map/intent-map.yaml** — 9 intents mapping task → injection rules
- **docs/knowledge-map/systems/** — condensed/minimal system documentation

### Injection Profiles
| Profile | Context | Budget | Use Case |
|---------|---------|--------|----------|
| opus-1m | 1M tokens | 50K | Full system docs, all tools, complete manuals |
| sonnet-200k | 200K tokens | 15K | Condensed docs, key tools, essential config |
| localai-8k | 8K tokens | 3K | Minimal identity, top-1 RAG result |
| heartbeat | any | 0 | No injection — just the prompt |

### Intent Matching (two-pass)
1. **Keywords first** — specific task types (code, fleet, model, rag, config)
2. **Complexity then** — analyze_complexity() score for general routing

### Flow
```
Prompt → match_intent() → select_profile(model)
  → get_injection_spec() → {profile, intent, branches, budget}
  → assemble_context() → augmented prompt with KB context
```

### Integration Points
- Controller calls navigator.assemble_context() before backend.execute()
- KB provides RAG search results for context blocks
- Router's analyze_complexity() feeds intent matching
