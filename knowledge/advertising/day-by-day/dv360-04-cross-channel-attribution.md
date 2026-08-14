# 跨渠道归因与测量（Day 4）

> **领域**: 广告投放 / 归因与测量
> **深度**: ⭐⭐⭐⭐⭐ 实战级指南
> **标签**: dv360, attribution, floodlight, measurement, cross-channel
> **更新时间**: 2026-08-14
> **类型**: 学习笔记

---

## 📌 今日学习重点

今天我们深入 DV360 的**跨渠道归因与测量**体系。归因（Attribution）回答一个根本问题：**当用户在多个渠道、多个设备上多次接触广告后终于转化，这一次转化应该"算给谁"、分几成？**

核心结论先行：
1. **Floodlight 是整个归因体系的"地基"** —— 没有统一的转化埋点，一切归因模型都是空中楼阁。
2. **归因模型没有绝对正确** —— last-click 简单粗暴但口径稳定，data-driven 最接近真实但需要大量转化数据支撑。
3. **跨渠道 ≠ 跨平台** —— DV360 的跨渠道归因发生在 GMP 生态内（DV360 + CM360 + GA360 + SA360），跨到 Meta/TikTok 只能靠**统一用户 ID 或广告主自建 CDP** 手动对齐。

先读的文档里 `dv360-measurement-attribution-deep.md` 讲了归因模型总览与 Go 生产实现，`dv360-architecture-deep.md` 的第六章讲了测量与归因概览。本笔记**不再重复模型总览表**，而是聚焦 **Floodlight 埋点真实结构、转化回传数据流、API 拉取转化报表、以及跨渠道数据打通的生产级踩坑**。

---

## 一、核心概念与架构

### 1.1 跨渠道归因在 GMP 中的位置

Google Marketing Platform（GMP）是一个"全家桶"。归因这件事不是 DV360 单独干的，而是整个 GMP 协作的产物：

```
Google Marketing Platform (GMP) 全家桶的归因协作

                       ┌──────────────────────────────┐
                       │      Campaign Manager 360    │
                       │   (CM360) 广告追踪/服务端归因   │
                       │   Floodlight 埋点与转化接收入口  │
                       └───────────────┬──────────────┘
                                       │  Floodlight 转化数据(回传)
         ┌─────────────────────────────┼──────────────────────────┐
         │                             │                          │
   ┌─────▼───────┐             ┌───────▼────────┐        ┌────────▼────────┐
   │   DV360     │             │   SA360        │        │   GA360        │
   │  展示/视频   │◄────────────┤  搜索           │        │  全量分析/行为   │
   │  媒体购买    │             │  Search Ads    │        │  Google Analytics│
   └─────┬───────┘             └───────┬────────┘        └────────┬────────┘
         │                             │                          │
         └───────────────┬─────────────┴──────────────────────────┘
                         ▼
              ┌──────────────────────┐
              │   Google 数据驱动归因   │
              │  (DDA / MCF 数据)      │
              │  集成到 DV360 出价优化   │
              └──────────────────────┘
```

**关键理解**：DV360 不自己收集转化。转化由 **CM360 的 Floodlight** 统一收集并打上（channel, source, campaign, creative…）的归因维度，然后：
- 回传给你配置了 vsCM 参数的 DSP（如 DV360 自己）；
- 写给 GA/GA360 做交叉分析；
- 喂给 Google 的数据驱动归因（Data-Driven Attribution）计算每个触点的贡献度；
- 再把这些"贡献度"用回 DV360 的自动出价（value-based bidding / tCPA）优化买量。

### 1.2 什么是 Floodlight

Floodlight 是 CM360 的**转化与活动追踪系统**，是跨渠道归因数据的统一采集层。一个 Floodlight 埋点由三个层次组成：

```
Floodlight 埋点结构
├── Floodlight 配置 (Floodlight Configuration)
│   ├── 归因窗口 (lookback window)
│   ├── 计数方法 (Counting Method: Sessions / Standard / Unique)
│   ├── 转化是否计入出价优化 (用于 DV360 bidding)
│   └── 关联的 CM360 AD (活动) 与活动组
├── Floodlight 活动 (Floodlight Activity)
│   ├── activityId (唯一 ID, 如 vcarn2)
│   ├── activityTagString (如 dv360_purchase 这种可读名字)
│   ├── activityType (如 TRANSACTION / COUNTER)
│   ├── countingMethod (SESSION / STANDARD / UNIQUE)
│   ├── floodlightConfigurationId
│   └── 指定回传对象 (回传 DV360 的 advertiserId 与
│       cm360 placement / ad 映射)
└── 网站/App 上的具体 Tag (Google Tag / event snippet)
    ├── aw / flu 参数
    ├── u1~u5 用户自定义变量 (自定义维度)
    └── qty / cost / ord (数量 / 价值 / 去重 ID)
```

> **一句话总结**：Floodlight 配置是"全局归因规则"，Floodlight 活动是"一个个具体转化事件"，Tag 是"网站上实际触发的那段 JS"。

### 1.3 跨媒体（Cross-Media）数据打通架构

真正意义上的"跨渠道归因"依赖**数据打通**。有三条路线，从浅到深：

