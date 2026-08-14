# DV360 定向系统完整指南（上下文定向 / 受众定向 / 频率控制 / 品牌安全）

> **领域**: 广告投放 / 定向系统
> **深度**: ⭐⭐⭐⭐⭐ 实战级指南
> **标签**: dv360, targeting, audience, contextual-targeting, frequency-capping, brand-safety
> **更新时间**: 2026-08-14
> **类型**: 深度文档

---

## 一、核心概念与架构

### 1.1 DV360 定向体系总览

Display & Video 360（简称 DV360）是 Google Marketing Platform 旗下的一站式程序化广告 DSP（Demand-Side Platform，需求方平台）。在 DV360 中，定向（Targeting）是决定"广告该投给谁、投在哪、投在什么内容环境里"的核心决策层。与 Google Ads 的"keyword 优先"逻辑不同，DV360 面向品牌广告主与代理商，强调对**库存、人群、内容环境与卖方的精细化控制**，因此它的定向体系是全市场最丰富、也最容易踩坑的。

一个完整的 DV360 定向体系可以按"谁来投 / 投到哪 / 投在什么环境下 / 投多频繁 / 别投到哪"这条主线划分为五大类：

```
DV360 定向体系全貌
│
├── 一、上下文定向 Contextual   → 页面内容 / 关键词 / 分类 / 位置
│       ├── 关键词定向 (Keyword)
│       ├── 分类定向 (Category)
│       ├── 站点-URL 定向 (URL/Placement)
│       ├── App / 应用定向
│       └── 内容类型 / 页面类型 (video / article / games)
│
├── 二、受众定向 Audience         → "人"是谁
│       ├── 第一方数据 (1st-party: CSVD / 自定义受众 / 动态受众)
│       ├── 第二方数据 (2nd-party: 发布商共享)
│       ├── 第三方数据 (3rd-party: 数据商如 Oracle BlueKai / Nielsen)
│       ├── Google 受众 (Affinity / In-Market / Life Events / Detailed Demographics)
│       ├── 类似受众 (Similar / Lookalike)
│       └── 组合受众 (Custom / 并集/差集)
│
├── 三、人口统计与设备定向        → "场景"条件
│       ├── 年龄 / 性别 / 收入 / 家长状态
│       ├── 设备类型 (手机/平板/电脑/电视/车载)
│       ├── 操作系统 (iOS/Android/Windows/macOS)
│       ├── 地域 Geo (国家/州/城市/邮编/半径)
│       ├── 网络连接 (WIFI/4G/5G)
│       └── 时段 / 日期 (dayparting)
│
├── 四、频率控制 Frequency       → "多久见一次"
│       ├── 频控单位 (per IO / per Line Item / per creative)
│       ├── 频控窗口 (每日/每周/每小时/整体 campaign)
│       └── 跨 IO 去重 (dedup within insertion order)
│
└── 五、品牌安全 Brand Safety    → "别投到哪"
        ├── 内容排除 (Content Exclusions)
        ├── 品牌安全分类 (Brand Safety Categories)
        ├── 敏感类别 (物化/医疗/政治等)
        ├── 卖方设置 (GAR / 差异化标签)
        └── 第三方校验 (Integral Ad Science / DoubleVerify)
```

**关键理解：DV360 的定向是"叠加"而非"唯一匹配"。** 一个广告展示机会（impression）必须同时满足该 Line Item 上所有已设定的**正向（included）定向条件**，同时不得命中任何**负向（excluded）定向条件**，才会进入竞价。任何一层不满足，该次展示机会就被跳过。

### 1.2 正定向与负定向（排除）

DV360 定向分为两个方向，理解这点是避免"以为圈里全是目标用户、结果 fill 为零"的关键：

| 方向 | 英文 | 含义 | 作用 | 风险 |
|------|------|------|------|------|
| 正定向 | Included / Targeting | 明确"只要这些" | 收窄人群，提高相关性 | 太窄 → 可投放库存骤降、fill 低 |
| 负定向 | Excluded / Negative | 明确"不要这些" | 剔除品牌风险、低质流量 | 太少 → 预算浪费在无效库存 |

**定向组合的默认逻辑：**
- 所有正定向维度之间是 **AND（交集）关系**：比如"年龄 25-34 **且** 地域美国 **且** 兴趣跑鞋"。
- 同一维度内多个值之间通常是 **OR（并集）关系**：比如"年龄 25-34 **或** 35-44"。
- 负定向是 **NOT（排除）**：命中的一律排除，优先级最高。

```
正定向（必须全部满足，AND）
┌─────────────────────────────────────────┐
│  地域 = US ∪ CA            (OR 并集)       │
│  ∩ 年龄 = 25-34 ∪ 35-44   (OR 并集)       │
│  ∩ 兴趣 = Running Shoes    (单一值)        │
│  ∩ 内容 = 不限制           (全量)          │
└─────────────────────────────────────────┘
                       ∩
负定向（命中即剔除，NOT）
┌─────────────────────────────────────────┐
│  排除 地域 = 波多黎各                      │
│  排除 分类 = Gambling / Violence          │
│  排除 App = [黑名单 App 列表]              │
└─────────────────────────────────────────┘
                       ＝
             最终 eligible audience
```

**实战心智模型：DV360 的"全量库存"金字塔。** 设想你有一个 100% 的品牌安全库存池（Bid）。每加一层正定向，库存就的可能竞价机会就缩小；每加一层负定向，剔除掉的是你不想要的。优化的本质就是在"相关性"与"可投量/出量"之间取均衡点。

### 1.3 定向单位（Targeting Unit）

在 DV360 的对象模型中，定向条件不是散落的字段，而是被封装在 **Targeting Unit（定向单位）** 中，并通过 `assigned targeting options`（已分配定向选项）挂载到具体的实体上。

```
靶场实体 (Targeting Roster / 定向方案)
   │
   ├─ 挂载到 Line Item（线项）级别 = 最常用
   ├─ 挂载到 Insertion Order（IO 订单项）级别
   └─ 挂载到 Advertiser（广告主）级别（默认横跨所有）

每个 Targeting Unit 内包含若干 assigned targeting option：
   ├─ TargetingOption.keyword   → 关键词
   ├─ TargetingOption.category  → 分类
   ├─ TargetingOption.geo       → 地域
   ├─ TargetingOption.audience  → 受众
   ├─ TargetingOption.device    → 设备
   ├─ TargetingOption.app       → 应用
   ├─ TargetingOption.content_exclusion → 内容排除
   └─ ... 每个 option 有一个 targetType 字段标识"included / excluded"
```

