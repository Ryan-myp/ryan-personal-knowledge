# 跨平台归因与增量测量深度指南

> **领域**: 广告投放 / 跨平台
> **深度**: ⭐⭐⭐⭐⭐ 实战级指南
> **标签**: cross-platform, attribution, incrementality, clean-room, shapley, markov
> **更新时间**: 2026-08-14
> **类型**: methodology/production

---

## 目录

- [一、核心概念与架构](#一核心概念与架构)
  - [1.1 从单平台视角到跨平台视角](#11-从单平台视角到跨平台视角)
  - [1.2 为什么"归因"不等于"效果"](#12-为什么归因不等于效果)
  - [1.3 增量测量的核心定义](#13-增量测量的核心定义)
  - [1.4 跨平台归因的总体架构](#14-跨平台归因的总体架构)
  - [1.5 关键术语表（Glossary）](#15-关键术语表glossary)
  - [1.6 数据孤岛与身份时空断裂](#16-数据孤岛与身份时空断裂)
  - [1.7 参与者与角色（Stakeholders & Roles）](#17-参与者与角色stakeholders--roles)
  - [1.8 归因系统的成熟度模型](#18-归因系统的成熟度模型)
- [二、深度原理解析](#二深度原理解析)
  - [2.1 各平台归因窗口与模型对比](#21-各平台归因窗口与模型对比)
  - [2.2 Google 归因模型深度详解](#22-google-归因模型深度详解)
  - [2.3 Meta（Facebook/Instagram）归因深度详解](#23-metafacebookinstagram归因深度详解)
  - [2.4 TikTok 归因深度详解](#24-tiktok-归因深度详解)
  - [2.5 DV360（Display & Video 360）归因深度详解](#25-dv360display--video-360归因深度详解)
  - [2.6 last-click vs data-driven 决策矩阵](#26-last-click-vs-data-driven-决策矩阵)
  - [2.7 Value Rules（价值规则）详解](#27-value-rules价值规则详解)
  - [2.8 增量测量方法论总览](#28-增量测量方法论总览)
  - [2.9 Geo Holdout / Geo Lift 测试](#29-geo-holdout--geo-lift-测试)
  - [2.10 GAIA（Google's Aggregate Incremental Ad Impact）](#210-gaiagoogles-aggregate-incremental-ad-impact)
  - [2.11 Holdout 测试（受众级）](#211-holdout-测试受众级)
  - [2.12 PSA（Public Service Ads）增量测试](#212-psapublic-service-ads增量测试)
  - [2.13 增量实验设计与统计推断](#213-增量实验设计与统计推断)
  - [2.14 统一归因模型设计总览](#214-统一归因模型设计总览)
  - [2.15 时间衰减模型（Time Decay）](#215-时间衰减模型time-decay)
  - [2.16 位置加权模型（Linear / Position-Based / U-Shape）](#216-位置加权模型linear--position-based--u-shape)
  - [2.17 Shapley 值归因（Shapley Value Attribution）](#217-shapley-值归因shapley-value-attribution)
  - [2.18 马尔可夫链归因（Markov Chain Attribution）](#218-马尔可夫链归因markov-chain-attribution)
  - [2.19 统一归因模型对比与选择](#219-统一归因模型对比与选择)
  - [2.20 Data Clean Room 原理与隐私计算](#220-data-clean-room-原理与隐私计算)
  - [2.21 Google Ads Data Clean Room / Amazon Marketing Cloud](#221-google-ads-data-clean-room--amazon-marketing-cloud)
  - [2.22 数据融合流程、Schema 对齐与 Join Keys](#222-数据融合流程schema-对齐与-join-keys)
  - [2.23 从归因到预算分配自动化闭环](#223-从归因到预算分配自动化闭环)
  - [2.24 差分隐私与隐私增强技术的数学原理](#224-差分隐私与隐私增强技术的数学原理)
- [三、生产环境实战](#三生产环境实战)
  - [3.1 统一事件数据管道搭建（Event Pipeline）](#31-统一事件数据管道搭建event-pipeline)
  - [3.2 统一归因引擎实现（Attribution Engine）](#32-统一归因引擎实现attribution-engine)
  - [3.3 增量测试平台落地（Incrementality Lab）](#33-增量测试平台落地incrementality-lab)
  - [3.4 Data Clean Room 生产对接](#34-data-clean-room-生产对接)
  - [3.5 归因到预算的自动化闭环实现](#35-归因到预算的自动化闭环实现)
  - [3.6 监控、告警与 SLO](#36-监控告警与-slo)
  - [3.7 端到端实战案例：跨国电商 App](#37-端到端实战案例跨国电商-app)
  - [3.8 数据血缘、版本管理与可复现性](#38-数据血缘版本管理与可复现性)
  - [3.9 成本与性能优化](#39-成本与性能优化)
- [四、常见问题与排查](#四常见问题与排查)
  - [4.1 归因窗口不一致导致的数据对不上](#41-归因窗口不一致导致的数据对不上)
  - [4.2 跨设备/跨平台身份无法打通](#42-跨设备跨平台身份无法打通)
  - [4.3 增量测试结果"没效果"但归因显示有增长](#43-增量测试结果没效果但归因显示有增长)
  - [4.4 Clean Room Join 结果为空或严重过采样](#44-clean-room-join-结果为空或严重过采样)
  - [4.5 Data-driven 归因波动剧烈、不可复现](#45-data-driven-归因波动剧烈不可复现)
  - [4.6 隐私政策（ATT / GDPR / DMA）导致数据缺口](#46-隐私政策att--gdpr--dma导致数据缺口)
  - [4.7 预算自动化震荡与风险控制](#47-预算自动化震荡与风险控制)
  - [4.8 SQL / Python 诊断速查](#48-sql--python-诊断速查)
  - [4.9 多渠道互抢功劳的归属争议](#49-多渠道互抢功劳的归属争议)
  - [4.10 数据延迟与回溯窗口问题](#410-数据延迟与回溯窗口问题)
- [五、自测题](#五自测题)
- [附录 A：数学符号约定](#附录-a数学符号约定)
- [附录 B：参考资源与延伸阅读](#附录-b参考资源与延伸阅读)

---

## 一、核心概念与架构

### 1.1 从单平台视角到跨平台视角

现代数字广告早已不是一个平台的游戏。一个用户可能在一天内经历以下完整的旅程：

```text
触发场景：用户在手机上看 YouTube 看到品牌短片
  ↓ 2 小时
用户在 Instagram 刷到同一品牌的展示广告，点击进入落地页，但未转化
  ↓ 第 2 天
用户在 Google 搜索品牌词，点击付费搜索广告，加购但未下单
  ↓ 第 3 天
用户在 TikTok 刷到达人种草视频，点赞收藏
  ↓ 第 5 天
用户回到 App 内，打开推送，完成下单
```

在这条长达 5 天的旅程中，至少有 4 个平台（YouTube/Google、Meta、TikTok、自有 App）参与了"功劳"的争夺。如果只从单一平台看：

- **Google Ads 后台**：会把这单归给最后一次点击的付费搜索广告；
- **Meta 后台**：会把这单归给早前的展示广告（在其 7 天点击+1 天浏览窗口内）；
- **TikTok 后台**：会把这单归给达人视频（在其 7 天点击窗口内）；
- **自有 App**：会把这单归给推送通知（Push）。

于是同一笔转化被 4 个平台各记了一次，加起来"转化"远多于实际生意。这就是**跨平台归因**要解决的第一个核心矛盾：**同一事实（一次真实成交），多个平台各自宣称全部功劳。**

> **一句话定义**：跨平台归因（Cross-Platform Attribution, XPA）是**在一套统一的规则下，把一次转化/成交的增量功劳，按业务约定的颗粒度（点击/曝光/触点）分配到多个广告渠道与触点**，从而回答"我的广告到底哪一笔钱产生了真实生意"。

#### 1.1.1 为什么单平台后台不足信

平台后台的归因通常是**垄断性 + 利己性**的：

1. **窗口剪裁**：平台只统计其自身定义的归因窗口内的触点，窗口之外的功劳它根本看不到；
2. **隐身触点**：平台无法看到其它平台的触点，因此它把所有功劳都推给"自己"；
3. **样本偏差**：平台后台多基于其自己的信号（点击归因倾向于"最后一击"），会系统性高估最接近转化那个触点所在平台的功劳；
4. **隐私掩码**：在 iOS ATT、GDPR 等约束下，平台能看到的数据越来越小，跨设备打通更不完整。

结果就是：**"后台转化数"是虚高的、不可跨平台相加的、被各平台故意渲染得好看的**。跨平台归因就是用来校正这套偏差的"第三方视角"。

#### 1.1.2 跨平台归因要回答的三个问题

```text
Q1: 路径问题（How）——用户转化前经历了哪些触点、什么顺序、间隔多久？
Q2: 功劳问题（Who）——每个触点/渠道应该拿到多少转化功劳？
Q3: 增量问题（What if）——如果没有某平台/某渠道的曝光，生意会损失多少？
```

- Q1 是**路径数据层**，需要统一的点击/曝光事件数据；
- Q2 是**归因模型层**，需要选择/设计分配规则；
- Q3 是**增量测量层**，需要实验或因果推断。

三者层层递进，缺一不可。**只做 Q2 不做 Q3，等于只知道"蛋糕怎么分"，却不知道"蛋糕本身有多大、广告是否把蛋糕做大了"。**

#### 1.1.3 为什么现在特别难

近年广告测量的环境发生了剧变，使得跨平台归因从"加分项"变成了"必要项"：

| 变化 | 影响 | 应对 |
| --- | --- | --- |
| iOS ATT 生效 | IDFA 大幅缺失，跨设备打通困难 | 登录态、Server-side 回传、聚合模型 |
| 第三方 Cookie 淘汰 | 浏览器端追踪断裂 | 一方数据、Clean Room、概率图谱 |
| GDPR / DMA / PDPA | PII 使用受限、数据最小化 | 差分隐私、Data Clean Room、同意管理 |
| 平台数据壁垒 | 各平台只给自有视角 | 统一归因 + 增量实验 + MMM |
| 隐私聚合（AGA） | 个体事件被聚合/掩码 | 接受聚合口径、MMM 校准 |
| 信号丢失（Signal Loss） | 转化回传不完整 | Conversion API、增量兜底 |

> **结论**：在隐私新常态下，**"一条龙打通所有用户个体"变得越来越难，业界共识是转向"个体归因 + 聚合增量 + 媒体混合建模（MMM）三轨并行"**，用不同颗粒度互相验证。

### 1.2 为什么"归因"不等于"效果"

归因回答的是"功劳怎么分"，增量回答的是"广告到底带来了多少额外生意"。二者本质差异在于**反事实（Counterfactual）**：

- 归因模型假设：**这个转化本就归因于我并归我所有**，问题只是该怎么在触点间分；
- 增量测量假设：**需要一个"不投广告"的对照组**，来估算"没有广告会有多少转化"。

用公式表达：

```text
增量转化 (Incremental Conversions) = 广告组的观察转化 - 对照组(反事实)的转化
```

如果某个渠道完全不投，总转化并没有下降 30%（尽管它后台揽下了 30% 的功劳），那么这 30% 里大部分是"本就会发生的转化"（例如品牌自然搜索、老客复购），并非这个渠道带来的**增量**。

> **经典误区**：把"归因转化数"当作"广告带来的生意增长"。举例——某品牌在 618 大促投放全渠道，总 GMV 暴涨 3 倍，每个平台后台都说自己贡献最大。但增量测试（Geo holdout）显示：即使完全不投广告，大促的自然需求也会让 GMV 涨 2 倍。因此全部广告带来的**真实增量只有 50%**，而各平台后台却合计认领了 200%。

#### 1.2.1 归因与增量的关系象限

| 维度 | 归因（Attribution） | 增量（Incrementality） |
| --- | --- | --- |
| 核心问题 | 功劳怎么在已发生转化中分配 | 广告在反事实下创造了多少额外转化 |
| 数据依赖 | 触点路径 + 转化事件 | 随机/准实验 + 对照组 |
| 是否需要实验 | 不需要，观察数据即可 | 必须要随机化或准实验设计 |
| 输出 | 渠道/触点的功劳占比 | 增量率、ROAS、增量成本、饱和曲线 |
| 因果性 | 弱（相关） | 强（可识别平均处理效应 ATE） |
| 典型工具 | 统一归因引擎、各平台后台 | Geo Lift、PSA、GAIA、Holdout、MMM |
| 服务决策 | 优化预算分配方向、创意素材评分 | 判定"该投不投、投多少" |

**两者必须结合使用**：增量测量回答"总盘子多大、要不要投、总预算多少"，归因回答"在既定预算下，钱往哪分"。业界成熟做法是 **"以增量定总量、以归因定结构"**。

### 1.3 增量测量的核心定义

**增量测量**是一整套基于实验或准实验的统计方法，用于量化广告投放在**反事实情境**下的边际业务影响力。其目标不是"分功劳"，而是估计**处理的因果效应**。

#### 1.3.1 基本因果框架（Potential Outcomes / Rubin Causal Model）

对每个用户（或地理区域）`i`，定义两个潜在结果：

```text
Y_i(1) = 用户 i 被投放广告时的转化/收入（处理组潜在结果）
Y_i(0) = 用户 i 未被投放广告时的转化/收入（对照组潜在结果）
```

我们希望估计**个体处理效应（ITE）**：

```text
τ_i = Y_i(1) - Y_i(0)
```

由于"同一用户不能同时处于处理组与对照组"，我们永远只能观察到 `Y_i(1)` 或 `Y_i(0)` 之一，这就是**根本问题**（Fundamental Problem of Causal Inference）。我们能做的是估计**平均处理效应（ATE）**：

```text
ATE = E[Y_i(1) - Y_i(0)]
```

在完全随机分组的理想实验下：

```text
ATE = E[Y | T=1] - E[Y | T=0]
```

其中 `T=1` 表示处理组，`T=0` 表示对照组。

#### 1.3.2 增量率（Incremental Lift / iROAS）

- **增量率（Lift%）**：

```text
Lift% = (处理组均值 - 对照组均值) / 对照组均值 × 100%
```

- **增量收入 ROAS（iROAS, Incremental Return On Ad Spend）**：

```text
iROAS = 增量收入 / 广告花费
       = (处理组收入 - 对照组收入) / 广告花费
```

- **增量转化率（iCVR）**：

```text
iCVR = 处理组转化率 - 对照组转化率
```

#### 1.3.3 增量测试的统一工作流

无论哪种机制（Geo Lift / Audience Holdout / PSA），核心工作流一致：

```text
① 定义目标指标（M）与处理（T）
        ↓
② 选择切入单元（Unit）：地理区域 / 用户 / 广告投放批次
        ↓
③ 设计分配（随机化 or 准实验对照）
        ↓
④ 确定样本量与检验力（a priori power analysis）
        ↓
⑤ 运行期：处理组投广告，对照组不投（或投 PSA）
        ↓
⑥ 分析期：估计 Lift、置信区间、显著性
        ↓
⑦ 解读：iROAS、饱和曲线、预算建议
        ↓
⑧ 反馈：写入预算/出价系统（预算闭环）
```

### 1.4 跨平台归因的总体架构

一套生产级的跨平台归因 + 增量测量系统，通常由七个模块组成：

```text
┌─────────────────────────────────────────────────────────────────────┐
│                     数据接入层 (Ingestion)                            │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌─────────────┐ │
│  │ Google   │ │ Meta     │ │ TikTok   │ │ DV360    │ │ 自有站/App  │ │
│  │ click/imp│ │ click/imp│ │ click/imp│ │ event    │ │ 转化事件     │ │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘ └──────┬──────┘ │
└───────┼────────────┼────────────┼────────────┼───────────────┼───────┘
        ▼            ▼            ▼            ▼               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                 事件规范化层 (Normalization / CDP)                    │
│   统一事件模型：STANDARD_EVENT (click/impression/conversion)         │
│   统一身份键：IDs → {device_id, cookie_id, advertising_id, hashed}   │
└───────────────────────────────┬─────────────────────────────────────┘
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                 身份解析 / ID 图谱层 (Identity Graph)                 │
│   cross-device & cross-platform 打通 → 生成 unified user_id           │
└───────────────────────────────┬─────────────────────────────────────┘
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                  路径构建层 (Journey Builder)                         │
│   按 unified_user_id 按事件时间排序 → 触点路径                        │
└───────────────────────────────┬─────────────────────────────────────┘
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                  归因计算层 (Attribution Service)                    │
│   规则归因 | 数据驱动 | Shapley | Markov | 时间衰减 | 位置加权        │
│   + 统一归因窗口 / value rules                                        │
└───────────────┬───────────────────────────────┬─────────────────────┘
                ▼                               ▼
┌──────────────────────────────┐   ┌───────────────────────────────┐
│   增量测量层 (Incrementality) │   │   预算/出价闭环 (Optimization) │
│   Geo lift | PSA | GAIA      │   │   incremental weight → 出价/   │
│   | Holdout | Power analysis │   │   预算分配 → 平台 API 下发     │
└──────────────────────────────┘   └───────────────────────────────┘
                └───────────────┬──────────────────────────────┬┘
                                ▼                              ▼
                     ┌──────────────────┐            ┌──────────────────┐
                     │ 报表/BI / 看板    │            │ Data Clean Room  │
                     │ (逐渠道归因,      │            │ (隐私合规融合分析)│
                     │ 增量 ROI)        │            │        └──┐       │
                     └──────────────────┘            └───────────┘       │
                                                   联网广告方/品牌方 融合分析
```

#### 1.4.1 七个模块职责速查表

| 模块 | 职责 | 关键输出 | 典型技术 |
| --- | --- | --- | --- |
| 数据接入层 | 拉取多平台点击/曝光/转化 | 原始事件湖 | API、S3、BigQuery、GCS |
| 事件规范化层 | 统一字段与语义 | 规范事件表 | ETL、CDP、事件建模 |
| 身份解析层 | 跨设备跨平台打通 | user_id 图谱 | 概率/确定性匹配 |
| 路径构建层 | 组织用户旅程序列 | 触点路径 | Spark/Flink/Python |
| 归因计算层 | 分配功劳 | 归因分担表 | Python/SQL/ML |
| 增量测量层 | 因果效应估计 | 增量率/CI | 实验平台、统计库 |
| 预算闭环层 | 反馈到投放 | 预算分配建议 | 平台 API、调度器 |

### 1.5 关键术语表（Glossary）

| 术语 | 英文 | 定义 |
| --- | --- | --- |
| 归因 | Attribution | 将转化功劳按规则分配到触点/渠道 |
| 归因窗口 | Attribution Window | 触点发生与转化之间可被认可的最长时间 |
| 点击归因 | Click-based Attribution | 只认点击触点的功劳 |
| 浏览归因 | View-through Attribution | 认展示（曝光）触点的功劳（无点击） |
| 触点 | Touchpoint | 一次点击或展示，旅程中的一个节点 |
| 路径 | Journey / Path | 用户从首次触点到最后转化的触点序列 |
| 最后点击 | Last Click | 归因给本次转化前的最后一个触点 |
| 首次点击 | First Click | 归因给路径中第一个触点 |
| 位置归因 | Position-based | 首尾各分权重，中间平分 |
| 线性归因 | Linear | 路径上所有触点平分功劳 |
| 时间衰减 | Time Decay | 越接近转化的触点权重越高 |
| 数据驱动归因 | Data-Driven Attribution (DDA) | 基于 ML 学习触点真实贡献 |
| Shapley 值 | Shapley Value | 合作博弈中按边际贡献分功劳 |
| 马尔可夫链 | Markov Chain | 把路径建模为状态转移，计算移除效应 |
| 移除效应 | Removal Effect | 删除某渠道后转化概率的下降量 |
| 增量 | Incrementality | 广告带来的反事实额外效果 |
| 增量率 | Lift % | (处理-对照)/对照 |
| 增量 ROAS | iROAS | 增量收入/花费 |
| 平均处理效应 | ATE | E[Y(1)-Y(0)] |
| 置信区间 | Confidence Interval | 参数估计的不确定范围 |
| 检验力 | Power | 1 - β，真实效应被检出的概率 |
| 显著性水平 | α | 第一类错误概率（通常0.05） |
| Geo Holdout | 地理对照 | 以地理区域为单元的实验 |
| PSA | Public Service Ads | 用公益广告替代真实广告作对照 |
| GAIA | Google's Aggregate Incremental Ad Impact | Google 聚合增量影响测量解决方案 |
| Data Clean Room | DCR | 隐私受控的数据协作环境 |
| 差分隐私 | Differential Privacy | 通过加噪保护个体隐私 |
| 安全多方计算 | MPC | 多方在不泄露明文下联合计算 |
| Join Key | 连接键 | 两表融合时匹配的公共字段 |
| 反事实 | Counterfactual | 未发生情境下的可能结果 |
| 选择偏差 | Selection Bias | 样本非随机导致的系统性偏差 |
| MMM | Media Mix Modeling | 媒体混合建模，时间序列计量经济学 |
| SUTVA | Stable Unit Treatment Value | 单元间处理互不干扰假设 |
| DID | Difference-in-Differences | 双重差分，准实验估计 |
| MDE | Minimum Detectable Effect | 最小可检测效应 |

### 1.6 数据孤岛与身份时空断裂

跨平台归因最大的工程障碍，来自两大数据问题：**数据孤岛**与**身份断裂**。

#### 1.6.1 数据孤岛

每个平台（Google、Meta、TikTok、DV360）都有其**私有的、不互通的**用户观测：

```text
        Google 侧                 Meta 侧                TikTok 侧
  ┌───────────────┐      ┌───────────────┐      ┌───────────────┐
  │ user: GID-123 │      │ user: c_userX │      │ user: T-ID-9  │
  │ click 事件     │      │ impression    │      │ click         │
  │ 仅见 Google   │      │ 仅见 Meta    │      │ 仅见 TikTok   │
  └───────────────┘      └───────────────┘      └───────────────┘
         │                      │                      │
         └────────── 互相不可见 ─┴──────────────────────┘
                            ↓
              身份（user）能不能打通，是跨平台归因的前提
```

#### 1.6.2 身份时空断裂（Identity & Time-space Fragmentation）

用户在不同平台/不同设备上呈现不同标识：

| 维度 | 标识 | 说明 |
| --- | --- | --- |
| 设备 ID | IDFA(Apple) / AAID(Android) | 受 ATT 限制后显著减少 |
| Cookie ID | 第三方 Cookie | 浏览器逐步禁用（Chrome 2024+ 弃用） |
| 平台自持 ID | GAID、Meta c_user、TikTok 匿名 ID | 平台内部 ID，跨平台不可用 |
| 登录态 ID | 邮箱 / 手机号 / 自有 user_id | 可作为确定性 bridge |
| 哈希 ID | SHA-256(email) 等 | 用于 Clean Room / 广告方匹配 |

**跨平台归因必须处理三条断裂线**：

```text
① 跨平台断裂：Google 的 A 用户 与 Meta 的 B 用户是否是同一个人？
② 跨设备断裂：用户的手机、平板、电脑是否是同一个人？
③ 时空间断裂：一次点击在第 6 天发生、转化在第 30 天，是否还在归因窗口内？
```

#### 1.6.3 身份匹配策略矩阵

| 策略 | 确定性 | 成本 | 覆盖率 | 说明 |
| --- | --- | --- | --- | --- |
| 登录匹配（Email/Phone） | 高 | 中 | 低-中 | 只有注册/登录用户可匹配 |
| 设备图谱（确定性） | 高 | 中 | 中 | 同一设备多 Cookie 合并 |
| 概率图谱（行为相似） | 中 | 高 | 高 | 用行为特征 ML 预测 |
| Hash PII 匹配 | 高 | 低 | 中 | 配合 Clean Room 使用 |
| 平台模糊（不匹配，用模型层折衷） | — | 低 | 100% | 用增量/MMM 替代个体级归因 |

> **工程建议**：生产系统中通常采用**"确定性优先 + 概率补充"的混合图谱**；在隐私强约束下退化为**平台级聚合归因（不打通个体，改用 MMM / 增量测量做总账）**。

### 1.7 参与者与角色（Stakeholders & Roles）

跨平台归因项目需要四方协同，这一节帮助读者理解组织分工与责任边界。

| 角色 | 关注点 | 主要负责模块 |
| --- | --- | --- |
| 品牌方/广告主（Brand/Advertiser） | 生意目标、ROI、预算决策 | 目标定义、预算闭环 |
| 数据团队/数据科学（Data Science） | 因果识别、模型、统计正确性 | 归因模型、增量实验、统计推断 |
| 媒体采购/增长团队（Growth Media） | 渠道执行、素材、出价 | 平台 API、投放优化 |
| 工程团队（Engineering） | 数据管道、血缘、质量、可靠性 | 接入、规范化、Clean Room、调度 |
| 法务/合规/隐私（Legal & Privacy) | GDPR/DMA/ATT、数据最小化 | 数据协议、Clean Room 合规 |

> **关键提醒**：增量与归因的结论必须能被增长团队信任并据此改预算，否则系统再漂亮也只是"报告工具"。**要让投放手里握着数据做决策，而不只是报表里有数。**

### 1.8 归因系统的成熟度模型

大多数组织从"平台后台各自为政"逐步演进到"统一归因 + 增量 + 预算闭环"。用成熟度模型帮助定位：

| 等级 | 名称 | 特征 | 典型输出 |
| --- | --- | --- | --- |
| L0 | 混沌期 | 只看各平台后台，相互打架 | 各平台转化数（虚高） |
| L1 | 统一口径 | 有统一事件管道与统一归因窗口 | 自建归因报表 |
| L2 | 统一模型 | 引入规则或数据驱动模型统一分功劳 | 渠道功劳占比 |
| L3 | 增量校准 | 用 Geo / PSA / GAIA 校准归因 | 增量率、iROAS |
| L4 | 闭环优化 | 归因+增量输入预算/出价自动化 | 自动预算分配 |
| L5 | 因果智能 | 多轨并行（个体+聚合+MMM）互相验证 | 长期最优分配 |

> 多数组织卡在 L1–L2：有统一归因报表，但没有增量校准，也没有预算闭环。**向 L3 迈进是最有价值的单步**，因为它让归因从"好看"变为"可信"。

---

## 二、深度原理解析

### 2.1 各平台归因窗口与模型对比

本节目的是先把**各平台默认行为与可配置能力**摸清楚，因为它是跨平台统一归因时"为什么对不上"的第一块肇因。

#### 2.1.1 归因窗口总对比表

| 能力维度 | Google Ads | Meta (Facebook/IG) | TikTok Ads | DV360 (Display & Video 360) |
| --- | --- | --- | --- | --- |
| 默认转化窗口（点击） | 30 天 | 7 天 | 7 天 | 可配置（常见 30 天） |
| 可调点击窗口范围 | 1–90 天 | 1 天 / 7 天 / 28 天 | 7 天 / 28 天（部分 1 天） | 自定义（灵活） |
| 默认浏览窗口（View-through） | 1 天（默认开启对部分广告） | 1 天（7天点击+1天浏览 是常见组合） | 24 小时（部分） | 可配置（默认启用 view-through） |
| 默认归因模型 | 数据驱动（DDA，若数据门闸满足）否则最后点击 | 7天点击+1天浏览（合并） | 7 天点击 | Flight级/可配置；常用 最后点击 + view-through 可配 |
| 是否支持数据驱动模型 | 支持 DDA | 部分（Advantage+ / DDA） | 有限（正推驱动优化） | 有限 |
| Value Rules | 支持（转化价值规则自定义） | 支持定制转化价值（advanced） | 有限 | 可配 |
| 跨设备归因 | 支持（登录用户 + 设备） | 支持（登录态） | 有限 | 支持（结合 Google 图谱） |
| 最小统计量要求（DDA 启用） | 至少 15,000 次转化/30天（Google 指导值） | 无严格公开阈值 | — | — |

> **重要**：以上数值为业界常见默认值，平台会不定期调整，且取决于广告类型的差异（如 App 广告 vs 网页广告）。生产中对账时**永远以平台 API 返回的实际配置为准**，不要硬编码。

#### 2.1.2 各平台归因窗口语义差异详解

**点击归因窗口（Click-through Window）**：指用户**点击**广告到发生转化之间被认可的时间窗。超过该窗口的转化不算该触点功劳。

**浏览归因窗口（View-through Window）**：指用户**看到（曝光）但未点击**广告，随后转化才被认可的时间窗。浏览归因通常仅给"展示"型广告（YouTube、Meta feed、DV360）。

两者的关系：

```text
成功路径(有点击)：
  曝光 ──► 点击 ──(归因窗口: 30天)──► 转化
                ↑
          以"点击"为归因基准

浏览归因路径(无点击)：
  曝光 ──(归因窗口: 1天)──► 转化
                ↑
          以"曝光"为归因基准，通常窗口短得多
```

#### 2.1.3 组合视图：Meta 常见的"7+1"组合

Meta 采纳的典型归因是 **"7 天点击 + 1 天浏览"**（Click 7d + View 1d）：

```text
浏览归因窗口 = 1 天（仅曝光、无点击）
点击归因窗口 = 7 天（有点击）
两者是"或"关系：只要转化落在任一窗口内即被归因给 Meta
```

这个"7+1"会**显著放大 Meta 认领的转化**，因为搜索/展示之外的少量曝光也会被计入。理解这一点对跨平台对账非常关键。

#### 2.1.4 平台差异带来的一致性问题

```text
同一用户：
  第1天  YouTube 展示 → 无点击
  第8天  用户在 App 下单

    Google(浏览窗口1天) : 已超出1天 → 不归因给展示
    Google(若开启跨设备) : 可能归因
    Meta(7+1)            : 超出1天浏览 → 可能不归因
    自有App(推送归因)     : 归因给推送
```

**结论**：由于各平台窗口不一致，**同一成交在不同平台后台"是否被认领"甚至可能互相矛盾**。统一归因的第一步就是在自建系统中**冻结一套统一的窗口与模型口径**，作为唯一事实源（Single Source of Truth）。

### 2.2 Google 归因模型深度详解

#### 2.2.1 Google 支持的归因模型

| 模型 | 类型 | 说明 | 适用场景 |
| --- | --- | --- | --- |
| 最后点击（Last Click） | 规则 | 全部功劳给最后一个触点 | 简单、可解释；但高估尾部渠道 |
| 首次点击（First Click） | 规则 | 全部功劳给第一个触点 | 关注"获客入口" |
| 线性（Linear） | 规则 | 路径上所有触点平分 | 各触点作用均匀假设 |
| 时间衰减（Time Decay） | 规则 | 越接近转化权重越大 | 品牌期广告效果衰减快 |
| 位置归因（Position Based） | 规则 | 首尾各 40%，中间 20% | 兼顾冷启动与临门一脚 |
| 数据驱动（Data Driven, DDA） | 数据驱动 | 用转化数据 ML 学习贡献 | 数据充分时最推荐 |

#### 2.2.2 Google 数据驱动归因（DDA）原理

Google DDA 实质上使用基于**机器学习 + Shapley 思想**的算法度量每个触点对转化的边际贡献。Google 官方主要为"数据驱动归因"实现的是基于转化数据的、把功劳按学习到的贡献比例分配的模型。

关键启用条件（官方指导值）：

```text
DDA 启用条件（近似）：
  - 过去 30 天内的转化 ≥ 15,000 次
  - 该转化行动有足够的点击数据与路径多样性
  - 数据足以学习触点间的边际贡献
```

> 不足以上阈值的转化行动会自动回退到"最后点击"。

#### 2.2.3 Google 归因窗口设置

Google 支持在**转化行动（Conversion Action）**级别配置归因窗口：

```text
转化事件配置示例（Google Ads UI / API）：
  归因模型      = DATA_DRIVEN
  点击窗口      = 30 天（可调 1~90）
  浏览窗口      = 1 天（可开关）
  跨设备        = 开启（合并同一 Google 用户的跨设备路径）
  独立转化计数  = 开启（允许同一用户多次转化各获一次归因）
```

#### 2.2.4 通过 Google Ads API 读取归因设置

```json
{
  "results": [
    {
      "conversionAction": {
        "resourceName": "customers/123/conversionActions/456",
        "id": 456,
        "name": "Purchase",
        "type": "PURCHASE",
        "attributionModelSettings": {
          "attributionModel": "DATA_DRIVEN",
          "clickAttributionLookbackWindowDays": 30,
          "viewAttributionLookbackWindowDays": 1,
          "dataDrivenModelStatus": "ENABLED"
        },
        "countingType": "LAST_CLICK"
      }
    }
  ]
}
```

#### 2.2.5 Google 归因与跨设备

Google 拥有较完善的身份体系（Google 账号登录 + 设备图谱），因此在跨设备归因上有天然优势。启用"跨设备归因"后，Google 可以把同一用户的手机 + 电脑 + 平板路径合并，从而更好地把功劳分配给那些在 PC 上种草、在手机上成交的旅程。

```text
跨设备归因示例：
  PC 上搜索并点击广告（Day 1）
  手机 App 直接下单（Day 5）
  → 若跨设备开启，该转化可归因回 PC 的搜索点击
  → 若未开启，该转化可能被记为"无点击"/自然转化
```

### 2.3 Meta（Facebook/Instagram）归因深度详解

#### 2.3.1 Meta 归因窗口组合

Meta 的归因窗口以"点击窗口 + 浏览窗口"组合提供，常见预设：

| 配置名 | 说明 |
| --- | --- |
| 7 天点击 + 1 天浏览（默认，推荐给转化优化） | 7d click + 1d view |
| 1 天点击 | 只认 1 天内的点击 |
| 7 天点击 | 只认 7 天内的点击 |
| 28 天点击 + 1 天浏览 | 较长窗口，适合高决策周期商品 |
| 28 天点击 + 28 天浏览 | 最长，适合高客单/长尾 |

#### 2.3.2 Meta 归因模型

Meta 后台报表的归因本质上是**基于时间/最后的碰撞**规则归因 + **数据驱动**优化并存：

- **报表归因（Reporting）**：默认基于"7天点击 + 1天浏览"的最后触点优先；
- **优化归因（Optimization）**：广告投放优化使用 Meta 自己训练的转化模型，与实际报告归因不一定一致。

Meta 也提供自定义**转化价值与价值规则**，允许在同一事件上叠加不同价值。

#### 2.3.3 Meta Conversions API (CAPI) 与 Pixel 的归因协同

Meta 归因数据来自 Pixel + CAPI，二者配合后 Meta 能识别更多转化：

```text
Pixel（浏览器端） → 仅当用户浏览器保留 fbclid 且未 opt-out
CAPI（服务端）    → 广告主把转化事件从服务器直接发给 Meta
                    （不依赖 cookie，不受浏览器限制）

更好的匹配 = 更高的报告转化完整性
匹配选项：email / phone / waid / fbclid / 移动设备ID 等
```

#### 2.3.4 Meta 归因窗口 API 查询

```python
from facebook_business.adobjects.adsinsights import AdsInsights

fields = [
    AdsInsights.Field.campaign_id,
    AdsInsights.Field.campaign_name,
    AdsInsights.Field.spend,
    AdsInsights.Field.actions,
    AdsInsights.Field.conversions,
    AdsInsights.Field.purchase_roas,
]
params = {
    'date_preset': 'last_30d',
    'time_increment': 1,
    # 归因窗口通过 time_range 或 attribution window 相关参数控制
    'action_attribution_windows': ['7d_click', '1d_view'],
}
```

#### 2.3.5 Meta 增量测试（PSA，详见 2.12）

Meta 平台内最强的增量手段是 **PSA（Public Service Ads）**，它把对照组改为投放公益广告，从而在 Meta 生态内测量"真实广告 vs 无广告"的增量。这是 Meta 官方的增量测试路径。

### 2.4 TikTok 归因深度详解

#### 2.4.1 TikTok 归因窗口

| 维度 | 说明 |
| --- | --- |
| 默认点击窗口 | 7 天 |
| 可调范围 | 7 天 / 28 天（部分场景 1 天） |
| 浏览窗口 | 24 小时（需个性化归因配置） |
| 归因方式 | 主要基于点击；部分用浏览归因 |

#### 2.4.2 TikTok 归因特征

- **归因粒度**：TikTok 提供 Web Pixel 与 Events API 两种数据接入；
- **窗口偏短**：相比 Google 30 天，TikTok 默认 7 天，会系统性低估长决策链的转化；
- **自助归因模型**：TikTok 支持 "Click last touch" 等，也在持续推出 Data-driven 能力。

#### 2.4.3 TikTok 最短归因 vs 最长归因对比示例

```text
场景：用户 3 周前点过 TikTok 广告，今天才下单

  默认 7 天点击窗口 : 点击早已超 7 天 → TikTok 不归因（转化被别的渠道认领）
  28 天点击窗口     : 点击在 21 天内   → TikTok 归因该转化
```

> **对齐建议**：若品牌决策周期长（如 B2B SaaS、高客单家具），跨平台统一归因时不能简单用各平台默认窗口，而应基于**自有转化分布**重校准统一窗口。

#### 2.4.4 TikTok Event API 与 TikTok Pixel

TikTok 与 Meta 类似，同时提供浏览器端 Pixel 与服务端 Events API。对归因而言，Events API（服务端）能弥补浏览器端信号丢失，提高转化回传完整性，从而让窗口内的归因更准确。

### 2.5 DV360（Display & Video 360）归因深度详解

#### 2.5.1 DV360 归因窗口与灵活性

DV360 是 Google 的 DSP（需求方平台），归因能力比普通竞价更灵活：

| 能力 | 说明 |
| --- | --- |
| 归因窗口 | 高度可配置（常为 30 天点击，可自定义） |
| 转化来源 | Floodlight（Google 转化跟踪标签）+ CM 数据 |
| 归因模型 | 支持 last click、first click、linear、position、time decay 等 |
| View-through | 默认纳入（展示型核心场景），权重可调 |
| 跨设备 | 借用 Google 的统一身份图谱 |

#### 2.5.2 DV360 归因常见坑

1. **View-through 默认开启**：DV360 展示归因大量来自浏览归因，跨平台对账时若不单独看"view-through conversions"会严重高估 DV360；
2. **Floodlight 计数模式**：需区分"每次转化计数"与"每次点击计数"；
3. **归因窗口配错**：Floodlight 上窗口设置不统一会导致 DV360 与 CM 数据不一致。

#### 2.5.3 用 Floodlight 做转化跟踪的要点

```html
<script>
  // Floodlight 标记：GTM 或直接内嵌
  var axel = Math.random() + "";
  var a = axel * 10000000000000;
  document.write('<iframe src="https://12345678.fls.doubleclick.net/activityi;'
  + 'src=12345678;type=site;cat=conv;dc_lat=;dc_rdid=;'
  + 'tag_for_child_directed_treatment=;tfua=;npa=;gdpr=${GDPR};'
  + 'gdpr_consent=${GDPR_CONSENT};ord=' + a
  + '?" width="1" height="1" frameborder="0" style="display:none"></iframe>');
</script>
```

#### 2.5.4 Google Marketing Platform（GMP）全家桶协同

DV360 往往与 Campaign Manager 360（CM360）、Search Ads 360（SA360）组合，形成 GMP 生态。SA360 负责搜索归因，CM360 负责展示/视频打点与 Floodlight，DV360 负责 DSP 投放。真正的"全链路"归因往往在 CM360 / SA360 层面完成跨渠道合并，而非在 DV360 单点。

```text
GMP 归因协同：
  SA360  → 搜索 + 购物归因
  CM360  → 展示/视频 Floodlight + 跨渠道归因
  DV360  → DSP 投放执行
  Analytics/BigQuery → 汇聚统一数据
```

### 2.6 last-click vs data-driven 决策矩阵

选择归因模型本质上是在**可解释性 / 准确性 / 数据需求 / 稳定性**之间权衡。

| 决策维度 | 最后点击（Last Click） | 数据驱动（Data Driven） | Shapley / 移除效应 |
| --- | --- | --- | --- |
| 可解释性 | 极高（一眼看懂） | 中（黑盒但可给 Shap 解释） | 高（有经济学含义） |
| 准确性 | 低（严重高估最后触点） | 高（学到真实边际贡献） | 高（基于合作博弈最优性） |
| 数据需求 | 几乎为零 | 高（≥15k 转化） | 中-高 |
| 稳定性 | 高 | 中（易受噪声影响） | 中 |
| 因果性 | 低 | 中 | 中-高 |
| 工程成本 | 低 | 高（模型训练/监控） | 中（计算合作博弈） |
| 适用 | 起步、小数据、需要给投放解释 | 大转化量、成熟组织 | 需要严谨的预算分配经济学 |
| 平台支持 | 全平台 | Google(Meta部分) | 需自建 |

#### 2.6.1 决策流程图

```text
数据是否足够多(≥15k 转化/月)？ ──否──► 用规则模型(最后点击/时间衰减/位置)
        │是
        ▼
是否需要严格因果/经济学最优分配？ ──是──► Shapley / 移除效应
        │否
        ▼
是否能接受黑盒并由业务验证？ ──是──► 数据驱动(DDA)
        │否
        ▼
用规则 + A/B 验证迭代(时间衰减 或 位置)
```

> **生产建议**：多数组织采用**"规则模型起步 → 数据充分后升级 DDA/Shapley → 用增量实验校准"**的渐进路线，避免一步到位引起投放团队信任崩塌。

### 2.7 Value Rules（价值规则）详解

归因很多时候不是"1 次转化=1 次功劳"，而是**不同转化事件价值不同**。Value Rules（价值规则）用于**给不同转化事件/不同属性用户设定不同价值**，让归因与预算优化以"价值"而非"事件数"驱动。

#### 2.7.1 Value Rules 的典型用途

```text
① 分层价值：新客转化价值 100，老客重复购买价值 40
② 事件加权：付费(100) > 加购(20) > 浏览详情(5)
③ 用户价值：高 LTV 品类 +50%
④ 边际规则：首单对复购的提升额外计价值
```

#### 2.7.2 Value Rules 配置示例（概念性 JSON）

```json
{
  "value_rules": [
    {
      "rulename": "new_customer_booking",
      "event": "purchase",
      "criteria": {"customer_tier": "VIP"},
      "value": 120,
      "priority": 1
    },
    {
      "rulename": "regular_booking",
      "event": "purchase",
      "criteria": {"customer_tier": "REGULAR"},
      "value": 40,
      "priority": 2
    },
    {
      "rulename": "add_to_cart",
      "event": "add_to_cart",
      "value": 20,
      "priority": 3
    },
    {
      "rulename": "fallback",
      "event": "*",
      "value": 0,
      "priority": 99
    }
  ]
}
```

#### 2.7.3 Value Rules 与增量 ROAS 的结合

一旦给每笔转化打了价值，就可以计算**带价值的增量指标**：

```text
增量价值收入    = Σ(处理组转化价值) - Σ(对照组转化价值)
iROAS(价值版)  = 增量价值收入 / 花费
```

价值规则让"归因权重"从一开始就输入到**预算与出价优化**中（详见 2.23 与 3.5），因为平台回传的"转化价值"会直接影响智能出价的预算让渡。

### 2.8 增量测量方法论总览

增量测量有四种主流机制，它们在**切入单元、对照组构造、成本、统计性质**上不同。

| 机制 | 切入单元 | 对照组构造 | 适用 | 成本 | 统计强度 |
| --- | --- | --- | --- | --- | --- |
| Geo Holdout / Lift | 地理区域（DMA/国家/州） | 相似地理区域不投放 | 全国性/线上+线下都要 | 高 | 中-高 |
| Audience Holdout | 用户 | 随机不暴露的用户组 | 线上纯转化 | 中 | 高 |
| PSA（Meta） | 用户 | 同样预算投放公益广告 | Meta 平台内 | 中 | 高 |
| GAIA（Google） | 聚合测量 | Google 机制内对照 | Google 全渠道 | 中 | 中 |
| 模型化 / MMM | 时间序列 | 计量经济学反事实 | 长周期、无随机化 | 低 | 中 |

#### 2.8.1 方法选型决策树

```text
是否能做严格随机化？
│
├─ 能，且单位=用户 → Audience Holdout / PSA(平台)
│
├─ 能，且单位=地理区域 → Geo Holdout / Geo Lift
│
└─ 不能随机化（预算/合规限制）→ MMM / 准实验(DID, 合成控制)

其次考虑：
  - 预算规模：Geo 需要较大地理池与预算
  - 隐私合规：用户级对照在新隐私下可能受限 → 聚合级(GAIA/MMM)
  - 决策周期：A/B/C 长链路高客单 → 长窗口 + MMM 交叉验证
```

### 2.9 Geo Holdout / Geo Lift 测试

#### 2.9.1 原理

**Geo Lift** 以地理区域为随机单元做增量测试。把全国拆成许多小地理区域（DMA、州、城市），随机分为**处理组**（投广告）与**对照组**（不投或少投），比较两组在测试期与基期（pre-period）的**转化/收入差异**。

#### 2.9.2 核心统计模型：DID（双重差分）

Geo Lift 常用**双重差分（Difference-in-Differences, DID）**：

```text
ATE = (处理组测试期均值 - 处理组基期均值)
    - (对照组测试期均值 - 对照组基期均值)
```

回归形式（对每个地理区域 g，时间 t）：

```text
Y_gt = β0 + β1·Treated_g + β2·Post_t + β3·(Treated_g × Post_t) + ε_gt
其中 β3 即 DID 估计量 = ATE
```

#### 2.9.3 统计细节与关键假设

- **平行趋势假设（Parallel Trends）**：无处理时，处理组与对照组的变化趋势应一致；需要在基期验证；
- **SUTVA**：地理区域间互不影响（跨区域用户流动会造成污染，需控制）；
- 由于地理单元数通常较少（几十个），**自由度低**，需要更大效应或更长测试期；
- 常辅以**聚类稳健标准误**（把误差聚类到地理区域）。

#### 2.9.4 Geo Lift 的样本量直觉（公式推导）

对地理单元数 N、每组各 N/2、组内方差 σ²、双尾 α、检验力 1-β，可测到的最小效应（MDE）近似：

```text
MDE ≈ (z_{1-α/2} + z_{1-β}) · sqrt( 2σ² / (N/2) )
    = sqrt(8) · (z_{1-α/2} + z_{1-β}) · σ / sqrt(N)
```

这里 `z_{1-α/2}` 为 α=0.05 时的 1.96，`z_{1-β}` 为 power=0.8 时的 0.84。于是：

```text
MDE = sqrt(8) × (1.96 + 0.84) × σ / sqrt(N)
    ≈ 6.26 × σ / sqrt(N)
```

可见：**可测最小效应与地理单元数的平方根成反比**。要测更小的增量，需要更多地理单元或更长时间（用时间换取更多伪样本）。

#### 2.9.5 Geo Lift 时间与预算建议

| 因素 | 建议 |
| --- | --- |
| 最少地理单元 | ≥ 24（理想 48+） |
| 测试时长 | ≥ 基期 2 倍以上；通常 4–8 周 |
| 预算占比 | 测试期增量预算通常占总预算 5–15% |
| 频率 | 季度级或按重大战役前评估 |
| 辅助 | MMM coefficient 交叉验证 |

#### 2.9.6 Geo 分配与样本量计算 Python

```python
import scipy.stats as st

def geo_mde(sigma, n_units, alpha=0.05, power=0.80):
    """
    sigma   : 地理单元基期收入的组内标准差
    n_units : 总地理单元数（平分成两组）
    返回可检测的最小收入差 MDE
    """
    z_alpha = st.norm.ppf(1 - alpha / 2)
    z_beta = st.norm.ppf(power)
    mde = (2 ** 0.5) * (z_alpha + z_beta) * sigma / (n_units / 2) ** 0.5
    return mde

# 例：48 个地理单元，基期收入标准差 = 2 万
print("MDE≈", round(geo_mde(20000, 48), 0), "单位/单元/期")
```

### 2.10 GAIA（Google's Aggregate Incremental Ad Impact）

#### 2.10.1 GAIA 概述

**GAIA** 是 Google Marketing Platform 提供的**聚合增量影响测量**解决方案，用于在**不泄露用户级数据**的前提下，估计广告对转化/销售的**增量影响**。

主要特征：

```text
① 聚合级（Aggregate）分析：不使用个体用户数据
② 测量 Google 渠道（搜索 + YouTube + Display）的增量
③ 与提升度测量(Longitudinal/experimental)结合
④ 在隐私合规前提下给出增量 ROAS、饱和曲线
```

#### 2.10.2 GAIA 测量机制

GAIA 采用"对照组-处理组"在**聚合层面**对比 + 反事实建模：

```text
处理组预算区（有广告）的销售
                       →
对照组（无广告机会）的反事实销售
                       ↓
增量 = 处理销售 - 反事实销售
```

GAIA 会把转化数据、Geo 对照组、建模合成，输出：

```text
- 增量转化数
- 增量收入
- 增量 ROAS（iROAS）
- 饱和曲线（Spend-Response）
- 渠道贡献分解
```

#### 2.10.3 GAIA 与关系型增量测量的区别

| 特性 | GAIA | 传统 Geo/PSA（个体级） |
| --- | --- | --- |
| 数据单元 | 聚合 | 个体/地理 |
| 隐私压力 | 低（不处理个体数据） | 中（需处理个体数据） |
| 随机化 | 部分机制 | 强随机化 |
| 可实现性 | 中（Google 生态内） | 高（通用） |
| 适用 | Google 渠道贡献评估、饱和分析 | 预算打架、跨渠道基准 |

> **提示**：GAIA 与 MMM 常组合：GAIA 给 Google 渠道一个"增量基准"，MMM 把全渠道放在一起建模，二者互相验证。

### 2.11 Holdout 测试（受众级）

#### 2.11.1 原理

**Audience Holdout** 以**用户**为单元：把目标受众随机分成处理组（投放广告）与对照组（不投放），对比两组的转化差异。这是"增量测量的黄金标准"，因为随机化最严格。

```text
目标受众(30 天活跃) 100%
        │
        ├─ 处理组(90%)：正常展示/点击广告 → 收集转化 Y(1)
        │
        └─ 对照组(10%)：完全不出现在广告曝光中 → 收集转化 Y(0)

增量转化 = E[Y(1)] - E[Y(0)]
```

#### 2.11.2 对照组的"干净"要求

对照组必须**完全不受广告影响**，且不因未看到广告而行为改变：

- 技术上：通过受众排除/黑名单让对照组用户永不匹配到广告；
- 风险：可能是因为"竞品看到"或"自曝"导致对照组污染；
- 个体级对照有**选择偏差**风险：若随机化不干净，处理组与对照组行为基线不同，增量估计有偏。

#### 2.11.3 计算与评估

```text
处理组转化率 p1 = 处理组转化 / 处理组样本
对照组转化率 p0 = 对照组转化 / 对照组样本
增量率 Lift = (p1 - p0) / p0
增量转化   = (p1 - p0) × 处理组规模
iROAS      = (处理组收入 - 对照组收入) / 花费
```

### 2.12 PSA（Public Service Ads）增量测试

#### 2.12.1 什么是 PSA

**PSA（Public Service Ads）**：Meta 提供的一种**增量测试工具**。方法是把原本应投给目标用户的广告预算，把**部分用户（对照组）改为投放公益广告（PSA）**，从而让对照组"同样被投放、同样占据广告位/注意力"，但展示的是非商业内容。

```text
处理组：给用户展示真实品牌广告 → 测量转化
对照组：给用户展示公益广告 PSA    → 测量"没有商业广告"的基线转化
```

#### 2.12.2 PSA 的优点与缺点

| 优点 | 缺点 |
| --- | --- |
| 随机化严格，因果性强 | 需牺牲部分预算（对照组投放 PSA 无商业转化） |
| 控制了"展示本身"的干扰（占位效应） | 只在 Meta 生态内有效 |
| 可测 Meta 内广告 vs 无广告增量 | PSA 展示也可能带来品牌暗示（轻微污染） |
| 结果可集成到 Meta 报表 | 无法覆盖 Google/TikTok 渠道 |
| 官方支持、半自动化 | 需要规划足够的对照组规模 |

#### 2.12.3 PSA 增量结果解读

```text
假定 PSA 测试结果：
  处理组转化率 = 5.0%
  对照组转化率 = 3.8%
  增量率 lift  = (5.0 - 3.8)/3.8 = 31.6%
  iROAS        = 由收入差与花费算出

若 Lift 不显著（置信区间包含 0），说明"在 Meta 上的投放没有带来显著增量"，
应缩减预算或重新评估素材/受众。
```

#### 2.12.4 PSA 实施注意点

```text
□ 对照组比例建议 ≥ 10%（否则检验力太低）
□ 需保证对照组用户"真的只看到 PSA"，不混入真实广告
□ 测试期需足够长以覆盖归因窗口
□ 基线期（pre-period）数据用于拟合与校准
□ 不同 objective（转化 vs 流量）需分别设计
```

### 2.13 增量实验设计与统计推断

本节是增量实验**最硬核**的部分：样本量、检验力、置信区间背后的完整数学。

#### 2.13.1 假设检验框架

对两比例（处理 vs 对照）做检验：

```text
H0: p1 = p0   （广告无增量）
H1: p1 ≠ p0   （广告有增量，双侧）
```

检验统计量（两比例之差的 Z 检验）：

```text
Z = (p̂1 - p̂0) / sqrt( p̂(1-p̂)·(1/n1 + 1/n0) )
其中 p̂ = (x1 + x0)/(n1 + n0) 为合并比例
```

#### 2.13.2 样本量公式推导（比例型）

目标：在显著性 α、检验力 1-β 下，检测到最小可检测效应 δ = p1 - p0。

对两组各 n 的平衡设计，样本量近似：

```text
n ≈ (z_{1-α/2} + z_{1-β})² · [ p0(1-p0) + p1(1-p1) ] / δ²
```

- `z_{1-α/2}`：α=0.05 → 双侧临界 1.96
- `z_{1-β}`：power=0.8 → 0.84
- p0：对照组基础转化率
- p1 = p0 + δ：处理组转化率

把 1.96 和 0.84 代入，得常用形式：

```text
n ≈ 7.84 · [ p0(1-p0) + p1(1-p1) ] / δ²
```

#### 2.13.3 数值算例

假设某 App 对照组基础转化率 p0=0.02，希望检测到增量率 30%，即：

```text
δ = 0.02 × 0.30 = 0.006
p1 = 0.026
n ≈ 7.84 · [ 0.02×0.98 + 0.026×0.974 ] / 0.006²
  ≈ 7.84 · [ 0.0196 + 0.0253 ] / 0.000036
  ≈ 9775
```

**每组约需 9,775**，两组合计约 2 万用户。

> 结论：要检测小增量率，样本量会膨胀得很快——这是为什么品牌广告"看起来没增量"往往是因为**样本不够、检验力不足**，而不是真的没增量。

#### 2.13.4 改用"收入"型指标（连续型）的样本量公式

当指标是收入（连续变量）时，样本量公式：

```text
n ≈ (z_{1-α/2} + z_{1-β})² · 2σ² / δ²
```

其中 σ² 是收入方差，δ 是期望检测的收入差。代入 1.96 与 0.84：

```text
n ≈ 7.84 · 2σ² / δ² = 15.68 · σ² / δ²
```

#### 2.13.5 置信区间（Confidence Interval）

对增量率 Lift 的置信区间，先算增量转化率的 CI：

```text
SE(p̂1 - p̂0) = sqrt( p̂1(1-p̂1)/n1 + p̂0(1-p̂0)/n0 )
95% CI = (p̂1-p̂0) ± 1.96 · SE

若 CI 包含 0 → 不显著；若不包含 0 → 统计显著。
```

#### 2.13.6 Python 实现：样本量计算

```python
import scipy.stats as st

def sample_size_proportion(p0, lift, alpha=0.05, power=0.80):
    """
    计算两比例检验所需每组样本量（平衡设计）。
    p0    : 对照组基础转化率
    lift  : 期望增量率（小数，如 0.30 表示 30%）
    alpha : 显著性水平
    power : 检验力 1-beta
    """
    delta = p0 * lift          # 期望可检测的转化率差
    p1 = p0 + delta            # 处理组转化率
    z_alpha = st.norm.ppf(1 - alpha / 2)   # 双侧
    z_beta = st.norm.ppf(power)
    n = ((z_alpha + z_beta) ** 2 *
         (p0*(1-p0) + p1*(1-p1))) / (delta ** 2)
    return max(1, int(round(n)))

p0 = 0.02
for lift in (0.10, 0.20, 0.30, 0.50):
    print(f"p0={p0} lift={lift:.0%} 每组样本量≈{sample_size_proportion(p0, lift)}")
```

输出（示意）：

```text
p0=0.02 lift=10% 每组样本量≈87246
p0=0.02 lift=20% 每组样本量≈21812
p0=0.02 lift=30% 每组样本量≈9694
p0=0.02 lift=50% 每组样本量≈3490
```

#### 2.13.7 Python 实现：假设检验与 CI

```python
import scipy.stats as st

def two_prop_test(n1, x1, n0, x0, alpha=0.05):
    """两比例之差的 Z 检验与置信区间"""
    p1, p0 = x1 / n1, x0 / n0
    pc = (x1 + x0) / (n1 + n0)     # 合并比例
    se = (pc * (1 - pc) * (1 / n1 + 1 / n0)) ** 0.5
    z = (p1 - p0) / se
    p_value = 2 * (1 - st.norm.cdf(abs(z)))   # 双侧
    # 用两样本各自方差做置信区间
    se2 = (p1*(1-p1)/n1 + p0*(1-p0)/n0) ** 0.5
    ci_lo = (p1 - p0) - 1.96 * se2
    ci_hi = (p1 - p0) + 1.96 * se2
    lift = (p1 - p0) / p0
    return {
        "p1": p1, "p0": p0,
        "z": z, "p_value": p_value,
        "ci_diff": (ci_lo, ci_hi),
        "lift": lift,
        "significant": p_value < alpha,
    }

res = two_prop_test(n1=10000, x1=270, n0=10000, x0=200)
print(res)
```

#### 2.13.8 检验力分析（Power Analysis）

在固定样本量下，计算能达到的检验力：

```python
import scipy.stats as st

def power_for_proportion(n, p0, lift, alpha=0.05):
    delta = p0 * lift
    p1 = p0 + delta
    z_alpha = st.norm.ppf(1 - alpha / 2)
    se = ((p0*(1-p0) + p1*(1-p1)) / n) ** 0.5
    std_normal = (abs(delta) / se) - z_alpha
    return st.norm.cdf(std_normal)

for n in (5000, 10000, 20000, 40000):
    print(f"n={n} 检验力={power_for_proportion(n, 0.02, 0.30):.3f}")
```

#### 2.13.9 伪发现率与多重检验

若同时测多个指标或多个渠道，会放大 α（多重比较问题）。用 **Bonferroni** 或 **FDR（BH 方法）** 校正：

```python
def bonferroni(alpha, m):
    return alpha / m

def bh_fdr(pvals, alpha=0.05):
    """Benjamini-Hochberg 校正，返回显著阈值"""
    import numpy as np
    p = np.sort(np.asarray(pvals, dtype=float))
    m = len(p)
    thresh = [(i + 1) / m * alpha for i in range(m)]
    below = p <= thresh
    if not below.any():
        return 0.0
    return float(thresh[int(np.where(below)[0][-1])])
```

#### 2.13.10 增量实验的质量检查清单

```text
□ 随机化是否充分（检验处理/对照组在年龄、地区、设备等协变量上是否平衡）？
□ 是否存在 SUTVA 违规（用户间/区域间相互污染）？
□ 对照组是否真的"无广告"（无曝光无点击）？
□ 基期是否足够长以稳定基线？
□ 样本量是否达到检验力要求（先算 n 再上线）？
□ 是否做了多重比较校正？
□ 结果是否稳健（换统计量/换聚类/做敏感性分析）？
□ 是否有外部因素（季节、竞品变动）混淆？
```

#### 2.13.11 协变量平衡检验

在分析前，先验证处理/对照组在关键协变量上是否平衡（若随机化充分应基本平衡）：

```python
import scipy.stats as st

def covariate_balance(df, treatment_col, covariate):
    """对连续协变量做两样本 t 检验；分类变量可用卡方"""
    g1 = df[df[treatment_col] == 1][covariate]
    g0 = df[df[treatment_col] == 0][covariate]
    stat, p = st.ttest_ind(g1, g0)
    return {"covariate": covariate, "t": stat, "p_value": p,
            "balanced": p > 0.05}
```

### 2.14 统一归因模型设计总览

自建统一归因引擎时，核心是"把原始触点路径 + 一套模型规则 → 输出每个触点/渠道的功劳比例"。

统一归因模型分两大类：

```text
规则归因（Rule-based）：
   首次点击 / 最后点击 / 线性 / 时间衰减 / 位置加权(首尾加权, U-shape)
   可解释、零数据、快速上线

算法归因（Method-based）：
   数据驱动（DDA）/ Shapley 值 / Markov 链移除效应
   需要路径数据、可学到边际贡献、结果更公平
```

#### 2.14.1 统一归因引擎的输入输出

```text
输入：
  - 统一路径表 journeys(user_id, conversion_id, ordered touchpoints)
  - 每条转化对应的价值 value
  - 配置的模型与参数

输出：
  - 触点贡献表 touch_credit(touchpoint_id, channel, credit)
  - 渠道聚合表 channel_attribution(channel, total_credit, pct)
```

### 2.15 时间衰减模型（Time Decay）

#### 2.15.1 数学定义

时间衰减给**距离转化越近的触点越高权重**。设路径上有 K 个触点，第 i 个触点距离转化的时间差为 `Δt_i`（越接近转化越小），半衰期参数为 `λ`，则第 i 个触点的原始权重：

```text
w_i = 2^(-Δt_i / λ)      （以 λ 为半衰期的指数衰减）
```

另一种常用指数形式：

```text
w_i = exp(-Δt_i / τ)     （τ 为时间常数）
```

归一化后得到每个触点的功劳比例：

```text
credit_i = w_i / Σ_j w_j
```

其中 `Σ_j w_j` 为路径上所有触点原始权重之和。

#### 2.15.2 性质

- 单调性：越近转化权重越大；
- 半衰期 λ 控制衰减速度；λ 越大衰减越慢（远端触点仍有话语权）；
- 与时间戳强相关，需要准确的触点时间；
- 常见默认半衰期：7 天（λ=7）。

#### 2.15.3 Python 实现

```python
from datetime import datetime

def time_decay_attribution(touchpoints, half_life_days=7.0):
    """
    touchpoints: list of (channel, event_time: datetime)
    half_life_days: 半衰期天数 λ
    返回每个触点的贡献比例 credit
    """
    conv_time = max(tp[1] for tp in touchpoints)  # 用最后触点近似转化时刻
    raw = []
    for ch, t in touchpoints:
        dt_days = (conv_time - t).total_seconds() / 86400.0
        w = 2 ** (-dt_days / half_life_days)
        raw.append((ch, t, w))
    total = sum(w for _, _, w in raw)
    return [(ch, t, w / total) for ch, t, w in raw]

# 示例：5 天前 YouTube 曝光、2 天前 Meta 点击、1 小时前 Google 点击
tps = [
    ("YouTube", datetime(2026, 8, 9, 10, 0)),
    ("Meta",    datetime(2026, 8, 12, 14, 0)),
    ("Google",  datetime(2026, 8, 14, 9, 0)),
]
for ch, t, c in time_decay_attribution(tps, half_life_days=7):
    print(f"{ch:8s} 贡献={c:.2%}")
```

输出（示意）：Google 分会拿最多（因为靠转化最近），Meta 次之，YouTube 最少。

#### 2.15.4 时间衰减 vs 最后点击

```text
                        YouTube(5d)  Meta(2d)  Google(1h)
最后点击(Last Click)     0%          0%        100%
时间衰减(λ=7d)           ~20%        ~33%      ~47%
```

时间衰减**平滑**了远端渠道的被低估问题，但比线性/位置更重视近端。

### 2.16 位置加权模型（Linear / Position-Based / U-Shape）

#### 2.16.1 线性归因（Linear）

路径上所有触点均分功劳：

```text
credit_i = 1 / K     （K = 路径触点总数）
```

#### 2.16.2 位置归因（Position-Based / U-Shape）

首尾触点权重高、中间触点权重低。常见分配（首 40% / 末 40% / 中间 20%）：

```text
首触点 credit = 0.40
末触点 credit = 0.40
中间每个触点 credit = 0.20 / (K - 2)   （K>2 时）
```

当 K=2 时：首末各 0.5；K=1 时：该触点 1.0。

#### 2.16.3 数学式子（推广形式）

设首部权重 `w_first`、尾部权重 `w_last`、中部剩余 `w_mid = 1 - w_first - w_last`：

```text
credit_1        = w_first
credit_K        = w_last
credit_i         = w_mid / (K-2)   for 2 <= i <= K-1
```

典型配置：

```text
线性        : w_first=0, w_last=0, 中间=1/K
U-shape(标准): w_first=0.4, w_last=0.4, w_mid=0.2
自定义       : 可调 w_first / w_last 比例
```

#### 2.16.4 Python 实现

```python
def position_based_attribution(touchpoints, w_first=0.4, w_last=0.4):
    """位置归因。touchpoints 为有序触点(channel, time)列表"""
    k = len(touchpoints)
    if k == 1:
        return [(touchpoints[0][0], 1.0)]
    if k == 2:
        return [(touchpoints[0][0], 0.5), (touchpoints[1][0], 0.5)]
    w_mid = 1.0 - w_first - w_last
    mid_each = w_mid / (k - 2)
    credits = []
    for i, (ch, t) in enumerate(touchpoints):
        if i == 0:
            credits.append((ch, w_first))
        elif i == k - 1:
            credits.append((ch, w_last))
        else:
            credits.append((ch, mid_each))
    return credits

path = [("YouTube", "t8"), ("Meta", "t7"), ("Google", "t2"), ("AppPush", "t1")]
for ch, c in position_based_attribution(path):
    print(f"{ch:9s} 贡献={c:.2%}")
```

输出：

```text
YouTube   贡献=40.00%
Meta      贡献=6.67%
Google    贡献=6.67%
AppPush   贡献=40.00%
```

#### 2.16.5 三种规则模型对比

| 模型 | 核心思想 | 优点 | 缺点 | 适用 |
| --- | --- | --- | --- | --- |
| First Click | 获客驱动 | 抓住拉新入口 | 高估入口/无视临门一脚 | 拉新素材评估 |
| Last Click | 转化驱动 | 简单可解释 | 高估尾端 | 快速起步 |
| Linear | 平均主义 | 简单 | 无视作用大小与时序 | 低决策链路 |
| Time Decay | 近端加权 | 时序合理 | 忽略首触点获客价值 | 中决策链路 |
| Position | 首尾加权 | 兼顾两端 | 中间权重主观 | 全局均衡 |

### 2.17 Shapley 值归因（Shapley Value Attribution）

#### 2.17.1 合作博弈视角

把渠道看作博弈中的**玩家（player）**，转化收益看作**联盟价值（coalition value）**。Shapley 值把总收益按**每个玩家在所有联盟中的边际贡献的平均**来分配，是唯一满足若干公平公理（对称性、可加性、虚拟性、效率）的解。

#### 2.17.2 数学定义

设有 n 个渠道集合 `N = {1,...,n}`，联盟 S ⊆ N 的价值为 `v(S)`（S 中渠道同时出现时产生的转化/收益期望）。渠道 i 的 Shapley 值：

```text
φ_i(v) = Σ_{S ⊆ N \ {i}}  ( |S|! · (n - |S| - 1)! / n! ) · [ v(S ∪ {i}) - v(S) ]
```

其中求和遍及所有**不包含 i 的联盟** S，`v(S ∪ {i}) - v(S)` 是把 i 加入 S 的边际贡献，权重 `|S|!(n-|S|-1)!/n!` 保证每个排序概率均等。

等价形式（把求和看成对随机排列中 i 的边际贡献求平均）：

```text
φ_i(v) = E_{random permutation}[ v(S_i^π ∪ {i}) - v(S_i^π) ]
```

其中 `S_i^π` 是排列 π 中排在 i 之前的渠道集合。

#### 2.17.3 转化路径上的 Shapley

在归因场景，把"联盟价值"定义为**该渠道集合在数据中被观测到的转化概率**。对给定路径频率，通过在所有子集上建模转化概率，即可算 Shapley 值。

常用简化的、基于**转化-计数**的经验 Shapley：

```text
v(S) ≈ (S 中渠道共同出现的路径上的转化数) / (S 中渠道共同出现过的总路径数)
```

#### 2.17.4 复杂度

```text
n 个渠道 → 需要评估 2^n 个子集 v(S)
渠道数少(≤ 10) → 可精确枚举
渠道数多(> 15) → 用蒙特卡洛抽样近似
```

#### 2.17.5 Python 实现（精确枚举 + 蒙特卡洛）

```python
from itertools import combinations
from collections import defaultdict
import random

def coalition_value(channels, journeys):
    """
    journeys: list of (set_of_channels, converted_bool)
    返回 v(S)：任意子集 S 的经验转化概率
    """
    cache = {}
    def v(S):
        S = frozenset(S)
        if S in cache:
            return cache[S]
        n_ctx = 0      # 出现过 S 中所有渠道的路径数（作为上下文）
        n_conv = 0
        for channels_set, conv in journeys:
            if S.issubset(channels_set):
                n_ctx += 1
                if conv:
                    n_conv += 1
        val = n_conv / n_ctx if n_ctx else 0.0
        cache[S] = val
        return val
    return v

def shapley_montecarlo(channels, journeys, n_permutations=2000, seed=42):
    """蒙特卡洛 Shapley 近似"""
    random.seed(seed)
    v = coalition_value(channels, journeys)
    n = len(channels)
    phi = defaultdict(float)
    for _ in range(n_permutations):
        perm = channels[:]
        random.shuffle(perm)
        prefix = set()
        for c in perm:
            before = frozenset(prefix)
            marginal = v(before | {c}) - v(before)
            phi[c] += marginal
            prefix.add(c)
    for c in channels:
        phi[c] /= n_permutations
    # 归一化到 100%
    total = sum(phi.values())
    return {c: w / total for c, w in phi.items()}

channels = ["Search", "Social", "Display"]
journeys = [
    ({"Search", "Social", "Display"}, True),
    ({"Search"}, True),
    ({"Social"}, False),
    ({"Search", "Social"}, True),
    ({"Display"}, False),
    ({"Search", "Display"}, True),
    ({"Social", "Display"}, False),
]
print(shapley_montecarlo(channels, journeys))
```

#### 2.17.6 Shapley 值的性质与局限

| 优点 | 局限 |
| --- | --- |
| 满足公平公理，经济学上严谨 | 联盟价值 v(S) 的估计有统计噪声 |
| 天然处理渠道间互动/协同 | 需要大量路径数据估计 v(S) |
| 结果可用于严格预算分配 | 计算开销可观（2^n / 采样） |
| 对"冗余"渠道惩罚（协同） | 是对"已发生转化"的分摊，非严格因果 |

### 2.18 马尔可夫链归因（Markov Chain Attribution）

#### 2.18.1 原理

把用户旅程建模为**马尔可夫链**：状态包括各渠道触点状态 + 两个吸收态（转化 CONV / 未转化 NULL）。通过估计转移概率，计算**移除效应（Removal Effect）**，进而算出每个渠道的功劳。

- **移除效应（Removal Effect）**：把某渠道从图中移除，观察转化率下降的比例。下降越多 → 该渠道对转化越不可或缺 → 功劳越大。

```text
移除效应(渠道 i) = (完整模型转化概率 - 移除 i 后转化概率) / 完整模型转化概率
```

#### 2.18.2 转移矩阵构造

从路径数据中以"渠道 → 下一渠道/转化/流失"统计转移次数，得转移矩阵 P。示例（5 状态：START, A=Search, B=Social, C=Display, 吸收态 CONV, NULL）：

```text
         START    A       B       C       CONV    NULL
START    0        .4      .3      .2      0       .1
A        0        .1      .3      .2      .3      .1
B        0        .2      .15     .2      .25     .2
C        0        .2      .25     .1      .3      .15
CONV     0        0       0       0       1       0
NULL     0        0       0       0       0       1
```

#### 2.18.3 转化概率计算

吸收马尔可夫链的转化概率 = 从 START 开始，最终到达 CONV 的概率。设基本矩阵 N = (I - Q)^(-1)，R 为从暂态到吸收态的转移矩阵，则吸收概率矩阵 B = N·R；B 中(START, CONV)即整体转化率。

#### 2.18.4 Python 实现（用移除效应 + 蒙特卡洛模拟）

```python
import numpy as np

def markov_removal_effect(transition_matrix, states, start_idx, conv_idx):
    """用蒙特卡洛模拟近似吸收概率，并计算各渠道移除效应"""
    def conversion_prob(P):
        rng = np.random.default_rng(42)
        conv = 0.0
        n_sim = 10000
        for _ in range(n_sim):
            s = start_idx
            for step in range(200):
                if s == conv_idx:
                    conv += 1.0
                    break
                # 若进入其它吸收态则停止
                if P[s][s] == 1.0 and s != conv_idx:
                    break
                nxt = rng.choice(len(states), p=P[s])
                s = int(nxt)
            else:
                continue
        return conv / n_sim

    full = conversion_prob(transition_matrix)
    credits = {}
    for i, st in enumerate(states):
        if st in ("START", "CONV", "NULL"):
            continue
        Pm = transition_matrix.copy()
        row = Pm[i].copy()
        self_p = row[i]
        row[i] = 0.0
        s = row.sum()
        if s > 0:
            Pm[i] = row / s * (1 - self_p)   # 移除自环并保持总质量
        conv_removed = conversion_prob(Pm)
        removal = (full - conv_removed) / full if full > 0 else 0.0
        credits[st] = removal
    total = sum(credits.values())
    return {k: v / total for k, v in credits.items()} if total > 0 else credits
```

> 该实现为教学演示；生产中可用 **`ChannelAttribution`（R/Python 包）** 等成熟库。

#### 2.18.5 使用成熟的 Python 包 `ChannelAttribution`

```bash
pip install ChannelAttribution
```

```python
from ChannelAttribution import markov_model

data = {
    "path": ["A>B>C", "A>C", "B>C", "A>B", "C", "A>B>C"],
    "conv": [1, 1, 0, 1, 0, 1],
    "null": [0, 0, 1, 0, 1, 0],
}
res = markov_model(data)
print(res["result"])   # channel, total_conversions, attribution
```

#### 2.18.6 Shapley vs Markov 对比

| 维度 | Shapley 值 | Markov 移除效应 |
| --- | --- | --- |
| 理论根基 | 合作博弈 | 随机过程/图论 |
| 是否建模转化路径 | 只用联盟出现/转化 | 用完整路径与顺序 |
| 是否显式建模"未转化" | 间接 | 直接（NULL 状态） |
| 渠道间协同 | 显式 | 隐式（图结构） |
| 计算 | 2^n / 采样 | 矩阵运算 + 反复移除 |
| 输出 | 公平的功劳分摊 | 基于不可或缺性的功劳 |
| 局限 | 依赖 v(S) 估计 | 假设一阶马尔可夫（可放宽） |

### 2.19 统一归因模型对比与选择

#### 2.19.1 一张大对比表

| 模型 | 类型 | 数学复杂度 | 数据需求 | 因果性 | 可解释性 | 对大链路的稳健性 |
| --- | --- | --- | --- | --- | --- | --- |
| First Click | 规则 | O(1) | 路径 | 低 | 极高 | 差 |
| Last Click | 规则 | O(1) | 路径 | 低 | 极高 | 差 |
| Linear | 规则 | O(K) | 路径 | 低 | 高 | 中 |
| Time Decay | 规则 | O(K) | 路径+时间 | 中 | 高 | 中 |
| Position-Based | 规则 | O(K) | 路径 | 中 | 高 | 中 |
| DDA (数据驱动) | ML | O(模型) | 大数据 | 中 | 中 | 高 |
| Shapley | 博弈 | 2^n/采样 | 大量路径 | 中-高 | 高 | 高 |
| Markov | 随机过程 | O(矩阵) | 路径+顺序 | 中-高 | 中 | 高 |
| 移除效应 | 综合 | 依赖实现 | 路径 | 中-高 | 中 | 高 |

#### 2.19.2 选择建议矩阵

```text
业务场景                            推荐
──────────────────────────────────────────────────────
刚刚起步、数据少、要快速上线        Last Click / Time Decay
需要给投放团队讲得清楚              Position-Based / Time Decay
大转化量、信任数据科学              Shapley / Markov / DDA
需要严谨的预算分配经济学            Shapley（最优分摊）+ 增量校准
多平台联合预算打架                  Shapley / Markov 统一口径
B2B/长链路高客单                    Time Decay(长 λ) / Markov
```

#### 2.19.3 工程实践：多模型并行 + 主模型

生产系统常用**多模型并存**：

```text
┌───────────────────────────────────────────────┐
│  主模型（用于预算分配）: Shapley 或 DDA         │
│  解释模型（给投放看）  : 位置/时间衰减           │
│  校验模型（科学判断）  : 增量实验(Markov+Geo)   │
└───────────────────────────────────────────────┘
        │                │               │
        ▼                ▼               ▼
  预算权重           报表解释          因果校准
  输入出价/预算       投放沟通           交叉验证
```

### 2.20 Data Clean Room 原理与隐私计算

#### 2.20.1 为什么要 Clean Room

跨平台归因需要把广告主的第一方数据与广告平台的数据**融合**，但这触碰 GDPR / DMA / ATT / cookie 弃用等隐私红线。**Data Clean Room（数据清洁室，DCR）** 提供了一个**在不直接交换原始 PII** 的前提下协作分析的控制环境。

#### 2.20.2 三种主流隐私增强技术（PET）

| PET | 全称 | 核心思想 | 示例 |
| --- | --- | --- | --- |
| Differential Privacy | 差分隐私 | 在查询结果加受控噪声，使任何单条记录对输出影响有界 | Apple、Google 聚合 |
| MPC | 安全多方计算 | 多方各自持有分片，联合计算而不泄露明文输入 | 统计、匹配 |
| TEE / Trusted Execution Env | 可信执行环境 | 数据在硬件隔离区内解密、计算、加密后输出 | 云平台 enclave |

**差分隐私（DP）** 的核心定义：随机化算法 M 满足 ε-差分隐私，若对任意相邻数据集 D、D'（差一条记录）与任意输出 S：

```text
P[M(D) ∈ S] ≤ e^ε · P[M(D') ∈ S]
```

- ε（隐私预算）：越小隐私越好；越大效用越好；
- 常见机制：Laplace 机制（数值查询）+ 敏感度缩放。

**Laplace 噪声机制**：

```text
M(D) = f(D) + Lap(Δf / ε)
其中 Δf 为全局敏感度，Lap(b) 为尺度 b 的拉普拉斯分布
```

#### 2.20.3 Clean Room 的典型约束

```text
① 不能导出原始行级 PII
② 只能输出聚合结果（count/sum/mean/average）且需满足最低行数（k-anonymity, 如 ≥ 20）
③ 结果可叠加噪声（DP）再输出
④ 查询与代码在受控沙箱内运行
⑤ 审计日志记录所有访问
```

#### 2.20.4 去标识化 / 假名化流程

```text
第一方数据(邮箱/手机号/设备ID)
        │  SHA-256 + 随机盐(salt)
        ▼
Hash 化标识 (normalized+salted hash)
        │
        ├──► 上传到 Clean Room（云端，与平台方共享）
        │
        ▼
与平台侧的 Hash 化标识做安全匹配（join）
        │
        ▼
允许聚合分析（频次、重合度、增量估计）
```

### 2.21 Google Ads Data Clean Room / Amazon Marketing Cloud

#### 2.21.1 Google Ads Data Clean Room（DCR）

Google Ads DCR 让广告主把**自己的一方数据**放到 Google 的 Clean Room 中，与 Google Ads 的观测数据在受控环境中匹配与分析：

```text
能力：
  - 一方数据 (customer list) 与 Google Ads 数据做匹配
  - 基于匹配做聚合分析（reach, overlap, conversions）
  - 不与第三方共享原始数据
  - 通过 DCR API / UI 操作
```

#### 2.21.2 Amazon Marketing Cloud（AMC）类比

Amazon 的 **AMC** 是业界最成熟的 DCR 之一：

```text
- 登录 Amazon Ads 的 SQL 环境
- 用户级(假名化)数据集在沙箱内查询
- 不支持行级原始导出，只输出聚合
- 支持跨渠道(Amazon Ads + DSP + 品牌方数据)融合
- 用 SQL 编写自定义查询做归因/受众分析
```

AMC 的 SQL 查询示例（概念）：

```sql
-- 融合 Amazon Ads 转化 (conversions) 与品牌一方数据 (custom_events)
SELECT
  channel,
  COUNT(DISTINCT user_pseudo_id) AS users_converted
FROM amc.conversions c
LEFT JOIN (
  SELECT user_pseudo_id, event_name
  FROM brand.custom_events
) b
  USING (user_pseudo_id)
WHERE c.conversion_type = 'purchase'
GROUP BY channel
HAVING COUNT(DISTINCT user_pseudo_id) >= 20   -- 最小行数约束
```

#### 2.21.3 各 DCR 平台能力对比

| 能力 | Google Ads DCR | Amazon Marketing Cloud | 商业第三方 DCR |
| --- | --- | --- | --- |
| 主导方 | Google | Amazon | 如 Snowflake/初创 |
| 数据源 | Google Ads + 一方 | Amazon Ads + 一方 | 多平台汇总 |
| 查询语言 | API/UI | SQL | SQL |
| 假名化 | Hash 匹配 | 假名化 OTT 设备 | 通用 |
| 输出约束 | 聚合 | 聚合+最小行数 | 可配置 |
| 典型用途 | Google 归因、受众重叠 | 全漏斗归因、频次分析 | 全渠道 MMM |

### 2.22 数据融合流程、Schema 对齐与 Join Keys

#### 2.22.1 完整数据融合五步

```text
① 数据盘点与声明（Data Inventory）
   —— 明确各方有哪些数据、字段、时间范围、敏感字段
② Schema 对齐（Schema Alignment）
   —— 统一字段名、类型、语义、粒度、时区
③ 标识符对齐（Identity Alignment / Join Keys）
   —— 选定可安全匹配的键（hash 化 PII / 设备 ID / 自有 user_id）
④ 受控执行（Controlled Execution）
   —— 在 DCR/PET 环境中做 join 与聚合
⑤ 合规输出（Compliant Output）
   —— DP 加噪、最小行数、聚合表输出
```

#### 2.22.2 Schema 对齐清单

| 字段 | 品牌一方 | 平台侧 | 统一规范 |
| --- | --- | --- | --- |
| 用户标识 | email(明文→hash) | 平台 ID | hash user_id, user_pseudo_id |
| 事件时间 | UTC 时间戳 | 平台时区 | 统一转 UTC (ISO8601) |
| 事件名 | purchase | purchase | 映射到标准事件字典 |
| 金额 | USD decimal | USD | 统一币种、精度 |
| 设备 | iOS/Android | 平台设备 | OS 枚举 |
| 国家 | ISO 3166 | 平台 geo | ISO 3166-1 alpha-2 |

#### 2.22.3 Join Keys 策略

| Join Key | 匹配质量 | 隐私风险 | 可用性 | 说明 |
| --- | --- | --- | --- | --- |
| Hash(email/手机) | 高 | 中（可撞库） | 中 | 需 salt；标准化后再 hash |
| 设备 ID (IDFA/AAID) | 高 | 高 | 低（ATT 后大幅缺失） | 依赖用户授权 |
| 自有 user_id | 高 | 中 | 低（仅登录用户） | 覆盖面受限 |
| 概率匹配（行为） | 中 | 中 | 中 | ML 预测、误差可控 |
| 聚合配对（模型层） | 低-中 | 低 | 高 | 不做个体级 join，用统计 |

#### 2.22.4 哈希标准化步骤示例

```python
import hashlib

def normalize_and_hash(email: str, salt: str) -> str:
    """标准化的邮箱 → 加盐 SHA-256 哈希"""
    e = email.strip().lower()           # 统一小写、去空白
    return hashlib.sha256((salt + e).encode()).hexdigest()

print(normalize_and_hash("Alice@Example.com", "SALT123"))
```

> 注意：真正的 email 标准化要考虑 provider 规则（Gmail 去点、+tag）等，样例仅为演示。

#### 2.22.5 数据融合的常见用例

```text
① 渠道重叠分析：一方成交用户与各平台受众的重合度（reach & overlap）
② 跨渠道频次控制：同一用户被多平台重复触达的程度（频次管理）
③ 全漏斗归因：从一方转化出发，回溯各平台触点的完整路径
④ 增量测量辅助：在 DCR 内构造匹配后的处理/对照分析
⑤ 人群包/受众扩展：基于高 LTV 一方用户做 lookalike
```

### 2.23 从归因到预算分配自动化闭环

这是跨平台归因的"终极应用"：**把归因权重 / 增量结论 转化为平台的出价与预算信号**，形成自动优化闭环。

#### 2.23.1 闭环架构

```text
归因引擎输出每渠道权重 credit(ch)
        │
        ▼
增量校准：weight'(ch) = credit(ch) × incrementality_factor(ch)
        │
        ▼
预算分配：按 weight' 与边际收益曲线分配预算
        │
        ▼
出价信号：把增量价值回传给平台（value rules / conversion value /
          Server-side Conversions API 增强）
        │
        ▼
平台智能出价据此优化 → 产生新数据
        │
        ▼
再次归因 → 闭环
```

#### 2.23.2 增量校准因子

不同渠道的"归因功劳"与"真实增量"往往不一致。定义一个校准因子：

```text
incrementality_factor(ch) = 增量测试测得的 iROAS(ch) / 归因模型给的 信用比例(ch)
```

然后把归因权重乘以校准因子并重新归一化，得到**增量校准后的预算权重**：

```text
w_calibrated(ch) = credit(ch) · incrementality_factor(ch)
预算占比(ch)     = w_calibrated(ch) / Σ 所有渠道 w_calibrated
```

> 这是"以增量定总盘子、以归因定结构、用增量校准结构"的落地公式。

#### 2.23.3 边际收益曲线（Spend-Response）

预算分配更严谨的做法是**按边际收益分配**（等边际原则）：预算应在**各渠道边际 ROAS 相等**时最优。

```text
最优条件：MR(ch1) = MR(ch2) = ... = λ (所有渠道的边际收入相等)
```

用 Python 做预算求解：

```python
def budget_allocate(response_params, budget, channels):
    """
    用等边际法则分配预算。
    response_params: {ch: (a, b)} 其中 response(spend) = a*spend**b (幂律饱和)
    budget: 总预算, channels: 渠道列表
    返回 {ch: spend}
    """
    def spend_for_channel(lam, a, b):
        # marginal = a*b*spend**(b-1) = lam
        return (lam / (a * b)) ** (1 / (b - 1))

    lo, hi = 1e-9, 1e9
    for _ in range(200):
        mid = (lo + hi) / 2
        total = sum(spend_for_channel(mid, *response_params[c]) for c in channels)
        if total > budget:
            lo = mid
        else:
            hi = mid
    lam = (lo + hi) / 2
    return {c: max(0.0, spend_for_channel(lam, *response_params[c])) for c in channels}

resp = {"Search": (5000, 0.35), "Social": (4000, 0.40), "Display": (2500, 0.50)}
alloc = budget_allocate(resp, 100000, list(resp.keys()))
print(alloc)
```

#### 2.23.4 输出到平台的方式

```text
方式 A：按渠道预算分配 —— 直接改 campaign budget / 每日预算
方式 B：出价信号 —— 用 value rules / conversion value 重置转化价值，
        让平台智能出价自动倾向高增量渠道
方式 C：A/B 迁移 —— 定期对比新旧分配，验证后再扩大
方式 D：Cap 控制 —— 对低增量渠道设花费上限，保障风险
```

#### 2.23.5 闭环中的风控与人工确认

```text
□ 分配变化是否在安全范围（单次最大变更限额，如 ±20%）？
□ 是否触发最小实验期（避免频繁改动导致平台学习不稳定）？
□ 是否设了渠道花费下限（不能把某渠道砍到 0 导致丢失）？
□ 是否有人工审批节点（重大结构变化需增长负责人确认）？
□ 是否有回滚机制（一键恢复上一版分配）？
```

### 2.24 差分隐私与隐私增强技术的数学原理

#### 2.24.1 差分隐私的形式化定义

算法 M 对相邻数据集 D 与 D'（仅差一条记录）满足 (ε, δ)-DP，若对所有输出集 S：

```text
P[M(D) ∈ S] ≤ e^ε · P[M(D') ∈ S] + δ
```

当 δ=0 时即纯 ε-DP（如 Laplace 机制）。

#### 2.24.2 Laplace 机制与全局敏感度

对实值查询 f，全局敏感度：

```text
Δf = max_{D, D'} ||f(D) - f(D')||_1
```

Laplace 机制：`M(D) = f(D) + Lap(Δf/ε)`。对 count 查询，Δf=1。

#### 2.24.3 组合性质（Composition）

顺序组合：连续执行 ε1 与 ε2 两个 DP 机制，整体的隐私预算是 ε1 + ε2。并行组合：在互斥数据集上执行，预算取 max。

```text
顺序组合: ε_total = Σ ε_i
并行组合: ε_total = max ε_i
```

#### 2.24.4 DP 加噪的 Python 实现

```python
import numpy as np

def laplace_noise(sensitivity, epsilon):
    """返回尺度为 sensitivity/epsilon 的拉普拉斯噪声"""
    return np.random.laplace(0, sensitivity / epsilon)

def dp_count(true_count, epsilon=0.5, sensitivity=1.0):
    return int(round(true_count + laplace_noise(sensitivity, epsilon)))

# 例
print("DP 化转化数:", dp_count(1280, epsilon=0.5))
```

#### 2.24.5 什么时候用哪种 PET

```text
场景                             推荐 PET
────────────────────────────────────────────────
数值聚合查询(count/sum/mean)     Laplace/高斯 DP 加噪
多方求交集/匹配而不泄露明文      PSI (Private Set Intersection, MPC 族)
多方联合回归/统计                安全多方计算 MPC
高敏数据保护且需高性能            TEE 可信执行环境
跨平台匹配 + 聚合                三者组合（PSI 匹配 + DP 输出）
```

#### 2.24.6 MPC / PSI 简析

- **PSI（Private Set Intersection）**：两方各自持有集合，先在不暴露元素的前提下求交集元素。归因中常用于"一方用户 ∩ 平台触点"的安全匹配。
- 结合流程：先用 PSI 求安全交集，得到匹配后的假名化用户集，再在 Clean Room / DP 条件下做聚合统计，最后输出 DP 化的增量结果。

```text
品牌一方(用户集 U)  +  平台触点集 T
        │                    │
        ▼                    ▼
   ┌────────────────────────────────┐
   │        PSI（安全求交集）         │
   └───────────────┬────────────────┘
                   ▼
        匹配后的假名化用户集合 M
                   ▼
    （可选）Clean Room 内聚合 / MPC / DP 加噪
                   ▼
         输出聚合增量结果（不含个体 PII）
```

---

## 三、生产环境实战

### 3.1 统一事件数据管道搭建（Event Pipeline）

#### 3.1.1 目标数据模型

设计一套**统一事件模型**，让各平台数据都能落进同一张宽表/事件表。

概念表 `events`：

```sql
CREATE TABLE events (
  event_id           STRING NOT NULL,          -- 平台约定的事件 id
  unified_user_id    STRING,                   -- 打通的用户 id
  raw_id             STRING,                   -- 原始平台 id
  platform           STRING,                   -- google|meta|tiktok|dv360|first-party
  event_type         STRING,                   -- click|impression|conversion
  event_name         STRING,                   -- purchase|add_to_cart|...
  event_ts_utc       TIMESTAMP NOT NULL,       -- 统一 UTC 时间
  campaign_id        STRING,
  adset_id           STRING,
  creative_id        STRING,
  conversion_value   DOUBLE,                   -- 价值（若为转化）
  country_iso        STRING,
  device_os          STRING,
  sales_channel      STRING,                   -- web|app|offline
  raw_payload        STRUCT<...>,              -- 原始字段兜底
  ingested_at        TIMESTAMP NOT NULL
)
PARTITIONED BY (event_date STRING)
```

#### 3.1.2 每日增量拉取（Python + 各平台 API）

```python
import requests, datetime as dt

def pull_google_ads_since(days=30, last_ingest=None):
    # 使用 google-ads-api client 拉取 click/impression/conversion
    # 简化为占位：返回一批事件
    return [{
        "platform": "google",
        "event_type": "conversion",
        "event_name": "purchase",
        "event_ts_utc": dt.datetime.utcnow().isoformat(),
        "campaign_id": "camp-001",
    }]

def pull_meta_since(days=7):
    return []

def pull_tiktok_since(days=7):
    return []

def normalize_and_upsert(events):
    for e in events:
        e["event_ts_utc"] = to_utc(e["event_ts_utc"])
        canonicalize_ids(e)
    dedup(events)
    write_to_bigquery(events)

# 每日调度主流程
def daily_pipeline():
    for puller in (pull_google_ads_since, pull_meta_since, pull_tiktok_since):
        normalize_and_upsert(puller())
    rebuild_identity_graph()
    rebuild_journeys()
```

#### 3.1.3 事件去重与幂等

```sql
-- 用 platform + 平台事件 id 去重，保证幂等
SELECT
  platform, event_id, COUNT(*) AS dup
FROM events
GROUP BY platform, event_id
HAVING COUNT(*) > 1
```

#### 3.1.4 数据质量监控 SQL

```sql
-- 每日事件量监控（应与平台后台交叉核对）
SELECT
  event_date,
  platform,
  COUNT(DISTINCT campaign_id) AS campaigns,
  COUNT(*) AS events
FROM events
WHERE event_date = CURRENT_DATE - 1
GROUP BY event_date, platform
ORDER BY platform;
```

### 3.2 统一归因引擎实现（Attribution Engine）

#### 3.2.1 引擎接口设计

```python
# attribution/engine.py
from abc import ABC, abstractmethod

class AttributionModel(ABC):
    @abstractmethod
    def credit(self, journey, config):
        """输入一条路径，返回 {touchpoint_id: credit}"""
        pass

class TimeDecayModel(AttributionModel):
    def __init__(self, half_life_days=7.0):
        self.half_life = half_life_days
    def credit(self, journey, config):
        return time_decay_attribution(journey, self.half_life)

class ShapleyModel(AttributionModel):
    def __init__(self, journeys_store):
        self.store = journeys_store
    def credit(self, journey, config):
        return shapley_montecarlo(list(journey['channels']), self.store.journeys)
```

#### 3.2.2 模型路由与配置

```yaml
# attribution_config.yaml
models:
  default: shapley
  fallback: time_decay           # 数据不足时回退
routing:
  min_journeys_for_shapley: 200000
  min_journeys_for_dda: 15000
window:
  click_days: 30
  view_days: 1
  conversion_cap: 1             # 同一路径最多归给 1 次转化
value_rules:
  enabled: true
  event_to_value:
    purchase: 100
    add_to_cart: 20
```

#### 3.2.3 批量归因任务

```python
import pandas as pd

def run_attribution_batch(events_df, model_name="shapley"):
    # 1) 构造路径
    journeys = build_journeys(events_df)
    # 2) 选模型
    model = get_model(model_name)
    # 3) 计算每个触点功劳
    rows = []
    for j in journeys:
        credits = model.credit(j, {})
        for tp, c in credits.items():
            rows.append({"journey_id": j["id"], "touchpoint": tp, "credit": c})
    return pd.DataFrame(rows)
```

#### 3.2.4 渠道聚合输出表

```sql
CREATE TABLE channel_attribution_daily AS
SELECT
  event_date,
  platform,
  SUM(credit)                 AS attributed_conversions,
  SUM(credit)                 AS attributed_value,
  SUM(credit)/NULLIF(SUM(SUM(credit)) OVER (),0) AS pct
FROM touch_credit
GROUP BY event_date, platform;
```

### 3.3 增量测试平台落地（Incrementality Lab）

#### 3.3.1 测试登记表

```yaml
# incrementality/tests/2026q3_geo_meta.yaml
test:
  name: "2026Q3-Geo-Meta-Brand"
  mechanism: geo_holdout       # geo_holdout | audience_holdout | psa | gaia
  unit: geo_dma
  primary_metric: revenue
  secondary_metric: [purchases, conversion_rate]
  treatment_budget: 5000
  holdout_pct: 0.15
  geo_pool_size: 48
  pre_period_days: 30
  test_period_days: 42
  power_target: 0.80
  alpha: 0.05
  mde_lift: 0.30
  randomization_seed: 20260814
```

#### 3.3.2 测试结果分析脚本

```python
def analyze_geo_lift(pre_df, post_df, geo_units, treated):
    """
    pre_df/post_df: (geo, revenue) ; treated: 处理地理集合
    用 DID 估计 ATE 与 CI
    """
    import numpy as np
    rows = []
    for g in geo_units:
        pre = pre_df[pre_df.geo == g].revenue.mean()
        post = post_df[post_df.geo == g].revenue.mean()
        rows.append({"geo": g, "diff": post - pre,
                     "treated": g in treated})
    df = pd.DataFrame(rows)
    te = df[df.treated].diff.mean() - df[~df.treated].diff.mean()
    var_t = df[df.treated].diff.var() / df[df.treated].shape[0]
    var_c = df[~df.treated].diff.var() / df[~df.treated].shape[0]
    se = (var_t + var_c) ** 0.5
    return {"ATE_incremental": te,
            "ci": (te - 1.96*se, te + 1.96*se),
            "significant": abs(te)/se > 1.96}
```

#### 3.3.3 测试运行状态机

```text
DRAFT → REVIEW(人工确认设计) → PLANNING(样本量/Geo 分配)
     → RUNNING(投放与对照执行) → DATA_COLLECTION_END
     → ANALYZING → REPORTED → ARCHIVED
              ↘          ↘
              INVALID(设计违规)   UNVERIFIED(未达信度)
```

### 3.4 Data Clean Room 生产对接

#### 3.4.1 一方数据准备

```python
def prepare_first_party_for_dcr(users_df, salt):
    """把一方用户表 hash 化，供 DCR 上传"""
    prepared = users_df.copy()
    prepared["user_pseudo_id"] = prepared["email"].apply(
        lambda e: normalize_and_hash(e, salt))
    # 保留必要聚合字段，不含明文 PII
    return prepared[["user_pseudo_id", "lifetime_value", "country"]]
```

#### 3.4.2 Clean Room 内的归因查询（SQL）

```sql
-- 在 DCR 中对一方成交用户与各平台触点做聚合归因分析
WITH matched AS (
  SELECT
    dc.user_pseudo_id,
    ev.platform,
    ev.event_type,
    ev.event_ts_utc
  FROM dcr.ads_events AS ev
  JOIN dcr.first_party AS dc
    ON ev.user_pseudo_id = dc.user_pseudo_id
  WHERE ev.event_type IN ('click', 'impression')
    AND ev.event_ts_utc >= TIMESTAMP_SUB(CURRENT_TIMESTAMP, INTERVAL 7 DAY)
)
SELECT
  platform,
  COUNT(DISTINCT user_pseudo_id) AS reached_users,
  COUNT(DISTINCT IF(event_type='click', user_pseudo_id, NULL)) AS clicked_users
FROM matched
GROUP BY platform
HAVING COUNT(DISTINCT user_pseudo_id) >= 20   -- 最小行数/占最小化
ORDER BY reached_users DESC;
```

#### 3.4.3 DP 加噪输出

```python
import numpy as np

def laplace_mechanism(true_value, sensitivity, epsilon):
    """对聚合查询加拉普拉斯噪声（ε-DP）"""
    scale = sensitivity / epsilon
    noise = np.random.laplace(0, scale)
    return true_value + noise

# 例：对"处理组转化数"加噪
count_conv = 1280
print("DP 化转化数:", int(round(laplace_mechanism(count_conv, 1, 0.5))))
```

#### 3.4.4 合规与审计清单

```text
□ PII 是否在 DCR 外已去标识化/假名化？
□ Hash 是否加盐（防彩虹表）？
□ 是否声明数据处理目的（purpose）并符合合法性基础？
□ 输出是否满足最小行数（k-anonymity）与 DP 预算？
□ 是否有访问审计日志与权限最小化？
□ 是否设置了数据保留期与删除流程？
□ 是否按 DMA/ATT 处理同意（consent）信号？
```

### 3.5 归因到预算的自动化闭环实现

#### 3.5.1 预算引擎调度

```python
def budget_optimization_loop():
    # 1. 读取归因权重
    weights = load_attribution_weights()          # {ch: credit}
    # 2. 读取增量校准因子
    incr_factors = load_incrementality_factors()  # {ch: factor}
    # 3. 校准
    calibrated = {ch: w * incr_factors.get(ch, 1.0)
                  for ch, w in weights.items()}
    total = sum(calibrated.values())
    alloc = {ch: v / total for ch, v in calibrated.items()}
    # 4. 套上预算与风控
    alloc = apply_caps_and_floors(alloc)
    # 5. 通过平台 API 下发
    push_to_platforms(alloc)
    # 6. 记录 + 告警
    log_allocation(alloc)
```

#### 3.5.2 CAP 与回滚

```python
def apply_caps_and_floors(alloc, max_change=0.20, floor=0.05):
    """限制单渠道单次变更幅度，并设地板"""
    new = {}
    for ch, v in alloc.items():
        prev = get_previous_alloc(ch)
        v = min(v, prev * (1 + max_change))   # 涨幅上限
        v = max(v, prev * (1 - max_change))   # 跌幅上限
        v = max(v, floor)                     # 地板
        new[ch] = v
    # 重新归一化到 1
    s = sum(new.values())
    return {c: x / s for c, x in new.items()}
```

#### 3.5.3 下发到平台（以 Google / Meta 为例）

```python
# Google Ads：调整 campaign budget_amount_micros
from google.ads.googleads.client import GoogleAdsClient
client = GoogleAdsClient.load_from_dict(config)
bga = client.get_service("BudgetService")

def set_budget(campaign_id, budget_micros):
    op = client.get_type("BudgetOperation")
    budget = op.update
    budget.resource_name = f"customers/{cid}/budgets/{campaign_id}"
    budget.amount_micros = budget_micros
    budget.is_explicitly_shared = False
    bga.mutate_budgets(customer_id=cid, operations=[op])
```

#### 3.5.4 闭环观测指标

```text
- 决策一致性：分配后各渠道 iROAS 是否趋近（等边际收敛）
- 稳定性：分配在不同日/周是否震荡
- 生意结果：总 iROAS、总转化是否提升
- 平台学习：改预算后各平台 CPA/成本是否收敛
- 风险：是否有渠道被误砍导致覆盖丢失
```

### 3.6 监控、告警与 SLO

#### 3.6.1 关键监测指标

| 指标 | 含义 | SLO | 告警阈值 |
| --- | --- | --- | --- |
| 事件延迟 | 事件从发生到可查询的延迟 | p95 < 6h | > 12h |
| 事件丢失率 | 平台 API 因限流/授权丢失 | < 0.5% | > 2% |
| 身份匹配率 | 可打通到 unified_user 的事件占比 | > 70% | < 60% |
| 归因任务 SLA | 归因批处理完成时间 | 每日 08:00 前 | 延迟 > 2h |
| 对账差额 | 自建归因 vs 平台后台转化差 | < 10% | > 30% |
| 增量测试信度 | 完成且显著的测试占比 | 80% | < 60% |
| 预算闭环偏差 | 计划 vs 实际下发预算差 | < 3% | > 10% |

#### 3.6.2 数据对账脚本（Python）

```python
def reconciliation(own_df, platform_df, join_key, metric):
    """自建 vs 平台后台对账，输出差异报表"""
    merged = own_df.merge(platform_df, on=join_key, suffixes=("_own", "_plat"))
    merged["diff"] = merged[f"{metric}_own"] - merged[f"{metric}_plat"]
    merged["diff_pct"] = merged["diff"] / merged[f"{metric}_plat"].replace(0, 1)
    return merged.sort_values("diff_pct", ascending=False)
```

#### 3.6.3 告警（Alerting）示例

```text
rule: attribution_metric_drift
  when: abs(own_conv - platform_conv)/platform_conv > 0.30
  for: 3 consecutive days
  severity: warning
  action: notify @media-data; open ticket

rule: journey_dropout
  when: identity_match_rate < 0.60
  for: 1 day
  severity: critical
```

### 3.7 端到端实战案例：跨国电商 App

#### 3.7.1 背景

某跨国电商 App，主打欧洲与东南亚市场，投放四个渠道：Google Search、Google YouTube、Meta（FB+IG）、TikTok。业务痛点：

```text
- 各平台后台转化合计 > 真实成交 2.4 倍（重复归因）
- 决策链路长（下载→浏览→加购→下单），平均 5~9 天
- 曾用默认归因窗口，TikTok 与 Meta 互相抢功劳
- 合规需满足 GDPR（欧盟）+ 泰国 PDPA，且 iOS ATT 渗透率高
```

#### 3.7.2 目标设定

```text
① 建一套唯一事实源统一归因，取代各平台后台口径
② 用增量测量回答："哪些渠道真带来增量？总预算该多少？"
③ 把结果自动接回预算，形成季度级优化闭环
```

#### 3.7.3 方案设计

```text
统一窗口：点击 30 天 + 浏览 1 天（基于自有转化时滞分布校准）
主归因模型：Shapley（数据充分）→ 回退时间衰减
增量测量：
  - Google 生态：GAIA（聚合，隐私友好）
  - Meta：PSA（平台内）
  - TikTok：Audience Holdout
  - 总体结构：MMM 季度校准
Clean Room：用 Google Ads DCR + AMC，把一方成交用户与各平台
            hash 匹配做全漏斗归因与重叠分析
预算闭环：季度初按增量校准后的权重分配，月度小步微调 ±20%
```

#### 3.7.4 结果与要点

```text
- 统一归因后，重复计数从 2.4x 收敛到 1.0x（与真实成交一致）
- 增量测量发现：TikTok 对"新客拉新"有高增量，但对"高客单复购"增量低
- 预算按增量校准重分配：TikTok 新客预算 +18%，Display 高预算区 -12%
- 结论被增长团队采纳，下一次季度 iROAS 提升 14%
- 合规上：所有分析在 DCR 内完成，PII 不出环境
```

#### 3.7.5 复盘经验清单

```text
✓ 先用增量测量定总盘子，再用归因定结构
✓ 统一窗口避免平台互抢，对账先对"真实成交数"
✓ 隐私强约束下，优先聚合级方案(GAIA/MMM)，不再强求个体级打通
✓ 双速闭环：季度的战略分配 + 周度的战术微调，避免震荡
✓ 把结论做成增长团队能信、能按的决策工具，而非仅报表
```

### 3.8 数据血缘、版本管理与可复现性

#### 3.8.1 为什么重要

归因与增量结论常被用于预算决策，必须**可复现 + 可审计**：任何一份报表都要能追溯"用了哪个版本的数据、哪个模型、哪个参数"。

#### 3.8.2 血缘与版本设计

```text
✓ 数据版本：事件表按天分区，且保留原始 payload
✓ 模型版本：模型注册表（model_id, 参数, 训练日期）
✓ 配置版本：attribution_config 带版本号并记录变更日志
✓ 结果快照：每日归因结果带 effective_date + config_version
✓ 可复现：给定 (数据范围, config_version) 应能重算出同一份归因
```

#### 3.8.3 配置版本化示例

```yaml
config_version: 2026-08-14-v3
changes:
  - "模型由 time_decay(v2) 升级为 shapley"
  - "点击窗口从 7 天改为 30 天"
  - "新增 value rule: VIP 客户价值 120"
approved_by: data-lead
effective_date: 2026-08-15
```

#### 3.8.4 结果可复现的校验

```python
def reproducibility_check(rerun_result, stored_result, tol=1e-6):
    """校验重新计算与历史存储结果是否一致"""
    diff = abs(rerun_result - stored_result)
    return {"consistent": diff <= tol, "max_diff": float(diff)}
```

### 3.9 成本与性能优化

#### 3.9.1 计算成本分布

跨平台归因系统的主要成本集中在：

```text
① 事件管道 ETL（拉取 + 规范化）—— 最大头
② 身份图谱构建（概率匹配很贵）
③ 归因计算（Shapley 2^n / 采样最贵）
④ 增量测试分析
⑤ Clean Room 使用费
```

#### 3.9.2 优化策略

```text
✓ 增量拉取而非全量：按上次 ingest 时间拉增量
✓ 分区裁剪：按 event_date 分区 + 只处理需要的分区
✓ 采样近似：对超大规模路径用蒙特卡洛/抽样
✓ 预聚合：对高频查询做预聚合物化视图
✓ 冷热分层：热数据热存储，数月前事件降冷存储
✓ 缓存：identity graph 与 coalition value 用缓存复用
```

#### 3.9.3 Shapley 计算的工程加速

```text
- 用采样代替精确 2^n 枚举
- 用 Spark 并行：每个渠道的边际贡献可并行
- 对 coalition value 用缓存字典（frozenset 作 key）
- 必要时降维：把低价值渠道合并为"其他"
```

#### 3.9.4 一个典型成本估算表格

| 环节 | 量级（参考） | 优化后 |
| --- | --- | --- |
| 事件规范化 | 10 亿事件/日 | 增量 + 分区裁剪 -60% |
| 身份图谱 | 5 亿用户 | 采样 + 缓存 -40% |
| Shapley 归因 | 1000 万转化 | 蒙特卡洛 -70% |
| Clean Room | 按里查询计费 | 预聚合查询 -50% |

---

## 四、常见问题与排查

### 4.1 归因窗口不一致导致的数据对不上

**现象**：自建归因与某平台后台转化数差距大（如差 30%+）。

**排查步骤**：

```text
① 对比归因窗口：自建是否与平台一致（点击 30/7/28，浏览 1 天）
② 对比计数方式：每次转化 vs 每次点击（counting type）
③ 对比时间归因：转化时间 vs 点击时间 的归属日
④ 对比跨设备/浏览开关
⑤ 对比并发排除（排除无效/付费流量）
```

**建议**：以"真实成交数"为对账单，先对齐总盘子再对齐各渠道；记录双方口径差异到一个"对账差异字典"。

### 4.2 跨设备/跨平台身份无法打通

**现象**：身份匹配率低（<60%），路径大量断裂，归因结果偏少。

**排查**：

```text
□ 是否充分收集了登录态（email/phone）？
□ 是否对 Web 与 App 都能发唯一 visitor id 并持久化？
□ 概率匹配是否校准、精度是否评估？
□ iOS ATT 是否导致了 IDFA 缺失（可改聚合方案）？
□ Hash 规范化是否一致（大小写/空格/provider 规则）？
```

**对策**：提高登录率、做设备图谱、在隐私约束下转聚合模型。

### 4.3 增量测试结果"没效果"但归因显示有增长

**现象**：归因系统显示某渠道贡献很多转化，但增量测试显示无显著增量。

**原因分析**：

```text
① 归因高估（该渠道大量"顺水推舟"本就会发生的转化）
② 增量测试样本不足、检验力低（没检测到但并非没效应）
③ 增量测试对照组污染（对照组其实也看到了广告）
④ 预算/节奏问题：测试期预算太小或投放期太短
⑤ MDE 设置过高：可检测的最小效应太大
```

**对策**：互相交叉验证；优先用"总生意没广告会怎样"（Geo/MMM）判断盘子，再用个体测试判断渠道边际。

### 4.4 Clean Room Join 结果为空或严重过采样

**现象**：与平台数据 join 后命中的用户极少，或重叠异常高。

**排查**：

```text
□ Hash 规范化是否两端一致（salt、算法、大小写）？
□ 数据时间窗口是否对齐（一方数据 vs 平台数据的时区）？
□ 一方用户是否过于小众（样本不足）？
□ 是否有重复/脏数据导致过度匹配？
□ 是否用错 join key（比如拿 email hash 去 match device id）？
□ 输出最小行数过滤是否把结果滤没了？
```

**对策**：做命中率监控（match rate），先拿一个小样本验证匹配质量再全校。

### 4.5 Data-driven 归因波动剧烈、不可复现

**现象**：同一批数据，DDA 结果每天差异很大，无法向投放解释。

**排查**：

```text
① 转化量是否过低（< 15k/30天，模型不稳定）
② 是否存在季节/战役脉冲导致学习漂移
③ 是否在模型窗口与训练时间上不一致
④ 特征是否有标签泄漏（如把"转化后"信息当特征）
```

**对策**：DDA 需足够数据与稳定性；不稳定时回退规则模型（时间衰减/位置），或用 Shapley 按日聚合平滑。

### 4.6 隐私政策（ATT / GDPR / DMA）导致数据缺口

**现象**：iOS 侧转化/身份大幅缺失，匹配率骤降。

**排查与对策**：

```text
□ 是否依赖 IDFA？→ 增加登录态 + Server-side(CAPI) 回传
□ 是否遵守 ATT 弹窗与 consent？→ 让用户主动给权限
□ 是否可用聚合方案？→ 转 GAIA/MMM/DP 聚合
□ GDPR：是否满足合法性基础 + 目的限制 + 数据最小化？
□ DMA：公平竞争要求下的数据互操作与隐私
```

### 4.7 预算自动化震荡与风险控制

**现象**：预算闭环频繁大改，导致平台学习不稳定、成本飙升。

**排查**：

```text
□ 是否单次变更过大（应设 ±20% 上限）？
□ 是否过早变更（未过最小实验期）？
□ 是否把某渠道砍到 0（应设地板）？
□ 是否缺少回滚与人工审批？
□ 平台是否有学习窗口（改预算后需稳定期）？
```

**对策**：加 CAP/floor、最小稳定期、一次性回滚、决策审计日志。

### 4.8 SQL / Python 诊断速查

```sql
-- 01 检查事件去重：发现重复，需修管道
SELECT platform, event_id, COUNT(*) c
FROM events GROUP BY platform, event_id HAVING c > 1;

-- 02 检查身份匹配率
SELECT
  ROUND(100 * COUNTIF(unified_user_id IS NOT NULL) / COUNT(*), 1) AS match_rate
FROM events WHERE event_date = CURRENT_DATE - 1;

-- 03 检查归因窗口内的路径长度分布
SELECT
  path_len, COUNT(*) AS journeys
FROM (
  SELECT journey_id, COUNT(*) AS path_len
  FROM touch_credit GROUP BY journey_id
) GROUP BY path_len ORDER BY path_len;
```

```python
# 检查归因任务是否在当日完成
def check_sla(attribution_table, expected_time="08:00"):
    latest = get_max_ingested(attribution_table)
    if latest.date() == today and latest.time() <= expected_time:
        return "OK"
    return "LATE"
```

### 4.9 多渠道互抢功劳的归属争议

**现象**：投放团队之间争论"这个转化到底是我的渠道带来的"，导致预算争夺与信任危机。

**处理建议**：

```text
① 统一口径：全网只用一套归因 + 统一窗口（唯一事实源）
② 认账者定义：明确"功劳"按同一把尺子量，不按各平台后台
③ 用增量说话：单个渠道的被认领数≠真实贡献，用 iROAS/增量排名
④ 过程透明：归因配置版本化 + 所有人可查询可复现
⑤ 治理机制：预算归因争议走"数据对账 + 增量验证"仲裁流程
```

### 4.10 数据延迟与回溯窗口问题

**现象**：转化事件回传有延迟（如 3 天后才到），导致今日归因被"回溯修正"，报表总在变。

**排查与缓解**：

```text
□ 统计回传延迟分布：记录 conversion ts 与 ingest ts 之差
□ 使用"延迟校正"：按历史延迟分布平滑最新几天
□ 对外口径：最终报表用"结算截止日"(如 T+7) 冻结
□ 临时口径：实时看板允许被回溯修正，但标注"未冻结"
□ 平台侧：区分"已结算末尾点击"与"待回填"
```

```sql
-- 观察回传延迟分布，决定结算截止日
SELECT
  DATE_DIFF(ingested_at, conversion_ts, DAY) AS lag_days,
  COUNT(*) AS convs
FROM events
WHERE event_type='conversion'
GROUP BY lag_days ORDER BY lag_days;
```

---

## 五、自测题

### Q1
某 App 对照组基础转化率为 2.0%，你想检测到 30% 的增量率（α=0.05, power=0.80）。请根据两比例样本量公式，估算每组约需多少样本？并解释为什么检测更小的增量需要更多样本。

<details>
<summary>查看答案</summary>

**答案**：δ = 0.02×0.30 = 0.006，p1 = 0.026。

```text
n ≈ 7.84·[0.02×0.98 + 0.026×0.974]/0.006² ≈ 9775
```

每组约需 **9,775**，两组合计约 1.96 万。因为样本量公式中 n ∝ 1/δ²，效应越小所需的样本量按**平方**量级增长——要检测更小的增量，必须大幅增加样本量，否则检验力不足、容易得出"没增量"的错误结论。

</details>

### Q2
用户旅程为 `YouTube曝光 → Meta点击 → Google点击 → 转化`，请说明在"最后点击""线性""位置归因(40/40/20)""时间衰减(半衰期7天)"四种模型下，各渠道大致会拿到多少功劳？

<details>
<summary>查看答案</summary>

**答案**：

```text
最后点击   : Google 100%，其余 0%
线性       : 4 个触点各 25%
位置归因   : YouTube(首)40%，Google(末)40%，Meta/中间 各 10%（(1-0.8)/(4-2)=10%）
时间衰减   : 越靠近转化权重越大 → Google > Meta > YouTube（取决于各自距转化天数）
```

核心区别：**最后点击**只奖励临门一脚；**线性**平均；**位置**兼顾首尾获客与成交；**时间衰减**按时间近远加权。

</details>

### Q3
为什么"归因"不能替代"增量测量"？请用"平台后台转化合计 > 真实成交"的例子解释。

<details>
<summary>查看答案</summary>

**答案**：归因解决的是"已发生转化的功劳怎么分"，它**默认这些转化都是广告带来的**；但增量测量引入**反事实（对照组）**，估计"没有广告会有多少转化"。若某渠道后台揽下 30% 功劳，但把它停投后总生意并未下降 30%，说明这 30% 里大部分是"本就会发生"的转化，并非该渠道的**增量**。因此"归因转化数"被各平台同时认领会虚高（合计 > 真实成交），必须用增量测量（Geo/PSA/GAIA/MMM）先定"蛋糕有多大、广告真贡献多少"，再用归因分"蛋糕怎么切"。

</details>

### Q4
在 iOS ATT/GDPR 隐私约束下，为什么倾向于从"个体级归因"转向"聚合级增量测量（GAIA / MMM / 差分隐私）"？

<details>
<summary>查看答案</summary>

**答案**：个体级归因依赖跨设备身份打通（IDFA/Cookie），而 ATT 与 cookie 弃用导致这些信号显著缺失，匹配率骤降、归因失真，且处理个体 PII 的合规成本高。聚合级方案（GAIA 聚合增量、MMM 时间序列反事实、差分隐私加噪输出、Data Clean Room 受控融合）**不以个体打通为前提**，所需数据更少、隐私风险更低、合规更易满足，同时仍能回答"广告增量与预算"这一类决策问题。因此在强隐私环境下，聚合/受控的因果与预算方法更可落地。

</details>

### Q5
解释 Shapley 值与 Markov 移除效应在"把预算分给哪个渠道"上的差别，并说明为什么 Shapley 通常被认为是更公平的分摊解。

<details>
<summary>查看答案</summary>

**答案**：

- **Shapley 值**：把渠道当合作博弈玩家，按"在所有联盟中的边际贡献平均"分摊总收益，满足效率、对称性、可加性、虚拟性四条公平公理，对**渠道间协同/冗余**有精细处理，经济学上最"公平"。
- **Markov 移除效应**：把旅程建模为马尔可夫链，删掉某渠道后看**转化概率下降多少**，衡量的是该渠道的"不可或缺性"（对转化的依赖程度）。

差别：Shapley 回答"总功劳如何公平分摊"，Markov 回答"谁不可或缺"。Shapley 因为显式处理协同且满足公平公理，常被用于**预算的公平分配**；Markov 则更适合识别**关键不可缺失渠道**。实践中可两者并用：Shapley 定权重、Markov 提示风险。

</details>

### Q6
在 Data Clean Room 中做归因融合时，为什么通常使用"加盐哈希 + PSI 求交集 + DP 加噪输出"，三者各解决什么问题？

<details>
<summary>查看答案</summary>

**答案**：三者分工互补：

- **加盐哈希（Salted Hash）**：把明文 PII（邮箱/手机）安全地变成不可逆的假名化标识，防止彩虹表撞库，同时保持可匹配性（同一输入得同一哈希）；
- **PSI（Private Set Intersection）**：在双方**不向对方暴露各自全集元素**的前提下安全求出交集（哪些用户在两边都有记录），避免一方"看到另一方全部数据"；
- **DP 加噪输出**：在最终聚合结果上叠加受控噪声，保证**即使攻击者知道除某个体外所有数据，也无法推断该个体的记录**，满足 k-anonymity / ε-DP 合规输出。

因此这是"身份安全可比对（hash+PSI）+ 结果隐私保护（DP）"的组合，实现"能分析、不能看见个体"的跨平台归因协作。

</details>

### Q7
预算分配给某渠道的方式有"改 campaign budget""用 value rules 重置转化价值""A/B 迁移验证"。请简述三者权衡与适用时机。

<details>
<summary>查看答案</summary>

**答案**：

- **改**campaign budget** **：直接调整每日/总预算，简单直接，确定性强，能立即改变花费上限；但会打断平台学习窗口，且不精细（无法指定"哪些转化类型更重要"）。适用**：已明确目标渠道、需要精确控制花费、预算整体比例要做大调整时。

- **Value Rules 重置转化价值**：通过抬高/压低某渠道转化事件的价值，把信号喂给平台智能出价，让出价算法"自动"倾向高价值渠道；更精细、利用了平台优化能力，但属于"间接控制"，结果由平台算法决定、可预测性较低。适用**：想要让平台端自动优化、配合智能出价（如 tCPA/tROAS）时。

- **A/B 迁移验证**：把目标分配变化放到一部分流量上跑对照，先验证提升再全量；最稳健、风险最低，但速度慢、需要实验期，不适合"立刻止血/立刻放量"的紧急决策。适用**：分配方案有分歧、或历史数据不足、需要事实证明确改对时。

**实践组合建议**：重大结构调整先用 A/B 验证 → 验证通过后用 campaign budget 落实规模 → 常规微调用 value rules 交给平台优化 → 全程配 CAP/floor 与回滚。

</details>

---

## 附录 A：数学符号约定

| 符号 | 含义 |
| --- | --- |
| Y_i(1) / Y_i(0) | 处理/对照潜在结果 |
| ATE / τ | 平均处理效应 |
| Lift % | 增量率 |
| iROAS | 增量收入/花费 |
| δ | 可检测的效果差 |
| α | 显著性水平（第一类错误） |
| 1-β | 检验力 |
| p0 / p1 | 对照组 / 处理组转化率 |
| z_{1-α/2} | 标准正态双侧临界值（0.05→1.96） |
| v(S) | 联盟 S 的价值 |
| φ_i | 渠道 i 的 Shapley 值 |
| Δf | 全局敏感度（差分隐私） |
| ε | 差分隐私预算 |
| λ | 半衰期（时间衰减） |
| K | 路径触点数量 |
| N | 地理单元数（Geo Lift） |
| σ² | 方差 |
| Q / R / N | 吸收马尔可夫链的转移矩阵分块 |

---

## 附录 B：参考资源与延伸阅读

- Google Ads Help：归因模型与归因窗口、数据驱动归因启用条件
- Meta Business Help Center：归因窗口设置、Conversions API、PSA 增量测试
- TikTok Ads Manager：归因窗口与 Events API
- Google Marketing Platform：GAIA（Aggregate Incremental Ad Impact）
- Amazon Marketing Cloud 文档：SQL 环境与聚合查询
- 《Causal Inference: What If》— Hernán & Robins（因果推断理论）
- 《Attribution Modeling in python / ChannelAttribution》包文档（Markov 与 Shapley 实现）
- 差分隐私经典论文：Dwork 2006《Differential Privacy》
- 各平台 Attribution 与隐私合规（GDPR、DMA、ATT）官方资料

> 本文为方法论与工程实践综合指南；平台数值（窗口、阈值）会随版本变化，**生产中务必以各平台官方最新 API 配置为准**。

---

*文档结束。*
