# Meta Advantage+ 完整体系深度实战文档

> **领域**: 广告投放 / Meta
> **深度**: ⭐⭐⭐⭐⭐ 实战级指南
> **标签**: meta-ads, advantage-plus, asc, aac, automation, ai-ads
> **更新时间**: 2026-08-14
> **类型**: 实战深度文档

---

## 一、核心概念与架构

### 1.1 什么是 Advantage+ 体系

Advantage+（原名 Automatic Placements / Optimization for Ad Delivery，后经多次迭代升级为统一的自动化产品家族）是 Meta 面向广告投放自动化的**一整套产品组合**。它不是单一个功能，而是覆盖「受众、创意、版位、预算、出价、优化、目录」多个维度的自动化矩阵。其设计目标是：把过去需要人工逐层配置与反复测试的投放决策，交给 Meta 的机器学习系统去实时完成，从而在数据量足够的前提下获得更低的获客成本（CPA）和更高的广告花费回报（ROAS）。

Advantage+ 的核心思想可以概括为一句话：

> **把「信号搜集」「创意组合」「受众探索」「预算分配」四件事全部交给模型，人类只负责定义目标、提供素材、设定预算边界。**

这与经典的手动投放（Manual Campaign）形成鲜明对照。手动投放里，广告主明确指定受众、版位、出价、创意，Meta 只是执行者的角色；而 Advantage+ 里，Meta 是决策者，广告主是「资源供给方」。

在本项目中，我们通过 `scripts/ad_platform_api.py` 脚本库以编程方式管理 Advantage+ 相关资源，并结合 Meta Marketing API 的 Graph API 端点做底层控制。本文档会同时给出**产品逻辑**、**Graph API 精确端点与 curl 示例**、**Python 脚本调用方式**，以及**真实业务场景中的踩坑经验**。

### 1.2 Advantage+ 产品家族全景

Advantage+ 家族目前主要包含以下八类产品，本文档会逐一展开：

| # | 产品名称 | 英文全称 | 覆盖维度 | 常见简称 |
|---|----------|----------|----------|----------|
| 1 | 优势受众 | Advantage+ Audience | 受众 | AAP（Ad Set 层）/ ABA |
| 2 | 优势创意 | Advantage+ Creative | 创意（素材增强、动态组合） | AAC / ADC |
| 3 | 优势版位 | Advantage+ Placements | 版位 | A+ Placements |
| 4 | 优势购物广告系列 | Advantage+ Shopping Campaigns | 电商全流程 | ASC |
| 5 | 优势应用广告系列 | Advantage+ App Campaigns | 应用安装/转化 | AAC（App） |
| 6 | 优势目录广告 | Advantage+ Catalog Ads | 目录/动态商品 | ACA / DPA Advantage |
| 7 | 优势预算 | Advantage+ Budget（Advantage Campaign Budget） | 预算分配 | ACB / ABB |
| 8 | 优势优化 | Advantage+ Optimizations | 优化目标/出价 | A+ Optimizations |

> ⚠️ **命名易混提醒**：`Advantage+ Creative` 与 `Advantage+ App Campaigns` 的缩写都可能是「AAC」。为区分，本文档统一用 **ADC** 表示 Advantage+ Creative（Creative 取首字母 C 的衍生），用 **AAC** 表示 App Campaigns；涉及 Audience 时用 **ABA**。凡是出现 AAC 的地方，本文档默认指 **Advantage+ App Campaigns**，除非上下文明确指 Advantage+ Creative。

### 1.3 Advantage+ 体系的四层架构

整个 Advantage+ 体系可以在逻辑上分为四层。理解这四层是掌握全部产品的前提：

```
┌─────────────────────────────────────────────────────────────┐
│  L4 目标层（人类定义）                                          │
│   Objective / Buying Type / 转化目标 / CAC 或 LTV 预期 / 预算上限 │
├─────────────────────────────────────────────────────────────┤
│  L3 策略层（模型决策，Advantage+ 核心）                          │
│   Advantage+ Audience · Advantage+ Creative                   │
│   Advantage+ Placements · Advantage+ Budget · Optimization     │
├─────────────────────────────────────────────────────────────┤
│  L2 执行层（资产准备）                                          │
│   Catalog 商品池 · 素材库（图片/视频/文案/HOOK） · Pixel/CAPI 事件 │
├─────────────────────────────────────────────────────────────┤
│  L1 数据层（信号底座）                                          │
│   Pixel · Conversion API · 应用事件 · 目录 feed · 离线转化        │
└─────────────────────────────────────────────────────────────┘
```

关键点：**L1 数据层是地基**。Advantage+ 的机器学习本质上依赖转化信号的质量和密度。如果 Pixel / CAPI 数据缺失、延迟、字段不一致，那么上层所有 Advantage+ 产品都会「无米下锅」，模型探索阶段会显著拉长，甚至出现预算花不出去或 CPA 虚高的情况。这一点在后面「与 CAPI/Pixel 数据质量的关系」一节会重点讲。

### 1.4 按「受众控制权」划分的两大类 Advantage+

Advantage+ 家族可以从「Modeled Audience」的角度分成两类：

**A 类：受众仍由广告主划定（模型在圈内优化）**

这类产品里，广告主仍然给出受众边界（例如自定义受众、国家、年龄），模型只负责在边界内优化交付、创意和预算：

- Advantage+ Audience（作为 Ad Set 的受众选项，勾选「Advantage+ audience」后 Meta 负责拓展/重叠处理）
- Advantage+ Placements（自动版位）
- Advantage+ Creative（创意增强）
- Advantage+ Budget（预算共享）
- Advantage+ Optimizations（优化选择）

**B 类：受众由 Meta 全权探索（模型自主找用户）**

这类产品的受众决策完全交给 Meta 的系统（Advantage+ Shopping Audience），也是 ASC / AAC 最与众不同的地方：

- ASC（Advantage+ Shopping Campaigns）——受众由 Meta 的「Advantage+ shopping audience」自动探索
- AAC（Advantage+ App Campaigns）——受众由 Meta 自动探索，广告主只提供一个「初始种子受众」作为偏置

这个二分法非常关键，因为它解释了为什么 ASC 不能细分受众、不能把受众压得很窄——因为 B 类产品的价值恰恰在于让模型在大范围里自主寻找高转化人群。如果广告主强行细分，反而破坏模型的学习空间。

### 1.5 统一架构图：一个 ASC 在体系中的位置

以最复杂的 ASC 为例，看它如何把其他 Advantage+ 组件整合在一起：

```
                      ┌──────────────────────────────────────────┐
                      │  ASC (Advantage+ Shopping Campaigns)      │
                      │  objective = OUTCOME_SALES / OUTCOME_APP  │
                      └──────────────┬───────────────────────────┘
                                     │
        ┌────────────────────────────┼────────────────────────────┐
        ▼                            ▼                            ▼
┌───────────────┐            ┌───────────────┐            ┌───────────────┐
│  Advantage+   │            │  Advantage+   │            │  Advantage+   │
│  Shopping     │            │  Placements   │            │  Creative     │
│  Audience     │            │  (全版位)     │            │  (动态创意)    │
│  (受众探索)    │            │               │            │               │
└───────────────┘            └───────────────┘            └───────────────┘
        │                            │                            │
        ▼                            ▼                            ▼
┌───────────────┐            ┌───────────────┐            ┌───────────────┐
│ Catalog 商品池 │            │  Pixel + CAPI │            │  素材库        │
│ Dynamic     │            │  (转化信号)    │            │ 图片/视频/文案  │
│ Product Set │            │               │            │ HOOK/Benefit  │
└───────────────┘            └───────────────┘            └───────────────┘
        │                            │                            │
        └────────────┬───────────────┴────────────┬───────────────┘
                     ▼                            ▼
        ┌──────────────────────┐       ┌──────────────────────┐
        │  模型实时分配流量      │       │  Advantage+ Budget    │
        │  探索 vs 利用 平衡     │       │  (组合预算动态分配)     │
        └──────────────────────┘       └──────────────────────┘
```

这张图串起了本文档的大部分内容。后面 2.x 节会逐层深挖其内部机制。

### 1.6 术语对照表（速查）

以下术语会在全文反复出现，先建立统一口径：

| 术语 | 缩写 | 含义 |
|------|------|------|
| Advantage+ Shopping Audience | — | ASC 内的模型受众，Meta 自主探索 |
| Advantage+ Shopping Campaigns | ASC | 电商广告自动化 campaign 类型 |
| Advantage+ App Campaigns | AAC | 应用投放广告自动化 campaign 类型 |
| Advantage+ Creative | ADC | 创意增强/动态创意组件 |
| Advantage+ Audience | ABA | Ad Set 层的自动化受众选项 |
| Advantage+ Placements | — | 全自动版位（以前叫 Automatic Placements） |
| Advantage Campaign Budget | ACB | 广告系列预算优化 |
| Dynamic Ads / DPA | DPA | 动态商品广告（Carousel/单商品） |
| Product Set / 商品集 | — | Catalog 中的商品筛选池 |
| Catalog | — | 商品目录，商品数据的仓库 |
| Conversion API | CAPI | 服务端事件回传 |
| Pixel | — | 浏览器端事件追踪 |
| OUTCOME_SALES | — | Optimization Goal，优化「购买」 |
| OUTCOME_APP | — | 优化「应用内事件」 |
| LAL / Lookalike | LAL | 类似受众 |
| 学习期 | — | 模型根据最近数据校准的阶段 |
| Ultimate Conversion | — | 优化目标里较后的转化步骤 |
| Broad / Hoarding | — | 模型在大量用户里「囤积」转化信号 |

### 1.7 各 Advantage+ 产品的适用场景矩阵

不同 Advantage+ 产品适合不同的业务阶段与投放目标。下表是决策时的速查表：

| 产品 | 最佳适用场景 | 典型 KPI | 覆盖对象 |
|------|--------------|----------|----------|
| ASC | 电商放量、目标 CPA/ROAS 明确、素材多元 | CPA ↓、ROAS ↑ | 老客+新客 |
| AAC | 应用拉新/促活/付费优化 | 安装成本、付费 ROAS | 拉新、再营销 |
| Advantage+ Shopping Ads（目录增强） | 电商想用目录但没有完整 ASC 时 | CTR、加购率 | 目录曝光 |
| Advantage+ Audience（Ad Set 层） | 传统 conversion 想拓宽触达 | CPA ↓ | 老客+新客 |
| Advantage+ Creative | 提升点击率与素材复用率 | CTR、CPC | 创意层 |
| Advantage+ Placements | 所有绩效 campaign 的基础版位策略 | eCPM、CPA | 所有 |
| Advantage+ Budget（组合预算） | 多 campaign/多商品抢同一用户池 | 总 ROAS | 跨 campaign |
| Advantage+ Optimizations | 想要自动出价/Ultimate 优化 | CPA、ROAS | 优化目标 |
| Advantage+ for Videos | 视频素材少、想自动生成变体 | 完播率、CTR | 视频广告 |

#### 1.7.1 按投放目标选产品（决策树）