在项目脚本 `ad_platform_api.py` 中，与定向单位直接相关的封装方法有：

- `dv360_list_targeting_units(advertiser_id)` —— 列出某广告主下的所有定向单位
- `dv360_create_targeting_unit(advertiser_id, ...)` —— 创建定向单位
- `dv360_update_targeting_unit(targeting_unit_id, ...)` —— 更新定向单位（增删 assigned targeting options）
- `dv360_delete_targeting_unit(targeting_unit_id)` —— 删除定向单位
- `dv360_list_targetings(advertiser_id)` —— 列出定向项（targeting options 层面的视图）

在底层 REST API v4 中，对应的资源是：

```
GET  /v4/advertisers/{advertiserId}/targetingTypes/{targetingType}/assignedTargetingOptions
POST /v4/advertisers/{advertiserId}/targetingTypes/{targetingType}/assignedTargetingOptions
PATCH/DELETE /v4/advertisers/{advertiserId}/targetingTypes/{targetingType}/assignedTargetingOptions/{assignedTargetingOptionId}
```

其中 `targetingType` 取值为 `TARGETING_TYPE_CONTEXTUAL`、`TARGETING_TYPE_AUDIENCE`、`TARGETING_TYPE_GEO`、`TARGETING_TYPE_AGE`、`TARGETING_TYPE_GENDER`、`TARGETING_TYPE_KEYWORD`、`TARGETING_TYPE_PLACEMENT`、`TARGETING_TYPE_APP`、`TARGETING_TYPE_DEVICE`、`TARGETING_TYPE_OPERATING_SYSTEM`、`TARGETING_TYPE_CONTENT_EXCLUSION` 等。每个 `AssignedTargetingOption` 还带 `targetingOptionId`（指向选项库中的具体选项）和 `targetingType` 的 included/excluded 语义。

### 1.4 定向维度选项库

`dv360_api.py` 的 `get_targeting_dimension_options()` 返回了官方支持的定向维度选项骨架：

```python
def get_targeting_dimension_options(self) -> List[Dict]:
    """获取官方定向维度选项"""
    return [
        {'code': 'GEO', 'name': '地域', 'description': '国家、地区、城市定向'},
        {'code': 'AGE', 'name': '年龄', 'description': '年龄段定向'},
        {'code': 'GENDER', 'name': '性别', 'description': '男/女定向'},
        {'code': 'INTEREST', 'name': '兴趣', 'description': '兴趣标签定向'},
        {'code': 'BEHAVIOR', 'name': '行为', 'description': '用户行为定向'},
        {'code': 'KEYWORD', 'name': '关键词', 'description': '页面关键词定向'},
        {'code': 'PLACEMENT', 'name': '投放位置', 'description': '具体网站/应用定向'},
        {'code': 'APP', 'name': '应用', 'description': '特定应用定向'},
        {'code': 'DEVICE', 'name': '设备', 'description': '手机/平板/电脑定向'},
        {'code': 'OPERATING_SYSTEM', 'name': '操作系统', 'description': 'iOS/Android/Windows定向'},
    ]
```

注意：这个列表是"官方配置文件"里给的简化清单。真实 DV360 的 targetingType 枚举远比这丰富（见上文 1.3）。**在实现上，凡是需要"列出选项"的地方都要走 API 拉取**，而不是硬编码，因为 DV360 的选项库（尤其分类、关键词、In-Market 受众）会随季度更新。

### 1.5 频率控制与品牌安全在整个定向体系中的位置

频率控制（Frequency Capping）与品牌安全（Brand Safety）虽然常被单独讨论，但**在 DV360 的定向架构里，它们就是两类特殊的"定向条件"**：

- **频率控制**：决定一个用户在一定时间窗口内最多能看到几次广告。它不是"投给谁"，而是"同一个用户叠加几次"，本质上是**负向叠加限制**——超出频控的用户会被自动从可竞价库存中扣除。
- **品牌安全**：决定"内容环境是否安全"。它是一组**负向定向**（Content Exclusion / Brand Safety Category），命中不安全分类（暴力、赌博、成人、敏感政治等）的库存直接不可竞。

因此，一个完整的人群决策流是"先过滤环境安全 → 再按正定向圈人 → 再扣减频控超限用户 → 剩余进入竞价"：

```
实时请求到达 (Bid Request)
   │
   ▼
① 品牌安全过滤（Content Exclusion / Category）
   │ 命中不安全分类? ──是──► 丢弃 (no bid)
   ▼ 否
② 负定向过滤（Excluded options）
   │ 命中任一排除项? ──是──► 丢弃
   ▼ 否
③ 正定向匹配（Included options，AND 叠加）
   │ 所有正定向都满足? ──否──► 丢弃
   ▼ 是
④ 频控检查（Frequency Cap）
   │ 该用户当前窗口内已达上限? ──是──► 丢弃
   ▼ 否
⑤ 进入竞价 (auction) + 出价
```

这张图的顺序在后续"Go 实现定向匹配引擎"一节里会被翻译成真实代码。

### 1.6 DV360 定向 vs. 广义广告定向（承接已有文档）

Ryan 个人知识库中已有多篇**广义广告系统**的定向文档（`ad-targeting-*.md`、`ad-frequency-capping-*.md`、`ad-lookalike-audience-expansion.md`、`ad-retargeting-strategy-optimization.md` 等），它们讲的是"一套自研 DSP/广告系统应该怎么设计定向与频控"。而本文聚焦 **DV360 这个具体 SaaS 平台**：它的 UI 操作、REST API 封装方法、后台算法行为（如 DV360 自己的 Lookalike、In-Market 模型）以及"平台侧"的坑。两者互补关系如下：

| 层面 | 广义广告系统文档 | 本文（DV360 平台） |
|------|----------------|-------------------|
| 定向算法原理 | 详述（倒排索引、向量召回） | 本文第 2.5 节给 Go 引擎实现 |
| 频控理论 | 频控算法、滑动窗口 | 本文第 2.4 节讲 DV360 单位/窗口设置 |
| 平台操作 | 无 | UI + REST API + 封装方法 |
| 数据源 | 自研 DMP | 第一方 CSVD、第三方 partner、Google 自有受众 |
| 踩坑 | 通用缺陷 | DV360 特有（fill、匹配率、audience 同步） |