```
跨渠道数据打通的三条路线 (由浅到深)

路线A：GMP 内生态归因(默认, 最省事)
  DV360 + SA360 + GA360 + CM360
  ├── 共享 Floodlight 转化数据
  ├── 共享 Google 账号 ID (cookies / mobile ads id)
  ├── Google 数据驱动归因自动计算
  └── 优点: 零开发; 缺点: 覆盖不到 Meta/TikTok

路线B：广告主自建数据中台 (CDP/DMP)
  各平台 (DV360/Meta/TikTok/SA360) 通过 s2s 回传
  ├── Splunk / BigQuery / Snowflake 统一存储
  ├── 用统一用户ID (登录邮箱哈希 / 手机号) 做 ID 解析与拼接
  ├── 自建归因引擎 (参考上一篇的 Go 归因引擎) 统一打分
  └── 优点: 全渠道统一; 缺点: 工作量大, 需数据治理

路线C：清洁室 / 广告主数据云 (ADS Data Hub)
  Google Ads Data Hub (ADH) 结合加密 Click/Impression 日志
  ├── 在隐私沙盒内做跨平台去重与归因
  ├── 输出聚合分析, 不暴露单用户
  └── 未来 cookie 消亡后的主要方向
```

### 1.4 归因数据在 DV360 报表面板中的闭环

有了 Floodlight 埋点后，DV360 的报表与出价依赖这条闭环：

```
埋点 → 回传 → 归因 → 报表 → 出价 (闭环)

  用户访问落地页触发 Floodlight Tag
       │
       ▼
  Floodlight activity 打点 (含 u1~u5 自定义维度、转化价值 cost)
       │
       ▼
  CM360 接收转化, 按归因窗口/计数方法去重
       │
       ▼
  转化写回 DV360 (通过 advertiserId 关联)
       │
       ├──▶ 报表: dv360_get_report(...) 拉转化/Floodlight 维度
       ├──▶ 维度: dv360_list_dimension_values("FLOODLIGHT_ACTIVITY", ...)
       └──▶ 出价: 转化价值回传给 bidding, 驱动 tCPA/value bidding
```

**本节小结（架构层面你要记住的 3 件事）**：
1. Floodlight 是 GMP 归因的唯一数据源，建在 CM360，DV360 只是消费者。
2. 跨渠道归因的"渠道"在 GMP 内部是原生打通的；跨到外部平台要靠自建 CDP 或清洁室。
3. 归因结果不仅用于"看数字"，更会**喂回出价系统**，所以埋点质量直接决定买量模型准不准。

---

## 二、深度原理解析

### 2.1 归因模型的数学原理与公式对比

归因本质上是一个**信用（credit）分配问题**：给定一条转化路径（一串结构化触点），把转化价值（或"1 次转化"）按某种规则分给路径上的每个触点（渠道 / 广告系列 / 创意）。

我们用一套统一符号来写公式：

```
记号约定
  n       = 转化路径上的触点数量
  i       = 触点下标, i = 1..n (按时间从早到晚)
  t_i     = 第 i 个触点的发生时间
  t_conv  = 转化发生时间
  w_i     = 第 i 个触点获得的权重 (归一化后 Σw_i = 1)
  V       = 转化价值 (value), 或直接取 1 代表"一次转化"
  attrib_i = 分给第 i 个触点的信用 = V * w_i
```

#### (1) Last Click（最后点击）
只保留路径上最后一个触点，其余全部为 0：

```
w_i = { 1,  i == n
        0,  i != n }
```

优点：简单、口径稳定、可复现；缺点：完全无视前置触点，天然低估品牌/展示/视频等上层渠道。

#### (2) First Click（首次点击）
与 last click 对称，第一个触点拿到全部：

```
w_i = { 1,  i == 1
        0,  i != 1 }
```

优点：强调"获客"价值；缺点：无视临门一脚，高估曝光型渠道。

#### (3) Linear（线性）
均匀分配：

```
w_i = 1 / n   (对任意 i)
```

优点：公平；缺点：不区分触点重要性，稀释了真正关键的触点。

#### (4) Time Decay（时间衰减）
越接近转化的触点权重越高，典型实现是指数/半衰期衰减：

```
w_i ∝ exp(-λ · (t_conv - t_i))       （指数形式）
w_i ∝ 0.5 ^ ((t_conv - t_i) / halfLife)  （半衰期形式, 更直观）
```

然后归一化：`w_i = raw_i / Σ raw_j`。半衰期参数 `halfLife` 控制衰减快慢——不管是 1 小时还是 7 天，取决于品类决策周期。

#### (5) Position Based / U 型（首尾加权）
首尾各拿大份，中间平分：

```
w_1   = 0.4
w_n   = 0.4
w_i   = 0.2 / (n - 2)   (1 < i < n, 当 n >= 3)
当 n == 1: w_1 = 1
当 n == 2: w_1 = w_2 = 0.5
```

适合"品牌触达 + 效果转化"兼顾的路径。

#### (6) Data-Driven（数据驱动，DDA）
不用固定权重公式，而是用**历史转化路径数据训练一个模型**，估计每个触点对转化的"边际贡献"。本质是估计条件概率：

```
设 y = 是否转化, X_i = 第 i 个触点是否出现 (0/1)
利用历史数据拟合 P(y=1 | X)
第 i 个触点贡献 ∝ 该触点存在时转化概率的提升
  ΔP_i = P(y=1 | X_i=1) - P(y=1 | X_i 被移除后的基线)
```