```
你现在的目标是什么？
│
├── 电商卖货，量要上来，能接受交给模型
│   └── ASC（首选）
│
├── 电商卖货，但转化信号很稀、要精确控制
│   └── DPA / Catalog Ads + Advantage+ 组件
│
├── 推广 App，要安装量
│   └── AAC（安装优化）
│
├── 推广 App，要付费/留存
│   └── AAC（App Events + ROAS 目标）
│
├── 卖实体商品但不想换 campaign 结构
│   └── 现有 conversion campaign + Advantage+ Audience/
│        Placements/Budget/Creative
│
└── 品牌/曝光为主，几乎不追踪转化
    └── 传统 brand campaign + Advantage+ Creative/Placements
```

### 1.8 Advantage+ 家族的时间线与版本演变（理解命名混乱）

Advantage+ 命名经历了多次合并，理解演变有助于看懂旧文档与旧代码：

```
时间线（示意）
│
│  早期：Automatic Placements（自动版位）
│   │      Optimization for Ad Delivery（转化优化）
│   │      Campaign Budget Optimization (CBO) → 后并入 Advantage+ Budget
│   │
│  中期：Dynamic Ads（DPA）
│   │      App Installs / App Campaigns
│   │      Automated rules
│   │
│  现在：Advantage+ 统一品牌
│   │      Advantage+ Audience / Creative / Placements / Budget
│   │      Advantage+ Shopping Campaigns (ASC)
│   │      Advantage+ App Campaigns (AAC)
│   └      Adv+ Optimizations / Catalog Ads / Videos
```

理解这一点，你就不会奇怪为什么某些老代码里出现「Automatic Placements」「CBO」这样的参数——它们现在大多被 Advantage+ 统一命名取代，但在 Graph API 字段层可能仍以旧名出现（例如 `campaign_budget_optimization`）。

---

## 二、深度原理解析

### 2.1 ASC 的结构：Campaign → AdSet → Ad

ASC 虽然套用了 Campaign / AdSet / Ad 三层结构，但其层级含义与手动投放有本质区别。

#### 2.1.1 结构总览

```
ASC 层级结构
│
├── Campaign（广告系列）
│   ├── 目标：购买 / 应用安装（电商）
│   ├── 特殊广告类目（special_ad_categories）：无/政治/信用等
│   ├── 预算：单一每日预算 或 组合预算（Advantage Campaign Budget）
│   ├── 优化目标：OUTCOME_SALES（购买）等
│   └── 是否启用 Advantage+：是（campaign 级标记）
│
├── Ad Set（广告组）
│   ├── 受众：Advantage+ Shopping Audience（模型自主，非手工受众）
│   ├── 版位：Advantage+ Placements（自动全版位）
│   ├── 优化：Advantage+ Optimization
│   ├── 预算分配：由 Advantage+ Budget 动态切分
│   └── 起始国家、币种（可选国家定向）
│
└── Ad（广告）
    ├── 素材：图片/视频/文案/标题/描述/CTA
    ├── 商品：绑定整个 Catalog（而非单个商品集）或指定产品集
    ├── 动态创意：Advantage+ Creative 关闭时，广告内多个素材由模型选择
    └── 追踪：utm / pixel / CAPI
```

#### 2.1.2 ASC 与传统 Campaign 的层级差异

| 维度 | 传统手动 campaign | ASC |
|------|-------------------|-----|
| Ad Set 数量 | 广告主可建多个，每个自定受众 | 通常 1-2 个，受众由模型管 |
| 受众 | 手工受众/自定义/LAL | Advantage+ Shopping Audience |
| 版位 | 可选或手动布局 | 强制 Advantage+ Placements（全自动） |
| 创意 | 每个 Ad 固定一个 creative | 一个 Ad 带多套素材，由模型组合 |
| 商品绑定 | 常绑定单个商品集 | 可绑定整个 Catalog，模型全球选品 |
| 预算 | 每 Ad Set 独立预算 | 组合预算，模型分配 |
| 出价 | 可手动设 bid | 自动出价（Auto Bid）+ 可选 ROI 目标 |

#### 2.1.3 为什么 ASC 的 Ad Set 通常只有一个

在手动投放中，广告主通过「多个 Ad Set = 多个受众 + 多个测法」来做 A/B。但在 ASC 中，**受众由模型统一管理**，如果广告主强行建多个 Ad Set（例如按国家分多个 Ad Set、按价格带分多个 Ad Set），反而会：

1. 把总预算切成多份，每份训练样本变少，学习期反复；
2. 模型无法在 Ad Set 之间重新分配流量（Advantage+ Budget 只在启用组合预算时才跨 Ad Set 动态分配）；
3. 人为制造用户重叠与数据稀疏。

所以 ASC 最佳实践是：**单 Ad Set（或极少数），把预算集中，让模型在最大的搜索空间里探索**。商品选择的差异通过「绑定不同商品集」或「素材差异」来体现，而不是通过 Ad Set 受众差异来体现。

### 2.2 ASC 的机器学习机制

#### 2.2.1 三阶段交付模型（交付漏斗）

Meta 的广告交付本质是一个「实时竞价 + 概率预测」的三阶段漏斗。ASC 在此基础上强化了「探索」能力：

```
                    ┌─────────────────────────────────────┐
                    │           广告竞价流程                 │
                    └─────────────────────────────────────┘
                                   │
        ┌──────────────────────────┼──────────────────────────┐
        ▼                          ▼                          ▼
┌──────────────┐          ┌──────────────┐          ┌──────────────┐
│  Stage 1     │          │  Stage 2     │          │  Stage 3     │
│  过滤候选用户  │  ──────▶ │  模型打分排序  │  ──────▶ │  竞价出价      │
│  (谁有机会看) │          │  (预测转化率) │          │  (确定展示)   │
└──────────────┘          └──────────────┘          └──────────────┘
                                 │
                       ┌─────────┴─────────┐
                       ▼                   ▼
              ┌──────────────┐    ┌──────────────┐
              │ p(转化率)    │    │  竞价因子      │
              │ p(点击率)    │    │  广告质量分     │
              │ p(价值)      │    │  出价金额      │
              │ 新鲜度/重复   │    └──────────────┘
              │ 上下文       │
              └──────────────┘
```

ASC 的核心是让这个漏斗里的「预测转化率」由模型在 **Advantage+ Shopping Audience** 上学习，而不是局限于手工受众。模型会不断尝试展示给不同人群，观察哪些人产生购买，然后逐渐把预算倾斜到高转化人群。

#### 2.2.2 探索（Explore）与利用（Exploit）的平衡

机器学习在广告里本质上是在解决「探索-利用」权衡（Explore–Exploit Tradeoff）：

- **利用（Exploit）**：把预算集中在已知高转化的用户身上，最大化当前回报；
- **探索（Explore）**：把一小部分预算花在「尚未验证」的用户或素材上，收集新信号。

ASC 内置了一个动态的探索预算（通常表现为「模型保留小比例预算用于测试新受众/新创意」）。这个比例的合理性直接决定了：

- 探索太少 → 命中率虽高但增长见顶，放不了量；
- 探索太多 → CPA 虚高，浪费预算。

这就是为什么 ASC 需要「**足够的预算**」和「**充分的学习期**」——如果预算太少，探索比例不足以让模型积累足够的转化样本；如果频繁改预算/改创意打断学习，模型每次都要重新校准。

#### 2.2.3 主导创意（Dominant Creative）机制

ASC 的一个可观察特性是「主导创意」：经过一段时间学习后，某一个或某几个创意会拿到绝大部分流量，其他创意流量趋近于零。

```
创意流量分布随时间变化
│
│  创意 A  ████████████████████████████████████
│  创意 B  ██████████
│  创意 C  ████
│  创意 D  ██
│  创意 E  █
│  创意 F  .
│
└──────────────────────────────────────────▶ 时间
                模型收敛后出现主导创意
```

这意味着：**素材是 ASC 的胜负手**。如果素材本身质量差、同质化严重，模型无论怎么组合都只能从「矮子里拔将军」。相反，如果你的素材池差异足够大（不同利益点、不同风格、不同人群视角），模型才有足够的空间去「选出赢家并放大」。

#### 2.2.4 为什么 ASC 需要「信号密度」

机器学习需要样本。Meta 的经验数据表明：

| 优化目标 | 建议的每周转化信号量 | 说明 |
|----------|---------------------|------|
| OUTCOME_SALES（购买） | 建议每周 ≥ 某个转化下限（经验上购物类常要求 20+ / 周量级，越多越好） | 采购事件是最稀疏的信号 |
| （中间步骤，如加购） | 更宽松 | 中间事件更密集 |
| OUTCOME_APP | 应用内事件 | 同上 |

如果转化信号不足，ASC 会进入长期的「探索模式」，预算花出去但 CPA 迟迟不降。这种情况下需要：

1. 提升数据质量（CAPI 后端回传补足 Pixel 丢失）；
2. 使用「Ultimate Conversion」或更早的优化步骤作为过渡；
3. 增加预算到模型能「看到足够多转化」的量级；
4. 延长学习期观察窗口，不要频繁操作。

### 2.3 ASC 的创意动态组合

#### 2.3.1 创意组件的组成

ASC 的一个 Ad 里，创意不再是一张图或一条视频，而是一个「组件组合」，模型会实时拼接。常见组件维度：

```
创意动态组合（Creative Composition）
│
├── 媒体素材（Media）
│   ├── 主图/主视频（Primary media）
│   └── 附加媒体（Additional media，视频+图片可混搭）
│
├── 文案（Primary text / Body）
│   ├── 多组文案（最多可给多条，模型 A/B）
│   └── 自动生成文案（AI 生成）
│
├── 标题（Headline）
│   └── 多条标题，模型选优
│
├── 描述（Description）
├── CTA（行动号召按钮）
├── 品牌名（Brand）
├── 展示链接（Display URL / Website URL）
│
└── 商品元素（Dynamic product）
    ├── 主商品（从 Catalog 选）
    └── 搭配商品（Carousel 多商品）
```

#### 2.3.2 素材的最佳数量

Meta 官方建议 ASC 提供充足的素材变体。实践中，比较稳健的配置是：

| 素材维度 | 建议数量 | 说明 |
|----------|----------|------|
| 图片 | 3-5+ 张 | 不同构图/场景 |
| 视频 | 3-5+ 条 | 不同利益点/风格 |
| 文案（Primary text） | 5+ 条 | 覆盖不同卖点/人群 |
| 标题 | 5+ 条 | 与文案、目标人群匹配 |
| 利益点/特色（Optional） | 尽可能多且互不重复 | 用于生成「利益点增强创意」 |

一个常见的误区是「我给了 2 张图 + 2 条文案就够了」。实践表明，**素材变体太少时，ASC 的学习空间被压缩**，模型没有足够多的「组合可能性」来实现真正的动态创意，最终效果与「手动投放固定创意 + 自动版位」差别不大。

#### 2.3.3 素材多样性指南

素材多样性的正确打开方式不是「同一张图换几个颜色」，而是「不同利益点 + 不同人群视角 + 不同叙事」：

```
素材多样性 should be 语义级，而非像素级
│
│  不要：同一主图 4 个背景色（低多样性）
│  要  ：同一主图 4 个利益点文案（卖点不同）
│  要  ：视频 A 讲「功效」，视频 B 讲「使用场景」
│  要  ：视频 C 用 KOL/真人出镜，视频 D 用产品特写
│  要  ：文案 1 针对「新客」讲首单，文案 2 针对「复购」讲套装
```

