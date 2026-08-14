# 广告平台统一数据模型设计

> **领域**: 广告投放 / 跨平台
> **深度**: ⭐⭐⭐⭐⭐ 实战级指南
> **标签**: cross-platform, data-model, etl, data-warehouse, schema-mapping
> **更新时间**: 2026-08-14
> **类型**: data/architecture

---

## 目录

- [一、核心概念与架构](#一核心概念与架构)
- [二、深度原理解析](#二深度原理解析)
- [三、生产环境实战](#三生产环境实战)
- [四、常见问题与排查](#四常见问题与排查)
- [五、自测题](#五自测题)

---

## 一、核心概念与架构

### 1.1 为什么要做"统一数据模型"

现代广告投放业务很少只投一个平台。一个典型的出海投放团队，可能同时运营 Google Ads、Meta（Facebook/Instagram）、TikTok Ads，以及通过 DV360（Display & Video 360）购买程序化展示广告资源。每个平台都有自己的 API、自己的实体命名、自己的指标口径、自己的时区和货币。如果没有一套"统一数据模型"，跨平台汇总、预算统筹、归因分析、报告输出就会变成一张巨大的"手工对账表"，几乎必然出现：

- 同一渠道在不同报表里数字对不上；
- "花费"在 Google 是美元，在 Meta 是当地货币，在 TikTok 又是另一种；
- "转化"的统计口径各平台天差地别；
- 报表团队每天花数小时做 Excel 合并，却仍然无法回答"整体 ROAS 是多少"。

**统一数据模型（Unified Data Model, UDM）** 的目标，就是把各平台 API 的原始数据，转换并落成一套**单一事实来源（Single Source of Truth, SSOT）** 的标准化结构，让下游的报表、BI、算法、归因、风控都能基于同一套口径做分析。

```
┌────────────┐   ┌────────────┐   ┌────────────┐   ┌────────────┐
│ Google Ads │   │   Meta     │   │  TikTok    │   │   DV360    │
│    API     │   │ Marketing  │   │   Ads API  │   │    API     │
└─────┬──────┘   └─────┬──────┘   └─────┬──────┘   └─────┬──────┘
      │                │                │                │
      └───────────────▶│  API Connector / ETL          │
                       ▼                                │
              ┌──────────────────┐                     │
              │     Raw Layer    │  (逐平台原样落盘)      │
              └──────────────────┘                     │
                       ▼                                │
              ┌──────────────────┐                     │
              │  Standardized    │◀── 统一数据模型       │
              │  (SSOT / ODS)    │   Campaign/AdGroup   │
              └──────────────────┘   Ad/Creative/Aud    │
                       │              ience/Conversion   │
                       ▼                                │
        ┌──────────────┴──────────────┐                 │
        ▼                             ▼                 │
  ┌──────────────┐            ┌──────────────┐          │
  │  DWD / Mart  │            │  Realtime    │          │
  │  (聚合/主题)  │            │  Stream      │          │
  └──────────────┘            └──────────────┘          │
```

### 1.2 统一模型的设计原则

设计跨平台统一数据模型时，应坚持以下原则：

1. **实体最小化（Entity Minimization）**：找出各平台真实存在的、语义等价的最小实体集合。不要为了"图省事"而把所有平台的概念强行塞进一张宽表，也不要为了"完整"而保留每个平台的专属抖动。
2. **源与统一分离（Source vs Unified）**：`raw` 层保存各平台 API 返回的**原始 JSON**（后续可追溯、可回放），`standardized` 层才是统一的 SSOT。二者通过 `platform` + `external_id` 关联。
3. **可逆映射（Bidirectional Mapping）**：统一模型必须保留映射回各平台的能力（统一 ID ↔ 平台外部 ID），否则无法与平台侧对账。
4. **口径显式化（Explicit Semantics）**：每个指标（impressions、clicks、spend、conversions）必须带元数据，说明它来自哪个平台、哪个归因窗口、哪种统计方式。
5. **枚举归一化（Enum Normalization）**：所有状态、目标、出价策略等枚举值，统一到一份字典，避免"ACTIVE / ACTIVE / ENABLED / LIVE"这种混乱。
6. **时间和货币统一**：全链路统一到 UTC + 指定报表时区，金额统一存 `micro`/`分` 加 `currency` 字段，杜绝小数误差。

### 1.3 各平台实体概念对照

四个平台的"层级/实体结构"并不完全一致，统一模型的第一步就是做概念对齐。

| 统一实体 | Google Ads | Meta | TikTok Ads | DV360 |
|---------|-----------|------|-----------|-------|
| 账户/客户 | Customer（客户 ID） | Ad Account（ad_account_id） | Advertiser（advertiser_id） | Advertiser（advertiser_id） |
| 广告系列/计划 | Campaign | Campaign | Campaign | Campaign |
| 系列分组 | CampaignGroup | — (无直接概念) | Campaign Group | Insertion Order (IO) |
| 广告组（投放单元） | Ad Group | Ad Set（adset） | Ad Group（adgroup） | Line Item (LI) |
| 广告（创意载体） | Ad（含 Ad Group Ad） | Ad | Ad | Creative（单独实体） |
| 创意素材 | Ad（含素材） | Creative（material） | Creative | Creative |
| 受众 | Audience / Audience List | Audience / Custom Audience | Audience | Audience / Audience List |
| 转化 | Conversion / Conversion Action | Event / Custom Conversion | Conversion / Optimization Event | Floodlight（活动+计数） |

> **关键点**：注意 **Meta 的 AdSet** 与 **Google 的 AdGroup** 语义并不完全等价——Meta 的 AdSet 承担了"预算、投放目标、受众"三个职能，而 Google 的 AdGroup 主要承担"关键词/定向 + 出价"职能。统一模型中，我们把"投放单元"抽象为 `ad_group`，但用属性区分其是否承载预算与受众。

#### 1.3.1 Google Ads 实体层级

```
Customer (客户)
 └── CampaignGroup (系列分组)
    └── Campaign (广告系列)
        └── AdGroup (广告组)
            ├── Ad (广告/广告变体)
            │    └── 引用 Creative (素材)
            └── Keyword / Targeting (定向)
```

#### 1.3.2 Meta 实体层级

```
Ad Account (广告账户)
 └── Campaign (广告系列)  — 携带 objective
     └── AdSet (广告组)  — 携带 budget、targeting、schedule、bidding
         └── Ad (广告)   — 携带 creative、状态
              └── Creative (素材/创意)
```

#### 1.3.3 TikTok Ads 实体层级

```
Advertiser (广告主)
 └── Campaign (广告系列) — 携带 objective
     └── AdGroup (广告组) — 携带 budget、targeting、schedule、bidding
         └── Ad (广告)   — 携带 creative 与素材
```

#### 1.3.4 DV360 实体层级

```
Advertiser (广告主)
 └── Insertion Order (插入订单/IO)
     └── Line Item (订单项/LI)
         ├── Creative (创意关联)
         └── Flight (投放档期)
```

#### 1.3.5 对应关系速记表

| 业务功能 | Google Ads | Meta | TikTok | DV360 |
|---------|-----------|------|--------|-------|
| 客户/账户 | Customer | Ad Account | Advertiser | Advertiser |
| 最高层投放容器 | Campaign | Campaign | Campaign | Insertion Order |
| 预算/受众/计划承载 | — | AdSet | AdGroup | Line Item + Flight |
| 定向+出价单元 | AdGroup | AdSet | AdGroup | Line Item |
| 具体展示素材 | Ad | Ad | Ad | Creative |
| 转化口径 | Conversion Action | Event / Custom Conv | Optimization Event | Floodlight |

### 1.4 统一实体的核心标识（ID 策略）

统一数据模型里，每一条记录都需要一个**全局稳定主键**。标准做法是 `平台 + 平台实体ID + 时间/版本` 的组合：

```
统一主键规则：
  {platform}:{entity_type}:{external_id}

示例：
  google:campaign:8456_1234567890
  meta:campaign:2384790348
  tiktok:adgroup:179832367
  dv360:line_item:320915

快照/版本化主键：
  {platform}:{entity_type}:{external_id}@{snapshot_date}
```

> 这里额外引入一层"统一内部 ID"（自增或 UUID，如 `dim_campaign_id`），用于跨表外键关联与血缘，同时保留 `platform_external_id` 用于回写平台与对账。

#### 1.4.1 统一 ID 生成的伪代码

```python
import hashlib

def unified_id(platform: str, external_id: str) -> str:
    raw = f"{platform}:{external_id}"
    # 短哈希保留可读性 + 唯一性
    h = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]
    return f"{platform}_{h}"

assert unified_id("google", "8456-12345678") == "google_3b9f8c1d2e44aa11"
```

#### 1.4.2 为什么不能只用平台外部 ID

- 平台外部 ID 格式随平台变化（Google 是长整数，Meta 是整数，DV360 是长整数），类型不统一；
- 外部 ID 可能被平台回收复用（极少数情况删除后重建）；
- 关联其他系统（如归因、CRM）时需要一段稳定、与平台解耦的标识；
- 统一内部数字/哈希 ID 便于建索引、做分区键。

### 1.5 统一数据模型的总体分层（Medallion 视角）

虽然 Medallion 架构我们会在第五节详解，这里先给出统一模型在整个数仓中的位置：

```
                       ┌───────────────────────────────┐
                       │   Bronze / Raw (原始层)         │
                       │   逐平台 API JSON，原样落盘       │
                       └───────────────┬───────────────┘
                                       │ 标准化解析 + 映射
                       ┌───────────────▼───────────────┐
                       │ Silver / Standardized (ODS)   │
                       │ 统一 schema：campaign/ad_group  │
                       │ /ad/creative/audience/conv     │
                       └───────────────┬───────────────┘
                                       │ 清洗、去重、SCD
                       ┌───────────────▼───────────────┐
                       │ Gold / Mart (主题/集市)         │
                       │ 日粒度/小时粒度指标、口径表、      │
                       │ 统一报表、ROAS、归因结果          │
                       └───────────────┬───────────────┘
                                       ▼
                              BI / 算法 / 归因 / 风控
```

### 1.6 统一模型的价值量化示例

为帮助理解统一模型的投资回报，这里给出一个"报表口径归一"前后的对比场景：

```
场景：某出海客户同时投放 4 平台，日均花费合计约 $50,000。

统一前：
 - 4 个平台各出一份报表（不同货币/时区/口径/字段名）
 - 分析师每天 2-3 小时手工合并 Excel
 - 跨平台 ROAS 无法直接回答，需二次加工
 - 出价优化逻辑各自为政，无法统一决策

统一后：
 - 每天 04:00 UTC 自动拉取，02 小时完成全量标准化
 - SSOT 供报表/BI/归因/风控共用一套口径
 - 跨平台 ROAS 一条 SQL 即得
 - 出价/预算分配算法基于统一模型做全局最优
```

这一节奠定了后续所有内容的基础。下一节将深入剖析统一实体模型、字段映射、数据类型标准化与转化的设计。

## 二、深度原理解析

### 2.1 统一实体模型：六大核心实体

统一数据模型围绕六个核心实体展开：

1. **Campaign（广告系列）** — 最高层投放容器（Google/Meta/TikTok 的 Campaign，DV360 的 IO 归入 Campaign 或单独 CampaignGroup 概念）。
2. **AdGroup（广告组/投放单元）** — 承载预算、受众、定向、出价的层级（Google AdGroup、Meta AdSet、TikTok AdGroup、DV360 Line Item）。
3. **Ad（广告）** — 平台上的"广告条目"，引用创意与归属的广告组。
4. **Creative（创意/素材）** — 实际展示给用户的内容素材（图片、视频、文案、落地页等）。
5. **Audience（受众）** — 定向人群与种子人群。
6. **Conversion（转化）** — 用户完成的目标动作（购买、注册、加购等）。

外加两个支撑性实体：

- **PlatformAccount（平台账户）** — 维表，标识平台账户/客户。
- **Metric（指标）** — 每实体的每日/小时粒度的统计指标快照。

#### 2.1.1 实体关系概览（ER 图简化）

```
 ┌──────────────┐ 1        N ┌──────────────┐ 1        N ┌──────────────┐
 │ PlatformAccount│──────────│   Campaign   │──────────│   AdGroup    │
 └──────────────┘            └──────────────┘          └──────────────┘
                                 1                         1       │
                                 │                         │       │
                                 │ 1                      N │       │ N
                                 ▼                         ▼       ▼
                        ┌──────────────┐           ┌──────────────┐ ┌────────────┐
                        │   Audience   │◀─────────│      Ad      │ │  Metric    │
                        └──────────────┘           └──────────────┘ └────────────┘
                                                          │ 1
                                                          │
                                                          ▼ N
                                                     ┌──────────────┐
                                                     │   Creative   │
                                                     └──────────────┘

  Campaign ──1:N── AdGroup ──1:N── Ad ──N:1── Creative
  Campaign ──N:M── Audience (通过定向关系表)
  AdGroup  ──1:N── Metric (日/小时粒度的指标)
  (Conversion 关联 Ad / AdGroup / 归因窗口，见 2.7)
```

#### 2.1.2 完整的 ER 图

```text
                          ┌──────────────────────────────┐
                          │      platform_account        │
                          │  pk: platform_account_id     │
                          │      platform                │
                          │      external_account_id     │
                          │      account_name            │
                          │      currency                │
                          │      timezone                │
                          └───────────────┬──────────────┘
                                          │ 1
                                          │ N
                     ┌────────────────────▼────────────────────┐
                     │                 campaign                 │
                     │  pk: dim_campaign_id                     │
                     │      platform                            │
                     │      platform_external_id                │
                     │      account_id (FK)                     │
                     │      campaign_name                       │
                     │      objective (归一化)                   │
                     │      status (归一化)                      │
                     │      currency / timezone                 │
                     └───────┬──────────────────┬──────────────┘
                             │ 1                │ 1
                             │ N                │ N
              ┌──────────────▼─────┐   ┌────────▼──────────────┐
              │      ad_group      │   │       audience        │
              │  pk: dim_adgroup_id│   │  pk: dim_audience_id  │
              │      campaign_id   │   │      audience_name    │
              │      budget        │   │      audience_type    │
              │      bid_strategy  │   │      platform_ref     │
              └──────┬─────────┬───┘   └────────▲──────────────┘
                     │ 1       │ 1              │
                     │ N       │ N              │ (M:N 定向关系)
              ┌──────▼───┐ ┌───▼────────┐ ┌─────┴──────────┐
              │   ad     │ │   metric   │ │ adgroup_audience│
              └──────┬───┘ └────────────┘ └────────────────┘
                     │ 1
                     │ N
              ┌──────▼──────────────┐
              │     creative        │
              └─────────────────────┘

          conversion (转化)：独立事实，关联 campaign/ad_group/ad + 归因属性
```

### 2.2 统一 schema 设计（核心 DDL）

下面给出统一层（Silver / Standardized）每张核心表的 DDL。示例采用 PostgreSQL/BigQuery 兼容写法。

#### 2.2.1 `dim_platform_account` — 平台账户维表

```sql
CREATE TABLE IF NOT EXISTS dim_platform_account (
    dim_account_id      BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    platform            STRING      NOT NULL,              -- google / meta / tiktok / dv360
    external_account_id STRING      NOT NULL,              -- 平台外部账户ID
    account_name        STRING      NOT NULL,
    -- 账户级默认货币与时区（可被 campaign 覆盖）
    default_currency    STRING      NOT NULL,              -- ISO 4217: USD / EUR / CNY ...
    default_timezone    STRING      NOT NULL,              -- IANA: Asia/Shanghai ...
    account_status      STRING      NOT NULL,              -- 归一化 status
    -- 审计字段
    ingested_at         TIMESTAMP   NOT NULL,              -- 入库时间(UTC)
    updated_at          TIMESTAMP   NOT NULL,
    UNIQUE (platform, external_account_id)
);
```

#### 2.2.2 `dim_campaign` — 统一广告系列维表

```sql
CREATE TABLE IF NOT EXISTS dim_campaign (
    dim_campaign_id      BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    -- 关联
    dim_account_id       BIGINT     NOT NULL REFERENCES dim_platform_account(dim_account_id),
    platform             STRING     NOT NULL,
    platform_external_id STRING     NOT NULL,              -- 平台 Campaign ID
    campaign_name        STRING     NOT NULL,
    campaign_group_id    STRING,                           -- Google CampaignGroup / DV360 IO / TikTok CampaignGroup
    -- 目标（归一化枚举，见 2.5.3）
    objective            STRING     NOT NULL,              -- app_install / website_conversion ...
    -- 出价策略（归一化，见 2.5.4）
    bid_strategy         STRING,                           -- maximize_conversions / tcpa ...
    -- 预算（micro + 货币，见 2.6.2 金额标准化）
    budget_micro         INT64      NOT NULL DEFAULT 0,    -- 预算金额(微单位)
    budget_currency      STRING     NOT NULL,              -- budget_micro 所属货币
    -- 状态（归一化字典，见 2.5.2）
    status               STRING     NOT NULL,              -- ACTIVE / PAUSED / ARCHIVED ...
    -- 时间与时区
    start_date           DATE,                             -- 投放开始(账户时区)
    end_date             DATE,                             -- 投放结束
    timezone             STRING     NOT NULL,              -- 该系列报表会计时区
    currency             STRING     NOT NULL,              -- 该系列报表货币
    -- 审计
    valid_from           TIMESTAMP  NOT NULL,              -- SCD 生效起始
    valid_to             TIMESTAMP,                        -- SCD 生效结束(NULL=当前)
    is_current           BOOL       NOT NULL DEFAULT TRUE, -- SCD 当前版本
    ingested_at          TIMESTAMP  NOT NULL,
    UNIQUE (platform, platform_external_id, valid_from)
);
```

#### 2.2.3 `dim_ad_group` — 统一广告组/投放单元维表

```sql
CREATE TABLE IF NOT EXISTS dim_ad_group (
    dim_ad_group_id      BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    dim_campaign_id      BIGINT     NOT NULL REFERENCES dim_campaign(dim_campaign_id),
    platform             STRING     NOT NULL,
    platform_external_id STRING     NOT NULL,
    ad_group_name        STRING     NOT NULL,
    -- 层级语义：来自哪个平台概念（Meta adset / Google adgroup / DV360 line_item）
    source_level         STRING     NOT NULL,    -- adgroup / adset / line_item
    -- 预算（Meta adset 与 TikTok adgroup 在此承载预算）
    budget_micro         INT64      NOT NULL DEFAULT 0,
    budget_currency      STRING,
    bid_amount_micro     INT64,                  -- 出价金额(micro)，若有
    bid_strategy         STRING,                 -- 出价策略归一化
    -- 目标（adset 级目标，覆盖 campaign 目标时优先）
    objective            STRING,
    -- 状态
    status               STRING     NOT NULL,
    start_date           DATE,
    end_date             DATE,
    valid_from           TIMESTAMP  NOT NULL,
    valid_to             TIMESTAMP,
    is_current           BOOL       NOT NULL DEFAULT TRUE,
    ingested_at          TIMESTAMP  NOT NULL,
    UNIQUE (platform, platform_external_id, valid_from)
);
```

#### 2.2.4 `dim_ad` — 统一广告实体表

```sql
CREATE TABLE IF NOT EXISTS dim_ad (
    dim_ad_id            BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    dim_ad_group_id      BIGINT     NOT NULL REFERENCES dim_ad_group(dim_ad_group_id),
    platform             STRING     NOT NULL,
    platform_external_id STRING     NOT NULL,
    ad_name              STRING     NOT NULL,
    status               STRING     NOT NULL,
    -- 展示状态（审核相关，各平台含义不同）
    serving_status       STRING,                 -- 归一化: SERVING / LEARNING / PAUSED ...
    approval_status      STRING,                 -- 归一化: APPROVED / REJECTED / PENDING
    policy_violations    JSON,                   -- 平台策略违规详情(原始)
    -- 指向创意
    primary_creative_id  STRING,                 -- 平台 creative 外部 ID
    -- 落地页/标题等简要（详情入 creative/json）
    landing_page         STRING,
    valid_from           TIMESTAMP  NOT NULL,
    valid_to             TIMESTAMP,
    is_current           BOOL       NOT NULL DEFAULT TRUE,
    ingested_at          TIMESTAMP  NOT NULL,
    UNIQUE (platform, platform_external_id, valid_from)
);
```

#### 2.2.5 `dim_creative` — 统一创意/素材表

```sql
CREATE TABLE IF NOT EXISTS dim_creative (
    dim_creative_id   BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    platform          STRING     NOT NULL,
    platform_external_id STRING  NOT NULL,
    creative_name     STRING,
    creative_type     STRING,                  -- image / video / carousel / native / html5 ...
    -- 素材 URL 与描述
    asset_urls        JSON,                     -- ["https://...jpg", ...]
    headline          STRING,
    primary_text      STRING,
    call_to_action    STRING,                   -- 归一化 CTA
    duration_ms       INT64,                    -- 视频时长(如有)
    dimensions        JSON,                     -- {"width":1080,"height":1920}
    thumbnail_url     STRING,
    -- 版本
    version           INT64      NOT NULL DEFAULT 1,
    is_current        BOOL       NOT NULL DEFAULT TRUE,
    valid_from        TIMESTAMP  NOT NULL,
    valid_to          TIMESTAMP,
    ingested_at       TIMESTAMP  NOT NULL,
    UNIQUE (platform, platform_external_id, version)
);
```

#### 2.2.6 `dim_audience` — 统一受众维表

```sql
CREATE TABLE IF NOT EXISTS dim_audience (
    dim_audience_id    BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    platform           STRING     NOT NULL,
    platform_external_id STRING   NOT NULL,
    audience_name      STRING     NOT NULL,
    -- 受众类型（归一化，见 2.5.5）
    audience_type      STRING     NOT NULL,    -- lookalike / custom / retargeting / interest ...
    -- 规模（平台提供的预估触达）
    estimated_size     INT64,
    -- 定向规则（原始 JSON 保留）
    targeting_json     JSON,
    status             STRING     NOT NULL,
    valid_from         TIMESTAMP  NOT NULL,
    valid_to           TIMESTAMP,
    is_current         BOOL       NOT NULL DEFAULT TRUE,
    ingested_at        TIMESTAMP  NOT NULL,
    UNIQUE (platform, platform_external_id, valid_from)
);
```

#### 2.2.7 `fact_adgroup_audience` — 广告组×受众多对多关系

```sql
CREATE TABLE IF NOT EXISTS fact_adgroup_audience (
    dim_ad_group_id   BIGINT NOT NULL REFERENCES dim_ad_group(dim_ad_group_id),
    dim_audience_id   BIGINT NOT NULL REFERENCES dim_audience(dim_audience_id),
    platform          STRING NOT NULL,
    relation_type     STRING NOT NULL,          -- include / exclude
    effective_from    TIMESTAMP NOT NULL,
    effective_to      TIMESTAMP,
    ingested_at       TIMESTAMP NOT NULL,
    PRIMARY KEY (dim_ad_group_id, dim_audience_id, relation_type, effective_from)
);
```

#### 2.2.8 `fact_metric_daily` — 日粒度指标事实表

```sql
CREATE TABLE IF NOT EXISTS fact_metric_daily (
    metric_id          BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    platform           STRING      NOT NULL,
    dim_campaign_id    BIGINT      REFERENCES dim_campaign(dim_campaign_id),
    dim_ad_group_id    BIGINT      REFERENCES dim_ad_group(dim_ad_group_id),
    dim_ad_id          BIGINT      REFERENCES dim_ad(dim_ad_id),
    -- 会计日期：以统一报表时区归一化后的日期
    report_date        DATE        NOT NULL,
    -- 展示/点击/花费（金额统一 micro + currency）
    impressions        INT64       NOT NULL DEFAULT 0,
    clicks             INT64       NOT NULL DEFAULT 0,
    spend_micro        INT64       NOT NULL DEFAULT 0,       -- 花费(微单位)
    currency           STRING      NOT NULL,
    -- 转化（平台统计口径，归因属性另存）
    conversions        INT64       NOT NULL DEFAULT 0,
    conversion_value_micro INT64   NOT NULL DEFAULT 0,
    view_through_conversions INT64 NOT NULL DEFAULT 0,
    -- 质量指标（在 mart 层计算，此处存平台原始值备核对）
    ctr                NUMERIC,    -- 平台原始 CTR (保留足够精度)
    cpm_micro          NUMERIC,    -- 千次展示成本(micro)
    cpc_micro          NUMERIC,    -- 单次点击成本(micro)
    -- 数据来源/校验
    source_reference   STRING,     -- 指向 raw 层血缘的 reference
    is_complete        BOOL      NOT NULL DEFAULT FALSE,      -- 是否已回填稳定
    ingested_at        TIMESTAMP NOT NULL,
    updated_at         TIMESTAMP NOT NULL,
    UNIQUE (platform, dim_campaign_id, dim_ad_group_id, dim_ad_id, report_date)
);
```

#### 2.2.9 `fact_conversion` — 统一转化事实表

转化是最复杂、最需要元数据表意的实体，单独成节（见 2.7）。这里给出骨架 DDL：

```sql
CREATE TABLE IF NOT EXISTS fact_conversion (
    conversion_id      BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    platform           STRING      NOT NULL,      -- 转化上报来源平台
    event_time         TIMESTAMP   NOT NULL,      -- 事件发生时间(UTC)
    report_date        DATE        NOT NULL,      -- 归一到报表时区后的日期
    -- 归因关联（可为空，回填归因）
    dim_campaign_id    BIGINT      REFERENCES dim_campaign(dim_campaign_id),
    dim_ad_group_id    BIGINT      REFERENCES dim_ad_group(dim_ad_group_id),
    dim_ad_id          BIGINT      REFERENCES dim_ad(dim_ad_id),
    -- 事件与目标（归一化）
    result_action      STRING      NOT NULL,      -- purchase / add_to_cart / sign_up ...
    conversion_action_name STRING,
    -- 平台转化口径归属
    attribution_window INT64,                     -- 归因窗口(天)
    attributed_by      STRING,                    -- click / view / none
    attribution_type   STRING,                    -- last_click / data_driven ...
    -- 价值与货币
    value_micro        INT64,                     -- 转化价值(micro)
    value_currency     STRING,
    order_id           STRING,                    -- 电商订单号(若可对应)
    -- 幂等去重（见 3.2.4）
    dedup_key          STRING      NOT NULL,
    ingested_at        TIMESTAMP   NOT NULL,
    UNIQUE (dedup_key)
);
```

> **设计取舍**：`fact_metric_daily` 的行粒度采用 "哪个维度组合活跃就哪些列非空"（如只有 campaign 级指标则 ad_group/ad 列为 NULL）。生产上更倾向拆成 campaign/ad_group/ad 三级指标宽表以保证行密度，此处为演示保留一张表。

#### 2.2.10 补充 E-R 关系的关联键说明

为方便理解，这里给出各表的关联键速查：

| 表 | 主键 | 外键/关联键 | 关联目标 |
|----|------|------------|---------|
| dim_platform_account | dim_account_id | platform + external_account_id | (唯一) |
| dim_campaign | dim_campaign_id | dim_account_id | dim_platform_account |
| dim_ad_group | dim_ad_group_id | dim_campaign_id | dim_campaign |
| dim_ad | dim_ad_id | dim_ad_group_id | dim_ad_group |
| dim_creative | dim_creative_id | (platform + external_id + version) | (唯一) |
| dim_audience | dim_audience_id | (platform + external_id) | (唯一) |
| fact_adgroup_audience | (adgroup,audience,type,from) | 两个 dim | dim_ad_group/dim_audience |
| fact_metric_daily | metric_id | 三个 dim | campaign/adgroup/ad |
| fact_conversion | conversion_id | dedup_key 唯一 | campaign/adgroup/ad |

### 2.3 统一 schema 的 JSON 表示

除了 DDL，统一模型也常以 JSON Schema 落地，用于校验 API 连接器输出、驱动报表框架、生成可视化表单。一个 `campaign` 的 JSON Schema 示例：

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "campaign",
  "type": "object",
  "required": ["platform", "external_id", "name", "status", "objective"],
  "properties": {
    "platform": { "type": "string", "enum": ["google", "meta", "tiktok", "dv360"] },
    "external_id": { "type": "string" },
    "name": { "type": "string", "minLength": 1 },
    "status": {
      "type": "string",
      "enum": ["ACTIVE", "PAUSED", "ARCHIVED", "DELETED", "UNKNOWN"]
    },
    "objective": {
      "type": "string",
      "enum": [
        "unset", "app_install", "app_engagement", "website_conversion",
        "website_traffic", "brand_awareness", "video_views", "lead_generation",
        "sales", "reach", "traffic", "awareness"
      ]
    },
    "bid_strategy": {
      "type": "string",
      "enum": [
        "unset", "maximize_clicks", "maximize_conversions", "maximize_conversion_value",
        "target_cpa", "target_roas", "target_impression_share", "cost_per_view",
        "manual_cpc", "optimized_cpm", "lowest_cost_without_cap"
      ]
    },
    "budget": {
      "type": "object",
      "properties": {
        "micro": { "type": "integer" },
        "currency": { "type": "string", "pattern": "^[A-Z]{3}$" }
      },
      "required": ["micro", "currency"]
    },
    "dates": {
      "type": "object",
      "properties": {
        "start": { "type": "string", "format": "date" },
        "end": { "type": ["string", "null"], "format": "date" }
      }
    },
    "timezone": { "type": "string" },
    "currency": { "type": "string", "pattern": "^[A-Z]{3}$" },
    "created_at": { "type": "string", "format": "date-time" },
    "updated_at": { "type": "string", "format": "date-time" }
  }
}
```

### 2.4 各平台字段映射表

这一节做"逐字段映射矩阵"。我们按业务语义分组，从 Campaign / AdGroup / Ad / Metric / Status / 出价 / 目标 等维度展开。

#### 2.4.1 Campaign 字段映射

| 统一字段 | Google Ads | Meta | TikTok Ads | DV360 | 备注 |
|---------|-----------|------|-----------|-------|------|
| campaign id | customer_id + `campaign.id` | `campaign_id` | `campaign_id` | `campaign.id` / IO id | 统一层存平台外部 ID |
| name | `campaign.name` | `campaign.name` | `campaign.name` | `campaign.name` | 一致 |
| status | `campaign.status`(enum: ENABLED/PAUSED/REMOVED) | `campaign.status`(ACTIVE/PAUSED/ARCHIVED/DELETED) | `operation_status`(ACTIVE/DISABLE...) | `campaign.status`(ACTIVE/PAUSED/ARCHIVED) | 需归一化 |
| objective | `campaign.campaign_goal` / `campaign_goal` | `campaign.objective`(APP_INSTALLS, ...) | `campaign.objective` | 无直接目标，用 Line Item | 归一化为统一字典 |
| budget | `campaign_budget.amount_micros` | `campaign.lifetime_budget` / `daily_budget` | `campaign.budget` | `insertion_order.budget` | Meta 预算在 adset/campaign 均可 |
| start/end | `campaign.start_date/end_date` | `campaign.start_time/stop_time` | `campaign.start_time` | `insertion_order.start_date/end_date` | 需时区转换 |
| currency | 账户级 | 账户级 | 账户级 | 账户级 | 见 2.6.2 |
| timezone | 账户级默认 | 账户级 | 账户级 | 账户级 | 见 2.6.1 |

#### 2.4.2 AdGroup（投放单元）字段映射

| 统一字段 | Google AdGroup | Meta AdSet | TikTok AdGroup | DV360 Line Item |
|---------|---------------|-----------|----------------|-----------------|
| id | `ad_group.id` | `adset_id` | `adgroup_id` | `line_item.id` |
| name | `ad_group.name` | `adset.name` | `adgroup.name` | `line_item.name` |
| status | ENABLED/PAUSED/REMOVED | ACTIVE/PAUSED/ARCHIVED | ACTIVE/DISABLE | ACTIVE/PAUSED/ARCHIVED |
| budget | 继承 campaign | `adset.lifetime_budget/daily_budget` | `adgroup.budget` | `line_item.budget` |
| bid_amount | `ad_group.cpc_bid_micros` | `adset.bid_amount` | `adgroup.bid_price` | `line_item.bid_strategy`(CPM/CPC/... 底价) |
| bid_strategy | `ad_group.bidding_strategy` | `adset.bid_strategy` | `adgroup.bid_type` | `line_item.bid_strategy` |
| targeting | 通过网/关键词 | `adset.targeting` | `adgroup.targeting` | `line_item.targeting`(audience/inventory) |
| schedule | – | `adset.start_time/end_time` | – | `line_item.flight` |

#### 2.4.3 Ad / Creative 字段映射

| 统一字段 | Google Ads | Meta | TikTok | DV360 |
|---------|-----------|------|--------|-------|
| ad id | `ad_group_ad.ad.id` | `ad_id` | `ad_id` | `creative_id` |
| creative type | `ad.type`(RESPONSIVE, IMAGE...) | `creative.object_story_spec` | `ad.creatives` | `creative`(banner/video/native) |
| headline | `ad.headline`(responsively) | `creative.title` | `ad.title` | `creative.headline` |
| description | `ad.description` | `creative.body` | `ad.description` | `creative.description` |
| image/video | `ad.assets`(youtube/媒体) | `creative.image_hash/video_id` | `ad.creative`(素材) | `creative.media`(hosted/external) |
| call_to_action | `ad.call_to_action` | `creative.call_to_action` | `ad.call_to_action` | `creative.cta` |

#### 2.4.4 核心指标映射

| 统一指标 | Google Ads | Meta | TikTok Ads | DV360 |
|---------|-----------|------|-----------|-------|
| impressions | `metrics.impressions` | `impressions` | `impressions` | `metrics.impressions` |
| clicks | `metrics.clicks` | `clicks` | `clicks` | `metrics.clicks` |
| spend 花费 | `metrics.cost_micros` | `spend` | `spend` | `metrics.total_cost_micros` / media cost |
| conversions | `metrics.conversions` | `conversions` | `conversions` / `result` | `metrics.activations` |
| conversion_value | `metrics.conversions_value` | `purchase_value` | `complete_payment_value` | `metrics.activations_value` |
| CTR | 计算 | 计算 | 计算 | 计算 |
| CPM | 计算 | `cpm` | `cpm` | 计算 |
| CPC | 计算 | `cpc` | `cpc` | 计算 |
| ROAS | 计算 | `omni_purchase_roas` | `roas` | 计算 |

> **口径差异关键点**：
> - Google `cost_micros` 单位是**微元**（1 元 = 1e6 微元），Meta/TikTok 的 `spend` 单位是**当地货币最小单位/元**（按 API 参数而定，通常是分）。
> - "转化"口径差异巨大：Google 有「跨设备/跨窗口/数据驱动」归因，Meta 有「7 天点击 + 1 天浏览」默认窗口，TikTok 有「优化事件 vs 统计事件」之分，DV360 用 Floodlight 活动计数。
> - DV360 的 `total_cost_micros` 通常包含 media cost + data fee + platform fee，需要单独拆出净媒体成本用于 ROAS 与出价计算。

#### 2.4.5 指标级差异明细（Meta 与 Google 归因窗口对照）

| 平台 | 默认归因窗口 | 可配置 | 术语 |
|-----|------------|--------|------|
| Google Ads | 点击后 30 天；浏览后 1 天（可配置到 14-90 天） | 是 | conversion window |
| Meta | 点击后 7 天 + 浏览后 1 天（可分活动配置） | 是 | attribution window |
| TikTok | 点击后 6/7 天；浏览后 7 天不等 | 是 | attribution window |
| DV360/Floodlight | 点击后 30 天；浏览后 10 天（可配置） | 是 | attribution window |

这张表说明：**统一模型的转化口径必须带 `attribution_window` 与 `attributed_by` 元数据**，否则跨平台加总毫无意义。

#### 2.4.6 完整逐字段映射矩阵（一页总览）

为便于 ETL 开发与 review，下面给出一张"逐字段映射矩阵"总表（示例为 Campaign 实体的关键字段到四个平台 API 字段）：

| 统一字段 | 类型 | Google Ads 字段 | Meta 字段 | TikTok 字段 | DV360 字段 | 转换/校验 |
|---------|------|----------------|-----------|-------------|-----------|----------|
| external_id | string | campaign.resource_name 解析 id | campaign_id | campaign_id | campaign.id | 数字转字符串 |
| name | string | campaign.name | campaign.name | campaign.name | campaign.name | 去首尾空白 |
| status | enum | campaign.status | campaign.status | operation_status | campaign.status | 归一化字典 |
| objective | enum | campaign.campaign_goal | campaign.objective | campaign.objective | io(na) | 归一化字典; vs 校验 |
| budget_micro | int | campaign_budget.amount_micros | campaign.lifetime_budget*1e6 | campaign.budget*1e6 | io.budget.budget_amount_micros | micro 化, +currency |
| daily_budget | int | campaign_budget.daily_spend_limit | adset.daily_budget | adgroup.daily_budget | li.daily_budget | 可选 |
| start_date | date | campaign.start_date | campaign.start_time | campaign.start_time | io.start_date | 时区归日 |
| end_date | date | campaign.end_date | campaign.stop_time | campaign.stop_time | io.end_date | 时区归日 |
| currency | enum | 账户默认 | 账户默认 | 账户默认 | 账户默认 | ISO 4217 |
| timezone | string | 账户时区 | 账户时区 | 账户时区 | 账户时区 | IANA |
| created_at | timestamp | campaign.create_time | campaign.created_time | campaign.create_time | io.create_time | →UTC |
| updated_at | timestamp | campaign.update_time | campaign.updated_time | campaign.update_time | io.update_time | →UTC |

### 2.5 枚举归一化字典

这是统一模型最琐碎也最容易出错的部分。我们建立一套"统一字典"，并把各平台枚举值映射进来。

#### 2.5.1 统一 status 字典

| 统一 status | 含义 | Google | Meta | TikTok | DV360 |
|------------|------|--------|------|--------|-------|
| ACTIVE | 投放中/启用 | ENABLED | ACTIVE | ACTIVE | ACTIVE |
| PAUSED | 暂停 | PAUSED | PAUSED | DISABLE / PAUSED | PAUSED |
| ARCHIVED | 归档/删除 | REMOVED | ARCHIVED | DELETED | ARCHIVED |
| UNKNOWN | 未知/其他 | UNKNOWN / OTHER | UNKNOWN / OTHER | UNKNOWN | N/A |
| DRAFT | 草稿（未提交） | – | DRAFT | – | – |

#### 2.5.2 统一 objective（目标）字典

| 统一 objective | 中文 | Google | Meta | TikTok | DV360 |
|------------|-----|--------|------|--------|-------|
| app_install | 应用安装 | APP_INSTALL | APP_INSTALLS | INSTALL_APP | (N/A) |
| website_conversion | 网站转化 | CONVERSIONS | CONVERSIONS / WEBSITE_PURCHASES | CONVERSIONS | (N/A) |
| lead_generation | 线索收集 | LEAD_GENERATION | LEAD_GENERATION | LEAD_GENERATION | (N/A) |
| website_traffic | 网站流量 | TRAFFIC | TRAFFIC / WEBSITE_TRAFFIC | TRAFFIC | (N/A) |
| brand_awareness | 品牌认知 | BRAND_AWARENESS | BRAND_AWARENESS | BRAND_AWARENESS | REACH / BRAND |
| video_views | 视频观看 | VIDEO_VIEWS | VIDEO_VIEWS | VIDEO_VIEWS | (N/A) |
| app_engagement | 应用互动 | – | APP_INTERACTION | APP_ENGAGEMENT | (N/A) |
| sales | 销售（电商） | (无独立) | SALES(文档目标) | LIVE_SHOPPING / PRODUCT_SALES | TRACKING |
| reach | 触达 | (无) | REACH | REACH | REACH |
| awareness | 认知 | (无) | AWARENESS | VIDEO_VIEWS | AWARENESS |
| unset | 未设置 | – | – | – | (io/li 无目标) |

#### 2.5.3 统一 bid_strategy（出价策略）字典

| 统一出价策略 | 中文 | Google | Meta | TikTok |
|------------|-----|--------|------|--------|
| maximize_conversions | 最大化转化 | MAXIMIZE_CONVERSIONS | LOWEST_COST_WITHOUT_CAP / MAXIMIZE_RESULTS | MAXIMIZE_CONVERSIONS |
| maximize_conversion_value | 最大化转化价值 | MAXIMIZE_CONVERSION_VALUE | HIGHEST_VALUE_WITHOUT_CAP | MAXIMIZE_VALUE |
| maximize_clicks | 最大化点击 | MAXIMIZE_CLICKS | – | MAXIMIZE_CLICKS |
| target_cpa | 目标每次转化成本 | TARGET_CPA | COST_CAP / TARGET_COST | TARGET_CPA |
| target_roas | 目标广告支出回报 | TARGET_ROAS | VALUE_OPTIMIZED (ROAS) | TARGET_ROAS |
| manual_cpc | 手动每次点击出价 | MANUAL_CPC / CPC | – | MANUAL_CPC |
| manual_cpm | 手动千次展示 | MANUAL_CPM / CPM | – | MANUAL_CPM |
| target_impression_share | 目标展示份额 | TARGET_IMPRESSION_SHARE | – | – |
| optimized_cpm | 优化千次展示 | – | OCPM / OMPM | OCPM |
| cost_per_view | 每次观看出价 | VCPM / CPV | – | CPV / VCPV |
| unset | 未设置 | – | – | – |

> DV360 的出价不进入这套 objective 策略字典，而是按 `bid_strategy_type`：`BID_STRATEGY_TYPE_CPM` / `CPC` / `CPA` / `FLAT_CPM` 等，这里单独做映射。

**DV360 出价策略单独映射**：

| 统一出价类型（DV360） | DV360 bid_strategy_type | 说明 |
|---------------------|------------------------|------|
| cpm | CPM / FLAT_CPM | 按展示付费（固定 CPM） |
| cpc | CPC | 按点击付费 |
| cpa | CPA | 按转化（目标 CPA） |
| viewable_cpm | VIEWABLE_CPM | 可视展示 |
| guaranteed | FIXED_CPM | 程序化保量 |

#### 2.5.4 统一 audience_type（受众类型）字典

| 统一类型 | 中文 | Google | Meta | TikTok | DV360 |
|---------|-----|--------|------|--------|-------|
| custom | 自定义受众（规则） | CUSTOM_AUDIENCE | CUSTOM_AUDIENCE | CUSTOM_AUDIENCE | CUSTOM_AUDIENCE |
| lookalike | 相似受众 | LOOKALIKE | LOOKALIKE | LOOKALIKE / 类似受众 | LOOKALIKE |
| retargeting | 再营销 | REMARKETING_LIST | CUSTOM(retarget)/(page/website) | RETARGETING | REMARKETING |
| interest | 兴趣 | AFFINITY / IN_MARKET | INTEREST | INTEREST | INTEREST |
| demographic | 人口统计 | DEMOGRAPHIC | AGE / GENDER | GENDER / AGE | DEMOGRAPHIC |
| saved | 已保存受众 | – | SAVED_AUDIENCE | – | – |
| combined | 组合受众 | COMBINED_AUDIENCE | – | – | – |
| unknown | 未知 | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN |

#### 2.5.5 统一 result_action（转化动作）字典

| 统一 result_action | 中文 | Google | Meta | TikTok | DV360(Floodlight) |
|-----------|-----|--------|------|--------|---------------------|
| purchase | 购买 | PURCHASE | PURCHASE | COMPLETE_PAYMENT | sale / transaction |
| add_to_cart | 加购 | ADD_TO_CART | ADD_TO_CART | ADD_TO_CART | cart |
| initiate_checkout | 发起结账 | BEGIN_CHECKOUT | INITIATE_CHECKOUT | INITIATE_CHECKOUT | checkout |
| sign_up | 注册 | SIGNUP | COMPLETE_REGISTRATION | REGISTRATION | signup / registration |
| lead | 线索 | LEAD | LEAD | FORM_SUBMISSION | lead |
| page_view | 页面浏览 | PAGE_VIEW | VIEW_CONTENT | CONTENT_VIEW | pageview |
| search | 搜索 | SEARCH | SEARCH | SEARCH | search |
| app_install | 应用安装 | INSTALL | INSTALL | INSTALL_APP | appinstall |
| other | 其他 | OTHER | OTHER | OTHER | other |

#### 2.5.6 枚举字典落地为维表

比散落在代码里更好的是把统一枚举当成"维表"（lookup table）管理，供约束校验、血缘、报表标签统一使用：

```sql
CREATE TABLE IF NOT EXISTS dict_status (
    status_code       STRING PRIMARY KEY,   -- ACTIVE / PAUSED / ARCHIVED ...
    status_label      STRING NOT NULL,      -- 中文/展示名
    cluster           STRING NOT NULL,      -- active/inactive/archived 语义簇
    description       STRING
);
INSERT INTO dict_status VALUES
  ('ACTIVE','投放中','active','正在投放'),
  ('PAUSED','暂停','inactive','已暂停'),
  ('ARCHIVED','已归档','archived','已归档/删除'),
  ('UNKNOWN','未知','unknown','平台返回未知值'),
  ('DRAFT','草稿','inactive','草稿未提交');
```

```sql
CREATE TABLE IF NOT EXISTS dict_objective (
    objective_code    STRING PRIMARY KEY,   -- app_install / website_conversion ...
    objective_label   STRING NOT NULL,
    family            STRING NOT NULL,      -- acquisition / engagement / brand ...
    description       STRING
);
INSERT INTO dict_objective VALUES
  ('app_install','应用安装','acquisition','推广 app 安装'),
  ('website_conversion','网站转化','acquisition','推动网站转化'),
  ('lead_generation','线索收集','acquisition','收集销售线索'),
  ('website_traffic','网站流量','traffic','引流到站'),
  ('video_views','视频观看','engagement','视频观看目标'),
  ('brand_awareness','品牌认知','brand','提升品牌认知'),
  ('reach','触达','brand','最大化触达人数'),
  ('awareness','认知','brand','认知类目标'),
  ('sales','销售','acquisition','电商销售'),
  ('unset','未设置','other','未设置目标');
```

### 2.6 数据类型标准化

跨平台数据的最大坑在于"同名的字段类型不同、单位不同、时区不同、空值不同"。

#### 2.6.1 时间戳标准化

**原则**：存储统一用 `TIMESTAMP`（带时区，落地 always UTC），展示层按 `timezone` 字段换算；所有"会计日期"（报表归属日）按统一报表时区归一化。

各平台返回时间格式：

| 平台 | 时间格式 | 示例 | 时区 |
|-----|---------|------|------|
| Google Ads | ISO-8601 或 `YYYY-MM-DD` | `2026-08-14T10:00:00Z` | 多为 UTC / 账户时区 |
| Meta | 毫秒时间戳或 ISO | `1755182400` | UTC（API 默认） |
| TikTok | 秒时间戳 / ISO | `1755182400` | UTC |
| DV360 | ISO-8601 / epoch | `2026-08-14T10:00:00+08:00` | 可带偏移 |

**统一规则**：
```sql
-- 存储统一为 UTC：
event_time_utc TIMESTAMP NOT NULL -- 由源解析、带偏移的转成 UTC

-- 会计日期：按报表时区归日
report_date DATE NOT NULL
-- 示例查询：把 UTC 时间转换到账户时区再取 DATE
SELECT DATE(TIMESTAMP(event_time_utc), 'Asia/Shanghai') AS report_date_sh
```

**时区转换示例（Python）**：
```python
from datetime import datetime, timezone
import zoneinfo

def to_utc(ts, tz="UTC"):
    if isinstance(ts, (int, float)):
        # epoch 秒
        return datetime.fromtimestamp(ts, tz=timezone.utc)
    # ISO 字符串
    return datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone(timezone.utc)

def to_account_date(utc_dt, tz="America/New_York"):
    return utc_dt.astimezone(zoneinfo.ZoneInfo(tz)).date()
```

**推导：时区换算公式**（统一日切点约定）

1. 所有事件先转 UTC 存储；
2. 报表日 = `DATE(event_utc AT TIME ZONE 'account_timezone')`；
3. 约定"日切点"为账户时区 00:00（也可配置为凌晨点，如 04:00 为日切，满足特殊结算需求）；
4. 任何跨平台的"今日/昨日"比较都基于统一时区，避免各平台日切不同步。

**必须规避的错误**：
- 把带 `+08:00` 的时间当成 UTC 直接存；
- 混用 epoch 秒与毫秒；
- 报表日按 UTC 计算导致与中国/美东时区"半夜事件归错日"；
- 各平台对"日切点"定义不同（Meta 可按广告账户时区日切，DV360 可按日区分割线不同）。

#### 2.6.2 金额标准化（分/micro + 货币）

**核心问题**：浮动金额在 SQL/JSON 中提到会遇到精度损失与实际差异。标准做法是**用最小整数单位（micro 或 分）+ currency 字段**存储，展示与计算时才除以换算系数。

**货币单位对照**：

| 金额 | 单位 | 说明 | 换算 |
|-----|------|------|------|
| USD 元 | 元（美元） | 人类可读 | 1e6 micro |
| USD micros | 微美元 | Google `cost_micros` | 1 美元 = 1,000,000 micro |
| CNY 元 | 元（人民币） | | 1 元 = 100 分 |
| 分 | 最小本币单位 | Meta/TikTok 默认 `spend` 单位（可由参数控制） | 1 元 = 100 分 |

**统一存储建议**：金额一律存 `*_micro`（64 位整数，即 1e-6 精度）或 `*_cents`，并加 `currency`。为归一化，推荐统一到 micro：

```python
def to_micro(value, unit="micro"):
    """把各平台金额统一转 micro。"""
    if unit == "micro":
        return int(value)
    if unit == "cents":     # 分 → micro
        return int(round(value * 1_000_000 / 100))
    if unit == "unit":      # 元 → micro（按货币小数位）
        return int(round(value * 1_000_000))
    raise ValueError(f"unknown unit: {unit}")
```

**比率/派生指标的精度**（CTR/CVR/ROAS）建议统一用 `NUMERIC(18, 10)` 或 `BIGINT` 分子分母，避免浮点误差：

```sql
-- mart 层派生指标：保留分子分母，方便按需重算
SELECT
    report_date,
    impressions,
    clicks,
    ROUND(clicks * 100.0 / NULLIF(impressions, 0), 4) AS ctr_pct,   -- CTR 保留 4 位百分比
    ROUND(spend_micro / 1e6 / NULLIF(conversions, 0), 6) AS cpa,     -- 单次转化成本
    ROUND(conversion_value_micro * 1.0 / NULLIF(spend_micro, 0), 6) AS roas
FROM fact_metric_daily
WHERE report_date = '2026-08-14';
```

#### 2.6.3 比率精度约定

| 指标 | 存储类型 | 精度约定 | 示例 |
|-----|---------|---------|------|
| CTR | NUMERIC(18,8) | 保留 8 位小数，展示 2-4 位百分比 | 0.01234567 → 1.23% |
| CVR | NUMERIC(18,8) | 同上 | 0.0345 → 3.45% |
| ROAS | NUMERIC(18,8) | 倍数，保留 6-8 位 | 3.512346 |
| CPM/CPC | NUMERIC(18,8)（micro 或元） | 金额再加 micro | 12.345678 元 |
| 预算消耗率 | NUMERIC(18,8) | 0-1 | 0 满 |

> 不要用 `FLOAT`/`DOUBLE` 存金额与精确比率。SQL 中统一用 `NUMERIC`/`DECIMAL`。

#### 2.6.4 null / 缺失值处理

**三类缺失**要区分：

1. **平台本身不提供该字段**（例如 DV360 Line Item 无 objective）→ 存 `NULL`，并在元数据里标记 `not_applicable`，**不能**用 0 填充，否则会被误当成真实 0 参与统计。
2. **平台提供但当前无值**（如无消耗的 campaign 的 `spend`）→ 归为 0 或 NULL 视业务而定；建议指标缺失统一填 0 便于加总，但需在血缘标注。
3. **拉取失败/尚未拉取** → 必须与"真 0"区分，用 `is_complete=false` 或 NULL + 状态标记，防止"昨天没拉到数据"被当成"昨天花费 0"。

**缺失处理策略表**：

| 类型 | 处理 | 示例 |
|------|------|------|
| 不适用（N/A） | 存 NULL + 元数据 not_applicable | DV360 objective |
| 平台无值 | 指标填 0；属性填 NULL | 新 campaign 的 spend=0 |
| 拉取失败 | 标记 is_complete=false，重试/告警 | 数据缺口检测 |
| 除零 | 用 NULLIF 避免，输出 NULL | CTR 当 impressions=0 |

```sql
-- 安全的比率计算（防止除零与浮点）
ROUND(clicks::numeric * 100 / NULLIF(impressions, 0), 4) AS ctr_pct
```

#### 2.6.5 通用转换异常处理清单

统一连接器在解析时应对以下常见"非标准值"做防御：

| 场景 | 处理 |
|------|------|
| 负数花费 | 拒绝或标记，触发告警（属于异常口径） |
| 空字符串 vs NULL | 空串→NULL，统一按缺失处理 |
| 超大金额（溢出） | 校验上限，超限告警 |
| 非法货币代码 | 拒绝或映射到 UNKNOWN |
| 非法时区 | 拒绝或回退账户默认时区 |
| 日期跨界（9999） | 视为"无截止"，存 NULL + 元数据 |

### 2.7 转化实体的深入设计（Conversion）

转化是统一模型里最需要"解释"的实体，因为它高度依赖平台归因口径。设计上把转化拆成两层：

1. **平台口径转化（Platform Attribution）**：平台自己上报的、按平台归因窗口统计的转化（报表可见的 `conversions`）。用于与平台对账。
2. **自有归因转化（第一方归因）**：通过 Pixel/CAPI/服务端上报到自己数据仓的事件，用自己的归因引擎（last-click / data-driven）归因到广告。用于业务财务核算。

两张表（或两个 partition）分别建模，避免混用。

```
                        ┌─────────────────────────────┐
   平台报表转化            │  fact_metric_daily         │ ← 平台 statistics 拉取
   (Platform stats)       │  conversions / value       │
                        └─────────────────────────────┘
   第一方事件              ┌─────────────────────────────┐
   (First-party events)   │  fact_conversion            │ ← Pixel/CAPI/Webhook 上报
                          │  event_time / value / dedup │
                          └──────────────┬──────────────┘
                                         │ 归因引擎(自有)回填
                          ┌──────────────▼──────────────┐
                          │  fact_attribution           │
                          │  dim_ad * conversions 映射   │
                          └─────────────────────────────┘
```

**转化统一字典与口径表**，由于口径差异，建议单独维护一张 `dim_attribution_policy` 或直接在每个转化上带 `attribution_window / attributed_by / attribution_type` 元数据。

**平台转化口径元数据字段说明**：

| 字段 | 含义 | 示例 |
|------|------|------|
| attribution_window | 归因窗口（天） | 30 |
| attributed_by | 归因来源 | click / view / none |
| attribution_type | 归因方式 | last_click / data_driven / position_based |
| conversion_action_name | 转化动作名 | "Purchase" |
| result_action | 归一化动作 | purchase |

### 2.8 血缘（Lineage）设计

统一模型要求可追溯：任何一张报表数字都能回答"来自哪个平台、哪次拉取、哪条 raw JSON"。血缘分两层：

- **逻辑血缘**：原始 API 字段 → 标准化字段 → 报表字段的映射关系（文档化）。
- **物理血缘**：raw 表行 JSON → silver 表行 → gold 表聚合 的具体实例关系，通常通过 `source_reference`、batch_id、拉取 job 元数据关联。

统一模型里每张业务表都建议带：

```sql
-- 血缘/审计通用列
source_reference   STRING,   -- 指向 raw 层 (platform, batch_id, row_hash)
batch_id           STRING,   -- 本次拉取批次
job_run_id         STRING,   -- ETL job 运行实例
ingested_at        TIMESTAMP,-- 入库时间
updated_at         TIMESTAMP,-- 最后更新
```

血缘目录表：

```sql
CREATE TABLE IF NOT EXISTS lineage_catalog (
    entity_name      STRING NOT NULL,   -- dim_campaign / fact_metric_daily ...
    source_platform  STRING NOT NULL,
    source_field     STRING NOT NULL,   -- API 原始字段
    target_field     STRING NOT NULL,   -- 统一字段
    transform_rule   STRING,            -- 转换说明/函数
    owner            STRING,
    updated_at       TIMESTAMP NOT NULL
);
```

**血缘演进 / 审计辅助**：raw 层采用 JSON 保留+追加式写入，配合 `batch_id` 支持"重放"与"回退"，这是数据事故恢复与口径审计的底牌。

### 2.9 语义一致性：口径版本化（Semantic Versioning）

指标口径会因为平台 API 变更、归因窗口调整、货币结算变化而变化，统一模型必须支持"口径版本"：

```sql
CREATE TABLE IF NOT EXISTS metric_definition (
    metric_code      STRING NOT NULL,       -- conversions / spend / roas
    metric_version   STRING NOT NULL,       -- v1 / v2
    definition       STRING NOT NULL,
    formula          STRING,                -- SQL 表达式
    effective_from   DATE NOT NULL,
    effective_to     DATE,
    PRIMARY KEY (metric_code, metric_version, effective_from)
);
```

每次口径变更走"新增版本"，历史数据保留旧版本计算，避免历史断裂。报表框架通过 `metric_version` 决定取哪种口径。

### 2.10 归一化为何不是"简单翻译"

一个常见误区是：把统一模型当成"各平台字段的字典翻译"。实际上，归一化必须同时处理三类问题的叠加：

1. **命名差异**（impressions vs impressions，同义但字段名不同）——需要映射表；
2. **口径差异**（同一字段在不同平台含义不同，如 conversions 的归因窗口不同）——需要元数据与口径版本；
3. **结构差异**（Meta 把预算放 adset，Google 放 campaign；DV360 用 IO 而非 campaign）——需要实体抽象与层级映射。

只有三者在统一 schema 中同时解决，才算真正的"统一"，而不是简单的"合并列名"。这也是为什么我们保留 `source_level`、`attribution_window`、`metric_version` 等"语义元数据"字段——它们承担了跨平台解释差异的职责。

## 三、生产环境实战

### 3.1 统一数据的落地流程总览

```
平台 SDK → 连接器(拉取) → Raw(原样 JSON) → 解析/校验 → Silver(统一 schema)
      → 清洗/去重/SCD → Gold(Mart) → 报表/API/归因
```

本节围绕 **ETL 管道设计**（第 4 点要求）、**实时 vs 离线**（第 5 点要求）展开，给出生产级落地细节。

### 3.2 ETL 管道设计：从平台 API 到统一数仓

#### 3.2.1 整体架构

```
                     ┌──────────────────────────────────────────┐
                     │           调度层 (Airflow / Prefect)       │
                     │  提取器 → 标准化器 → 校验器 → 装载器 + 血缘   │
                     └──────────────────────────────────────────┘
  ┌────────┐   拉取    ┌───────────┐   JSON   ┌────────────┐
  │ Google │━━━━━━━━━▶│ Raw Layer │━━━━━━━━▶│  Silver/ODS │
  │  API   │           │  (Object Storage / BQ)   │ Standardized │
  └────────┘           └───────────┘           └────────────┘
  │ Meta  │──────────────────▶─────▶─────────────────────────▶
  │TikTok │──────────────────▶─────▶─────────────────────────▶
  │ DV360 │──────────────────▶─────▶─────────────────────────▶
                                                     │
                                                     ▼
                                               ┌────────────┐
                                               │ Gold / Mart│
                                               └────────────┘
```

#### 3.2.2 增/全量拉取策略

各平台 API 对"增量"的支持不同，生产上通常用以下模式：

| 平台 | 支持增量 | 常用方式 |
|-----|---------|---------|
| Google Ads | 是（GAQL + 日期/点击时间过滤） | 按 `segments.date` 拉取日粒度 |
| Meta | 部分（stats 按日期区间；实体按 updated_since） | 按 `date_preset` 或起止日期 |
| TikTok | 是 | 按 `stat_time_day` 区间 |
| DV360 | 是 | 报表按 `date` 分区（可 T+1） |

**策略一：按日期分区增量（最常见）**

```python
# 增量拉取：只拉昨天（T-1），或定期回填历史缺口
def fetch_daily_stats(platform, report_date):
    # 1. 检查该日是否已拉取且完整
    if is_complete(platform, report_date):
        return
    # 2. 调用平台 statistics API
    rows = platform.fetch_stats(
        start_date=report_date, end_date=report_date,
        level="adgroup", timezone="account"
    )
    # 3. 结构化并写 raw
    write_raw(platform, report_date, rows)
    # 4. 标记该日数据状态
    mark_date(platform, report_date, status="fetched")
```

日期分区的核心是维护一张 **拉取状态表（partition watermark / completeness）**：

```sql
CREATE TABLE IF NOT EXISTS ingestion_watermark (
    platform      STRING NOT NULL,     -- google/meta/tiktok/dv360
    data_level    STRING NOT NULL,     -- campaign/adgroup/ad/stats/conversion
    report_date   DATE   NOT NULL,     -- 数据日
    status        STRING NOT NULL,     -- pending/fetching/complete/failed/partial
    retry_count   INT64  NOT NULL DEFAULT 0,
    first_fail_at TIMESTAMP,
    completed_at  TIMESTAMP,
    PRIMARY KEY (platform, data_level, report_date)
);
```

**策略二：游标/分页（实体级增量，如创建/更新）**

```python
def fetch_entities(platform, cursor=None, updated_since=None):
    params = {"page_size": 500, "page_token": cursor}
    while True:
        resp = platform.get_entities(params)
        for item in resp["data"]:
            yield normalize_entity(platform, item)
        cursor = resp.get("next_page_token")
        if not cursor:
            break
```

**策略三：差量合并（用于变更流/Webhook）**，见第五节实时部分。

#### 3.2.3 分页处理

各平台分页机制：

| 平台 | 分页字段 | 说明 |
|-----|---------|------|
| Google Ads | GAQL + `page_token`/`page_size` | 游标分页 |
| Meta | `after` cursor | 游标分页，`limit` 上限 |
| TikTok | `page` + `page_size` | 页码分页 |
| DV360 | 报表导出（SDF/API 分片） | 大报表分片下载 |

分页通用要点：
- 循环拉取直到 `next_page_token` 为空；
- 对 `page_size` 过大导致的 4xx/限流降级；
- 记录 `total_records / fetched_records` 用于完整性校验。

**通用分页实现**：

```python
def paginated_get(client, endpoint, params, token_key="page_token",
                  data_key="data", limit=200):
    """通用游标分页封装。"""
    page_token = None
    all_items = []
    while True:
        p = dict(params)
        p["limit"] = limit
        if page_token:
            p[token_key] = page_token
        resp = client.get(endpoint, params=p)
        items = resp.get(data_key, [])
        all_items.extend(items)
        page_token = resp.get("next_page_token") or resp.get("next_page") \
                     or resp.get("paging", {}).get("cursors", {}).get("after")
        if not page_token or not items:
            break
    return all_items
```

#### 3.2.4 幂等键与去重（Idempotency Key）

**为什么需要**：平台 API 可能重复返回、连接器可能重试、同一个 job 可能因为失败而重跑。要保证"同一逻辑业务记录只落一份"，必须为每个事实/实体定义**幂等键**。

**通用幂等键设计**：

| 表 | 幂等键（unique key） |
|----|---------------------|
| dim_* 维表 | (platform, external_id, valid_from) → 维度存在性 upsert |
| fact_metric_daily | (platform, report_date, dim_campaign_id, dim_ad_group_id, dim_ad_id) |
| fact_conversion | (dedup_key) |
| ingestion_watermark | (platform, data_level, report_date) |

**转换去重键生成（转化）**：

```python
import hashlib

def conversion_dedup_key(platform, event_time, event_id, order_id=None):
    """优先级：平台 event_id > order_id+event_time > 哈希。"""
    if event_id:
        return f"{platform}:{event_id}"
    base = f"{platform}:{event_time}:{order_id}"
    return hashlib.sha1(base.encode()).hexdigest()
```

**upsert 幂等写入（BigQuery MERGE）**：

```sql
MERGE INTO fact_metric_daily t
USING (SELECT * FROM raw_metric WHERE report_date = @date) s
ON  t.platform = s.platform
AND t.report_date = s.report_date
AND t.dim_campaign_id = s.dim_campaign_id
AND t.dim_ad_group_id = s.dim_ad_group_id
AND t.dim_ad_id = s.dim_ad_id
WHEN MATCHED THEN UPDATE SET
    impressions = s.impressions, clicks = s.clicks,
    spend_micro = s.spend_micro, updated_at = CURRENT_TIMESTAMP()
WHEN NOT MATCHED THEN INSERT (...);
```

> 注意：**日粒度指标会被平台在 T+2/T+3 回填修订**（延迟转化、抽样修正）。因此指标表不能只写一次，而要在每次拉取时以"覆盖当天"方式重写/upsert，并记录 `updated_at`。建议保留"平台原始 T 拉取值"与"修订后值"分层。

**幂等写入的三种实现方式对比**：

| 方式 | 适用 | 优点 | 缺点 |
|------|------|------|------|
| INSERT OR IGNORE | 去重键冲突丢弃 | 简单、快 | 无法回填修订值 |
| MERGE / UPSERT | 以键覆盖更新 | 支持修订回填 | 成本略高 |
| 全量重写分区 | 小数据量/按日分区 | 最彻底一致 | 大数据量昂贵 |

#### 3.2.5 Schema 演进（Schema Evolution）

平台 API 会新增字段、改枚举、废弃字段。统一模型要能平滑演进：

1. **Raw 层用 JSON/SEMI-STRUCTURED 存储**：所有平台字段原样保留，新增字段无需改 DDL。BigQuery 用 `JSON`，PG 用 `JSONB`。
2. **Silver 层用向后兼容的 ADD COLUMN**：约定只加列、不改/删已有列，旧字段保留。
3. **版本化接口字段名**：统一模型内部字段稳定，平台新字段映射到扩展 `ext_*` 或 JSON。
4. **枚举字典支持新增**：新增平台枚举先"落 UNKNOWN"，再细化映射。
5. **迁移策略**：小表重建、大表 `ADD COLUMN` + `ALTER`；分区表按分区迁移。

**Schema 变更防呆清单**：
- 绝不 drop 已有列；
- 变更后跑一致性校验（新旧 schema 对账）；
- 变更记录进 `schema_change_log`。

```sql
CREATE TABLE IF NOT EXISTS schema_change_log (
    change_id     INT64 GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    changed_at    TIMESTAMP NOT NULL,
    entity_name   STRING NOT NULL,
    change_type   STRING NOT NULL,   -- add_column / rename / redefine
    before_schema JSON,
    after_schema  JSON,
    author        STRING
);
```

#### 3.2.6 缓慢变化维度（SCD）

维表（campaign/adgroup/ad 的名称、状态、预算）会随时间变化。统一模型推荐 **SCD Type 2** 记录历史版本 + **Type 1** 更新当前属性 的混合策略：

- 业务关键且需回溯历史的属性（状态、预算、名称）→ SCD2（保留 valid_from/valid_to/is_current）；
- 仅当前有效的属性（如审计时间）→ SCD1 覆盖。

```
时间线示例（campaign #123 改名/改预算）：
  v1: valid_from=2026-08-01, valid_to=2026-08-10, budget=1000, name="Summer A", is_current=false
  v2: valid_from=2026-08-11, valid_to=NULL,       budget=2000, name="Summer A v2", is_current=true
```

**SCD2 实现（识别变化 + 关闭旧版 + 开新版）**：

```python
def upsert_sq2(current_row, new_values, key_fields, tracked_fields):
    changed = any(new_values[f] != current_row[f] for f in tracked_fields)
    if not changed:
        return  # 无变化，仅 SCD1 更新审计字段
    close_old(current_row)          # valid_to = now, is_current=false
    insert_new(new_values)          # valid_from=now, valid_to=NULL, is_current=true
```

**SQL 关闭旧版本**：

```sql
UPDATE dim_campaign
SET valid_to = CURRENT_TIMESTAMP(), is_current = FALSE
WHERE platform = 'google' AND platform_external_id = '8456-123'
  AND is_current = TRUE;

INSERT INTO dim_campaign (platform, platform_external_id, campaign_name, status, ...)
VALUES ('google', '8456-123', 'Summer A v2', 'PAUSED', ...);
```

> SCD2 与事实表关联时：事实表应该按"业务发生日"关联当时有效的维度版本（`effective_date BETWEEN valid_from AND valid_to`），这样才能回溯历史口径。

**SCD2 查询历史口径示例**：

```sql
SELECT
    f.report_date,
    c.campaign_name,
    c.budget_micro
FROM fact_metric_daily f
JOIN dim_campaign c
  ON c.dim_campaign_id = f.dim_campaign_id
 AND f.report_date BETWEEN DATE(c.valid_from) AND COALESCE(DATE(c.valid_to), '9999-12-31')
WHERE f.platform = 'google' AND f.report_date = '2026-08-14';
```

#### 3.2.7 数据质量校验（Data Quality Checks）

统一模型必须内置多层校验，防止"脏数据进、脏数据出"。

**校验层级**：

1. **结构校验**：是否符合统一 JSON Schema（字段、类型、枚举、必填）。
2. **完整性校验**：拉取行数 vs 平台返回总数；missing dates 检测。
3. **口径校验**：`impressions >= 0`、`spend >= 0`、`ctr 在 (0,1)`、`clicks <= impressions`。
4. **一致性校验**：同实体、同时段的汇总与平台侧对账（delta 阈值）。
5. **单调性/合理性校验**：跨天突变告警（spend 突增 10x）。

**质量规则表（以 SQL 存储规则，供校验框架执行）**：

```sql
CREATE TABLE IF NOT EXISTS dq_rules (
    rule_id        INT64 GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    entity_name    STRING NOT NULL,
    rule_name      STRING NOT NULL,
    severity       STRING NOT NULL DEFAULT 'warn',  -- error/warn/info
    check_sql      STRING NOT NULL,                 -- 返回违反的行
    enabled        BOOL   NOT NULL DEFAULT TRUE,
    last_run_at    TIMESTAMP,
    fail_count     INT64
);
```

**使用 Python 校验框架（Great Expectations 风格单测）**：

```python
# dq_checks.py
def validate_metric_bounds(df):
    errors = []
    if (df["impressions"] < 0).any():
        errors.append("negative impressions found")
    if (df["clicks"] > df["impressions"]).any():
        errors.append("clicks > impressions")
    if (df["spend_micro"] < 0).any():
        errors.append("negative spend")
    # 平台对账：gold 汇总 vs 平台 API 汇总
    gap = abs(df["spend_micro"].sum() - platform_total_micro)
    if gap / max(platform_total_micro, 1) > 0.02:   # 2% 阈值
        errors.append(f"spend reconciliation gap {gap}")
    return errors
```

**缺失日期检测 SQL**（黄金指标：数据缺口）:

```sql
-- 找出缺拉取、未完整的日期
SELECT platform, report_date
FROM (
    SELECT platform, report_date, status
    FROM ingestion_watermark
    WHERE DATE(report_date) >= DATE_SUB(CURRENT_DATE(), INTERVAL 7 DAY)
) w
WHERE w.status <> 'complete'
ORDER BY platform, report_date;
```

**对账 SQL（平台侧 vs 统一层）**：

```sql
SELECT
    report_date,
    SUM(impressions) AS our_impressions,
    SUM(clicks)      AS our_clicks,
    SUM(spend_micro) AS our_spend_micro
FROM fact_metric_daily
WHERE report_date = '2026-08-14' AND platform = 'meta'
GROUP BY report_date
-- 与 Meta API 返回的 stats 逐日对账，差异超阈值告警
```

#### 3.2.8 血缘跟踪落地

血缘不只是一个文档，更要通过 `raw → silver → gold` 的字段级引用在数据目录（如 DataHub/OpenMetadata/自定义 catalog）体现。实现要点：

```python
# lineage_writer.py —— 每次 job 完成后写入血缘
record_lineage(
    upstream      = {"table": "raw_meta_stats", "field": "spend"},
    downstream    = {"table": "fact_metric_daily", "field": "spend_micro"},
    transform     = "to_micro(spend, unit='cents')",
    job_run_id    = job_run_id,
)
```

**血缘回溯查询**（某报表字段来源）：

```sql
SELECT source_platform, source_field, transform_rule
FROM lineage_catalog
WHERE entity_name = 'fact_metric_daily' AND target_field = 'spend_micro';
```

**血缘 + 可观测性闭环**：建议把血缘 catalog、DQ 规则、调度日志、指标对账结果四者打通，构成"数据可观测性"（data observability）的闭环——任何报表数字异常都能顺血缘找到源头的异常。

### 3.3 ETL 实际代码示例（Airflow + Python + SQL)

#### 3.3.1 Airflow DAG：每日广告数据同步

```python
# dags/ad_sync_dag.py
from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.providers.google.cloud.operators.bigquery import BigQueryInsertJobOperator

default_args = {"retries": 3, "retry_delay": timedelta(minutes=5)}

with DAG(
    dag_id="ad_platform_daily_sync",
    schedule_interval="0 4 * * *",      # 每天 04:00 UTC
    start_date=datetime(2026, 8, 1),
    catchup=False,
    default_args=default_args,
) as dag:

    def yesterday():
        return (datetime.now() - timedelta(days=1)).date()

    fetch_meta = PythonOperator(
        task_id="fetch_meta_stats",
        python_callable=lambda **_: fetch_daily_stats("meta", yesterday()),
    )
    fetch_google = PythonOperator(
        task_id="fetch_google_stats",
        python_callable=lambda **_: fetch_daily_stats("google", yesterday()),
    )
    fetch_tiktok = PythonOperator(
        task_id="fetch_tiktok_stats",
        python_callable=lambda **_: fetch_daily_stats("tiktok", yesterday()),
    )
    fetch_dv360 = PythonOperator(
        task_id="fetch_dv360_stats",
        python_callable=lambda **_: fetch_daily_stats("dv360", yesterday()),
    )

    standardize = PythonOperator(
        task_id="standardize_to_silver",
        python_callable=lambda **_: standardize_daily(yesterday()),
    )

    validate = PythonOperator(
        task_id="dq_validate",
        python_callable=lambda **_: run_dq_checks(yesterday()),
    )

    load_mart = BigQueryInsertJobOperator(
        task_id="load_mart",
        configuration={
            "query": {
                "query": MART_MERGE_SQL,
                "useLegacySql": False,
            }
        },
    )

    # DAG 依赖
    [fetch_meta, fetch_google, fetch_tiktok, fetch_dv360] >> standardize
    standardize >> validate >> load_mart
```

#### 3.3.2 标准化转换函数（Python）

```python
# normalizers.py
def normalize_status(platform, raw_status):
    """把各平台 status 映射为统一枚举。"""
    mapping = {
        "google": {
            "ENABLED": "ACTIVE", "PAUSED": "PAUSED", "REMOVED": "ARCHIVED",
            "UNKNOWN": "UNKNOWN",
        },
        "meta": {
            "ACTIVE": "ACTIVE", "PAUSED": "PAUSED",
            "ARCHIVED": "ARCHIVED", "DELETED": "ARCHIVED",
            "IN_PROCESS": "UNKNOWN", "WITH_ISSUES": "UNKNOWN",
        },
        "tiktok": {
            "ACTIVE": "ACTIVE", "DISABLE": "PAUSED", "DELETE": "ARCHIVED",
            "PAUSED": "PAUSED",
        },
        "dv360": {
            "ACTIVE": "ACTIVE", "PAUSED": "PAUSED", "ARCHIVED": "ARCHIVED",
            "DELETED": "ARCHIVED",
        },
    }
    return mapping.get(platform, {}).get(raw_status, "UNKNOWN")


def normalize_objective(platform, raw):
    """平台 objective → 统一 objective。"""
    m = {
        "meta": {
            "APP_INSTALLS": "app_install",
            "CONVERSIONS": "website_conversion",
            "WEBSITE_PURCHASES": "website_conversion",
            "LOGO_PURCHASES": "website_conversion",
            "LEAD_GENERATION": "lead_generation",
            "WEBSITE_TRAFFIC": "website_traffic",
            "BRAND_AWARENESS": "brand_awareness",
            "REACH": "reach",
            "VIDEO_VIEWS": "video_views",
            "APP_INTERACTION": "app_engagement",
            "SALES": "sales",
        },
        "google": {
            "APP_INSTALL": "app_install",
            "CONVERSIONS": "website_conversion",
            "LEAD_GENERATION": "lead_generation",
            "TRAFFIC": "website_traffic",
            "BRAND_AWARENESS": "brand_awareness",
            "VIDEO_VIEWS": "video_views",
        },
    }
    return m.get(platform, {}).get(raw, "unset")
```

#### 3.3.3 指标行处理（标准化）

```python
# metric_row.py

def to_micro(value, unit="micro"):
    if unit == "micro":
        return int(value)
    if unit == "cents":
        return int(round(value * 1_000_000 / 100))
    if unit == "unit":
        return int(round(value * 1_000_000))
    raise ValueError(f"unknown unit: {unit}")


def spend_unit(platform):
    """各平台 spend 单位换算。"""
    return {"google": "micro", "meta": "cents", "tiktok": "cents",
            "dv360": "micro"}[platform]


def to_metric_row(platform, raw, report_date):
    row = {
        "platform": platform,
        "report_date": report_date,
        "impressions": int(raw.get("impressions", 0)),
        "clicks": int(raw.get("clicks", 0)),
        "spend_micro": to_micro(raw.get("spend", 0), unit=spend_unit(platform)),
        "currency": raw.get("currency", "USD"),
        "conversions": int(raw.get("conversions", 0)),
        "conversion_value_micro": to_micro(raw.get("conversion_value", 0),
                                           unit=spend_unit(platform)),
    }
    return row
```

#### 3.3.4 平台适配器接口

为便于扩展新平台，统一模型用"适配器"抽象每个平台连接器：

```python
# platform/base.py —— 抽象基类
from abc import ABC, abstractmethod

class PlatformAdapter(ABC):
    @abstractmethod
    def fetch_campaigns(self, **kwargs): ...
    @abstractmethod
    def fetch_adgroups(self, **kwargs): ...
    @abstractmethod
    def fetch_stats(self, date, level, tz): ...
    @abstractmethod
    def map_status(self, raw) -> str: ...
    @abstractmethod
    def map_objective(self, raw) -> str: ...
    @abstractmethod
    def to_metric_rows(self, raw) -> list: ...


# platform/meta.py
class MetaAdapter(PlatformAdapter):
    def fetch_stats(self, date, level="adgroup", tz="account"):
        params = {
            "level": level, "date_preset": "custom",
            "time_range": {"since": str(date), "until": str(date)},
            "time_increment": 1, "timezone": tz,
        }
        return calls_graph_api("act_xxx/insights", params)

    def to_metric_rows(self, raw):
        return [to_metric_row("meta", r, raw["date"]) for r in raw["data"]]


adapters = {"google": GoogleAdapter(), "meta": MetaAdapter(),
            "tiktok": TikTokAdapter(), "dv360": DV360Adapter()}
```

这种"适配器 + 归一化映射"让新增平台（如 Snap / Pinterest / Amazon Ads）只写一个适配器即可接入统一模型。

#### 3.3.5 Gold 层 / Mart 例子（统一日报）

```sql
-- mart_campaign_daily.sql —— 生成统一日报（跨平台）
SELECT
    p.platform,
    c.dim_campaign_id,
    c.campaign_name,
    f.report_date,
    SUM(f.impressions)                      AS impressions,
    SUM(f.clicks)                           AS clicks,
    ROUND(SUM(f.clicks) * 100.0 / NULLIF(SUM(f.impressions), 0), 4) AS ctr_pct,
    ROUND(SUM(f.spend_micro) / 1e6, 2)      AS spend,
    SUM(f.conversions)                      AS conversions,
    ROUND(SUM(f.conversion_value_micro) * 1.0
          / NULLIF(SUM(f.spend_micro), 0), 6) AS roas
FROM fact_metric_daily f
JOIN dim_campaign c USING (dim_campaign_id)
JOIN dim_platform_account p ON p.dim_account_id = c.dim_account_id
WHERE f.report_date >= DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY)
GROUP BY 1, 2, 3, 4
ORDER BY 4 DESC, spend DESC;
```

### 3.4 实时 vs 离线数据处理策略

#### 3.4.1 两类处理的定位

| 维度 | 离线批量（T+1） | 实时流（近实时） |
|------|---------------|----------------|
| 数据源 | 平台报表 API（statistics） | Webhook / Pixel / CAPI / 事件流 |
| 延迟 | 小时~天 | 秒~分钟 |
| 用途 | 报表、对账、归因回溯、预算回顾 | 实时出价、实时告警、风控、个性化 |
| 一致性 | 最终一致，可回填修订 | 尽力一致，需幂等与去重 |
| 保证 | 平台最终口径 | 事件流（at-least-once） |

**典型分工**：
- 平台把"指标报表"做成批量 T+1（因为平台自身归因要几小时~几天才稳定）；
- 自己的第一方事件（曝光/点击/转化，通过 Pixel/CAPI/Webhook）做成实时流，驱动实时出价（RTA）、实时频控、实时反作弊、实时告警。

#### 3.4.2 实时事件流架构

```
 用户行为(Pixel/CAPI/Webhook)
        │
        ▼
   ┌──────────┐   首级    ┌────────┐
   │ Edge/Pixel│ ────────▶ │Event Hub│ (Kafka topic: ad.events)
   └──────────┘            └────────┘
                                │ 消费
                          ┌─────▼─────┐
                          │ Flink     │ 实时聚合/过滤/富化
                          │ (Streaming)│
                          └─────┬─────┘
                                ├─────────▶ 实时告警/风控(秒级)
                                ├─────────▶ 实时仪表盘(分钟级)
                                └─────────▶ 落实时事实表(供近实时报表)
```

**事件统一 schema（raw 上报）**：

```json
{
  "event_id": "uuid-xxxx",
  "event_name": "Purchase",
  "event_time": "2026-08-14T10:00:00Z",
  "platform": "meta",
  "user": { "client_user_agent": "...", "ip": "1.2.3.4", "external_id_md5": "..." },
  "source": { "pixel_id": "123", "app_id": "app-1" },
  "custom_data": { "value": 12.34, "currency": "USD", "order_id": "ORD-1" },
  "conversion_id": "conv-uuid-1"
}
```

#### 3.4.3 Kafka 概念映射

| 统一概念 | Kafka | 用途 |
|---------|-------|------|
| 事件总线 | Kafka topic（`ad.events`） | 承载所有第一方事件 |
| 分区序 | key 哈希分区（user_id/campaign） | 保证同类事件保序 |
| 幂等 | producer idempotence + 去重表 | 防止重放 |
| 消费 | consumer group 并行 | 缩放处理 |
| 消息可靠性 | acks=all + at-least-once | 不丢不重复消费需幂等 |

**去重（Streaming）**：实时流天然 at-least-once，需配合"去重表/状态 + 幂等写"：

```sql
-- 近实时去重：兜底用唯一键插入，冲突即丢弃重复
INSERT IGNORE INTO fact_conversion (dedup_key, ...) VALUES (...);
-- 或用 Flink 状态去重：按 dedup_key 存 TTL 状态
```

#### 3.4.4 Flink 实时聚合一例

```java
// AggregationJob.java —— 概念示例
DataStream<AdEvent> ev = env.addSource(kafka("ad.events"));

ev.keyBy(e -> e.campaignId)
  .window(TumblingEventTimeWindows.of(Time.minutes(5)))
  .aggregate(new MetricsAggregator())
  .map(toMetricRow())
  .addSink(bigquerySink("fact_metric_realtime"));
```

**Flink SQL 版本（等效）**：

```sql
-- 每分钟按 campaign 聚合并写入实时事实表
CREATE TEMP TABLE fact_metric_realtime AS
SELECT
  campaign_id,
  TUMBLE_END(proc_time, INTERVAL '1' MINUTE) AS window_end,
  COUNT(DISTINCT IF(event_name='Impression', event_id, NULL)) AS impressions,
  COUNT(DISTINCT IF(event_name='Click', event_id, NULL))      AS clicks
FROM ad.events
GROUP BY campaign_id, TUMBLE(proc_time, INTERVAL '1' MINUTE);
```

#### 3.4.5 Lambda 架构

Lambda 架构把"批处理 + 流处理"两层叠加，用一个"合并/服务层"对外提供一致查询：

```
                    ┌────────────────────────────────────┐
                    │            Query / Serving          │
                    │  合并历史(离线视图) + 最新(实时视图)   │
                    └───────────────┬────────────────────┘
                                    │
        ┌───────────────────────────┼───────────────────┐
        │ Batch Layer               │ Speed Layer        │
        └───────────────────────────┼───────────────────┘
        ┌──────────────┐            ┌──────────────┐
        │ Raw (全部历史) │───▶ 主/离线视图  │ 实时增量      │──▶ 实时视图
        └──────────────┘            └──────────────┘
```

**适用**：同时需要"精确全量历史"（批）与"低延迟最新"（流）的场景，如实时 ROI + 历史全量对账。缺点是要维护两套代码与合并逻辑，容易口径不一致。

**Lambda 视图合并示例（服务层 SQL）**：

```sql
-- 对外查询：历史精确 + 当日实时
SELECT * FROM (
  SELECT * FROM mart_campaign_daily        -- 离线精确视图
  WHERE report_date < @today
  UNION ALL
  SELECT * FROM mart_campaign_realtime     -- 当日实时近似视图
  WHERE report_date = @today
) WHERE campaign_id = @cid;
```

#### 3.4.6 Medallion / 湖仓分层复用同一模型

跨平台统一模型天然适配 Medallion：

| 层 | 内容 | 说明 |
|----|------|------|
| Bronze | raw 平台 JSON（逐平台、原样） | 可回放、可追溯 |
| Silver | 统一 schema（清洗、SCD、去重、标准化） | 单一事实来源 |
| Gold | 主题聚合 mart（日/小时指标、ROAS、归因） | 供 BI/应用 |

实时数据也先进 Bronze（事件 JSON），再在 Silver 做统一标准化的**实时变体**（`fact_metric_realtime`），最后在 Gold 与 T+1 数据合并/对账。

```
Bronze(原始) ──▶ Silver(统一/标准化) ──▶ Gold(聚合/主题)
   │                  │                      │
   ├─ raw_google      ├─ dim_campaign         ├─ mart_campaign_daily
   ├─ raw_meta        ├─ dim_ad_group         ├─ mart_roas
   ├─ raw_event      ├─ fact_metric_daily   └─ mart_attribution
   └─ raw_webhook     ├─ fact_metric_realtime
                       ├─ fact_conversion
                       └─ dim_audience
```

#### 3.4.7 延迟分层与一致性

**数据新旧分层（Freshness tiers）**：

| 层级 | 延迟目标 | 示例 |
|------|---------|------|
| 实时层 | 秒~分钟 | 实时出价、频控、告警、反作弊 |
| 近实时层 | 分钟~小时 | 实时看板（近似值） |
| 离线层 | T+1（小时~天） | 财务对账、正式报表、归因回填 |
| 深度层 | T+2~T+7 | 平台修订后最终口径、历史回溯 |

**一致性策略**：
- 实时层用**最终一致**，容忍近似值，标 `is_provisional=true`；
- 离线层用**平台最终口径覆盖**，标 `is_complete=true`；
- 报表框架按延迟层级选择数据源，并展示数据新鲜度。

**容错**：
- 实时流：Kafka 分区副本、checkpoint、至少一次 + 幂等写入，消费落后阈值告警；
- 离线批：重试 + 拉取状态表 + 缺口检测 + schema 兼容；
- 平台 API 限流（429）：退避重试、令牌桶、优先级队列。

**限流处理示例**：

```python
import time, random

def call_with_backoff(fn, max_retries=5):
    for attempt in range(max_retries):
        try:
            return fn()
        except RateLimitError as e:
            wait = (2 ** attempt) + random.uniform(0, 1)
            time.sleep(wait)
    raise TimeoutError("rate limit exhausted")
```

#### 3.4.8 平台差异：实时 vs 批量数据源对比表

| 平台 | 批量报表 | 实时事件 | 实时能力 |
|-----|---------|---------|---------|
| Google Ads | GAQL statistics（日粒度） | Google Ads API / 无通用实时转化流 | 转化经 GoogleTag/CAPI |
| Meta | Marketing API insights | Pixel / CAPI（Conversion API） | CAPI 服务端事件，秒~分钟 |
| TikTok | Report API | Pixel / Events API | Events API 上报 |
| DV360 | 报表导出 / SDF | (基本无实时事件流) | 以批量为主 |

> 结论：**第一方事件的实时化依赖 Pixel/CAPI/Events API**，而**平台指标只适合批量**。统一模型应在"批量指标表"与"实时事件表"之间建立对照与对账关系，用离线 T+1 校准实时近似。

**实时与批量对账（回填校准）**：

```sql
-- 把当日"实时近似"替换为"离线最终口径"，并标记完整性
MERGE INTO mart_campaign_daily t
USING mart_campaign_realtime s
ON t.dim_campaign_id = s.dim_campaign_id AND t.report_date = s.report_date
WHEN MATCHED THEN UPDATE SET
    impressions = GREATEST(t.impressions, s.impressions),
    is_complete = TRUE,
    updated_at = CURRENT_TIMESTAMP();
```

### 3.5 映射 JSON 示例（单条 campaign 从各平台入统一模型）

以 Meta 为例，原始 API 返回 → 标准化后的统一 JSON：

```json
// ---- 平台原始 (raw_meta) ----
{
  "campaign_id": "2384790348",
  "name": "Summer Launch - iOS",
  "objective": "APP_INSTALLS",
  "status": "ACTIVE",
  "daily_budget": "5000",
  "buying_type": "AUCTION",
  "start_time": "2026-08-01T00:00:00+0800"
}

// ---- 统一 (silver.dim_campaign) ----
{
  "platform": "meta",
  "platform_external_id": "2384790348",
  "dim_account_id": 101,
  "campaign_name": "Summer Launch - iOS",
  "objective": "app_install",
  "status": "ACTIVE",
  "bid_strategy": "optimized_cpm",
  "budget_micro": 5000000000,          // 5000 元 → 5000 * 1e6
  "budget_currency": "USD",
  "start_date": "2026-08-01",
  "timezone": "Asia/Shanghai",
  "currency": "USD",
  "valid_from": "2026-08-01T00:00:00Z",
  "valid_to": null,
  "is_current": true
}
```

### 3.6 数据仓库落地注意点

1. **分区与聚类**：指标事实表按 `report_date` 做 date partition；按 `platform` 做 cluster（BigQuery）或索引（PG），避免全表扫。
2. **物化视图**：日频热点查询（日报、ROAS）用物化视图/增量表，避免每次重算。
3. **数据保留**：raw 层按合规与成本设置保留期（如 90 天），silver/gold 长期保留；识别欧盟/当地数据保留法规。
4. **隐私与脱敏**：受众、用户级事件含 PII，需脱敏/tokenization/加密；遵循 GDPR/CCPA/Cookie 合规。
5. **可观测性**：打通 Airflow 监控、DQ 校验、血缘 catalog、数据目录，形成"数据可观测性"闭环。

**推荐的分区/建表落地示例（BigQuery）**：

```sql
CREATE TABLE IF NOT EXISTS fact_metric_daily (
    report_date  DATE NOT NULL,
    platform     STRING NOT NULL,
    ...
)
PARTITION BY report_date
CLUSTER BY platform;
```

### 3.7 落地路线图与团队分工

统一数据模型的落地不是一次性工程，建议分阶段推进：

| 阶段 | 目标 | 关键产出 | 里程碑 |
|------|------|---------|--------|
| 阶段一（1-2 月） | 打通原始拉取 + raw 层 | 4 平台连接器、raw 落盘 | 能回放原始 JSON |
| 阶段二（2-3 月） | 统一 Silver schema | dim_*/fact_metric_daily 全部落库 | 单一事实来源可用 |
| 阶段三（1-2 月） | 指标/归因对账 | 对账任务、DQ 校验、血缘 | 差异 < 2% 阈值 |
| 阶段四（持续） | Gold/实时/算法接入 | mart、实时流、CAPI 事件 | 全链路可观测 |

**团队职责建议**：

| 角色 | 职责 |
|------|------|
| 数据工程师 | 连接器、ETL、调度、DQ、血缘 |
| 数据平台/架构 | 统一 schema 制定、口径治理、数据目录 |
| 数据/广告分析师 | 口径定义、报表需求、对账验收 |
| 数据科学家 | 归因、优化模型消费统一模型 |
| 平台接口 owner | 各平台 API 变更跟踪、适配器更新 |

## 四、常见问题与排查

### 4.1 各平台数字对不上（Reconciliation）

**现象**：同一账户，平台后台的 spend 与统一模型报表 spend 有差异。

**排查步骤**：
1. 确认口径：是否都算媒体成本 + 数据费？DV360 的 total_cost 含 fee，需拆净媒体成本。
2. 确认时区：报表日是否按同一会计时区归日。
3. 确认归因窗口/统计方式是否一致。
4. 确认是否包含"增量回填"（t+2/t+3 修订）。
5. 检查原始审批未包含的昨日数据缺口（is_complete=false）。

**解决方案**：建立逐日对账任务，差异超过 2% 阈值告警。

```sql
-- 对账脚本：统一层 vs 平台 API（以 spend 为例）
WITH ours AS (
  SELECT report_date, SUM(spend_micro) spend_micro
  FROM fact_metric_daily WHERE platform='meta' GROUP BY 1
), theirs AS (
  SELECT report_date, SUM(spend_micro) spend_micro FROM raw_meta_stats GROUP BY 1
)
SELECT o.report_date, o.spend_micro, t.spend_micro,
       (o.spend_micro - t.spend_micro) AS gap
FROM ours o JOIN theirs t USING (report_date)
WHERE ABS(o.spend_micro - t.spend_micro) > 0.02 * t.spend_micro;
```

### 4.2 转化重复统计（Double Counting）

**现象**：同一笔订单在多个平台/多次拉取中被重复计入。

**原因**：转化由多个来源上报（Pixel + CAPI + 平台自身），且批量重跑。

**解决**：
- 用 `dedup_key` 唯一键；
- 统一由第一方归因引擎负责最终归属，平台报表转化只用于对账；
- 定义清晰的"主数据源"避免多渠道重复写入。

```python
# 案例：同一 order_id 被 Pixel 与 CAPI 各报一次，靠 dedup 收敛
dedup = conversion_dedup_key("meta", event_time, None, order_id="ORD-1")
# 若 server 与 client 都带相同 order_id+时间哈希 → 只保留一条
```

### 4.3 平台 API 限流 / 超时

**现象**：拉取大量 campaign 时频繁 429 / 超时。

**解决**：
- 退避重试（指数退避 + 抖动）；
- 分批并行，控制并发；
- 对超大账户启用分片/离线报表导出（如 DV360 SDF、Google 全量报告）。

```python
# 令牌桶限流客户端
import threading, time

class TokenBucket:
    def __init__(self, rate, capacity):
        self._rate = rate; self._capacity = float(capacity)
        self._tokens = self._capacity; self._lock = threading.Lock()
        self._ts = time.time()
    def acquire(self):
        with self._lock:
            now = time.time()
            self._tokens = min(self._capacity,
                              self._tokens + (now - self._ts) * self._rate)
            self._ts = now
            if self._tokens >= 1:
                self._tokens -= 1
                return True
            return False
```

### 4.4 时间/时区归错日

**现象**：深夜事件归到错误日期，导致日报波动。

**解决**：统一 `event_time` 转 UTC 存储，报表日统一按账户时区 `DATE(event_time, tz)` 计算；日切点统一约定并写入元数据。

```sql
-- 排查特定小时数据是否归错日
SELECT
  tz_date,
  COUNT(*) AS events
FROM (
  SELECT DATE(TIMESTAMP(event_time_utc), @account_tz) AS tz_date
  FROM fact_conversion
  WHERE event_time_utc BETWEEN @start AND @end
) GROUP BY 1 ORDER BY 1;
```

### 4.5 浮点金额误差

**现象**：金额在多平台汇总后出现 0.01 级别误差。

**解决**：金额一律整数 micro/cents 存储；只在最终展示时才除以换算系数；比率用 NUMERIC。

### 4.6 指标缺失被当成 0

**现象**：某日平台拉取失败，报表显示"花费为 0"，被业务误解为无消耗。

**解决**：`ingestion_watermark.is_complete` 标记；报表层过滤 `is_complete=false`；缺口恢复后自动回填重跑。

```sql
-- 报表层强制排除未完成数据
SELECT * FROM mart_campaign_daily
WHERE is_complete = TRUE AND report_date = @date;
```

### 4.7 平台字段语义变化 / 废弃

**现象**：Meta/TikTok 更新字段，旧字段弃用，映射失效。

**解决**：raw 层 JSON 保留全部字段；Silver 层映射函数版本化；枚举新增落 UNKNOWN 并触发人工映射；schema_change_log 记录。

### 4.8 排查工具：一张"数据血缘到指标"的追查 SQL

```sql
-- 从报表指标追溯到统一表
SELECT * FROM mart_campaign_daily WHERE report_date='2026-08-14' AND campaign_id=...
-- 再到 silver 与 raw
SELECT * FROM fact_metric_daily WHERE report_date='2026-08-14' AND dim_campaign_id=...
SELECT * FROM raw_meta_stats WHERE report_date='2026-08-14'
-- 再用 lineage_catalog 确认字段映射与转换规则
```

### 4.9 常见问题速查表

| 症状 | 可能根因 | 排查/处置 |
|------|---------|----------|
| spend 对不上 | 货币/时区/口径/费用拆分 | 对账脚本 + 口径核对 |
| 转化重复 | 多来源上报 | dedup_key + 主数据源 |
| 报表日波动大 | 时区归日错误 | 统一 UTC + 账户时区归日 |
| 金额 0.01 误差 | FLOAT 精度 | 整数 micro 存储 |
| 某日全 0 | 拉取失败当 0 | is_complete 过滤 + 回填 |
| 字段突然 UNKNOWN | 平台枚举新增/废弃 | 落 UNKNOWN + 人工映射 |
| API 429 频发 | 限流 | 退避 + 令牌桶 + 并发控制 |
| 指标延迟数天 | 平台归因回填未稳定 | 标记 is_complete 阈值控制 |

## 五、自测题

### 问题 1
统一数据模型中，为什么 `fact_metric_daily` 的 spend 建议用整数 micro/cents + currency 字段，而不是 FLOAT？请说明精度风险与换算方式。

<details>
<summary>点击查看答案</summary>

**答案**：FLOAT 是二进制浮点，无法精确表示十进制的金额（如 0.1 元）；跨平台大量金额相加时会产生累计误差（如 0.1+0.2=0.30000000000000004）。统一模型应采用 64 位整数（`micro`=1e-6，或 `cents`=1e-2）无损存储，并加 `currency` 表示所属币种。展示与计算时才按换算系数（micro→元 除以 1e6）转换为浮点，确保入库与聚合阶段无精度损失。比率类（CTR/ROAS）用 NUMERIC/DECIMAL。
</details>

### 问题 2
简述 Meta 的 AdSet 与 Google 的 AdGroup 在语义上的差异，以及统一模型中如何设计 `source_level` 字段。

<details>
<summary>点击查看答案</summary>

**答案**：Meta AdSet 同时承载预算、目标受众、排期、出价策略；Google AdGroup 主要承载定向与出价，预算在 Campaign。二者在"投放单元"语义上等价但职责不同。统一模型统一抽象为 `dim_ad_group`，用 `source_level` 标注其来源概念（adgroup / adset / line_item），并允许 `budget_micro` 字段只在 Meta/TikTok/DV360 这类承载预算的来源层级上填充，从而保留差异又统一口径。
</details>

### 问题 3
为什么平台转化指标不能直接加总成"整体转化"？统一模型如何处理归因口径问题？

<details>
<summary>点击查看答案</summary>

**答案**：各平台归因窗口与统计方式不同（Google 点击后 30 天、Meta 点击 7 天+浏览 1 天、DV360 30+10 天），同名"conversions"口径不等价，直接加总会重复/遗漏。统一模型把转化分两层：平台口径转化（带 attribution_window/attributed_by 元数据，仅用于对账）与第一方归因转化（用自己的归因引擎统一归属）。对外只输出一个最终归属口径。
</details>

### 问题 4
ETL 中"日粒度指标在 T+2/T+3 会被平台回填修订"，设计上应如何避免拿"当时的 0/近似值"当作最终值？

<details>
<summary>点击查看答案</summary>

**答案**：应使用"覆盖当天 + 幂等 upsert + 修订状态"模式：指标表对所有来源行以 `(platform, report_date, dim_id组合)` 为唯一键做 MERGE/upsert，每次最新拉取覆盖旧值，并更新 `updated_at` 与 `is_complete`。从"平台拉取状态表"判断某日是否达到稳定（可配置稳定阈值，如 T+2），达到稳定后才对报表标记 `is_complete=true`，报表默认只展示完整数据，避免把未回填的 0 当作最终值。
</details>

### 问题 5
实时流（CAPI/Pixel 事件）与批量报表（T+1）如何协同，避免"实时口径"与"最终口径"冲突？

<details>
<summary>点击查看答案</summary>

**答案**：建议实时流用于低延迟场景（实时出价、频控、风控、近实时看板），结果标 `is_provisional=true`（近似值）；批量 T+1 报表用于正式对账与财务核算，标 `is_complete=true`（最终口径）。报表框架按"数据新鲜度分级"选择数据源：需要最新→实时视图，需要准确→离线视图，并在展示层说明数据延迟与口径层级。二者在 Bronze 同源、在 Gold 通过 MERGE/对账合并，利用离线结果校准实时近似值。
</details>

### 问题 6（附加）
设计一个 `dedup_key` 以解决"同一订单被 Pixel 与 CAPI 重复上报"的问题，并说明其优先级。

<details>
<summary>点击查看答案</summary>

**答案**：`dedup_key` 优先级：① 平台 event_id（最稳定，官方去重ID）→ ② 若无 event_id，用 `order_id + event_time + platform` 组合哈希 → ③ 再兜底用 `event_time + user_hodler`。实现对同一业务事件的多次上报收敛为一条。写入时用 `INSERT IGNORE`/`MERGE ON dedup_key`，重复冲突即忽略。同时统一"主数据源"（如以 CAPI 服务端为准），避免与 Pixel 客户端重复计入。
</details>

---

## 六、附录：术语表与参考

### 6.1 统一模型核心术语表

| 术语 | 英文 | 含义 |
|------|------|------|
| 统一数据模型 | Unified Data Model (UDM) | 跨平台标准化的数据 schema 集合 |
| 单一事实来源 | Single Source of Truth (SSOT) | 统一层作为唯一权威数据来源 |
| 原始层 | Bronze / Raw | 逐平台原样 JSON 落盘 |
| 标准化层 | Silver / Standardized / ODS | 统一 schema 的清洗层 |
| 主题层 | Gold / Mart | 面向应用的聚合层 |
| 缓慢变化维度 | Slowly Changing Dimension (SCD) | 维度历史版本管理（Type 2） |
| 幂等键 | Idempotency Key | 保证重复数据只落一份的唯一键 |
| 会计日期 | Report Date | 按会计时区归一化的归属日 |
| 微单位 | Micro | 1e-6 精度整数金额单位 |
| 血缘 | Lineage | 数据从源头到报表的追踪关系 |
| 数据新鲜度 | Data Freshness | 数据新旧层级（实时/近实时/离线） |

### 6.2 ETL 失败模式补充清单

除第四章的常见问题外，这里补充一批 ETL 特有的失败模式与处置：

| 失败模式 | 现象 | 处置 |
|---------|------|------|
| 平台时分页死循环 | 下一页 token 一直不变 | 限制最大页数 + 去重 token 检测 |
| Watermark 回退 | 历史某日数据需重拉 | 支持按日期触发回填 re-run |
| 并行并发过载 | 多平台同时拉取导致本地资源打满 | 并发限流 + 串行排程 |
| 上游 schema 破坏 | API 返回结构突变 | raw 存 + 校验 fail + 人工介入 |
| 货币换算公式错误 | 汇率固定导致误差 | 汇率维表 + 版本控制 |
| 夏令时(DST)影响 | 时区切换导致归日偏差 | 用 IANA 时区 + 转换库正确处理 |
| 空 partition 误入 | 拉到 0 行但状态置 complete | 行数完整性校验 rule |
| 编码/emoji 乱码 | 文案字段编码问题 | UTF-8 强制 + 清洗规则 |

### 6.3 规模与性能参考指标

| 场景 | 参考取值 |
|------|---------|
| 单账户日指标行数 | 数百 ~ 数十万（按粒度） |
| 全账户日指标写入 | 数十万 ~ 千万行 |
| 拉取频率（批量） | 每日 1-3 次（T+1 / T+2） |
| 实时事件吞吐 | 每秒 ~ 上万事件（按业务） |
| 指标回填稳定窗口 | T+2 ~ T+7（平台相关） |
| 对账差异阈值 | 2%（可配置） |
| 保留期（raw） | 通常 90 天（合规可调整） |

### 6.4 推荐的工具选型速查

| 环节 | 可选工具 | 备注 |
|------|---------|------|
| 调度 | Airflow / Prefect / Dagster | 选熟悉且生态全者 |
| 存储 | BigQuery / Snowflake / Postgres / 湖仓 | 视规模与预算 |
| 流处理 | Kafka + Flink / Spark Structured Streaming | 有状态去重用 Flink |
| 校验 | Great Expectations / dbt test / 自研 | 规则化守门 |
| 血缘/目录 | DataHub / OpenMetadata / 自研 catalog | 字段级依赖 |
| 事件采集 | Pixel / CAPI SDK / 自定义 SDK | 平台事件实时化 |

### 6.5 dbt 式 Mart 模型落地（补充示例）

对于以 dbt 为核心的数仓团队，可用 dbt seed 管理枚举字典、用 models 管理标准化与 mart。这里给出 mart 模型的 YAML 测试断言示例：

```yaml
# models/marts/_mart_campaign_daily.yml
version: 2
models:
  - name: mart_campaign_daily
    description: "跨平台统一日报"
    columns:
      - name: spend
        description: "花费(元，已换算)"
        tests:
          - not_null
          - dbt_utils.accepted_range:
              min_value: 0
      - name: roas
        tests:
          - dbt_utils.accepted_range:
              min_value: 0
      - name: platform
        tests:
          - accepted_values:
              values: ['google', 'meta', 'tiktok', 'dv360']
      - name: report_date
        tests:
          - not_null
```

```sql
-- models/marts/mart_campaign_daily.sql
SELECT
    c.platform,
    c.campaign_name,
    f.report_date,
    SUM(f.impressions) AS impressions,
    SUM(f.clicks)      AS clicks,
    SAFE_DIVIDE(SUM(f.clicks) * 100.0, SUM(f.impressions)) AS ctr_pct,
    SUM(f.spend_micro) / 1e6                              AS spend,
    SAFE_DIVIDE(SUM(f.conversion_value_micro),
                SUM(f.spend_micro))                       AS roas
FROM {{ ref('fact_metric_daily') }} f
JOIN {{ ref('dim_campaign') }} c USING (dim_campaign_id)
GROUP BY 1, 2, 3
```

---

> **文档说明**：本文档为 `ryan-personal-knowledge` 广告业务专家库的「跨平台统一数据模型」深度文档，从统一实体模型、逐字段映射、数据类型标准化、ETL 管道、实时 vs 离线五个维度，面向数据工程落地展开。所有代码与 Schema 为教学型示例，生产实施需结合各平台最新 API 与组织数据治理规范进行裁剪。附录部分补充了术语表、失败模式清单、规模参考、工具选型与 dbt 落地示例，便于一线数据工程师直接落地。
