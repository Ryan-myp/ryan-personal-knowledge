# 四大广告平台战略级选型与整合指南

> **领域**: 广告投放 / 跨平台策略
> **深度**: ⭐⭐⭐⭐⭐ 实战级指南
> **标签**: cross-platform, google-ads, meta-ads, tiktok-ads, dv360, strategy
> **更新时间**: 2026-08-14
> **类型**: strategy/cross-platform

---

## 一、平台定位矩阵

### 1.1 核心定位对比

| 维度 | Google Ads | Meta Ads | TikTok Ads | DV360 |
|------|-----------|----------|-----------|-------|
| **平台本质** | 搜索意图引擎 | 社交兴趣引擎 | 短视频注意力引擎 | 程序化品牌引擎 |
| **用户心智** | "我要找..." | "我在刷..." | "我在看..." | "我在买..." |
| **核心优势** | 精准意图捕获 | 大规模触达 | 年轻用户+创意爆发 | 企业级控制 |
| **适用目标** | 效果转化为主 | 品牌+效果兼顾 | 年轻人群种草 | 大品牌全局投放 |
| **预算门槛** | $500/月起步 | $300/月起步 | $200/月起步 | $10,000/月起步 |
| **学习曲线** | 中等 | 较低 | 中等 | 陡峭 |
| **数据闭环** | 强（GA4+BigQuery） | 中（CAPI补充） | 弱（像素限制多） | 强（ADH整合） |
| **API 成熟度** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ |
| **自动化程度** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| **创意灵活性** | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ |

### 1.2 用户规模对比

```
                    日活用户 (DAU)  月活用户 (MAU)  全球渗透率
Google Ads         —              —              90%+ (搜索覆盖)
Meta Ads           39亿            33亿            45%+ (FB+IG)
TikTok Ads         20亿            18亿            25%+ (核心市场)
DV360 (间接)       —              —              90%+ (Web库存)
```

### 1.3 平台能力雷达图（文字版）

```
                Google Ads          Meta Ads           TikTok Ads         DV360
意图精准度    ████████████████   ████████████      ████████          ████████████████
触达规模      ██████████████     ██████████████████  ████████████████  ████████████████
创意空间      ████████           ██████████████████  ██████████████████ ████████
数据闭环      ██████████████████ ████████████████    ████████          █████████████████
自动化程度    ██████████████████ ██████████████████  ████████████████  ████████████████
成本控制      ████████████████   ████████████████    ████████████      ████████████████
企业管控      ███████████████    █████████████       ████████          ██████████████████
```

---

## 二、行业适配策略

### 2.1 电商行业

```
电商投放优先级矩阵：

第一梯队（必投）：
├── Google Shopping/PMax — 搜索意图最高，转化路径最短
├── Meta Advantage+ Shopping — 再营销+兴趣匹配，ROAS稳定
└── TikTok Shop — 种草转化，年轻用户渗透

第二梯队（应投）：
├── Google Search — 品牌词+品类词拦截
├── Meta Feed/Collection Ads — 商品展示+即时购买
└── Google Display — 再营销召回

第三梯队（选投）：
├── DV360 — 品牌大促期加大声量
├── TikTok Spark Ads — 达人带货放大
└── Google YouTube — 品牌故事+产品评测
```

**预算分配建议（月预算 $50K 电商）：**

| 平台 | 预算占比 | 月预算 | 主要目标 |
|------|---------|--------|---------|
| Google PMax | 35% | $17,500 | 直接转化 |
| Meta ASC | 25% | $12,500 | 再营销+扩量 |
| TikTok Shop | 20% | $10,000 | 种草转化 |
| Google Search | 12% | $6,000 | 品牌保护 |
| DV360 | 8% | $4,000 | 大促加量 |

### 2.2 游戏行业

