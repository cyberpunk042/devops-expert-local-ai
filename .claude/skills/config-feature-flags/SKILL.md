---
name: config-feature-flags
description: Manage AICP's feature-toggle pattern — there is NO dedicated feature-flag system; toggles are expressed via profile YAMLs (per-environment) + config keys (`enabled: true/false` flags in `config/default.yaml`) + env vars for one-off runs. Use this skill to add a new toggle, audit existing toggles, or migrate an ad-hoc toggle into the profile system. Loads when the operator says "add a feature flag" / "toggle feature X off in prod" / "what features can I disable" / "where do feature flags live".
allowed-tools: Read, Write, Edit, Bash, Glob, Grep
effort: low
---

# config-feature-flags

Manage AICP's feature-toggle approach. AICP does NOT use a dedicated
feature-flag service (LaunchDarkly, GrowthBook, etc.) — toggles live in:

1. **Config keys** with `enabled: true/false` semantics in `config/default.yaml`
2. **Profile overlays** for per-environment behavior (e.g., `reliable.yaml`
   enables circuit-breaker tighter thresholds; `offline.yaml` disables
   cloud backends)
3. **Env vars** for one-off runs (e.g., `AICP_DEFAULT_BACKEND`)

This skill is the lifecycle operator for "add a toggle", "audit toggles",
or "migrate an ad-hoc bool into the profile system".

## Trigger phrases (when to load this skill)

Load when the conversation matches any of:

- **Direct verb**: operator says "add a feature flag", "toggle feature X
  off in prod", "what features can I disable", "where do feature flags live"
- **Migration**: operator notices a bool flag scattered in code (e.g.,
  `if ENABLED:` constant) — promote into config
- **Audit**: enumerate which features are togglable for a security/ops
  review
- **Per-env behavior**: operator wants feature X enabled in dev but disabled
  in prod — choose between profile overlay vs env var

Do NOT load when:

- The concern is per-deploy profile selection (load `config-deploy`)
- The concern is environment variable lifecycle generally (load `config-env`)
- The concern is config schema migration (load `config-migrations`)
- The concern is adding a NEW feature with toggle (load `feature-implement`
  for the implementation; this skill governs the toggle shape)

## Operations

### Operation 1 — Add a new feature toggle

**When**: a new feature needs to be enable/disable-able per environment
or per invocation.

**Process**:

1. Decide the toggle SCOPE:
   - Per-environment → add to `config/default.yaml` with `enabled: true`,
     override in `config/profiles/<env>.yaml` to `enabled: false`
   - Per-invocation → support an `AICP_<FEATURE>_ENABLED` env var read at
     runtime
   - Both → support both, with profile overlay being the primary surface
2. Add the config key to `default.yaml` (the schema source of truth):
   ```yaml
   <feature_name>:
     enabled: true  # or false for opt-in features
     # other config under same prefix
   ```
3. In code: read via `config.get("<feature_name>", {}).get("enabled", <default>)`
4. Document in CLAUDE.md or feature documentation: which profiles enable
   it by default, what disabling implies for behavior
5. If the feature has security/safety implications, also load `infra-security`
   for review of the disable path

**Quality bar**: the DEFAULT in `default.yaml` reflects the most-common
expected state; profiles override for the minority environments. Don't
default to `false` and require every profile to enable it — that scales
poorly.

### Operation 2 — Audit existing feature toggles

**When**: review which AICP features are togglable.

**Process**:

1. Search for `enabled:` keys in config: `Grep -nE "^\s*enabled:" config/`
2. Search for env-var toggle reads: `Grep -nE "os\.environ\.get\(.AICP_.*ENABLED" aicp/`
3. Search for code-level toggles (less ideal — should migrate to config):
   `Grep -nE "(ENABLED|DISABLED)\s*=\s*(True|False)" aicp/`
4. Build a table: feature × default state × profile overrides × env var
5. Report ad-hoc code-level toggles as candidates for migration to config

**Quality bar**: every togglable feature should be discoverable from
`config/default.yaml` (or env var, listed in `.env.example`). Code-level
constants are operationally invisible.

### Operation 3 — Migrate an ad-hoc bool to the profile system

**When**: Operation 2 found a code-level constant that should be a config-driven toggle.

**Process**:

1. Identify the constant's intent (per-env vs per-invocation)
2. Add the new config key to `default.yaml` with the SAME default value
   the constant currently has (zero behavioral change)
3. Change the code to read from config instead of the constant
4. Remove the constant
5. Add profile overrides if any environment needs different behavior
6. Run pytest to verify no behavioral change
7. Document the new toggle in CLAUDE.md or AGENTS.md

**Quality bar**: the migration is behavior-preserving by default. Profile
overrides come AFTER the migration is verified.

## Gotchas

- **Detection**: agent adds a code-level `ENABLED = True` constant.
  **Rule**: feature toggles go in config (or env var), NOT code constants.
  **Reasoning**: code constants are operationally invisible — operators
  can't toggle them without editing code.

- **Detection**: agent defaults a feature to `false` when most environments
  want it on.
  **Rule**: default to the MAJORITY expected state; override the minority.
  **Reasoning**: scaling overrides across N profiles is more error-prone
  than overriding the exception.

- **Detection**: agent treats AICP as if it has a LaunchDarkly-style flag service.
  **Rule**: AICP uses static config + profiles + env vars. There is no
  dynamic flag fetcher.
  **Reasoning**: setting expectations correctly avoids architectural
  drift toward a runtime flag service that doesn't exist.

- **Detection**: agent puts a security toggle in env var only (no profile default).
  **Rule**: security toggles need profile defaults so unconfigured environments
  inherit the safe state.
  **Reasoning**: env-var-only toggles are easy to forget; profile defaults
  ensure the safe state is the fallback.

## Reference exemplars

- `config/default.yaml` — `rag.enabled`, `cluster.auto_route` etc. as
  example feature toggles
- `config/profiles/offline.yaml` — overrides backend chain to disable
  cloud (a feature-toggle-via-profile example)
- `config/profiles/reliable.yaml` — overrides DLQ + circuit_breaker
  thresholds (multi-knob profile, includes toggles)
- `aicp/config/loader.py` — config overlay logic that materializes the
  effective toggle states

## Domain context

AICP intentionally avoids a dynamic feature-flag service to keep
runtime simple and operator-inspectable. All toggles are statically
declared (config + profile + env var) — a `aicp --profile-cmd show`
output reveals the complete toggle state for the active profile. This
trades the flexibility of dynamic flags for operational transparency
and zero dependency on an external flag service.

## Related skills

| Skill | When to use |
|-------|-------------|
| `config-env` | When the toggle lifecycle is broader env var management |
| `config-deploy` | When the concern is which profile activates per environment |
| `config-migrations` | When a toggle's schema changes between releases |
| `infra-security` | When the toggle has security implications |
| `feature-implement` | When implementing the gated feature itself |