---

## 二、深度原理解析

### 2.1 上下文定向：关键词 / 分类 / 位置的底层逻辑

**上下文定向（Contextual Targeting）** 是 DV360 最"上古"但依然极其有效的定向方式。它不看用户是谁，而是看**当前页面/应用的"内容上下文"**。它的核心价值在于：不依赖任何用户历史数据与 Cookie，天然适配隐私沙盒（Privacy Sandbox）与第三方 Cookie 退场后的环境。

#### 2.1.1 三种上下文信号

| 信号类型 | API 封装方法 | 说明 | 典型用途 |
|---------|-------------|------|---------|
| 关键词定向 | `dv360_list_keyword_targeting` / `dv360_create_keyword_targeting` / `dv360_delete_keyword_targeting` | 匹配页面正文中的关键词或词组 | 母婴品牌投"新生儿护理"页面 |
| 上下文定向 | `dv360_list_contextual_targeting` / `dv360_create_contextual_targeting` / `dv360_delete_contextual_targeting` | 匹配内容类别（Auto / Travel / Finance…） | 汽车品牌投"汽车"内容分类 |
| 位置/URL 定向 | `dv360_list_placement_targeting` / `dv360_create_placement_targeting` | 精确指定某个站点/URL/App | 品牌只在自家媒体与白名单站点投放 |
| 站点分类定向 | `dv360_list_site_category_targeting` | 按站点所属类别定向 | 在"体育类站点"整体投放 |

**关键词匹配机制（在 DV360 内部）：** DV360 的爬虫持续对海量内容做语义分析，抽出页面主题标签。当请求到达时，将当前页面的已解析主题与广告的 Keyword 定向条件比对。匹配逻辑支持**词组匹配 / 宽泛匹配 / 否定匹配**，且会做近义与同义词扩展（例如 "shoes" 与 "sneakers"）。

**注意一个关键区别**：DV360 的 `KEYWORD` 与 `CONTEXTUAL` 虽都属上下文定向，但 `KEYWORD` 更"精确到词"，匹配页面的自然语言内容；`CONTEXTUAL`（内容分类）更"按语义桶"，匹配 Google 的分类体系（IAB 分类的一种，见 2.1.2）。

#### 2.1.2 分类体系：IAB 分类与 DV360 分类

DV360 采用两级分类体系来组织内容：
- **IAB 内容分类**：行业标准，如 `IAB1 - Arts & Entertainment`、`IAB3 - Business`、`IAB17 - Sports`、`IAB19 - Technology & Computing` 等。
- **DV360 自有分类（Sensitive Categories / Brand Safety 分类）**：用于品牌安全（见 2.6）。

在项目脚本中可以通过 `dv360_list_content_categories()`、`dv360_list_publisher_categories()` 拉取分类选项。

```
IAB 一级分类示例（用于上下文定向）
├── IAB1  Arts & Entertainment
├── IAB3  Business
├── IAB7  Health & Fitness
├── IAB18  News & Politics
├── IAB19  Technology & Computing
└── IAB20  Travel
```

**踩坑 1（分类粒度太粗导致相关性低）**：用"Travel"粗分类投放酒店广告，会命中大量"旅游攻略"内容但人群意图极不精准，CTR 低、无效曝光多。**解决**：叠加更细的二级分类+关键词，或改用 In-Market 受众（见 2.2）。

#### 2.1.3 位置定向（Placement）的精确控制

Placement 定向是把广告"钉"在指定站点/应用/URL 上，是品牌广告主控制品牌环境的最直接手段，常用于：**白名单（Whitelist）**只投签约媒体；**程序化保量（Programmatic Guaranteed）**锁定优质卖方库存；**站点/频道定向**精确到内容。

```python
# 示例：为广告主列出当前的位置(Placement)定向配置
from ad_platform_api import AdPlatformAPI

api = AdPlatformAPI(credentials)
advertiser_id = "1234567890"

# 列出当前所有投放位置定向配置
placements = api.dv360_list_placement_targeting(advertiser_id)
for p in placements:
    print(f"  Placement: {p.get('displayName', p.get('targetingOptionId'))} "
          f"status={p.get('status')}")

# 新增一个精确 URL 定向
resp = api.dv360_create_placement_targeting(
    advertiser_id,
    url="https://example.com/tech-news",
    target_type="included",          # 正定向
)
print("created:", resp)
```

#### 2.1.4 上下文定向的优劣势与适用场景

| 优势 | 劣势 |
|------|------|
| 不依赖用户 Cookie，隐私合规友好 | 只能控制"环境"，控制不了"人是谁" |
| 品牌环境可控性强（投在匹配内容旁更有感染力） | 相关性与转化意图并不强相关 |
| 数据准备成本低（无需受众数据） | 容易误配到语义相近但意图不同的内容 |
| 适合品牌曝光、内容营销 | 对效果型（转化）投放帮助有限 |

**适用场景总结：** 新品上市/品牌造势用上下文+分类获取与品牌调性匹配的优质内容位；内容营销联动投放在"评测/教程"类内容旁放大价值；隐私受限品类（医药、金融对 cookie 敏感）作为受众定向的有效替代。

### 2.2 受众定向：第一方 / 第三方 / Google 自有 / 动态受众

**受众定向（Audience Targeting）** 是 DV360 投放效果的核心引擎，它回答"这个人是否属于我圈定的人群"。DV360 的受众来源非常丰富，是它与普通 DSP 拉开差距的地方。

#### 2.2.1 受众数据的五大数据源

| 数据源 | 说明 | API 封装方法 | 适用 |
|--------|------|-------------|------|
| 第一方数据 | 广告主自有（CSV 上传的客户邮箱、Pixel/Floodlight 采集的网站访客、转化用户） | `dv360_list_audiences` | High-value Retargeting、Lookalike 种子 |
| 动态受众 | Floodlight/Lookback 窗口动态更新的访客集合 | `dv360_list_dynamic_audiences` | 实时 Retargeting |
| 第二方数据 | 发布商/合作伙伴共享的受众 | `dv360_list_audiences` | 与媒体谈判时的数据叠加 |
| 第三方数据 | 数据商（如 Oracle BlueKai、Nielsen、Experian）提供的受众包 | `dv360_list_audiences` | 拓量、人群细分 |
| Google 自有受众 | Affinity、In-Market、Life Events、Detailed Demographics | `dv360_list_audience_segments` | 机器模型生成的意图/兴趣人群 |

