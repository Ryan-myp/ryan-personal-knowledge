# 代码库学习任务

你是一个资深软件架构师。请基于以下代码扫描结果，
总结这个系统的架构、业务流程、数据模型和关键技术决策。

## 仓库信息
- **eino**: go @ /tmp/eino

## 代码结构摘要
- Structs: 850
- Functions: 949
- Routes: 0
- Imports: 0

## 关键业务 Struct

### `agentToolRequest`
文件: eino/adk/agent_tool.go
- `Request`: string json:request

### `agentCancelConfig`
文件: eino/adk/cancel.go

### `cancelMonitoredToolHandler`
文件: eino/adk/cancel.go

### `plainResponseModel`
文件: eino/adk/cancel_edge_test.go

### `multiResponseGatedModel`
文件: eino/adk/cancel_test.go

### `ToolsConfig`
文件: eino/adk/chatmodel.go

### `LsInfoRequest`
文件: eino/adk/filesystem/backend.go

### `ReadRequest`
文件: eino/adk/filesystem/backend.go

### `MultiModalReadRequest`
文件: eino/adk/filesystem/backend.go

### `GrepRequest`
文件: eino/adk/filesystem/backend.go

### `GlobInfoRequest`
文件: eino/adk/filesystem/backend.go

### `WriteRequest`
文件: eino/adk/filesystem/backend.go

### `EditRequest`
文件: eino/adk/filesystem/backend.go

### `ExecuteRequest`
文件: eino/adk/filesystem/backend.go

### `ExecuteResponse`
文件: eino/adk/filesystem/backend.go

### `DeterministicTransferConfig`
文件: eino/adk/flow.go

### `MyHandler`
文件: eino/adk/handler.go

### `testInstructionHandler`
文件: eino/adk/handler_test.go

### `testInstructionFuncHandler`
文件: eino/adk/handler_test.go

### `testToolsHandler`
文件: eino/adk/handler_test.go

## 服务层
- **edgeHandlerManager** (0 methods)
- **preNodeHandlerManager** (0 methods)
- **preBranchHandlerManager** (0 methods)
- **channelManager** (0 methods)
- **taskManager** (0 methods)
- **CtxManagerKey** (0 methods)

## 调用关系 (Call Graph)
- **?** ← called by: 

## 入口点 (Entry Points)
- **eino**
- **callbacks**
- **compose**
- **internal**
- **schema**
- **schema_test**
- **adk**
- **components**
- **agent**
- **parent**
- **utils**
- **multiquery**
- **router**
- **react**
- **host**
- **embedding**
- **document**
- **retriever**
- **prompt**
- **model**

## 权限/鉴权模型 (Authentication & Authorization)
共 1 个中间件/鉴权组件

- **受保护路由**: 0 个路由需要登录认证

## 向后兼容 (Backward Compatibility)
共 42 个兼容问题:
- DEPRECATED: 42

- **[S:critical]** `DEPRECATED` (eino/callbacks/interface.go:90): // Deprecated: Use AppendGlobalHandlers instead.
- **[S:warning]** `DEPRECATED` (eino/compose/graph_compile_options.go:76): // Deprecated: Eager execution is automatically enabled by default when a node's trigger mode is set to AllPredecessor.
- **[S:critical]** `DEPRECATED` (eino/compose/checkpoint.go:47): // Deprecated: RegisterSerializableType is deprecated. Use schema.RegisterName[T](name) instead.
- **[S:warning]** `DEPRECATED` (eino/compose/interrupt.go:44): // Deprecated: prefer Interrupt/StatefulInterrupt and CompositeInterrupt.
- **[S:warning]** `DEPRECATED` (eino/compose/interrupt.go:50): // Deprecated: prefer Interrupt(ctx, info) or StatefulInterrupt(ctx, info, state).
- **[S:critical]** `DEPRECATED` (eino/compose/workflow.go:431): // Deprecated: use *Workflow[I,O].End() to obtain a WorkflowNode instance for END, then work with it just like a normal 
- **[S:critical]** `DEPRECATED` (eino/schema/message.go:172): // Deprecated: Use MessageOutputPart.Extra or MessageInputPart.Extra to set additional metadata instead.
- **[S:warning]** `DEPRECATED` (eino/schema/message.go:297): // Deprecated: This struct is deprecated as the MultiContent field is deprecated.
- **[S:warning]** `DEPRECATED` (eino/schema/message.go:339): // Deprecated: This struct is deprecated as the MultiContent field is deprecated.
- **[S:warning]** `DEPRECATED` (eino/schema/message.go:356): // Deprecated: This struct is deprecated as the MultiContent field is deprecated.
- **[S:warning]** `DEPRECATED` (eino/schema/message.go:373): // Deprecated: This struct is deprecated as the MultiContent field is deprecated.
- **[S:warning]** `DEPRECATED` (eino/schema/message.go:389): // Deprecated: This struct is deprecated as the MultiContent field is deprecated.
- **[S:critical]** `DEPRECATED` (eino/schema/message.go:506): // Deprecated: Use UserInputMultiContent for user multimodal inputs and AssistantGenMultiContent for model multimodal ou
- **[S:critical]** `DEPRECATED` (eino/adk/handler.go:61): // Deprecated: Use TypedChatModelAgentState.ToolInfos in BeforeModelRewriteState instead.
- **[S:warning]** `DEPRECATED` (eino/adk/react.go:61): // Deprecated: State is exported only for checkpoint backward compatibility.
- **[S:critical]** `DEPRECATED` (eino/adk/interrupt.go:37): // Deprecated: use InterruptContexts from the embedded InterruptInfo for user-facing details,
- **[S:critical]** `DEPRECATED` (eino/adk/chatmodel.go:118): // Deprecated: use ResumeWithData and ChatModelAgentResumeData instead.
- **[S:critical]** `DEPRECATED` (eino/adk/chatmodel.go:235): // Deprecated: Use ChatModelAgentMiddleware (interface-based Handlers) instead.
- **[S:critical]** `DEPRECATED` (eino/adk/chatmodel.go:310): // Deprecated: Use Handlers instead. Middlewares will be removed in a future release.
- **[S:critical]** `DEPRECATED` (eino/adk/retry_chatmodel.go:241): // Deprecated: Use ShouldRetry instead for richer retry control including message

---

请基于以上信息，输出以下结构化知识：

1. **架构总览** — 系统定位、技术栈、服务拆分、部署架构
2. **核心业务流程** — 主要业务场景的流程描述（用文字，不需要 mermaid）
3. **数据库表结构** — 表名、字段、ER 关系
4. **服务层架构** — Service/DAO/Model 分层说明
5. **外部系统集成** — 第三方 API、消息队列等
6. **术语 Glossary** — 业务术语及其含义