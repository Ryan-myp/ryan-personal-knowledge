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