#### 2.2.2 第一方受众（1st-Party Audience）详解

第一方数据是最可控、最精准、也最需要"养"的数据。包括：**CSV 客户列表（Customer Match）**把加密后的邮箱/手机号上传匹配 Google 登录用户；**Floodlight 网站访客**收集访问过网站特定页面的用户；**App 用户**通过 Firebase / GA4 导入；**转化用户**完成 Floodlight 转化的高价值人群。

```python
# 示例：列出广告主当前可用的受众（第一方/第三方/Google 自有）
audiences = api.dv360_list_audiences(advertiser_id)
for a in audiences:
    print(f"[{a.get('audienceType', 'N/A')}] {a.get('displayName')} "
          f"size={a.get('estimatedAudienceSize')} "
          f"status={a.get('status')}")
```

**关键点：Audience 有"有效期"与"规模"两个属性**
- **规模（estimatedAudienceSize）**：反映该人群的可投人数，过低（如 < 1000）往往意味着投放会出量困难。
- **状态**：`ACTIVE` / `EXPIRING`（快过期）/ `EXPIRED`（已过期）。CSV 上传的受众通常有 540 天有效期，过期后不再积累新用户，需要重新上传刷新。

**踩坑 2（受众过期导致投放静默失效）**：Retargeting 用的是上传的客户列表受众，有效期到了以后 DV360 不再把新老用户算进人群，但 **Line Item 状态仍然是 ACTIVE**，导致"看起来在投放、实际一个展示都不出"。**排查方法**：进入受众管理界面查看 audience 的 expiration date 与 status，或在 `dv360_list_audiences` 结果里检查 `status` 字段。

#### 2.2.3 动态受众（Dynamic Audiences）

动态受众与静态列表的最大区别是**集合是滚动的**：DV360 根据 Floodlight 的实时事件 + 自定义的 Lookback 窗口（例如"过去 7 天访问过结账页但未下单的用户"）动态维护人群，无需人工上传。这对 Retargeting 与阶段触达（funnel）非常关键。

```python
# 列出动态受众
dynamic = api.dv360_list_dynamic_audiences(advertiser_id)
for d in dynamic:
    print(f"动态受众: {d.get('displayName')}  "
          f"lookback={d.get('membershipDurationDays')}天  "
          f"事件类型={d.get('floodlightActivityIds')}")
```

**动态受众 vs 静态列表对比：**

| 维度 | 动态受众 | 静态客户列表 |
|------|---------|-------------|
| 更新方式 | 自动，实时 | 手动重新上传 |
| 维护成本 | 低（配一次即可） | 高（需定期刷新） |
| 时效性 | 高（滚动窗口） | 中（从上传日算起） |
| 适合场景 | Retargeting、阶段触达 | 已知客户精准圈定、Lookalike 种子 |
| 有效期 | 一般无固定到期（看配置） | 有明确有效期 |

#### 2.2.4 Google 自有受众：Affinity / In-Market / Life Events / Detailed Demographics

这些是 **Google 用机器学习模型基于大量行为信号生成的"意图/兴趣"受众**，不需要你提供任何数据，是**拓量**的王牌：

| 受众类型 | 逻辑 | 例子 | 适用 |
|---------|------|------|------|
| Affinity（兴趣受众） | 长期兴趣，宽泛 | "美食爱好者"、"健身爱好者" | 品牌曝光、心智种草 |
| In-Market（意向受众） | 近期购买意图（30 天内研究/准备购买） | "计划购车的人"、"计划订酒店的人" | 效果型、临门一脚 |
| Life Events（人生大事） | 近期人生变化 | 新婚、搬家、毕业、新生儿 | 场景化投放 |
| Detailed Demographics | 细粒人口（收入/教育/家长/婚姻） | "高收入、研究生学历" | 精准分层 |

```python
# 列出广告主可用的 Google 自有受众段（audience segments）
segments = api.dv360_list_audience_segments(advertiser_id)
for s in segments:
    print(f"[{s.get('segmentType')}] {s.get('displayName')} "
          f"size={s.get('estimatedAudienceSize')}")
```

**踩坑 3（盲目叠加受众导致 fill 骤降）**：营销人员把"In-Market：计划购车" + "Affinity：汽车" + "年龄 25-54" + "地域：加州某小城市" 全叠一起，受众规模从几百万骤降到几百，Line Item 几乎不出量。**解决**：先大后小——先用单一宽受众（如 In-Market 购车）观察出量再逐步加层；或用 reach forecast（`dv360_list_reach_forecasts` / `dv360_get_performance_forecast`）预估，过低再放宽。

#### 2.2.5 类似受众（Similar / Lookalike Audiences）

Lookalike 是"以种子人群为蓝本，用机器学习找出与之行为相似的全新用户"，是**扩量**的核心。

```python
# 以第一方高价值受众为种子，查询类似受众
lookalikes = api.dv360_list_audiences(advertiser_id, audience_type="LOOKALIKE")
for l in lookalikes:
    print(f"Lookalike: {l.get('displayName')} "
          f"seed={l.get('seedAudienceId')} "
          f"size={l.get('estimatedAudienceSize')}")
```

**Lookalike 的种子选择成败关键：**

| 种子质量 | 表现 | 建议 |
|---------|------|------|
| 高转化客户（已下单） | 最佳 | 首选购买过、价值高的用户 |
| 中价值（已注册/加购） | 好 | 作为中继拓量 |
| 低价值（访问未转化） | 差 | 慎用，lookalike 会继承低意图 |

**最佳实践**：Lookalike 种子要有一定规模（一般建议 ≥ 1,000 活跃种子用户），且要"纯"（只含高价值行为，不要混入无关流量），否则模型学到的是噪声。

### 2.3 定向组合逻辑：AND / OR / 正负结合

#### 2.3.1 层级聚合规则

DV360 的定向组合是**多级布尔逻辑**，目标合法集合 = （所有正定向 AND 交集）−（负定向排除）−（频控超限用户）。在同一个 Line Item 上，所有 `included` 定向维度之间是 **AND**；每个维度内部多值之间是 **OR**；所有 `excluded` 选项是 **NOT**；Advertiser 级设置会继承叠加到其下所有 IO 与 Line Item。

