# DV360 API 官方文档精读与实战

## 一、DV360 官方架构

### 1.1 官方定义与定位

**Google 官方定义：**
> Display & Video 360 (DV360) 是企业级程序化广告平台，支持跨媒体、跨渠道的广告投放和管理。

**核心价值：**
- 跨媒体投放：展示、视频、音频、电视、零售媒体
- 多 DSP 接入：通过 Exchange 连接多个广告交换平台
- 实时竞价：基于 RTB 的程序化购买
- 数据驱动：结合 Google Ads Data Hub 实现跨平台归因
- 企业级管理：支持多层级账户结构和批量操作

### 1.2 账户层级结构

**官方层级：**

```
360 Connector (360 连接器)
├── Advertisers (广告主)
│   ├── Insertion Orders (IO，订单项)
│   │   ├── Line Items (线条项目)
│   │   │   ├── Creatives (创意)
│   │   │   ├── Targeting (定向)
│   │   │   └── Schedule (排期)
│   │   └── Budget (预算)
│   ├── Partners (合作伙伴)
│   └── Users (用户)
├── Campaigns (广告系列)
├── Reports (报告)
└── Tools (工具)
```

### 1.3 交易类型

**官方交易类型：**

| 类型 | 说明 | 适用场景 |
|------|------|----------|
| Programmatic Guaranteed (PG) | 程序化保量采购 | 品牌大额投放 |
| Private Market Place (PMP) | 私有市场交易 | 优质库存采购 |
| Preferred Deal (PD) | 优先交易 | 优先购买权 |
| Open Auction | 公开竞价 | 常规投放 |

### 1.4 创意格式

**官方创意格式：**

| 格式 | 尺寸 | 说明 |
|------|------|------|
| 横幅广告 | 728x90, 300x250 | 标准尺寸 |
| 矩形广告 | 336x280, 300x600 | 大尺寸 |
| 原生广告 | 自适应 | 与内容融合 |
| HTML5 广告 | 自适应 | 富媒体交互 |
| 视频广告 | 多种比例 | 前贴片、中贴片、后贴片 |

## 二、核心 API 端点实战

### 2.1 认证与授权

**OAuth2 Service Account 流程：**

```
1. 创建 Google Cloud 项目
2. 启用 DV360 API
3. 创建 Service Account
4. 下载 JSON 密钥文件
5. 在 DV360 中授权 Service Account
6. 使用 JWT 签名获取 access_token
7. 调用 API
```

### 2.2 广告主管理

**获取广告主列表：**

```
GET /displayvideo/v2/advertisers
```

**创建广告主：**

```
POST /displayvideo/v2/advertisers
{
  "displayName": "My Advertiser"
}
```

### 2.3 订单项 (IO) 管理

**创建 IO：**

```
POST /displayvideo/v2/advertisers/{advertiser_id}/insertionOrders
{
  "displayName": "My IO",
  "flightEndDateMillis": 1735689600000,
  "flightStartDateMillis": 1704153600000,
  "lineItemCount": 5,
  "targetedGeoIds": ["2840"],
  "type": "PROGRAMMATIC_GUARANTEED"
}
```

### 2.4 线条项目 (Line Item) 管理

**创建 Line Item：**

```
POST /displayvideo/v2/advertisers/{advertiser_id}/insertionOrders/{insertion_order_id}/lineItems
{
  "displayName": "My Line Item",
  "advertiserId": "{advertiser_id}",
  "insertionOrderId": "{insertion_order_id}",
  "targetingType": "TARGETING_TYPE_UNSPECIFIED",
  "flightStartDateMillis": 1704153600000,
  "flightEndDateMillis": 1735689600000,
  "budgetId": "{budget_id}",
  "creativeRotation": {
    "type": "EQUAL_FRQUENCY"
  }
}
```

### 2.5 创意管理

**上传创意：**

```
POST /displayvideo/v2/advertisers/{advertiser_id}/lineItems/{line_item_id}/creatives
{
  "displayName": "My Creative",
  "type": "DISPLAY_VIDEO_AD"
}
```

## 三、定向策略

### 3.1 上下文定向

**关键词定向：**

```
POST /displayvideo/v2/advertisers/{advertiser_id}/lineItems/{line_item_id}/targetings
{
  "keywordTargetingDetails": [{
    "keyword": "running shoes"
  }]
}
```

**分类定向：**

```
POST /displayvideo/v2/advertisers/{advertiser_id}/lineItems/{line_item_id}/targetings
{
  "inMarketAudienceTargetingDetail": {
    "segmentId": "{segment_id}"
  }
}
```

### 3.2 受众定向

**第一方受众：**

```
POST /displayvideo/v2/advertisers/{advertiser_id}/lineItems/{line_item_id}/targetings
{
  "customAudienceTargetingDetail": {
    "customAudienceId": "{custom_audience_id}"
  }
}
```

**In-Market Audiences：**

| 类别 | 说明 | 示例 |
|------|------|------|
| 汽车购买者 | 正在购车的人 | 汽车买家 |
| 酒店预订者 | 正在预订酒店的人 | 旅行者 |
| 在线购物者 | 经常网购的人 | 电商用户 |
| 金融服务者 | 寻求金融服务的人 | 贷款申请者 |

**Life Events：**

| 事件 | 说明 | 适用产品 |
|------|------|----------|
| 新婚 | 最近结婚的人 | 家居、蜜月旅行 |
| 搬家 | 最近搬家的人 | 家具、装修 |
| 新工作 | 刚找到工作的人 | 职业装、理财 |
| 新生儿 | 最近有宝宝的人 | 母婴用品 |

## 四、测量与归因

### 4.1 转化追踪

**设置转化目标：**

```
POST /displayvideo/v2/advertisers/{advertiser_id}/lineItems/{line_item_id}/conversions
{
  "displayName": "Purchase Conversion",
  "type": "TYPE_UNSPECIFIED",
  "countingType": "ONE_PER_EVENT"
}
```

### 4.2 第三方测量

**集成第三方测量工具：**

| 工具 | 功能 | 集成方式 |
|------|------|----------|
| Moat | 品牌安全和可见性 | API 集成 |
| DoubleVerify | 品牌安全和可见性 | 标签集成 |
| Integral Ad Science | 广告质量 | API 集成 |
| comScore | 受众测量 | SDK 集成 |

### 4.3 归因模型

**官方归因模型：**

| 模型 | 说明 | 适用场景 |
|------|------|----------|
| Last Click | 最后一次点击 | 简单转化 |
| First Click | 首次点击 | 新客获取 |
| Linear | 均匀分配 | 全链路分析 |
| Time Decay | 时间衰减 | 短期转化 |
| Position Based | 首尾加权 | 品牌 + 转化 |
| Data-Driven | 数据驱动 | 优化投放 |

## 五、自测题

1. DV360 的核心功能是什么？
2. 四种交易类型各有什么特点？
3. 如何配置第三方测量工具？
4. 归因模型有哪些？各自适用什么场景？

## 六、动手验证

```bash
# 1. 配置 OAuth2 认证
# - 创建 Service Account
# - 下载密钥文件
# - 授权 DV360 API

# 2. 创建广告主
# - 设置广告主名称
# - 配置时区和货币

# 3. 创建 IO 和 Line Item
# - 设置预算
# - 设置排期
# - 选择交易类型

# 4. 上传创意
# - 准备创意素材
# - 上传到 DV360
# - 关联到 Line Item

# 5. 设置定向
# - 选择定向方式
# - 配置受众
# - 设置频率控制

# 6. 监控和优化
# - 查看报告
# - 分析表现
# - 调整策略
```
