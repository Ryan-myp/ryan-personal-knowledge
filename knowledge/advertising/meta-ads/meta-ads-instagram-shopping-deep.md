# Instagram 商业功能全链路深度文档：Shoppable Posts / Product Catalog / Checkout / 商品管理 API

> **领域**: 广告投放 / Meta
> **深度**: ⭐⭐⭐⭐⭐ 实战级指南
> **标签**: meta-ads, instagram, shopping, product-catalog, checkout
> **更新时间**: 2026-08-14
> **类型**: 实战深度文档

---

## 一、核心概念与架构

### 1.1 本文档的定位与边界

Instagram（下称 IG）商业功能（Instagram Shopping / 也叫 Instagram Commerce）是把「账号内容」与「商品买卖」打通的一整套能力。它不是一个孤立的广告功能，而是位于「商品目录（Catalog）」之上、与「Meta 广告投放（Advanced/DPA/Collection Ads）」并列的一层**零售转化设施**。

在阅读本文档前，请先明确它与仓库中另外两份文档的分工：

| 文档 | 定位 | 与本文的关系 |
| --- | --- | --- |
| `meta-ads-catalog-deep.md` | Catalog / Product / Product Set / Feed 的通用原理（服务于 DPA 广告） | 本文只 2.x 简要带过 Catalog 结构，聚焦 **IG 专属** 的绑定、标签、商店、结账 |
| `meta-ads-architecture-deep.md` | Meta 全平台账号/资产/权限/评分架构 | 本文聚焦 **IG 商业账号与 BM 关联** 这一个垂直切口 |
| 本文（本文件） | **IG Shopping 全链路**：开通 → 商品 → 打标 → 显示 → 结账 → API 管理 | 站在 Catalog 之上的一整套 IG 专属链路 |

> **一句话记住**：Catalog 是「货」，Meta 广告是「获客」，IG Shopping 是「在 IG 里面直接把货卖掉」。三者的关系是 `货（Catalog）→ 展示（Shoppable Post/Shop Tab）→ 转化（Checkout 内购或外链）`。

### 1.2 核心概念总览（先建立地图）

IG 商业功能涉及一组既重叠又分层的概念，先给一张速查表：

```
概念速查
├── Instagram 商业账号 (Business Account)
│   ├── 与个人号/创作者号的区别（专业主页、商业主页分类、链接工具）
│   └── IG Business / Creator Profile（2020 后 IG 专业账号统一为 Business/Creator 两种）
├── Meta 商务管理平台 (Business Manager, BM / Business Portfolio)
│   ├── 拥有并管理 Catalog、Pixel、Page、广告账户
│   └── 通过「已连接 Instagram 账号」把 IG 商业号纳入 BM 资产树
├── Product Catalog (商品目录)
│   ├── 归属 BM，类型：电商 / 酒店 / 航班 / 目的地 / 实体店
│   └── 通过「绑定向 IG 商业号」被 IG 消费
├── Shoppable Post (可购物帖子)
│   ├── 图片 / 轮播 / 视频 / Reels 上挂「商品标签 (product tags)」
│   └── 点击标签 → 打开商品详情页 → 结账
├── Product Tags (商品标签)
│   ├── 绑定到某条 Media 上的一个或多个商品
│   └── 受「每帖上限 / 审核 / 库存状态」约束
├── Instagram Checkout (原生结账, Native Checkout)
│   └── 用户在 IG 内完成支付、物流、退款（仅限指定国家/品类）
├── External Checkout (外部结账)
│   └── 点击标签跳转站外（外链 / Pixel 结账），落地站内由商家自己处理
├── Shop Tab / Collections (商店 Tab 与商品集合)
│   ├── IG 商店橱窗：按 Collection 分类陈列
│   └── Collection 是商品集的「面向用户」的展示形态
└── 管理与自动化层
    ├── Instagram Graph API（product_tags / shopping_product_catalogs / collections / shopping_orders）
    ├── Commerce API / Commerce Manager（商务管��平台）
    └── 数据：IG Insights / Commerce Insights
```

### 1.3 关键实体详解

#### 1.3.1 Instagram 商业账号（Business Account）

**什么是它**：在 IG 上通过「设置 → 账号类型 → 切换到专业账号 → 选商业」得到的功能集合。商业账号解锁了：联系方式按钮、商业分类、统计分析（Insights）、广告投放、以及最重要的——**商品打标与商店**。

**账号类型演进（重要，很多老教程已过时）：**

```
历史账号体系（2016 - 2021）
├── 个人账号 (Personal)
├── 企业账号 (Business) —— 需关联 Facebook 主页 (Page)
└── 创作者账号 (Creator) —— 面向 KOL，无「商业」主打

当前账号体系（2021 后，重要）
├── 个人账号 (Personal)
└── 专业账号 (Professional)
    ├── 商业账号 (Business)
    │   ├── 需要商业主页分类
    │   ├── 需要链接产品或配套付款/购物工具
    │   └── 后续演进：2021 年起**不再强依赖关联 Facebook 主页**即可开通购物
    └── 创作者账号 (Creator)
        └── 面向个人创作者，功能介于二者之间
```

> **踩坑点（实战高频）**：老教程里写「必须把 IG 账号关联到一个 Facebook 主页才能开通购物」。这条在 2021 年后被 Meta 放宽——IG 商业账号**可以不再关联 Page**，但**目录（Catalog）仍必须归属某个 BM，且该 BM 必须能访问到这个 IG 商业账号**。很多新手的第二个坑是：用一个「个人号」就去买域名、配 Pixel，最后在商务管理平台里根本找不到 IG 选项。

#### 1.3.2 与 Meta 商务管理平台（BM）的关联

**为什么必须关联 BM**：商品目录、Pixel、标签库、审核记录、订单数据都存放在 BM（现称 Business Portfolio / Meta Business Suite）里。IG 账号本身只是「消费这些资产的门店」，资产的所有权用 BM 的权限体系（Business Assets Roles）管理。

**关联后的资产树（关键架构图）：**

```
Meta Business Manager (BM)
│  business_id: 123456789012345
│
├── 广告账户 Ad Account ...（用于投放）
├── 主页 Page ...（可绑可不绑，见上）
├── Pixel ...（用于 External Checkout 追踪）
│
├── Product Catalog
│   └── catalog_id: 481263857108912
│       ├── Products（商品）
│       ├── Product Sets（商品集）
│       ├── Collections（商品集合，面向 IG 商店展示）
│       └── Feeds / Batches（数据源与批次）
│
└── Instagram Account（已连接 IG 商业号）
    └── ig_user_id: 1784140000000000
        ├── 挂接 catalog_id（可通过 /{ig-user-id}/shopping_product_catalogs 查询）
        ├── 可购物帖子 (Shoppable Media)
        ├── 商店 Collections（面向用户展示）
        └── 订单（Native Checkout 时）
```

**关联的三种典型方式：**

1. **IG App 内关联**：设置 → 专业账号 → 购物 → 选择「连接商务管理平台」→ 选择/创建目录。（最常用，用户可直接操作）
2. **BM 侧接入**：商务管理平台 → 业务设置 → Instagram 账号 → 连接 IG 商业号 → 分配目录权限。（适合代理/服务商批量管理）
3. **API 侧查询**：通过 `GET /{ig-user-id}/shopping_product_catalogs` 拿到已绑定的目录列表，验证关联是否成功。

#### 1.3.3 Shoppable Post（可购物帖子）

凡是**在帖子/Reels 上挂了商品标签**的 Media，统称可购物帖子（也叫 tagged post / product-tagged media）。受众侧表现为：图片某个像素点附近会出现一个「袋/商品」图标，点击后弹出一个商品浮层，进一步点击进入商品详情。

```
可购物帖子的用户侧体验（点击链路）
[信息流中的帖子]
        │
        │ 点击帖子左下角「🛍 查看商品」或图片上的商品标记点
        ▼
[商品浮层 Pop-Up]
        │  显示：商品图 + 价格 + 名称 + 「查看商店」
        ▼
[商品详情页 Product Detail Page (PDP)]
        │  可切换不同标签商品、查看描述、规格
        ▼
[结账 Checkout]
   ├── Native（原生结账：站内完成支付/物流/退款）
   └── External（外链：跳转商家站点 / 用 Pixel 追踪的结账流）
```

**可购物内容的类型维度：**

| 内容形态 | 是否可打标签 | 备注 |
| --- | --- | --- |
| 普通图片帖（单图） | ✅ | 每帖有商品标签上限 |
| 轮播帖（Carousel） | ✅ | 每张卡片可独立打不同标签 |
| 视频帖（video） | ✅ | IGTV/普通视频 |
| Reels | ✅ | 2021 后支持 Reels 打标签（进入 Video Shopping 范畴） |
| 快拍（Stories） | ⚠️ | 通过「商品贴纸」单商品呈现，非 product_tags 边 |
| 直播（Live Shopping） | ⚠️ | 直播打标签，分地区开放 |

> **关于标签数量上限（务必核实到最新的官方数字）**：历史上 IG 每帖商品标签上限为 **5 个**；2021 年 Meta 将部分账号/地区开放到 **20 个**。上限与账号状态、地区、目录类型相关，**上线前务必以官方「最近版本」的份额说明为准**，不要写死在代码里。

#### 1.3.4 原生结账（Instagram Checkout / Native Checkout）vs 外部结账（External Checkout）

这是 IG 商业功能里**最容易混淆**的一对概念，也是影响「货该怎么卖」的第一决策点。

```
结账模式二选一（账号只能选一种结账方式进入商店）
┌─────────────────────────────────────────────┐
│  选择结账方式                              │
│                                             │
│  [A] 在 Instagram 上结账 (Native Checkout) │
│      ├── 用户在 IG 内支付（绑定支付方式）   │
│      ├── IG 处理支付/税费/物流/退货          │
│      ├── 仅限特定国家 / 品类 / 账号通过审核 │
│      └── 商品需走 Meta 供应链与退货政策     │
│                                             │
│  [B] 在网站上结账 (External / Pixel 结账)  │
│      ├── 点击「查看网站」跳转到商家域名     │
│      ├── 商家自建站负责支付/物流/退货       │
│      ├── 需配置 Pixel / 外链追踪           │
│      └── 覆盖国家更广，��乎所有国家可用    │
└─────────────────────────────────────────────┘
```

| 维度 | Native Checkout（原生结账） | External Checkout（外部结账） |
| --- | --- | --- |
| 支付发生地 | IG App 内（Meta 钱包/卡） | 商家网站（跳转） |
| 物流/退货 | Meta 与商家共同/商家按平台规则 | 商家完全自管 |
| 结账转化 | 站内转化，跳出率低 | 依赖落地页与复访 |
| 支持国家 | 少（美/英/澳/加/法等逐步开放） | 广（凡支持 Shopping 的国家大致可用） |
| 追踪方式 | Meta 掌握完整漏斗，订单数据显示在 IG | 依赖 Pixel/Conversion API 回传 |
| 佣金/手续费 | 平台收取处理费（比例/按件随市场而变） | 无平台交易抽成，但付广告费与支付渠道费 |
| 审核门槛 | 更高（需通过 Checkout 准入） | 相对低（Domain + 政策合规） |
| 典型适用 | 品牌方、有 Meta 供应链诉求者 | 绝大多数独立站/平台型卖家 |

> **核心坑位**：**中国内地 / 大多数非开放国商家装不了 Native Checkout**。绝大多数自建站（Magento/Shopify 独立站但无海外公司主体）实际只能走 External。先确认「结账方式」再谈后续 Permalink 与 Pixel，能省掉大量返工。

### 1.4 商店 Tab 与 Collections（商品集合）

**IG 商店（Shop Tab / shop）**：IG 商业号主页上的「查看商店」入口，把一个「面向用户的橱窗」（你所有可购商品 + 按 Collection 分类的陈列）呈现给受众。它由「目录里的商品 + Collection 排序」共同决定。

**Collection（商品集合/含卡片）**：在商务管理平台（Commerce Manager）里创建的可购商品的逻辑分组，例如「新品上架」「夏季精选」。它与 Catalog 的 Product Set（商品集）相关但**不等同**：Product Set 更多服务于广告分组/API 逻辑，Collection 是「面对用户的陈列层」，且通常一个 Collection 对应一张「商店 Tab 上的卡片（Collection Card）」。

