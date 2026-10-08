# Agent Repository Architecture

## Decision

The repository has one application-neutral Agent Harness and one application-neutral
Agent Platform. Advertising is a reusable set of Tool Sources, Skills and Knowledge
selected by a Scenario. It does not own a second Agent, Run Kernel, Tool gate or
business-specific turn pipeline.

## Target Layout

```text
agents/
├── agent_harness/                  # Pure Agent loop and execution contracts
│   ├── core/                       # Generic intent, Tool, policy and trace contracts
│   ├── skills/                     # Standard Skill source/catalog adapters
│   ├── agent.py                    # Model ↔ Tool loop and transcript state
│   ├── agent_runtime.py            # Run-facing Runtime facade
│   ├── runtime_kernel.py           # Run/Turn identity, lease, mode and cancellation
│   ├── tool_execution.py           # Bounded, policy-hooked Tool scheduling
│   ├── turn_pipeline.py            # Generic application-stage contract
│   └── application.py              # Standalone Harness composition
│
├── agent_platform/                 # Hosting and shared platform services
│   ├── api/                        # Generic routes and request context
│   ├── data/                       # Knowledge, Memory and persistence ports
│   │   ├── knowledge/              # Generic ingest, indexing, query and audit
│   │   └── persistence/            # Store interfaces and implementations
│   ├── integrations/               # MCP and other protocol adapters
│   │   └── mcp/
│   ├── management/                 # Tenant-managed Skills and plugin packages
│   ├── governance/                 # Shared identity and Tool execution policy
│   ├── infrastructure/             # Durable tasks, workers and stores
│   ├── definitions.py              # Agent and Scenario declarations
│   ├── platform.py                 # Registry and application factory
│   └── runtime.py                  # Six-layer Platform composition
│
├── tools/
│   └── advertising/                # Reusable advertising Tool Sources
│       ├── shared/                 # Shared contracts, surfaces and templates
│       ├── clients/                # Provider SDK/HTTP clients
│       ├── providers/              # Provider Tool definitions and executors
│       │   ├── google/
│       │   ├── meta/
│       │   ├── tiktok/
│       │   └── dv360/
│       └── contracts/              # Provider request/evidence fixtures
│
├── skills/
│   └── advertising/                # Standard, portable SKILL.md packages
│       ├── channels/
│       ├── businesses/
│       └── cross-channel/
│
├── knowledge/
│   └── advertising/
│       └── wiki/                   # Source-of-truth Markdown documents
│
├── scenarios/
│   └── advertising.py              # Declarative Agent/Tool/Skill selection
│
├── deployments/
│   └── advertising/                # HTTP/CLI hosting and deployment-owned UI
│       ├── api_server.py
│       ├── chat.py
│       ├── local_config.py
│       ├── static/
│       └── templates/
│
├── ad_agent/                       # Product composition root and config only
│   ├── application.py              # Creates the configured PlatformApplication
│   └── config.yaml
│
├── docs/advertising/               # Product docs and diagrams
└── tests/
    ├── harness/
    ├── platform/
    └── advertising/
```

Repository operator scripts are outside the importable package tree at
`scripts/advertising/`.

Packaging metadata lives at the repository root and deployment configuration
remains in `ad_agent/`. HTTP
hosting, CLI and static assets are under `deployments/advertising`; the deployment
entry in `ad_agent/` only constructs the selected Platform application. Repository
audits and operator commands live under `scripts/advertising`. Generated databases,
local `.env` files and provider evidence are data, not Python package modules.

## Ownership Rules

| Area | Owns | Must not own |
| --- | --- | --- |
| Harness | Agent loop, Run/Turn lifecycle, Tool-call scheduling, generic clarification and bounded follow-up | HTTP serving, Provider names, advertising account fields, business policy |
| Platform | Agent/Scenario registry, API hosting, MCP, Knowledge/Memory services, governance, durable infrastructure | Provider-specific campaign logic or advertising workflow branches |
| Tool Source | Closed schemas, effect/risk/replay metadata, fixed executors, Provider clients and provider-specific templates | Run lifecycle, direct model loop, permission bypasses |
| Skills | Natural-language SOP, trigger conditions, business guidance and references | Executable API calls, credential access, Tool registration |
| Knowledge | Original Markdown and other advisory source material | Identity, authorization or executable workflow definitions |
| Scenario | Selecting registered Tool/Skill/Knowledge sources and scenario metadata | Planner, turn handler, Runtime, API client or business control flow |
| Deployment | HTTP/CLI hosting, configuration loading, static assets and construction of the selected application | Run lifecycle, a second Tool gate, or direct Provider API calls |

