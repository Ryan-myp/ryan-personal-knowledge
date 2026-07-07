# TikTok Marketing API 官方文档精读与实战

## 一、TikTok Marketing API 官方架构

### 1.1 官方定义与定位

**TikTok 官方定义：**
> TikTok Marketing API 是 TikTok 提供的广告管理平台接口，帮助广告主自动化广告创建、管理和优化流程。

**覆盖功能：**
- 广告系列管理
- 广告组管理
- 广告创意管理
- 受众管理
- 商品目录管理
- 像素事件追踪
- 数据报告与分析

### 1.2 账户体系

**官方层级结构：**

```
Business Center (商务中心)
├── Ad Accounts (广告账户)
│   ├── Campaigns (广告系列)
│   │   ├── Ad Groups (广告组)
│   │   │   ├── Creatives (创意)
│   │   │   └── Targeting (定向)
│   │   └── Budget (预算)
│   └── Pixels (像素)
├── Users (用户)
├── Payment Methods (支付方式)
├── Identity (身份)
│   ├── TT User (TT 用户)
│   └── Auth Code (授权码)
└── Catalogs (商品目录)
```

**Identity 两种类型：**

| 类型 | 说明 | 用途 |
|------|------|------|
| TT User | TikTok 用户身份 | 个人广告账户 |
| Auth Code | 授权码身份 | 代理商管理客户账户 |

**Auth Code 工作流程：**

```
1. 广告主登录 TikTok Ads Manager
2. 生成 Auth Code
3. 分享给代理商
4. 代理商使用 Auth Code 授权
5. 代理商可以管理广告账户
```

### 1.3 广告系列目标

**官方目标类型：**

| 目标 | 说明 | 适用场景 |
|------|------|----------|
| Sales (销售) | 促成网站或应用内购买 | 电商转化 |
| App Promotion (应用推广) | 推广移动应用 | 应用安装、应用内事件 |
| Lead Generation (潜在客户) | 收集潜在客户信息 | B2B、教育、金融 |
| Website Traffic (网站流量) | 引导用户访问网站 | 品牌曝光、引流 |
| Video Views (视频观看) | 提升视频观看量 | 品牌故事、内容推广 |
| Engagement (互动) | 提升帖子互动 | 品牌建设、社区运营 |

### 1.4 广告格式

**官方广告格式：**

| 格式 | 说明 | 适用场景 |
|------|------|----------|
| In-Feed Ads (信息流广告) | 出现在用户刷到的短视频信息流中 | 品牌曝光、转化 |
| Spark Ads (火花广告) | 使用达人有机视频投放广告 | 达人合作、原生内容 |
| TopView Ads (顶视图广告) | 用户打开 TikTok 时首屏展示 | 品牌大片、新品发布 |
| Brand Takeover (品牌 takeover) | 用户打开 TikTok 时展示的全屏广告 | 品牌曝光 |
| Branded Effects (品牌特效) | 品牌定制的 AR 滤镜、贴纸、音效 | 用户互动、病毒传播 |
| Branded Hashtag Challenge (品牌话题挑战) | 品牌发起的话题挑战活动 | 用户创作、病毒传播 |
| TikTok Shop Ads (商城广告) | TikTok 内电商闭环广告 | 电商转化 |
| Search Ads (搜索广告) | 搜索结果中的广告 | 精准投放 |

## 二、核心 API 端点实战

### 2.1 广告系列管理

**创建广告系列：**

```
POST /open_api/v1.3/campaign/create/
{
  "access_token": "{token}",
  "advertiser_id": "{advertiser_id}",
  "campaign": {
    "name": "My Campaign",
    "promote_object": {
      "object_type": "WEBSITE",
      "website_page_id": "{page_id}"
    },
    "daily_budget": 10000,
    "campaign_group_status": 1,
    "optimization_goal": "CLICK_THROUGH",
    "targeting": {
      "gender": 1,
      "ages": ["18-26"],
      "countries": ["US"],
      "interests": [{
        "id": "{interest_id}"
      }]
    }
  }
}
```

**获取广告系列：**

```
GET /open_api/v1.3/campaign/get/
{
  "access_token": "{token}",
  "advertiser_id": "{advertiser_id}",
  "filtering": [{
    "field": "CAMPAIGN_IDS",
    "operator": "IN",
    "values": ["{campaign_id}"]
  }]
}
```

