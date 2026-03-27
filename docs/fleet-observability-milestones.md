# Fleet Observability & Interaction — Milestone Plan

## What We Know

### OpenClaw Channel System
- 9 built-in channels (Telegram, WhatsApp, Discord, etc.)
- NO dedicated "headless/API" channel — agents communicate through chat channels
- Control UI at gateway port communicates via WebSocket SPA
- MC connects as an RPC client, NOT as a channel
- The "Channel is required" error blocks MC→Agent message delivery

### Mission Control Observation Features (Already Built)
- **Activity Events**: audit trail with event_type, message, agent_id, task_id, board_id
- **SSE Streams**: real-time feeds for approvals, board memory, task comments (2s polling, 15s heartbeat)
- **Board Memory**: persistent context storage + bidirectional chat between humans and agents
  - Tagged "chat" entries auto-notify running agents
  - @mentions route to specific agents
  - Supports /pause and /resume commands
- **Approval System**: pending/approved/rejected with confidence scores, rubric_scores, multi-task linking
  - Resolution notifies board lead agent
  - SSE stream for real-time approval updates
- **Task Comments**: agents post results, humans can add comments, SSE stream available

### What This Means
MC already has most of what we need for observation and interaction:
- Board Memory chat = human↔agent real-time communication
- Task comments = agent output visible to humans
- Approval system = human gates on agent work
- SSE streams = real-time observation without polling

The MISSING piece is the channel for MC→Agent message delivery.

## The Channel Problem — Options

### Option A: Configure a minimal channel
Set up one lightweight channel (e.g., Telegram bot or Discord bot) that MC routes through.
- Pro: uses existing OpenClaw infrastructure
- Con: adds an external dependency just for internal communication

### Option B: Use the Control UI channel
The gateway's built-in web UI communicates through WebSocket. MC could connect the same way.
- Pro: no external dependency
- Con: may not be designed for MC's dispatch pattern

### Option C: Build an MC channel plugin for OpenClaw
Create an OpenClaw plugin that acts as a "Mission Control channel" — receives messages from MC and delivers them to agents without a chat platform.
- Pro: clean architecture, purpose-built
- Con: requires understanding OpenClaw's plugin SDK

### Option D: Bypass the channel requirement
Modify the fleet's gateway interaction to use `agent` method with a session directly, bypassing channel routing.
- Pro: simplest, no new components
- Con: may not trigger all of OpenClaw's agent lifecycle properly

### Recommended: Option C (MC Channel Plugin)
This is the most architecturally sound approach. It:
- Fits OpenClaw's extension model (plugins)
- Gives MC a proper channel identity
- Allows full agent lifecycle (sessions, memory, tools)
- Is reusable for any MC↔OpenClaw integration

## Milestones

### M38: Study OpenClaw Plugin SDK
- Read plugin SDK documentation and source
- Understand channel plugin interface
- Map what a "mission-control" channel needs to implement
- Design the plugin architecture

### M39: Build MC Channel Plugin for OpenClaw
- Create openclaw-mc-channel plugin
- Implements: receive message from MC, deliver to agent session, return response
- Register as an OpenClaw channel
- Add to fleet's setup.sh

### M40: Configure Observation in MC
- Enable SSE streams for real-time monitoring
- Configure board memory chat for human↔agent interaction
- Set up approval gates on edit/act tasks
- Test: human sees agent work in real-time, can add input

### M41: Build AICP Skill for Dashboard Components
- Skill: `openclaw-add-dashboard-component`
- Can add custom views/widgets to MC
- Uses MC's API to create custom fields, views, activity feeds
- Parameterized: component type, board, config

### M42: End-to-End Flow Test
- Human creates task in MC → agent picks it up → executes → posts result
- Human observes in real-time via SSE/board memory
- Human adds input mid-execution via board memory chat
- Agent incorporates input → completes task
- Human approves → task done
- No manual commands at any step

### M43: NNRT Autonomous Contribution
- Fleet's first real autonomous mission on external project
- Using all the infrastructure: MC tasks, OpenClaw agents, channels, observation
- Human monitors through MC dashboard

## What This Means for AICP

AICP needs these skills (worked on from this repo):
1. `openclaw-plugin-create` — scaffold an OpenClaw plugin
2. `openclaw-channel-setup` — configure a channel for a fleet
3. `openclaw-add-dashboard-component` — add components to MC
4. `openclaw-stream-monitor` — monitor SSE streams from CLI

These are generic skills that work on any OpenClaw project.