#### 2.3.4 动态创意与 Audience 的组合优化

ASC 的动态创意本质上是一个「**内容-受众联合学习**」（Content-Audience Joint Optimization）：模型不只学「哪个人群转化高」，还学「哪个创意配哪个人群效果好」。因此：

- 创意与受众是**联合**优化的，而不是「先定受众再选创意」；
- 这也是为什么 ASC **不能细分受众**——你一旦把受众框死，联合学习的搜索空间就塌了一半。

### 2.4 ASC 的受众/预算/投放逻辑

#### 2.4.1 受众逻辑：Advantage+ Shopping Audience

Advantage+ Shopping Audience 是 ASC 内建的、由 Meta 模型驱动的受众。它的特点是：

| 特性 | 说明 |
|------|------|
| 自主探索 | 模型自动在更广人群中找高转化用户 |
| 无手工受众 | 你可以加「起始国家」等粗边界，但无法手工 ABC 细分 |
| 利用历史数据 | 会参考 Custom Audience、Pixel 数据、目录行为作为「信号种子」 |
| 自动去重 | 模型处理用户重叠 |
| 可附加定位（Optional） | 某些情况下可附加「custom audience 作为起点」，但作为起步偏置而非精确边界 |

**关键认知**：你仍然需要给模型「信号」——例如你有一个过往购买者的 Custom Audience，或在 Pixel 里有加购/购买事件。模型会把这些人当作「已知高转化锚点」，然后从这些人身上扩展相似用户。所以**广告主的历史数据质量直接决定 ASC 受众探索的起点**。

#### 2.4.2 预算逻辑：组合预算与动态分配

ASC 支持两种预算方式：

1. **单一 campaign 每日预算**：为整个 campaign 设每日预算，Ad Set 之间由模型分配（前提是启用 Advantage Campaign Budget）。这是最常用的方式。
2. **Campaign 预算优化（ACB / Advantage+ Budget）**：把预算放在 campaign 层，模型在 Ad Set / 创意 / 商品之间动态分配。

```
Advantage Campaign Budget 原理
│
│  Campaign 每日预算 = $300
│
├── 模型按「实时预期价值」切分到 Ad Sets
│   ├── Ad Set A（获客效率高）→ $180
│   ├── Ad Set B（探索/新客）→ $90
│   └── Ad Set C（暂停/停滞）→ $30
│
└── 分配随数据实时更新，不要求广告主手动调
```

在 「Advantage+ 完整体系」语境下的 Advantage+ Budget，通常就指这个组合预算机制——**预算在 campaign 内各交付单元之间动态流动**，避免「一个 Ad Set 预算花不完、另一个却超支」的经典问题。

#### 2.4.3 出价与优化

- 出价默认 **自动出价（Auto Bid）**，模型根据竞争环境和转化概率动态出价以达成目标；
- 可选 **ROAS 目标出价（Advantage+ Target ROAS）**：你设定一个期望的 ROI（例如 3.0），模型在尽量达成该 ROI 的前提下花费预算；
- 优化目标：通常 OUTCOME_SALES（购买），也可用 OUTCOME_APP（应用内事件），或选择更早的中间步骤（如加购「AddToCart」）作为过渡优化。

#### 2.4.4 投放逻辑与学习期

- 新 ASC 会经历学习期（Learning Phase），期间模型收集数据校准；
- 学习期内不要频繁暂停/调整；
- 预算大幅波动（例如一日翻 3 倍）会打断学习。

### 2.5 ASC 与传统 DPA（动态商品广告）的差异

这是广告主最容易混淆的一处。DPA（Dynamic Product Ads，动态商品广告/目录广告）是更早的技术，ASC 在很多维度上是对 DPA 的自动化升级。关键差异如下：

| 维度 | 传统 DPA（目录广告） | ASC（Advantage+ Shopping Campaigns） |
|------|----------------------|----------------------------------------|
| Campaign 类型 | 用 Sales/Conversions+目录，传统受众 | 独立 ASC campaign |
| 受众 | 手工受众 / 再营销 / LAL | Advantage+ Shopping Audience（模型探索） |
| 创意 | 通常 Carousel 固定模板 + 目录商品 | 动态创意组合（素材组件 + 商品） |
| 商品选择 | 依赖 Product Set / 触发器（如加购不买） | 模型更主动地动态选品 |
| 版位 | 通常自动但可选手动 | 强制 Advantage+ Placements |
| 预算 | 每 Ad Set 独立预算 | 组合预算，模型分配 |
| 个性化粒度 | 按「用户历史行为」推荐 | 按用户行为 + 模型探索 + 素材组合 |
| 学习方式 | 规则触发 + 用户行为 | 端到端机器学习联合优化 |
| 测试成本 | 广告主需人工建多个变体 | 内置自动测试 |

**核心区别一句话**：DPA 是「把目录商品用固定创意模板推给按规则圈定的人群」；ASC 是「把整个目录 + 多套素材交给模型，让模型同时决定「给谁看、用什么创意、推荐哪个商品、花多少预算」。

#### 2.5.1 什么时候不该用 ASC（仍然用 DPA）

不是所有场景都应该切到 ASC。以下场景 DPA / 手动更合适：

- **转化信号极稀疏**且无法补足时（例如超低频高价 B2B 大件）；
- **需要严格遵守品牌安全/合规**、必须精确控制受众与版位时；
- **预算极小**（低于 ASC 最低预算阈值），模型没有学习空间时；
- **正处于严格控制的精细投放实验**，需要隔离变量时。

### 2.6 AAC（Advantage+ App Campaigns）的安装/转化逻辑

Advantage+ App Campaigns（AAC）是用来推广移动应用（推广 App 安装或应用内事件）的自动化 campaign。它的逻辑与 ASC 有对称性，但目标不同。

#### 2.6.1 AAC 的目标

| 目标 | 说明 |
|------|------|
| 应用安装（App Installs） | 最大化安装量 |
| 应用事件（App Events） | 优化注册/付费/特定事件（如 Purchases） |
| 混合（App Promotion） | 相对复杂的目标组合 |

AAC 同样由模型管理受众与版位，广告主提供：

- 创意素材（图片/视频/预览）；
- 一个「初始种子受众」（可选，作为偏置）；
- App 事件的接入（通过 Facebook App Events SDK 或 MMP）。

#### 2.6.2 AAC 结构

```
AAC 层级结构
│
├── Campaign
│   ├── 目标：App Promotions / App Installs / App Events
│   ├── 买量：按安装或按事件
│   └── 预算：每日预算 / lifetime
│
├── Ad Set
│   ├── 受众：App Advantage+ Audience（模型探索）
│   ├── 版位：Advantage+ Placements（全自动）
│   └── 优化：按目标选择（安装/事件/ROAS）
│
└── Ad
    ├── 创意素材（图片/视频，可达多条，模型组合）
    ├── 应用链接/商店链接
    └── 追踪：App Ads Helper / CAPI / MMP 回传
```

#### 2.6.3 AAC 的安装逻辑

- **安装优化**：模型学习「哪些素材、哪些人群最可能安装」，随后把预算集中；
- 受众上，AAC 分两种：用「Advantage+ audience」时（模型探索），或可选「app audience」（如针对已安装/类似安装用户做再营销）。前者适合拉新，后者适合促活/再营销。

#### 2.6.4 AAC 的转化（App Events）逻辑

- 接入 **Facebook App Events SDK** 或 **MMP（如 Adjust / AppsFlyer / Singular，支持 S2S）** 回传事件；
- 优化「付费事件」时，模型预测每个用户未来付费概率与价值，优先展示给高 LTV 倾向用户；
- 可设置 **ROAS 目标**（如目标安装后 7 日 ROAS）。
- 注意：应用内事件的回传质量极大影响 AAC 效果。若事件缺失、字段不符、延迟过高，模型信号会被污染。

#### 2.6.5 AAC 与「App Campaigns（旧 Auto App Ads）」的关系

较早版本的 App Campaigns（通过 `objective=APP_INSTALLS` / `app_campaign=AD_APP_CAMPAIGN` 或「Localized Manual Placements」）相对手动；而 Advantage+ App Campaigns 是在此基础上把受众、版位、创意、优化全面自动化的形态。两者的共性是用 App 相关目标，差异仍是「自动化程度」。

### 2.7 其余 Advantage+ 组件的原理

#### 2.7.1 Advantage+ Audience（Ad Set 层）

适用于非 ASC/AAC 的传统 Campaign（如普通转化/流量/品牌）。当你在 Ad Set 里开启「Advantage+ audience」：

- 模型会在你给出的「起始受众」（如有）基础上自动扩宽；
- 自动去除重叠用户，自动寻找 lookalike 高转化人群；
- 你放弃对「详细定向/排除」的精确控制，换取更大流量空间与更低 CPA。

```
Advantage+ Audience 打开前后
│
│  关闭（Manual）                      打开（Advantage+）
│  ┌──────────────┐                   ┌──────────────────────┐
│  │ 固定兴趣/自定义 │                   │ 起始受众 + 模型扩展     │
│  │ 精确受众      │                   │ 自动扩展 + 自动去重     │
│  └──────────────┘                   └──────────────────────┘
```

打开方式：Ad Set → Targeting → 勾选「Advantage+ audience」。
关闭方式：关闭该开关，使用 Manual Targeting。

#### 2.7.2 Advantage+ Creative（创意增强）

Advantage+ Creative 是一组创意自动化能力，作用于单个 creative：

| 能力 | 说明 |
|------|------|
| 智能裁剪（Smart Crop） | 自动为不同版位裁剪图片/视频 |
| 自动生成变体 | 基于给定素材自动生成多种尺寸/比例 |
| 动态文案 | 为不同用户生成/适配文案 |
| 背景定制 | 自动放大/补充背景以适配版位 |
| 音乐/旁白 | 视频增强功能 |

在 creative 的 `object_story_spec` 里，往往通过 `Advantage+ Creative` 相关字段控制。打开方式：在创意设置里开启「Advantage+ creative」开关；关闭方式：关闭该开关并用静态源素材。

> 注意：Advantage+ Creative 打开后，你看到的「展示出去的样子」可能不是你上传的原始素材（模型做了增强/组合）。这让某些追求「所见即所得」的品牌（尤其合规严格的行业）选择关闭。

#### 2.7.3 Advantage+ Placements（版位）

- 自动在所有版位（Feed、Stories、Reels、Video Feeds、Instant Articles、Marketplace、Audience Network 等）实时投放；
- 模型根据「哪个版位对当前目标转化贡献最高」实时分配预算；
- 打开/关闭：Campaign 或 Ad Set 层选择「Advantage+ placements」或手动勾选特定版位。ASC/AAC 通常强制 Advantage+ Placements。

#### 2.7.4 Advantage+ Optimizations（优化）

指自动化优化选择，包括优化目标下钻、Ultimate Conversion、自动出价等。例子：

- 用「Ultimate conversion」时，模型把较前的转化（如加购）当作优化信号，同时向更后转化（购买）靠拢；
- 自动获取更多转化（Modeled conversions）。

#### 2.7.5 Advantage+ Budget（组合预算）