```
Advertiser 级别（继承到所有下级）
  排除: 敏感分类 / 成人内容
      │
      ▼ 叠加
Insertion Order 级别（继承到其下 Line Items）
  地域: US + CA + GB      (OR)
      │
      ▼ 叠加
Line Item 级别（最细粒度）
  正定向: 年龄 25-44 (OR)  +  In-Market: 购车 (AND)
  负定向: 排除 App = 竞品
      │
      ▼ 最终
   = 满足(地域 in {US,CA,GB}) AND 满足(年龄 in {25-44})
     AND 满足(In-Market 购车) AND NOT(敏感类目) AND NOT(竞品App)
```

**最容易踩的坑（层级继承导致的"意外定向"）**：在 Advertiser 级别设了地域 = {US}，结果在某个线项想投加拿大时发现永远不出量——因为没有意识到上级定向会**继承叠加**下来。排查时一定要"向上看三层"多层级定向。

#### 2.3.2 为什么要"正负结合"

正定向负责"精准圈人"，负定向负责"低价/低质/竞品/风险排除"。二者结合，策略才完整：

| 正定向（要） | 负定向（不要） |
|-------------|--------------|
| In-Market 购车 | 排除 18-24 岁销量低的细分 |
| 地域：一线城市 | 排除竞品站点/应用 |
| 设备：iPhone | 排除 in-app 激励流量 |
| 兴趣：汽车 | 排除低可见性库存 |

### 2.4 频率控制（Frequency Capping）机制

#### 2.4.1 频控的三个基本维度

1. **频控单位（scope）**：作用范围是"每个用户"（per user）。
2. **频控层级（level）**：在哪个对象粒度做频控——`per Line Item`、`per Insertion Order`、`per creative` 等。
3. **窗口（window）**：在什么时间窗口计数——`hourly`、`daily`、`weekly`、`campaign lifetime` 等。

```
Frequency Cap 配置示例
├── 层级: Line Item 级别
├── 限制: 最多 3 次 / 每 24 小时 (per user)
├── 附加:
│     ├── 是否对 view-through 也计量
│     ├── 是否跨 insertion order 去重 (deduplicate within IO)
│     └── 若干天内的总频控 (如 10 次 / 7 天)
└── 计量事件:
      ├── impression (展示)
      └── completed view (完播)
```

#### 2.4.2 频控为什么重要

- **品牌类**：太高的频次（如 10+ 次/天）会让用户厌烦，提升"广告盲区"与负品牌情绪；频控太低则曝光浪费、Reach 不足。
- **效果类**：频控影响转化路径——太低的频控会导致用户还没完成转化就被掐掉。

```
转化率 / 有效曝光 vs 频次
转化率
 │          ╭── 边际效用递减甜区（通常 2-4 次/周）
 │        ╭╯
 │      ╭╯
 │   ╭─╯
 │  ╭╯
 │ ╭╯
 │╭╯
 └───────────────────────▶ 展示频次
       转化甜区               过饱和区(浪费/厌烦)
```

**踩坑 4（频控单位用错）**："per Line Item 3 次/天"与另一个预算接近的 Line Item 各设一个，同一个用户在两个线项上被各看 3 次，总计 6 次/天。**解决**：需要跨线项统一的频控时，把频控设在 **Insertion Order 级别**，勾选 "deduplicate within insertion order"。

**踩坑 5（频控导致 fill 崩）**：视频投放设了"每个用户 1 次 / 每小时"，用户一小时内只可被展示一次，大幅压缩可投库存，出量暴跌。

#### 2.4.3 从"0 到 N"的频控演进实践

**阶段 0：不设频控**（冷启动观察自然频次），投放 1-2 天，观察每个用户的实际频次分布（报表 impressions / unique users）。如果 unique users 占比低（一个人反复被轰炸）就要尽快上频控。

**阶段 1：极简频控**（建议起点）`per Line Item：每天 3 次 / 用户`，控制明显超频同时不限制冷启动数据收集。

**阶段 2：分角色频控**（跑数据后）品牌曝光类 `3-5 次 / 周`；效果转化类 `4-8 次 / 月窗口 + 每日 2-3 次`；临门一脚重定向 `最多 4 次 / 天` 配 3 天冷却。

**阶段 3：跨 IO 去重 + 复杂窗口** IO 级频控 + deduplicate within IO，配多种窗口（daily + weekly + lifetime）组合。

### 2.5 Go 实现定向匹配引擎

下面给出一个**生产级可参考的 Go 定向匹配引擎**实现，把"品牌安全过滤 → 负向排除 → 正向 AND/OR 交集 → 频控计数 → 竞价"翻译成真实代码，用**倒排索引**做高效定向查询、做交集判断、做频控计数（窗口 + 过期重置）。