```
商店 Tab 的呈现结构
IG 商店（/ig-user-id 的 shop）
├── 精选 Collection A（卡片：封面图 + 名称）
│   └── 商品1 商品2 商品3 ...
├── 精选 Collection B
│   └── 商品4 商品5 ...
└── 全部商品（默认兜底视图，未归类商品也在此出现）
```

**Collection 与 Product Set 关系（架构图）：**

```
Catalog (catalog_id)
├── Products（全部商品）
├── Product Sets  product_set_id      ← 服务端逻辑分组，DPA 广告用它
│    └── 可被 Collection 引用
└── Collections  collection_id        ← 用户可见包装
     ├── 名称 name（面向展示）
     ├── 包含的商品（来自商品集或直接选商品）
     └── 展示在 IG 商店页面（可选设为「精选」）
          └── Async：改变需等审核/传播，非即时生效
```

### 1.5 与 Meta 广告体系的关系（为什么投放专家要看本文）

IG Shopping 不只是「卖货」，它还是**三者广告产品的底层素材**：

1. **Shopping Ads（商品购物广告）**：可购物广告目录（Catalog Sales objective）落地到可购物帖子/商品页，受众直接购买。可购物帖是它的自然形态。
2. **Collection Ads（精品栏广告）**：落地页展示商品集合（Collection Card），与 IG 商店的 Collection 共用一套商品集逻辑。
3. **Dynamic Ads（动态商品广告 DPA）**：由 Catalog + Pixel 行为触发，重定向展示商品，点击后同样落到商品详情页。

**一句话**：IG Shopping 打通了「内容（帖子/Reels）→ 商品（Catalog）→ 转化（结账）」，而广告投放只是把这个链路**放大给更多受众**。所以 Catalog 的字段质量、库存同步、标签策略会同时影响**可购物内容体验**与**广告转化**。

### 1.6 术语表（TL;DR 表）

| 术语 | 英文 | 说明 |
| --- | --- | --- |
| 可购物帖子 | Shoppable Post | 挂了商品标签的帖子/Reels |
| 商品标签 | Product Tag | 挂在 Media 上的单个商品标记 |
| 商品目录 | Product Catalog | 商品数据库，归属 BM |
| 商品集 | Product Set | Catalog 内的逻辑分组 |
| 商品集合/橱窗卡 | Collection / Collection Card | 面向用户的陈列分组 |
| 原生结账 | Instagram Checkout / Native Checkout | 站内支付 |
| 外部结账 | External Checkout / Pixel checkout | 站外跳转结账 |
| 商业账号 | Instagram Business Account | 开通购物的前置账号形态 |
| 商务管理平台 | Business Manager（现 Business Portfolio） | 资产与权限归属地 |
| 购物目录绑定 | Connected Product Catalog | IG 账号 ↔ 目录的挂接 |

---

## 二、深度原理解析

这是本文档的重点，我们从「数据流」与「状态机」两层把 IG 商业功能讲透。

### 2.1 Instagram 商业账号与 BM 关联的原理

#### 2.1.1 账号模型：为什么「IG 商业号」是这一切的地基

IG 商业功能的所有能力都以「账号是 Business 类型」为前提。个人账号（Personal）无法创建/查看商品标签，也无法关联目录。账号类型的本质是一个 `follows_profile_type` 之类的元数据 + 一组解锁的功能位（feature flag），而**这些功能位又绑定到「评分的账号是否达到政策合规」**。

**账号资产模型（Graph API 视角）：**

```
IG 账号（ig-user-id, type=Business）
├── name / username / biography（公开资料）
├── follows_count / followers_count
├── media（帖子集合）
│    └── 每条 media 可携带 product_tags
├── connected catalog（绑定目录）
├── shop（商店/橱窗）
├── collections（商品集合）
└── business_discovery / insights（数据）
```

#### 2.1.2 IG 账号 ↔ Page ↔ BM 三者关系（含演进）

**2021 年之前的关系（老范式）：**

```
Facebook Page（主页）
   │  拥有（通过 BM 授权）
   ▼
Instagram Business Account
   │  Page 是 IG 商业号的「管理者」
   ▼
Business Manager 资产树
   ├── Page
   └── IG 仅作为 Page 的附属，购物要求 Page+IG+Catalog 三者连通
```

**2021 年之后的实际关系（新范式，很多教程没更新）：**

```
Business Manager (BM)
   │  通过「关联的 Instagram 账号」直接持有
   ▼
Instagram Business Account
   │  不强制关联 Page（可删掉 Page 依赖）
   ▼
Product Catalog（目录）
   │  与 IG 绑定（shopping_product_catalogs）
   ▼
IG 商店/可购物内容
```

> **结论给实战者**：判断「能否开通购物」，现代标准主要看三个独立要件：① IG 是商业账号；② BM 能访问该 IG 账号并与目录连通；③ 账号/域名/商品通过政策与审核。Page 不再是硬依赖，但**部分地区的审核流程仍会参考 Page 状态**，所以「有 Page 没坏处，但没有也不是不能做」。

#### 2.1.3 权限模型：谁有资格打标签/管商店

权限决定「哪个账号/管理员能往 Media 上打标签、能改商店」。这是 API 调用总会先碰到的门。

```
IG 权限层级（按授权关系由高到低）
├── IG 账号管理员 / BM 的 Business Admin
│   ├── 配置目录挂接、提交审核、管理订单
│   └── 拥有完整 Commerce 权限
├── BM 的业务编辑 (Business Editor)
│   └── 可改商品、集合、商店展示
├── 广告投放用户 (Advertiser)
│   └── 可创建广告、引用商品，但改不了商店设置
└── 分析用户 (Analyst) / 仅查看
    └── 只读 Insights，不能改标签
```

打标签的「最终执行人」一般是**内容（Media）的作者账户**，且该账户需具备 Commerce 资格。这就是为什么很多公司「运营发帖的账号」与「商务管理员」是不同人时，需要先在 BM 里把 IG 账号设置为管理员/编辑，才能由脚本（以该 IG 账号的 token）调用 `POST /{ig-media-id}/product_tags`。

**Token 权限字段（IG Graph API 需要的权限）：**

| 权限 scope | 用途 | 本文涉及的端点 |
| --- | --- | --- |
| `instagram_basic` | 读取公开资料与 media | 大部分 GET |
| `instagram_content_publish` | 发布/修改内容 | 打标签相关 POST/DELETE |
| `instagram_manage_comments` 等 | 留言管理 | 非本文重点 |
| `commerce_account_manage` | 管理工作商务账号/目录/订单 | Commerce 相关端点 |
| `pages_show_list` / `pages_read_engagement` | 读取 Page（若用 Page 流） | 关联类 |

> **坑**：很多开发只申请了 `instagram_basic`，调用 `GET /{ig-user-id}/shopping_product_catalogs` 时拿到 `(#200) Permission error` 或 `(#100) No commerce permission`，其实是要补 `commerce_account_manage` 并在 App 审核里申明用途。

### 2.2 Product Catalog 与 Instagram 的绑定原理

Catalog 的通用结构在 `meta-ads-catalog-deep.md` 里已覆盖，这里只讲 **IG 专属的绑定语义**。

#### 2.2.1 目录如何「挂」到 IG 商业号

IG 不直接持有商品数据，它**引用** BM 里的一个 Catalog。绑定关系由 `shopping_product_catalogs` 边表达：

```
GET /{ig-user-id}/shopping_product_catalogs
    ?access_token=...
    ?fields=id,name,product_count
```

响应（示意）：

```json
{
  "data": [
    {
      "id": "481263857108912",
      "name": "Ryan 电商目录",
      "product_count": 3421
    }
  ]
}
```

**绑定的必要条件：**

1. 目录属于某个 BM，且该 BM 对该 IG 账号有访问权；
2. 目录类型是「电商」且商品的 `availability` 等字段合法；
3. IG 账号已完成购物开通（至少通过基础资格检查）。

**多目录**：一个 IG 账号一般只挂一个主营目录（Shopping 场景）。若需要多目录（如品牌拆分），需在 IP 上确认；多数接入是「一账号一目录」。

#### 2.2.2 商品在 IG 侧的可见性与三种「状态门」

目录里有商品 ≠ IG 里能看到。商品在 IG 侧要过三道门：

```
图：一张商品卡从 Catalog 到「能被打上标签」的链路
[Catalog 商品]
   │  ① 结构校验（必填字段、图片 URL 可达、价格合法、货币匹配）
   ▼
[Commerce Eligibility（商业资格）]
   │  ② 地区支持、品类合规、政策审核通过
   ▼
[可见/可打标(available for tagging)]
   │  ③ 商品 availability=in stock、未被下架、目录仍绑定
   ▼
[出现在打标候选列表 / 可被 product_tags 引用]
```

如果商品「在目录里但打不上标签」，逐门排查：图片超规格、必填字段缺失、availability 是 discontinued、目录被解绑、账号审核未过。

### 2.3 Shoppable Posts 与商品标签（Product Tags）原理

这是 IG 商业的核心，值得拆到最细。

#### 2.3.1 标签在数据模型上长什么样

一条 `media`（图片/视频/Reels）可以挂多个 `product_tag`。标签是 **media 与 product 的关联对象**，本质是一个 `(media_id, product_id, position)` 三元组：

```
Product-Tag 对象（概念）
├── media_id      挂到哪条帖子
├── product_id    挂在哪个商品（对应 catalog 里的商品）
├── product_image_url  缩略图（冗余，展示用）
├── product_name / product_price  （展示快照，滞后于 catalog 的实时值）
└── position / 锚点坐标（图片上标记点位置，可选）
```

**抓取某条 Media 上的所有标签：**

```
GET /{ig-media-id}/product_tags
    ?access_token=...
    ?fields=product_id,product_name,product_price,image_url
```

#### 2.3.2 打标签的两种路径与约束

**路径一：App 手动打标**——创作者在发布界面点「标记商品」，从已绑定目录的商品里选。适合小批量、运营人工编辑。

**路径二：API 打标**——用 IG Graph API 的 `product_tags` 边，适合规模化内容（同一模板帖批量挂多个商品）：

```
POST /{ig-media-id}/product_tags
     ?product_id={product_id}
     &access_token={page_or_ig_token}
```

```
DELETE /{ig-media-id}/product_tags
        ?product_id={product_id}
        &access_token={token}
```

**关键约束（API 打标容易踩的坑）：**

1. **Media 必须已发布**：草稿/审核中的 media 无法打标（部分版本支持对已排期 media 打标，需确认）。
2. **商品必须在绑定的 Catalog 中**：否则返回 `(#100) The product does not belong to the catalog connected to this business account` 一类错误。
3. **每帖标签数量上限**：受平台当前上限约束（5 / 20 视账号与地区），超出报参数错误。
4. **标签会随商品状态联动**：商品 `availability` 变为 `out_of_stock` / `discontinued`、或商品被从目录删除、或目录解绑 → **已有标签自动失效/隐藏**（不是报错，是标签消失）。这就是库存同步延迟会表现为「标签莫名消失」。
5. **作业是异步的**：`POST` 打标返回的通常是成功确认，但标签能否显示受后台异步传播影响，需要轮询 `GET /{ig-media-id}/product_tags` 确认最终落库。

**查询某商品被哪些 Media 打标（反向边）：**

```
GET /{ig-user-id}/product_tags
    ?product_id={product_id}
    ?fields=media_id,caption,permalink
```

这用于「给某个商品批量做素材盘点 / 排查误标」。

#### 2.3.3 轮播（Carousel）与 Reels 的特殊性

- **轮播**：每张 Card 是独立的 `media`（子节点），各自可打不同标签。批量操作时要遍历 `GET /{ig-media-id}/children` 逐卡打标。
- **Reels**：Reels 也是一种 media（`media_type=VIDEO` 或 `REELS`），打标 API 相同，但**上线时间与地区支持不一致**；还注意 Reels 打标通常要求在发布时或发布后短时间内完成。
- **Stories**：不走 `product_tags` 边，走「商品贴纸（Product Sticker）」，一个贴纸对应一个商品，接口与门槛不同。

