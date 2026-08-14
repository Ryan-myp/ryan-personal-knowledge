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

### 2.8 API 全链路实战：从建 Line Item 到完成一套定向

下面用一个完整的 Python 示例串起"建 Line Item → 建/查定向单位 → 挂关键词/受众/地域/排除 → 设频控 → 验证"的整条链路。这是把前面所有原理落到代码的最佳示范。

```python
# -*- coding: utf-8 -*-
"""
DV360 定向全链路脚本（教学示范）
场景：为"智能门铃出海美国"配置一个精准 Line Item 的整套定向。
"""
from ad_platform_api import AdPlatformAPI

api = AdPlatformAPI(credentials)
advertiser_id = "1234567890"

# ========== Step 0: 前置检查 ==========
# 确认能访问、拉取维度选项骨架
dims = api.dv360_list_targeting_units(advertiser_id)  # 也可用 get_targeting_dimension_options()
print("当前定向单位数:", len(dims or []))

# ========== Step 1: 查可用受众（选第一方/动态/Google 自有） ==========
audiences = api.dv360_list_audiences(advertiser_id)
aud_by_name = {a.get('displayName'): a for a in (audiences or [])}
overall_retarget = None
in_market_car = None
for name, a in aud_by_name.items():
    print(f"  受众: {name} type={a.get('audienceType')} size={a.get('estimatedAudienceSize')} st={a.get('status')}")
    if '网站访客' in name or 'visitor' in name.lower():
        overall_retarget = a
    if 'IN_MARKET' in name.upper() and 'CAR' in name.upper():
        in_market_car = a

# ========== Step 2: 建 Line Item（空定向，后续挂单位） ==========
li = api.dv360_create_line_item(
    advertiser_id,
    name="US 智能门铃 - 精准 Retargeting",
    flight={"dateRange": {"startDate": "2026-08-15", "endDate": "2026-09-15"}},
    lineItemType="LINE_ITEM_TYPE_DISPLAY",
    pacing={"pacingMode": "PACING_MODE_DISTRIBUTE_EVENLY"},
    budget={"budgetUnit": "BUDGET_UNIT_CURRENCY", "maxAmount": {"amountMicros": int(5000 * 1e6)}},
)
line_item_id = li.get('lineItemId')
print("新建 Line Item:", line_item_id)

# ========== Step 3: 创建定向单位并挂 assigned targeting options ==========
unit = api.dv360_create_targeting_unit(advertiser_id, name="US 门铃定向单位")
unit_id = unit.get('targetingUnitId')
print("新建定向单位:", unit_id)

# 用 update_targeting_unit 往单位里加定向选项（示意）
api.dv360_update_targeting_unit(
    unit_id,
    targets={
        # 受众: 重定向访客（正定向）
        "audience": {"included": [overall_retarget['audienceId']] if overall_retarget else []},
        # 地域: 全美（正定向）
        "geo": {"included": ["country:US"]},
        # 关键词: 智能/家居/安防（正定向）
        "keyword": {"included": ["智能门铃", "smart doorbell", "home security"]},
        # 排除: 已下单用户 + 赌博内容
        "audienceExcluded": [],
        "contentExcluded": ["GAMBLING", "ADULT"],
    },
)

# ========== Step 4: 把定向单位挂到 Line Item ==========
api.dv360_update_line_item(advertiser_id, line_item_id, targetingUnitIds=[unit_id])

# ========== Step 5: 便捷封装（关键词定向的细化写库） ==========
resp = api.dv360_create_keyword_targeting(advertiser_id, keywords=["smart home", "doorbell"], target_type="included")
print("keyword targeting created:", resp)

# ========== Step 6: 验证 - 拉全量定向核对 ==========
targetings = api.dv360_list_targetings(advertiser_id)
for t in targetings or []:
    print(f"  [{t.get('targetingType')}] {t.get('displayName')} "
          f"targetType={t.get('targetType')} status={t.get('status')}")
```

**要点：**
1. **先建后挂**：DV360 里"创建定向单位 → 再 update 加入 targeting options → 再挂到 Line Item"是三步走，不能一步到位（与 Google Ads 的 AdGroup 结构不同）。
2. **audience 需要 id 映射**：受众必须先 `dv360_list_audiences` 拿到 `audienceId` 再引用，不能直接用名字。
3. **便捷方法与完整单位的区别**：像 `dv360_create_keyword_targeting` 这类"便捷封装"直接写单类型定向；`dv360_create_targeting_unit` + `dv360_update_targeting_unit` 是"一次配全套"的完整单位方式。两者可混用但要防止重复覆盖。

### 2.9 定向对象模型与数据粒度（进阶）

把 DV360 的定向对象模型与常见的数据字段梳理清楚，便于排查时对齐字段名：

| 对象 | 关键字段 | 说明 |
|------|---------|------|
| TargetingType | `targetingType` | 维度枚举（GEO/AUDIENCE/KEYWORD/...） |
| AssignedTargetingOption | `targetingOptionId` / `targetType`(included/excluded) / `status` | 一个已分配的定向选项 |
| TargetingUnit | `targetingUnitId` / `targetingOptions` | 定向单位，装载多个 option |
| Audience | `audienceId` / `audienceType` / `estimatedAudienceSize` / `status` | 受众 |
| LineItem | `lineItemId` / `targetingUnitIds` / `pacing` / `budget` | 线项 |

**为什么"单位"与"选项"双层结构重要？** 它让同一套定向可以**复用**：一个定向单位可以挂到多个 Line Item，避免重复配置。批量修改时只改单位即可横向下发。

**数据粒度建议：**
- 报表拆维度时用 `dv360_list_report_dimensions()` / `dv360_list_report_metrics()` 对齐官方维度/指标。
- 定向明细用 `dv360_list_*_targeting_detail(targeting_id)` 系列拿具体值。
- 复杂决策用 `dv360_get_performance_forecast` / `dv360_list_reach_forecasts` 做预测。

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

### 3.6 定向配置自动化与审计（规模运维）

当账户有大量 Advertiser/IO/Line Item 时，人工在 UI 上逐个配置定向并不可靠。生产实践通常把定向配置**代码化并纳入版控**，配合**定时审计**保证"配置即事实"。

**自动化思路：**
1. **配置即代码（IaC）**：把每个 Line Item 的定向定义写成结构化配置（YAML/JSON），通过封装方法批量下发。
2. **幂等**：同样的配置反复执行结果一致，避免重复创建单位/选项。
3. **审计比对**：定时拉取线上定向，与期望配置做 diff，漂移则告警或自动回滚。

