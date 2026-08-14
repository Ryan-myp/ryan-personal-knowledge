# Google Ads PMax for Shopping 深度实战：GMX、Merchant Center、Feed 优化、商品分组

> **领域**: 广告投放 / GOOGLE_ADS
> **深度**: ⭐⭐⭐⭐⭐ 实战级指南
> **标签**: GOOGLE_ADS, 广告投放
> **更新时间**: 2026-08-14
> **类型**: 深度知识文档

---

> 本文是 Ryan 个人知识库 Google Ads 体系中的 **Shopping / PMax 专项深度文档**。
> 它与同目录下 `google-ads-display-video-shopping-app-deep.md`（Display/Video/Shopping/App 泛类）
> 和 `google-ads-architecture-deep.md`（整体架构）**严格区分**：
> 本篇完全聚焦 **PMax for Shopping + GMX（Google Merchant Experience/商品体验）+ Merchant Center +
> Feed 优化 + 商品分组（Product Groups）**，深入 GMX 数据链路、Feed 诊断、单品（product 视图）指标、
> 商品类目瀑布拆分等现有文档未展开的核心细节。
> 适合：独立站 3C/服饰/家居/游戏周边卖家、DTC 品牌操盘手、跨境电商代理商、电商 App 增长负责人、
> 直播带货供应链团队在 Google 渠道的落地执行。

## 一、核心概念与架构

### 1.1 什么是 Performance Max for Shopping（PMax-S）

**Performance Max（全效果广告）** 是 Google 基于目标的自动化广告系列类型。
传统手工广告系列让你选择渠道、关键词、出价，而 PMax 把这一切外包给机器学习，
只用你输入的 **转化目标 + 预算 + 资产（素材）** 驱动投放。

PMax for Shopping 是其中最特殊的一种：**不需要你发明语言创意**，
它直接消费 **Merchant Center 里的商品 Feed（Product Feed）**。
也就是说，你只需要把商品数据维护对，PMax 会自动把商品拼装成
购物轮播（Shopping Carousel）、图文、视频、搜索栏等多种形态。
核心工作从"做广告词"变成了"**做 Feed**"，这是普通 SEM 思维的 180° 转变。

**GMX 词义澄清：**
GMX 在 Google 语境下有两层含义，容易混淆：

1. **Google Merchant eXperience（历史称谓）/ Google Merchant Experience**：
   指 Google 面向电商卖家的整套商品数据产品体验，以 Merchant Center 为核心。
2. **GMX 结构化导入**：特指通过 **Google Merchant Center 的数据源（Data Sources）** 体系
   把商品源（Content API 源 / 定期文件上传 / 本地文件 / 关联平台）接入的过程。
   本文的 GMX 主要指这一整套 **Feed 接入与诊断体系**，
   它与 PMax 消费的商品数据是同一份数据。

两者本质是同一数据的两种视角：**GMX 管"货怎么进来、是否健康"，
PMax 管"货进来之后怎么花预算卖出去"。**

### 1.2 PMax-S 与标准购物（Standard Shopping）的本质差异

| 维度 | PMax for Shopping | 标准购物广告（Standard Shopping） |
|------|-------------------|------------------------------------|
| 广告系列子类型 | `PERFORMANCE_MAX_FOR_GOALS`（带 Shopping 目标） | `SHOPPING_SMART_ADS` / `SHOPPING_GOALS` |
| 出价方式 | 只能智能出价（tROAS / tCPA / Max Conv） | 可手动 CPC 或智能出价 |
| 渠道 | 搜索 + YouTube + Discover + Gmail + 展示全网 | 仅 Google 搜索购物标签 + 部分重定向 |
| 关键词 | 无人工关键词，靠 Feed 标题/内容理解 | 可配置否定关键词、品类定位大致引导 |
| 商品组 | 通过 **Feed + 资产组** 间接控制，无商品组细分 | 有完整 **商品组（Product Group）** 拆分（除全部商品外的维度） |
| 素材 | 必须提供文案/图片/视频资产组（Asset Group） | 无需素材，纯商品卡片 |
| 学习期 | 事件驱动，换预算/资产会重置 | 相对稳定 |
| 控制粒度 | 低，靠拆分系列/资产组/Feed 编码隔离 | 高，可逐商品组控价 |

一句话总结：**PMax-S 用"素材 + Feed + 转化"换回了自动化全渠道，
代价是放弃了标准购物的商品组级人工控制。** 想找回控制力，
恰恰要靠 **Feed 上的深度工作 + 多系列拆分（瀑布拆分）**，
而不是回到手工竞价。

### 1.3 核心参与方总览

```
                       ┌─────────────────────────────────────────────┐
                       │               Merchant Center (GMX)          │
                       │  商品数据源 Data Sources                      │
                       │   ├ Content API 源   (GMC API 实时推送)        │
                       │   ├ 定期文件上传     (FTP/SFTP/GS/HTTP)         │
                       │   ├ 本地文件直接     (TSV/XML/RSS Feeds)         │
                       │   └ 补充 Feed (Supplemental Feed, 覆盖增量)     │
                       └───────────────▲─────────────────────────────┘
                                       │ 商品信号同步 (Product signals)
                                       │ 状态: approved / disapproved / pending
              ┌────────────────────────┴─────────────────────────┐
              │              Google Ads (PMax for Shopping)        │
              │                                                    │
              │  性能广告系列 PMax (PERFORMANCE_MAX_FOR_GOALS)     │
              │    ├ 资产组 Asset Group (图文/视频/标题/说明)     │
              │    └ 出价 TARGET_ROAS / TARGET_CPA / MAX_CONV      │
              │                                                    │
              │  (可选) 标准购物系列 → 商品组 Product Group 拆分    │
              └────────────────────────┬─────────────────────────┘
                                       │ 竞价请求 (auction)
                                       ▼
        ┌──────────────────────────────────────────────────────────────┐
        │              Google 投放矩阵 (Search/YouTube/Discover/Gmail)  │
        │   购物轮播 | 搜索横幅 | 视频 In-stream | 展示 | Discover 卡    │
        └──────────────────────────────────────────────────────────────┘
```

### 1.4 广告系列子类型归档（GAQL/API 视角）

在 API 层面，PMax 相关的 `campaign.advertising_channel_sub_type` 枚举如下：

| API 枚举值 | 含义 | 出价 | 典型用途 |
|------------|------|------|----------|
| `PERFORMANCE_MAX_FOR_GOALS` | PMax（通用目标，含购物目标） | tROAS/tCPA/MAX_CONV | 通用 PMax，可自定义目标 |
| `PERFORMANCE_MAX_FOR_TRAVEL_GOALS` | 旅游 PMax | MAX_CONV/tCPA | 酒店/航班 |
| `SHOPPING_GOALS` | 购物目标类（计划中的子类型） | tROAS | 以商品为驱动的购物目标 |
| `PERFORMANCE_MAX_FOR_ANDROID_APPS` | Android 应用 PMax | MAX_CONV/tCPA | App 增长 |
| `APP_CAMPAIGN` | 普通应用广告 | tCPA | App 通用 |
| `SHOPPING_SMART_ADS` | 标准购物（SMART 变体） | — | 标准购物 |

关键：对电商而言，勾选"购物"目标后，PMax 仍属于
`PERFORMANCE_MAX_FOR_GOALS`，但系统会把 **Merchant Center Feed**
作为主要商品信号源，与"标准销售目标-only 的 PMax"在商品利用上有差异。
API 侧判断是否真的在消费商品数据，看的是
`campaign.shopping_setting`（已下线）与 Asset Group 是否链接商品。

### 1.5 PMax 的三个"齿轮"：信号 → 资产 → 出价

PMax 是一个闭环系统，围绕三个输入旋转：

- **信号（Signals）**：受众信号、品类、产品 Feed 中的商品属性
  （标题里的关键词、价格、品牌、GTIN），是"投给谁、组什么创意"的依据。
- **资产（Assets）**：Asset Group 里的素材
  （`SITELINK`, `CALLOUT`, `CALL`, `STRUCTURED_SNIPPET`, `PRICE`,
   `IMAGE`, `YOUTUBE_VIDEO`, `TEXT`, `HEADLINE`, `BUSINESS_NAME`,
   `LEAD_FORM`）。电商场景下，商品卡片（来自 Feed）与这些资产自由拼接。
- **出价（Bidding）**：`TARGET_ROAS`, `TARGET_CPA`, `MAXIMIZE_CONVERSIONS`,
  `MAXIMIZE_CONVERSION_VALUE` 等策略决定每一次拍卖愿意出的价。

**为什么 GMX/Feed 在 PMax 里 = 命脉：**
因为 PMax 没有关键词，系统对"哪个用户搜什么词该看到你哪个商品"的理解，
**几乎全部来自 Feed 字段**（标题的语义、类别映射、属性扩展）。
Feed 一顿乱写，PMax 就像盲人开车：预算照花，转化惨淡。
这就是本文反复强调 **"Feed 是第一生产力"** 的原因。

### 1.6 数据链路全景：从商品录入到一次拍卖

一条商品从录入到曝光，走的链路是：

```
商品录入 (EMS/ERP/PIM)
   │ 1. 生成 TSV/XML 或走 Content API
   ▼
Merchant Center 数据源 (GMX)
   │ 2. 数据源抓取/接收 → 商品入库
   │ 3. 品类映射 + 属性校验 + 政策审核
   ▼
商品状态 (approved / disapproved / pending)
   │ 4. 同步到 Google Ads 作为商品信号
   ▼
PMax 资产组 + 出价策略
   │ 5. 每次竞价实时决策
   ▼
广告展示 (轮播/搜索/视频/Discover)
   │ 6. 转化回流 (离线转化/像素) → 供出价学习
   ▼
报表 (product 视图 / campaign 视图)
```

**关键结论：任何一环断裂（Feed 拒绝、属性缺失、转化回流中断），
下游全部失效。** 排查效率 = 对这条链路的熟悉程度。

### 1.7 GMX 三层 Feed 源：API、定期上传、补充 Feed

**第一层：Content API 源（实时推送，推荐大卖家）**
通过 Google Merchant Content API（`content.googleapis.com`）实时推送/更新商品。
优点：秒级更新、支持价格提醒、无需定时抓取。
缺点：需要工程能力；高频推送要注意配额。

**第二层：定期文件上传（SPF/SFTP/Cloud Storage/HTTP）**
卖家把 TSV/XML/RSS 放到指定地址，GMC 按设定的时区与频率定时抓取。
优点：零工程、稳定。缺点：更新滞后（通常 1-24h），时区不一致。

**第三层：补充 Feed（Supplemental Feed）**
不独立建商品，而是 **叠加在主 Feed 之上，用 target country/feed label
做 join**，只覆盖你提供的字段（如只补 shipping 或只补 sale_price）。
其优先级凌驾于主 Feed 的同名字段，用于快速补改而无需重建主 Feed。
生命周期内可以挂多个补充 Feed，用优先级 `priority` 控制。

**选型建议表：**

| 场景 | 推荐方案 | 理由 |
|------|----------|------|
| SKU < 500，改动低频 | 定期文件上传 | 简单稳定，够用 |
| SKU 数千，价格随库存频繁波动 | Content API | 秒级同步，避免价格/库存陈旧 |
| 需要按市场补 shipping/sale 价 | 补充 Feed | 不污染主 Feed，覆盖粒度细 |
| 多语言多国家多店铺 | 每国家一 Feed + Feed Label | 隔离政策与费率 |

**务必注意：GMC 的 `feedLabel` 和 `targetCountry` 要与广告账户的国家/语言对齐，
否则商品虽然 approved，在 Ads 侧可能 fl: 不匹配而不可用。**

### 1.8 为什么"控制力"丢失后反而要靠拆分

标准购物靠商品组控价，PMax 拿走了这个按钮。
找回控制力的三把钥匙（后文展开）：

1. **Feed 侧编码隔离**：用 `custom_label_0~4` 给商品打业务标签，
   通过 & 过滤让不同 PMax 只投某段商品（配合 Asset Group signal）。
2. **按 ROAS/品类瀑布拆分**：把高毛利、低毛利商品拆到不同 PMax，
   各自配不同的 tROAS。
3. **并行标准购物竞技场**：用标准购物（可商品组拆分 + 手动 CPC）与 PMax 并行
   Cookie 很小、容易屠 PMax，是"诊断武器"而非"替补"。

这三把钥匙都围绕同一个思想：**自动化吞掉了 fine-grained 控制，
你必须用数据工程（Feed 标签）、架构工程（拆分）、竞价工程（tROAS）
在更高的抽象层找回。** 这就是本文全部内容的核心方法论。

### 1.9 GMX：Merchant Center 账户体系与数据源（Data Sources）详解

**Merchant Center 账户层级：**

```
Google Ads MCC (经理账户)
   └── Ads 客户账户 (Customer, 如 123-456-7890)
         嵌套在 MCC 下管理
Google Merchant Center 账户 (Content API Merchant ID)
   ├── 数据源 Data Sources
   │    ├─ Primary Feeds (主 Feed: 商品主体)
   │    ├─ Supplemental Feeds (补充 Feed: 覆盖字段)
   │    └─ Local inventory feeds (本地库存: LIA 用)
   ├── 配送设置 (Shipping Settings)
   ├── 税率设置 (Tax Settings)
   ├── 促销 (Promotions / 优惠券)
   └── Diagnostics (诊断控制台)
```

**两个账户体系的唯一连接点：**
Ads 账户必须与 GMC 账户通过 **"Linked accounts → Google Ads"** 链接。
链接后 GMC 的商品数据才会以信号形式进入 PMax。
如果没链接，你在 Ads 里建的 PMax 即便选了"购物"，也是没有商品的空壳。

