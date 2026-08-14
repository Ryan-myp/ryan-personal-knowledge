# DV360 欺诈检测与品牌安全（Viewability / 品牌安全分级 / 可见性标准 / Invalid Traffic）

> **领域**: 广告投放 / 欺诈与品牌安全
> **深度**: ⭐⭐⭐⭐⭐ 实战级指南
> **标签**: dv360, brand-safety, viewability, fraud, invalid-traffic, ivt
> **更新时间**: 2026-08-14
> **类型**: 深度文档

---

## 一、核心概念与架构

### 1.1 为什么广告主必须同时管理品牌安全、可见性、无效流量

在程序化广告（Programmatic Advertising）中，广告主通过 DV360（Display & Video 360, Google 旗下顶级 DSP）每一次参与竞价、每一次展示、每一次点击，背后都潜藏着三类风险：

1. **品牌安全风险（Brand Safety）**：广告出现在与品牌调性冲突的页面/应用旁（暴力、政治争议、成人、假新闻、仇恨言论），导致品牌资产受损。
2. **可见性风险（Viewability）**：广告虽然"展示"了，但用户在页面加载时根本没看到（首屏之外、被遮挡、立即滚走），花钱买了无效曝光。
3. **无效流量风险（Invalid Traffic, IVT）**：广告被机器、Bot、数据农场（Click Farm）、SDK 注入捏造出来，点击/转化并非真实人类意图，直接烧掉预算并污染数据。

这三者相互交织但本质不同。品牌安全回答**"广告出现在哪"**，可见性回答**"广告是否真的被看到"**，无效流量回答**"点击/展示是否来自真实人类"**。DV360 将这三者统合在 **Content Exclusions（内容排除）+ Viewability 出价 + Invalid Traffic 过滤** 三个机制中。

> 本文姊妹文档《DV360 创意管理与品牌安全深度实战》已覆盖 L1-L4 四级防护的宏观框架、事件响应与可见性优化技巧。本文在此之上更进一步：深入 MRC/IAB 技术标准本身、GIVT/SIVT 检测算法、第三方测量（Moat/IAS/DoubleVerify）的数据格式与对齐差异、买卖侧（Buyer/Seller）协作协议（Ads.txt/app-ads.txt/sellers.json），并用可运行的 Python 与 Go 代码呈现可见性计算器与 IVT 评分引擎。

### 1.2 品牌安全全貌：分类排除、内容分级、敏感类别

DV360 的品牌安全能力可以在多个层级叠加，形成一个**漏斗（Funnel）式过滤链路**：

```
                    采购流量（All Impressions）
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
   L1: 库存来源           L2: 分类排除          L3: 品牌安全分级
   Ads.txt/app-ads.txt    Content Exclusion      Brand Safety
   sellers.json 验证      敏感类别屏蔽           Tiers / 自定义
        │                     │                     │
        └─────────────────────┼─────────────────────┘
                              ▼
               L4: 第三方测量（Moat/IAS/DoubleVerify）
                              ▼
               可见性目标（Viewability Goal）出价层
                              ▼
               IVT 过滤（无效流量，Google 侧自动 + 我方二次评分）
                              ▼
                   有效、可见、安全的人流量
```

**A. 分类排除（Content Exclusions）**

通过 API 的 `dv360_list_content_exclusions` / `dv360_create_content_exclusion` 管理与投放位置无关的内容排除规则。DV360 内置的分类排除维度包括：

| 排除分类（Content Exclusion） | 说明 | 典型敏感度 |
|------|------|------|
| ADULT_CONTENT | 成人/色情内容 | 极高 |
| ALCOHOL | 酒类内容 | 高 |
| DRUGS | 毒品/药品相关内容 | 极高 |
| GAMBLING | 赌博内容 | 高 |
| VIOLENCE | 暴力内容 | 高 |
| POLITICAL | 政治内容 | 高（取决于品牌） |
| HATE_SPEECH | 仇恨言论 | 极高 |
| TERRORISM | 恐怖主义 | 极高 |
| WEAPONS | 武器内容 | 高 |
| ILLEGAL_CONTENT | 非法内容 | 极高 |
| MISINFORMATION | 虚假信息 | 高 |

**B. 内容分级（Brand Safety 分级）**

Google 将库存按风险等级分为若干 **Tier（层级）**，广告主可选择"放行到什么层级"。最流行的框架是 **GARM（Global Alliance for Responsible Media，全球负责任媒体联盟）** 的分类法——它把敏感内容按行业定义分为若干大类（如感动型内容、敏感社会议题、未经证实的毁谤等），帮助行业在对品牌安全有一致语言的基础上进行分级与讨论。

DV360 中品牌安全分级的落地方式：

| 措施 | 说明 | 接口/入口 |
|------|------|-----------|
| 默认分类排除 | Google 预置的敏感内容自动过滤 | DV360 UI 自动生效 |
| 自定义排除列表 | 广告主自行维护域名/内容黑名单 | `dv360_create_content_exclusion` |
| 第三方品牌安全供应商 | 接入 Moat/IAS/DoubleVerify 的分类信号 | Partner 级别配置 |
| App / App Category 排除 | 应用商店分类级别的过滤 | `dv360_list_app_targeting` 相关 |

**C. 敏感类别（Sensitive Categories）**

需要注意：**品牌安全（Brand Safety）**与**敏感类别（Sensitive Category，会影响竞价）**在 DV360 中是两套独立信号：

- 品牌安全 = 内容出现在何处（内容语境）。
- 敏感类别 = 受众本身是否属于受保护群体特征（如基于健康数据、政治倾向、宗教的定向，会受限）。

DV360 允许通过 `dv360_list_brand_safety_categories` 拉取当前可用的品牌安全分类清单，用于构建"该屏蔽什么"的决策表。

### 1.3 可见性（Viewability）概念

可见性指一个广告展示是否具备**被用户真实看到的几何+时间条件**。基于 **MRC（Media Rating Council，媒介评级委员会）** 与 **IAB（Interactive Advertising Bureau，互动广告局）** 的《Viewable Impression Guidelines》，DV360 的可见性测量遵循以下核心标准：