```
游戏投放优先级矩阵：

第一梯队（必投）：
├── Meta Instant Games + UA — 安装量最大来源
├── TikTok Spark Ads + In-Feed — 年轻玩家获取
└── Google App Campaigns — 搜索+展示全覆盖

第二梯队（应投）：
├── Google PMax for Apps — 跨渠道归因优化
├── Meta Advantage+ App Install — 智能扩量
└── TikTok TopView — 新品发布爆发

第三梯队（选投）：
├── DV360 — 品牌认知建设
└── Google YouTube Pre-roll — 游戏预告片
```

### 2.3 金融/保险行业

```
金融投放优先级矩阵：

第一梯队（必投）：
├── Google Search — 高意向搜索词（贷款、保险、投资）
├── Meta Lead Forms — 留资成本最优
└── Google PMax — 全渠道转化优化

第二梯队（应投）：
├── Meta CAPI — 事件追踪强化
├── Google Display Re-engagement — 再营销召回
└── DV360 — 品牌信任建设

关键合规要求：
- Google: 金融广告预审政策
- Meta: 敏感受众限制（住房/就业/信用）
- TikTok: 金融内容审核严格
- DV360: 品牌安全级别要求最高
```

### 2.4 品牌广告行业

```
品牌广告优先级矩阵：

第一梯队（必投）：
├── DV360 — 程序化品牌投放核心平台
├── Google Video (YouTube) — 品牌故事讲述
└── Meta Brand Awareness — 大规模曝光

第二梯队（应投）：
├── TikTok Brand Takeover — 年轻化品牌沟通
├── Google Display — 上下文定向品牌展示
└── Meta Video Views — 长视频品牌内容

核心KPI：
- DV360: Viewability (>70%)、Brand Lift (+15%+)
- Google: Brand Search Lift、Video Completion Rate
- Meta: Reach Frequency、Brand Awareness Lift
- TikTok: Brand Lift Study、View-Through Rate
```

---

## 三、平台能力深度对比

### 3.1 出价系统对比

| 出价类型 | Google Ads | Meta Ads | TikTok Ads | DV360 |
|---------|-----------|----------|-----------|-------|
| **CPC** | ✅ Enhanced CPC | ✅ Manual CPC | ✅ Manual CPC | ✅ pCPC |
| **CPM** | ✅ Target CPM | ✅ Target CPM | ✅ Target CPM | ✅ vCPM |
| **oCPM** | ❌ (via PMax) | ✅ Optimized CPM | ✅ oCPM | ✅ oCPM |
| **tCPA** | ✅ Target CPA | ✅ Target Cost per Result | ✅ tCPA | ✅ Target CPA |
| **tROAS** | ✅ Target ROAS | ✅ Target Cost per Result | ✅ tROAS | ✅ Target ROAS |
| **Smart Bidding** | ✅ Maximize Conv. | ✅ Advantage+ | ✅ Smart Bidding | ✅ Bid Surge |
| **Portfolio Bidding** | ✅ Campaign Groups | ✅ Portfolio Bids | ✅ 无 | ✅ 无 |

**关键洞察：**
- Google 的 Smart Bidding 生态最完善（10+ 策略）
- Meta 的 Advantage+ 自动程度最高
- TikTok 的出价策略相对有限但增长快
- DV360 的 Bid Surge 是独有的动态调价能力

### 3.2 归因系统对比

```
归因窗口期对比：

Google Ads:
├── Last Click: 默认30天点击 / 15天浏览
├── Data-Driven: 30天点击 / 7天浏览
├── Position-Based: 自定义
└── Time Decay: 自定义
→ 支持 BigQuery 导出原始事件

Meta Ads:
├── Last Interaction: 1天 / 7天 / 28天
├── First Interaction: 1天 / 7天 / 28天
├── Linear: 1天 / 7天 / 28天
├── Time Decay: 1天 / 7天 / 28天
└── Unique Clicks: 1天 / 7天 / 28天
→ 受 iOS 隐私限制，CAPI 补充

TikTok Ads:
├── Last Click: 7天
├── First Click: 7天
├── Linear: 7天
└── Time Decay: 7天
→ 归因窗口较短，窗口选择有限

DV360:
├── Last Click: 自定义
├── First Click: 自定义
├── Linear: 自定义
├── Time Decay: 自定义
├── Position-Based: 自定义
└── Data-Driven: 自定义
→ 与 GA4/ADH 深度整合，窗口最灵活
```

