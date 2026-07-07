# Meta Marketing API 官方文档精读与实战

## 一、Meta Marketing API 官方架构

### 1.1 官方定义与定位

**Meta 官方定义：**
> 市场营销 API 是一系列图谱 API 端点及其他功能的集合，可用于帮助您在各 Meta 技术平台上发布广告。在 Facebook、Instagram、Messenger 和 WhatsApp 上发布广告之前，建议您先了解 Meta 的广告系列架构。

**覆盖平台：**
- Facebook
- Instagram
- Messenger
- WhatsApp

### 1.2 广告系列架构（Campaign Structure）

**官方层级结构：**

```
Business Manager (商务管理平台)
├── Ad Account (广告账户)
│   ├── Campaign (广告系列)
│   │   ├── Objective (目标)
│   │   ├── Budget (预算)
│   │   ├── Bidding Strategy (竞价策略)
│   │   └── Schedule (排期)
│   │   ├── Ad Set (广告组)
│   │   │   ├── Targeting (定向)
│   │   │   ├── Placements (投放位置)
│   │   │   ├── Daily Budget (每日预算)
│   │   │   └── Bid Cap / Cost Cap (出价上限)
│   │   │   ├── Ad (广告)
│   │   │   ├── Creative (创意素材)
│   │   │   ├── Primary Text (主要文案)
│   │   │   ├── Headline (标题)
│   │   │   ├── Description (描述)
│   │   │   ├── CTA (行动号召)
│   │   │   └── Tracking URL (跟踪 URL)
│   │   └── Assets (附加信息)
└── Pixel (像素) / Conversion API (转化 API)
```

**关键概念：**

| 对象 | 说明 | 必填字段 |
|------|------|----------|
| Campaign | 广告系列，定义目标和预算 | name, objective, status |
| Ad Set | 广告组，定义定向和投放位置 | name, placement, targeting, status |
| Ad | 广告创意，定义素材和文案 | name, creative, status |

### 1.3 八大广告目标（Official Objectives）

**Meta 官方定义的八大目标：**

```
Awareness (认知)
├── Brand Awareness (品牌认知)
│   └── 优化目标：品牌认知度提升
└── Reach (触达)
    └── 优化目标：最多触达人数

Consideration (考虑)
├── Traffic (流量)
│   └── 优化目标：最多链接点击量
├── Engagements (互动)
│   └── 优化目标：最多互动量
│       ├── 帖子互动
│       ├── 页面点赞
│       ├── Messenger 对话
│       ├── 视频观看
│       ├── 活动参与
│       └── 消息互动
├── App Installs (应用安装)
│   └── 优化目标：最多应用安装量
├── Video Views (视频观看)
│   └── 优化目标：最多视频观看量
├── Lead Generation (潜在客户)
│   └── 优化目标：最多潜在客户数
└── Messages (消息)
    └── 优化目标：最多消息量

Conversion (转化)
├── Conversions (转化)
│   └── 优化目标：最多转化量
├── Catalog Sales (商品销售)
│   └── 优化目标：最多销售金额
└── Store Traffic (到店流量)
    └── 优化目标：最多到店人数
```

### 1.4 竞价策略（官方 Bidding Guide）

**Meta 官方竞价策略：**

| 策略 | 说明 | 适用场景 |
|------|------|----------|
| Lowest Cost (最低成本) | 在预算内获得最多结果 | 大多数场景 |
| Cost Cap (成本上限) | 控制平均每次结果成本 | 成本敏感 |
| Bid Cap (出价上限) | 设置最高出价 | 竞争激烈 |
| Target ROAS (目标广告支出回报率) | 目标广告支出回报率 | 电商 |
| Minimum ROAS (最低广告支出回报率) | 最低广告支出回报率 | 电商 |

**计费方式：**

| 方式 | 说明 | 适用场景 |
|------|------|----------|
| CPM (千次展示) | 按千次展示付费 | 品牌曝光 |
| CPC (每次点击) | 按点击付费 | 引流 |
| CPI (每次安装) | 按安装付费 | 应用推广 |
| CPA (每次转化) | 按转化付费 | 效果广告 |
| vCPM (千次可见展示) | 按千次可视展示付费 | 视频广告 |

## 二、核心 API 端点实战

### 2.1 广告系列管理

**创建广告系列：**

```
POST /v20.0/{ad-account-id}/campaigns
{
  "name": "My Campaign",
  "objective": "SALES",
  "status": "PAUSED",
  "daily_budget": 1000,
  "special_categories": []
}
```