Shapley 值是理论依据之一：它公平分配"合作博弈"中每个参与者的边际贡献。Google 的 DDA 需要每个转化路径月数据量 **≥ 1000 转化** 才有统计意义，且会每周自动重新训练。

**模型对比速查表（本笔记的核心表格）**：

| 模型 | 数学形式 | 权重分布特征 | 优点 | 缺点 | 适用场景 |
|------|----------|--------------|------|------|----------|
| Last Click | 最后触点=1 | 极端(独吞) | 简单/口径稳 | 忽视上层漏斗 | 效果广告、转化路径短 |
| First Click | 首触点=1 | 极端(独吞) | 重视获客 | 忽视转化触点 | 首次获客评估 |
| Linear | 1/n | 均分 | 公平 | 稀释关键触点 | 全链路粗略盘点 |
| Time Decay | 指数/半衰期 | 渐近 | 重视近期 | 忽视首次触达 | 短决策周期、促销 |
| Position Based | 首尾0.4/中0.2 | 首尾重 | 平衡品牌+转化 | 比例固定死板 | 品牌+效果混合 |
| Data-Driven | 统计模型+Shapley | 数据学习 | 最贴近真实 | 需海量数据/黑盒 | 转化量大、优化出价 |

### 2.2 跨设备 / 跨渠道归因（Google 数据驱动归因）

Google 的数据驱动归因不止看"渠道之间的先后"，还会在**去重用户**（Unified ID / 登录态）与**跨设备**层面做处理：

```
跨设备归因的数据来源
├── Google 账号登录态 (最强信号, 用户未登出)
├── Google 信号 (广告个性化, 需用户授权)
├── 移动设备广告 ID (GAID / IDFA, 日渐受限)
├── Cookie (First-party 为主, third-party 走向消亡)
└── 离线 / 确定性匹配 (广告主上传 CRM 哈希)

归因窗口 (Lookback Window) 常见配置
├── 点击归因窗口: 默认 30 天 (可 1~90 天)
├── 浏览归因窗口 (View-through): 默认 1 天 (可最 7 天)
└── 转化计数: 每次转化独立 / 按会话去重 / 唯一转化
```

**重要概念区分**：
- **跨设备（Cross-device）**：同一用户手机 + 平板 + 电脑的触点拼接，靠登录态 / ID。
- **跨渠道（Cross-channel）**：展示 / 视频 / 搜索 / 社交 / 直接访问多条路径的归因。
- **GA360 的多渠道漏斗（MCF）**：从"用户行为数据（GA360）"角度做归因；**CM360 的 Floodlight**：从"广告投放数据"角度做归因。两者数据源不同，数字天然不一样——这是生产环境最大的口径冲突点之一。

### 2.3 Floodlight 活动设计与转化回传数据流

设计 Floodlight 活动时，要对齐"计数方法"和"归因窗口"，这直接决定转化数字的算法：

| 计数方法 (countingMethod) | 行为 | 适用 |
|---------------------------|------|------|
| SESSION | 同一会话内多次触发只算 1 次 | 通用网页转化 |
| STANDARD | 每次触发都计 1 次 | 多步漏斗、每次事件 |
| UNIQUE | 同一用户全程只计 1 次 | 留资、注册 |

**转化回传（vsCM）数据流**——这是 DV360 能否拿到转化的关键机制：

```
Floodlight 转化回传 DV360 的链路
   用户完成转化
       │
       ▼
  Floodlight Tag 触发 (前端 JS 或 GTM 上的 Google Tag)
       │
       ▼
  浏览器/App 向 DoubleClick (CM360) 发起请求
     URL 形如:
     https://ad.doubleclick.net/ddm/activity/src=xxx;type=yyy;cat=zzz;
          u1=自定义维度1;u2=自定义维度2;qty=2;cost=99.0;ord=随机序号
       │
       ▼
  CM360 接收, 生成转化记录(含点击/展示对应关系)
       │
       ├──▶ 回传给 DV360 (通过 floodlight 关联的 advertiserId / bidder)
       ├──▶ 回传给 SA360 / GA360
       └──▶ 写入 BigQuery / 报表
```

**去重（de-dup）**的 `ord` 参数非常关键：每次会话生成一个唯一 `ord=`，CM360 只会计数第一次收到该 ord 的请求，用于防止重复计数（如用户刷新页面 / 多次触发 tag）。

### 2.4 DV360 归因与报表指标口径

DV360 报表里的转化指标口径需要仔细分清，新手最容易混：

| 指标 | CM360/GA 侧含义 | DV360 报表注意点 |
|------|------------------|------------------|
| Conversions | 归因到 DV360 的转化次数 | 取决于归因窗口与计数方法 |
| Floodlight 转化 | Floodlight activity 原始计数 | DV360 报表里按 "Floodlight 转化" 维度拆 |
| View-through conv | 展示后(未点击)归因转化 | 依赖浏览窗口设置, 口径最易吵 |
| Click-through conv | 点击后归因转化 | 更稳定, 常用于核对 |
| Revenue / Value | 转化价值(cost 参数) | 精确到会受 currency 与去重影响 |
| Floodlight 覆盖率 | 有埋点的转化/全部 | 覆盖率低说明埋点缺失, 归因失真 |