### 3.3 受众系统对比

| 能力 | Google Ads | Meta Ads | TikTok Ads | DV360 |
|------|-----------|----------|-----------|-------|
| 自定义受众 | ✅ Upload | ✅ Upload + URL | ✅ Upload + Pixel | ✅ RAI |
| Lookalike | ✅ Similar | ✅ Lookalike | ✅ Lookalike | ✅ 无 |
| 兴趣定向 | ✅ In-market | ✅ Detailed | ✅ Interest | ✅ In-Market |
| 上下文定向 | ✅ Keyword | ✅ Page/Content | ✅ Hashtag | ✅ Topic |
| 行为定向 | ✅ Life Events | ✅ Behaviors | ✅ Behaviors | ✅ Life Events |
| 再营销 | ✅ Website Visitors | ✅ Pixel + Engagement | ✅ Pixel + Engagement | ✅ Floodlight |
| 批量受众 | ✅Audience Manager | ✅Campaign Budget Pool | ✅ 无 | ✅ Dynamic Remarketing |

### 3.4 创意系统对比

```
创意格式支持对比：

                    Google          Meta            TikTok          DV360
单图广告            ✅ Search      ✅ FB/IG Feed   ✅ In-Feed       ✅ Display
多图轮播            ✅ Shopping    ✅ Carousel     ✅ Carousel      ✅ Display
视频广告            ✅ Video      ✅ Video        ✅ In-Feed/TopView ✅ Video
长视频(>60s)        ✅ YouTube    ✅ FB Video     ✅ N/A           ✅ Video
短视频(<15s)         ✅ Shorts     ✅ Reels        ✅ Spark         ✅ Display
原生广告            ✅ Discovery  ✅ Instant Exp. ✅ Native        ✅ Native
HTML5广告           ✅ Responsive ✅ N/A           ✅ N/A           ✅ Rich Media
动态产品广告        ✅ PMax/Shopping✅ DPA          ✅ TikTok Shop   ✅ Dynamic
交互式广告          ✅ VAST       ✅ Collection   ✅ Interactive   ✅ Rich Media
```

---

## 四、跨平台组织架构适配

### 4.1 小团队 (< 5 人)

```
推荐平台组合：Google + Meta

理由：
1. Google 覆盖搜索意图，Meta 覆盖社交兴趣，互补性强
2. 两个人可以同时运营两个平台
3. 预算集中，ROI 可衡量
4. 工具和流程相对标准化

排除平台：
- TikTok: 需要专门的短视频创意团队
- DV360: 需要专业的程序化投手，学习成本高
```

### 4.2 中团队 (5-20 人)

```
推荐平台组合：Google + Meta + TikTok

理由：
1. 三个平台覆盖主流用户场景
2. 可以组建专项小组：搜索组+社交组+短视频组
3. TikTok 的达人合作需要专门团队运营
4. 预算分配更灵活

可选扩展：
- DV360: 如果预算 > $50K/月且品牌诉求强
```

### 4.3 大团队 (> 20 人)

```
推荐平台组合：Google + Meta + TikTok + DV360（全平台）

理由：
1. 可以组建全栈投放团队
2. DV360 用于品牌大投放和程序化采买
3. 每个平台有专人负责深度优化
4. 跨平台数据打通和归因成为核心能力

关键角色配置：
├── 平台负责人 x4 (Google/Meta/TikTok/DV360)
├── 创意中心 x1 (跨平台创意产出)
├── 数据/归因专家 x1 (跨平台数据分析)
├── 竞价策略专家 x1 (跨平台出价优化)
└── 工具/自动化工程师 x1 (API集成/自动化)
```

---

## 五、跨平台数据打通方案

### 5.1 统一数据模型