- 把预算放在更高层级，由模型在子层级（Ad Set / 广告 / 商品）之间动态分配；
- 单独设置的 Ad Set 预算在限额内使用，支持「Cap」防止某个 Ad Set 花超；
- 打开方式：在 Ad Set 层开启「Advantage Campaign Budget」并把预算设为 campaign 层；
- 关闭方式：改为每 Ad Set 独立预算。

### 2.8 各 Advantage+ 产品的打开/关闭方式总表

| 产品 | 在哪里配置 | 打开方式 | 关闭方式 |
|------|-----------|----------|----------|
| Advantage+ Audience | Ad Set → Targeting | 勾选 Advantage+ audience | 取消勾选，用 Manual targeting |
| Advantage+ Creative | Creative 设置 | 开启 Advantage+ creative 开关 | 关闭开关，使用源素材 |
| Advantage+ Placements | Campaign/Ad Set → Placements | 选择 Advantage+ placements | 手动勾选具体版位 |
| Advantage+ Budget | Ad Set → Performance & Goal | 开启 Advantage Campaign Budget（campaign 层预算） | 关闭，改每 Ad Set 预算 |
| Advantage+ Optimizations | Ad Set → Optimization | 选择 Ultimate/Advantage 优化 | 选择固定优化目标 |
| ASC | 新建 campaign 选 Advantage+ shopping campaign | 直接进入 ASC 流程 | 改用传统 Sales/Conversions campaign |
| AAC | 新建 campaign 选 App 目标并开启 Advantage+ | 进入 Advantage+ app campaign | 用手动 App campaign |
| Advantage+ Catalog Ads | 目录广告 campaign 内 | 开启 Advantage+ 相关优化 | 用传统 DPA 配置 |

### 2.9 一张图看懂「该用哪个 Advantage+」

```
                    你的投放目标是什么？
                            │
        ┌───────────────────┼───────────────────┐
        ▼                   ▼                   ▼
     电商（卖货）          App（应用）          品牌/其他转化
        │                   │                   │
        ▼                   ▼                   ▼
  场景是否适合快速自动化？  用 AAC              用传统 campaign
        │                                       + Advantage+
        ├── 是 → ASC                            Audience/Creative/
        │        （Advantage+ Shopping）         Placements/Budget
        │
        └── 否 → 用 DPA + Advantage+ 组件
                 （控制性强但自动化低）
```

### 2.10 机器学习分配逻辑的细化：Value 信号的来源

Advantage+（尤其 ASC 与 AAC 的「价值」维度）不仅看「是否转化」，还看「转化的价值」。理解 Value 信号从哪来，能解释为什么同一 Cost 下 ROAS 差异巨大。

```
Value 信号来源
│
├── 转化金额（Purchase 事件的 value）
│   ├── 来自 Pixel：browser 端 Purchase 事件带 value
│   └── 来自 CAPI：服务端回传更准确的 order value
│
├── 商品价值
│   ├── Catalog 里每个商品的价格
│   └── 订单里商品组合的客单价
│
├── 长期价值（LTV）近似
│   ├── 通过「事件时序」推断：注册→加购→购买→复购
│   └── AAC 里用 app events 序列预测 LTV
│
└── 相邻信号
    └── 加购/收藏/结账可作为购买的前置信号
```

**实践意义**：如果你在 Pixel/CAPI 里没有正确传 `value` 与 `currency`，模型会把所有转化视为「等值」，从而更偏向「数量多但金额低」的人群，导致 ROAS 偏低。因此**价值信号的质量直接决定 Advantage+ 的价值优化效果**。

### 2.11 为什么 Advantage+ 会被误认为「玄学」：可解释性边界

Advantage+ 的决策是黑盒的，这让很多投放操盘手觉得「玄」。其实它的行为是可被归纳的，只是因果链很复杂：

| 可被解释 | 难以精确解释 |
|----------|--------------|
| 高转化人群获得更多预算 | 模型到底用了哪些特征打分 |
| 主导创意流量占比提升 | 为什么某个素材突然起量 |
| 预算在多国间按表现流动 | 具体某次竞价输给了谁 |
| CAPI/Pixel 数据好则信号足 | 平台更新后模型行为的漂移 |

**应对策略**（实战）：
- 用「投放结构」做可观测变量（素材版本、Ad Set 边界、国家），把黑盒问题转成「控制一个变量观察整体指标」；
- 不逐日微观解读，而是以 7 天窗口看趋势；
- 记录「变更日志」：每次改了什么、改于何时、后续 7 天指标如何——形成自己的经验库。

### 2.12 ASC 内「动态创意」的详细运转：Ad Creative 的组合爆炸

ASC 的动态创意本质是在「有限素材输入」下生成大量「组合创意」。模型在曝光前按用户特征选择最合适的组合：

```
给定素材输入
│  3 个视频 × 3 张图片 × 5 条文案 × 3 个标题 × 3 CTA
│  = 理论上可生成 3×3×5×3×3 = 405 种组合
│
└── 模型实时决策
    ├── 对用户 A（年轻女性，冲浪场景）→ "视频2 + 文案5 + 标题3"
    ├── 对用户 B（中年男，价格敏感）  → "图片1 + 文案1 + 标题1 + 折扣CTA"
    └── 对用户 C（已加购未买）        → "商品特写 + 文案2 + 结账CTA"
```

**要点**：组合数是「乘积」关系，所以素材维度每多一个、每个维度多几条，组合空间会指数级扩大。这正是我们强调「素材语义多样」的数学基础——多样素材让模型有更多「组合杠杆」可用。

#### 2.12.1 product_tags 与素材增强

ASC 支持 `product_tags`，允许把目录商品的「利益点/特色」标签贴到素材上，模型据此生成「利益点增强创意」（如「免运费」「48 小时发货」徽章）。给足互不重复的标签，能显著提升动态创意的表现力。

```json
{
  "product_tags": [
    {"provider_name": "free_shipping", "label": "Free Shipping"},
    {"provider_name": "fast_delivery", "label": "48h Delivery"},
    {"provider_name": "discount", "label": "Extra 20% Off"}
  ]
}
```

#### 2.12.2 素材组内互补 vs 互斥

- **互补素材**：同一个商品的不同卖点/角度，模型可自由组合——适合 ASC；
- **互斥素材**：竞品、不同定位、必须分开投放——不应放同一 ASC Ad 内，否则模型可能学出「模棱两可」的人群。

### 2.13 学习期的三个阶段细节

很多操盘手只听说「学习期 5-7 天」，其实学习期内部可分三阶段：

```
学习期三阶段
│
├── 阶段A（冷启动 1-3 天）
│   ├── 模型对人群/素材一无所知，广泛探索
│   ├── 表现通常不稳定、CPA 偏高
│   └── 切忌此时下结论
│
├── 阶段B（收敛 3-5 天）
│   ├── 模型开始锁定高转化信号
│   ├── CPA 下行、起量加快
│   └── 主导创意逐渐显现
│
└── 阶段C（稳定 5-7 天）
    ├── 模型近收敛，指标相对稳定
    ├── 此时才适合评估 CPA/ROAS、决定放量
    └── 任何大改动都回到阶段A
```

**操作铁律**：学习期内（尤其阶段 A/B）不要改预算、改受众、改素材、暂停。要改就先记录，等一个完整学习期后再评估。

### 2.14 AAC 的安装与转化完整数据流

把 AAC 从「建 campaign」到「模型学习」的数据流转画全：

```
AAC 数据流
│
│  App 侧
│   ├── Facebook App Events SDK（客户端埋点）
│   └── MMP（Adjust/AppsFlyer/Singular，S2S 回传）
│        └── 回传 install / 注册 / 付费 事件
│
│  事件到达 Meta
│   ├── 与用户去重、归因（click/impression 窗）
│   └── 写入该 App 的事件库
│
│  模型学习
│   ├── 学习「哪些投放单元带来 install」
│   └── 学习「哪些用户后续付费」（LTV 预测）
│
│  出价与展示
│   ├── 按 install/ROAS 目标实时出价
│   └── 预算分配到促成高 LTV 用户的素材/人群
```

**关键陷阱**：App 事件必须与「广告点击」正确关联（靠 click_id / event source）。如果 App 内 SDK 初始化前用户已点击广告，或用错 MMP 归因（如 MMP 与 Meta 归因口径冲突），会造成「明明在买量、Meta 却看不到转化」的假象。

---

## 三、生产环境实战

### 3.1 前置条件：数据质量是 Advantage+ 的生命线

在创建任何 Advantage+ 系列之前，先确认数据底座。这里用本项目脚本演示如何核对。

#### 3.1.1 检查 Pixel / CAPI 配置

```python
# scripts/ad_platform_api.py 中的 meta_query_insights 可用于核对转化
from ad_platform_api import MetaAdPlatform  # 假定的类名，具体以项目为准

client = MetaAdPlatform()  # 初始化，读取 credentials

# 查看账户下的转化设置
account_id = "act_<你的广告账户ID>"
pixel_id = "<你的Pixel ID>"

# 核对标准转化 / 自定义转化是否配置正确
conversions = client.meta_list_standard_conversions(account_id)
for c in conversions:
    print(c.get("name"), c.get("event"), c.get("id"))
```

#### 3.1.2 核对 CAPI 事件回传

```python
# 校验 CAPI 事件是否正常到达
pixel_id = "<Pixel ID>"
capi_events = client.meta_list_capi_events(pixel_id)
for ev in capi_events:
    print(ev.get("event_name"), ev.get("event_time"), ev.get("user_data", {}).get("hashed_email"))
```

建议在跑 ASC/CAC 前确认：

1. Pixel 与 CAPI 都开启，且事件不重复（去重逻辑正常）；
2. 核心事件（Purchase / AddToCart / InitiateCheckout）字段完整；
3. 事件延迟可控，避免 CAPI 与 Pixel 延迟导致同归因窗重复计数。

#### 3.1.3 补充说明：CAPI 端点到本项目

本项目在 `scripts/ad_platform_api.py` 中提供了 `meta_send_capi`、`meta_send_capi_batch`、`meta_validate_event_data`、`meta_list_matched_fields` 等方法，可在需要为 ASC 补齐服务端事件时调用。数据质量相关踩坑详见「四、常见问题与排查」的 4.6 节。

### 3.2 准备 Catalog 与 Product Set

ASC 可以绑定整个 Catalog 或某个 Product Set。推荐先用 Product Set 圈定「主推商品池」。

#### 3.2.1 列出 Catalog

```python
# 列出账户下所有商品目录
catalogs = client.meta_list_catalogs(account_id)
for c in catalogs:
    print(c.get("id"), c.get("name"))
```

#### 3.2.2 创建 / 列出动态商品集（Product Set）

```python
catalog_id = "<Catalog ID>"

# 列出已有动态商品集
product_sets = client.meta_list_dynamic_product_sets(catalog_id)
for ps in product_sets:
    print(ps.get("id"), ps.get("name"))

# 创建新的动态商品集（用一个简单的 Rule 过滤）
new_set = client.meta_create_dynamic_product_set(
    catalog_id,
    name="ASC-Main-Products",
    filter={
        "name": "product_set",
        "filter": {
            "field": "price",
            "operator": "GREATER_THAN",
            "value": "0"
        }
    }
)
print(new_set)
```

> 提示：Hyper 模式下动态商品集即 `product_set` 对象，可用 `filter` 冻结 URL 参数表达商品规则。伪代码如下，具体以项目封装为准：

