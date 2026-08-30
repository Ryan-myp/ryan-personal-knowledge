# Skills 实现指南

> 状态说明：本文保留为设计参考。`SKILL.md` 只负责自然语言专家知识、SOP 和安全边界；它不是 Tool 注册表，也不提供可执行代码。可执行实现以 `capabilities/`、`api_clients/`、`core/` 和 `runtime/` 源码为准。当前四个平台 Capability 共 261 个工具，跨渠道编排由 Runtime + `core/cross_channel.py` 提供。

## 架构分层

```
skills/
├── channels/<platform>/
│   ├── SKILL.md          # 自然语言知识、SOP、安全边界
│   └── references/        # 可选上下文资料
└── cross-channel/
    └── SKILL.md          # 跨渠道知识和策略上下文
```

## 当前状态

| 层级 | 状态 | 说明 |
|------|------|------|
| SKILL.md (上下文层) | ✅ | 专家知识、SOP 和安全边界；不作为 Runtime 工具注册源 |
| runtime/skill.py (加载层) | ✅ 完成 | 自动解析 SKILL.md 和可选 plugin |
| core/tool_registry.py (注册层) | ✅ 完成 | 统一注册与执行前 Schema 校验 |
| core/tool_selector.py (选择层) | ✅ 完成 | 动态选择相关工具 |
| core/context_optimizer.py (优化层) | ✅ 完成 | 构建精简 LLM 上下文 |
| capabilities/ (实现层) | ✅ | 当前 Runtime 的实际 Handler/API Client 入口 |

## 如何补充实现

新增内置渠道能力时，在 `capabilities/<platform>/capability.py` 中定义
`ToolDefinition` 与 Handler，并导出 `create_<platform>_capability(api_client=None)`。
如果需要真实 Provider 访问，再在 `api_clients/<platform>_client.py` 中导出
`create_<platform>_client(credentials)`。Runtime 会按包约定发现它们；无需修改
中心 Router、平台列表或其他渠道的 Skill。

如果只是补充现有渠道或提供业务专属流程，使用标准 Skill 目录中的 `SKILL.md`、
`references/`、`scripts/`、`assets/`、`evals/` 等包文件提供上下文；这些文件由管理
系统保存、版本化和评测，但不会自动执行。`SKILL.md` 只补充自然语言知识、SOP 与
安全边界，不能用 Markdown 工具清单代替 executable Tool 注册。可执行能力必须在
受注册和审计的 Capability/Tool 中实现；`workflow.yaml` 不是 Skill 的上传、编辑或
执行入口。LLM 根据 Skill 上下文提出计划，Runtime + Tool metadata + Harness 负责
顺序、参数、权限、账户、dry-run、确认、幂等和恢复。

## 动态工具选择原理

### 工作流程

```
用户输入: "查询 Google Campaign 报表"
    │
    ▼
IntentParser 解析
    │
    ├─ intent_type: "get_report"
    ├─ platforms: ["google"]
    └─ objective: None
    │
    ▼
DynamicToolSelector 筛选
    │
    ├─ 按意图从 Google 平台工具契约中动态筛选
    ├─ 根据 intent_type="get_report" 筛选
    │   ├─ 关键词: ["report", "get_", "list_", "query"]
    │   └─ 匹配工具:
    │       ├─ google_get_campaign_report ✅
    │       ├─ google_get_keyword_report ✅
    │       └─ ... (共 7 个)
    │
    ├─ 获取专家知识
    │   └─ bidding_strategies.md, report_metrics.md
    │
    ▼
ContextOptimizer 构建 Prompt
    │
    ├─ system prompt 只包含 7 个工具
    ├─ 注入专家知识摘要
    └─ 控制总长度 < 2000 tokens
    │
    ▼
LLM 收到精简上下文
    │
    └─ 调用相关工具执行
```

### 效果对比

| 方案 | 工具数 | Token 消耗 | 响应速度 |
|------|--------|-----------|----------|
| 原始方案（全部工具） | 87 | ~8000 tokens | 慢 |
| 优化方案（动态选择） | 5-12 | ~1000 tokens | 快 5x |

## 扩展新渠道（3 步）

### 步骤 1：创建 SKILL.md（只写自然语言上下文）

```yaml
# skills/new-platform/SKILL.md
---
skill:
  name: new-platform-api
  version: "1.0"
  description: "新平台 API 专家 Skill"
  platform: new-platform
---

# 新平台 API 专家 Skill

## 创建流程与安全边界

描述创建广告系列所需的业务流程、参数解释、枚举含义和确认要求；不要在本文
中声明 Tool 名称来暗示其可执行。
```

### 步骤 2：实现 Capability 与可选 Client

```python
# agents/ad_agent/api_clients/new_platform_client.py（可选）
def create_new_platform_client(credentials): ...

# agents/ad_agent/capabilities/new_platform/capability.py
def create_new_platform_capability(api_client=None): ...
```

Capability 的 `ToolDefinition` 自己声明 `action`、`resource_type`、参数 Schema
和可选 `intent_types`；Client 通过 `api_clients/<platform>_client.py` 的命名约定
自动发现。

### 步骤 3：自动生效

```bash
# 无需修改其他代码，自动加载
python agents/ad_agent/api_server.py
```

## 当前推荐的可执行扩展契约（仅仓库内受信任源码）

对于不需要修改内置 Capability 的新增功能，使用以下目录结构：

```text
skills/channels/<skill-name>/
├── SKILL.md
└── tools.py                 # 或 tools/__init__.py；仅受信任源码可用
```

仓库内受信任的 `tools.py` 导出 `create_skill(api_client=None)`，返回实现 Core
`Skill` 接口的对象。用户通过管理系统上传的 Skill 包不会加载此类插件：

```python
class MySkill(Skill):
    name = "my-skill"
    platform = "meta"  # 也可以是新的、受控配置的平台名

    def get_tools(self):
        return [my_tool_definition]

    def get_tool_handler(self, tool_name):
        return my_handler if tool_name == "my_tool" else None

def create_skill(api_client=None):
    return MySkill()
```

`SKILL.md` 保持自然语言，用于专家知识、SOP 和安全边界。标准操作由
ToolDefinition 的 `action`、`resource_type`、`parent_resource_type` 自动发现；资源 ID
字段和异常结果回查关系也必须由 Tool 显式声明，Runtime 不根据 `campaign`、`ad` 等
资源名或 Tool 名称推断它们；
非标准操作在 ToolDefinition 上声明 `intent_types=["my_intent"]`。新增 Tool
或渠道不需要编辑中心 Router 配置文件。

Runtime 自动加载受信任 plugin 后，工具仍由统一 Registry 执行；不能因为在 `SKILL.md`
中列出工具，就绕过 Handler、schema、白名单或 dry-run/live 安全门禁。

服务启动时会自动：
1. 扫描 `skills/` 目录下所有 SKILL.md，加载受限上下文
2. 按 `capabilities/<platform>/capability.py` 约定发现 Capability
3. 按 `api_clients/<platform>_client.py` 约定创建可选 Client
4. 将 Capability 或 Skill plugin 提供的 Tool 注册到 ToolRegistry
5. 参与动态工具选择，并继续经过统一安全门禁
