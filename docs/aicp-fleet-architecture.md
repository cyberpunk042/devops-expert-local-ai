# AICP ↔ Fleet: Architectural Boundary

## Two Independent Systems

### AICP (devops-expert-local-ai)
- **What it is**: A tool for working on code and projects
- **Who drives it**: A human or an agent giving it direction
- **What it does**: Reads, analyzes, edits, tests, deploys code
- **When it acts**: When asked to
- **Scope**: Any project it's pointed at

### OpenClaw Fleet (openclaw-fleet)
- **What it is**: An autonomous AI agent workforce
- **Who drives it**: Mission Control tasks, cron, flows — self-directed
- **What it does**: Executes tasks through OpenClaw agents
- **When it acts**: Continuously, when work is assigned
- **Scope**: Whatever projects/tasks are on its boards

They share a machine but are independent. AICP doesn't run the fleet. The fleet doesn't need AICP at runtime.

## AICP's Role with the Fleet

AICP works ON the fleet project the same way it works on any project:
- Point AICP at `/home/jfortin/openclaw-fleet`
- Use skills to set up, configure, evolve the project
- The skills produce code, config, scripts that become part of the fleet project
- Once built, the fleet runs on its own

## What the Fleet Project Needs to Be Self-Bootstrapping

The fleet project should have everything needed to go from clone to running:

```
openclaw-fleet/
├── setup.sh                  # One command: installs OpenClaw, configures auth,
│                             # starts services, registers agents, creates boards
├── docker-compose.yaml       # Mission Control services
├── config/
│   ├── fleet.yaml            # Fleet config
│   ├── openclaw.json.template # OpenClaw config template
│   └── ...
├── scripts/
│   ├── install-openclaw.sh   # Install OpenClaw globally
│   ├── configure-auth.sh     # Set up Anthropic auth (interactive if needed)
│   ├── register-agents.sh    # Register all agents in OpenClaw
│   ├── setup-mc.sh           # Start MC, register gateway, create boards
│   └── start-fleet.sh        # Start everything
├── agents/                   # Agent definitions
├── gateway/                  # Gateway code (may become unnecessary as we
│                             # integrate deeper with OpenClaw native)
└── Makefile                  # Convenient targets for all of the above
```

The key: `setup.sh` or `make setup` takes you from zero to running fleet.
No manual commands. No "run this then that." One flow.

## What AICP Skills Should Exist

### For Working on Any OpenClaw Project
These are generic, reusable skills:

- **`openclaw-setup`**: Set up OpenClaw in a project (install, configure, verify)
- **`openclaw-add-agent`**: Add an agent to an OpenClaw deployment (workspace, soul, identity, auth)
- **`openclaw-configure-mc`**: Connect Mission Control to an OpenClaw gateway
- **`openclaw-health`**: Check health of OpenClaw + MC + agents

### For Working on the Fleet Project Specifically
These are project-specific skills that live in the fleet repo:

- **`fleet-setup`**: Full fleet setup from scratch
- **`fleet-add-agent`**: Add a new specialized agent to the fleet
- **`fleet-create-template`**: Create a new workflow template
- **`fleet-status`**: Check fleet operational status

## What Needs to Happen Now

1. **In AICP**: Create the `openclaw-*` skills (generic, reusable)
2. **In the fleet project**: Create `setup.sh` and supporting scripts that make the fleet self-bootstrapping
3. **In the fleet project**: Create a `Makefile` with targets for common operations
4. **Test**: Clone the fleet on a fresh machine, run `make setup`, verify everything works

The auth blocker is a setup.sh problem, not an AICP problem. The fleet's setup script should handle it — detect if auth is configured, prompt if needed, configure automatically if possible.

## Milestones (Revised)

### M35b: Fleet Self-Bootstrap Scripts
- setup.sh that handles everything: OpenClaw install, auth, MC, agents
- Makefile with targets
- Scripts in scripts/ for each step
- Test the full flow

### M36: AICP OpenClaw Skills
- Generic skills for working on OpenClaw projects
- These live in AICP's skill set, not the fleet
- Reusable across any OpenClaw deployment

### M37: Fleet Operational Testing
- Run the fleet autonomously on a real task
- Verify: task in MC → agent executes → result back
- No manual intervention

### M38+: Everything else from the plan
- Skills migration, governance, NNRT work, ocf-tag layers