**坑**：DV360 报表里的转化数 ≠ CM360 报表里的转化数 ≠ GA360/GA4 里的转化数。原因：归因窗口、计数方法、去重逻辑、是否含 view-through 都不同。生产环境一定以**某一平台为准**并文档化，不能拿三个数字互相质问。

### 2.5 Python 拉取转化报表（Floodlight 维度）

我们可以用工坊里封装的 API 客户端拉取带 Floodlight 维度的转化报表。核心方法：

- `dv360_list_floodlight_configs(advertiser_id)` —— 列出广告主下的 Floodlight 配置，拿到配置结构。
- `dv360_get_report(advertiser_id, ...)` —— 生成报表，可指定维度与指标。
- `dv360_get_report_metrics(advertiser_id)` —— 拉取报表指标定义，确认指标名称。
- `dv360_list_dimension_values("FLOODLIGHT_ACTIVITY", ...)` —— 列出某个维度的可选值（这里是 Floodlight 活动）。

```python
# 伪代码: 用工坊脚本拉取带 Floodlight 维度的转化报表
from ad_platform_api import AdPlatformClient

client = AdPlatformClient()
ADVERTISER_ID = "4659631"   # 示例广告主 ID

# 1) 先看这个广告主配了哪些 Floodlight 配置
configs = client.dv360_list_floodlight_configs(advertiser_id=ADVERTISER_ID)
for cfg in configs:
    print("配置ID:", cfg.get("floodlightConfigurationId"),
          "| 名称:", cfg.get("name"),
          "| 标签前缀:", cfg.get("floodlightTagId"))

# 2) 拉取带 Floodlight 活动维度的转化/价值报表
report = client.dv360_get_report(
    advertiser_id=ADVERTISER_ID,
    dimensions=["FLOODLIGHT_ACTIVITY", "DATE"],   # Floodlight 活动 x 日期
    metrics=["IMPRESSIONS", "CLICKS", "TOTAL_CONVERSIONS",
             "REVENUE", "MEDIA_COST", "ROAS"],
    date_range={"start": "2026-08-01", "end": "2026-08-14"},
    level="ADVERTISER"
)
for row in report.get("rows", []):
    print(row)

# 3) 如果想确认某个指标名字准不准确, 先拉指标定义
metrics = client.dv360_get_report_metrics(advertiser_id=ADVERTISER_ID)
for m in metrics:
    if "CONVERSION" in m.get("name", "").upper():
        print(m.get("name"))

# 4) 枚举该维度的合法取值 (Floodlight 活动列表)
activities = client.dv360_list_dimension_values(
    dimension="FLOODLIGHT_ACTIVITY",
    advertiser_id=ADVERTISER_ID
)
for a in activities:
    print(a.get("value"), "->", a.get("displayName"))
```

`DV360Client`（`dv360_api.py`）里还有 `get_report(advertiser_id, date_start, date_end, level, dimensions)` 与 `get_transaction_type_options()` 可用于更底层的报表与交易类型说明。

---

## 三、生产环境实战

### 3.1 搭建跨渠道归因埋点案例（Floodlight 是关键）

下面是从零搭建一次"电商 App 购买"跨渠道归因的完整落地步骤。**再次强调：Floodlight 是 key**，没有它，DV360 拿不到转化，后面所有归因和出价优化都无从谈起。

#### 场景
某跨境电商，在 DV360（展示/视频）、SA360（搜索）、GA360（站内行为）三处投放，目标是用统一归因衡量"App 内购买"。

#### 步骤一：规划 Floodlight 活动清单

先决定要埋哪些转化点。不要一上来就埋几十个，**按转化漏斗分层**：

| Floodlight 活动 | activityType | countingMethod | 说明 |
|-----------------|--------------|----------------|------|
| 首页浏览 | COUNTER | SESSION | 上层漏斗, 用于蓄水池分析 |
| 搜索/查看商品 | COUNTER | SESSION | 中层 |
| 加购 Add to Cart | TRANSACTION | SESSION | 转化意向, 带价值 |
| 下单 Checkout | TRANSACTION | STANDARD | 关键转化 |
| 支付完成 Purchase | TRANSACTION | UNIQUE | 决定性转化, 回传出价 |

#### 步骤二：配置 Floodlight 归因窗口与计数方法

在 CM360 的 Floodlight 配置层面：
- **点击归因窗口**：电商建议 30 天（决策周期较久）。
- **浏览归因窗口**：默认 1 天即可，别开 7 天，否则 view-through 转化口径会失真且难解释。
- **计数方法**：购买（Purchase）建议 UNIQUE，防重复付款/重复刷新计数。

#### 步骤三：埋点（GTM / Google Tag 事件 snippet）

用 Google Tag Manager 埋 Global Site Tag + Floodlight event snippet：

```html
<!-- 支付完成页触发, 通过 GTM 的自定义 HTML Tag -->
<script>
  window.google_conversion_floodlight_id = 1234567890;      // CM360 activity id
  window.google_conversion_floodlight_group = 'purchase';    // 活动组
  window.google_custom_params = {
    'u1': 'campaign_A',    // 自定义维度: 活动分组
    'u2': 'ios',           // 自定义维度: 设备
    'u3': 'returning',     // 自定义维度: 新老客
    'qty': '1',            // 数量
    'cost': '129.90'       // 转化价值
  };
</script>
<script src="//www.googleadservices.com/pagead/conversion_async.js"
        async></script>
```