```
跨平台 Campaign 统一模型：

interface UnifiedCampaign {
  // 平台识别
  platform: 'google' | 'meta' | 'tiktok' | 'dv360';
  platformCampaignId: string;
  
  // 通用属性
  name: string;
  status: 'active' | 'paused' | 'draft' | 'ended';
  campaignType: 'search' | 'display' | 'video' | 'shopping' | 'app' | 'brand';
  objective: 'conversion' | 'traffic' | 'awareness' | 'lead' | 'catalog';
  
  // 预算与排期
  dailyBudget?: number;
  lifetimeBudget?: number;
  startDate: string;
  endDate?: string;
  schedule?: { type: 'all_day' | 'scheduled', windows: [string, string][] };
  
  // 出价与目标
  biddingStrategy: string;
  targetCPA?: number;
  targetROAS?: number;
  targetCPC?: number;
  targetCPM?: number;
  
  // 定向
  geoTargets: string[];           // ISO 3166 国家代码
  ageRange?: [number, number];
  gender?: 'all' | 'male' | 'female';
  audienceSegments?: string[];
  
  // 性能指标 (统一为 USD)
  metrics: {
    impressions: number;
    clicks: number;
    spend: number;
    conversions: number;
    cvr: number;        // conversions / clicks
    cpc: number;        // spend / clicks
    cpm: number;        // spend / impressions * 1000
    roas: number;       // revenue / spend
  };
  
  // 时间戳
  createdAt: string;
  updatedAt: string;
}
```

### 5.2 ETL 管道架构

```
                    ┌─────────────────────────────────────┐
                    │         统一数据湖 (BigQuery)         │
                    │  unified_campaigns / unified_metrics  │
                    └──────────────┬──────────────────────┘
                                   │
        ┌──────────────────────────┼──────────────────────────┐
        │                          │                          │
        ▼                          ▼                          ▼
┌───────────────┐         ┌───────────────┐         ┌───────────────┐
│  Google Ads   │         │   Meta Ads    │         │   TikTok Ads  │
│    ETL       │         │    ETL        │         │    ETL        │
│  (Official)  │         │  (Graph API)  │         │  (Marketing   │
│              │         │               │         │   API)        │
└───────┬───────┘         └───────┬───────┘         └───────┬───────┘
        │                         │                         │
        └─────────────────────────┼─────────────────────────┘
                                  ▼
                    ┌───────────────────────────┐
                    │      DV360 ETL           │
                    │    (Display Video API)   │
                    └───────────────────────────┘
```

### 5.3 跨平台归因闭环

```
跨平台归因闭环架构：

┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  Google     │     │   Meta      │     │  TikTok     │
│  Ads       │     │   Ads       │     │  Ads        │
│             │     │             │     │             │
│ PMax自动    │     │ Advantage+  │     │ Spark+In-Feed│
│ 优化        │     │ 优化        │     │ 优化        │
└──────┬──────┘     └──────┬──────┘     └──────┬──────┘
       │                   │                   │
       └───────────────────┼───────────────────┘
                           ▼
              ┌────────────────────────┐
              │    统一归因引擎         │
              │  (Data-Driven / Shapley)│
              └───────────┬────────────┘
                          ▼
              ┌────────────────────────┐
              │   预算重分配 Agent      │
              │  (每24h自动调整)        │
              └───────────┬────────────┘
                          ▼
       ┌──────────────────┼──────────────────┐
       ▼                  ▼                  ▼
  Google PMax         Meta ASC          TikTok Smart
  +15%预算            +10%预算           +20%预算
  (基于增量贡献)      (基于增量贡献)     (基于增量贡献)
```

---

## 六、平台切换与迁移策略

### 6.1 从单一平台扩展到多平台

```
Phase 1: Google 单平台 → 增加 Meta (第2个月)
├── 承接 Google 验证过的产品和受众
├── 使用相同的落地页和转化追踪
└── 目标：测试 Meta 的增量价值

Phase 2: + TikTok (第3-4个月)
├── 建立短视频创意能力
├── 与达人合作测试 Spark Ads
└── 目标：年轻用户渗透

Phase 3: + DV360 (第6个月+)
├── 品牌大促期先小规模测试
├── 建立程序化投放团队
└── 目标：品牌声量+程序化采买优化
```

