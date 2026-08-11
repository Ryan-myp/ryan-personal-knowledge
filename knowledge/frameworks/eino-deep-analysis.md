# Eino 框架深度分析报告

> 生成时间：2026-08-12  
> 分析工具：biz-delivery learn 模式  
> 仓库：github.com/cloudwego/eino

---

## 一、框架概述

### 1.1 基本信息

| 属性 | 值 |
|------|-----|
| 名称 | Eino (易诺) |
| 组织 | CloudWeGo (字节跳动) |
| 语言 | Go |
| 定位 | AI 应用开发框架 |
| 包数量 | 43 |
| Structs | 294 |
| Functions | 438 |
| 代码图节点 | 2582 |
| 代码图边 | 3439 |

### 1.2 核心特性

Eino 是一个面向 Go 语言的 AI 应用开发框架，主要特性：

1. **工作流编排** - 基于图的 DAG（有向无环图）编排
2. **Agent 系统** - 支持 ReAct、Plan-and-Execute 等 Agent 模式
3. **组件化设计** - 模块化组件（Model、Tool、Retriever 等）
4. **流式处理** - 支持流式响应和回调
5. **多模态支持** - 支持文本、图像等多种输入输出

---

## 二、架构设计

### 2.1 核心模块

```
┌─────────────────────────────────────────────────────────────┐
│                         Eino Core                           │
├─────────────────────────────────────────────────────────────┤
│  compose     │  工作流编排引擎（Graph/Workflow/Chain）       │
│  schema      │  数据类型定义（Message/Tool/Stream）          │
│  callbacks   │  回调机制（Handler/Aspect）                  │
│  react       │  ReAct Agent 实现                           │
│  planexecute │  Plan-and-Execute Agent 实现                 │
│  supervisor  │  多Agent编排                                 │
│  model       │  LLM模型适配层                              │
│  tool        │  Tool工具定义                               │
│  retriever   │  检索器接口                                 │
│  embedding   │  Embedding适配层                            │
│  document    │  文档处理                                   │
│  prompt      │  Prompt模板管理                             │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 核心组件详解

#### 2.2.1 Compose（编排引擎）

**核心接口：**

```go
// Graph - 工作流图
type Graph struct {
    // 节点管理
    AddNode(name string, node Node) *Graph
    AddEdge(from, to string) *Graph
    
    // 编译与执行
    Compile(ctx context.Context, opts ...Option) (*CompiledGraph, error)
    Invoke(ctx context.Context, input Any, opts ...Option) (Any, error)
}

// CompiledGraph - 编译后的图
type CompiledGraph interface {
    Invoke(ctx context.Context, input Any, opts ...Option) (Any, error)
    Stream(ctx context.Context, input Any, opts ...Option) (StreamReader, error)
}
```

**支持的编排模式：**

| 模式 | 说明 |
|------|------|
| Graph | 通用 DAG 编排 |
| Workflow | 工作流编排（带状态） |
| Chain | 线性链式调用 |
| FanIn/FanOut | 多输入/多输出聚合 |

#### 2.2.2 Schema（数据类型）

**核心类型：**

```go
// 消息类型
type Message struct {
    Role      Role          // system/user/assistant/tool
    Content   []ContentBlock
    Metadata  map[string]Any
}

// 内容块
type ContentBlock struct {
    Type      ContentType    // text/image/tool_call
    Text      string
    Image     *ImageBlock
    ToolCall  *ToolCall
}

// Tool定义
type Tool struct {
    Name        string
    Description string
    InputSchema jsonschema.Definition
    OutputSchema jsonschema.Definition
}
```

#### 2.2.3 Callbacks（回调机制）

```go
// Handler - 回调处理器
type Handler interface {
    OnStart(ctx context.Context, info RunInfo) context.Context
    OnEnd(ctx context.Context, info RunInfo, output Any) Any
    onError(ctx context.Context, info RunInfo, err error)
}

// 支持Aspect-Oriented编程
type Aspect interface {
    Around(handler Handler) Handler
}
```

#### 2.2.4 Agent 系统

**ReAct Agent:**

```go
// Agent - ReAct模式Agent
type Agent struct {
    ChatModel     ChatModel
    Tools         []Tool
    Prompt        Prompt
    MaxSteps      int
}

func NewAgent(opts ...Option) *Agent
func (a *Agent) Invoke(ctx context.Context, input Any) (Any, error)
```

**Plan-and-Execute:**

```go
// Planner - 规划器
type Planner interface {
    Plan(ctx context.Context, task string) (*Plan, error)
}

// Executor - 执行器
type Executor interface {
    Execute(ctx context.Context, plan *Plan) (*Result, error)
}
```

**Supervisor（多Agent编排）:**

```go
// Supervisor - 多Agent协调
type Supervisor struct {
    Agents   map[string]*Agent
    Router   Router
}

func NewSupervisor(opts ...Option) *Supervisor
```

---

## 三、核心流程

### 3.1 工作流执行流程

```
用户输入
    ↓
Graph.Compile() 编译为 CompiledGraph
    ↓
CompiledGraph.Invoke() 执行
    ↓
┌─────────────────────────────────────┐
│  遍历DAG节点                        │
│  ├─ 执行节点逻辑                    │
│  ├─ 触发回调（OnStart/OnEnd）       │
│  └─ 处理中断/恢复                   │
└─────────────────────────────────────┘
    ↓