**三个容易踩的坑：**
1. Ads 账户与 GMC 账户不在同一国家/币种 → 商品无法匹配。
2. 多人共用 GMC 导致审批混乱 → 权限要收敛为 Owner/Admin/Standard。
3. PMax 系列所在 Ads 账户与 GMC 未链接 → 白建系列。

### 1.10 TSV / XML(RSS 2.0) / Google 产品 Feed 格式细节

**TSV（Tab-separated values）** 是最常见的上传格式：

```
# 第一行是字段名, 字段间用 TAB; 不要加 BOM; UTF-8 编码
id<TAB>title<TAB>description<TAB>link<TAB>image_link<TAB>price<TAB>availability<TAB>condition
sku-001<TAB>Anker 10000mAh 磁吸充电宝<TAB>20W 快充便携<TAB>https://shop.example/p/001<TAB>https://img.example/001.jpg<TAB>19.99 USD<TAB>in stock<TAB>new
```

**XML（RSS 2.0）格式（开放式网络铺货常用）：**

```xml
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:g="http://base.google.com/ns/1.0">
  <channel>
    <title>My Product Feed</title>
    <link>https://example.com</link>
    <description>3C accessories catalog</description>
    <item>
      <g:id>sku-0011</g:id>
      <g:title>Anker 10000mAh 磁吸充电宝</g:title>
      <g:description>20W PD fast charge, portable</g:description>
      <g:link>https://example.com/p/001</g:link>
      <g:image_link>https://img.example.com/001.jpg</g:image_link>
      <g:price>19.99 USD</g:price>
      <g:availability>in stock</g:availability>
      <g:condition>new</g:condition>
      <g:brand>Anker</g:brand>
      <g:gtin>00842322978883</g:gtin>
      <g:google_product_category>Electronics > Communications > Phone Accessories > Cases</g:google_product_category>
    </item>
  </channel>
</rss>
```

**关键细节：**
- XML 必须做 HTML 转义（`&`→`&amp;`），否则解析失败。
- 时间戳要带时区，配合调度时间避免抓取到半成品。
- 文件名含日期版本（如 `feed_20260814.tsv`）便于回滚。
- Feed 行内不要有换行符，标题/描述里出现的换行会破坏解析。

### 1.11 定时抓取的范围、时区与失败补偿

| 参数 | 推荐值 | 说明 |
|------|--------|------|
| 抓取频率 | 每天 1 次 起（贵品每小时 1 次） | Content API 推送则无此限制 |
| 抓取时间 | 站内价格/库存变更低峰后 1h | 与转化回流错峰 |
| 时区 | 与 GMC 账户一致 | 跨时区用 UTC 换算 |
| 失败重试 | 连续失败 3 次告警 | 文件 URL 变化/权限丢失最常见 |
| 错误处理 | 上传 `delivery_failure` 通知 | 监控邮件/API 通知 |

**核心认知：** 定期抓取 = 旧数据的延迟（通常 12-24h 才生效）。
对价格战、大促、缺货频繁的商品，**Content API 是唯一能跟上节奏的方案**。


---

## 二、深度原理解析

### 2.1 Feed 字段体系：必填 / 建议 / 可选

Google 的商品 Feed 字段按"强制（Required）/ 强烈建议（Strongly Recommended）/
可选（Optional）"分三档。弄清每一档对 PMax 的意义，才能知道优化从哪里下手。

| 字段 | 是否必填 | 为什么重要 / PMax 影响 |
|------|----------|--------------------------|
| `id` | ✅ 必填 | 商品唯一标识，单品聚合的关键，必须稳定 |
| `title` | ✅ 必填 | PMax 理解语义的主要来源；决定匹配质量与 CTR |
| `description` | ✅ 必填 | 补足语义，影响内容相关性与 Quality |
| `link` | ✅ 必填 | 落地页，影响转化与 Quality Score 变体 |
| `image_link` | ✅ 必填 | 首图，直接决定购物轮播/展示的 CTR |
| `price` | ✅ 必填 | 出价价值锚点，影响 tROAS 的计算 |
| `availability` | ✅ 必填 | `in stock / out of stock / preorder`，决定可投性 |
| `condition` | ✅ 必填（非美=参与度） | `new / used / refurbished` |
| `brand` | 强烈建议 | 无则分类被拒或被忽略，PMax 无法理解品牌诉求 |
| `gtin` | 强烈建议（配备 barcode 国家） | 提升匹配与数据质量，缺则降级 |
| `mpn` | 建议 | 制造商标号，无 gtin 时的替代 |
| `google_product_category` | 强烈建议 | 决定品类定向与分类，优先级最高 |
| `product_type` | 建议 | 你方内部类目，用于细分与 custom_label |
| `sale_price` | 可选 | 促销价，覆盖 price 用于展示与出价 |
| `sale_price_effective_date` | 可选 | 促销窗口，避免过期价误伤 |
| `shipping` | 建议(美内) | 运费影响总价感知与转化 |
| `shipping_weight`/`size`/`color`/`material`/`pattern` | 可选 | 变体属性和过滤标签 |
| `availability_date` | 可选 | 预售/上架时间 |
| `custom_label_0~4` | 可选 | **业务标签，PMax 拆分的主战场** |
| `promotion_id` | 可选 | 关联促销活动 |
| `multipack`/`item_group_id` | 可选 | 变体分组 |

**PMax 视角的关键领悟：**
除了必填字段，`google_product_category`、`product_type`、`brand`、`gtin`、`custom_label`
这几项在很大程度上决定了**系统能否把你的货理解清楚并投给对的人**。
Feed 优化不是"补齐必填就完事"，而是把"系统需要语义的字段"做深。

### 2.2 字段详细原理：title、images、availability

**title（标题）—— PMax 的"类关键词"。**
标准搜索靠 keyword，PMax 靠 title 里的语言来反应检索意图。
Google 会把 title 切成 N-gram，用于：
- 判断商品属于哪个 query（相关性）
- 拼接购物标题（展示用）
- 匹配用户已购/浏览的商品（再营销）

所以 title 的写法有一套行业共识规则：
- 前 30 字符放最强关键词（移动端截断）
- 结构：`品牌 + 关键属性(型号/容量/颜色盖过型号) + 品类词 + 差异化 USP`
- 不要关键词堆砌；每词都有意义；不要全大写（会被判迷惑性）。

**image_link（图片）—— 肉眼可见的第一道 CTR 过滤。**
- 必须白底（美国等要求纯白），至少 100x100，推荐 1200x1200 以上正方形。
- 不得有文字/水印/边框/促销贴纸（会被 disapprove 或降级）。
- 多图 `additional_image_link` 用分号分隔，最多 10 张。

**availability / price —— 出价正确性的数据底座。**
- `in stock` 但落地页缺货 → 差评与退出率上升，拉低转化，PMax 学不到真信号。
- tROAS 计算依赖 `conversions_value / cost`，而价值锚点来自价格；
  若 `price` 与落地页实际不一致，出价模型会系统性偏离。
- 促销价用 `sale_price` 而非直接改 `price`：这样系统能看到
  "原价→促销价"的价差信号，利于价格敏感竞价，且避免价格变动误伤学习。

### 2.3 brand / gtin / identifier_exists / condition 的深层规则

**identifier_exists（标识符是否存在）。**
- 对有 GTIN 的商品，缺 gtin 会导致 disallow（federal 政策）或降级。
- 如果商品确实没有 GTIN（如无条码的定制货），要显式设 `identifier_exists=FALSE`，
  不要留空。留空 = 系统以为你没填，而不是"确实不存在"，会被拒。
- 有 UPC/EAN/ISBN 的国家，`gtin` 建议必填；品牌+MPN 组合可作为无 GTIN 时的替代。

**condition（成色）。** 美国站必填。`used` 需要额外字段
（即 `condition` 为 used 时可能需要说明）。refurbished 需品牌授权。
错标成色直接拒绝（Misrepresentation）。

**brand（品牌）。** 无品牌或未验证时，可能会导致：
- Shopping 拒绝（某些品类强制品牌）
- PMax 无法理解品牌搜索意图（"Nike 跑步鞋"的用户搜不到你）
- 与 Feed 里的品牌不一致 → 数据质量下降

**一张决策表：**

| 情况 | 正确做法 | 陷阱 |
|------|----------|------|
| 有真实 GTIN | 填 `gtin` | 别乱填假 GTIN 会被判伪造 |
| 无 GTIN 有 MPN | 填 `mpn` + `brand` | 两者都要才有效 |
| 完全无标识 | `identifier_exists=false` | 留空 = 被当缺失 |
| 定制/无品牌 | 自定义品牌或"generic" | 品牌不能与官网不一致 |

### 2.4 shipping 与产品类目（product categories）

**shipping（运费）—— 影响总价感知与转化率。**
- 单件运费：Feed 里填 `shipping[price]`。
- 按国家/地区表：在 Merchant Center 的配送设置（Shipping Settings）统一配置。
- 运费过高会压垮 CVR；免费运费（Free shipping threshold）是转化利器。
- PMax 无法单独为"高运费商品"调价，但高价运费会拉低 tROAS 外壳。
  建议把"包邮"商品和"不包邮"商品拆开做分层实验。

**产品类目（google_product_category）—— PMax 的定向频谱开关。**
- `google_product_category` 决定商品归入 Google 标准品类树，
  这不仅影响展示位置，也影响 PMax 对"该商品什么属性值得突出"的判断。
- 用 `product_type`（你的内部类目）配合 `custom_label` 才能在拆分时引用。
- 类目映射错（如把"手机壳"填成"手机"）会导致严重错配。

**类目映射关系示意：**

```
google_product_category: 电子产品 > 通信 > 手机配件 > 保护套
        └── Google 标准分类（决定展示与季节性理解）
product_type:       3C配件 > 苹果 > iPhone15 > 保护壳 > 磁吸
        └── 你的维度（用于 custom_label / 拆分）
custom_label_0:     high_roas / low_roas  (业务标签)
```

### 2.5 GAQL product 视图：单品级指标的解剖（Python）

PMax 和标准购物都能用 **product_view** 拿到**单品级**指标。
这是诊断"哪些 SKU 在烧钱、哪些在赚钱"的唯一 API 途径。
下面用项目里的 `google_ads_api.py` 客户端（封装 `search`）拉取
`product_group_view` / `product_view`。

```python
# -*- coding: utf-8 -*-
"""
单品级 (product) 指标拉取示例
使用 scripts/google_ads_api.py 中的 GoogleAdsClient
端点: https://googleads.googleapis.com/v24
方法: search -> POST customers/{id}:search
"""
from google_ads_api import GoogleAdsClient

CREDENTIALS = {
    "google_ads": {
        "access_token": "ya29....",          # OAuth2 access token
        "developer_token": "AbCdEf123...",   # developer-token header
        "login_customer_id": "123-456-7890", # login-customer-id header (号码)
    }
}
CUSTOMER_ID = "1234567890"

def fetch_product_metrics(client: GoogleAdsClient, customer_id: str, days: int = 30):
    """拉取商品级指标 (product 视图)。"""
    # product_group_view 在标准购物里是商品组维度;
    # 商品组到单品需要 join product_group_view 不可行,
    # 用 shopping_performance_view + segments.product_item_id 做单品聚合 (购物绩效视图)。
    from_date = f"{days}D_AGO"
    query = f"""
        SELECT
          segments.date,
          shopping_performance_view.product_title,
          shopping_performance_view.offer_id,
          shopping_performance_view.merchant_id,
          shopping_performance_view.country,
          shopping_performance_view.language,
          metrics.impressions,
          metrics.clicks,
          metrics.ctr,
          metrics.cost_micros,
          metrics.conversions,
          metrics.conversions_value,
          metrics.all_conversions_value
        FROM shopping_performance_view
        WHERE segments.date DURING LAST_{days}_DAYS
        ORDER BY metrics.cost_micros DESC
    """
    resp = client.search(customer_id, query)
    if not resp.success:
        print("查询失败:", resp.error)
        return []
    rows = resp.data.get("results", [])
    print(f"共 {len(rows)} 条商品-日期记录")
    # 按 offer_id 聚合，算 ROAS
    sku_map = {}
    for row in rows:
        spv = row.get("shoppingPerformanceView", {})
        m = row.get("metrics", {})
        oid = spv.get("offerId", "?")
        cost = int(m.get("costMicros", 0)) / 1e6      # 微元 -> 元
        cv   = float(m.get("conversionsValue", 0.0))
        agg  = sku_map.setdefault(oid, {"impressions":0,"clicks":0,"cost":0.0,"conv":0,"value":0.0,"title":spv.get("productTitle","")})
        agg["impressions"] += int(m.get("impressions",0))
        agg["clicks"]      += int(m.get("clicks",0))
        agg["cost"]        += cost
        agg["conv"]        += int(m.get("conversions",0))
        agg["value"]       += cv
        agg["roas"]        = cv / cost if cost > 0 else 0.0
        agg["ctr"]         = agg["clicks"]/agg["impressions"] if agg["impressions"] else 0.0
    return sorted(sku_map.values(), key=lambda x: -x["cost"])

if __name__ == "__main__":
    client = GoogleAdsClient(CREDENTIALS)
    skus = fetch_product_metrics(client, CUSTOMER_ID, 30)
    print(f"\n{'SKU':<20}{'CTR':>8}{'Cost':>10}{'ROAS':>8}  Title")
    for s in skus[:40]:
        print(f"{s['title'][:18]:<20}{s['ctr']:>8.3f}{s['cost']:>10.2f}{s['roas']:>8.2f}  {s['title'][:30]}")
```

