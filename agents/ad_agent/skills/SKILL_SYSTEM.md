# ad-agent Skills 系统架构

## 设计原则

1. **Skill 独立** - 每个渠道有独立的 SKILL.md，提供自然语言专家知识、SOP 和安全边界
2. **Capability 扩展** - 渠道 Capability/plugin 提供可执行 Tool、Provider schema 和 adapter
3. **Runtime Harness** - 统一负责路由、权限、dry-run、确认、幂等、恢复和审计
4. **跨渠道编排** - 通过 Skill 的业务流程意图和统一资源模型管理多平台 Campaign

## Skill 目录结构

```
skills/
├── SKILL_SYSTEM.md        # 本文件：系统架构说明
├── channels/              # 渠道 Skill：只放专家上下文与 SOP
│   ├── meta/SKILL.md
│   ├── tiktok/SKILL.md
│   ├── google-ads/SKILL.md
│   └── dv360/SKILL.md
├── businesses/             # 业务 Skill：业务规则与适用渠道
│   └── <business>/SKILL.md
└── cross-channel/          # 跨渠道 Skill：业务 SOP 与统一模型说明
    └── SKILL.md

# 可执行能力不放在上面的 Markdown 目录中：
capabilities/<platform>/capability.py  # 渠道 Capability + ToolDefinition
api_clients/<platform>_client.py        # 可选 Provider Client
skills/<name>/tools.py                  # 可选 Skill plugin
```

## Skill 定义格式

每个 Skill 的 SKILL.md 包含身份元数据、自然语言知识、流程说明和安全边界。
它不是 Tool 注册表，也不应通过 Markdown 标题、表格或 YAML 清单直接产生可执行能力。
每个可执行 Tool 必须由 Capability/plugin 以结构化 `ToolDefinition` 和 Handler 注册，
这样 schema、权限、Provider adapter 和 Harness 门禁可以被 Runtime 统一验证。

如果确实需要确定性的多步编排，可以在 Skill 目录中额外提供 `workflow.yaml`；它只能
声明 Tool 名称、依赖、条件和输入输出映射，不能包含 Python、网络调用或绕过 Runtime 的
执行逻辑。普通 Skill 不需要这个文件，流程知识仍然可以只用自然语言表达。

SKILL.md 的推荐内容：

```yaml
skill:
  name: meta-marketing-api
  version: "1.0"
  description: "Meta Marketing API 专家 Skill"
  platform: meta
  author: "Ryan"
  
skills:
  - name: meta_bidding_expert
    description: "出价策略专家"
    strategies: [...]
```

## 跨渠道 Campaign 管理

跨渠道 Skill 提供业务层流程和统一口径；真正的查询/计划/执行能力仍来自已注册的
平台 Capability 和 Tool：

1. **Campaign 总览** - 统一查看各平台 Campaign 状态
2. **预算分配** - 跨平台预算智能分配
3. **性能对比** - 对比各平台 ROI/CPA
4. **批量操作** - 一键启停多个平台 Campaign

## 扩展新渠道

按以下边界扩展：

1. 创建 `skills/channels/{channel}/SKILL.md`，描述专家知识、SOP 和安全边界
2. 创建 `capabilities/{channel}/capability.py`，导出约定的 Capability factory
3. 按需创建 `api_clients/{channel}_client.py` 或 Skill plugin
4. 让 Runtime 自动发现；Tool 仍需通过统一 Registry、schema 和 Harness 安全门禁
