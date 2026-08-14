# WhatsApp Business 完整深度实战指南（App / Cloud API / Click-to-WhatsApp 广告）

> **领域**: 广告投放 / Meta
> **深度**: ⭐⭐⭐⭐⭐ 实战级指南
> **标签**: meta-ads, whatsapp, business-api, message-templates, click-to-whatsapp
> **更新时间**: 2026-08-14
> **类型**: 实战深度文档

---

## 一、核心概念与架构

### 1.1 WhatsApp Business 生态全景

WhatsApp 是 Meta 旗下全球最大的即时通讯应用，月活用户超过 20 亿，是全球商业沟通密度最高、打开率最高的渠道之一。与邮件（打开率 20%~40%）和短信（打开率 60%~80%）相比，WhatsApp 商业消息的打开率普遍在 **80%~99%** 区间，因此成为营销、客服、交易通知的首选私域触点。

围绕 WhatsApp 的商业能力，Meta 提供三套互相独立但互补的产品，理解它们的差异是进入本领域的第一个关键分水岭：

| 维度 | WhatsApp Business App（App） | WhatsApp Business Platform – On-Premises API | WhatsApp Business Platform – Cloud API |
|------|------------------------------|----------------------------------------------|----------------------------------------|
| 运行位置 | 手机 App（Android/iOS） | 自建服务器（Meta 托管版已停用） | 云托管，Meta 全托管 |
| 适用对象 | 小微商家、单人运营 | 中型企业自托管 | 大型/开发者，企业级 |
| 创建方式 | 应用商店下载，手机号注册 | 通过 Meta Business Manager 申请 | 通过 Meta Business Manager 申请 |
| API 访问 | 无官方开放 API（有非官方库） | Hosted/自托管 API，有自己的域名回拨 | 官方 Cloud API，`graph.facebook.com/vX.Y` |
| 多用户 | 单机单号 | 多座席共享号码 | 多座席共享号码 |
| 计费 | 无 API 费用 | 按会话计费 | 按会话计费 |
| 认证 | 无需 | Access Token | System User Token / Permanent Token |
| 维护成本 | 极低 | 高（需自管基础设施） | 低（Meta 托管） |

**核心结论**：2023 年 Meta 已宣布 On-Premises API 逐步停用，**所有新接入一律使用 Cloud API**。本文档以 Cloud API + Graph API 为技术主线，同时覆盖 App 端的运营能力（自动回复、标签、目录、快捷回复等），因为 App 与平台是一对"运营视图"与"工程接口"的关系。

```
┌────────────────────────────────────────────────────────────────────────────┐
│                   WhatsApp Business 商业能力全景                            │
├────────────────────────────────────────────────────────────────────────────┤
│                                                                            │
│  WhatsApp Business App（手机端，小微商家）                                  │
│  ├── 商业资料 Business Profile（名称/描述/网站/营业时间/地址/类目）          │
│  ├── 自动回复（问候语/离开消息/快捷回复/关键词自动回复）                     │
│  ├── 标签（内部管理会话）                                                   │
│  ├── 目录 Catalog（在聊天内展示商品）                                       │
│  ├── 快捷回复 Shortcuts                                                     │
│  └── 已读回执、置顶、静音、群发（受限）                                     │
│                                                                            │
│  WhatsApp Business Platform - Cloud API（开发者，企业级）                   │
│  ├── 消息发送（文本/模板/互动/媒体/多产品/位置/联系人）                     │
│  ├── 消息模板 Message Templates（认证/营销/实用 + 审核）                     │
│  ├── Webhook 事件回拨（消息/状态/模板审核结果）                             │
│  ├── 商业资料管理与管理系统账号                                               │
│  ├── 目录与商品（多产品消息）                                               │
│  ├── 会话窗口（24h Utility / 7天广义 Marketing）管理                        │
│  └── QR 码 / wa.me 深链 / Click-to-WhatsApp 广告                            │
│                                                                            │
│  Meta 广告体系（获客入口，与本文档强相关）                                  │
│  ├── Click-to-WhatsApp 广告（点击即开启会话）                               │
│  ├── WhatsApp Messaging Objectives 落地                                     │
│  ├── CAPI / Pixel 事件回传（会话归因）                                      │
│  └── 消息模板质量与预算评级联动                                              │
│                                                                            │
└────────────────────────────────────────────────────────────────────────────┘
```

### 1.2 WhatsApp Business Account（WABA）结构

接入 Cloud API 的第一件事不是拿手机号，而是理解账号层级。Meta 的 WhatsApp Business 账号体系是一条四层归树结构：

```
┌────────────────────────────────────────────────────────────────────────────┐
│  Meta Business Portfolio（商业资产组合/公司主体，可选，最高层）             │
│    └── Meta Business Manager / Business Account（BM 商业账户）             │
│          ├── WhatsApp Business Account（WABA，履约账号）                    │
│          │     ├── Phone Number（电话号码，1:N 挂到 WABA 下）               │
│          │     │     ├── Messaging（消息发送能力）                          │
│          │     │     ├── Message Templates（模板，1:N）                     │
│          │     │     ├── Business Profile（商业资料）                       │
│          │     │     └── Conversations（会话窗口）                          │
│          │     └── WhatsApp System User（API 调用者身份）                   │
│          ├── Ads Account（广告账户，Click-to-WhatsApp 的投放主体）          │
│          └── Pixel / Conversions（转化追踪）                                │
└────────────────────────────────────────────────────────────────────────────┘
```

**关键 ID 的区分（最高频踩坑点）：**

| 概念 | ID 示例形态 | 用途 | 说明 |
|------|------------|------|------|
| WABA ID | `123456789012345` | 账号主体 | 创建模板、管理号码用 `POST /{WABA_ID}/message_templates` |
| Phone Number ID | `456789012345678` | 号码消息能力 | 发消息、读资料、收 webhook 用 `/{PHONE_NUMBER_ID}/messages` |
| 实际手机号 | `+8613800000000` | 商家对外号码 | 需在 Meta 侧实名注册，人机验证 |
| System User Token | `EAAG...` | API 认证 | 长期令牌，替代短期 App Token |
| Template Namespace | `abc123_...` | 模板命名空间 | 与 WABA 绑定，防止跨账号冲突 |

> **经验**：很多开发者把 `WABA_ID` 当成电话号码发消息，得到 404；或把「实际手机号」当成接口路径。请牢记——**发消息一律走 `/PHONE_NUMBER_ID/messages`**，**建模板一律走 `/WABA_ID/message_templates`**。

### 1.3 电话号码的注册、限制与人机验证

一个 WABA 下可以挂多个手机号，但每条新闻与实体的商业化能力受以下核心规则约束。

**号码来源限制：**
- 必须提供一个**真实有效、可接收短信/电话呼叫验证**的手机号；
- Meta 不支持使用免费虚拟号（如 Google Voice 的免费号码、多种临时号）完成企业验证；
- 一个手机号**只能注册到一个 WhatsApp 账号**；若该号已用于普通版 WhatsApp（个人号），需先在个人号里退出才能绑定到商业 API。

**「两个国籍号码」限制的实务理解：**
- 业界常说的「一个号码两个国籍」指：**一个国家和地区代码只能注册一个 WhatsApp 商业号码**，而同一商家可以跨多个国家分别注册号码，形成多国本地号矩阵；
- 例如：`+86` 号段注册中国商业号 + `+1` 号段注册美国商业号 + `+44` 号段注册英国商业号，可分别用于本地化触达——这是 Click-to-WhatsApp 投放多国市场的常见架构；
- **踩坑**：若同一 `+86` 号码已在普通 WhatsApp 用户侧存在，商业 API 注册会失败，报错提示号码已被占用（`PHONE_NUMBER_ALREADY_REGISTERED`）。

**人机验证（Human Verification）：**
- 号码首次接入 Cloud API 前，Meta 会要求完成一台一次性的**人机验证**（在浏览器打开指定安全页，做验证码）；
- 该验证码随 Cloud API 初始化响应返回（`code` 字段），仅当验证未实现自动验证时才需要人工操作；
- 若跳过此步，后续调用 `/{WABA_ID}` 相关接口会持续返回 403 权限类错误。

### 1.4 消息类型的二分法：模板消息 vs 会话消息

这是 WhatsApp 商业消息与普通 IM 最大的差异，也是计费与合规的核心。**任何一条 WhatsApp 商业消息在发送时都只能属于「模板消息」或「会话消息」两类之一**，二者由「是否存在一个开启状态的会话窗口」决定。

