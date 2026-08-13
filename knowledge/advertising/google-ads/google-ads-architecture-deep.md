# Google Ads 平台架构与商业逻辑深度解析

## 一、Google Ads 平台定位与商业本质

### 1.1 Google Ads 的商业本质

Google Ads 不是简单的广告平台，而是一个**实时意图匹配引擎**。它的核心价值在于：当用户带着明确意图搜索时，将最相关的商业信息在最合适的时机呈现给用户。

**商业模式的三个核心支柱：**

1. **意图捕获（Intent Capture）**
   - 搜索广告：用户主动表达需求时的即时匹配
   - 展示广告：基于用户画像的被动触达
   - 视频广告：内容消费过程中的品牌植入
   - 购物广告：购买决策时刻的产品展示

2. **实时竞价（Real-Time Bidding）**
   - 每次搜索/展示都是一次独立的拍卖
   - 毫秒级完成竞价、排序、展示决策
   - 基于质量评分的动态定价机制

3. **数据飞轮（Data Flywheel）**
   - 用户行为数据 → 模型优化 → 更精准的匹配 → 更多用户行为
   - 跨平台数据整合（搜索、YouTube、Gmail、Play、GDN）
   - 机器学习驱动的自动优化

**市场规模与竞争格局：**

| 指标 | Google Ads | Meta Ads | Amazon Ads | TikTok Ads |
|------|------------|----------|------------|------------|
| 2023 收入 | $188B | $135B | $43B | $12B |
| 全球份额 | 28% | 20% | 6% | 2% |
| 日均查询 | 85 亿次搜索 | 50 亿次展示 | 50 亿次商品浏览 | 30 亿次视频播放 |
| 主要优势 | 搜索意图 | 社交互动 | 购买意图 | 短视频创新 |
| 主要劣势 | 竞争激烈 | iOS 隐私影响 | 平台局限 | 数据追踪弱 |

### 1.2 Google Ads 生态系统全景

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        Google Ads Ecosystem Map                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  用户层 (Users)                                                               │
│  ├── 搜索用户 (Search Users) — 主动表达需求                                   │
│  ├── 浏览用户 (Browsing Users) — 内容消费中                                   │
│  ├── 购物用户 (Shoppers) — 购买决策中                                         │
│  └── 应用用户 (App Users) — 移动设备使用中                                     │
│                                                                              │
│  ↓ 用户意图信号                                                               │
│                                                                              │
│  广告平台层 (Ad Platforms)                                                    │
│  ├── Google Search (搜索广告)                                                 │
│  │   ├── 文本广告 (Text Ads)                                                  │
│  │   ├── 商品广告 (Shopping Ads)                                              │
│  │   ├── 应用广告 (App Ads)                                                   │
│  │   └── 电话广告 (Call Ads)                                                  │
│  ├── Google Display Network (展示广告)                                         │
│  │   ├── 横幅广告 (Banner Ads)                                                │
│  │   ├── 原生广告 (Native Ads)                                                │
│  │   ├── 响应式广告 (Responsive Ads)                                          │
│  │   └── HTML5 富媒体广告 (HTML5 Rich Media)                                  │
│  ├── YouTube (视频广告)                                                       │
│  │   ├── In-Stream (插播广告)                                                  │
│  │   ├── In-Feed (信息流广告)                                                  │
│  │   ├── Bumper (快闪广告)                                                    │
│  │   └── Shorts (短视频广告)                                                   │
│  ├── Google Shopping (购物广告)                                               │
│  │   ├── Standard Shopping (标准购物广告)                                      │
│  │   ├── Local Campaigns (本地广告)                                           │
│  │   └── Performance Max (全效果广告)                                         │
│  ├── Google App (应用广告)                                                    │
│  │   ├── App Installs (应用安装)                                              │
│  │   ├── App Engagement (应用互动)                                            │
│  │   └── App Retargeting (应用再营销)                                         │
│  └── Performance Max (全效果广告系列)                                         │
│      ├── 跨渠道自动投放                                                        │
│      ├── AI 驱动创意组合                                                       │
│      └── 全局预算优化                                                         │
│                                                                              │
│  ↓ 竞价与排序                                                                 │
│                                                                              │
│  竞价引擎层 (Bidding Engine)                                                  │
│  ├── 实时竞价系统 (Real-Time Bidding)                                          │
│  │   ├── 竞价请求处理 (Bid Request Processing)                                 │
│  │   ├── 用户信号分析 (User Signal Analysis)                                  │
│  │   ├── 预测模型推理 (Prediction Inference)                                  │
│  │   ├── 出价计算 (Bid Calculation)                                           │
│  │   └── 竞价决策 (Bid Decision)                                              │
│  ├── 质量评分系统 (Quality Score System)                                      │
│  │   ├── 预期点击率 (Expected CTR)                                            │
│  │   ├── 广告相关性 (Ad Relevance)                                            │
│  │   └── 落地页体验 (Landing Page Experience)                                 │
│  └── 预算管理系统 (Budget Management)                                         │
│      ├── 每日预算控制 (Daily Budget Control)                                   │
│      ├── 月度预算封顶 (Monthly Budget Cap)                                    │
│      └── 跨账户预算分配 (Cross-Account Allocation)                            │
│                                                                              │
│  ↓ 数据反馈                                                                  │
│                                                                              │
│  数据与归因层 (Data & Attribution)                                            │
│  ├── 转化追踪系统 (Conversion Tracking)                                        │
│  │   ├── Website Conversions (网站转化)                                       │
│  │   ├── App Conversions (应用转化)                                           │
│  │   ├── Call Conversions (电话转化)                                          │
│  │   └── Offline Conversions (线下转化)                                       │
│  ├── 归因分析引擎 (Attribution Engine)                                        │
│  │   ├── Last Click (最后点击)                                                │
│  │   ├── First Click (首次点击)                                               │
│  │   ├── Linear (线性)                                                       │
│  │   ├── Time Decay (时间衰减)                                                │
│  │   ├── Position-Based (位置基础)                                            │
│  │   └── Data-Driven (数据驱动)                                               │
│  └── 报告与分析 (Reporting & Analytics)                                       │
│      ├── 标准报告 (Standard Reports)                                          │
│      ├── 自定义报告 (Custom Reports)                                          │
│      └── API 数据导出 (API Data Export)                                       │
│                                                                              │
│  ↓ 优化反馈                                                                  │
│                                                                              │
│  机器学习层 (Machine Learning)                                                │
│  ├── 自动出价优化 (Automated Bidding Optimization)                            │
│  │   ├── Target CPA (目标每次转化费用)                                         │
│  │   ├── Target ROAS (目标广告支出回报率)                                      │
│  │   ├── Maximize Conversions (最大化转化)                                    │
│  │   └── Maximize Conversion Value (最大化转化价值)                            │
│  ├── 创意优化 (Creative Optimization)                                         │
│  │   ├── Responsive Ad Optimization (响应式广告优化)                           │
│  │   ├── Dynamic Creative Optimization (动态创意优化)                          │
│  │   └── Creative Performance Prediction (创意表现预测)                        │
│  └── 受众优化 (Audience Optimization)                                         │
│      ├── Similar Audience Generation (类似受众生成)                           │
│      ├── Audience Expansion (受众扩展)                                        │
│      └── Bid Adjustment by Audience (受众出价调整)                            │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 1.3 Google Ads 的核心竞争优势