**解读要点：**
- `cost_micros` 是微元（1/1,000,000 单位货币），除以 1e6 才是实际金额。
- `conversions_value / cost_micros*1e-6` 才是真实 ROAS。
- 按 `offer_id`（Feed 里的 `id`）聚合能看到 **单品级烧钱排行榜**。
- 标题截断、Country 过滤（`shopping_performance_view.country`）在跨境时必加。

### 2.6 出价原理：TARGET_ROAS 的机制解剖

**TARGET_ROAS（目标广告支出回报率）** 是 PMax-S 的默认出价策略。
它不是一个固定出价，而是一个 **"回报/支出"目标的约束优化问题**：

```
每次拍卖:
   pCTR(p) × pCVR(p) × 预期客单价(price→conversion value)
        = 预期转化价值 EV(p)
   目标 ROAS = tROAS_target
   ==> 出价 max_bid ≤ EV(p) / tROAS_target
   （框架内约束: 预算内最大化总转化价值 Σ EV）
约束:
   - 总预算上限 (campaign.budget)
   - 学习期: 需要足够转化事件 (通常 30 天内 15+ / 周)
   - 手调上下限: 可设 tROAS 上限 (max 出价上限) 控制冒进
```

**关键机理：**
- tROAS 越高 = 出价越保守 = 量大减、ROAS 升；反之放宽出价、量增、ROAS 降。
- 系统在**预算约束下最大化总转化价值**，所以 tROAS 只是一个约束阈值，
  实际单次出价会围绕它波动，不会每条都恰好达标。
- 对电商来说，**conversion value 必须可靠**（回传真实订单金额），
  否则 tROAS 的"回报"算错，模型全线失衡。

**设错 tROAS 的后果矩阵：**

| tROAS 设置 | 后果 |
|-----------|------|
| 定得过高（远超历史真实 ROAS） | 出价过保守，量暴跌、学习期拉长、甚至跑不出 |
| 定得过低（远低于历史） | 出价激进、预算快烧完、真实 ROAS 低于预期 |
| 学习期就频繁改动 | 学习重置，永远学不到稳定信号 |

### 2.7 单品级竞价：为什么 PMax 无法单品控价 + 解法

标准购物可以给每个商品组设不同出价。PMax 把出价合并到系列层面，
**无法直接对单品出价**。但 PMax 内部其实会在每次拍卖里给不同商品
估不同的价值（高毛利爆款出价高、冷门出价低）——这是模型行为，不是你能控制的。

**实操解法（把单品控价"伪迁"到 PMax）：**
1. **拆分 PMax**：把高价值 SKU 与低价值 SKU 用 `custom_label` 区分，
   分别建 PMax，各自配不同 tROAS —— 相当于"按 ROAS 分层控价"。
2. **峰值卡预算**：为高价值分层设充足的预算，低价值分层限制预算
   （预算本身就是一个隐式出价上限）。
3. **并行标准购物**：对极少数高价值商品，用标准购物手动 CPC 精确控价，
   与 PMax 并行并观察相互蚕食。

### 2.8 预算分配与学习期（Python 检查学习期状态）

PMax 学习期是**事件驱动**的：每 30 天需要约 15 个转化/周才算稳定，
改预算/资产/出价都会重新触发学习。用 API 检查优化分与转化速率：

```python
def check_learning_health(client: GoogleAdsClient, customer_id: str) -> None:
    """检查 PMax 学习期健康度: 优化分 + 近30天转化速率。"""
    query = """
        SELECT
          campaign.id,
          campaign.name,
          campaign.status,
          campaign.optimization_score,
          campaign_budget.amount_micros,
          metrics.cost_micros,
          metrics.conversions,
          metrics.conversions_value,
          metrics.impressions
        FROM campaign
        WHERE campaign.advertising_channel_sub_type = 'PERFORMANCE_MAX_FOR_GOALS'
          AND segments.date DURING LAST_30_DAYS
    """
    resp = client.search(customer_id, query)
    if not resp.success:
        print("查询失败:", resp.error); return
    print(f"{'Campaign':<22}{'Opt':>6}{'Budget':>12}{'Cost':>10}{'Conv':>6}{'Val':>10}{'tROAS':>7}")
    for row in resp.data.get("results", []):
        cam = row.get("campaign", {})
        b   = row.get("campaignBudget", {})
        m   = row.get("metrics", {})
        cost = int(m.get("costMicros",0))/1e6
        val  = float(m.get("conversionsValue",0.0))
        troas = val/cost if cost>0 else 0.0
        print(
            f"{cam.get('name','')[:20]:<22}"
            f"{cam.get('optimizationScore',0)*100:>5.0f}%"
            f"{int(b.get('amountMicros',0))/1e6:>11.0f}"
            f"{cost:>10.0f}"
            f"{int(m.get('conversions',0)):>6}"
            f"{val:>10.0f}"
            f"{troas:>7.2f}"
        )
    print("\n提示: optimization_score < 0.5 或 30 天转化 < 15 → 大概率在学习/不稳定")
```

- `optimization_score` 反映系列做得多好（0-1）。
- 转化不足时优先**合并转化事件**（主站购买 + 加入购物车 + 订阅）帮助学习，
  但注意合并会导致 tROAS 按"含辅助转化"的价值计算，需理解口径差异。

### 2.9 出价策略枚举与 tROAS 配置的 Go 侧（创建/更新 PMax）

Go 侧直接调用 REST（v24），把 `TARGET_ROAS` 配置写进 PMax：

```go
package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
)

const (
	baseURL       = "https://googleads.googleapis.com/v24"
	accessToken   = "OAUTH_ACCESS_TOKEN"
	developerToken = "DEVELOPER_TOKEN"
	loginCustomerID = "123-456-7890" // 号码不带横杠则直接传字符串
	customerID    = "1234567890"
)

func mutate(endpoint string, payload map[string]interface{}) ([]byte, error) {
	body, _ := json.Marshal(payload)
	req, err := http.NewRequest("POST",
		fmt.Sprintf("%s/%s", baseURL, endpoint), bytes.NewReader(body))
	if err != nil {
		return nil, err
	}
	req.Header.Set("Authorization", "Bearer "+accessToken)
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("developer-token", developerToken)
	req.Header.Set("login-customer-id", loginCustomerID)
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	out, _ := io.ReadAll(resp.Body)
	if resp.StatusCode != 200 {
		return nil, fmt.Errorf("HTTP %d: %s", resp.StatusCode, string(out))
	}
	return out, nil
}

// createPmaxForShopping 创建带 TARGET_ROAS 的 PMax for Shopping
func createPmaxForShopping() error {
	// campaign 必须设置: 名称 + 预算 + advertising_channel_type=Shopping
	// + 子类型 PERFORMANCE_MAX_FOR_GOALS + TARGET_ROAS 出价
	payload := map[string]interface{}{
		"operations": []map[string]interface{}{
			{
				"create": map[string]interface{}{
					"resourceName": fmt.Sprintf("customers/%s/campaigns/-1", customerID),
					"name":         "PMax-Shopping-3C-配件-高价值",
					"status":       "PAUSED",
					"advertisingChannelType": "SHOPPING",
					"advertisingChannelSubType": "PERFORMANCE_MAX_FOR_GOALS",
					"targetRoas": map[string]interface{}{
						"targetRoas": 4.0, // tROAS = 400%
						"cpcBidCeilingMicros": 3000000, // 出价上限 $3.00 (可选)
					},
					"campaignBudget": fmt.Sprintf(
						"customers/%s/campaignBudgets/-1", customerID),
					"finalUrlSuffix": "{lpurl}?utm_source=pmax&utm_medium=shopping",
				},
			},
		},
		"partialFailure": true,
	}
	out, err := mutate(fmt.Sprintf("customers/%s/campaigns:mutate", customerID), payload)
	if err != nil {
		return err
	}
	fmt.Println("创建结果:", string(out))
	return nil
}

func main() {
	if err := createPmaxForShopping(); err != nil {
		panic(err)
	}
}
```

**Go 侧注意：**
- `target_roas` 是 4.0 = 400%（ROAS 是倍数，非百分比数字）。
- `cpc_bid_ceiling_micros` 是可选上限，防止单次 CPC 过高冒进，但别设太紧否则量骤减。
- `partialFailure: true` 保证批量操作中单条失败不影响其他条。
- 新建先用 `PAUSED`，配好资产组与 Feed 校验后再 `resume_campaign`。

### 2.10 资产组（Asset Group）与 Shopping 数据源的绑定原理

PMax 的每个 Asset Group 需要：
- 图片 / 视频（至少一种）
- 标题（最多 5 条 System generated + 手动）
- 长标题（1 条）
- 描述（最多 5 条）
- 业务名称
- 可选 SITELINK / CALLOUT / CALL / STRUCTURED_SNIPPET / PRICE / LEAD_FORM

**与 Feed 的绑定：**
通过 `<custom_label>` 或 `product filters` 让 Asset Group 对应到某段商品
（见 3.4 拆分原理）。Asset Group 的标题/描述是**系统生成的补充文案**，
真正的商品信息仍来自 Feed。所以很多人起的"给 Asset Group 写广告语"
在 PMax-S 里不是主角，主角永远是 Feed 标题。

**Asset Group 常用资产矩阵：**

| 资产类型 | 用途 | PMax-S 权重 |
|----------|------|-------------|
| HEADLINE | 短标题，拼接创意 | 高 |
| LONG_HEADLINE | 长标题，搜索/展示用 | 高 |
| DESCRIPTION | 描述 | 中 |
| IMAGE | 首图 + 附加图 | 高（购物相关） |
| YOUTUBE_VIDEO | 视频素材 | 开放后提升 |
| BUSINESS_NAME | 品牌名 | 中 |
| SITELINK | 链接推荐 | 中 |
| CALLOUT | 卖点短语 | 中 |
| PRICE | 价格卡片 | 中 |
| CALL | 电话 | 低（纯电商） |

**知识结论：** PMax-S 的"素材系统"本质是 **Feed 商品卡 + 资产组宣传文字的
动态拼装引擎**。理解这一点，就不会在 Asset Group 文案上过度纠结，
而是把精力放在 Feed 字段上。

### 2.11 拍卖机制深度：PMax 的出价怎么被"价值化"

PMax-S 里没有固定 CPC 出价，而是转化价值化的 "tROAS 约束优化"。单次拍卖流程：

```
用户发起 query (如 "iphone 15 pro max 无线充电器")
   │
   ├─ recall: 从 Feed 召回候选商品(标题/品类/GTIN 匹配)
   ├─ pCTR:   模型预测点击概率 (标题相关性+首图+品牌)
   ├─ pCVR:   模型预测转化概率 (落地页+价格+历史)
   ├─ EV = pCTR × pCVR × 预期客单价(price→value)
   ├─ bid = min(EV / target_roas, cpc_bid_ceiling)
   └─ 拍卖: 盈亏平衡 vs 其他广告主 → 胜出则展示
```

**实践启示：**
- 提高 `EV` 的手段 = 提高 pCTR（图/标题）、pCVR（落地页/价格）、
  客单价（捆绑/高 SKU 分层）。这比盯着"出价数字"更本质。
- `cpc_bid_ceiling_micros` 是硬上限，防止单次冒进，
  但设太紧会削掉高价值拍卖的胜出机会。
- tROAS 目标是"约束"不是"每次必达"；系统在预算内优化总价值，
  所以偶尔单条 ROAS 低于目标很正常, 不要据单条惊慌。

### 2.12 标准购物的商品组（Product Group）在 API 侧怎么配

标准购物用 **product group（商品组）** 做维度拆分，是"商品分组"最精细的落点。
GAQL 拉取分组：

```python
def list_product_groups(client, customer_id, campaign_id) -> None:
    query = f"""
        SELECT
          product_group.id,
          product_group.type,
          product_group.cpc_bid_micros,
          advertising_Channel=: 0,
          metrics.impressions,
          metrics.clicks,
          metrics.cost_micros
        FROM product_group_view
        WHERE campaign.id = {campaign_id}
    """
    resp = client.search(customer_id, query)
    if not resp.success:
        print("失败:", resp.error); return
    for row in resp.data.get("results", []):
        pg = row.get("productGroup", {})
        m  = row.get("metrics", {})
        print(
            f"PG {pg.get('id')} type={pg.get('type')} bid={int(pg.get('cpcBidMicros',0))/1e6:.2f} "
            f"imps={m.get('impressions')} clicks={m.get('clicks')} "
            f"cost={int(m.get('costMicros',0))/1e6:.2f}"
        )
```

**商品组类型（product_group.type）：**
- `UNIT`：叶子分组, 可设独立 `cpc_bid_micros`。
- `SUBDIVISION`：中间层, 用于把"全部商品"拆成多个 UNIT。

**产品维度（product_condition / brand / category / channel / id）：**
你可以在分支节点用 `product_condition=NEW`、`product_brand=Anker` 等维度细分，
在 UNIT 上给不同出价。这是标准购物相对 PMax 的核心控制能力。

### 2.13 落地页与描述（description）优化对转化价值的影响

- `description` 越长越丰富，越能帮助系统判断相关性（用于 pCTR/pCVR 特征），
  但首屏描述要精炼，把关键卖点放前面。
- 落地页是需要**快**：加载 < 3s、移动端友好、价格/库存/运费可见。
  落地页差直接把 pCVR 拉下来，进而压低 EV 与出价。
- 建议 feed 描述与落地页主文案呼应，避免"内容不一致"被降级。

### 2.14 additional_image_link：多图与变体的数据价值

- `additional_image_link` 以分号分隔多张图，最多 10 张。
- 变体（颜色/容量）用 `item_group_id` 归组 + 每变体一张专属首图。
- 多图 + 高质变体图能给系统更多 pCTR 特征，提升购物轮播点击与转化。

**图规格速查表：**

