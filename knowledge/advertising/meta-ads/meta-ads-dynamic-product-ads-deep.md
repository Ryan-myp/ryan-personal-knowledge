# Meta 动态产品广告 (DPA) 完整深度实战：从 Catalog 到再营销漏斗

> **领域**: 广告投放 / Meta
> **深度**: ⭐⭐⭐⭐⭐ 实战级指南
> **标签**: meta-ads, dpa, dynamic-product-ads, catalog, product-sets, retargeting
> **更新时间**: 2026-08-14
> **类型**: 实战深度文档

---

## 一、核心概念与架构

### 1.1 DPA 是什么：一句话定义

**动态产品广告（Dynamic Product Ads, DPA）** 是 Meta 广告体系中以「目录商品为最小创意单元、以用户行为事件为触发信号、以实时商品数据为渲染素材」的自动化广告形态。它的核心逻辑可以概括为：

```
用户行为                           广告引擎                         用户看到
──────────                    ──────────────                  ─────────────
浏览某商品页面  ──Pixel/CAPI──▶  识别 content_ids              
加入购物车      ──Pixel/CAPI──▶  匹配 Catalog 商品            个性化商品卡片
发起结账  ──Pixel/CAPI──▶  命中 Product Set 筛选      ─────▶  (价格/图片/标题
完成购买  ──Pixel/CAPI──▶  组装动态创意                      实时取自 Feed)
```

与传统广告的根本区别在于：传统广告的「创意（creative）」是人写死的素材，而 DPA 的**创意是模板 + 运行时数据渲染出来的**。同一条 DPA 广告，对不同用户展示不同商品，甚至对同一用户不同时间展示不同商品（比如价格或库存变化后立即更新）。

### 1.2 DPA 在 Ryan 知识库中的位置

本文档是「Meta 广告深度系列」中的一份，聚焦 **DPA 完整落地**。与相邻文档的关系：

| 文档 | 覆盖范围 | 本文档的处理方式 |
|------|----------|------------------|
| `meta-ads-catalog-deep.md` | Catalog 商品目录通用（商品字段、Feeds、上传方式） | 基础一笔带过，只补充 DPA 相关的 Catalog 管理细节 |
| `meta-ads-marketing-api-deep.md` | Marketing API 认证、权限、版本、限流 | 直接引用其认证前提，不重复 |
| `meta-ads-objectives-creatives-deep.md` | 目标、创意格式通用 | 只展开 DPA 专属的动态创意部分 |
| `meta-ads-targeting-advantage-deep.md` | 受众定向、Advantage+ 定向 | 聚焦行为事件驱动再营销受众 |
| `meta-ads-advantage-plus-full-deep.md` | ASC（Advantage+ Shopping Campaign） | 单独一节对比 DPA 与 ASC 的差异与迁移 |
| **本文件** | **DPA 全链路：Catalog→Product Set→Rules→再营销→动态广告** | — |

### 1.3 DPA 全链路架构总览

```
                          ┌─────────────────────────────────────────────────────┐
                          │                  DPA 全链路数据流                      │
                          └─────────────────────────────────────────────────────┘

 ┌─────────────┐   ┌──────────────┐   ┌──────────────┐   ┌───────────────────┐
 │ 商品数据源    │──▶│  Catalog 目录  │──▶│ Product Set   │──▶│  广告系列/组/广告   │
 │ (Product    │   │ (商品池)       │   │ (规则筛选子集) │   │ (Campaign/AdSet/  │
 │  Feed)      │   │              │   │              │   │  Ad)              │
 │  TSV/CSV/   │   │ items 维度     │   │ conditions   │   │  objective=      │
 │  XML/API    │   │ 商品唯一性      │   │ field+       │   │  OUTCOME_SALES   │
 └──────┬──────┘   └──────┬───────┘   │  operator+    │   │  product_set_id   │
        │                │           │  value        │   └─────────┬─────────┘
        │ 上传/同步        │ 校验/审核   └──────┬───────┘             │
        ▼                ▼                  │                     ▼
 ┌──────────────┐   ┌──────────────┐         │           ┌───────────────────┐
 │ Feed 更新机制  │   │ 商品审核/状态   │         └──────────▶ │  动态创意模板       │
 │ 实时 API 批量  │   │ availability  │                     │  Carousel/         │
 │ 定时拉取       │   │ price 同步     │                     │  Collection/       │
 └──────────────┘   └──────────────┘                     │  Single Image      │
                                                         └──────────┬────────┘
                                                                   │
 ┌──────────────────────┐   ┌──────────────────────┐   ┌──────────▼──────────┐
 │ 网站行为 (Pixel)       │   │ 服务器事件 (CAPI/DAPI) │   │  广告引擎匹配逻辑      │
 │ ViewContent          │   │ Purchase             │   │ 1. 命中 content_ids  │
 │ AddToCart            │   │ AddToCart            │   │ 2. 商品在 Product    │
 │ InitiateCheckout     │──▶│ CustomEvent          │──▶│    Set 内            │
 │ Purchase             │   │ (去重/去重一致性)       │   │ 3. 组装创意+出价       │
 └──────────────────────┘   └──────────────────────┘   └─────────────────────┘
```

流程一句话：**商品从 Feed 进入 Catalog → 通过 Product Set 规则圈出可投子集 → 广告系列绑定 Product Set → 用户的 Pixel/CAPI 行为事件与 Catalog 商品 ID 匹配 → 引擎按受众与出价动态组装创意 → 用户看到与自己行为相关的商品。**

### 1.4 核心对象关系（实体模型）

```
Ad Account (广告账户)
├── Product Catalog (商品目录) 1..N
│   ├── Product / Item (商品条目) 1..N
│   │   ├── id (item_id, 唯一)
│   │   ├── retailer_id / external_id
│   │   ├── title / description / image_url
│   │   ├── price / sale_price / currency
│   │   ├── availability / condition
│   │   ├── brand / gtin / mpn / product_type
│   │   └── custom_label_0..4 / custom_number_0..4
│   ├── Product Set (商品集) 1..N
│   │   └── filter (条件规则表达式)
│   ├── Product Feed (数据源) 1..N
│   │   ├── API Upload (实时上传)
│   │   ├── File Upload (TSV/CSV 文件)
│   │   ├── Scheduled Fetch (定时 URL 拉取)
│   │   └── Partner Integration (Shopify 等)
│   └── Collection (商品合集) 1..N
│       └── Collection Card (合集卡片) 1..N
├── Campaign (广告系列) 1..N
│   ├── objective = OUTCOME_TRAFFIC / OUTCOME_SALES / OUTCOME_ENGAGEMENT
│   ├── special_ad_category
│   └── Ad Set (广告组) 1..N
│       ├── promotion: product_catalog_id / product_set_id / retailer_product_ids
│       ├── dynamic_creative 的开关
│       ├── Audience (受众定向) + 排除
│       └── Ad (广告) 1..N
│           └── creative: DPA 模板 (Carousel/Collection/Single Image/Video)
├── Pixel (网站像素)
│   └── Event (事件) 与 Catalog 绑定 (pixel 与 catalog 关联)
└── Conversion API (服务器事件)
    └── 与 Pixel 去重 (deduplication)
```

**绑定关系要点（这是最容易出错的地方）：**

| 绑定关系 | 通过什么字段 | 常见错误 |
|---------|-------------|---------|
| 事件 ↔ 商品 | `content_ids` + `content_type='product'` | 只发事件不传 content_ids，DPA 永远不生效 |
| 广告 ↔ Catalog | Ad 创建时 `product_catalog_id` | 忘了传，广告变成静态广告 |
| 广告 ↔ 商品子集 | Creative 中 `product_set_id` | 传错 Product Set，展示不符合预期的商品 |
| 广告 ↔ 指定商品 | `retailer_product_ids` | 需要精确指定时未覆盖 |
| Pixel ↔ Catalog | 数据源里绑定 Pixel 的 Catalog | 事件无法归因到目录 |

### 1.5 DPA 与静态广告、ASC 的本质差异

| 维度 | 静态广告 (Static Ad) | DPA (动态产品广告) | ASC (Advantage+ Shopping Campaign) |
|------|---------------------|-------------------|-----------------------------------|
| 创意来源 | 人工制作 | 模板 + Catalog 数据 | 模板 + Catalog 数据 |
| 商品选择 | 人工指定 | 引擎按事件/规则选择 | 引擎全自动（含商品选择优化） |
| 受众 | 手动定向/自定义受众 | 再营销 + 行为匹配 | 全自动（Advantage 受众） |
| 出价 | 手动/自动 | Lowest Cost / Target ROAS | Target ROAS / 全自动 |
| 版位 | 手动选 | 可手动或 Advantage+ | 全自动（Advantage+） |
| 创意多样性 | 手动制作 | 动态模板有限 | 自动重组素材 + 商品 |
| 数据结构 | 无 | **必须有 Catalog + Feed** | 必须有 Catalog + Feed |
| 适用阶段 | 品牌/测试 | 中大型商品库再营销/拓新 | 规模放量主力 |

**一句话选型**：有自建站 + 商品库规模 100+ → DPA 起步；已经从 DPA 跑通了模型并追求放量 → 迁移/并行 ASC。DPA 的输出（Catalog、Feed 运维、事件质量）是 ASC 的输入，二者不是替代关系而是衔接关系。

