# Instagram 电商全链路深度学习笔记

> 创建日期: 2026-08-14
> 作者: Ryan
> 定位: 资深专家级 — Instagram 商业化全链路
> 前置阅读: meta-04（功能版图）、meta-05（Ads API 高级）、meta-ads-catalog-deep（Catalog 通用知识）
> 本文侧重: Instagram 电商专属业务串联（Shoppable / Checkout / 商店 Tab / 标签 / 与投流联动），与 Catalog 通用知识互补而非重复。

---

## 第一部分: Instagram 商业账号开通与绑定

### 1.1 三种账号形态辨析：个人号 / 商业号 / 创作者号

在进入电商链路之前，必须先理解账号形态。Instagram 上有三种账号类型，而「能不能做电商」几乎完全由账号形态决定。

```
─────────────────────────────────────────────────────────────────────
 账号形态           可开商店?   可挂商品链接?   可投广告?   适用人群
─────────────────────────────────────────────────────────────────────
 Personal(个人)      ✗           ✗(仅可挂1个link)  ✗(需切换到商业)  普通生活用户
 Business(商业)      ✔           ✔              ✔          商家/品牌
 Creator(创作者)     ✔(部分)      ✔              ✔          红人/博主
─────────────────────────────────────────────────────────────────────
```

关键结论：
- 只有 **Business（商业账号）** 能完整开通 Instagram Shopping（商店 / 打标 / Checkout）。
- Creator（创作者账号）在部分市场也能用 Shopping，但功能与后台入口不稳定，**做电商一律优先切 Business**。
- 从个人号切到商业号是单向可逆操作（随时能切回），但切换会重置部分「非公开」指标口径，统计前先想清楚。

### 1.2 开通商业账号的完整步骤清单

```
Step 1  手机端: 设置 → 账户 → 切换到专业账户 → 选择「商家」
    ├── 选择商家类型: 本地商户 / 品牌 / 创作者
    └── 填写联系方式: 电话、邮箱、地址(可选)

Step 2  绑定 Facebook 主页 (Page)
    ├── 进入「专业账户设置 → Connect or create a Facebook Page」
    ├── 必须有一个 Facebook 主页作为「身份锚点」
    └── 一个 FB 主页通常只能绑定一个 IG 商业号(通过 BM 可多对一托管)

Step 3  接入 Business Manager (BM / Meta Business Suite)
    ├── 进入 business.facebook.com 创建商务管理平台
    ├── 绑定 Instagram 商业账号
    └── 添加广告账户 + 设置支付方式

Step 4  开通 Instagram Shopping
    ├── 要求: 商业账号 + 已绑定 FB 主页 + 已接入 BM
    ├── 设置 → 业务 → 购物 → 「继续设置」
    └── 选择要关联的商品目录(Catalog)

Step 5  等待审核
    └── Meta 审核「购物功能」与「商品目录」，通常数小时~数天
```

> ⚠️ 踩坑点 1：**IG Shopping 的开通必须走「已审核通过的 FB 主页」**。如果你用的是「没有管理员权限的个人主页」，会卡在审核永不通过。请确保在 BM 里用拥有 Page 完整管理员权限的账号操作。

### 1.3 账号绑定的对象层级关系

理解对象层级是后续一切 API 调用的地基：

```
Business Manager (BM)
  ├── Ad Account (广告账户)
  │     └── Campaign → Ad Set → Ad
  ├── Page (Facebook 主页)
  │     ├── Instagram Account (商业号)   ← 电商容器
  │     │     ├── Media (帖子/Reels/Story)
  │     │     ├── Product Tags (商品标签)
  │     │     └── Shop (商店 Tab)
  │     └── Catalog (商品目录)
  │           ├── Product Set
  │           ├── Product Item → Product Group
  │           └── Collection
  └── Pixel / Conversions API (转化追踪)
```

### 1.4 绑定相关 API 与权限

在 Graph API 中，IG 商业号的电商能力通过以下权限与端点暴露：

```
Account-Level 权限:
├─ instagram_basic               读取基础账号信息
├─ instagram_shopping_tag_products  为 IG 内容打商品标签(电商核心)
├─ instagram_content_publish     发布内容
├─ instagram_manage_insights     读取洞察
└─ catalog_management / catalog_read  目录管理

Page-Level(通过 Page Token 间接获得):
├─ pages_read_engagement / pages_manage_metadata
└─ 读取/管理绑定关系

关键端点:
```
GET    /{instagram-account-id}                      读取账号信息
GET    /{instagram-account-id}/shops                列出账号关联的商店
GET    /{instagram-account-id}/product_tags         读取已打标内容
GET    /{instagram-media-id}/product_tags           读取单条内容商品标签
POST   /{instagram-media-id}/product_tags           为已发布内容打标签
GET    /{instagram-account-id}/catalogs             列出可用商品目录
```

### 1.5 Python 实现：读取 IG 账号与商店

```python
import requests

