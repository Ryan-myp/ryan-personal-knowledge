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