### 6.2 跨平台扩量策略

```
当单一平台遇到瓶颈时：

Google 扩量路径：
1. 扩大关键词匹配类型（精确→短语→广泛）
2. 启用 Search Partner 网络
3. PMax 扩展至 Discovery/YouTube/Gmail
4. 扩大地理定向
5. 利用 Similar Audiences

Meta 扩量路径：
1. 扩大 Advantage+ 受众范围
2. 启用 Expanded Reach
3. 测试新的创意格式（Reels/Instant Experience）
4. 扩展地理定向
5. 利用 Lookalike 扩展

TikTok 扩量路径：
1. 扩大兴趣定向范围
2. 测试 Pangle 网络
3. 增加短视频投放时长
4. 扩展地理位置
5. Spark Ads 达人合作扩量

DV360 扩量路径：
1. 扩大 Private Marketplace 交易
2. 增加 DSP 连接
3. 扩展程序化保量采购
4. 增加零售媒体网络
5. 利用 ADH 跨平台扩展
```

---

## 七、实战案例

### 7.1 跨境电商多平台投放案例

```
背景：某 DTC 品牌，月预算 $100K，主营家居用品

投放架构：

Google Ads ($40K/月, 40%)
├── PMax Shopping: $20K (直接转化主力)
├── Search Brand: $8K (品牌保护)
├── Search Generic: $7K (品类词捕获)
└── Display Re-engagement: $5K (再营销召回)

Meta Ads ($30K/月, 30%)
├── Advantage+ Shopping: $15K (智能扩量)
├── Lead Forms (邮箱收集): $5K (私域引流)
├── Retargeting (加购未支付): $7K
└── Brand Awareness: $3K

TikTok Ads ($20K/月, 20%)
├── In-Feed 转化: $10K
├── Spark Ads (达人): $5K
└── TikTok Shop: $5K

DV360 ($10K/月, 10%)
├── Brand Takeover (大促): $6K
├── Display Retargeting: $3K
└── Video Pre-roll: $1K

综合效果：
- 总转化: ~2,500 单/月
- 综合 ROAS: 3.2x
- 获客成本: $40/人
- 品牌搜索增长: +35%
```

### 7.2 游戏厂商 UA 案例

```
背景：某手游厂商，首月预算 $200K

平台分配：
- Meta Instant Games: $80K (40%) — 安装主力
- Google App Campaigns: $60K (30%) — 搜索+展示
- TikTok Spark Ads: $40K (20%) — 年轻用户
- DV360 YouTube: $20K (10%) — 品牌认知

关键策略：
1. Meta 负责大规模安装获取
2. Google 负责搜索拦截和高价值用户
3. TikTok 负责年轻用户和病毒式传播
4. DV360 YouTube 负责品牌故事和预告片

效果：
- CPI: $1.2
- D1留存: 35%
- D7留存: 18%
- LTV:CPI: 3.5x
```

---

## 八、常见陷阱与避坑指南

### 8.1 平台选择陷阱

| 陷阱 | 表现 | 解决方案 |
|------|------|---------|
| 盲目追新 | 看到 TikTok 火就全部转过去 | 基于目标受众数据做决策 |
| 平台依赖 | 90% 预算在一个平台 | 分散风险，建立 2-3 个主力平台 |
| 忽视搜索 | 只做社交不做 Google | 搜索意图最精准，必须保留 |
| DV360 过早上线 | 团队能力不足就开 DV360 | 先有程序化基础再上 DV360 |

### 8.2 跨平台冲突

```
常见问题：
1. 同一受众在多个平台重复曝光 → 频率控制 + 跨平台频次管理
2. 各平台归因数据不一致 → 建立统一归因模型，以 GA4/BigQuery 为准
3. 预算分配失衡 → 每周跨平台 Review，动态调整
4. 创意重复使用 → 各平台差异化创意策略
5. 账号关联风险 → 各平台独立注册，避免关联封号
```

### 8.3 数据治理陷阱