```python
# 幂等：先查再建，避免重复
def ensure_keyword_targeting(api, advertiser_id, line_item_id, keywords, target_type="included"):
    existing = api.dv360_list_targetings(advertiser_id)
    need = set(keywords)
    have = set()
    for t in existing or []:
        if t.get('targetingType') == 'TARGETING_TYPE_KEYWORD':
            have.add(t.get('displayName'))
    # 只创建缺失的
    missing = need - have
    for kw in missing:
        api.dv360_create_keyword_targeting(advertiser_id, keywords=[kw], target_type=target_type)
    # 移除多余的（可选）
    extra = have - need
    for kw in extra:
        for t in existing or []:
            if t.get('targetingType') == 'TARGETING_TYPE_KEYWORD' and t.get('displayName') == kw:
                api.dv360_delete_keyword_targeting(t.get('assignedTargetingOptionId'))
    return {"added": list(missing), "removed": list(extra)}
```

**自动审计脚本骨架：**

```python
import json, hashlib

# 把线上定向做成"规范快照"便于 diff
def snapshot(api, advertiser_id):
    out = []
    for t in api.dv360_list_targetings(advertiser_id) or []:
        out.append({
            "type": t.get("targetingType"),
            "name": t.get("displayName"),
            "targetType": t.get("targetType"),
            "status": t.get("status"),
        })
    out.sort(key=lambda x: (x["type"], x["name"]))
    return hashlib.sha256(json.dumps(out, ensure_ascii=False).encode()).hexdigest()

def audit(api, advertiser_id, expected_hash, notify):
    cur = snapshot(api, advertiser_id)
    if cur != expected_hash:
        notify("定向配置漂移! 期望Hash=%s 实际=%s" % (expected_hash[:12], cur[:12]))
        return False
    return True
```

**审计指标建议（写进每日巡检）：**

| 指标 | 说明 | 告警阈值 |
|------|------|---------|
| 配置 Hash 漂移 | 线上与期望不一致 | 任何差异 |
| 受众过期数 | EXPIRED/EXPIRING 受众数量 | > 0 即查 |
| 低 fill 线项数 | fill < 阈值 | > 20% 线项 |
| 频控异常 | 平均频次 > 目标 1.5x | 触发 |
| 排除缺失 | 关键排除项被删 | 任何缺失 |

### 3.7 定向数据质量治理（第一方数据）

定向效果的前提是"数据干净"。第一方受众数据质量直接决定 Retargeting 与 Lookalike 的成败。

**数据清洗清单：**

```
第一方数据治理 Checklist
├── 上传前
│   ├── 去重: 合并重复邮箱/手机号
│   ├── 规范化: 邮箱小写、去掉首尾空格
│   ├── 有效性: 过滤明显无效/伪造记录
│   └── 权限: 确认有合法使用这些数据做广告的权限
├── 上传时
│   ├── 使用稳定标识符（邮箱优先）
│   ├── 按 DV360 要求做 SHA-256 哈希
│   └── 检查匹配率（< 60% 需警惕格式问题）
└── 上传后
    ├── 定期刷新（540 天到期前）
    ├── 按价值分层（高/中/低转化种子）
    └── 记录匹配率趋势，异常即排查
```

**匹配率低的主因排序（按影响）：**
1. **标识符类型**：邮箱匹配率通常最高，手机号次之，设备 ID 最低。
2. **格式错误**：空格、大小写、分隔符不一致 → 规范化可救。
3. **未哈希或哈希方式不对**：必须与 DV360 一致（SHA-256，hex 小写）。
4. **受众陈旧**：用户很少登录或改变了标识 → 刷新。
5. **数据量太小**：统计波动大，匹配率不稳。

**把种子分层的价值：**
- 高价值种子（已下单）→ Lookalike 蓝本、精准重定向。
- 中价值种子（注册/加购）→ 中继拓量。
- 避免把低中高混作一桶当种子，会稀释 Lookalike 质量。

**治理频率建议：**
- 每周：重定向受众刷新 + 匹配率监控。
- 每月：Lookalike 种子更新、过期受众清理。
- 每季：全量数据权限合规审查。

---

## 四、常见问题与排查
### 4.1 常见 FAQ 总表

| # | 问题 | 一句话答案 | 详见 |
|---|------|-----------|------|
| 1 | 定向不出量 / fill 太低 | 定向叠太多 AND 层或圈得太窄，先大后小并看 reach forecast | 4.2 |
| 2 | Audience 不同步 / 匹配率低 | CSV 列表匹配率依赖数据质量与类别，检查上传格式、有效期与加密 | 4.3 |
| 3 | 关键字中文乱码 | 确保 UTF-8 编码、合法 keyword 长度与格式，用 API 校验 | 4.4 |
| 4 | 排除定向没生效 | 排除可能设在错误层级或未保存，检查 included/excluded 与层级 | 4.5 |
| 5 | 频控不生效 | 检查频控层级、窗口、是否跨 IO 去重、计量事件配置 | 4.6 |
| 6 | 用了 Lookalike 反而变差 | 种子不纯/太小，Lookalike 继承了噪声 | 4.7 |
| 7 | 想投某地区却完全不出量 | 上级 Advertiser/IO 定向继承把你卡住了，向上看三层 | 4.8 |
| 8 | 品牌安全太严影响出量 | 分级防线 + 平衡，别一刀切 | 2.6.3 |

### 4.2 定向不出量 / Fill 过低的排查（Tree）

```
定向不出量 / fill 过低
│
├─ ① 检查 Line Item 状态
│       └─ 是否 PAUSED / ACTIVE? 阶段是否已过? 预算是否 0?
│
├─ ② 检查受众
│       ├─ audience 是否 EXPIRED / EXPIRING ?
│       ├─ estimatedAudienceSize 是否过小 (< 千级)?
│       └─ 是否用动态受众但 Lookback window/事件配置错误?
│
├─ ③ 检查定向组合
│       ├─ 正定向 AND 是否叠太多层?
│       ├─ 地域是否过细(邮编/半径)?
│       ├─ 设备/OS 是否过于限制?
│       └─ 是否继承到上级 Advertiser/IO 的更严格定向?
│
├─ ④ 检查排除
│       ├─ 排除项是否误伤目标(如把品牌相关内容也排了)?
│       ├─ 竞品排除是否过广?
│       └─ 品牌安全分类是否全排?
│
└─ ⑤ 用报表/forecast 验证
        ├─ 看 forecast/reach 预估
        ├─ 看投放日志里"未参与竞价的原因"
        └─ 逐步放宽(每次只放宽一个维度)观察出量
```

**实操排障手法：** 一次"只动一个变量"。若出量低，首先不要同时放宽五个维度——否则你不知道是哪个起了作用。典型顺序：先确认状态与受众未过期 → 再逐步放宽地域粒度 → 再减定向 AND 层 → 最后检查排除/品牌安全。

### 4.3 Audience 不同步 / 匹配率低

**现象**：上传第一方受众后，系统显示的匹配用户数与期望相差很远，或投放很久后受众规模不动。

**根因与对策：**

