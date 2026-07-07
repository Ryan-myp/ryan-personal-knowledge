# Meta Catalog 商品目录深度实战：从架构到投放

## 一、Catalog 商业本质

### 1.1 什么是 Catalog？

**Meta 官方定义：** Catalog 是商品信息的结构化数据库，用于动态展示商品广告（Dynamic Product Ads, DPA）。

**核心价值：**
- **自动化广告**：无需手动创建每个商品广告，系统自动匹配
- **精准再营销**：根据用户浏览行为展示相关商品
- **规模化投放**：支持数十万级商品同时投放
- **实时同步**：价格、库存、状态实时同步到广告

**适用场景：**
- 电商：商品再营销、新品推广、促销广告
- 旅游：酒店、航班、租车动态展示
- 房地产：房源动态展示
- 招聘：职位动态展示

### 1.2 Catalog 在 Meta 生态中的位置

```
Meta 广告生态系统
├── 广告账户 (Ad Account)
│   ├── 广告系列 (Campaign)
│   │   └── 目标: Catalog Sales (商品销售)
│   │       ├── 广告组 (Ad Set)
│   │       │   ├── 投放位置: Facebook/Instagram
│   │       │   ├── 受众: 类似受众/自定义受众
│   │       │   └── 出价: Target ROAS/Lowest Cost
│   │       └── 广告 (Ad)
│   │           └── 格式: Dynamic Product Ads (DPA)
│   │               ├── Product Set 选择
│   │               ├── 创意模板
│   │               └── 商品匹配
│   └── 商品目录 (Catalog)
│       ├── 商品 (Products)
│       ├── 商品集 (Product Sets)
│       └── 商品数据源 (Feeds)
├── Pixel (网站追踪)
│   └── ViewContent → content_ids
└── Conversion API (服务器追踪)
    └── Purchase → content_ids
```

## 二、Catalog 架构深度解析

### 2.1 核心对象关系

```
Catalog (商品目录)
├── Products (商品) — 核心数据单元
│   ├── id (必需) — 唯一标识
│   ├── title (必需) — 商品标题
│   ├── description — 商品描述
│   ├── image_url (必需) — 主图 URL
│   ├── price (必需) — 价格
│   ├── currency — 货币代码 (USD, CNY)
│   ├── availability — 库存状态 (in stock/out of stock/prevorder/backordered/discontinued)
│   ├── condition — 商品状态 (new/refurbished/used)
│   ├── brand — 品牌
│   ├── gtin — 全球贸易项目代码 (EAN, UPC, ISBN)
│   ├── mpn — 制造商零件编号
│   ├── product_type — 商品类型 (自定义层级)
│   ├── custom_label_0-4 — 自定义标签 (最多5个)
│   └── sale_price — 促销价
├── Product Sets (商品集) — 商品分组
│   ├── id — 商品集 ID
│   ├── name — 商品集名称
│   └── filter — 筛选规则 (JSON)
├── Product Feeds (商品数据源) — 数据上传方式
│   ├── API Upload — 实时 API 上传
│   ├── File Upload — CSV/TXT 文件上传
│   ├── Partner Integration — 合作伙伴集成
│   └── Scheduled Fetch — 定时拉取 RSS/URL
└── Product Catalogs (多个目录)
    └── 一个广告账户可创建多个 Catalog
```

### 2.2 商品字段详解

**必需字段：**

| 字段 | 类型 | 说明 | 示例 |
|------|------|------|------|
| id | String | 商品唯一 ID | "prod_12345" |
| title | String | 商品标题 | "Nike Air Max 2024" |
| image_url | String | 商品图片 URL | "https://..." |
| price | String | 商品价格 | "99.99 USD" |

**重要可选字段：**