| 属性 | 要求 |
|------|------|
| 首图 | 白底或纯色, ≥100x100, 建议 ≥1200x1200 正方形 |
| 文件格式 | JPEG/PNG/WebP (GIF 部分不支持) |
| 内容 | 禁止文字/水印/边框/拼接/促销贴纸 |
| 变体 | 每个 variant 独立首图, 用 item_group_id 归组 |
| 移动端 | 正方形 logo 区留白, 避免被 UI 裁剪 |

### 2.15 Feed 规则（Feed Rules）语法与模板覆盖

GMC 的数据源规则（Feed rules）可在**抓取后、审核前**对字段做程序化改写：

```
规则示例:
  若 [shipping country] == US 且 有库存
     则 title  = [brand] + " " + [product_type] + " " + title
     且 price  = 原价 * 0.9 (促销)
     且 google_product_category = 映射表匹配 product_type
```

**覆盖优先级（从低到高）：**
1. 主 Feed 原始值
2. 补充 Feed（Supplemental）同名字段
3. 数据源规则改写（规则优先级最高）

**用途：**
- 按市场/语言差异化 title 模板（跨语言铺货）。
- 汇率换算自动生成多国 price。
- 自动补 google_product_category（用 product_type 映射）。

### 2.16 Feed 校验脚本：提交前自检（Python）

在推送到 GMC 之前先用脚本自检，能挡掉一大部分 DISAPPROVED：

```python
def validate_feed(rows) -> list:
    """对 TSV 行做基本字段校验, 返回问题清单。"""
    errors = []
    required = ["id", "title", "description", "link", "image_link", "price", "availability"]
    for i, r in enumerate(rows, 1):
        for col in required:
            if not r.get(col):
                errors.append((i, f"缺少 {col}"))
        if r.get("title") and len(r["title"]) < 5:
            errors.append((i, "title 过短, 无区分度"))
        if r.get("price") and " " not in r["price"]:
            errors.append((i, "price 缺货币单位 (如 USD)"))
        if r.get("availability") not in ("in stock", "out of stock", "preorder"):
            errors.append((i, "availability 拼音错误"))
        if not r.get("google_product_category"):
            errors.append((i, "缺 google_product_category"))
    return errors
```

**用例：** 大促前批量生成 3000 SKU Feed 时跑一遍，把 missing/bad 字段
在进入 GMC 前修掉，能省下大量 Diagnostics 返工时间。

---

## 三、生产环境实战

### 3.1 战例 S1：3C 配件独立站 3000 SKU 并行架构

**背景：**
一家 3C 配件独立站，3000 个 SKU（手机壳、钢化膜、磁吸支架、移动电源），
客单价 ¥40-¥400，毛利跨度极大（钢化膜 70%，移动电源 30%）。
历史在跑标准购物，利润率极低；目标是把 ROAS 从 2.1 提到 3.5 的同时不丢量。

**问题诊断：**
1. 全部 SKU 挤在一个标准购物系列，低毛利商品拖累整体出价，爆款被"平均化"。
2. Feed title 混乱，大量"iPhone Case 手机壳保护套"这种低区分度写法，
   系统分不清型号（iPhone15 与 iPhone14 混投）。
3. 价格与落地页不同步，tROAS 一旦启用就乱。
4. 转化回流只有"购买"，事件太少，学习期极长。

**解法（并行架构）：**

```
┌───────────── PMax for Shopping (主投放, 80% 预算) ─────────────┐
│  PMax-A · 高价值沉 (custom_label_0=high_roas)                 │
│    商品: 磁吸支架/移动电源/高端壳  · tROAS 400%              │
│  PMax-B · 高转化低价 (custom_label_0=mid_volume)              │
│    商品: 钢化膜/基础壳          · tROAS 280%                  │
│  PMax-C · 新品/滞销 (custom_label_0=new_stock)  · tROAS 200% │
└───────────────────────────────────────────────────────────────┘
┌───────────── 标准购物 (并行诊断, 20% 预算) ───────────────────┐
│  标准购物 S · 全部商品 · 商品组拆分 + 手动 CPC               │
│  用途: 拿到逐商品组真实 CTR/CVR 数据，反哺 PMax 拆分决策     │
└───────────────────────────────────────────────────────────────┘
```

**执行细节：**
- Feed 全部 SKU 打 `custom_label_0`（high_roas / mid_volume / new_stock），
  三个 PMax 各自用 `<custom_label_0=="high_roas">` 等过滤器只投对应段。
- PMax 间通过预算比例（80/20）与重复商品的最小互斥来防蚕食；
  标准购物作为观察窗不主张量。
- 把"购买+加购+订阅"合并为转化目标喂给 PMax，加快学习；
  但报表层面单独看"购买"口径的 ROAS。
- 两周后 PMax-A tROAS 达标 4.1，B 3.1，C 2.3，整体 ROAS 3.4（达 3.5 门内）。

**量化结果表：**

| 分层 | 商品数 | tROAS 目标 | 实际 ROAS | 日预算 | CTR | CVR |
|------|--------|-----------|-----------|--------|-----|-----|
| PMax-A 高价值 | 940 | 400% | 4.1 | ¥3000 | 1.9% | 4.8% |
| PMax-B 高转化 | 1560 | 280% | 3.1 | ¥4200 | 2.3% | 6.1% |
| PMax-C 新品 | 500 | 200% | 2.3 | ¥1200 | 1.2% | 2.9% |
| 标准购物诊断 | 3000 | — | 2.6 | ¥900 | 1.6% | 4.0% |
| **合计** | **3000** | — | **3.4** | **¥9300** | — | — |

**教训：** 拆分不是目的，是手段。真正的杠杆在于 **Feed 分层标签 +
各层差异化 tROAS + 并行诊断数据回路**。

### 3.2 Feed 标题模板优化案例（T1）

**优化前（低区分度）：**
```
iPhone Case 手机壳保护套 透明
Wireless Charger 无线充电器 磁吸
```

**优化后（按分层模板重写）：**
```
【前30字符最强】Apple iPhone 15 Pro Max 磁吸透明手机壳 高清防摔
Anker 兼容 10000mAh 磁吸无线充电宝 PD20W 便携移动电源
```

**标题模板规则（行业共识）：**

| 位置 | 内容 | 说明 |
|------|------|------|
| 1-30 | 品牌 + 核心型号 + 最强属性 | 移动端截断区，必须放最关键信息 |
| 31-60 | 品类词 + 次要属性 | 补充语义 |
| 61-90 | 差异化 USP + 规格 | 大小/容量/颜色 |
| 90+ | （可选）长尾 | 注意别堆砌关键词 |

**为什么 title 是 PMax 的最强杠杆之一：**
- 高相关 title → 系统理解商品 → 匹配到对的需求 → CTR 升、cost 降。
- 重写 title 后：CTR +0.6pp（1.3%→1.9%），同样是 7 天观察窗。
- 变体（颜色/容量）必须在 title 中标明，否则系统会把不同变体当同一商品。

**用 Python 批量重写 title 模板（示例）：**

```python
def build_title(item):
    """按分层模板批量生成 title。
    规则: brand + model + variant(容量/颜色) + 品类 + USP
    """
    brand = item.get("brand", "Anker")
    model = item.get("model", "Charger")
    cap   = item.get("capacity", "10000mAh")
    color = item.get("color", "")
    cat   = item.get("product_type", "磁吸无线充电宝")
    usp   = item.get("usp", "PD20W 便携")
    # 前 30 字符拼最强信息
    head = f"{brand} {model} {cap} {color}".strip()
    return f"{head} {cat} {usp}".strip()

# 应用到每个 item 的 title 字段，再推送 Content API / 上传 Feed
for it in item_list:
    it["title"] = build_title(it)
```

### 3.3 商品分类与瀑布拆分（C1）

**什么是瀑布拆分（waterfall split）：**
把商品按某种优先级（ROAS 潜力/毛利/库存/新品）**逐层向下拆分**到不同 PMax，
像瀑布逐级分流。每一层有独立预算与 tROAS，互不干扰。

**商品类目拆分批配表（推荐口径）：**

| 拆分层 | 判别标准 | 目标 tROAS | 预算策略 |
|--------|----------|-----------|----------|
| 核心盈利品 | 毛利 > 40% 且 历史 ROAS > 3.5 | 400-500% | 充足，主量 |
| 动销品 | ROAS 2.5-3.5 | 300-350% | 稳定 |
| 潜力/新品 | 新品 ≤ 30 天，冷启动 | 200-250% | 试探 |
| 清仓/滞销 | 库存 > 90 天 或 季节性尾声 | 150-200% | 限量，保本 |
| 引流/低毛利 | 低客单拉量 | 180-250% | 控制 |

**瀑布拆分决策流程图：**

```
全部 SKU (3000)
   │ 按 custom_label_0 分流
   ├─ high_roas ────► PMax-A (tROAS 400, 高预算)
   ├─ mid_volume ───► PMax-B (tROAS 300, 稳预算)
   ├─ new_stock ────► PMax-C (tROAS 220, 试探预算)
   └─ clearout  ────► PMax-D (tROAS 160, 限量保本)
```

**python 侧按 ROAS 打标签脚本（从 product 视图回流打标）：**

```python
def assign_labels(client, customer_id, sku_roas, budget_bytes):
    """根据单品 ROAS 给 SKU 分配 custom_label_0（结果是给 Feed 打标参考）。"""
    def tier(roas):
        if roas >= 3.5: return "high_roas"
        if roas >= 2.5: return "mid_volume"
        if roas >= 1.5: return "new_stock"
        return "clearout"
    # 生成待写回 Feed 的 label 映射
    return {offer_id: tier(roas) for offer_id, roas in sku_roas.items()}
```

**关键：不要每天重打标签。** 高频重打会触发 PMax 学习重置。
建议按周/双周出具 ROAS 榜，仅对明显跨层的 SKU 迁移标签。

### 3.4 PMax 商品类目管理的 API 侧：Asset Group 过滤与 custom_label

PMax 控制"投哪些商品"的核心机制，是通过 **Asset Group 的 product filters**
引用 Feed 的 custom_label / id / 品类。下面用 Python 演示创建/更新 Asset Group
并绑定 custom_label 过滤。

```python
ASSET_FILTER = {
    "stringFilters": [
        {"type": "CUSTOM_LABEL", "value": "high_roas", "operation": "EQUALS"}
    ]
}

def create_asset_group(client, customer_id, campaign_id, label) -> None:
    """为 PMax 创建 Asset Group 并绑定 custom_label 过滤。"""
    ag = {
        "campaign": f"customers/{customer_id}/campaigns/{campaign_id}",
        "name": f"AG-{label}",
        "status": "ENABLED",
        # Business Name 资产
        "businessName": {"businessName": "My Brand"},
        # 标题、长标题、描述等资产
        "textAssets": [
            {"text": f"High quality {label} products", "type": "HEADLINE"},
            {"text": "Fast shipping & 30-day returns", "type": "DESCRIPTION"},
        ],
        # 商品过滤: 只投该 custom_label
        "productGroupsFilters": [
            {
                "stringFilters": [
                    {"type": "CUSTOM_LABEL", "value": label, "operation": "EQUALS"}
                ]
            }
        ],
    }
    resp = client.create_ad_group(customer_id, ag)   # 项目里 create_ad_group 封装
    if resp.success:
        print("创建 Asset Group 成功")
    else:
        print("失败:", resp.error)
```

**注意：**
- Asset Group 在 PMax 里对应"一组给某段商品的创意 + 商品过滤"。
- 用 `productGroupsFilters` 的 `CUSTOM_LABEL` 实现"这段商品只在这层跑"。
- 若不打过滤，所有 Asset Group 会投全部商品，拆分失去意义。

### 3.5 tROAS 配置实战指南（导出为配置表）

| 场景 | 推荐 tROAS | 说明 |
|------|-----------|------|
| 冷启动新品 PMax | 用历史同类 ROAS 的 70-80% 起步 | 不要一步到位大目标 |
| 稳定成熟品 | 历史 ROAS × 1.1-1.2 作为爬坡目标 | 每 7-14 天微调不超过 10-15% |
| 大促季（618/黑五） | 临时下调 15-25% 保流量 | 大促后两周内调回 |
| 清仓 | 显著下调求快清 | 保本即可 |
| 优化分 0.3 以下 | 先修 Feed/素材再谈 tROAS | 出价再准也救不了弱资产 |

**tROAS 微调的 Python（读当前 + 改目标）：**

```python
def adjust_troas(client, customer_id, campaign_id, new_troas):
    """更新 PMax 的 tROAS 目标（倍数）。"""
    updates = {
        "targetRoas": {"targetRoas": new_troas}
        # 不重设 cpc_bid_ceiling 以免误伤
    }
    resp = client.update_campaign(customer_id, campaign_id, updates)
    if resp.success:
        print(f"campaign {campaign_id} tROAS -> {new_troas}")
    else:
        print("失败:", resp.error)
```

**调 tROAS 的纪律：**
- 一次性别动超过 10-15%，否则学习重置、量可能骤降。
- 单次调完观察 3-7 天再动下一档。
- 结合预算：tROAS 上调时若预算不够，出价会被预算压住，测不准。
- 数据不足（<15 转化/周）时不要设 tROAS，先用 MAXIMIZE_CONVERSION_VALUE。

### 3.6 并行标准购物：多容器共存的最佳实践

**并行（parallel）的意义：**
- 标准购物保留"商品组拆分 + 手动 CPC + 否定关键词"，能精确测量逐组 CTR/CVR。
- 用标准购物的数据反哺 PMax 的拆分预算分配。

**反蚕食（anti-cannibalization）实现：**