### 1.6 Catalog 基础一页速览（详细见 meta-ads-catalog-deep.md）

只列出 DPA 必需的骨架，不再展开（详见 `meta-ads-catalog-deep.md`）：

- **Catalog = 商品池**。一个 Business 下可建多个 Catalog；每个 Catalog 有自己的 `id`、国家（`country`）、货币（`currency`）。
- **商品 = Catalog 内单元**，字段分为必需字段（`id/title/image_url/price`）与大量可选字段（`availability/sale_price/brand/gtin/product_type/custom_label_0..4`…）。
- **同步方式**：API 实时 / 文件上传 / 定时 URL 拉取 / 合作伙伴自动同步（如 Shopify pack）。
- **审核**：新的 Catalog 与商品需要经过数据质量与政策审核，审核不通过 → 动态广告不可投放（详见本文件 4.5）。

下面进入第二部分，把每个环节拆到原理层。

---

## 二、深度原理解析

### 2.1 Catalog 管理的深度原理

#### 2.1.1 多产品源（Multi Data Source）的组织方式

一个 Catalog 下可以挂多个「产品源（Feed Source）」。同一商品可以在不同源中出现，系统以 **`id`（item id）作为合并键**：相同 `id` 的商品，后到的源请求会**覆盖**先到的（按更新时间戳，或按上传顺序，取决于来源类型）。

```
Catalog: "Ryan 官网全量目录" (country=US, currency=USD)
├── Source A: 官网每日全量 TSV (Scheduled Fetch, 每日 02:00)
│   └── items: 全部 8,432 个
├── Source B: 官网实时增量 API (API Upload)
│   └── items: 变价/库存变化的 200 个（高频覆盖）
└── Source C: 供应商直供 XML (Partner/爬取)
    └── items: 第三方白标商品的 1,200 个
```

**要点**：
- 各源之间 `id` 不得冲突；冲突时后覆盖先（注意顺序与幂等性）。
- 增量源的更新窗口必须比全量源「新」，否则增量会被全量覆盖回去。
- 每个源有独立的批量（batch）与处理状态，可在 Dashboard「商品数据源」逐源查看。

#### 2.1.2 item 维度的生命周期

一个 item（商品条目）在 Meta 侧的生命周期：

```
创建(上传成功) → 处理中(解析/校验) → 已收录(LIVE) → 已索引(可被检索/可投)
                    │                    │
                    │ 字段非法             │ 数据质量不达标
                    ▼                    ▼
               处理错误              拒绝投放 / 隐藏
                    │                    │
                    └──────▶ 修复字段后重新上传 ◀──────┘
                                    │
                                    ▼
                          (定期全量上传进入下一轮)
```

- `POST /{catalog_id}/products` 返回 `handles` 与 `validation_status`；需要轮询 `GET /{catalog_id}/batches/{batch_id}`（或 `meta_get_catalog_batch`）来看每条商品的最终状态。
- 商品的状态枚举（API 返回的 `status` 字段没细，可组合）：`ACTIVE / ARCHIVED / IN_REVIEW / DISAPPROVED / OFFLINE`（不同版本 API 表达略有差异，以 `product_count_hidden` / 审核 API 为准）。
- 商品若审核失败进入 `DISAPPROVED`，即使 Product Set 匹配也不会投放。

#### 2.1.3 Catalog 与 Pixel / 商店绑定

Catalog 必须与 **Pixel** 和 **店铺**（page，用于购物流程）绑定，动态广告才能建立「事件 → 商品」的归因链路：

```
POST /{catalog_id}
{
  "name": "Ryan 官网目录",
  "horizontal_catalog_id": ...,
  "country": "US",
  "currency": "USD",
  "destination": "websites",
  "product_label": ...
}
# 之后在 Business Manager 中为该 Catalog 关联 Pixel：
POST /{pixel_id}
{
  "catalog_id": "{catalog_id}"
}
```

关联之后，Pixel 事件里的 `content_ids` 才会被解释为**该 Catalog 中的商品**；否则事件归因缺失，再营销投放（见第 2.5 节）全部失效。

#### 2.1.4 多店铺多 Catalog 的组织模型

```
方案A：一店一 Catalog（推荐）
├── 店铺 A (ryan-store-us) → Catalog US (USD)
│   └── Feed_A.tsv（只含 store A 商品，id 前缀 A-）
├── 店铺 B (ryan-store-eu) → Catalog EU (EUR)
│   └── Feed_B.tsv（只含 store B 商品，id 前缀 B-）
└── 每个 Catalog 一个广告系列组，互不污染

方案B：多店一 Catalog（用 custom_label 切分）
├── Catalog 全量（含 A/B 店铺商品）
│   ├── Product Set：store = A
│   └── Product Set：store = B
└── 优点：一个 Catalog 统一审计；缺点：事件归因必须按店切 content_ids 前缀
```

实践中**商店/币种/system 不同 → 一个店铺一个族** 是最稳妥的：价格字段绑定货币；把两种货币的商品放一个 Catalog 会导致价格换算错误和投放失败。

#### 2.1.5 商品 ID 唯一性原理

Meta 的 `id` 是用来关联事件与商品的**唯一键**，规则：

- 同一个 Catalog 内，`id` 必须唯一；重复的 `id` 会丢弃/覆盖，导致库存、价格展示错乱。
- `id` 只能包含字母/数字/`-`/`_`，长度 ≤ 50（不同版本边界有差异，建议 40 以内）。
- `id` 一锤定音后**不要改**：改了 id 等于旧商品，事件与历史数据全部失效；改名只能更新其他字段。
- 站点内同一个 SPU 不同 SKU（颜色尺码）必须用**不同的 id**。

```
错误示范：
id=sku-001        (同一个 id)
id=sku-001        ← 两个不同商品共用 id → 后者覆盖前者，历史行为串台

正确示范：
id=sku-001-red-42  (红色 42 码)
id=sku-001-blue-42 (蓝色 42 码)
```

### 2.2 item 维度深度：变体、多图、自定义字段

#### 2.2.1 变体（Variant）的三级模型

```
Product Group（逻辑商品，可跨变体）
├── item variant 1: 颜色=Black, 尺码=42 → id=SKU-001-BK-42
├── item variant 2: 颜色=Black, 尺码=43 → id=SKU-001-BK-43
└── item variant 3: 颜色=White, 尺码=42 → id=SKU-001-WH-42
```

- 变体之间通过 `item_group_id` 归组；同一组在展示时系统会优先展示与用户启发一致的变体（例如用户看过黑色尺码 42，就给他展示同组黑色）。
- 变体的 `image_url` 必须带上**各自的颜色图**，否则投放会回退到第一张主图。
- 变体数量过多（如 1000+ 尺码）会导致 catalog 体积膨胀，建议只对「有独立视觉/库存/价格」的维度建变体。

#### 2.2.2 字段全集（DPA 用到为重点）

| 字段 | 类型 | DPA 中作用 | 优先级 |
|------|------|-----------|--------|
| `id` | string | 唯一键，事件匹配 | **必需** |
| `title` | string | 广告标题素材 | **必需** |
| `image_url` | string | 卡片主图 | **必需** |
| `price` | string | 显示价格 | **必需** |
| `currency` | string | 货币 | **必需**（随价格） |
| `availability` | enum | 决定是否可投 | 高 |
| `sale_price` | string | 促销价（与 `price` 配合划线价） | 高 |
| `sale_price_effective_date` | string | 促销有效期 | 中 |
| `brand` | string | 标题/搜索匹配 | 高 |
| `gtin` | string | 全球贸易代码（政策与审核加分） | 高 |
| `mpn` | string | 制造商编号 | 中 |
| `product_type` | string | 层级分类，可写 `A > B > C` | 中 |
| `category` | string | 归类的类目（审核用） | 中 |
| `custom_label_0..4` | string | 规则引擎常用，如季节/利润率/新品 | 高 |
| `custom_number_0..4` | number | 数值型自定义（如利润额） | 中 |
| `color`/`size`/`gender`/`age_group` | string | 变体维度 | 中 |
| `description` | string | 卡片说明文案 | 中 |
| `retailer_product_ids` 相关字段 | string[] | 手工指定投商品的映射 | 中 |

#### 2.2.3 促销：`price` vs `sale_price` 展示优先级

```
引擎渲染优先级：
sale_price 有效（且在 effective_date 内） ──▶ 展示 sale_price（并显示划线价 price）
sale_price 无效/过期                     ──▶ 展示 price
两者都没有                              ──▶ 该 item 报错（无法投放）
```

**踩坑**：只传 `sale_price` 不传 `price`，或者 `sale_effective_date` 提前过期导致回退为原价，都会造成「为什么广告显示的价格和站内不一致」的客诉。价格同步是 DPA 的老大难，见 4.2。

### 2.3 Product Feed 格式规范（TSV / CSV / XML）

#### 2.3.1 三种格式与选择策略

| 格式 | 结构 | 适用 | 注意 |
|------|------|------|------|
| **TSV** | 第一行为表头，`\t` 分隔 | 文件上传 / 定时拉取（最常用） | 字段内不能有 tab；换行需转义 |
| **CSV** | 逗号分隔，`"` 转义 | 与第三方工具互通 | 逗号转义易错，测试 CSV 请先验证 |
| **XML** | `<item>` 条目 | Shopify 等导出 / 高级字段 | 体积大，解析慢 |