**1. 意图数据的垄断性优势**

Google 拥有全球最完整的用户意图数据：

| 数据类型 | Google 拥有的数据 | 竞争对手缺乏的数据 |
|----------|------------------|-------------------|
| 搜索查询 | 所有语言的搜索历史 | 无 |
| 浏览行为 | GDN 200 万+网站的浏览数据 | 有限 |
| 视频观看 | YouTube 所有观看历史 | 仅自家平台 |
| 购物意图 | Google Shopping 商品浏览/购买 | 仅限电商平台 |
| 应用行为 | Google Play 安装/使用数据 | 有限 |
| 邮箱内容 | Gmail (历史数据，现有限) | 无 |
| 地图位置 | Google Maps 位置/搜索历史 | 有限 |
| 本地业务 | Google Business Profile | 有限 |

**2. 跨渠道的统一账户体系**

```
统一账户体系的优势：
├── 跨渠道归因
│   ├── 搜索 → 展示 → 转化的完整路径追踪
│   ├── 跨设备用户识别
│   └── 统一转化计数
├── 跨渠道预算分配
│   ├── 基于 ROI 自动分配预算
│   ├── 渠道间协同效应识别
│   └── 全局预算优化
└── 跨渠道受众复用
    ├── 搜索受众 → 展示投放
    ├── YouTube 观众 → 再营销
    └── 应用用户 → 类似受众扩展
```

**3. 机器学习的先发优势**

| 能力 | Google 的实现 | 行业平均水平 |
|------|--------------|-------------|
| 点击率预测 | Deep CTR 模型，实时训练 | 逻辑回归/浅层模型 |
| 转化率预测 | 多任务学习，跨渠道数据 | 单渠道数据 |
| 出价优化 | 强化学习，全局优化 | 规则/简单优化 |
| 创意生成 | AI 自动生成变体 | 手动创建 |
| 受众发现 | 深度学习识别模式 | 手动定向 |

## 二、账户体系架构深度解析

### 2.1 账户层级结构详解

```
┌─────────────────────────────────────────────────────────────────┐
│                    Google Ads 账户层级结构                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Level 0: Google Account (Google 账户)                           │
│  ├── 用于登录 Google Ads                                        │
│  └── 与管理员权限关联                                            │
│                                                                 │
│  Level 1: Manager Account (MCC/客户管理器账户)                    │
│  ├── 管理多个广告账户                                            │
│  ├── 跨账户报告和分析                                            │
│  ├── 批量操作和管理                                              │
│  ├── 模板功能（跨账户共享设置）                                   │
│  └── 合作伙伴门户（代理商使用）                                   │
│                                                                 │
│  Level 2: Customer (广告账户)                                    │
│  ├── 账单设置（付款方式、发票）                                   │
│  ├── 账户设置（时区、货币）                                      │
│  ├── 用户权限管理                                               │
│  ├── 转化追踪设置                                               │
│  ├── 链接账户（Merchant Center, GA, YouTube）                   │
│  └── 账户健康状态                                               │
│                                                                 │
│  Level 3: Campaign (广告系列)                                   │
│  ├── 广告目标（销售、潜在客户、流量等）                           │
│  ├── 广告系列类型（Search、Display、Video 等）                   │
│  ├── 预算设置（每日预算、预算分配策略）                           │
│  ├── 出价策略（手动 CPC、智能出价等）                            │
│  ├── 网络选择（搜索网络、展示网络）                               │
│  ├── 地理位置定向                                               │
│  ├── 语言定向                                                 │
│  ├── 设备偏好                                                 │
│  ├── 广告排期                                                 │
│  ├── 实验设置（A/B 测试）                                       │
│  └── 优化目标设置                                               │
│                                                                 │
│  Level 4: Ad Group (广告组)                                     │
│  ├── 关键词管理（添加、否定、匹配类型）                           │
│  ├── 受众管理（观察、定向）                                      │
│  ├── 出价设置（关键词出价、受众出价调整）                         │
│  ├── 广告创意管理（创建、编辑、优化）                             │
│  ├── 附加信息/资产管理                                          │
│  ├── 动态搜索广告设置                                           │
│  └── 商品分组（购物广告）                                        │
│                                                                 │
│  Level 5: Criterion (定向元素)                                   │
│  ├── Keywords (关键词)                                          │
│  │   ├── 匹配类型（精确、短语、广泛）                            │
│  │   ├── 出价                                                 │
│  │   └── 状态                                                 │
│  ├── Audiences (受众)                                          │
│  │   ├── 类似受众                                              │
│  │   ├── 再营销受众                                            │
│  │   └── 兴趣受众                                              │
│  ├── Locations (地理位置)                                       │
│  ├── Devices (设备)                                            │
│  ├── Schedules (排期)                                          │
│  └── Placements (投放位置)                                      │
│                                                                 │
│  Level 6: Ad & Asset (广告与资产)                                │
│  ├── Ads (广告创意)                                             │
│  │   ├── 响应式搜索广告 (RSA)                                   │
│  │   ├── 增强型 CPC 广告                                       │
│  │   └── 其他格式                                              │
│  ├── Assets (附加信息/资产)                                     │
│  │   ├── 站点链接                                              │
│  │   ├── 促销信息                                              │
│  │   ├── 来电展示                                              │
│  │   ├── 结构化摘要                                            │
│  │   ├── 应用链接                                              │
│  │   └── 图片资产                                              │
│  └── Extensions (附加信息)                                      │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 账户类型与适用场景

**标准账户 (Standard Account)：**

```
适用场景：
├── 单个品牌/业务
├── 预算 < $10,000/月
├── 广告系列 < 50 个
└── 不需要跨账户管理

优势：
├── 设置简单
├── 操作直观
└── 适合中小广告主
```

**客户管理器账户 (Manager Account / MCC)：**

```
适用场景：
├── 管理多个广告账户
├── 代理商管理客户账户
├── 大型企业多品牌管理
└── 预算 > $10,000/月

核心功能：
├── 批量操作（同时修改多个账户）
├── 跨账户报告（汇总分析）
├── 模板功能（共享设置）
├── 账户克隆（快速创建相似账户）
└── 注释系统（团队协作）
```

**合作伙伴账户 (Partner Account)：**

```
适用场景：
├── 广告代理商
├── 营销服务公司
└── Google 合作伙伴

