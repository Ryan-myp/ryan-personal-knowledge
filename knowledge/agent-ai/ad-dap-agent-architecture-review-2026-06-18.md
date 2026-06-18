# DAP Agent 架构评审报告

> 日期: 2026-06-18
> 方法: 基于 dap-agent skill + agent-ads-architecture skill 的知识框架，对照 dap 项目源码逐项验证
> 目的: 检验两个东西 — (1) 知识库到底是什么水平 (2) dap-agent 到底怎么样

---

## 一、知识库水平评估

### 1.1 知识库覆盖度

| 评估维度 | 知识库是否有对应知识 | 源码是否实现 | 结论 |
|---------|-------------------|------------|------|
| 分层架构 | ✅ agent-ads-architecture 有 | ✅ Dispatcher → Agent → Runtime → MCP | 匹配 |
| 双阶段意图 | ✅ agent-ads-architecture 有 | ✅ planWithStandardADK → heuristicPlan → deterministicPlan | 匹配 |
| 凭证安全 | ✅ agent-ads-architecture 有（Pitfall 警告） | ❌ **源码无 credential 模块** | ⚠️ 知识库有提醒但项目没实现 |
| Agent 类型体系 | ✅ 4 种标准类型 | ⚠️ 只有 UA Campaign 一种 Agent | ⚠️ 知识库有框架但项目只有 1 种 |
| Skill 系统 | ✅ dap-agent skill 详细描述了 v2.0/v3.1 | ✅ 已实现 | 匹配 |
| 四层扩展点 | ✅ extension-points.md 详细描述 | ✅ 已实现 | 匹配 |
| MCP 安全护栏 | ✅ agent-ads-architecture 有 | ⚠️ 有 MCPToolCaller 但无安全策略/权限检查 | ⚠️ 部分实现 |
| 记忆系统 | ✅ 6 层设计 | ✅ 6 层实现 | 匹配 |
| 熔断器 | ✅ circuitbreaker 设计 | ✅ 已实现 | 匹配 |
| 幂等性 | ✅ idempotency 设计 | ✅ 已实现 | 匹配 |

### 1.2 知识库准确性验证

**知识库说的 vs 源码实际：**

| 知识库声明 | 源码验证 | 准确度 |
|-----------|---------|--------|
| UA Go 代码 ~10,708 行 | ua_campaign/ 共 14,420 行（含 config/session/log/model） | ⚠️ 偏低 |
| support_flow.go 3,706 行 | support_flow.go 2,872 行 | ⚠️ 偏高（已拆分） |
| 状态机 12 状态 | 14 个 State 常量 | ⚠️ 少了 2 个 |
| 12 个 Skill Steps | workflow.yaml 8 个 step + 5 个 subflow | ✅ 基本匹配 |
| 28+ 个槽位字段 | slot_schema.yaml 28 个字段 | ✅ 准确 |
| builtin executor 9 个 | 9 个 builtin executor | ✅ 准确 |
| 5 个 subflow | 5 个 subflow YAML | ✅ 准确 |
| 11 个 reference YAML | 11 个 YAML 文件 | ✅ 准确 |
| Phase 1 wait_external/verify_published 未实现 | 源码中确实没有 | ✅ 准确 |
| 测试覆盖 6/10 | 29/75 文件有测试 = 39% | ✅ 准确 |

### 1.3 知识库质量问题

**知识库做得好的：**
1. v3.1-assessment.md 提供了真实数据（代码行数、评分）
2. extension-points.md 记录了 v3.1 实践教训（"不要把查询流程交给 LLM"）
3. architecture-review-2026-06-18.md 列出了 P0-P5 问题
4. 文件结构定义清晰（4 必须 + 5 可选）

**知识库缺失的：**
1. **没有 MCP 安全策略文档** — agent-ads-architecture 说了"凭证安全是致命错误"，但 dap 项目里完全没有 credential 管理模块
2. **没有 MCP 路由规则文档** — 源码有 RoutingMCPToolCaller 但知识库没记录路由规则
3. **没有 MCP 超时配置文档** — HTTPMCPToolCaller 默认 30s 超时，知识库没提
4. **没有 RunConfirmedToolActionWithVerify 的参数文档** — 这个函数有 15 个回调参数，是代码异味，但知识库没记录
5. **没有测试策略文档** — 测试覆盖率 39%，知识库只说了 6/10