#### 2.3.2 TSV 表头规范（必需字段 + 常用可选）

```
id  title   description     image_link  link  price   currency  availability  condition  brand  gtin  mpn  product_type  custom_label_0  custom_label_1  sale_price  google_product_category  color  size  gender  age_group
```

Field 名小写；`image_url` 在较新版本字段名是 `image_url`（早期是 `image_link`）——**以 Meta 文档当前版为准，本文示例两种都会出现但统一用 `image_url`**（旧文档/旧 SDK 里两者都接受过）。

#### 2.3.3 TSV 示例（真实可跑）

```
id	title	description	image_url	link	price	currency	availability	condition	brand	product_type	gtin	custom_label_0
RYAN-001	Ryan Brand Classic Tee Navy	100% 精梳棉，圆领基础款	https://static.ryan.com/img/RYAN-001.jpg	https://www.ryan.com/products/RYAN-001	19.99	USD	in stock	new	Ryan Original	Apparel > T-Shirts	0694241234567	summer
RYAN-002	Ryan Brand Sweatshirt Grey	加绒卫衣，男女同款	https://static.ryan.com/img/RYAN-002.jpg	https://www.ryan.com/products/RYAN-002	39.99	USD	in stock	new	Ryan Original	Apparel > Hoodies	0694241234568	winter
RYAN-003	Ryan Camo Cap	军绿迷彩鸭舌帽	https://static.ryan.com/img/RYAN-003.jpg	https://www.ryan.com/products/RYAN-003	19.99	USD	out of stock	new	Ryan Original	Accessories > Hats	0694241234569	spring
```

**TSV 注意事项**：
- 表头第一行必须包含 `id`、`title`、`image_url`、`price` 等（缺必填字段 → 整行）。header 中名称大小写敏感。
- 数值字段如 `price` 必须带货币代码 `"19.99 USD"`（两段式）；不带的会解析失败。
- 文件编码 UTF-8（无 BOM），换行 `\n`。
- 每行产品数量上限按源配置（文件上传批量大不限制，但 curl 注入请分批）。
- `availability` 枚举：`in stock` / `out of stock` / `preorder` / `backordered` / `discontinued`。

#### 2.3.4 XML 示例（摘要）

```xml
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:g="http://base.google.com/ns/1.0">
  <channel>
    <title>Ryan 产品源</title>
    <link>https://www.ryan.com</link>
    <description>全量商品源</description>
    <item>
      <g:id>RYAN-3012</g:id>
      <g:title>Ryan Ceramic Mug 300ml</g:title>
      <g:description>双色陶瓷马克杯，可进微波炉洗碗机</g:description>
      <g:link>https://www.ryan.com/products/RYAN-3012</g:link>
      <g:image_link>https://cdn.ryan.com/img/RYAN-3012.jpg</g:image_link>
      <g:price>12.99 USD</g:price>
      <g:availability>in stock</g:availability>
      <g:brand>Ryan Original</g:brand>
      <g:product_type>Home > Kitchen</g:product_type>
      <g:custom_label_0>hot</g:custom_label_0>
    </item>
  </channel>
</rss>
```

#### 2.3.5 上传方式对比与频率建议

| 更新方式 | 频率上限 | 适合场景 | 注意 |
|---------|---------|---------|------|
| API Upload（实时） | 秒级 | 价格/库存实时变更 | 单次请求量限制，要有批量+重试 |
| File Upload（TSV 文件） | 手动 | 一次性全量/周更 | 文件大小限制（通常 1GB 上限） |
| Scheduled Fetch | 定时爬取 URL | 每日/每小时 | URL 需稳定；403 会失败 |
| Partner（Shopify 插件） | 自动 | 小型站点 | 字段覆盖不全 |

**通用更新策略**（生产建议，在 3.3 展开）：

```
快速变化字段（价格/库存）→ 实时 API 增量，10-30 分钟一个周期
中速变化字段（标题/描述/图） → 每 4-8 小时全量 API 或文件
低频变化字段（新品/上下架）  → 每日全量 Scheduled Fetch
```

### 2.4 Product Set 与 Rules（规则引擎深入）

#### 2.4.1 什么是 Product Set

Product Set 是 **Catalog 的子集 + 投放单位**。它在 DPA 中的三件事：

1. 决定广告能投哪些商品（引擎从 Product Set 内挑）；
2. 决定商品集的规模（影响学习速度 & 匹配率）；
3. 决定你的测试维度（按品牌/新品/促销拆多个 Set 量化控制）。

#### 2.4.2 规则语法（conditions / filter）

Product Set 的 `filter` 是一个 JSON 表达式，支持：

- **字段访问**：`availability`、`price`（注意 price 是字符串，用数值操作需 `value` 传字符串）、`brand`、`gtin`、`product_type`、`custom_label_0..4`、`custom_number_0..4`、`age` 等。
- **操作符（operator）**：

| 操作符 | 含义 | 示例 |
|--------|------|------|
| `EQUALS` | 等于 | `{availability} EQUALS "in stock"` |
| `NOT_EQUALS` | 不等于 | `{brand} NOT_EQUALS "Ryan Original"` |
| `GREATER_THAN` | 大于 | `{price} GREATER_THAN 20` |
| `GREATER_THAN_OR_EQUALS` | 大于等于 | `{custom_number_0} GREATER_THAN_OR_EQUALS 10` |
| `LESS_THAN` | 小于 | `{price} LESS_THAN 50` |
| `LESS_THAN_OR_EQUALS` | 小于等于 | `{price} LESS_THAN_OR_EQUALS 199` |
| `IN` | 在列表中 | `{size} IN ["M", "L"]` |
| `NOT_IN` | 不在列表中 | `{brand} NOT_IN ["X", "Y"]` |
| `CONTAINS` | 包含 | `{product_type} CONTAINS "Shoes"` |
| `STARTS_WITH` | 开头 | `{id} STARTS_WITH "RYAN-"` |
| `EXISTS` / `NOT_EXISTS` | 字段存在判断 | `{sale_price} EXISTS` |
| `IS` (针对布尔)  | 真值 | `{available} EQUALS true` |

- **逻辑组合**：
  - 同层多个条件 = **AND**；
  - 用 内层嵌套数组实现 **OR**；
  - `max_price` / `min_price` 是便捷字段（把价格条件与可用性合并）。

**完整 filter JSON 示例**：

```json
{
  "conditions": [
    {
      "field": "availability",
      "operator": "EQUALS",
      "value": "in stock"
    },
    {
      "field": "sale_price",
      "operator": "EXISTS"
    },
    {
      "field": "price",
      "operator": "LESS_THAN_OR_EQUALS",
      "value": 199.99
    },
    {
      "field": "custom_label_0",
      "operator": "IN",
      "value": ["summer", "hot"]
    }
  ]
}
```

等效于: `availability=in stock AND exists(sale_price) AND price ≤ 199.99 AND custom_label_0 ∈ {summer, hot}`。

**OR 示例**：条件数组内的 `OR` 通过把多个子条件放到同一数组的 `"or"` 组实现（部分端点直接支持顶层 `"or": [...]`）：

```json
{
  "or": [
    {
      "field": "brand",
      "operator": "EQUALS",
      "value": "Ryan Original"
    },
    {
      "field": "brand",
      "operator": "EQUALS",
      "value": "Ryan Kids"
    }
  ]
}
```

#### 2.4.3 字段与操作符的匹配矩阵（值得保存的表格）

| 字段 | EQUALS | NOT_EQUALS | IN | GREATER_THAN | LESS_THAN | EXISTS | CONT根据 |
|------|--------|------------|----|-------------|-----------|--------|---------|
| availability | ✅ | ✅ | ✅ | ❌ | ❌ | ✅ | ✅(CONTAINS) |
| price | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| brand | ✅ | ✅ | ✅ | ❌ | ❌ | ✅ | ✅ |
| gtin | ✅ | ✅ | ✅ | ❌ | ❌ | ✅ | ✅ |
| product_type | ✅ | ✅ | ✅ | ❌ | ❌ | ✅ | ✅ |
| custom_label_n | ✅ | ✅ | ✅ | ❌ | ❌ | ✅ | ✅ |
| custom_number_n | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ |
| id | ✅ | ✅ | ✅ | ❌ | ❌ | ✅ | ✅ |
| color/size | ✅ | ✅ | ✅ | ❌ | ❌ | ✅ | ✅ |

> 数值比较注意：`price` 是字符串格式（`"19.99 USD"`），规则引擎自动解析数值比较（传 `99` 即可），但**字符串比较的坑**：`price EQUALS 99` 只有当格式完全一致才命中，推荐用范围或 `LESS_THAN`。

#### 2.4.4 规则评估机制（什么时候“商品集”结算）