```
数据治理 checklist：
□ 所有平台安装统一 Pixel/Conversion API
□ 建立中央数据仓库（BigQuery 推荐）
□ 设定统一的指标定义和计算口径
□ 每日自动同步各平台数据
□ 建立异常检测告警机制
□ 定期 audit 各平台数据准确性
```

---

## 九、自测题

### Q1: 一个预算 $30K/月的中小电商，应该优先选择哪两个平台？

<details>
<summary>点击查看答案</summary>

**Google + Meta**。理由：
1. Google 覆盖搜索意图，转化效率最高
2. Meta 覆盖社交兴趣，可以扩量和再营销
3. TikTok 需要短视频创意能力，$30K 预算不足以支撑
4. DV360 学习成本太高，不适合小预算

建议分配：Google 60% ($18K)，Meta 40% ($12K)。
</details>

### Q2: 如何判断是否应该引入 DV360？

<details>
<summary>点击查看答案</summary>

判断标准：
1. **预算门槛**: 月预算 > $50K 且程序化广告占 20%+
2. **团队能力**: 有专人或外包程序化投放经验
3. **品牌诉求**: 需要大规模品牌曝光 + 程序化采买
4. **数据需求**: 需要 ADH 跨平台归因
5. **合规要求**: 需要品牌安全分级和可见性保障

如果以上有 3 项满足，可以考虑引入 DV360。
</details>

### Q3: 跨平台归因结果不一致时，以哪个平台为准？

<details>
<summary>点击查看答案</summary>

优先级排序：
1. **BigQuery + GA4** — 自建数据仓库，唯一真相源
2. **Google PMax** — 数据驱动归因，窗口最长
3. **Meta CAPI** — 服务器端数据，比客户端可靠
4. **各平台内建归因** — 仅作参考，各有偏差

最佳实践：建立一个统一的归因模型（如 Shapley Value），在 BigQuery 中计算各平台的真实增量贡献。
</details>

---

## 十、快速决策树

```
开始
 │
 ├─ 主要目标是品牌曝光？ ──→ 是 ──→ DV360 + YouTube + Meta Brand
 │
 └─ 否（效果导向）
      │
      ├─ 目标受众年龄？
      │    ├─ 18-24 ──→ TikTok 必投
      │    ├─ 25-34 ──→ Meta + TikTok
      │    ├─ 35+ ──→ Google + Meta
      │    └─ 全年龄 ──→ Google + Meta
      │
      ├─ 产品类型？
      │    ├─ 实体商品 ──→ Google Shopping + Meta DPA
      │    ├─ 数字产品 ──→ Google App Campaigns + Meta
      │    ├─ 服务/咨询 ──→ Google Search + Meta Lead
      │    └─ 游戏 ──→ Meta UA + Google App + TikTok
      │
      └─ 月预算？
           ├─ <$10K ──→ 单平台（Google 或 Meta 二选一）
           ├─ $10K-$50K ──→ Google + Meta
           ├─ $50K-$200K ──→ Google + Meta + TikTok
           └─ >$200K ──→ 全平台 + DV360
```

---

## 十一、附录：平台 API 能力速查

| 能力 | Google | Meta | TikTok | DV360 |
|------|--------|------|--------|-------|
| OAuth 认证 | ✅ | ✅ | ✅ | ✅ Service Account |
| 批量操作 | ✅ Streaming | ⚠️ 有限 | ⚠️ 有限 | ✅ Batch |
| 实时推送 | ⚠️ Limited | ✅ Webhook | ✅ Webhook | ✅ Webhook |
| 异步操作 | ✅ Async Mutate | ⚠️ Limited | ✅ Async | ⚠️ Limited |
| GraphQL | ❌ | ✅ | ❌ | ❌ |
| gRPC | ✅ | ❌ | ❌ | ❌ |
| SDK | ✅ Python/Java/Go | ✅ Python/Node | ❌ | ✅ Python/Java |
| Sandbox | ✅ | ✅ | ✅ | ⚠️ 需申请 |

---

*本文档作为四大广告平台战略选型的基础参考，建议结合实际业务数据定期更新。*