### 2.4 Checkout（结账）原理

#### 2.4.1 Native Checkout 的端到端数据流

原生结账意味着：**用户长期留在 Meta 生态内**完成「看商品 → 下单 → 付款 → 看到物流 → 申请退货」。这对 Meta 来说等于掌握了交易的完整漏斗，因此它只对「审核通过 + 地区开放 + 品类合规」的卖家开放。

```
Native Checkout 端到端链路
[用户点标签/商店]
      ▼
[商品详情页 PDP]（Meta 渲染，读 catalog 商品字段）
      ▼
[购物车 / 结算]（Meta UI）
      ▼
[支付]（Meta 钱包：绑卡/Apple Pay/Google Pay 等，分地区）
      ▼
[订单创建]
      ├── 订单状态机：CREATED → CONFIRMED → ... → COMPLETED/CANCELLED
      ├── 通知：商家在 Commerce Manager / API 看到订单
      └── 履约：商家发货，更新物流单号（tracking），由 Meta 侧告知用户
      ▼
[退货/退款]（Meta 政策 + 商家退货政策，订单状态更新）
```

**订单相关端点（Commerce 层）：**

```
GET /{ig-user-id}/shopping_orders
     ?fields=id,created_time,payment_details,shipping_address
GET /{shopping-order-id}?fields=...
GET /{shopping-order-id}/item_fulfillments   （履约/物流）
GET /{ig-user-id}/commerce_payouts           （结算/打款）
```

**Native Checkout 的准入关键点：**

- **国家/地区**：仅 Meta 明确开放的结账国家可用（美、英、澳、加、法、德等，中国大陆通常不可用）。**先查「结账国家支持表」再决定架构**。
- **支付货币**：商品 `price` 的货���需在平台支持列表内，且与结算币种一致，否则商品在结账页报货币不匹配。
- **品类合规**：处方药、成人用品、部分虚拟商品等在结账环节被拒。
- **退货政策**：需在设置里填写退货政策并合规，否则审核不过。

#### 2.4.2 External Checkout 的端到端数据流

外部结账把「买卖」放回商家网站，Meta 只负责「导流与追踪」。

```
External Checkout 端到端链路
[用户点标签]
      ▼
[商品详情页 PDP]（仍是 Meta 渲染，展示商品信息 + 「查看网站」按钮）
      ▼
[跳转商家落地页]（URL 由 catalog 的 link/url 字段或 Permalink 给出）
      ▼
[商家网站支付/物流/退货]（商家完全自管）
      ▼
[回传追踪]
      ├── Pixel：ViewContent → AddToCart → InitiateCheckout → Purchase
      └── CAPI / 手动回传：补全 Meta 看不到的数据
```

**为什么 External 是默认形态**：它不要求 Meta 掌握你的支付供应链，只要「域名验证 + Pixel + 政策合规」，就能几乎在全球范围使用。独立站、Magento/Shopify 商家绝大多数走这条路。

**External 的关键工程点**：

1. **域名验证（Domain Verification）**：在 BM 里验证你的落地域名（如 `buy.ryan-store.com`），否则商品 `link` 指向的域名不被信任，签可能不显示或跳转异常。
2. **Permalink / 落地 URL**：catalog 商品的 `link` 字段决定点进去看哪里；某些情况下工具的 `icon_url`/`additional_image_url` 也要正确。
3. **Pixel 事件**：至少埋 `ViewContent`（content_ids = catalog 的 `retailer_id`/`id`）与 `Purchase`，让 Meta 能回传广告归因与再营销。

#### 2.4.3 结账模式的切换规则

- 结账方式**一经选定并进入审核**，切换需要重新走审核流程，切换期间商店可能短暂不可用。
- 同一账号**同一时间只能有一种结账方式**生效。
- 从 External 切到 Native 或者反向，都需要：改 Business Manager 设置 → 重新提交商店 → 等待审核 → 验证商店可正常下单。

#### 2.4.4 佣金与成本结构（概算）

| 模式 | Meta 侧主要成本 | 商家侧 |
| --- | --- | --- |
| Native Checkout | 平台处理费（订单金额一定比例，随市场与合同变化；也有按件/上限），支付渠道费 | 广告费 + 履约成本 |
| External Checkout | 无平台交易抽成（但仍付广告费） | 支付渠道费 + 履约成本 + 站内转化优化成本 |

> **注意**：比例是动态的、分市场，且会随政策调整。写进系统预算前，以商务管理平台当前合同与官方帮助中心为准，不要当作固定公式。

### 2.5 商店 Tab 与 Collections 原理

#### 2.5.1 商店的渲染依赖

IG 商店不是「独立资源」，而是「目录 + 账号设置 + 集合排序」的结果视图。商店 Tab 在账号主页以「查看商店」曝光，点进去展示精选集合与全部商品。

```
商店渲染依赖图
IG 商店 (Shop Tab)
├── 数据源：绑定 Catalog 的可购商品
├── 展示组织：Collections（可设精选 / 排序）
├── 结账方式：Native 或 External（二选一，见 2.4）
└── 审核状态：账号需处于「购物已启用」状态，否则商店页显示错误
```

#### 2.5.2 Collection 的对象模型与 API

Collection（商品集合）的数据结构：

```
Collection 对象
├── id
├── name（展示名，如「夏季精选」）
├── created_time
├── type（一般为 MANUAL，另有自动/智能集合）
└── products（成员商品，有数量上限；超过会截断展示）
     └── 每个商品引用自绑定 Catalog
```

**常用 API：**

```
列出集合
GET /{ig-user-id}/collections?access_token=...

创建集合
POST /{ig-user-id}/collections
     ?name=夏季精选
     &product_id={product_id}   （首个商品，之后可再加）

查看集合信息
GET /{collection-id}?fields=name,description,created_time

列出集合内商品
GET /{collection-id}/products?fields=id,image_url,name

向集合加商品
PUT /{collection-id}/products?product_id={product_id}&access_token=...

从集合移除商品
DELETE /{collection-id}/products?product_id={product_id}&access_token=...
```

**Collection 与 Collection Card 的区分**：Collection Card（橱窗卡）是商店 Tab 上**展示单元**——一张卡 = 一个集合的封面与名称。卡的可用性取决于集合是否有合规封面图、是否达到最低商品数。

> **坑**：集合名重复、集合为空（无商品）、封面图不达标，会导致卡片不在商店展示。删除「精选」集合后商店可能只剩「全部商品」兜底视图。

### 2.6 视频购物（Video Shopping / Live Shopping）原理

#### 2.6.1 Reels / 视频打标签

视频与图片共用 `product_tags` 边，但有两个额外约束：**内容需满足视频质量与时长政策**、**打标签需在可打标的窗口内完成**。Video Shopping 还包括「视频内商品豆荚/标签位置」的展示优化。

#### 2.6.2 Live Shopping（直播购物）

直播购物把「实时讲解 + 商品卡」结合，主播在直播页挂多件商品，观众边看边下单（Native 或外部）。其接口历史上有 `live_videos` 与商品关联，属于比 Reels 更进阶、地区限制更严的能力。策略上：直播购物适合「高互动、临门转化」，需要主播账号通过审核并具备相应功能位。

```
直播购物链路（概念）
[开播 Live Video]
      │  挂在直播上的商品卡（每场直播可挂若干件）
      ▼
[观众边看边点]
      ├── Native：站内加购/下单
      └── External：跳站
      ▼
[直播结束] → 数据沉淀到 Commerce Insights
```

### 2.7 管理自动化：Instagram Graph API + Commerce API 体系

这是把「人工打标」升级到「规模化运营」的关键，也是本文 Python 示例的核心。

#### 2.7.1 两套 API 的分工（重要概念澄清）

```
包一层理解
├── Instagram Graph API（IG 内容与账号边）
│   ├── product_tags（打标/查标）
│   ├── shopping_product_catalogs（查绑定目录）
│   ├── collections（商店集合）
│   ├── shopping_orders / commerce_payouts（原生结账订单）
│   └── live_videos、media、insights
└── Commerce API / Commerce Manager（商务化经营）
    ├── Commerce Manager UI（business.facebook.com/commerce）
    └── Commerce API：目录商品增删改查、订单履约、返还/退货
```

- **IG Graph API** 更多面向「内容侧动作」（给帖子打标、摆集合）；
- **Commerce API**（含 catalog 商品管理与订单）更多面向「经营侧动作」（改价、改库存、处理订单、退款）；
- 两者共用同一 Catalog/BM 底层，但端点、权限、审核要求不同。

#### 2.7.2 端到端「一件商品上架到可购物」的 API 步骤图

```
编号 工具           动作                                       涉及端点
1   Commerce Manager  创建目录（或复用已有）                     Commerce UI
2   meta_api          在目录里新增商品（含图/价/库存/link）      POST /{catalog_id}/products
3   IG API            确认目录已绑定 IG 商业号                   GET /{ig-user-id}/shopping_product_catalogs
4   meta_api          在内容上打标签                              POST /{ig-media-id}/product_tags
5   IG API            验证标签落库                                GET /{ig-media-id}/product_tags
6   meta_api          建集合/加精选，让商店可见                   POST /{ig-user-id}/collections
7   Insights          看互动/转化                                 GET /{ig-user-id}/insights ...
```

#### 2.7.3 异步与终态（关键工程概念）

目录的增删改、集合变更、标签传播**都不是同步立即生效**，都经过内部异步管线：

```
图中的「写入 → 传播 → 可见」三段式
[写请求]  ──►  [异步处理（队）]  ──►  [最终一致可见]
 立即返回              秒~分钟                        分钟~数小时
 用 Batch/Job 状态查询  用 GET 回读验证
```

所以**校验正确性的姿势**不是「发了就当成功」，而是「发 → 轮询 Job/Batch → 回读资源」三连。库存与价格同步尤其如此：catalog 改了价，IG 商品详情页可能要数分钟才跟得上。

---

### 2.8 授权与 Token 深度：谁是「能打标」的执行者

#### 2.8.1 IG Graph API 的 Token 体系

调用 `product_tags` / `collections` / `shopping_product_catalogs` 用 **Instagram User Access Token（IG 用户令牌）**，由以下方式获得：

```
Token 获取链路
[App 通过审核（含 Instagram 权限）]
        ▼
[App 走 Facebook Login / Instagram 授权]
        ▼
[用户授权：选择要授权的 IG 商业账号 + 同意权限 scope]
        ▼
[拿到 Short-lived token（约 1h）]
        ▼
[再换 Long-lived token（约 60 天）]
        ▼
[业务侧用 System User Token（60 天，可续）+ 权限代理]
```

**系统用户（System User）推荐**：服务商/脚本批量管理多个客户账号时，用 BM 的「系统用户」+ 授权，避免每个客户都跑一遍 OAuth 流程。

#### 2.8.2 权限不足的典型表现（报错对照）

| 症状 | 可能的权限缺项 | 修复方向 |
| --- | --- | --- |
| `(#200) Permission error` | `commerce_account_manage` 缺失 | 补权限 + 重新授权 + App 复审用途 |
| `(#100) No commerce permission for this user` | 账号非商业 / 未绑目录 | 切商业账号 / 绑目录 |
| `(#10) Application does not have permission for this action` | App 未完成商务审核 | 完成 App Review 并展示 Interaction 流程 |
| `(#190) Access token has expired` | token 过期 | 刷新/续期 Long-lived token |

### 2.9 标签的「锚点与展示」原理

打标签在图片上通常是给一个商品「锚点坐标」，用户点击该点或点「查看商品」进入浮层。但这个坐标**不是必填的**（很多打法不给坐标，整图都可点，或系统自动放置）。工程上不必纠结像素坐标，重点是 `product_id` 与 `media_id` 的关联正确、商品可见。

```
展示决策树（某商品标签是否在受众端可见）
商品标签可见 ?
├── 否：商品 availability != in stock（已售罄/下架）
├── 否：目录被解绑 / 账号购物被禁用
├── 否：media 被删 / 被设置为私有
├── 否：标签数量超上限被截断
├── 否：地区不支持打标
└── 是：商品在 PDP 可购（Native）或可跳站（External）
```