特有功能：
├── 合作伙伴门户
├── 客户绩效管理报告
├── Google 认证要求
└── 合作伙伴折扣（符合条件时）
```

### 2.3 广告系列类型深度解析

**搜索广告系列 (Search Campaign)：**

```
工作原理：
1. 用户输入搜索词
2. Google 匹配相关关键词
3. 触发符合条件的广告组
4. 基于质量和出价排序
5. 展示最佳匹配的广告

关键配置：
├── 网络选择：
│   ├── 搜索网络 = Google Search + Search Partners
│   └── 展示网络 = GDN（搜索广告系列默认不包含）
├── 匹配类型策略：
│   ├── 广泛匹配 + 智能匹配扩展
│   ├── 短语匹配
│   └── 精确匹配
└── 出价策略：
    ├── 手动 CPC
    ├── 目标 CPA
    ├── 目标 ROAS
    └── 最大化转化
```

**展示广告系列 (Display Campaign)：**

```
工作原理：
1. 基于受众/关键词/主题定位
2. Google 在 GDN 中寻找匹配的广告位
3. 实时竞价获取展示
4. 展示适配尺寸的响应式广告

GDN 规模：
├── 200 万+ 网站和应用
├── 覆盖 90%+ 互联网用户
├── 每天 1 万亿+ 次展示
└── 支持 100+ 种语言

投放位置类型：
├── 网站横幅 (Website Banners)
├── 移动应用 (Mobile Apps)
├── Gmail 推广标签 (Gmail Promotions)
├── YouTube 侧边栏 (YouTube Sidekick)
└── Google 合作伙伴 (Google Properties)
```

**视频广告系列 (Video Campaign)：**

```
YouTube 广告格式详解：

1. In-Stream Ads (插播广告)
   ├── Skippable (可跳过)
   │   ├── 5 秒后可跳过
   │   ├── 完整观看 = 计费
   │   └── 适合品牌故事
   ├── Non-Skippable (不可跳过)
   │   ├── 15-30 秒
   │   ├── 100% 展示
   │   └── 适合品牌曝光
   └── Bumper Ads (快闪广告)
       ├── ≤6 秒
       ├── CPM 计费
       └── 适合频率控制

2. In-Feed Ads (信息流广告)
   ├── 搜索结果显示
   ├── YouTube 侧边栏
   ├── YouTube 首页推荐
   └── CPC 计费

3. Shorts Ads (短视频广告)
   ├── 全屏竖版
   ├── 滑动体验
   └── CPV 计费

4. Outstream Ads (外置视频广告)
   ├── 自动播放（静音）
   ├── 滚动到视口时播放
   └── 适合移动端
```

**购物广告系列 (Shopping Campaign)：**

```
工作原理：
1. 商品数据源 (Product Feed)
   ├── 通过 Google Merchant Center 管理
   ├── 包含：标题、描述、价格、图片、GTIN 等
   └── 定期同步到 Google Ads

2. 商品分组 (Product Groups)
   ├── All Products (所有商品)
   ├── 按分类细分 (Category)
   ├── 按品牌细分 (Brand)
   ├── 按自定义标签细分 (Custom Label)
   └── 设置不同出价

3. 广告展示
   ├── 搜索结果顶部/侧边
   ├── Shopping 标签页
   ├── Google Images
   └── Google Shopping App

Smart Shopping vs Standard Shopping：
├── Smart Shopping (已合并到 PMax)
│   ├── 自动投放位置
│   ├── 自动创意生成
│   └── ROAS 优化
└── Standard Shopping
    ├── 手动控制投放位置
    ├── 手动创意
    └── CPC 或 ROAS 出价
```

**应用广告系列 (App Campaign)：**

```
投放位置：
├── Google Search (搜索)
├── Google Play Store (应用商店)
├── Google Display Network (展示网络)
├── YouTube (视频)
└── Gmail (邮件)

优化目标：
├── App Installs (应用安装)
│   ├── 新用户获取
│   └── 最大化安装量
├── In-App Actions (应用内行动)
│   ├── 注册、购买、游戏关卡等
│   └── 基于价值优化
└── App Engagement (应用互动)
    ├── 回访用户
    └── 提升活跃度
```

**全效果广告系列 (Performance Max Campaign)：**

```
核心价值：
├── 跨所有 Google 广告资源自动投放
├── AI 驱动的广告组合优化
├── 基于目标和受众信号自动寻找转化
└── 只需提供素材和目标，其余交给 AI

所需素材组：
├── 文本素材
│   ├── 3-15 个标题 (最多 30 字符)
│   ├── 2-4 个描述 (最多 90 字符)
│   └── 显示路径 (2 个，各 15 字符)
├── 图片素材
│   ├── 16:1 横版 (1200x628)
│   ├── 1:1 方形 (1200x1200)
│   └── 9:16 竖版 (1536x640)
├── 视频素材
│   ├── 16:9 横版视频 (至少 15 秒)
│   └── 或上传现有 YouTube 视频
├── Logo
│   └── 1:1 方形 (1200x1200)
└── 媒体库 (可选)
    └── 提供更多素材供 AI 组合

受众信号 (Audience Signals)：
├── 自定义受众 (Custom Segments)
│   ├── 搜索关键词
│   ├── 网址
│   └── App
├── 用户数据受众 (Customer Lists)
├── 类似受众 (Lookalike Audiences)
└── Google 受众 (Google Audiences)

优势：
├── 自动化程度最高
├── 跨渠道覆盖最广
├── AI 优化效果最好
└── 管理成本最低

劣势：
├── 控制力最弱
├── 透明度最低
└── 不适合需要精细控制的场景
```

### 2.4 出价策略深度解析

**自动出价策略对比：**

| 策略 | 优化目标 | 数据要求 | 适用场景 | 控制程度 |
|------|----------|----------|----------|----------|
| Maximize Clicks | 最多点击 | 无 | 引流、品牌曝光 | 低（设预算和 CPC 上限） |
| Maximize Conversions | 最多转化 | 15+ 转化/30 天 | 转化量优化 | 中（可设 CPA 上限） |
| Target CPA | 目标每次转化费用 | 15+ 转化/30 天 | 成本可控的转化 | 高（设目标 CPA） |
| Target ROAS | 目标广告支出回报率 | 15+ 转化/30 天 | 收入最大化 | 高（设目标 ROAS） |
| Maximize Conversion Value | 最大化转化价值 | 无 | 收入优化 | 中（可设 ROAS 上限） |
| Viewable CPV | 最多可见视频观看 | 无 | 视频品牌曝光 | 低（设 CPV 出价） |

**智能出价算法原理：**

```
Target CPA 出价决策流程：

1. 收集实时信号
   ├── 用户信号
   │   ├── 搜索历史
   │   ├── 浏览行为
   │   ├── 设备类型
   │   ├── 地理位置
   │   └── 时间上下文
   ├── 广告信号
   │   ├── 关键词相关性
   │   ├── 广告质量评分
   │   └── 创意吸引力
   └── 竞争信号
       ├── 同类竞价者
       ├── 当前竞价水平
       └── 库存稀缺性