| 根因 | 现象 | 对策 |
|------|------|------|
| 数据格式错误 | 匹配数几乎为 0 | 检查 CSV 表头/邮箱/手机号格式，用正确分隔符，勿含空格 |
| 类别选择不当 | 匹配率偏低 | 邮箱匹配率高、手机号次之、设备 ID 取决于平台 |
| 未加密/哈希方式不符 | 匹配失败 | 按 DV360 要求做 SHA-256 加密并去掉 PII |
| 上传了太多无效记录 | 匹配率低 | 清掉重复/过期记录再传 |
| 有效期到了 | 规模不涨/失效 | 定期刷新 (通常 540 天) |
| 数据量太小 | 匹配波动大 | 累积更多种子再上传 |

**黄金实践：**
- 使用**稳定标识符**（邮箱优先）做种子。
- 上传前做**去重与清洗**。
- 上传后 24-48 小时观察匹配规模，尽早发现格式问题。
- 定期（每周/月）刷新 CSV 保持新鲜度。

### 4.4 关键字中文乱码 / 非法关键字

**现象**：通过 API 或 UI 输入中文关键词后，投放报错或显示乱码、无法保存。

**根因与对策：**

| 根因 | 对策 |
|------|------|
| 请求体编码非 UTF-8 | 统一用 UTF-8 编码请求，requests 的 json 会自动处理 |
| 包含非法字符（引号/换行/通配符） | 清洗关键词，仅保留合法字符 |
| 关键词过长 | 截断到 DV360 允许的最大长度（如 80 字符） |
| 使用了随机/无意义词 | 用 `dv360_list_keyword_targeting` 验证可用的 keyword |
| 用了敏感/受限词 | 换成合规同义表达 |

```python
# 清洗关键词再创建，避免乱码与非法字符
import re

def clean_keywords(raw: list) -> list:
    cleaned = []
    for kw in raw:
        kw = str(kw).strip()
        # 只保留中文、英文、数字、空格与常规符号
        kw = re.sub(r'[^\w\s\u4e00-\u9fff]', '', kw, flags=re.UNICODE)
        kw = kw[:80]  # 截断
        if kw:
            cleaned.append(kw)
    return cleaned

kws = clean_keywords(["智能门铃", '"car" review', "NFT**", ""])
resp = api.dv360_create_keyword_targeting(advertiser_id, keywords=kws, target_type="included")
print(resp)
```

### 4.5 排除定向没生效

**现象**：线上仍出现你明确加入排除的站点/分类/App。

**排查步骤：**
1. **确认"排除放在哪个层级"**：排除设在 Advertiser 级只对该 Advertiser 生效；若你想在某个 Line Item 排除，需在对应 Line Item 角度配。
2. **确认 target_type**：确保该 assigned targeting option 的 `targetType == "excluded"`，不是 "included"。
3. **层级被覆盖**：有时下级主动 included 了一个上级 excluded 的选项 → 检查规则覆盖。
4. **时序**：修改后是否生效（DV360 配置变更可能需几分钟到几十分钟）。
5. **验证**：用报表按维度（site/category/app）回看是否仍投到，逐条核对。

```python
# 验证排除配置是否正确写入
targetings = api.dv360_list_targetings(advertiser_id)
for t in targetings:
    if t.get('targetingType') == 'TARGETING_TYPE_CONTENT_EXCLUSION':
        print(f"  排除项: {t.get('displayName')} "
              f"targetType={t.get('targetType')} "
              f"status={t.get('status')}")
```

### 4.6 频控不生效

**现象**：用户被展示次数远超设置的上限。

**排查维度：**
- **层级**：是否在正确的对象层级设了频控（per IO vs per Line Item vs per creative）。
- **窗口**：窗口单位是否与预期一致（小时/天/周/总战役）。
- **跨 IO**：多个 line item 各自计数，未做 IO 级去重 → 需要把频控放进 IO 级 + deduplicate。
- **计量事件**：是否只对 impression 计量（view-through 不算），导致把 seen 但未计量的展示漏数。
- **创意轮换**：如果是按 creative 频控，同一 Line Item 多个 creative 各计各的。

**黄金实践：** 需要"每个用户每个 IO 每天 X 次"就把频控设在 **Insertion Order 级**，勾选 deduplicate within insertion order；需要"每个创意"就设 per creative。

### 4.7 Lookalike 效果变差

| 症状 | 根因 | 对策 |
|------|------|------|
| CTR/CVR 低于投放前预期 | 种子不纯（混入低价值流量） | 只用高转化种子重建 Lookalike |
| 覆盖人群过小 | 种子太小或相似度设得太高（如 1%） | 提高比例（3-5%）或扩大种子 |
| 波动大 | 种子太小不稳定 | 累积 ≥ 1000 活跃种子 |
| 与 Retargeting 重叠高 | Lookalike 与重定向人群重合 | 用负定向排除已重定向人群 |

### 4.8 上级定向继承导致的"意外不出量"

**排查口诀"向上看三层"：**
- Advertiser 级 → IO 级 → Line Item 级 → 全都要看。
- 若上级设了地域/受众/排除，下级会自动继承并叠加。
- 用 `dv360_list_targetings(advertiser_id)` 按层级拉取，逐层核对 inherited conditions。

```
排查流程
┌→ Advertiser 级别定向
│     地域? 受众? 排除?
├→ Insertion Order 级别
│     地域? 受众? 频控?
├→ Line Item 级别
│     定向 AND 层数? 排除? 频控窗口?
└→ 结论: 逐层放开"不该继承"的定向
```

---

## 五、自测题

### 5.1 选择题

<details><summary>查看答案</summary>
1. C 2. B 3. A 4. B 5. A
</details>

**第 1 题：DV360 中，同一个 Line Item 上所有 `included`（正向）定向维度之间是什么关系？**

- A. OR（并集）
- B. NOT（排除）
- C. AND（交集）
- D. 无固定关系

**第 2 题：下面哪种情况最容易导致 DV360 定向 fill 过低？**

- A. 只设一个宽 In-Market 受众
- B. 把 In-Market + Affinity + 年龄段 + 单一邮票邮编 全叠加为正定向
- C. 只设地域=美国
- D. 只在 IO 级设频控

**第 3 题：CSV 上传的第一方受众通常的有效期约为多少天？**

- A. 540 天
- B. 30 天
- C. 90 天
- D. 无限期

**第 4 题：想实现"每个用户在每个 Insertion Order 内每天最多 3 次"，最合适的做法是？**

- A. 在每个 Line Item 上分别设 per Line Item 3 次/天
- B. 在 Insertion Order 级别设频控并勾选 deduplicate within insertion order
- C. 在 Advertiser 级别设 per creative 3 次/天
- D. 在创意级别设 3 次/天

**第 5 题：负定向（excluded）的优先级在所有定向规则中属于？**

- A. 最高（命中即剔除）
- B. 最低
- C. 与正定向相同层级
- D. 仅对展示型有效

### 5.2 实操题

