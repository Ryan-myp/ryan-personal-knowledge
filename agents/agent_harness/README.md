# Agent Harness

`agents.agent_harness` is the application-neutral Agent core. It does not know
advertising channels, Skills, Capabilities, MCP servers, credentials or
business workflows.

```text
AgentRuntime
  -> Runtime Kernel       identity, session lease, mode, Run lifecycle
  -> Agent / TurnPipeline model turns and application stages
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

- a model adapter with `complete(messages, tools, request)`;
- standard `SKILL.md` directories through `MarkdownSkillSource` or
  `MarkdownSkillDirectorySource`;
- a `ToolCatalog` and `ToolSource` backed by local, SDK/HTTP or MCP Tool
  bindings;
- policy hooks such as `before_tool_call` and `after_tool_call`;
- an optional `RunStore` and session implementation.

Advertising is only one collection of Skills and Tool Sources. Its existing
Provider/Capability objects are compatibility adapters at the integration
boundary; the Harness does not require or expose that concept.

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

Skill directories are advisory context only. They never register an
executable Tool, receive credentials or bypass the Tool policy hook.

The Harness is imported from the repository source tree through the existing
Python 3.13 project environment. The repository currently runs the agent
service with `PYTHONPATH=.`; packaging it as a separate distribution is a
follow-up deployment concern, not a runtime dependency on `ad_agent`.