### 2.10 数据同步：库存 / 价格的最终一致性

这是「运营最痛的点」。目录为单一数据源，但 IG 侧商品展示、标签快照是**冗余副本**，同步是最终一致的，且有延迟。

```
Catalog(权威) ──同步──► IG/展示（副本，秒~分钟级延迟）
    │  改价 / 改库存 / 上/下架
    ▼
发生「同步事件」→ 排队 → 传播到 IG 商品详情/标签快照 → 回读验证
```

**同步延迟的常见量级（经验值，非保证）：**

| 变更类型 | 典型延迟 | 表现 |
| --- | --- | --- |
| 改价格 | 秒~分钟 | PDP 价格滞后 |
| 改库存（in/out of stock） | 分钟 | 标签可能短暂仍显示可购 |
| 上/下架商品 | 分钟~小时 | 商品从商店消失需时间 |
| 删标签（API DELETE） | 秒~分钟 | 需回读确认真正消失 |
| 新增商品 | 分钟 | 打标候选列表延迟出现 |

**规避方案**：任何「改了目录就以为 IG 同步」的判断都是错的。流程必须是：**写 Catalog → 轮询 Job/Batch 至终态 → 再回读 IG 侧资源确认**。对价格类变更，设一个「漂移校订」任务（每小时/每晚对账 catalog 与 IG 展示）。

### 2.11 审核流程与账号状态机（Shopping 审核如何流转）

开通/恢复 Shopping 是一个带状态的异步流程。理解状态机能帮你定位「卡在哪一步」。

```
Shopping 启用状态机（概念简化）
[未启用]
   ▼  提交开通（绑目录、填设置、过资格检查）
[审核中 Pending Review]
   ▼  48h ~ 数天（视排队与政策风吹草动）
[已启用 Enabled]
   ├── 正常打标 / 商店可见
   ▼  触发重新审核的事由（改域名/改目录/被投诉/政策变化）
[需重新审核 Re-review / 被停用 Disabled]
   ▼  修正 → 重新提交
[复审中 …] → [Enabled]
```

**常见重新审核触发点**：换落地域名、目录换了主营品类、账号被举报售假、图片违规、Checkout 结账方式切换。

**审核被拒的常见根因（见第四部分深度排查）**：
- 商品/品类属平台限制类目（成人、处方药、仿冒、虚拟货币、医疗保健品等）；
- 图片质量/数量不达标、描述与实物不符、价格严重离谱（诱导欺诈）；
- 落地页域名与 BM 验证不一致、落地页无法购买或残缺；
- 账号历史违规（售假、刷量、封号记录）未清零；
- 地区不支持但账号伪装开启。

### 2.12 商品上架字段「合规审核清单」

下面的字段不仅是 Catalog 的通用字段，更是**能否在 IG 打标/过审核**的硬性门槛，逐条过：

| 字段 | 是否必填 | IG 侧审核关注点 |
| --- | --- | --- |
| `title` | ✅ | 真实、无夸大/诱导词 |
| `description` | 建议 | 合规、不含禁词 |
| `image_url` | ✅（第一张图为主图）| HTTPS、可访问、清晰、无水印误导、无文字堆砌 |
| `additional_image_urls` | 可选 | ≤ 一定张数，质量一致 |
| `price` / `currency` | ✅ | 货币受支持、价格合理、与落地页一致 |
| `availability` | ✅ | in stock 才能打标（out_of_stock 标签隐藏） |
| `condition` | ✅ | new/refurbished/used |
| `link` | ✅（External 必需）| 域名需在 BM 验证、可购买 |
| `brand` / `gtin` / `mpn` | 建议 | 一致性、打假凭据 |
| `product_type` / `custom_label_*` | 可选 | 分组与广告用 |
| `retailer_id` | 建议 | 外部商品 ID，Pixel content_ids 对应它 |

> **规避**：目录字段值随意、图片占用外部不可达 CDN、`link` 指向未验证域名，是「商品目录里好好的但 IG 就是不给打标/商店空白」的高频元凶。

---

## 三、生产环境实战

这是本文档的第二个重点。我们从「真正把它上线」的角度，给出一套可复制的操作清单与代码。

### 3.1 前置准备清单（开工前先对照）

```
前置 checklist（缺一不可）
□ IG 账号已切成「商业账号」(Business)
□ 有 Metilda/BM（业务组合）可访问该 IG 账号
□ 选择合适的结账方式（见 §2.4）：
     - 中国大陆/据外独立站商家 → 基本只能 External
     - 海外主体 + 希望站内购买 → 评估 Native
□ 若是 External：
     - 已验证落地域名（BM 域名验证）
     - Pixel 已建好并埋点（ViewContent/AddToCart/InitiateCheckout/Purchase）
□ 商品数据（SKU、价格、库存、图片）准备好，可导出为目录内容
□ 图源 URL 稳定可访问（HTTPS、无防盗链）
□ 决定接入方式：手动（Magicical UI）/ 半自动（IG API）/ 全自动（Commerce API）
```

### 3.2 开通 Instagram Shopping 分步指南

#### Step 1：确认 IG 是商业账号

IG App → 设置 → 账号类型 → 切换到专业账号 → 选「商业」。若账号本身还是个人号，购物选项不会出现。

#### Step 2：在 BM 创建（或复用）商品目录

商务管理平台（business.facebook.com/commerce 或业务设置 → 数据源）→ 商品目录 → 创建目录 → 选类型（**电商**）→ 选数据源（手动 / 数据Feed / Pixel / API）。

```
数据源选型对照
┌─────────────────────────────────┬──────────────────────────┐
│ 数据源                           │ 适用                       │
├─────────────────────────────────┼──────────────────────────┤
│ 手动上传 (Manual)              │ 少量 SKU，起步验证          │
│ 商品数据 Feed (TSV/XML/JSON)   │ 批量、定期同步、自建站主流    │
│ Pixel（商品页面自动收集）       │ 装上 Pixel 后自动学习商品     │
│ API（Commerce API 增删改查）    │ 全自动、实时、脚本/业务系统   │
│ Shopify 官方渠道 App            │ Shopify 商家零代码           │
└─────────────────────────────────┴──────────────────────────┘
```

#### Step 3：把目录绑定到 IG 商业号

- **方式 A（IG App 内）**：设置 → 购物 → 选目录。
- **方式 B（BM）**：业务设置 → Instagram → 选账号 → 关联目录。
- **方式 C（API 验证）**：

```python
# scripts/meta_api.py 中新增/复用方法示例
def meta_list_instagram_shopping_products(ig_user_id: str, access_token: str) -> list[dict]:
    """列出绑定到当前 IG 商业号的目录及其商品数（用于验证绑定是否生效）。"""
    from scripts.meta_api import MetaAPI
    api = MetaAPI({"access_token": access_token})
    resp = api.request(
        "GET",
        f"/{ig_user_id}/shopping_product_catalogs",
        params={"fields": "id,name,product_count", "access_token": access_token},
    )
    return resp.data.get("data", [])
```

#### Step 4：提交商店开通审核

在商务管理平台的「商店/购物」里提交，等待审核（常见 48h~数天）。审核期间**不要反复改目录/域名**，否则会打断排队。

#### Step 5：验证商店可打标、可结账

发布一条测试帖，手动/API 打一个商品标签，确认：受众端能看到标签；点进去 PDP 正常；External 能跳转页面并完成测试下单（Native 走完支付测试）。

### 3.3 商品上架与库存管理（Commerce API 实战）

#### 3.3.1 在目录里新增商品

```python
# scripts/meta_api.py 已有方法示例：meta_add_products
def meta_add_products(catalog_id: str, products: list[dict], access_token: str) -> dict:
    """
    向 catalog 批量新增商品。
    参数逐条说明：
      - catalog_id: 目录 ID
      - products:   商品列表，每项含
          retailer_id         外部商品ID（建议，用于 Pixel content_ids 对应）
          name / title        商品名称（必填）
          description         描述
          image_url           主图 HTTPS（必填）
          additional_image_urls   附图（列表）
          price + currency    价格与币种（必填，货币需受支持）
          availability        in stock / out of stock / preorder / backordered
          condition           new / refurbished / used
          link                落地页 URL（External 必需）
          brand / gtin / mpn  品牌 / 条形码 / 厂商号
          google_product_category  谷歌商品分类（可选，辅助投放）
          custom_label_0..4   自定义分组
    """
    from scripts.meta_api import MetaAPI
    api = MetaAPI({"access_token": access_token})
    single = products[0] if len(products) == 1 else None
    if single:
        # 单条商品新增
        return api.request("POST", f"/{catalog_id}/products", params={"access_token": access_token, **single}).data
    # 批量：走异步批次（返回 batch_id，需轮询）
    batch = api.request("POST", f"/{catalog_id}/products/batch", params={"access_token": access_token}, json={"items": products})
    return batch.data
```

对应的 **curl**：

```bash
# 单条新增商品
curl -X POST "https://graph.facebook.com/v22.0/{catalog_id}/products" \
  -H "Content-Type: application/json" \
  -d '{
    "access_token": "IG_TOKEN_OR_SYSTEM_TOKEN",
    "retailer_id": "SKU-00123",
    "name": "Ryan 联名帆布托特包",
    "description": "16 安士帆布，防水涂层，可背可拎",
    "image_url": "https://cdn.ryan-store.com/p1.jpg",
    "additional_image_urls": "[\"https://cdn.ryan-store.com/p1b.jpg\"]",
    "price": "299.00",
    "currency": "USD",
    "availability": "in stock",
    "condition": "new",
    "link": "https://buy.ryan-store.com/products/sku-00123",
    "brand": "Ryan Studio",
    "gtin": "0698712345678"
  }'

# 批量新增（异步批次）
curl -X POST "https://graph.facebook.com/v22.0/{catalog_id}/products/batch" \
  -H "Content-Type: application/json" \
  -d '{"access_token":"TOKEN","items":[{"retailer_id":"A","name":"商品A","image_url":"...","price":"10.00","currency":"USD","availability":"in stock"},{"retailer_id":"B","name":"商品B","image_url":"...","price":"20.00","currency":"USD","availability":"in stock"}]}'
```

#### 3.3.2 列出目录商品

```python
def meta_list_catalog_products(catalog_id: str, access_token: str, limit: int = 100, after: str = None) -> list[dict]:
    """分页列出目录商品。支持 limit 与 cursor 翻页。"""
    from scripts.meta_api import MetaAPI
    api = MetaAPI({"access_token": access_token})
    params = {"fields": "id,retailer_id,name,price,currency,availability,condition,image_url,link",
              "limit": limit, "access_token": access_token}
    if after:
        params["after"] = after
    return api.request("GET", f"/{catalog_id}/products", params=params).data.get("data", [])
```

```bash
curl -G "https://graph.facebook.com/v22.0/{catalog_id}/products" \
  --data-urlencode "fields=id,retailer_id,name,price,currency,availability,condition,image_url,link" \
  --data-urlencode "limit=100" \
  --data-urlencode "access_token=TOKEN"
```

#### 3.3.3 商品状态变更（改价 / 改库存 / 下架）

改价/改库存是高频操作，走商品更新：

```bash
# 更新单个商品（改价格 + 库存）
curl -X POST "https://graph.facebook.com/v22.0/{product_id}" \
  --data-urlencode "price=259.00" \
  --data-urlencode "currency=USD" \
  --data-urlencode "availability=in stock" \
  --data-urlencode "access_token=TOKEN"

# 下架（置为 discontinued 会使其标签失效并从商店移除）
curl -X POST "https://graph.facebook.com/v22.0/{product_id}" \
  --data-urlencode "availability=discontinued" \
  --data-urlencode "access_token=TOKEN"

# 删除商品（彻底移除）
curl -X DELETE "https://graph.facebook.com/v22.0/{product_id}?retailer_id=SKU-00123&access_token=TOKEN"
```

> **重要语义**：
> - `availability=out of stock`：商品仍在目录，PDP 显示「缺货」，**已打标签自动隐藏**。
> - `availability=discontinued`：商品作废，视为下架。
> - `DELETE`：彻底移除，历史标签一并失效。
> - 库存变更是**异步最终一致**，变更后需轮询 `GET /{catalog_id}/products` 确认，再回读 IG 侧。