**获取广告系列：**

```
GET /v20.0/{campaign-id}
Fields: id, name, objective, status, daily_budget, optimized_campaign_goal
```

**更新广告系列：**

```
POST /v20.0/{campaign-id}
{
  "status": "ACTIVE"
}
```

### 2.2 广告组管理

**创建广告组：**

```
POST /v20.0/{ad-account-id}/adsets
{
  "name": "My Ad Set",
  "campaign_id": "{campaign-id}",
  "billing_event": "IMPRESSIONS",
  "optimization_goal": "LINK_CLICKS",
  "bid_amount": 100,
  "daily_budget": 1000,
  "targeting": {
    "geo_locations": {
      "countries": ["US"]
    },
    "age_min": 18,
    "age_max": 65,
    "genders": [1]
  },
  "status": "PAUSED"
}
```

**投放位置 (Placements)：**

```
自动投放位置 (Automatic Placements):
├── facebook_feed
├── facebook_instant_articles
├── facebook_instream
├── facebook_search
├── facebook_about
├── facebook_marketplace
├── facebook_group
├── facebook_page_likes
├── facebook_event
├── facebook_reels
├── facebook_story
├── instagram_explore
├── instagram_story
├── instagram_feed
├── instagram_audience_network
├── instagram_direct
├── instagram_reels
├── instagram_search
├── instagram_profile
├── facebook_instagram_audience_network
├── facebook_instagram_instream
├── facebook_instagram_story
├── facebook_instagram_reels
├── facebook_instagram_search
├── facebook_instagram_profile
├── facebook_instagram_direct

手动投放位置 (Manual Placements):
├── 选择特定位置
└── 排除低效位置
```

### 2.3 广告创意管理

**创建广告：**

```
POST /v20.0/{ad-account-id}/ads
{
  "name": "My Ad",
  "adset_id": "{adset-id}",
  "status": "PAUSED",
  "creative": {
    "body": "Check out our new products!",
    "title": "New Products",
    "message": "Check out our new products!",
    "object_store_url": "https://www.example.com/",
    "object_type": "PRODUCT",
    "call_to_action": {
      "type": "SHOP_NOW"
    },
    "image_hash": "{image-hash}"
  }
}
```

**广告创意格式：**

| 格式 | 说明 | 规格 |
|------|------|------|
| 单图广告 | 使用单张图片 | 1200x628 像素 |
| 视频广告 | 使用视频内容 | MP4, MOV, ≤4GB |
| 轮播广告 | 可滑动的多图/视频 | 2-10 张卡片 |
| 集合广告 | 全屏背景 + 产品网格 | 1080x1080 |
| 即时体验广告 | 快速加载的全屏体验 | 自适应 |
| 动态广告 | 基于商品目录自动展示 | 需商品目录 |

### 2.4 受众管理

**核心受众 (Core Audiences)：**

```
人口统计定向 (Demographics):
├── 年龄和性别
├── 教育
├── 工作经验
├── 父母状态
├── 语言
└── 关系状态

兴趣定向 (Interests):
├── 兴趣类别
├── 行为
└── 连接

行为定向 (Behaviors):
├── 购买行为
├── 数字活动
├── 设备操作系统
├── 旅行行为
└── 生活动态
```

**自定义受众 (Custom Audiences)：**

| 类型 | 说明 | 数据来源 |
|------|------|----------|
| 客户列表 | 基于邮箱/电话 | CRM 数据 |
| 网站活动 | 基于 Pixel 事件 | 网站访客 |
| 应用活动 | 基于 SDK 事件 | 应用用户 |
| 联系人列表 | 基于手机号/邮箱 | 线下数据 |
| 页面互动 | 基于页面互动 | Facebook 页面 |
| 视频观看 | 基于视频观看 | YouTube/Facebook |

**类似受众 (Lookalike Audiences)：**

```
创建类似受众:
├── 种子受众 (Seed Audience)
│   ├── 客户列表
│   ├── 网站访客
│   └── 应用用户
├── 目标国家
└── 规模 (1-10%)
    ├── 1%: 最相似
    ├── 2-5%: 平衡
    └── 10%: 最大范围
```

## 三、转化追踪

### 3.1 Pixel 事件

**标准事件 (Standard Events)：**