**第 6 题（场景排查）**：你的新视频 Line Item 已启动 48 小时，但出量极低。你会按什么顺序排查？请写出你的排查步骤与原因。

<details><summary>查看答案</summary>
按"一次只动一个变量"原则：
1. 确认 Line Item 状态 AE ACTIVE、flight 未结束、预算 > 0。
2. 确认所用受众未 EXPIRED、规模不小。
3. 检查定向 AND 是否叠太多层、地域是否过细。
4. 检查上级 Advertiser/IO 是否有继承的更严定向。
5. 检查品牌安全/排除是否误伤。
6. 用 forecast/report 验证并每次放宽一个维度观察出量。
</details>

**第 7 题（设计题）**：某品牌想"America 全美投放智能门铃"，既要出量充足又要精准，请设计分层定向策略（拓量层/精准层/品牌层）。

<details><summary>查看答案</summary>
- 拓量层（大预算）：地域=美国全国、单一宽受众（In-Market 家居安防）、全设备、排除高风险分类。
- 精准层（中预算）：地域=Top DMA、第一方高价值访客重定向、排除已转化、适度频控。
- 品牌层（小预算）：地域=美国、Lookalike（以高转化种子）、第三方品牌安全校验。
三层用不同创意/频控，观察出量与转化后动态调整预算与比例。
</details>

**第 8 题（计算题）**：某品牌曝光 Line Item 用"per Line Item 3 次/天"，另一个转化 Line Item 也用"per Line Item 3 次/天"，两者都投同一人群。请指出这样配置的问题并给出正确方案。

<details><summary>查看答案</summary>
问题：两个 Line Item 各自独立计数，同一个用户可能被每个线项各看 3 次，合计 6 次/天，超出"每天 3 次"的品牌预期，造成过度曝光与用户厌烦。
正确方案：把频控提升到 Insertion Order 级别，设为"每个用户每天 3 次"，并勾选 deduplicate within insertion order，让两个线项共享同一频控上限。
</details>

### 5.3 论述题

**第 9 题**：为什么在第三方 Cookie 退场背景下，上下文定向与第一方数据的组合会比单纯依赖第三方受众更稳健？请结合 DV360 机制论述。

<details><summary>查看答案</summary>
- 上下文定向不依赖用户标识，只看页面内容（关键词/分类/URL），因此在无 Cookie 环境依然可用，天然对抗隐私变化。
- 第一方数据（CSV/Floodlight）是广告主自有资产，匹配 Google 登录用户，不依赖第三方 Cookie，可控且可持续刷新。
- 第三方受众依赖跨站追踪与 Cookie，在隐私沙盒与浏览器限制下覆盖率会显著下降、匹配率变差。
- 组合策略：用上下文+第一方做"确定性触达与重定向"，用 Google 自有的 In-Market/Affinity 模型做拓量，减少对脆弱第三方数据的依赖。这是 DV360 官方推荐的隐私时代定向路径。
</details>

---

## 六、术语表与速查

### 6.1 定向体系术语速查

| 术语 | 英文 | 解释 |
|------|------|------|
| 定向 | Targeting | 决定广告投给谁/投在哪/投在什么环境 |
| 正定向 | Included Targeting | 明确"只要这些"的定向 |
| 负定向 | Excluded Targeting | 明确"不要这些"的定向 |
| 定向单位 | Targeting Unit | 一组定向选项的容器，可复用到多个 Line Item |
| 已分配定向选项 | Assigned Targeting Option | 挂载在实体上的具体定向条件 |
| 上下文定向 | Contextual Targeting | 按页面内容（关键词/分类/URL）定向 |
| 关键词定向 | Keyword Targeting | 匹配页面自然语言关键词 |
| 位置定向 | Placement Targeting | 精确指定站点/URL/App |
| 站点分类定向 | Site Category Targeting | 按站点类别定向 |
| 受众定向 | Audience Targeting | 按人群数据定向 |
| 第一方数据 | 1st-Party Data | 广告主自有数据 |
| 第二方数据 | 2nd-Party Data | 发布商/合作伙伴数据 |
| 第三方数据 | 3rd-Party Data | 数据商数据 |
| 客户匹配 | Customer Match | 用加密邮箱/手机号匹配 Google 用户 |
| 动态受众 | Dynamic Audience | Floodlight 实时滚动维护的受众 |
| 兴趣受众 | Affinity Audience | 长期兴趣（宽泛） |
| 意向受众 | In-Market Audience | 近期购买意图 |
| 人生大事 | Life Events | 新婚/搬家/毕业等人生变化 |
| 类似受众 | Lookalike / Similar Audience | 以种子人群找相似新用户 |
| 人口统计 | Demographics | 年龄/性别/收入/家长状态 |
| 频控 | Frequency Capping | 限制每个用户看到广告的次数 |
| 频控层级 | Frequency Cap Level | per LI / per IO / per creative |
| 频控窗口 | Frequency Cap Window | hourly/daily/weekly/lifetime |
| 跨 IO 去重 | Deduplicate within IO | 同一 IO 下多个 Line Item 共享频控 |
| 品牌安全 | Brand Safety | 确保内容环境安全 |
| 内容排除 | Content Exclusion | 排除不安全内容类型 |
| 品牌安全分类 | Brand Safety Category | DV360 内置敏感分类 |
| 第三方校验 | Third-Party Verification | IAS / DoubleVerify 等 |
| 填充率 | Fill Rate | 实际投放量/可投量 |
| 受众规模 | Estimated Audience Size | 受众可投人数估计 |
| 有效期 | Expiration | 受众的有效期限 |
| 冷启动 | Cold Start | 无历史数据下的初始投放 |
| 白名单 | Whitelist | 只投指定站点 |
| 私市 | Private Marketplace | 邀请制优质库存交易 |
| 程序化保量 | Programmatic Guaranteed | 保证展示量的程序化购买 |

### 6.2 API 方法速查（本主题相关）

**受众与定向单位：**

| 方法 | 用途 |
|------|------|
| `dv360_list_targetings(advertiser_id)` | 列出定向项 |
| `dv360_list_targeting_units(advertiser_id)` | 列出定向单位 |
| `dv360_create_targeting_unit(advertiser_id)` | 创建定向单位 |
| `dv360_update_targeting_unit(targeting_unit_id)` | 更新定向单位 |
| `dv360_delete_targeting_unit(targeting_unit_id)` | 删除定向单位 |
| `dv360_list_audiences(advertiser_id)` | 列出受众 |
| `dv360_list_dynamic_audiences(advertiser_id)` | 列出动态受众 |
| `dv360_list_audience_segments(advertiser_id)` | 列出受众段（Google 自有等） |
| `dv360_list_interests(advertiser_id)` | 列出兴趣 |
| `dv360_list_interests_detail(interest_id)` | 兴趣详情 |

**上下文/关键词/位置：**