class InstagramCommerce:
    """
    Instagram 电商基础能力封装。
    基于 scripts/ad_platform_api.py 的 meta_* 命名风格扩展。
    """
    GRAPH = "https://graph.facebook.com/v20.0"

    def __init__(self, access_token: str):
        self.token = access_token
        self.session = requests.Session()

    def _get(self, path: str, params: dict | None = None) -> dict:
        params = params or {}
        params["access_token"] = self.token
        resp = self.session.get(f"{self.GRAPH}/{path}", params=params)
        resp.raise_for_status()
        return resp.json()

    def meta_list_instagram_accounts(self, page_id: str) -> list[dict]:
        """
        列出 FB 主页绑定的 Instagram 商业账号。
        GET /{page-id}/instagram_accounts
        """
        data = self._get(f"{page_id}/instagram_accounts",
                         {"fields": "id,username,followers_count"})
        return data.get("data", [])

    def meta_get_instagram_account(self, ig_account_id: str) -> dict:
        return self._get(ig_account_id, {
            "fields": "id,username,biography,followers_count,"
                      "media_count,is_business,shopping_product_tagging_eligibility"
        })

    def meta_list_ig_shops(self, ig_account_id: str) -> list[dict]:
        shops = self._get(f"{ig_account_id}/shops",
                          {"fields": "id,commerce_merchant_settings_id"})
        return shops.get("data", [])
```

### 1.6 绑定常见失败与排查

```
失败现象                           根因排查
─────────────────────────────────────────────────────────────────────
IG 账号下拉为空                    该 FB 主页未绑定 IG 商业号 / 权限不足
Shopping 审核一直 pending          主页无完整管理员 / 目录未审核 / 登录账号无权限
绑定报 #10 权限错误                 未授权 instagram_shopping_tag_products
目录选择不了                        
    ├── Catalog 未与该 IG 账号关联
    └── Catalog 状态非 ACTIVE
商店 Tab 不显示                    账号所在市场不支持 / Checkout 未开通
```

---

## 第二部分: Product Catalog 与 Shoppable Posts

### 2.1 Shoppable Posts 的概念

「可购物帖（Shoppable Post）」指带有商品标签的 Instagram 帖子/Reels/Story。用户点击商品标签会弹出商品卡片，可跳转到商品详情或直接结算。

```
Shoppable Post 形成条件:
┌────────────────────────────────────────────┐
│  1. 商业账号(已开通 IG Shopping)            │
│  2. 已关联 Catalog(商品目录)               │
│  3. 发布帖子                                    │
│  4. 在帖子的商品上打标签(product tag)      │
│  └→ 标签指向 Catalog 中的 Product Item     │
└────────────────────────────────────────────┘
        │
        ▼
用户浏览 → 点击标签 → 弹出商品卡片 → 跳商店/结算
```

### 2.2 四种商品卡片形态对比

IG 电商的内容触点有以下几种，需要区分其应用场景：

```
形态                触发方式              点击后去向         适用
────────────────────────────────────────────────────────────────────────
1. Product Tag      帖子上手动打标       商品详情/Checkout   日常内容中「软性带货」
2. Shoppable Feed   商店 Tab 的商品流    商店Tab本身         聚合浏览
3. Collection       商店Tab中成组的商品  组内商品流          主题/场景推荐
4. Sticker(Sticker quiz/poll+tag)  Story中的商品贴纸  商品快照        种草Story

差异要点:
├─ Product Tag 是「细粒度」绑定: 一条内容可挂多个商品
├─ Shoppable Feed 是「账号粒度」聚合: 全账号可售商品流
│   └→ 内容隐藏后, 其商品会从商店 Tab 中不再展示
└─ Collection 是「运营粒度」编排: 面向场景而非单品
```

### 2.3 Commerce 数据模型

```
Catalog (目录, 一个商家通常一个主目录)
  └── Product (商品)
        ├── Product Group (商品组: 同款不同规格/颜色)
        │     ├── Product Item 1 (红色 M 码)
        │     ├── Product Item 2 (红色 L 码)
        │     └── Product Item 3 (蓝色 M 码)
        ├── 字段: title, description, price, currency,
        │        image_url, link, availability, condition,
        │        gtin, brand, color, size, ...(custom*)
        └── 使用 Product Set (商品集) 进行投放分组