2. 预测转化概率
   ├── 使用深度学习模型
   ├── 实时推理 (<100ms)
   └── 输出转化概率 p(conversion)

3. 计算最优出价
   ├── 目标 CPA = $10
   ├── 出价 = 目标 CPA × p(conversion) × 调整系数
   └── 考虑预算约束和频率控制

4. 参与竞价
   ├── 提交出价到拍卖
   ├── 等待结果
   └── 记录结果用于模型训练
```

**手动出价 vs 自动出价决策树：**

```
选择出价策略
├── 有足够的转化数据吗？(15+/30天)
│   ├── 是 → 有收入优化目标吗？
│   │   ├── 是 → Target ROAS
│   │   └── 否 → Target CPA
│   └── 否 → 有明确的 CPC 控制需求吗？
│       ├── 是 → Manual CPC
│       └── 否 → Maximize Conversions (积累数据)
```

## 三、核心概念深度解析

### 3.1 质量评分 (Quality Score) 详解

**质量评分的三大组成要素：**

```
质量评分 (1-10 分)
├── 预期点击率 (Expected CTR) — 40% 权重
│   ├── 基于关键词历史 CTR
│   ├── 考虑广告相关性
│   ├── 考虑附加信息使用情况
│   └── 实时预测
├── 广告相关性 (Ad Relevance) — 30% 权重
│   ├── 关键词与广告文案匹配度
│   ├── 广告组主题聚焦度
│   └── 标题中包含关键词
└── 落地页体验 (Landing Page Experience) — 30% 权重
    ├── 页面加载速度
    ├── 移动端友好度
    ├── 内容相关性
    ├── 导航清晰度
    └── 隐私政策
```

**质量评分对 CPC 的影响：**

```
广告排名公式：
广告排名 = 最高出价 × 质量评分

实际 CPC 公式：
实际 CPC = (下一名广告排名 / 自身质量评分) + $0.01

示例：
├── 广告 A: 出价 $5.00, 质量评分 10
│   ├── 广告排名 = $5.00 × 10 = $50.00
│   └── 实际 CPC = ($40.00/10) + $0.01 = $4.01
├── 广告 B: 出价 $4.00, 质量评分 8
│   ├── 广告排名 = $4.00 × 8 = $32.00
│   └── 实际 CPC = ($32.00/8) + $0.01 = $4.01
└── 广告 C: 出价 $3.50, 质量评分 6
    ├── 广告排名 = $3.50 × 6 = $21.00
    └── 无法赢得展示

关键洞察：
├── 高质量评分可以降低 CPC
├── 质量评分高 1 分，CPC 可降低 20-30%
└── 优化质量评分比提高出价更有效
```

**质量评分优化实战：**

```
预期点击率优化 (40% 权重)
├── 使用相关关键词
│   └── 确保关键词出现在广告标题中
├── 添加吸引人的广告文案
│   └── 突出独特卖点和行动号召
├── 使用附加信息
│   └── 站点链接、促销信息等增加占用空间
└── A/B 测试广告变体
    └── 找到 CTR 最高的组合

广告相关性优化 (30% 权重)
├── 广告组主题聚焦
│   └── 每个广告组 5-20 个相关关键词
├── 关键词与广告文案高度相关
│   └── 关键词出现在标题和描述中
└── 使用关键词插入
    └── {KeyWord:默认文案} 动态插入

落地页体验优化 (30% 权重)
├── 提高页面加载速度
│   └── 目标：<3 秒加载完成
├── 移动端友好设计
│   └── 响应式布局，触摸友好
├── 内容与广告高度相关
│   └── 广告承诺的内容在落地页清晰展示
├── 清晰的导航和信息架构
│   └── 用户能快速找到目标信息
└── 明确的行动号召
    └── 突出的 CTA 按钮，简化的转化流程
```

### 3.2 关键词匹配类型深度解析

**五种匹配类型对比：**

| 匹配类型 | 语法 | 示例 | 触发条件 | 流量范围 | 控制精度 |
|----------|------|------|----------|----------|----------|
| 广泛匹配 | keyword | running shoes | 相关变体、同义词、相关搜索 | 最宽 | 最低 |
| 广泛匹配 + 修饰符 | +running +shoes | +running +shoes | 包含所有修饰词的任何顺序 | 宽 | 低 |
| 短语匹配 | "running shoes" | "running shoes" | 包含完整短语，前后可有其他词 | 中等 | 中 |
| 精确匹配 | [running shoes] | [running shoes] | 完全匹配或密切变体 | 窄 | 高 |
| 消极匹配 | -free | -free | 排除包含该词的搜索 | 排除 | 最高 |

**匹配类型演变（Google 的变化）：**

```
历史变化：
├── 2010 年前：精确匹配最常用
├── 2010-2017：广泛匹配主导，配合大量否定关键词
├── 2017-2020：智能匹配引入，广泛匹配更聪明
└── 2020 至今：广泛匹配 + 智能扩展，强调负向关键词

当前最佳实践：
├── 广泛匹配 + 紧密变体
│   └── 依赖 Google 的智能匹配算法
├── 配合大量否定关键词
│   └── 精确否定不相关流量
├── 短语匹配用于核心关键词
│   └── 平衡流量和控制
└── 精确匹配用于高价值关键词
    └── 最大化控制和出价
```

**否定关键词策略：**

```
否定关键词层级管理：

Level 1: 账户级别否定
├── 行业通用否定词
│   ├── free, cheap, DIY (产品相关)
│   └── job, career, salary (招聘相关)
└── 历史无效词库
    └── 从搜索词报告中积累的否定词

Level 2: 广告系列级别否定
├── 品牌无关词
│   └── 与品牌无关的通用词
├── 竞品词 (如需排除)
│   └── 不想投放的竞争对手品牌
└── 不相关产品线
    └── 该系列不销售的产品

Level 3: 广告组级别否定
├── 不相关搜索词
│   └── 与广告组主题无关的词
├── 低质量流量词
│   └── 高点击低转化的词
└── 无关产品词
    └── 该广告组不推广的产品