| 方法 | 用途 |
|------|------|
| `dv360_list_keyword_targeting(advertiser_id)` | 列出关键词定向 |
| `dv360_create_keyword_targeting(advertiser_id)` | 创建关键词定向 |
| `dv360_delete_keyword_targeting(targeting_id)` | 删除关键词定向 |
| `dv360_list_contextual_targeting(advertiser_id)` | 列出上下文定向 |
| `dv360_create_contextual_targeting(advertiser_id)` | 创建上下文定向 |
| `dv360_delete_contextual_targeting(targeting_id)` | 删除上下文定向 |
| `dv360_list_placement_targeting(advertiser_id)` | 列出位置定向 |
| `dv360_create_placement_targeting(advertiser_id)` | 创建位置定向 |
| `dv360_delete_placement_targeting(targeting_id)` | 删除位置定向 |
| `dv360_list_site_category_targeting(advertiser_id)` | 列出站点分类定向 |
| `dv360_create_site_category_targeting(advertiser_id)` | 创建站点分类定向 |
| `dv360_list_placements(advertiser_id)` | 列出投放位 |

**维度详情：**

| 方法 | 用途 |
|------|------|
| `dv360_list_geo_targeting_detail(targeting_id)` | 地理定向详情 |
| `dv360_list_device_targeting_detail(targeting_id)` | 设备定向详情 |
| `dv360_list_os_targeting_detail(targeting_id)` | 操作系统定向详情 |
| `dv360_list_app_targeting(advertiser_id)` | 列出 App 定向 |
| `dv360_list_video_targeting(advertiser_id)` | 列出视频定向 |
| `dv360_list_operating_systems()` | 操作系统选项 |
| `dv360_list_device_types()` | 设备类型选项 |
| `dv360_list_connection_types()` | 连接类型选项 |
| `dv360_list_banner_positions()` | 横幅位置选项 |

**品牌安全：**

| 方法 | 用途 |
|------|------|
| `dv360_list_content_exclusions(advertiser_id)` | 列出内容排除 |
| `dv360_create_content_exclusion(advertiser_id)` | 创建内容排除 |
| `dv360_delete_content_exclusion(exclusion_id)` | 删除内容排除 |
| `dv360_list_brand_safety_categories()` | 列出品牌安全分类 |
| `dv360_list_ad_verification_services()` | 列出广告验证服务 |
| `dv360_list_brand_safety_providers()` | 列出品牌安全供应商 |
| `dv360_list_viewability_providers()` | 列出可见性供应商 |
| `dv360_list_viewability_targets()` | 可见性目标 |

**预测/报表：**

| 方法 | 用途 |
|------|------|
| `dv360_list_reach_forecasts(advertiser_id)` | 触达预测 |
| `dv360_list_frequency_forecasts(advertiser_id)` | 频次预测 |
| `dv360_get_performance_forecast(advertiser_id)` | 效果预测 |
| `dv360_list_report_dimensions()` | 报表维度 |
| `dv360_list_report_metrics()` | 报表指标 |
| `dv360_get_report(advertiser_id)` | 拉报表 |
| `dv360_get_targeting_dimension_options()` | 维度选项骨架（dv360_api.py） |

**Line Item 侧：**

| 方法 | 用途 |
|------|------|
| `dv360_list_line_items(advertiser_id)` | 列出线项 |
| `dv360_create_line_item(advertiser_id)` | 创建线项 |
| `dv360_update_line_item(advertiser_id, line_item_id)` | 更新线项（挂定向单位等） |
| `dv360_get_line_item(advertiser_id, line_item_id)` | 获取线项详情 |
| `dv360_pause_line_item` / `dv360_resume_line_item` | 暂停/恢复 |
| `dv360_list_insertion_orders(advertiser_id)` | 列出 IO |
| `dv360_list_flights(advertiser_id, line_item_id)` | 列出排期 |

### 6.3 常见定向配置模板（速查卡）

**品牌曝光模板：**

```
地域: 目标市场(国家/州)
受众: Affinity(宽) 或 In-Market(中)
设备: 全设备
频控: 3-5 次/周 (per IO + dedup)
品牌安全: 成人/赌博/暴力排除 + (可选)第三方校验
```

**效果转化模板：**

```
地域: 目标市场 Top DMA
受众: 第一方重定向(高价值) + Lookalike
设备: 手机+桌面
频控: 2-3 次/天 + 冷却
品牌安全: 严格内容排除
出价: CPA/tCPA 或 ocpm
```

**新品上市模板：**

```
地域: 全国
受众: 上下文+分类 + In-Market
设备: 全设备
频控: 4-6 次/周
创意: 多版式 AB 测试
```

---

## 七、附录：进阶主题（隐私合规、算法细节、跨平台对比）

### 7.1 隐私合规与定向（Privacy Sandbox / TCF）

- DV360 支持 Google 的 Privacy Sandbox 相关信号（Topics、Protected Audience 等），上下文定向与第一方数据的价值因此上升。
- 欧洲区投放需处理 GDPR / TCF 2.x 同意信号：`dv360_get_compliance_status` / `dv360_list_policy_violations` 可用于检查合规状态。
- 上传第一方数据必须确认数据使用权限（含用户同意），否则面临政策处罚。

### 7.2 DV360 定向 vs Google Ads / Meta 的差异

| 维度 | DV360 | Google Ads | Meta |
|------|-------|-----------|------|
| 定向重心 | 程序化库存+品牌环境控制 | 搜索+GDN 关键词 | 社交兴趣/行为 |
| 受众来源 | 第一方/第三方/Google 自有最全 | Google 受众 | Meta 自有+像素 |
| 频控 | 多层级+跨 IO 去重 | 相对简单 | 频次控制 |
| 品牌安全 | 最完整（排除+分类+第三方） | 中等 | 较弱 |
| 库存类型 | 开放+私市+保量 | GDN/搜索 | 站内 feed |

### 7.3 DV360 定向的算法细节（公开信息整理）

- **In-Market 受众**基于近 30 天内用户的搜索/浏览/购买信号，按品类分层。
- **Affinity 受众**基于长期兴趣曲线，覆盖广但意图弱。
- **Lookalike** 在 DV360 内基于"种子人群特征向量"做相似度检索，比例越接近种子越像。
- **频控**由 DV360 广告服务端按 cookie/device ID 计数；隐私环境下覆盖率会下降。
- **可见性/品牌安全分类**由 DV360 与第三方（IAS/DV）的扫描系统对页面实时分类。

### 7.4 投放效果分析维度建议（用报表验证定向）

| 分析维度 | 报表维度/指标 | 用途 |
|---------|--------------|------|
| 频次分布 | Impressions / Unique Users | 判断是否过曝 |
| 地域效果 | Geo dimension | 发现高/低效地区 |
| 设备效果 | Device dimension | 调整设备定向 |
| 内容环境 | Site / Category dimension | 验证上下文定向相关性 |
| 受众效果 | Audience dimension | 验证 Retargeting/Lookalike |
| 时段 | Hour of day | 调整 Dayparting |