- Product Set 不是「实时查询」，而是 **Meta 后台按 Feed 更新的节奏重新扫描** 计算的集合。这意味着**Feed 更新后，Product Set 的商品量会先落库再更新**（通常几分钟到几小时）。
- `GET /{product_set_id}/products`（或 Panel「查看商品集」）能看当前商品数；**如果刚更新完 Feed，应立即轮询等商品数正确再开广告**，否则会出现「Product Set 空结果」或「背投旧集」。
- Product Set 可以**手动（Manual）**：Meta 只支持规则生成；但你可以「生成后再覆盖为指定商品」的情况用 `retailer_product_ids` 返回接口处理（API 层面的动态集主要是规则模式）。

#### 2.4.5 规则相关的实用概念

| 概念 | 说明 |
|------|------|
| `product_set_id` | 全局唯一 ID，广告创建时必填 |
| 默认 Set | Catalog 里自带的「全部商品」（`*`），用 `id` 规避手写 |
| `retailer_product_ids` 优先级 | 比 Product Set 更高：显式指定的商品优先投 |
| Set 大小建议 | ≥ 100 商品（学习期）；< 50 商品需注意学习期难收敛 |
| 空集 | `0 products` → 广告组直接不能投放（详情见 4.4） |

### 2.5 事件驱动再营销原理（Pixel / CAPI 与 DPA 的关系）

DPA 的「再营销」不是关键词定向，而是**事件驱动的商品级再定向**。理解下面这张图是 DPA 的核心：

```
                              用户行为（网站/App/站外）
                                      │
              ┌───────────────────────┼───────────────────────────────┐
              ▼                       ▼                               ▼
     ViewContent                AddToCart / InitiateCheckout      Purchase
     (浏览)  ──────────────┐    (加购 / 开始结算) ──────┐      (成交) ───────┐
              │            │            │              │            │
              │  content_ids=[SKU-1]    │ content_ids=[SKU-2]      │ content_ids=[SKU-3]
              ▼            ▼            ▼              ▼            ▼
        Pixel (浏览器)             Pixel + CAPI (双源去重)        Pixel (转化优化)
              │                        │                       │
              │                        │                       │
              ▼                        ▼                       ▼
        ┌─────────────────────────────────────────────────────────────┐
        │              事件落地到关联的 Catalog / 归因模型               │
        └─────────────────────────────────────────────────────────────┘
                         │
                         ▼
             广告引擎按目标:
        ┌─────────────┐   ┌───────────────────┐   ┌──────────────────┐
        │ Retargeting │   │ 行为相似(LSLA)      │   │ 补充推荐          │
        │ 浏览过 SKU-1 的人 │   │ 与购买者相似的受众     │   │ 看了鞋看背包        │
        └─────────────┘   └───────────────────┘   └──────────────────┘
```

#### 2.5.1 标准事件与参数

Meta 标准事件（与 DPA 相关的）：

| 事件 | 触发时机 | 关键参数 | DPA 用途 |
|------|---------|---------|---------|
| `PageView` | 任意页 | 无 | 基准 |
| `ViewContent` | 看商品详情 | `content_ids`、`content_type`（`product`）、`content_name`、`value`、`currency` | 浏览再营销 |
| `AddToCart` | 加购物车 | `content_ids`、`value` | 加购再营销 |
| `InitiateCheckout` | 开始结账 | `content_ids`、`value` | 结算再营销（长时窗出价高） |
| `Purchase` | 支付成功 | `content_ids`（订单商品）、`value`、`currency` | 转化/排除（不要投已购） |
| `Search`（可选） | 搜索 | `search_string` | 关键词定向补充 |

**参数必传规范**：

```js
fbq('track', 'ViewContent', {
  content_type: 'product',
  content_ids: ['RYAN-001'],               // 重要！商品 id，与 Catalog 的 id 一致
  content_name: 'Ryan Brand Tee',
  value: 19.99,
  currency: 'USD'
});
```

#### 2.5.2 从「事件 → 广告引擎选品」的完整机制（重点）

1. 用户产生事件 → Pixel/CAPI 上报 `content_ids`；
2. 事件与 **当前 Catalog**（通过 Pixel 与 Catalog 绑定）关联；
3. 引擎把该用户标记为「与商品 X 有交互」；
4. 广告请求时引擎在该用户的长期行为记忆池中取商品候选：
   - 命中 Product Set 的商品 → 优先；
   - 有行为信号 → 再重定向媒体；
   - 有交易信号 → 排序加权；
5. 组装创意（模板 + 商品字段）并竞价（出价由 Campaign 优化目标决定）；
6. 呈现。

```
广告请求发到引擎的选品阶段（伪逻辑）：

if 用户有 {ViewContent/AddToCart/InitiateCheckout 记录的 content_ids}:
    候选 = 该用户命中过的商品（去重视图靠后）
else:
    候选 = Catalog 内最近热门 / 随机（用于冷启动）
候选 = 候选 ∩ Product Set（在规则集合内）
if 候选为空:
    回退 = 默认集合或放弃本次展示
```

**为什么事件缺失导致无法再营销**：没有 `content_ids` → 引擎无可匹配 → 即使受众里包含这个人，也没有商品给他展示 → 广告空置（`products` 缺失、impression 为 0，见 4.8）。

#### 2.5.3 Pixel 与 CAPI（DAPI）双通道与去重

- Pixel = 浏览器端，CAPI = 服务器端。两者并行上报（同一个 `eventid` / `event_id` 做去重主键）。
- **去重键**：`event_id`（事件唯一 ID）+ `event_time`。发送 CAPI 与 Pixel 时用同一个 `event_id`，Meta 自动去重（`Event Dedup` 参数决策在去重面板可见）。
- 共享 `client_user_agent` / `action_source`（`website`）。
- 事件数量的差异会直接影响 DPA 的匹配规模与学习速度，参见 4.8。

#### 2.5.4 基础事件质量上报（浅显）与 DPA 的学习期

- 学习期：广告组积累 ~50 次转化/周（目标优化）才退出学习期。
- DPA 加速学习：保证 Product Set 规模 + 事件密度；学习期不足遵守。
- 尤其是「加购 → 购买」链路，需要完整事件回传（例如 iOS ATT 授权率低 → 需 CAPI 兜底）。

### 2.6 动态创意与模板（DPA 的渲染原理）

#### 2.6.1 创意组成

DPA 的 creative 结构：

```
创意 (creative)
├── 模板层 (dynamic): 位置 placeholder
│   ├── {title} / {description} / {price}
│   ├── {image}  (来自 item.image_url)
│   └── {link}   (来自 item.link / 你传的 URL 模板)
├── 静态层：品牌标识、CTA、主标题、封底图
└── 素材策略：多套模板（轮播/大图/集合）
```

#### 2.6.2 三种主流 DPA 创意格式

| 格式 | 结构 | 适合 | 注意 |
|------|------|------|------|
| **Carousel** | 横滑多卡片（每卡一件商品） | 主推跨品类、变体多 | 卡片数建议 2-10 |
| **Collection** | 封面大图 + 下方网格（多商品） | 品类场景、促销 | 需搭配 `Collection` 资源，封面图自动生成的规则 |
| **Single Image** | 单张商品图 | 极简/移动端 | 图片字段利用率高 |

**Carousel 参数**（动态）：

```
+ 每张卡片：
+  ├─ image（item.image_url）
+  ├─ title（item.title）
+  ├─ price / sale_price（自动）
+  └─ CTA（如 Shop Now）
```

**Collection**：需要先建 `Collection`（合集）+ `Collection Card`（卡片）：

```
Collection 示例 "夏季新品"
├── 封面: 自动选品类图 或 上传图
├── 网格: 8-12 个商品（由规则/手动选择）
└── 落地页: Shop Now 链接到合集页
```

相关的 API（见 3.x）：
- `POST /{catalog_id}/collections`（创建合集）
- `POST /{collection_id}/cards`（创建卡片）
- 广告 creative 中引用 `collection_id`。

#### 2.6.3 动态文案（dynamic_voice）

`dynamic_creative` 支持文案动态：
- `title` 可禁用固定文本、用商品标题映射表（覆盖文案规则 `{title}`）；
- 描述用商品 `description` 截断渲染；
- CTA 按钮文案可选 `dynamic_voice`（"了解详情/立即购买"）。
- 落地页 URL 可用 `{catalog_url}` 或商品的 `link` 字段（`link` 出落地页、`image_url` 出图片）。

### 2.7 多目录聚合（Catalog Aggregation）

#### 2.7.1 场景与概念

多 Catalog（比如多个店铺/多币种）不能直接合并成一个广告。Meta 提供：

- **Catalog Aggregation**（目录聚合）：将多个 Catalog 聚合成一个「父目录」，子目录分别维护 Feed，广告绑定父目录即可跨子目录投放。
- 聚合条件：**所有子目录必须同名同币种同国家**（否则报错）。

```
Catalog A (USD, US, 店铺A) ─┐
Catalog B (USD, US, 店铺B) ─┼──▶ Aggregated Catalog (USD, US)
Catalog C (USD, US, 店铺C) ─┘          │
                                      ▼
                           DPA 广告绑定聚合目录 + Product Set(聚合)
```

- 事件归因：`content_ids` 的 id 空间合并即可（id 中数量必须唯一）。
- Aggregated Catalog 的 Product Set 也可以按 `custom_label` 蒸馏子集（例如按店铺用 `custom_label_1=store_a`）。

#### 2.7.2 聚合限制