```
发起方视角（谁先开口谁主导）

  企业主动（B 2 C 首触 / 无会话）：
      只能发 → 「模板消息」     （预先审核、按模板计费、24 小时窗口）
  
  用户主动（C 2 B / 会话已开）：
      只能发 → 「会话消息」     （自由文本/媒体/互动，按会话计费）

  规则：若当前存在一个“开启的会话窗口”，企业可发“会话消息”；
        若没有窗口，企业要主动触达只能发“模板消息”。
```

| 能力 | 模板消息 (Template) | 会话消息 (Session/Conversational) |
|------|---------------------|-----------------------------------|
| 触发条件 | 无会话窗口时，企业主动发 | 存在 24h 窗口（或新 7 天广义窗口）时 |
| 是否需审核 | 需要，创建后提交人工/自动审核 | 不需要，即发即用 |
| 内容自由度 | 受模板结构限制，含变量占位符 | 完全自由，文本/媒体/互动/位置皆可 |
| 计费方式 | 按「模板消息计费」（按类别单价不同） | 按「会话窗口计费」（按发起分类） |
| 复制性 | 高（同一模板群发） | 低（个性化） |
| 典型场景 | 通知、验证码、促销群发、订单状态 | 客服对话、售后跟进、多轮交互 |

### 1.5 24 小时会话窗口（24-hour Customer Service Window）

**窗口的开启与关闭（经典规则，2024 年 10 月后新增广义规则，见 2.1 深化）：**

- 每当**用户主动向商家发送消息**，或**商家成功发送一条模板消息**，即开启一个 **24 小时（客服服务）会话窗口**；
- 窗口开启期间，商家可以发送**任意数量、任意类型的会话消息**（文本、媒体、互动消息等）——这些都不计费为模板消息；
- 窗口在开启后 **24 小时整点关闭**（即窗口起点 +24h），此后商家若要再次主动触达，只能发送模板消息，从而开启**新的** 24 小时窗口；
- 会话本身（`Contact ID`）不因窗口关闭而消失，但消息能力被限制。

```
      用户发来消息 / 商家发模板成功
              │
              ▼
    ┌─────────────────────────────────┐
    │  24 小时会话窗口开启（服务窗口）   │
    │  商家可自由发会话消息（不限量）     │
    └─────────────────────────────────┘
              │
              │ 24 小时后
              ▼
        窗口关闭 ──► 商家再主动触达：只能发模板消息
                            │
                            └─► 发送成功 → 再次开新窗口
```

**时间线 ASCII（两种开启方式的差异）：**

```
范例 A：用户先开口
  00:00  用户发消息 ─────► 窗口开启（起点 T0）
  00:01  商家回复（会话消息，自由）
  12:00  商家再发一条（会话消息，自由）
  T0+24h 窗口关闭
  之后   商家主动 → 只能模板

范例 B：商家先发模板
  T0     商家发模板成功 ─► 窗口开启（起点 T0）
  T0+1h  用户回复（这是用户会话）
  T0+5h  商家在窗口内自由聊天
  T0+24h 窗口关闭
  之后   商家再主动 → 只能模板
```

---

## 二、深度原理解析

### 2.1 会话窗口机制深化：经典 24h 与「7 天广义营销窗口」

2024 年 10 月起，Meta 对会话窗口做了重要革新，理解新旧规则并存对计费与策略至关重要。

**经典 24 小时窗口（Utility / Service）：**
- 上文 1.5 所述：以用户消息或模板消息为起点，24 小时整点关闭；
- 窗口内会话消息统称为「服务会话」（utility/service conversation），按服务会话价格计费；
- 绝大多数「客服 + 售后 + 及时信息」场景依赖此窗口。

**新「7 天广义窗口」（Open Conversation / Market 分类）：**
- 当商家发送的是**营销类（Marketing）模板**或用户点击 **Click-to-WhatsApp 广告**进入时，Meta 允许开放一个最长 **7 天**的「广义（open）会话窗口」；
- 窗口内商家同样可以发送会话消息，但计费归类按**营销/开放会话（marketing/open conversation）**计费，价格通常高于服务会话；
- 该规则让「广告落地后的长周期培育」成为可能——用户点广告进会话后，商家可以在 7 天内多次跟进而无需反复发模板。

```
时间轴对比：

  服务会话（Utility）
  ──┬─────────────────────────────┬───────────►
   T0       24h                   T0+24h 关闭

  广义会话（Marketing / Open）
  ──┬─────────────────────────────────────────────────────────────────┬───►
   T0                                     最多 7 天                    T0+7d 关闭

  落地方式差异化：
  用户主动发消息 / 非营销模板    → 服务会话（24h）
  Click-to-WhatsApp 广告点击    → 广义会话（7d）
  营销类模板发送成功            → 广义会话（7d）
```

**五类会话的完整计费矩阵（费率以官方商定为准，此处给优先级理解）：**

| 会话类型 | 触发 | 窗口时长 | 相对费率 |
|---------|------|---------|---------|
| Authentication（认证） | 认证类模板 | 3 分钟（一次性计费封顶） | 最低档 |
| Marketing（营销） | 营销模板 / 广义会话 | 7 天 | 高档 |
| Utility（实用） | 实用模板 / 服务窗口 | 24 小时 | 中档 |
| Service（服务客服） | 用户消息 / 服务窗口 | 24 小时 | 低档 |
| User-initiated（用户发起） | 用户主动消息 | 24 小时 | 低档 |

> **业务含义**：面向 ROI，营销类会话价格最高，应尽量减少"用营销模板开窗但只做服务"的浪费；客服场景应优先让用户先开口，以用户发起会话（低费率）承接，而非用营销模板开高费率窗口。

### 2.2 消息模板 Message Templates 的完整分类

模板是 WhatsApp 企业主动触达的"通行证"。一条模板 = 结构化的、预先审核通过的消息，可复用、可群发、可带变量。

**历史上的四类模板：**
- **Authentication（认证）**：发送一次性密码/登录验证码，如 `Your code is {{1}}`；
- **Marketing（营销）**：促销、活动、新品、订阅推广，如 `大促 8 折，点此领取 {{1}}`；
- **Utility（实用/事务性）**：订单、物流、预约、账单、位置提醒，如 `您的包裹 {{1}} 已发货，预计 {{2}} 送达`；
- **Service（服务）**：客服对话的开启模板（较早期概念，现已与 Utility 合并理解，2025 年后官方主要保留 Auth/Marketing/Utility 三大类）。

**2025 新政后的「新模板结构」：**
随着消息模板规范更新，新创建的模板采用**更宽松但同样审核**的结构：

```
全新模板结构（新规范）：
  ├── 标题（Header）：可选，可保存文本/媒体占位符
  │     └─ 仅支持 1 个 Header（text / image / video / document / location）
  ├── 正文（Body）：必填，支持变量 {{1}} {{2}} ...
  ├── 页脚（Footer）：可选，纯文本
  └── 按钮（Buttons）：可选
        ├── 最多 2 个「快速回复按钮」（自定义行为，如"开始咨询"）
        ├── 最多 1 个「URL 按钮」（跳转链接，如"立即购买"）
        ├── 最多 1 个「电话号码按钮」（点按呼出）
        └── 最多 1 个「复制优惠券按钮」（复制验证码）
```

**模板语言与类别：**
- 每个模板必须指定**语言**（language code，如 `zh_CN`、`en_US`、`es_ES`），且模板变量值的展示语言应与语言一致；
- 类别（category）必须在创建时声明，审核会校验类别与内容是否匹配——把营销促销内容报成 Utility 是典型的**审核被拒**原因；
- 同类内容（如"订单发货通知"）如需多语言，要为每种语言各建一个模板，模板 ID 不同。

**Media Templates（媒体模板）与高品质模板等级：**
- 新规范支持 Header 为**图片（image）/视频（video）/文档（document）/位置（location）**的模板，称为 Media Template；
- Media Template 的审核更严格，且涉及素材的版权/敏感内容审查；
- Meta 根据模板的**用户反馈**（屏蔽率、举报率、投诉率）为模板打**质量评级（Quality Rating）：HIGH / MEDIUM / LOW**，并对模板施加每日发送上限。LOW 评级模板每日可发送的会话数上限会被大幅收紧。

### 2.3 模板创建与审核的状态机

模板从创建到可发送，经历一条不可跳过的审核状态链：