#### 3.3.4 批次（Batch）与作业状态查询

批量上架/改价走异步批次，必须轮询进度与逐条错误：

```python
def meta_list_catalog_batches(catalog_id: str, access_token: str) -> list[dict]:
    """列出目录最近的异步批次作业（新增/更新商品）。"""
    from scripts.meta_api import MetaAPI
    api = MetaAPI({"access_token": access_token})
    return api.request("GET", f"/{catalog_id}/batches", params={"access_token": access_token}).data.get("data", [])

def meta_get_catalog_batch(batch_id: str, access_token: str) -> dict:
    """查询单个批次的执行进度与逐条错误（含 request_successful / error）。"""
    from scripts.meta_api import MetaAPI
    api = MetaAPI({"access_token": access_token})
    return api.request("GET", f"/{batch_id}", params={"fields": "status,handles,error_summary", "access_token": access_token}).data
```

```bash
# 创建批次（生产环境推荐，可逐条回传错误）
curl -X POST "https://graph.facebook.com/v22.0/{catalog_id}/products/batch" \
  -H "Content-Type: application/json" \
  -d '{"access_token":"TOKEN","items":[{...},{...}]}'
# 返回 {"batch_id": "..."}

# 查询批次状态
curl -G "https://graph.facebook.com/v22.0/{batch_id}" \
  --data-urlencode "fields=status,handles,error_summary" \
  --data-urlencode "access_token=TOKEN"
```

批次状态机：`IN_PROGRESS` → `COMPLETED` / `FAILED`；`handles` 里每条 handle 有 `request_successful` 与 `error` 字段（含错误码与商品 retailer_id），用于对账「哪些 SKU 成功、哪些失败、为什么」。

#### 3.3.5 与 Shopify / Magento 集成（真实场景）

**Shopify 商家（推荐零代码）**：
- 安装官方 **Instagram Shopping（IG Shopping）销售渠道**，完成授权后 Shopify 自动把商品库推送到 Catalog，库存/价格自动同步，且自动生成 `commerce` 集合。
- 追责点：Shopify 用其自有映射，商品 `availability` 由 Shopify 库存驱动；禁用「继续销售已售罄商品」时，缺货标签会自动隐藏。

```
Shopify 集成数据流
[Shopify Admin 商品库]
      │  IG Shopping 销售渠道（App）自动同步
      ▼
[Meta Catalog（由 Shopify 自动填充/更新）]
      │
      ├── 绑定到 IG 商业号 → 可打标/商店
      └── 供 DPA / Shopping Ads 使用
```

**Magento 自建站商家（需要自己接）**：
- 没有「一键」渠道，走 **Commerce API 或数据 Feed**。
- 常见做法：Magento 后台出一个 TSV/JSON Feed（含 retailer_id、name、price、inventory、image、link），定时（cron 每小时）上传到 Catalog；或用脚本调 Commerce API 逐条/批更新。

```
Magento 集成数据流
[Magento 商品表 (catalog_product + inventory)]
      ▼  脚本导出 Feed 或调 API
[管线：映射字段 → 生成商品负载]
      ▼  POST /{catalog_id}/products/batch（增量）或 Feed 全量
[Meta Catalog]
      ▼ 绑定 IG
[IG 可购物内容 / 商店]
```

**同步延迟的教训**：无论是 Shopify 还是 Magento，价格/库存波动导致的标签闪现在所难免。建议把「对账任务」（比对 catalog 与 IG 侧快照）放进每日 cron，配合 `distill`/`kb_health_check` 这类巡检思路，尽早发现漂移。

### 3.4 创建 Shoppable Posts（打标签实战）

#### 3.4.1 手工打标（运营兜底）

在 IG App 发布图片/Reels 时点「标记商品」，从绑定目录选商品即可。适合：零星内容、KOL 合作内容、需要人工把关的素材。注意标签数量上限与商品库存状态。

#### 3.4.2 API 打标（规模化）

```python
# scripts/meta_api.py 新增示例：给单条 media 打一个商品标签
def meta_tag_media_product(media_id: str, product_id: str, access_token: str) -> dict:
    """给已发布的 media 打上商品标签。
    约束：
      - media 必须是已发布（非草稿）；
      - product 必须属于绑定到该 IG 商业号的目录；
      - 打标是异步的，需用 GET /{media_id}/product_tags 回读确认最终落库。
    """
    from scripts.meta_api import MetaAPI
    api = MetaAPI({"access_token": access_token})
    return api.request(
        "POST",
        f"/{media_id}/product_tags",
        params={"product_id": product_id, "access_token": access_token},
    ).data

def meta_untag_media_product(media_id: str, product_id: str, access_token: str) -> dict:
    """移除 media 上的某个商品标签。"""
    from scripts.meta_api import MetaAPI
    api = MetaAPI({"access_token": access_token})
    return api.request(
        "DELETE",
        f"/{media_id}/product_tags",
        params={"product_id": product_id, "access_token": access_token},
    ).data

def meta_list_media_product_tags(media_id: str, access_token: str) -> list[dict]:
    """列出某条 media 上已打的商品标签，含商品快照字段。"""
    from scripts.meta_api import MetaAPI
    api = MetaAPI({"access_token": access_token})
    params = {"fields": "product_id,product_name,product_price,image_url",
              "access_token": access_token}
    return api.request("GET", f"/{media_id}/product_tags", params=params).data.get("data", [])
```

```bash
# 给帖子打标签
curl -X POST "https://graph.facebook.com/v22.0/{ig-media-id}/product_tags" \
  --data-urlencode "product_id=610318248591203" \
  --data-urlencode "access_token=TOKEN"

# 查帖子上的标签
curl -G "https://graph.facebook.com/v22.0/{ig-media-id}/product_tags" \
  --data-urlencode "fields=product_id,product_name,product_price,image_url" \
  --data-urlencode "access_token=TOKEN"

# 移除标签
curl -X DELETE "https://graph.facebook.com/v22.0/{ig-media-id}/product_tags" \
  --data-urlencode "product_id=610318248591203" \
  --data-urlencode "access_token=TOKEN"
```

#### 3.4.3 轮播批量打标工具函数

轮播的每张 Card 是独立 media（子节点），需遍历 children：

```python
def meta_tag_carousel(carousel_id: str, product_by_card: dict[int, list[str]], access_token: str) -> dict:
    """
    给轮播的每张卡片打上各自商品标签。
    product_by_card = {卡片索引: [product_id, ...]}，索引从 0 开始。
    实际 api 通过 GET /{carousel_id}/children 取各子 media_id 再逐卡打标。
    """
    from scripts.meta_api import MetaAPI
    api = MetaAPI({"access_token": access_token})
    children = api.request("GET", f"/{carousel_id}/children",
                           params={"fields": "id", "access_token": access_token}).data.get("data", [])
    results = {}
    for idx, child in enumerate(children):
        media_id = child["id"]
        for pid in product_by_card.get(idx, []):
            results[f"{idx}:{pid}"] = api.request(
                "POST", f"/{media_id}/product_tags",
                params={"product_id": pid, "access_token": access_token}).data
    return results
```

#### 3.4.4 全品类素材盘点（某商品被哪些帖子打过标）

```python
def meta_where_products_tagged(ig_user_id: str, product_id: str, access_token: str) -> list[dict]:
    """反查某商品被哪些 media 打过标签（用于素材审计/误标排查）。"""
    from scripts.meta_api import MetaAPI
    api = MetaAPI({"access_token": access_token})
    return api.request(
        "GET", f"/{ig_user_id}/product_tags",
        params={"product_id": product_id, "fields": "media_id,caption,permalink",
                "access_token": access_token},
    ).data.get("data", [])
```

```bash
curl -G "https://graph.facebook.com/v22.0/{ig-user-id}/product_tags" \
  --data-urlencode "product_id=610318248591203" \
  --data-urlencode "fields=media_id,caption,permalink" \
  --data-urlencode "access_token=TOKEN"
```

> **打标最佳实践**：
> 1. 上线前选「在商品目录里且 in stock」的商品做候选，避免打上去就因缺货隐藏；
> 2. 打标后**回读**确认，而不是 POST 返回就完事；
> 3. 用 retailer_id 建立与 SKU 系统的映射，避免对账时 ID 对不上；
> 4. 标签上限即将达到时，优先保留「高转化」主推商品，删除低效标签。

### 3.5 标签管理（Tagging 权限 / 批量 / 联动）

#### 3.5.1 Tagging 权限矩阵

| 角色 | 打标签 | 删标签 | 管理 Catalog | 审批商店 | 处理订单 |
| --- | --- | --- | --- | --- | --- |
| IG 账号管理员 | ✅ | ✅ | 取决于 BM | ✅ | ✅（Native） |
| BM Business Admin | ✅（多数） | ✅ | ✅ | ✅ | ✅ |
| BM Business Editor | ✅ | ✅ | ✅ | ⚠️ 部分 | ✅ |
| Media 作者（运营号） | ✅ | ✅ | ❌ | ❌ | ❌ |
| Advertiser / Analyst | ❌（一般） | ❌ | ❌ | ❌ | ❌ |

**实战提醒**：若脚本以「运营账号 token」打标而该账号连目录查看权都没有，会报 commerce 权限错误。把「持有目录权限的 BM 系统用户 token」设为打标凭证是更稳的姿势。

#### 3.5.2 标签的「联动失效」管理

标签不会「永久有效」，它跟随商品与目录状态：

```
标签生命周期
[可用 Active] ──商品缺货/下架/删除──► [失效 Inactive（受众侧隐藏）]
     ▲                                        │
     └──── 商品恢复 in stock ──────────────┘   （若商品还在目录且未删）
   （若商品已被 DELETE：标签彻底移除，无法复活）
```

**联动场景的真实教训**：
- 大促期间 SKU 缺货，一大批标签「凭空消失」，客服收到大量「为什么买不了」——根因是 `availability=out of stock`，标签自动隐藏；
- 解决方案：盘点任务每天扫一遍「已打标商品的 availability」，缺货的提前在文案里说明或换标签，避免挂空。

#### 3.5.3 批量清标 / 重标项目

```python
def meta_rebuild_tags(ig_user_id: str, media_batch: list[str], product_map: dict[str, list[str]],
                      access_token: str) -> dict:
    """
    批量重建标签：先清空再按 product_map 重打。
    product_map = {media_id: [product_id,...]}
    该函数仅供演示编排思路，生产应加入限速与指数退避，并逐条回读确认。
    """
    from scripts.meta_api import MetaAPI
    api = MetaAPI({"access_token": access_token})
    out = {"cleared": 0, "tagged": 0, "errors": []}
    for mid in media_batch:
        # 1) 清空该 media 现有标签
        existing = api.request("GET", f"/{mid}/product_tags",
                               params={"fields": "product_id", "access_token": access_token}).data.get("data", [])
        for t in existing:
            api.request("DELETE", f"/{mid}/product_tags",
                        params={"product_id": t["product_id"], "access_token": access_token})
            out["cleared"] += 1
        # 2) 打上新标签
        for pid in product_map.get(mid, []):
            try:
                api.request("POST", f"/{mid}/product_tags",
                            params={"product_id": pid, "access_token": access_token})
                out["tagged"] += 1
            except Exception as e:
                out["errors"].append({"media": mid, "product": pid, "error": str(e)})
    return out
```

### 3.6 Collections（商品集合）管理实战

```python
# scripts/meta_api.py 已有/新增示例
def meta_list_collection_cards(ig_user_id: str, access_token: str) -> list[dict]:
    """列出该 IG 商业号的商店商品集合（橱窗卡），含名称与商品数。"""
    from scripts.meta_api import MetaAPI
    api = MetaAPI({"access_token": access_token})
    return api.request("GET", f"/{ig_user_id}/collections",
                       params={"access_token": access_token}).data.get("data", [])

def meta_create_collection_card(ig_user_id: str, name: str, product_id: str,
                                access_token: str) -> dict:
    """创建商品集合（首个商品必填，创建后可用 PUT 再加商品）。"""
    from scripts.meta_api import MetaAPI
    api = MetaAPI({"access_token": access_token})
    return api.request("POST", f"/{ig_user_id}/collections",
                       params={"name": name, "product_id": product_id,
                               "access_token": access_token}).data
```