> 生产坑：`u1~u5` 是**自定义变量**，必须先在 CM360 里定义好字段名，否则数据进不来；`cost` 决定归因价值与 ROAS，务必在服务端用可靠金额填充，别用前端可篡改的值。

#### 步骤四：服务端回传（server-to-server）提升准确性

前端点击丢失（广告拦截、Safari ITP、App 内 webview）时，前端埋点会漏。更稳的方式是**服务端回传**：支付服务确认订单后，在服务端向 CM360 floodlight 端点回传一条转化记录，带上 `ord`、`cost`、`u1~u5`、以及关联的 clickId（`gclid` / `dclid` / 第三方点击 ID）。这样即使前端 tag 被拦截，转化一样能被归因。

### 3.2 多平台数据合并归因（GMP 内 + 外部平台）

#### 场景 A：GMP 内三平台合并
DV360 + SA360 + GA360 天然共享 Floodlight 转化与 Google 数据驱动归因，**不需要自己拼**。你要做的只是：
1. 确认三个产品都在**同一 CM360 Floodlight 配置**下。
2. 在 DV360 里开启"使用 Google 数据驱动归因"（转化量达标后自动可用）。
3. 开启"价值自动出价"（value-based bidding），让归因贡献度直接驱动出价。

```
GMP 内自动合并归因
  Floodlight 转化库 (CM360)
        │
        ├── DV360 媒体 → 归因贡献度 → 自动出价
        ├── SA360  搜索 → 归因贡献度 → 自动出价
        └── GA360  行为 → 漏斗/路径分析 (MCF)
```

#### 场景 B：合并 DV360 + Meta + TikTok（需要自建 CDP）
这三个平台互不共享转化。生产做法是把三方数据抽到统一数仓：

1. **统一 ID 关联**：用登录邮箱哈希 / 手机号哈希作 join key。DV360/GA360 侧拿 "user-id"(不含 PII 的桶)，Meta 侧 CAID / 转化 API（CAPI）回传同一哈希。
2. **统一时间与去重**：以 UTC 为准统一时间戳；用转化订单号做跨平台去重（同一订单在三方各记一次，必须只留一次）。
3. **统一归因引擎**：把三方回传的触点序列合并成"统一转化路径"，再用自建归因引擎（见 `dv360-measurement-attribution-deep.md` 的 Go 引擎）统一打分。
4. **口径文档化**：明确"官方报表是 last-click、自建 CDP 是 DDA"，别混用。

```python
# 伪代码: 三方转化去重与合并 (按订单号)
def merge_conversions(rows):
    dedup = {}
    for r in rows:                     # rows 来自 DV360/Meta/TikTok 报表
        key = r["platform"] + ":" + r["order_id"]
        if key not in dedup or r["event_time"] < dedup[key]["event_time"]:
            dedup[key] = r            # 同一订单只保留最早到达的一条
    return list(dedup.values())
```

### 3.3 最佳实践清单

| 实践 | 说明 |
|------|------|
| 埋点先在测试环境验证 | 用 DV360 报表 / CM360 预览确认 tag 触达 |
| 用唯一 ord 防重复 | SESSION/UNIQUE 计数 + ord 双保险 |
| 统一归因窗口 | 全团队约定同一 click/view window, 避免口径打架 |
| 每季度核对三方数字 | 挑一阶段手工核对 GA360 vs DV360 vs 内部数仓 |
| 埋点版本化 | 埋点改动走发布流程, 保留历史版本, 避免口径突变 |
| 为出价只回传"高质量转化" | 给 DV360 回传 purchase 而非所有事件, 否则破坏 tCPA |
| 监控 Floodlight 覆盖率 | 覆盖 <90% 时先查埋点缺失再谈归因 |
| 保留原始点击/展示日志 | 归因可追溯时回放验证 (ADH 或 BigQuery) |

### 3.4 生产踩坑实录（这些都是血泪教训）

**踩坑 1：Floodlight 埋点缺失导致转化追不上**
- 现象：某活动 DV360 报表转化量骤降。
- 排查：先查 Floodlight 覆盖率 —— 结果发现新版落地页换了 URL，旧的 GTM tag 没跟着部署上去，埋点直接没了。
- 解决：加"埋点监控"：用服务端回传兜底 + 每日检查覆盖率 + 快照告警。
- 口诀：**转化追不上，先查埋点，再谈归因。**

**踩坑 2：view-through 口径冲突**
- 现象：CM360 报 120 转化，GA360 报 250 转化，销售拿 250 质问媒体。
- 原因：GA 默认把 view-through 和"直接访问"也计进来，且窗口/计数不同。
- 解决：明确"媒体归因口径"限定为 click-through + 固定 30 天窗口，文档写入日报口径说明。
- 口诀：**三个平台三套数，先定口径再对比。**

**踩坑 3：归因重复计算（一单算两遍）**
- 现象：做了 A/B 版本埋点，两个版本都触发 purchase tag。
- 原因：新旧两套 tag 同时线上，缺少统一 `ord` 或 UNIQUE 计数。
- 解决：砍掉旧 tag，统一用 UNIQUE 计数 + 服务端唯一 ord。
- 口诀：**重复计数八成是埋点重复或缺少去重。**