```
                    提交审核
    ┌──────────────────────┐
    │  PENDING（待审核）      │
    └──────────┬───────────┘
               │ 自动 + 人工审核
      ┌────────┴────────┐
      ▼                 ▼
   APPROVED         REJECTED（被拒）
      │                 │ 修改后重新提交
      │                 └────────────► 再次进入 PENDING
      ▼
   (之后可能有) 
   状态升级：PENDING → APPROVED
   状态异常：DOWN（被降级/禁用，多见于 LOW 质量 + 高投诉）
   状态删除：DELETED（可删，删后不可再用）
```

**补充状态与迁移：**
- `PAUSED`：模板被暂停（可因违规被 Meta 主动暂停）；
- `DISABLED`：模板被永久禁用；
- 模板被拒后会返回**拒绝原因**（如 `INVALID_FORMAT`、`LOW_QUALITY`、`INCORRECT_CATEGORY`、`DISALLOWED_CATEGORY` 等），需针对性修复后重新提交；
- **审核时长**：通常 5 分钟到数小时，复杂媒体模板或高音量账号可能 >24h；营销类模板审核普遍比 Utility 长。

**营销模板 vs 实用模板的差异（审核策略参考）：**

| 维度 | Utility | Marketing |
|------|---------|-----------|
| 审核通过率 | 高（事务上下文明确） | 中（受内容合规影响） |
| 审核时长 | 快 | 相对慢 |
| 触发会话 | 服务窗口（24h） | 广义窗口（7d） |
| 发送限制 | 较宽 | 更严（受质量评级约束） |
| 典型合规风险 | 扭曲为营销用途 | 夸大/误导/诱导性措辞 |

### 2.4 互动消息 Interactive Messages：按钮 / 列表 / 商品

互动消息是**会话消息（窗口开启时）**内可发送的富媒体交互组件，极大提升点击转化率。与模板中的按钮不同，互动消息的按钮**无需审核、即发即用**，是对话式营销的核心武器。

**三类互动消息：**

```
① 回复按钮消息（Reply Buttons）
   ┌───────────────────────────────┐
   │ 正文文本                        │
   │ [ 按钮A 开始咨询 ]   [ 按钮B 看报价 ] │
   └───────────────────────────────┘
   用户点按 → 回调 payload → 机器人据此分发对话分支

② 列表消息（List Message，最多 10 个 section，每 section 最多 30 行）
   ┌───────────────────────────────┐
   │ 标题：选择服务                   │
   │ 正文：请从以下选项中选择           │
   │ [ ▾ 查看选项 ]                  │
   │   ├ 服务A（描述）                │
   │   ├ 服务B（描述）                │
   │   └ 服务C（描述）                │
   └───────────────────────────────┘
   适合菜单导航、商品浏览

③ 商品/多产品消息（Product / Multi-Product Message）
   ┌───────────────────────────────┐
   │ [ 商品图 ] 商品A  ¥299          │
   │ [ 商品图 ] 商品B  ¥199          │
   │ [ 查看全部 ]                    │
   └───────────────────────────────┘
   需要关联 Catalog 目录与商品 ID
```

**各组件字段要点：**

| 组件 | 关键字段 | 约束 |
|------|---------|------|
| Reply Button | `id`(5-256 char), `title`(≤20 char), `type`=REPLY | 最多 3 个回复按钮 |
| URL Button | `url`, `type`=URL | 与回复按钮互斥组合限制 |
| List | `button`(≤20 char), `sections[].rows[].id/title/description` | sections ≤10，每 section rows ≤30 |
| Product | `catalog_id`, `product_retailer_id` | 需先绑定目录 |
| Multi-Product | `sections[].product_items[].product_retailer_id` | 最多 30 个商品、1 个 header |

**付费业务经常忽略的点**：互动消息**只能用于会话窗口内**。若窗口已关闭，发送互动消息接口会返回 403，此时必须改为发模板消息以重开窗口。

### 2.5 QR 码与 wa.me 深链的机制

QR 码和 `wa.me` 链接本质是把「潜在的 WhatsApp 会话」转成一个**可扫码 / 可点击的入口**，引导用户进入会话，从而打开（用户发起的）会话窗口。

**wa.me 链接格式：**
```
https://wa.me/<国家码+号码>?text=<预填文本>
示例：https://wa.me/8613800000000?text=你好，我想了解报价
```
- `wa.me` 只能用于**普通 WhatsApp 用户**（App / Web），它打开的是用户侧微信界面，并预填 `text` 文本；
- **注意**：`wa.me` 不能直接用于商业 API 的自动回复——它触发的是用户自己用 WhatsApp App 发消息给你的号码，之后你的平台通过 webhook 收到该用户消息。

**QR 码的来源（两种）：**
1. **WABA 侧「通过 API 生成二维码」**：`POST /{PHONE_NUMBER_ID}/qr_code`，返回一个可下载/显示的二维码图片（用于线下物料、包装、门店）；
2. **第三方生成器**：把 `wa.me` 链接或 `https://api.whatsapp.com/send?phone=...` 交给二维码工具生成图片。

**QR 与广告结合**：Click-to-WhatsApp 广告落地页、品牌线下物料普遍放 QR/wa.me，配合 `text` 预填，让同一号码承载多渠道会话入口，且全部为用户发起会话（低费率、开 24h 服务窗口）。

### 2.6 商业资料 Business Profile

商业资料（Business Profile）是用户点开你号码聊天时看到的"名片"，直接影响信任度与转化。

```
用户视角的 Business Profile 信息：
  ├── 名称（display name，审核，与类目匹配）
  ├── 简介（description，≤512 字符）
  ├── 网站（websites，最多 2 个）
  ├── 营业时间（hours，按日）
  ├── 地址（address，Map 可点击）
  ├── 邮箱（email）
  ├── 类目（category，from 官方类目树）
  ├── 头像/LOGO
  └── 状态（关于/状态文字）
```

- 通过 Cloud API：`GET /{PHONE_NUMBER_ID}/profile` 读取，`POST /{PHONE_NUMBER_ID}/profile` 更新；
- **display name 审核**：显示名和类目需要匹配，避免误导；名称被拒会返回 `APP_DISPLAY_NAME_RETRY` 等错误；
- 商业资料是**点击打开率**的重要变量：资料完整、有营业时间与地址，用户信任度显著高于裸号。

### 2.7 Click-to-WhatsApp 广告与 pre-registration（落地）

**Click-to-WhatsApp（点击开启 WhatsApp 会话）广告**是 WhatsApp 商业能力与 Meta 广告体系结合的核心形态。用户在 Facebook/Instagram 看到广告，点击"发送消息"按钮后，直接跳转到该商家号码的 WhatsApp 会话。

**pre-registration（预注册 / 预登记）的落地点：**
- 广告的落地区（destination）选择 **WhatsApp**（而非 App / 网站 / Messenger / 线索表单）；
- 点击广告后，用户先进入一个**预登记/预聊天页面（pre-registration page）**，在这里选择想聊的产品/进入点（可选），然后点击"继续"进入 WhatsApp；
- 该页面可**预填一条文本**（用户进入会话时自动发送，如"我想咨询夏季套餐"），商家 webhook 一收到即开窗并识别来意；
- Meta 侧还可在广告 object 上配置 `pre_filled_text`（预填文本）与「whatsapp_number」要使用的号码。

**落地链路（端到端）：**

```
 广告投放（Ads Manager）
   │  目标：Conversions / Engagement → destination=WhatsApp
   ▼
 用户点击 CTA（"发送消息"/"WhatsApp"）
   │
   ▼
 Pre-registration 预登记页（选择进入点 + 预填文案）
   │  [ WhatsApp 图标 + "继续" ]
   ▼
 打开 WhatsApp 会话（商家的号码）
   │  会话自动发出预填文本
   ▼
 商家 Cloud API 收到 Webhook（用户发起的会话，开 24h 窗口）
   │
   ▼
 机器人/人工客服承接 → 转化
```

**事件回传与归因联动：**
- 广告目标为转化时，需通过 **CAPI（Conversion API）** 或 Pixel 回传 `Lead`、`Purchase`、`CompleteRegistration` 等事件；
- 常用方法：`meta_send_capi(pixel_id, event_name='Lead', ...)`，将 WhatsApp 会话内的成交/潜客绑定回广告触发的用户；
- 归因依赖 `fbp/fbc`、或通过从广告进入会话的会话元数据关联。

> **获奖策略**：Click-to-WhatsApp 广告 + pre-registration 预填文本 + 会话内 CAPI 事件回传，形成「广告 → 会话 → 成交 → 归因」闭环，是当前 META 广告主增长 WhatsApp 私域流量的标准打法。