```python
# 更稳定的做法：直接通过 API 传 filter
product_set = client.meta_create_dynamic_product_set(
    catalog_id, name="MainPool",
    filter={
        "name": "product_set",
        "filter": {
            "field": "availability",
            "operator": "IN",
            "value": ["in stock"]
        }
    }
)
```

#### 3.2.3 核对商品列表

```python
# 列出商品，确保 Catalog 数据含可用商品
products = client.meta_list_catalog_products(catalog_id)
print("商品总数:", len(products))
for p in products[:5]:
    print(p.get("id"), p.get("product_name"), p.get("price"))
```

### 3.3 用 Python 脚本创建 ASC（核心）

本节展示如何通过 `scripts/ad_platform_api.py` 以编程方式创建 ASC。由于脚本对高低层级做了一定封装，这里给出「直接组装 + 调用封装方法」两种视角。

#### 3.3.1 创建 Campaign（ASC 主系列）

```python
account_id = "act_<ID>"

# 创建 ASC 主 campaign
# objective 在 Sales 系中使用 OUTCOME_SALES
camp = client.meta_create_campaign(
    account_id,
    name="ASC - 北美 - Main - 2026-08",
    objective="OUTCOME_SALES",
    status="PAUSED",            # 先暂停，配置好再启用
    buying_type="AUCTION",
    special_ad_categories=[],    # 无特殊类目；若有则填 ["CREDIT"] 等
)
campaign_id = camp["id"]
print("Campaign ID:", campaign_id)
```

#### 3.3.2 创建 Ad Set（ASC 组，受众全部交给模型）

```python
# ASC 的 Ad Set 受众交给模型，不手工传详细定向
adset = client.meta_create_adset(
    campaign_id,
    name="ASC - AdSet - AudienceAuto",
    daily_budget=1000000,        # 1,000,000 = 100 * 10000（分）
    bid_strategy="LOWEST_COST_WITHOUT_CAP",
    optimization_goal="OFFSITE_CONVERSIONS",
    targeting={
        "geo_locations": {"countries": ["US", "CA"]},
        "age_min": 18,
        "age_max": 65,
        "page_types": ["MobileAndDesktop"],
        "publisher_platforms": ["facebook", "instagram", "messenger", "audience_network"],
    },
    billing_event="IMPRESSIONS",
    status="PAUSED",
)
adset_id = adset["id"]
print("AdSet ID:", adset_id)
```

> 上面 `targeting` 只给出粗边界（国家/年龄/平台），**不放入手工兴趣或详细排除**——这正是 ASC 受众交给模型的做法。

#### 3.3.3 创建 Ad（含 Catalog 与多素材）

ASC 的 Ad 绑定 Catalog/Product Set，并携带多套素材供模型组合。

```python
ad = client.meta_create_ad(
    adset_id,
    name="ASC - Ad - CreativeSet1",
    status="PAUSED",
    creative={
        "name": "ASC Creative",
        "object_story_spec": {
            "page_id": "<你的Page ID>",
            # 动态商品：绑定 catalog / product_set
            "product_set_id": product_set_id,
            "link_data": {
                "link": "https://yourstore.com",
                "message": "多条文案由模型选择：A/B versions ...",
                "headline": "多标题模板",
                "call_to_action": {"type": "SHOP_NOW"},
                "image_source": {}                # 会由动态商品填充
            }
        },
        "template_url_spec": {"web": {"url": "https://yourstore.com"}},
        "product_tags": [],                       # 可选，用于增强素材
    },
    tracking_urls={"tracking_specs": "utm_source=facebook&utm_medium=pa&utm_campaign=asc"},
)
ad_id = ad["id"]
print("Ad ID:", ad_id)
```

然后启用：

```python
# 全部启用
client.meta_resume_campaign(campaign_id)
print("ASC 已启用")
```

> ⚠️ 不同版本的脚本对 `product_set_id` / `catalog_id` 的字段传递方式略有差异。创建前先用 `meta_list_dynamic_product_sets` 拿真实 product_set，再用 `meta_create_ad` 传入，能减少 400 报错。

### 3.4 用 Graph API + curl 创建 ASC（底层）

脚本封装最终会落到 Graph API。这里给出可直接验证的 curl 端点。Graph API 版本以 `v19.0` 为例（本项目脚本也用了 v19.0）。

先准备好：
- `ACCESS_TOKEN`：长期 token 或系统用户 token；
- `AD_ACCOUNT_ID`：形如 `act_1234567890`；
- `PAGE_ID`、`CATALOG_ID`、`PRODUCT_SET_ID`。

#### 3.4.1 创建 ASC Campaign

```bash
curl -X POST \
  "https://graph.facebook.com/v19.0/act_<AD_ACCOUNT_ID>/campaigns" \
  -F "access_token=$ACCESS_TOKEN" \
  -F "name=ASC-NA-Main" \
  -F "objective=OUTCOME_SALES" \
  -F "status=PAUSED" \
  -F "buying_type=AUCTION" \
  -F "special_ad_categories=[]"
```

返回：

```json
{"id": "120000000000000", "name": "ASC-NA-Main"}
```

要点：`special_ad_categories` 为空数组表示非特殊类目；若投放信贷产品需传 `["CREDIT"]`，这类会导致部分自动投放能力受限。

#### 3.4.2 创建 ASC Ad Set

```bash
curl -X POST \
  "https://graph.facebook.com/v19.0/<CAMPAIGN_ID>/adsets" \
  -F "access_token=$ACCESS_TOKEN" \
  -F "name=ASC-AdSet-Auto" \
  -F "daily_budget=1000000" \
  -F "billing_event=IMPRESSIONS" \
  -F "bid_strategy=LOWEST_COST_WITHOUT_CAP" \
  -F "optimization_goal=OFFSITE_CONVERSIONS" \
  -F "targeting={'geo_locations':{'countries':['US','CA']},'age_min':18,'age_max':65,'page_types':['MobileAndDesktop'],'publisher_platforms':['facebook','instagram','messenger','audience_network']}" \
  -F "status=PAUSED"
```

#### 3.4.3 创建 ASC Ad（绑定目录 + 素材）

```bash
curl -X POST \
  "https://graph.facebook.com/v19.0/<ADSET_ID>/ads" \
  -F "access_token=$ACCESS_TOKEN" \
  -F "name=ASC-Ad-Creative1" \
  -F "status=PAUSED" \
  -F "adset_id=<ADSET_ID>" \
  -F "creative={'name':'ASC-Creative','object_story_spec':{'page_id':'<PAGE_ID>','product_set_id':'<PRODUCT_SET_ID>','link_data':{'link':'https://yourstore.com','message':'多条文案','headline':'多标题','call_to_action':{'type':'SHOP_NOW'}}},'template_url_spec':{'web':{'url':'https://yourstore.com'}}}" \
  -F "tracking_urls={'__CONTAINER_AS_TRACKING__':[]}"
```

#### 3.4.4 启用

```bash
curl -X POST \
  "https://graph.facebook.com/v19.0/<CAMPAIGN_ID>" \
  -F "access_token=$ACCESS_TOKEN" \
  -F "status=ACTIVE"
```

### 3.5 用 Python 脚本查看/管理已有 Advantage+ 系列

#### 3.5.1 列出账户下的 campaign

```python
campaigns = client.meta_list_campaigns_by_account(account_id)
for c in campaigns:
    print(c.get("id"), c.get("name"), c.get("status"), c.get("objective"))
```

#### 3.5.2 查看某 campaign 下的 Ad Sets / Ads

```python
adsets = client.meta_list_adsets(campaign_id)
for a in adsets:
    print(a.get("id"), a.get("name"))

ads = client.meta_list_ads_by_adset(adset_id)
for a in ads:
    print(a.get("id"), a.get("name"))
```

#### 3.5.3 查询洞察（Insights）

```python
insights = client.meta_query_insights(
    account_id,
    date_preset="last_7d",
    fields="campaign_name,spend,actions,outbound_clicks,cpc,cpm,ctr",
    level="campaign",
)
for row in insights.get("data", []):
    print(row.get("campaign_name"), row.get("spend"), row.get("ctr"))
```

> 实际脚本中输出的字段名以小写为主，如有差异以实际 API 返回为准。

### 3.6 用 Python 脚本创建 AAC（Advantage+ App Campaigns）

AAC 的目标与 ASC 不同，这里演示通过脚本创建。

#### 3.6.1 创建 AAC Campaign

```python
# AAC 的 objective 用应用类目标
app_camp = client.meta_create_campaign(
    account_id,
    name="AAC - US - AppEvents - 2026-08",
    objective="OUTCOME_APP",     # 或 APP_INSTALLS，视目标
    status="PAUSED",
    buying_type="AUCTION",
    special_ad_categories=[],
)
app_campaign_id = app_camp["id"]
```

#### 3.6.2 创建 AAC Ad Set

```python
app_adset = client.meta_create_adset(
    app_campaign_id,
    name="AAC - AdSet",
    daily_budget=800000,
    bid_strategy="LOWEST_COST_WITHOUT_CAP",
    optimization_goal="APP_EVENTS",       # 应用事件
    targeting={
        "app_install": {
            "app_store": "apple_app_store",
            "app_id": "<你的App ID>",
            "object_store_url": "itms-apps://itunes.apple.com/app/id<APPLE_APP_ID>",
        },
        "geo_locations": {"countries": ["US"]},
        "publisher_platforms": ["facebook", "instagram"],
    },
    billing_event="IMPRESSIONS",
    status="PAUSED",
)
```

> 不同版本的 App objective 配置字段有差异（`app_install` 结构、`application_id` 等）。创建前用 `meta_get_adset` 先读一个已存在的 App campaign 作参照会更稳。

#### 3.6.3 创建 AAC Ad

```python
app_ad = client.meta_create_ad(
    app_adset_id,
    name="AAC - Ad - Video",
    status="PAUSED",
    creative={
        "name": "AAC Creative",
        "object_story_spec": {
            "page_id": PAGE_ID,
            "video_data": {
                "video_id": "<视频库ID>",
                "image_url": "<首帧图>",
                "message": "App 推广文案",
                "call_to_action": {"type": "INSTALL_APP"},
            }
        },
        "template_url_spec": {"app": {"url": "https://apps.apple.com/..."}},
    },
)
```

### 3.7 Graph API 里 ASC/AAC 的关键响应字段解读

创建成功后，用 GET 读取，关注以下字段以判断是否真正「Advantage+」：

```bash
# 读取 campaign 详情，看 objective / special_ad_categories 等
curl -G "https://graph.facebook.com/v19.0/<CAMPAIGN_ID>" \
  -d "access_token=$ACCESS_TOKEN" \
  -d "fields=id,name,objective,status,special_ad_categories,daily_budget,optimization_goal,buying_type"
```

```bash
# 读取 adset，看受众/版位是否 Advantage+
curl -G "https://graph.facebook.com/v19.0/<ADSET_ID>" \
  -d "access_token=$ACCESS_TOKEN" \
  -d "fields=id,name,targeting,optimization_goal,bid_strategy,daily_budget,billing_event"
```

```bash
# 读取 ad 的 creative，确认是否绑定商品目录
curl -G "https://graph.facebook.com/v19.0/<AD_ID>" \
  -d "access_token=$ACCESS_TOKEN" \
  -d "fields=id,status,creative,adcreative_enabled,campaign"
```