## Dependency Direction

```text
ad_agent deployment entry
        │ selects
        ▼
Scenario ── selects ── Tool Sources + Skill Sources + Knowledge Sources
        │                         │
        ▼                         ▼
Deployment ── configures ── Agent Platform ── hosts ── Agent Harness
```

The Harness has no imports from the Platform, advertising tools, Skills or
Knowledge. The Platform may depend on Harness contracts. Tool Sources implement
Harness contracts and may depend on provider SDK/HTTP clients. Skills and Knowledge
are inert inputs. Scenario registration composes these sources without adding
execution code. HTTP/API modules call the Platform application and never call a
Provider client directly.

## Migration Map

| Current location | Target owner |
| --- | --- |
| `ad_agent/core` | Generic Run/Turn/Tool/intent contracts into Harness; Memory, model adapter, MCP and managed-package services into Platform; advertising-only scope and provider rules into advertising Tool Sources |
| `ad_agent/runtime` | Generic loop/interaction/execution behavior moved to Harness; hosting, persistence, management and API behavior moved to Platform/Deployment; remaining advertising composition and turn adapter live under `tools/advertising/application` and are a documented reduction gap, not a second Runtime |
| `ad_agent/tools/providers` | `agents/tools/advertising/providers` |
| `ad_agent/api_clients` | `agents/tools/advertising/clients` |
| `ad_agent/creation_templates.py`, `ad_agent/domain/ad/blueprint.py`, `parameter_catalog.py` | `agents/tools/advertising/shared` and provider template assets |
| `ad_agent/domain/ad` | Split: provider creation rules/evidence/security into the advertising Tool Source; principal and generic request identity into Platform governance; Knowledge adapters into Platform Knowledge |
| `ad_agent/skills` | `agents/skills/advertising` |
| `ad_agent/knowledge_base` | Markdown corpus to `agents/knowledge/advertising/wiki`; generic ingest/query/audit services to `agent_platform/data/knowledge` |
| `ad_agent/knowledge_*` | Generic Knowledge service modules under `agent_platform/data/knowledge` |
| `ad_agent/mcp_management.py`, `runtime_mcp.py` | `agent_platform/integrations/mcp` |
| `ad_agent/skill_management.py`, `plugin_management.py` | `agent_platform/management` |
| `ad_agent/agent_definition.py` | `agents/scenarios/advertising.py` |
| `ad_agent/integration_investigation.py` | Harness generic interaction service, retaining the existing read-only Tool allowlist and bounded-call guarantees |
| `ad_agent/integration_turn_*`, `integration_result_assembler.py` | Split generic request/response mechanics into Harness; remove advertising-only routing/creation behavior in favor of Skills, Tool schemas and shared interaction contracts |
| `ad_agent/api_server.py`, `ad_agent/chat.py`, `ad_agent/static`, `ad_agent/templates` | `agents/deployments/advertising`; HTTP/CLI and assets remain outside Platform core |
| `ad_agent/api`, generic chat/session/task routes | `agent_platform/api`; scenario selection is injected by the deployment entry |
| `ad_agent/persistence` | `agent_platform/data/persistence`; business callers use store interfaces, never SQL or SQLite-specific types |
| `ad_agent/scripts` | repository `scripts/advertising`; commands are not importable runtime capabilities |
| `ad_agent/docs` and product guides | `agents/docs/advertising`; the root `agents/ARCHITECTURE.md` is the canonical architecture decision |
| `ad_agent/templates`, static assets | `agents/deployments/advertising`; provider-specific editors stay optional and cannot call APIs directly |
| mixed tests in `ad_agent/tests` | Harness, Platform or advertising test directory according to the behavior under test |

## Implementation Sequence

1. Lock the layout, ownership table and import-direction checks in architecture tests.
2. Move Harness contracts and generic interaction behavior; update all imports and
   prove a non-advertising Agent can run without importing advertising packages.
3. Move shared API, identity, management, MCP, Knowledge, Memory, persistence and
   durable services into Platform packages; keep Provider SDKs out of Platform.
4. Make the advertising Scenario a declarative selection of the single Agent,
   advertising Tool Source, Skills and Knowledge source. Keep deployment assembly
   limited to configuration, model selection and dependency construction.