**踩坑 4：数据对不上墙（点击归因 vs 展示归因）**
- 现象：同一波展示，报表里 view-through 转化忽高忽低。
- 原因：浏览器清除 cookie / IDFA 限额导致归因匹配率波动。
- 解决：用**去重用户**归因 + 服务端回传补充，理解"波动是匹配率问题而非效果真下降"。

**踩坑 5：出价模型被脏转化带偏**
- 现象：开了 tCPA 后成本起飞。
- 原因：把"加购"也回传给出价，模型把加购当购买优化。
- 解决：出价只回传 purchase（高价值转化），分析报表里才看加购。
- 口诀：**喂给出价的转化要和"真正赚钱"的转化严格一致。**

---

## 四、常见问题与排查

### 4.1 FAQ 速查

**Q1：为什么 DV360 报表里的转化数总是比想象中少/追不上？**

排查顺序永远是"埋点 → 覆盖率 → 归因窗口 → 计数方法 → 报表口径"：

```
转化追不上排查流程
 1. Floodlight 覆盖率 < 90% ? ──是──▶ 查埋点缺失/新页面没部署tag
 2. 归因窗口设太短 ?           ──是──▶ 拉长 click window (如30天)
 3. 计数方法对不对 ?           ──是──▶ 确认 UNIQUE/SESSION/STANDARD
 4. 是否漏 view-through ?       ──是──▶ 确认浏览窗口与统计口径
 5. 三方报表口径不同 ?          ──是──▶ 以一方为准并文档化
 6. 都正常仍少 ?              ──▶  查是否被广告拦截/匹配率波动
```

**Q2：归因重复计算怎么办？**

| 根因 | 解法 |
|------|------|
| 新旧两套 tag 重复触发 | 只保留一套 tag, 走发布流程下线旧版 |
| 缺少去重 | 统一生成唯一 `ord`, 会话级/用户级 |
| 计数方法选错 | purchase 用 UNIQUE, 避免每次触发都计 |
| 多平台各记一次 | 用订单号在自建 CDP 去重 |

**Q3：归因窗口（lookback window）该怎么设？**

| 品类 | 点击窗口建议 | 浏览窗口建议 |
|------|-------------|--------------|
| 快消/冲动消费 | 7~14 天 | 1 天 |
| 电商购物 | 30 天 | 1 天 |
| B2B / 高决策 | 60~90 天 | 7 天(谨慎) |

原则：决策周期越长窗口越长；浏览窗口别随意拉长，否则 view-through 口径失真又难解释。

**Q4：跨设备识别困难 / 归因匹配率低怎么办？**

- 依赖登录态（Google 账号）最强；
- 用服务端回传补充前端丢失（ITP / 广告拦截）；
- 移动端广告 ID（GAID/IDFA）受隐私限制，未来越来越难；
- 理解"匹配率波动是行业常态"，别把匹配率下降误判成效果下降。

**Q5：Data-Driven Attribution（DDA）为什么不可用或不稳定？**

| 条件 | 说明 |
|------|------|
| 转化量不足 | 需 ≥1000 转化/月, 否则用固定模型 |
| 路径太短 | 大量单触点路径, 模型学不到贡献差异 |
| 数据稀疏 | 某些渠道触点太少, 置信度低 |
| 模型每周重训 | 结果每周波动, 短期对比要小心 |

**Q6：DV360 出价用了归因价值，结果 CPA 失控？**

优先检查是否把"低价值事件"（加购/浏览）回传给了出价。出价应只吃"真正赚钱的转化"，过滤噪声，否则模型被带偏。

### 4.2 常见异常速查表

| 异常现象 | 最可能原因 | 首要排查动作 |
|----------|------------|--------------|
| 转化量为 0 | 埋点没触发 / tag 报错 | 用 CM360 预览 + 浏览器控制台验证 tag 触达 |
| 转化量暴跌 | 新版页面丢埋点 | 查 Floodlight 覆盖率, 检查新 URL |
| 转化翻倍 | tag 重复 / 重复计数 | 检查唯一 ord 与计数方法 |
| 三方数字打架 | 窗口/计数/口径不同 | 统一口径, 以一方为准 |
| view-through 忽高忽低 | 匹配率波动 / 浏览窗口 | 用去重用户+服务端回传补充 |
| ROAS 异常 | cost 字段被篡改/缺失 | 服务端可靠填充金额, 监控 value 分布 |
| 出价成本起飞 | 喂了脏转化给 bidding | 只回传 purchase 等高质量转化 |
| 归因与 GA 对不上 | 数据源不同(FA vs GA) | CM360 管广告归因, GA 管行为, 勿混 |

### 4.3 报表二次核对的最佳实践

```python
# 伪代码: 三方核对(内部数仓 vs DV360 vs GA360)
def reconcile_report(dw_rows, dv_rows, ga_rows):
    checks = []
    # 以内部数仓为 truth, 计算偏差
    checks.append(("DV360_conv_deviation",
                   dev(dv_rows.total_conv, dw_rows.total_conv)))
    checks.append(("GA360_conv_deviation",
                   dev(ga_rows.total_conv, dw_rows.total_conv)))
    # 偏差 > 5% 标红, 进入人工排查
    return [c for c in checks if abs(c["dev"]) > 0.05]
```