### 2.8 自动回复与窗口判定的分工

自动回复分「App 端」与「平台端」两套，二者能力不同、不可混淆：

```
                    App 端（人工/轻量）
   ┌─ 问候语（新会话开启自动发）          ┌─ 平台端（可编程，工程级）
   ├─ 离开消息（外出自动回）              ├─ Webhook 实时接收 → 代码路由
   ├─ 快捷回复（预设文本，手点）          ├─ 关键词/意图 → 互动消息分流
   ├─ 关键词自动回复（简易规则）          ├─ 多轮状态机对话
   └─ 无 API，纯手机端 UI               ├─ 与 CRM/订单系统打通
                                         └─ 并发、限流、审计日志
```

**工程侧自动回复的关键前提——窗口判定：**
- webhook 收到一条**用户消息** → 该用户会话窗口必然开着 → 可以直接回**会话消息/互动消息**；
- webhook 收到一条**商家自己 sent 的模板状态** → 说明这是模板发送的结果，不代表窗口（模板本身成功就开了窗口）；
- 若要判断是否能自由聊天，核心看**最后一次窗口起点是否在 24h/7d 内**，本地维护 `session_last_open[contact_id]`。

### 2.9 消息模板质量评级与预算/广告的联动

这是「WhatsApp 商业」与「Meta 广告」交叉的深层机制：

- 每个**电话号**（而非 WABA 全局）都有一份消息质量评级，由用户**屏蔽率（block rate）、举报率（report rate）、投诉率（complaint rate）**加权得出；
- 评级分 `HIGH / MEDIUM / LOW`，同时影响：**每日可开启会话上限、模板可用性、以及作为 Click-to-WhatsApp 落地号的可信度**；
- 评级为 LOW 时，Meta 可能限制该号码的营销发送能力，甚至暂停；
- **踩坑**：营销模板若发送过密、文案诱导（告知收件人点链接可获奖但实为空），会迅速推高屏蔽与投诉，导致号码降级——进而拖累广告落地质量，广告学习期指标变差。

**降级自救三板斧：**
1. 收紧营销频率，降低打扰；
2. 优化文案，去掉夸大/诱导措辞，让预期与内容一致；
3. 对高投诉用户做退订/黑名单，避免持续触达。

---

## 三、生产环境实战

### 3.0 环境准备与三要素

在任何代码之前，先确认已拿到能在请求中反复出现的三个关键值：

```
 1. WABA_ID           → 建模板 / 管号码
 2. PHONE_NUMBER_ID   → 发消息 / 读资料 / 收消息
 3. ACCESS_TOKEN      → 认证（System User Token 为佳，避免短期令牌过期）
```

**Token 策略（重要）：**
- 开发初期可用 Graph API Explorer 生成的短期 token 快速验证；
- 生产必须使用 **System User Token**（在 BM → System Users 创建，授予 `whatsapp_business_messaging`、`whatsapp_business_management` 权限，app secret 生成长期 token）；
- 长 token 存储在安全环境变量中，禁止写死进代码仓库。

**先用 curl 验证连通性（发一条文本模板）：**

```bash
# 1) 读取商业资料，验证 token 与 phone number id 有效
curl -X GET "https://graph.facebook.com/v21.0/${PHONE_NUMBER_ID}/profile?access_token=${ACCESS_TOKEN}"

# 2) 列出已审核通过的模板
curl -X GET "https://graph.facebook.com/v21.0/${WABA_ID}/message_templates?access_token=${ACCESS_TOKEN}&limit=100"

# 3) 列出号码下的会话（验证号码与资料）
curl -X GET "https://graph.facebook.com/v21.0/${WABA_ID}/phone_numbers?access_token=${ACCESS_TOKEN}"
```

### 3.1 发送文本消息（会话窗口内）

当窗口已开启时，最简单的是发**文本消息**。

```bash
curl -X POST "https://graph.facebook.com/v21.0/${PHONE_NUMBER_ID}/messages" \
  -H "Authorization: Bearer ${ACCESS_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "messaging_product": "whatsapp",
    "to": "8613800000000",
    "type": "text",
    "text": {
      "preview_url": false,
      "body": "您好，欢迎咨询我们的服务！如需帮助请直接回复。"
    }
  }'
```

响应示意：
```json
{
  "messaging_product": "whatsapp",
  "contacts": [{"input": "8613800000000", "wa_id": "8613800000000"}],
  "messages": [{"id": "wamid.HBgNODYx...."}]
}
```

> **注**：窗口未开时发纯文本会得 403（`Re-engagement message / No Window`），需改用模板消息。

**对应 `meta_send_whatsapp_message` 封装：**

```python
def meta_send_whatsapp_message(
    self, phone_number_id: str, to: str, body: str,
    message_type: str = "text", **kwargs
) -> Dict:
    """发送 WhatsApp 消息（text/template/interactive），对应 Cloud API POST /{phone-number-id}/messages"""
    import requests
    token = self.credentials.get('meta', {}).get('access_token', '')
    url = f"https://graph.facebook.com/v21.0/{phone_number_id}/messages"
    payload = {
        'messaging_product': 'whatsapp',
        'to': to,
        'type': message_type,
    }
    if message_type == 'text':
        payload['text'] = {'preview_url': kwargs.get('preview_url', False), 'body': body}
    elif message_type == 'template':
        payload['template'] = {
            'name': kwargs.get('template_name'),
            'language': {'code': kwargs.get('language', 'zh_CN')},
            'components': kwargs.get('components', []),
        }
    resp = requests.post(url, headers={'Authorization': f'Bearer {token}'}, json=payload, timeout=30)
    return resp.json()
```

### 3.2 创建消息模板并提交审核

模板在 WABA 层级创建（注意不是 phone number id）。

```bash
# 创建一条中文 Utility 模板（带变量 + 快速回复按钮）
curl -X POST "https://graph.facebook.com/v21.0/${WABA_ID}/message_templates" \
  -H "Authorization: Bearer ${ACCESS_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "order_shipping_update_zh",
    "language": "zh_CN",
    "category": "UTILITY",
    "components": [
      {
        "type": "HEADER",
        "format": "TEXT",
        "text": "订单 {{1}} 已发货"
      },
      {
        "type": "BODY",
        "text": "您的订单 {{1}} 已发出，预计 {{2}} 送达。物流单号 {{3}}。"
      },
      {
        "type": "FOOTER",
        "text": "如需帮助请回复本消息"
      },
      {
        "type": "BUTTONS",
        "buttons": [
          {
            "type": "QUICK_REPLY",
            "text": "查看物流"
          },
          {
            "type": "QUICK_REPLY",
            "text": "联系客服"
          }
        ]
      }
    ]
  }'
```

响应含模板 id 与 status（通常 `PENDING`）：
```json
{
  "id": "1234567890",
  "status": "PENDING",
  "category": "UTILITY",
  "name": "order_shipping_update_zh",
  "language": "zh_CN"
}
```

> **要点**：`name` 只能含小写字母、数字与下划线，不能有空格或特殊字符；Header/Footer 中出现的变量 `{{1}}` 与 Body 变量计数独立（Header 与 Body 各自从 `{{1}}` 编号时可能冲突，实务建议按官方规范区分配置）。

**对应的 `meta_create_whatsapp_template` 封装与查询：**

```python
def meta_create_whatsapp_template(
    self, waba_id: str, name: str, language: str,
    category: str, components: List[Dict], **kwargs
) -> Dict:
    """创建 WhatsApp 消息模板，对应 POST /{waba-id}/message_templates"""
    import requests
    token = self.credentials.get('meta', {}).get('access_token', '')
    url = f"https://graph.facebook.com/v21.0/{waba_id}/message_templates"
    payload = {
        'name': name,
        'language': language,
        'category': category,
        'components': components,
    }
    resp = requests.post(url, headers={'Authorization': f'Bearer {token}'}, json=payload, timeout=30)
    return resp.json()

def meta_list_whatsapp_templates(self, waba_id: str, **kwargs) -> List[Dict]:
    """列出 WABA 下模板，对应 GET /{waba-id}/message_templates"""
    import requests
    token = self.credentials.get('meta', {}).get('access_token', '')
    params = {'access_token': token, 'limit': kwargs.get('limit', 100)}
    data = requests.get(f"https://graph.facebook.com/v21.0/{waba_id}/message_templates",
                        params=params, timeout=30).json()
    return data.get('data', [])
```