5. Move advertising-only blueprints, account rules, provider connectors, Tool
   definitions and response assets under `tools/advertising`; express user-facing
   procedures as standard Skill packages. Remove the old advertising runtime,
   integration pipeline and duplicate entry points instead of forwarding imports.
6. Move HTTP/CLI hosting and static assets to `deployments/advertising`; keep the
   application package as a thin composition entry. Move audits to
   `scripts/advertising`, product docs to `agents/docs/advertising`, update all
   launch/test commands and run the full acceptance suite.

Each move is validated at its new owner before the next layer is migrated. No
compatibility package or import shim is part of the target architecture.

The `ad_agent` directory is reduced to application construction, scenario
configuration and packaging metadata. Deployment hosting is in
`agents/deployments/advertising`. No import compatibility modules are retained;
repository imports and launch/test commands are updated together.

## Implementation Status

The directory and ownership migration described above is implemented. The
repository now uses the Harness, Platform, reusable advertising Tools, standard
Skills, Knowledge, declarative Scenario, Deployment, operator scripts, docs and
separated test roots shown in the target tree. Imports, Make targets, package
metadata, CI paths and Skill-up evaluation paths point at those owners; old
`ad_agent/core`, `runtime`, `api`, `persistence`, `scripts`, `tests`, `skills`,
`evals` and `contracts` import paths are not kept as forwarding shims.

Deployment-owned account configuration is injected into the advertising Tool
composition. The Tool package does not infer a deployment config path; without
an injected allowlist it denies account access. The platform-hosted Skill-up
adapter constructs a read/plan-only principal from the repository's controlled
test-account allowlist and runs with in-memory persistence, dry-run and offline
Provider fixtures. Case text and `SessionInput.kwargs` cannot grant scope or
credentials.

Root wheel packaging has a regression test that pre-seeds stale build output and
checks the produced archive. Generated `build`/test output, SQLite files and
sidecars, and local `.env` files are excluded; runtime Tool, Skill, Knowledge,
deployment assets and `.env.example` are retained.

### Acceptance Evidence (2026-10-08)

- `make ad-agent-check`: passed; 1,236 tests passed, 1 dependency deprecation
  warning; Tool audit and snapshot validated 297 Tools.
- `make ad-agent-knowledge-check`: passed; 69 documents / 479 chunks, retrieval
  hit@3 1.0, negative leakage 0.
- Pinned Skill-up CLI: config validation passed; 6/6 offline Runtime cases passed.
- Root wheel regression test: passed with pre-seeded stale build files.

The structural migration is complete, but that does not mean the Agent platform
has reached its separate 95-point capability target. The local readiness report
still records Provider query E2E coverage at 62, Provider write E2E and live
verification at 0, no production multi-instance evidence, and maintainability at
93 (largest advertising composition module: 430 lines against a 400-line target).
These remain explicit runtime/API evidence and decomposition work, not directory
compatibility work.

## Acceptance Criteria

1. A second Scenario can select a different Tool Source and Skill Source through
   `AgentPlatform` without changing Harness or Platform execution code.
2. The advertising Tool Source can be imported and registered without importing
   `agents.ad_agent`.
3. Scenarios contain selection/configuration only and do not define a Tool executor,
   turn planner, Run lifecycle or Provider client.
4. There is one Run/Session/Tool execution gate. Existing principal, dry-run/live,
   test-account allowlist, confirmation, idempotency, audit, timeout and recovery
   behavior remains enforced by shared contracts and Platform policy.
5. Generic MCP, Skill, Knowledge, Task and API tests live under
   `agents/tests/{harness,platform}`; advertising provider contracts and Skills
   evaluations live under `agents/tests/advertising` and `agents/evals/advertising`.
6. Repository launch, packaging, audits, contract validation and test commands use
   the new paths. Empty legacy skeleton directories and stale architecture maps are
   removed or replaced.

## Current Migration Note

The directory moves are not evidence by themselves that every application adapter
is generic. Advertising currently injects a domain-specific turn adapter and a
large composition module into the single Platform/Harness lifecycle. It does not
own a second Run Kernel or Tool policy gate, but its size and scope remain a
maintainability/genericity gap; it must be reduced by moving deterministic
capabilities into registered Tools and advisory procedures into Skills, not by
renaming it as a second framework layer.
