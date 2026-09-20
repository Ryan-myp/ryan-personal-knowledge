# Agent Harness

`agents.agent_harness` is the application-neutral Agent core. It does not know
advertising channels, Skills, Capabilities, MCP servers, credentials or
business workflows.

```text
AgentRuntime
  -> Runtime Kernel       identity, session lease, mode, Run lifecycle
  -> Agent / TurnPipeline model turns and application stages
  -> ToolCatalog          Tool definitions and trusted executors
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

- a model adapter with `complete(messages, tools, request)`;
- a `ToolCatalog` backed by local, SDK/HTTP or MCP Tool bindings;
- policy hooks such as `before_tool_call` and `after_tool_call`;
- an optional `RunStore` and session implementation.

Advertising remains an application package. Its `Capability` classes are
compatibility adapters that publish Tools; they are not required by this
Harness and must not become a second generic abstraction.

The package is imported from the repository source tree through the existing
Python 3.13 project environment. The repository currently runs the agent
service with `PYTHONPATH=.`; packaging it as a separate distribution is a
follow-up deployment concern, not a runtime dependency on `ad_agent`.