```

### 2.4 商品目录的三种数据源（Feed）

```
Catalog Feed 类型:
┌────────────────────────────────────────────────────────────────┐
│ 1. Manual Upload(手动)                                          │
│    └→ CSV / TSV / 由 BM 界面手动维护商品列表                   │
│                                                                  │
│ 2. Hosted Feed(托管)                                            │
│    └→ 商家把商品 Feed 文件放到商家自己的 URL                    │
│    └→ Catalog 定时抓取(可设抓取频率: DAILY/SCHEDULED)          │
│                                                                  │
│ 3. Product Sync / API(商品同步)                                 │
│    └→ 通过 Product Catalog API 增量增删改商品                   │
│    └→ 适合: 平台型商家、SKU 量大、实时库存的场景                │
└────────────────────────────────────────────────────────────────┘
```

> 生产环境的建议：**用 API/同步方式维护库存与价格**，因为手动 Feed 无法满足「秒级下架无货商品」的需求；若 SKU 不多且更新频率低，托管 Feed 最简单可靠。

### 2.5 Python 实现：目录与商品操作

```python
class InstagramCommerce:
    # ... 承接 1.5 节

    def meta_list_catalogs(self, ad_account_id: str) -> list[dict]:
        """列出广告账户名下的商品目录。"""
        return self._get(f"{ad_account_id}/product_catalogs",
                         {"fields": "id,name,vertical,product_count"}).get("data", [])

    def meta_get_catalog(self, catalog_id: str) -> dict:
        return self._get(catalog_id, {"fields": "id,name,vertical"})

    def meta_list_categories(self, catalog_id: str) -> list[dict]:
        """读出目录的类别树(品类结构), 用于商品归类。"""
        return self._get(f"{catalog_id}/categories",
                         {"fields": "id,name,parent_id,child_ids"}).get("data", [])

    def meta_add_products(self, catalog_id: str, products: list[dict]) -> dict:
        """
        向目录批量新增商品。
        products: [{title, price, currency, availability, ...}, ...]
        返回 catalog_item_batch 结果。
        """
        return self._get(f"{catalog_id}/products", {"products": str(products)})

    def meta_list_catalog_products(self, catalog_id: str, page: int = 0,
                                   page_size: int = 100) -> list[dict]:
        """分页读取目录商品(含规格/库存/图片)。"""
        return self._get(f"{catalog_id}/products", {
            "fields": "id,title,price,currency,availability,image_url,"
                      "product_group,retailer_id,status",
            "limit": page_size,
            "offset": page * page_size,
        }).get("data", [])

    def meta_update_product(self, catalog_id: str, retailer_id: str,
                            updates: dict) -> dict:
        """按 retailer_id(商家自身SKU) 更新商品价格/库存/可用性。"""
        return self._get(f"{catalog_id}/products", {
            "retailer_id": retailer_id,
            "updates": str(updates),
        })
```

### 2.6 商品字段完备性检查清单

上架到 IG 前，建议对每个商品做字段体检，字段缺失会直接导致**无法被搜索、无法打标、无法投广告**：

```
必填字段:
├─ title              商品标题
├─ description        商品描述
├─ price              价格
├─ currency           币种 (如 USD)
├─ availability       可用性 (in stock / out of stock / preorder)
├─ link              落地页 URL
└─ image_url          商品图 URL
推荐字段(影响曝光/搜索):
├─ brand              品牌
├─ condition          new / used
├─ gtin / mpn        国际条码 / 厂商型号
├─ color / size       颜色 / 尺码(配合 Product Group)
├─ category           品类
├─ google_product_category  谷歌品类(商家自建也可)
└─ custom_label_0~4   自定义标签(常用于投放分组)
```

---

## 第三部分: IG Checkout 与商店 Tab

### 3.1 商店 Tab（Shop Tab）是什么

商店 Tab 是 IG 商业号主页上那个购物袋图标入口，聚合账号内所有可售内容与商品，是「自营店铺」的入口。

```
主页 → 商店 Tab
   ├── Shop (商店聚合)
   │     ├── 精选商品 (Featured Products)
   │     ├── Collections (主题商品组, 也叫"系列")
   │     └── 全部商品 (All Products)
   ├── 由 Catalog + 已打标内容共同渲染
   └── 点击商品 → 落地到详情/外链结算或 App 内 Checkout
```

### 3.2 Checkout 的两种模式

Checkout 决定了用户「在哪完成付款」，直接影响转化率与数据闭环：

```
模式 A: Instagram 站内结算 (IG Checkout / Pay)
├── 用户在整个购物流程内不离开 IG
├── 依托 Facebook Pay / (在中国大陆无此能力)
├── 转化率最高, 数据闭环最干净
└── 仅支持白名单市场 & 商家须走审核 & 有手续费(约 5% 左右, 视地区)