| 字段 | 类型 | 说明 | 推荐度 |
|------|------|------|--------|
| description | String | 商品描述 | ⭐⭐⭐ |
| availability | Enum | 库存状态 | ⭐⭐⭐⭐⭐ |
| condition | Enum | 商品状态 | ⭐⭐⭐ |
| brand | String | 品牌 | ⭐⭐⭐⭐ |
| gtin | String | 全球贸易代码 | ⭐⭐⭐⭐⭐ |
| mpn | String | 制造商编号 | ⭐⭐⭐⭐ |
| product_type | String | 商品类型层级 | ⭐⭐⭐⭐⭐ |
| custom_label_0-4 | String | 自定义标签 | ⭐⭐⭐⭐ |
| sale_price | String | 促销价 | ⭐⭐⭐ |
| sale_price_date | String | 促销时间 | ⭐⭐ |
| color | String | 颜色 | ⭐⭐⭐ |
| size | String | 尺码 | ⭐⭐⭐ |
| gender | Enum | 性别 | ⭐⭐⭐ |
| age_group | Enum | 年龄组 | ⭐⭐ |
| adult | Boolean | 成人商品 | ⭐⭐ |

**product_type 层级示例：**

```
Clothing > Shoes > Athletic > Running
```

**custom_label 用途：**

| 标签 | 用途 | 示例值 |
|------|------|--------|
| custom_label_0 | 利润率 | high/medium/low |
| custom_label_1 | 季节 | spring/summer/fall/winter |
| custom_label_2 | 促销状态 | on_sale/not_on_sale |
| custom_label_3 | 畅销程度 | bestseller/popular/niche |
| custom_label_4 | 供应商 | supplier_a/supplier_b |

### 2.3 Product Set 商品集

**Product Set 是什么：**
商品集是从 Catalog 中筛选商品的方法，用于广告定向。

**创建方式：**

```
1. 手动选择
   └── 从 Catalog 中手动挑选商品

2. 规则筛选
   └── 使用 JSON 规则自动筛选
```

**筛选规则语法：**

```json
// 所有可用商品
{"available": true}

// 促销商品
{"sale_price": {"exists": true}}

// 高利润商品
{"custom_label_0": "high"}

// 特定品牌
{"brand": "Nike"}

// 价格范围
{"price": {"gte": "50", "lte": "100"}}

// 组合条件 (AND)
{"available": true, "sale_price": {"exists": true}}

// 组合条件 (OR)
{"brand": ["Nike", "Adidas", "Puma"]}
```

**Product Set 在广告中的应用：**

```
Ad Set (广告组)
└── dynamic_ad_specs
    └── product_set_id: "{product_set_id}"
```

### 2.4 商品数据源 (Feeds)

**上传方式对比：**

| 方式 | 说明 | 适用场景 | 频率 |
|------|------|----------|------|
| API Upload | 通过 Marketing API 上传 | 实时同步、小批量 | 实时 |
| File Upload | 上传 CSV/TXT 文件 | 大批量、定期更新 | 手动/定时 |
| Scheduled Fetch | 定时从 URL 拉取 | 电商网站、RSS | 每日/每小时 |
| Partner Integration | 合作伙伴集成 | Shopify, WooCommerce | 自动同步 |

**File Upload 格式 (TSV)：**

```
id\ttitle\tdescription\timage_url\tprice\tavailability\tbrand\tproduct_type\tgtin
prod_001\tNike Air Max\tComfortable running shoes\thttps://.../shoe.jpg\t99.99 USD\tin stock\tNike\tShoes > Running\t1234567890123
prod_002\tAdidas Ultraboost\tPremium running shoe\thttps://.../boost.jpg\t180.00 USD\tin stock\tAdidas\tShoes > Running\t9876543210987
```

**Scheduled Fetch 配置：**

```
1. 创建 Catalog
2. 添加数据源
   ├── 选择 "Scheduled Fetch"
   ├── 输入商品 Feed URL
   ├── 设置更新频率 (每小时/每日/每周)
   └── 选择格式 (CSV/TXT/XML)
3. 验证 Feed
   ├── 检查商品数量
   ├── 检查错误商品
   └── 检查警告信息
4. 保存并同步
```

## 三、Catalog API 深度实战

### 3.1 创建与管理 Catalog