搜索词报告优化流程：
1. 每周查看搜索词报告
2. 识别高转化搜索词 → 添加为关键词
3. 识别低转化/无效搜索词 → 添加为否定关键词
4. 分析搜索词趋势 → 发现新机会
5. 持续迭代否定词库
```

### 3.3 附加信息 (Assets) 详解

**附加信息类型与效果：**

| 类型 | 说明 | 对 CTR 的提升 | 适用场景 |
|------|------|--------------|----------|
| 站点链接 | 添加额外链接到广告 | +10-15% | 多页面引导 |
| 促销信息 | 展示促销活动 | +8-12% | 限时优惠 |
| 来电展示 | 显示电话号码 | +5-10% | 电话转化 |
| 应用链接 | 引导下载应用 | +15-20% | 应用推广 |
| 结构化摘要 | 展示产品特性 | +5-8% | 多产品对比 |
| 定位扩展 | 显示地理位置 | +10-15% | 本地业务 |
| 图片 | 添加图片 | +15-30% | 视觉展示 |
| 优惠码 | 提供折扣代码 | +5-10% | 促销转化 |

**响应式搜索广告 (RSA) 最佳实践：**

```
RSA 结构要求：
├── 标题：3-15 个 (每个最多 30 字符)
├── 描述：2-4 个 (每个最多 90 字符)
├── 显示路径：2 个 (每个最多 15 字符)
└── 最终 URL：1 个

标题策略（15 个标题覆盖所有场景）：
├── 品牌标题 (3-5 个)
│   ├── 包含品牌名称
│   ├── 品牌 + 产品
│   └── 品牌 + 卖点
├── 产品标题 (3-5 个)
│   ├── 产品名称
│   ├── 产品 + 特性
│   └── 产品 + 场景
├── 促销标题 (2-3 个)
│   ├── 折扣信息
│   ├── 限时优惠
│   └── 免费配送
├── 行动号召 (2-3 个)
│   ├── Shop Now
│   ├── Buy Today
│   └── Learn More
└── 差异化标题 (2-3 个)
    ├── 独特卖点
    ├── 社会证明
    └── 痛点解决

描述策略（4 个描述覆盖所有角度）：
├── 描述 1：产品特性 + 优势
├── 描述 2：促销信息 + 紧迫感
├── 描述 3：社会证明 + 信任建立
└── 描述 4：行动号召 + 低风险承诺
```

## 四、自测题

1. Google Ads 的三大核心竞争优势是什么？
2. 质量评分的三大组成要素及其权重分别是多少？
3. 五种关键词匹配类型各有什么特点？如何组合使用？
4. Target CPA 和 Target ROAS 的适用场景有何不同？
5. Performance Max 广告系列需要哪些素材？适合什么场景？

## 五、动手验证

```bash
# 访问 https://ads.google.com

# - 选择目标：销售
# - 选择类型：Search
# - 设置预算：$50/天
# - 选择出价策略：Maximize Clicks

# - 命名：Running Shoes
# - 添加关键词：[running shoes], "men running shoes", running shoes
# - 添加否定关键词：[free], [cheap]

# - 添加 5 个标题
# - 添加 2 个描述
# - 设置最终 URL

# - 站点链接：Shop Now, Sale Items
# - 促销信息：Summer Sale - 50% Off

# - 检查关键词质量评分
# - 分析影响质量评分的因素
# - 实施优化措施
```

## 六、Go 源码级实现：Google Ads API 客户端

### 6.1 竞价请求处理器

```go
package googleads

import (
	"context"
	"fmt"
	"log"
	"sync"
	"time"
)

// BidRequest 封装一次广告竞价请求
type BidRequest struct {
	AdUnitID    string
	UserID      string
	Timestamp   time.Time
	Keywords    []string
	ContextTags []string
	DeviceType  string
	GeoLocation GeoTarget
	Budget      float64
}

// GeoTarget 地理位置目标
type GeoTarget struct {
	CountryCode string
	City        string
	Lat, Lng    float64
	RadiusMeters int
}

// AdCandidate 竞价候选广告
type AdCandidate struct {
	AdID       string
	CampaignID string
	BidAmount  float64
	QualityScore float32
	eCPM       float64
	Format     string
	CreativeID string
}

// BidResponse 竞价响应
type BidResponse struct {
	WinningAd *AdCandidate
	eCPM      float64
	LatencyMs float64
	Decision  string // "win"/"lose"/"no_fill"
}

// BidEngine 竞价引擎核心
type BidEngine struct {
	mu          sync.RWMutex
	candidateDB map[string][]*AdCandidate // campaignID -> candidates
	qsModel     QualityScoreModel
	bidOptimizer BidOptimizer
	logger      *log.Logger
}

// NewBidEngine 创建竞价引擎
func NewBidEngine(logger *log.Logger) *BidEngine {
	return &BidEngine{
		candidateDB: make(map[string][]*AdCandidate),
		logger:      logger,
	}
}

// CalculateQualityScore 计算质量评分（核心算法）
// eCPM = bid * QS, QS = CTR预测 * CVR预测 * 体验分
func (be *BidEngine) CalculateQualityScore(req *BidRequest, ad *AdCandidate) float32 {
	// 1. CTR 预测（基于历史点击数据 + 上下文特征）
	pCTR := be.qsModel.PredictCTR(req, ad)
	
	// 2. CVR 预测（基于点击后的转化漏斗）
	pCVR := be.qsModel.PredictCVR(req, ad)
	
	// 3. 落地页体验分（1.0-5.0，Google内部评分）
	lpageScore := be.calculateLandingPageScore(ad)
	
	// 4. 广告相关性（关键词与广告的匹配度）
	relevance := be.calcRelevance(req.Keywords, ad)
	
	// 综合质量评分 = pCTR * pCVR * lpageScore * relevance
	qs := pCTR * pCVR * (lpageScore / 5.0) * relevance
	
	// 归一化到 0-10 范围
	if qs > 10.0 {
		qs = 10.0
	}
	
	return float32(qs)
}

// calcRelevance 计算关键词与广告的相关性
func (be *BidEngine) calcRelevance(keywords []string, ad *AdCandidate) float32 {
	// BM25 相似度算法
	score := 0.0
	adText := ad.AdID // 简化：实际应使用广告文案
	
	for _, kw := range keywords {
		// 精确匹配最高分，部分匹配递减
		if kw == adText {
			score += 1.0
		} else if contains(kw, adText) || contains(adText, kw) {
			score += 0.5
		} else {
			// 语义相似度（需要嵌入向量）
			score += 0.1
		}
	}
	
	return float32(score / float32(len(keywords)))
}