```bash
# 列出集合
curl -G "https://graph.facebook.com/v22.0/{ig-user-id}/collections" \
  --data-urlencode "access_token=TOKEN"

# 创建集合
curl -X POST "https://graph.facebook.com/v22.0/{ig-user-id}/collections" \
  --data-urlencode "name=夏季精选" \
  --data-urlencode "product_id=610318248591203" \
  --data-urlencode "access_token=TOKEN"

# 查看集合内商品
curl -G "https://graph.facebook.com/v22.0/{collection-id}/products" \
  --data-urlencode "fields=id,name,image_url,price" \
  --data-urlencode "access_token=TOKEN"

# 向集合加商品
curl -X PUT "https://graph.facebook.com/v22.0/{collection-id}/products" \
  --data-urlencode "product_id=610318248591204" \
  --data-urlencode "access_token=TOKEN"

# 从集合移除商品
curl -X DELETE "https://graph.facebook.com/v22.0/{collection-id}/products" \
  --data-urlencode "product_id=610318248591204" \
  --data-urlencode "access_token=TOKEN"
```

**集合运营要点**：
- 集合是「商店的陈列组织」，改集合不会即刻同步到 App，需等待传播并回读；
- 空集合、重名集合、封面不达标的集合不会出现在商店 Tab；
- 「全部商品」是兜底视图，未归类的商品也会展示——不想展示的品要主动下架而不是指望「不归类就不显示」。

### 3.7 三种典型业务场景拆解

#### 场景 A：Shopify 店铺接入（最快路径）

```
步骤
1. IG 商业账号 + BM 就绪
2. Shopify 后台安装 IG Shopping 销售渠道 → 授权 Meta
3. 选结账方式：
     - 中国大陆主体间接账方式受限，多数 External
     - 或评估 Native（需开放区域 + 主体）
4. 设域名验证 + Pixel（External 必需）
5. Shopify 自动同步 Catalog → 绑定 IG → 发帖打标 → 商店可见
```

关键点：几乎零代码，但**受 Shopify↔Meta 映射控制**；想要更自由的营销字段（custom_label、product_type）需要走 Commerce API 或额外配置。

#### 场景 B：Magento 自建站接入（最可控）

```
步骤
1. IG 商业账号 + BM + 域名验证 + Pixel
2. 建目录（若已有则复用）
3. 写同步脚本：
     - 从 Magento 取 SKU/价格/库存/图/链接
     - 映射字段 → 组装商品负载
     - POST /{catalog_id}/products/batch 增量同步
     - 轮询批次至 COMPLETED
4. 绑定目录到 IG → 提交商店审核
5. 运营发帖 → API 打标（meta_tag_media_product）
6. 每日对账任务校准库存/价格与标签
```

```
Magento → IG 同步主循环（伪代码）
while True:
    rows = fetch_magento_products(changed_since=last_run)
    if rows:
        batch_id = meta_add_products(catalog_id, [map_to_payload(r) for r in rows], token)
        wait_settle(batch_id)
    reconcile_tags(ig_user_id, token)      # 清理失效标签、补齐缺失标签
    reconcile_inventory(ig_user_id, token) # 校准价格/库存快照
    sleep(3600)
```

#### 场景 C：动态广告 + 购物联动（投放协同）

```
链路
[Catalog 单一数据源]
   ├── 到 IG：可购物内容 / 商店（本文主题）
   └── 到广告：DPA / Shopping Ads / Collection Ads
           │ 用 Collection / Product Set 做商品分组
           ▼
[受众点击广告] → 落到可购物帖子/PDP → 结账
```

要点：Catalog 的字段质量（图、价、库存、custom_label）同时决定**购物体验**与**广告 ctr/cvr**，一套数据源两处受益。用 `meta_list_dynamic_product_sets` 管理分组并复用为商店 Collection 的思路，能减少「广告组」与「商店陈列」两套孤岛。

```python
def meta_list_dynamic_product_sets(catalog_id: str, access_token: str) -> list[dict]:
    """列出目录下的动态/自定义商品集（供广告与商店分组复用）。"""
    from scripts.meta_api import MetaAPI
    api = MetaAPI({"access_token": access_token})
    return api.request("GET", f"/{catalog_id}/product_sets",
                       params={"fields": "id,name,product_count,filter",
                               "access_token": access_token}).data.get("data", [])
```

### 3.8 监控：IG 账号 / 商店 / 内容 Insights

```python
def meta_list_instagram_accounts(bm_id: str, access_token: str) -> list[dict]:
    """列出 BM 下已连接 / 授权的 Instagram 商业账号（用于盘点可购物账号）。"""
    from scripts.meta_api import MetaAPI
    api = MetaAPI({"access_token": access_token})
    # 通过 business / connected instagram accounts 端点
    return api.request("GET", f"/{bm_id}/client_instagram_accounts",
                       params={"fields": "id,username,name,profile_picture_url",
                               "access_token": access_token}).data.get("data", [])
```

**监控指标（IG Insights / Commerce Insights）**：

| 维度 | 关键指标 | 说明 |
| --- | --- | --- |
| 内容互动 | impressions / reach / engagement | 可购物内容的曝光与互动 |
| 引流 | taps / saves / profile_visits | 商品点击次数是核心 CTR 指标 |
| 转化 | product clicks / checkouts（Native）/ purchase 事件（External） | 看实际结账 |
| 经营 | orders / GMV / returns（Native） | 订单视角 |

**采样端点**（示意）：

```
GET /{ig-media-id}/insights?metric=impressions,reach,engagement,saved
GET /{ig-user-id}/insights?metric=...
GET /{ig-user-id}/shopping_orders （Native 订单，供对账）
```

> **口径坑**：Native 结账的订单量来自 `shopping_orders`；External 的「购买」完全依赖 Pixel/CAPI 的 `Purchase` 事件与 `content_ids` 对齐。两者的「销售额」口径不同，汇总报表时要么分开列要么口径统一，不要在总表里混算。

---
### 3.9 商品对象逐字段参数说明（CCPA/Graph API 用于调用的完整清单）

下表把 `POST /{catalog_id}/products` / 商品更新时可用的参数逐条展开，供代码与配置文件直接对照：

| 参数 | 类型 | 必填 | 说明 | 校验/约束 |
| --- | --- | --- | --- | --- |
| `id`/`product_id` | string | 更新时必填 | 由目录返回的内部 ID | 读接口返回，勿手写 |
| `retailer_id` | string | 强烈建议 | 外部商品唯一键（可含字母数字） | 用于 Pixel content_ids 对应与幂等 |
| `name` / `title` | string | ✅ | 商品名称 | 1-130 字符，避免夸大诱导词 |
| `description` | string | 建议 | 商品描述 | 合规、无禁词，建议 500 字内 |
| `image_url` | string | ✅ | 主图（HTTPS） | 需可访问、清晰、无营销水印 |
| `additional_image_urls` | list<string> | 可选 | 附图 | 数量与质量与主图一致 |
| `video_url` | string | 可选 | 商品视频 | 部分场景支持 |
| `price` | string | ✅ | 最终售价（含小数）  | 与 currency 共同作为字符串提交 |
| `currency` | string | ✅ | ISO 4217 币种 | 需在受支持列表内 |
| `sale_price` | string | 可选 | 促销价 | 需 < price |
| `availability` | enum | ✅ | `in stock`/`out of stock`/`preorder`/`backordered`/`discontinued` | 影响标签与商店展示（见 §3.5.2） |
| `condition` | enum | ✅ | `new`/`refurbished`/`used` | 按售卖状态如实填 |
| `brand` | string | 建议 | 品牌 | 一致性与打假凭据 |
| `gtin` | string | 建议 | EAN/UPC/ISBN | 标准长度，用于打假 |
| `mpn` | string | 建议 | 制造商零件号 | 与 gtin 互补 |
| `link` | string | External 必填 | 落地购买页 URL | 域名需在 BM 验证 |
| `email_notification_for_errors` | string | 可选 | 错误通知收件邮箱 | 批次失败时收告警 |
| `google_product_category` | string | 可选 | 谷歌商品分类 | 辅助投放匹配 |
| `product_type` | string | 可选 | 自定义商品类型（层级） | 分组/店铺陈列 |
| `custom_label_0..4` | string×5 | 可选 | 自定义标签 | 广告分组（每套 5 个） |
| `origin_country` | string | 可选 | 原产地（部分跨境） | 合规披露 |
| `importer_name`/`importer_address` | string | 可选 | 进口商信息（部分地区） | 跨境合规 |
| `commerce_tax_category` | enum | 可选 | 税收品类（Native 结账） | 影响计税 |

> **提交细节**：`price`/`currency` 作为「字符串」成对提交（如 `"price":"299.00","currency":"USD"`），不要混用数字类型；`additional_image_urls` 以 JSON 数组字符串传入。

### 3.10 分页、限流与重试（规模化脚本的必修课）

#### 3.10.1 分页（Cursor 分页）

列表类端点（目录商品、product_tags、collections、shopping_orders）返回分页：

```json
{
  "data": [ ... ],
  "paging": {
    "cursors": { "before": "...", "after": "..." },
    "next": "https://graph.facebook.com/v22.0/...?...&after=..."
  }
}
```

```python
def meta_get_all_catalog_products(catalog_id: str, access_token: str) -> list[dict]:
    """用 cursor 翻完整个目录商品列表（注意大目录的内存与限流）。"""
    from scripts.meta_api import MetaAPI
    api = MetaAPI({"access_token": access_token})
    out, after = [], None
    while True:
        params = {"fields": "id,retailer_id,name,price,currency,availability,condition,image_url,link",
                  "limit": 100, "access_token": access_token}
        if after:
            params["after"] = after
        data = api.request("GET", f"/{catalog_id}/products", params=params).data
        out.extend(data.get("data", []))
        nxt = (data.get("paging") or {}).get("cursors", {}).get("after")
        if not nxt or nxt == after:
            break
        after = nxt
    return out
```

#### 3.10.2 限流与退避

Graph API 有应用级与调用级限流。规模化脚本请遵循：

```
限流应对策略
1. 小步批量：每批 ≤ N 条（如 50-100）
2. 指数退避：失败（#4 / 429 / 超时）→ 等待 2^n 秒（上限如 60s）
3. 异步批次：大批量一律走 batch，避免并发 POST 打爆限流
4. 串行化重试：对失败项单独重发，不整批重跑
5. 记录 usage：读响应里的 X-App-Usage / rate_limit 字段做预算
```

```python
import time, random

def meta_retry(fn, max_attempts=5, base_wait=2.0, max_wait=60.0):
    """带指数退避与抖动（jitter）的重试包装。"""
    for attempt in range(1, max_attempts + 1):
        try:
            return fn()
        except Exception as e:
            if attempt == max_attempts:
                raise
            wait = min(base_wait * (2 ** (attempt - 1)), max_wait) * (0.5 + random.random())
            time.sleep(wait)
    raise RuntimeError("unreachable")
```

#### 3.10.3 幂等设计

- **目录商品**：用 `retailer_id` 作唯一键。重复提交同一 retailer_id 的后果与行为要确认（多数是更新而非新建），否则对账时会出现「重复/被覆盖」。
- **集合创建**：`POST /{ig-user-id}/collections` 无天然幂等，先在调用前 `GET /{ig-user-id}/collections` 查重，避免每跑一次 cron 生成一个同名集合。
- **打标**：`POST /{media-id}/product_tags` 同一 (media, product) 重复提交，多数幂等无害；但仍以回读 `GET /{media-id}/product_tags` 为准。

### 3.11 生产运行架构（把上架→打标→商店→对账做成系统）

