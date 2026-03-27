# Fleet Observability & Interaction — Milestone Plan

## Architecture Analysis (Definitive)

### Three Independent Systems

**1. `chat.send` — Internal/WebSocket Path (Used by MC)**
- MC calls `chat.send` via WS with `deliver=false`
- Gateway uses `INTERNAL_MESSAGE_CHANNEL` — no external channel needed
- Gateway ACKs immediately, runs agent asynchronously
- MC opens a NEW WebSocket per call, gets ACK, disconnects
- Agent response broadcasts to connected WS clients (MC is already disconnected)
- Normal task dispatch uses this path exclusively

**2. `agent` RPC Method — Outbound Delivery Path**
- Used by external integrations and CLI
- Requires a channel ONLY when `deliver=true`
- MC triggers this in exactly TWO places: nudge and ask-user coordination
- Normal task dispatch does NOT use this

**3. Channels (WhatsApp, Telegram, Discord, etc.)**
- Purpose: OUTBOUND delivery to external chat platforms
- Completely independent from `chat.send`
- Not needed for headless fleet operation

### MC's Built-in Provisioning System

MC already has a complete agent provisioning pipeline:

1. **Agent creation** (`POST /api/v1/agents`) auto-triggers provisioning
2. **Token minting**: `mint_agent_token()` generates a bcrypt-hashed token per agent
3. **TOOLS.md push**: Provisioning renders `BOARD_TOOLS.md.j2` and pushes to agent in OpenClaw via `agents.files.set` RPC
4. **TOOLS.md contents**: `BASE_URL`, `AUTH_TOKEN`, `AGENT_ID`, `BOARD_ID`, `WORKSPACE_ROOT`, OpenAPI discovery instructions
5. **SOUL.md push**: Agent instructions pushed alongside TOOLS.md
6. **Template sync**: `POST /api/v1/gateways/{id}/sync` re-provisions all agents

OpenClaw loads TOOLS.md and SOUL.md as bootstrap files — injected into agent context when running.

### Agent REST API (Already Built)

Agents authenticate with `X-Agent-Token` header. Key endpoints:
- `GET /api/v1/agent/boards/{board_id}/tasks` — list tasks
- `PATCH /api/v1/agent/boards/{board_id}/tasks/{task_id}` — update status, add comment
- `POST /api/v1/agent/boards/{board_id}/tasks/{task_id}/comments` — log progress
- `POST /api/v1/agent/boards/{board_id}/memory` — write to board memory (tags: chat, decision, plan)
- `POST /api/v1/agent/boards/{board_id}/approvals` — create approval requests
- `POST /api/v1/agent/heartbeat` — heartbeat/liveness
- `GET /api/v1/agent/healthz` — health check

### How Response Flow Works (End-to-End)

```
1. MC creates task, assigns to agent
2. MC calls chat.send(message, deliver=false) → agent's OpenClaw session
3. OpenClaw runs the agent (Claude Code backend)
4. Agent reads TOOLS.md → gets AUTH_TOKEN, BASE_URL, BOARD_ID
5. Agent calls MC REST API:
   - PATCH task status → "in_progress"
   - POST comments with progress
   - POST board memory with results
   - PATCH task status → "done" (or "review" if approval required)
6. MC sees updates via SSE streams + dashboard
7. Human observes, can intervene via board memory chat
```

### What's Actually Missing

Our `setup.py` calls `POST /api/v1/agents` which triggers provisioning. But we need to verify:
1. Did provisioning succeed? (TOOLS.md actually pushed to OpenClaw agents)
2. Are agents reading TOOLS.md when they run?
3. Does the agent's SOUL.md instruct it to call back to MC?

The SOUL.md templates currently have **no MC callback instructions**. Agents know their role
but don't know HOW to report back. MC's BOARD_TOOLS.md.j2 template provides the API
discovery mechanism (OpenAPI refresh + operation tables), but agents need explicit workflow
instructions in their SOUL.md.

## Revised Milestones

### M38: Verify and Complete Provisioning
**Goal**: Ensure agents are fully provisioned with credentials and callback knowledge.

Tasks:
1. Check if agent provisioning ran successfully during setup
   - Query MC for agent status (should be "active" not "provisioning")
   - Verify TOOLS.md was pushed to agents in OpenClaw (`agents.files.get`)
2. If provisioning didn't run, trigger template sync:
   - Call `POST /api/v1/gateways/{gateway_id}/sync`
   - Add to setup.py after agent registration
3. Update SOUL.md templates with MC workflow instructions:
   - Read TOOLS.md for credentials
   - Use MC REST API to update task status
   - Post results to board memory
   - Request approval when required
4. Push updated SOUL.md to agents (via sync or API)
5. Test: send message via `chat.send` → agent reads TOOLS.md → agent calls MC API → result visible

### M39: End-to-End Task Loop
**Goal**: Complete MC → OpenClaw → Agent → MC round-trip.

Tasks:
1. Create task in MC → assign to agent
2. MC dispatches via `chat.send` (deliver=false)
3. Agent receives instruction in OpenClaw session
4. Agent reads TOOLS.md, authenticates to MC
5. Agent updates task status, posts results
6. Result visible in MC dashboard
7. Add to setup.sh as a smoke test

### M40: Observation & Interaction
**Goal**: Human watches and participates in real-time.

Tasks:
1. SSE streams for real-time monitoring
2. Board memory chat for human↔agent interaction
3. Approval gates on critical tasks
4. @mention routing to specific agents
5. Test: human observes, intervenes, agent adapts

### M41: Coordination Features
**Goal**: Agent-to-agent and agent-to-human coordination.

Tasks:
1. For nudge/ask-user paths that need `deliver=true`:
   - Option A: Configure the built-in web channel
   - Option B: Modify those paths to use board memory callbacks instead
2. Lead agent coordination
3. Multi-agent task chains

### M42: AICP Skills
**Goal**: Reusable skills for fleet management from AICP.

- `openclaw-fleet-provision` — trigger template sync
- `openclaw-stream-monitor` — monitor SSE streams
- `openclaw-task-dispatch` — dispatch tasks from AICP
- `openclaw-observation-setup` — configure board observation

### M43: NNRT Autonomous Contribution
**Goal**: Fleet's first real mission on external project.