| 广告形式 | 像素条件 | 时间条件 | 是否满足 MRC 可见展示 |
|----------|---------|---------|----------------------|
| 展示广告（Display） | ≥50% 像素进入可视区域 | ≥1 秒 | 是 |
| 视频广告（Video / 在线视频广告 >4:3） | ≥50% 像素进入可视区域 | ≥2 秒连续 | 是 |
| 大型视频广告（≥16:9，超大面积） | ≥30% 像素进入可视区域 | ≥2 秒连续 | 是（MRC 对大面积伴播视频的规定） |

> **关键区分**：Video 的可见标准是 **≥2 秒**，Display 是 **≥1 秒**。广泛传播的"1 秒"可见标准只适用于展示广告；视频广告（尤其伴播视频 Pre-roll/Mid-roll）必须满足 2 秒标准才算可见展示。

DV360 通过第三方测量（Moat/IAS/DoubleVerify）与自有测量提供"**用可见展示计费（Viewable Impression Buying）**"与"**可见性出价（Viewability Targeting / Goal）**"两种能力。

### 1.4 无效流量（Invalid Traffic, IVT）：GIVT 与 SIVT

依据 **MRC《Invalid Traffic Detection and Filtration Guidelines》**，无效流量被分为两大类：

| 类型 | 全称 | 定义 | 典型来源 | 检测难度 |
|------|------|------|---------|---------|
| **GIVT** | General Invalid Traffic（一般无效流量） | 行为模式上即可识别、无需复杂分析的无效流量 | 已知数据中心 IP、已知爬虫、隐藏 iframe、重复计数、非人类浏览器（headless） | 低-中 |
| **SIVT** | Sophisticated Invalid Traffic（复杂无效流量） | 需要高度复杂分析（机器学习、行为特征、设备指纹）才能识别 | 模拟人类行为的 Bot、僵尸网络、Click Farm（数据农场）、坐标污染、SDK 滥用、代理注入 | 高 |

**GIVT 示例检测信号：**
- 流量来源 IP 属于云数据中心（AWS/Azure/GCP）而非住宅 ISP。
- User-Agent 匹配 Googlebot/Bingbot/其他已知 crawler。
- 展示发生在 1×1 像素或隐藏 iframe（display:none）内。
- 同一用户/IP 在极短时间内产生大量展示。

**SIVT 示例检测信号：**
- 鼠标轨迹完全规则/无人类抖动。
- 网页坐标与真实设备视口不匹配（广告永远不进入可视区却记录 viewable）。
- 点击发生时间呈完美周期性（机器节奏）。
- 设备指纹异常：JavaScried 被禁、同一设备跨多个 IP。

### 1.5 DV360 品牌安全 / 欺诈防护能力全景图

```
                    DV360 品牌安全 + 反欺诈能力矩阵
┌─────────────────────────────────────────────────────────────┐
│  层    │  能力                          │  主责方   │  关键 API   │
├────────┼────────────────────────────────┼──────────┼─────────────┤
│ 库存层 │ Ads.txt / app-ads.txt 校验     │ 买卖双方  │ list_sellers│
│        │ sellers.json / OAR 原生广告    │ Google/SSP│ dv360_list_seller_metrics │
├────────┼────────────────────────────────┼──────────┼─────────────┤
│ 内容层 │ 分类排除/品牌安全分级/自定义列表│ 买(广告主)│ dv360_list_content_exclusions / create_content_exclusion │
│        │ 第三方品牌安全信号             │ 供应商    │ list_brand_safety_categories │
├────────┼────────────────────────────────┼──────────┼─────────────┤
│ 位置层 │ Placement 级别的黑/白名单       │ 买        │ dv360_list_placements / list_targeting_units │
├────────┼────────────────────────────────┼──────────┼─────────────┤
│ 可见性 │ Viewability 目标(>=50%/1s 等)   │ 买/Google │ dv360_list_viewability_targets │
│        │ Visible Impressions 出价        │          │ dv360_create_line_item 配置  │
├────────┼────────────────────────────────┼──────────┼─────────────┤
│ 欺诈    │ GIVT 全自动过滤                │ Google   │ 计费报告剔除 invalid traffic │
│        │ SIVT 高级保护(机器学习)         │ Google    │ dv360_get_report / sync_report │
│        │ 我方二次 IVT 评分引擎           │ 买(自建)  │ 对接 report metrics          │
├────────┼────────────────────────────────┼──────────┼─────────────┤
│ 度量    │ 第三方测量差异对账             │ 供应商+买 │ get_report_metrics / list_dimension_values │
│        │ Floodlight 转化去重             │ 买        │ list_floodlight_configs      │
└────────┴────────────────────────────────┴──────────┴─────────────┘
```

**第五节前的读者须知：** 本图里每一个"关键 API"都会在第二节（原理）与第三节（实战）中给出真实调用代码与可运行实现。

### 1.6 术语速查表

| 缩写 | 全称 | 中文 | 一句话解释 |
|------|------|------|-----------|
| DV360 | Display & Video 360 | 展示与视频 360 | Google 企业级 DSP |
| DSP | Demand-Side Platform | 需求方平台 | 广告主采买流量的平台 |
| SSP | Supply-Side Platform | 供给方平台 | 媒体方售卖流量的平台 |
| MRC | Media Rating Council | 媒介评级委员会 | 制定可见性/无效流量标准的行业机构 |
| IAB | Interactive Advertising Bureau | 互动广告局 | 互联网广告行业标准组织 |
| GARM | Global Alliance for Responsible Media | 全球负责任媒体联盟 | 制定品牌安全内容分级框架 |
| IVT | Invalid Traffic | 无效流量 | 欺诈/非人类流量 |
| GIVT | General Invalid Traffic | 一般无效流量 | 简单可识别的无效流量 |
| SIVT | Sophisticated Invalid Traffic | 复杂无效流量 | 需高级分析识别的无效流量 |
| VAST | Video Ad Serving Template | 视频广告投放模板 | 视频广告请求/响应协议 |
| VAST Wrapper | — | VAST 封装 | 允许多层 ad server 转发的协议 |
| OpenRTB | Open Real-Time Bidding | 开放实时竞价协议 | 竞价请求/响应标准 |
| OAR | Open Ad Server Relay | 开放广告服务器中继 | 原生广告/服务器侧转换标准 |
| advertisers.json | — | 广告主清单 | 买家侧供应链披露文件 |
| sellers.json | — | 卖家清单 | 卖家身份披露文件 |
| Ads.txt | Authorized Digital Sellers | 授权数字卖家 | 声明谁有权售卖某库存 |
| app-ads.txt | — | 应用授权数字卖家 | 移动端版 Ads.txt |
| Floodlight | — | — | DV360 的转化跟踪像素/标签 |
| CPA / CPM / CPC | — | 成本模型 | 按行为/千次展示/点击计费 |
| MOAT | — | — | Oracle 旗下可见性/品牌安全测量商（现属 Oriel/曾有动荡） |
| IAS | Integral Ad Science | — | 广告质量与品牌安全测量商 |
| DV (DoubleVerify) | — | 双重验证 | 独立第三方测量商 |
| IR | Interaction Rate | 互动率 | 视频互动指标 |

