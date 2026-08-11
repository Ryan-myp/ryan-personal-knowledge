# 代码库学习任务

你是一个资深软件架构师。请基于以下代码扫描结果，
总结这个系统的架构、业务流程、数据模型和关键技术决策。

## 仓库信息
- **eino**: go @ /tmp/eino

## 代码结构摘要
- Structs: 294
- Functions: 438
- Routes: 0
- Imports: 0

## 关键业务 Struct

### `HandlerBuilder`
文件: eino/callbacks/handler_builder.go

### `handlerImpl`
文件: eino/callbacks/handler_builder.go

### `FanInMergeConfig`
文件: eino/compose/graph_compile_options.go

### `userCompanyRequest`
文件: eino/compose/tool_node_test.go

### `userCompanyResponse`
文件: eino/compose/tool_node_test.go

### `userSalaryRequest`
文件: eino/compose/tool_node_test.go

### `userSalaryResponse`
文件: eino/compose/tool_node_test.go

### `mockToolRequest`
文件: eino/compose/tool_node_test.go

### `mockToolResponse`
文件: eino/compose/tool_node_test.go

### `newGraphConfig`
文件: eino/compose/graph.go

### `handlerPair`
文件: eino/compose/generic_helper.go

### `edgeHandlerManager`
文件: eino/compose/graph_manager.go

### `preNodeHandlerManager`
文件: eino/compose/graph_manager.go

### `preBranchHandlerManager`
文件: eino/compose/graph_manager.go

### `channelManager`
文件: eino/compose/graph_manager.go

### `taskManager`
文件: eino/compose/graph_manager.go

### `testGraphStateCallbackHandler`
文件: eino/compose/graph_test.go

### `ToolAliasConfig`
文件: eino/compose/tool_node.go

### `ToolsNodeConfig`
文件: eino/compose/tool_node.go

### `AgenticResponseMeta`
文件: eino/schema/agentic_message.go

## 服务层
- **edgeHandlerManager** (0 methods)
- **preNodeHandlerManager** (0 methods)
- **preBranchHandlerManager** (0 methods)
- **channelManager** (0 methods)
- **taskManager** (0 methods)

---

请基于以上信息，输出以下结构化知识：

1. **架构总览** — 系统定位、技术栈、服务拆分、部署架构
2. **核心业务流程** — 主要业务场景的流程描述（用文字，不需要 mermaid）
3. **数据库表结构** — 表名、字段、ER 关系
4. **服务层架构** — Service/DAO/Model 分层说明
5. **外部系统集成** — 第三方 API、消息队列等
6. **术语 Glossary** — 业务术语及其含义