输出结果
```

### 3.2 Agent执行流程（ReAct）

```
┌─────────────────────────────────────────────────────────┐
│  ReAct Agent Loop                                       │
├─────────────────────────────────────────────────────────┤
│  1. Think: LLM生成思考过程                              │
│     ↓                                                   │
│  2. Act: 调用Tool执行操作                               │
│     ↓                                                   │
│  3. Observe: 获取Tool执行结果                           │
│     ↓                                                   │
│  4. 判断是否完成 → 循环或输出                           │
└─────────────────────────────────────────────────────────┘
```

### 3.3 流式处理流程

```
Input
    ↓
Graph.Invoke() with stream option
    ↓
StreamReader <- 返回流式读取器
    ↓
for chunk := range reader.Read() {
    // 处理每个chunk
}
```

---

## 四、关键数据结构

### 4.1 Graph 节点类型

| 节点类型 | 说明 |
|----------|------|
| Node | 基础节点接口 |
| ToolNode | 工具调用节点 |
| ModelNode | LLM调用节点 |
| ConditionNode | 条件分支节点 |
| ParallelNode | 并行执行节点 |
| AgenticToolsNode | 智能工具节点 |

### 4.2 编译选项

```go
type GraphCompileOptions struct {
    MaxRetry         int                    // 最大重试次数
    Timeout          time.Duration          // 超时时间
    InterruptConfig  InterruptConfig        // 中断配置
    FanInMergeConfig FanInMergeConfig       // FanIn合并配置
    CheckpointStore  CheckPointStore        // 检查点存储
}
```

### 4.3 中断与恢复

```go
// 中断类型
type InterruptType int

const (
    InterruptNone InterruptType = iota
    InterruptRequested
    InterruptTimeout
)

// 中断处理
func CompositeInterrupt(interrupts ...Interrupt) Interrupt
func ExtractInterruptInfo(result Any) (*InterruptInfo, bool)
func BatchResumeWithData(graph CompiledGraph, data map[string]Any)
```

---

## 五、扩展点

### 5.1 可插拔组件

```go
// 模型适配
type ChatModel interface {
    Generate(ctx context.Context, msgs []*Message, opts ...Option) (*Message, error)
    Stream(ctx context.Context, msgs []*Message, opts ...Option) (StreamReader, error)
}

// Tool适配
type InvokableTool interface {
    Invoke(ctx context.Context, input Any, opts ...Option) (Any, error)
}

type StreamableTool interface {
    Stream(ctx context.Context, input Any, opts ...Option) (StreamReader, error)
}

// Retriever适配
type Retriever interface {
    Retrieve(ctx context.Context, query string, opts ...Option) ([]Document, error)
}
```

### 5.2 插件系统

```go
// Callback插件
AppendGlobalHandlers(handlers ...Handler)
AppendHandlers(handlers ...Handler)

// Aspect切面
type Aspect interface {
    Around(handler Handler) Handler
}
```

---

## 六、术语表

| 术语 | 英文 | 说明 |
|------|------|------|
| 工作流 | Workflow | 带状态的有向图执行流程 |
| 编译图 | CompiledGraph | 编译后的可执行图 |
| 节点 | Node | 图中的执行单元 |
| 边 | Edge | 节点间的连接 |
| 中断 | Interrupt | 执行过程中的暂停点 |
| 恢复 | Resume | 从中断点继续执行 |
| 检查点 | Checkpoint | 执行状态的快照 |
| 回调 | Callback | 执行事件的监听器 |
| 流式 | Streaming | 分块返回结果 |
| FanIn | 聚合 | 多输入合并为单输出 |
| FanOut | 广播 | 单输入分发为多输出 |

---

## 七、与竞品的对比

| 特性 | Eino | LangChain | DSPy |
|------|------|-----------|------|
| 语言 | Go | Python/JS | Python |
| 编排方式 | DAG图 | 链式/图 | 声明式 |
| Agent模式 | ReAct/Plan|ReAct/Plan | 仅Plan |
| 流式支持 | ✅ | ✅ | ❌ |
| 中断/恢复 | ✅ | ❌ | ❌ |
| 类型安全 | 强 | 弱 | 中 |

---

## 八、总结

### 8.1 核心优势

1. **类型安全** - Go强类型系统保证编译期检查
2. **编排能力** - 灵活的DAG图编排，支持复杂工作流
3. **中断恢复** - 支持长时间运行的Agent任务
4. **流式原生** - 第一性支持的流式处理
5. **模块化** - 清晰的组件分层，易于扩展

### 8.2 适用场景

- 需要高性能AI应用的Go项目
- 复杂的多步骤Agent工作流
- 需要中断/恢复的长时任务
- 对类型安全有高要求的系统

### 8.3 代码质量评估

| 指标 | 评分 | 说明 |
|------|------|------|
| 架构设计 | ⭐⭐⭐⭐⭐ | 清晰的模块分层 |
| 类型安全 | ⭐⭐⭐⭐⭐ | 强类型+泛型 |
| 扩展性 | ⭐⭐⭐⭐ | 接口抽象完善 |
| 测试覆盖 | ⭐⭐ | 需提升 |
| 文档完整 | ⭐⭐⭐ | 部分缺失 |

---

*报告由 biz-delivery 自动生成*