// SubmitBid 提交竞价请求，返回竞价结果
func (be *BidEngine) SubmitBid(ctx context.Context, req *BidRequest) (*BidResponse, error) {
	start := time.Now()
	
	be.mu.RLock()
	defer be.mu.RUnlock()
	
	// 1. 获取该请求下所有候选广告
	var candidates []*AdCandidate
	for _, ads := range be.candidateDB {
		for _, ad := range ads {
			if ad.Budget <= 0 {
				continue // 预算耗尽
			}
			candidates = append(candidates, ad)
		}
	}
	
	if len(candidates) == 0 {
		return &BidResponse{Decision: "no_fill"}, nil
	}
	
	// 2. 计算每个候选的 eCPM
	type scoredAd struct {
		ad   *AdCandidate
		eCPM float64
	}
	
	scored := make([]scoredAd, 0, len(candidates))
	for _, ad := range candidates {
		qs := be.CalculateQualityScore(req, ad)
		ad.QualityScore = qs
		ad.eCPM = ad.BidAmount * float64(qs/10.0)
		scored = append(scored, scoredAd{ad, ad.eCPM})
	}
	
	// 3. 按 eCPM 降序排序
	for i := 0; i < len(scored); i++ {
		for j := i + 1; j < len(scored); j++ {
			if scored[j].eCPM > scored[i].eCPM {
				scored[i], scored[j] = scored[j], scored[i]
			}
		}
	}
	
	// 4. 取最高 eCPM 的广告
	latency := time.Since(start).Seconds() * 1000
	resp := &BidResponse{
		WinningAd: scored[0].ad,
		eCPM:      scored[0].eCPM,
		LatencyMs: latency,
		Decision:  "win",
	}
	
	be.logger.Printf("Bid: ad=%s eCPM=%.4f latency=%.2fms", 
		resp.WinningAd.AdID, resp.eCPM, resp.LatencyMs)
	
	return resp, nil
}

// AddCandidates 批量添加候选广告
func (be *BidEngine) AddCandidates(campaignID string, ads []*AdCandidate) {
	be.mu.Lock()
	defer be.mu.Unlock()
	be.candidateDB[campaignID] = ads
}

func contains(a, b string) bool {
	return len(a) >= len(b) && (a == b || findSubstring(a, b))
}

func findSubstring(s, sub string) bool {
	for i := 0; i <= len(s)-len(sub); i++ {
		if s[i:i+len(sub)] == sub {
			return true
		}
	}
	return false
}
```

### 6.2 预算控制与频次限制

```go
package googleads

import (
	"sync"
	"time"
)

// BudgetController 预算控制器 - 防止超投
type BudgetController struct {
	mu         sync.Mutex
	campaigns  map[string]*CampaignBudget
	userFreq   map[string]*FrequencyCap // userID -> frequency data
}

// CampaignBudget 广告系列预算
type CampaignBudget struct {
	CampaignID string
	DailyLimit float64
	SpendToday float64
	EndTime    time.Time
	TotalBudget float64
	SpendTotal float64
}

// NewBudgetController 创建预算控制器
func NewBudgetController() *BudgetController {
	return &BudgetController{
		campaigns: make(map[string]*CampaignBudget),
		userFreq:  make(map[string]*FrequencyCap),
	}
}

// CheckBudget 检查预算是否充足
func (bc *BudgetController) CheckBudget(campaignID string, bidAmount float64) bool {
	bc.mu.Lock()
	defer bc.mu.Unlock()
	
	budget, ok := bc.campaigns[campaignID]
	if !ok {
		return true // 无预算限制
	}
	
	// 日预算检查
	if budget.SpendToday+bidAmount > budget.DailyLimit {
		return false
	}
	
	// 总预算检查
	if budget.SpendTotal+bidAmount > budget.TotalBudget {
		return false
	}
	
	// 时间窗口检查
	if time.Now().After(budget.EndTime) {
		return false
	}
	
	return true
}

// RecordSpend 记录花费
func (bc *BudgetController) RecordSpend(campaignID string, amount float64) {
	bc.mu.Lock()
	defer bc.mu.Unlock()
	
	if budget, ok := bc.campaigns[campaignID]; ok {
		budget.SpendToday += amount
		budget.SpendTotal += amount
	}
}

// FrequencyCap 频次控制
type FrequencyCap struct {
	mu       sync.Mutex
	caps     map[string]int     // adID -> impression count today
	window   time.Duration      // 统计窗口
	resetAt  time.Time
}

// NewFrequencyCap 创建频次控制器
func NewFrequencyCap(window time.Duration) *FrequencyCap {
	return &FrequencyCap{
		caps:    make(map[string]int),
		window:  window,
		resetAt: time.Now().Add(window),
	}
}

// CanShow 检查是否可以展示（频次控制）
func (fc *FrequencyCap) CanShow(userID, adID string) bool {
	fc.mu.Lock()
	defer fc.mu.Unlock()
	
	// 窗口过期重置
	if time.Now().After(fc.resetAt) {
		fc.caps = make(map[string]int)
		fc.resetAt = time.Now().Add(fc.window)
	}
	
	count := fc.caps[adID]
	return count < 3 // 默认每个广告每天最多展示3次
}

// RecordImpression 记录展示
func (fc *FrequencyCap) RecordImpression(adID string) {
	fc.mu.Lock()
	defer fc.mu.Unlock()
	fc.caps[adID]++
}
```

### 6.3 实时竞价 HTTP 服务

```go
package googleads

import (
	"encoding/json"
	"net/http"
	"time"
)

// BidService 提供竞价 HTTP 接口
type BidService struct {
	engine    *BidEngine
	budgetCtl *BudgetController
	server    *http.Server
}

// NewBidService 创建竞价服务
func NewBidService(engine *BidEngine, budgetCtl *BudgetController) *BidService {
	return &BidService{
		engine:    engine,
		budgetCtl: budgetCtl,
	}
}

// Start 启动 HTTP 服务
func (bs *BidService) Start(addr string) error {
	mux := http.NewServeMux()
	mux.HandleFunc("/bid", bs.handleBid)
	mux.HandleFunc("/health", bs.handleHealth)
	
	bs.server = &http.Server{
		Addr:         addr,
		Handler:      mux,
		ReadTimeout:  100 * time.Millisecond, // 极低超时
		WriteTimeout: 200 * time.Millisecond,
	}
	
	return bs.server.ListenAndServe()
}

func (bs *BidService) handleBid(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
		return
	}
	
	var req BidRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, "invalid request", http.StatusBadRequest)
		return
	}
	
	// 执行竞价（必须在 50ms 内完成）
	ctx, cancel := context.WithTimeout(r.Context(), 50*time.Millisecond)
	defer cancel()
	
	resp, err := bs.engine.SubmitBid(ctx, &req)
	if err != nil {
		http.Error(w, "bid failed", http.StatusInternalServerError)
		return
	}
	
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(resp)
}

func (bs *BidService) handleHealth(w http.ResponseWriter, r *http.Request) {
	w.WriteHeader(http.StatusOK)
	w.Write([]byte(`{"status":"healthy","service":"google-ads-bid"}`))
}
```

### 6.4 关键词质量评分系统

```go
package googleads

// QualityScoreModel 质量评分模型接口
type QualityScoreModel interface {
	PredictCTR(req *BidRequest, ad *AdCandidate) float64
	PredictCVR(req *BidRequest, ad *AdCandidate) float64
}

// LRModel 逻辑回归质量评分模型（简化版）
type LRModel struct {
	Weights []float64
	Bias    float64
}