- 聚合 Cap：一个聚合目录最多挂若干个 Catalog（官方限制约 36 个子目录，以文档为准）。
- 聚合后不能单独对子目录开广告差异化，差异只能靠 Product Set 规则。
- 各子目录同币同国 →** 严格点验证**，否则聚合创建失败并抛出 `domain_check` 错误。

### 2.8 再营销漏斗与受众分层（Retargeting 全解）

#### 2.8.1 漏斗设计

```
                  ┌────────────────────────────────────────────┐
                  │         DPA 再营销漏斗（示例）                  │
                  └────────────────────────────────────────────┘

 漏斗层           受众                                                    目标/出价
 ─────────────  ─────────────────────────────────────────────  ─────────────
 L1 浏览者       浏览过内容未加购 (Pixel=ViewContent, 14天)          CPC 出价适中
 L2 加购者       加购未结账 (Pixel=AddToCart, 14天)                 CPA 出价×1.2
 L3 放弃结算     InitiateCheckout 未购买 (30天)                   CPA 出价×1.5
 L4 已购用户     已购买 (365天) → 排除 / 交叉销售另投              转化目标+排除
 L5 新客        未发生过任何事件的用户（通过排除获得）               拓新/放量
```

#### 2.8.2 受众技术实现（自定义受众）

方式一：基于 Pixel 事件的自定义受众（`behavioral` 类型），如：

- 浏览：` event=ViewContent 且 30 天内 >= 1 次`
- 加购：` AddToCart 7 天`
- 结账：` InitiateCheckout 30 天`
- 购买：` Purchase 365 天`
- 定制：` 事件 = 任一内容相关 `

组合细节：
- `audience` 每个受众由 ` 规则= AND/OR 嵌套` 构造（在 Meta 编辑器里是可视化「事件 + 时间」），API 有 `metadata` 参数（删除会小心，id 只做组）。

#### 2.8.3 DPA 的「缺失再营销」问题（重灾区）

**典型失败：我建了 30 天浏览受众，投放 0 展示。** 原因拆解：

1. **事件没发**：`ViewContent` 未在站点打点（尤其 SPA——路径变化不触发）→ 无内容可投。
2. **content_ids 没传**或与 Catalog `id` 不对应。
3. **受众确实为空**：站点本身无浏览。
4. **受众告警为空**但广告没跟着 Product Set 绑定（Product Set 匹配失败 → 广告停投）。

所以排查顺序永远是：**事件 → content_ids 一致性 → 受众规模 → Product Set 商品数**。

### 2.9 出价与优化的机制（DPA 的 Bid

#### 2.9.1 优化目标与出价

| 优化目标 | 出价方式 | DPA 的关注点 |
|---------|---------|-------------|
| `OUTCOME_SALES` / `PURCHASE` | Target ROAS / 最低成本（Highest volume） | 必须配合转化事件（Purchase）且有归因窗口 |
| `OUTCOME_TRAFFIC` / `LINK_CLICKS` | 每次点击出价 | 无转化数据时的过渡方案 |
| `OUTCOME_ENGAGEMENT` | 每互动出价 | 不太推荐用于 DPA |

#### 2.9.2 Target ROAS 经验

- 初始建议按历史 MER/整体 ROAS 的 60-80% 设阈值（保守起量）。
- 商品级差异化：`custom_number_n` 可做利润加权，不过 Target ROAS 的核心是转化数据。
- DPA 的「转化」默认统计 Attribution Setting（7 天点击 / 1 天浏览等），要去「转化归因」确认别漏。

### 2.10 DPA 与 ASC（Advantage+ Shopping Campaign）的底层差异（深化）

| 维度 | DPA | ASC（Advantage+） |
|------|-----|------------------|
| 商品范围 | 由 Product Set 界定 | 同一 Catalog，自动全部商品 |
| 定向 | 手动受众 / DPA 再营销受众 | 自动受众（Advantage audience），不可手动 |
| 创意 | 手动接模板（可加静态素材） | 系统自动组合（素材 + 商品） |
| 版位 | 可选择 | 全自动（Advantage+ placements） |
| 预算 | 常规 | 预算可设置 |
| 相似性 | 交流/可控 | 更「黑盒」，便于放量 |
| 场景 | 精细化漏斗（分层再营销） | 规模化交付/智能放量 |

**真实业务经验**：很多团队在 DPA 跑稳定后把预算搬给 ASC，DPA 只保留「高意向漏斗层」（加购 / 弃购），这是 **DPA + ASC 双轨** 的标准打法。两者可以用同一个 Catalog、同一套 Product Set 规则，但注意受众重叠：加购受众里 70%+ 被 ASC 抢先转化，DPA 就空转，需要频控 + 受众排除策略（详见 3.10）。
---

## 三、生产环境实战

### 3.0 环境准备与认证前提

本部分全部示例基于 `scripts/ad_platform_api.py`（`AdPlatformAPI` 封装类）与 Meta Graph API / Marketing API. 认证使用标准的 System User Token 或 User Token（参考 `meta-ads-marketing-api-deep.md` 的 OAuth 章节），本文不再展开。

```python
# scripts/ad_platform_api.py 的基础用法
from ad_platform_api import AdPlatformAPI

api = AdPlatformAPI(credentials_file="credentials.json")  # 内含 meta.access_token

AD_ACCOUNT_ID = "act_123456789"   # act_ 前缀
CATALOG_ID    = "123456789012"    # 目录 ID（数字）
```

> 权限：操作 Catalog / Product / Product Set / 广告对象需要以下权限（在 App 审核中申请）：`catalog_management`、`ads_management`、`business_management`、`ads_read`。没有这些权限会返回 `(#200) Permissions error`。

### 3.1 第一步：列出目录并确认目标 Catalog

```python
# 列出当前账户下所有目录
catalogs = api.meta_list_catalogs(AD_ACCOUNT_ID)
for c in catalogs:
    print(c["id"], c["name"])

# 期望输出类似：
# 123456789012  Ryan 官网全量目录
# 123456789013  Ryan 分销子目录
```

**Graph API 等价**：

```bash
curl -G "https://graph.facebook.com/v19.0/act_123456789/product_catalogs" \
  -H "Authorization: Bearer $META_TOKEN" \
  -d "fields=id,name,currency,country&limit=10"
```

**要点**：DPA 之前先确认：
1. 目录所在 **Business** 与你广告账户属于同一组织（否则广告账户无法直接引用该 Catalog）；
2. 目录的 **货币/国家** 与广告账户一致（不一致会导致商品货币报错）；
3. 目录里商品数 > 0 且审核通过（见 3.4）。

### 3.2 准备并上传 Product Feed

#### 3.2.1 生成本地 TSV（Python）

```python
import csv
import io

def build_tsv(products: list[dict]) -> str:
    """把商品 dict 列表转成 Meta TSV 文本。首行是表头。"""
    columns = [
        "id", "title", "description", "image_url", "link",
        "price", "currency", "availability", "condition",
        "brand", "gtin", "mpn", "product_type",
        "sale_price", "custom_label_0", "custom_label_1",
    ]
    buf = io.StringIO()
    w = csv.writer(buf, delimiter="\t", lineterminator="\n")
    w.writerow(columns)
    for p in products:
        w.writerow([
            p["id"], p["title"], p.get("description", ""),
            p["image_url"], p["link"],
            f'{p["price"]:.2f} {p["currency"]}',
            p["currency"], p["availability"], p.get("condition", "new"),
            p.get("brand", ""), p.get("gtin", ""), p.get("mpn", ""),
            p.get("product_type", ""),
            f'{p["sale_price"]:.2f} {p["currency"]}' if p.get("sale_price") else "",
            p.get("custom_label_0", ""), p.get("custom_label_1", ""),
        ])
    return buf.getvalue()

# 示例商品
products = [
    {
        "id": "RYAN-001", "title": "Ryan Brand Classic Tee Navy",
        "description": "100% 精梳棉圆领",
        "image_url": "https://static.ryan.com/img/RYAN-001.jpg",
        "link": "https://www.ryan.com/products/RYAN-001",
        "price": 19.99, "currency": "USD", "availability": "in stock",
        "brand": "Ryan Original", "product_type": "Apparel > T-Shirts",
        "sale_price": 15.99, "custom_label_0": "summer",
    },
]

tsv_text = build_tsv(products)
with open("feed_ryan.tsv", "w", encoding="utf-8") as f:
    f.write(tsv_text)
print(tsv_text)
```

输出：

```
id	title	description	image_url	link	price	currency	availability	condition	brand	gtin	mpn	product_type	sale_price	custom_label_0	custom_label_1
RYAN-001	Ryan Brand Classic Tee Navy	100% 精梳棉圆领	https://static.ryan.com/img/RYAN-001.jpg	https://www.ryan.com/products/RYAN-001	19.99 USD	USD	in stock	new	Ryan Original	\N	\N	Apparel > T-Shirts	15.99 USD	summer	
```

#### 3.2.2 通过 API 批量上传商品（批量/实时路径）

`meta_add_products` 上传商品：