| 手段 | 作用 |
|------|------|
| 用 custom_label 在两类系列间划分商品 | 明确"哪些归 PMax，哪些归标准购物" |
| 给标准购物设"观察"预算（≤ 总预算 20%） | 不抢量，仅诊断 |
| 共享转化目标 | 口径一致，出价可比 |
| 时段错峰（PMax 主、标准购物少） | 减少同时竞争 |

**Observing 模式的 Go 侧（创建标准购物并配手动 CPC）：**

```go
// createStandardShopping 创建标准购物系列（带商品组手动 CPC）
func createStandardShopping() error {
	payload := map[string]interface{}{
		"operations": []map[string]interface{}{
			{
				"create": map[string]interface{}{
					"name":   "StandardShopping-Diagnostics",
					"status": "ENABLED",
					"advertisingChannelType": "SHOPPING",
					"advertisingChannelSubType": "SHOPPING_GOALS",
					"campaignBudget": "customers/1234567890/campaignBudgets/-1",
					"manualCpc": map[string]interface{}{
						"enhancedCpcEnabled": true,
					},
				},
			},
		},
	}
	out, err := mutate("customers/1234567890/campaigns:mutate", payload)
	if err != nil { return err }
	fmt.Println(string(out))
	return nil
}
```

### 3.7 Shopping 展示样式：轮播、Local Inventory、Showcase

**标准购物轮播（Standard Shopping Carousel）：**
Feed 商品卡片组成"一行产品卡"。出现在搜索顶部或侧栏。
决定 CTR 的是首图、价格、标题、品牌、评分。

**本地商品库广告（Local Inventory Ads, LIA）：**
针对"线下门店 + 线上库存"的本地零售。
前提是提交库存到 Merchant Center 的 local products inventory feed。
适用：有门店的连锁品牌、O2O 模式。

**橱窗购物广告（Showcase Shopping）：**
面向"未明确想买哪个型号、还在探索品类"的用户。
由品牌 + 一组相关商品构成，点击展开商品目录。
适用：品牌方做品类探索阶段的种草。

**展示样式选择表：**

| 样式 | 适用场景 | 数据要求 | PMax-S 中出现的频率 |
|------|----------|----------|---------------------|
| 购物轮播 | 明确购买意图 | 标准 Feed | 高 |
| Local Inventory | 有实体店 | 本地库存 Feed | 中（需 LIA 开通） |
| Showcase | 品类探索/品牌种草 | 品牌目录 | 中 |
| 搜索横幅 | 搜索意图 | 正常 | 高 |
| Discover/YouTube | 泛兴趣 | 素材强 | 中 |

**注意：** PMax-S 会自动决定在哪种样式展示，你无法强制。
你能优化的只有：@首图质量、@标题语义、@品类映射、@品牌素材，
这些决定了各样式能不能被触发、CTR 高低。

### 3.8 Feed 诊断：Merchant Center Diagnostics 体系（D1）

**Diagnostics（诊断）分级：**
- **DISAPPROVED（被拒）**：商品不能投放，必须处理。
- **WARNING（警告）**：可投但数据质量问题，可能未来被拒。
- **EXCLUDED（排除）**：因政策/数据源问题被排除。

**item 级拒绝原因（常见）：**

| 拒绝码 | 含义 | 修法 |
|--------|------|------|
| `MISSING_PRICE` | 缺价格 | 补 price |
| `INVALID_PRICE` | 价格非法 | 修正格式 |
| `MISSING_IMAGE` | 缺首图 | 补 image_link |
| `INVALID_IMAGE` | 图片非法/糊 | 换合规图 |
| `GTIN_INVALID` | GTIN 非法 | 换真实 GTIN |
| `BRAND_MISMATCH` | 品牌与官网不符 | 修正 brand |
| `DESTINATION_MISMATCH` | Landing page 与商品不符 | 核对落地页 |
| `TAX/SHIPPING` | 税/运费属性错 | 修正 delivery 设置 |
| `POLICY` | 违反政策（成人/医疗等） | 依政策整改 |

**诊断优先级金字塔：**
```
被拒 DISAPPROVED (不可投, 立即修)
   ▲ 必须优先, 影响直接收入
警告 WARNING (可投但质量差, 次之)
   ▲ 影响匹配质量/可能未来被拒
排除 EXCLUDED (数据源级, 需查源)
   ▲ 少但难缠
```

### 3.9 用 Python + GMC API 拉取商品 offer 并交叉诊断

```python
# -*- coding: utf-8 -*-
"""
拉取 Merchant Center 商品 offer (Content API) 并交叉诊断。
这里演示 REST 调用 GMC Content API: https://shoppingcontent.googleapis.com
"""
import requests

GMC_BASE = "https://shoppingcontent.googleapis.com/content/v2.1"
MERCHANT_ID = "123456789"   # GMC 账户号 (不是 Ads customer_id)
GMC_TOKEN  = "GMC_OAUTH_TOKEN"

def list_offers(merchant_id, token):
    url = f"{GMC_BASE}/{merchant_id}/products"
    headers = {"Authorization": f"Bearer {token}"}
    # status: active|inactive|pending, 用 filters 只看活动
    params = {"status": "active", "maxResults": 50}
    r = requests.get(url, headers=headers, params=params, timeout=30)
    r.raise_for_status()
    return r.json().get("resources", [])

def diagnose_offers(offers):
    """对 offer 做字段完整性检查, 返回问题清单。"""
    issues = []
    for o in offers:
        oid = o.get("id", "?")
        if not o.get("title"):
            issues.append((oid, "MISSING_TITLE"))
        if not o.get("price", {}).get("value"):
            issues.append((oid, "MISSING_PRICE"))
        if not o.get("imageLink"):
            issues.append((oid, "MISSING_IMAGE"))
        if o.get("identifierExists", ...) is not False and not o.get("gtin") and not o.get("mpn"):
            issues.append((oid, "MISSING_IDENTIFIER"))
        if not o.get("googleProductCategory"):
            issues.append((oid, "MISSING_CATEGORY"))
    return issues

if __name__ == "__main__":
    offers = list_offers(MERCHANT_ID, GMC_TOKEN)
    problems = diagnose_offers(offers)
    print(f"检查 {len(offers)} 个 offer, 发现 {len(problems)} 个问题:")
    for oid, issue in problems[:30]:
        print(f"  {oid}: {issue}")
```

**交叉诊断思路：** 把 GMC 拿到的 offer 与 Ads 的 shopping_performance_view
按 `offer_id` join，找出"GMC 里 approved 但 Ads 里没量"的商品（说明 Feed 与
Ads 间的信号没同步 / 品类映射错 / 落地页不一致）。

### 3.10 Feed 规则（Feed Rules）与自动化

**Feed 规则（Supplemental Feed + rules）**：GMC 里可用规则自动改写/补全字段，
例如：
- 把"iPhone"自动打上 `product_type=3C配件>苹果`
- 把价格按汇率自动换算成目标国家货币
- 用模板自动生成 title（可编程化模版）

**规则模板示例（title 拼接）：**
```
规则: title = [brand] [product_type] [title_override]
条件: 仅当 country == US 且 有库存
```

**为什么要规则化：**
- 减少人工逐条改 Feed 的出错率。
- 按市场/语言差异化模板，避免一个模板打天下。
- 配合 HTTP 上传可做到"数据驱动"的全自动 Feed 生成（CI/CD 化）。

### 3.11 性能诊断与季节性（D2）

**季节性（seasonality）：**
- 换季/大促时需求曲线陡变，tROAS 模型基于历史会滞后。
- 处理：大促前 2-3 周用 `Seasonality adjustment`（季节性调整）或临时下调 tROAS，
  保流量卡位。
- 用 `segments.date` 周趋势看是否进入需求高峰期，决定预算加码。

**SKU 拆分后的性能诊断流程：**

```
拉 product 视图 (Python) → 按 offer_id 聚合
   → 按 ROAS/cost 分层
   → 找"烧钱无转化"的 SKU (cost 高, ROAS<历史均值)
   → 打 custom_label 迁移到低 tROAS 层 or 暂停该层
   → 每周一次, 避免学习重置
```

**用 generate_report 做周趋势：**

```python
def weekly_trend(client, customer_id) -> None:
    """用 generate_report 看 90 天周趋势, 识别季节性信号。"""
    resp = client.generate_report(
        customer_id,
        {"start": "2026-05-16", "end": "2026-08-13"},
    )
    if not resp.success:
        print("失败:", resp.error); return
    rows = resp.data.get("results", [])
    print(f"{'Week':<12}{'Impr':>10}{'Clicks':>8}{'Cost':>10}{'Conv':>6}{'Val':>10}")
    for row in rows:
        m = row.get("metrics", {})
        print(
            f"{'--':<12}"
            f"{int(m.get('impressions',0)):>10}"
            f"{int(m.get('clicks',0)):>8}"
            f"{int(m.get('costMicros',0))/1e6:>10.0f}"
            f"{int(m.get('conversions',0)):>6}"
            f"{float(m.get('conversionsValue',0)):>10.0f}"
        )
```

**注意：** `generate_report` 返回的结果是 series 聚合，
要看**单品级**还得回到 `shopping_performance_view`（见 2.5）。
两个视图职责不同：campaign 视图看系列整体与趋势，product 视图看 SKU 明细。

### 3.12 面向不同业务类型的落地建议

| 业务类型 | Focus | tROAS 起点 | 关键动作 |
|----------|-------|-----------|----------|
| 3C 配件独立站 | Feed title + 品类映射 + 分层 | 280-350% | SKU 拆分 + 标题模板 |
| 服饰鞋包 DTC 品牌 | 变体属性 + 品牌素材 | 300-400% | Showcase + 品牌受众 |
| 电商 App 增长 | 转化事件 + LTV 回传 | 250% | Asset Group 视频 + 深链 |
| 游戏周边/潮玩 | 新品冷启动 + 联名 | 200% | 预购 + 限量清仓分层 |
| 跨境代理商（多店铺） | Feed Label 隔离 + 汇率 | 250-350% | 每国家一 Feed + 规则 |
| 直播带货供应链 | 强促销价 + 限时 | 200-280% | sale_price + 促销标签 |

### 3.13 一套完整的 PMax-S 初始化的 Go 侧脚手架（含预算）

```go
package main

// createBudgetAndCampaigns 创建预算 + 三层 PMax，演示完整初始化。
func createBudgetAndCampaigns() error {
	// 1) 创建预算
	budgetPayload := map[string]interface{}{
		"operations": []map[string]interface{}{
			{"create": map[string]interface{}{
				"name":            "PMax-3C-主预算",
				"amountMicros":    9300000000, // 日预算 ¥9300
				"deliveryMethod":  "STANDARD",
				"explicitlyShared": false,
			}},
		},
	}
	if _, err := mutate("customers/1234567890/campaignBudgets:mutate",
		budgetPayload); err != nil {
		return err
	}
	// 2) 层层创建 PMax（此处简化为循环, 实际三层 tROAS 不同）
	tiers := []struct{ name string; troas float64 }{
		{"PMax-A-high_roas", 4.0},
		{"PMax-B-mid_volume", 3.0},
		{"PMax-C-new_stock", 2.2},
	}
	for _, t := range tiers {
		payload := map[string]interface{}{
			"operations": []map[string]interface{}{
				{"create": map[string]interface{}{
					"name":                       t.name,
					"status":                     "PAUSED",
					"advertisingChannelType":     "SHOPPING",
					"advertisingChannelSubType":  "PERFORMANCE_MAX_FOR_GOALS",
					"targetRoas":                 map[string]interface{}{"targetRoas": t.troas},
					"campaignBudget":             "customers/1234567890/campaignBudgets/-1",
				}},
			},
		}
		if _, err := mutate("customers/1234567890/campaigns:mutate", payload); err != nil {
			return err
		}
	}
	return nil
}
```

**初始化后验收四步：**
1. Feed 全部 approved（GMC Diagnostics 全绿）。
2. 每个 Asset Group 至少 1 图 1 标题 1 描述 1 业务名称。
3. 转化目标配置完成（purchase + add_to_cart + subscribe）。
4. 出价策略为 TARGET_ROAS，预算充足不触顶。
全部通过后再 `resume_campaign`，否则先 PAUSED 守住。

### 3.14 素材/Asset Group 实验（Experiment）方法论

**不要拍脑袋改素材。** 用 PMax 系列的素材实验验证：

| 实验维度 | 对照 | 变量 | 观测指标 |
|----------|------|------|----------|
| 首图 | 白底产品图 | 场景图/模特图 | CTR, CVR, cost |
| 视频 | 无视频 | 竖版短视频 | impressions, eCPM |
| 标题 | 系统生成 | 自定义标题 | CTR |
| 描述 | 基础描述 | 促销性描述 | CVR |
| 长标题 | 无 | 长标题(90ch) | 展示份额 |

**实验纪律：**
- 一次只改一个变量（控制变量法）。
- 实验期 ≥ 2-3 周（跨完整学习周期）。
- 用小预算实验层或 Asset Group 级素材实验，赢了再全量。
- 不要看 3 天数据就下结论（流量波动 ≤ 学习噪声）。

### 3.15 预算分配：tROAS 与预算的联动策略

**预算即隐式出价。** tROAS 决定"单次值不值得出价"，预算决定"总量上限"。
两者要一起看：

| 状态 | 含义 | 动作 |
|------|------|------|
| 预算 100% 花完 | 需求 > 供给, 出价被预算钳制 | 加预算 or 上移 tROAS |
| 预算花不完 | 出价过保守或量不足 | 降 tROAS 或补商品/拆层 |
| 学习期预算反复波动 | 学习混乱 | 稳定预算 2-3 周 |

**预算分配 Python：**

