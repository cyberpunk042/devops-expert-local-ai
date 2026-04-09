# Phase 4: Making It Real — Milestone Planning

## The Problem

We have three systems that are connected but not operational:

- **AICP**: 73 skills, project management, can talk to Claude Code and LocalAI. But the skills haven't been used to build anything real.
- **OCF**: 7 agents registered in Mission Control, WebSocket gateway running. But the gateway can't execute tasks — it's a registration shell.
- **Mission Control**: Running, has our org/board/agents. But no tasks exist, no work flows through it.

The gap: **nothing actually works end-to-end as a system.**

## What "Working" Means

A working system means:

1. A user creates a task in Mission Control (or via API/CLI)
2. Mission Control assigns it to the right agent
3. The OCF gateway receives the assignment
4. The gateway executes it through Claude Code with the agent's context
5. The result goes back to Mission Control
6. The user sees the result in the MC dashboard
7. History, activity log, and state are all updated

That's the operational loop. Without it, everything we built is scaffolding.

## Milestone Principles

- **Each milestone produces a working loop** — not just a feature, but a testable end-to-end flow
- **Prove before expanding** — make one thing work completely before adding more
- **Use what we built** — AICP skills should drive OCF development. If they can't, fix them.
- **Mission Control is the truth** — all state lives there, not in local files
- **High standards** — no shortcuts, no "we'll fix it later"

---

## M20: The Operational Loop (Critical Path)

**Goal**: One task flows through the entire system end-to-end.

**What this means concretely:**
1. Create a task on the Fleet Operations board via MC API
2. Assign it to the Architect agent
3. OCF gateway receives the task (poll MC API or receive via WS)
4. Gateway invokes Claude Code with Architect's context + task prompt
5. Claude Code returns a result
6. Gateway posts the result back to MC as a task comment/update
7. Task status updated to "done" in MC
8. Visible in the MC dashboard

**What needs to be built:**
- Gateway task polling/receiving from MC API
- Task-to-Claude-Code execution pipeline
- Result reporting back to MC
- Agent context injection (reads agent's CLAUDE.md + context/)

**What this proves:** The system works. A task in, a result out, tracked in MC.

---

## M21: Agent Specialization in Action

**Goal**: Different agents produce meaningfully different results for the same project.

**What this means:**
- Assign "Design the intake layer for ocf-tag" to Architect → get architecture doc
- Assign "Implement the intake layer" to Software Engineer → get code
- Assign "Review the implementation" to QA Engineer → get test results
- Assign "Document the intake layer" to Technical Writer → get docs

**What needs to be built:**
- Agent context differentiation (each agent's CLAUDE.md shapes behavior)
- Mode enforcement per agent (Architect=think, Engineer=edit, QA=act)
- Task dependency tracking (Engineer waits for Architect's output)

**What this proves:** Agents are real specialists, not just labels.

---

## M22: AICP Driving OCF Development

**Goal**: Use AICP's skill system to actually build OCF features.

**What this means:**
- `aicp --skill run feature-plan` on the OCF repo → produces a plan
- `aicp --skill run feature-implement` → implements the feature
- `aicp --skill run feature-test` → writes tests
- Skills produce real artifacts that get committed

**What needs to be built:**
- Skills need to actually work on a real project (not just have SKILL.md files)
- AICP project state for OCF needs to reflect reality
- Skill chains need to pass context between steps

**What this proves:** AICP is a real development tool, not just a CLI wrapper.

---

## M23: ocf-tag Layer 1 — Intake

**Goal**: The Accountability Generator's first layer exists and functions.

**What this means:**
- Intake module: collect claims, policies, evidence
- Data model: actors, claims, evidence, timelines
- Storage: persistent (database or files)
- API: submit evidence, query claims
- Tests: the module works

**Built by the fleet**: Architect designs, Engineer implements, QA tests, Writer documents — all tracked in Mission Control.

**What this proves:** The fleet can build real software collaboratively.

---

## M24: Continuous Operation

**Goal**: The fleet runs autonomously on assigned work without manual intervention.

**What this means:**
- Gateway polls MC for new tasks continuously
- Executes them in order, respects dependencies
- Reports back automatically
- User reviews in MC dashboard, approves/rejects
- Failed tasks get retried or escalated

**What needs to be built:**
- Persistent gateway loop (not one-shot)
- Task queue management
- Error handling and retry logic
- Approval integration

**What this proves:** The fleet is a workforce, not a one-time script.

---

## M25: Multi-Project Operations

**Goal**: The fleet works on multiple projects simultaneously.

**What this means:**
- OCF fleet board has tasks for different repos/projects
- Agents switch context based on task assignment
- AICP tracks multiple projects through its registry
- Mission Control provides unified visibility

**What this proves:** This scales beyond one project.

---

## Dependency Graph

```
M20 (Operational Loop)
  │
  ├── M21 (Agent Specialization)
  │
  ├── M22 (AICP Driving OCF)
  │
  └── M23 (ocf-tag Intake) ←── uses M21 + M22
        │
        M24 (Continuous Operation)
        │
        M25 (Multi-Project)
```

M20 is the foundation. Everything else depends on the loop working. M21, M22, M23 can partially overlap once M20 is solid. M24 and M25 build on top.

---

## What I'm Uncertain About

1. **MC's task dispatch protocol**: How does MC actually push tasks to a gateway? Is it WS events, or does the gateway poll? Need to study their `gateway_dispatch.py` more.

2. **How much to build in the gateway vs rely on MC**: MC has a sophisticated task lifecycle. Should our gateway be smart (make decisions) or dumb (just execute what MC says)?

3. **AICP skills vs direct Claude Code**: When building OCF features, should we use AICP skills (which add structure) or just point Claude Code at the OCF repo directly? The skills add overhead — is it worth it?

4. **ocf-tag architecture**: The 5 layers are defined conceptually but not technically. What's the actual tech stack for Intake? Database? API framework? This needs the Architect agent to actually decide.

---

## My Recommendation

Start with **M20**. Nothing else matters until the operational loop works. One task, one agent, one result, visible in Mission Control. Then expand from there.