```
Instagram Shopping 生产运行架构（建议）
┌─────────────────────────────────────────────────────────┐
│  业务系统（Magento/Shopify/自建 ERP）                     │
│    商品/SKU/库存/价格/图片/落地链接                        │
└──────────────┬──────────────────────────────────────────┘
               │ 同步适配层（映射字段 → 组装商品负载）
               ▼
┌─────────────────────────────────────────────────────────┐
│  同步管线（cron / 消息队列）                              │
│   ├─ 增量同步 → POST /{catalog_id}/products/batch       │
│   ├─ 轮询批次 → GET /{batch_id}                         │
│   ├─ 失败重放（按 retailer_id）                          │
│   └─ 对账任务（校准 availability/价格/标签）              │
└──────────────┬──────────────────────────────────────────┘
               │ 绑定目录到 IG 已由商务侧完成
               ▼
┌─────────────────────────────────────────────────────────┐
│  IG 侧能力（Graph API + Commerce UI）                    │
│   ├─ 可购物内容（打标 media / Reels）                    │
│   ├─ 商店（Collections / Shop Tab）                      │
│   └─ 结账（Native 订单 / External 落地+Pixel）            │
└──────────────┬──────────────────────────────────────────┘
               │ 数据回流
               ▼
┌─────────────────────────────────────────────────────────┐
│  监控/报表                                                │
│   ├─ IG Insights（互动/点击/留存）                       │
│   ├─ Commerce Insights（订单/GMV/退款, Native）           │
│   └─ Pixel/CAPI（External 归因与再营销）                  │
└─────────────────────────────────────────────────────────┘
```

**落地建议**：
- 用 `scripts/meta_api.py`、`scripts/ad_platform_api.py` 封装统一凭证与请求，业务方不直接拼 URL；
- 把「批次轮询 / 分页 / 退避 / 幂等」做成公共工具，避免各脚本重复实现出错；
- 建一张对账表：`retailer_id ↔ catalog product_id ↔ IG 可见性`，每日比对，漂移即告警。

### 3.12 地区 / 货币 / 品类可用性矩阵（决策表）

写系统前先按「地区 × 结账方式 × 币种」三维度确认，避免上线后再重构：

| 决策维度 | 主要影响 | 需确认点 |
| --- | --- | --- |
| 结账国家 | Native 是否可用 | 是否在开放结账国家列表 |
| 结算币种 | PDP/结账币别 | catalog `currency` 是否受支持且一致 |
| 商品品类 | 打标/审核/结账可行 | 是否平台受限品类 |
| 账号主体 | Checkout 准入 | 海外主体 vs 大陆主体的差异 |
| 内容形态 | 打标能力 | 图片/轮播/Reels/Stories/直播各自支持度 |
| 数据源 | 同步方式 | Feed / Pixel / API / Shopify 渠道 |
| 开票方 | 税务合规 | 对应结算/退货责任 |

**决策建议**：
- 不确定走哪条路时，**先选 External**（覆盖广、门槛低、独立站可控），后期如需再评估 Native；
- 币种统一用主营结算币（如 USD），避免多币种目录在结账侧的货币错配；
- 品类明确合规后再花成本做 N 刷审核，避免反复被拒消耗排队额度。

### 3.13 Native 结账订单管理实战（Commerce / shopping_orders）

若你的主体走 Native Checkout（海外主体、开放国家），订单管理是重要一环。相关端点与状态机如下。

#### 3.13.1 订单读取

```bash
# 列出该 IG 商业号的结账订单
curl -G "https://graph.facebook.com/v22.0/{ig-user-id}/shopping_orders" \
  --data-urlencode "fields=id,created_time,last_updated,payment_details,shipping_address,cancel_reason,state" \
  --data-urlencode "access_token=TOKEN"

# 单个订单详情
curl -G "https://graph.facebook.com/v22.0/{shopping-order-id}" \
  --data-urlencode "fields=id,created_time,shipping_address,state,payment_details,item_count" \
  --data-urlencode "access_token=TOKEN"

# 订单履约（物流）写入
curl -X POST "https://graph.facebook.com/v22.0/{shopping-order-id}/item_fulfillments" \
  -H "Content-Type: application/json" \
  -d '{"access_token":"TOKEN","shipping_carrier":"DHL","tracking_number":"1234567890"}'

# 订单结算/打款
curl -G "https://graph.facebook.com/v22.0/{ig-user-id}/commerce_payouts" \
  --data-urlencode "fields=id,status,amount,currency,created_time" \
  --data-urlencode "access_token=TOKEN"
```

#### 3.13.2 订单状态机（Native）

```
Native 订单状态机（示意）
CREATED → CONFIRMED → 已支付/待发货 → SHIPPED（填物流） → DELIVERED → COMPLETED
    └─────────── 任意阶段可 CANCELED / 部分 REFUNDED / RETURNED
```

**每级状态都影响报表口径**：只有走到结算完成的才算 GMV；退款要把 `REFUNDED`/`CANCELLED` 单剔除。与 3.8 的「口径统一」呼应，核算时明确按状态过滤。

#### 3.13.3 退款 / 退货处理策略

- 退货政策需在商务管理平台配置，退款流程由商家发起（符合平台规则）。
- 退款会更新订单状态与结算（commerce_payouts），务必让财务侧接入订单状态同步，避免「退了钱但报表没减」。
- 警戒：Native 退款一旦超过政策/频次阈值可能触发风控复核，策略要合规、克制。

### 3.14 Collections 深化：精选 / 排序 / 封面

#### 3.14.1 让集合出现在商店

- 集合需「有合规封面 + 至少若干商品 + 名称不重复」才会上架商店 Tab 卡片。
- 「精选」集合优先展示在商店顶部；未精选的按系统排序出现。

```
商店 Tab 排序示意
[精选 Collection A]   ← 置顶（可手动设精选）
[精选 Collection B]
[其他 Collection]     ← 默认顺序
[全部商品]            ← 兜底
```

#### 3.14.2 封面与卡片的坑

- 商品主图质量影响卡片观感与点击，也影响审核；
- 封面若不达标，该 Collection Card 可能不展示，但「全部商品」仍在——用「全部商品」兜底测试商店是否基本可用。

### 3.15 Reels / 视频购物与直播购物实战

#### 3.15.1 Reels 打标的最佳实践

- Reels 与图片共用 product_tags，但**尽量在创作阶段（发布前）规划好商品位**，发布后窗口有限；
- 用「内容卡点」对应商品位：同一 Reels 展示 A→B→C 三个商品位，符合信息流「卡点+标签」的沉浸感；
- 监控：Reels 的可购物内容用 `insights` 里的 `taps`/`product clicks` 评估带货效率，淘汰低效视频。

```
Reels 带货内容模板（示意）
[前 3s 钩子] → [商品A 卡点+标签] → [对比/痛点] → [商品B 卡点+标签] → [CTA] → [商品C 卡点+标签]
```

#### 3.15.2 Live Shopping（直播购物）要点

- 需主播账号具备 live shopping 功能位 + 行为合规；
- 直播页可一次挂多件商品的商品卡，观众边看边下单；
- 能力与地区限制较严，先确认账号是否「直播购物」可用再排期；
- 复用 Catalog 商品、Native/External 结账各自适用，直播通常更适合 Native（转化即时、跳出低），但要处理发货与退款 SLA。

### 3.16 质量与合规自查（上线前的最后一关）

上线前对照下面清单逐项自测，能显著降低审核被拒与上线后踩坑：

```
□ 目录必填字段齐全，图片 HTTPS 可达、无水印误导
□ 价格/货币一致，sale_price < price
□ availability 与真实库存同步（默许策略：缺货即 out of stock）
□ link 域名已在 BM 验证（External）
□ Pixel 已埋 ViewContent/AddToCart/InitiateCheckout/Purchase（External）
□ 品类无受限项（成人/处方药/仿冒/虚拟货币/医疗等）
□ 结账方式决策已确认（Native / External 二选一）
□ 每帖标签数在平台当前上限内
□ 批量操作走 batch + 轮询 + 幂等
□ 每日对账任务就绪（漂移即告警）
□ 报表口径统一（Native 看 orders / External 看 Pixel）
```

### 3.17 常见人群 / 角色与 BOM（一份「接手即懂」的运营速览）

```
角色分工（建议）
├── 商务管理员（BM Admin）：建目录、绑 IG、过审核、管订单/退款
├── 内容运营（IG 运营号）：发帖、手工打标、Reels 带货
├── 工程/自动化：同步管线、批量打标、对账、报表
└── 广告投放：引用 Catalog/Collection 做 DPA / Shopping Ads

资产管理（谁持有什么）
├── BM：目录、Pixel、广告账户、系统用户 token
├── IG 商业号：媒体、商店、集合、可购物内容
└── 系统侧：SKU↔retailer_id 映射、对账表、密钥保管
```

---

## 四、常见问题与排查

### 4.1 审核被拒（商店/购物开通被拒）

#### 4.1.1 常见被拒根因与对策

| # | 被拒原因 | 根因 | 对策 |
| --- | --- | --- | --- |
| 1 | 商品/品类属平台受限 | 成人、处方药、仿冒品、虚拟货币、医疗保健、枪械、赌博等 | 确认品类合规；移除受限商品后再提交 |
| 2 | 图片质量/合规不达标 | 有水印、文字堆砌、模糊、与描述不符、侵权 | 用高清晰主图，去掉营销水印，保证与实物一致 |
| 3 | 落地页无法购买/残缺 | External 落地页是首页而非商品页、域名未验证、无法下单 | 落地页指向可购买商品页，BM 完成域名验证，测试完整下单 |
| 4 | 价格严重离谱/诱导 | 价格与落地页不一致、虚标、0 元引流 | 价格与 site 一致，杜绝标题党式价格 |
| 5 | 账号历史违规 | 过往售假/刷量/封号记录 | 清理违规资产；申诉或冷启动新合规账号（注意资产复用） |
| 6 | 地区不支持 | 账号主体在非结账开放国使用 Native | 切换 External 结账；差异化地区策略 |

#### 4.1.2 被拒后的正确处理流程

```
被拒 → 不要盲目重提
1. 读拒审原因/政策邮件，定位根因
2. 修复（改品类/图/域名/价格/账号）
3. 等冷却期（避免频繁重提被标「恶意刷审」）
4. 重新提交 → 观察审核状态
5. 仍被拒 → 联系商务支持/代理（Business Support），带上拒审具体提示
```

> **坑**：很多人被拒后马上改域名重提，结果因「落地域名与验证不一致」连环被拒。先想清楚是「品类问题」还是「域名/落地页问题」，对症下药。

### 4.2 标签不显示 / 打不上标签

#### 4.2.1 排查路径（逐层下探）

```
标签不显示 → 按层排查
┌─ 1. 账号层：IG 是否 Business？购物是否 Enabled？地区是否支持打标？
├─ 2. 目录层：目录是否绑定到该 IG？商品是否在该目录？
├─ 3. 商品层：
│     availability 是否 in stock？（out_of_stock 标签隐藏）
│     图片/必填字段是否合规？价格货币是否受支持？
├─ 4. Media 层：
│     是否已发布？是否在可打标窗口？是否超标签上限？
└─ 5. 传播层：变更是否已完成异步传播？回读确认了吗？
```

#### 4.2.2 常见错误码对照表

| 错误片段 | 可能含义 | 处理 |
| --- | --- | --- |
| `(#100) Invalid parameter` | 参数错（如 product_id 格式错误） | 核对 ID 与参数名 |
| `(#100) No commerce permission for this user` | 账号非商业/未绑目录 | 切商业号、绑目录 |
| `(#100) The product does not belong to the catalog` | 商品不在绑定目录 | 核对目录与商品归属 |
| `(#100) Product tagging is not enabled` | 账号未启用购物打标 | 完成开通与审核 |
| `(#100) Media is not published` | 帖子未发布不能打标 | 发布后再打 |
| `(#200) Permission error` | 权限 scope 不足 | 补 `instagram_basic`/`commerce_account_manage` 并重授权 |
| `(#10) ... does not have permission` | App 未过审 | 完成 App Review |
| `(#190) Access token has expired` | token 过期 | 刷新 Long-lived token |
| `(#4) Application request limit reached` | 触发限流 | 增加退避重试 |
| 批次内异常 | 见批次 `error` 字段（如某条 retailer_id 重复） | 按 retailer_id 对账重发 |

#### 4.2.3 标签数量上限与「消失」