---

## 二、深度原理解析

### 2.1 可见性标准的精确几何定义（MRC/IAB）

**"可见展示（Viewable Impression）"的精确判定**，不是一个模糊的"看到没看到"，而是严格的几何 + 时间条件的组合。以下用坐标几何来精确定义。

**2.1.1 像素条件（>=50% 像素）**

设广告元素的包围盒（bounding box）为矩形 `A`，其坐标由四个角点定义：
- A.left, A.top（左上角）
- A.width, A.height（宽高）

浏览器可视区（Viewport）矩形为 `V`。

两矩形相交的可见区域矩形 `I` 计算如下（基于标准 2D 矩形求交）：

```
I.left   = max(A.left, V.left)
I.top    = max(A.top, V.top)
I.right  = min(A.left + A.width, V.left + V.width)
I.bottom = min(A.top + A.height, V.top + V.height)
I.width  = max(0, I.right - I.left)
I.height = max(0, I.bottom - I.top)
I.area   = I.width * I.height
A.area   = A.width * A.height
visibleRatio = I.area / A.area
```

- 若 `visibleRatio >= 0.5`（即 ≥50% 像素）且持续满足时间条件（Display ≥1s，Video ≥2s），则记为可见展示。

**2.1.2 大面积伴播视频的特殊规则（>=30%）**

MRC 对**大面积伴播视频（large viewability）**——主要指 ≥16:9、面积很大的视频广告——额外规定：

> 当视频广告面积超过一定阈值（MRC 建议定义：视口很大时），像素门槛从 50% 降到 **30%**，时间条件仍为 **≥2 秒连续**。

这一规则的动机：超大视频即使只露出 30%，用户也几乎必然看到了内容核心区域。DV360 在第三方合作测量中会遵循该特例。

**2.1.3 时间条件的"连续"语义**

视频的 2 秒条件是**连续（continuous）**的：即必须在同一连续时间段内像素占比达到 50%（或 30% 特例）并保持 2 秒。中断（scrolling 后重新进入）不算连续满足。

**2.1.4 测量方法：几何法 vs 数据法**

| 方法 | 说明 | 典型实现 |
|------|------|---------|
| 几何法（Geometry） | 用 getBoundingClientRect() + 滚动监听 + 定时采样计算像素占比 | JS 测量标签 |
| 浏览器 IntersectionObserver | 浏览器原生 API 回调可见性变化 | 现代 SDK 首选 |
| 数据法（Data-level / log-level） | 从服务端日志推断是否可见（无法 100% 精确，多用于估计） | DSP/SSP 日志分析 |

**重要**：MRC 认可的"可见展示测量"必须来自**与加载上下文同步的测量**（如 JS 标签或 IntersectionObserver），**纯服务端几何估计不能作为合规的可见性测量**，这是第三方测量（Moat/IAS/DV 的 JS 测量）存在的根本原因。

### 2.2 第三方测量（Moat / IAS / DoubleVerify）数据格式与接入

**2.2.1 测量标签（Measurement Tag）如何工作**

第三方测量商通过一种"测量像素/标签"（通常为 JS SDK 或 VAST Wrapper 中的测量 tag）实时计算可见性与品牌安全信号，并把结果通过回调（callback URL）实时回传，同时通过日志（log-file）提供可对账数据。

```
  DV360（DSP）
     │ 发起对第三方供应商的测量请求
     ▼
  第三方测量服务器（Moat/IAS/DV）
     │  下发测量 SDK / VAST wrapper
     ▼
  网页 / App 端 SDK 执行测量：
     ├── IntersectionObserver 计算可见性
     ├── 内容分类（爬取/上下文分析）→ 品牌安全信号
     ├── IVT 检测（设备指纹、行为分析）
     └── 通过 pixel callback 实时上报
     ▼
  测量服务器聚合 → 生成：
     ├── 实时 Dashboard
     ├── 每日/小时 Log-file（供对账）
     └── 计费可见性数据
```

**2.2.2 常见第三方测量字段格式**

| 字段 | 含义 | 示例 |
|------|------|------|
| timestamp | 展示发生时间戳 | 2026-08-14T03:22:15Z |
| imp_id | 展示唯一 id | 0af9...e2 |
| bundle / domain | App 包名或网站域名 | com.newspaper.app / example.com |
| viewability | 是否可见（0/1 或明文字符） | 1 / "measured-viewable" |
| viewable_ratio | 像素占比 | 0.87 |
| duration_visible_sec | 可见持续秒数 | 3.4 |
| brand_safety_category | 品牌安全分类代码 | "mature" / "adult" / "safe" |
| fraud_score | 欺诈风险分 | 0.02 |
| givt_sivt | 无效流量分类 | "givt" / "sivt" / "valid" |
| device_type | 设备类型 | "mobile" / "desktop" |
| city/region | 位置 | "beijing" / "CN-BJ" |

**2.2.3 第三方数据 vs DV360 平台数据的差异（一致性对账）**

第三方测量与 DV360 自身数据**几乎必然存在差异**，原因：

| 差异来源 | 说明 | 处理建议 |
|---------|------|---------|
| 时间窗口 | 平台按小时计，第三方按展示实时 | 用同一时区与口径 |
| 定义不同 | DV360 "可见性"可能用自测，第三方用 MRC 测量 | 明确同一标准 |
| 去重逻辑 | 各方便用不同的 impression dedup key | 对齐 imp_id |
| IVT 过滤时点 | 平台展示前过滤，第三方测量后标记 | 区分"平台剔除"与"第三方回测标记" |
| 采样/延迟 | 第三方 log 有延迟与采样 | 允许 ±5% 容差，超出则排查 |