// PredictCTR 使用逻辑回归预测 CTR
func (m *LRModel) PredictCTR(req *BidRequest, ad *AdCandidate) float64 {
	// 特征工程：提取关键特征
	features := []float64{
		float64(len(req.Keywords)),              // 关键词数量
		float64(len(req.ContextTags)),           // 上下文标签数
		m.matchScore(req.Keywords, ad),          // 匹配分数
		m.keywordQuality(req.Keywords),          // 关键词质量
		m.adRelevance(ad),                       // 广告相关性
		float64(m.deviceClickRate(req.DeviceType)), // 设备点击率
	}
	
	// 线性组合 + sigmoid
	logit := m.bias
	for i, f := range features {
		if i < len(m.Weights) {
			logit += m.Weights[i] * f
		}
	}
	
	return 1.0 / (1.0 + exp(-logit))
}

func (m *LRModel) matchScore(keywords []string, ad *AdCandidate) float64 {
	score := 0.0
	for _, kw := range keywords {
		if kw == ad.AdID {
			score += 3.0 // 精确匹配
		} else if contains(kw, ad.AdID) {
			score += 1.5 // 短语匹配
		} else {
			score += 0.5 // 广泛匹配
		}
	}
	return score / float64(len(keywords))
}

func (m *LRModel) keywordQuality(keywords []string) float64 {
	// 基于历史 CTR 的关键词质量分
	return 2.0 // 简化
}

func (m *LRModel) adRelevance(ad *AdCandidate) float64 {
	return 3.0 // 简化
}

func (m *LRModel) deviceClickRate(device string) float64 {
	rates := map[string]float64{
		"mobile": 0.03,
		"desktop": 0.02,
		"tablet": 0.025,
	}
	return rates[device]
}

func exp(x float64) float64 {
	if x > 700 { return 1e308 }
	if x < -700 { return 0 }
	// 简单近似
	result := 1.0
	for i := 1; i <= 20; i++ {
		result += pow(x, float64(i)) / factorial(float64(i))
	}
	return result
}

func pow(base, expVal float64) float64 {
	result := 1.0
	for i := 0; i < int(expVal); i++ {
		result *= base
	}
	return result
}

func factorial(n float64) float64 {
	if n <= 1 { return 1 }
	return n * factorial(n-1)
}
```

### 6.5 Google Ads API 集成

```go
package googleads

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"time"
)

// GoogleAdsClient Google Ads API 客户端
type GoogleAdsClient struct {
	APIKey      string
	DeveloperToken string
	BaseURL     string
	HTTPClient  *http.Client
}

// NewGoogleAdsClient 创建 API 客户端
func NewGoogleAdsClient(apiKey, devToken string) *GoogleAdsClient {
	return &GoogleAdsClient{
		APIKey:       apiKey,
		DeveloperToken: devToken,
		BaseURL:      "https://googleads.googleapis.com/v17",
		HTTPClient: &http.Client{
			Timeout: 30 * time.Second,
		},
	}
}

// CreateCampaign 创建广告系列
func (c *GoogleAdsClient) CreateCampaign(customerID string, campaign *Campaign) (*CampaignResponse, error) {
	url := fmt.Sprintf("%s/customers/%s/campaigns", c.BaseURL, customerID)
	
	body, err := json.Marshal(campaign)
	if err != nil {
		return nil, fmt.Errorf("marshal campaign: %w", err)
	}
	
	req, err := http.NewRequest("POST", url, bytes.NewReader(body))
	if err != nil {
		return nil, fmt.Errorf("create request: %w", err)
	}
	
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("developer-token", c.DeveloperToken)
	req.Header.Set("login-customer-id", customerID)
	
	resp, err := c.HTTPClient.Do(req)
	if err != nil {
		return nil, fmt.Errorf("execute request: %w", err)
	}
	defer resp.Body.Close()
	
	if resp.StatusCode != http.StatusOK {
		bodyBytes, _ := io.ReadAll(resp.Body)
		return nil, fmt.Errorf("API error %d: %s", resp.StatusCode, string(bodyBytes))
	}
	
	var result CampaignResponse
	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		return nil, fmt.Errorf("decode response: %w", err)
	}
	
	return &result, nil
}

// GetReport 获取报告数据
func (c *GoogleAdsClient) GetReport(customerID, reportType string, dateRange DateRange) ([]ReportRow, error) {
	url := fmt.Sprintf("%s/customers/%s:generateReport", c.BaseURL, customerID)
	
	reqBody := map[string]interface{}{
		"report_type": reportType,
		"date_range": map[string]string{
			"start_date": dateRange.Start.Format("2006-01-02"),
			"end_date":   dateRange.End.Format("2006-01-02"),
		},
		"columns": []string{
			"campaign.id",
			"campaign.name",
			"metrics.impressions",
			"metrics.clicks",
			"metrics.costMicros",
			"metrics.conversions",
		},
	}
	
	body, err := json.Marshal(reqBody)
	if err != nil {
		return nil, err
	}
	
	req, err := http.NewRequest("POST", url, bytes.NewReader(body))
	if err != nil {
		return nil, err
	}
	
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("developer-token", c.DeveloperToken)
	req.Header.Set("login-customer-id", customerID)
	
	resp, err := c.HTTPClient.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	
	var result ReportResponse
	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		return nil, err
	}
	
	return result.Rows, nil
}

// Campaign 广告系列定义
type Campaign struct {
	Name            string `json:"name"`
	AdvertisingChannelType string `json:"advertising_channel_type"` // SEARCH, DISPLAY, SHOPPING
	Budget            *Budget `json:"budget,omitempty"`
	BiddingStrategy   string `json:"bidding_strategy_type"`     // MANUAL_CPC, TARGET_ROAS
	Status            string `json:"status"`                    // ENABLED, PAUSED
}

// Budget 预算配置
type Budget struct {
	Name          string `json:"name"`
	DeliveryMethod string `json:"delivery_method"` // STANDARD, ACCELERATED
	MicroAmount   int64  `json:"micro_amount"` // 微金额（1 USD = 1,000,000 micros）
}

// CampaignResponse API 响应
type CampaignResponse struct {
	ResourceName string `json:"resource_name"`
	ID           int64  `json:"id"`
}

// DateRange 日期范围
type DateRange struct {
	Start, End time.Time
}

// ReportResponse 报告响应
type ReportResponse struct {
	Rows []ReportRow `json:"rows"`
}

// ReportRow 报告行
type ReportRow struct {
	CampaignID      int64   `json:"campaign_id"`
	Impressions     int64   `json:"impressions"`
	Clicks          int64   `json:"clicks"`
	CostMicros      int64   `json:"cost_micros"`
	Conversions     float64 `json:"conversions"`
}
```

### 6.6 自动出价优化器

```go
package googleads

import (
	"math"
	"sync"
	"time"
)

// BidOptimizer 出价优化器接口
type BidOptimizer interface {
	Optimize(currentBid float64, metrics *AdMetrics) float64
}

// TargetROAS 目标 ROAS 出价策略
type TargetROAS struct {
	targetROAS    float64 // 例如 400% = 4.0
	learningRate  float64
	mu            sync.Mutex
	history       []AdMetrics
}