模式 B: 跳转外部站点结算 (Checkout with External / Link 外链)
├── 点击商品 → 打开浏览器落地商家自建站/平台
├── 无需 IG Checkout 白名单, 任何开通 Shopping 的市场都可用
├── 数据闭环依赖 Pixel / CAPI 回传才能衡量
└── 也是目前国内出海卖家最常用的模式
```

### 3.3 IG 站内 Checkout 开通前提（白名单制）

```
开通 IG Checkout(站内结算) 的硬性条件:
├─ 商家处于受支持市场
├─ 拥有购物功能的商业账号
├─ 通过「Meta 信任与安全审核」
├─ 绑定有效支付能力(Facebook Pay / 当地支付)
├─ 目录中的商品合规(禁售品/成人/健康等需额外审核)
└─ 合规的退货与客户服务政策
```

> ⚠️ 踩坑点 2：IG Checkout 是**邀请/白名单制**，不是点了开关就开通。很多团队把「IG Shopping 开通」误当成「IG Checkout 开通成功」，导致后链路的订单数据一直不落盘。务必区分：**Shopping 校验商品展示，Checkout 校验支付闭环**。

### 3.4 商店 Tab 与 Catalog 的关系

商店内能看到什么，完全由 Catalog 与内容联动决定：

```
商店 Tab 展示规则:
├─ 已打标的帖/Reels → 出现在「精选商品」候选
├─ Catalog 中 availability=in stock 的商品 → 出现在「全部商品」
├─ 主动配置的 Collection → 出现在专区
├─ 商品无图/无价/未打标 → 不展示(静默过滤)
└─ 内容被隐藏/下架 → 关联商品从聚合流消失
```

### 3.5 Python 实现：Collection（商品系列）管理

```python
class InstagramCommerce:
    # ... 承接上文

    def meta_list_collection_cards(self, catalog_id: str) -> list[dict]:
        """
        列出目录下的商品系列(Collection / Collection Card)。
        系列是「面向主题/场景」的商品组织单元, 常用于商店 Tab 专区
        与 Collection 广告创意。
        """
        return self._get(f"{catalog_id}/collection_cards",
                         {"fields": "id,name,product_set_id,image_url"}).get("data", [])

    def meta_create_collection_card(self, catalog_id: str, name: str,
                                    product_set_id: str, image_url: str) -> dict:
        return self._get(f"{catalog_id}/collection_cards", {
            "name": name,
            "product_set_id": product_set_id,
            "image_url": image_url,
        })

    def meta_list_dynamic_product_sets(self, catalog_id: str) -> list[dict]:
        """
        列出动态商品集(Dynamic Product Set)。
        通过规则(规则引擎)自动圈选商品, 是 DPA/Collection 广告投放的关键单元。
        """
        return self._get(f"{catalog_id}/product_sets",
                         {"fields": "id,name,product_count"}).get("data", [])
```

### 3.6 动态商品集 vs 系列（易混点）

这是实操中最常见的概念混淆，务必厘清：

```
动态商品集 Dynamic Product Set:
├─ 本质: 目录下按「规则」动态圈选的一组商品(如 price < 50 且 in stock)
├─ 用途: 投放(DPA/Collection 广告的动态商品池)
├─ 更新: 自动(规则匹配到的商品实时进入)
└─ 不面向店铺 UI

系列 Collection Card:
├─ 本质: 商店 Tab 中面向用户的「主题橱窗」(如"夏日新品")
├─ 用途: 店铺展示 + 可作为 Collection 广告的素材
├─ 更新: 半手动(编辑成员)
└─ 面向店铺 UI

关系: 一个 Collection Card 通常与一个 Product Set 关联
```

---

## 第四部分: 标签管理与商品管理 API

### 4.1 商品标签（Product Tag）的完整生命周期

```
创建内容(可选, 先发布后打标, 或预处理打标)
   │
   ├─ 方式1: 发布时打标(用 media_publish 预置 tags)  ← 需 INSTAGRAM_COMMERCE 深层权限
   ├─ 方式2: 发布后补打标(POST /media-id/product_tags) ← 最常用, 无需高风险权限
   │
   ▼
GET 读标签(验证)  →  定期审查合规(违禁品自动下浮)
   │
   └─ 下架/隐藏内容时标签一并失效
```

### 4.2 后打标（Post-Publish Tagging）

最稳妥、权限要求最低的方式是**先发布内容，再补打商品标签**：

```
POST /{instagram-media-id}/product_tags
Body: 
  {
    "access_token": "...",
    "username": "ryan_brand",
    "product_tags": [
      {"product_id": "111222333444", "x": 0.45, "y": 0.30},
      {"product_id": "111222333555", "x": 0.70, "y": 0.55}
    ]
  }