### 2.3 Ads.txt / app-ads.txt / sellers.json 与库存验证

**2.3.1 Ads.txt（Authorized Digital Sellers）**

Ads.txt 是 IAB 推出的、由**媒体发布方**在其根域放置的 TXT 文件，声明"谁有权售卖我的库存"。DSP 与 SSP 在竞价时校验该文件，从而识别并过滤未经授权的转售/劫持库存。

```
# example.com/ads.txt
google.com, pub-1234567890, DIRECT, f08c47fec0942fa0
appnexus.com, 9271, RESELLER, f5ab79cb980f111d
rubiconproject.com, 16978, RESELLER, 0bfd66d529a5580a
```

格式：`<域名>, <发布商ID>, <关系类型>, <证书ID可选>`
- 关系类型：`DIRECT`（直接授权）、`RESELLER`（允许转售）。
- 证书 ID：该发布商对该卖家的成员认证哈希。

**2.3.2 app-ads.txt**

App 无法像网站一样放根域 TXT，所以广告 SDK 会请求**开发者的网站根域**下的 `app-ads.txt`，通过 `App 包名` 关联：

```
# publisher.com/app-ads.txt
com.myapp.game, google.com, pub-900001, DIRECT, f08c47fec0942fa0
```

**2.3.3 sellers.json 与 advertisers.json**

- **sellers.json**：由**卖家/AdX/SSP**托管，列出所有直接与间接卖家身份（`seller_id`, `seller_type`（PUBLISHER/INTERMEDIARY/BOTH）, `name`, `domain`），配合 OpenRTB 的 `pchain`（卖家链）使用。
- **advertisers.json**：由**买家/DSP**托管（DV360 支持），向供给方披露广告主身份。

`dv360_list_sellers` 与 `dv360_list_seller_metrics` 可用来枚举并评估卖家质量。

**2.3.4 库存验证在 DV360 的落地**

- DV360 会对已声明 Ads.txt 的库存做强校验，对未声明的库存标记为"未认证风险"。
- 广告主可通过 `dv360_list_placements` 查看每个 placement 的认证状态，并在定向时选择"仅用授权库存"。

### 2.4 GIVT 检测原理

GIVT 检测的特征偏"确定性、可规则化"。核心维度：

| 维度 | GIVT 信号示例 | 检测方式 |
|------|--------------|---------|
| IP 信誉 | 云数据中心、已知代理、Tor 出口 | IP 黑名单/信誉库 |
| User-Agent | 已知 crawler / 机器人 UA | UA 白黑名单 + 爬虫库（如 uaparser） |
| 隐藏环境 | display:none, 0-size, off-screen | 几何检测/iframe 透明检测 |
| 频率异常 | 单设备秒级海量展示 | 频次计数 |
| 重复/镜像 | 相同展示/点击反复 | 指纹去重（imp_id hash） |

**GIVT 的例子**：某次投放中，同一 `imp_id` 被回传了 300 次；源 IP 全在 `AWS` 的 `us-east-1` 网段；UA 是 `HeadlessChrome`。DV360 计费侧自动剔除，报告里的可见展示/计费展示不会包含这些。

### 2.5 SIVT 检测原理

SIVT 需要机器学习与行为建模：

| 维度 | SIVT 信号示例 | 检测方法 |
|------|--------------|---------|
| 行为节奏 | 点击间隔分布呈完美均匀/周期 | 统计分布检验（如 Kolmogorov-Smirnov） |
| 鼠标轨迹 | 无抖动、直线、瞬移 | 轨迹几何/速度异常检测 |
| 坐标污染 | 广告在可视区外却上报 viewable | 坐标↔视口一致性校验 |
| 设备指纹 | 指纹不稳、过多、被篡改 | Fingerprint 聚类（孤立森林/DBSCAN） |
| 图谱异常 | 大量设备共享同一 IP/同一点击目标 | 图分析（社群检测） |
| 时间-地理位置 | 点击速度超过物理极限（跨省瞬间） | 速度校验 v = Δdist/Δt |

**SIVT 的经典例子（Click Farm）**：某市场出现 500 台设备，每台设备 1 天点 3000 次，全部点击同一批广告主 App；点击坐标在 2 毫秒内从北京"跳到"上海。这些设备共享 12 个 IP。通过设备指纹聚类 + 地理速度校验可把这一簇标记为 SIVT。

### 2.6 品牌安全内容分类法（深入）

GARM 把敏感内容分为 **7 大类**（每个大类下有子分类），这是品牌安全"分级"的行业语言：

| GARM 大类 | 含义 | 子分类示例 |
|----------|------|-----------|
| 1. 与权威的冲突 | 政治、社会议题 | 选举、抗议、未经证实的毁谤 |
| 2. 成人/性内容 | 成人内容 | 露骨性内容、约会 |
| 3. 赌博 | 赌博 | 线下/线上赌博 |
| 4. 非法药品/毒品 | 毒品 | 大麻、处方药 |
| 5. 受管毒品 | 受管制物质 | 酒精、烟草 |
| 6. 武器 | 武器 | 枪支、弹药 |
| 7. 仇恨/冒犯行为 | 仇恨言论 | 种族歧视、不当行为 |

DV360 + 第三方供应商（IAS/Moat/DV）会把 GARM 分类映射到各自的分类代码，广告主设定"每个大类允许/屏蔽/中间层"。

### 2.7 Python：调用 DV360 API 管理品牌安全与查看 IVT

下面用知识库统一脚本 `ad_platform_api.py` 中的方法，给出切实可用的 Python 调用示例。

**2.7.1 拉取品牌安全分类清单**

```python
# filename: examples/bs_categories.py
from ad_platform_api import AdPlatformAPI

api = AdPlatformAPI(credentials="config/credentials.json")

# 枚举所有品牌安全分类
categories = api.dv360_list_brand_safety_categories(partner_id="<PARTNER_ID>")
for c in categories:
    print(f"[{c.get('id')}] {c.get('name')} - {c.get('description')}")

# 可以看到 GARM 分类、Google 分类等，据此构建屏蔽决策表。
```

**2.7.2 列出/创建内容排除规则**

