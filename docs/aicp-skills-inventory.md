# AICP Skills Inventory — Universal Project Lifecycle

## Philosophy

Skills are the encoded knowledge of how to build software. Not templates — executable workflows that drive a project from an idea to production and beyond. Each skill is a chain of AI-driven steps that can be run standalone or composed into larger workflows.

Skills operate at every phase of a project's life. They are backend-agnostic (work with LocalAI or Claude Code). They are parameterized. They are chainable. They produce real artifacts, not just text.

---

## Skill Categories

### 1. Genesis — From Nothing to Something

#### `idea-capture`
Take raw user input (conversation, notes, pasted text) and produce a structured idea document with: vision, core concepts, target users, key differentiators, constraints.

#### `idea-refine`
Take an existing idea document and iterate on it through guided questioning. Identify gaps, contradictions, missing stakeholders, unstated assumptions.

#### `architecture-propose`
Analyze an idea document and propose: system architecture, component breakdown, layer structure, data flows, technology choices, deployment model. Output as a structured architecture document.

#### `architecture-review`
Review an architecture document against the idea. Flag: over-engineering, missing components, scalability concerns, security gaps, dependency risks. Propose alternatives.

#### `scaffold`
Create a new project from an architecture document. Generate: directory structure, README, CLAUDE.md, config files, package manifests, .gitignore, CI skeleton, initial test structure. Git init + first commit.

#### `scaffold-monorepo`
Scaffold a monorepo with multiple packages/services. Generate workspace config, shared dependencies, inter-package references, build orchestration.

#### `scaffold-subagent`
Create a new sub-agent inside an existing fleet project. Generate: agent directory, agent config, mission definition, capability declaration, registration boilerplate.

---

### 2. Foundation — Making It Real

#### `foundation-deps`
Analyze the project and install/configure all dependencies. Resolve version conflicts, set up lock files, configure package managers.

#### `foundation-config`
Set up configuration management: environment files, config loaders, secrets handling, multi-environment support (dev/staging/prod).

#### `foundation-ci`
Generate CI/CD pipeline: GitHub Actions, test matrix, lint checks, build steps, deployment triggers. Tailored to the project's stack.

#### `foundation-docker`
Generate Dockerfile, docker-compose, and container orchestration. Multi-stage builds, dev vs prod configs, volume mounts, networking.

#### `foundation-database`
Set up database: schema design, migrations, connection pooling, ORM/query builder config, seed data.

#### `foundation-auth`
Implement authentication: user model, login/register, token management, middleware, role-based access. Adapted to project requirements.

#### `foundation-logging`
Set up structured logging, error tracking, and basic observability. Log levels, formatters, sinks, correlation IDs.

#### `foundation-testing`
Set up testing infrastructure: test runner, fixtures, mocking, coverage reporting, test database, integration test harness.

---

### 3. Infrastructure — The Systems That Support

#### `infra-api`
Design and implement API layer: endpoints, request/response schemas, validation, error handling, versioning, documentation (OpenAPI/Swagger).

#### `infra-queue`
Set up message queue / event system: producer/consumer patterns, dead letter handling, retry logic, backpressure.

#### `infra-cache`
Implement caching layer: cache strategy, invalidation, Redis/in-memory, cache-aside patterns.

#### `infra-storage`
Set up file/object storage: upload handling, CDN integration, access control, cleanup policies.

#### `infra-search`
Implement search: indexing strategy, query building, faceted search, relevance tuning.

#### `infra-monitoring`
Set up monitoring and alerting: health checks, metrics endpoints, Prometheus/Grafana, uptime tracking, alert rules.

#### `infra-security`
Security hardening: input validation, CORS, rate limiting, CSP headers, dependency auditing, secrets rotation.

#### `infra-networking`
Network configuration: reverse proxy, TLS, load balancing, service discovery, DNS.

---

### 4. Configuration — Managing Complexity

#### `config-env`
Generate and manage environment-specific configurations. Diff between environments, validate completeness, template generation.

#### `config-feature-flags`
Set up feature flag system: flag definitions, rollout strategies, per-environment overrides, cleanup tracking.

#### `config-secrets`
Secrets management: vault integration, encrypted env files, rotation schedules, access auditing.