x/y: 打标点的坐标(0~1 相对坐标)
```

### 4.3 Python 实现：内容打标与标签读取

```python
class InstagramCommerce:
    # ... 承接上文

    def meta_tag_ig_product(self, media_id: str, username: str,
                            product_tags: list[dict]) -> dict:
        """
        为已发布的 IG 内容(帖/Reel)打商品标签。
        product_tags: [{"product_id": "..", "x": 0.4, "y": 0.5}, ...]
        """
        payload = {"username": username, "product_tags": str(product_tags)}
        return self._get(f"{media_id}/product_tags", payload)

    def meta_list_media_product_tags(self, media_id: str) -> list[dict]:
        """读取单条内容上的商品标签。"""
        return self._get(f"{media_id}/product_tags",
                         {"fields": "product_id,image_url,title,price"}).get("data", [])

    def meta_list_ig_tags(self, ig_account_id: str, limit: int = 100) -> list[dict]:
        """列出账号名下带商品标签的全部内容。"""
        return self._get(f"{ig_account_id}/tags",
                         {"fields": "media_id,permalink", "limit": limit}).get("data", [])
```

### 4.4 标签打不上 / 打错位的排查

```
标签失败                          排查方向
─────────────────────────────────────────────────────────────
报 product not tagged(商品不可打)  该商品不在 Catalog / 未过审核 / availability≠in stock
报 media not eligible(内容不可打)  内容太旧 / 类型不支持(如部分 Reels 需满足条件)
报 coordinate out of range          x/y 超出 0~1 范围
报 permission error                缺 instagram_shopping_tag_products 权限
打标成功但用户看不到               IG 缓存/审核延迟, 或商品被静默下架
```

### 4.5 商品管理的最佳实践（同步策略）

对于自建站卖家，建议按下述节奏同步商品，平衡时效与限流：

```
推荐同步策略:
├─ 全量同步: 每日 1 次(Daily Full Sync), 兜底一致性
├─ 增量同步: 每次订单/库存变更触发(Request-level Update)
│     ├─ 库存归零 → availability=out_of_stock(立即)
│     ├─ 价格变更 → 立即更新
│     └─ 下架商品 → 从 Catalog 移除或置 out_of_stock
├─ 限流护肤: 
│     ├─ 单请求 < 1000 商品
│     ├─ 加指数退避重试(应对 #80004 rate limit)
│     └─ 用异步队列消费库存消息, 避免突发送爆
└─ 数据源单一: 选 API/同步作为 Source of Truth, Feed 只做兜底
```

---

## 第五部分: 与付费广告联动（Collection / DPA）

### 5.1 为什么电商必须联动投流

IG 电商的「自然流」转化有限，真正起量靠付费广告。两条主线：

```
主线1: DPA (Dynamic Product Ads / Catalog Sales)
  └→ 依据用户行为动态展示已看过的商品(动态重定向)
  └→ 依托 Catalog, 用 Product Set 作为商品池

主线2: Collection Ads
  └→ 「封面 + 即时橱窗(Instant Storefront)」的沉浸式广告格式
  └→ 无需进入商店 Tab, 广告内直接逛商品 → 转化更高
```

### 5.2 DPA 广告的结构与对象串联

```
Marketing Campaign Objective = SALES / OUTCOME_TRAFFIC(catalog 场景)
  └── Ad Set
        ├── Optimization: conversions / link_clicks
        ├── 受众: 动态受众(DPA 自动) 或 自定义
        ├── 商品池: Product Set(动态商品集)
        └── Placements: Feed / Stories / Reels / Explore
              └── Ad
                    └── Creative: 动态创意模板(用 Product 字段渲染)
                          ├── 标题: {{product.name}}
                          ├── 价格: {{product.price}}
                          └── 图片: {{product.image_url}}
```

### 5.3 DPA 素材模板变量

```
动态素材支持的模板变量(Product 字段自动替换):
├─ {{product.name}}          商品名
├─ {{product.description}}   描述
├─ {{product.price}}         价格
├─ {{product.link}}          落地页
├─ {{product.image_url}}     商品图
├─ {{product.retailer_id}}   商家SKU
└─ {{custom.xxxx}}           自定义字段(需目录含 custom_label_* 等)

用模板的意义:
├─ 一套广告结构, 千万级 SKU 自动复用
└─ 每次展示按用户兴趣动态换品
```

### 5.4 Collection Ads 的三种布局

Collection 广告的「即时橱窗(Instant Storefront)」有三种布局，按转化目标选：

```
布局1: Grid(网格)
    └→ 封面图 + 商品网格(类似商店流), 适合大量 SKU

布局2: Product Set(商品集)
    └→ 按 Product Set 展示, 适合主题投放(如"爆款区")

布局3: Media Let (媒体集)
    └→ 封面 + 混排的多媒体素材, 更沉浸, 适合品牌故事

选择建议:
├─ 注重快速转化 → Grid / Product Set
├─ 注重种草与品牌 → Media Let
└─ 单一爆品 → 直接 DPA 单品动态广告更精准
```

### 5.5 Python 实现：创建 DPA 广告（Catalog Sales）

```python
class InstagramCommerce:
    # ... 承接上文

    def meta_create_dpa_campaign(self, ad_account_id: str, name: str,
                                 objective: str = "OUTCOME_SALES") -> dict:
        """创建以 SALES 为目标、落地 Catalog 的 Campaign。"""
        return self._get(f"{ad_account_id}/campaigns", {
            "name": name,
            "objective": objective,
            "status": "PAUSED",  # 先暂停, 校验完毕再开启
            "special_ad_categories": "NONE",
        })

    def meta_create_dpa_adset(self, campaign_id: str, name: str,
                              product_set_id: str,
                              pixel_id: str | None = None) -> dict:
        """
        创建 DPA Ad Set: 商品池=Product Set, 优化=转化。
        """
        params = {
            "name": name,
            "campaign_id": campaign_id,
            "optimization_goal": "LINK_CLICKS" if not pixel_id else "OFFSITE_CONVERSIONS",
            "billing_event": "IMPRESSIONS",
            "status": "PAUSED",
            "targeting": str({
                "geo_locations": {"countries": ["US"], "location_types": ["home"]},
            }),
            "product_set_id": product_set_id,
        }
        if pixel_id:
            params["promoted_object"] = str({"pixel_id": pixel_id,
                                             "custom_event_type": "PURCHASE"})
        return self._get(f"{campaign_id}/adsets", params)
```

### 5.6 从零到一联动投流的最短路径图

```
深度串联示意(一张图看懂数据与商品如何流动):

  [自建站/PIM 商品库]
        │  (API/Feed)
        ▼
   [Product Catalog]──────────────┐
        │                          │
        ├─ availability/price 同步 │  (商品集规则)
        ▼                          ▼
   [商店 Tab]                [Dynamic Product Set]
        │                          │
        │  (打标)                  │  (素材模板)
        ▼                          ▼
   [Shoppable 内容]         [DPA/Collection Ads]
        │                          │
        └──────────┬───────────────┘
                   ▼
        [用户点击 → Pixel/CAPI 回传 Purchase]
                   │
                   ▼
        [Meta 学习 → 动态重定向 → 再营销闭环]
```

### 5.7 归因与数据闭环

DPA 广告的真实 ROI 重度依赖回传质量：

```
转化回传两条腿:
├─ Meta Pixel(前端): 自动收集 click/view 行为
│     └→ 天然支持 IG 广告归因(点击后1天/浏览后1天等窗口)
└─ Conversions API(后端): 服务器端回传, 补足无 Pixel 的通道
      └→ 需要 event_id 去重, 避免双计

归因窗口(IG 场景常见配置):
├─ Click-through: 7 天
├─ View-through: 1 天
└─ 说明: 归因窗口过短会低估 IG 的"种草延迟转化"价值

常见坑:
├─ 双回传未去重 → 转化虚高
├─ CAPI event_id 不一致 → 无法配对 → 转化丢失
└─ Pixel 未装全站 → DPA 动态池"无行为种子" → 冷启动困难
```

---

## 第六部分: 从零到一完整业务流程与踩坑记录

### 6.1 端到端业务流程图（从零到一）

下面是一张「从创建账号到第一笔 IG 电商订单」的完整泳道流程：

```
┌─────────────┐   ┌───────────────┐   ┌──────────────────┐   ┌───────────────┐
│  Step1 基建  │   │  Step2 商品   │   │  Step3 内容开关  │   │  Step4 投流  │
└─────────────┘   └───────────────┘   └──────────────────┘   └───────────────┘
1. BM 账号         1. 建 Catalog      1. IG 商业号接入      1. 建 DPA 广告
2. FB 主页         2. 传/同步商品      2. 绑定 Catalog        2. 建 Product Set
3. IG 商业号       3. 商品字段体检      3. 发布+打标          3. 建 Campaign/AdSet
4. 关联广告账户    4. 建 Product Set   4. 验证商店 Tab        4. 配模板+Pixel
5. Pixel/CAPI      5. 建 Collection    5. 人工审核           5. 开启投放/归因
```

### 6.2 完整步骤清单（可直接执行）

```
□ 1. 基建
  □ 1.1 注册 Business Manager (business.facebook.com)
  □ 1.2 创建/认领 Facebook 主页并拥有管理员
  □ 1.3 将 IG 切换为商业账号并绑定该主页
  □ 1.4 在 BM 中把 IG 商业号添加到资产
  □ 1.5 创建广告账户 + 充值 + 绑定支付方式
  □ 1.6 创建 Pixel(或 APC) 并在站点注入
  □ 1.7 配置 Conversions API 并做 event 去重测试

□ 2. 商品
  □ 2.1 创建 Product Catalog(vertical: commerce)
  □ 2.2 通过 API/Feed 同步首批商品
  □ 2.3 跑一遍字段体检(必填齐全/图链可用/价格币种正确)
  □ 2.4 将 Catalog 关联到 IG 账号
  □ 2.5 建 1~2 个 Product Set(如"全量在售"、"优惠款")
  □ 2.6 (可选)建 Collection 卡片用于店铺橱窗

□ 3. 内容与开关
  □ 3.1 提交 IG Shopping 审核并等待通过
  □ 3.2 发布 3~5 条种草内容(帖+Reels)
  □ 3.3 为内容打商品标签(后打标方式)
  □ 3.4 手机端验证商店 Tab / 商品卡片可点
  □ 3.5 (若目标市场支持)申请 IG Checkout 站内结算

□ 4. 投流
  □ 4.1 Pixel/CAPI 确认能收到 Purchase/ViewContent 事件
  □ 4.2 建 DPA Campaign(SALES)
  □ 4.3 建 AdSet(商品池=Product Set, 落地商店/商品页)
  □ 4.4 用动态模板建实现创意
  □ 4.5 小预算冷启动(建议 $50~100/天起)
  □ 4.6 观测学习期(前 50 次转化), 再放大预算

□ 5. 运营与归因
  □ 5.1 每日看 DPA 报告的 ROAS/CVR
  □ 5.2 用 Collection Ads 测新款式/新人群
  □ 5.3 关注商店 Tab 收藏/加购漏斗
  □ 5.4 库存/价格变更及时同步, 避免点击后死链
```

### 6.3 踩坑记录（真实问题库）

```
坑1: 账号形态没切商业号 → Shopping 根本开不了
     教训: 先确认 IG 是 Business 账号 + 已绑定 FB 主页

坑2: 误把"Shopping 开通"当"Checkout 开通"
     教训: Shopping=展示, Checkout=支付闭环, 两者审批独立

坑3: 用无管理员的 FB 主页绑 IG → 审核永久 pending
     教训: 用拥有 Page 完整权限的账号, 在 BM 资产里操作

坑4: 商品图/落地页 404 → 广告点击后死链, 转化 0
     教训: 上架前自动校验 link 与 image_url 可达性

坑5: 双回传未去重(CAPI+Pixel) → 转化虚高, 误判 ROI
     教训: event_id + 服务端去重; 用报告与站内单量对账

坑6: 库存卖光但 Catalog 还标 in stock → 用户下单失败
     教训: 库存归零立即置 out_of_stock, 异步同步

坑7: DPA 冷启动无转化种子 → 动态池空转
     教训: 先喂足 Catalog 浏览/加购事件, 或用相似受众

坑8: 打标坐标乱填 → 商品标签"悬空"不可点
     教训: x/y 用 0~1 相对坐标, 发布的图未改尺寸前先算准

坑9: 忽略审核市场/站点政策 → 商品被静默下架
     教训: 上线前查目标市场的禁售品与购物政策

坑10: 只用托管 Feed 更新库存 → 秒级下架做不到
     教训: 高频变更用 API/同步, Feed 仅兜底
```

### 6.4 踩坑教训汇总（方法论沉淀）

```
一条「踩坑—根因—预防」循环:
  踩坑发生 → 记录现象获得一线证据
           → 定位根因(数据/权限/字段/市场四象限)
           → 补监控(上报失败/告警)
           → 沉淀为检查项进上线 Checklist
           → 形成"一次性问题不再犯"的纪律

优先级矩阵(每次上线前自查):
├─ P0(必查): 账号形态 / 权限 / 字段完备 / 图链可用 / 支付可结算
├─ P1(要查): 归因去重 / 库存实时性 / 限流退避 / 目标市场合规
└─ P2(随查): Collection 内容新鲜度 / 素材点击率 / Shop 漏斗
```

---

## 第七部分: 总结

### 7.1 全链路心智模型（一图总结）

```
Instagram 电商的本质 = 内容(种草) × 商品(Catalog) × 交易(Checkout) × 流量(广告)

  [账号层]  BM → FB主页 → IG商业号(身份 & 绑定)
  [商品层]  Catalog → Product → Product Set / Collection(货)
  [内容层]  帖/Reels/Story + Product Tag(种)
  [交易层]  商店 Tab / Checkout / 外链(收)
  [流量层]  DPA / Collection Ads + Pixel/CAPI(驱)
  [数据层]  转化回传 → 归因 → 优化 → 再营销(闭环)
```

### 7.2 关键要点速记

```
├─ IG 电商以"商业账号 + FB主页 + BM"三件套为起点
├─ Catalog 是贯穿展示/交易/投流的中枢数据
├─ Shoppable=打标展示, Checkout=支付闭环, 两者审批独立
├─ DPA 吃动态商品池(Product Set)与商品字段完备度
├─ Collection 广告把"逛"前置到广告内, 转化效率更高
├─ ROI 成色取决于归因去重与回传质量
├─ 库存/价格要实时同步, 死链是转化杀手
└─ 上线前过 P0 检查项, 让"一次性问题"不复现
```

### 7.3 学习总结与后续方向

本笔记完成了从「账号基建 → 商品目录 → 内容打标 → 商店/结算 → 广告联动 → 完整业务流程」的 Instagram 电商全链路串联。下一步延伸方向：

```
后续可深入:
├─ IG Checkout 站内结算的开放市场与费率细节
├─ Collection 广告各版位(Reels/Story/Explore)的创意规范
├─ DPA + 电商 API 双轨下的库存事件流(异步一致)
├─ IG 购物归属与退税/对账口径
└─ 与 TikTok Shop / Amazon 的多平台商品中台设计
```

---

## 自测题

### 问题 1
为什么「开通 IG Shopping」不能等同于「开通 IG Checkout」？两者审批的关键差异是什么？

<details>
<summary>查看答案</summary>

IG Shopping 是「商品展示/打标/商店 Tab」能力的统称，只要求商业账号绑定 FB 主页并关联 Catalog；而 IG Checkout 是「站内支付闭环」，是额外的邀请/白名单制，还要求商家处于受支持市场、通过信任与安全审核、绑定支付能力与退货政策，且口径上是"支付"而非"展示"。很多团队误把 Shopping 开通当成 Checkout 成功，导致后续订单数据不落盘。P0 上要分别确认两者状态。
</details>

### 问题 2
打商品标签时 x/y 坐标字段的含义是什么？使用不当会怎样？

<details>
<summary>查看答案</summary>

x/y 是打标点在内容上的相对坐标，取值 0~1（如 0.45/0.30 表示内容画面 45% 宽、30% 高的位置）。使用不当(如超出 0~1 或按原始图片尺寸直接填像素值)会导致报 coordinate out of range，或标签"悬空/偏移"不可点击。正式发布的图若被裁剪，需按展示比例重算坐标。
</details>

### 问题 3
DPA 广告的"商品池"由什么决定？想让一套广告结构自动适配海量 SKU 应该怎么做？

<details>
<summary>查看答案</summary>

DPA 的商品池由 Product Set（动态商品集）决定，动态商品集通过规则自动圈选商品并实时更新。要让一套广告适配海量 SKU，应在 Creative 上使用动态素材模板（如 {{product.name}}、{{product.price}}、{{product.image_url}}），由系统按用户兴趣自动替换商品字段，从而一份广告结构覆盖全部在售商品。
</details>

### 问题 4
CAPI 与 Pixel 双回传会造成什么指标问题？如何规避？

<details>
<summary>查看答案</summary>

双回传若不使用统一的 event_id 去重，同一笔购买会同时被前端 Pixel 与后端 CAPI 各计一次，导致转化虚高、误判 ROAS。规避方法：两端为每个事件生成一致的 event_id，在 Meta 端做去重去重配对；同时用站内真实订单量定期对账，验证归因报告是否与实际单量收敛。
</details>

### 问题 5
库存卖光但 Catalog 仍标 in stock 会带来什么后果？生产环境应如何同步库存？

<details>
<summary>查看答案</summary>

会导致用户点击广告后在落地页或结算时发现无货而流失，转化骤降，并拉低广告学习与账户质量分。生产环境应把库存变更做成事件流：库存归零立即通过 API 将 availability 置为 out_of_stock，价格/上下架变更按请求级增量同步，并配合指数退避应对限流；高频变更用 API/同步作为 Source of Truth，托管 Feed 仅做每日全量兜底。
</details>

---

*今天系统梳理 Instagram 电商全链路：账号 → 目录 → 打标 → 商店/结算 → 投流 → 业务流程与踩坑。*
*答不出自测题？回去重读对应部分。*
