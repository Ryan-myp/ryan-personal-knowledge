# 广告平台层级结构完整指南 v3.0

> **更新时间**: 2026-08-20  
> **覆盖平台**: Google Ads / Meta Marketing API / TikTok Ads / DV360  
> **版本**: v3.0（按广告类型组织，层级图 + 字段说明）

---

# 📋 目录

1. [Google Ads 层级结构](#1-google-ads-层级结构)
   - 1.1 搜索广告
   - 1.2 性能最大化广告 (PMax)
   - 1.3 购物广告 (Shopping)
   - 1.4 视频广告
   - 1.5 展示广告
   - 1.6 应用安装广告
2. [Meta Marketing API 层级结构](#2-meta-marketing-api-层级结构)
   - 2.1 流量广告
   - 2.2 转化广告
   - 2.3 潜在客户广告
   - 2.4 互动广告
   - 2.5 商品广告 (Catalog)
   - 2.6 消息广告
3. [TikTok Ads 层级结构](#3-tiktok-ads-层级结构)
   - 3.1 产品销售广告
   - 3.2 Spark Ads
   - 3.3 线索收集广告
   - 3.4 应用推广广告
   - 3.5 品牌广告
4. [DV360 层级结构](#4-dv360-层级结构)
5. [平台对比速查表](#5-平台对比速查表)

---

# 1. Google Ads 层级结构

> Google Ads 账号可以视为一个对象层次结构，从 Customer 到 Campaign 到 Ad Group 再到 Ad。

### 广告位（Ad Placements）

| 广告位 | 展示位置 | 适用广告类型 |
|--------|----------|-------------|
| **Google Search** | 搜索引擎结果页（SERP）顶部/底部 | Search Ads, Shopping Ads |
| **Google Search Network** | Partner 网站搜索结果页 | Search Ads, Shopping Ads |
| **YouTube** | 视频前贴片/中插/贴片 | Video Ads |
| **Gmail** | Gmail 顶部推广标签 | Display Ads |
| **Google Display Network** | 数百万合作网站/App | Display Ads, PMax |
| **YouTube Discovery** | YouTube 搜索结果/推荐 | Video Ads, PMax |
| **Google Shopping Tab** | 购物标签页 | Shopping Ads |
| **Google Play** | 应用商店推广位 | App Ads |
| **Maps** | Google Maps 搜索结果 | Local Ads |

---

## 1.1 搜索广告（Search Ads）

### 使用场景

| 场景 | 适用条件 | 预期效果 |
|------|----------|----------|
| **品牌词投放** | 用户搜索品牌名时出现广告 | 抢占品牌流量，防止竞品截流 |
| **品类词投放** | 用户搜索产品/服务类型词 | 精准捕获有明确购买意图的用户 |
| **竞品词投放** | 用户搜索竞争对手品牌词 | 拦截竞品流量，争夺市场份额 |
| **长尾词投放** | 用户搜索具体型号/细分需求词 | 低成本获取精准线索 |
| **地理定向投放** | 本地商家/区域性业务 | 精准触达本地潜在客户 |

### 层级结构图

```
Customer
    │
    └── Campaign (广告系列)
            │
            ├── Budgets (预算)
            ├── Dates (投放时间)
            ├── Campaign criteria (广告系列定向)
            │
            └── Ad Group (广告组)
                    │
                    ├── Campaign criteria (广告组级别定向)
                    │
                    ├── Ad (广告)
                    │       ├── Headlines (标题)
                    │       ├── Descriptions (描述)
                    │       ├── URLs (落地页)
                    │       └── Assets (附加信息)
                    │
                    └── Ad Group Criteria (关键词)
                            └── Keywords (关键词列表)
```

### 各层级字段说明

#### Customer（客户）
| 字段 | 说明 |
|------|------|
| `customer_id` | 客户 ID，如 1234567890 |
| `descriptive_name` | 账户描述名称 |
| `currency_code` | 货币代码 (USD/CNY等) |
| `time_zone` | 时区设置 |
| `auto_tagging_enabled` | 是否开启自动标签 |

#### Campaign（广告系列）
| 字段 | 说明 |
|------|------|
| `resource_name` | 资源名称，格式: customers/{customerId}/campaigns/{campaignId} |
| `name` | 广告系列名称 |
| `status` | ENABLED / PAUSED / REMOVED |
| `advertising_channel_type` | SEARCH |
| `campaign_budget` | 关联的预算资源名称 |
| `bidding_strategy` | 出价策略资源名称 |
| `start_date` | 开始日期 |
| `end_date` | 结束日期 |
| `network_settings.target_google_search` | 是否在 Google 搜索投放 |
| `network_settings.target_search_network` | 是否在搜索网络投放 |
| `settings.hand_raised_status_frequency` | 手举状态频率 |

#### Ad Group（广告组）
| 字段 | 说明 |
|------|------|
| `resource_name` | 格式: customers/{customerId}/adGroups/{adGroupId} |
| `campaign` | 关联的广告系列资源名称 |
| `name` | 广告组名称 |
| `status` | ENABLED / PAUSED / REMOVED |
| `cpc_bid_ceiling_micros` | CPC 出价上限 |
| `cpc_bid_floor_micros` | CPC 出价下限 |
| `target_cpa_bid_micros` | 目标 CPA 出价 |
| `final_urls` | 最终 URL 列表 |
| `ad_group_criterion` | 广告组定向条件 |

#### Ad（广告）
| 字段 | 说明 |
|------|------|
| `resource_name` | 格式: customers/{customerId}/ads/{adId} |
| `ad_group` | 关联的广告组资源名称 |
| `status` | ENABLED / PAUSED / REMOVED |
| `type` | TEXT_AD |
| `text.headlines` | 标题数组，最多 30 个字符 |
| `text.descriptions` | 描述数组，最多 90 个字符 |
| `text.path1` / `text.path2` | 路径增强字段 |
| `final_urls` | 最终落地页 URL |
| `tracking_url_template` | 追踪 URL 模板 |
| `final_url_suffix` | 最终 URL 后缀 |
| `url_expansion_opt_out` | 是否关闭 URL 扩展 |

#### Keywords（关键词）
| 字段 | 说明 |
|------|------|
| `resource_name` | 格式: customers/{customerId}/adGroupCriteria/{id} |
| `ad_group` | 关联的广告组 |
| `criterion.type` | KEYWORD |
| `keyword.text` | 关键词文本 |
| `keyword.match_type` | EXACT / PHRASE / BROAD |
| `negative` | 是否负面关键词 |
| `cpc_bid_micros` | CPC 出价（微单位） |
| `explicit_cpc_bid_micros` | 显式 CPC 出价 |

---

### 广告附加信息（Extensions）

> **重要提示**：广告附加信息可根据上下文（如设备和位置）以及预测的组合动态提供，以提高点击率。**即使设置了，也不一定每次都会显示**，谷歌会根据广告质量、排名、出价等因素动态调用。
>
> 位于第一位置的广告 - 排名靠前的广告 - 将有资格获得展示的更多广告附加信息。
>
> 如果未在广告系列中设置，Google 会动态生成一些附加信息，例如附加链接。

| 附加信息类型 | 英文 | 是否可点击 | 展示数量限制 | 适用场景 |
|-------------|------|-----------|-------------|----------|
| 附加链接 | Sitelink extensions | ✅ 可点击 | 2-6个（移动端最多8个） | 链接到网站其他页面 |
| 卖点 | Callout extensions | ❌ 不可点击 | 2-6个 | 突出优惠和利益点 |
| 结构化代码段 | Structured snippet extension | ❌ 不可点击 | - | 展示产品/服务类别 |
| 致电 | Call extension | ✅ 可点击 | - | 添加电话号码 |
| 发送信息 | Message extension | ✅ 可点击 | - | 短信联系 |
| 位置 | Location extension | ✅ 可点击 | - | 显示实体店地址 |
| 联盟商家 | Affiliate location extension | ✅ 可点击 | - | 零售连锁店产品定位 |
| 价格 | Price extension | ✅ 可点击 | 最多8个 | 展示产品价格 |
| 应用程序 | App extension | ✅ 可点击 | - | 引导下载App |
| 促销 | Promotion extension | ✅ 可点击 | - | 展示促销活动 |

#### 1. 附加链接 Sitelink extensions
- **用途**：链接到网站上的其他网页
- **展示数量**：广告可能显示的附加链接数量在两到六个不等，在移动设备的轮播中最多可以显示八个
- **配置层级**：账户、广告系列或广告组级别

#### 2. 卖点 Callout extensions
- **用途**：不可点击，旨在突出用户的优惠和利益
- **示例**："免费送货"、"免费退货"、"退款保证"等
- **展示数量**：可在移动设备或桌面设备上随机显示两到六个标注
- **配置层级**：账户、广告系列或广告组一级

#### 3. 结构化代码段 Structured snippet extension
- **用途**：不可点击，突出提供的产品或服务的各个方面
- **格式**：使用标题格式，如"课程 Courses"和"样式 Styles"等
- **示例**：服装零售商可设置为：`Styles: Skinny, Straight, Flare, Jeggings`

#### 4. 致电 Call extension
- **用途**：在广告中附加电话号码
- **功能**：在移动设备上，用户可以点按直接从分机拨打电话
- **注意**：如果没有设置附加电话信息，Google 可能会使用网站上的电话号码显示

#### 5. 发送信息 Message extension
- **用途**：仅在能够发送和接收文本消息的移动设备上显示
- **要求**：商家号码必须能够发送和接收短信
- **消息示例**："请用更多信息给我发短信 Please text me with more information"
- **计费方式**：当有人点击广告中的邮件信息图标时收费，而不是等到发送完信息后才收费

#### 6. 位置 Location extension
- **用途**：如果你有真实的位置，需要使用附加地址信息
- **前置条件**：需要将"Google My Business"账户与 Google Ads 账户相关联
- **展示位置**：搜索、Google 地图以及展示广告和视频广告中均可展示

#### 7. 联盟商家 Affiliate location extension
- **用途**：在零售连锁店销售产品的品牌和制造商可以启用联盟附加地址信息
- **功能**：帮助用户在附近的地点找到他们的产品
- **覆盖范围**：在美国，目前有超过 80 个连锁店可用于联盟会员附加地址

#### 8. 价格 Price extension
- **用途**：可点击的扩展程序，突出显示服务或产品的价格
- **展示数量**：最多可以在移动设备上显示八个
- **配置要求**：每个价格扩展包括一个可自定义的标题和描述，每个最多 25 个字符。Google 建议至少设置五个价格扩展项

#### 9. 应用程序 App extension
- **用途**：可点击的链接，让用户通过文字广告访问 Google Play 或 Apple App Store 中的移动应用程序
- **注意**：此附加信息不会替换 App 应用程序广告
- **自动检测**：Google 会自动检测用户的设备类型，并仅在相应的设备上显示应用程序附加信息

#### 10. 促销 Promotion extension
- **用途**：展示促销活动或优惠
- **特点**：可点击的，带有价格标签图标，最多可包含两行文本
- **节日选择**：可以从下拉列表中选择一个特定节日，例如母亲节或黑色星期五
- **日期设置**：可以设置促销日期，如黑色星期五促销活动仅在 11 月 15 日至 12 月 15 日期间展示

---

## 1.2 性能最大化广告（Performance Max）

### 使用场景

| 场景 | 适用条件 | 预期效果 |
|------|----------|----------|
| **电商全渠道销售** | 有 Merchant Center 产品数据 | AI 自动优化搜索+购物+展示+视频+YouTube 转化 |
| **新商品推广** | 新品上市，缺乏历史数据 | 多频道快速冷启动，自动化出价 |
| **线索收集自动化** | 需要多触点收集线索 | 跨渠道自动寻找高意向用户 |
| **预算有限的高效投放** | 希望节省人工优化时间 | 算法自动分配预算至最优渠道 |

### 层级结构图

```
Customer
    │
    └── Campaign (广告系列)
            │
            ├── Budgets (预算)
            ├── Dates (投放时间)
            ├── Campaign goal settings (广告目标设置)
            │       ├── sales_campaign_goal_setting (销售目标)
            │       └── lead_campaign_goal_setting (线索目标)
            │
            ├── Audience signals (受众信号)
            │       ├── custom_segments (自定义细分)
            │       └── customer_match_user_lists (客户匹配列表)
            │
            └── Asset groups (资产组) × N个
                    │
                    ├── Product selection (产品选择 - 电商类型)
                    │       └── Product group (产品分组)
                    │
                    ├── Assets (资产素材)
                    │       ├── Headlines (标题)
                    │       ├── Descriptions (描述)
                    │       ├── Images (图片)
                    │       ├── Logos (Logo)
                    │       ├── Videos (视频)
                    │       └── CTAs (行动号召)
                    │
                    └── Final URL suffix (最终URL后缀)
```

### 各层级字段说明

#### Campaign（广告系列）
| 字段 | 说明 |
|------|------|
| `advertising_channel_type` | MAX (Performance Max) |
| `status` | ENABLED / PAUSED / REMOVED |
| `campaign_budget` | 关联的预算资源名称 |
| `bidding_strategy` | 出价策略资源名称 |
| `settings.campaign_goal_setting.sales_campaign_goal_setting.goal_type` | SALES_GOAL_TYPE_ECOMMERCE / ONLINE_SALES / LEAD_GENERATION |
| `settings.campaign_goal_setting.sales_campaign_goal_setting.ecommerce_checkout_progress` | 结账进度（0-1，用于电商） |
| `settings.campaign_goal_setting.lead_campaign_goal_setting.generate_leads_campaign_goal_setting.lead_form` | 线索表单配置 |
| `settings.location_extension_setting.enabled` | 是否启用位置扩展 |
| `settings.account_budget` | 关联的账户预算 |

#### Audience Signals（受众信号）
| 字段 | 说明 |
|------|------|
| `audience_signals.custom_segments[].name` | 自定义细分名称，如 "In-Market - Apparel" |
| `audience_signals.custom_segments[].membership_reason` | 成员原因：SEO / RECOMMENDATION / MANUAL |
| `audience_signals.customer_match_user_lists[].user_list_id` | 客户匹配用户列表 ID |
| `audience_signals.first_party_contact_info_list.id` | 第一方联系信息列表 ID |

#### Asset Groups（资产组）
| 字段 | 说明 |
|------|------|
| `resource_name` | 格式: customers/{customerId}/assetGroups/{assetGroupId} |
| `campaign` | 关联的广告系列 |
| `name` | 资产组名称 |
| `status` | ENABLED / PAUSED / REMOVED |
| `audience_signal` | 受众信号配置 |
| `product_selection.listing_group_type` | PRODUCT_SELECTION（电商类型） |
| `product_selection.product_group` | 产品分组配置 |
| `product_selection.excluded_product_ids` | 排除的产品 ID |

#### Assets（资产素材）- PMax 9 种 Asset 类型详解

PMax 的 Asset Group 必须包含以下 9 种 Asset 类型中的至少一种（建议全部配置以获得最佳效果）：

| Asset 类型 | 字段名 | 说明 | 建议数量 | 字符/尺寸限制 | 用途示例 |
|-----------|--------|------|----------|---------------|----------|
| **Headline** | `headline` | 主标题，出现在搜索/展示广告中 | 10-15 个 | 30 字符 | "Summer Sale", "Up to 50% Off" |
| **Description** | `description` | 描述文本，补充标题信息 | 5-10 个 | 90 字符 | "Discover our latest collection", "Free shipping on orders over $50" |
| **Image** | `image.media_file.url` | 营销图片，用于展示广告 | 5-10 个 | 1280x800 (1.6:1), 1200x628 (Facebook), 最大 5MB | 产品展示图、生活方式图 |
| **Logo** | `logo.media_file.url` | 品牌 Logo，1:1 方形 | 3-5 个 | 1200x1200 (1:1), 最大 5MB | 品牌 Logo |
| **Video** | `video.media_file.url` | YouTube 视频，用于视频广告 | 1-5 个 | 16:9 或 1:1, 至少 15 秒 | 品牌故事、产品演示 |
| **CTA Text** | `cta_text` | 行动号召文本按钮 | 1-2 个 | 25 字符 | "Shop Now", "Learn More", "Sign Up" |
| **Call Out** | `call_out` | 卖点突出文本，用于展示广告 | 5-10 个 | 25 字符 | "Free Shipping", "Easy Returns", "24/7 Support" |
| **Sitelink** | `sitelink` | 附加链接，带标题和描述 | 4-8 个 | 标题 25 字符 / 描述 25 字符 | "New Arrivals" + "Shop the latest styles" |
| **Product Feed Link** | `product_feed_link` | 直接链接到商品目录，自动展示商品 | 1 个 | - | 连接 Merchant Center 商品数据 |

---

### 各 Asset 类型详细说明

#### 1. Headline（标题）
**用途**: 搜索广告和展示广告的主要文本
**最佳实践**:
- 包含品牌名或核心卖点
- 使用行动导向语言（"Shop", "Buy", "Get"）
- 针对不同受众创建差异化标题
- 建议准备 10-15 个以便算法自动组合

**示例**:
```
- "Summer Collection - Up to 50% Off"
- "Free Shipping on Orders $50+"
- "Shop New Arrivals Today"
```

#### 2. Description（描述）
**用途**: 补充标题，提供更详细信息
**最佳实践**:
- 描述产品特色或优惠
- 包含行动号召
- 突出独特卖点（USP）

**示例**:
```
- "Discover our latest summer styles with up to 50% off"
- "Free returns and easy exchanges"
- "Join millions of satisfied customers"
```

#### 3. Image（图片）
**用途**: 展示广告的视觉吸引
**尺寸要求**:
| 类型 | 尺寸 | 比例 |
|------|------|------|
| 标准图片 | 1200 x 628 px | 1.91:1 |
| 正方形图片 | 1200 x 1200 px | 1:1 |
| 竖版图片 | 1080 x 1920 px | 9:16 |

**最佳实践**:
- 使用高质量、高分辨率图片
- 展示产品使用场景
- 包含品牌元素
- 避免文字覆盖图片主体

#### 4. Logo（Logo）
**用途**: 品牌识别
**尺寸要求**: 1200 x 1200 px (1:1 正方形)
**最佳实践**:
- 使用透明背景的 PNG
- 确保 Logo 清晰可辨
- 保持简洁设计

#### 5. Video（视频）
**用途**: YouTube 和视频展示广告
**尺寸要求**:
- 横版: 1920 x 1080 px (16:9)
- 正方形: 1200 x 1200 px (1:1)
- 竖版: 1080 x 1920 px (9:16)

**最佳实践**:
- 前 5 秒抓住注意力
- 添加字幕（70% 用户静音观看）
- 时长 15-60 秒
- 明确行动号召

#### 6. CTA Text（行动号召）
**用途**: 广告中的按钮文本
**可用选项**:
| CTA 文本 | 适用场景 |
|----------|----------|
| Shop Now | 电商销售 |
| Learn More | 信息获取 |
| Sign Up | 注册转化 |
| Download | 应用下载 |
| Book Now | 预约服务 |
| Contact Us | 客户咨询 |

#### 7. Call Out（卖点突出）
**用途**: 展示广告的额外卖点文本
**常见示例**:
```
- Free Shipping
- Easy Returns
- 24/7 Support
- Secure Checkout
- Money Back Guarantee
- Fast Delivery
- Exclusive Deals
```

#### 8. Sitelink（附加链接）
**用途**: 引导用户到特定落地页
**结构**:
- 链接标题 (25 字符)
- 链接描述 (25 字符)

**常见示例**:
```
【New Arrivals】Shop the latest styles
【Sale Items】Up to 50% off today
【Best Sellers】Most popular products
【Gift Guide】Find the perfect gift
```

#### 9. Product Feed Link（商品目录链接）
**用途**: 连接 Merchant Center 商品数据
**配置**:
- 选择已验证的 Product Feed ID
- 自动从商品数据提取标题、图片、价格
- 用于 Shopping 和 PMax 电商广告

**前置条件**:
- 已设置 Merchant Center 账户
- 商品数据已验证通过
- 关联到 Google Ads 账户
```python
# PMax Asset Group 配置（完整 9 种 Asset）
asset_group = {
    "asset_group.name": "Summer Collection",
    "asset_group.status": "ENABLED",
    "asset_group.headlines": [
        {"text": "Summer Sale"},
        {"text": "Up to 50% Off"},
        {"text": "Shop Now"}
    ],
    "asset_group.descriptions": [
        {"text": "Discover our latest collection"},
        {"text": "Free shipping on orders over $50"}
    ],
    "asset_group.images": [
        {"media_file": {"url": "https://example.com/image1.jpg"}},
        {"media_file": {"url": "https://example.com/image2.jpg"}}
    ],
    "asset_group.logos": [
        {"media_file": {"url": "https://example.com/logo.jpg"}}
    ],
    "asset_group.videos": [
        {"media_file": {"url": "https://youtube.com/watch?v=xxx"}}
    ],
    "asset_group.cta_text": "Shop Now",
    "asset_group.call_outs": [
        {"text": "Free Shipping"},
        {"text": "Easy Returns"},
        {"text": "24/7 Support"}
    ],
    "asset_group.sitelinks": [
        {
            "sitelink_text": {"text": "New Arrivals"},
            "sitelink_description": {"text": "Shop the latest styles"}
        },
        {
            "sitelink_text": {"text": "Sale Items"},
            "sitelink_description": {"text": "Up to 50% off"}
        }
    ],
    "asset_group.product_feed_link": {
        "product_feed_id": "product_feed_123"
    }
}
```

#### Product Group（产品分组）
| 字段 | 说明 |
|------|------|
| `all_products` | 根节点配置 |
| `product_type_1~5.values` | 产品子类（最多 5 层，来自 Merchant Center） |
| `custom_label_0~4.values` | 自定义标签（来自 Merchant Center） |
| `brand.values` | 品牌列表 |
| `category.values` | Google 品类 ID |
| `condition.condition_type` | NEW / USED / REFURBISHED |
| `condition.condition_values` | 条件值列表 |
| `cpc_bid_micros` | CPC 出价（仅叶节点可设置） |

---

## 1.3 购物广告（Shopping Ads）

### 使用场景

| 场景 | 适用条件 | 预期效果 |
|------|----------|----------|
| **电商产品直接展示** | 有完整产品数据Feed | 展示产品图片/价格，直接引导购买 |
| **清仓促销** | 库存清理需求 | 通过 Product Group 细分不同促销力度 |
| **新品首发** | 新品上线推广 | 配合 PMax 或独立 Shopping Campaign |
| **价格竞争激烈的品类** | 电商品类标准化程度高 | 价格透明对比，需精细化出价策略 |

### 层级结构图

```
Customer
    │
    └── Campaign (广告系列)
            │
            ├── Budgets (预算)
            ├── Dates (投放时间)
            │
            └── Shopping Setting (购物设置)
                    ├── merchant_id (商家 ID)
                    ├── sales_country (销售国家)
                    ├── priority (优先级 0-100)
                    └── exclude_offline_store_locations (排除门店)
            │
            └── Ad Group (广告组)
                    │
                    └── Product Group / Listing Group (产品分组) × N个
                            ├── all_products (根节点)
                            ├── product_type_1~5 (产品子类细分)
                            ├── custom_label_0~4 (自定义标签细分)
                            ├── brand / category / condition (其他细分)
                            └── cpc_bid_micros (叶节点出价)
```

### 各层级字段说明

#### Campaign（广告系列）
| 字段 | 说明 |
|------|------|
| `advertising_channel_type` | SHOPPING |
| `status` | ENABLED / PAUSED / REMOVED |
| `campaign_budget` | 关联的预算资源名称 |
| `bidding_strategy` | 出价策略资源名称 |
| `settings.shopping_setting.merchant_id` | Merchant Center 商家 ID |
| `settings.shopping_setting.sales_country` | 销售国家 (ISO 代码，如 US) |
| `settings.shopping_setting.priority` | 优先级 (0-100，多 Campaign 时使用) |
| `settings.shopping_setting.exclude_offline_store_locations` | 是否排除线下门店 |
| `settings.shopping_setting.store_sales_mode` | 本地库存广告模式 |

#### Product Group（产品分组）
| 字段 | 说明 |
|------|------|
| `resource_name` | 格式: customers/{customerId}/adGroupCriteria/{id} |
| `ad_group` | 关联的广告组 |
| `criterion.type` | PRODUCT_GROUP |
| `product_group.all_products` | 根节点（所有商品） |
| `product_group.product_type_1.values` | 产品子类第 1 层 |
| `product_group.product_type_2.values` | 产品子类第 2 层 |
| `product_group.product_type_3~5.values` | 产品子类第 3-5 层 |
| `product_group.custom_label_0~4.values` | 自定义标签 0-4 |
| `product_group.brand.values` | 品牌列表 |
| `product_group.category.values` | Google 品类 ID |
| `product_group.condition.condition_type` | NEW / USED / REFURBISHED |
| `product_group.condition.condition_values` | 条件值列表 |
| `cpc_bid_micros` | CPC 出价（仅叶节点可设置） |

---

## 1.4 视频广告（Video Ads）

### 使用场景

| 场景 | 适用条件 | 预期效果 |
|------|----------|----------|
| **品牌故事讲述** | 有高质量品牌视频素材 | 建立品牌认知和情感连接 |
| **产品功能演示** | 视频展示产品使用方式 | 直观展示，提升转化率 |
| **YouTube 前贴片** | 目标用户在 YouTube 观看视频 | 利用 Google 视频生态触达海量用户 |
| ** ремаркетинг** | 已访问网站但未转化的用户 | 通过视频再次触达，唤醒转化意愿 |

### 层级结构图

```
Customer
    │
    └── Campaign (广告系列)
            │
            ├── Budgets (预算)
            ├── Dates (投放时间)
            │
            └── Ad Group (广告组)
                    │
                    ├── Targeting (定向)
                    │       ├── placement_ids (网站/APP 投放位)
                    │       └── audience_signals (受众信号)
                    │
                    └── Ad (广告)
                            ├── Video (视频)
                            │       ├── video_id (YouTube 视频 ID)
                            │       └── tracking_urls (追踪链接)
                            ├── Final URL (落地页)
                            └── Assets (附加信息)
                                    ├── Headlines
                                    ├── Descriptions
                                    └── Call To Action
```

### 各层级字段说明

#### Campaign（广告系列）
| 字段 | 说明 |
|------|------|
| `advertising_channel_type` | VIDEO |
| `status` | ENABLED / PAUSED / REMOVED |
| `campaign_budget` | 关联的预算资源名称 |
| `bidding_strategy` | 出价策略资源名称 |

#### Ad Group（广告组）
| 字段 | 说明 |
|------|------|
| `campaign` | 关联的广告系列 |
| `name` | 广告组名称 |
| `status` | ENABLED / PAUSED / REMOVED |
| `targeting` | 投放定位配置 |
| `targeting.placement_ids[]` | 网站/APP 投放位 ID 列表 |
| `targeting.audience_signals[]` | 受众信号配置 |

#### Ad（广告）
| 字段 | 说明 |
|------|------|
| `ad_group` | 关联的广告组 |
| `status` | ENABLED / PAUSED / REMOVED |
| `type` | VIDEO |
| `video.video_id` | YouTube 视频 ID |
| `video.tracking_urls[]` | 追踪 URL 列表 |
| `final_urls[]` | 最终落地页 URL |
| `tracking_url_template` | 追踪 URL 模板 |
| `text.headlines[]` | 标题 |
| `text.descriptions[]` | 描述 |
| `call_to_action.text` | 行动号召文本 |

---

## 1.5 展示广告（Display Ads）

### 使用场景

| 场景 | 适用条件 | 预期效果 |
|------|----------|----------|
| **品牌曝光** | 需要大范围品牌认知 | 大规模展示，提升品牌知名度 |
| ** ремаркетинг** | 已访问但未转化的用户 | 跟随用户在不同网站展示，唤醒记忆 |
| **受众定向** | 特定兴趣/行为人群 | 精准触达目标受众群体 |
| **移动端 App 内广告** | 目标用户在 App 中活跃 | 展示横幅/原生广告，成本较低 |

### 层级结构图

```
Customer
    │
    └── Campaign (广告系列)
            │
            ├── Budgets (预算)
            ├── Dates (投放时间)
            │
            └── Ad Group (广告组)
                    │
                    ├── Targeting (定向)
                    │       ├── placements (投放位)
                    │       ├── topics (主题)
                    │       ├── keywords (关键词)
                    │       └── audience_signals (受众信号)
                    │
                    └── Ad (广告)
                            ├── Responsive Display Ad (响应式展示广告)
                            │       ├── headlines (标题)
                            │       ├── descriptions (描述)
                            │       ├── images (图片)
                            │       ├── logos (Logo)
                            │       └── business_name (商家名称)
                            │
                            └── Standard Display Ad (标准展示广告)
                                    ├── final_url (落地页)
                                    ├── advertisement_images (广告图片)
                                    └── path1 / path2 (路径增强)
```

### 各层级字段说明

#### Ad Group（广告组）
| 字段 | 说明 |
|------|------|
| `targeting.placements[]` | 投放位配置，如网站/APP URL |
| `targeting.topics[]` | 主题定向 |
| `targeting.keywords[]` | 关键词定向 |
| `targeting.audience_signals[]` | 受众信号 |

#### Responsive Display Ad（响应式展示广告）
| 字段 | 说明 |
|------|------|
| `type` | RESPONSIVE_DISPLAY_AD |
| `headline` | 主标题 |
| `long_headline` | 长标题 |
| `description` | 描述 |
| `call_to_action.text` | 行动号召 |
| `marketing_image.media_file.url` | 营销图片 |
| `logo_image.media_file.url` | Logo 图片 |
| `square_marketing_image.media_file.url` | 方形营销图片 |
| `business_name` | 商家名称 |
| `ultimate_url` | 最终 URL |

---

## 1.6 应用安装广告（App Ads）

### 使用场景

| 场景 | 适用条件 | 预期效果 |
|------|----------|----------|
| **新 App 推广** | 应用上线初期需要安装量 | 快速获得大量用户安装 |
| **应用激活/留存** | 已有安装但需要激活用户 | 引导用户完成核心功能使用 |
| **再营销** | 已安装但未活跃的用户 | 重新唤醒，提升留存率 |
| **跨渠道整合** | 需要在搜索+展示+视频多频道投放 | 统一预算，智能分配至最优渠道 |

### 层级结构图

```
Customer
    │
    └── Campaign (广告系列)
            │
            ├── Budgets (预算)
            ├── Dates (投放时间)
            │
            └── Ad Group (广告组)
                    │
                    ├── Targeting (定向)
                    │       └── audience_signals (受众信号)
                    │
                    └── Ad (广告)
                            ├── App Campaign Assets (应用广告素材)
                            │       ├── headlines (标题)
                            │       ├── descriptions (描述)
                            │       ├── images (图片)
                            │       ├── videos (视频)
                            │       └── logos (Logo)
                            │
                            └── App Settings (应用设置)
                                    ├── app_id (应用 ID)
                                    ├── app_store (应用商店)
                                    └── deep_link (深度链接)
```

### 各层级字段说明

#### Campaign（广告系列）
| 字段 | 说明 |
|------|------|
| `advertising_channel_type` | APP |
| `status` | ENABLED / PAUSED / REMOVED |
| `bidding_strategy` | 出价策略（需为 APP 类型） |

#### Ad（广告）
| 字段 | 说明 |
|------|------|
| `type` | APP_AD |
| `app_campaign_assets.headlines[]` | 标题列表 |
| `app_campaign_assets.descriptions[]` | 描述列表 |
| `app_campaign_assets.images[]` | 图片列表 |
| `app_campaign_assets.videos[]` | 视频列表 |
| `app_campaign_assets.logos[]` | Logo 列表 |
| `app_settings.app_id` | 应用 ID，如 com.example.app |
| `app_settings.app_store` | GOOGLE_PLAY / APP_STORE |
| `app_settings.deep_link` | 深度链接 URL |

---

# 2. Meta Marketing API 层级结构

> Meta 广告架构：Business Manager → Ad Account → Campaign → Ad Set → Ad

### 广告位（Ad Placements）

| 广告位 | 展示位置 | 适用广告类型 |
|--------|----------|-------------|
| **Facebook Feed** | 用户动态信息流 | 所有类型 |
| **Facebook Right Column** | 桌面端右侧栏 | 展示广告 |
| **Facebook Stories** | Facebook 故事 | 视频/图片广告 |
| **Facebook In-Stream** | 视频流中插广告 | 视频广告 |
| **Facebook Search** | Facebook 搜索结果 | 搜索广告 |
| **Instagram Feed** | Instagram 信息流 | 所有类型 |
| **Instagram Stories** | Instagram 故事 | 视频/图片广告 |
| **Instagram Reels** | Instagram 短视频 | 视频广告 |
| **Instagram Explore** | Instagram 探索页 | 图片/视频广告 |
| **Messenger Story** | Messenger 故事 | 视频/图片广告 |
| **Audience Network** | 第三方 App/网站 | 展示/视频广告 |
| **WhatsApp Status** | WhatsApp 状态（部分地区） | 视频/图片广告 |

---

## 2.1 流量广告（Traffic Ads）

### 使用场景

| 场景 | 适用条件 | 预期效果 |
|------|----------|----------|
| **网站引流** | 需要将用户引导至落地页 | 低成本获取点击，提升网站流量 |
| **内容推广** | 博客/文章/白皮书推广 | 增加内容曝光和阅读数量 |
| **活动预热** | 新品发布/活动前的流量蓄水 | 提前积累潜在客户池 |
| **A/B 测试引流** | 测试不同创意/定向的点击率 | 快速筛选最优组合 |

### 层级结构图

```
Business Manager
    │
    └── Ad Account (广告账户)
            │
            └── Campaign (广告系列)
                    │
                    ├── objective (目标: TRAFFIC)
                    ├── special_ad_categories (特殊广告类别)
                    ├── daily_budget / lifetime_budget (预算)
                    │
                    └── Ad Set (广告组)
                            │
                            ├── optimization_guide (优化指南)
                            ├── billing_event (计费事件)
                            ├── target_cost (目标成本)
                            │
                            ├── targeting (受众定向)
                            │       ├── geo_locations (地理位置)
                            │       ├── age (年龄)
                            │       ├── genders (性别)
                            │       ├── interests (兴趣)
                            │       └── behaviors (行为)
                            │
                            └── Ad (广告)
                                    │
                                    ├── creative (创意)
                                    │       ├── image_url (图片)
                                    │       ├── video_url (视频)
                                    │       └── link_data (链接数据)
                                    │
                                    └── tracking_urls (追踪链接)
```

### 各层级字段说明

#### Campaign（广告系列）
| 字段 | 说明 |
|------|------|
| `id` | 广告系列 ID |
| `name` | 名称 |
| `status` | ACTIVE / PAUSED / DELETED |
| `objective` | TRAFFIC / CONVERSIONS / BRAND_AWARENESS / LEAD_GENERATION / MESSAGES / SALES |
| `special_ad_categories` | ['NONE'] / ['HOUSING', 'EMPLOYMENT', 'CREDIT'] |
| `daily_budget` | 日预算（分，如 1000 = $10） |
| `lifetime_budget` | 总预算 |
| `start_time` / `end_time` | 投放时间 |

#### Ad Set（广告组）
| 字段 | 说明 |
|------|------|
| `id` | 广告组 ID |
| `campaign_id` | 关联广告系列 ID |
| `name` | 名称 |
| `status` | ACTIVE / PAUSED / DELETED |
| `optimization_guide` | LINK_CLICKS / CONVERSIONS / THRUPLAY / QUALITY_RANKING 等 |
| `billing_event` | IMPRESSION / CLICK / THRUPLAY |
| `target_cost` | 目标成本（分） |
| `daily_budget` | 日预算（可选，覆盖 Campaign 级别） |
| `start_time` / `end_time` | 投放时间 |

#### Targeting（定向）
| 字段 | 说明 |
|------|------|
| `geo_locations.countries` | 国家代码数组，如 ["US", "CA"] |
| `geo_locations.key` | 位置类型: country / city / dma_radius |
| `age_min` / `age_max` | 年龄范围 |
| `genders` | 1 = MALE, 2 = FEMALE, 3 = ALL |
| `interests.name` | 兴趣名称数组 |
| `behaviors` | 行为标签数组 |
| `custom_audiences` | 自定义受众 ID 数组 |

#### Ad（广告）
| 字段 | 说明 |
|------|------|
| `id` | 广告 ID |
| `adset_id` | 关联广告组 ID |
| `name` | 名称 |
| `status` | ACTIVE / PAUSED / DELETED |
| `creative.image_url` | 图片 URL |
| `creative.video_url` | 视频 URL |
| `creative.link_data.message` | 消息内容 |
| `creative.link_data.call_to_action.type` | CTA 类型: LEARN_MORE / SHOP_NOW 等 |
| `tracking_urls` | 追踪 URL 数组 |
| `preview_url` | 预览 URL |

---

## 2.2 转化广告（Conversion Ads）

### 使用场景

| 场景 | 适用条件 | 预期效果 |
|------|----------|----------|
| **电商购买转化** | 有 Pixel/CAPI 追踪配置 | 直接驱动销售，最大化 ROAS |
| **表单提交** | 落地页有转化表单 | 获取用户线索，跟进销售 |
| **电话拨打** | 客服电话/预约咨询 | 直接获取销售线索 |
| **App 下载+激活** | 有 App 追踪配置 | 从安装到激活的全链路优化 |

### 层级结构图

```
Business Manager
    │
    └── Ad Account (广告账户)
            │
            └── Campaign (广告系列)
                    │
                    ├── objective (目标: CONVERSIONS / SALES)
                    ├── pixel_id / capi_config (转化追踪配置)
                    │
                    └── Ad Set (广告组)
                            │
                            ├── optimization_guide (优化: CONVERSIONS)
                            ├── conversion_spec_id (转化事件 ID)
                            ├── daily_budget (预算)
                            │
                            ├── targeting (受众定向)
                            │
                            └── Ad (广告)
                                    │
                                    ├── creative (创意)
                                    │       ├── primary_image / primary_video
                                    │       └── call_to_action (CTA)
                                    │
                                    └── tracking_url (转化追踪)
```

### 关键配置差异（vs Traffic Ads）

| 配置项 | Traffic Ads | Conversion Ads |
|--------|-------------|----------------|
| `objective` | TRAFFIC | CONVERSIONS / SALES |
| `optimization_guide` | LINK_CLICKS | CONVERSIONS |
| `conversion_spec_id` | 不需要 | 需要指定 |
| `pixel_id` | 可选 | 必需 |
| `cta_type` | LEARN_MORE | SHOP_NOW / CONVERT |

---

## 2.3 潜在客户广告（Lead Ads）

### 使用场景

| 场景 | 适用条件 | 预期效果 |
|------|----------|----------|
| **B2B 线索收集** | 需要获取企业决策人信息 | Instant Form 降低填写门槛，提高线索量 |
| **课程/服务咨询** | 教育/培训/服务机构 | 快速获取潜在客户联系方式 |
| **会员注册** | 需要沉淀私域用户 | 一键表单，提升注册转化率 |
| **问卷调查** | 需要用户反馈/调研 | 轻量级互动，获取用户洞察 |

### 层级结构图

```
Business Manager
    │
    └── Ad Account
            │
            └── Campaign
                    │
                    └── Ad Set
                            │
                            ├── objective: LEAD_GENERATION
                            │
                            └── Instant Form (即时表单)
                                    ├── title (表单标题)
                                    ├── description (表单描述)
                                    ├── privacy_policy_url (隐私政策)
                                    │
                                    └── Fields (表单字段)
                                            ├── full_name (全名)
                                            ├── email_address (邮箱)
                                            ├── phone_number (电话)
                                            └── custom_question (自定义问题)
```

### 各层级字段说明

#### Campaign（广告系列）
| 字段 | 说明 |
|------|------|
| `objective` | LEAD_GENERATION |
| `special_ad_categories` | 必须为 ['NONE']（除特定行业） |

#### Instant Form（即时表单）
| 字段 | 说明 |
|------|------|
| `title` | 表单标题，最多 80 字符 |
| `description` | 表单描述，最多 240 字符 |
| `privacy_policy_url` | 隐私政策 URL |
| `thank_you_screen.title` | 感谢页标题 |
| `thank_you_screen.description` | 感谢页描述 |

#### Form Fields（表单字段）
| 字段 | 说明 |
|------|------|
| `field_type` | full_name / email_address / phone_number / custom |
| `title` | 字段标题 |
| `description` | 字段描述 |
| `required` | 是否必填 |
| `options` | 单选/多选选项数组 |

---

## 2.4 互动广告（Engagement Ads）

### 使用场景

| 场景 | 适用条件 | 预期效果 |
|------|----------|----------|
| **页面点赞增长** | 新 Page 冷启动 | 快速积累粉丝基数，建立社交证明 |
| **帖子互动提升** | 重要内容推广 | 增加点赞/评论/分享，提升自然触达 |
| **活动报名** | 线上/线下活动推广 | 通过互动收集参与意愿 |
| **Messenger 对话** | 客户服务/咨询引导 | 直接引导用户发起对话 |

### 层级结构图

```
Business Manager
    │
    └── Ad Account
            │
            └── Campaign
                    │
                    └── Ad Set
                            │
                            ├── objective: ENGAGEMENT
                            ├── engagement_type: POST_ENGAGEMENT / PAGE_LIKES 等
                            │
                            └── Ad
                                    │
                                    └── Creative
                                            ├── media_url (媒体 URL)
                                            └── call_to_action (CTA)
```

### 常用 Engagement Type

| 类型 | 说明 |
|------|------|
| `POST_ENGAGEMENT` | 帖子互动（点赞、评论、分享） |
| `PAGE_LIKES` | 页面赞 |
| `EVENT_RESPONSES` | 活动响应 |
| `MESSAGES` | Messenger 消息 |
| `OFFER_CLAIMS` | 优惠领取 |
| `LEAD_GENERATION` | 线索收集 |
| `BRAND_AWARENESS` | 品牌认知 |

---

## 2.5 商品广告（Catalog/Sales Ads）

### 使用场景

| 场景 | 适用条件 | 预期效果 |
|------|----------|----------|
| **动态商品广告 (DPA)** | 有商品目录Feed | 根据用户浏览行为自动推荐相关商品 |
| **Collection 广告** | 移动端体验优先 | 沉浸式商品展示，一键进入商店 |
| ** ремаркетинг 商品** | 浏览未购买的用户 | 精准展示用户感兴趣的商品 |
| **季节性促销** | 大促/节日促销 | 批量展示促销活动商品 |

### 层级结构图

```
Business Manager
    │
    └── Ad Account
            │
            └── Campaign
                    │
                    ├── objective: SALES / CONVERSIONS
                    ├── catalog_id (商品目录 ID)
                    │
                    └── Ad Set
                            │
                            ├── optimization_guide: CONVERSIONS
                            ├── catalog_ad_type: DYNAMIC_PRODUCT_ADS / COLLECTION 等
                            │
                            ├── Product Set (商品集)
                            │       ├── filter.conditions (过滤条件)
                            │       └── default_filter (默认过滤)
                            │
                            └── Ad
                                    │
                                    └── Dynamic Creative (动态创意)
                                            ├── carousel_ad_type (轮播类型)
                                            ├── card_style (卡片样式)
                                            └── product_ids (产品 ID 列表)
```

### 各层级字段说明

#### Campaign（广告系列）
| 字段 | 说明 |
|------|------|
| `objective` | SALES / CONVERSIONS |
| `catalog_id` | 商品目录 ID |

#### Product Set（商品集）
| 字段 | 说明 |
|------|------|
| `id` | 商品集 ID |
| `name` | 名称 |
| `filter.conditions[]` | 过滤条件数组 |
| `filter.conditions[].field` | 字段名: product_type / category / availability 等 |
| `filter.conditions[].operator` | EQUAL / NOT_EQUAL / CONTAINS |
| `filter.conditions[].value` | 值 |
| `default_filter.all_products` | 是否包含所有商品 |

#### Ad（广告）
| 字段 | 说明 |
|------|------|
| `carousel_ad_type` | CAROUSEL / SINGLE_PRODUCT |
| `carousel_format_style` | PRODUCT_CARD / COLLECTION |
| `product_ids[]` | 展示的产品 ID 列表 |

---

## 2.6 消息广告（Messaging Ads）

### 使用场景

| 场景 | 适用条件 | 预期效果 |
|------|----------|----------|
| **WhatsApp 客服** | 拉美/东南亚等 WhatsApp 普及地区 | 直接对话，提升客户满意度和转化率 |
| **Messenger 咨询** | 欧美市场，年轻用户群体 | 即时响应，缩短购买决策路径 |
| **IG DM 互动** | 品牌与年轻用户建立关系 | 私密对话，增强品牌亲和力 |
| **订单状态通知** | 电商售后沟通 | 自动化推送，提升服务效率 |

### 层级结构图

```
Business Manager
    │
    └── Ad Account
            │
            └── Campaign
                    │
                    └── Ad Set
                            │
                            ├── messaging_app_setting (消息应用设置)
                            │       ├── whatsapp_number (WhatsApp 号码)
                            │       ├── instagram_direct_message_setting (IG DM 设置)
                            │       └── messenger_setting (Messenger 设置)
                            │
                            └── Ad
                                    └── Welcome Message (欢迎消息)
```

### 各层级字段说明

#### messaging_app_setting
| 字段 | 说明 |
|------|------|
| `whatsapp_number` | WhatsApp 商业号码 |
| `instagram_business_id` | Instagram 商业账号 ID |
| `welcome_message` | 欢迎消息文本 |

---

# 3. TikTok Ads 层级结构

> TikTok Ads 架构：Business Center → Advertiser → Campaign → Ad Group → Ad

### 广告位（Ad Placements）

| 广告位 | 展示位置 | 适用广告类型 |
|--------|----------|-------------|
| **In-Feed Ads** | For You 页面信息流 | 产品销售/Spark Ads |
| **TopView** | App 开屏独占展示 | 品牌广告 |
| **Brand Takeover** | App 开屏/首页横幅 | 品牌广告 |
| **Hashtag Challenge** | 话题挑战赛入口 | 品牌/互动广告 |
| **Spark Ads** | 达人原生内容流 | Spark Ads |
| **Pinned Comment** | 视频评论区置顶 | 互动广告 |
| **Collection Ads** | 沉浸式商品展示页 | 商品广告 |
| **Instant Experience** | 全屏落地页体验 | 所有类型 |

---

## 3.1 产品销售广告（Product Sales）

### 使用场景

| 场景 | 适用条件 | 预期效果 |
|------|----------|----------|
| **TikTok Shop 带货** | 有 TikTok Shop 店铺或商品 | 直接引导购买，缩短转化路径 |
| **站外电商引流** | 独立站/电商平台推广 | 将 TikTok 用户引导至外部购买页面 |
| **新品/爆款推广** | 需要快速起量的产品 | 视频原生展示，激发冲动消费 |
| **价格敏感人群** | 折扣/促销商品推广 | 年轻用户对价格敏感，转化效率高 |

### 层级结构图

```
Business Center
    │
    └── Advertiser (广告主)
            │
            └── Campaign (广告系列)
                    │
                    ├── objective_type (广告目标: PRODUCT_SALES)
                    ├── daily_budget / campaign_budget (预算)
                    ├── budget_mode (预算模式: DAY / LIFETIME)
                    ├── promotion_type (推广类型: STANDARD / SPARK)
                    │
                    └── Ad Group (广告组)
                            │
                            ├── bid_type (出价类型: AUTO / MANUAL)
                            ├── bid_amount (出价金额)
                            │
                            ├── promoted_object (推广对象配置)
                            │       ├── objective_type: PRODUCT_SALES
                            │       ├── website_url: "https://example.com"
                            │       ├── catalog_id: "catalog_123"  # 商品目录 ID
                            │       └── product_set_id: "product_set_123"  # 商品集 ID
                            │
                            ├── targeting (定向)
                            │       ├── age_min / age_max (年龄)
                            │       ├── genders (性别: 1=MALE, 2=FEMALE)
                            │       ├── geo_locations.country_codes (国家)
                            │       ├── interest_ids (兴趣)
                            │       └── language_ids (语言)
                            │
                            └── Ad (广告)
                                    │
                                    ├── promoted_type (类型: VIDEO / IMAGE)
                                    ├── video_id / image_url (素材)
                                    ├── tracking_url (追踪链接)
                                    └── title / description (文案)
```

### 各层级字段说明

#### Campaign（广告系列）
| 字段 | 说明 |
|------|------|
| `campaign_id` | 广告系列 ID |
| `campaign_name` | 名称 |
| `status` | ENABLED / PAUSED / DISABLED / ARCHIVED |
| `objective_type` | PRODUCT_SALES / BRAND_AWARENESS / VIDEO_VIEWS / LEAD_GENERATION / APP_PROMOTION / CONVERSIONS |
| `daily_budget` | 日预算（分，如 5000 = $50） |
| `budget_mode` | BUDGET_MODE_DAY / BUDGET_MODE_LIFETIME |
| `promotion_type` | PROMOTION_TYPE_STANDARD / PROMOTION_TYPE_SPARK |
| `start_time` / `end_time` | 投放时间 |

#### Ad Group（广告组）
| 字段 | 说明 |
|------|------|
| `adgroup_id` | 广告组 ID |
| `adgroup_name` | 名称 |
| `status` | ENABLED / PAUSED / DISABLED |
| `bid_type` | AUTO_BID / MANUAL_BID |
| `bid_amount` | 出价金额（分） |
| `promoted_object` | 推广对象配置 |
| `promoted_object.catalog_id` | 商品目录 ID（关联到 TikTok Shop 商品目录） |
| `promoted_object.product_set_id` | 商品集 ID（定义展示哪些商品） |
| `promoted_object.website_url` | 落地页 URL |
| `daily_budget` | 日预算（可选） |

#### Catalog（商品目录）
| 字段 | 说明 |
|------|------|
| `catalog_id` | 商品目录 ID |
| `name` | 目录名称 |
| `country` | 销售国家 |
| `language` | 语言设置 |
| `currency` | 货币代码 |
| `products_count` | 商品数量 |

#### Product Set（商品集）
| 字段 | 说明 |
|------|------|
| `product_set_id` | 商品集 ID |
| `name` | 商品集名称 |
| `filter.conditions[]` | 过滤条件数组 |
| `filter.conditions[].field` | 过滤字段: product_type / category / availability 等 |
| `filter.conditions[].operator` | 操作符: EQUAL / NOT_EQUAL / CONTAINS |
| `filter.conditions[].value` | 过滤值 |
| `default_filter.all_products` | 是否包含所有商品 |

#### targeting（定向）
| 字段 | 说明 |
|------|------|
| `age_min` / `age_max` | 年龄范围 |
| `genders` | 1 = MALE, 2 = FEMALE |
| `geo_locations.country_codes` | 国家代码数组 |
| `interest_ids` | 兴趣 ID 数组 |
| `language_ids` | 语言 ID，如 "1001" = 英语 |

#### Ad（广告）
| 字段 | 说明 |
|------|------|
| `ad_id` | 广告 ID |
| `name` | 名称 |
| `status` | ENABLED / PAUSED / DISABLED |
| `promoted_type` | PROMOTED_TYPE_VIDEO / PROMOTED_TYPE_IMAGE |
| `video_id` | 视频 ID（视频广告） |
| `image_url` | 图片 URL（图片广告） |
| `tracking_url` | 追踪链接 |
| `title` | 标题 |
| `description` | 描述 |
| `cta_type` | "SHOP_NOW" / "LEARN_MORE" / "SIGN_UP" |

---

## 3.2 Spark Ads（达人原生广告）

### 使用场景

| 场景 | 适用条件 | 预期效果 |
|------|----------|----------|
| **达人内容投放** | 已与达人达成合作授权 | 使用达人真实内容，信任度高，CTR 优于普通广告 |
| **UGC 风格广告** | 需要原生感强的广告素材 | 避免"广告感"，降低用户抵触心理 |
| **社交证明强化** | 已有达人测评/推荐内容 | 放大达人影响力，提升品牌背书 |
| **低成本素材获取** | 预算有限，缺乏专业拍摄 | 复用达人原创内容，降低成本 |

### 层级结构图

```
Business Center
    │
    └── Advertiser
            │
            └── Campaign
                    │
                    └── Ad Group
                            │
                            └── Spark Ad (Spark 广告)
                                    │
                                    └── spark_info (Spark 配置)
                                            ├── video_id (视频 ID)
                                            ├── creator_id (达人 ID)
                                            ├── authorization_id (授权 ID)
                                            └── authorization_status (授权状态)
```

### 特殊要求

| 配置项 | 说明 |
|--------|------|
| `promotion_type` | 必须设置为 `PROMOTION_TYPE_SPARK` |
| `spark_info.video_id` | 达人原创视频的 TikTok 视频 ID |
| `spark_info.authorization_id` | 视频授权 ID（需达人授权） |
| `spark_info.authorization_status` | 授权状态: AUTHORIZED / PENDING |

---

## 3.3 线索收集广告（Lead Generation）

### 使用场景

| 场景 | 适用条件 | 预期效果 |
|------|----------|----------|
| **B2B 线索获取** | 企业级产品/服务推广 | 通过表单收集潜在客户信息 |
| **免费试用注册** | SaaS/工具类产品 | 引导用户注册免费试用，培育商机 |
| **活动报名** | 线上/线下活动推广 | 快速获取参与者信息 |
| **问卷调查** | 市场调研/用户反馈收集 | 轻量级互动，获取用户洞察 |

### 层级结构图

```
Business Center
    │
    └── Advertiser
            │
            └── Campaign
                    │
                    └── Ad Group
                            │
                            └── Lead Form (线索表单)
                                    ├── title (表单标题)
                                    ├── description (表单描述)
                                    └── questions (问题列表)
                                            └── name / type / required (字段配置)
```

### 表单字段类型

| type | 说明 |
|------|------|
| `TEXT` | 文本输入 |
| `EMAIL` | 邮箱 |
| `PHONE_NUMBER` | 电话号码 |
| `DROPDOWN` | 下拉选择 |
| `CHECKBOX` | 多选 |

---

## 3.4 应用推广广告（App Promotion）

### 使用场景

| 场景 | 适用条件 | 预期效果 |
|------|----------|----------|
| **App 安装推广** | 新 App 上线或推广期 | 快速获取大量安装用户 |
| **App 激活优化** | 已有安装但激活率低 | 引导用户完成核心功能使用 |
| **再营销唤醒** | 已安装但未活跃的用户 | 重新激活，提升留存率 |
| **竞品用户转化** | 目标用户在竞品 App 中活跃 | 通过兴趣定向触达竞品用户 |

### 层级结构图

```
Business Center
    │
    └── Advertiser
            │
            └── Campaign
                    │
                    └── Ad Group
                            │
                            └── App Settings (应用设置)
                                    ├── app_id (应用 ID)
                                    ├── app_store (应用商店: TIKTOK / APP_STORE / GOOGLE_PLAY)
                                    └── deep_link (深度链接)
```

---

## 3.5 品牌广告（Brand Ads）

### 使用场景

| 场景 | 适用条件 | 预期效果 |
|------|----------|----------|
| **品牌曝光** | 品牌知名度建设 | 大规模视频曝光，建立品牌认知 |
| **TopView 开屏** | 品牌大事件/新品发布 | 独占性高曝光，强品牌冲击 |
| **品牌挑战赛** | 品牌营销活动 | 用户参与创作，病毒式传播 |
| **品牌故事讲述** | 有高质量品牌视频素材 | 情感连接，提升品牌好感度 |

### 层级结构图

```
Business Center
    │
    └── Advertiser
            │
            └── Campaign
                    │
                    └── Ad Group
                            │
                            └── Brand Video Ad (品牌视频广告)
                                    ├── duration (视频时长: 秒)
                                    └── title (标题)
```

---

# 4. DV360 层级结构

> DV360 (Display & Video 360) 是 Google 的程序化广告平台，支持跨媒体、跨 DSP 的实时竞价购买。

### 使用场景

| 场景 | 适用条件 | 预期效果 |
|------|----------|----------|
| **大规模程序化购买** | 需要跨多个 DSP/媒体源投放 | 统一管理平台，最大化覆盖和效率 |
| **DSP 聚合** | 同时使用多个 DSP 供应商 | 通过 DV360 统一管理和优化 |
| **品牌安全控制** | 对广告曝光位置有严格要求 | 详细的品牌安全设置和黑名单管理 |
| **第三方数据接入** | 使用 CDP/DMP 等外部数据源 | 精准定向，提升投放效果 |
| **复杂审批流程** | 大型企业多层级审批需求 | IO 审批工作流，确保合规性 |

### 广告位（Ad Placements）

DV360 的广告位来自其连接的媒体供应商和 SSP（Supply Side Platform），主要包括：

| 广告位类型 | 展示位置 | 说明 |
|-----------|----------|------|
| **Programmatic Direct (PMP)** | 优质媒体预购库存 | 与媒体方直接谈判的优质展示位 |
| **Private Marketplace (PI)** | 私有市场拍卖库存 | 邀请制程序化直采 |
| **Open Auction** | 公开拍卖市场 | RTB 实时竞价，所有买家参与 |
| **Reseller Inventory** | 第三方代理库存 | 通过中介购买的媒体库存 |
| **First-Party Inventory** | 自有媒体库存 | 广告主自己的网站/App |
| **Video Pre-roll** | 视频前贴片 | YouTube/OTT/CTV 视频广告 |
| **Video Mid-roll** | 视频中插广告 | 长视频内容中的广告 |
| **Video Post-roll** | 视频后贴片 | 视频结束后的广告 |
| **Banner Display** | 网页横幅广告 | 各种尺寸的展示广告 |
| **Native Ads** | 原生广告 | 与信息流内容融合的广告 |
| **Connected TV (CTV)** | 智能电视广告 | Hulu/Peacock/Roku 等流媒体平台 |
| **OTT/TV** | 在线流媒体电视 | 跨屏视频广告体验 |
| **Mobile In-App** | 移动应用内广告 | App 内横幅/插屏/激励视频 |
| **Audio Ads** | 音频广告 | Spotify/Pandora 等音乐平台 |
| **Digital Out-of-Home (DOOH)** | 数字户外广告 | 地铁站/商场/便利店数字屏幕 |

> **注意**: DV360 本身不拥有媒体库存，所有广告位均来自连接的 SSP 和媒体供应商。具体可用广告位取决于：
> 1. 已配置的 SSP 连接（如 Google Ad Manager, Xandr, PubMatic 等）
> 2. 媒体的品牌安全和内容分类设置
> 3. 广告主的投放策略和预算分配

---

## 4.1 完整层级结构图

```
Google Marketing Platform (GMP)
    │
    └── Partner (合作伙伴 / 媒体方)
            │
            └── Buyer (广告买家 / DSP 代理商)
                    │
                    ├── buyer_id (买家 ID)
                    ├── status (状态: PENDING / ACTIVE / REJECTED)
                    │
                    ├── Campaign (广告系列)
                    │       ├── campaign_id (系列 ID)
                    │       ├── name (名称)
                    │       ├── status (状态)
                    │       ├── start_date / end_date (投放时间)
                    │       └── budget (预算)
                    │
                    └── Insertion Order (IO / 广告订购单)
                            │
                            ├── io_id (IO ID)
                            ├── name (名称)
                            ├── status (状态: DRAFT / APPROVING / ACTIVE / PAUSED / ENDED)
                            ├── start_date / end_date (投放时间)
                            ├── budget (预算 / CPM 或 CPD)
                            ├── bid_strategy (出价策略)
                            ├── creative_set_id (关联创意集)
                            │
                            └── Line Item (LI / 行项目)
                                    │
                                    ├── li_id (行项目 ID)
                                    ├── name (名称)
                                    ├── status (状态)
                                    ├── type (类型: PROGRAMMATIC_AGENCY / PROGRAMMATIC_DIRECT / REMARKETING / HOSTED)  
                                    ├── budget (预算 / flight 级别或累计)
                                    ├── billing_event (计费方式: CPM / CPC / CPD / CPV)
                                    ├── targeting (定向配置)
                                    │       ├── audience_segment (受众细分)
                                    │       ├── placement (投放位)
                                    │       ├── device_type (设备类型)
                                    │       ├── creative_type (创意类型)
                                    │       └── geo_location (地理位置)
                                    │
                                    ├── Creative Set (创意集)
                                    │       └── Creative (创意)
                                    │               ├── creative_id (创意 ID)
                                    │               ├── type (类型: BANNER / VIDEO / NATIVE / HTML5)
                                    │               ├── file (创意文件)
                                    │               ├── dimensions (尺寸)
                                    │               └── tracking_urls (追踪链接)
                                    │
                                    └── Reporting (报表)
                                            ├── impression_tracking (展示追踪)
                                            ├── click_tracking (点击追踪)
                                            └── conversion_tracking (转化追踪)
```

---

## 4.2 核心概念说明

### 层级关系图解

```
┌─────────────────────────────────────────────────────────────────────┐
│  Campaign (广告系列) — 战略层                                        │
│  • 定义整体广告目标、预算、时间范围                                  │
│  • 可包含多个 IO / Line Item                                         │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│  Insertion Order (IO / 广告订购单) — 合同层                          │
│  • 与媒体方签订的广告投放合同                                        │
│  • 包含审批流程 (APPROVING → ACTIVE)                                │
│  • 设置总预算和计费方式                                              │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│  Line Item (LI / 行项目) — 执行层                                    │
│  • 具体的广告投放指令                                                │
│  • 定义定向、出价、预算分配                                          │
│  • 支持多种类型: 程序化Agency / 程序化直采 / ремаркетинг / 托管      │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│  Creative Set → Creative (创意) — 素材层                             │
│  • 实际投放的广告素材                                                │
│  • 支持多种格式: 横幅/视频/原生/HTML5                               │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 4.3 各层级字段说明

### Partner（合作伙伴）
| 字段 | 说明 |
|------|------|
| `partner_id` | 合作伙伴 ID |
| `name` | 合作伙伴名称 |
| `partner_type` | 类型: PUBLISHER (媒体) / BUYER (买家) / AGENCY (代理商) |

### Buyer（广告买家）
| 字段 | 说明 |
|------|------|
| `buyer_id` | 买家 ID |
| `name` | 买家名称 |
| `status` | PENDING / ACTIVE / REJECTED |
| `payment_profile_id` | 付款配置 ID |
| `allowed_buyer_types[]` | 允许的买家类型 |

### Campaign（广告系列）
| 字段 | 说明 |
|------|------|
| `campaign_id` | 广告系列 ID |
| `name` | 名称 |
| `status` | DRAFT / ACTIVE / PAUSED / ENDED |
| `start_date` | 开始日期 |
| `end_date` | 结束日期 |
| `budget` | 系列级别预算 |
| `client_campaign_id` | 客户端自定义系列 ID |

### Insertion Order（IO / 广告订购单）
| 字段 | 说明 |
|------|------|
| `io_id` | IO ID |
| `name` | 名称 |
| `status` | DRAFT / APPROVING / ACTIVE / PAUSED / ENDED / REJECTED |
| `start_date` | 开始日期 |
| `end_date` | 结束日期 |
| `budget.total_amount_micros` | 总预算（微单位） |
| `billing_event` | 计费方式: CPM / CPC / CPD / CPV |
| `creative_set_id` | 关联创意集 ID |
| `approval_status` | 审批状态: PENDING / APPROVED / REJECTED |
| `notes` | 备注信息 |

### Line Item（LI / 行项目）
| 字段 | 说明 |
|------|------|
| `line_item_id` | 行项目 ID |
| `name` | 名称 |
| `status` | DRAFT / APPROVING / ACTIVE / PAUSED / ENDED |
| `type` | 程序化类型: PROGRAMMATIC_AGENCY / PROGRAMMATIC_DIRECT / REMARKETING / HOSTED |
| `budget.total_amount_micros` | 预算金额 |
| `billing_event` | 计费方式: CPM / CPC / CPD / CPV |
| `bid_amount_micros` | 出价金额 |
| `impression_cap` | 展示上限 |
| `click_cap` | 点击上限 |
| `targeting` | 定向配置 |

### Targeting（定向配置）
| 字段 | 说明 |
|------|------|
| `audience_segment` | 受众细分 ID 列表 |
| `placement.values` | 投放位 URL/APP ID 列表 |
| `device_type` | 设备类型: DESKTOP / SMARTPHONE / TABLET / ALL |
| `creative_type` | 创意类型: BANNER / VIDEO / NATIVE / HTML5 |
| `geo_location.country_codes` | 国家代码列表 |
| `geo_location.region_codes` | 地区代码列表 |
| `frequency_capping` | 频次控制配置 |

### Creative（创意）
| 字段 | 说明 |
|------|------|
| `creative_id` | 创意 ID |
| `name` | 名称 |
| `type` | BANNER / VIDEO / NATIVE / HTML5 |
| `file_url` | 创意文件 URL |
| `dimensions.width` | 宽度 |
| `dimensions.height` | 高度 |
| `click_through_url` | 点击跳转 URL |
| `tracking_urls.click_tracking[]` | 点击追踪 URL |
| `tracking_urls.impression_tracking[]` | 展示追踪 URL |

---

## 4.4 IO 与 Line Item 的关系

```
┌─────────────────────────────────────────────────────────────────────┐
│  一个 Campaign 可包含多个 IO                                         │
│  一个 IO 可包含多个 Line Item                                        │
│  一个 Line Item 关联一个 Creative Set                                │
└─────────────────────────────────────────────────────────────────────┘

示例结构:
Campaign: "Summer 2026 Brand Campaign"
  ├── IO-001: "Programmatic Agency - Display"
  │     ├── LI-001: "Banner Ads - US - Desktop"
  │     ├── LI-002: "Banner Ads - US - Mobile"
  │     └── LI-003: "Video Ads - Global"
  │
  ├── IO-002: "Programmatic Direct - Premium Publishers"
  │     ├── LI-004: "Sponsored Content - Forbes"
  │     └── LI-005: "Native Ads - Bloomberg"
  │
  └── IO-003: "Remarketing - Engaged Users"
        └── LI-006: "Remarket - Site Visitors 7d"
```

---

## 4.5 Line Item 类型说明

| 类型 | 说明 | 适用场景 |
|------|------|----------|
| **PROGRAMMATIC_AGENCY** | 通过 DSP 进行程序化竞价购买 | 需要多 DSP 聚合、自动化优化 |
| **PROGRAMMATIC_DIRECT** | 程序化直采（PMP/PI） | 优先购买优质媒体库存 |
| **REMARKETING** | ремаркетинг投放 | 针对已访问过网站的用户再触达 |
| **HOSTED** | 托管广告（非程序化） | 直接购买固定位置、固定时间段广告 |

---

# 5. 平台对比速查表

## 5.1 层级结构对比

| 层级 | Google Ads | Meta | TikTok | DV360 |
|------|------------|------|--------|-------|
| **顶级** | Customer ID | Business Manager | Business Center | Partner |
| **第二层** | Campaign Budget | Ad Account | Advertiser | Buyer |
| **第三层** | Campaign | Campaign | Campaign | Flight |
| **第四层** | Ad Group | Ad Set | Ad Group | Creative Set |
| **第五层** | Ad + Keywords/Product Group | Ad + Creative | Ad + Spark Info | Creative |
| **特殊** | Campaign Criteria | Pixel/CAPI | targeting | bid_strategy |

## 5.2 广告类型对比

| 广告类型 | Google Ads | Meta | TikTok | DV360 |
|---------|------------|------|--------|-------|
| 搜索广告 | ✅ Search | ❌ | ❌ | ✅ (搜索显示) |
| 购物广告 | ✅ Shopping + PMax | ✅ Catalog | ✅ Shop | ✅ |
| 视频广告 | ✅ YouTube | ✅ Video | ✅ In-Feed | ✅ |
| 展示广告 | ✅ Display | ✅ Display | ❌ | ✅ |
| Spark Ads | ❌ | ❌ | ✅ 独家 | ❌ |
| 应用安装 | ✅ App | ✅ App | ✅ App | ✅ |
| 消息广告 | ❌ | ✅ 独家 | ❌ | ❌ |
| 线索收集 | ✅ Lead Form | ✅ Instant Form | ✅ Lead Form | ✅ |
| TopView | ❌ | ❌ | ✅ 独家 | ❌ |

## 5.3 核心差异总结

```
┌─────────────────────────────────────────────────────────────────────┐
│  Google Ads                                                          │
│  ├── 优势: 搜索意图驱动、PMax 全渠道自动化、Shopping 独立管理        │
│  ├── 特点: Keywords 为核心、Bidding Strategy 丰富、Product Group    │
│  └── 适用: 意图明确、转化导向的广告活动                              │
├─────────────────────────────────────────────────────────────────────┤
│  Meta Marketing API                                                  │
│  ├── 优势: 受众定向最灵活、Pixel+CAPI 双轨追踪、消息广告独占         │
│  ├── 特点: 兴趣/行为驱动、Instant Form 便捷、Dynamic Ads             │
│  └── 适用: 品牌认知、社交互动、精准人群触达                          │
├─────────────────────────────────────────────────────────────────────┤
│  TikTok Ads                                                          │
│  ├── 优势: Spark Ads 原生感强、年轻用户群体、TopView 强曝光          │
│  ├── 特点: 视频原生、内容驱动、达人授权机制                          │
│  └── 适用: 品牌曝光、年轻人群、电商带货                              │
├─────────────────────────────────────────────────────────────────────┤
│  DV360                                                               │
│  ├── 优势: RTB 实时竞价、跨媒体聚合、程序化购买效率最高              │
│  ├── 特点: 支持 DSP 聚合、CDP/DMP 接入、第三方数据                   │
│  └── 适用: 大规模程序化购买、跨平台投放、数据驱动优化                │
└─────────────────────────────────────────────────────────────────────┘
```

---

**文档版本**: v3.0  
**创建日期**: 2026-08-20  
**作者**: Ryan