### 1.4 知识库总体评分

| 维度 | 评分 | 说明 |
|------|------|------|
| 覆盖度 | 8/10 | 核心架构都覆盖了，但 MCP 安全/路由/超时缺失 |
| 准确性 | 8.5/10 | 数据基本准确，部分行号有偏差 |
| 实用性 | 7/10 | 有实践教训但缺少关键安全文档 |
| 时效性 | 9/10 | 2026-06-18 的最新评估 |
| **综合** | **8.1/10** | 中等偏上水平 |

---

## 二、DAP Agent 架构评审

### 2.1 架构优势

#### ✅ 配置驱动方向正确

```yaml
# 验证：skill_bundle.yaml 确实是索引文件
version: v1
workflow: workflow.yaml
slot_schema: slot_schema.yaml
tools: tool_arguments.yaml
messages: messages.yaml
subflows:
  ua_lookup_flow: subflows/lookup_flow.yaml
  ...
```

源码 `CompileSkillBundle()` 在启动时读取 `skill_bundle.yaml` → 加载引用的 YAML → 编译成 `SkillBundle[S]`，运行时纯内存只读。验证通过。

#### ✅ 泛型类型安全

```go
type DynamicAgent[S any] struct {
    manifest      AgentManifest
    bundle        *SkillBundle[S]
    runner        RuntimeRunner[S]
    store         SessionStore[*DynamicSession[S]]
    ...
}
```

`DynamicAgent[dynamicAgentCompileCheckSlots]` 编译时校验。验证通过。

#### ✅ 四层扩展点体系

| 级别 | 验证 |
|------|------|
| 级别 1: StepExecutor | ✅ `StepExecutorRegistry` + `custom:*` 注册 |
| 级别 2: WrapperAgent | ✅ `WrapperAgent` + Hooks |
| 级别 3: Custom Runtime | ✅ `RuntimeRunner` 接口可替换 |
| 级别 4: UniversalAgent | ✅ `core.UniversalAgent` 接口 |

验证通过。

#### ✅ MCP 强制走工具层

```go
type MCPToolCaller interface {
    CallTool(ctx context.Context, req MCPToolRequest) (*MCPToolResult, error)
}
```

业务写操作必须经过 `MCPToolCaller`，有 `DryRunMCPToolCaller` 和 `UnavailableMCPToolCaller` 测试替身。验证通过。

#### ✅ 双层意图规划

源码 `planning/agent.go`:
- `planWithStandardADK` — LLM（Eino ADK）
- `heuristicPlan` — 规则 fallback
- `deterministicPlan` — 确定性兜底

验证通过。

#### ✅ 6 层记忆系统

```
core/memory/:
  profile.go    — ProfileStore
  role.go       — RoleStore
  preference.go — PreferenceStore
  procedural.go — ProceduralStore
  episodic.go   — EpisodicStore
  team.go       — TeamStore
  manager.go    — Manager (聚合)
```

验证通过。

#### ✅ 熔断器

```go
// core/circuitbreaker/circuitbreaker.go
type CircuitBreaker struct {
    state          State        // closed/open/half_open
    failureCount   int          // 默认 5
    successCount   int          // 默认 3
    resetTimeout   time.Duration // 默认 30s
    windowDuration time.Duration // 默认 60s
}
```

验证通过。

#### ✅ 幂等性

```go
// core/idempotency/idempotency.go
type Lock struct {
    Key      string
    Status   LockStatus  // acquired/waiting/completed/failed
    Owner    string
    ExpiresAt time.Time
}
```

验证通过。

#### ✅ 可观测性

```go
// core/observability/observability.go
// 每个 step 都有 logSummaryContext 记录
// trace_id, span_id, 步骤耗时, 工具调用记录
```

验证通过。

#### ✅ 会话持久化

```go
// core/checkpoint_session_store.go
// 文件持久化，每次响应都写入
```