### 2.2 广告组管理

**创建广告组：**

```
POST /open_api/v1.3/adgroup/create/
{
  "access_token": "{token}",
  "advertiser_id": "{advertiser_id}",
  "ad_group": {
    "name": "My Ad Group",
    "campaign_id": "{campaign_id}",
    "promote_object": {
      "object_type": "WEBSITE",
      "website_page_id": "{page_id}"
    },
    "daily_budget": 5000,
    "ad_group_status": 1,
    "bid_type": "AUTO_BID_TYPE_VALUE_MAXIMIZE_CONVERSIONS",
    "bid_amount": 100,
    "targeting": {
      "gender": 1,
      "ages": ["18-26"],
      "countries": ["US"],
      "interests": [{
        "id": "{interest_id}"
      }],
      "exclude_interests": [{
        "id": "{exclude_id}"
      }],
      "placements": ["AUTOMATIC_PLACEMENT_TYPE_ALL"]
    }
  }
}
```

**投放位置 (Placements)：**

| 位置 | 说明 | 适用场景 |
|------|------|----------|
| TikTok Feed (推荐页) | 用户主要浏览的信息流 | 大多数场景 |
| TikTok Search (搜索) | 搜索相关内容 | 精准投放 |
| TikTok Post (发布后) | 视频发布后 | Spark Ads |
| TikTok Marketplace (商城) | TikTok 商城 | 电商 |
| TikTok Series (系列) | 系列视频 | 长视频广告 |
| TikTok Live (直播) | 直播间 | 直播购物广告 |

### 2.3 广告创意管理

**创建广告：**

```
POST /open_api/v1.3/ad/create/
{
  "access_token": "{token}",
  "advertiser_id": "{advertiser_id}",
  "ad": {
    "name": "My Ad",
    "ad_group_id": "{ad_group_id}",
    "promotion_type": "PROMOTION_TYPE_LINK",
    "tracking_url": "{tracking_url}",
    "conversion_id": "{conversion_id}",
    "custom_conversion_id": "{custom_conversion_id}",
    "brand_safety": {
      "brand_safety_type": "BS_TYPE_STANDARD"
    },
    "run_time_settings": {
      "start_time": "{start_time}",
      "end_time": "{end_time}"
    },
    "ad_text_settings": {
      "primary_text": "Check out our new products!",
      "title": "New Products",
      "description": "Shop now and get 50% off!",
      "cta_type": "CTA_TYPE_DOWNLOAD"
    },
    "image": {
      "image_url": "{image_url}",
      "image_hash": "{image_hash}"
    }
  }
}
```

**创意素材要求：**

| 格式 | 尺寸 | 时长 | 说明 |
|------|------|------|------|
| 图片 | 1200x628 | - | 推荐尺寸 |
| 图片 | 1200x1200 | - | 方形 |
| 图片 | 1536x640 | - | 竖版 |
| 视频 | 1280x720 | 5-60 秒 | 横版 |
| 视频 | 720x1280 | 5-60 秒 | 竖版 |

### 2.4 受众管理

**兴趣定向：**

| 类别 | 示例兴趣 | 适用产品 |
|------|----------|----------|
| 时尚美妆 | Beauty, Fashion, Skincare | 化妆品、服装 |
| 游戏娱乐 | Gaming, Entertainment, Music | 游戏、音乐 App |
| 食品饮料 | Food, Cooking, Recipes | 食品、餐饮 |
| 运动健身 | Fitness, Health, Sports | 运动装备、健康食品 |
| 教育培训 | Education, Learning, Courses | 在线教育、培训 |

**行为定向：**

| 行为类型 | 说明 | 示例 |
|----------|------|------|
| 视频互动 | 点赞、评论、分享 | 高互动用户 |
| 达人互动 | 关注、观看直播 | 达人粉丝 |
| 电商行为 | 浏览、购买 | 电商用户 |
| 应用行为 | 下载、使用 | 应用用户 |

**自定义受众：**

| 类型 | 说明 | 数据要求 |
|------|------|----------|
| 客户列表 | 上传邮箱、手机号 | CSV 文件 |
| 网站活动 | Pixel 追踪 | 网站流量 |
| 应用活动 | SDK 追踪 | 应用用户 |
| 视频观看者 | 视频观看记录 | 观看数据 |
| 互动用户 | 帖子互动用户 | 互动数据 |

