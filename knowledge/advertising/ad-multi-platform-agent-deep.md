# 多平台广告投放 Agent 系统架构深度指南

> **领域**: 广告投放 / 跨平台
> **深度**: ⭐⭐⭐⭐⭐ 实战级指南
> **标签**: cross-platform, multi-agent, orchestrator, llm-agent, skill-system
> **更新时间**: 2026-08-14
> **类型**: architecture/production

---

## 目录

- [一、核心概念与架构](#一核心概念与架构)
  - [1.1 为什么需要一个多平台广告投放 Agent 系统](#11-为什么需要一个多平台广告投放-agent-系统)
  - [1.2 核心术语与角色定义](#12-核心术语与角色定义)
  - [1.3 整体架构图（ASCII）](#13-整体架构图ascii)
  - [1.4 编排层级结构：Orchestrator / Supervisor / Worker](#14-编排层级结构orchestrator--supervisor--worker)
  - [1.5 Agent 拓扑模型：Hierarchical vs Peer-to-Peer](#15-agent-拓扑模型hierarchical-vs-peer-to-peer)
  - [1.6 任务分解（Task Decomposition）](#16-任务分解task-decomposition)
  - [1.7 消息路由与协议](#17-消息路由与协议)
  - [1.8 协调模式：同步 / 异步 / 事件驱动](#18-协调模式同步--异步--事件驱动)
- [二、深度原理解析](#二深度原理解析)
  - [2.1 平台抽象层设计理念](#21-平台抽象层设计理念)
  - [2.2 统一的接口契约（Contract）](#22-统一的接口契约contract)
  - [2.3 Go Interface 定义](#23-go-interface-定义)
  - [2.4 Python ABC 定义](#24-python-abc-定义)
  - [2.5 各平台实现策略](#25-各平台实现策略)
  - [2.6 错误 / 限流 / 速率归一化](#26-错误--限流--速率归一化)
  - [2.7 与 ad_platform_api.py 的对应关系](#27-与-ad_platform_apipy-的对应关系)
  - [2.8 Agent 记忆系统理论](#28-agent-记忆系统理论)
  - [2.9 记忆存储模型与 Schema](#29-记忆存储模型与-schema)
  - [2.10 状态机、快照与恢复](#210-状态机快照与恢复)
  - [2.11 事件日志与溯源](#211-事件日志与溯源)
  - [2.12 反思（Reflection）机制](#212-反思reflection机制)
  - [2.13 Agent Skill 系统设计](#213-agent-skill-系统设计)
  - [2.14 Skill 注册表与调度](#214-skill-注册表与调度)
  - [2.15 Skill 调用示例与链路](#215-skill-调用示例与链路)
- [三、生产���境实战](#三生产环境实战)
  - [3.1 完整系统组件图](#31-完整系统组件图)
  - [3.2 编排循环：Plan→Act→Observe→Reflect](#32-编排循环planactobservereflect)
  - [3.3 并发与协作模型](#33-并发与协作模型)
  - [3.4 防抖与冲突消解（并发改预算）](#34-防抖与冲突消解并发改预算)
  - [3.5 监控与可观测性](#35-监控与可观测性)
  - [3.6 审计与合规](#36-审计与合规)
  - [3.7 灰度上线](#37-灰度上线)
  - [3.8 故障恢复与容灾](#38-故障恢复与容灾)
  - [3.9 端到端真实投放场景推演](#39-端到端真实投放场景推演)
  - [3.10 与知识库现有 Skills 的对接](#310-与知识库现有-skills-的对接)
- [四、常见问题与排查](#四常见问题与排查)
- [五、自测题](#五自测题)

---

## 一、核心概念与架构

### 1.1 为什么需要一个多平台广告投放 Agent 系统

现代广告投放早已不是「在单一平台建一个 Campaign」那么简单。一个成熟的品牌/代理商需要在 Google Ads、Meta Ads、TikTok Ads、Display & Video 360（DV360）等多个平台同时投放，而每一个平台都有各自不同的：

- **数据模型**：Campaign / Ad Group / Ad 的层级结构各家不同（Meta 是 Campaign → AdSet → Ad；Google 是 Campaign → Ad Group → Ad；TikTok 是 Campaign → Ad Group → Ad；DV360 是 Partner → Advertiser → Campaign → Insertion Order → Line Item → Creative）。
- **API 协议**：REST（TikTok、Meta Graph API）、gRPC/proto（Google Ads API）、REST/discovery（DV360）。
- **鉴权方式**：OAuth2 refresh token（Google）、长期 access token（Meta）、Access-Token header（TikTok）、Service Account JWT（DV360）。
- **出价与预算语义**：micros（Google）、分（TikTok）、dollar 类（Meta）、daily_budget / lifetime_budget……
- **限流与配额规则**：各家完全不同。
- **报表口径**：归因窗口、时区、去重规则、数据延迟各不相同。

一个**人类投放优化师**（Media Buyer）一天的工作：

```
1. 早晨先打开 4 个平台后台，刷新昨晚的投放数据；
2. 对比各平台 ROAS，决定今天把钱花在哪；
3. 把明天要提量的 Campaign 手动加预算、改出价；
4. 发现 Meta 某 AdSet CPA 飙高，手动暂停；
5. 看到 Google 有个关键词效果爆炸，加否定词、扩量；
6. 检查 DV360 某个 Line Item 的填充率；
7. 基于归因报告决定是否关停某个渠道；
8. 花 2 个小时写日报。
```

当 Campaign 数量到达上百个、跨平台后，人类不可能手工完成这一切。**多平台广告投放 Agent 系统** 的目标，就是把这套「感知 → 决策 → 执行 → 复盘」的循环自动化、智能化。

> 一句话定义：**多平台广告投放 Agent 系统** 是一个由 Orchestrator（编排器）+ 多个平台专属 Agent + 多个通用 Agent 组成的协作智能体集群，通过统一平台抽象层屏蔽各平台 API 差异，配合记忆系统、Skill 系统，实现跨 Google / Meta / TikTok / DV360 的自动化广告投放、优化与复盘。

### 1.2 核心术语与角色定义

| 术语 | 英文 | 说明 |
|------|------|------|
| 编排器 | Orchestrator / Supervisor | 顶层的「总导演」，负责把用户目标拆解成任务、分发给各 Agent、汇总结果、做全局决策 |
| 平台专属 Agent | Platform Agent | 每个广告平台一个，如 GoogleAgent、MetaAgent、TikTokAgent、DV360Agent，只懂自己平台 |
| 通用 Agent | Generic Agent | 跨平台能力，如数据 Agent、创意 Agent、归因 Agent、风控 Agent |
| 任务 | Task | 一个可执行的单元，如「降低 Meta CPA」 |
| 技能 | Skill | 一组预定义的工具/能力，如 google-ads-api-expert，是可被 Agent 调用的原子能力 |
| 记忆 | Memory | Agent 的持久化状态，含短期工作记忆、长期情景记忆、向量库 |
| 平台抽象层 | Platform Abstraction Layer | 统一的接口契约 + 各平台实现，屏蔽 API 差异 |
| 状态机 | State Machine | 描述 Campaign/任务的合法状态流转 |
| 反射 | Reflection | Agent 在行动后对自身行为的复盘与改进 |

### 1.3 整体架构图（ASCII）

```
┌───────────────────────────────────────────────────────────────────────────────┐
│                             用户 / 业务方（Goal）                              │
│                     "ROAS>3 的前提下，全渠道放量 30%"                           │
└───────────────────────────────────────┬───────────────────────────────────────┘
                                        │
                                        ▼
┌───────────────────────────────────────────────────────────────────────────────┐
│                      ORCHESTRATOR / SUPERVISOR (总编排器)                      │
│  ┌────────────┐  ┌───────────────┐  ┌──────────────┐  ┌───────────────────┐  │
│  │ 目标理解    │  │ 任务分解       │  │ 调度与路由    │  │ 全局预算/冲突仲裁  │  │
│  │ (Planner)  │  │ (Decomposer)  │  │ (Router)     │  │ (Budget Arbiter)  │  │
│  └────────────┘  └───────────────┘  └──────────────┘  └───────────────────┘  │
│  ┌────────────┐  ┌───────────────┐  ┌──────────────┐  ┌───────────────────┐  │
│  │ 反思        │  │ 记忆协调器     │  │ 事件总线      │  │ 审计/监控          │  │
│  │ (Reflector)│  │ (Memory Hub)  │  │ (Event Bus)  │  │ (Audit/Monitor)   │  │
│  └────────────┘  └───────────────┘  └──────────────┘  └───────────────────┘  │
└───────────────────────────────────────┬───────────────────────────────────────┘
                                        │ 消息路由（统一 Agent 消息协议）
        ┌───────────────────────────────┼───────────────────────────────┐
        ▼                               ▼                               ▼
┌───────────────────┐        ┌───────────────────┐        ┌───────────────────┐
│   GOOGLE AGENT    │        │    META AGENT     │        │   TIKTOK AGENT    │
│  (平台专属 Agent)  │        │   (平台专属 Agent)  │        │  (平台专属 Agent)  │
│ ┌───────────────┐ │        │ ┌───────────────┐ │        │ ┌───────────────┐ │
│ │ Skill:        │ │        │ │ Skill:        │ │        │ │ Skill:        │ │
│ │ google-ads-   │ │        │ │ meta-marketing-│ │        │ │ tiktok-ads-   │ │
│ │ api-expert    │ │        │ │ api-expert    │ │        │ │ expert        │ │
│ └───────────────┘ │        │ └───────────────┘ │        │ └───────────────┘ │
│ ┌───────────────┐ │        │ ┌───────────────┐ │        │ ┌───────────────┐ │
│ │ 短/长期记忆    │ │        │ │ 短/长期记忆    │ │        │ │ 短/长期记忆    │ │
│ └───────────────┘ │        │ └───────────────┘ │        │ └───────────────┘ │
└─────────┬─────────┘        └─────────┬─────────┘        └─────────┬─────────┘
          │                            │                            │
          ▼                            ▼                            ▼
┌──────────────────────────────────────────── 统一平台抽象层 ────────────────────┐
│         PlatformPort (接口契约)                                                │
│   createCampaign  getReport  updateBid  pause  updateBudget  ...               │
│  ┌─────────┐   ┌─────────┐   ┌─────────┐   ┌─────────┐                         │
│  │GoogleImpl│  │ MetaImpl│   │TikTokImpl│  │ DV360Impl│                        │
│  └─────────┘   └─────────┘   └─────────┘   └─────────┘                         │
│  ┌──────────┐  ┌─────────┐   ┌──────────┐  ┌─────────┐                        │
│  │错误归一化 │  │限流归一化│   │速率控制器 │  │重试策略  │                        │
│  └──────────┘  └─────────┘   └──────────┘  └─────────┘                        │
└────────────────────────┬───────��───────────────────────────────────────────────┘
                         │
┌────────────────────────▼───────────────────────────────────────────────────────┐
│                      通用 Agent（跨平台）                                        │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌──────────┐  │
│  │ 数据 Agent │  │ 创意 Agent │  │ 归因 Agent │  │ 风控 Agent │  │ 报表 Agent│  │
│  └────────────┘  └────────────┘  └────────────┘  └────────────┘  └──────────┘  │
└────────────────────────┬───────────────────────────────────────────────────────┘
                         │
┌────────────────────────▼───────────────────────────────────────────────────────┐
│                        记忆与基础设施                                             │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌──────────┐  │
│  │ 关系库(状态) │  │ Redis(缓存) │  │ 向量库(Embed)│ │ 事件流(Kafka)│  │对象存储   │  │
│  └────────────┘  └────────────┘  └────────────┘  └────────────┘  └──────────┘  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

这个架构的核心思想是**「编排者不碰平台细节，平台 Agent 不碰全局，通用 Agent 专注横切能力」**。分层使得系统可以水平扩展、灰度替换某个平台实现、单独加一个新的平台 Agent。

### 1.4 编排层级结构：Orchestrator / Supervisor / Worker

编排不是「一个傻循环」，而是有清晰角色的层级结构。我们用三层模型描述：

```
第 0 层  用户/业务目标          User Goal
第 1 层  Orchestrator          总编排器（唯一的入口，负责任务分解与全局决策）
第 2 层  Supervisor / Agent    平台 Agent（Google/Meta/TikTok/DV360）+ 通用 Agent
第 3 层  Worker / Skill        技能执行单元（实际调用平台 API 的原子动作）
```

每个层级只信任相邻层级，消息在层级间流转，不允许 Agent 跨层直接调用另一个 Agent 的底层 API。

#### Orchestrator 的职责清单

| 职责 | 说明 | 典型动作 |
|------|------|----------|
| 目标理解 | 把自然语言目标转成结构化指令 | 「ROAS>3 放量 30%」→ JSON 目标对象 |
| 任务分解 | 把大目标拆成平台级子任务 | 分解成 Google 放量、Meta 调 CPA、TikTok 扩素材 |
| 平台路由 | 决定哪个子任务发给哪个 Agent | Google 子任务 → GoogleAgent |
| 调度 | 安排执行顺序、并行或串行 | 先做数据汇总，再并行派平台任务 |
| 冲突仲裁 | 处理多 Agent 的冲突请求（如都想要预算） | 预算仲裁器分配预算 |
| 结果聚合 | 汇总各 Agent 结果做全局判断 | 汇总各平台 ROAS 判断是否达标 |
| 反思 | 对一轮循环做复盘，输出经验 | 生成 reflection 记忆 |
| 人机协作 | 需要人工确认时暂停等待 | 大额预算调整触发审批 |

#### Supervisor 模式（插槽式管理）

在 Supervised 架构中，Orchestrator 作为 Supervisor，维护一组 Agent「槽位」：

```yaml
supervisor:
  name: ad-orchestrator
  agents:
    - slot: google
      agent: GoogleAgent
      capacity: 1
      handlers: [campaign, bidding, keyword]
    - slot: meta
      agent: MetaAgent
      capacity: 1
    - slot: tiktok
      agent: TikTokAgent
      capacity: 1
    - slot: dv360
      agent: DV360Agent
      capacity: 1
    - slot: data
      agent: DataAgent
      capacity: 2
    - slot: creative
      agent: CreativeAgent
      capacity: 2
    - slot: attribution
      agent: AttributionAgent
      capacity: 1
    - slot: risk
      agent: RiskAgent
      capacity: 1
  routing:
    mode: intent-based       # 基于意图路由
    fallback: role-based     # 兜底基于角色
  conflict:
    arbiter: budget-arbiter  # 预算仲裁器
    lock: distributed-lock   # 分布式锁
```

`capacity` 表示该 Agent 类型���多可并发多少个实例，防止资源被少量任务打爆。

### 1.5 Agent 拓扑模型：Hierarchical vs Peer-to-Peer

Agent 系统有两种基本拓扑，也可以混合使用。我们系统地对比：

| 维度 | Hierarchical（层级式） | Peer-to-Peer（对等式） |
|------|------------------------|------------------------|
| 控制流 | 上层 Orchestrator 下发命令给下层 Agent | 各 Agent 互相直接通信、协商 |
| 依赖 | 强，Agent 依赖 Orchestrator 决策 | 弱，Agent 可独立决策 |
| 扩展性 | 加 Agent 需要一个编排逻辑 | 加 Agent 只需接入协议 |
| 故障影响 | Orchestrator 挂了全停 | 单点故障影响小 |
| 冲突处理 | 集中仲裁，不容易冲突 | 容易多 Agent 互相打架 |
| 调试 | 好，链路清晰 | 难，消息杂乱 |
| 适用场景 | 预算全局分配、跨平台协同 | 局部自治、快速试错 |
| 广告场景建议 | ✅ 主架构 | 部分自治任务（如创意轮换） |

```ascii
Hierarchical（推荐主架构）             Peer-to-Peer（局部使用）
                                  ┌─────────┐
        ┌──────────┐               │ Agent A │◄───┐
        │Orchestrator│             └────┬────┘    │
        └─��───┬────┘                 ▲  │        │
   ┌──────────┼──────────┐           │  ▼        │
   ▼          ▼         ▼       ┌─────────┐     │
┌─────┐   ┌─────┐   ┌─────┐     │ Agent B │◄────┘
│ G/M │   │ T/D │   │Data │     └─────────┘
└─────┘   └─────┘   └─────┘
```

**在广告系统中我们采用「Hierarchical 为主 + P2P 为辅」的混合模型**：
- 跨平台预算分配、全局 ROAS 判断 → **层级式**，由 Orchestrator 统一决策，避免各平台 Agent 各自抢预算。
- 单个平台内部的创意轮换、素材 A/B 测试到期切换 → **对等式**，让 CreativeAgent 与平台 Agent 直接协商，减少 Orchestrator 的转发瓶颈。

### 1.6 任务分解（Task Decomposition）

任务分解是把「用户目标」递归变成「可执行任务树」的过程。我们用一个真实例子：

**用户目标**：`“在新产品发布的 4 周内，全渠道（4 平台）合计 ROAS ≥ 3，总预算 $100k，并控制单平台日花费波动 ≤ 20%。”

第 1 步：Orchestrator 把目标转成结构化目标对象：

```json
{
  "goal_id": "g_20260814_001",
  "objective": "product_launch",
  "horizon": {"start": "2026-08-14", "end": "2026-09-10"},
  "constraints": {
    "total_budget_usd": 100000,
    "min_roas": 3.0,
    "daily_spend_drift_max": 0.20
  },
  "platforms": ["google", "meta", "tiktok", "dv360"]
}
```

第 2 步：递归任务分解（生成任务树）：

```
g_20260814_001 (产品发布全渠道放量)
├── t1 预算分配子任务
│   ├── t1.1 基于历史 ROAS 给出初始预算分割 (DataAgent)
│   └── t1.2 预算仲裁与确认 (Orchestrator)
├── t2 Google 平台子任务
│   ├── t2.1 新建/复用产品 Campaign (GoogleAgent)
│   ├── t2.2 设置出价策略 (GoogleAgent)
│   └── t2.3 关键词规划与否定 (GoogleAgent)
├── t3 Meta 平台子任务
│   ├── t3.1 创建 AdSet 并设置受众 (MetaAgent)
│   ├── t3.2 创意接入与轮换 (CreativeAgent + MetaAgent)
│   └── t3.3 CAPI 转化事件配置 (MetaAgent)
├── t4 TikTok 平台子任务
│   ├── t4.1 创建 Campaign + AdGroup (TikTokAgent)
│   └── t4.2 Spark Ads / 达人口播素材 (CreativeAgent)
├── t5 DV360 平台子任务
│   ├── t5.1 创建 Insertion Order / Line Item (DV360Agent)
│   └── t5.2 频控与像素配置 (DV360Agent)
├── t6 归因与追踪
│   ├── t6.1 统一归因模型 (AttributionAgent)
│   └── t6.2 转化回传校验 (AttributionAgent + 各平台Agent)
└── t7 风控与合规
    └── t7.1 预算超支检测 (RiskAgent)
```

第 3 步：把任务树编码为 DAG，标注依赖与并行性：

```python
# tasks_dag.py —— 任务树的 DAG 表示
tasks = [
    Task("t1.1", "预算分割", depends=[], agent="data"),
    Task("t1.2", "预算确认", depends=["t1.1"], agent="orchestrator"),
    Task("t2.1", "Google 建 Campaign", depends=["t1.2"], agent="google"),
    Task("t3.1", "Meta 建 AdSet", depends=["t1.2"], agent="meta"),
    Task("t4.1", "TikTok 建 Campaign", depends=["t1.2"], agent="tiktok"),
    Task("t5.1", "DV360 建 IO/LineItem", depends=["t1.2"], agent="dv360"),
    # t2.1 / t3.1 / t4.1 / t5.1 之间互不依赖 → 可并行
]
```

**分解原则**：
1. **单一职责**：每个任务只改一个平台、一类对象，便于回滚与审计。
2. **最小权限**：任务之间不共享写权限，降低冲突。
3. **可观测**：每个任务都带 goal_id、trace_id，可追溯。
4. **可回滚**：每个任务都能被暂停/撤销（对应平台 pause 操作）。

### 1.7 消息路由与协议

各 Agent 之间、Agent 与 Orchestrator 之间通过**统一的 Agent 消息协议**通信。我们定义消息的结构化格式（信封 + 载荷）：

```json
{
  "schema_version": "1.0",
  "message_id": "msg_8f2c9a1b",
  "trace_id": "trace_20260814_abc",
  "goal_id": "g_20260814_001",
  "src": "orchestrator",
  "dst": "google_agent",
  "type": "task.assign",
  "correlation_id": "t2.1",
  "timestamp": "2026-08-14T09:00:00Z",
  "payload": {
    "task_id": "t2.1",
    "action": "create_campaign",
    "args": {
      "platform": "google",
      "customer_id": "1234567890",
      "name": "new-product-launch",
      "budget_micros": 12500000
    }
  },
  "meta": {
    "priority": 10,
    "idempotency_key": "create_camp_g_001_t2.1_retry1"
  }
}
```

#### 消息类型表

| type | 方向 | 用途 | 示例 |
|------|------|------|------|
| `task.assign` | Orchestrator → Agent | 派发任务 | 让 MetaAgent 降低 CPA |
| `task.ack` | Agent → Orchestrator | 确认收到 | 返回待办 |
| `task.progress` | Agent → Orchestrator | 汇报进度 | 已完成 30% |
| `task.result` | Agent → Orchestrator | 返回结果 | 返回新 Campaign id |
| `task.result.failure` | Agent → Orchestrator | 失败 + 原因 | 平台限流 |
| `query.request` | 任意 → 数据 Agent | 查数据 | 查各平台昨晚 ROAS |
| `query.response` | 数据 Agent → 调用方 | 返回数据 | ROAS 列表 |
| `memory.write` | Agent → 记忆 Hub | 写记忆 | 记录一次调价 |
| `memory.read` | Agent → 记忆 Hub | 读记忆 | 拉取历史经验 |
| `conflict.request` | Agent → Orchestrator | 申请资源 | 申请 +$5k 预算 |
| `conflict.granted/denied` | Orchestrator → Agent | 仲裁结果 | 拒绝 |
| `event.notify` | 任意 → 事件总线 | 领域事件 | campaign.paused |
| `barrier.wait/entered` | Orchestrator/Agent | 同步 | 等两个平台都写好再归因 |

#### 消息路由策略

```python
# router.py —— 基于 intent + role 的混合路由
class Router:
    def route(self, msg):
        dst = msg["dst"]
        if dst == "orchestrator":
            return self.supervisor_handle(msg)
        # 平台路由：基于 payload.action ���平台字段
        platform = msg["payload"]["action"].get("platform")
        return self.agent_map[platform + "_agent"].deliver(msg)
```

路由的权衡：**集中式路由（经 Orchestrator 转发）** vs **直连地址（P2P）**。为兼顾可控性与低延迟，我们采用「默认经 Orchestrator，白名单直连」策略——如创意素材协同可直连，预算类消息必须经仲裁。

### 1.8 协调模式：同步 / 异步 / 事件驱动

#### 1.8.1 同步协调（Sync）

用于强一致的场景：B 必须等 A 完成后才能开始。例如归因必须先等所有平台的转化事件都回传完。

```python
# async 风格的同步等待（用信号量实现汇合）
async def orchestrate_post_launch():
    # 并行派发 4 个建站任务
    results = await asyncio.gather(
        google_agent.create_campaign(...),
        meta_agent.create_adset(...),
        tiktok_agent.create_campaign(...),
        dv360_agent.create_line_item(...),
    )
    # 等全部完成后，才进行归因配置
    await attribution_agent.configure(results)
```

#### 1.8.2 异步协调（Async）

用于可解耦、最终一致的场景：数据同步不阻塞决策；事件通知不阻塞主流程。

```python
# 异步：把「报表拉取」放进后台，不阻塞派发任务
async def run():
    report_task = asyncio.create_task(data_agent.pull_all_reports())
    campaign_task = asyncio.create_task(google_agent.create_campaign(...))
    await campaign_task        # 先关心建站
    report = await report_task # 稍后取报表
```

#### 1.8.3 事件驱动协调（Event-driven）

用事件总线解耦「动作」和「反应」。例如当某个平台检测到 CPA 飙升，该 Agent 发出 `metric.cpa-spike` 事件，Orchestrator 或 RiskAgent 订阅后采取行动。

```python
# event_bus.py —— 轻量事件总线
from dataclasses import dataclass
import asyncio

class EventBus:
    def __init__(self):
        self.subscribers = {}

    def subscribe(self, event_type, handler):
        self.subscribers.setdefault(event_type, []).append(handler)

    async def publish(self, event):
        for handler in self.subscribers.get(event["type"], []):
            asyncio.create_task(handler(event))
```

```python
# 使用
bus = EventBus()
bus.subscribe("metric.cpa-spike", risk_agent.assess)
bus.subscribe("campaign.paused", orchestrator.rebalance_budget)
await bus.publish({"type": "metric.cpa-spike", "payload": {...}})
```

#### 1.8.4 协调模式选择矩阵

| 场景 | 建议模式 | 原因 |
|------|----------|------|
| 建站（前后依赖） | 同步 | 需要拿到 id 才能继续 |
| 各平台独立放量 | 异步并行 | 互不依赖，可并行 |
| 预算变更通知 | 事件驱动 | 解耦，低延迟反应 |
| 数据同步 | 异步 + 事件 | 最终一致即可 |
| 归因计算 | 同步汇合 | 需要所有平台数据到齐 |
| 风控拦截 | 事件驱动 + 同步审计 | 需要及时但也要留痕 |

---

## 二、深度原理解析

### 2.1 平台抽象层设计理念

平台抽象层是整个系统的「翻译官」。它的目标：

1. **统一接口**：让所有上层 Agent 只面向一套接口，不感知平台差异。
2. **归一化异常**：把各家不同的错误码、限流语义统一成可控的异常语法。
3. **归一化速率**：把各家不同的配额/限流策略统一成一套速率控制算法。
4. **可插拔**：新增一个平台 = 新增一个实现 + 注册表登记，不改上层代码。

设计原则遵循 **Ports & Adapters（六边形架构）**：
- **Port（端口）**：系统内部定义的接口契约，属于「系统侧」。
- **Adapter（适配器）**：对接外部平台的具体实现，属于「外部侧」。

```
      内部领域（Agent 层）
            │
            ▼
   ��────────────────┐
   │  PlatformPort   │ ← 内部接口（Port）
   └───────┬────────┘
           │
    ┌──────┼──────┬──────┐
    ▼      ▼      ▼      ▼
 [Google] [Meta] [TikTok][DV360]   ← 适配器（Adapters）对接外部世界
```

### 2.2 统一的接口契约（Contract）

我们先定义「领域模型」——所有平台统一之后的通用实体。这些实体是接口参数/返回值的骨架：

#### 统一 Campaign 模型

```python
@dataclass
class UnifiedCampaign:
    platform: str                 # google / meta / tiktok / dv360
    platform_id: str              # 平台侧 id
    name: str
    status: str                   # normalized: ENABLED/PAUSED/REMOVED/ARCHIVED
    channel_type: str             # SEARCH/DISPLAY/VIDEO/SHOPPING...
    objective: str                # normalized objective
    daily_budget_micros: int      # 统一用 micros（1 usd = 1_000_000 micros）
    total_budget_micros: int
    currency: str
    start_date: str
    end_date: str
    bidding_strategy: dict        # normalized
    targeting: dict               # normalized
    created_at: str
    updated_at: str
```

> **关键设计决策：金额统一用 micros（微单位）**。Google 用 micros、TikTok 用分、Meta 用分/美元、DV360 用美元。若不做归一化，跨平台对比预算时极易算错（差 100 倍 / 1000000 倍）。所有内部接口一律使用 micros，仅在与平台 SDK 交互的边缘做换算。

#### 统一报表模型

```python
@dataclass
class UnifiedMetrics:
    date: str
    platform: str
    campaign_id: str
    impressions: int
    clicks: int
    spend_micros: int
    conversions: int
    cvr: float                # conversions / clicks
    ctr: float
    cpc_micros: int           # spend / clicks
    cpa_micros: int           # spend / conversions
    roas: float               # revenue / spend
    revenue_micros: int
```

#### 统一错误模型

```python
@dataclass
class PlatformError(Exception):
    platform: str
    kind: str        # normalized: AUTH/RATE_LIMIT/RESOURCE_NOT_FOUND/INVALID_ARG/CONFLICT/INTERNAL/TIMEOUT
    code: str        # 平台原始错误码（保留用于排查）
    retryable: bool
    retry_after: int # 秒
    message: str
```

### 2.3 Go Interface 定义

Go 是广告后端的主力语言（高并发、多平台 API 调用天然适合）。我们用 Go interface 定义 PlatformPort。

```go
// platform_port.go —— 统一的平台端口接口
package platform

import "context"

// Money 统一金额（用 micros 表达，1 USD = 1_000_000 micros）
type Money struct {
    Micros int64
    Currency string
}

// Campaign 统一 Campaign 模型
type Campaign struct {
    Platform   string
    PlatformID string
    Name       string
    Status     string // ENABLED / PAUSED / REMOVED / ARCHIVED
    Channel    string
    Objective  string
    DailyBudget Money
    TotalBudget  Money
    StartDate  string
    EndDate    string
    Bidding    map[string]string
    Targeting  map[string]interface{}
}

// Metrics 统一报表指标
type Metrics struct {
    Date         string
    Platform     string
    CampaignID   string
    Impressions  int64
    Clicks       int64
    Spend        Money
    Conversions  float64
    CVR          float64
    CTR          float64
    CPC          Money
    CPA          Money
    ROAS         float64
    Revenue      Money
}

// Query 报表查询
type Query struct {
    AccountIDs []string
    StartDate  string
    EndDate    string
    Level      string // CAMPAIGN/ADGROUP/AD
    Fields     []string
}

// PlatformPort —— 平台抽象端口（内部契约）
type PlatformPort interface {
    // ─── 账户 ───
    ListAccounts(ctx context.Context) ([]map[string]interface{}, error)
    GetAccount(ctx context.Context, accountID string) (map[string]interface{}, error)

    // ─── Campaign ───
    CreateCampaign(ctx context.Context, c *Campaign) (string, error)
    GetCampaign(ctx context.Context, campaignID string) (*Campaign, error)
    UpdateCampaign(ctx context.Context, campaignID string, patch map[string]interface{}) (*Campaign, error)
    PauseCampaign(ctx context.Context, campaignID string) error
    ResumeCampaign(ctx context.Context, campaignID string) error
    DeleteCampaign(ctx context.Context, campaignID string) error

    // ─── 出价与预算 ───
    UpdateBid(ctx context.Context, campaignID string, bidMicros int64, opts ...Option) error
    UpdateBudget(ctx context.Context, campaignID string, dailyBudgetMicros int64) error

    // ─── 报表 ───
    GetReport(ctx context.Context, q Query) ([]Metrics, error)

    // ─── 创意 ───
    ListCreatives(ctx context.Context, parentID string) ([]map[string]interface{}, error)
    UploadCreative(ctx context.Context, parentID string, asset interface{}) (string, error)

    // ─── 归因事件 ───
    TrackEvent(ctx context.Context, pixelID string, evt map[string]interface{}) error

    // ─── 能力探测 ——
    Capabilities() PlatformCapabilities
}

// PlatformCapabilities 描述该平台实现支持的能力（可选特性探测）
type PlatformCapabilities struct {
    SupportsBudgetUpdate bool
    SupportsMicroBid     bool
    SupportsCAPI         bool
    MaxBatchSize         int
    RateLimitPerMinute   int
}
```

**注意**：接口里的 `[]map[string]interface{}` 用于放平台专属的、无法统一的高阶字段（例如 Meta 的 custom_audience spec、Google 的 GAQL query），保证「统一 + 可扩展」兼顾。

配套的 Option 模式（函数式选项）：

```go
// options.go
type Option func(*callOptions)

type callOptions struct {
    IdempotencyKey string
    AccountID      string
    Timeout        time.Duration
    Retry          bool
}

func WithIdempotencyKey(k string) Option {
    return func(o *callOptions) { o.IdempotencyKey = k }
}
func WithAccountID(id string) Option {
    return func(o *callOptions) { o.AccountID = id }
}
```

### 2.4 Python ABC 定义

Python 侧（Skill/Agent 层常用）用 `abc.ABC` 定义同样的契约，便于与知识库现有脚本 `ad_platform_api.py` 对接。

```python
# platform_port.py —— Python 抽象基类（ABC）
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any

MICROS_PER_UNIT = 1_000_000  # 1 USD = 1e6 micros

@dataclass
class UnifiedCampaign:
    platform: str
    platform_id: str = ""
    name: str = ""
    status: str = "UNKNOWN"
    channel: str = ""
    objective: str = ""
    daily_budget_micros: int = 0
    total_budget_micros: int = 0
    currency: str = "USD"
    start_date: str = ""
    end_date: str = ""
    bidding: Dict[str, Any] = field(default_factory=dict)
    targeting: Dict[str, Any] = field(default_factory=dict)

    @property
    def daily_budget_usd(self) -> float:
        return self.daily_budget_micros / MICROS_PER_UNIT

@dataclass
class UnifiedMetrics:
    date: str = ""
    platform: str = ""
    campaign_id: str = ""
    impressions: int = 0
    clicks: int = 0
    spend_micros: int = 0
    conversions: float = 0.0
    cvr: float = 0.0
    ctr: float = 0.0
    cpc_micros: int = 0
    cpa_micros: int = 0
    roas: float = 0.0
    revenue_micros: int = 0

class PlatformError(Exception):
    """归一化的平台错误"""
    PLATFORM = "unknown"
    KINDS = {"AUTH", "RATE_LIMIT", "RESOURCE_NOT_FOUND", "INVALID_ARG",
             "CONFLICT", "INTERNAL", "TIMEOUT"}

    def __init__(self, kind: str, code: str = "", message: str = "",
                 retryable: bool = False, retry_after: int = 0):
        super().__init__(f"[{self.PLATFORM}:{kind}] {message}")
        self.kind = kind
        self.code = code
        self.retryable = retryable
        self.retry_after = retry_after

class PlatformPort(ABC):
    """平台抽象端口——所有平台实现必须遵循的契约"""

    platform: str = "unknown"

    # 账户
    @abstractmethod
    def list_accounts(self) -> List[Dict[str, Any]]: ...
    @abstractmethod
    def get_account(self, account_id: str) -> Dict[str, Any]: ...

    # Campaign
    @abstractmethod
    def create_campaign(self, campaign: UnifiedCampaign) -> str: ...
    @abstractmethod
    def get_campaign(self, campaign_id: str) -> UnifiedCampaign: ...
    @abstractmethod
    def update_campaign(self, campaign_id: str, patch: Dict[str, Any]) -> UnifiedCampaign: ...
    @abstractmethod
    def pause_campaign(self, campaign_id: str) -> None: ...
    @abstractmethod
    def resume_campaign(self, campaign_id: str) -> None: ...

    # 出价与预算
    @abstractmethod
    def update_bid(self, campaign_id: str, bid_micros: int, **opts) -> None: ...
    @abstractmethod
    def update_budget(self, campaign_id: str, daily_budget_micros: int, **opts) -> None: ...

    # 报表
    @abstractmethod
    def get_report(self, query: Dict[str, Any]) -> List[UnifiedMetrics]: ...

    # 创意
    @abstractmethod
    def list_creatives(self, parent_id: str) -> List[Dict[str, Any]]: ...
    @abstractmethod
    def upload_creative(self, parent_id: str, asset: Dict[str, Any]) -> str: ...

    # 事件
    @abstractmethod
    def track_event(self, pixel_id: str, event: Dict[str, Any]) -> None: ...

    def capabilities(self) -> Dict[str, Any]:
        return {"supports_budget_update": True, "supports_micro_bid": True}
```

### 2.5 各平台实现策略

我们对四个平台一一讲解如何实现 `PlatformPort`。核心原则是：**实现里才写平台专属代码，把差异性尽量隔离在适配器内部。**

#### 2.5.1 GoogleAdsImpl —— 基于 gRPC + proto + GAQL

Google Ads API 是基于 gRPC 的，使用 GAQL（Google Ads Query Language）查询，金额单位为 micros，customer/ID 体系。

```python
# impl_google.py
class GoogleAdsImpl(PlatformPort):
    platform = "google"

    def __init__(self, google_client):
        self.client = google_client          # google.ads.googleads.client.GoogleAdsClient
        self.customer_id = None              # 通过 list_accounts 选择

    def list_accounts(self):
        svc = self.client.get_service("CustomerService")
        resp = svc.list_accessible_customers()
        return [{"id": rn.split("/")[-1], "resource_name": rn}
                for rn in resp.resource_names]

    def create_campaign(self, campaign: UnifiedCampaign) -> str:
        svc = self.client.get_service("CampaignService")
        op = self.client.get_type("CampaignOperation")
        c = op.create
        c.resource_name = f"customers/{self.customer_id}/campaigns/-"
        c.name = campaign.name
        c.advertising_channel_type = self._map_channel(campaign.channel)
        c.status = self.client.enums.CampaignStatusEnum.PAUSED
        # 预算：Google 用 Budget resource
        budget_op = self.client.get_type("CampaignBudgetOperation")
        budget_op.create.name = f"{campaign.name}-budget"
        budget_op.create.amount_micros = campaign.daily_budget_micros
        budget_op.create.delivery_method = (self.client.enums.BudgetDeliveryMethodEnum.STANDARD)
        c.campaign_budget = budget_op.create.resource_name
        resp = svc.mutate_campaigns(customer_id=self.customer_id, operations=[op],
                                    partial_failure=True)
        return resp.results[0].resource_name.split("/")[-1]

    def get_report(self, query):
        # 用 GAQL 查询，归一化为 UnifiedMetrics
        gaql = f"""
            SELECT campaign.id, metrics.impressions, metrics.clicks,
                   metrics.cost_micros, metrics.conversions, metrics.ctr
            FROM campaign
            WHERE segments.date BETWEEN '{query['start_date']}' AND '{query['end_date']}'
        """
        svc = self.client.get_service("GoogleAdsService")
        out = []
        for batch in svc.search_stream(customer_id=self.customer_id, query=gaql):
            for row in batch.results:
                m = UnifiedMetrics()
                m.platform = "google"
                m.campaign_id = str(row.campaign.id)
                m.impressions = row.metrics.impressions
                m.clicks = row.metrics.clicks
                m.spend_micros = row.metrics.cost_micros
                m.conversions = row.metrics.conversions
                m.ctr = row.metrics.ctr
                out.append(m)
        return out
```

**Google 实现要点**：
- ID 换算：resource_name 形如 `customers/123/campaigns/456`，取最后一段。
- 预算与 Campaign 分离（CampaignBudget 资源），建 Campaign 前要先建预算。
- 金额天然 micros，无需换算。
- 部分失败用 `partial_failure` + 错误码解析。
- OAuth2 refresh token 过期需刷新。

#### 2.5.2 MetaImpl —— 基于 Python SDK / Graph API REST

Meta Marketing API 是 REST + Graph，层级 Campaign→AdSet→Ad，账户带 `act_` 前缀，金额单位分/美元（取决于 currency）。

```python
# impl_meta.py
class MetaImpl(PlatformPort):
    platform = "meta"

    def __init__(self, facebook_api):
        from facebook_business.adobjects.campaign import Campaign
        from facebook_business.adobjects.adset import AdSet
        from facebook_business.adaccounts import AdAccount
        self.Campaign, self.AdSet, self.AdAccount = Campaign, AdSet, AdAccount

    def create_campaign(self, campaign: UnifiedCampaign) -> str:
        account = self.AdAccount(f"act_{self.account_id}")
        c = account.create_campaign(
            name=campaign.name,
            objective=self._map_objective(campaign.objective),
            status=self.Campaign.Status.paused,   # 先建再启，防误投
            special_ad_categories=[],
        )
        return c["id"]

    def update_budget(self, campaign_id: str, daily_budget_micros: int, **opts):
        # Meta 预算以「分」为单位，micros → 分
        cents = daily_budget_micros // 10_000  # 1 cent = 10_000 micros
        self._save_field(campaign_id, "daily_budget", cents)

    def get_report(self, query):
        from facebook_business.adinsights import AdInsights
        params = {
            "level": query.get("level", "campaign"),
            "date_preset": "last_7d",
            "fields": ["campaign_id", "impressions", "clicks", "spend",
                       "conversions", "ctr"],
        }
        ins = AdInsights.get_insights(
            accounts=[self.AdAccount(f"act_{self.account_id}")], params=params)
        out = []
        for i in ins:
            m = UnifiedMetrics()
            m.platform = "meta"
            m.campaign_id = i["campaign_id"]
            m.impressions = int(i.get("impressions", 0))
            m.clicks = int(i.get("clicks", 0))
            m.spend_micros = int(float(i.get("spend", 0)) * MICROS_PER_UNIT)
            out.append(m)
        return out
```

**Meta 实现要点**：
- 层级：Campaign → AdSet → Ad；AdSet 承载预算与定向。
- 金额：Graph 返回的 spend 是美元字符串，`spend*1e6` 得 micros；写入时 `micros//1e4` 得分。
- 账户 id 需要 `act_` 前缀。
- 长期 access_token；注意 token 权限范围（ads_management / ads_read）。
- 使用 `debug` 参数可见 API 全程。

#### 2.5.3 TikTokImpl —— 基于 REST + signature

TikTok Business API 是 REST，使用 `Access-Token` header，金额单位「分」（cents），层级 Campaign→AdGroup→Ad。

```python
# impl_tiktok.py
class TikTokImpl(PlatformPort):
    platform = "tiktok"
    BASE = "https://business-api.tiktok.com/open_api/v1.3"

    def __init__(self, token: str, app_id: str, secret: str):
        self.token, self.app_id, self.secret = token, app_id, secret

    def _hdrs(self):
        return {"Access-Token": self.token, "Content-Type": "application/json"}

    def create_campaign(self, campaign: UnifiedCampaign) -> str:
        import requests
        body = {
            "advertiser_id": self.account_id,
            "campaign_name": campaign.name,
            "objective_type": self._map_objective(campaign.objective),
            "budget_mode": "BUDGET_MODE_DAY",
            "budget": campaign.daily_budget_micros // 100_000,  # micros→分(=元小单位) 近似
            "status": "PAUSED",
        }
        resp = requests.post(f"{self.BASE}/campaign/create/",
                             headers=self._hdrs(), json=body, timeout=30)
        data = resp.json().get("data", {})
        if resp.status_code != 200 or data.get("code") != 0:
            raise self._raise(resp)
        return data["campaign_ids"][0]

    def get_report(self, query):
        import requests
        resp = requests.get(f"{self.BASE}/report/get/", headers=self._hdrs(),
                            params={...}, timeout=30)
        ...
```

**TikTok 实现要点**：
- Access-Token 在 header，且部分接口需要 timestamp + signature（老版本 portal 端点）。
- 金额单位是「分」（TikTok 的 currency 小单位），与 Google micros 不同，需换算。
- 响应统一 `{"code":0,"message":"OK","data":{...}}`；业务失败在 HTTP 200 内用 code 表达——**必须在实现里对 `code != 0` 抛错**。
- 版本号：open_api/v1.3；老 portal 端点为 `v20230728`。

#### 2.5.4 DV360Impl —— 基于 Discovery API + Service Account

DV360（Display & Video 360）用 google-api-python-client 的 `displayvideo` discovery，鉴权是 Service Account + JWT。层级是 Partner→Advertiser→Campaign→Insertion Order→Line Item。

```python
# impl_dv360.py
import google.auth
from googleapiclient.discovery import build

class DV360Impl(PlatformPort):
    platform = "dv360"

    def __init__(self, sa_file: str):
        from google.oauth2 import service_account
        creds = service_account.Credentials.from_service_account_file(
            sa_file, scopes=["https://www.googleapis.com/auth/display-video"])
        self.svc = build("displayvideo", "v1", credentials=creds)

    def list_creatives(self, advertiser_id: str):
        req = self.svc.advertisers().creatives().list(
            advertiserId=advertiser_id, pageSize=50)
        page = req.execute()
        return page.get("creatives", [])

    def create_campaign(self, campaign: UnifiedCampaign) -> str:
        # DV360 建 Campaign 需要 partner/advertiser 上下文
        body = {"displayName": campaign.name, "campaignGoal": {...}}
        req = self.svc.advertisers().campaigns().create(
            advertiserId=owning_advertiser_id, body=body)
        resp = req.execute()
        return resp["campaignId"]
```

**DV360 实现要点**：
- Service Account JWT 刷新由 discovery 层处理（Google SDK 自动刷新）。
- 金额用美元（部分场景 micros），注意换算。
- 层级更深（IO / Line Item），���口方法体��较大。
- DV360 的审核/审批规则更严格，改预算常有 Flighting 限制。
- 报表通过 `query` 资源异步产出，需要轮询（POLL），与即时报表不同。

#### 2.5.5 平台实现对照表

| 维度 | Google | Meta | TikTok | DV360 |
|------|--------|------|--------|-------|
| 传输协议 | gRPC/proto | REST(Graph) | REST | REST(discovery) |
| 鉴权 | OAuth2 refresh | 长期 access_token | Access-Token header | Service Account JWT |
| 金额单位 | micros | 分/美元 | 分 | 美元 |
| Campaign 层级 | Campaign→AdGroup→Ad | Campaign→AdSet→Ad | Campaign→AdGroup→Ad | Partner→Adv→Camp→IO→LI |
| 预算承载 | CampaignBudget(campaign) | AdSet | Campaign/AdGroup | IO/Line Item |
| 报表方式 | GAQL search | Insights | report/get | async query+POLL |
| 失败语义 | cartesian error(codes) | Graph error(error object) | {code,message} 200内 | Google-style errors |
| 限流特征 | 按 developer token quota | 按 app 速率 | 按 advertiser 配额 | 按 API 速率 |

### 2.6 错误 / 限流 / 速率归一化

不同平台的错误与限流语义差异巨大，如果不归一化，上层每个 Skill 都要写 `try ... except GoogleQuotaExceeded / MetaRateError / ...` 一堆分支。我们做三层归一化。

#### 2.6.1 错误归一化

每个平台实现把「平台原始错误」翻译成 `PlatformError`：

```python
# errors.py —— 错误归一化工具
def normalize_error(platform: str, exc: Exception) -> PlatformError:
    e = PlatformError("INTERNAL", message=str(exc))
    e.PLATFORM = platform
    if platform == "google":
        from google.api_core.exceptions import PermissionDenied, ResourceExhausted, NotFound
        if isinstance(exc, ResourceExhausted):
            e.kind, e.retryable, e.retry_after = "RATE_LIMIT", True, 60
        elif isinstance(exc, NotFound):
            e.kind = "RESOURCE_NOT_FOUND"
        elif isinstance(exc, PermissionDenied):
            e.kind = "AUTH"
    elif platform == "meta":
        # Graph 错误形如 (Type, code, message)
        code = getattr(exc, "code", None)
        if code == 17 or code == 32:      # reach limit / page rate
            e.kind, e.retryable = "RATE_LIMIT", True
        elif code == 100:                 # invalid parameter
            e.kind = "INVALID_ARG"
        elif code == 200:                 # permission
            e.kind = "AUTH"
    elif platform == "tiktok":
        # TikTok 业务错误在 resp code，非异常
        ...
    e.code = getattr(exc, "code", "")
    return e
```

#### 2.6.2 限流归一化

每平台有独立的限流语义，我们用「每平台一个速率控制器」把配额转换成标准令牌桶：

```python
# rate_limiter.py —— 令牌桶限流器
import threading
import time

class TokenBucket:
    def __init__(self, rate_per_min: float, burst: int = 10):
        self.rate = rate_per_min / 60.0      # 每秒令牌
        self.burst = burst
        self.tokens = float(burst)
        self.updated = time.monotonic()
        self.lock = threading.Lock()

    def acquire(self):
        with self.lock:
            now = time.monotonic()
            self.tokens = min(self.burst,
                              self.tokens + (now - self.updated) * self.rate)
            self.updated = now
            if self.tokens < 1:
                wait = (1 - self.tokens) / self.rate
                self.lock.release()
                time.sleep(wait)
                self.lock.acquire()
                self.tokens -= 1
                return True
            self.tokens -= 1
            return True

# 每平台配额表（示例值，以实际开通配额为准）
RATE_LIMITS = {
    "google": {"rpm": 2500, "burst": 100},
    "meta":   {"rpm": 600,  "burst": 50},
    "tiktok": {"rpm": 1200, "burst": 60},
    "dv360":  {"rpm": 300,  "burst": 30},
}

_limiter = {}
def limiter_for(platform: str) -> TokenBucket:
    if platform not in _limiter:
        cfg = RATE_LIMITS[platform]
        _limiter[platform] = TokenBucket(cfg["rpm"], cfg["burst"])
    return _limiter[platform]
```

#### 2.6.3 重试与退避策略

统一的重试封装，遵循「平台 retryable + 指数退避 + 抖动 + 上限」：

```python
# retry.py —— 指数退避重试
import random
import time

def with_retry(fn, platform: str, attempts: int = 4):
    for i in range(attempts):
        try:
            limiter_for(platform).acquire()
            return fn()
        except PlatformError as e:
            if not e.retryable or i == attempts - 1:
                raise
            base = min(2 ** i * 2, 120)          # 指数退避
            jitter = random.uniform(0, base * 0.3)
            time.sleep(base + jitter)
    raise RuntimeError("unreachable")
```

#### 2.6.4 幂等性

平台操作必须可重试，重试不能造成重复创建。为此引入「幂等键」：

```python
# idempotency.py
import hashlib, json

def make_idem_key(goal_id, task_id, action, args, attempt):
    raw = json.dumps({"g": goal_id, "t": task_id, "a": action,
                      "args": args, "n": attempt}, sort_keys=True)
    return hashlib.sha1(raw.encode()).hexdigest()

# 在实现里：创建前先查「是否已用相同 idem_key 创建过」
# （对不支持服务端幂等的平台，用 idempotency store 记录已创建的返回）
```

### 2.7 与 ad_platform_api.py 的对应关系

知识库中已有脚本 `ad_platform_api.py`，它是一整套「直接调用各平台 SDK/REST」的工具函数集合（`tiktok_create_campaign`、`meta_create_campaign`、`google_create_campaign`……）。它正是 PlatformPort 各实现可以复用/封装的下层基础。

我们把 `ad_platform_api.py` 定位为 **Adapter 的底层驱动（底层 SDK 封装层）**，在其之上包一层 `PlatformPort`，得到清晰的依赖分层：

```
Agent / Skill 层
      │ 统一契约
      ▼
PlatformPort 实现（impl_google / impl_meta / impl_tiktok / impl_dv360）
      │ 复用底层驱动
      ▼
ad_platform_api.py（平台客户端封装：AdPlatformClient，各平台 xxx_* 方法）
      │ 使用平台 SDK
      ▼
平台官方 SDK / REST（facebook_business, google-ads, googleapiclient, requests+tiktok）
```

`impl_meta.create_campaign` 可直接委托 `AdPlatformClient().meta_create_campaign(...)`：

```python
# 复用 ad_platform_api 的实现示例
from ad_platform_api import AdPlatformClient

class MetaImplViaScript(PlatformPort):
    def __init__(self):
        self.client = AdPlatformClient()   # 复用凭证加载与客户端缓存

    def create_campaign(self, campaign: UnifiedCampaign) -> str:
        res = self.client.meta_create_campaign(
            account_id=self.account_id,
            name=campaign.name,
            objective=campaign.objective,
        )
        return res["id"]
```

> **设计建议**：`ad_platform_api.py` 本身已经是「统一客户端」的雏形，但它把所有平台塞进一个类、返回原始 dict。生产级演进方向是：
> 1. 把它重构为「每个平台一个 Adapter + PlatformPort 契约」；
> 2. 返回值从裸 dict 升级为 `UnifiedCampaign / UnifiedMetrics`；
> 3. 增加错误归一化与幂等层。

### 2.8 Agent 记忆系统理论

Agent 记忆系统模拟人类的记忆分层。参考认知科学，我们把记忆分成：

| 记忆类型 | 中文 | 特征 | 存储 | 生命周期 |
|----------|------|------|------|----------|
| Working Memory | 工作记忆 | 当前任务上下文，小、快、易失 | Redis / 内存 | 任务级（秒~分钟） |
| Episodic Memory | 情景记忆 | 「某时某平台我做了什么、结果如何」 | 关系库/事件流 | 中长期（天~月） |
| Semantic Memory | 语义记忆 | 从经验提炼的规则与事实 | 关系库/图 | 长期（月~年） |
| Procedural Memory | 程序记忆 | 怎么做事的技能/流程 | Skill 库 | 长期 |

这里我们重点讲广告场景最关键的三种落地形态：

1. **短期 Working Memory**：一条 Task 的执行上下文（当前正在改哪个 Campaign、改到多少、上次调价是什么时候）。这是防止重复操作、保证一致性的关键。
2. **长期 Episodic Memory**：每条「动作 → 结果」的记录。例如「8/14 我把 Meta 的 A AdSet CPA 从 10 提到 12 抗波动，结果 ROAS 从 2.8 掉到 2.5」。这些是后续反思与决策的依据。
3. **向量库（Vector Memory）**:把经验、文档、Campaign 描述变成向量，供语义检索（RAG）。例如新任务「处理方法与 8 月那次 CPA spike 类似」，可通过向量检索拉出历史成功/失败经验。

### 2.9 记忆存储模型与 Schema

我们用关系库做「结构化记忆」（状态机/快照/事件），用向量库做「语义记忆」。下面给出 schema。

#### 2.9.1 关系库 Schema（Campaign 状态持久化）

```sql
-- campaign_states.sql
CREATE TABLE campaign_states (
    id            BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    goal_id       VARCHAR(64)  NOT NULL,
    trace_id      VARCHAR(64)  NOT NULL,

    -- 实体身份（跨平台唯一键：platform + platform_campaign_id）
    platform      VARCHAR(16)  NOT NULL,
    platform_campaign_id VARCHAR(128) NOT NULL,
    unified_campaign_key VARCHAR(192) NOT NULL,   -- platform:platform_id
    UNIQUE KEY uq_entity (unified_campaign_key),

    -- 状态机
    state         VARCHAR(32)  NOT NULL,          -- DRAFT/PLANNED/ACTIVE/PAUSED/...
    previous_state VARCHAR(32) NULL,

    -- 业务快照（JSON）
    snapshot      JSON         NOT NULL,          -- 完整 UnifiedCampaign 快照
    budget_micros BIGINT       NOT NULL DEFAULT 0,
    bid_micros    BIGINT       NULL,
    status_remote VARCHAR(32)  NULL,              -- 平台侧原始状态

    -- 版本号（乐观锁，防止并发覆盖）
    version       INT UNSIGNED NOT NULL DEFAULT 1,

    -- 时间
    created_at    DATETIME(3)  NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    updated_at    DATETIME(3)  NOT NULL DEFAULT CURRENT_TIMESTAMP(3)
                         ON UPDATE CURRENT_TIMESTAMP(3),

    KEY idx_goal (goal_id),
    KEY idx_platform (platform, state)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

#### 2.9.2 事件日志 Schema

```sql
-- event_log.sql —— 不可变事件日志（追加写）
CREATE TABLE agent_events (
    id         BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    event_id   CHAR(36)     NOT NULL,               -- UUID
    trace_id   VARCHAR(64)  NOT NULL,
    goal_id    VARCHAR(64)  NULL,
    agent      VARCHAR(32)  NOT NULL,               -- 哪个 Agent
    event_type VARCHAR(64)  NOT NULL,               -- campaign.paused / bid.updated ...
    occurred_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    payload    JSON         NOT NULL,               -- 事件载荷
    KEY idx_trace (trace_id),
    KEY idx_type_time (event_type, occurred_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

#### 2.9.3 反思（Reflection）Schema

```sql
-- reflections.sql —— 反思记录
CREATE TABLE agent_reflections (
    id          BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    goal_id     VARCHAR(64) NOT NULL,
    trace_id    VARCHAR(64) NOT NULL,
    agent       VARCHAR(32) NOT NULL,
    topic       VARCHAR(128) NOT NULL,             -- 反思主题
    outcome     VARCHAR(16),                        -- good/bad/neutral
    summary     TEXT,                               -- 反思正文
    lesson      TEXT,                               -- 提炼的教训
    action_ids  JSON,                               -- 关联的那些动作事件
    created_at  DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    embedded    TINYINT(1)  DEFAULT 0               -- 是否已写入向量库
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

#### 2.9.4 向量库 Schema（语义记忆）

以 Qdrant / Pinecone / Milvus 为例：

```json
{
  "collection": "agent_memory",
  "vector": {
    "size": 1536,
    "distance": "Cosine"
  },
  "payload_schema": {
    "memory_type": "reflection | episodic | doc",
    "goal_id": "string",
    "platform": "string",
    "timestamp": "datetime",
    "score": "float",
    "text": "string"
  }
}
```

写入示例（Python + Qdrant）：

```python
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct, VectorParams, Distance

client = QdrantClient("localhost", port=6333)

def embed(text: str):
    # 假设已有 embedding 服务
    return model.encode(text).tolist()

def save_memory(text, meta):
    vec = embed(text)
    client.upsert(
        collection_name="agent_memory",
        points=[PointStruct(id=uuid4().int, vector=vec, payload=meta)],
    )

def search_memory(query, top_k=5, platform=None):
    filter_ = {"must": [{"key": "platform", "match": {"value": platform}}]} if platform else {}
    return client.search(collection_name="agent_memory",
                         query_vector=embed(query), limit=top_k,
                         query_filter=filter_)
```

### 2.10 状态机、快照与恢复

#### 2.10.1 Campaign 状态机

统一的 Campaign 生命周期状态机：

```
              ┌──────────┐
              │   DRAFT  │ 初始（本地草稿，未上平台）
              └────┬─────┘
                   │ 提交到平台
              ┌────▼─────┐    ┌─────────────────────────────┐
              │  PLANNED │───►│  PENDING_APPROVAL (平台审核)  │
              └────┬─────┘    └───────┬──────────┬──────────┘
                   │ 启用             │ 通过      │ 拒绝
              ┌────▼─────┐     ┌──────▼────┐     ▼
              │  ACTIVE  │◄────│          │    REJECTED
              └─┬───┬────┘     └──────────┘
                │   │ 暂停
                │   ▼
                │  PAUSED ──────► 启用回到 ACTIVE
                │
                ▼
             REMOVED  (删除/归档)

  合法迁移表：
  DRAFT → PLANNED           提交
  PLANNED → PENDING_APPROVAL 平台审核中
  PENDING_APPROVAL → ACTIVE  审核通过
  PENDING_APPROVAL → REJECTED 审核拒绝
  ACTIVE → PAUSED            平台暂停
  PAUSED → ACTIVE            平台恢复
  ACTIVE/PAUSED → REMOVED    删除
```

#### 2.10.2 状态机实现

用确定性的状态机库（如 Python 的 `transitions`）：

```python
from transitions import Machine

class CampaignFSM:
    states = ["DRAFT", "PLANNED", "PENDING_APPROVAL", "ACTIVE", "PAUSED", "REJECTED", "REMOVED"]

    transitions = [
        {"trigger": "submit",   "source": "DRAFT", "dest": "PLANNED"},
        {"trigger": "review",   "source": "PLANNED", "dest": "PENDING_APPROVAL"},
        {"trigger": "approve",  "source": "PENDING_APPROVAL", "dest": "ACTIVE"},
        {"trigger": "reject",   "source": "PENDING_APPROVAL", "dest": "REJECTED"},
        {"trigger": "pause",    "source": ["ACTIVE"], "dest": "PAUSED"},
        {"trigger": "resume",   "source": ["PAUSED"], "dest": "ACTIVE"},
        {"trigger": "remove",   "source": ["ACTIVE", "PAUSED", "REJECTED"], "dest": "REMOVED"},
    ]

    def __init__(self):
        self.machine = Machine(model=self, states=self.states,
                               transitions=self.transitions, initial="DRAFT")
        # 在每次迁移时记录事件
        self.machine.add_transition_condition(...)  # 可加守卫条件
```

> 关键点：状态迁移必须**回写事件日志 + 更新快照**，且只用「本地状态 = 权威」，平台侧状态作为 `status_remote` 冗余记录，用于对账（下面讲对账）。

#### 2.10.3 快照（Snapshot）

快照是某时刻 Campaign 完整状态的拷贝，用于恢复与审计。策略：

- **变更即快照**：每次写入 campaign_states 时，整份 JSON 快照落库。
- **定期全量**：每天对活跃 Campaign 打一次全量快照（便于跨天回溯）。
- **快照版本**：`version` 字段配合「乐观锁」，检查 `version` 防止旧写覆盖新写。

```python
def take_snapshot(campaign: UnifiedCampaign) -> dict:
    return {
        "unified_campaign_key": f"{campaign.platform}:{campaign.platform_id}",
        "state": campaign_state,
        "budget_micros": campaign.daily_budget_micros,
        "bid_micros": campaign_bid,
        "targeting": campaign.targeting,
        "bidding": campaign.bidding,
        "captured_at": utcnow_iso(),
        "version": current_version,
    }
```

#### 2.10.4 恢复（Recovery）

当进程崩溃 / 任务中断时，从最终一致状态恢复。恢复流程：

```python
def recover_campaign(platform, campaign_id):
    snap = load_latest_snapshot(platform, campaign_id)   # 本地权威
    remote = platform_port.get_campaign(campaign_id)     # 平台侧现状
    if snap_matches(snap, remote):
        return snap                        # 一致，直接用
    # 不一致：进入对账（reconciliation）流程
    reconciled = reconcile(snap, remote)
    apply_corrections(reconciled)          # 按席位规则修正
    return reconciled
```

对账要遵循「激动最小」原则：本地没动、平台也没动 → 不动；本地要动而平台没同步 → 推送；平台被外部改了 ��� 以平台为准并记录差异事件。

### 2.11 事件日志与溯源

每个动作都记一个不可变事件。事件是「溯源」与「审计」的原料。

```json
{
  "event_id": "8f2c9a1b-...",
  "trace_id": "trace_20260814_abc",
  "goal_id": "g_20260814_001",
  "agent": "meta_agent",
  "event_type": "budget.updated",
  "occurred_at": "2026-08-14T09:12:33Z",
  "payload": {
    "campaign_key": "meta:6099123456",
    "from_micros": 50000000,
    "to_micros": 65000000,
    "reason": "roas_upscale",
    "idempotency_key": "idem_xxx",
    "approved_by": "budget-arbiter"
  }
}
```

事件还用于**事件溯源（Event Sourcing）**：不直接改最终状态，而是记录一串事件，状态可由事件流回放得到。这带来强大的审计与重放能力：

```
状态 = fold(起始状态, [event1, event2, event3, ...])

campaign_states 只是「已物化」的读模型(hot cache)，真正的真相(event log)可随时重放重建
```

### 2.12 反思（Reflection）机制

反思是 Agent「从经验中学习」的闭环。相比人类每天写复盘，Agent 的系统化反思流程如下：

```
Observe（观察结果）
   │
   ▼
Evaluate（评估成效：达标? / 恶化? / 持平?）
   │
   ▼
Attribute（归因：是什么动作导致的？）
   │
   ▼
Generalize（概括：提炼成一条可复用的规则/教训）
   │
   ▼
Persist（落库 + 写入向量库，供未来检索）
```

#### 反思触发条件

| 触发 | 说明 | 示例 |
|------|------|------|
| 目标达成/未达成 | 每轮循环结束 | ROAS 达标 → 记录放量手法有效 |
| 异常 | 检测到异常 | CPA 飙升 → 记录「xx 条件下别盲目提价」 |
| 周期性 | 每天/每周定时 | 每周总结预算分配经验 |
| 人工反馈 | 用户纠正 | 用户说「别动 Meta 的定位」→ 记录偏好 |

#### 反思代码示例

```python
def reflect(goal, actions, results):
    metrics = summarize(results)          # 汇总各平台指标
    lessons = []
    for a in actions:
        outcome = evaluate_outcome(a, metrics)
        if outcome == "good":
            lessons.append({"lesson": f"{a.name} 有效", "kind": "do_more",
                            "platform": a.platform, "topic": a.name})
        elif outcome == "bad":
            lessons.append({"lesson": f"{a.name} 导致 {a.cost} 恶化", "kind": "avoid",
                            "platform": a.platform, "topic": a.name})
    # 持久化到关系库 + 向量库
    for lesson in lessons:
        ink_reflection(goal.goal_id, lesson)
        save_memory(lesson["lesson"], {"memory_type": "reflection",
                                       "platform": lesson["platform"],
                                       "goal_id": goal.goal_id})
    return lessons
```

**反思的两种粒度**：
1. **动作级反思**：单次调价后马上评估（快、浅）。
2. **目标级反思**：一轮完整循环后，对整体策略复盘（慢、深）。

### 2.13 Agent Skill 系统设计

Skill 是 Agent 的「肌肉记忆」——把可复用的原子能力打包。参考知识库现有的 Expert Skills（`google-ads-api-expert`、`meta-marketing-api-expert`、`tiktok-ads-expert`、`dv360-expert`），我们把 Skill 设计成与它们对接的「可注册能力单元」。

#### Skill 元数据模型（Manifest）

```yaml
# skill.yaml —— Skill 清单模板
name: google-ads-api-expert
version: 1.4.0
description: "Google Ads API 专家技能：OAuth、广告管理、智能出价、报表、限流处理"
platform: google
category: platform           # platform | generic
capabilities:
  - auth
  - campaign
  - bidding
  - budget
  - report
  - keyword
  - creative
tools:
  - google_list_campaigns
  - google_create_campaign
  - google_update_bid
  - google_download_report
permissions:
  requires: [ads_management, ads_read]
  blocklist: [delete_irreversible]
rate:
  rpm: 2500
  burst: 100
```

#### Skill 目录清单

**平台专属 Skill：**

| Skill | 平台 | 覆盖能力 | 提供 Tools 示例 |
|-------|------|----------|-----------------|
| google-ads-api-expert | Google | 认证、广告管理、批量操作、智能出价、报表下载、限流 | google_list_campaigns / google_create_campaign / google_update_bid / google_download_report |
| meta-marketing-api-expert | Meta | 认证、广告管理、Pixel、CAPI、受众、报表 | meta_create_adset / meta_list_audiences / meta_send_capi / meta_query_insights |
| tiktok-ads-expert | TikTok | 认证、广告管理、Spark Ads、Pixel、CAPI、报表 | tiktok_create_campaign / tiktok_create_adgroup / tiktok_track_pixel / tiktok_query_report |
| dv360-expert | DV360 | Line Item/Flight/Creative、媒体购买、报表、DSP 集成 | dv360_create_io / dv360_list_line_items / dv360_fetch_report / dv360_upload_creative |

**通用 Skill：**

| Skill | 类别 | 作用 | 提供能力 |
|-------|------|------|----------|
| data-analytics-expert | 数据 | 报表聚合、指标计算、趋势检测 | aggregate_report / compare_platforms / detect_anomaly |
| creative-optimizer-expert | 创意 | 素材轮换、A/B、审核加速 | rotate_creatives / score_creative / submit_approval |
| bidding-strategy-expert | 出价 | 出价策略、预算分配、ROAS 目标 | calc_bid_micros / allocate_budget / set_roas_target |
| attribution-expert | 归因 | 跨渠道归因、转化计数、去重 | run_attribution / dedupe_conversions / shard_by_channel |
| safety-guardrails-expert | 安全 | 预算闸门、竞品风控、敏感词 | check_budget_cap / detect_fraud / kill_switch |
| report-writer-expert | 报表 | 日报/周报生成 | gen_daily_report / gen_weekly_review |

#### Skill 注册表（Registry）

```python
# skill_registry.py —— Skill 注册表
class SkillRegistry:
    def __init__(self):
        self._skills = {}

    def register(self, skill):
        if skill.name in self._skills:
            raise ValueError(f"duplicate skill: {skill.name}")
        self._skills[skill.name] = skill

    def get(self, name):
        return self._skills.get(name)

    def find_by_platform(self, platform):
        return [s for s in self._skills.values() if s.platform == platform]

    def all(self):
        return list(self._skills.values())

# 启动时注册
registry = SkillRegistry()
registry.register(GoogleAdsExpert())
registry.register(MetaMarketingExpert())
registry.register(TikTokAdsExpert())
registry.register(DV360Expert())
registry.register(DataAnalyticsExpert())
registry.register(CreativeOptimizerExpert())
registry.register(BiddingStrategyExpert())
registry.register(AttributionExpert())
registry.register(SafetyGuardrailsExpert())
registry.register(ReportWriterExpert())
```

### 2.14 Skill 注册表与调度

Skill 需要一种「让 Agent 知道什么时候该用哪个 Skill」的机制。两种主流方法：

1. **声明式路由**：任务类型 → Skill 的静态映射（适合确定性强的场景）。
2. **语义检索路由**：把任务描述向量化，检索最匹配的 Skill（适合 LLM 动态场景）。

```python
# skill_router.py —— 语义路由
def route_to_skill(task: dict, registry: SkillRegistry):
    task_vec = embed(to_text(task))
    best, best_score = None, -1
    for skill in registry.all():
        score = cosine(task_vec, skill.embedding)   # skill 预计算 embedding
        if score > best_score:
            best, best_score = skill, score
    if best_score < 0.5:
        return None     # 无匹配，交给 Orchestrator 兜���
    return best
```

#### Skill 调��（并发控制）

同一 Skill 的调用需防抖与限流（防止多个 Agent 同时用同一个 Skill 打爆平台配额）：

```python
# skill_executor.py —— Skill 执行调度
import threading
from collections import defaultdict

class SkillExecutor:
    def __init__(self):
        self._locks = defaultdict(threading.Lock)   # 每 Skill 一把锁
        self._rate = defaultdict(Semaphore)         # 每 Skill 速率

    def call(self, skill_name, task, registry):
        with self._locks[skill_name]:               # 串行化同 Skill（防抖）
            skill = registry.get(skill_name)
            return skill.execute(task)

    # 或：允许并发但对平台限额
    def call_async(self, skill_name, task, registry):
        skill = registry.get(skill_name)
        limiter_for(skill.platform).acquire()       # 平台限流
        return skill.execute(task)
```

### 2.15 Skill 调用示例与链路

一个完整的 Skill 调用链路：**Agent 决定用 Skill → 路由器选 Skill → 执行器拿平台配额 → Skill 调 PlatformPort → 结果回写记忆**。

```python
# 链路演示：MetaAgent 降低 CPA
class MetaAgent:
    def __init__(self, registry, memory, platform):
        self.registry = registry
        self.memory = memory
        self.platform = platform          # PlatformPort 实现

    def lower_cpa(self, campaign_key, target_cpa_micros):
        # 1. 从记忆读取该 Campaign 上下文（工作记忆）
        ctx = self.memory.load_working(campaign_key)

        # 2. 选 Skill（语义路由）
        skill = route_to_skill(
            {"platform": "meta", "action": "lower_cpa", "campaign": campaign_key},
            self.registry)

        # 3. 调 Skill（内部走 PlatformPort）
        result = skill.execute({
            "platform": self.platform,
            "campaign_key": campaign_key,
            "target_cpa_micros": target_cpa_micros,
            "ctx": ctx,
        })

        # 4. 尝试降低出价（平台动作）
        self.platform.update_bid(campaign_key, target_cpa_micros,
                                 WithAccountID(ctx["account_id"]),
                                 WithIdempotencyKey(make_idem_key(...)))

        # 5. 记事件 + 更新快照
        self.memory.emit("bid.updated", {...})
        self.memory.snapshot(campaign_key, {...})

        return result
```

---

## 三、生产环境实战

### 3.1 完整系统组件图

生产系统把「编排 + 平台抽象 + 记忆 + Skill」落地成可部署组件：

```
┌─────────────────────────────── Web / API 网关（用户入口） ───────────────────────────────┐
│   /api/goals (提交目标)  /api/campaigns (查询)  /api/report (报表)  /api/audit           │
└───────────────────────────────────────────┬────────────────────────────────────────────┘
                                            ▼
┌────────────────────────────── Orchestrator 服务（无状态，可横向扩展） ───────────────────┐
│  Planner / Decomposer / Router / BudgetArbiter / Reflector / MemoryHub                  │
│  ┌───────────────┐   ┌───────────────┐   ┌───────────────┐   ┌───────────────┐          │
│  │  Planner       │   │ Router        │   │ BudgetArbiter │   │ Reflector     │          │
│  └───────────────┘   └───────────────┘   └───────────────┘   └───────────────┘          │
└───────────────────────────────┬─────────────────────────────────────────────────────────┘
                                │ 内部消息总线（NATS / Kafka / gRPC）
┌───────────────────────────────▼─────────────────────────────────────────────────────────┐
│                     Agent 工作节点（每个 Agent 类型一组 Pod）                              │
│   [GoogleAgent]  [MetaAgent]  [TikTokAgent]  [DV360Agent]                              │
│   [DataAgent]  [CreativeAgent]  [AttributionAgent]  [RiskAgent]  [ReportAgent]        │
│        每个 Agent:  SkillExecutor + 本地短记忆缓存                                        │
└───────────────────────────────┬��────────────────────────────────────────────────────────┘
                                │ PlatformPort 接口
┌───────────────────────────────▼─────────────────────────────────────────────────────────┐
│                   Adapter 层（各平台实现） + 错误/限流/重试归一化                          │
└───────────────────────────────┬─────────────────────────────────────────────────────────┘
                                │
        ┌───────────────────────┼───────────────────────┐
        ▼                       ▼                       ▼
  [Google 平台 API]      [Meta 平台 API]        [TikTok / DV360 平台 API]

┌────────────────────────────────────── 数据与控制平面 ────────────────────────────────────┐
│  MySQL/PG  : campaign_states / agent_events / reflections                              │
│  Redis     : working memory / idempotency store / distributed lock                     │
│  Qdrant    : 向量记忆(RAG)                                                              │
│  Kafka     : 事件流 / 对账 / 审计                                                        │
│  S3        : 报表 / 创意资产                                                            │
│  Prometheus+Grafana : 指标监控                                                          │
└─────────────────────────────────────────────────────────────────────────────────────────┘
```

**部署要点**：
- Orchestrator 无状态，便于水平扩容与滚动升级。
- Agent 节点按类型分组，可分别扩缩容（Meta 任务多就多开 MetaAgent）。
- Adapter 层可单独灰度替换（先替换 Meta 实现，观察再换其他）。

### 3.2 编排循环：Plan→Act→Observe→Reflect

核心编排��环是 Agent 系统的「心跳」。每个目标/每轮优化都走这个循环：

```
   Plan ────► Act ────► Observe ────► Reflect
    ▲                                    │
    └──────────────(下一轮)──────────────┘
```

#### 3.2.1 Plan（规划）

基于记忆 + 当前数据，制定本轮动作。

```python
def plan(goal, memory, data):
    # 注入上下文：工作记忆 + 向量检索相关经验
    ctx = {
        "goal": goal,
        "working": memory.load_working(goal.goal_id),
        "historical": search_memory(f"{goal.objective} {goal.platforms}", top_k=5),
    }
    plan_prompt = build_plan_prompt(ctx)
    return llm(plan_prompt)        # 返回 {actions: [...]}
```

#### 3.2.2 Act（执行）

执行任务树中的动作，走 Skill + PlatformPort，全部幂等 + 可追踪。

```python
for action in plan["actions"]:
    task = materialize_action(action)          # 转成可执行 Task
    result = execute_task(task)                # Skill + PlatformPort
    memory.emit(f"{task.kind}.executed", {...}) # 事件
```

#### 3.2.3 Observe（观察）

拉取各平台最新报表/状态，与计划时的基线对比，判断成效。

```python
def observe(goal, actions):
    reports = data_agent.pull_all(goal.platforms)
    metrics = aggregate(reports, group_by=["platform", "campaign"])
    for a in actions:
        a.actual = metrics.get(a.campaign_key)  # 记录实际表现
    return metrics
```

#### 3.2.4 Reflect（反思）

评估本轮，沉淀经验，决定是否继续下一轮。

```python
def reflect(goal, actions, metrics):
    lessons = []
    for a in actions:
        outcome = evaluate(a, metrics)
        lessons.append(record_lesson(a, outcome))
    persist_lessons(lessons)                     # 写 reflections + 向量库
    goal_done = is_goal_met(goal, metrics)
    return goal_done, lessons
```

#### 3.2.5 完整循环（带 LLM 的主循环伪代码）

```python
def orchestrate(goal, memory):
    step, max_steps = 0, 24
    goal_done = False
    while not goal_done and step < max_steps:
        # PLAN
        plan_ctx = memory.compose_context(goal)
        plan = planner.plan(plan_ctx)                    # LLM 或规则

        # ACT
        results = []
        for action in plan.actions:
            results.append(await execute_action(action))
            await memory.emit(action)

        # OBSERVE
        metrics = await observe(goal, plan.actions)

        # REFLECT
        goal_done, lessons = reflect(goal, plan.actions, metrics)
        await memory.record(lessons)

        step += 1
        await sleep(goal.report_interval)                # 控制节奏，防抖
    return goal_done
```

### 3.3 并发与协作模型

#### 3.3.1 任务并发模型

编排循环内部可并行跑「互不依赖」的任务。我们用 Python `asyncio` / Go goroutine 描述：

```go
// Go: 并行派发平台建站任务
package main

func deployAcrossPlatforms(ctx context.Context, goals []Goal) error {
    var wg sync.WaitGroup
    errCh := make(chan error, len(goals))
    for _, g := range goals {
        wg.Add(1)
        go func(g Goal) {
            defer wg.Done()
            if err := deploySingle(ctx, g); err != nil {
                errCh <- err
            }
        }(g)
    }
    wg.Wait()
    close(errCh)
    return firstError(errCh)
}

func deploySingle(ctx context.Context, g Goal) error {
    switch g.Platform {
    case "google":
        return googlePort.CreateCampaign(ctx, g.ToCampaign())
    case "meta":
        return metaPort.CreateCampaign(ctx, g.ToCampaign())
    case "tiktok":
        return tiktokPort.CreateCampaign(ctx, g.ToCampaign())
    case "dv360":
        return dv360Port.CreateCampaign(ctx, g.ToCampaign())
    }
    return nil
}
```

#### 3.3.2 边界：并发改造同一个平台

尽管「不同平台可并行」，但**同一平台内的写操作必须串行/加锁**（防止 MetaAgent 两个实例同时改 Meta 预算）。并发边界规则：

| 资源 | 可并行度 | 机制 |
|------|----------|------|
| 不同平台 | ✅ 全并行 | 无共享状态 |
| 同一平台、不同 Campaign | ✅ 可并行（不同锁） | 每 Campaign 一把锁 |
| 同一平台、同一 Campaign | ❌ 必须串行 | 分布式锁 + 版本乐观锁 |

### 3.4 防抖与冲突消解（并发改预算）

这是广告 Agent 系统最经典的坑：**多个 Agent 或多次循环同时想改同一个 Campaign 的预算，导致「抖动」「打架」「把预算改过头」。**

#### 3.4.1 问题场景

```
场景：周末促销，系统要在 1 小时内给某 Meta AdSet 加预算。
- RoasAgent 判断 ROAS 好，想 +20%；
- BudgetArbiter 全局想调整预算分配；
- 两个循环并发写同一 AdSet 的 daily_budget。
若不加保护：写写冲突，最终值不可控，甚至实际超支。
```

#### 3.4.2 防抖（Debounce / Cooldown）

给「同一实体的写操作」加冷却期——短时间内不重复���同一对象：

```python
# debounce.py —— 基于 Redis 的冷却窗口
import redis
r = redis.Redis()

def guard_cooldown(entity_key, action, cooldown_sec=300):
    lock_key = f"cooldown:{entity_key}:{action}"
    acquired = r.set(lock_key, "1", nx=True, ex=cooldown_sec)
    if not acquired:
        raise ConflictError(f"{entity_key} 正在 {action} 的冷却期内，跳过")
    return True

# 用法：同一 Campaign 的 budget 5 分钟内最多改 1 次
guard_cooldown("meta:6099123456", "budget", cooldown_sec=300)
```

#### 3.4.3 冲突消解规则（预算仲裁）

定义一个**预算仲裁器（Budget Arbiter）**，统一决定「预算给谁、给多少、何时给」：

```python
# budget_arbiter.py —— 预算仲裁
class BudgetArbiter:
    def __init__(self, total_cap_micros, platform_weights):
        self.total = total_cap_micros
        self.weights = platform_weights      # 各平台预算权重

    def request(self, req, current):
        """
        req: {platform, campaign_key, wanted_micros, priority}
        current: 当前分配快照
        返回 granted_micros / denied
        """
        # 1. 全局上限闸门
        if req.wanted_micros > self.total:
            return deny("超过全局预算上限")
        # 2. 平台配额
        platform_alloc = self.weights[req.platform]
        if current_platform_usage(req.platform) + req.wanted_micros > platform_alloc:
            return deny("超过平台配额")
        # 3. 冲突判断：同一 Campaign 已有待处理写操作
        if is_pending_write(req.campaign_key):
            return deny("该 Campaign 已有待处理变更，进入队列")
        # 4. 幂等/冷却
        try:
            guard_cooldown(req.campaign_key, "budget", 300)
        except ConflictError:
            return deny("冷却期")
        return grant(req)
```

**冲突消解优先级（决定谁先获得资源）：**

| 优先级 | 请求来源 | 说明 |
|--------|----------|------|
| P0 | 人工/风控强制 | 立即生效，最高 |
| P1 | 预算超额保护 | 防超支，仅次于人工 |
| P2 | ROAS 优化 | 常规优化 |
| P3 | 测试/探索 | 最低，可牺牲 |

#### 3.4.4 分布式锁（真正串行写）

对「同一实体写」用 Redlock / Redis 分布式锁 + 乐观版本号：

```python
def locked_write(campaign_key, do_write):
    # 获得分布式锁
    token = uuid4().hex
    ok = r.set(f"lock:{campaign_key}", token, nx=True, ex=30)
    if not ok:
        raise ConflictError("已被其他 Agent 锁定")
    try:
        return do_write()          # 真正的写操作
    finally:
        # 仅当 token 匹配才释放（防误删他人锁）
        with r.pipeline() as p:
            p.watch(f"lock:{campaign_key}")
            if p.get(f"lock:{campaign_key}") == token:
                p.multi()
                p.delete(f"lock:{campaign_key}")
                p.execute()
```

### 3.5 监控与可观测性

生产系统必须有全面的可观测性。我们分「技术指标」与「业务指标」。

#### 3.5.1 技术指标（Prometheus）

```yaml
# prometheus.yml 采集的服务指标
- 编排：
  - orchestrator_loop_total{goal}          # 循环次数
  - orchestrator_plan_duration_seconds
  - orchestrator_reflect_duration_seconds
- Agent：
  - agent_message_published_total{src,dst,type}
  - agent_execution_seconds{agent,skill}
  - agent_action_failures_total{platform,kind}
- 平台抽象层：
  - platform_api_calls_total{platform,method}
  - platform_api_latency_seconds{platform}
  - platform_rate_limited_total{platform}
  - platform_retry_total{platform,attempt}
- 记忆：
  - memory_snapshot_count
  - memory_event_written_total
```

```python
# instrumentation.py —— 用 Prometheus Client 打点
from prometheus_client import Counter, Histogram

API_CALLS = Counter("platform_api_calls_total", "平台调用", ["platform", "method"])
API_LATENCY = Histogram("platform_api_latency_seconds", "平台延迟", ["platform"])

def traced_call(platform, method, fn):
    API_CALLS.labels(platform, method).inc()
    with API_LATENCY.labels(platform).time():
        return fn()
```

#### 3.5.2 业务指标

| 业务指标 | 意义 | 告警阈值示例 |
|----------|------|--------------|
| 日花费 vs 预算 | 是否超支 | >100% 报警 |
| 各平台 ROAS | 是否达标 | <2.5 告警 |
| 单平台花费波动 | 稳定性 | 日环比 >20% 告警 |
| 转化回传延迟 | 追踪质量 | 延迟>24h 告警 |
| 审核驳回率 | 创意质量/合规 | >30% 告警 |
| 自动操作被拒次数 | 冲突/风控 | >N 告警 |

#### 3.5.3 日志与追踪

- **结构化日志**：JSON 输出，含 trace_id / goal_id / agent。
- **分布式追踪**：用 OpenTelemetry，从 Orchestrator 派发到 Agent 执行的整条链路打 span。

```json
{
  "ts": "2026-08-14T09:12:33Z",
  "level": "info",
  "logger": "meta_agent",
  "trace_id": "trace_x",
  "goal_id": "g_001",
  "event": "budget.updated",
  "campaign_key": "meta:6099123456",
  "from": 50000000, "to": 65000000,
  "duration_ms": 42
}
```

### 3.6 审计与合规

广告投放涉及真实资金，审计与合规至关重要。

#### 3.6.1 审计要求

1. **谁在何时做了什么**：每个动作都留痕（agent_events）。
2. **可解释性**：每个自动操作都有 reason 字段（为什么这么做）。
3. **不可篡改**：事件日志只追加，不允许 UPDATE/DELETE。
4. **人机边界**：关键操作（大额预算、删 Campaign）必须人工审批/留痕。

#### 3.6.2 关键操作分级

| 操作 | 风险 | 是否自动 | 审批要求 |
|------|------|----------|----------|
| 出价微调（±10%） | 低 | ✅ 自动 | 无需 |
| 预算微调（±20%） | 中 | ✅ 自动+风控闸门 | 需 BudgetArbiter |
| 预算大调（>50%） | 高 | ❌ 需人工 | 二次确认 |
| 暂停 Campaign | 高 | ⚠️ 可自动但必须审计 | 通知 + 留痕 |
| 删除 Campaign | 极高 | ❌ 禁止自动 | 人工 |
| 新建大投放 | 高 | ❌ 需人工 | 审批 |

```python
# approval.py —— 审批流
class ApprovalService:
    THRESHOLD_MICROS = 50_000_000   # $50 以上预算变更需审批

    def request_if_needed(self, action):
        if action.kind == "budget" and action.delta_micros > self.THRESHOLD_MICROS:
            req = self.open_approval(action)
            return Approval(request_id=req, status="pending")
        return Approval(status="auto")
```

### 3.7 灰度上线

引入新功能/新 Agent/新策略时，应灰度，避免风险全量暴露。

#### 3.7.1 灰度策略

| 灰度维度 | 做法 | 示例 |
|----------|------|------|
| 按平台 | 先只在一个平台启用新 Agent | 先只用新版 MetaAgent |
| 按账户 | 先对小预算账户启用 | 只在测试账户跑 |
| 按 Campaign | 只对部分 Campaign 启用某个 Skill | 只在 5 个 Campaign 用新版出价 |
| 按流量 | 仅 x% 的请求走新逻辑 | 影子模式对比 |
| 影子模式 | 新逻辑只记录不实际写平台 | 对比新旧决策差异 |

#### 3.7.2 开关（Feature Flag）

```python
# feature_flags.py
FEATURES = {
    "auto_bid_v2": {"enabled": True,
                    "platforms": ["meta"], "accounts": ["test_acct"]},
    "auto_pause":  {"enabled": False},
    "creative_rating_v2": {"enabled": True, "rollout": 0.5},
}

def enabled(feature, platform=None, account=None):
    cfg = FEATURES.get(feature, {})
    if not cfg.get("enabled"): return False
    if platform and cfg.get("platforms") and platform not in cfg["platforms"]:
        return False
    if account and cfg.get("accounts") and account not in cfg["accounts"]:
        return False
    if "rollout" in cfg:
        return hash(f"{feature}:{account}") % 100 < cfg["rollout"] * 100
    return True
```

#### 3.7.3 比对验证

灰度期要做「新旧对照」：新逻辑在影子模式下产生的「建议动作」与旧逻辑对比，确认差异符合预期才放量。

```
Oracle输出(新建议) vs 现状(旧)
- 新建议: Meta AdSet X 预算 +10%
- 旧行为: 不改
- 若 oracle 引出的预测 ROAS 提升 > 阈值 → 放量；否则回滚
```

### 3.8 故障恢复与容灾

#### 3.8.1 故障类型与恢复策略

| 故障 | 现象 | 恢复策略 |
|------|------|----------|
| 平台 API 限流 | 大量 RATE_LIMIT | 指数退避 + 排队 + 降级为只读 |
| 平台鉴权失效 | token 过期 | 自动刷新 + 告警 |
| Orchestrator 崩溃 | 无状态，自动重启 | 事件回溯 + 从快照恢复 |
| Agent 崩溃 | 任务中断 | 幂等重放（有 idempotency key） |
| 数据库故障 | 读不到状态 | 只读降级 + 缓存 |
| 网络分区 | 与平台失联 | 熔断 + 延迟重试 + 人工兜底 |

#### 3.8.2 熔断器（Circuit Breaker）

对平台调用加熔断，防止雪崩：

```python
# circuit_breaker.py
class CircuitBreaker:
    def __init__(self, fail_threshold=5, cooldown=60):
        self.failures = 0
        self.state = "closed"        # closed 正常 / open 熔断 / half-open 试探
        self.fail_threshold = fail_threshold
        self.cooldown = cooldown
        self.opened_at = None

    def call(self, fn):
        if self.state == "open":
            if time.time() - self.opened_at > self.cooldown:
                self.state = "half-open"
            else:
                raise CircuitOpen("平台熔断中，降级")
        try:
            r = fn()
            self.failures = 0
            self.state = "closed"
            return r
        except PlatformError as e:
            self.failures += 1
            if self.failures >= self.fail_threshold:
                self.state = "open"
                self.opened_at = time.time()
            raise
```

#### 3.8.3 快速恢复与回滚

每个「有风险的写操作」都应能回滚。回滚实现：

```python
def rollback(campaign_key, snapshot_before):
    current = platform_port.get_campaign(campaign_key)
    # 恢复预算/出价快照（用本地快照覆盖）
    platform_port.update_budget(campaign_key, snapshot_before["budget_micros"])
    platform_port.update_bid(campaign_key, snapshot_before.get("bid_micros"))
    # 若状态变化了也恢复
    if current.status != snapshot_before["state"]:
        (resume if snapshot_before["state"] == "ACTIVE" else pause)(campaign_key)
```

#### 3.8.4 灾备拓扑

```
主集群（生产）                   备集群（容灾）
[Orchestrator x3]             [Orchestrator x1 standby]
[Agent 工作节点]              [Agent 工作节点 standby]
[MySQL 主] ——同步/半同步——► [MySQL 备]
[Redis 主]                    [Redis 备]
[Kafka 主]                    [Kafka 备]
[对象存储 主]                [对象存储 同城/异地复制]
```

关键数据（campaign_states / agent_events）要**跨可用区、跨地域备份**，RPO 目标 ≤ 1 分钟，RTO 目标 ≤ 5 分钟。

### 3.9 端到端真实投放场景推演

我们完整推演一个真实场景，把前面所有机制串起来。

#### 场景：周末大促「全渠道放量 30%」

**目标**：`G`（新用户获取，4 平台合计，ROAS≥3，预算 $60k→$78k，周六凌晨放量）。

##### Step 1 目标受理
用户通过 API/Web 提交目��，Orchestrator 生成 `goal_id`，写入事件 `goal.created`。

##### Step 2 规划
Planner 组装上下文（历史 ROAS：Google 2.2 / Meta 3.1 / TikTok 2.8 / DV360 2.0），LLM 产出放量计划：
```
actions:
  - 平台=google: 预算 +5% ($15k) ，更新出价策略为 tROAS=3.0
  - 平台=meta:   预算 +15% ($24k)，提高易转化 AdSet 出价
  - 平台=tiktok: 预算 +5% ($12k)，新增 2 个 Spark Ads 素材
  - 平台=dv360:  预算 +5% ($7k) ，扩展频控、提高填充
```

##### Step 3 仲裁与授权
BudgetArbiter 校验全局预算 `78k ≤ cap`，各平台配额未超，批准放量。`conflict.request` → `conflict.granted`。

##### Step 4 并行执行
各平台 Agent 并行执行（不同平台不同锁）：

- **MetaAgent**：调用 `meta-marketing-api-expert` 的 `update_budget`，把 AdSet 预算 +15%；更新 `campaign_states` 快照、写事件。
- **GoogleAgent**：调用 `google-ads-api-expert` 更新 tROAS，设置预算。
- **TikTokAgent**：调用 `tiktok-ads-expert` 创建 Spark Ads 素材。
- **DV360Agent**：调用 `dv360-expert` 提高 Line Item 出价。

##### Step 5 观察
DataAgent 拉取 4 平台在放量后 6 小时的数据，汇总 UnifiedMetrics，判断 ROAS。

##### Step 6 反思与收敛
- Google ROAS 掉到 2.0（低于 3）→ Reflector 记录「Google 短期放量拉低 ROAS」，触发「降 Google 出价」动作（P2）。
- Meta ROAS 升到 3.4 → 记录「Meta 放量有效」，继续保留。
- 产出 daily_report。

##### Step 7 风控复核
RiskAgent 检查总花费是否超预算、是否有异常波动、是否有素材被拒，全部通过。

#### 时序图（多 Agent 协作）

```
        用户      Orchestrator    BudgetArbiter   GoogleAgent  MetaAgent  TikTokAgent  DV360Agent  DataAgent
          │            │               │              │          │          │            │            │
          │ goal       │               │              │          │          │            │            │
          ├───────────►│ plan           │              │          │          │            │            │
          │            ├──────────────►│ 仲裁          │          │          │            │            │
          │            │               ├─────────────►│ 建站/放量   │          │            │            │
          │            │               ├─────────────►│          │ 建站/放量 │            │            │
          │            │               ├─────────────►│          │          │ 建站/素材   │            │
          │            │               ├─────────────►│          │          │            │ 放量/出价    │
          │            │               ◄─────────────┤ 结果      │          │            │            │
          │            │               ◄─────────────┤          │ 结果     │            │            │
          │            │               ◄─────────────┤          │          │ 结果       │            │
          │            │               ◄─────────────┤          │          │            │ 结果        │
          │            │ observe   ──────────────────────────────────────────────────────────────► 拉数据
          │            │ ◄────────────────────────────────────────────────────────────────────── 汇总
          │            │ reflect
          │            ├─────────────────────────── 写记忆/反思
          │ ◄──────────┤ goal_result
          │            │
```

### 3.10 与知识库现有 Skills 的对接

本系统设计为可直接对接 `ryan-personal-knowledge` 知识库现有的专家 Skills：

- `google-ads-api-expert`
- `meta-marketing-api-expert`
- `tiktok-ads-expert`
- `dv360-expert`

#### 3.10.1 对接方式

现有 Skills 是「给 LLM 读的一整套 API 操作指南 + 工具能力」。我们的 Agent 系统有两种对接路径：

```
路径 A：把 Skill 的 Tools 包成 PlatformPort 实现（推荐）
  google-ads-api-expert 的 google_create_campaign
        │ 包装
        ▼
  GoogleAdsImpl.create_campaign  ──► 符合 PlatformPort 契约

路径 B：Skill 作为 Agent 的「提示词 + 工具清单」直接注入
  MetaAgent 拿到 meta-marketing-api-expert 的 manifest
        │ 让 LLM 按 Skill 指导调用工具
        ▼
  动态选择 meta_* 工具执行
```

#### 3.10.2 Skill⇄Skill 能力映射表

| 本系统 Skill | 对接的现有 Expert Skill | 复用的工具/能力 |
|--------------|-------------------------|-----------------|
| platform agent (google) | google-ads-api-expert | google_list_campaigns / google_create_campaign / google_update_bid / google_download_report |
| platform agent (meta) | meta-marketing-api-expert | meta_create_adset / meta_send_capi / meta_list_audiences / meta_query_insights |
| platform agent (tiktok) | tiktok-ads-expert | tiktok_create_campaign / tiktok_create_adgroup / tiktok_track_pixel |
| platform agent (dv360) | dv360-expert | dv360 io / line item / creative 管理、报表查询 |
| universal tools | ad-platform-tools (30+ 通用工具) | auth / sync / report / track 通用能力 |

#### 3.10.3 对接注册示例

```python
# 把现有 Skill 的 manifest 注册进 SkillRegistry
from types import SimpleNamespace

def wrap_expert_skill(expert_skill):
    # expert_skill 提供: name, capabilities, tools
    return SimpleNamespace(
        name=expert_skill["name"],
        platform=expert_skill.get("platform"),
        category=expert_skill.get("category", "platform"),
        tools=expert_skill["tools"],
        execute=lambda task: expert_skill["call"](task),
    )

registry.register(wrap_expert_skill(load("google-ads-api-expert")))
registry.register(wrap_expert_skill(load("meta-marketing-api-expert")))
registry.register(wrap_expert_skill(load("tiktok-ads-expert")))
registry.register(wrap_expert_skill(load("dv360-expert")))
```

#### 3.10.4 建议的落地适配层

知识库脚本 `ad_platform_api.py` 已经实现了各平台大量工具（`tiktok_*` / `meta_*` / `google_*`），这些正好可以做 PlatformPort 实现的底层。推荐演进：

```
现有 ad_platform_api.py 的 xxx_* 方法
   │ (包一层)
PlatformPort 实现 impl_*.py  (补上错误/限流/幂等归一化)
   │ (暴露统一契约)
Agent 的 SkillExecutor 通过 PlatformPort 调用
   │
Skill 对接：ad-platform-tools + 各 expert skill manifest
```

---

## 四、常见问题与排查

### 4.1 平台金额换算错误

**现象**：跨平台预算对比差了 100 倍 / 1000000 倍；Google 预算写了但 TikTok 花超。

**原因**：各家金额单位不同（Google micros / Meta 分 / TikTok 分 / DV360 美元），没在适配器统一换算。

**排查**：
1. 检查是否统一用 micros 作为内部单位；
2. 检查适配器入口/出口换算系数：
   - Google：天然 micros，勿再乘；
   - Meta：读 `spend*1e6`，写 `micros//1e4`；
   - TikTok：读/写都除以/乘以小单位系数；
   - DV360：确认是美元还是 micros。
3. 用「基准测���」：对每个平台写一个 $1 预算的对照 Case，验证读回是否一致。

**修复**：在 PlatformPort 边界统一 `to_micros()` / `from_micros()`，禁止上层直接接触单位。

### 4.2 多个 Agent 同时改预算导致抖动/超支

**现象**：BudgetArbiter 记录显示一小时改了 8 次预算，最终超支或来回抖动。

**原因**：缺少冷却窗口 / 分布式锁 / 仲裁。

**排查**：
1. 查 `agent_events` 中同一 campaign_key 的 `budget.updated` 时间戳密度；
2. 查是否有两个循环（RoasAgent + BudgetArbiter）并发写同一实体；
3. 检查 `guard_cooldown` 是否配置了足够冷却期。

**修复**：
1. 同实体写加分布式锁（Redlock）；
2. 加冷却窗口（默认 5 分钟）；
3. 预算变更统一走 BudgetArbiter 仲裁；
4. 加「最小变更阈值」：提升量 <5% 直接忽略，避免无意义抖动。

### 4.3 限流被反复打爆 / 重试风暴

**现象**：平台返回大量 429 / quota 超限，日志里重试一串失败。

**原因**：没有统一限流器和退避抖动；重试没有最大次数。

**排查**：
1. 查 `platform_rate_limited_total` 指标；
2. 确认限流器 `TokenBucket` 是否按平台正确配置 rpm；
3. 检查熔断器是否已触发（Circuit open）。

**修复**：
1. 每个平台独立令牌桶限流；
2. 指数退避 + 随机抖动 + 最大重试（4 次）；
3. 加熔断器防止雪崩；
4. 对可降级操作降级为「只读 / 延迟」。

### 4.4 事故后恢复不一致（本地状态 ≠ 平台状态）

**现象**：进程崩溃重启后，本地 campaign_states 与平台实际状态不符（如本地 ACTIVE 但平台已 PAUSED）。

**原因**：切换只在本地，未同步平台；或平台侧被外部手动改了。

**排查**：
1. 走 `recover_campaign` 对账流程对比 snapshot 与 remote；
2. 查看 `status_remote` 与 `state` 差异；
3. 查 agent_events 中最后一次成功写平台的记录。

**修复**：
1. 状态以「本地 state = 权威」，`status_remote` 冗余；
2. 每次动作后强制对账；
3. 事件溯源重放，从最终一致恢复；
4. 定期（每小时）对活跃 Campaign 做全量对账，发现漂移自动修正并告警。

### 4.5 模糊重复创建 Campaign

**现象**：重试后平台出现两个同名 Campaign。

**原因**：平台不支持服务端幂等，重试未带 idempotency key / 未查重。

**排查**：
1. 查 `agent_events` 里同 `trace_id` 多次 `create_campaign`；
2. 查平台后台同名 Campaign 数量。

**修复**：
1. 生成并传递 `idempotency_key`（`make_idem_key`）；
2. 创建前先按 name + idem_key 在 idempotency store 查重；
3. 创建后立即记录 platform_id 到快照，重试先查库而非再创建。

### 4.6 向量记忆检索到过期/错误经验

**现象**：反思常被陈旧经验误导（如沿用已失效的定位策略）。

**原因**：语义记忆无时效衰减、无置信评分。

**排查**：
1. 检查搜索结果的 payload 里 timestamp；
2. 检查是否有 TTL / 衰减机制。

**修复**：
1. 检索时按时间衰减权重（越新越高）；
2. 给记忆加置信度（来自 successful outcome 次数）；
3. 定期对低置信/过期反思做归档或淘汰。

### 4.7 审计信息缺失 / 不可解释

**现象**：出了问题时，查不出「为什么某 Campaign 被暂停」。

**原因**：动作没有记录 reason；事件被 UPDATE/DELETE。

**排查**：
1. 查 agent_events（不可变日志）中对应事件及其 reason；
2. 确认事件表未做 UPDATE/DELETE。

**修复**：
1. 每个动作强制写 reason 字段；
2. 事件表只追加（DB 权限禁止 UPDATE/DELETE）；
3. 所有关键操作走分级审批并留痕。

### 4.8 平台审核 / 素材被拒导致的投放中断

**现象**：某平台素材审核被拒，Campaign ��量。

**原因**：创意未做合规预检；未监控审核状态。

**排查**：
1. 查 `PENDING_APPROVAL → REJECTED` 状态迁移事件；
2. 查被拒素材的 reason。

**修复**：
1. SafetyGuardrails 在提交前做敏感词/合规预检；
2. 监控审核状态变化事件，被拒自动替换备用素材；
3. 素材池维护多个合规备选。

### 4.9 排查决策树（综合）

```
遇到投放异常
├─ 花费异常？
│   ├─ 超支 → 查 BudgetArbiter 与冷却日志；检查全局上限闸门
│   └─ 花费为0/掉量 → 查平台状态、素材审核、出价是否过低
├─ ROAS 异常？
│   ├─ 某平台骤降 → 查该平台该 Campaign 的 recent events + 归因
│   └─ 全平台降 → 查归因追踪、转化回传是否中断
├─ API 报错？
│   ├─ 429 → 查限流器与重试
│   ├─ auth → 查 token 刷新
│   └─ 校验错误 → 查参数归一化（金额/字段名）
├─ 状态不一致？
│   └─ 跑对账 recover_campaign + 看 status_remote
└─ 无法解释的动作？
    └─ 查 agent_events 的 reason + 审计
```

---

## 五、自测题

### 问题 1（概念）
**多平台广告投放 Agent 系统中，「编排器（Orchestrator）」和「平台专属 Agent（如 MetaAgent）」的核心职责边界是什么？为什么该系统采用「层级式为主」的编排拓扑？请说明跨平台预算分配为什么必须交给出「仲裁器」而非让各平台 Agent 自行决定。**

<details>
<summary>查看答案</summary>

**职责边界**：
- **Orchestrator**：唯一入口，负责任务分解、平台路由、调度、冲突仲裁、结果聚合、反思、人机协作。它不直接接触平台 API 细节。
- **平台专属 Agent**：只懂自己平台，面向 PlatformPort 统一契约，通过该平台的 Skill 执行具体操作（建站、改价、报表等），维护自己的短/长期记忆。

**层级式为主的原因**：层级式控制流清晰、单点仲裁容易避免冲突、调试链路好。广告场景中预算、ROAS 判断等是「全局决策」，若各平台 Agent 各自抢预算会互相打架，因此由集中式 Orchestrator + BudgetArbiter 统一决策。局部自治（如创意轮换）才用对等式。

**为什么预算分配交给仲裁器**：预算总量有限，多平台都想要钱，存在竞争。仲裁器基于优先级（P0 人工/风控 > P1 超支保护 > P2 ROAS 优化 > P3 测试）、平台权重、全局上限和并发锁统一裁决，保证「不超支、不抖动、优先级合理」，这是分散决策无法做到的。
</details>

### 问题 2（抽象层与单位）
**平台抽象层为什么必须统一金额单位为 micros？请给出 Google、Meta、TikTok、DV360 四家平台的金额单位差异，以及写入成本时各自的换算公式（micros→平台单位）。**

<details>
<summary>查看答案</summary>

**原因**：四家平台金额单位完全不同（Google 天然 micros、Meta 分/美元、TikTok 分、DV360 美元），若不统一，跨平台对比预算/成本极易算错（差 100 倍~1000000 倍），也会导致预算写错造成超支或无效投放。统一 micros 作为内部契约后，仅需在适配器边界换算，上层不变。

**单位差异与换算**（设 1 USD = 1_000_000 micros）：
- Google：天然 micros，无需换算，`写 micros`；
- Meta：写入 `daily_budget` 用分，`cents = micros // 10_000`；读取 `spend*1e6 → micros`；
- TikTok：写入用分（TikTok 币种小单位），按币种系数换算；读取同理；
- DV360：多数场景美元，`usd = micros // 1_000_000`；读取 `usd*1e6 → micros`。
统一原则：接口层一律 micros，仅 PlatformPort 实现内部做 `to_micros() / from_micros()`，上层禁止接触原始单位。
</details>

### 问题 3（记忆与恢复）
**Agent 记忆系统包含哪几种记忆形态？「事件日志（Event Log）」和「快照（Snapshot）」分别起什么作用？当一个 Campaign 本地状态与平台侧不一致时，恢复流程应如何处理？**

<details>
<summary>查看答案</summary>

**记忆形态**：Working Memory（工作记忆，Redis/内存，任务级）、Episodic Memory（情景记忆，关系库，中长期）、Semantic Memory（语义记忆，关系库/图，长期）、向量库（语义检索/RAG）。

**作用**：
- **事件日志**：不可变、只追加，记录「谁在何时做了什么、为什么」（含 reason），是溯源与审计的原料；支持事件溯源（event sourcing）。
- **快照**：某时刻实体完整状态拷贝（campaign_states + JSON snapshot + version），用于恢复与跨期回溯；配合乐观锁防并发覆盖。

**不一致恢复流程**（recover_campaign）：
1. 加载本地最新快照（权威）；
2. 拉取平台侧真实状态（remote）；
3. 对比，若一致直接使用；
4. 若不一致进入对账：本地未动平台也未动→不动；本地要动但未同步→推送；平台被外部改→以平台为准并记录差异事件；
5. 应用修正并记录审计事件。遵循「激动最小」原则，只在必要时修改。
</details>

### 问题 4（并发与防抖）
**描述「多 Agent 同时修改同一 Campaign 预算」这一冲突，并从防抖、分布式锁、仲裁三个层面说明如何避免。为什么还会需要「最小变更阈值」？**

<details>
<summary>查看答案</summary>

**冲突**：多个 Agent（如 RoasAgent 和 BudgetArbiter）或多轮循环可能并发写同一 AdSet 的 daily_budget，导致抖动、写覆盖、超支。

**三层防护**：
1. **防抖（Debounce）**：对同一实体+动作加冷却窗口（Redis `cooldown:{entity}:{action}`，默认 300s），冷却期内重复请求直接拒绝；
2. **分布式锁（Distributed Lock）**：真正串行化同一实体写（Redlock + 乐观版本号 + token 校验释放，防误删他人锁）；
3. **仲裁（Arbiter）**：统一 BudgetArbiter 检查全局上限、平台配额、待处理写、冷却状态，按优先级（P0>P1>P2>P3）裁决 grant/deny。

**最小变更阈值**：即使不加锁，若某次提升只有 1%~2%，对整个投放无实质影响却会引入抖动与 API 调用。设定「变更量 <5% 忽略」可过滤无意义的频繁微调，进一步抑制抖动，减少平台 API 压力和风险。
</details>

### 问题 5（生产与灰度）
**采用 CRUD 的真实资金系统为何必须引入「审计与合规」机制？请列举关键操作的分级（哪些可自动、哪些需人工）。「灰度上线」有哪些策略维度？影子模式的作用是什么？**

<details>
<summary>查看答案</summary>

**原因**：广告投放涉及真实资金，需要可解释性（每个自动操作要有 reason）、不可抵赖（事件只追加）、人机边界（关键操作人工把关），否则出了问题无法追责、无法回滚、会引发合规风险。

**关键操作分级**：
- 自动+无需审批：出价微调（±10%）、预算微调（±20%，经仲裁）；
- 自动+风控闸门：预算中等调整（BudgetArbiter）；
- 需人工审批：预算大调（>50%）、删除 Campaign、新建大投放；
- 自动但须审计：暂停 Campaign（通知+留痕）。
删除 Campaign 禁止自动。

**灰度策略维度**：按平台、按账户、按 Campaign、按流量百分比、影子模式。
**影子模式**：新逻辑「只决策、不真正写平台」，把其建议动作与现状/旧逻辑输出对比，验证差异符合预期后再放量。可避免直接上线对真实投放造成风险，且便于 A/B 验证新策略的有效性。
</details>

---

## 附录 A：常用速查表

### A.1 四大平台适配要点速查

| 平台 | 鉴权 | 金额 | 层级 | 限流 | 报表 | 实现库 |
|------|------|------|------|------|------|--------|
| Google Ads | OAuth2 refresh | micros | Campaign→AdGroup→Ad | developer token quota | GAQL search_stream | google-ads Python / Go |
| Meta | 长期 access_token | 分/美元 | Campaign→AdSet→Ad | app 速率 | Insights | facebook_business |
| TikTok | Access-Token header | 分 | Campaign→AdGroup→Ad | advertiser 配额 | report/get | requests |
| DV360 | Service Account JWT | 美元 | Partner→Adv→Camp→IO→LI | API 速率 | async query+POLL | googleapiclient displayvideo |

### A.2 状态机合法迁移速查

```
DRAFT → PLANNED → PENDING_APPROVAL → ACTIVE
                                  ↘ REJECTED
ACTIVE ↔ PAUSED （可互相切换）
ACTIVE / PAUSED / REJECTED → REMOVED
```

### A.3 常用事件类型速查

| event_type | 含义 |
|------------|------|
| goal.created / updated / completed | 目标生命周期 |
| task.assigned / result / failed | 任务生命周期 |
| campaign.created / paused / resumed / removed | Campaign 状态 |
| budget.updated / bid.updated | 预算/出价变更 |
| metric.cpa-spike / roas-drop | 指标异常 |
| conflict.request / granted / denied | 冲突仲裁 |
| reflection.recorded | 反思写入 |

---

> 本指南为「多平台广告投放 Agent 系统」深度架构文档，覆盖 Multi-Agent 编排、平台抽象层、记忆系统、Skill 系统与生产级参考实现。配套可参考知识库 `ad_platform_api.py` 脚本与 `ad-platform-tools`、`google-ads-api-expert`、`meta-marketing-api-expert`、`tiktok-ads-expert`、`dv360-expert` 等 Skills。