验证通过。

### 2.2 架构问题

#### ⚠️ P0: support_flow.go 2,872 行（已拆分但从 3,706 降下来）

虽然拆分了 `support_flow_list_query.go`（797 行），但 `support_flow.go` 仍有 2,872 行。建议继续拆分：
- `support_flow_creative.go`
- `support_flow_publish.go`
- `support_flow_validation.go`

#### ⚠️ P1: Phase 1 阻塞项未完成

知识库确认 `builtin:wait_external` 和 `builtin:verify_published` 未实现。源码中确实没有这两个 executor。

#### ⚠️ P2: RunConfirmedToolActionWithVerify 有 15 个回调参数

```go
type ConfirmedToolActionWithVerifyInput[S any] struct {
    Context            WorkflowContext[S]
    Caller             MCPToolCaller
    Confirmed          bool
    Review             func() *WorkflowResult[S]
    Request            MCPToolRequest
    ToolError          func(*MCPToolResult) string
    Apply              func(*S, *MCPToolResult)
    BuildVerifyRequest func(S, *MCPToolResult) (MCPToolRequest, bool)
    OnCallError        func(S, ToolCallRecord) *WorkflowResult[S]
    OnToolError        func(S, ToolCallRecord, string, *MCPToolResult) *WorkflowResult[S]
    OnVerifyCallError  func(S, ToolCallRecord, ToolCallRecord, *MCPToolResult) *WorkflowResult[S]
    IsVerified         func(S, *MCPToolResult, *MCPToolResult) bool
    OnNotVerified      func(S, ToolCallRecord, ToolCallRecord, *MCPToolResult, *MCPToolResult) *WorkflowResult[S]
    OnSuccess          func(S, ToolCallRecord, ToolCallRecord, *MCPToolResult, *MCPToolResult) *WorkflowResult[S]
}
```

14 个回调参数，每次调用都要写一堆匿名函数。知识库没记录这个问题。

#### ⚠️ P3: 无 MCP 安全策略

知识库 `agent-ads-architecture` 明确说了"凭证安全是致命错误"，但源码中：
- 没有 `credential_manager.go`
- 没有 `security/policy.go`
- 没有 `permission` 检查
- MCP 调用只有 `DryRun` 和 `Unavailable` 测试替身，没有权限验证

**这是知识库有提醒但项目没实现的关键差距。**

#### ⚠️ P4: 无凭证管理

同上。`agent-ads-architecture` 的 Pitfall 写了：
> 凭证永远不硬编码，从环境变量读取
> .gitignore 排除所有凭证文件

但 dap 项目中找不到任何 credential 相关文件。

#### ⚠️ P5: 测试覆盖率 39%

29/75 文件有测试。知识库评分 6/10 是准确的。
- `slot_guard` 无测试（知识库确认）
- `support_flow.go` 2,872 行无单独测试
- `patterns.go` 15 个回调参数的函数无测试

#### ⚠️ P6: TypedDynamicAgent 嵌套三层

源码验证：
```
TypedDynamicAgent (core/typed_dynamic_agent.go)
  → DynamicAgent (core/dynamic_agent.go)
    → WrapperAgent (core/patterns.go)
```

调试 trace 层级深。知识库 `architecture-review-2026-06-18.md` 确认了这个问题。

### 2.3 新增 Agent 成本验证

#### Calculator 示例（简单 Agent）

```
calculator/skill/:
  SKILL.md                    ✅ 必须
  agent_metadata.yaml         ✅ 必须
  references/skill_bundle.yaml ✅ 必须
  references/workflow.yaml    ✅ 必须
  references/slot_schema.yaml  ✅ 可选
  references/tools.yaml        ✅ 可选
  references/messages.yaml     ✅ 可选
  references/subflows/         ✅ 可选
```

workflow.yaml 6 个 steps，其中 1 个 custom executor。验证：简单 Agent 确实只需要 ~250 行。

#### UA Campaign（复杂 Agent）

```
ua-campaign-creation/:
  SKILL.md                    ✅
  agent_metadata.yaml         ✅
  references/ (11 个 YAML)    ✅
  subflows/ (5 个 YAML)       ✅
```