```go
package targeting

import (
    "fmt"
    "sync"
    "time"
)

// ============ 基础类型 ============

type TargetType int

const (
    TypeKeyword TargetType = iota
    TypeCategory
    TypeGeo
    TypeAge
    TypeGender
    TypeAudience
    TypeApp
    TypeDevice
    TypeOS
    TypeContentExclusion
)

// TargetCondition 一条定向选项
type TargetCondition struct {
    Type      TargetType
    OptionID  string   // 目标选项 ID（对应 targetingOptionId）
    IsExclude bool     // true=负向排除, false=正向
}

// TargetingUnit 定向单位
type TargetingUnit struct {
    ID         string
    Name       string
    Conditions []TargetCondition
}

// ============ 竞价请求 ============

// BidRequest 进入定向引擎的竞价请求（简化）
type BidRequest struct {
    UserID       string
    Geo          string
    Age          string
    PageKeywords []string
    Categories   []string
    App          string
}

// ============ 倒排索引 ============

// InvertedIndex 倒排索引: 定向条件值 -> 命中的 Line Item 集合
type InvertedIndex struct {
    mu      sync.RWMutex
    keyword map[string]map[string]bool
    cat     map[string]map[string]bool
    geo     map[string]map[string]bool
    age     map[string]map[string]bool
    aud     map[string]map[string]bool
}

func NewInvertedIndex() *InvertedIndex {
    return &InvertedIndex{
        keyword: map[string]map[string]bool{},
        cat:     map[string]map[string]bool{},
        geo:     map[string]map[string]bool{},
        age:     map[string]map[string]bool{},
        aud:     map[string]map[string]bool{},
    }
}

// AddLineItem 注册一个 Line Item 的正向定向到索引
func (idx *InvertedIndex) AddLineItem(lineItemID string, cond TargetCondition) {
    idx.mu.Lock()
    defer idx.mu.Unlock()
    if cond.IsExclude {
        return // 负向不建正向索引
    }
    var bucket map[string]map[string]bool
    switch cond.Type {
    case TypeKeyword:
        bucket = idx.keyword
    case TypeCategory:
        bucket = idx.cat
    case TypeGeo:
        bucket = idx.geo
    case TypeAge:
        bucket = idx.age
    case TypeAudience:
        bucket = idx.aud
    default:
        return
    }
    if bucket[cond.OptionID] == nil {
        bucket[cond.OptionID] = map[string]bool{}
    }
    bucket[cond.OptionID][lineItemID] = true
}

// ============ 频控计数 ============

// FrequencyCounter 频控计数: userID -> {lineItemID -> 窗口计数}
type FrequencyCounter struct {
    mu   sync.Mutex
    data map[string]map[string]*Window
}

type Window struct {
    start time.Time
    count int
}

func NewFrequencyCounter() *FrequencyCounter {
    return &FrequencyCounter{data: map[string]map[string]*Window{}}
}

// Incr 递增窗口计数，返回是否超限
func (fc *FrequencyCounter) Incr(userID, lineItemID string, cap int, win time.Duration) bool {
    fc.mu.Lock()
    defer fc.mu.Unlock()
    if fc.data[userID] == nil {
        fc.data[userID] = map[string]*Window{}
    }
    w, ok := fc.data[userID][lineItemID]
    now := time.Now()
    if !ok || now.Sub(w.start) > win {
        w = &Window{start: now, count: 0}
        fc.data[userID][lineItemID] = w
    }
    w.count++
    return w.count > cap // true 表示已超限，应禁用
}

// ============ 定向匹配引擎主逻辑 ============

type TargetingEngine struct {
    index         *InvertedIndex
    freq          *FrequencyCounter
    lineItemConds map[string][]TargetCondition
}

func NewTargetingEngine() *TargetingEngine {
    return &TargetingEngine{
        index:         NewInvertedIndex(),
        freq:          NewFrequencyCounter(),
        lineItemConds: map[string][]TargetCondition{},
    }
}

func (e *TargetingEngine) Register(lineItemID string, conds []TargetCondition) {
    e.lineItemConds[lineItemID] = conds
    for _, c := range conds {
        e.index.AddLineItem(lineItemID, c)
    }
}

// Match 对一个竞价请求做定向匹配，返回可参与竞价的 lineItemID 列表
func (e *TargetingEngine) Match(req BidRequest) []string {
    candidateSet := map[string]bool{}
    first := true
    merge := func(bucket map[string]map[string]bool, vals []string) {
        if len(vals) == 0 {
            return
        }
        hit := map[string]bool{}
        for _, v := range vals {
            for id := range bucket[v] {
                hit[id] = true
            }
        }
        if first {
            for id := range hit {
                candidateSet[id] = true
            }
            first = false
        } else {
            for id := range candidateSet {
                if !hit[id] {
                    delete(candidateSet, id)
                }
            }
        }
    }
    merge(e.index.keyword, req.PageKeywords)
    merge(e.index.cat, req.Categories)
    merge(e.index.geo, []string{req.Geo})
    merge(e.index.age, []string{req.Age})

    result := []string{}
    for id := range candidateSet {
        if e.validate(id, req) {
            result = append(result, id)
        }
    }
    return result
}

// validate 校验单个 Line Item 的所有定向（含负向 + 频控）
func (e *TargetingEngine) validate(lineItemID string, req BidRequest) bool {
    conds := e.lineItemConds[lineItemID]
    // 负向优先：命中任一排除即返回 false
    for _, c := range conds {
        if c.IsExclude && e.condMatch(c, req) {
            return false
        }
    }
    // 频控检查（演示 daily cap = 3）
    const dailyCap = 3
    if e.freq.Incr(req.UserID, lineItemID, dailyCap, 24*time.Hour) {
        return false
    }
    return true
}

// condMatch 判断请求是否命中某条条件（按 Type 分发）
func (e *TargetingEngine) condMatch(c TargetCondition, req BidRequest) bool {
    switch c.Type {
    case TypeGeo:
        return req.Geo == c.OptionID
    case TypeAge:
        return req.Age == c.OptionID
    case TypeKeyword:
        for _, kw := range req.PageKeywords {
            if kw == c.OptionID {
                return true
            }
        }
    case TypeCategory:
        for _, cat := range req.Categories {
            if cat == c.OptionID {
                return true
            }
        }
    }
    return false
}

func main() {
    eng := NewTargetingEngine()
    eng.Register("LI-1001", []TargetCondition{
        {Type: TypeAudience, OptionID: "IN_MARKET_CAR", IsExclude: false},
        {Type: TypeGeo, OptionID: "US", IsExclude: false},
        {Type: TypeContentExclusion, OptionID: "GAMBLING", IsExclude: true},
    })
    req := BidRequest{UserID: "u-1", Geo: "US", Age: "30-34",
        PageKeywords: []string{"car"}, Categories: []string{"IAB2"}}
    hits := eng.Match(req)
    fmt.Printf("eligible line items: %v\n", hits)
}
```

**代码要点说明：**
1. **倒排索引召回**：用 `条件值 -> lineItem集合` 的倒排结构快速缩小候选，避免全量扫描，支撑高 QPS。
2. **AND 并集/交集合并**：跨维度做交集（`merge` 中保留 candidateSet），维度内多值并用 `for v := range vals` 收集 OR 命中。
3. **负向优先**：在 `validate` 中最先扫描排除项，命中即短路返回，避免无效计算。
4. **频控计数**：以 `window + count` 表示"某用户在窗口内的计数"，窗口过期自动重置，`Incr` 返回是否超限；生产环境应换成 Redis `HASH`/`INCRBY` + 过期 key。
5. **可扩展性**：新增维度只需在 `TargetType` 加枚举、`InvertedIndex` 加 bucket、`condMatch` 加分支。

**关于 reach 预估**：脚本中暂未实现 `dv360_estimate_reach`，可用 `dv360_list_reach_forecasts` / `dv360_get_performance_forecast` / `dv360_list_frequency_forecasts` 作为预估入口，在投放前预判圈层规模（预判 fill 风险）。

### 2.6 内容排除与品牌安全分类

#### 2.6.1 品牌安全在 DV360 的实现层次