### 3.8 Advantage+ Budget 与 Portfolio Budget 的管理

#### 3.8.1 预算拆分（Budget Split）

优势预算的另一种表现是「Budget Split」，允许把一笔预算按比例拆分到多个账户/活动（常用于同一 Campaign 下不同来源）。项目脚本提供：

```python
# 列出已有预算拆分
splits = client.meta_list_budget_splits(account_id)
for s in splits:
    print(s.get("id"), s.get("name"))

# 创建预算拆分
from datetime import date, timedelta
today = date.today()
new_split = client.meta_create_budget_split(
    account_id,
    name="Split-2026-08",
    split_source_config={
        "budget_split_primary_dataset_id": "<dataset id>",  # 用于自定义受众拆分
        "split_source_type": "CUSTOM_AUDIENCE",
    },
    split_part_config=[
        {"split_part_type": "CUSTOM_AUDIENCE", "split_part_value": "<custom_audience_id>", "split_part_name": "CA-A"},
        {"split_part_type": "CUSTOM_AUDIENCE", "split_part_value": "<custom_audience_id>", "split_part_name": "CA-B"},
    ],
    start_date=today.isoformat(),
    end_date=(today + timedelta(days=30)).isoformat(),
)
print(new_split)
```

#### 3.8.2 组合预算（Portfolio Budget / Delta Budget）

「Portfolio Budget」把多个账户/系列的预算池化：

```python
portfolios = client.meta_list_portfolio_budgets(account_id)
for p in portfolios:
    print(p.get("id"), p.get("name"))

new_portfolio = client.meta_create_portfolio_budget(
    account_id,
    name="Portfolio-NA-2026",
    daily_budget=5000000,           # 组合每日预算
    start_date=today.isoformat(),
    end_date=(today + timedelta(days=30)).isoformat(),
)
print(new_portfolio)
```

#### 3.8.3 优点与注意

- 组合预算让模型在不同 Campaign / Ad Set 之间动态调配，适合「多个 Campaign 相互有用户重叠、预算互相抢」的场景；
- 注意：组合预算开启后，单个 Ad Set 的预算是「Cap（上限）」而非「固定值」，模型可以低于上限花。

### 3.9 素材与创意准备：让 ASC 真正发挥

#### 3.9.1 素材清单模板

建议在跑 ASC 前按下面清单准备好素材：

| 素材维度 | 数量建议 | 关键提示 |
|----------|----------|----------|
| 主视频 | 3-5 条 | 每条表达不同利益点/不同人群 |
| 主图 | 3-5 张 | 不同构图，避免同一张图改色 |
| 文案（Primary text） | 5+ 条 | 覆盖新客/复购/套装/首单等卖点 |
| 标题 Header | 5+ 条 | 与文案对应 |
| CTA | 统一或少量 | 建议统一 SHOP_NOW 便于对比 |
| 品牌名 | 1 个 | — |

#### 3.9.2 用脚本批量上传素材（示意）

```python
# 通过 creatives 接口批量建 multiple creatives（示意）
from ad_platform_api import MetaAdPlatform

creatives = client.meta_list_creatives(account_id)
print("已建创意数量:", len(creatives))
```

> 具体素材文件上传在脚本中通过 `meta_add_products` / `meta_update_catalog_product`（目录商品）或创意的 `object_story_spec` 处理。批量上传建议按目录 feed 方式批量入库，效率高于逐个上传。

#### 3.9.3 素材多样性自检清单

```
ASC 素材自检
│
├── 是否 >5 条互相「语义不同」（非换色）的素材？
├── 是否覆盖不同人群视角（新客/复购/高意向）？
├── 是否既有视频又有图片？
├── 是否每条素材的标题/CTA 能与文案匹配？
├── 是否避免「同一主视觉 + 四行不同文案」的低效组合？
└── 是否在广告上线前就把素材一次性给足（避免上线后再补）？
```

### 3.10 预算与放量：从测试到规模化

#### 3.10.1 起始预算

- ASC 的最低预算与地区/币种有关（例如美国市场常见建议每日预算不低于某个美元阈值，需以账户实际提示为准）；
- 给模型「足够学习」的预算，通常不低于最低阈值数倍更稳。

#### 3.10.2 放量路径

```
放量安全路径
│
├── 阶段1 测试期：每日预算 2-3 倍最低值，跑足 5-7 天学习期，只看结果不改预算
├── 阶段2 稳定期：确认 CPA/ROAS 达标，+20-30% 预算，间隔观察
├── 阶段3 放量期：翻倍或更多，但一次别让预算跳 3 倍以上
└── 阶段4 常态化：小步多次调，每次记录「调预算→学习期→结果」闭环
```

#### 3.10.3 失败如何快反

- 若 7-10 天 CPA 仍高于目标 2 倍：先查素材质量与信号密度，不盲目加预算；
- 若预算花不完（花出率低）：可能受众探索受限或素材相关性差，检查是否误设手工详细定向/排除。

### 3.11 多国投放

#### 3.11.1 国家边界 vs 模型探索

ASC 可通过 `geo_locations.countries` 指定投放国家。多国投放有两种做法：

1. **单 Ad Set 多国**：让模型在多个国家间按转化效率分配预算（推荐，给模型更大探索空间）；
2. **每国一 Ad Set**：需要独立预算与对比，但会稀释单 Ad Set 样本量。

```
多国投放决策
│
├── 各国转化信号都充足 → 可单 Ad Set 多国，模型自动分配
├── 信号不平衡（A国强B国弱）→ 建议按强弱分，或先用模型观察再分
└── 必须严格按国控制预算 → 用组合预算 + Cap 或分 Ad Set
```

#### 3.11.2 多国注意事项

- 货币换算：脚本与 API 中预算以「分/小额单位」计，多国需注意币种与汇率影响；
- 时区：Lifetime 预算按广告账户时区计算；
- 语言/素材本地化：文案最好按目标国语言提供，否则模型在非母语市场难做动态组合。

### 3.12 常见完整流程：把上述串起来

```
ASC 上线 11 步清单
│
├── 1. 确认数据底座：Pixel + CAPI 事件完整、无重复
├── 2. 准备 Catalog 与 Product Set
├── 3. 准备素材池（图片/视频/文案/标题，语义多样）
├── 4. 用脚本/API 创建 Campaign（OUTCOME_SALES）
├── 5. 创建 Ad Set（受众交给模型，粗边界即可）
├── 6. 创建 Ad（绑定目录 + 多素材）
├── 7. 检查 GET 确认 special_ad_categories 正确、objective 正确
├── 8. 设置预算（campaign 层或组合预算）
├── 9. 启用并进入学习期，5-7 天不改
├── 10. 用 meta_query_insights 监控 CPA/ROAS
├── 11. 依据数据小幅放量或调整素材
```

### 3.13 Graph API 中 adv_advantage 系列字段详解

Graph API 通过一组 `adv_advantage` 前缀字段控制 Advantage+ 能力。理解这些字段，能在 API 层精确开关各组件。

#### 3.13.1 campaign 层的 adv_advantage 字段

```bash
curl -G "https://graph.facebook.com/v19.0/act_<AD_ACCOUNT_ID>/campaigns" \
  -d "access_token=$ACCESS_TOKEN" \
  -d "name=AdvTest" \
  -d "objective=OUTCOME_SALES" \
  -d "status=PAUSED" \
  -d "buying_type=AUCTION" \
  -d "special_ad_categories=[]" \
  -d "adv_advantage_campaign_budget=true"
```

> 说明：`adv_advantage_campaign_budget=true` 表示启用 campaign 预算优化（Advantage+ Budget）。不同字段可能随版本演进，实际以账户可用字段为准。

#### 3.13.2 adset 层的 adv_advantage 字段（受众/版位/优化）

```bash
curl -X POST "https://graph.facebook.com/v19.0/<CAMPAIGN_ID>/adsets" \
  -F "access_token=$ACCESS_TOKEN" \
  -F "name=AdvAdSet" \
  -F "daily_budget=1000000" \
  -F "billing_event=IMPRESSIONS" \
  -F "optimization_goal=OFFSITE_CONVERSIONS" \
  -F "targeting={'geo_locations':{'countries':['US']},'age_min':18,'age_max':65}" \
  -F "promoted_object={'pixel_id':'<PIXEL_ID>','custom_event_type':'PURCHASE'}" \
  -F "adv_advantage_audience=true" \
  -F "status=PAUSED"
```

> `adv_advantage_audience=true` 启用 Advantage+ Audience（模型探索受众）。若想限制模型探索范围，可用 `adv_advantage_audience` + 起始受众字段加以偏置。

#### 3.13.3 creative 层：Advantage+ Creative 开关

在 creative 的 `object_story_spec` 或直接字段上控制：

```bash
curl -X POST "https://graph.facebook.com/v19.0/<ADSET_ID>/adcreatives" \
  -F "access_token=$ACCESS_TOKEN" \
  -F "name=AdvCreative" \
  -F "object_story_spec={'page_id':'<PAGE_ID>','link_data':{'link':'https://yourstore.com','message':'Advantage+ creative 增强','headline':'测试','call_to_action':{'type':'SHOP_NOW'}}}" \
  -F "template_url_spec={'web':{'url':'https://yourstore.com'}}" \
  -F "adv_advantage_creative=true"
```

> `adv_advantage_creative=true` 启用创意增强；`false` 则保留你的原始素材（所见即所得）。

#### 3.13.4 读取时如何确认每个 Advantage+ 开关

```bash
curl -G "https://graph.facebook.com/v19.0/<ADSET_ID>" \
  -d "access_token=$ACCESS_TOKEN" \
  -d "fields=id,name,adv_advantage_audience,targeting,effective_status,bid_strategy,daily_budget,optimization_goal"
```

返回中 `adv_advantage_audience` 为 true/false，可据此确认该 Ad Set 是否处于 Advantage+ 受众模式。

### 3.14 用脚本批量创建多个 ASC（放量场景）

当需要一次性起多个国家/多个商品池的 ASC 时，用循环批量创建，注意保留 id 映射。

```python
# 批量创建多个 ASC（按国家拆分的例子，取决于数据量是否足够）
countries = ["US", "CA", "GB", "DE"]
created = {}

for country in countries:
    # 每个国家一个独立 campaign，便于按国控制
    camp = client.meta_create_campaign(
        account_id,
        name=f"ASC-{country}-2026-08",
        objective="OUTCOME_SALES",
        status="PAUSED",
        buying_type="AUCTION",
        special_ad_categories=[],
    )
    cid = camp["id"]

    adset = client.meta_create_adset(
        cid,
        name=f"ASC-{country}-AdSet",
        daily_budget=1000000,
        bid_strategy="LOWEST_COST_WITHOUT_CAP",
        optimization_goal="OFFSITE_CONVERSIONS",
        targeting={
            "geo_locations": {"countries": [country]},
            "age_min": 18,
            "age_max": 65,
        },
        billing_event="IMPRESSIONS",
        status="PAUSED",
    )
    aid = adset["id"]

    created[country] = {"campaign_id": cid, "adset_id": aid}
    print(f"{country}: campaign={cid}, adset={aid}")

# 全部启用（可选：确认无误后再启用）
for country in created:
    client.meta_resume_campaign(created[country]["campaign_id"])
```

