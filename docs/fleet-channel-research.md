# Fleet Channel Research — Definitive Findings

## The Original Problem

MC dispatches tasks to agents via `chat.send` → gateway returns ACK. We assumed the
"Channel is required (no configured channels detected)" error was blocking this flow.

## What We Found

### The error is NOT on the task dispatch path.

MC calls `chat.send` with `deliver=false`. When `deliver=false`, the gateway uses
`INTERNAL_MESSAGE_CHANNEL` — no external channel needed. The ACK comes back immediately
and the agent runs asynchronously. This path works without any channel configuration.

### Where the error actually comes from

`resolveMessageChannelSelection()` in `infra/outbound/channel-selection.ts:201` throws
"Channel is required" when:
1. `deliver=true` is set
2. No channel is explicitly specified
3. No channels are configured in openclaw.json

MC triggers this in exactly TWO places:
- **Agent nudge** (`coordination_service.py:199`) — `deliver=True`
- **Ask user via gateway main** (`coordination_service.py:468`) — `deliver=True`

Normal task dispatch always uses `deliver=False` (`tasks.py:575`, `tasks.py:592`).

### How responses flow back

MC's RPC pattern is fire-and-forget:
1. Connect WS → authenticate → send `chat.send` → receive ACK → disconnect
2. Agent runs asynchronously
3. Agent output broadcasts to connected WS clients (MC already disconnected)

Agents report results back to MC via **REST API** — posting to board memory:
```
POST /api/v1/agent/boards/{board_id}/memory
Body: {"content":"<result>","tags":[...],"source":"..."}
```

This is explicit in MC's coordination messages. The agents use MC's REST API as their
"response channel", completely bypassing OpenClaw's outbound channel system.

## Revised Understanding

### Chat (`chat.send`) and Channels are INDEPENDENT

| Feature | `chat.send` | Channels |
|---------|-------------|----------|
| Purpose | Send message to agent session | Outbound delivery to external platforms |
| Used by | MC, Control UI, gateway CLI | WhatsApp, Telegram, Discord, etc. |
| Channel needed? | No (uses INTERNAL_MESSAGE_CHANNEL) | Yes (that IS the channel) |
| Response path | WS broadcast to connected clients | External platform delivery |
| MC uses? | Yes, for all task dispatch | Only for nudge/ask-user coordination |

### What's Actually Needed for End-to-End

1. **Agent SOUL.md with callback instructions** — tell agents how to POST results to MC
2. **Agent MC API tokens** — agents need auth to call MC's REST API
3. **For coordination features** — either configure a channel OR use `deliver=false` + callbacks

### A channel plugin is NOT needed for basic operation.

The original plan to build an MC channel plugin was based on a misunderstanding.
Channels are for OUTBOUND delivery to external platforms. MC already has its own
communication path: REST API + board memory + SSE streams.

## Impact on Milestones

The channel blocker is resolved. M38 becomes "Agent Callback Infrastructure" instead
of "Study OpenClaw Plugin SDK". The path forward is:
1. Configure agents to call back to MC via REST API
2. Test the full task dispatch → execution → callback loop
3. Add coordination features (nudge/ask-user) later with optional channel config