#### `config-migrations`
Database migration management: generate migrations from schema changes, rollback plans, data migrations, zero-downtime strategies.

#### `config-deploy`
Deployment configuration: infrastructure as code, environment provisioning, rollback procedures, blue-green/canary setup.

---

### 5. Feature Development — Building Value

#### `feature-plan`
Take a feature request and produce: acceptance criteria, technical design, affected components, test plan, estimated complexity.

#### `feature-implement`
Implement a feature end-to-end: code changes across all affected files, follow existing patterns, maintain consistency.

#### `feature-test`
Write comprehensive tests for a feature: unit tests, integration tests, edge cases, error scenarios, performance benchmarks.

#### `feature-review`
Review implemented code: correctness, patterns, performance, security, maintainability. Produce actionable feedback.

#### `feature-document`
Generate documentation for a feature: user-facing docs, API docs, architecture decision records, changelog entries.

#### `feature-iterate`
Take feedback on an existing feature and implement improvements. Compare before/after, validate against original requirements.

---

### 6. Quality — Keeping It Right

#### `quality-lint`
Run linting and formatting across the project. Fix auto-fixable issues, report manual fixes needed.

#### `quality-audit`
Security audit: dependency vulnerabilities, code patterns, exposed secrets, access control review.

#### `quality-performance`
Performance analysis: identify bottlenecks, propose optimizations, benchmark before/after.

#### `quality-coverage`
Test coverage analysis: identify untested code paths, generate missing tests, set coverage targets.

#### `quality-debt`
Technical debt assessment: identify code smells, propose refactoring targets, estimate effort, prioritize by impact.

#### `quality-accessibility`
Accessibility audit: WCAG compliance, screen reader compatibility, keyboard navigation, color contrast.

---

### 7. Refactoring — Making It Better

#### `refactor-extract`
Extract module/service/component: identify boundaries, move code, update imports, maintain tests.

#### `refactor-rename`
Rename across the entire project: variables, functions, files, directories, references, imports, documentation.

#### `refactor-patterns`
Apply design patterns: identify where patterns are needed, implement with minimal disruption, document decisions.

#### `refactor-split`
Split a monolith into services or a large file into modules. Identify boundaries, create interfaces, migrate incrementally.

#### `refactor-dependencies`
Upgrade/replace dependencies: compatibility analysis, migration guide, breaking change resolution, testing.

#### `refactor-architecture`
Major architectural changes: move between patterns (MVC to hexagonal, monolith to microservices), incremental migration plan.

---

### 8. Evolution — Growing the System

#### `evolve-scale`
Analyze scaling needs and implement: horizontal scaling, connection pooling, caching layers, database sharding.

#### `evolve-integrate`
Add external integrations: API clients, webhooks, OAuth providers, payment processors, notification services.

#### `evolve-migrate`
Data or platform migration: migration scripts, validation, rollback, dual-write strategies, cutover plans.

#### `evolve-internationalize`
Add i18n support: string extraction, translation management, locale handling, RTL support, date/number formatting.

#### `evolve-plugin-system`
Design and implement plugin/extension architecture: plugin interface, discovery, lifecycle management, sandboxing.

#### `evolve-api-version`
API versioning: add new version, deprecation strategy, migration guides, backward compatibility.

---

### 9. Operations — Running It

#### `ops-deploy`
Execute deployment: pre-flight checks, deploy, smoke test, rollback if needed. Environment-aware.

#### `ops-rollback`
Rollback deployment: identify last good state, execute rollback, verify, post-mortem template.

#### `ops-incident`
Incident response: gather diagnostics, identify root cause, propose fix, generate incident report.

#### `ops-backup`
Backup and restore: database dumps, file backups, verification, restore testing.

#### `ops-scale`
Runtime scaling: adjust replicas, resource limits, autoscaling rules based on current load.

#### `ops-maintenance`
Maintenance tasks: dependency updates, certificate renewal, log rotation, cleanup jobs.

---

### 10. Project Management — Driving It

#### `pm-assess`
Assess project state: what's built, what's pending, what's blocked, risks, next actions. Compare against plan.

#### `pm-plan`
Generate or update project plan: milestones, dependencies, effort estimates, critical path.