### 3.3 发送模板消息（重开窗口）

模板审核通过（status=APPROVED）后即可发送。

```bash
curl -X POST "https://graph.facebook.com/v21.0/${PHONE_NUMBER_ID}/messages" \
  -H "Authorization: Bearer ${ACCESS_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "messaging_product": "whatsapp",
    "to": "8613800000000",
    "type": "template",
    "template": {
      "name": "order_shipping_update_zh",
      "language": { "code": "zh_CN" },
      "components": [
        {
          "type": "body",
          "parameters": [
            { "type": "text", "text": "SO-2026-0001" },
            { "type": "text", "text": "8月20日" },
            { "type": "text", "text": "SF1234567890" }
          ]
        }
      ]
    }
  }'
```

> **错误排查**：若模板中有按钮，且按钮包含 URL/优惠券，还需在 components 中传对应参数；缺失参数会导致 `ParamComponentFail` 之类错误。

### 3.4 互动消息：回复按钮 / 列表 / 商品

**回复按钮消息（Reply Buttons，会话窗口内）：**

```bash
curl -X POST "https://graph.facebook.com/v21.0/${PHONE_NUMBER_ID}/messages" \
  -H "Authorization: Bearer ${ACCESS_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "messaging_product": "whatsapp",
    "recipient_type": "individual",
    "to": "8613800000000",
    "type": "interactive",
    "interactive": {
      "type": "button",
      "body": { "text": "请问您需要哪个帮助？" },
      "action": {
        "buttons": [
          { "type": "reply", "reply": { "id": "btn_sales", "title": "咨询报价" } },
          { "type": "reply", "reply": { "id": "btn_aftersales", "title": "售后服务" } },
          { "type": "reply", "reply": { "id": "btn_other", "title": "其他" } }
        ]
      }
    }
  }'
```

**列表消息（List）：**

```bash
curl -X POST "https://graph.facebook.com/v21.0/${PHONE_NUMBER_ID}/messages" \
  -H "Authorization: Bearer ${ACCESS_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "messaging_product": "whatsapp",
    "to": "8613800000000",
    "type": "interactive",
    "interactive": {
      "type": "list",
      "header": { "type": "text", "text": "选择服务套餐" },
      "body": { "text": "请从以下套餐中选择一项" },
      "footer": { "text": "所选套餐信息将随后续消息发送" },
      "action": {
        "button": "查看选项",
        "sections": [
          {
            "title": "基础套餐",
            "rows": [
              { "id": "plan_a", "title": "标准版", "description": "适合个人起步" },
              { "id": "plan_b", "title": "进阶版", "description": "适合成长型" }
            ]
          },
          {
            "title": "企业套餐",
            "rows": [
              { "id": "plan_c", "title": "旗舰版", "description": "适合团队协作" }
            ]
          }
        ]
      }
    }
  }'
```

**商品消息（Product，需先绑定 Catalog）：**

```bash
curl -X POST "https://graph.facebook.com/v21.0/${PHONE_NUMBER_ID}/messages" \
  -H "Authorization: Bearer ${ACCESS_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "messaging_product": "whatsapp",
    "recipient_type": "individual",
    "to": "8613800000000",
    "type": "interactive",
    "interactive": {
      "type": "product",
      "body": { "text": "推荐这款热销产品" },
      "footer": { "text": "点击查看详情" },
      "action": {
        "catalog_id": "1234567890",
        "product_retailer_id": "SKU-1001"
      }
    }
  }'
```

**对应的 `meta_send_whatsapp_interactive` 封装：**

```python
def meta_send_whatsapp_interactive(
    self, phone_number_id: str, to: str,
    interactive_type: str = "button", **kwargs
) -> Dict:
    """发送互动消息（button/list/product/multi_product），对应 POST /{phone-number-id}/messages"""
    import requests
    token = self.credentials.get('meta', {}).get('access_token', '')
    url = f"https://graph.facebook.com/v21.0/{phone_number_id}/messages"
    payload = {
        'messaging_product': 'whatsapp',
        'to': to,
        'type': 'interactive',
        'interactive': {'type': interactive_type, **kwargs.get('interactive', {})},
    }
    resp = requests.post(url, headers={'Authorization': f'Bearer {token}'}, json=payload, timeout=30)
    return resp.json()
```

### 3.5 商业资料读取与更新

```bash
# 读取
curl -X GET "https://graph.facebook.com/v21.0/${PHONE_NUMBER_ID}/profile?access_token=${ACCESS_TOKEN}"

# 更新（POST 合并更新 profile 字段）
curl -X POST "https://graph.facebook.com/v21.0/${PHONE_NUMBER_ID}/profile" \
  -H "Authorization: Bearer ${ACCESS_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "messaging_product": "whatsapp",
    "about": "专注跨境电商与私域运营咨询",
    "description": "提供 WhatsApp 商业落地方案、Click-to-WhatsApp 广告投放、消息模板与自动化客服。",
    "websites": ["https://example.com"],
    "address": "中国 上海",
    "email": "hello@example.com",
    "profile_picture_handle": ""
  }'
```

**对应的 `meta_get_whatsapp_business_profile` 封装：**

```python
def meta_get_whatsapp_business_profile(self, phone_number_id: str, **kwargs) -> Dict:
    """获取 WhatsApp 商业资料，对应 GET /{phone-number-id}/profile"""
    import requests
    token = self.credentials.get('meta', {}).get('access_token', '')
    resp = requests.get(
        f"https://graph.facebook.com/v21.0/{phone_number_id}/profile?fields=about,description,websites,address,email,vertical,profile_picture_url",
        headers={'Authorization': f'Bearer {token}'}, timeout=30)
    return resp.json()
```

### 3.6 QR 码与 wa.me 深链落地

**生成二维码（Cloud API）：**

```bash
# 获取二维码图片（保存在服务器侧或转存 CDN）
curl -X POST "https://graph.facebook.com/v21.0/${PHONE_NUMBER_ID}/qr_code" \
  -H "Authorization: Bearer ${ACCESS_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "image_format": "PNG",
    "qr_code_size": 300
  }'
```

**wa.me 深链（供广告落地 / 物料植入）：**

```python
def build_wa_me_link(phone_e164: str, prefill_text: str = "") -> str:
    """生成 wa.me 深链，phone_e164 形如 8613800000000"""
    digits = phone_e164.lstrip("+")
    link = f"https://wa.me/{digits}"
    if prefill_text:
        from urllib.parse import quote
        link += "?text=" + quote(prefill_text)
    return link

def meta_generate_whatsapp_qr(self, phone_number_id: str, size: int = 300, **kwargs) -> bytes:
    """生成 WhatsApp 号码二维码（PNG bytes），对应 POST /{phone-number-id}/qr_code"""
    import requests
    token = self.credentials.get('meta', {}).get('access_token', '')
    url = f"https://graph.facebook.com/v21.0/{phone_number_id}/qr_code"
    resp = requests.post(
        url,
        headers={'Authorization': f'Bearer {token}'},
        json={'image_format': 'PNG', 'qr_code_size': size},
        timeout=30)
    return resp.content
```

### 3.7 验证号码状态（两国籍/多国号码架构）

在接入 Click-to-WhatsApp 之前，建议用 Cloud API 校验号码的归属与状态：

```bash
curl -X GET "https://graph.facebook.com/v21.0/${WABA_ID}/phone_numbers?access_token=${ACCESS_TOKEN}"
```

响应每个号码含 `verified_name`（企业名）、`code_verification_status`（`NOT_VERIFIED` / `VERIFIED`）、`quality_rating`、`platform_type` 等字段，用于多国号码矩阵的巡检：

```json
{
  "data": [
    {
      "id": "1234",
      "display_phone_number": "+86 13800000000",
      "verified_name": "Ryan 咨询",
      "quality_rating": "HIGH",
      "code_verification_status": "VERIFIED",
      "throughput": { "level": "STANDARD" }
    },
    {
      "id": "5678",
      "display_phone_number": "+1 2025550147",
      "verified_name": "Ryan Consulting",
      "quality_rating": "MEDIUM",
      "code_verification_status": "VERIFIED"
    }
  ]
}
```

### 3.8 自动回复：Webhook 接收与窗口路由

**接收 webhook（FastAPI 示例）：**