> 注意：是否「按国拆 campaign」取决于你的数据量。若某国转化信号不足，拆出来反而导致该国 campaign 一直处于探索态。数据均衡时可拆，不均衡时建议单 campaign 多国。

### 3.15 用脚本做素材/创意批量管理

ASC 最适合「素材多跑量」，脚本循环注册多个 creative 是高频操作。

```python
# 为某个 AdSet 批量创建多个 ad（不同 creative）
adset_id = "<ADSET_ID>"
image_ids = ["img_1", "img_2", "img_3"]   # 已上传的图片库 ID
messages = [
    "首单立减优惠，点击购买",
    "全网最低价，48 小时发货",
    "升级你的装备，限时活动",
    "老客复购享 9 折",
]

for idx, (img, msg) in enumerate(zip(image_ids, messages)):
    ad = client.meta_create_ad(
        adset_id,
        name=f"ASC-Ad-Creative{idx+1}",
        status="ACTIVE",
        creative={
            "name": f"Creative{idx+1}",
            "object_story_spec": {
                "page_id": PAGE_ID,
                "link_data": {
                    "link": "https://yourstore.com",
                    "message": msg,
                    "headline": f"标题{idx+1}",
                    "call_to_action": {"type": "SHOP_NOW"},
                    "image_hash": img,
                }
            },
            "product_set_id": PRODUCT_SET_ID,
        },
        tracking_urls={"tracking_specs": f"utm_source=facebook&utm_campaign=asc&mt={idx+1}"},
    )
    print("created ad:", ad.get("id"))
```

### 3.16 ASC 监控与诊断：用 Insights 定位问题

#### 3.16.1 关键指标组合

单一指标会误导，建议按「成本 + 效率 + 规模」三组看：

```python
insights = client.meta_query_insights(
    account_id,
    date_preset="last_14d",
    fields=(
        "campaign_name,spend,impressions,clicks,ctr,cpc,cpm,"
        "actions,purchases,conversions,roas,cost_per_action_type"
    ),
    level="campaign",
    time_increment=1,     # 便于看趋势
)
```

#### 3.16.2 诊断思路

```
ASC 诊断框架（7 天窗口）
│
├── ROI 达标吗？
│   ├── 达标 → 放量（+20-30%），看下个窗口
│   └── 不达标 → 进入下一步
│
├── 是 CPA 高，还是量不足？
│   ├── CPA 高：查素材质量、信号密度、是否探索过多
│   └── 量不足/花不出去：查受众是否过窄、素材相关性、预算是否够
│
├── 是某一国/某素材拖后腿？
│   ├── 素材层：暂停表现最差的创意，看是否改善
│   └── 国层：用国家维度 insights 定位
│
└── 数据本身准吗？
    └── 核对 CAPI/Pixel 去重、归因窗口
```

#### 3.16.3 按维度拆分 insights

```python
# 按 "ad" 维度看哪个素材在拖后腿
by_ad = client.meta_query_insights(
    account_id,
    date_preset="last_7d",
    fields="ad_name,spend,actions,ctr,roas",
    level="ad",
)
for row in by_ad.get("data", []):
    print(row.get("ad_name"), row.get("spend"), row.get("roas"))

# 按 "country" 维度看多国表现
by_country = client.meta_query_insights(
    account_id,
    date_preset="last_7d",
    fields="country,spend,actions,roas",
    level="country",
)
```

### 3.17 ASC 与离线/抽象转化的处理（Ultimate Conversion）

当购买信号稀疏时，ASC 会难以收敛。Meta 提供「Ultimate Conversion」类优化（在部分账户可用），它把较前的转化事件当作代理信号：

```
优化目标选择决策
│
├── 购买信号充足（每周几十+） → 直接优化 Purchase
├── 购买信号中等 → 可优化 Purchase + 观察
├── 购买信号稀疏 → 用中间事件（AddToCart/InitiateCheckout）作为过渡
└── 极稀疏且无法补足 → 考虑传统 campaign + 手动优化，而非硬用 ASC
```

在 Graph API 中，`optimization_goal` 常结合 `optimization_event` 字段来指定。若账户支持 Ultimate Conversion，可设置让模型从较前事件向 Purchase 靠拢（具体字段与可用性需按账户查询）。

> ⚠️ Ultimate Conversion 需要你同时回传中间事件（AddToCart 等），否则模型没有「前置信号」可用。这也是数据质量在 ASC 冷启动的重要性体现。

### 3.18 成本与预算换算实战提醒

脚本与 API 中预算、出价、价值以「分/微单位」计，容易出现数量级错误：

| 场景 | 常见错误 | 正确做法 |
|------|----------|----------|
| daily_budget | 把美元直接填进 API | API 用「分」，USD $100 = 10000 |
| CAPI value | 值传成整数美分 | value 以「元」计，currency 必填 |
| ROAS 计算 | 忘记 value 单位 | 用 value（元）÷ spend（换算后） |
| 多国币种 | 所有国家同一 budget 数值 | 按汇率换算成账户币种 |

```python
# 预算换算示意：以美元为例，API 用分
USD_DOLLAR = 100.0
daily_budget_cents = int(USD_DOLLAR * 100)  # 10000
print("API daily_budget（分）:", daily_budget_cents)
```

---

## 四、常见问题与排查

### 4.1 ASC 学习期有多久、何时算「稳定」

- 新 ASC 学习期通常 5-7 天，期间系统用最近数据校准；部分目标（低频购买）可能更长。
- 判定标准不是「天数」而是「是否有足够转化信号」：若 7 天转化 < 目标建议量，可能处于持续探索态。
- 排查：用 `meta_query_insights` 看转化事件量与 latency，若一直偏低，优先补数据而不是加预算。

### 4.2 ASC 最低预算是多少

- 官方对 ASC 每日预算有下限（不同国家/币种不同，需看账户内提示）。用脚本创建时若返回预算过低的 400，说明低于阈值。
- 实践经验：建议设为最低预算的 2-3 倍，以保证模型有学习余量。
- 若预算极低（远低于阈值）跑 ASC，会出现「花不出去」或「CPA 虚高」。

### 4.3 为什么 ASC 不能细分受众

- 因为 ASC 的核心价值是「让模型在 Advantage+ Shopping Audience 里自主找高转化用户」。细分受众 = 人为压缩学习空间，会显著降低自动化带来的 CPA/ROAS 增益。
- 需要精确控制受众的合规/品牌场景，建议回到 DPA 或传统 campaign，不要硬用 ASC。

### 4.4 数据倾斜问题（信号分布不均）

- 现象：转化信号偏向某一国家/某一素材/某一商品，模型被「带偏」。
- 原因：历史数据分布不均、素材引入流量不均、Pixel/CAPI 埋点不均。
- 对策：
  1. 用组合预算 + 国家边界让模型在更大空间内平衡；
  2. 保证素材多样性，避免某类素材独占流量；
  3. 检查 CAPI 是否漏掉某类设备的转化。

### 4.5 测试与放量的取舍

- 不要用 ASC 做「手工细粒度 A/B」——那是手动 campaign 的事；
- 测试集中在「素材组合」与「整体系列」层面；
- 放量遵循 20-30% 阶梯，避免单次跳 3 倍打断学习。

### 4.6 与 CAPI / Pixel 数据质量的关系（核心踩坑）

这是 ASC/AAC 成败的最高频原因。数据质量问题表现如下：

| 症状 | 可能根因 | 排查动作 |
|------|----------|----------|
| ASC 预算花不出去 / 花出率低 | 模型找不到足够「可信」转化的用户 | 核对 Pixel/CAPI 事件是否正常到达 |
| CPA 虚高、一直探索态 | 转化信号稀疏或回传延迟 | 用 CAPI 补服务端事件，检查延迟 |
| ROAS 波动剧烈 | 归因受 CAPI/Pixel 双写重复 / 延迟影响 | 核对去重逻辑与归因设置 |
| 学习期反复 | 频繁改预算/素材打断校准 | 减少操作频率 |

推荐在数据薄弱时：

```python
# 用 CAPI 补 Server-side 事件（提升信号密度）
# 传入 hashed email / phone 等匹配字段
client.meta_send_capi(
    pixel_id,
    event_name="Purchase",
    event_time=<timestamp>,
    user_data={
        "em": "<sha256(email)>",
        "ph": "<sha256(phone)>",
        "client_ip_address": "<ip>",
        "client_user_agent": "<ua>",
        "fbc": "<click_id>",
        "fbp": "<browser_id>",
    },
    custom_data={
        "currency": "USD",
        "value": 49.99,
        "content_ids": ["pid_123"],
        "content_type": "product",
    },
)
```

### 4.7 ASC 与手动系列如何共存

很多团队是「手动作主导、ASC 做补充」：

```
投放组合策略
│
├── 手动作系：控制性强、精细测试、品牌/合规场景
├── ASC：放量、低成本获客、模型自主探索
├── DPA：再营销、目录个性化
└── 预算层面：用组合预算避免互相抢用户
```

- 两者可用同一 Pixel/CAPI 信号；
- 避免「同一受众、同一素材」在手动作与 ASC 同时出现造成自我竞争，需靠归因设置与预算管理协调。

### 4.8 常见 API 报错与处理

| 报错 | 含义 | 处理 |
|------|------|------|
| 400 `(#100) param special_ad_categories must be non-empty` | 被判定为特殊类目但未传 | 正确传 `special_ad_categories`，如 `["CREDIT"]` |
| 400 `budget too small` | 每日预算低于阈值 | 提高 daily_budget |
| 400 `optimization_goal not allowed` | 目标与 objective 不匹配 | 核对 objective/optimization_goal 组合 |
| 400 `targeting too narrow` | 受众/排除过窄（不利模型探索） | 去掉过多详细定向/排除 |
| 400 `creative invalid` | 素材结构错误 | 用 `meta_get_ad` 读取参照创意结构 |
| #200 `(OAuthException)` | token 失效/权限不足 | 刷新 token、检查 scope |

### 4.9 为什么「照搬别人跑赢的 ASC 配置」不一定灵

- ASC 高度依赖你自己的数据（Pixel/CAPI、历史转化、Catalog 商品质量），不同账户信号质量差异巨大；
- 照搬预算/素材数量但不匹配自身数据密度，往往效果打折；
- 建议以本文 3.12 的「11 步清单」为基线，再按自己数据量微调。

### 4.10 素材显示「与上传不一致」

- 若开启了 Advantage+ Creative，展示的可能是模型自动增强/组合后的版本；
- 若必须「所见即所得」，关闭 Advantage+ Creative 并确认 `adcreative_enabled` 状态。

### 4.11 归因窗口与优化目标选择

- 优化目标越靠后（购买）、归因窗口越宽，数据越稀疏，学习越慢；
- 中间过渡（加购/结账）事件更密集，可作为冷启动过渡，稳定后再切到购买。

### 4.12 为什么「预算涨了量却没涨」？

这是放量阶段最常见的困惑。可能原因：