**创建 Catalog：**

```
POST /{ad-account-id}/product_catalogs
{
  "name": "My Product Catalog",
  "country": "US",
  "currency": "USD"
}

Response:
{
  "id": "{catalog_id}"
}
```

**获取 Catalog 列表：**

```
GET /{ad-account-id}/product_catalogs
Fields: id, name, country, currency, product_count, feed_count
```

**更新 Catalog：**

```
POST /{catalog-id}
{
  "name": "Updated Catalog Name"
}
```

### 3.2 商品管理 API

**批量上传商品：**

```
POST /{catalog-id}/products
[
  {
    "id": "prod_001",
    "title": "Nike Air Max",
    "description": "Comfortable running shoes",
    "image_url": "https://example.com/shoe.jpg",
    "price": "99.99 USD",
    "availability": "in stock",
    "condition": "new",
    "brand": "Nike",
    "product_type": "Shoes > Running",
    "gtin": "1234567890123",
    "custom_label_0": "high",
    "custom_label_1": "spring"
  }
]
```

**更新商品：**

```
POST /{catalog-id}/products
[
  {
    "id": "prod_001",
    "price": "89.99 USD",
    "availability": "on sale"
  }
]
```

**删除商品：**

```
DELETE /{catalog-id}/products
ids: ["prod_001", "prod_002"]
```

**查询商品：**

```
GET /{catalog-id}/products
Fields: id, title, price, availability, brand
Filtering: availability=in stock, brand=Nike
```

### 3.3 Product Set API

**创建 Product Set：**

```
POST /{catalog-id}/product_sets
{
  "name": "Sale Items",
  "filter": "{\"sale_price\": {\"exists\": true}}"
}
```

**更新 Product Set：**

```
POST /{product-set-id}
{
  "filter": "{\"sale_price\": {\"exists\": true}, \"availability\": \"in stock\"}"
}
```

**删除 Product Set：**

```
DELETE /{product-set-id}
```

### 3.4 数据源管理 API

**创建 Scheduled Fetch 数据源：**

```
POST /{catalog-id}/feeds
{
  "name": "Daily Product Feed",
  "url": "https://example.com/feed.tsv",
  "schedule": "EVERY_DAY",
  "format": "TSV",
  "country": "US",
  "language": "en"
}
```

**获取 Feed 状态：**

```
GET /{feed-id}
Fields: status, product_count, error_count, last_fetch_time
```

**手动触发同步：**

```
POST /{feed-id}/refresh
```

## 四、Catalog 广告投放逻辑

### 4.1 Dynamic Product Ads (DPA) 工作原理

```
用户行为追踪
├── 浏览商品页面 → Pixel: ViewContent + content_ids
├── 加入购物车 → Pixel: AddToCart + content_ids
├── 开始结算 → Pixel: InitiateCheckout + content_ids
└── 完成购买 → Pixel: Purchase + content_ids
    ↓
广告系统匹配
├── 识别用户浏览过的商品
├── 从 Catalog 获取商品信息
├── 匹配 Product Set
└── 生成个性化广告
    ↓
广告展示
├── 展示用户浏览过的商品
├── 展示相关/类似商品
└── 展示促销商品
```

### 4.2 DPA 广告系列结构

```
Campaign (广告系列)
├── 目标: Catalog Sales (商品销售)
├── 预算: $100/天
├── 出价策略: Target ROAS 400%
└── Ad Set (广告组)
    ├── 投放位置: Facebook Feed, Instagram Feed
    ├── 受众:
    │   ├── 自定义受众 (网站访客 30 天)
    │   └── 类似受众 (购买用户 1%)
    ├── Product Set: "Sale Items"
    └── Ad (广告)
        └── 格式: Dynamic Product Ads
            ├── 创意模板: Carousel (轮播)
            ├── 标题模板: {title}
            ├── 描述模板: {description}
            └── CTA: Shop Now
```

### 4.3 DPA 创意模板

**Carousel 模板：**