```python
from fastapi import FastAPI, Request, Response
import hmac, hashlib, logging

app = FastAPI()
WABA_TOKEN = "your-verify-token"
APP_SECRET = "your-app-secret"

logger = logging.getLogger("whatsapp")

@app.get("/webhook")
async def verify(request: Request):
    """Webhook 验证：Meta 首次接入时的 GET 握手"""
    q = request.query_params
    mode = q.get("hub.mode")
    token = q.get("hub.verify_token")
    challenge = q.get("hub.challenge")
    if mode == "subscribe" and token == WABA_TOKEN:
        return Response(content=challenge, media_type="text/plain")
    return Response(status_code=403)

@app.post("/webhook")
async def receive(request: Request):
    """接收消息/状态事件"""
    payload = await request.json()
    # 校验签名（生产必须做）
    body_bytes = await request.body()
    signature = request.headers.get("X-Hub-Signature-256", "")
    expected = "sha256=" + hmac.new(APP_SECRET.encode(), body_bytes, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, expected):
        return Response(status_code=401)

    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            for msg in value.get("messages", []):
                from_id = msg.get("from")
                msg_type = msg.get("type")
                # 用户消息 → 窗口必然开启 → 可自由回复
                reply = route_by_intent(msg)
                if reply:
                    api.meta_send_whatsapp_message(
                        PHONE_NUMBER_ID, from_id, reply["body"],
                        message_type=reply["type"], **reply.get("kwargs", {}))
    return {"status": "ok"}
```

**窗口判定与消息类型路由（核心算法）：**

```python
def route_by_intent(msg: dict) -> dict:
    """根据收到的用户消息路由到「互动消息 / 文本 / 模板」"""
    mtype = msg.get("type")
    text = ((msg.get("text") or {}).get("body", "")).strip()
    interactive = msg.get("interactive")

    if mtype == "interactive" and interactive:
        payload = (interactive.get("button_reply") or interactive.get("list_reply") or {})
        pid = payload.get("id", "")
        # 按钮/列表回调 → 用互动消息继续分支
        if pid == "btn_sales":
            return {"body": "好的，客服马上为您核算报价。", "type": "text"}
        if pid == "btn_aftersales":
            return {"body": "为您转接售后，请稍候。", "type": "text"}
        return {"body": f"您选择了：{pid}", "type": "text"}

    # 关键词自动回复
    if text:
        if any(k in text for k in ("价格", "报价", "多少钱")):
            return {"body": "请选择套餐查看价格：", "type": "interactive",
                    "kwargs": {"interactive": {"type": "list", ...}}}
        if any(k in text for k in ("人工", "客服", "转人工")):
            return {"body": "正在为您转接人工客服……", "type": "text"}
    # 兜底：礼貌回复
    return {"body": "收到您的消息，我们的顾问会尽快回复。", "type": "text"}
```

### 3.9 批量发送与限流（缩短延时）

批量发模板/会话消息时，Cloud API 有吞吐（throughput）限制。不同级别的号码吞吐不同，需做限速与重试。

```python
import time, threading
from queue import Queue
from concurrent.futures import ThreadPoolExecutor

def batch_send(path_meta, phone_number_id, targets, send_one, max_workers=10):
    """按号码吞吐受限地批量发送。
    send_one: callable(contact) -> dict(发送单条)。
    """
    results = []
    sem = threading.Semaphore(max_workers)

    def worker(contact):
        with sem:
            for attempt in range(3):
                try:
                    r = send_one(contact)
                    if r.get("error") is None:
                        results.append((contact, "ok", r))
                        return
                    # 429 限流 → 指数退避
                    if r.get("error", {}).get("code") == 429 or "rate" in str(r.get("error", {})):
                        time.sleep(2 ** attempt)
                        continue
                    results.append((contact, "fail", r))
                    return
                except Exception as e:
                    time.sleep(2 ** attempt)
            results.append((contact, "fail", None))

    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        list(ex.map(worker, targets))
    return results
```

> **经验**：不要在营销模板刚通过审核的瞬间就打全量——先小样本（如 50~200 人）观察质量与打开，再逐步放量，避免大规模触发屏蔽导致号码降级。

### 3.10 Click-to-WhatsApp 广告对象与落地（Ads Manager / API）

在 Ads Manager 落地 Click-to-WhatsApp 的核心配置：

```
Campaign Objective：Conversions 或 Engagement（边栏选「发送 WhatsApp 消息」作为转化目标）
 ├─ Ad Set
 │    ├─ Destination：WhatsApp
 │    ├─ WhatsApp：选择要使用的商业号码（可多选/按地区）
 │    └─ 优化：Conversions（以 CAPI Lead/Purchase 优化）或 Engagement
 └─ Ad
      ├─ CTA：Send WhatsApp Message
      ├─ Pre-filled text：如「你好，我想咨询夏季套餐」
      └─ 创意：图片/视频/Reels
```

**用 Marketing API 创建 Click-to-WhatsApp 广告（核心字段）：**

```python
def create_click_to_whatsapp_ad(api, ad_account_id, page_id, whatsapp_number_id,
                                creative_spec, objective="OUTCOME_CONVERSIONS"):
    """创建 Click-to-WhatsApp 广告的示意（依赖 meta-api-expert 的广告创建方法）"""
    # 1) 广告创意（destination 为 WhatsApp）
    ad_creative = api.meta_create_ad_creative(
        ad_account_id,
        object_story_spec={
            "page_id": page_id,
            "link_data": {
                "call_to_action": {"type": "WHATSAPP_MESSAGE", "value": {"link": "https://wa.me/..."}},
                "message": creative_spec["message"],
                "link": creative_spec.get("link"),
                "image_hash": creative_spec.get("image_hash"),
            },
        },
        object_type="LINK",
        **{"adlabels": []}
    )
    # 2) 广告组（destination=WhatsApp，whatsapp number id 关联）
    adset = api.meta_create_ad_set(ad_account_id, ...)  # 含 destination 字段
    # 3) 广告
    ad = api.meta_create_ad(ad_account_id, adset["id"], ad_creative["id"], name="CTA-WhatsApp")
    return {"creative": ad_creative, "adset": adset, "ad": ad}
```

> **归因要点**：WhatsApp 会话内的转化不会自动回到广告报表，必须通过 **CAPI 事件回传**（`meta_send_capi`）把 `Lead / CompleteRegistration / Purchase` 打回，Meta 才能优化与统计 ROI。

### 3.11 端到端工作流编排示例

把上述能力串成「广告 → 会话 → 培育 → 转化」完整流水线：

```python
def whatsapp_acquisition_pipeline(api, phone_number_id, pixel_id, leads: list):
    """Click-to-WhatsApp 获客流水线示意"""
    results = []
    for lead in leads:
        # 1) 发送实用模板开窗（订单/预约类）
        tmpl_resp = api.meta_send_whatsapp_message(
            phone_number_id, lead["phone"], "",
            message_type="template",
            template_name="appointment_confirm_zh",
            language="zh_CN",
            components=[{"type": "body", "parameters": [
                {"type": "text", "text": lead["name"]},
                {"type": "text", "text": lead["slot"]},
            ]}]
        )
        # 2) 发送互动消息收集意向
        itx = api.meta_send_whatsapp_interactive(
            phone_number_id, lead["phone"], "button",
            interactive={"type": "button",
                         "body": {"text": "是否预约本月顾问 1v1？"},
                         "action": {"buttons": [
                             {"type": "reply", "reply": {"id": "yes", "title": "预约"}},
                             {"type": "reply", "reply": {"id": "no", "title": "暂不需要"}},
                         ]}}
        )
        # 3) 回传 CAPI 事件（把成交/潜客打回广告归因）
        capi = api.meta_send_capi(pixel_id, event_name="Lead",
                                  user_data={"phone": lead["phone"]},
                                  event_source_url="https://wa.me/...")
        results.append({"phone": lead["phone"], "template": tmpl_resp, "interactive": itx, "capi": capi})
    return results
```

### 3.12 多产品消息与目录联动（简要，避免与 Catalog 文档重复）

- 商品消息依赖 Catalog（目录）与 Product；
- `POST /{phone-number-id}/messages` 的 `interactive.type=multi_product` 支持一次展示多达 30 个商品；
- 目录/商品创建的完整细节见 `knowledge/advertising/meta-ads/meta-ads-catalog-deep.md`，此处不展开。

### 3.13 模板变量的正确传递（Header 与 Body 编号冲突案例）

**高频 bug**：新规范中 Header 与 Body 各自可以有变量，但 Cloud API 发送时 `components` 里的 `parameters` 是按「组件类型」传的。若 Header 也用 `{{1}}`、Body 也用 `{{1}}`，发送时需分别放在各自组件下，参数值各自对应各自组件内的占位符顺序：