```python
# 一次上传一个商品列表（或一个完整 Feed）
resp = api.meta_add_products(
    CATALOG_ID,
    items=[
        {
            "id": "RYAN-001",
            "title": "Ryan Brand Classic Tee Navy",
            "description": "100% 精梳棉圆领",
            "image_url": "https://static.ryan.com/img/RYAN-001.jpg",
            "link": "https://www.ryan.com/products/RYAN-001",
            "price": 19.99,
            "currency": "USD",
            "availability": "in stock",
            "condition": "new",
            "brand": "Ryan Original",
            "product_type": "Apparel > T-Shirts",
            "sale_price": 15.99,
            "sale_price_effective_date": "2026-08-01T00:00:00+00:00/2026-08-31T23:59:59+00:00",
            "custom_label_0": "summer",
            "visibility": "published",
        },
        {
            "id": "RYAN-002",
            "title": "Ryan Brand Sweatshirt Grey",
            "image_url": "https://static.ryan.com/img/RYAN-002.jpg",
            "link": "https://www.ryan.com/products/RYAN-002",
            "price": 39.99, "currency": "USD", "availability": "in stock",
            "condition": "new", "brand": "Ryan Original",
        },
    ],
    _schema="individual",
)
print(resp)
```

**同时可以指定 `schema=TSV` 直接传 feed 字符串**。常见做法是「文件上传」+「实时增量 API」双轨，见 3.2.5。

#### 3.2.3 用文件上传（Scheduled Fetch / File Upload）

如果你有稳定的 feed URL（例如 `https://cdn.ryan.com/feeds/feed.tsv`），创建定时拉取数据源：

```python
# 简化：创建 Feed 数据源（Scheduled Fetch）
feed = api.meta_create_feed(
    CATALOG_ID,
    name="Ryan 官网全量源",
    url="https://cdn.ryan.com/feeds/feed.tsv",
    schedule="EVERY_DAY",
    format="TSV",
    country="US",
    language="en",
)
feed_id = feed["id"]
print("feed_id", feed_id)
```

> 注意 `meta_create_feed` / `meta_refresh_feed` 在同一脚本里可能未直接暴露为方法名；实际 Graph API 端点如下，脚本需要时可直接扩展或改用 `api` 底层 requests。为保持示例可读，这里补充标准 curl。

```bash
# 创建定时拉取数据源（Graph API）
curl -X POST "https://graph.facebook.com/v19.0/$CATALOG_ID/feeds" \
  -H "Authorization: Bearer $META_TOKEN" \
  -d "name=Ryan+官网全量源" \
  -d "url=https%3A%2F%2Fcdn.ryan.com%2Ffeeds%2Ffeed.tsv" \
  -d "schedule=EVERY_DAY" \
  -d "format=TSV" \
  -d "country=US" \
  -d "language=en"

# 手动触发一次同步（刷数据源）
curl -X POST "https://graph.facebook.com/v19.0/$FEED_ID/refresh" \
  -H "Authorization: Bearer $META_TOKEN"
```

#### 3.2.4 轮询批量处理状态（batches）

上传是异步的，必须轮询 `batches` 才能知道商品是否成功收录：

```python
import time

def wait_batch_done(batch_id: str, timeout=600):
    """轮询 GET /{catalog_id}/batches/{batch_id} 直到终态。"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        batch = api.meta_get_catalog_batch(batch_id)
        status = batch.get("status", "PROCESSING")
        print(f"batch {batch_id} -> {status} "
              f"failed={batch.get('failed_items', 0)} "
              f"success={batch.get('succeeded_items', 0)}")
        if status in ("FINISHED", "COMPLETED", "FAILED", "ERROR"):
            return batch
        time.sleep(10)
    raise TimeoutError(f"batch {batch_id} 超时未完成")

# 列出最近批次
batches = api.meta_list_catalog_batches(CATALOG_ID)
print(batches)

# 对最新失败 batch 深入排查
latest = batches[0]
bad = api.meta_get_catalog_batch(latest["id"])
print("error_items", bad.get("errors", []))
```

#### 3.2.5 实时增量 vs 全量：双轨同步策略（踩坑沉淀）

```
场景：价格/库存高频变化（电商大促、闪购）
推荐：全量 Scheduled Fetch（每日 1 次）+ 实时 API 增量（每 10-30 分钟 1 次）
```

```python
def sync_price_incremental(catalog_id: str, price_updates: list[dict]):
    """把『只变了价格』的商品用小批量 API 推上去，避免全量消耗。"""
    for i in range(0, len(price_updates), 50):   # 建议分批
        chunk = price_updates[i:i+50]
        api.meta_add_products(
            catalog_id,
            items=[{"id": p["id"], "price": p["price"], "currency": "USD"}
                   for p in chunk],
        )
        time.sleep(1)  # 限流余量
```

**踩坑**：
- 增量更新会覆盖同名 `id` 的全量字段（只传 price 字段，其余字段不变才安全）。
- 若增量只传 `price`，它不会丢 image/title（Meta 合并语义按字段粒度），但若增量漏传了本来该有的字段可能导致字段被清空——**尽量在全量 Feed 每次都带全字段**。
- 大量变价瞬间（大促 0 点）请错峰：把增量请求分散到 30 分钟窗口，避免 API 限流（`(#4) Application request limit reached`）。

### 3.3 商品管理实战（增删改查 + 上下架）

#### 3.3.1 列出目录商品

```python
products = api.meta_list_catalog_products(
    CATALOG_ID,
    limit=10,
    fields=["id", "title", "price", "availability", "status"],
)
for p in products:
    print(p["id"], p["title"], p["price"], p["availability"], p.get("status"))
```

```bash
curl -G "https://graph.facebook.com/v19.0/$CATALOG_ID/products" \
  -H "Authorization: Bearer $META_TOKEN" \
  -d "fields=id,title,price,availability&limit=10"
```

#### 3.3.2 更新单个商品（改价 / 改库存 / 改图）

```python
# 更新商品（例如价格直接改成 17.99，库存改为 out of stock）
resp = api.meta_update_catalog_product(
    "RYAN-001",
    price=17.99,
    currency="USD",
    availability="out of stock",
)
print(resp)
```

由于 API 里 `meta_update_catalog_product` 是对 `product_id` 的更新，内部多走 `POST /{catalog_id}/products` 或 `POST /{product_id}`，这里给出底层等价：

```bash
# 方式一：整条替换（用 catalog 的 products 端点 + 完整 item）
curl -X POST "https://graph.facebook.com/v19.0/$CATALOG_ID/products" \
  -H "Authorization: Bearer $META_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "items": [{
      "id": "RYAN-001",
      "title": "Ryan Brand Classic Tee Navy",
      "image_url": "https://static.ryan.com/img/RYAN-001.jpg",
      "price": 17.99, "currency": "USD",
      "availability": "out of stock", "condition": "new",
      "brand": "Ryan Original"
    }],
    "schema": "individual"
  }'
```

#### 3.3.3 删除商品

```python
# 按 product id 删除
resp = api.meta_delete_catalog_product("RYAN-003")  # 下架某 SKU
print(resp)
```

```bash
# Graph：从 catalog 删除商品（按 id 数组）
curl -X POST "https://graph.facebook.com/v19.0/$CATALOG_ID/products" \
  -H "Authorization: Bearer $META_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"items": [{"id": "RYAN-003"}], "schema": "individual",
       "filter": {"availability": {"is_delisted": true}}}'
```

> 下架商品的推荐做法是**把 `availability` 改为 `out of stock` / `discontinued`，而不是删除**——删除会丢历史归因；`out of stock` 则既不下发到 DPA（不可投）又保留数据用于再营销学习。详见 4.3。

#### 3.3.4 商品可用性状态检查（投放前必检）

```python
def catalog_health(catalog_id: str):
    prods = api.meta_list_catalog_products(catalog_id, limit=100,
                                           fields=["id", "availability", "status"])
    in_stock = sum(1 for p in prods if p.get("availability") == "in stock")
    hidden   = sum(1 for p in prods if not p.get("status", "ACTIVE") == "ACTIVE")
    print(f"共 {len(prods)} 个（抽样）；in stock={in_stock}，非 ACTIVE/隐藏={hidden}")
    return {"total": len(prods), "in_stock": in_stock, "hidden": hidden}
```

### 3.4 商品审核（Catalog/Item 审核）实战

DPA 投放前必须通过 Meta 的商品审核（Product Review）。常见流程：

```python
# 获取目录的审核状态
review = api.meta_list_catalog_products(CATALOG_ID, fields=["status", "review_status", "badge"])
# 每位商品 status/review_status 可能为 APPROVED / PENDING / REJECTED / DISAPPROVED
```

**常见审核拒绝原因与解法**（详见 4.5）：

| 原因 | 现象 | 解法 |
|------|------|------|
| 图片违规（差评/文字/边框） | 商品 DISAPPROVED | 换合规主图 |
| 价格与实际不符（砍单） | 大量差评 | 保证 Feed 价格=落低价 |
| 品牌侵权（假货） | REJECTED | 移除违规品牌，提供授权 |
| 缺失 gtin/品牌 | 数据质量不足 | 补全 `gtin`、`brand` |
| 落地页 404 / 无法访问 | 链接无效 | 修 `link` 字段与落地页 |

**要点**：审核状态变化会延迟；改完字段后重新上传触发重新审核。**不要把 0 个审核通过商品的广告直接投放。**

### 3.5 Product Set 创建与验证（Rule 实战）

#### 3.5.1 用脚本创建 Product Set