- 28 个 slot 字段
- 8 个 workflow steps
- 5 个 subflows
- 12 个 custom executors
- 14 个状态
- 100+ MCP tool 映射

验证：复杂 Agent 仍然需要大量 Go 代码。

### 2.4 DAP Agent 总体评分

| 维度 | 评分 | 说明 |
|------|------|------|
| 架构合理性 | 8/10 | 分层清晰，配置驱动方向正确 |
| 可拓展性 | 8/10 | 4 级扩展点体系完善 |
| 接入方便性 | 6/10 | 简单 Agent 方便，复杂 Agent 仍繁琐 |
| 稳定性 | 8/10 | 熔断/幂等/持久化都有，但 MCP 安全缺失 |
| 测试覆盖 | 4/10 | 39% 偏低，关键模块无测试 |
| 安全性 | 5/10 | 无凭证管理、无 MCP 安全策略 |
| **综合** | **6.5/10** | 方向对但执行不到位 |

---

## 三、知识库 vs 源码差距总结

### 知识库有但源码没有的

| 知识库内容 | 源码状态 | 风险 |
|-----------|---------|------|
| 凭证安全管理 | ❌ 无 | 🔴 高 — 凭证泄露风险 |
| MCP 安全策略/权限 | ❌ 无 | 🔴 高 — 未授权调用风险 |
| MCP 路由规则文档 | ❌ 无 | 🟡 中 — 维护困难 |
| MCP 超时配置文档 | ❌ 无 | 🟢 低 — 默认 30s 够用 |
| RunConfirmedToolActionWithVerify 参数文档 | ❌ 无 | 🟡 中 — 代码异味 |

### 知识库准确的部分

| 知识库声明 | 源码验证 | 误差 |
|-----------|---------|------|
| UA Go ~10,708 行 | 14,420 行（含子目录） | 统计口径不同 |
| support_flow.go 3,706 行 | 2,872 行 | 已拆分减少 |
| 12 状态 | 14 状态 | 少了 2 个 |
| 12 Skill Steps | 8 steps + 5 subflows | 基本匹配 |
| 28+ 槽位 | 28 字段 | ✅ 准确 |
| 9 builtin executor | 9 个 | ✅ 准确 |
| 5 subflow | 5 个 | ✅ 准确 |
| Phase 1 未完成 | 确实未完成 | ✅ 准确 |
| 测试 6/10 | 39% | ✅ 准确 |

### 知识库缺少的

1. MCP 安全策略（凭证/权限）
2. MCP 路由规则
3. RunConfirmedToolActionWithVerify 的参数说明
4. 测试策略
5. 性能基准数据

---

## 四、结论

### 知识库水平：8.1/10

知识库在架构设计层面是**中等偏上**水平：
- ✅ 架构方向判断准确
- ✅ 实践教训有价值（v3.1 教训）
- ✅ 数据结构基本准确
- ⚠️ 缺少 MCP 安全/凭证管理的文档
- ⚠️ 部分行号有偏差

### DAP Agent 水平：6.5/10

DAP Agent 架构**方向正确但执行不到位**：
- ✅ 配置驱动 + 泛型 + 四层扩展点 设计合理
- ✅ 记忆系统/熔断/幂等/可观测性 都有
- ❌ 无 MCP 安全策略（凭证管理）— 这是最严重的缺口
- ❌ 测试覆盖率 39% 偏低
- ❌ support_flow.go 2,872 行太大
- ❌ RunConfirmedToolActionWithVerify 15 个回调参数

### 优先级建议

1. 🔴 **P0: 加 MCP 安全策略和凭证管理** — 知识库有提醒但项目没实现
2. 🔴 **P0: 完成 Phase 1** — wait_external + verify_published
3. 🟡 **P1: 拆 support_flow.go** — 从 2,872 降到 < 1,000
4. 🟡 **P1: 给 RunConfirmedToolActionWithVerify 加默认回调组**
5. 🟢 **P2: 补测试** — slot_guard, support_flow, patterns
6. 🟢 **P2: 更新知识库** — 补 MCP 安全/路由/超时文档