```bash
curl -X POST "https://graph.facebook.com/v21.0/${PHONE_NUMBER_ID}/messages" \
  -H "Authorization: Bearer ${ACCESS_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "messaging_product": "whatsapp",
    "to": "8613800000000",
    "type": "template",
    "template": {
      "name": "media_announce_zh",
      "language": {"code": "zh_CN"},
      "components": [
        {
          "type": "header",
          "parameters": [
            {"type": "image", "image": {"link": "https://cdn.example.com/banner.png"}
          ]
        },
        {
          "type": "body",
          "parameters": [
            {"type": "text", "text": "夏季"}, {"type": "text", "text": "8月20日"}
          ]
        }
      ]
    }
  }'
```

> **教训**：参数个数不匹配是 `ParamComponentFail`、`PARAMETER_MISMATCH` 的头号来源；建议发送前用脚本校验每个组件占位符个数是否等于参数个数。

---

## 四、常见问题与排查

### 4.1 模板审核被拒：十大高频原因与对策

| 拒绝原因码（示意） | 含义 | 对策 |
|-------------------|------|------|
| `INCORRECT_CATEGORY` | 类别报错（把营销报成 Utility） | 按内容真实分类，营销内容报 Marketing |
| `INVALID_FORMAT` | 模板结构/变量格式不对 | 检查组件顺序与变量编号 |
| `LOW_QUALITY` | 内容质量差/诱导 | 去掉夸大、虚假、诱导性措辞 |
| `DISALLOWED_CATEGORY` | 使用被禁类别/内容 | 涉及赌博/金融夸大/色情等需走特殊审核或放弃 |
| `INCORRECT_LANGUAGE` | 语言与变量内容不符 | 模板语言与变量值语言一致 |
| `DUPLICATE_TEMPLATE` | 与已有模板重复 | 改名或删除重复项 |
| `EXPIRED_TOKEN` | 创建时 token 过期 | 换长期 token 重试 |
| `INSUFFICIENT_PERMISSION` | 缺少 `whatsapp_business_management` | 系统用户补权限 |
| `APP_DISPLAY_NAME_RETRY` | 显示名/类目不符 | 修正 display name |
| `POLICY_VIOLATION` | 违反消息规范 | 阅读官方消息规范，改写内容 |

**排查流程：**

```
模板被拒
   ↓ 读取拒绝详情（GET /{waba-id}/message_templates 看 status 与 error 字段）
   ├─ category 问题 → 改 category
   ├─ 内容问题 → 改文案重提（去掉诱导/夸大）
   ├─ 变量问题 → 修正组件/参数
   └─ 权限问题 → 修 token/权限
   重新提交 → 进入 PENDING → 等待 APPROVED
```

### 4.2 24h 窗口误解与"发不出去"排查

**最容易误判的场景：**

```
症状：会话消息发送返回 403「Re-engagement message」（或称 No Open Window）
根因：当前不存在开启的会话窗口 → 纯会话消息（text/interactive）不允许
解决：改用模板消息发送；或用 消息史/本地 session 维护判断当前窗口状态

症状：窗口明明开了却发不出去
排查：1) 是否误用模板消息发自由文本（模板名不存在）→ 404
      2) 号码质量评级 LOW 被限流 → 看 429/-1
      3) token 过期 → 401
      4) 号码类型/权限异常 → 403 权限类
```

**判定工具：查询号码的唯一开口信息**

```python
def assert_window_open(api, phone_number_id, contact_id, last_open_ts) -> bool:
    """本地窗口判定：last_open_ts 为最后一次窗口起点（秒）"""
    import time
    now = time.time()
    return (now - last_open_ts) < 24 * 3600
```

### 4.3 号码注册：人机验证与两国籍限制

**遇错清单：**

| 现象 | 根因 | 解法 |
|------|------|------|
| 注册报 `PHONE_NUMBER_ALREADY_REGISTERED` | 号码已在普通 WhatsApp/其他商业账号 | 先在原账号退出/注销，再重新注册 |
| 报 403 人机验证未过 | 跳过 Human Verification 步骤 | 完成浏览器验证码后再调 WABA API |
| 报 `INVALID_VERIFY_CODE` | 验证码输入错误 | 重新获取 code |
| `+86` 号码创建第二商业号失败 | 同国家号段单一商业号 | 需换号码或用其它国家号段 |
| 号码被检测为虚拟/一次性号 | 免费虚拟号被禁 | 换真实运营商号码 |

**多国号码矩阵建议：**

```
目标市场  建议号段   用途                   落地方式
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
中国      +86       国内客服/私域            wa.me + QR
美国      +1        跨境/本地化              Click-to-WhatsApp 广告
英国      +44       欧洲本地化               Click-to-WhatsApp 广告
东南亚    +65/+60   新兴市场                 wa.me + QR

同号码不可跨两国家重复注册；每个市场一个本地号，提升打开率与信任。
```

### 4.4 质量评级下降与发送限制

**评级 → 限制联动：**

```
HIGH   → 每日可开启会话数：较高
MEDIUM → 中等，可能被抽样限制
LOW    → 每日上限大幅收紧，营销类几乎不可用
        持续 LOW → 号码被暂停（严重）

触发因素：屏蔽率 / 举报率 / 投诉率升高
常见诱因：营销过密、文案诱导（点链接与承诺不符）、
          频繁向未订阅用户群发、垃圾模板
```

**恢复评级的最佳实践：**
1. 暂停营销模板，给用户"冷却期"；
2. 只对明确订阅/高意向用户发送；
3. 优化文案降低预期落差；
4. 提供便捷退订，避免用户用"举报/屏蔽"表达不满；
5. 长期用 Utility 模板承载高频通知，营销低频化。

### 4.5 Webhook 不触发与消息状态核查

**Webhook 常见问题：**

| 现象 | 排查 |
|------|------|
| 收不到用户消息 | 1) 确认 app 已订阅 `messages` 字段；2) 确认 webhook 校验 token 一致；3) 确认号码属于该 WABA |
| 收不到发送状态 | 需在 App settings 订阅 `message_deliveries`、`message_reads`、`message_sent` |
| 回执重复 | Meta 会重试投递，接口需**幂等**（用 message id/entry id 去重） |
| 签名校验失败 | 需用 App Secret 做 HMAC-SHA256 校验；不要关掉校验 |

**消息送达状态机（便于做发送监控）：**

```
sent（已发送）
  └─ delivered（已送达）
       └─ read（已读，若开启已读回执）
  ├─ failed（失败）→ 查 error code（如 131048 触达限制、131026 号码无效）
  └─ 最终：以 sent/failed 为准做重试审计
```

### 4.6 常见错误码速查（Cloud API）

| 错误码 | 含义 | 处理 |
|--------|------|------|
| 100 | 参数错误/缺少字段 | 检查请求体结构与必填字段 |
| 190 | 无效 access token | 刷新/重新生成 token |
| 200 | 权限不足 | 系统用户补 `whatsapp_business_*` 权限 |
| 429 | 限流/并发超限 | 退避重试，控制吞吐 |
| 131000 | 一般性 WhatsApp 错误 | 看子错误码 |
| 131026 | 接收方号码无效 | 校验号码格式（含国家码，去 + 号） |
| 131030 | 会话窗口未开启 | 改用模板消息 |
| 131042 | 号码未注册/未验证 | 完成人机验证与证书 |
| 131048 | 触达数量限制 | 评级 LOW / 营销量超限，改善评级 |
| 131056 | 消息太小（<1 字节） | 模板/正文不能为空 |
| 131062 | 消息对应用户不可达 | 对方已退订/封禁，放弃 |

### 4.7 模板变量与"发送后立即开窗"的连锁

**易忽略点**：一旦模板消息发送成功，系统会为接收者开一个新窗口（服务或广义，取决于模板类别）。因此：

- 发**营销模板** → 开 7 天广义窗口（高费率），若能在这期间完成转化则划算；
- 发**Utility 模板** → 开 24h 服务窗口；
- 若同一用户连续被发多种模板，窗口类型会**迁移**为最新一次生成的类型，计费取最新；多次发送可能多次计费。**排错先看**：给同一个人反复开模板窗口，账单可能以营销类别计算，超出预算预期。

**预算与质量评级的关系**：我们会在投放侧限制单用户 7 天内模板触达次数，并监控每次账单的会话类别分布，避免被"营销会话"拖高成本。

---

## 五、自测题

### 自测题 1：会话窗口与消息类型