```python
def reallocate_budget(client, customer_id, layers):
    """按层分配日预算: layers = [(campaign_id, daily_budget_micros)]"""
    for cid, micros in layers:
        client.update_campaign(
            customer_id, cid,
            {"campaignBudget": {"amountMicros": micros}}
        )
    print("预算已按层更新")
```

**注意：** `explicitlyShared=false` 的预算才是系列独占预算，
共享预算会互相蚕食，拆分层时务必独立预算。

### 3.16 直播带货/秒杀场景的 PMax 配置

**场景特征：**
- 价格实时变（开播价/停播价），库存脉冲式。
- 转化集中在 2-4 小时直播窗口。
- 移动端为主，冲动型消费。

**配置要点：**
```
- sale_price_effective_date 只覆盖直播时段 → 平时恢复原价
- 直播前 1-2 小时预热, 预算上浮 30-50%
- 直播中转化高峰: 依靠 MAXIMIZE_CONVERSION_VALUE 而非固定 tROAS
- 直播后取消防疫禁售, 或把"直播专属价"移除, 防流量错配
- 设备定向: PMax 自动, 但对模板系特殊; 用素材和价格引导移动端
```

| 时间窗 | 动作 | 理由 |
|--------|------|------|
| 开播前 3-5 天 | 预热素材+预算试探 | 提前拿学习数据 |
| 开播前 1h | 预算上浮 30-50% | 覆盖瞬间流量高峰 |
| 直播期 | 不调出价(学习窗口) | 频繁改动毁学习 |
| 直播后 24h | 恢复常规 tROAS/预算 | 防价格错配 |

**CVR 量化基准（直播带货参考表）：**

| 类型 | 展示-CTR | CTR-CVR | 单访客价值 |
|------|---------|---------|------------|
| 直播解馋(秒杀价 39 元) | 1.5-2.5% | 8-15% | ¥25-45 |
| 常规电商券 | 0.8-1.5% | 2-5% | ¥5-12 |

### 3.17 API 批量业绩报告流水线（项目脚本化）

**职责分工建议：**
- `/scripts/google_ads_api.py` 提供底层封装的 `search / generate_report / mutate`
- 业务层新写 report runner, 拉"PMax 分层 + 单品 + 预算"三张表

```python
def daily_pipeline(client, customer_id) -> dict:
    """日常三表: 系列层 / 单品层 / 预算层。"""
    out = {}
    # 1) 系列层: 拉所有 PMax 的 ROAS 与预算使用
    q_campaign = f"""
        SELECT campaign.id, campaign.name, campaign_budget.amount_micros,
               metrics.cost_micros, metrics.conversions_value
        FROM campaign
        WHERE campaign.advertising_channel_sub_type =
              'PERFORMANCE_MAX_FOR_GOALS'
          AND segments.date DURING LAST_7_DAYS
    """
    out["campaign"] = client.search(customer_id, q_campaign).data
    # 2) 单品层: product 视图
    out["product"] = _fetch_product_summary(client, customer_id)
    # 3) 预算层: 预算顶满率
    out["budget"] = _budget_usage(client, customer_id)
    return out

def _budget_usage(client, customer_id):
    q = ("SELECT campaign_budget.id, campaign_budget.amount_micros, "
         "metrics.cost_micros FROM campaign "
         "WHERE segments.date DURING LAST_1_DAYS")
    rows = client.search(customer_id, q).data
    return [{
        "budget_day": int(b["amountMicros"])/1e6,
        "cost": int(r["metrics"]["costMicros"])/1e6,
        "usage": int(r["metrics"]["costMicros"])/int(b["amountMicros"]),
    } for r in rows for b in [r.get("campaignBudget",{})]]
```

**落地注意：** 单品层表要与 GMC 的 offer join，出"低质+烧钱"黑名单，
自动签发提醒给投放组（阈值: cost>¥500 且 ROAS<1.2 连续 2 周）。

### 3.18 多业务线（游戏/电商/App 增长）在 PMax-S 上的差异化

| 业务 | PMax-S 角色 | 关键动作 | 成功指标 |
|------|-------------|----------|----------|
| 游戏周边(手办/服饰) | 商品卡 + 联名素材爆款 | 联名款拆高 tROAS 层 | ROAS 3.0-4.5 |
| 电商 App 内购(订阅) | App 安装 PMax(非购物) | tCPA + 订阅 LTV | eCPA/订阅 |
| 品牌直播间 | 直播购物卡 | 直播时段高预算 | ROAS 直播 CVR |
| 3C 配件 | Shopping 主层 + 标准购物 | 详见 3.1 | ROAS 3.4 |
| 服饰 DTC | Shopping + Discovery 素材 | 变体组 + 品牌 | ROAS 3.5-5 |

**要点：** PMax 通用层（非购物 PMax）与 Shopping PMax 一起跑的账户，
必须靠 custom_label / feed 过滤把商品错开，否则同一商品会被两套
系列重复竞价（转嫁给自己）。

### 3.19 SKU 维度看板 Prompt 与解读要点

**落地页看板维度：**

```
报表 tab:
  ├── PMax-S 整体: ROAS / 预算使用 / 学习期状态
  ├── 分层明细: 每层 (tROAS 目标 vs 实际, CVR, CTR)
  ├── 商品 top 烧钱: offer_id, cost, roas<1, 连续天数
  ├── 商品 top 价值: offer_id, value, roas>3.5
  └── Feed 健康: approved 率, disapproved 数 (GMC 数据拉出)
```

**数据回路：** 每周五出榜 → 周一迁移标签 + 调 tROAS → 周四复查学习状态。
这样的节奏让"优化"变成一个可重复的闭环，而不是一次性动作。

---

## 四、常见问题与排查（24 个实战 Q&A）

### Q1：PMax for Shopping 的广告系列类型为什么有的叫 `PERFORMANCE_MAX_FOR_GOALS` 有的叫 `SHOPPING_GOALS`？

**答案：**
`PERFORMANCE_MAX_FOR_GOALS` 是通用 PMax，可选择含"购物/销售"目标；
`SHOPPING_GOALS` 是计划中被单独归档的购物目标子类型。
两者在面向电商时消费同一份 Merchant Center Feed，
只是在 UI 里选择目标路径不同。API 侧统一的判断口径是：
- `advertising_channel_type = SHOPPING`
- `advertising_channel_sub_type = PERFORMANCE_MAX_FOR_GOALS`
- 且存在消费商品 Feed 的 Asset Group 信号
用这个口径去查询最稳，不要依赖 UI 名称。

**排查：** 用 `list_campaigns` 带 filter 看每个 series 的子类型，
确认它确实在消费购物数据。

```python
resp = client.list_campaigns(
    CUSTOMER_ID,
    filter="advertising_channel_sub_type = 'PERFORMANCE_MAX_FOR_GOALS'"
)
```

### Q2：为什么商品在 Merchant Center 显示 approved，但 PMax 里没有流量？

**可能原因（按概率排序）：**
1. **落地页与 Feed 不一致**（link 跳转到 404 或缺货页）→ 商品信号被判无效。
2. **品类映射错误**导致系统把它归类到错误需求池。
3. **没有打 custom_label 或打了但 Asset Group 过滤器没配** → 商品没进任何 Asset Group。
4. **Feed Label / 国家语言不匹配**（fl: 与投放国家不一致）→ 在 Ads 侧不可用。
5. **预算被其它商品吃光**，该商品没机会出价。
6. 商品 `availability=out_of_stock` 但落地页在售 → 数据源信号不一致。

**排查步骤：**
```
1. GMC Diagnostics 检查商品状态 (approved?) → 是
2. 检查落地页可访问性 (curl -I link) → 200?
3. 检查 Asset Group 的 product filter 是否包含该商品
4. 检查 feedLabel/targetCountry 与广告国家是否一致
5. 用 shopping_performance_view 查该 offer_id 有无 impressions
```

### Q3：为什么我的 PMax ROAS 很低，但标准购物 ROAS 能到 4？

**分析：**
- PMax 是全渠道、全素材，很多时候在探索（Discover/YouTube/展示）的低意图流量，
  这些流量 ROAS 天然低于搜索购物。
- 标准购物主要吃高意图搜索，ROAS 虚高是"争气房里的孩子"。
- 若 PMax 明显偏低（比如不到标准的一半），检查：
  - 素材（Asset Group）质量差，导致泛渠道 CTR 极低。
  - 转化目标太少，学习期拉长，出价太飘。
  - 是否把"加购"也算成转化但价值设错了，稀释 tROAS。

**动作：** 不要直接用标准购物 ROAS 去设 PMax 的 tROAS，
应参考 **PMax 分层的真实历史 ROAS** 来定爬坡目标。

### Q4：PMax tROAS 目标设定了 400%，但实际只跑出 2.5，怎么办？

**根因排查：**
- 历史转化数据不足（<15 转化/周）→ 模型学不准，tROAS 形同虚设。
- `conversions_value` 回传金额不准（漏回传/错回传）→ tROAS 算错。
- 预算过小，出价被预算钳制，测不准。
- Feed 混乱导致无法理解商品，转化本身差。

**动作：**
```
1. 检查近 30 天转化量与价值回传。
2. 若转化 <15/周 → 合并转化目标或降 tROAS 到 200-250%。
3. 检查价值回传 (enhanced conversions / offline conv) 准确性。
4. 放宽预算上限 2-3 倍再观察 3-5 天。
5. 仍差 → 查 Feed 质量，别死磕出价。
```

### Q5：改了 tROAS 之后量突然暴跌，是学习期重置吗？

**答案：**
是。PMax 是事件驱动学习，改动出价（或预算/资产）会触发**学习期重置**，
模型重新校准通常需要 1-2 周。尤其是：
- tROAS 一次性上调过猛（>15-20%）最容易导致量骤减。
- 学习期中最忌讳频繁改动。

**缓解：**
```
- 每次 tROAS 调整幅度 ≤ 10-15%。
- 调整间隔 ≥ 3-7 天。
- 学习期不要动预算/资产/出价。
- 用 Experiment 先在试验系列验证再全量。
```

### Q6：为什么有的 SKU 一直烧钱但无转化？

**排查：**
```
1. 用 shopping_performance_view 按 offer_id 聚合, 找 cost 高 ROAS~0 的 SKU。
2. 检查该 SKU: Feed 价格/图片/标题是否正常。
3. 检查落地页: 是否 404/缺货/与 Feed 不符。
4. 检查该类目是否有政策/质量降级。
5. 考虑把该 SKU 打 label 迁移到低 tROAS 层或暂停该层。
```
这种 SKU 是"模型黑洞"，会持续消耗预算，必须用数据及早识别。

### Q7：价格、促销价、availability 到底该怎么配合才会让 PMax 学好？

**答案：**
- `price` 填原价，`sale_price` 填促销价 + `sale_price_effective_date` 有效期。
  让系统看到"原价→促销价"的价差信号，利于价格敏感竞价与转化反哺。
- `availability` 与落地页**严格同步**，缺货立即改 out_of_stock，
  避免"Feed 在售、落地页缺货"的高跳出低转化。
- 价格变动尽量走 sale_price 而不是直接改 price，减少对模型的扰动。

### Q8：多市场多国家（跨境）怎么用 Feed Label 隔离？

**答案：**
- 每个 `targetCountry` 建立独立 Feed（或 feed 表），
  币种、税率、shipping、语言都按国家配置。
- 用 `feedLabel` 区分，比如 `feedLabel=US`、`feedLabel=DE`。
- Ads 侧 PMax 的投放国家（campaign 的 targets）必须与 feed 的
  targetCountry/feedLabel 一致，否则商品在 Ads 侧 fl: 不可用。
- 汇率换算用 Feed 规则自动生成，避免手工错。

### Q9：我该把什么设置为转化目标才能让 PMax 学得更快？

**答案：**
- 必须有"价值型"转化（购买）作为主目标，tROAS 才成立。
- 若转化事件太少，可**合并辅助转化**（加入购物车、订阅、表单）
  作为补充学习信号，但报表口径要分开。
- 价值回传（revenue）务必真实准确，这是 tROAS 正确性的地基。
- 不要只设"点击"这类无价值事件，那会让 PMax 出价失锚。

### Q10：为什么 Asset Group 的文案写了也没多大变化？

**答案：**
PMax-S 的创意是"**Feed 商品卡 + 资产组宣传文案**"的动态拼装。
文案重要，但**主角是 Feed 标题**。很多操盘手把精力全投在 Asset Group 文案上，
收效甚微。正确顺序：
```
1. 先修 Feed (title/image/category/price) → 收益最大
2. 再配 Asset Group 基本文案与图片/视频 → 保证可出创意
3. 最后用素材实验(A/B) micro-optimize
```

### Q11：购物轮播里我的商品为什么排在别人后面？

**影响排名的因素：**
- 出价（tROAS 下的价值化出价）。
- 商品数据质量（标题相关性、图片质量、品类映射）。
- 转化历史与 Quality（类 Quality score）。
- 落地页体验（加载速度、稳定性）。

**动作：**
```
- 提高 title 与目标 query 的相关性。
- 用高对比白底高清首图。
- 提升落地页 CVR（加载、信任、运费透明度）。
- 必要时临时上调该层 tROAS（前提是历史支撑）。
```

### Q12：Diagnostics 显示 WARNING 但商品能投，要不要管？

**答案：**
要。WARNING 表示"数据质量问题"，现在能投，但：
- 会降低匹配质量与曝光机会。
- 可能升级为 DISAPPROVED。
- 影响 PMax 对商品的理解。
常见 WARNING：图片过糊、`sale_price_effective_date` 缺失、
`brand` 与落地页不一致、`availability` 空。

**动作：** 建立周度 WARNING 清理清单，逐条补全，别等它变拒。

### Q13：补充 Feed（Supplemental Feed）和主 Feed 优先级怎么控制？