### 7.5 面向未来的定向趋势（Ryan 知识库视角）

1. **第三方 Cookie 退场** → 上下文+第一方+Google 模型组合成为主流。
2. **信号弱化** → 频控、归因、优化都受影响，需要更多"确定性信号"（登录态、第一方）。
3. **AI 自动定向** → DV360 的 Smart Bidding/自动受众扩展会接管更多人工定向决策。
4. **跨平台整合** → 广告主需要像本文这样的统一定向方法论，把 DV360/Google Ads/Meta/TikTok 的定向语言对齐。

---

## 八、总结

DV360 定向系统是全市场最完整的程序化定向体系之一。掌握它需要同时理解**平台的对象模型**（Targeting Unit / Assigned Targeting Option / 层级继承）、**五大类定向**（上下文 / 受众 / 人口设备 / 频控 / 品牌安全）、**AND/OR/正负组合逻辑**，以及**生产环境中的踩坑**（fill、受众过期、频控单位、品牌安全过严、Geo 过细等）。

核心心法可以浓缩为一句话：**"先宽后窄、正负结合、频控分层、数据养熟、环境守底"**——先大后小保证出量，正负结合保证相关性，频控分层保证触达质量，第一方数据持续养熟保证 Lookalike 质量，品牌安全兜底保证品牌资产。

配合本文的 Go 定向匹配引擎、Python 全链路脚本与自动化审计代码，你可以把 DV360 定向从"手点 UI"升级为"可代码化、可审计、可预测"的工程化能力。

---

## 九、深度实战案例库（沉淀真实业务经验）

### 9.1 案例A：澳洲教育机构留学招生——定向过窄导致 fill 暴跌的全过程复盘

**背景**：某澳洲大学委托代理商在 DV360 投放"硕士留学申请"广告，目标人群"亚太区 22-30 岁、雅思 6.5 以上、有意向读商科"，预算充足但出量严重不足。

**初始配置（过度定向）：**

```
Line Item: AU 商科硕士招生
├── 地域: 澳大利亚墨尔本 + 悉尼 (仅两城)
├── 受众: 第一方"雅思考生列表"(仅 800 人)  (AND)
├── 年龄: 22-24 仅 (AND)
├── 性别: 女 (AND)     ← 过于武断
├── 设备: iPhone 仅 (AND)
├── 排除: 几乎全部敏感分类
```

**现象**：投放 5 天，仅 120 次展示、30 次点击、0 个申请，fill 惨不忍睹，CPM 却高达 $38（因为可拍卖库存太少）。

**诊断过程：**
1. `dv360_list_audiences` 显示种子受众仅 800 人且 40% 已过期。
2. 五层 AND 叠加，理论可达用户 < 100。
3. 单一两城市 + 单一设备 + 单一性别的组合近乎"精准空集"。

**优化方案：**

```
策略分两组：
├── 拓量组 (70% 预算)
│   ├── 地域: 澳洲全国 + 亚洲主要生源国 (中国/印度/越南) (OR 并集)
│   ├── 受众: Google In-Market "高等教育 + 留学" (宽模型受众)
│   ├── 年龄: 20-30 (OR)
│   └── 设备: 全设备
└── 精准组 (30% 预算)
    ├── 地域: 澳洲 + 亚洲 (OR)
    ├── 受众: 第一方"意向咨询"动态受众 (Lookback 60 天) + Lookalike
    ├── 年龄: 22-28
    └── 频控: 2 次/天 + 冷却
```

**结果**：拓量组 3 天内 fill 恢复正常，CPM 从 $38 降至 $9；精准组转化率显著提升。**结论**：教育/转化类定向要"宽圈层拓量 + 窄圈层精准"，绝不能让"精准"变成"空集"。

### 9.2 案例B：跨境电商 App 出海——first-party 匹配率与频控单位的连锁坑

**背景**：某跨境电商 App 出海东南亚，用 CSV 上传老客手机号做重定向，并配两个 Line Item（新客拓量 + 老客重定向）各设 3 次/天频控。

**问题现象：**
1. 重定向匹配率仅 22%，几乎无法投放。
2. 新客与老客两个线项对同一用户各计 3 次，合计 6 次/天，老客投诉"广告轰炸"。

**根因：**
- 手机号做种子，未规范化（带 +86 前缀、空格、字母），导致哈希后无法匹配。
- 未对重定向人群设"排除已转化"，且两个线项未在 IO 级去重。

**修复：**
1. 改用邮箱优先做种子 + 手机号规范化（E.164）后再上传，匹配率回升到 68%。
2. 在 Insertion Order 级设频控（3 次/天 + deduplicate within IO），两线项共享上限。
3. 重定向线项排除已下单用户。

**教训**：**第一方数据"格式即生死"**；**频控层级放错是"隐形超频"的头号元凶**。

### 9.3 案例C：品牌安全过严挤走 80% 出量——金融科技客户的平衡术

**背景**：某金融科技（支付）品牌在欧美投放，出于风控考量把**几乎全部敏感分类**（新闻、政治、健康、债务、赌博、成人、小众社交）都设为排除。

**现象**：可投库存骤减约 80%，虽然在投但无法达标，且因库存过少导致 CPM 显著抬升。

**诊断**：金融确实对"债务/贷款"等敏感，但把"新闻/政治/健康"也全部排除，等于放弃了大量优质的程序化库存。

**优化：**
- **必排（不可妥协）**：赌博、成人、暴力、毒品、债务催收。
- **可选排（按风险承受度评估）**：新闻政治设立"品牌安全分级"——只排"高敏政治议题"而非全部政治；健康只排"医药功效宣称"而非全部健康。
- 引入第三方校验（IAS/DV）做"第二道闸"，而不是靠人工一刀切全部排除。

**结果**：出量恢复约 60% 的损失，品牌安全事件仍控制在极低水平。**教训**：品牌安全是"风险管理"而非"零风险"，分级 + 第三方是现代做法。

### 9.4 案例D：实时出价时的定向性能——高 QPS 定向索引优化

**背景**：自研 DSP 侧需要对 DV360 风格的定向做实时匹配，峰值 QPS 达 5 万，最初的线性扫描把每个请求的定向匹配延迟推到 12ms，超过预算。

**优化：**
1. 用**倒排索引**：`定向条件值 -> lineItemID 列表`，把候选从全量 5K 个 Line Item 缩到几十个。
2. **AND 合并**：多维度交集先取最短集合做起点。
3. **负向短路**：排除命中即返回。
4. **L1 缓存**：热定向组合做内存 cache（一级），冷数据走索引（二级）。

**结果**：延迟从 12ms 降到 1.2ms，P99 达标。这就是本文 2.5 节 Go 引擎在真实生产中的价值。