```python
# 用 filter 规则创建动态商品集
filter_json = {
    "conditions": [
        {"field": "availability", "operator": "EQUALS", "value": "in stock"},
        {"field": "sale_price", "operator": "EXISTS"},
        {"field": "custom_label_0", "operator": "EQUALS", "value": "summer"},
    ]
}

resp = api.meta_create_dynamic_product_set(
    CATALOG_ID,
    name="夏季促销-现货",
    filter=filter_json,
)
ps_id = resp.get("id")
print("product_set_id", ps_id)
```

**Graph API 等价**：

```bash
curl -X POST "https://graph.facebook.com/v19.0/$CATALOG_ID/product_sets" \
  -H "Authorization: Bearer $META_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "夏季促销-现货",
    "filter": {
      "conditions": [
        {"field": "availability", "operator": "EQUALS", "value": "in stock"},
        {"field": "sale_price", "operator": "EXISTS"}
      ]
    }
  }'
```

#### 3.5.2 列出与更新 Product Set

```python
# 列出全部动态商品集
sets = api.meta_list_dynamic_product_sets(CATALOG_ID)
print(sets)

# 更新一个商品集的规则（改 filter）
resp = api.meta_update_dynamic_product_set(
    ps_id,
    name="夏季促销-现货-v2",
    filter={"conditions": [{"field": "availability", "operator": "EQUALS", "value": "in stock"}]},
)
print(resp)
```

```bash
# 读取单个 Product Set 详情（含当前商品数）
curl -G "https://graph.facebook.com/v19.0/$PRODUCT_SET_ID" \
  -H "Authorization: Bearer $META_TOKEN" \
  -d "fields=id,name,filter,product_count"

# 更新 Product Set
curl -X POST "https://graph.facebook.com/v19.0/$PRODUCT_SET_ID" \
  -H "Authorization: Bearer $META_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"夏季促销-现货-v2",
       "filter":{"conditions":[
         {"field":"availability","operator":"EQUALS","value":"in stock"}
       ]}}'
```

#### 3.5.3 验证商品集匹配结果（空集排查）

```python
# 查看 Product Set 内的商品（判断是否命中）
products_in_set = api.meta_list_dynamic_product_sets(CATALOG_ID)
# 若需要精确商品数，读取 product_set详情字段 product_count
ps = api.meta_get_dynamic_product_set(ps_id, fields=["id", "product_count"])
print("当前商品数", ps.get("product_count"))

# 创建后立刻读 product_count，若为 0 则排查规则（见 4.4）
```

**经验**：Product Set 规则里的 `availability=in stock` 很常见，但如果 feed 里 `availability` 字段拼写为 `"in-stock"`（连字符），`EQUALS "in stock"` 就匹配不到——**字段值与规则 value 必须完全一致**，这是空集头号原因。

### 3.6 Pixel / CAPI 事件联动实战

#### 3.6.1 Pixel 标准事件（前端）

以 `ViewContent` 为例（渲染商品详情页时触发）：

```html
<script>
  fbq('init', 'PIXEL_ID');
  fbq('track', 'ViewContent', {
    content_type: 'product',
    content_ids: ['RYAN-001'],
    content_name: 'Ryan Brand Classic Tee Navy',
    value: 19.99,
    currency: 'USD'
  });
</script>
```

#### 3.6.2 CAPI（服务器端）事件（后端）

```python
import requests

def send_capi_purchase(pixel_id: str, token: str, event_id: str, content_ids: list[str],
                       value: float, currency: str):
    """服务器端上报 Purchase 事件。"""
    url = f"https://graph.facebook.com/v19.0/{pixel_id}/events"
    payload = {
        "data": [{
            "event_name": "Purchase",
            "event_time": int(time.time()),
            "event_id": event_id,               # 与 Pixel 同 id 用于去重
            "action_source": "website",
            "user_data": {
                "em": "<sha256(email)>",         # 哈希后的邮箱
                "ph": "<sha256(phone)>",
                "client_ip_address": "...",
                "client_user_agent": "...",
            },
            "custom_data": {
                "content_ids": content_ids,       # 商品 id 数组
                "content_type": "product",
                "value": value,
                "currency": currency,
                "num_items": len(content_ids),
            },
        }],
        "test_event_code": "TEST12345",           # 可选：测试时用
    }
    r = requests.post(url,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json=payload)
    return r.json()

# 脚本里可直接复用
resp = api.meta_send_capi(PIXEL_ID, event_name="Purchase", **{...})
```

#### 3.6.3 事件-目录绑定（确保 content_ids 可匹配）

```python
# 把 Pixel 与 Catalog 关联（在 Business Manager，此处示意绑定关系）
resp = api.meta_update_catalog(CATALOG_ID,
    name="Ryan 官网全量目录",
    destination="websites",
)
# 通过 Business API 在 Catalog 上挂 Pixel 即可（Graph: POST /{catalog_id}/...）
```

**验证**：在 Events Manager → 测试事件 里触发一次 `ViewContent`，确认 `content_ids` 命中 Catalog 商品（出现「与目录匹配」标记）。没命中 = 事件无法驱动 DPA。

#### 3.6.4 `MatchesContentCatalogSchema` 与去重链路健康度

脚本里还提供 `meta_get_event_quality` / `meta_validate_event_data` 可用于检查 DPA 常用事件：

```python
# 检查 Pixel 事件质量（DPA 关注 Purchase/ViewContent 是否合格、去重是否到位）
q = api.meta_get_event_quality(PIXEL_ID)
print(q)
```

### 3.7 创建完整 DPA 广告系列（Campaign → AdSet → Ad）

这是最核心的一步。下面给出「目标 OUTCOME_SALES（SALES）」与「OUTCOME_TRAFFIC」两套的完整脚本。

#### 3.7.1 Campaign（系列）——目标与预算

```python
# 目标 = OUTCOME_SALES（SALES），用来做转化优化
campaign = api.meta_create_campaign(
    AD_ACCOUNT_ID,
    name="DPA-夏季促销-再营销",
    objective="OUTCOME_SALES",        # 也可 UNITY/ 直接用 SALES
    special_ad_categories=[],
    status="PAUSED",                  # 先暂停，配好再启用
    daily_budget=50000,               # 单位：分；50000 分 = $500 或 ¥500（看币种）
)
campaign_id = campaign["id"]
print("campaign_id", campaign_id)
```

**Graph 等价**：

```bash
curl -X POST "https://graph.facebook.com/v19.0/$AD_ACCOUNT_ID/campaigns" \
  -H "Authorization: Bearer $META_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "DPA-夏季促销-再营销",
    "objective": "OUTCOME_SALES",
    "status": "PAUSED",
    "daily_budget": 50000,
    "special_ad_categories": []
  }'
```

> 若某市场没有 Purchase 转化，可用 `OUTCOME_TRAFFIC`（LINK_CLICKS）先跑，等有转化再切 SALES/ROAS。**objective 与产品集/创意组合必须在创建时确定；之后改 objective 会报错。**

#### 3.7.2 Ad Set（广告组）——绑定 Catalog 相关参数

DPA 的关键参数都在 Ad Set / Ad 层：

```python
adset = api.meta_create_adset(
    campaign_id,
    name="DPA-AdSet-夏季现货-加购受众",
    targeting={
        "geo_locations": {"countries": ["US"]},
        # 受众：加购未买（见 3.8 建受众后填 ID）
        "custom_audiences": [{"id": "238470000001"}],
        # 排除已购用户
        "excluded_custom_audiences": [{"id": "238470000009"}],
        "targeting_automation": {},   # 可开 Advantage audience
    },
    daily_budget=20000,
    billing_event="IMPRESSIONS",
    optimization_goal="OFFSITE_CONVERSIONS",
    bid_strategy="LOWEST_COST_WITHOUT_CAP",   # 或 TARGET_ROAS
    status="PAUSED",
)
adset_id = adset["id"]
print("adset_id", adset_id)
```

**注意**：DPA 的 **`product_catalog_id` / `product_set_id` 其实放在 Ad（创意层）**，而不是 AdSet。AdsManager 的「产品目录/产品集」在 advertisement 的 `creative` 上。更多详见 3.7.3。

#### 3.7.3 Ad（广告）——动态创意 + 商品绑定（DPA 的核心）

```python
# 构造 DPA 动态创意
dpa_creative = {
    "product_catalog_id": CATALOG_ID,
    "product_set_id": ps_id,            # 这是关键！决定投哪些商品
    "retailer_product_ids": None,       # 若要精确指定可填 ["RYAN-001","RYAN-002"]，否则留空
    "name": "DPA-creative-夏季促销",
    # 模板：Carousel 轮播
    "template_data": {
        "format": "CAROUSEL",
        "link": "https://www.ryan.com/collections/summer",
        "call_to_action": {"type": "SHOP_NOW"},
        "description": "夏季精选，现货速发",
    },
    # 允许动态商品自动替换
    "dynamic_ad_voice": "DYNAMIC",
    "object_story_spec": {
        "product_catalog_id": CATALOG_ID,
        "link_data": {
            "link": "https://www.ryan.com/?product_id={product.id}",
            "name": "{product.title}",
            "description": "低至 ${product.sale_price}",
            "message": "Ryan 夏季特惠",
            "call_to_action": {"type": "SHOP_NOW"},
        },
    },
}

ad = api.meta_create_ad(
    adset_id,
    name="DPA-Ad-夏季促销-轮播",
    creative=dpa_creative,
    status="PAUSED",
)
print("ad_id", ad["id"])
```