**答案：**
- 补充 Feed 覆盖更新主 Feed 的同名字段，优先级通过 feed 的 `priority`
  字段控制（多个补充 Feed 时高优先级覆盖低）。
- 适用：只想补 shipping / sale_price / custom_label 而不想重建主 Feed。
- 注意：补充 Feed 的 join key 是 `targetCountry` + `feedLabel` + `item id`，
  主 Feed 里必须有对应 item 才能补上，孤儿 item 会被忽略。

### Q14：为什么用 API 建的 PMax 一直没量，UI 建的同配置却有？

**排查点：**
```
1. 校验 campaign 子类型: PERFORMANCE_MAX_FOR_GOALS + SHOPPING。
2. 校验 Asset Group 是否齐全 (至少 1 图/1 标题/1 描述)。
3. 校验是否有 product filter 把商品排除光了。
4. 校验 campaign_budget 是否共享/被其它系列占用。
5. 校验转化目标是否在账户级配置。
6. 校验 feed 与该账户的国家语言对齐。
```
API 建的 PMax 最容易漏的就是 **Asset Group 与 balance/label 过滤**，
导致"系列活着但什么都没投"。

### Q15：PMax 到底要不要配否定关键词？配了为什么没用？

**答案：**
- PMax 本身**不支持**人工否定关键词。
- 曾有过账户级或 Exclusions 机制，但对商品驱动的 PMax-S 影响有限。
- 想排除某类"不希望投的词"可以由 **Feed 侧**间接做：把不想要的品类/属性
  从 title 和 category 里弱化，或把它单独拆到限制预算的层。
- 结论：PMax 不需要也没法靠否定词，靠 Feed 与拆分控制方向。

### Q16：怎么判断一个 SKU 该从 PMax 阶段拆分出去？

**判断标准：**
```
连续 2 周: cost 占比前 20% 且 ROAS < 全账户均值的 60%
  → 打 label 迁到低 tROAS 层 (保量) 或暂停层 (止损)
连续 2 周: ROAS > 全账户均值的 180% 且量充足
  → 迁到高 tROAS 层, 追求更高回报
```
用 `shopping_performance_view` 周度出榜，做**低频（周）**迁移，
避免打标签过频触发学习重置。

### Q17：PMax 在 YouTube/Discover 上烧钱但没转化，能关掉这些渠道吗？

**答案：**
PMax 的渠道分配是**自动**的，你不能手动关闭某个渠道。
但可以通过素材与预算间接影响：
- 若视频素材缺失，Discover/YouTube 参与度低，天然少投。
- 若 ROAS 极差且集中在泛渠道，优先检查素材质量 + 落地页，
  而不是幻想能"只投搜索"。
- 大促/直播这种强需求期，Search 为主；非需期泛渠道比例会升高。
理解 PMax = "全渠道自适应"，若想要"只要搜索"，那更适合标准购物。

### Q18：为什么设置 tROAS 390% 和 400% 差别不大，但标准购物手动 CPC 设差异很大？

**答案：**
- tROAS 是**连续约束**，在预算充足、历史稳定的情况下，
  系统会尽量找到平衡点，差 10% 可能反映在量上有细微差别，
  但不会像手动 CPC 那样"差 0.1 就完全不同"。
- 手动 CPC 是硬编码，模型不兜底，差 0.1 会直接改变参与拍卖的竞争力。
- 结论：tROAS 调整要结合"预算是否顶满"来判断是否生效，
  预算顶满时 tROAS 上调 = 量减、ROAS 升；预算空时 tROAS 无效。

### Q19：Feed 里的 brand 和落地页不一致会怎样？

**答案：**
- 会触发 `BRAND_MISMATCH` 拒绝（DISAPPROVED），或降级匹配质量。
- PMax 无法把该商品与"正确的品牌搜索意图"对应，导致相关性差。
- 若你是代销/联盟，品牌要与授权一致；无授权就低调处理，别伪造。
- 修法：统一 Feed brand 与官网品牌声明，或走授权流程。

### Q20：补充 Feed 更新了价格，为什么半天没生效？

**答案：**
补充 Feed 的生效需要：
1. 补充 Feed 完成抓取（若它是文件型）。
2. 与主 Feed 按 targetCountry+feedLabel+item id join 成功。
3. 触发商品重新审核。
链路每一步都有延迟（尤其文件抓取 1 场为 12-24h）。
若你要**秒级**更新，应改用 Content API 直接改主 Feed，而非补充 Feed。

### Q21：PMax 的"优化分"到底代表什么，怎么提升？

**答案：**
`campaign.optimization_score`（0-1）反映"相对可实现的潜力达成度"，
与"是否合格"无关。它越高代表系统认为你的设置越接近最优配置。
提升手段：
```
- 补齐全材质素材 (图片/视频/标题/描述/业务名)
- 让预算接近但不超过目标 (别大额溢出)
- 转化目标清晰单一, 价值回传准确
- 关键词信号/受众信号充分
- 别频繁改设置
```
优化分不是 ROAS 本身，但低分往往伴随投放不佳，可作健康度参考。

### Q22：跨账户/多店铺怎么统一管理 PMax-S？

**答案：**
用 **MCC（经理账户）+ Content API 多 merchant**：
- 每个店铺独立 Ads 客户账户 + GMC merchant，独立链接。
- 用脚本按 MCC 下的 customer 列表批量拉 per-account 报表与优化分。
- Feed 用每店铺独立主 Feed + `feedLabel` 区分，避免串货。
- 预算、授权、素材统一在模板层管理，避免重复劳动。

### Q23：为什么明明加购很多但购买转化少，PMax ROAS 却看起来不差？

**答案：**
因为**加购与购买都是转化**，都计入了 `conversions_value`（若你把加购
也当作价值转化并配了价值）。若加了"加购=表 CT+$X"的价值，
会让 tROAS 的分子偏大、看起来 ROAS 不错，但线下实际购买少。
正确处理：**主价值转化只有"购买"**，加购/订阅作为"无价值辅助"或不计入
tROAS 的转化，否则出价会往"虚高价值"方向偏。

### Q24：怎么用脚本发现"烧钱无转化"的 SKU 并一键迁移分层？

**答案：**
用 product 视图定期扫描 + 批量改 Feed label：

```python
def flag_burning_skus(client, customer_id, weeks=2, cost_floor=500.0):
    """找连续多周 cost高 且 ROAS 低的 SKU。"""
    q = f"""
        SELECT shopping_performance_view.offer_id,
               metrics.cost_micros, metrics.conversions_value
        FROM shopping_performance_view
        WHERE segments.date DURING LAST_{weeks*7}_DAYS
    """
    resp = client.search(customer_id, q)
    if not resp.success:
        print("失败:", resp.error); return []
    agg = {}
    for row in resp.data.get("results", []):
        spv = row.get("shoppingPerformanceView", {})
        m = row.get("metrics", {})
        oid = spv.get("offerId")
        cost = int(m.get("costMicros", 0)) / 1e6
        val = float(m.get("conversionsValue", 0.0))
        a = agg.setdefault(oid, {"cost": 0.0, "val": 0.0})
        a["cost"] += cost; a["val"] += val
    return [o for o, a in agg.items()
            if a["cost"] >= cost_floor and a["cost"] > 0 and a["val"] / a["cost"] < 1.2]
```

把这个黑名单 SKU 的 `custom_label` 改为 `clearout`（低 tROAS 层），
再推送 GMC / Content API，即可"一键迁移"而不重设广告系列本身。


---

## 五、自测题

### 题 1：概念题
PMax for Shopping 相比标准购物，在"商品组控价"上有什么根本差异？
当你发现某个高毛利 SKU 在 PMax 里 ROAS 被拉低时，
你手上的三把"找回控制力"的钥匙分别是什么？

<details>
<summary>答案</summary>

PMax for Shopping **没有商品组级的人工竞价控制**，出价被收到系列层面，
由 TARGET_ROAS 在预算约束下最大化总转化价值。标准购物则有完整
商品组拆分 + 手动 CPC。

三把钥匙（对应本文方法论）：
1. **Feed 侧编码隔离**：用 `custom_label_0~4` 打业务标签（high_roas/mid/new/clearout），
   并通过 Asset Group 的 `productGroupsFilters` 按 CUSTOM_LABEL 过滤，
   让不同 PMax 只投对应商品段。
2. **按 ROAS/品类瀑布拆分**：高毛利、低毛利拆到不同 PMax，
   各自配不同的 tROAS（如 400% vs 200%）与预算。
3. **并行标准购物竞技场**：对极少数高价值商品用标准购物手动 CPC 精确控价，
   与 PMax 并行并观察蚕食，同时用其数据反哺拆分。

这套方法论的本质是：自动化吞掉 fine-grained 控制后，
必须在更高的抽象层（数据工程 / 架构工程 / 竞价工程）找回。
</details>

### 题 2：代码/API 题
请写出用项目里的 `GoogleAdsClient.search` 拉取"近 30 天单品级 ROAS 排行"
所需的关键 GAQL 字段（至少包含最核心的 5 个），
并说明为什么 `cost_micros` 要除以 1e6。

<details>
<summary>答案</summary>

核心 GAQL（product 级用 `shopping_performance_view`）：

```sql
SELECT
  shopping_performance_view.offer_id,
  shopping_performance_view.product_title,
  metrics.impressions,
  metrics.clicks,
  metrics.cost_micros,
  metrics.conversions,
  metrics.conversions_value
FROM shopping_performance_view
WHERE segments.date DURING LAST_30_DAYS
ORDER BY metrics.cost_micros DESC
```

最核心 5 个：`offer_id`（单品标识）、`product_title`、
`metrics.cost_micros`（花费，微元）、`metrics.conversions`（转化）、
`metrics.conversions_value`（转化价值）。

`cost_micros` 的单位是**微元（1/1,000,000 单位货币）**，
所以除以 1e6 才得到实际金额（如元/美元）。而 `conversions_value` 是
标准小数金额，两者单位不同，**必须先统一单位再算 ROAS**：
`ROAS = conversions_value / (cost_micros / 1e6)`。
否则会得到被放大百万倍的假 ROAS。
</details>

### 题 3：诊断题
用户在 GMC 里看到一个商品 DISAPPROVED，理由是"GTIN_INVALID"，
同时它在 PMax 里没有流量。请给出你从诊断到修复的完整步骤，
包括它与 PMax 流量丢失之间的因果链。

<details>
<summary>答案</summary>

诊断修复步骤：
1. 打开 GMC → Diagnostics → 定位该商品，确认拒绝码 `GTIN_INVALID`。
2. 核实该商品真实 GTIN（用 GS1 / 条码库），删除 Feed 里伪造或错误的 GTIN。
3. 若商品确实无条码，改为填 `mpn`+`brand`，或显式设 `identifier_exists=false`，
   并确保与落地页一致。
4. 修正后重新提交该商品（触发 GMC 抓取/Content API 推送）。
5. 等待重新审核（通常几小时到 24h），确认状态变 approved。

与 PMax 流量丢失的因果链：
```
商品 GTIN 非法 → GMC DISAPPROVED → 商品信号从 Feed 移除
   → PMax 无法把它作为商品参与竞价 → 该 SKU 零曝光零流量
```
关键点：**PMax-S 只投 approved 的 Feed 商品**。任何 DISAPPROVED
（含 GTIN/price/image/policy）都会直接切断该商品在 PMax 的流量，
即使广告系列其他部分正常。这是"GMC 卡住、Ads 没量"最常见的根因之一。
</details>

### 题 4：出价题
一个稳定期的 PMax 历史真实 ROAS 是 3.0，你想爬坡到 4.0。
请说明：第一天该设多少 tROAS？调整的幅度纪律是什么？
为什么"一步到位设 4.0"可能适得其反？

<details>
<summary>答案</summary>

- **第一步**：不要直接设 4.0。参考历史真实 ROAS 3.0，
  按"每档 +10-15%"爬坡，比如先设 3.3-3.5，观察 3-7 天。
- **幅度纪律**：
  - 单次调整不超过 10-15%。
  - 每次调完观察 ≥3-7 天再动下一档。
  - 学习期内不要同时动预算/资产/出价。
  - 确保预算充足（不要触顶），否则出价会被预算钳制、测不准。
- **为什么一步到位 4.0 会适得其反**：
  - 上调过猛会触发**学习期重置**，模型退一步，量可能骤降。
  - tROAS 过高 = 出价过于保守，会导致流量枯竭、学习事件不足。
  - 系统在预算约束下最大化总价值，过苛刻的目标反而让它在低效区震荡。
  结论：**渐进爬坡 + 数据支撑单档位调整**，才是稳定逼近 4.0 的正道。
</details>

### 题 5：案例题
一个 3C 配件独立站 3000 SKU，你想用 PMax 分层 + 标准购物并行。
请画出完整架构（分层标签、各层 tROAS、预算分配、标准购物角色），
并给出你决定各层 tROAS 的依据来源。

<details>
<summary>答案</summary>

架构沿用本文 3.1/3.3 的瀑布拆分：

```
全部 3000 SKU
   │ custom_label_0 分流
   ├─ high_roas (940)  → PMax-A, tROAS 400%, 日预算 ¥3000
   ├─ mid_volume(1560) → PMax-B, tROAS 300%, 日预算 ¥4200
   └─ new_stock (500)  → PMax-C, tROAS 220%, 日预算 ¥1200
标准购物 Diagnostics (3000) · 手动 CPC · 日预算 ¥900 (观察窗)
合计日预算 ¥9300
```

- **分层标签**：`custom_label_0 = high_roas / mid_volume / new_stock / clearout`，
  由 `shopping_performance_view` 的单品 ROAS 榜（按周）决定归属。