你收到一条 webhook 用户消息之后，能否直接通过 API 发送一条**非模板文本消息**给该用户？发送一条**互动按钮消息**呢？如果用户**从未**主动发过消息、也没有任何窗口，此时你要主动触达，必须使用哪种消息类型？请说明规则依据。

<details><summary>答案</summary>

可以。只要当前存在一个开启的会话窗口（用户刚发来消息必然开窗），商家就可以发送任意数量的会话消息，包括文本和互动消息（按钮/列表/商品），且这些都不按模板计费。

若用户从未发起、也无窗口，则必须使用**模板消息**（预先审核通过的）来主动触达，发送成功后会自动开启新的窗口。

规则依据：消息只能属于「模板消息」或「会话消息」之一；会话消息仅在窗口开启时允许；模板消息无论何时都能发（但要求模板已 APPROVED）。

</details>

### 自测题 2：模板审核被拒后的正确处理

你的 Utility 模板因 `INCORRECT_CATEGORY` 被拒，里面其实写的是"全场 8 折促销"。请判断正确做法，并说明修改类别后会对会话窗口和计费产生什么连锁影响。

<details><summary>答案</summary>

正确做法是**将类别改为 Marketing**（因为内容是促销），而不是继续用 Utility 硬塞；同时优化文案去掉可能的夸大/诱导措辞，重新提交进入 PENDING 直到 APPROVED。

连锁影响：营销售出后开的是 **7 天广义（Marketing）会话窗口**，计费按营销会话（高费率）而非服务（24h）。这意味着同一模板的窗口时长与单价都变了——若误报 Utility 即便侥幸通过，也属违规且存在被降级/暂停风险。因此类别必须真实匹配内容，并相应调整预算预期。

</details>

### 自测题 3：Click-to-WhatsApp 广告的归因闭环

你投放 Click-to-WhatsApp 广告，用户在 WhatsApp 会话里完成了咨询并留下联系方式。为什么广告系统的转化报表里可能看不到这笔成交？你该怎么做才能让广告学习到「有效线索/成交」并据此优化出价？

<details><summary>答案</summary>

因为 WhatsApp 会话内的转化**不会自动回传**到广告归因系统。广告点击只触发会话打开，会场内的成交/线索不产生页面转化事件，Meta 无法自动得知。

正确做法是通过 **Conversion API（CAPI）** 或 Pixel 主动回传事件——例如在你处理会话（识别为有效线索/成交）时调用 `meta_send_capi(pixel_id, event_name='Lead'/'Purchase', user_data={...})`，把该 users 的 fbp/fbc 或 phone 关联回去。Meta 将其作为 ads conversion 信号进入学习/优化，进而能按此类转化优化出价并获得 ROI 统计。

</details>

### 自测题 4：多国号码与本地化落地

你想同时在北美、拉美、东南亚三个市场通过 Click-to-WhatsApp 拉新，且希望打开率最高。请给出号码与落地资源的组织建议，并说明「同一个号码注册两个国家队」是否可行。

<details><summary>答案</summary>

建议为每个目标市场分配一个**单独的本地号码**（如 `+1` 北美、`+34`/`+52` 拉美、`+65`/`+60` 东南亚），都挂到同一 WABA 下；每个号码配置对应语言的 business profile 与本地化模板；广告 Ad Set 按国家选择对应号码，落地用 wa.me/Click-to-WhatsApp 并预填本地语言文案。

「同一个号码注册两个国家」在现代规则下不可行/不推荐：一个手机号只能注册一个 WhatsApp 账号，且同一国家号段单一商业号；跨市场应使用不同国家号的独立号码，形成多国号码矩阵，而非把单个号码硬塞两个市场。这既能提升本地化打开率，也避免号码冲突与政策风险。

</details>

### 自测题 5：号码质量评级下降的应急处理

你的号码质量评级从 HIGH 掉到了 LOW，且营销模板发送频繁受限。请列出排查这条号码时你会先检查的指标、可能的诱因，以及最优先的三步恢复动作。

<details><summary>答案</summary>

先检查三类核心信号：**屏蔽率（block rate）、举报率（report rate）、投诉率（complaint rate）**，结合最近营销模板的发送量、已读/未读、点击后落地是否与承诺一致。

常见诱因：营销过密导致打扰、文案故意诱导（点链接与结果不符）、对未订阅/无度用户群发。

最优先三步恢复：
1. **暂停营销模板**并停止对高打扰用户的触达，让用户冷却；
2. **收敛触达范围**，仅保留明确订阅/高意向用户，并提供便捷退订；
3. **重写文案**去掉夸大/虚假，用 Utility 模板承载高频通知、营销低频化，持续观察评级回升后再渐进放量。

</details>

---

## 附录 A：Cloud API 端点速查表

| 操作 | 方法 | 端点 |
|------|------|------|
| 发送消息（文本/模板/互动/媒体/多产品/位置/联系人） | POST | `/{phone-number-id}/messages` |
| 检查号码是否在 WhatsApp（批量） | POST | `/{phone-number-id}/contacts` |
| 创建消息模板 | POST | `/{waba-id}/message_templates` |
| 列出消息模板 | GET | `/{waba-id}/message_templates` |
| 更新模板 | POST | `/{waba-id}/message_templates/{template-id}` |
| 删除模板 | DELETE | `/{waba-id}/message_templates/{name}` |
| 读取商业资料 | GET | `/{phone-number-id}/profile` |
| 更新商业资料 | POST | `/{phone-number-id}/profile` |
| 生成 QR 码 | POST | `/{phone-number-id}/qr_code` |
| 列出号码（多国矩阵管理） | GET | `/{waba-id}/phone_numbers` |
| 注册/验证号码 | POST | `/{phone-number-id}/register` |
| 请求号码证书 | POST | `/{phone-number-id}/request_code` |
| 媒体上传 | POST | `/{phone-number-id}/media` |
| 媒体下载 | GET | `/{media-id}` |

## 附录 B：本文档脚本方法映射（新增命名建议）

以下为本文为 `scripts/meta_api.py` / `scripts/ad_platform_api.py` 合理扩展的 `meta_*` 方法签名，作为团队落地参考：

```python
def meta_send_whatsapp_message(self, phone_number_id, to, body, message_type='text', **kwargs): ...
def meta_create_whatsapp_template(self, waba_id, name, language, category, components, **kwargs): ...
def meta_list_whatsapp_templates(self, waba_id, **kwargs): ...
def meta_get_whatsapp_business_profile(self, phone_number_id, **kwargs): ...
def meta_send_whatsapp_interactive(self, phone_number_id, to, interactive_type='button', **kwargs): ...
def meta_generate_whatsapp_qr(self, phone_number_id, size=300, **kwargs): ...
def meta_send_whatsapp_media(self, phone_number_id, to, media_type, link, **kwargs): ...
def meta_register_whatsapp_number(self, phone_number_id, **kwargs): ...
```

其可复用的既有能力包括：
- `meta_list_conversation_templates(account_id, **kwargs)`：列出对话模板（可在其上包一层获取模板状态）；
- `meta_create_conversation_template(account_id, **kwargs)`：创建对话模板；
- `meta_list_standard_conversions(account_id, **kwargs)`：列出标准转化；
- `meta_send_capi(pixel_id, event_name=..., **kwargs)`：回传 CAPI 事件用于 Click-to-WhatsApp 归因。

## 附录 C：参考与延伸

- [Meta WhatsApp Business Platform Cloud API 文档](https://developers.facebook.com/docs/whatsapp/cloud-api)
- [WhatsApp Message Templates 规范](https://developers.facebook.com/docs/whatsapp/message-templates)
- [Meta 消息模板质量评级](https://developers.facebook.com/docs/whatsapp/message-templates/quality)
- [Click-to-WhatsApp 广告（Messaging Destinations）](https://www.facebook.com/business/help/click-to-whatsapp)
- 本仓库延展：`knowledge/advertising/meta-ads/meta-ads-catalog-deep.md`（目录/商品，本文商品互动消息依赖）、`meta-ads-marketing-api-deep.md`（Graph API 与广告对象）。

---

> 本文由 Ryan 个人知识库生成，覆盖 WhatsApp Business App 与 Cloud API、消息模板、QR/wa.me、商用资料、互动消息、24h/7 天会话窗口、Click-to-WhatsApp 广告与 pre-registration 落地、自动回复、批量发送、质量评级与踩坑排查全链路。实践部分请以 Meta 官方最新 API 版本与费率表为准。