> 生产建议：**每月跑一次三方核对**，偏差超阈值立即排查。这能及早暴露埋点缺失、口径漂移等问题，避免月底对账时才发现。

### 4.4 一个完整的排障实战案例（时间线）

```
背景: 某电商 DV360 活动, 上周转化 800/天, 本周骤降至 200/天
DAY1 发现: 报表侧转化骤降, 但展示/点击正常(说明不是流量问题)
DAY2 初查: Floodlight 覆盖率从 93% 掉到 40% → 怀疑埋点缺失
DAY3 定位: 本周上线了新详情页, 新的 GTM 容器没包含 purchase tag
DAY4 修复: 为所有新页面部署统一 GTM 容器 + 加服务端回传兜底
DAY5 验证: 覆盖率回到 95%, 转化恢复; 复盘加入"部署检查清单"
```

**复盘要点**：流量正常、转化骤降 → 先怀疑**埋点/回传**，不要先去调归因模型或出价。等埋点修好、数据稳定后，再谈归因结论。

---

## 五、自测题

### 题 1：归因模型原理

一个用户转化路径为：展示(DV360) 第0天 → 视频(DV360) 第3天 → 搜索(SA360) 第9天 → 转化 第9天。
请问在 last-click、first-click、linear、time-decay、position-based 下，搜索渠道各拿到多少权重？（不考虑窗口裁剪）

<details>
<summary>查看答案</summary>

- **last-click**：搜索 = 1（最后一个触点独吞）。
- **first-click**：搜索 = 0（首触点展示拿 1）。
- **linear**：搜索 = 1/3（三个触点均分）。
- **time-decay**：转化当天与转化最近，`t_conv - t_搜索 ≈ 0`，故搜索权重**最大**（接近 1，其余按半衰期衰减后归一化）。
- **position-based**：首(展示)=0.4 / 末(搜索)=0.4 / 中间(视频)=0.2，搜索 = 0.4。

核心：**同一笔转化，不同模型给同一渠道的权重完全不同**，这就是为什么"选哪个模型"会在报表里造成巨大差异。

</details>

### 题 2：Floodlight 计数与去重

网站一用户点击广告进入落地页，提交表单成功后刷新页面 3 次，每次刷新都重复触发 purchase tag。若 countingMethod = STANDARD，CM360 会计几次？改用 UNIQUE 呢？

<details>
<summary>查看答案</summary>

- **STANDARD**：每次触发都计，刷新 3 次 → 计入多次（再加上首次共约 4 次，但若每次刷新 `ord` 不同会各自计数）。
- **UNIQUE**：同一用户全程只计 1 次。

因此 `purchase` 这类"决定成交"的事件建议用 **UNIQUE** 或用固定会话 `ord` 去重，防止刷新/重复提交污染转化数与出价模型。

</details>

### 题 3：跨渠道 vs 跨平台

"DV360 报表里的转化能覆盖到用户在 Meta 上的点击"这句话对吗？为什么？

<details>
<summary>查看答案</summary>

不对。DV360 的 Floodlight 只统计**归因到 DV360（GMP 生态）投放**的触点。Meta / TikTok 的点位不会自动进入 DV360 的归因，除非你建了自建 CDP 或清洁室，把 Meta/TikTok 转化回传到统一数仓后再统一归因。**MV 内部归因是"跨渠道"（展示/视频/搜索等 GMP 频道），不是"跨平台"（覆盖 Meta/TikTok）。**

</details>

### 题 4：归因窗口

某 B2B 产品决策周期 2~3 个月。若沿用 30 天点击窗口，会有什么后果？

<details>
<summary>查看答案</summary>

会把大量"研究期 >30 天"的真实转化判为**不受该投放影响**，导致：
- 转化数被低估，ROAS 被低估；
- 出价模型学不到长周期转化，价值出价失真。

建议把点击归因窗口调整到 **60~90 天**，并让 tCPA/value bidding 吃到这些转化。代价是"归因相对时效变慢"，需在报表中认可。

</details>

### 题 5：排障顺序

某活动展示、点击正常，但转化骤降。正确的排查顺序是什么？为什么不能直接改归因模型或出价？

<details>
<summary>查看答案</summary>

顺序：**先埋点/回传 → 再覆盖率 → 再窗口/计数 → 再口径 → 最后才考虑模型/出价**。

理由：展示点击正常而转化骤降，最可能是**数据采集断了**（新版页面丢 tag、tag 报错、回传故障），而非模型或出价的问题。直接调归因/出价会掩盖真实原因，且等埋点修好后又得调回来，浪费工时。

</details>

---

## 六、扩展主题（供进阶）

### 6.1 Measurement Protocol / GA4 的事件归因

如果想做**站内 EVO 行为 + 广告归因**的统一，可用 Google Analytics 的 Measurement Protocol 做服务端事件上报，与广告点击 ID 关联。这在"前端埋点受限"（ITP、广告拦截、跨域）时非常有用。

```
Measurement Protocol 关联广告回传
  服务端确认转化后, 上报到 GA4
  带 campaign 参数(如 utm / gclid / dclid)
  → GA4 关联广告触点, 做路径分析
```