- 每帖标签有上限（历史 5 个，2021 后部分账号/地区开放到 20 个）。**打满后新标签会失败**。
- 「标签莫名消失」绝大多数不是 bug，而是**商品 availability 变化 / 商品删除 / 目录解绑 / 账号购物被禁用**导致的联动隐藏。排查顺序：先查商品状态，再查标签。

### 4.3 Checkout（结账）相关问题

| 问题 | 原因 | 处理 |
| --- | --- | --- |
| 结账方式设置里没有「在 Instagram 上结账」 | 地区/品类/主体不满足 Native 准入 | 用 External；确认开放国家 |
| Native 下单时货币不匹配 | 商品 `currency` 与结算币种不一致 | 统一 catalog 币种 |
| Native 审核久久不过 | 品类/退货政策/支付信息不完整 | 补全支付与退货政策后重提 |
| External 跳转后无法购买 | 落地页残缺、域名未验证、错误配置 | 验证域名 + 修正 `link` |
| 订单数据对不上 | Native 看 `shopping_orders`，External 看 Pixel/CAPI | 口径统一、两套分别核对 |
| 无法退款（Native） | 退货政策/退款流程未设置 | 在商务管理平台配置退货政策并走履约流程 |

### 4.4 库存 / 价格同步问题

```
现象：改了库存/价格，IG 侧迟迟不更新
排查：
1. Catalog 侧是否已到终态（轮询 Batch/Job）？
2. 是否传到 IG 侧副本？（再回读 GET /{catalog}/products 或商品详情）
3. 有没有「最终一致」没有完成（对账任务补一次同步）？
4. 数据源是 Feed 的话，Feed 有没有重新上传/被 cron 覆盖成旧值？
```

**经验值**：价格秒~分钟、库存分钟、上下架分钟~小时、标签删/增秒~分钟、新商品分钟级。一切以回读为准，不要在写法里假设「发出去就生效」。

> **典型翻车**：Magento 每 24h 全量覆盖 Feed，导致「某商品缺货了但旧 Feed 又把它置回 in stock」，标签一会儿显示一会儿隐藏。解法：Feed 全量覆盖时把 `availability` 字段也按当前库存刷新，或改用增量 API/batch。

### 4.5 权限 / Token 问题

| 场景 | 提示 | 解决 |
| --- | --- | --- |
| 脚本打标报 commerce 权限错 | 执行 token 的账号缺目录/商务权限 | 换用持有目录权限的 BM 系统用户 token |
| 换人后 token 失效 | 单独 Long-lived token 过期 | 用系统用户 token + 续期 |
| App 审核被拒 | 权限用途说明不足 | 把「打标/管理目录/读订单」写成合规的业务用例 |

### 4.6 运营排障 Runbook（速查）

```
IG 商店空白 / 无商品
  ├─ 目录是否绑定？ → GET /{ig-user-id}/shopping_product_catalogs
  ├─ 商品是否 in stock？→ GET /{catalog_id}/products
  └─ 审核是否 Enabled？→ 商务管理平台状态
无法打标签
  ├─ 账号商业/购物？→ 设置里看
  ├─ 商品归属目录？→ 核对
  ├─ 超上限？→ 计数
  └─ 权限？→ 换 token
结账失效
  ├─ 结账方式被重置？→ 重走审核
  └─ 品类/地区？→ 用 External
订单对不上
  ├─ Native 口径 → shopping_orders
  └─ External 口径 → Pixel/CAPI Purchase + content_ids
```

### 4.7 端到端 Python 编排示例（把整条链路串起来）

下面的函数演示「新增一批商品 → 绑定验证 → 发布打标 → 建集合 → 对账」的完整实战编排，企业可用它做成每日任务：

```python
# runbooks/instagram_shopping_sync.py（示例编排）
from scripts.meta_api import (
    MetaAPI,
    meta_add_products,
    meta_list_catalog_products,
    meta_get_catalog_batch,
    meta_list_instagram_shopping_products,
    meta_tag_media_product,
    meta_list_media_product_tags,
    meta_create_collection_card,
)

def sync_instagram_shop(ig_user_id: str, catalog_id: str, access_token: str,
                        new_products: list[dict], draft_media_ids: list[str],
                        collection_name: str) -> dict:
    api = MetaAPI({"access_token": access_token})
    report = {"added": 0, "tagged": 0, "verified": 0}

    # 1) 验证目录与 IG 的绑定关系
    attached = meta_list_instagram_shopping_products(ig_user_id, access_token)
    attached_ids = [c["id"] for c in attached]
    if catalog_id not in attached_ids:
        raise RuntimeError(f"catalog {catalog_id} 未绑定到 IG {ig_user_id}，请先在商务管理平台绑定")

    # 2) 批量上架新商品（异步批次 → 轮询至终态）
    if new_products:
        batch_id = meta_add_products(catalog_id, new_products, access_token)["batch_id"]
        for _ in range(12):  # 最多轮询 ~60s
            st = meta_get_catalog_batch(batch_id, access_token).get("status")
            if st in ("COMPLETED", "FAILED"):
                break
            import time; time.sleep(5)
        report["added"] = len(new_products)

    # 3) 给草稿媒体打标（约束：必须已发布，demo 中假设已发布）
    for mid in draft_media_ids:
        for prod in new_products:
            product_id = prod.get("retailer_id")  # demo: 需换成 catalog product_id
            meta_tag_media_product(mid, product_id, access_token)
            report["tagged"] += 1

    # 4) 回读验证
    for mid in draft_media_ids:
        tags = meta_list_media_product_tags(mid, access_token)
        report["verified"] += len(tags)

    # 5) 建集合让商店分类展示（demo，可能重复需幂等处理）
    if collection_name:
        meta_create_collection_card(ig_user_id, collection_name,
                                    new_products[0]["retailer_id"], access_token)
    return report
```

> **工程要点**：生产代码请加入幂等（retailer_id 唯一键、重复创建检测）、指数退避限流、以及「失败 SKU 落日志并可重放」。批次里失败项按 `retailer_id` 对账重发，不要整体重跑。

---

## 五、自测题

### 题目 1
一位 Charlotte 的商家把 Magento 里的 3000 个 SKU 通过 `POST /{catalog_id}/products` 逐条提交后，发现有的商品在 IG 商店怎么都搜不到。请说明：这批商品要经过哪几道「门」才能出现在 IG 商店？逐条提交有哪些问题？正确的批量姿势应该是什么？

<details><summary>答案</summary>
要出现在 IG 商店，商品需依次通过：① Catalog 结构校验（必填字段、图片 URL 可达、价格与货币合法）；② IG 商业资格/审核（地区、品类、账号 Enabled）；③ 可见性门（availability=in stock、目录仍绑定、未被下架）；④ 异步传播完成（最终一致）。

逐条 POST 的问题：慢、易触发限流（#4）、无统一的失败对账，且 POST 返回不代表已可见。正确姿势：用 `POST /{catalog_id}/products/batch`（异步批次）批量提交 → 轮询 `GET /{batch_id}` 至 `COMPLETED/FAILED` → 按 `retailer_id` 对账成功/失败项 → 再回读 `GET /{catalog_id}/products` 确认最终一致。
</details>

### 题目 2
你给某条 Reels 用 API 打上 3 个商品标签，但一次全都没显示。请列出 4 个以上可能导致的原因，以及对应的排查手段（含具体端点）。

<details><summary>答案</summary>
可能原因与排查：
1. 账号非 Business 或购物未启用 → 查设置/商务管理平台状态；
2. 商品不在绑定目录（或用错 product_id）→ `GET /{ig-user-id}/shopping_product_catalogs` 核对目录，`GET /{catalog_id}/products` 核对商品；
3. 商品 availability 非 in stock（缺货会隐藏标签）→ 查商品 availability；
4. 超过每帖标签上限 → 计数并删低效标签；
5. Reels 未在可打标窗口/未发布到账 → 确认发布状态；
6. 权限不足或 token 过期 → `#200`/`#190` 报错换 token；
7. 异步传播未完成 → `GET /{ig-media-id}/product_tags` 回读确认，等待传播后再看；
8. 地区不支持打标 → 确认地区可用性。
</details>

### 题目 3
请分别画出 Native Checkout 与 External Checkout 的端到端数据流，并说明：为什么中国大陆主体商家基本只能用 External？外部结账为什么必须做「域名验证 + Pixel 埋点」？

<details><summary>答案</summary>
Native：点标签 → Meta 渲染 PDP → 站内购物车/支付（Meta 钱包）→ 订单状态机 → Meta 通知/商家履约物流 → 退货退款；数据全在 Meta（shopping_orders / commerce_payouts）。
External：点标签 → Meta 渲染 PDP（展示商品+「查看网站」） → 跳转商家落地页（catalog 的 link）→ 站内支付物流退货 → 靠 Pixel/CAPI 回传（ViewContent→AddToCart→InitiateCheckout→Purchase）。

中国大陆主体基本只用 External 的原因：Native Checkout 仅限 Meta 明确开放的结账国家且需海外主体/支付与执法合规，大陆通常不在开放列表；External 只需域名验证 + 政策合规即可，覆盖广。
域名验证让 Meta 信任落地域名（否则商品 link 不被采信/跳转异常）；Pixel 埋点把 Meta 看不到的站内转化回传，用于归因与再营销（content_ids 需对应 catalog 的 retailer_id 才能对齐商品）。
</details>

### 题目 4
「标签在受众端一时显示一时消失」的可能根因与排查顺序是什么？请说明标签与商品/目录状态的联动语义（availability 的 in stock / out of stock / discontinued 分别会怎样影响标签）。

<details><summary>答案</summary>
根因通常是「最终一致」下 catalog 与 IG 副本不同步，或商品状态联动：`in stock` 标签可用显示；`out of stock` 商品仍在目录但 PDP 显示缺货、已打标签自动隐藏；`discontinued` 视为下架、标签隐藏；DELETE 彻底移除、标签不可复活。目录解绑/账号购物禁用也会让标签消失；Feed 全量覆盖用旧库存值也可能把标签闪回。

排查顺序：① 目录是否仍绑定（shopping_product_catalogs）；② 商品 availability（catalog products）；③ 账号购物是否 Enabled；④ 回读 media 的 product_tags 确认标签是否还在；⑤ 检查数据源（Feed 是否被旧值覆盖）与同步延迟。解法：加每日对账任务，按 retailer_id 校准 availability 与标签，不要假设发出去就生效。
</details>

### 题目 5
请对比「IG 商店的 Collection（商品集合）」与「Catalog 的 Product Set（商品集）」，说明二者在数据模型与用途上的区别。并用 GitHub/Graph API 端点说明如何创建一个商店集合、往集合加商品、以及验证它在商店可见前要经历什么。

<details><summary>答案</summary>
Product Set 是 Catalog 内的服务端逻辑分组，主要服务 API/广告（DPA、Collection Ads），可带 filter；Collection 是面向用户的陈列层，出现在 IG 商店 Tab，一个 Collection 对应一张橱窗卡。二者可以引用/互补，但不能混为一谈。

创建与加商品：`POST /{ig-user-id}/collections?name=...&product_id=...` 创建；`PUT /{collection-id}/products?product_id=...` 加商品、`DELETE /{collection-id}/products` 移除；`GET /{ig-user-id}/collections` 与 `GET /{collection-id}/products` 回读验证。
验证可见前的保证：创建与改集合同样是异步传播，需回读确认；空集合、重名、封面不达标不会出现在商店；「全部商品」是兜底视图，未归类商品也会出现，不希望展示的商品要主动下架而非寄望于「不归类就不显示」。
</details>

---

## 六、结语与进一步阅读

- Catalog 通用原理 → `meta-ads-catalog-deep.md`
- Meta 全平台架构/权限/评分 → `meta-ads-architecture-deep.md`
- Meta Marketing API 广告投放 → `meta-ads-marketing-api-deep.md`
- 统一平台工具与认证 → `scripts/ad_platform_api.py`、`scripts/meta_api.py`
- 电商数据对账/巡检思路 → 参考 `distill`、`kb_health_check.py` 的定期巡检范式

> 本文档所有端点、权限、国家/地区与上限等信息会随 Meta 政策更新变化，落地系统前务必以官方最新文档与商务管理平台实际状态为准。