```python
# content_exclusions.py
from ad_platform_api import AdPlatformAPI
api = AdPlatformAPI(credentials="config/credentials.json")

advertiser_id = "<ADV_ID>"

# 列出既有排除
existing = api.dv360_list_content_exclusions(advertiser_id)
for ex in existing:
    print(ex)

# 创建一条内容排除：屏蔽成人 + 赌博
created = api.dv360_create_content_exclusion(
    advertiser_id,
    name="大客户-硬性排除-成人&赌博",
    content_categories=["ADULT_CONTENT", "GAMBLING"],
    status="ENABLED",
)
print("created exclusion:", created)
```

**2.7.3 列出可见性目标并创建带可见性/品牌安全配置的 Line Item**

```python
# line_item_viewability.py
from ad_platform_api import AdPlatformAPI
api = AdPlatformAPI(credentials="config/credentials.json")

adb_id = "<ADV_ID>"

vt = api.dv360_list_viewability_targets()
print("可用可见性目标:", [t.get('name') for t in vt])
# 常见: VIEWABILITY_50_PERCENT_1S, VIEWABILITY_50_PERCENT_2S(视频),
#       VIEWABILITY_100_PERCENT_1S, IVT 目标等

li = api.dv360_create_line_item(
    adb_id,
    name="Q3-品牌安全-可见性严格",
    type="DISPLAY",
    bidding_strategy={"fixedBid": {"fixedBidAmountMicros": 2_500_000}},  # 2.5 元 CPM(微元)
    viewability_config={
        "targetingType": "VIEWABILITY_TARGETING_TYPE_AWARE",
        "viewabilityTarget": "VIEWABILITY_50_PERCENT_1S",
    },
    brand_safety_config={
        "contentExclusion": "ADULT_CONTENT,GAMBLING,VIOLENCE",
        "useGoogleApprovedList": True,
    },
    inventory_sources=["INVENTORY_SOURCE_EXCHANGE", "INVENTORY_SOURCE_PUBLISHER"],
    status="PAUSED",  # 先暂停，配好再启用
)
print("line item id:", li.get("id"))
```

**2.7.4 卖家指标与账户健康**

```python
# seller_health.py
from ad_platform_api import AdPlatformAPI
api = AdPlatformAPI(credentials="config/credentials.json")

# 卖家指标：看某个卖家的可见性/欺诈占比
m = api.dv360_list_seller_metrics(seller_id="<SELLER_ID>")
print("viewable_impressions:", m.get("viewableImpressions"))
print("invalid_traffic_rate:", m.get("invalidTrafficRate"))

# 账户健康总览
h = api.dv360_get_account_health("<ADV_ID>")
print("ivt rate:", h.get("ivtRate"), "flagged domains:", h.get("flaggedDomains"))

# 定向维度选项
from dv360_api import DV360APIClient
client = DV360APIClient(credentials=...)
dims = client.get_targeting_dimension_options()
print([d['name'] for d in dims])  # 地域/年龄/性别/兴趣...
```

### 2.8 Go：可见性计算器（Viewability Calculator）

用 Go 实现一个 MRC 合规的可见性判定器。核心是矩形求交 + 时间连续性判定。

```go
// viewability.go
package viewability

import "time"

// Rect 表示一个 2D 矩形
type Rect struct {
	Left, Top, Width, Height float64
}

func (r Rect) Right() float64 { return r.Left + r.Width }
func (r Rect) Bottom() float64 { return r.Top + r.Height }

// Intersection 计算两个矩形交集面积
func Intersection(a, b Rect) float64 {
	left := max(a.Left, b.Left)
	top := max(a.Top, b.Top)
	right := min(a.Right(), b.Right())
	bottom := min(a.Bottom(), b.Bottom())
	if right <= left || bottom <= top {
		return 0
	}
	return (right - left) * (bottom - top)
}

// VisibleRatio 返回广告元素相对可视区的像素占比
func VisibleRatio(ad, viewport Rect) float64 {
	if ad.Width <= 0 || ad.Height <= 0 {
		return 0
	}
	inter := Intersection(ad, viewport)
	return inter / (ad.Width * ad.Height)
}

// ViewabilityDecision MRC 判定结果
type ViewabilityDecision struct {
	Viewable      bool
	Ratio         float64
	AdType        AdType
	MeasuredSecs  float64
}

type AdType int

const (
	Display AdType = iota
	Video
	LargeVideo // >=16:9 且面积很大的伴播视频
)

// MRCRules 返回某广告类型对应的 MRC 阈值
func MRCRules(t AdType) (ratioThreshold, secondsThreshold float64) {
	switch t {
	case Display:
		return 0.50, 1.0
	case Video:
		return 0.50, 2.0
	case LargeVideo:
		return 0.30, 2.0
	}
	return 0.50, 1.0
}

// IsViewable 根据采样的可见占比序列判定是否可见展示。
// samples: 自广告出现在页面起的可见占比采样；sampleInterval 为采样间隔秒。
func IsViewable(adType AdType, samples []float64, sampleInterval time.Duration) ViewabilityDecision {
	ratioTh, secTh := MRCRules(adType)
	var continuous float64 // 当前连续满足的秒数
	maxContinuous := 0.0
	for _, r := range samples {
		if r >= ratioTh {
			continuous += sampleInterval.Seconds()
			if continuous > maxContinuous {
				maxContinuous = continuous
			}
		} else {
			continuous = 0
		}
	}
	return ViewabilityDecision{
		Viewable:     maxContinuous >= secTh,
		Ratio:        lastOrMax(samples),
		AdType:       adType,
		MeasuredSecs: maxContinuous,
	}
}

func lastOrMax(s []float64) float64 {
	m := 0.0
	for _, v := range s {
		if v > m {
			m = v
		}
	}
	return m
}
```

**测试用例：**