- **各层 tROAS 依据**：
  - 以**该层的真实历史 ROAS** 为基准（不是全账户均值），
    逐档 +10-15% 爬坡。
  - 参考毛利：高毛利层可设更高 tROAS。
  - 新品层用"潜力/冷启动"逻辑（tROAS 放宽保量）。
- **标准购物角色**：
  - **诊断观察窗**（≤20% 预算），拿到逐商品组真实 CTR/CVR 反哺 PMax 拆层。
  - 对极小部分高价值商品可手动 CPC 精确控价。
- **约束**：周度迁移、避免打标签过频重置学习；预算不触顶。
</details>

### 总结

本文从**架构 → 原理 → 实战 → 排查 → 自测**五层展开，
核心结论一句话：
> PMax for Shopping 的竞争力不在"做广告"，而在"**做 Feed + 做拆分 + 做出价**"。
> 把 Merchant Center 的货理清楚、用 custom_label 分层、按 ROAS 瀑布拆分、
> 用好 tROAS 渐进爬坡 + 标准购物并行诊断，才能在自动化时代保住利润。

**继续阅读：**
- Google Ads 官方 PMax 文档
- Google Merchant Center 数据源与 Diagnostics 文档
- Google Ads API v24 GAQL 参考（product/shopping_performance_view）
- 本库其他文档：`google-ads-architecture-deep.md`（整体架构）、
  `google-ads-display-video-shopping-app-deep.md`（泛类）、
  `google-ads-pmax-dark-matter-deep.md`（PMax 底层机制）

---

## 附录 A：GAQL / API 速查表

### A.1 常用 GAQL 片段

```sql
-- 1) 拉所有 PMax 系列（含子类型与优化分）
SELECT campaign.id, campaign.name, campaign.status,
       campaign.advertising_channel_type,
       campaign.advertising_channel_sub_type,
       campaign.optimization_score
FROM campaign
WHERE campaign.advertising_channel_sub_type = 'PERFORMANCE_MAX_FOR_GOALS'

-- 2) 单品级指标（Shopping 绩效视图）
SELECT shopping_performance_view.offer_id,
       shopping_performance_view.product_title,
       shopping_performance_view.merchant_id,
       shopping_performance_view.country,
       shopping_performance_view.language,
       metrics.impressions, metrics.clicks, metrics.cost_micros,
       metrics.conversions, metrics.conversions_value,
       metrics.ctr
FROM shopping_performance_view
WHERE segments.date DURING LAST_30_DAYS
  AND metrics.impressions > 0
ORDER BY metrics.cost_micros DESC

-- 3) 资产组（Asset Group）状态
SELECT asset_group.id, asset_group.name, asset_group.status,
       asset_group.campaign,
       metrics.impressions, metrics.clicks
FROM asset_group
WHERE asset_group.campaign =
  'customers/1234567890/campaigns/111'
  AND segments.date DURING LAST_14_DAYS

-- 4) 转化行为
SELECT conversion_action.id, conversion_action.name,
       conversion_action.type,
       conversion_action.status
FROM conversion_action

-- 5) 预算使用率
SELECT campaign_budget.id, campaign_budget.name,
       campaign_budget.amount_micros,
       metrics.cost_micros,
       metrics.impressions
FROM campaign_budget
WHERE segments.date DURING LAST_7_DAYS
```

### A.2 出价策略枚举速查

| 枚举值 | 用途 | 是否适用 PMax-S |
|--------|------|-----------------|
| `TARGET_ROAS` | 目标 ROAS | ✅ 默认 |
| `TARGET_CPA` | 目标每次转化成本 | ✅（无价值回传时） |
| `MAXIMIZE_CONVERSIONS` | 预算内最大化转化量 | ✅（学习期） |
| `MAXIMIZE_CONVERSION_VALUE` | 预算内最大化转化价值 | ✅（无 tROAS 时） |
| `MAXIMIZE_CLICKS` | 最大化点击 | ⚠️ 不推荐购物 |
| `TARGET_IMPRESSION_SHARE` | 目标展示份额 | ❌ 不适用 |

### A.3 资产类型枚举速查（Asset Group）

| 枚举 | 中文 | 说明 |
|------|------|------|
| `HEADLINE` | 短标题 | ≤ 30 字符, 多条 |
| `LONG_HEADLINE` | 长标题 | ≤ 90 字符 |
| `DESCRIPTION` | 描述 | ≤ 90 字符, 多条 |
| `BUSINESS_NAME` | 业务名称 | ≤ 25 字符 |
| `IMAGE` | 图片 | 首图/方图/横图 |
| `YOUTUBE_VIDEO` | 视频 | 横竖版 |
| `SITELINK` | 站点链接 | 引导多个页面 |
| `CALLOUT` | 促销信息/卖点 | 短语 |
| `CALL` | 电话 | 不常用 |
| `STRUCTURED_SNIPPET` | 结构化摘要 | 属性列表 |
| `PRICE` | 价格 | 价格卡片 |
| `LEAD_FORM` | 表单 | 线索收集 |

### A.4 端点速查

| 端点 | 方法 | 用途 |
|------|------|------|
| `POST customers/{id}:search` | POST | GAQL 查询（本库 `search`） |
| `POST customers/{id}:searchStream` | POST | 流式分页（大结果集） |
| `POST customers/{id}/campaigns:mutate` | POST | 系列批量增改 |
| `POST customers/{id}/adGroupCriteria:mutate` | POST | 关键词/条件批量（`create_keywords`） |
| `POST customers/{id}/conversionActions:mutate` | POST | 转化行为 |
| `PATCH customers/{id}/campaigns/{cid}` | PATCH | 单系列更新（`update_campaign`） |
| `GET customers/{id}/campaigns/{cid}` | GET | 单系列详情 |
| `DELETE customers/{id}/campaigns/{cid}` | DELETE | 删除系列 |

---

## 附录 B：Feed 字段完整速查（主 Feed + 补充 Feed）

### B.1 必填字段（主 Feed）

| 字段 | 示例 | 错误样例 |
|------|------|----------|
| `id` | `sku-001` | 空 / 含换行 |
| `title` | `Anker 10000mAh 磁吸充电宝` | 只有"充电宝" |
| `description` | `20W 快充，兼容 iPhone/Android` | 空 |
| `link` | `https://shop.example/p/1` | 404 链接 |
| `image_link` | `https://img.example/1.jpg` | 带水印图 |
| `price` | `19.99 USD` | `19.99`（缺币种） |
| `availability` | `in stock` | `available`（拼错） |
| `condition` | `new` | `全新`（要英文枚举） |

### B.2 建议字段（强烈建议）

| 字段 | 作用 | 缺失后果 |
|------|------|----------|
| `brand` | 品牌理解 | 匹配降级/拒 |
| `gtin` | 条码标识 | 数据质量降级 |
| `mpn` | 制造商编号 | 无 GTIN 时替代 |
| `google_product_category` | 标准品类 | 品类错配 |
| `product_type` | 内部类目 | 无法细分 |
| `sale_price` | 促销价 | 价格战劣势 |
| `shipping` | 运费 | 转化/政策问题 |
| `custom_label_0~4` | 业务标签 | 无法拆分分层 |

### B.3 补充 Feed 使用场景表

| 场景 | 主 Feed 不动 | 补充 Feed 覆盖 |
|------|--------------|----------------|
| 全站改运费 | ❌ 不动 | `shipping` 覆盖 |
| 大促价 | 原价保留 | `sale_price` + `effective_date` |
| 按国家差异化标题 | 基础标题 | `title` 覆盖 |
| 加 custom_label | 基础 | `custom_label_0` 覆盖 |

---

## 附录 C：术语表（Glossary）

| 术语 | 全称/含义 | 一句话解释 |
|------|-----------|------------|
| PMax | Performance Max | Google 全渠道自动化广告系列 |
| PMax-S | PMax for Shopping | 以商品 Feed 为驱动的 PMax |
| GMX | Google Merchant eXperience | Merchant Center 商品数据体验体系 |
| GMC | Google Merchant Center | 商品管理平台 |
| Feed | 商品数据源 | 结构化商品清单（TSV/XML/API） |
| Supplemental Feed | 补充 Feed | 覆盖主 Feed 字段的增量源 |
| feedLabel | Feed 标签 | 区分多 Feed 的标识 |
| targetCountry | 目标国家 | Feed 投放国家 |
| GAQL | Google Ads Query Language | Google Ads 报表查询语言 |
| tROAS | Target ROAS | 目标广告支出回报率 |
| Asset Group | 资产组 | PMax 的素材+信号单元 |
| Product Group | 商品组 | 标准购物的分组/出价单元 |
| custom_label | 自定义标签 | Feed 业务标签（拆分关键） |
| Diagnostics | 诊断 | GMC 商品健康检查 |
| DISAPPROVED | 被拒 | 商品不可投放 |
| WARNING | 警告 | 质量问题但可投 |
| offer_id | 商品 ID | Feed 的 id，单品聚合键 |
| micros | 微元 | 1/1,000,000 单位货币 |

---

## 附录 D：PMax for Shopping 上线/迭代检查清单

### D.1 上线前（Pre-launch）

```
□ GMC 账户与 Ads 账户已链接
□ Feed 全部 approved（Diagnostics 无 DISAPPROVED）
□ 必填字段 100% 覆盖, 建议字段 ≥90%
□ title 模板按分层生成, 前 30 字符含最强关键词
□ 首图合规（白底/无水印/≥1000px）
□ 转化目标: 购买（价值型）为主, 辅助事件明确
□ 出价: tROAS 基于历史真实 ROAS × 0.7-0.8 起步
□ 预算: 高于历史周均 1.5-2 倍, 独立预算不共享
□ Asset Group: 图片/标题/描述/业务名齐全
□ 素材 ≥3 套, 视频 ≥1 条
□ 学习期计划: 2-3 周内不动设置
```

### D.2 上线后周度（Weekly Ops）

```
□ 单品 ROAS 榜（product 视图）扫描烧钱 SKU
□ 分层标签迁移（high_roas/mid/new/clearout）
□ tROAS 微调（幅度 ≤10-15%, 间隔 ≥3-7 天）
□ 预算使用率检查（顶满→加量; 空转→降 tROAS）
□ GMC 新 DISAPPROVED 清单清零
□ 素材实验数据复核
```

### D.3 大促/季节性（Seasonal Ops）

```
□ 大促前 2-3 周: 预算上浮 30-50%, tROAS 临时下调 15-25%
□ 大促期间: 不频繁改设置, 保量
□ 大促后: 2 周内恢复常规 tROAS/预算
□ 换季: 清仓商品拆 clearout 层限量投放
□ 与标准购物并行: 观察窗数据反哺拆分
```

### D.4 自动化脚本清单（Python）

| 脚本 | 功能 | 调用方法 |
|------|------|----------|
| `fetch_product_metrics` | 单品指标聚合 | `client.search` |
| `validate_feed` | Feed 提交前自检 | 本地校验 |
| `check_learning_health` | 学习期健康检查 | `client.search` |
| `adjust_troas` | tROAS 微调 | `client.update_campaign` |
| `reallocate_budget` | 分层预算 | `client.update_campaign` |
| `flag_burning_skus` | 烧钱 SKU 识别 | `client.search` |
| `weekly_trend` | 周趋势 | `client.generate_report` |

---

## 附录 E：多业务场景速配表（游戏/电商/App/代理/品牌/直播）

| 业务 | 主系列 | 辅助系列 | 出价 | 核心指标 | 关键动作 |
|------|--------|----------|------|----------|----------|
| 游戏周边 | PMax-S 商品层 | 标准购物诊断 | tROAS 300% | ROAS/客单价 | 联名爆款拆高层 |
| 3C 配件 | PMax-S 三层 | 标准购物观察 | 400/300/220 | ROAS 3.4 | 标题模板+分层 |
| 服饰 DTC | PMax-S 品牌层 | 搜索品牌词 | tROAS 350% | CVR/eCPA | 变体组+品牌素材 |
| 电商 App | PMax App（非购物） | — | tCPA | eCPA/次留 | 深链+素材 |
| 直播带货 | PMax-S 直播层 | 购物轮播 | MAX_CONV_VALUE | 直播 ROAS | 直播窗预算上浮 |
| 跨境代理 | 每国家 PMax-S | 标准购物 | tROAS 250-350% | 分国 ROAS | feedLabel 隔离 |
| 品牌清仓 | PMax-S clearout | — | tROAS 160% | 库存周转 | 限量保本 |

---

## 结语

**这篇文档的完整度，等于你把它落地为自动化流水线的能力。**
核心复盘：

1. **PMax-S 的战场不在"广告"而在"Feed + 数据工程"**：
   title 模板、品类映射、custom_label、补充 Feed 是真正杠杆。
2. **拆分是找回控制力的唯一途径**：
   瀑布拆分 + 各层差异化 tROAS + 独立预算，替代被 PMax 拿走的商品组控价。
3. **tROAS 是约束不是开关**：
   渐进爬坡（+10-15%/次）、学习期纪律（≥2-3 周不动设置）、
   预算联动（顶满=出价被钳制）。
4. **诊断靠 product 视图 + GMC Diagnostics 双源交叉**：
   单品 ROAS 榜找烧钱 SKU，GMC 状态找被拒原因，
   两者 join 才能定位"GMC 卡住、Ads 没量"。
5. **自动化闭环**：周度出榜 → 迁移标签 → 调 tROAS → 复查学习，
   让优化变成一个可重复执行的流水线。

> 记住一句话：**PMax 是放大器，不是创造者。**
> 你的 Feed 有多健康，你的 ROAS 就有多高。
> 货不对板，预算只会放大亏损；货真价实，自动化才会放大利润。

（全文完）
