# Agent Harness

`agents/agent_platform/` 在 Harness 之上提供企业级六层平台目录：
应用场景、Agent、核心能力、数据、集成和基础设施。Harness 本身只负责中台执行内核，
不包含广告或其他业务；产品通过 `AgentDefinition`、`ScenarioDefinition`、Skill Source
和 Tool Source 接入。

`agents.agent_harness` is the application-neutral Agent core. It does not know
advertising channels, provider details, MCP servers, credentials or
business workflows.

The public package boundary is `agents.agent_harness`. Applications should
import Runtime, Pipeline, Skill and Tool contracts from this package directly.
An application-specific package may adapt these contracts, but it must not
publish a second Runtime or compatibility import surface.

```text
AgentRuntime
  -> Runtime Kernel       identity, session lease, mode, Run lifecycle
  -> Agent / Turn Handler model turns and application execution
  -> SkillCatalog          bounded advisory context
  -> ToolCatalog            Tool definitions and trusted executors
  -> RunStore              durable Run/events port
```

The stateful `Agent` follows a small, Pi-style loop:

```text
user message
  -> model turn
  -> assistant message
  -> optional Tool preflight/execution
  -> Tool result message
  -> next model turn
  -> agent end
```

Applications inject:

- a model adapter with `complete(messages, tools, request)`. Providers may
  additionally expose `stream(...)`; streamed deltas are observer events and
  Tool calls are executed only after the final `ModelTurn` is assembled;
- standard `SKILL.md` directories through `MarkdownSkillSource` or
  `MarkdownSkillDirectorySource`;
- a `ToolCatalog` and `ToolSource` backed by local, SDK/HTTP or MCP Tool
  bindings;
- one request-level Turn Handler when the application needs a deterministic
  orchestration adapter;
- policy hooks such as `before_tool_call` and `after_tool_call`;
- an optional `RunStore`, `TranscriptStore` and session implementation;
- an optional `IdempotencyStore` for cross-process, SQL-backed write replay
  protection.

Tool exposure is bounded per model turn. `AgentApplication.create` accepts
`max_tools` and an optional `tool_selector(request, tools)` so applications
can select a relevant subset without changing the Runtime or Tool contracts.
Session transcripts are isolated by tenant, user and `session_id`. The in-memory
working window is bounded, while an injected `TranscriptStore` keeps the full
sanitized history and hydrates a new process. Model adapters support bounded
retries, provider fallback for retryable failures, timeout signalling, streaming
deltas and cumulative token budgets. Persistence, lease, idempotency and audit
failures are returned as `recovery_required` with structured runtime signals.

The generic Runtime accepts only `dry_run` and `live` execution modes. A
platform may choose the default mode through governance, but live Tool writes
still require the Tool policy's explicit approval, permission, confirmation,
idempotency and write-guard checks.

Advertising is only one collection of Skills and Tool Sources. Provider
objects publish Tool definitions at the integration boundary; the Harness
does not require any provider-specific abstraction.

The convenient `AgentApplication` assembly is the recommended starting point
for a new Agent integration:

```python
from agents.agent_harness import AgentApplication, SkillBinding, StaticSkillSource

app = AgentApplication.create(model=my_model)
app.register_skill_source(StaticSkillSource(
    "support",
    [SkillBinding(name="support", instructions="...")],
))
app.register_tool_source(my_tool_source)
result = app.prompt("Help me with a ticket")
```

The Harness can also be built as a standalone wheel:

```bash
python -m pip wheel --no-deps agents/agent_harness
```

The wheel exposes only `agents.agent_harness` and has no advertising or
provider dependency.

Run metrics are opt-in and lifecycle-only:

```python
from agents.agent_harness import AgentApplication, InMemoryMetrics

metrics = InMemoryMetrics()
app = AgentApplication.create(model=my_model, metrics=metrics)
app.prompt("Help me with a ticket")
print(metrics.snapshot())
```

Applications can replace `InMemoryMetrics` with an adapter implementing
`MetricsSink`. The built-in collector does not retain prompts, arguments,
results, exceptions, or credentials.

Skill directories are advisory context only. They never register an
executable Tool, receive credentials or bypass the Tool policy hook.

The Harness is imported from the repository source tree through the existing
Python 3.13 project environment. The repository currently runs the agent
service with `PYTHONPATH=.`; the same public package can now be built and
installed independently through `agents/agent_harness/pyproject.toml`. The
package publishes `py.typed` and an explicit `__version__`.