品牌安全不是单一开关，而是**多层防线叠加**。第一层**内容排除（Content Exclusion）**：排除整类不想要的内容类型（成人、赌博、暴力、仇恨言论/敏感政治、非法/毒品）。第二层**品牌安全分类（Brand Safety Categories）**：DV360 内置的细粒度分类（物化女性、军事冲突、敏感健康医疗、新闻与政治）。第三层**第三方校验**（Integral Ad Science / DoubleVerify）见 `dv360_list_ad_verification_services` / `dv360_list_viewability_providers`。第四层**卖方侧设置**通过交易/私市只买安全认证库存。

#### 2.6.2 API 封装方法

```python
# 列出当前内容排除项
exclusions = api.dv360_list_content_exclusions(advertiser_id)
for ex in exclusions:
    print(f"排除: {ex.get('displayName')} category={ex.get('exclusionCategory')} "
          f"status={ex.get('status')}")

# 新建一条内容排除（排除赌博与成人内容）
resp = api.dv360_create_content_exclusion(
    advertiser_id,
    categories=["GAMBLING", "ADULT"],
    target_type="excluded",
)
print("created:", resp)

# 删除内容排除
api.dv360_delete_content_exclusion(exclusion_id=resp.get('id'))

# 列出可用品牌安全分类
brand_cats = api.dv360_list_brand_safety_categories()
for bc in brand_cats:
    print(f"  [{bc.get('code')}] {bc.get('name')}")
```

**内容排除 vs 站点分类定向的配合：** 站点分类定向（site category targeting）是正向圈"我要的类别"；内容排除（content exclusion）是负向剔"我绝对不能要的"，优先级最高。安全策略通常是**正向对准品牌相关分类 + 负向排除所有高风险分类**。

#### 2.6.3 品牌安全配置的坑

**踩坑 6（品牌安全过严导致出量不足）**：小众品牌把所有敏感分类全勾掉（新闻、政治、健康、娱乐全排），最终可投库存所剩无几、reach 严重缩水。**解决**：品牌安全要与出量目标平衡，用"分级防线"（核心必排：成人/赌博/暴力；可选优排：新闻/政治按目标定），叠加第三方校验而非一刀切。

**踩坑 7（第三方校验成本与延迟）**：接入 IAS/DV 做第三方校验会带来额外 CPM 成本与延迟，且可能把一些合法但温和的库存也拦下来。要权衡品牌保护的边际收益与成本/出量损失。

### 2.7 地域 / 设备 / 操作系统等维度的深层逻辑

#### 2.7.1 地域定向（Geo）

`dv360_list_geo_targeting_detail(targeting_id)` 返回地理定向的详情（国家/州/城市/DMA/邮编/半径）。

```
地域定向粒度
├── 国家 (Country)
├── 州/省 (State/Province)  -> 美国州, 中国省
├── 城市 (City)
├── DMA (Designated Market Area)
├── 邮编 (Postal/ZIP code)
└── 半径 (Radius，围绕某地点的距离)
```

**踩坑 8（geo 粒度过细导致 fill 低）**：精确到"美国纽约某邮编 + 半径 5 英里"，可投人数太小、fill 极低。**解决**：先国家/州级拓量，确认出量后再用 DMA/城市细分，且用多城市并集（OR）而非单一细粒度。

#### 2.7.2 设备与操作系统

- `dv360_list_device_targeting_detail(targeting_id)`：设备类型（手机/平板/桌面/电视/车载）定向详情。
- `dv360_list_os_targeting_detail(targeting_id)`：操作系统（Android/iOS/Windows/macOS）详情。
- `dv360_list_operating_systems()` / `dv360_list_device_types()`：选项列表。

**设备定向与创意格式强相关**：视频在电视/手机设备上的可用性不同；富媒体/HTML5 对桌面更友好。底层常要求**设备定向 + 版式定向 + 设备适配创意**三者匹配。

#### 2.7.3 其他细节维度

- **Dayparting（时段定向）**：对一天中的时段做定向（如"下班后 18-22 点"），常用于生活消费品/游戏。
- **连接类型**：`dv360_list_connection_types()`，WIFI/4G/5G 区分，常用于高带宽场景允许更大体积创意。

**人口统计（Demographics）注意点**：DV360 的人口统计定向基于**推断或可得出数据**，在隐私受限环境/无 Cookie 情况下覆盖率会下降。把它当"倾向性信号"而非"硬条件"，否则会进一步压缩可投人群。

---

## 三、生产环境实战

### 3.1 品牌出海地域+受众组合定向案例

**业务背景**：某国产智能家居品牌出海美国，主打"高端智能门铃"，目标人群是"美国家庭房主"，希望在预算有限的情况下最大化高效出量与转化。

**初始配置（过度定向）——错误示范：**

```
Line Item: US 智能门铃
├── 地域: 美国纽约市 (单一城市)
├── 年龄: 35-50
├── 受众: In-Market 家居安防 (AND)
├── 设备: iPhone 仅 (AND)
├── 兴趣: Affinity 家居 (AND)
└── 排除: 成人/赌博/暴力
```

**问题**：五层 AND 叠加后人群规模极小，加上手机仿用户有限，fill 接近 0，投放 72 小时只有几百次展示，CPM 虚高（因为可拍卖库存少导致竞价激烈但出量少）。

**优化后的分层策略（正确示范）：**

```
策略分 3 个 Line Item，各司其职
├── LI-A 拓量层 (60% 预算)
│   ├── 地域: 美国 (全国, 州级并集)
│   ├── 受众: In-Market 家居安防 (单一宽受众)
│   ├── 设备: 全部设备
│   └── 排除: 成人/赌博/暴力 + 竞品站点
│
├── LI-B 精准层 (30% 预算)
│   ├── 地域: 美国 Top 15 DMA (OR 并集)
│   ├── 受众: 第一方高价值访客 (Floodlight 重定向)
│   ├── 年龄: 30-54
│   └── 设备: 手机+桌面
│
└── LI-C 品牌安全层 (10% 预算)
    ├── 地域: 美国
    ├── 受众: Lookalike(以高转化种子为蓝本)
    └── 品牌安全: IAS 第三方校验 + 严格内容排除
```

**结果**：拓量层出量充足、积累了 Retargeting 种子；精准层把重定向用户高效转化；品牌安全层用 Lookalike 拓新客。整体 fill 提升数倍、CPM 回落、ROI 改善。

**可复用的"漏斗分层层级"心智：**