```
每张卡片:
├── 商品图片 (image_url)
├── 商品标题 (title)
├── 商品价格 (price)
└── 行动号召 (CTA)
```

**Collection 模板：**

```
封面:
├── 品牌图片
├── 品牌标语
└── 主 CTA

商品网格:
├── 商品 1 (image, title, price)
├── 商品 2 (image, title, price)
└── 商品 3 (image, title, price)
```

## 五、高级优化策略

### 5.1 商品 Feed 优化

**标题优化：**

```
好标题: "Nike Air Max 2024 Men's Running Shoes - Black/White"
差标题: "Shoes"

优化要点:
├── 品牌 + 产品名 + 关键属性
├── 包含搜索关键词
└── 长度 50-70 字符
```

**图片优化：**

```
要求:
├── 白底图片 (推荐)
├── 分辨率 ≥ 500x500
├── 格式: JPG, PNG
├── 无文字覆盖
└── 多角度展示 (最多 10 张)
```

**价格优化：**

```
格式: "99.99 USD"
├── 包含货币代码
├── 两位小数
└── 无千位分隔符
```

### 5.2 Product Set 策略

**分层 Product Set：**

```
Product Set 1: "All Products"
└── 所有商品

Product Set 2: "Sale Items"
└── sale_price 存在的商品

Product Set 3: "New Arrivals"
└── custom_label_0 = "new"

Product Set 4: "Best Sellers"
└── custom_label_3 = "bestseller"

Product Set 5: "High Margin"
└── custom_label_0 = "high"
```

### 5.3 受众策略

**再营销受众分层：**

| 受众 | 来源 | 出价调整 |
|------|------|----------|
| 购物车放弃用户 | Pixel: AddToCart (7 天) | +50% |
| 浏览用户 | Pixel: ViewContent (30 天) | +20% |
| 购买用户 | Pixel: Purchase (365 天) | 排除或交叉销售 |
| 高价值用户 | Pixel: Purchase (LTV 高) | +100% |

**类似受众：**

| 种子 | 规模 | 适用场景 |
|------|------|----------|
| 购买用户 | 1% | 高价值产品 |
| 购买用户 | 5% | 大多数场景 |
| 网站访客 | 10% | 品牌曝光 |

## 六、常见问题与排障

### 6.1 Feed 错误类型

| 错误 | 说明 | 解决方法 |
|------|------|----------|
| Missing Required Field | 缺少必需字段 | 添加 id, title, image_url, price |
| Invalid Image URL | 图片 URL 无效 | 检查 URL 可访问性 |
| Price Format Error | 价格格式错误 | 使用 "99.99 USD" 格式 |
| Duplicate ID | 商品 ID 重复 | 确保 ID 唯一 |
| Image Too Small | 图片尺寸太小 | 使用 ≥500x500 图片 |

### 6.2 投放异常处理

| 问题 | 可能原因 | 解决方案 |
|------|----------|----------|
| 无展示 | Product Set 为空 | 检查筛选规则 |
| 低 CTR | 图片/标题不佳 | 优化创意模板 |
| 高 CPA | 出价过低/受众不准 | 提高出价/优化受众 |
| 转化丢失 | Pixel 未正确配置 | 检查 content_ids 传递 |

## 七、自测题

1. Catalog 的核心组件有哪些？
2. Product Set 的筛选规则怎么写？
3. DPA 的工作原理是什么？
4. 如何优化商品 Feed？
5. 常见 Feed 错误有哪些？

## 八、动手验证

```bash
# 1. 创建 Catalog
# - 设置名称、国家、货币
# - 获取 Catalog ID

# 2. 上传商品
# - 准备 TSV 文件
# - 批量上传商品
# - 验证商品数量

# 3. 创建 Product Set
# - 设置筛选规则
# - 验证商品数量

# 4. 创建 DPA 广告系列
# - 选择 Catalog Sales 目标
# - 选择 Product Set
# - 设置受众和出价

# 5. 监控和优化
# - 查看商品同步状态
# - 分析广告表现
# - 优化 Feed 和创意
```