| 原因 | 说明 | 对策 |
|------|------|------|
| 触及受限/受众饱和 | 模型在当前受众/市场找不到更多高转化用户 | 加市场（国家）、新素材、或放宽边界 |
| 素材组合穷尽 | 现有素材的组合都被验证过，无新组合可试 | 补充语义不同的新素材 |
| 预算突增打断学习 | 一下加太多预算，模型需要重新校准 | 小步 20-30% 递增 |
| 数据信号不足封顶 | 转化事件量本身见顶 | 提升 CAPI 信号质量 |
| 预算花不完 | 花出率低，钱没真正放进去 | 先解决「花不出去」，再谈放量 |

### 4.13 「新建的 ASC 一直不起量」排查清单

```
ASC 不起量排查
│
├── 1. 信号底座：Pixel/CAPI 事件是否在正常到达？（最常见根因）
├── 2. 受众边界：是否误设了过细的手工定向/排除？
├── 3. 素材：是否只有 1-2 条且高度同质？
├── 4. 预算：是否低于 ASC 最低预算，导致模型没余量探索？
├── 5. 目标：是否优化了过稀疏的事件（如购买）？
├── 6. 合规：cong special_ad_categories 是否正确？
├── 7. 状态：campaign/adset/ad 是否真的 ACTIVE？
└── 8. 时间：是否才跑 1-2 天就下结论？（给足学习期）
```

### 4.14 为什么「照搬竞品素材」经常不赚钱

- 竞品素材是在「对方面向的人群 + 对方的数据信号」下被模型筛选出的赢家；
- 你复用素材后，模型要在你的受众/信号上重新学习，效果未必复制；
- 素材可以借鉴「结构」（利益点、节奏、构图），但必须配合你自己的信号底座与商品差异化。

### 4.15 与手动系列共存时的「自我竞争」处理

自我竞争（cannibalization）会让两个 campaign 在同一用户池上互相抬价：

```
自我竞争处理流程
│
├── 1. 识别：同一 Pixel、相似受众/素材的手动 + ASC 同时投放
├── 2. 分层：手动做精细测试/再营销，ASC 做拉新放量
├── 3. 素材错开：两侧不用完全相同素材
├── 4. 受众错开：借助归因与频控避免同人双触达
└── 5. 复盘：定期看总 ROAS，而非单 campaign
```

### 4.16 数据质量案例：CAPI 双写导致的「假 ROAS」

真实业务中常遇到「ROAS 报表很好看、实际不回本」，根因往往是 Pixel 与 CAPI 双写重复计数：

```
症状：ASC 报表 ROAS 3.5，但账本净利为负
│
├── 排查1：同一次购买是否被 Pixel 和 CAPI 各记一次？
├── 排查2：归因设置是 click 7d 还是 view 1d？
├── 排查3：CAPI 是否在 Pixel 之外额外触发了同一事件？
├── 排查4：value/currency 是否被传对？
│
└── 修复：CAPI 用 dedup 字段（如 event_id）与 Pixel 去重；
        核对 event_id 唯一性；修正 value。
```

> 这解释了为什么我们在前文反复强调「数据质量是 Advantage+ 的生命线」——一个 event_id 去重没做对，可能让整条 ASC 的决策都建立在被高估的转化上。

### 4.17 Meta 平台策略变更对 ASC 的影响

- Meta 会不定期调整 Advantage+ 的默认行为（如探索比例、最低预算、字段）。
- 应对：关注账户内「Advantage+ 更新说明」，用 API 读取真实字段状态，而不是写死假设。
- 脚本层：用 `meta_get_*` 系列读取对象当前结构，不依赖硬编码字段名。

---

## 五、自测题

<details>
<summary>题目 0（热身）：请说出 Advantage+ 家族的八个产品，并各用一句话说明其作用。</summary>

**答案：**

1. **Advantage+ Audience**：Ad Set 层自动化受众，模型在起始受众基础上自动扩展、去重。
2. **Advantage+ Creative**：创意增强/动态组合，智能裁剪、自动变体、动态文案。
3. **Advantage+ Placements**：全自动版位，模型按转化贡献实时分配。
4. **Advantage+ Shopping Campaigns (ASC)**：电商端到端自动化 campaign（受众+创意+商品+预算全交给模型）。
5. **Advantage+ App Campaigns (AAC)**：应用安装/事件优化的自动化 campaign。
6. **Advantage+ Catalog Ads**：目录/动态商品广告的自动化增强版。
7. **Advantage+ Budget**：组合预算，模型在 campaign/Ad Set 间动态分配。
8. **Advantage+ Optimizations**：自动化优化选择（终极转化、自动出价等）。

作用一句话：它们共同把「受众、创意、版位、预算、优化」交给模型，人类负责定义目标与供给资源。
</details><details>
<summary>题目 1：ASC 与 DPA 的核心区别是什么？为什么 ASC 不能细分受众？</summary>

**答案：**

1. **核心区别**：
   - DPA（动态商品广告）：用固定创意模板 + 目录商品，推给按规则（用户历史行为/再营销）圈定的人群；受众、创意、商品选择更规则化。
   - ASC（Advantage+ Shopping Campaigns）：把整个目录 + 多套素材交给模型，模型同时决定「给谁看（Advantage+ Shopping Audience）、用什么创意、推荐哪个商品、花多少预算」，是端到端联合优化。

2. **为何不能细分受众**：
   - ASC 的价值来自「让模型在广范围自主寻找高转化用户」的探索空间。细分受众 = 人为压缩搜索空间，会破坏「内容-受众联合学习」，使模型无法跨人群探索，最终退化成手动投放的效果，失去 Advantage+ 的增益。需要精确受众控制的合规/品牌场景应改用 DPA 或传统 campaign。
</details>

<details>
<summary>题目 2：数据质量（Pixel/CAPI）为何是 ASC 成败的关键？请列出至少三种「数据质量差」导致的 ASC 故障。</summary>

**答案：**

Advantage+ 的机器学习依赖转化信号底座（L1 数据层）。模型靠 Pixel/CAPI 的转化事件学习「哪个人群/哪个创意/哪个商品转化高」，如果没有可信、密集、不重复的转化信号，模型的探索-利用平衡会崩溃。

数据质量差导致的常见故障：
1. **预算花不出去 / 花出率低**：模型找不到足够「可信转化」的用户，停止投放。
2. **CPA 虚高、长期探索态**：转化信号稀疏或回传延迟，模型一直处于校准/试错。
3. **ROAS 波动剧烈**：Pixel 与 CAPI 双写重复、归因受延迟影响，模型数据被污染。
4. **学习期反复**：外部扰动的信号让系统不断重新校准。

对应用 `CAPI` 补服务端事件、核对去重与归因设置、降低操作频率即可缓解。
</details>

<details>
<summary>题目 3：为什么素材的「语义多样性」而非数量对 ASC 更重要？请给出具体的素材多样性原则。</summary>

**答案：**

ASC 的动态创意本质上做「内容-受众联合学习」，模型需要「不同的组合可能性」才能选出赢家并放大。如果素材只是数量多但语义同质（比如同一主图改几个背景色），模型没有足够不同的「学习维度」，动态组合退化成只比点击率，失去优势。

素材多样性原则：
1. 语义级差异，而非像素级：不同利益点、不同人群视角（新客/复购/高意向）、不同叙事。
2. 同时覆盖图片与视频：视频更能体现产品动态价值。
3. 每条素材的文案/标题/CTA 与目标人群匹配，形成「人-创意」配对空间。
4. 上线前一次性给足素材，避免上线后再补导致学习中断。
5. 避免「同一主视觉 + 改几行文案」的低效组合。
</details>

<details>
<summary>题目 4：ASC 学习期与放量的正确做法是什么？为什么「频繁改预算」是危险的？</summary>

**答案：**

**学习期做法**：新 ASC 通常 5-7 天学习期，期间用最近数据校准。稳定期的判定依据是「转化信号是否充足、CPA/ROAS 是否达标」，而非单纯看天数。学习期内**不频繁暂停/调整**，保持预算稳定。

**放量做法**：采用 20-30% 阶梯式加预算，每次调整后留观察窗口，走「调预算 → 学习期 → 看数据 → 再调」的闭环，避免单次跳 3 倍以上。

**为什么频繁改预算危险**：机器学习模型需要基于「稳定、连续」的数据校准。每次大幅或频繁改预算/改素材，都会让投放进入新的学习期，之前的校准被推翻；在预算极小时甚至出现「永远在试错、来不及收敛」的死循环，导致 CPA 迟迟降不下来、放不了量。
</details>

<details>
<summary>题目 5：在「多国投放、信号强弱不平衡」的情况下，如何用 Advantage+ 相关产品合理投放？</summary>

**答案：**

关键原则是「让模型在足够大的搜索空间里按转化效率分配，而不是人为按国均分预算」。

1. **信号充足且均衡**：可单 Ad Set 多国，让模型自动在各国间分配预算（Advantage+ Budget / 组合预算）。
2. **信号不平衡（A 国强、B 国弱）**：
   - 先用模型观察，不要一开始就按国分 Ad Set、均分预算；
   - 若必须控制，用「组合预算 + Cap」限制某国花满，或在模型稳定后按成绩拆 Ad Set；
   - 补足较弱市场的信号（CAPI 回传、本地化素材、本地语言文案）比简单加预算更有效。
3. **始终配合数据质量**：多国投放更要注意 Pixel/CAPI 在不同市场是否都完整埋点，避免「某国转化信号缺失被模型漏掉」。货币、时区、素材本地化也要一并处理。
</details>

---

## 附：与本文档相关的脚本方法速查

以下为 `scripts/ad_platform_api.py` 中与 Advantage+ 直接相关的方法，供复用时快速定位：

| 方法 | 用途 |
|------|------|
| `meta_create_campaign` | 创建 campaign（含 ASC/AAC objective） |
| `meta_create_adset` | 创建 Ad Set（受众交给模型/粗边界） |
| `meta_create_ad` | 创建 Ad（绑定目录 + 多素材） |
| `meta_create_audience` | 创建自定义受众（信号种子） |
| `meta_list_dynamic_ads` | 列出动态广告 |
| `meta_list_dynamic_product_sets` | 列出动态商品集 |
| `meta_query_insights` | 查询投放洞察（CPA/ROAS/CTR） |
| `meta_list_campaigns_by_account` | 按账户列出 campaign |
| `meta_list_budget_splits` | 列出预算拆分 |
| `meta_create_budget_split` | 创建预算拆分 |
| `meta_list_portfolio_budgets` | 列出组合预算 |
| `meta_create_portfolio_budget` | 创建组合预算 |
| `meta_send_capi` / `meta_send_capi_batch` | CAPI 服务端事件回传 |
| `meta_list_catalog_products` / `meta_add_products` | 目录商品管理 |
| `meta_list_placements` | 查看版位选项 |

> 说明：本文给出的是产品逻辑 + Graph API 端点 + 脚本调用方式的完整映射。实际调用时字段名与层级以 `scripts/ad_platform_api.py` 当前实现为准；若封装方法参数与文档示例有出入，以脚本源码为准，并结合 `meta_get_*` 系列方法读取真实对象结构作为参照。

---

> 本文档由知识库专家基于 Advantage+ 产品体系、Meta Marketing API Graph API v19.0 与 `scripts/ad_platform_api.py` 实战经验编写，覆盖 Advantage+ 家族全景、ASC/AAC 深层原理与完整生产流程。文中所涉产品名与 API 端点以 Meta 官方最新文档为准。