**类似受众：**

```
种子受众 (Seed Audience)
├── 客户列表
├── 网站访客
└── 应用用户
    ↓
TikTok 算法分析
├── 人口统计特征
├── 兴趣爱好
├── 行为模式
└── 社交关系
    ↓
类似受众 (Lookalike Audience)
├── 1% (最相似)
├── 2-5% (平衡)
└── 10% (最大范围)
```

## 三、像素与事件追踪

### 3.1 TikTok Pixel

**标准事件：**

| 事件 | 说明 | 参数 |
|------|------|------|
| PageVisit | 页面访问 | 无 |
| ViewContent | 查看内容 | content_type, content_id |
| Search | 搜索 | search_query |
| AddToCart | 加入购物车 | content_type, content_id, value, currency |
| AddToWishlist | 加入收藏 | content_type, content_id, value, currency |
| InitiateCheckout | 开始结算 | content_type, content_id, value, currency |
| Purchase | 购买 | content_type, content_id, value, currency |
| Lead | 潜在客户 | content_type, content_id, value, currency |
| CompleteRegistration | 完成注册 | content_type, content_id, value, currency |
| Subscribe | 订阅 | content_type, content_id, value, currency |
| Contact | 联系 | content_type, content_id |
| Schedule | 预约 | content_type, content_id, value, currency |
| StartTrial | 开始试用 | content_type, content_id, value, currency |
| AddPaymentInfo | 添加支付信息 | content_type, content_id, value, currency |

**事件追踪代码：**

```javascript
// TikTok Pixel 基础代码
<script>
  !function (w, d, t) {
    w.TiktokAnalyticsObject=t;var ttq=w[t]=w[t]||[];
    ttq.methods=["page","track","identify","instances","debug","off","on",
      "push"," setPage"," setGroup"," setCustomerId"," setPhone"," setEmail",
      " setOrder"," setUserConsent"," trackPageView"],
    ttq.methods.forEach(function(e){ttq[e]=ttq[e]||function(){
      var args=Array.prototype.slice.call(arguments,1);
      return ttq.push({e:e,a:args}),ttq}}),
    ttq.STATIC_ENDPOINT=tt.endpoint||"https://analytics.tiktok.com";
    var script=d.createElement(t);script.src="https://snaptiktok-1f46.kq07.com/sdk/v1/ta.js",
    script.async=!0,d.head.appendChild(script)}
  (window,document,"ttq");

  ttq.page();
</script>
```

### 3.2 转化追踪配置

**转化事件设置：**

```
1. 创建转化事件
   ├── 选择事件类型
   ├── 设置匹配方式
   └── 配置归因窗口

2. 验证事件
   ├── 测试事件发送
   ├── 检查事件匹配
   └── 确认数据回传

3. 优化事件
   ├── 调整匹配优先级
   ├── 优化事件参数
   └── 设置自定义参数
```

## 四、竞价与计费

### 4.1 出价策略

**官方出价策略：**

| 策略 | 说明 | 适用场景 |
|------|------|----------|
| Lowest Cost (最低成本) | 在预算内获得最多结果 | 大多数场景 |
| Cost Cap (成本上限) | 控制平均每次转化成本 | 成本敏感 |
| Bid Cap (出价上限) | 设置最高出价 | 竞争激烈 |
| Target CPA (目标每次转化费用) | 设定目标每次转化费用 | 转化目标 |
| Target ROAS (目标广告支出回报率) | 设定目标广告支出回报率 | 收入最大化 |

### 4.2 计费方式

| 方式 | 说明 | 适用场景 |
|------|------|----------|
| oCPM (目标千次展示) | 按千次展示付费，优化目标转化 | 大多数场景 |
| CPC (按点击付费) | 按点击付费 | 引流 |
| CPV (按观看付费) | 按视频观看付费 | 视频广告 |
| CPA (按转化付费) | 按转化付费 | 效果广告 |

## 五、自测题

1. TikTok Marketing API 的账户层级结构是怎样的？
2. 官方支持的广告格式有哪些？
3. 如何创建类似受众？
4. Pixel 标准事件有哪些？
5. 竞价策略和计费方式各有什么适用场景？

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

# 4. 配置 Pixel
# - 安装 Pixel 代码
# - 配置事件
# - 验证数据

# 5. 监控和优化
# - 查看数据报告
# - 分析表现
# - 调整策略
```