```go
// viewability_test.go
package viewability

import (
	"testing"
	"time"
)

func TestIsViewableDisplay1s(t *testing.T) {
	// 展示广告: 50% 像素 >= 1 秒
	viewport := Rect{Left: 0, Top: 0, Width: 1200, Height: 800}
	ad := Rect{Left: 100, Top: 200, Width: 400, Height: 300}
	// ad 全部在视口内 -> ratio = 1.0
	samples := []float64{1.0, 1.0, 1.0} // 3 个采样 * 0.5s = 1.5s
	d := IsViewable(Display, samples, 500*time.Millisecond)
	if !d.Viewable {
		t.Fatalf("display should be viewable, got %+v", d)
	}
}

func TestIsViewableVideo2s(t *testing.T) {
	// 视频: 50% >= 2 秒
	samples := []float64{1, 1, 1, 1, 1} // 5*0.5s=2.5s
	d := IsViewable(Video, samples, 500*time.Millisecond)
	if !d.Viewable {
		t.Fatal("video should be viewable after 2s")
	}
	// 中断: 1,0,1,1 => 连续只到 1s，不满足
	d2 := IsViewable(Video, []float64{1, 0, 1, 1}, 500*time.Millisecond)
	if d2.Viewable {
		t.Fatal("interrupted view should NOT be viewable")
	}
}

func TestLargeVideoThreshold(t *testing.T) {
	// 大面积视频: 30% 像素 >= 2 秒即可
	ratioTh, secTh := MRCRules(LargeVideo)
	if ratioTh != 0.30 || secTh != 2.0 {
		t.Fatalf("large video rule wrong: %v %v", ratioTh, secTh)
	}
}
```

### 2.9 Go：IVT 评分器（IVT Scorer）

下面实现一个可运行的 IVT 评分引擎，融合 GIVT 确定性规则与 SIVT 行为特征，输出 0~1 的 `fraud_score`。

```go
// ivt.go
package ivt

import (
	"math"
	"net"
	"strings"
	"time"
)

// Signal 单条事件的原始信号
type Signal struct {
	IP                     string
	UserAgent              string
	Timestamp              time.Time
	AreaRatio              float64 // 像素可见占比 0~1
	ClickOffsetMs          int64   // 点击距展示的偏移
	PrevClickOffsetMs      int64
	DeviceFingerprint      string
}

// Result 判定结果
type Result struct {
	FraudScore float64
	Tier       string // GIVT / SIVT / VALID
	Reasons    []string
	RuleHits   []string
}

var dataCenterPrefixes = []string{
	"3.", "34.", "13.", "15.", // AWS
	"20.", "40.", "52.", // Azure/GCP
}

func isDataCenterIP(ip string) bool {
	h := net.ParseIP(ip)
	if h == nil {
		return false
	}
	for _, p := range dataCenterPrefixes {
		if strings.HasPrefix(ip, p) {
			return true
		}
	}
	return false
}

func isCrawlerUA(ua string) bool {
	u := strings.ToLower(ua)
	for _, c := range []string{"googlebot", "bingbot", "applebot", "headlesschrome", "curl", "python-requests"} {
		if strings.Contains(u, c) {
			return true
		}
	}
	return false
}

// Score 返回该信号的欺诈评分 0(干净)~1(高度可疑)
func Score(s Signal) Result {
	res := Result{Tier: "VALID"}
	score := 0.0

	// ---- GIVT 确定性规则 ----
	if isDataCenterIP(s.IP) {
		score += 0.35
		res.Tier = "GIVT"
		res.Reasons = append(res.Reasons, "datacenter-ip")
		res.RuleHits = append(res.RuleHits, "GIVT:IP")
	}
	if isCrawlerUA(s.UserAgent) {
		score += 0.30
		res.Tier = "GIVT"
		res.Reasons = append(res.Reasons, "crawler-ua")
		res.RuleHits = append(res.RuleHits, "GIVT:UA")
	}

	// ---- SIVT 行为规则 ----
	// 1) 可见性坐标污染: 面积占比远低于可视却出现(暗示注入)
	if s.AreaRatio < 0.05 {
		score += 0.12
		res.Reasons = append(res.Reasons, "off-viewport-report")
		res.RuleHits = append(res.RuleHits, "SIVT:coord")
	}
	// 2) 点击太规律: 前后两次点击偏移完全相等(机器节奏)
	if s.PrevClickOffsetMs != 0 && s.ClickOffsetMs == s.PrevClickOffsetMs {
		score += 0.18
		res.Reasons = append(res.Reasons, "mechanical-click-interval")
		res.RuleHits = append(res.RuleHits, "SIVT:rhythm")
	}
	// 3) 点击过快: < 150ms 人类几乎不可能
	if s.ClickOffsetMs > 0 && s.ClickOffsetMs < 150 {
		score += 0.15
		res.Reasons = append(res.Reasons, "subhuman-click-speed")
		res.RuleHits = append(res.RuleHits, "SIVT:speed")
	}
	// 4) 指纹缺失/过短(JS 被禁场景的伪装)
	if len(s.DeviceFingerprint) < 6 {
		score += 0.10
		res.Reasons = append(res.Reasons, "weak-fingerprint")
		res.RuleHits = append(res.RuleHits, "SIVT:fingerprint")
	}

	score = math.Min(1.0, score)
	res.FraudScore = score
	if score >= 0.5 {
		res.Tier = "SIVT"
	}
	return res
}
```

**决策用法：**

```go
// Use: 阈值策略
r := Score(sig)
if r.Tier != "VALID" {
	// 记入 IVT 日志，投放端不为此付费/不计入绩效
	saveIVTRecord(sig, r)
}
```

---

## 三、生产环境实战

### 3.1 场景一：品牌安全配置——排除敏感分类 + 设置 Viewability 目标 + 启用好友情库存

**业务背景**：某快消品牌（FMCG）Q3 大促，要求广告只能出现在"安全、可见、高质量"的库存中，拒绝成人/赌博/暴力，且要控制无效流量。

**最佳实践步骤：**

1. **拉取目录**：先用 `dv360_list_brand_safety_categories` 看全量分类。
2. **建排除**：用 `dv360_create_content_exclusion` 建"硬排除"（成人、赌博、暴力、仇恨）。
3. **设可见性**：`dv360_list_viewability_targets` 确认 50%/1s（展示）与 50%/2s（视频）目标。
4. **建 Line Item**：`dv360_create_line_item` 带上 `brand_safety_config` 与 `viewability_config`。
5. **库存来源**：仅用认证库存 + 良质卖家，`dv360_list_seller_metrics` 排序筛卖家。
6. **灰度上线**：先 `PAUSED`，小流量跑通再放大。

**参考配置（Python 脚本）：**

