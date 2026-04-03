# Guardrails System

## Minimal
Permission enforcement: Think mode blocks writes, Edit mode restricts paths, Act mode allows controlled commands. Secret scanning on all responses.

## Condensed

### Purpose
Prevent AI backends from exceeding their permissions. Protect secrets, forbidden paths, and enforce mode constraints.

### Components
- **checks.py** — run_preflight_checks(): validates project path, mode compatibility, forbidden paths before execution
- **paths.py** — is_path_allowed(): glob-based allowlist/denylist for file operations
- **response.py** — scan_think_mode(): blocks shell/write patterns in think mode; scan_response_secrets(): detects AWS keys, JWTs, private keys, GitHub PATs

### Three Modes
| Mode | Can Read | Can Write | Can Execute |
|------|----------|-----------|-------------|
| Think | Yes | No | No |
| Edit | Yes | Scoped paths | No |
| Act | Yes | Yes | Allowlisted commands |

### Forbidden Patterns (always blocked)
`.env`, `.env.*`, `*.key`, `*.pem`, `*credentials*`, `*secret*`

### Secret Detection
Scans every response regardless of mode/backend for:
- AWS access keys (`AKIA...`)
- JWT tokens (`eyJ...`)
- Private key blocks (`-----BEGIN`)
- GitHub PATs (`ghp_...`)
- Bearer tokens, password= patterns

### Key Config
```yaml
guardrails:
  forbidden_patterns:
    - .env
    - '*.key'
    - '*credentials*'
  # allowed_paths: [src/, docs/]  # per-project whitelist
```