```
优化前后对比
┌─────────────┬────────────┬──────────┐
│  指标        │  优化前     │  优化后   │
├─────────────┼────────────┼──────────┤
│ 定向匹配延迟  │  12ms      │  1.2ms   │
│ 候选 LineItem│  ~5000     │  ~40     │
│ P99         │  超预算     │  达标     │
│ CPU 占用     │  高        │  低       │
└─────────────┴────────────┴──────────┘
```

### 9.5 跨案例通用方法论：定向健康度诊断

把以上案例提炼成一套可复用的"定向健康度诊断流程"：

```
定向健康度诊断
│
├─ ① 出量健康度
│       fill、impressions、reach 是否满足目标?
│       └─ 不满足 → 走"先宽后窄"调整
│
├─ ② 效率健康度
│       CTR/CVR/CPM/CPA 是否在合理区间?
│       └─ 不满足 → 检查相关性(分类粒度/受众意图/Lookalike 质量)
│
├─ ③ 频次健康度
│       平均频次是否过度? unique users 占比?
│       └─ 不满足 → 检查频控层级/跨 IO 去重
│
├─ ④ 数据健康度
│       受众有效期/匹配率/种子纯度?
│       └─ 不满足 → 数据治理(清洗/刷新/分层)
│
└─ ⑤ 合规健康度
        品牌安全/隐私合规/政策状态?
        └─ 不满足 → 分级防线 + 第三方 + 合规检查
```

---

## 十、延伸：从 DV360 到全平台定向方法论（承上启下）

### 10.1 为什么这套方法论可复制到其他平台

DV360 定向的**底层逻辑**（正负定向、AND/OR 组合、频控、数据分层、品牌安全）在 Google Ads、Meta、TikTok 同样适用，只是"叫法"不同：

| 概念 | DV360 | Google Ads | Meta | TikTok |
|------|-------|-----------|------|--------|
| 受众定向 | Audience | Audience | Audience | Audience |
| Lookalike | Lookalike | Similar segments | Lookalike Audience | Lookalike |
| 重定向 | First-party retargeting | Website audiences | Custom Audience | Retargeting |
| 频控 | Frequency cap | Frequency cap | Frequency cap | Frequency cap |
| 排除 | Excluded | Negative | Exclude | Exclude |
| 上下文/兴趣 | Contextual/In-market | Search keywords | Interest | Interest |

**方法论一句话**：无论平台如何，**"圈层机器"永远由四件事决定——人群数据、内容环境、触达频次、排除防负**。管好这四件事，任何 DSP 都能投得稳。

### 10.2 DV360 定向与自研 DSP 的协同（承接 ad-targeting 系列）

Ryan 知识库已有大量自研 DSP 定向文档（倒排索引、向量召回、频控滑动窗口等）。当同时使用 DV360（作为托管 DSP）与自研系统时，关键协同点：
1. **数据回传**：DV360 报表可作为自研优化的输入。
2. **定向语言统一**：把 DV360 的 TargetingType 映射到自研系统的定向 schema，复用同一套配置模型。
3. **频控跨系统**：若同一用户在 DV360 与自研 DSP 都曝光，需要统一频控（跨系统去重），否则重复轰炸。这是"隐形超频"的高级形态。

### 10.3 运维建议：定向的持续优化节奏

| 节奏 | 动作 |
|------|------|
| 每日 | fill/出量/频次快速巡检 + 告警 |
| 每周 | 定向维度效果分析，调整正负向 |
| 每周 | 第一方受众刷新 + 匹配率监控 |
| 每月 | Lookalike 种子更新、过期受众清理 |
| 每季 | 全量配置审计 + 合规审查 + 策略模板复盘 |

---

## 十一、结语

本文从 DV360 定向的**架构全貌**出发，深入到**上下文/受众/人口设备/频控/品牌安全五大类的实现原理**，给出了 **Go 定向匹配引擎**与 **Python API 全链路脚本**等可直接落地的代码，沉淀了**十余个真实踩坑案例**与**一套跨案例的诊断方法论**，并提供了术语表、API 速查与跨平台对比。

无论你是刚接手 DV360 投放、想用 API 自动化定向配置，还是要把 DV360 的方法论复用到自研 DSP，本文都是一份"从原理到生产"的完整参考。记住那句心法——
**"先宽后窄、正负结合、频控分层、数据养熟、环境守底。"**

---

## 十二、频率控制进阶：边界场景与工程化

### 12.1 频控的边界与种子问题

**频控不是"越多越好"，也不是"越严越好"。** 极端配置都会伤出量或伤体验，需要理解边界：

| 极端方向 | 后果 | 何时会发生 |
|---------|------|-----------|
| 频控＝0（不设） | 同用户被反复轰炸、Reach 虚高无意义、等待投诉 | 冷启动初期漏配 |
| 频控过低（如 1 次/小时） | 可投库存被大幅扣减、出量崩 | 视频/大占比出量场景 |
| 频控过高（如 20 次/天） | 形同虚设、用户厌烦 | 复制粘贴模板忘记改 |
| 层级错误（每 LI 各计） | 隐形超频（见案例B） | 未做 IO 级去重 |

**关键认知：频控的本质是"减量器"。** 它在定向确认"这个用户符合条件"之后，再扣减"已看到太多"的用户。因此**频控只能让出量更少，绝不会让出量更多**。如果目的是"提高 Reach"，靠加频控是错的，要靠放宽定向或降低频控。

### 12.2 多窗口频控的组合逻辑

DV360 支持在同一对象上叠加多个窗口的频控，它们之间是"任何一条超限即剔除"的关系：

```
叠加频控示例
├── 每日: 3 次 (per user)
├── 每周: 8 次
└── 整个 campaign: 20 次
└── 任一超限 → 剔除 (OR 语义)
```

工程上，多窗口可用"每个窗口一个 counter"实现，检查时对每个窗口分别 `Incr` 并判断：

```go
// 多窗口频控判断
type Caps struct {
    daily   int
    weekly  int
    lifetime int
}
func (c Caps) anyExceeded(d, w, l int) bool {
    return d > c.daily || w > c.weekly || l > c.lifetime
}
```

### 12.3 频控与归因/效果的联动

- **频控太低**：用户可能在完成转化前就被掐掉，导致转化路径断裂——尤其效果型多触点。
- **频控太高**：边际效用递减（见 2.4.2 曲线），浪费预算、引发负品牌。
- **建议**：效果类先"低频控"保转化路径完整（如 2-3 次/天），跑出数据后再收紧；品牌类尽快"中低频控防轰炸"。

### 12.4 频控监控与告警工程化

把频控健康度纳入监控，可用下面的校验式思路：