#### `pm-retrospective`
Run a retrospective: what went well, what didn't, action items, patterns to keep/stop/start.

#### `pm-handoff`
Generate handoff documentation: architecture overview, how to run, how to deploy, known issues, tribal knowledge capture.

#### `pm-changelog`
Generate changelog from git history: group by feature/fix/breaking, link to PRs/issues, human-readable format.

#### `pm-status-report`
Generate status report: progress since last report, upcoming work, blockers, metrics, decisions needed.

---

### 11. MVP Generation — Fast Path

#### `mvp-full`
Chain: `idea-capture` → `architecture-propose` → `scaffold` → `foundation-deps` → `foundation-config` → `foundation-testing` → `foundation-ci` → `feature-implement` (core feature) → `feature-test` → `pm-assess`

One command to go from idea to working MVP.

#### `mvp-api`
Chain: `scaffold` → `foundation-deps` → `infra-api` → `foundation-auth` → `foundation-database` → `feature-test` → `foundation-docker`

API-focused MVP with auth and database.

#### `mvp-frontend`
Chain: `scaffold` → `foundation-deps` → `feature-implement` (UI) → `foundation-ci` → `foundation-docker`

Frontend MVP with CI.

#### `mvp-agent`
Chain: `scaffold-subagent` → `foundation-config` → `feature-implement` (agent logic) → `feature-test` → `ops-deploy`

New agent in a fleet from zero to deployed.

---

### 12. Advanced Workflows — Chains and Compositions

#### `full-feature-cycle`
Chain: `feature-plan` → `feature-implement` → `feature-test` → `feature-review` → `feature-document`

Complete feature from request to documented and tested.

#### `full-refactor-cycle`
Chain: `quality-debt` → `refactor-extract` or `refactor-patterns` → `feature-test` → `quality-coverage` → `feature-review`

Identify debt, fix it, verify quality improved.

#### `release-cycle`
Chain: `quality-lint` → `quality-audit` → `quality-coverage` → `pm-changelog` → `ops-deploy` → `pm-status-report`

Full release from quality check to deployment to reporting.

#### `incident-cycle`
Chain: `ops-incident` → `feature-plan` (fix) → `feature-implement` → `feature-test` → `ops-deploy` → `pm-retrospective`

From incident to fix to prevention.

#### `onboarding-cycle`
Chain: `pm-handoff` → `pm-assess` → `quality-debt` → `feature-plan` (first task)

New team member gets context, project state, and their first assignment.

---

## Skill Properties

Every skill has:

| Property | Description |
|----------|-------------|
| `name` | Unique identifier |
| `description` | What it does |
| `category` | Which lifecycle phase |
| `parameters` | Inputs (required/optional with defaults) |
| `steps` | Pipeline steps with mode/backend/prompt |
| `inputs` | What it reads (files, config, user input) |
| `outputs` | What it produces (files, reports, state changes) |
| `chains` | What skills it composes (for workflow skills) |
| `prerequisites` | What must exist before running |
| `backend_preference` | Which backend works best (local for fast/private, claude for complex) |

---

## Execution Model

1. **Standalone**: `aicp skill run scaffold --param name=my-project`
2. **Chained**: `aicp skill run mvp-full --param name=my-project --param idea="..."`
3. **Interactive**: `aicp skill run feature-plan` — prompts for input at each step
4. **Pipeline**: reference skills in `pipeline.yaml` by name
5. **Claude Code**: exported as `/scaffold`, `/feature-plan`, etc.

---

## Relationship to AICP

- Skills are the **operational vocabulary** of AICP
- The skill system (M15) provides the execution engine
- The project registry (M14) provides the target context
- The control plane (M17) provides visibility into skill execution
- Skills produce artifacts that update project state (M14)
- Advanced workflows compose skills via the pipeline system (M10)

---

## What This Enables

With this skill set, AICP can:

1. Take an idea and produce a working project in one session
2. Drive a project through its entire lifecycle without losing context
3. Maintain quality at every stage
4. Operate across multiple projects simultaneously
5. Encode team knowledge as reusable, executable workflows
6. Work on any project — OCF, ocf-tag, or anything else
