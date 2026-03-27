# Fleet Channel Research — Findings

## The Problem

MC dispatches to OpenClaw agents using the `agent` WS method, which requires a configured channel for message delivery. Without a channel, MC can connect to the gateway but can't dispatch work.

## Research Findings

### How MC Dispatches to Agents
- MC calls `send_agent_message()` → `ensure_session()` + `send_message()` → `chat.send` RPC
- BUT the gateway's agent execution path also calls the `agent` RPC method
- The `agent` method requires a delivery channel to route responses
- MC's heartbeat also uses `agent` with `channel: heartbeat` (unknown to gateway)

### OpenClaw Channel Options
Built-in channels: WhatsApp, Telegram, Discord, IRC, Slack, Signal, iMessage, Google Chat, LINE, Mattermost, Teams
Community plugins: DingTalk, WeChat, Zulip, Meshtastic, and more

### Simplest Local Channel: IRC
- Built-in OpenClaw extension (32 source files — manageable complexity)
- Needs: IRC server (local), nick, optional NickServ
- Can run entirely local with a lightweight IRC daemon (e.g., miniircd, inspircd)
- No external service dependency
- Config: server, port, nick in openclaw.json channels.irc section

### Alternative: Discord
- Needs a bot token
- OpenClaw has built-in support
- Good for team visibility (others can see agent conversations)

### Key Insight
The `openclaw agent` CLI command works without a channel (`--reply-channel` is optional).
The issue is specifically in MC's dispatch through the gateway WS protocol, which triggers the `agent` method's outbound delivery path.

## Recommended Approach

### Short-term: IRC with local server
1. Install a lightweight IRC daemon (miniircd — single Python file)
2. Configure OpenClaw IRC channel pointing to localhost
3. MC dispatches work → gateway sends through IRC → agent responds through IRC
4. Human can observe IRC traffic (all conversations visible)
5. Add to setup.sh as part of fleet bootstrap

### Medium-term: Custom MC channel
Build a lightweight OpenClaw channel plugin specifically for Mission Control:
- Receives messages from gateway, posts to MC board memory
- Receives messages from MC board memory, sends to gateway
- No external service needed
- Purpose-built for fleet operation

### Long-term: Contribute upstream
Work with OpenClaw and MC communities to add native headless/fleet operation support.

## What This Means for Milestones

### M38: Set up IRC channel for fleet
- Install miniircd or similar
- Configure in openclaw.json
- Add to setup.sh and Makefile
- Test MC→IRC→Agent→IRC→MC flow

### M39: Verify full MC flow with channel
- Board onboarding completes
- Tasks dispatch to agents
- Results visible in MC dashboard
- Human can observe and interact

### M40+: Continue with the plan
- NNRT contribution, ocf-tag layers, etc.