| 事件 | 说明 | 参数 |
|------|------|------|
| PageView | 页面浏览 | 无 |
| ViewContent | 查看内容 | content_type, content_ids |
| Search | 搜索 | search_string |
| SearchResult | 搜索结果 | search_string, num_results |
| AddToCart | 加入购物车 | content_type, content_ids, value, num_items |
| AddToWishlist | 加入收藏 | content_type, content_ids, value, num_items |
| AddPaymentInfo | 添加支付信息 | value, currency, content_type, content_ids |
| InitiateCheckout | 开始结算 | value, currency, content_type, content_ids |
| Schedule | 预约 | value, currency, content_type, content_ids |
| Subscribe | 订阅 | value, currency, content_type, content_ids |
| StartTrial | 开始试用 | value, currency, content_type, content_ids |
| Contact | 联系 | content_type, content_ids |
| Donate | 捐赠 | value, currency |
| FindLocation | 查找地点 | content_type, content_ids |
| CompleteRegistration | 完成注册 | content_type, content_ids |
| CompleteTutorial | 完成教程 | value, currency |
| AchieveLevel | 达成等级 | level, success |
| UnlockAchievement | 解锁成就 | achievement |
| Rate | 评分 | rating, max_rating |
| Recommend | 推荐 | value, currency |
| SpendCredits | 花费积分 | value, currency |
| ContactContent | 联系内容 | content_type, content_ids |
| StartCheckout | 开始结账 | value, currency, num_items |
| AddInformation | 添加信息 | value, currency |
| Purchase | 购买 | value, currency, content_type, content_ids |
| Lead | 潜在客户 | content_type, content_ids |
| CompletePayment | 完成付款 | value, currency |
| SubmitApplication | 提交申请 | value, currency |

**自定义事件 (Custom Events)：**

```
创建自定义事件:
├── 事件名称
├── 事件类型
├── 事件参数
└── 事件值
```

### 3.2 Conversion API (CA)

**Pixel + CA 双轨追踪：**

```
Pixel 追踪:
├── 浏览器事件
├── 客户端数据
└── 易受 iOS 影响

CA 追踪:
├── 服务器事件
├── 服务端数据
└── 不受 iOS 影响

匹配优化:
├── 发送用户哈希数据
├── 匹配 Pixel 和 CA 事件
└── 提高转化归因准确率
```

**CA 配置步骤：**

```
1. 设置服务器端追踪
   ├── 安装 SDK
   ├── 配置事件
   └── 测试数据回传
2. 优化事件匹配
   ├── 发送用户数据 (邮箱、手机)
   ├── 哈希处理
   └── 验证匹配率
3. 监控数据一致性
   ├── 对比 Pixel 和 CA 数据
   ├── 分析差异原因
   └── 优化匹配策略
```

## 四、成效分析 API

**关键指标：**

| 指标 | 说明 | 计算公式 |
|------|------|----------|
| Impressions | 展示量 | 广告展示次数 |
| Reach | 触达人数 | 唯一用户数 |
| Frequency | 频次 | 展示量/触达人数 |
| Clicks | 点击量 | 用户点击次数 |
| CTR | 点击率 | 点击量/展示量 |
| CPC | 单次点击费用 | 花费/点击量 |
| CPMA | 千人成本 | 花费/展示量 × 1000 |
| Conversions | 转化量 | 转化事件数 |
| CPA | 单次转化费用 | 花费/转化量 |
| ROAS | 广告支出回报率 | 转化价值/花费 |

**Insights API：**

```
获取广告组数据:
GET /v20.0/{adset-id}/insights
Fields: impressions, clicks, ctr, cpc, cpma, conversions, cost_per_total_action, roas
Time ranges: 7d, 14d, 30d, lifetime
Breakdowns: age, gender, country, region, city, device_platform
```

## 五、自测题

1. Meta Marketing API 覆盖哪些平台？
2. 八大广告目标各有什么特点？
3. 如何创建类似受众？
4. Pixel 和 Conversion API 的区别是什么？
5. 如何优化转化追踪数据？

## 六、动手验证

```bash
# 1. 创建广告系列
# - 选择目标
# - 设置预算
# - 选择出价策略

# 2. 创建广告组
# - 设置定向
# - 选择投放位置
# - 设置预算

# 3. 创建广告创意
# - 上传素材
# - 编写文案
# - 设置 CTA

# 4. 配置转化追踪
# - 安装 Pixel
# - 配置 Conversion API
# - 验证数据

# 5. 监控和优化
# - 查看 Insights
# - 分析表现
# - 调整策略
```