// AdMetrics 广告指标
type AdMetrics struct {
	Clicks      int64
	Conversions float64
	Cost        float64
	Revenue     float64
	Timestamp   time.Time
}

// NewTargetROAS 创建目标 ROAS 优化器
func NewTargetROAS(targetROAS float64) *TargetROAS {
	return &TargetROAS{
		targetROAS:   targetROAS,
		learningRate: 0.1,
	}
}

// Optimize 基于目标 ROAS 调整出价
func (t *TargetROAS) Optimize(currentBid float64, metrics *AdMetrics) float64 {
	t.mu.Lock()
	defer t.mu.Unlock()
	
	if metrics.Conversions <= 0 || metrics.Revenue <= 0 {
		return currentBid // 没有转化数据，保持当前出价
	}
	
	actualROAS := metrics.Revenue / metrics.Cost
	roasDiff := actualROAS - t.targetROAS
	
	// ROAS 调整公式：new_bid = current_bid * (1 + learning_rate * roas_diff)
	adjustment := 1.0 + t.learningRate*roasDiff
	
	// 限制调整幅度在 20% 以内
	if adjustment > 1.2 {
		adjustment = 1.2
	} else if adjustment < 0.8 {
		adjustment = 0.8
	}
	
	newBid := currentBid * adjustment
	
	// 确保出价不为负
	if newBid < 0.01 {
		newBid = 0.01
	}
	
	t.history = append(t.history, *metrics)
	
	// 自适应学习率：随着数据增多降低学习率
	if len(t.history) > 100 {
		t.learningRate = 0.05
	}
	
	return newBid
}

// MaximizeConversions 最大化转化出价策略
type MaximizeConversions struct {
	budget        float64
	currentSpend  float64
	conversionVal float64
}

func (m *MaximizeConversions) Optimize(currentBid float64, metrics *AdMetrics) float64 {
	remainingBudget := m.budget - m.currentSpend
	if remainingBudget <= 0 {
		return 0 // 预算耗尽
	}
	
	// 如果转化价值高，提高出价
	if m.conversionVal > 0 && metrics.Conversions > 0 {
		efficiency := metrics.Conversions / float64(metrics.Clicks)
		if efficiency > 0.05 { // 转化率 > 5%，提高出价
			return currentBid * 1.1
		}
	}
	
	return currentBid
}

// SmartBidding 智能出价（多策略融合）
type SmartBidding struct {
	strategies []BidOptimizer
	weights    []float64
}

// NewSmartBidding 创建智能出价
func NewSmartBidding() *SmartBidding {
	return &SmartBidding{
		strategies: []BidOptimizer{
			NewTargetROAS(300), // 300% ROAS
			&MaximizeConversions{},
		},
		weights: []float64{0.6, 0.4},
	}
}

// Optimize 多策略加权融合
func (sb *SmartBidding) Optimize(currentBid float64, metrics *AdMetrics) float64 {
	if len(sb.strategies) != len(sb.weights) {
		return currentBid
	}
	
	var weightedSum float64
	totalWeight := 0.0
	
	for i, strategy := range sb.strategies {
		adjusted := strategy.Optimize(currentBid, metrics)
		weightedSum += adjusted * sb.weights[i]
		totalWeight += sb.weights[i]
	}
	
	if totalWeight == 0 {
		return currentBid
	}
	
	return weightedSum / totalWeight
}

// 数值工具函数
func pow(x float64, n int) float64 {
	result := 1.0
	for i := 0; i < n; i++ {
		result *= x
	}
	return result
}

## 七、自测题

### Q1: Google Ads 竞价引擎中，eCPM 的计算公式是什么？为什么不用 bid 直接排序？

<details>
<summary>查看答案</summary>

**答案：**

eCPM = bid × QualityScore / 10

不使用 bid 直接排序的原因：
1. **用户体验优先**：Google 需要确保展示的广告与用户意图相关，低质量但高价的广告不应优先
2. **长期生态**：如果只看出价，低质广告商会无限加价，最终损害用户体验和平台长期收入
3. **质量评分维度**：CTR预测 × CVR预测 × 落地页体验 × 广告相关性
4. **实际效果**：高质量低出价广告可能打败低质量高出价广告，因为 eCPM 更高

**源码级细节：**
- QualityScore 在 1-10 范围，10 为最佳
- 竞价排序是降序排列，取最高 eCPM
- 实际支付采用广义第二价格（GSP）：获胜者支付略高于第二名 eCPM 的金额
- 质量评分每日更新，基于最近 7 天数据

</details>

### Q2: 如何实现 Google Ads 的预算控制和频次限制？生产环境需要考虑哪些边界情况？

<details>
<summary>查看答案</summary>

**答案：**

核心实现要点：
1. **预算控制器**使用 mutex 保护共享状态，每次竞价前 CheckBudget，竞价后 RecordSpend
2. **日预算**和**总预算**双重检查，防止超投
3. **频次控制**按用户ID+广告ID维度统计，窗口过期自动重置
4. **微金额**存储（1 USD = 1,000,000 micros），避免浮点精度问题

生产环境边界情况：
- **竞态条件**：高并发下同一预算可能被多个 goroutine 同时读取，必须用 sync.Mutex 或 CAS 操作
- **时钟漂移**：日预算切换依赖系统时间，多机部署时 NTP 同步必须准确
- **预算耗尽后的处理**：不应直接拒绝，应返回"no_fill"让 DSP 换其他广告
- **频次控制的内存占用**：亿级用户 × 百万级广告，需要 Redis 分布式计数而非本地 map
- **突增流量**：预算控制器需要在 50ms 内完成检查，否则影响竞价延迟

</details>

### Q3: Google Ads 的质量评分模型中，逻辑回归的特征工程如何设计？为什么选择这些特征？

<details>
<summary>查看答案</summary>

**答案：**

核心特征及其选择理由：

| 特征 | 类型 | 选择理由 |
|------|------|----------|
| 关键词匹配分数 | 分类（精确/短语/广泛） | 直接决定广告与搜索意图的相关性 |
| 历史 CTR | 数值 | 最直接的点击意愿信号 |
| 广告文案长度 | 数值 | 过长影响可读性，过短信息不足 |
| 落地页加载速度 | 数值 | 影响用户体验和转化率 |
| 设备类型 | 分类 | 不同设备点击行为差异显著 |
| 时间段 | 分类 | 早晚高峰 CTR 差异大 |
| 地理位置 | 分类 | 地域相关广告需要地理匹配 |
| 关键词质量分 | 数值 | 关键词本身的历史表现 |

**源码级实现：**
- 线性组合 + sigmoid 函数将 logits 映射到 [0,1]
- sigmoid(x) = 1/(1+e^(-x))
- 权重通过离线训练（梯度下降）获得
- 线上推理只需一次矩阵乘法 + sigmoid，计算量极小

</details>