| 层级 | 预算 | 定向策略 | 目标 |
|------|------|---------|------|
| 拓量层 | 大 | 宽 In-Market / Lookalike | 大量触达、积累种子 |
| 精准层 | 中 | 第一方重定向 + 硬人口条件 | 高效转化 |
| 品牌安全层 | 小 | Lookalike + 严格品牌安全 | 拓新客不打折品牌 |

### 3.2 Retargeting 与 Lookalike 配置实战

#### 3.2.1 Retargeting 配置

```python
# 步骤 1: 确认重定向需要的动态受众/Floodlight
dyn = api.dv360_list_dynamic_audiences(advertiser_id)
visit_audience_id = None
for d in dyn:
    if "网站访客" in d.get("displayName", ""):
        visit_audience_id = d.get("audienceId")

# 步骤 2: 建 Retargeting Line Item（正定向=该受众 + 排除已转化）
recency_window = 30  # 30 天内访问过的人

resp = api.dv360_create_line_item(
    advertiser_id,
    name="Retargeting 30d 访客",
    flight={"dateRange": {"startDate": current_day, "endDate": end_day}},
    targeting={
        "audience": {"included": [visit_audience_id], "excluded": [converter_audience_id]},
        # 排除已下单人群，避免浪费
    },
)
```

**Retargeting 最佳实践：**
- **排除已转化人群**：重定向访客时务必排除已下单用户，否则重复触达浪费预算。
- **设频控**：重定向人群小，易被反复轰炸，务必加频控（如 2-3 次/天 + 冷却窗口）。
- **阶段分离**：按漏斗把访问（浅层）与加购/结账（深层）分开成不同 Line Item，用不同创意与频控。

#### 3.2.2 Lookalike 配置

```
Lookalike 配置要点
├── 种子: 高价值转化用户（最近 30-90 天下单、高客单价）
├── 规模: 种子 ≥ 1,000 活跃用户
├── 比例: 1% ~ 5%(相似度越高但越小) => 平衡扩量与精准
├── 频控: 设每日上限防止过度轰炸
└── 监控: 每组 Lookalike 单独观察 CTR/CVR，淘汰表现差的
```

**Lookalike 的"1% vs 5%"取舍：**

| 比例 | 相似度 | 人群大小 | 效果倾向 | 建议 |
|------|--------|---------|---------|------|
| 1% | 极高 | 很小 | 高转化、低曝光 | 精准执行 |
| 3% | 高 | 中 | 平衡 | 常用起点 |
| 5% | 中 | 大 | 更广、稍弱 | 拓量阶段 |

### 3.3 频控从 0 到 N 的演进实战

以一个"品牌 + 效果混合"账户为例，讲述频控的落地过程：

**第 1 周（冷启动，频控=0）**
- 不设频控，投放 3-5 天收集频次分布。
- 用报表看 `impressions` 与 `unique users`，计算平均频次 = impressions / unique users。
- 假设观测到平均频次 8 次/周，远超健康值 → 触发频控紧急干预。

**第 2-4 周（基础频控上量）**
- 品牌类：`per Line Item 3 次/周`。
- 效果类：`per Line Item 2 次/天 + 5 次/周`。
- 观察频次分布回落、转化/有效曝光改善。

**第 5-8 周（精细化）**
- 把重复严重的两个线项合并，频控移到 **Insertion Order 级别**，勾选 deduplicate within IO，实现跨线项统一频次。
- 加"窗口组合"：daily 2 + weekly 4 + lifetime 12。

**长期（治理）**
- 建立"频次健康度"报表与告警：若某线项平均频次长期高于目标 1.5 倍且转化未升 → 收紧频控。
- 结合 creative rotation，防止同一创意重复轰炸。

```
频控演进时间线
Day0        Day7        Day30       Day60
│ 冷启动      │ 基础频控    │ 精细化      │ 治理
│ 频控=0      │ daily/week  │ IO级+去重   │ 告警+报表
│ 观测频次     │ 观察回落     │ 多窗口组合   │ 自动化
```

### 3.4 定向投放的完整操作清单（Checklist）

**投放前：**
- [ ] 确定投放目标（品牌曝光 / 转化 / 拓客）
- [ ] 用 reach forecast 预估目标圈层规模（预判 fill）
- [ ] 检查/刷新第一方受众状态与有效期
- [ ] 确认品牌安全防线（内容排除 + 是否接第三方校验）
- [ ] 在最低粒度（Advertiser/IO/LineItem）规划定向层级继承

**投放中（每天/每周）：**
- [ ] 监控 fill rate 与出量：若出量低，逐层放宽定向（先宽受众，再三减 And 层）
- [ ] 监控频次分布：超标则收紧频控
- [ ] 定期检查受众是否过期
- [ ] 看排除是否误伤：正常量下降但无明确原因时检查是否排除项过广

**投放后（复盘）：**
- [ ] 分析各定向维度贡献（分维度报表）
- [ ] 找出表现差的维度并加排除
- [ ] 培植高价值种子 → 更新 Lookalike 种子
- [ ] 沉淀"定向策略模板"供下次复用

### 3.5 踩坑经验汇总（生产环境）

| # | 坑 | 现象 | 根因 | 解法 |
|---|-----|------|------|------|
| 1 | 分类粒度过粗 | CTR 低、无效曝光 | 粗分类语义宽泛 | 加二级分类+关键词 |
| 2 | 受众过期 | 静默不出量 | CSV 列表到期未刷新 | 监控 status/到期日，定时刷新 |
| 3 | 盲目叠加受众 | fill 骤降 | AND 越多库存越少 | 先大后小 + forecast 预估 |
| 4 | 频控单位用错 | 超预期频次 | per-LI 各自计数 | 频控移 IO 级 + 去重 |
| 5 | 频控过严 | 出量崩 | 每小时 1 次太狠 | 放宽窗口/升级 |
| 6 | 品牌安全过严 | 出量不足 | 全敏感类目全排 | 分级防线+第三方而非一刀切 |
| 7 | 第三方校验 | 成本高/出量降 | 校验拦截过度 | 权衡收益与成本 |
| 8 | Geo 粒度过细 | fill 极低 | 单一城市+半径 | 先州/全国，多城市并集 |
| 9 | 层级继承 | 意外不出量 | 上级定了地域/受众 | 排查向上看三层 |
| 10 | 排除没生效 | 仍投到不想要的 | 排除在错误层级/未保存 | 检查层级与 included/excluded |

---

## 四、常见问题与排查