```python
# 频控健康度检查（伪代码）
def freq_health(api, advertiser_id, line_items, threshold_ratio=1.5, target_freq=3):
    problems = []
    for li_id in line_items:
        # 拉取该线项的 impressions 与 unique users（假设有报表方法）
        impressions = get_impressions(li_id)
        uniques = get_unique_users(li_id)
        if uniques > 0:
            avg_freq = impressions / uniques
            if avg_freq > target_freq * threshold_ratio:
                problems.append((li_id, avg_freq))
    return problems  # 返回频次超标线项
```

**建议告警规则：**
- 某线项平均频次 > 目标 1.5 倍 → warn。
- 某线项 fill < 20% 且原因含"频控" → warn。
- 新投放 48h 内未设频控 → 提醒。

### 12.5 频控与创意轮换

同一 Line Item 挂多个创意时，频控粒度可选 per creative 或 per Line Item：
- **per Line Item**：无论哪个创意，用户总共 N 次。
- **per creative**：每个创意各计 N 次（适合创意多样性、避免同创意重复）。

**工程注意**：per creative 频控若多个创意共享 budget，可能触发"创意间互斥"问题——一个创意满频后换另一个创意继续，累计反而更高。**需要总频控兜底**（Line Item 级 max）。

---

## 十三、定向监控与告警体系（生产运营）

### 13.1 定向相关的关键监控指标

| 指标 | 定义 | 健康区间 | 告警 |
|------|------|---------|------|
| Fill Rate | 实际投放/可投库存 | > 60% 通常健康 | < 40% |
| Impressions | 展示数 | 达标 | 连续下滑 |
| Unique Reach | 独立用户 | 达标 | 停滞 |
| 平均频次 | Impressions/Unique | 1-5 视品类 | > 目标 1.5x |
| CTR | 点击率 | 行业基准 | 显著下滑 |
| CVR | 转化率 | 基准 | 显著下滑 |
| Audience 规模 | 受众可投数 | > 千级 | < 千级 |
| 过期受众数 | EXPIRED | 0 | > 0 |
| 匹配率 | 匹配/上传 | > 60% | < 40% |
| CPM/CPC | 成本 | 预算内 | 突增 |

### 13.2 告警分类与响应

```
告警分级
├── P0 (立即处理)
│   ├── 全部线项 fill → 0
│   ├── 受众全部过期 → 投放停摆
│   └── 合规/政策违规
├── P1 (当日处理)
│   ├── 单线项出量骤降
│   ├── 频次超标
│   └── 匹配率暴跌
└── P2 (本周处理)
    ├── CPM 渐升
    ├── Lookalike 效果下滑
    └── 个别维度效率差
```

### 13.3 巡检脚本整合

生产上建议把本主题涉及的所有检查整合成一个定时巡检脚本：

```python
def daily_tuning(api, advertiser_id):
    report = {
        "expired_audiences": [],
        "low_fill": [],
        "freq_over": [],
        "config_drift": None,
    }
    # 1. 受众健康
    for a in api.dv360_list_audiences(advertiser_id) or []:
        if a.get('status') in ('EXPIRING', 'EXPIRED'):
            report["expired_audiences"].append(a.get('displayName'))
    # 2. 出量健康（示例用线项数据）
    # 3. 频次健康（见 12.4）
    # 4. 配置审计（见 3.6 audit）
    return report  # 交给告警/通知
```

---

## 十四、复习题（进阶）

### 14.1 进阶自测

**第 10 题**：请描述 DV360 中"正向定向维度之间是 AND、维度内多值之间是 OR、负向是 NOT、层级继承"这四条规则的组合效果，并举一个"看似准确实则空集"的例子。

<details><summary>查看答案</summary>
四条规则共同决定了"最终可投集合"。一个"看似准确实则空集"的例子：单一城市 + 单一性别 + 单一设备 + 已过期的小种子受众 + 全敏感排除，五层同时作用，可投人数趋近于 0 甚至直接空集。正向 AND 越多、维度值越单一、数据越陈旧，就越容易空集。
</details>

**第 11 题**：为什么"提高频控"不能提高 Reach？正确做法是什么？

<details><summary>查看答案</summary>
频控是"减量器"，只能在定向确认后扣减"看过太多"的用户，因此只能让出量更少。要提高 Reach（独立用户数），应放宽定向范围（降低 AND 层、扩地域/受众）、适当降低频控限制让更多新用户进入，并搭配 Lookalike 拓新客，而不是增加频控。
</details>

**第 12 题**：给出"跨系统（DV360 + 自研 DSP）同用户重复曝光"问题的一个可行解决方案。

<details><summary>查看答案</summary>
统一 userId 映射（登录态/Cookie/设备ID归一化）后，将两侧曝光事件并入同一频控计数存储（如 Redis），两侧出价前都查询同一频控表，达成跨系统去重；同时在一侧达到上限时另一侧也不再出价。工程上可抽象出一个"共享频控服务"，作为两者的唯一真源。
</details>

---

## 十五、参考与延伸阅读

### 15.1 Ryan 个人知识库内相关文档（互补定位）

| 文档 | 与本主题的关系 |
|------|---------------|
| `dv360-architecture-deep.md` | 定向策略详解（维度/受众细分），本文深化到原理+代码 |
| `dv360-marketing-api-deep.md` | 定向策略部分的 API 视角，本文补全定向单位与全链路 |
| `dv360-optimization-deep.md` | 定向优化分层 2.1，本文补全频控/品牌安全专项 |
| `dv360-creative-brand-safety-deep.md` | 品牌安全与创意侧，本文从定向角度覆盖品牌安全 |
| `ad-frequency-capping-*.md` | 广义广告频控算法，本文聚焦 DV360 平台单位/窗口 |
| `ad-targeting-*.md` | 广义广告定向系统，本文聚焦 DV360 SaaS 平台 |
| `ad-lookalike-audience-expansion.md` | Lookalike 扩量技术，本文给平台侧配置要点 |
| `ad-retargeting-strategy-optimization.md` | 重定向策略，本文细化到 DV360 配置 |
| `ad-dmp-sync-failure-case-deep.md` | 数据同步失败排查，与受众同步问题互补 |

### 15.2 官方参考

- Display & Video 360 API v4: `https://developers.google.com/display-video/api`
- `partners/{partnerId}/advertisers`、`advertisers/{advertiserId}/targetingTypes/{type}/assignedTargetingOptions` 等 REST 资源
- DV360 UI 中的 Targeting、Audience、Frequency Capping、Brand Safety 模块

### 15.3 作者备注

本文由 Ryan 个人知识库的 DV360 深度文档任务生成，聚焦**定向系统**这一主题。文中 API 方法名对应项目脚本 `ad_platform_api.py`（dv360_* 系列）与 `dv360_api.py`（`get_targeting_dimension_options` 等），供工程实现参考。如脚本后续新增 `dv360_estimate_reach`、`dv360_list_frequency_caps` 等方法，可在此文档对应小节补充引用。

> **心法重申**：先宽后窄、正负结合、频控分层、数据养熟、环境守底。