**Graph 等价（重点看字段拼写）**：

```bash
curl -X POST "https://graph.facebook.com/v19.0/$ADSET_ID/ads" \
  -H "Authorization: Bearer $META_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "DPA-Ad-夏季促销-轮播",
    "status": "PAUSED",
    "creative": {
      "product_catalog_id": "'$CATALOG_ID'",
      "product_set_id": "'$PRODUCT_SET_ID'",
      "name": "DPA-creative-夏季促销",
      "object_story_spec": {
        "product_catalog_id": "'$CATALOG_ID'",
        "link_data": {
          "link": "https://www.ryan.com/?product_id={product.id}",
          "name": "{product.title}",
          "description": "低至 ${product.sale_price}",
          "message": "Ryan 夏季特惠",
          "call_to_action": {"type": "SHOP_NOW"}
        }
      }
    }
  }'
```

#### 3.7.4 启用广告前的前置校验清单

```python
# 校验：广告能否被投
def validate_dpa_before_activate(catalog_id, product_set_id):
    prods = api.meta_list_catalog_products(catalog_id, limit=1,
                                           fields=["status", "availability"])
    ps = api.meta_get_dynamic_product_set(product_set_id, fields=["product_count"])
    print("catalog 商品 status:", prods[0] if prods else "empty")
    print("product_set 商品数:", ps.get("product_count"))
    # 要求商品数 > 0 且至少 1 个 in stock 且审核通过，再启用

validate_dpa_before_activate(CATALOG_ID, ps_id)
```

**上线动作**：把 campaign / adset / ad 三个 status 从 `PAUSED` 依次改为 `ACTIVE`（先 enable campaign，再 adset，再 ad），或调用脚本里的 `meta_resume_campaign` 等。

### 3.8 再营销受众构建实战

#### 3.8.1 基于 Pixel 事件的自定义受众（用脚本创建）

```python
# 创建「加购未购买」受众：事件 AddToCart 在 14 天内触发
aud = api.meta_create_audience(
    AD_ACCOUNT_ID,
    name="DPA-加购14天",
    subtype="CUSTOM",
    description="加购未买，用于再营销",
    rule={
        "inclusions": {
            "operator": "or",
            "rules": [{
                "event_sources": [{"type": "pixel", "id": PIXEL_ID}],
                "retention_seconds": 14 * 86400,
                "filter": {
                    "field": "event",
                    "operator": "eq",
                    "value": "AddToCart",
                },
            }],
        },
        "exclusions": {
            "operator": "or",
            "rules": [{
                "event_sources": [{"type": "pixel", "id": PIXEL_ID}],
                "retention_seconds": 14 * 86400,
                "filter": {"field": "event", "operator": "eq", "value": "Purchase"},
            }],
        },
    },
)
print(aud)
```

**常用再营销受众速查**（可直接复用）：

| 受众名 | 规则（inclusion event, retention） | 出价方向 |
|--------|-----------------------------------|---------|
| 浏览未加购 14 天 | ViewContent, 14天；排除 AddToCart | 中等 |
| 加购未结算 14 天 | AddToCart, 14天；排除 InitiateCheckout | 偏高 |
| 开始结算未买 30 天 | InitiateCheckout, 30天；排除 Purchase | 高 |
| 已购买用户 365 天 | Purchase, 365天 | 排除/大礼包 |
| 全部递进漏斗 | 多个事件 OR | — |

#### 3.8.2 类似受众（Lookalike，用种子受众）

```python
# 以「购买用户」为种子做 1% 类似受众（拓新用）
lala = api.meta_create_lookalike_audience(
    seed_audience_id=PURCHASER_AUDIENCE_ID,
    name="LAL-购买1%",
    country="US",
    ratio="0.01",
)
print(lala)
```

#### 3.8.3 完整漏斗预算分配参考

```
L1 浏览 14天  预算 25%   出价 Lowest cost
L2 加购 14天  预算 30%   出价 +10%
L3 弃购 30天  预算 35%   出价 +25%
L4 已购/排除  （不投）
新客 LAL 1%   预算 10%   低出价拓新
```

> 这是一套**经验起点**，按 3-4 周数据迭代调整；漏斗层之间用排除避免重复扣量。

### 3.9 Collection 与 Collection Card 制作实战

DPA 的 **Collection** 格式需要先建合集与卡片：

```python
# 1) 创建 Collection（一本商品合集）
collection = api.meta_create_collection(
    CATALOG_ID,
    name="夏季新品合集",
    # 可选：自动选封面图策略
)
collection_id = collection.get("id") or stubbed_collection_id

# 2) 创建 Collection Card（集合卡片：封面 + 网格）
card = api.meta_create_collection_card(
    collection_id,
    title="夏季新品",
    # 封面可以是图片 URL 或自动图
    image_url="https://static.ryan.com/img/collection-summer.jpg",
    landing_page_url="https://www.ryan.com/collections/summer",
    call_to_action="SHOP_NOW",
)
print("collection_id", collection_id, "card_id", card.get("id"))
```

**Graph 等价**：

```bash
# 创建 Collection
curl -X POST "https://graph.facebook.com/v19.0/$CATALOG_ID/collections" \
  -H "Authorization: Bearer $META_TOKEN" \
  -d "name=Ryan+夏季合集" \
  -d "cover_image_url=https%3A%2F%2Fstatic.ryan.com%2Fimg%2Fcollection-summer.jpg"

# 创建 Collection Card
curl -X POST "https://graph.facebook.com/v19.0/$COLLECTION_ID/cards" \
  -H "Authorization: Bearer $META_TOKEN" \
  -d "name=夏季新品"

# 列出 Collection Cards（脚本里 meta_list_collection_cards 直接可用）
```

**把 Collection 用到广告创意里**：用 `creative.object_story_spec.collection_data` 指定 `collection_id`。

### 3.10 多目录聚合实战

```python
# 前提：子目录同国家同币种
agg = api.meta_create_catalog_aggregation(
    name="Ryan 聚合目录-USD-US",
    country="US",
    currency="USD",
    subcatalogs=["CAT_A_ID", "CAT_B_ID", "CAT_C_ID"],   # 注意：脚本中可传 sub_catalogs
)
agg_id = agg.get("id")
print("aggregated catalog", agg_id)
```

**使用**：把聚合目录当普通 Catalog 绑定到广告，Product Set 用聚合目录的 `id`。

> API 方法名若与脚本不完全一致（如 `meta_create_catalog_aggregation` 未内置），可直接用底层 Graph 调用 `POST /business/{business_id}/product_catalogs` 传 `catalog_type=AGGREGATED` 与 `domain_ids`（子目录）。

### 3.11 上线后监控与健康检查

#### 3.11.1 Feed / 批次健康

```python
# 定期（每日 cron 或每小时）巡检
def daily_catalog_health(catalog_id):
    batches = api.meta_list_catalog_batches(catalog_id)
    pset = api.meta_list_dynamic_product_sets(catalog_id)
    report = {
        "batches": batches,
        "product_sets": [(s.get("id"), s.get("name")) for s in pset],
    }
    # 在传送到群/脚本，或用 meta_query_insights 拉广告表现
    return report
```

#### 3.11.2 广告表现洞察

```python
# 拉取 DPA 广告系列洞察（可选 level=adset / ad）
ins = api.meta_query_insights(
    AD_ACCOUNT_ID,
    date_preset="last_7d",
    level="adset",
    fields=["adset_id", "spend", "impressions", "clicks", "cpc", "cpa"],
)
print(ins)
```

#### 3.11.3 用「动态广告」专门的读取

脚本里的 `meta_list_dynamic_ads` 可扫 DPA 广告：

```python
dpa_all = api.meta_list_dynamic_ads(AD_ACCOUNT_ID)
print(dpa_all)
```

> 由于脚本方法常返回空实现（占位），生产上建议直接扩展用 Graph `GET /{ad_id}?fields=effective_status,creative{product_set_id}` 确认每个广告绑定的 Product Set 与状态是否 OK。

**上线 checklist（可贴到团队复盘）**：
- [ ] Catalog 商品数、in stock 数、审核通过数打印
- [ ] Product Set 商品数 > 0
- [ ] Pixel 已绑 Catalog，`content_ids` 测试命中
- [ ] CAPI + Pixel 去重率 < 某个阈值（如 < 30% 丢单）
- [ ] Campaign / AdSet / Ad 用 `PAUSED` 建好 → 预检通过 → 依次 `ACTIVE`
- [ ] 上线后 24h 看 impressions；为 0 立即按 4.x 排查

### 3.12 高级：用 `meta_list_categories` / 预聚合做品类定投

```python
# 列出商品类目（用于按品类圈 Product Set 前的辅助）
cats = api.meta_list_categories(CATALOG_ID)
print(cats)
```

按品类建 Product Set 的常见规则示例：

```json
{
  "conditions": [
    {"field": "product_type", "operator": "CONTAINS", "value": "Apparel"},
    {"field": "availability", "operator": "EQUALS", "value": "in stock"}
  ]
}
```