**注意**：GA4 的默认归因是 **data-driven / last-click 组合**，与 CM360 Floodlight 口径天然不同。做统一归因前，先在 GA4 后台把"归因模型"与"回看窗口"显式设成与 DV360/CM360 一致。

### 6.2 Ads Data Hub（ADH）与隐私归因

随着 cookies 与移动广告 ID 受限，真实跨平台归因的可行路径是**广告主数据云 / 干净室**：

```
ADH 隐私归因流程
  以加密的 click/impression 日志 + 转化日志送入 ADH
       │
       ▼
  在受控环境内做跨平台去重与归因 (不暴露单用户粒度)
       │
       ▼
  输出: 聚合级的增量/归因分析结果 (如 vROAS)
```

- 优点：合规、能做跨平台增量分析。
- 挑战：需要工程接入、查询语言门槛高、需要准确的身份信号。

### 6.3 提升衡量（Incrementality）与归因的关系

归因给的是"credit 分配"，**提升衡量**回答的是"不做广告是不是就不转化"。两者互补：
- **归因**：把已有转化分给渠道（内部一致性）。
- **实验/增量**：用 A/B geo lift、随机实验估算"没有广告的基线"，衡量广告真正带来的**增量转化**。
- 生产建议：归因负责"运营监控与出价"，增量实验负责"预算规模与渠道取舍"。别把 last-click 的转化数当增量铁证。

### 6.4 术语速查表

| 术语 | 含义 |
|------|------|
| Floodlight | CM360 的转化/活动追踪系统 |
| Floodlight Activity | 单个转化事件(如 purchase) |
| Counting Method | SESSION / STANDARD / UNIQUE 计数方式 |
| Lookback Window | 归因回看窗口(点击/浏览) |
| View-through | 展示后未点击即转化的归因 |
| Click-through | 点击后转化的归因 |
| ord | 去重用唯一序号 |
| u1~u5 | Floodlight 自定义变量 |
| DDA | 数据驱动归因 |
| MCF | 多渠道漏斗(GA360) |
| vsCM | 转化回传 DSP 的参数 |
| ADH | Ads Data Hub 广告主数据云 |
| Incrementality | 增量提升衡量 |

### 6.5 一套可落地的归因健康度指标

| 指标 | 目标 | 说明 |
|------|------|------|
| Floodlight 覆盖率 | ≥ 90% | 有埋点转化 / 全部转化 |
| 三方偏差 | ≤ 5% | DV360 vs GA vs 内部数仓 |
| 匹配率 | 尽量高 | 能归因到用户的比例 |
| view-through 占比 | 稳定 | 波动大提示匹配率问题 |
| 出价转化纯净度 | 高 | 喂给出价的转化 = 真变现转化 |

---

## 七、每日一练（动手验证）

```bash
# 1) 用工坊脚本拉当前广告主的 Floodlight 配置
python3 -c "
from ad_platform_api import AdPlatformClient
c = AdPlatformClient()
for x in c.dv360_list_floodlight_configs(advertiser_id='4659631')[:5]:
    print(x)
"

# 2) 拉近 14 天带 Floodlight 活动维度的转化报表
python3 -c "
from ad_platform_api import AdPlatformClient
c = AdPlatformClient()
r = c.dv360_get_report(
    advertiser_id='4659631',
    dimensions=['FLOODLIGHT_ACTIVITY', 'DATE'],
    metrics=['TOTAL_CONVERSIONS', 'REVENUE', 'MEDIA_COST'],
    date_range={'start': '2026-08-01', 'end': '2026-08-14'})
print(r.get('rows', []))
"

# 3) 枚举 Floodlight 活动维度值, 核对埋点与报表是否对得上
python3 -c "
from ad_platform_api import AdPlatformClient
c = AdPlatformClient()
for a in c.dv360_list_dimension_values('FLOODLIGHT_ACTIVITY'):
    print(a.get('value'), a.get('displayName'))
"
```

**今日自检清单**：
- [ ] 我能画出 Floodlight 配置 / 活动 / Tag 三层结构
- [ ] 我能说出 6 种归因模型的公式与优劣
- [ ] 我清楚 DV360 报表转化 ≠ CM360 ≠ GA 的原因
- [ ] 我能列出"转化追不上"的排查顺序
- [ ] 我明白"跨渠道"与"跨平台"在归因里的区别
- [ ] 我知道出价模型不能吃脏转化

---

## 八、参考资料与扩展阅读

- [Display & Video 360 API 官方文档](https://developers.google.com/display-video/api)
- [Campaign Manager 360 / Floodlight 文档](https://support.google.com/campaignmanager/answer/10298999)
- [Google 数据驱动归因说明](https://support.google.com/analytics/answer/3438880)
- 同仓库关联文档：
  - `knowledge/advertising/dv360/dv360-measurement-attribution-deep.md`（归因模型总览 + Go 引擎实现）
  - `knowledge/advertising/dv360/dv360-architecture-deep.md`（测量与归因第六章）
  - `knowledge/advertising/day-by-day/04-ad-attribution-modeling.md`（通用归因建模）

> **一句话收尾**：跨渠道归因的价值取决于埋点的诚实与口径的一致——**先把 Floodlight 埋好、把去重做对、把口径讲清，再谈哪个模型更"高级"。**

---