```python
# production_setup.py
from ad_platform_api import AdPlatformAPI
api = AdPlatformAPI(credentials="config/credentials.json")
ADB = "<ADV_ID>"

# 1) 品牌安全分类目录
cats = api.dv360_list_brand_safety_categories()

# 2) 创建内容排除
exclusion = api.dv360_create_content_exclusion(
    ADB, name="FMCG-Q3-硬排除",
    content_categories=["ADULT_CONTENT", "GAMBLING", "VIOLENCE", "HATE_SPEECH", "DANGEROUS_CONTENT"],
)

# 3) 可见性目标
api.dv360_list_viewability_targets()

# 4) 创建 Line Item
li = api.dv360_create_line_item(
    ADB, name="FMCG-Q3-安全&可见",
    type="DISPLAY",
    viewability_config={"targetingType": "VIEWABILITY_TARGETING_TYPE_AWARE",
                        "viewabilityTarget": "VIEWABILITY_50_PERCENT_1S"},
    brand_safety_config={"contentExclusion": "ADULT_CONTENT,GAMBLING,VIOLENCE,HATE_SPEECH"},
    inventory_sources=["INVENTORY_SOURCE_PUBLISHER", "INVENTORY_SOURCE_EXCHANGE"],
    status="PAUSED",
)

# 5) 卖家质量评估: 挑选 IVT 率低、可见性高的卖家
sellers = [api.dv360_list_seller_metrics(sid) for sid in candidate_seller_ids]
good = [s for s in sellers if s.get('invalidTrafficRate', 1) < 0.02
        and s.get('viewableRate', 0) > 0.60]
```

**结果监控：** 通过 `dv360_get_report`（维度：placement/content_category/fraud）查看排除了多少、可见率多少、IVT 拦截率多少。

### 3.2 场景二：点击率/转化异常 → IVT 排查流程

**症状**：某 Line Item CTR 异常高（从 0.3% 飙到 8%），但转化没跟上，消费却陡增。

**排查漏斗（分步）：**

```
第1步 先看平台级 IVT 拦截：dv360_get_report 的 invalid traffic 指标
   └→ 若平台已拦很高，说明有源发欺诈
第2步 按 placement/域名/App 拆看 CTR 异常点：dv360_list_placements + report
   └→ 圈出"高CTR×零转化"的长尾域名/App
第3步 第三方回测：把日志交给 Moat/IAS/DV 复核是否为 SIVT
   └→ 拿到供应商 fraud flag
第4步 我方二次评分：用 Go IVT Scorer 对日志跑一遍
   └→ 输出 fraud_score 与 tier
第5步 处置：把可疑 placement/域名加黑名单(exclusion)，或暂停该 LI
第6步 复盘：把识别出的签名写回规则库，避免重复
```

**报表查询（Python）：**

```python
# suspect_analysis.py
from ad_platform_api import AdPlatformAPI
api = AdPlatformAPI(credentials="config/credentials.json")

report = api.dv360_get_report(
    advertiser_id=ADB,
    metrics=["IMPRESSIONS", "CLICKS", "CTR", "INVALID_TRAFFIC_IMPRESSIONS", "SPEND"],
    dimensions=["PLACEMENT_ID", "DOMAIN", "APP"],
    date_range={"startDate": "2026-08-01", "endDate": "2026-08-07"},
    filter={"lineItemId": LI_ID},
)

flag = [r for r in report["rows"]
        if r["ctr"] > 0.05 and r["conversions"] == 0]
for f in flag:
    print("suspicious", f["domain"], f["ctr"], "spend:", f["spend"])
```

**关键脚本**：`/Users/yanping.ma/ryan-personal-knowledge/scripts/query_dv360_campaign.py` 提供了现成的 DV360 报表查询入口，可直接抽取上述指标用于对账与排查。

### 3.3 场景三：第三方数据与平台数据不一致 --> 对账

**症状**：Moat 报 Viewability 58%，DV360 平台报 72%，差 14 个百分点。

**原因核查表：**

| 候选原因 | 检查动作 |
|---------|---------|
| 定义不一致（自测 vs MRC） | 确认两边都用 MRC 50%/1s |
| 时间窗不同 | 用同一时区同一小时窗口 |
| 采样/延迟 | 等第三方 log 完全落地后再对 |
| imp_id 去重键不同 | 统一用 DV360 imp_id 或供应商 imp_id |
| IVT 过滤时点 | 平台展示前剔除 VS 第三方事后标记 |

**对账脚本（伪码）：**

```python
# reconcile.py
from ad_platform_api import AdPlatformAPI
third = load_third_party_log("moat_20260807.log")
plat = api.dv360_get_report_metrics(ADB, date="2026-08-07")

# 用 imp_id 对齐
third_imp = {r["imp_id"]: r for r in third}
platform_view = plat["viewable_impressions"]
third_view = sum(1 for r in third if r["viewable"] == 1)

diff = (plat["viewable_impressions"] - third_view) / max(third_view, 1)
print(f"平台可见率 {plat['viewable_rate']:.2%}, 第三方 {third_rate:.2%}, 差异 {diff:+.1%}")
# 高于 ±5% 触发告警
```

### 3.4 场景四：跨团队协作——买卖侧（Buyer/Seller）与供应链透明

**最佳实践清单：**

- 买侧：启用 `advertisers.json` 披露身份；维护 Ads.txt 校验策略。
- 卖侧：确保发布商部署 Ads.txt/app-ads.txt；SSP 暴露 sellers.json。
- DV360 侧：`dv360_list_sellers` 核对授权卖家，杜绝未授权转售。
- 定期用 `dv360_get_account_health` 检查账户健康分（IVT/可见性/认证库存占比）。

### 3.5 常见踩坑与规避

| 踩坑 | 现象 | 规避 |
|------|------|------|
| Viewability 目标设太高（如 100%/1s） | fill(填充率) 暴跌、竞价输掉、CPM 飙升 | 用 50%/1s 起步，逐步加压 |
| 品牌安全分类过粗（全屏蔽政治） | 误杀大量新闻类优质库存 | 用 GARM 分级精细化而非一刀切 |
| 误杀正常用户 | 合法用户被 IDC/住宅误判为欺诈 | 保留人工复核+阈值校准 |
| 排除列表误伤正常流量 | 大品牌自己的品牌词被排掉 | 白名单复核与灰度 |
| 第三方数据不对齐 | 对账差异>10% 引发信任问题 | 统一口径+容差+日志级对齐 |
| IVT 率偏高未深挖 | 预算持续流失 | 建立 CTR/转化异常自动告警 |
| 依赖平台单一信号 | 平台漏判 SIVT | 叠加第三方+自研二次评分 |

---

## 四、常见问题与排查（FAQ）

### 4.1 FAQ 一览

| # | 问题 | 快速答案 |
|---|------|---------|
| 1 | Viewability 只有 30%，太低了怎么办 | 先确认测量口径（MRC），再看位置/尺寸/是否 Video 2s 标准 |
| 2 | 平台 IVT 拦截率很高，我还要做什么 | 平台只拦 GIVT 主体，SIVT 需第三方+自研回测 |
| 3 | 为什么屏蔽了品牌安全还会被误杀 | 分类过粗/定向冲突，用 GARM 细粒度+白名单 |
| 4 | 第三方与 DV360 Viewability 不一致 | 定义/时区/采样/去重口径对齐 |
| 5 | Ads.txt 缺失的库存能投放吗 | 可投但有风险；建议仅授权库存 |
| 6 | 误杀正常用户怎么避免 | 阈值校准+人工复核+多信号融合 |
| 7 | 点击率异常高但转化为零 | 高度疑似 IVT，按 3.2 流程排查 |

### 4.2 深度排查案例：Viewability 低

```
症状: 某 Video LI 可见率 28%（行业>60%）
排查:
  1. 确认口径: 有没有用 Video 2s 标准? → 是
  2. 拆位置: 大部分展示在页面底部折叠区 → visible_ratio 低
  3. 拆设备: App 内 webview 测量被限 → 归因于环境
  4. 拆尺寸: 小尺寸横幅在移动端 → 面积小
  5. 决策: 
     - 用视频 50%/2s + 大尺寸
     - 位置上探（above-the-fold）
     - 用 Viewability 目标出价
结果: 可见率提升到 61%
```

### 4.3 深度排查案例：品牌安全误杀正常流量

```
症状: 屏蔽"政治"分类后，某新闻品牌大规模流量锐减
排查:
  1. 分类过粗: "政治"包含正常新闻报道与选举内容
  2. 用 GARM 子分类拆: 只屏蔽"选举期间的政治广告"，保留"一般新闻报道"
  3. 加白名单: 对核心优质新闻域设 allowlist
  4. 灰度: 先 10% 流量试验再全量
结果: 误杀率 -70%，品牌安全事件仍为 0
```

---

## 五、自测题

<details><summary>Q1：MRC 对不同广告形式的可见性标准有何不同？为什么视频需要更久？</summary>
展示广告：≥50% 像素 ≥1 秒；视频广告：≥50%（大面积 ≥30%）像素 ≥2 秒连续。视频需要 2 秒是因为视频内容需要一段连续时间才能被感知/传达信息，且伴播视频常自动播放，短于 2 秒很难被认知；展示静态图内容 1 秒即可辨认。大面积伴播视频从 50% 降到 30% 是因为面积足够大时即便只露 30% 用户也已看到核心内容。
</details>

<details><summary>Q2：GIVT 与 SIVT 有什么区别？各举 2 个检测信号。</summary>
GIVT 是可规则化识别的一般无效流量；SIVT 是需要机器学习/行为建模识别的复杂无效流量。GIVT 信号：数据中心 IP、已知 crawler UA、隐藏 iframe、重复展示。SIVT 信号：机械节奏点击间隔、坐标污染（可视区外上报 visible）、跨地域物理极限速度、设备指纹异常聚类。
</details>

<details><summary>Q3：为什么第三方测量（Moat/IAS/DV）与 DV360 平台的可见性数据会有差异？至少列出 3 个原因。</summary>
(1) 定义/测量口径不同（DV360 自测 vs 第三方 MRC 测量）；(2) 时间窗口与时区不同；(3) imp_id 去重键不同导致去重不一致；(4) IVT 过滤时点不同（平台展示前剔除 vs 第三方事后标记）；(5) 第三方 log 延迟与采样。解决办法是统一口径、同窗口、对齐 imp_id 并设 ±5% 容差。
</details>

<details><summary>Q4：Ads.txt、app-ads.txt、sellers.json 各自的职责是什么？</summary>
Ads.txt：媒体发布方在根域声明谁有权售卖其网站库存（DIRECT/RESELLER）。app-ads.txt：App 通过开发者网站根域声明应用库存的授权卖家。sellers.json：卖家/SSP 托管，披露直接与间接卖家身份，配合 OpenRTB pchain 用于供应链透明。三者共同构成供应链透明度与反劫持/反劫量的基础设施。
</details>

<details><summary>Q5：如果发现某个 Line Item 点击率异常高达 8% 但转化几乎为零，你的排查顺序是什么？</summary>
1) 先看平台级 IVT 指标（dv360_get_report）；2) 按 placement/域名/App 拆解找 CTR 异常点（dv360_list_placements + report）；3) 交第三方复核是否为 SIVT；4) 用自研 IVT Scorer（fraud_score/tier）二次评分；5) 处置：异常域名/placement 加黑名单或暂停；6) 复盘把特征写回规则库。整个过程配合品牌安全排除与 Viewability 目标从源头减少无效库存。
</details>

---

## 附：本主题与知识库相关文档的定位关系

| 文档 | 侧重 | 本主题如何互补 |
|------|------|---------------|
| dv360-creative-brand-safety-deep.md | 四级防护宏观框架、事件响应、可见性优化技巧 | 本主题深入 MRC 几何标准、GIVT/SIVT 算法、第三方数据格式、买卖侧协作、可运行 Go 实现 |
| ad-fraud-detection-deep.md | 欺诈类型与通用风控策略 | 本主题聚焦 DV360 平台内品牌安全/可见性/IVT 及对应 API |
| ad-fraud-gnn-realtime-deep.md | 图神经网络实时欺诈检测 | 本主题侧重 GIVT/SIVT 可解释规则与工程实现 |
| ad-fraud-prevention-deep.md | 预防体系 | 本主题补齐平台侧品牌安全分级与测量对账 |
