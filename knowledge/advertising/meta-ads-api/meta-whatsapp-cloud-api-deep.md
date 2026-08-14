# WhatsApp Cloud API 深度解析：Messages / Templates / Media / Interactive / Webhooks 全链路实战

> **领域**: 广告投放 / Meta
> **深度**: ⭐⭐⭐⭐⭐ API 专项指南
> **标签**: meta-ads-api, whatsapp, cloud-api, messages, templates, interactive
> **更新时间**: 2026-08-14
> **类型**: api-guide/deep

---

## 目录

- [一、核心概念与架构](#一核心概念与架构)
  - [1.1 WhatsApp Business Platform 全景](#11-whatsapp-business-platform-全景)
  - [1.2 核心对象关系图：App → WABA → Phone Number → 消息](#12-核心对象关系图app--waba--phone-number--消息)
  - [1.3 Cloud API 与 On-Premises API 对比](#13-cloud-api-与-on-premises-api-对比)
  - [1.4 认证体系：System User、长期 Token 与 App Secret Proof](#14-认证体系system-user长期-token-与-app-secret-proof)
  - [1.5 API 版本化与 Graph API 基地址](#15-api-版本化与-graph-api-基地址)
  - [1.6 沙盒（测试号码）与生产号码切换](#16-沙盒测试号码与生产号码切换)
  - [1.7 消息全链路数据流](#17-消息全链路数据流)
  - [1.8 核心术语表](#18-核心术语表)
- [二、深度原理解析](#二深度原理解析)
  - [2.1 Messages API 全类型消息](#21-messages-api-全类型消息)
  - [2.2 会话窗口机制与按会话计费](#22-会话窗口机制与按会话计费)
  - [2.3 模板系统：分类、创建、审核与状态机](#23-模板系统分类创建审核与状态机)
  - [2.4 Interactive Messages 交互消息](#24-interactive-messages-交互消息)
  - [2.5 Media API：上传、下载与媒体 ID](#25-media-api上传下载与媒体-id)
  - [2.6 电话号码管理、质量评级与消息限额](#26-电话号码管理质量评级与消息限额)
  - [2.7 QR Codes 与 wa.me 进入对话](#27-qr-codes-与-wame-进入对话)
  - [2.8 Webhooks：订阅、验签与事件处理](#28-webhooks订阅验签与事件处理)
  - [2.9 错误码体系深度剖析](#29-错误码体系深度剖析)
  - [2.10 费用结构与费用豁免](#210-费用结构与费用豁免)
- [三、生产环境实战](#三生产环境实战)
  - [3.1 生产架构设计](#31-生产架构设计)
  - [3.2 发送文本消息（含 curl 与 Python）](#32-发送文本消息含-curl-与-python)
  - [3.3 发送模板消息与变量填充](#33-发送模板消息与变量填充)
  - [3.4 发送交互消息（按钮/列表/目录）](#34-发送交互消息按钮列表目录)
  - [3.5 媒体上传、发送与下载](#35-媒体上传发送与下载)
  - [3.6 模板生命周期管理](#36-模板生命周期管理)
  - [3.7 WABA 与电话号码管理](#37-waba-与电话号码管理)
  - [3.8 二维码生成与 wa.me 落地页](#38-二维码生成与-wame-落地页)
  - [3.9 Webhook 服务实现（FastAPI 完整示例）](#39-webhook-服务实现fastapi-完整示例)
  - [3.10 会话窗口状态机与追踪器](#310-会话窗口状态机与追踪器)
  - [3.11 限流、重试与幂等](#311-限流重试与幂等)
  - [3.12 生产踩坑清单](#312-生产踩坑清单)
- [四、常见问题与排查](#四常见问题与排查)
  - [4.1 错误码速查表](#41-错误码速查表)
  - [4.2 模板审核问题排查](#42-模板审核问题排查)
  - [4.3 24 小时窗口问题排查](#43-24-小时窗口问题排查)
  - [4.4 媒体问题排查](#44-媒体问题排查)
  - [4.5 认证与权限问题排查](#45-认证与权限问题排查)
  - [4.6 Webhook 问题排查](#46-webhook-问题排查)
  - [4.7 典型问题定位决策树](#47-典型问题定位决策树)
- [五、自测题](#五自测题)
- [参考资源](#参考资源)

---

## 一、核心概念与架构

### 1.1 WhatsApp Business Platform 全景

WhatsApp Business Platform 是 Meta 面向企业提供的官方消息通道，通过 **Graph API**（Cloud API）以 REST 方式接入。与普通用户版 WhatsApp 不同，企业通过它发送**模板消息**、**交互消息**、**媒体消息**，并接收用户的消息与事件回调。

```
┌─────────────────────────────────────────────────────────────────────┐
│                  WhatsApp Business Platform 全景                      │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌──────────────┐      ┌─────────────────────────────┐               │
│  │  你的后端服务  │      │  Meta Graph API (Cloud API) │               │
│  │  (CRM/工单/    │──────▶  https://graph.facebook.com/ │               │
│  │   广告系统)    │      │  /v{ver}/{phone-number-id}/ │               │
│  └──────┬───────┘      └──────────────┬──────────────┘               │
│         │                             │                              │
│         │ Webhooks(HTTPS 回调)        │ 消息/模板/媒体/QR 读写          │
│         ▼                             ▼                              │
│  ┌──────────────┐      ┌─────────────────────────────┐               │
│  │  事件处理器    │◀─────│      WhatsApp 云端基础设施     │               │
│  │ (消息/状态/质量)│      │  (投递、会话计费、模板审核)      │               │
│  └──────────────┘      └──────────────┬──────────────┘               │
│                                        │                              │
│                                        ▼                              │
│                          ┌─────────────────────────────┐              │
│                          │     终端用户 WhatsApp 客户端    │              │
│                          │  (iOS / Android / Web/桌面端)  │              │
│                          └─────────────────────────────┘              │
│                                                                       │
│  广告链路: Click-to-WhatsApp (CFT) 广告 ──▶ wa.me/二维码 ──▶ 对话      │
└─────────────────────────────────────────────────────────────────────┘
```

**Cloud API 的关键特征：**

1. **托管式**：消息基础设施由 Meta 托管，企业无需自建 WhatsApp 服务器，无需关心 WhatsApp 协议层（Signal 协议、加密握手、长连接）实现。
2. **REST + HTTPS**：全部通过 Graph API 的 HTTP 端点读写，天然适配现有广告系统/CRM 技术栈。
3. **Webhook 驱动**：入站消息、消息状态（sent/delivered/read/failed）、模板审核状态、号码质量变化均通过 Webhook 推送。
4. **按会话计费**：2023 年起从"按条计费"改为"按会话计费"（Conversation-Based Pricing），会话时长按类型区分（24h/72h）。
5. **模板审核前置**：企业主动发起的营销/工具/认证类消息必须使用经过审核的模板，无法自由拼接文本。

### 1.2 核心对象关系图：App → WABA → Phone Number → 消息

Cloud API 的对象层级是理解一切端点的前提。**每一层都有独立的 ID，端点路径完全由 ID 驱动**：

```
┌────────────────────────────────────────────────────────────────┐
│                    Meta Business Manager (BM)                   │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │              Meta 应用 (App)                              │  │
│  │  - app_id / app_secret                                    │  │
│  │  - 系统用户 (System User) + 长期访问令牌                    │  │
│  │  - 订阅 WhatsApp 产品 (Product: whatsapp_business_messaging)│  │
│  └──────────────────────┬───────────────────────────────────┘  │
│                         │ owns                                  │
│  ┌──────────────────────▼───────────────────────────────────┐  │
│  │        WhatsApp Business Account (WABA)                  │  │
│  │  - waba_id（一级资源容器）                                │  │
│  │  - 拥有 message_templates（模板库）                       │  │
│  │  - 拥有 phone_numbers（业务号码集合）                     │  │
│  │  - 可订阅 App（subscribed_apps）                          │  │
│  └──────────────────────┬───────────────────────────────────┘  │
│                         │ contains                             │
│  ┌──────────────────────▼───────────────────────────────────┐  │
│  │      WhatsApp 业务号码 (Phone Number / Sender)            │  │
│  │  - phone_number_id（消息发送主体）                         │  │
│  │  - 质量评级 high/medium/low                                │  │
│  │  - 每日业务发起会话限额 250 → 1K → 10K → 100K               │  │
│  │  - 会话（Conversation）在此号码维度产生                      │  │
│  └──────────────────────┬───────────────────────────────────┘  │
│                         │ sends / receives                     │
│  ┌──────────────────────▼───────────────────────────────────┐  │
│  │                    消息 (Message)                         │  │
│  │  - message_id（wamid.xxx）                                │  │
│  │  - 类型: text/image/audio/video/document/sticker/         │  │
│  │         location/contacts/interactive/template/           │  │
│  │         reaction/button/order/system                       │  │
│  └──────────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────────┘
```

**对象 ID 获取路径：**

| 想获取什么 | 查询路径 | 说明 |
|---|---|---|
| WABA ID | `GET /{business-id}/owned_whatsapp_business_accounts` | BM 旗下所有 WABA |
| 号码 ID | `GET /{waba-id}/phone_numbers` | 该 WABA 下所有号码及 `phone_number_id` |
| 号码详情 | `GET /{phone-number-id}?fields=verified_name,display_phone_number,quality_rating` | 名称、评级、注册状态 |
| 模板列表 | `GET /{waba-id}/message_templates` | 该 WABA 的模板库 |
| 会话列表 | `GET /{phone-number-id}/conversations` | 号码维度会话（分页） |

> **踩坑经验**：很多新手把 `phone_number`（如 15550123456）与 `phone_number_id`（纯数字 ID）混淆。**消息发送端点用的是 `phone_number_id`，不是电话号码**。如果拿手机号直接拼 URL，会得到 `(#100) Invalid parameter`。

### 1.3 Cloud API 与 On-Premises API 对比

| 维度 | Cloud API（本指南主题） | On-Premises API（本地部署） |
|---|---|---|
| 部署形态 | Meta 托管，纯 REST 调用 | 自建 Docker 容器（whatsapp-business-api） |
| 接入成本 | 低：一个 App + 一个号码即可 | 高：需要服务器、容器编排、运维 |
| 协议 | HTTPS/JSON | 容器内 gRPC 端口 + 外部 HTTP 封装 |
| 版本升级 | Meta 灰度发布，按版本号切换 | 自行拉取镜像升级，需停机窗口 |
| 媒体存储 | 上传到 Meta 云端，返回媒体 ID | 本地挂载卷存储 |
| Webhook | 与 Graph API 同域验签（app_secret HMAC） | 自定义密钥，无统一验签规范 |
| 计费 | 按会话计费（Conversation-Based Pricing） | 按消息计费（Message-Based Pricing，已迁移） |
| 适合场景 | 中小团队、广告系统集成、快速上线 | 超大流量、强数据驻留合规诉求 |

> **演进事实**：Meta 已在逐步淘汰按消息计费的 On-Premises 模式，自 2024 年起所有新接入统一走 Cloud API。**新项目一律选择 Cloud API**，本指南全部内容基于 Cloud API。

### 1.4 认证体系：System User、长期 Token 与 App Secret Proof

Cloud API 认证由三层组成，缺一不可：

```
┌──────────────────────────────────────────────────────────────┐
│ 认证链路                                                      │
│                                                               │
│ ① 长期访问令牌 (Permanent Token)                              │
│    - 由 Business Manager → System Users → 生成               │
│    - 关联: App + WABA + 权限 (whatsapp_business_messaging)   │
│    - 有效期: 不自动过期（除非撤销）                            │
│    - 头: Authorization: Bearer <TOKEN>                        │
│                                                               │
│ ② App Secret Proof（可选但强烈推荐）                          │
│    - appsecret_proof = HMAC-SHA256(app_secret, token)         │
│    - 所有请求追加 appsecret_proof 参数                        │
│    - 防止 Token 被盗后在第三方复用                            │
│                                                               │
│ ③ App 权限 (Permissions)                                      │
│    - whatsapp_business_messaging: 收发消息                    │
│    - whatsapp_business_management: 管理 WABA/模板/号码        │
│    - business_management: 访问 BM 资源                        │
│                                                               │
└──────────────────────────────────────────────────────────────┘
```

**关键点：**

1. **不要用短期用户 Token 上生产**。开发时用 Graph API Explorer 生成的短期 Token 只适合调试；生产环境必须使用 System User 生成的**长期令牌**（never expires）。
2. **App Secret Proof 是防泄露的最后防线**。开启后，Meta 会用 `app_secret` 对每个请求的 Token 做 HMAC 校验；即使 Token 被拖走，攻击者没有 app_secret 也无法复用。
3. Token 粒度是 **App × 系统用户**，权限范围在创建系统用户时勾选。若新增 WABA 后调用报 `(#200) Permissions error`，多半是系统用户权限未覆盖新 WABA。

**Python 侧生成 appsecret_proof 的规范写法：**

```python
import hmac
import hashlib

def build_appsecret_proof(app_secret: str, access_token: str) -> str:
    """按 Meta 规范生成 appsecret_proof（HMAC-SHA256 十六进制小写）"""
    return hmac.new(
        app_secret.encode('utf-8'),
        access_token.encode('utf-8'),
        hashlib.sha256,
    ).hexdigest()
```

**curl 中的完整认证形态：**

```bash
curl -X POST "https://graph.facebook.com/v20.0/105118562409025/messages" \
  -H "Authorization: Bearer EAAG...long-term-token..." \
  -H "Content-Type: application/json" \
  -d '{
        "messaging_product": "whatsapp",
        "to": "8613800138000",
        "type": "text",
        "text": { "preview_url": false, "body": "Hello from Cloud API" }
      }'
```

### 1.5 API 版本化与 Graph API 基地址

Graph API 每季度发布一个新版本（v21.0 → v22.0 → …），**每个版本自发布起约支持 2 年**，过期后调用返回 `(#100) Unsupported get request` 或版本错误。

```
基地址模板:
  https://graph.facebook.com/{api-version}/{object-id}/{edge}

常用版本号写法:
  v20.0  — 2023-05 发布，2025 年进入弃用期
  v21.0  — 2024-01 发布
  v22.0  — 2024-05 发布
  ...
  生产建议: 固定到当前最新稳定版本，避免每季度跟随
```

**版本选择策略（生产建议）：**

1. **固定版本**：在配置中心定义 `GRAPH_VERSION`，全团队统一，禁止散落硬编码。
2. **提前迁移**：Meta 会在版本弃用前通过 Business Manager 通知；留出 2 周灰度窗口，新旧版本并行验证。
3. **不追新**：除非新版本修复了你的阻塞 bug，否则不必每季度升级；但也不要等到弃用前一周才动。

```python
# scripts/meta_api.py 风格配置段
GRAPH_BASE = "https://graph.facebook.com"
GRAPH_VERSION = "v20.0"          # 固定版本，随团队升级节奏统一调整
WABA_ID = "105118562409025"
PHONE_NUMBER_ID = "105118562409026"
SYSTEM_USER_TOKEN = "EAAG..."    # 生产环境应从密钥管理服务注入，严禁入库
APP_SECRET = "xxxx"              # 同上
```

### 1.6 沙盒（测试号码）与生产号码切换

每个新创建的 Meta App 会**自动附带一个测试号码**（格式 `+1 555 010 1234` 等）。沙盒环境与生产环境的差异必须清醒认知：

| 维度 | 沙盒（测试号码） | 生产号码 |
|---|---|---|
| 接收方 | 最多 5 个已添加的测试接收人 | 任意真实 WhatsApp 用户 |
| 模板审核 | 自动通过（秒级，便于联调） | 人工审核，数分钟到数天 |
| 自由文本消息 | 可在 24h 窗口内发给测试接收人 | 只能在服务会话窗口内回复 |
| 配额 | 宽松，主要用于联调 | 按质量评级分级限额 |
| 计费 | 免费 | 按会话计费 |
| 上线要求 | 无 | 需真实号码 + 业务验证（可选） |

**沙盒联调的正确姿势：**

1. 在 App 后台「WhatsApp → API Setup」添加测试接收人手机号（必须能收到验证码）。
2. 用测试号码把**消息收发、模板变量、交互按钮、媒体上传、Webhook 验签**全链路打通。
3. 联调完成后申请生产号码：将真实号码添加进 WABA → 通过短信/语音验证码注册（`request_code` / `verify_code`）。
4. 生产号码上线前必须**重新创建生产模板**（沙盒自动通过的模板不代表能过人工审核）。

> **踩坑经验**：沙盒能发自由文本，让很多人误以为生产也能。生产号码在**非服务窗口**用 `type=text` 发消息，必然收到 `131026 Message Undeliverable` 或 `131051` 窗口错误。沙盒通过 ≠ 生产可发，模板策略要按生产标准提前准备。

### 1.7 消息全链路数据流

以"用户点击广告 → 进入对话 → 企业回复 → 用户回复 → 状态回执"为例，完整时序：

```
 用户                  WhatsApp           Cloud API          你的后端
  │                       │                   │                  │
  │ 点击 CFT 广告/扫码      │                   │                  │
  │──────────────────────▶│                   │                  │
  │ 打开会话, 发送消息       │                   │                  │
  │──────────────────────▶│ 入站消息           │                  │
  │                       │──────────────────▶│ ① POST /webhook  │
  │                       │                   │    messages 事件  │
  │                       │                   │─────────────────▶│
  │                       │                   │  业务处理(查单/工单)│
  │                       │                   │◀──────────────────│
  │                       │                   │ ② POST /{pn-id}/   │
  │                       │                   │    messages 回复   │
  │                       │◀──────────────────│                   │
  │◀──────────────────────│                   │                   │
  │ 发送状态 sent          │                   │ ③ statuses 事件   │
  │◀──────────────────────│──────────────────▶│─────────────────▶│
  │ 投递状态 delivered     │                   │ ④ statuses 事件   │
  │◀──────────────────────│──────────────────▶│─────────────────▶│
  │ 已读 read             │                   │ ⑤ statuses 事件   │
  │◀──────────────────────│──────────────────▶│─────────────────▶│
  │                       │                   │ ⑥ conversations   │
  │                       │                   │    新会话事件      │
  │                       │                   │─────────────────▶│
```

**数据流要点：**

1. **入站消息必须用 Webhook 接收**，Cloud API 没有"拉取收件箱"的主动接口（`GET /{pn-id}/messages` 只能查最近消息，不能替代 Webhook）。
2. **状态回执（sent/delivered/read）也是 Webhook 事件**，字段 `type=statuses`，通过 `statuses[0].id` 关联发送的 `message_id`。
3. **会话事件（conversations）用于计费与窗口追踪**，携带 `origin.type`（service/marketing/utility/authentication）与 `expiration_timestamp`。
4. 全链路是**异步**的：POST 消息接口返回 `messages[0].id` 只代表"已受理"，不代表"已送达"，最终状态以 statuses Webhook 为准。

### 1.8 核心术语表

| 术语 | 全称/含义 | 关键 ID/字段 |
|---|---|---|
| WABA | WhatsApp Business Account | `waba_id`，模板与号码的容器 |
| Phone Number ID | 业务号码在 API 中的标识 | `phone_number_id`（发送主体） |
| Sender/Recipient | 发送方/接收方 | 发送方=`phone_number_id`，接收方=`to`(手机号) |
| Message ID | 消息唯一标识 | `wamid.xxx...`，用于状态关联 |
| Template | 模板消息（企业主动消息的唯一形式） | `name` + `language` 唯一 |
| Conversation | 会话（计费单元） | 24h/72h，按 origin 分 4 类 |
| Session Window | 会话窗口 | 服务 24h；营销/工具/认证 72h |
| CFT | Click to WhatsApp 广告 | 广告点击进入 wa.me 对话 |
| wa.me | 短链入口 | `https://wa.me/<phone>?text=...` |
| Quality Rating | 号码质量评级 | high/medium/low |
| Messaging Limit | 每日业务发起会话上限 | 250 → 1K → 10K → 100K |
| App Secret Proof | Token 防复用校验 | HMAC-SHA256(app_secret, token) |
| Webhook | 事件推送回调 | 订阅 messages/statuses/conversations 等字段 |
| System User | BM 系统用户 | 生成长期令牌的主体 |
| Test Number | 沙盒号码 | 最多 5 个测试接收人，模板自动审核 |

---

### 2.2 会话窗口机制与按会话计费

#### 2.2.1 什么是会话（Conversation）

会话是 **Meta 计费与投递规则的统一单元**。它不是"一次聊天"，而是一个**有窗口期、有类型（origin）的时间段**，由"最后一条消息时刻"或"模板发送时刻"作为锚点。

```
会话窗口时间线（服务会话 24h 为例）
─────────────────────────────────────────────────────────────────────
 客户发起消息              最后一条消息                 窗口关闭(24h)
   │                          │                            │
   ▼                          ▼                            ▼
   ├────────── 服务会话窗口（24 小时）──────────────────────┤
   │   █ 此处企业可自由发 text/media/interactive  █         │
   │                                                   │
   │   ↓ 24h 到达，窗口关闭                              │
   │   若企业仍想触达 → 必须用 模板消息 → 开启新会话       │
   │   新会话类型 = 模板类别(marketing/utility/auth)      │
   └─────────────────────────────────────────────────────┘
```

**会话的开启方式（两个来源）：**

| 开启方式 | 触发条件 | 会话类型（origin） | 窗口期 |
|---|---|---|---|
| 客户发起 | 客户主动发消息 | service（服务） | 24h |
| 企业模板发起 | 在无窗口/窗口内发送模板消息 | 由模板 category 决定 | 72h |
| 企业回复 | 窗口内回复客户（自由文本） | 计入已有 service 会话 | 24h |

**会话类型（origin）与窗口期（2024-11-01 后的口径）：**

| origin | 窗口期 | 典型内容 | 计费 |
|---|---|---|---|
| service | 24h | 客服回复、人工问答 | 客户发起入口免费，企业发起按 service 费 |
| marketing | 72h | 促销、活动、新品 | 按 marketing 费 |
| utility | 72h | 订单、物流、账单、预约确认 | 按 utility 费 |
| authentication | 72h | OTP 验证码、登录 | 按 authentication 费（享 50% 折扣） |

> **2024-11-01 定价改版要点**：marketing 会话从 24h 延长到 **72h**；utility/authentication 维持 72h；service 维持 24h。换算成商业意义：每次营销模板触达，你有 72 小时让客户在同一个会话里完成多轮互动，而仍只计一次 marketing 会话费用。

#### 2.2.2 窗口边界与自由文本消息的区别

这是**最容易在生产出事故**的规则：

- **窗口内（service 会话未关闭）**：可以自由发送 text/image/video/audio/document/interactive，**不额外收费**（计入当前 service 会话）。
- **窗口外**：**任何自由文本/媒体消息都会被拒绝**（典型错误码 `131026` / `131051`）。唯一触达手段是**发模板消息**，且模板开启的是**新会话**并按模板类别计费。

```
窗口外发送 text 的执行结果：
POST /{pn-id}/messages  type=text
        │
        ▼
HTTP 400  body: (#131026) Message Undeliverable
  details: "Message failed to send because more than 24 hours
            have passed since the customer last replied..."
```

**服务端必须自维护的窗口状态**（不能依赖 Meta 每次告诉你有窗口）：

1. 收到 `conversations` 事件（`origin.type=service`）→ 记录窗口开始（或重置）。
2. 收到任何 `messages` 事件（客户来消息）→ **重置 24h 计时**。
3. 窗口内出站自由文本 → 无需查模板。
4. 窗口外想触达 → 路由到模板发送逻辑（选合适 category 的模板）。
5. 客户不回复也不来新事件 → 24h 后按窗口外处理。

> **踩坑经验**：会话窗口的锚点是"最后一条客户消息"。客户 23:59 回复，0:00 仍算窗口内；客户 21:00 回复，次日 21:00 后窗口关闭。很多团队按"自然日归零"实现，导致客户傍晚来消息、次日早上自由回复失败，直接在 7 点高峰一堆 131026。**必须用"相对最后一条消息 + 24h"实现，而非自然日**。

### 2.3 模板系统：分类、创建、审核与状态机

模板（Message Template）是**企业主动触达客户的唯一形式**，也是 Cloud API 中最重、最吃审核经验的部分。

#### 2.3.1 模板分类（Category）

| Category | 用途 | 示例 | 审核重点 |
|---|---|---|---|
| MARKETING | 营销推广 | 促销、新品、优惠券 | 需真实退订/引导、不误导 |
| UTILITY | 工具通知 | 订单、物流、账单、预约、退款 | 需与业务动作强相关 |
| AUTHENTICATION | 认证 | OTP 验证码、双因素登录 | 需有安全提示文案 |

> 说明：认证模板发送的验证码在服务/第三方 BI 有额外限制，且**认证类别模板目前只在部分市场开放**。utility 是审核通过率最高、最稳的类别。

#### 2.3.2 模板组成部分与限制

一个模板由若干 **component** 组成：`header`（可选）、`body`（必填）、`footer`（可选）、`buttons`（可选）。

```
模板组件结构
┌─────────────────────────────────────┐
│ HEADER (可选)                        │
│   text    : 标题文本，≤60字符        │
│   image   : 图片(≤5MB)              │
│   video   : 视频(≤16MB)             │
│   document: 文档(≤100MB)            │
│   location: 定位                    │
├─────────────────────────────────────┤
│ BODY (必填)                          │
│   ≤1024字符，支持变量 {{1}}..{{N}}   │
│   ★ 变量上限 = 10 个                 │
│   ★ 必须为每个变量填 示例值(example)  │
├─────────────────────────────────────┤
│ FOOTER (可选)                        │
│   ≤60字符，纯文本，无变量            │
├─────────────────────────────────────┤
│ BUTTONS (可选, ≤3个)                 │
│   quick_reply : 快速回复按钮(≤25字符) │
│   url         : 外链跳转按钮         │
│   phone_number: 拨号按钮             │
│   copy_code   : 复制验证码按钮(auth) │
└─────────────────────────────────────┘
```

**限制速查（硬性，超限即审核拒绝或创建失败）：**

| 项 | 上限 |
|---|---|
| Body 长度 | ≤1024 字符 |
| Body 变量（占位符） | ≤10 个（{{1}}~{{10}}） |
| 变量示例值（example） | 每个变量必填，否则创建报 131026 或审核被拒 |
| Header text 长度 | ≤60 字符 |
| Footer 长度 | ≤60 字符（无变量） |
| 按钮数量 | ≤3 个 |
| 按钮文本长度 | ≤25 字符 |
| 模板名 | 全小写字母、数字、下划线，首字符为字母 |

**变量写法：** Body 中 `{{1}}`、`{{2}}` 为占位符，创建时应倒序引用（`{{2}}` 在 `{{1}}` 前会导致审核拒绝）。**example 中变量值不能填 `{{1}}` 本身**，必须填真实示例（如 `{{1}}` → `13800138000`）。

#### 2.3.3 创建模板（curl）

```bash
curl -X POST "https://graph.facebook.com/v20.0/105118562409025/message_templates" \
  -H "Authorization: Bearer EAAG..." \
  -H "Content-Type: application/json" \
  -d '{
    "name": "order_shipping_update_cn",
    "language": "zh_CN",
    "category": "UTILITY",
    "components": [
      {
        "type": "HEADER",
        "format": "TEXT",
        "text": "订单物流更新"
      },
      {
        "type": "BODY",
        "text": "您好 {{1}}，您的订单 {{2}} 已发出，预计 {{3}} 送达，请注意查收。",
        "example": { "body_text": [["张三", "SO20260814", "8 月 20 日"]] }
      },
      {
        "type": "FOOTER",
        "text": "如未收到请回复本消息"
      }
    ]
  }'
```

**语言（language）** 取值如 `zh_CN`、`en_US`、`en_GB`、`es` 等。**模板名 + 语言构成唯一键**：同名同语言只能有一个，重复创建返回错误。

#### 2.3.4 审核状态机

```
                   ┌────────────┐
                   │   PENDING   │  ← 提交后排队人工审核
                   └─────┬──────┘
                         │
        ┌────────────────┼─────────────────┐
        ▼                ▼                 ▼
   ┌─────────┐     ┌──────────┐      ┌──────────┐
   │PENDING_IN_│    │ APPROVED  │      │ REJECTED  │
   │  REVIEW  │     └────┬─────┘      └────┬─────┘
   │(审核中)   │          │                │ 可发起申诉
   └─────────┘          │                └──▶ IN_APPEAL ──▶ APPROVED/REJECTED
                        ▼
              ┌────────────────┐
              │ PAUSED(DISABLED)│ ← 质量问题/违规被收回
              └───────┬────────┘
                      │ 修复后可重新提交
                      ▼
                 ┌──────────┐
                 │ APPROVED  │ (再次通过)
                 └──────────┘
   DELETE/deregister: 从库中移除
```

**状态清单：**

| 状态 | 含义 | 能否发送 |
|---|---|---|
| PENDING | 已提交，排队审核 | 否 |
| PENDING_IN_REVIEW | 人工复核中 | 否 |
| APPROVED | 审核通过 | 能 |
| REJECTED | 审核拒绝（返回拒绝原因） | 否 |
| IN_APPEAL | 已申诉待复核 | 否 |
| PAUSED | 因质量问题/违规被暂停 | 否 |
| DISABLED | 被禁用 | 否 |
| DELETED | 已删除 | 否 |

**审核时长**：最快几分钟，慢则数天（涉及人工复核）。**生产上线前要提前 1~2 天把模板全部提交**，不能等到上线当天。

#### 2.3.5 常见审核拒绝原因（真实业务复盘）

1. **营销模板缺少真实退订说明**：缺少"回复 STOP 退订"或用户可取消的说明，被以 spam 风险拒绝。
2. **示例变量填了占位符**：`example` 里填 `{{1}}`、`xxx` 这种会被判为"无意义示例"。
3. **变量顺序倒序**：body 里写 `{{2}} ... {{1}}`。
4. **header/media 尺寸超限**：图片超过 5MB 等。
5. **文案过度承诺**：如"100% 中奖""保证到账"，涉误导。
6. **模板名与内容不符**：名字叫 order，内容却在推新品（类别与内容不匹配）。
7. **正常业务模板被误判**：通过**申诉（IN_APPEAL）**提交，附上真实使用截图与业务说明。

> **踩坑经验（重复模板名）**：不同语言共用同一语义模板时，很多人直接复用同名 → 上层 `name` 冲突失败。正确做法是 `name` 保持一致、`language` 区分（同一 name 可有多语言），或者 `name` 带业务前缀（如 `order_ship_zh`）。但**同一 name+language 不可重复创建**——重复创建即便 head 修好也会因已存在而报错。

### 2.4 Interactive Messages 交互消息

交互消息（`type=interactive`）让用户**不离开对话**就能完成选择、跳转、下单等动作，按 `action` 的类型区分：

```
Interactive Messages 组件结构
┌──────────────────────────────────────────────────┐
│ INTERACTIVE                                       │
│  ├─ type: button | list | product | product_list  │
│  ├─ header (可选): text/image/video/document      │
│  ├─ body   (必填): 说明文字 ≤1024                 │
│  ├─ footer (可选): ≤60                            │
│  └─ action                                        │
│      ├─ button   : buttons[] ≤3, 每按钮 title≤25  │
│      ├─ list     : button(触发文案) + sections[]  │
│      │             每 section: title + rows[]     │
│      │             每 list ≤10 rows               │
│      ├─ catalog  : 目录消息                        │
│      └─ product  : 单品消息                        │
└──────────────────────────────────────────────────┘
```

#### 2.4.1 按钮（button / quick_reply）

一组快速回复按钮，最多 3 个，用户点击后把 `reply.id` 作为一条入站消息回传。

```json
{
  "type": "interactive",
  "interactive": {
    "type": "button",
    "body": { "text": "请问您需要什么帮助？" },
    "footer": { "text": "点击下方按钮快速选择" },
    "action": {
      "buttons": [
        { "type": "reply", "reply": { "id": "btn_order", "title": "查订单" } },
        { "type": "reply", "reply": { "id": "btn_sale", "title": "看促销" } },
        { "type": "reply", "reply": { "id": "btn_human", "title": "转人工" } }
      ]
    }
  }
}
```

**用户点击后的回传**：你的 Webhook 会收到一条 `type=button` 的入站消息，`text.body` 等于按钮 `title`，`id` 相关字段可用于路由：

```json
{
  "messages": [{
    "from": "8613800138000",
    "id": "wamid.Abc...",
    "timestamp": "1723610000",
    "type": "button",
    "button": {
      "text": "查订单",      // 按钮 title
      "payload": "btn_order" // 按钮 reply.id（仅在部分实现回传）
    }
  }]
}
```

#### 2.4.2 列表（list）

适合"从多选项中选一个"（如售前咨询分类），比按钮承载更多选项（最多 10 行）：

```json
{
  "type": "interactive",
  "interactive": {
    "type": "list",
    "header": { "type": "text", "text": "售前服务" },
    "body": { "text": "请选择您想了解的服务" },
    "action": {
      "button": "查看选项",
      "sections": [
        {
          "title": "产品咨询",
          "rows": [
            { "id": "row_phone", "title": "手机", "description": "最新旗舰机型" },
            { "id": "row_pc",    "title": "电脑", "description": "笔记本与台式机" }
          ]
        },
        {
          "title": "售后服务",
          "rows": [
            { "id": "row_return", "title": "退换货", "description": "7 天无理由" },
            { "id": "row_warranty", "title": "保修查询", "description": "查询保修状态" }
          ]
        }
      ]
    }
  }
}
```

**限制**：`sections[]` 最多 10 个；每 section 最多 30 `rows`；全部 `rows` 合计 ≤10 个（注意不同版本口径，一般按 ≤10 row 规划）。点击后用户会收到一条 `type=interactive` 的入站消息，`interactive.list_reply.id` 对应选中 row 的 `id`。

#### 2.4.3 目录与产品消息（catalog / product）

用于把商品库直接呈现在对话里，用户在 WhatsApp 内完成浏览与下单连接。

- **catalog**：展示整个目录（需要先在 Meta 商务管理后台创建 Catalog 并关联）。
- **product**：单品卡片。

```json
// product 单品消息
{
  "type": "interactive",
  "interactive": {
    "type": "product",
    "body": { "text": "这是我们最受欢迎的商品 👇" },
    "action": {
      "catalog_id": "123456789",
      "product_retailer_id": "SKU_1001"
    }
  }
}
```

> **前提**：catalog/product 交互消息要求已把 WhatsApp 号码与 Catalog 关联，且 `product_retailer_id` 必须是 Catalog 中真实存在的 ID，否则报错。

#### 2.4.4 CTA URL 按钮（业务外链）

在模板或交互里放"查看订单/去支付"外链按钮，实现"对话内完成跳转"：

```json
{
  "action": {
    "buttons": [
      {
        "type": "url",
        "title": "查看订单",
        "url": "https://example.com/order/{{1}}"   // 模板中可拼接变量
      }
    ]
  }
}
```

#### 2.4.5 回复按钮（Reply Buttons）与 CFT

- **回复按钮**：即 2.4.1 的 quick_reply 按钮，最常用的"用户选择 → 自动路由"机制，也是模板 `BUTTONS` 组件的同一套思想在交互消息中的落地。
- **CFT（Click to WhatsApp）**：让营销/广告流量进入对话的入口。用户在广告中点"发消息"，打开预填 `wa.me/<phone>?text=...` 的对话，并带 `?text=` 开头语。落地后客户发出的首条消息开启 **service 会话（免费入口）**，企业窗口内可自由回复。

```
CFT → 会话计费关系
广告点击 → wa.me 对话(预填text) → 客户发首条 → 开启 service 会话(免费)
        → 企业 24h 内自由回复(计入该 service 会话)
        → 24h 后需营销/工具模板 → 开启对应类别会话(计费)
```

> **交互消息与窗口的关系**：交互消息本质上还是"自由文本类"消息，**只能在 service 窗口内发送**。窗口外想发带按钮的引导，必须把按钮做进**模板**（模板可以带按钮，且模板不受窗口限制）。这是"交互按钮"与"模板按钮"的最大区别，也是新手最常混的地方。

---

### 2.5 Media API：上传、下载与媒体 ID

#### 2.5.1 媒体上传（GET/POST /{phone-number-id}/media）

把要发送的图片/视频/音频/文档先上传到 Meta 云端，拿到 **media ID**，再在消息里引用：

**上传（multipart/form-data）：**

```bash
curl -X POST "https://graph.facebook.com/v20.0/105118562409026/media" \
  -H "Authorization: Bearer EAAG..." \
  -F "messaging_product=whatsapp" \
  -F "type=image/jpeg" \
  -F "file=@/tmp/product.jpg"
```

**响应：**

```json
{ "id": "589568114581024" }
```

**上传类型与大小硬性限制：**

| 媒体类型 | 支持格式 | 最大大小 |
|---|---|---|
| image | jpeg / png（推荐） | 5MB |
| video | mp4 / 3gpp | 16MB |
| audio | aac / mpeg / amr / ogg / opus / mp4 | 16MB |
| document | pdf 等 | 100MB |
| sticker | webp | 100KB |

> **踩坑经验（媒体上传大小）**：客户端上传原始照片动辄 8~15MB，直接 POST media 会收到 `131026` / `400` With file size error。**生产必须先压缩**：图片转 jpeg 限 5MB 内，视频转码至多 16MB。实测电商客服场景，若不压缩，约 20% 的照片上传会因超限失败。文档型（PDF）100MB 上限对大多数场景足够，但超大合同/工程图也要先压。

#### 2.5.2 获取媒体信息（GET /{media-id}）

```bash
curl -X GET "https://graph.facebook.com/v20.0/589568114581024" \
  -H "Authorization: Bearer EAAG..."
```

**响应：**

```json
{
  "messaging_product": "whatsapp",
  "url": "https://lookaside.fbsbx.com/whatsapp_business/attachments/?mid=...",
  "mime_type": "image/jpeg",
  "sha256": "e3b0...",
  "file_size": 8192,
  "id": "589568114581024"
}
```

- `url` 是**临时签名 URL**，返回后约 **5 分钟**内有效，需在过期前下载。
- `mime_type`、`file_size` 用于前置校验。
- `sha256` 可用于下载后校验完整性。

#### 2.5.3 下载媒体

下载 `url` 时**同样需要带授权头**（Bearer token），不能裸 curl：

```bash
# 注意：带 Authorization 头下载
curl -X GET "https://lookaside.fbsbx.com/whatsapp_business/attachments/?mid=..." \
  -H "Authorization: Bearer EAAG..." \
  -o /tmp/downloaded.jpg
```

> **踩坑经验（媒体下载权限）**：很多人用 `curl -o file` 直接下 `url`，忽略 Authorization 头，得到 403/空文件。**下载 URL 与发送 URL 不同**：发送媒体（帖子里 `link`）用的是你自己 CDN 的公开 URL；而下载入站媒体用的是 Meta 临时 URL，必须带 token。另一个坑：**不要保存 Meta 的临时 URL**，它 5 分钟就失效；正确做法是拿到后立即下载、落到自己的对象存储，再把自建 URL 用于发送。

#### 2.5.4 删除媒体

```bash
curl -X DELETE "https://graph.facebook.com/v20.0/589568114581024" \
  -H "Authorization: Bearer EAAG..."
```

#### 2.5.5 刚上传的媒体 ID 能否直接用于入站下载？

**不能混用**：Media 上传接口得到的 ID 用于"出站发送引用"；入站消息里 `image.id`/`video.id` 等是"入站媒体 ID"。两者都是调用 `GET /{media-id}`，但语义不同——出站媒体可删除，入站媒体由 Meta 管理、会在一定时间后清理。Webhook 里收到入站图片，`image.id` 即入站媒体 ID，直接 `GET /{image.id}` 拿 url 下载即可。

### 2.6 电话号码管理、质量评级与消息限额

#### 2.6.1 号码管理端点

```
WABA 维度（号码列表）:
  GET  /{waba-id}/phone_numbers          → 列出号码及 phone_number_id
号码维度（详情/注册/注销）:
  GET  /{phone-number-id}                → 详情(名称/评级/状态)
  POST /{phone-number-id}/register       → 注册号码(需验证码)
  POST /{phone-number-id}/request_code   → 请求短信/语音验证码
  POST /{phone-number-id}/verify_code    → 校验验证码
  POST /{phone-number-id}/deregister     → 注销号码
```

**注册号码流程（生产上线必经）：**

```bash
# ① 请求验证码（embed_signature 可选）
curl -X POST "https://graph.facebook.com/v20.0/105118562409026/request_code" \
  -H "Authorization: Bearer EAAG..." -H "Content-Type: application/json" \
  -d '{"code_method": "SMS"}'

# ② 收到短信后校验
curl -X POST "https://graph.facebook.com/v20.0/105118562409026/verify_code" \
  -H "Authorization: Bearer EAAG..." -H "Content-Type: application/json" \
  -d '{"code": "123456"}'
```

#### 2.6.2 质量评级（Quality Rating）

号码质量评级反映用户对消息的**负反馈率**（拉黑、举报、忽略）。影响限额与模板可用性：

| 评级 | 展示色 | 触发条件 | 后果 |
|---|---|---|---|
| high | 绿 | 负反馈率低 | 可申请更高消息限额 |
| medium | 黄 | 负反馈中等 | 限额受限 |
| low | 红 | 负反馈率高 | 强烈限制，可能被降级 |

**Webhook 监听**：订阅 `phone_number_quality_updates` 字段，号码评级变化会推送：

```json
{
  "value": {
    "event": "PHONE_NUMBER_QUALITY_UPDATED",
    "phone_number_id": "105118562409026",
    "display_phone_number": "15550123456",
    "current_quality": "LOW",
    "previous_quality": "MEDIUM",
    "updated_at": "2026-08-14T09:00:00Z"
  }
}
```

**质量评级修复动作：** 暂停营销模板触达、只保留必要 utility 消息、及时处理用户退订（尊重 STOP）、清理失效号码。

#### 2.6.3 消息限额（Messaging Limits）

每个业务号码每天有一个 **业务发起会话（business-initiated conversations）上限**：

| 阶梯 | 每日上限 | 到达条件 |
|---|---|---|
| 默认 | 250 | 新号码起步 |
| 1K | 1,000 | 质量 high + 使用积累 |
| 10K | 10,000 | 继续达标 |
| 100K | 100,000 | 大规模合规商家 |

另外 **Cloud API 单号码发送吞吐约 80 msg/s** 的量级（受版本与账号影响），超并发会触发限流错误（`130429` / `80004`）。

> **踩坑经验**：大促当日业务发起会话可能一天冲 2 万条。若号码卡在 1K 限额，第 1001 条模板直接失败（131056 模板受限/速率类错误）。**大促前必须提前将号码质量维持在 high 并申请提升限额**，并使用多个业务号码横向扩容。

### 2.7 QR Codes 与 wa.me 进入对话

#### 2.7.1 wa.me 短链

`wa.me` 是点对点进入对话的官方短链，格式：

```
https://wa.me/<国家码+号码>?text=<URL编码的预填文本>

示例:
https://wa.me/8613800138000?text=%E4%BD%A0%E5%A5%BD%EF%BC%8C%E6%88%91%E6%83%B3%E5%92%A8%E8%AF%A2
```

- 号码必须带国家码，**不含 + 号与空格**。
- `text` 需 URL 编码，用户点开后在输入框预填该文本（需 1 次确认）。
- 未安装 WhatsApp 的用户会先引导到下载，再进入对话。

**落地页组合拳**：`wa.me` 常与 CFT 广告、二维码、官网"联系我们"按钮配套，是**获客进入 service 会话（免费入口）**的开关。

#### 2.7.2 生成二维码（POST /{phone-number-id}/qr_codes）

Cloud API 提供二维码生成接口，一行拿到可印刷/投放的二维码图：

```bash
curl -X POST "https://graph.facebook.com/v20.0/105118562409026/qr_codes" \
  -H "Authorization: Bearer EAAG..." -H "Content-Type: application/json" \
  -d '{
        "prefilled_message": "您好，扫码咨询",
        "generate_qr_code": "PNG"
      }'
```

**响应：**

```json
{
  "qr_code_url": "https://example.com/qr/xxx.png",
  "qr_code": "<base64 PNG>",
  "prefilled_message": "您好，扫码咨询",
  "mime_type": "image/png"
}
```

- `qr_code_url`：可直接用于 web 展示/下载。
- `qr_code`：base64 编码的 PNG 数据。
- 二维码内容本质是指向 wa.me 的链接，扫码后进入预填对话。

> **使用建议**：把二维码用于**线下物料**（门店台卡、包装盒、广告海报）时，务必用**真实的当前生产号码**生成。曾见团队用测试号码生成一批海报二维码，上线后扫码发给客服的是测试号码，消息进了联调环境，真实客服收不到——典型的低效返工。

### 2.8 Webhooks：订阅、验签与事件处理

Webhook 是 Cloud API 的**入站唯一通道**，也是消息状态与模板审核的推送通道。错过 Webhook = 消息系统整体失灵。

#### 2.8.1 订阅链路

```
Meta 商务管理后台 / 应用
  ┌────────────────────────────┐
  │ ① App 配置 Webhook 回调 URL │  ← 你在自己的服务器提供的 https 端点
  │    设置 Verify Token        │
  └────────────┬───────────────┘
               │ 订阅字段(fields):
               │   messages / message_template_status_update /
               │   phone_number_quality_updates / account_alerts /
               │   conversations
               ▼
  ┌────────────────────────────┐
  │ ② 把 URL 订阅到 WABA        │
  │    POST /{waba-id}/subscribed_apps
  │    (或后台「WhatsApp → Configuration → Webhook」)
  └────────────────────────────┘
```

**验证握手（首次设置时 Meta 发起）：**

```
Meta ──GET 你的回调URL?──▶ 你的服务器
  ?hub.mode=subscribe
  &hub.verify_token=<你配置的VerifyToken>
  &hub.challenge=<随机挑战字符串>

你的服务器:
  if hub.mode=='subscribe' and hub.verify_token==VERIFY_TOKEN:
      return 200, body=hub.challenge
  else:
      return 403
```

#### 2.8.2 事件签名验证（X-Hub-Signature-256）

Meta 对每条 Webhook 推送，用 `app_secret` 对**原始请求体**做 HMAC-SHA256，放在 `X-Hub-Signature-256` 头。**生产必须验签**，否则任何人都能伪造入站消息。

```
X-Hub-Signature-256 = sha256=<hex(HMAC-SHA256(app_secret, raw_body))>
```

Python 验签实现见 3.9。

#### 2.8.3 事件类型（订阅字段）

| 字段 | 触发 | 典型 payload |
|---|---|---|
| messages | 新入站消息 / 出站消息状态 | `value.messages[]`、`value.statuses[]` |
| message_template_status_update | 模板状态变更 | `event`、`message_template_id`、`message_template_name`、`event`=APPROVED/REJECTED 等 |
| message_template_quality_update | 模板质量变化 | quality 字段 |
| phone_number_quality_updates | 号码评级变化 | `current_quality` |
| account_alerts | 账号告警（如余额/限制） | alert 详情 |
| conversations | 新会话开始 | `value.contacts[0]`、`value.conversations` |

**入站文本消息 payload：**

```json
{
  "object": "whatsapp_business_account",
  "entry": [{
    "id": "105118562409025",
    "changes": [{
      "field": "messages",
      "value": {
        "messaging_product": "whatsapp",
        "metadata": { "display_phone_number": "15550123456", "phone_number_id": "105118562409026" },
        "contacts": [{ "profile": { "name": "张三" }, "wa_id": "8613800138000" }],
        "messages": [{
          "from": "8613800138000",
          "id": "wamid.HBgNODYx...",
          "timestamp": "1723610000",
          "type": "text",
          "text": { "body": "你好，请问在吗？" }
        }]
      }
    }]
  }]
}
```

**消息状态 payload（statuses）：**

```json
{
  "value": {
    "statuses": [{
      "id": "wamid.Abc...",
      "status": "sent",                // sent|delivered|read|failed
      "timestamp": "1723611000",
      "recipient_id": "8613800138000",
      "errors": [{ "code": 131026 }]   // 仅 failed 时携带
    }]
  }
}
```

> **踩坑经验**：Meta 的 Webhook **不保证只投递一次**，也**不做强顺序保证**。落在 `failed` 的消息要能从 `errors.code` 拿到失败码；`delivered`/`read` 需要与发送时保存的 `message_id` 关联。**一定要做幂等**（用 `wamid` 去重入库），否则并发重试时重复入账、重复触发下游，大促时会被自己打爆。

#### 2.8.4 回调 URL 与订阅 API

```bash
# 查看 WABA 当前订阅的 App
curl -X GET "https://graph.facebook.com/v20.0/105118562409025/subscribed_apps" \
  -H "Authorization: Bearer EAAG..."

# 将你的 App 订阅到该 WABA（Webhook 生效）
curl -X POST "https://graph.facebook.com/v20.0/105118562409025/subscribed_apps" \
  -H "Authorization: Bearer EAAG..."
```

### 2.9 错误码体系深度剖析

Cloud API 的发送错误统一包在 HTTP 4xx/5xx 的 `error` 对象里，`code` 是精髓。这里给出生产中最常命中的错误码与定位思路：

```
错误响应统一结构
{
  "error": {
    "message": "(#131026) Message Undeliverable",
    "type": "OAuthException",
    "code": 131026,
    "error_subcode": ...,
    "error_data": { "details": "..." },
    "trace_id": "Abc...",
    "fbtrace_id": "Abc..."
  }
}
```

| 错误码 | 含义 | 常见根因与处置 |
|---|---|---|
| 131026 | Message Undeliverable（消息无法投递） | 号码无效/被拉黑/对方无 WhatsApp/窗口外且非模板；排查 `details` 与号码有效性 |
| 131030 | 无法把号码映射到 WhatsApp 账户 | 接收方**未注册 WhatsApp**；用 `/contacts` 预检查 |
| 131045 | 接收方不在允许列表 | **测试号码**下接收人未添加；生产号码不受此限 |
| 131051 | 超过 24 小时窗口 | 客户超时未回复且发送自由文本；需改用模板消息 |
| 131047 | Re-engagement（再触达被拒） | 窗口关闭状态下未用模板；改模板发送 |
| 132000 | Parameter format is invalid | 模板变量数与占位符**不匹配**（变量给多/给少/顺序错） |
| 133010 | 模板未获批准/被拒 | 发送了 REJECTED/PENDING 模板；等审核或改用已批准模板 |
| 131056 | 模板被暂停/受限 | 模板 PAUSED/DISABLED；修质量后重提 |
| 130429 | 请求过于频繁（限流） | 触发 TPS/日限额；退避重试、提升限额 |
| 80004 | 端点调用过于频繁（限流） | 同上，Graph API 层面的并发节流 |
| 190 | Invalid OAuth 2.0 Access Token | Token 失效/被吊销；换长期令牌 |
| 200 | Permissions error | 系统用户权限不足/未覆盖该 WABA；授权 |
| 10 | Permission/运营限制 | 不满足运营前置条件 |
| 100 | Invalid parameter | 参数格式错误（如 URL 用了电话号码而非 ID） |
| 132001 | 变量参数与模板不匹配 | 同 132000 |
| 131041 | 会话费用豁免/免费入口相关 | 服务会话免费入口判定 |

> **131026 vs 131051 的辨析**：二者常被混用。
> - **131026** 是"投递层"的**通用不可达**：号码无效、被客户拉黑、未装 WhatsApp 等都归它，`error_data.details` 会给出细分，需结合号码状态持续判断。
> - **131051** 是"**窗口语义**"专属错误：白纸黑字"more than 24 hours have passed since the customer last replied"，**处置方案固定 = 改为模板消息**。
> 排查 131026 时先看 `details` 是否含"24 hours"，若含则按 131051 处置；否则查号码是否在 WhatsApp。

#### 2.9.1 号码有效性预检查（避免无效触达）

用 `POST /{phone-number-id}/contacts` 预查号码是否可用，是**控制 131030 比例**的通用手段：

```bash
curl -X POST "https://graph.facebook.com/v20.0/105118562409026/contacts" \
  -H "Authorization: Bearer EAAG..." -H "Content-Type: application/json" \
  -d '{
        "messaging_product": "whatsapp",
        "contacts": [{ "phone": "8613800138000" }]
      }'
```

**响应：**

```json
{
  "contacts": [{
    "input": "8613800138000",
    "status": "valid",          // valid / invalid
    "wa_id": "8613800138000"
  }]
}
```

> **建议**：把 `wa_id` 作为业务主键回写 CRM；对 `status=invalid` 的号码标记为"非 WhatsApp 活跃用户"，避免反复浪费发送额度。

### 2.10 费用结构与费用豁免

#### 2.10.1 按会话计费模型

2023 年 6 月起全面切换为**按会话计费**，计费单位为"会话"，按 `origin` 分 4 类：

| 会话类型 | 计费触发 | 费用特征 |
|---|---|---|
| service | 企业发起的服务会话 | 客户发起入口**免费**；企业发起按 service 费 |
| marketing | 发送任一 marketing 模板 | 按 marketing 费 |
| utility | 发送任一 utility 模板 | 按 utility 费 |
| authentication | 发送验证码模板 | 按 authentication 费 |

**会话时长**（2024-11-01 起）：service=24h；marketing=72h；utility=72h；authentication=72h。**会话内多条消息只计一次**。

#### 2.10.2 费用豁免与降本点

1. **免费入口（Free Entry Point）**：客户主动发消息开启的 service 会话**免费**，且 24h 内企业所有自由回复都计入该免费会话。
2. **每月 1,000 个免费 service 会话**：每个业务号码每月的前 1,000 个企业发起的 service 会话不计费（超出部分按 service 费率）。
3. **authentication 折价**：认证类会话按标准费率打折（约 50% 优惠），验证码类消息天然便宜。
4. **无需回执不重复计费**：同会话内多轮互动不会叠计。
5. **模板被拒/发送失败不计费**：`failed` 状态的消息不产生会话费用。

**费率国家分层**：费率按国家分 4 档（Tier 1~4），相同消息在不同国家价格差距可达数倍。**成本核算要按目标市场分档预估**，不可用单一均价。

**典型成本优化路径（真实复盘）：**

```
现状: 每次用 marketing 模板触达 → 72h marketing 会话收费
优化:
  ① 引导客户"主动回复" → 进入 service 免费入口
  ② 把营销触达改为"客户先回复 opt-in → 再在窗口内自由推送"
  ③ 信息类统一走 utility（比 marketing 便宜）
  ④ 验证码走 authentication（享折扣）
预期: 营销费用下降 40%+，且大幅改善号码质量评级
```

> **踩坑经验**：别把"服务/营销/工具"类别用错——很多人把促销塞进 marketing 模板（合规），却把"账单提醒"误当营销发，导致**成本翻倍且质量评级下降**。类别选择先算账：信息通知 → utility，验证码 → authentication，唯一抗审核且便宜的组合。

---

## 三、生产环境实战

本节给出可在生产落地的完整 Python 实现，命名风格与既有工具脚本（`scripts/meta_api.py`、`scripts/ad_platform_api.py`）对齐，统一走 `meta_*` 前缀，并对 Cloud API 的能力做合理扩展。

### 3.1 生产架构设计

```
┌─────────────────────────────────────────────────────────────────────┐
│                    生产消息系统架构（WhatsApp 通道）                   │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  广告/营销系统 ──▶ 消息编排服务 ──▶ 会话窗口管理器                        │
│                        │                    │                       │
│                        ▼                    ▼                       │
│                 WhatsApp 客户端模块    会话状态存储(Redis/DB)          │
│                 (meta_send_* / meta_   窗口计时/模板路由               │
│                  upload/download)                                   │
│                        │                                            │
│                        ▼                                            │
│                  Graph API (Cloud API)                              │
│                        ▲                                            │
│                        │ Webhook                                    │
│   Webhook 服务(FastAPI)──┤                                            │
│      ├─ 验签(app_secret HMAC)                                       │
│      ├─ 幂等(按 wamid 去重)                                         │
│      ├─ 入站消息 → 口语/意图路由                                     │
│      └─ 状态/会话/质量 → 事件总线 → 监控告警                         │
│                                                                     │
│   配套: Redis(幂等锁/限流计数) + DB(会话/消息/模板台账)                 │
│         + 对象存储(媒体) + 监控(错误码/送达率/评级)                   │
└─────────────────────────────────────────────────────────────────────┘
```

**模块职责划分：**

| 模块 | 职责 | 关键函数 |
|---|---|---|
| 认证 | Token/AppSecret/Proof 管理 | `_build_headers` |
| 客户端 | 统一 Graph 调用、错误归一化 | `_graph_request` |
| 消息发送 | 各类型消息发送 | `meta_send_whatsapp_message` 系列 |
| 模板 | 模板 CRUD | `meta_list_whatsapp_templates` 等 |
| 媒体 | 上传/发送/下载 | `meta_upload_whatsapp_media` 等 |
| WABA/号码 | WABA 与号码管理 | `meta_get_waba` / `meta_list_phone_numbers` |
| QR | 二维码生成 | `meta_generate_whatsapp_qr` |
| Webhook | 收包/验签/分发 | `webhook_verify` / `webhook_handler` |
| 会话 | 窗口状态机 | `SessionWindowTracker` |

**统一客户端（与 meta_api.py 对齐的请求封装）：**

```python
# scripts/meta_api.py 追加（WhatsApp 通道）──────────────────────────
import time
import uuid
import hmac
import hashlib
import json
import requests
from typing import Dict, List, Optional

GRAPH_BASE = "https://graph.facebook.com"
GRAPH_VERSION = "v20.0"

class MetaWhatsAppClient:
    """WhatsApp Cloud API 统一客户端"""

    def __init__(self, app_id: str, app_secret: str, token: str):
        self.app_id = app_id
        self.app_secret = app_secret
        self.token = token
        self.session = requests.Session()

    def _appsecret_proof(self) -> str:
        return hmac.new(
            self.app_secret.encode(),
            self.token.encode(),
            hashlib.sha256,
        ).hexdigest()

    def _graph_request(self, method: str, path: str,
                       json_body: Optional[dict] = None,
                       data: Optional[dict] = None,
                       files: Optional[dict] = None,
                       params: Optional[dict] = None) -> Dict:
        """统一走 Graph API，自动带认证与 appsecret_proof"""
        url = f"{GRAPH_BASE}/{GRAPH_VERSION}/{path.lstrip('/')}"
        headers = {"Authorization": f"Bearer {self.token}"}
        query = params or {}
        query["appsecret_proof"] = self._appsecret_proof()
        resp = self.session.request(
            method, url, headers=headers,
            json=json_body, data=data, files=files, params=query,
        )
        if resp.status_code >= 400:
            raise MetaApiError(resp.status_code, resp.json())
        return resp.json()


class MetaApiError(Exception):
    """携带 Meta 错误码与 details 的异常"""
    def __init__(self, http_code: int, body: dict):
        err = body.get("error", {})
        self.http_code = http_code
        self.code = err.get("code")
        self.subcode = err.get("error_subcode")
        self.message = err.get("message")
        self.details = (err.get("error_data") or {}).get("details")
        super().__init__(f"[{http_code}] ({self.code}) {self.message} | {self.details}")
```

### 3.2 发送文本消息（含 curl 与 Python）

**场景**：客服窗口内回复客户咨询文本。

```bash
curl -X POST "https://graph.facebook.com/v20.0/105118562409026/messages" \
  -H "Authorization: Bearer EAAG..." \
  -H "Content-Type: application/json" \
  -d '{
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": "8613800138000",
        "type": "text",
        "text": { "preview_url": false, "body": "您好，我是客服小助手，请问有什么可以帮您？" }
      }'
```

```python
def meta_send_whatsapp_message(
    self,
    phone_number_id: str,
    to: str,
    body: str,
    preview_url: bool = False,
) -> Dict:
    """发送自由文本（仅限会话窗口内）"""
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to,
        "type": "text",
        "text": {"preview_url": preview_url, "body": body},
    }
    return self._graph_request(
        "POST", f"{phone_number_id}/messages", json_body=payload
    )
```

**调用：**

```python
client = MetaWhatsAppClient(APP_ID, APP_SECRET, SYSTEM_USER_TOKEN)
resp = client.meta_send_whatsapp_message(
    PHONE_NUMBER_ID, "8613800138000",
    "您好，已为您查询到订单状态，稍后发送明细。",
)
print("wamid:", resp["messages"][0]["id"])
```

> **文本注意**：`preview_url` 开启后会把 body 中的 URL 渲染成可点击卡片；关闭则纯文本。营销场景建议关闭避免被诱导性链接降低体验。

### 3.3 发送模板消息与变量填充

**场景**：24h 窗口关闭后，用模板给用户发订单物流通知（utility）。

**curl（变量通过 components parameters 填充）：**

```bash
curl -X POST "https://graph.facebook.com/v20.0/105118562409026/messages" \
  -H "Authorization: Bearer EAAG..." \
  -H "Content-Type: application/json" \
  -d '{
        "messaging_product": "whatsapp",
        "to": "8613800138000",
        "type": "template",
        "template": {
          "name": "order_shipping_update_cn",
          "language": { "code": "zh_CN" },
          "components": [{
            "type": "body",
            "parameters": [
              { "type": "text", "text": "张三" },
              { "type": "text", "text": "SO20260814" },
              { "type": "text", "text": "8 月 20 日" }
            ]
          }]
        }
      }'
```

**Python（带窗口判断，窗口外才走模板）：**

```python
def meta_send_whatsapp_template(
    self,
    phone_number_id: str,
    to: str,
    template_name: str,
    language_code: str,
    body_params: Optional[List[Dict]] = None,
    header_params: Optional[List[Dict]] = None,
    button_params: Optional[List[Dict]] = None,
) -> Dict:
    """发送模板消息，变量按 components 组织"""
    components: List[Dict] = []
    if header_params:
        components.append({"type": "header", "parameters": header_params})
    if body_params:
        components.append({"type": "body", "parameters": body_params})
    if button_params:
        components.append({"type": "button", "sub_type": "url", "index": 0,
                           "parameters": button_params})
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "template",
        "template": {
            "name": template_name,
            "language": {"code": language_code},
            "components": components,
        },
    }
    return self._graph_request(
        "POST", f"{phone_number_id}/messages", json_body=payload
    )


def notify_order_shipping(self, waba, phone_number_id, customer, order):
    """业务封装：订单物流通知（模板变量精准填充）"""
    # 先判断会话窗口：窗口内可自由文本，窗口外用模板
    if self._in_service_window(phone_number_id, customer.wa_id):
        return self.meta_send_whatsapp_message(
            phone_number_id, customer.wa_id,
            f"您的订单 {order['no']} 已发出，预计 {order['eta']} 送达。",
        )
    return self.meta_send_whatsapp_template(
        phone_number_id, customer.wa_id,
        template_name="order_shipping_update_cn",
        language_code="zh_CN",
        body_params=[
            {"type": "text", "text": customer.name},
            {"type": "text", "text": order["no"]},
            {"type": "text", "text": order["eta"]},
        ],
    )
```

> **踩坑经验（模板变量数）**：模板定义了 3 个变量，你传 2 个或 4 个，都会报 `132000 Parameter format is invalid`。**变量顺序必须与模板占位符顺序一致**（{{1}} 对应 parameters[0]）。自动化平台常用"模板变量 schema"机制：模板创建时登记变量名，发送时按名引用，杜绝顺序错位。

### 3.4 发送交互消息（按钮/列表/目录）

**场景 1：售后引导（按钮）——窗口内发送：**

```python
def meta_send_whatsapp_interactive(
    self,
    phone_number_id: str,
    to: str,
    interactive: Dict,
) -> Dict:
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "interactive",
        "interactive": interactive,
    }
    return self._graph_request(
        "POST", f"{phone_number_id}/messages", json_body=payload
    )


def send_after_sale_menu(self, phone_number_id, to):
    interactive = {
        "type": "button",
        "body": {"text": "请问您需要办理什么业务？"},
        "footer": {"text": "选择后我将为您转接对应服务"},
        "action": {
            "buttons": [
                {"type": "reply", "reply": {"id": "btn_refund", "title": "申请退款"}},
                {"type": "reply", "reply": {"id": "btn_track", "title": "查物流"}},
                {"type": "reply", "reply": {"id": "btn_human", "title": "转人工"}},
            ]
        },
    }
    return self.meta_send_whatsapp_interactive(phone_number_id, to, interactive)
```

**场景 2：售后分类（列表）：**

```python
def send_service_list(self, phone_number_id, to):
    interactive = {
        "type": "list",
        "header": {"type": "text", "text": "售后支持"},
        "body": {"text": "请选择您遇到的问题类型"},
        "action": {
            "button": "选择问题",
            "sections": [
                {
                    "title": "订单问题",
                    "rows": [
                        {"id": "r_delay", "title": "物流延迟", "description": "包裹超时未到"},
                        {"id": "r_wrong", "title": "发错货", "description": "收到与订单不符商品"},
                    ],
                },
                {
                    "title": "退款",
                    "rows": [
                        {"id": "r_refund", "title": "申请退款", "description": "提交退款诉求"},
                    ],
                },
            ],
        },
    }
    return self.meta_send_whatsapp_interactive(phone_number_id, to, interactive)
```

**场景 3：单品卡（product，需已关联 Catalog）：**

```python
def send_product_card(self, phone_number_id, to, catalog_id, sku):
    interactive = {
        "type": "product",
        "body": {"text": "这是我们最受欢迎的商品 👇"},
        "action": {"catalog_id": catalog_id, "product_retailer_id": sku},
    }
    return self.meta_send_whatsapp_interactive(phone_number_id, to, interactive)
```

**回传处理（Webhook 里根据 type 分派）：**

```python
def route_interactive_reply(self, msg: Dict):
    mtype = msg.get("type")
    if mtype == "button":
        btn = msg.get("button", {})
        return self._handle_button(btn.get("payload") or btn.get("text"))
    if mtype == "interactive":
        inter = msg.get("interactive", {})
        if "list_reply" in inter:
            return self._handle_list(inter["list_reply"]["id"])
        if "button_reply" in inter:
            return self._handle_button(inter["button_reply"]["id"])
    return None
```

### 3.5 媒体上传、发送与下载

**场景**：客户发来破损商品照片，客服保存后回传处理结果图。

```python
def meta_upload_whatsapp_media(
    self,
    phone_number_id: str,
    file_path: str,
    mime_type: str,
) -> Dict:
    """上传媒体到 Cloud API，返回 media id"""
    with open(file_path, "rb") as f:
        return self._graph_request(
            "POST", f"{phone_number_id}/media",
            data={"messaging_product": "whatsapp", "type": mime_type},
            files={"file": (file_path.split("/")[-1], f, mime_type)},
        )


def send_media_by_id(self, phone_number_id, to, media_id, media_type):
    """用已上传的 media_id 发送媒体消息"""
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": media_type,          # image/video/audio/document
        media_type: {"id": media_id},
    }
    return self._graph_request("POST", f"{phone_number_id}/messages",
                               json_body=payload)


def send_document(self, phone_number_id, to, link, filename):
    """以公开 URL 发送文档（发票等）"""
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "document",
        "document": {"link": link, "filename": filename},
    }
    return self._graph_request("POST", f"{phone_number_id}/messages",
                               json_body=payload)


def meta_get_whatsapp_media(self, media_id: str) -> Dict:
    """获取媒体信息（含临时下载 url）"""
    return self._graph_request("GET", f"{media_id}")


def download_inbound_media(self, media_id: str, target_path: str) -> Dict:
    """下载入站媒体（带 token 防 403），并落盘到对象存储"""
    info = self.meta_get_whatsapp_media(media_id)
    url = info["url"]
    headers = {"Authorization": f"Bearer {self.token}"}
    resp = self.session.get(url, headers=headers)     # 5 分钟内有效
    resp.raise_for_status()
    with open(target_path, "wb") as f:
        f.write(resp.content)
    return {"local_path": target_path, "info": info}
```

**完整链路（上传→发送→下载入站图）：**

```python
def media_full_flow(self, phone_number_id, customer_wa_id, local_img):
    # ① 压缩后上传
    up = self.meta_upload_whatsapp_media(
        phone_number_id, local_img, "image/jpeg")
    media_id = up["id"]
    # ② 用 media_id 发给客户
    self.send_media_by_id(phone_number_id, customer_wa_id,
                          media_id, "image")
    # ③ 收到客户回传图片（Webhook 已给出 image.id）
    inbound_id = "some_inbound_media_id"
    self.download_inbound_media(inbound_id, "/data/media/inbound_1.jpg")
```

> **踩坑经验（媒体大小/压缩）**：上传前统一走压缩管线（图片 <5MB、视频 <16MB）。写一个 `_compress_image` 工具，超过阈值自动等比压缩，避免抖动触发上传超限。

### 3.6 模板生命周期管理

```python
def meta_list_whatsapp_templates(
    self,
    waba_id: str,
    status: Optional[str] = None,
    name: Optional[str] = None,
) -> List[Dict]:
    """列出模板，支持按状态/名称过滤"""
    params = {}
    if status:
        params["status"] = status
    if name:
        params["name"] = name
    resp = self._graph_request(
        "GET", f"{waba_id}/message_templates", params=params)
    return resp.get("data", [])


def meta_create_whatsapp_template(
    self,
    waba_id: str,
    name: str,
    language: str,
    category: str,
    components: List[Dict],
    allow_category_change: bool = True,
) -> Dict:
    payload = {
        "name": name,
        "language": language,
        "category": category,
        "components": components,
        "allow_category_change": allow_category_change,
    }
    return self._graph_request(
        "POST", f"{waba_id}/message_templates", json_body=payload)


def delete_whatsapp_template(self, waba_id: str, template_id: str) -> Dict:
    return self._graph_request("DELETE", f"{template_id}")


def list_ready_templates(self, waba_id: str) -> List[Dict]:
    """只取出可用的 APPROVED 模板，供发送路由使用"""
    all_t = self.meta_list_whatsapp_templates(waba_id)
    return [t for t in all_t if t.get("status") == "APPROVED"]


def ensure_template_ready(self, waba_id: str, name: str, language: str) -> bool:
    """发送前校验：模板是否存在且 APPROVED，否则抛错并告警"""
    for t in self.meta_list_whatsapp_templates(waba_id, name=name):
        if t.get("language") == language and t.get("status") == "APPROVED":
            return True
    # 未就绪 → 告警，避免把 REJECTED/PENDING 模板发出去
    raise MetaTemplateNotReadyError(name, language)
```

**模板创建参数（BODY 三变量 + FOOTER）示例：**

```python
components = [
    {"type": "HEADER", "format": "TEXT",
     "text": "订单物流更新"},
    {"type": "BODY",
     "text": "您好 {{1}}，您的订单 {{2}} 已发出，预计 {{3}} 送达。",
     "example": {"body_text": [["张三", "SO20260814", "8 月 20 日"]]}},
    {"type": "FOOTER", "text": "如未收到请回复本消息"},
]
```

**模板审计台账思路**：把模板状态变化通过 `message_template_status_update` Webhook 入库，做成"模板健康看板"（Approved/Pending/Rejected/被拒原因），供运营提前补齐上线模板。

### 3.7 WABA 与电话号码管理

```python
def meta_get_waba(self, waba_id: str,
                  fields: Optional[List[str]] = None) -> Dict:
    """获取 WABA 详情（business_verification_status、display_name 等）"""
    params = {}
    if fields:
        params["fields"] = ",".join(fields)
    return self._graph_request("GET", f"{waba_id}", params=params)


def meta_list_phone_numbers(self, waba_id: str) -> List[Dict]:
    """列出 WABA 下所有业务号码（含 phone_number_id、质量评级）"""
    resp = self._graph_request("GET", f"{waba_id}/phone_numbers")
    return resp.get("data", [])


def get_phone_number_detail(self, phone_number_id: str) -> Dict:
    params = {"fields": "display_phone_number,verified_name,"
                        "quality_rating,code_verification_status"}
    return self._graph_request("GET", f"{phone_number_id}", params=params)


def register_phone_number(self, phone_number_id: str) -> Dict:
    """注册号码（生产上线唯一入口）"""
    return self._graph_request(
        "POST", f"{phone_number_id}/register",
        data={"messaging_product": "whatsapp", "pin": ""})


def request_verification_code(self, phone_number_id: str,
                              code_method: str = "SMS") -> Dict:
    return self._graph_request(
        "POST", f"{phone_number_id}/request_code",
        data={"code_method": code_method})


def verify_code(self, phone_number_id: str, code: str) -> Dict:
    return self._graph_request(
        "POST", f"{phone_number_id}/verify_code", data={"code": code})


def monitor_quality(self, waba_id: str):
    """巡检所有号码质量，把 low 号码告警出来"""
    low = []
    for n in self.meta_list_phone_numbers(waba_id):
        q = n.get("quality_rating")
        if q == "LOW":
            low.append(n)
    return low
```

**获取 Business 旗下全部 WABA：**

```python
def list_owned_wabas(self, business_id: str) -> List[Dict]:
    resp = self._graph_request(
        "GET", f"{business_id}/owned_whatsapp_business_accounts")
    return resp.get("data", [])
```

### 3.8 二维码生成与 wa.me 落地页

```python
def meta_generate_whatsapp_qr(
    self,
    phone_number_id: str,
    prefilled_message: str = "您好，欢迎咨询",
    format_: str = "PNG",
) -> Dict:
    """生成可印刷/投放的对话二维码"""
    return self._graph_request(
        "POST", f"{phone_number_id}/qr_codes",
        data={
            "prefilled_message": prefilled_message,
            "generate_qr_code": format_,
        })


def build_wa_me_link(self, display_phone_number: str, text: str = "") -> str:
    """构造 wa.me 落地短链（供广告/官网/物料使用）"""
    import urllib.parse
    base = f"https://wa.me/{display_phone_number}"
    if text:
        base += "?text=" + urllib.parse.quote(text)
    return base
```

**生成并投放到广告物料：**

```python
qr = client.meta_generate_whatsapp_qr(
    PHONE_NUMBER_ID, prefilled_message="您好，我想了解夏季促销")
print("QR PNG URL:", qr["qr_code_url"])   # 交给设计团队投放
```

### 3.9 Webhook 服务实现（FastAPI 完整示例）

**验签 —— 生产绝不省略：**

```python
import json
from fastapi import FastAPI, Request, Response, HTTPException

app = FastAPI()
VERIFY_TOKEN = "my-secret-verify-token"   # 与后台配置一致
APP_SECRET = "xxxx"
MAX_PAYLOAD = 1_000_000                   # 防超长 body


def verify_signature(raw_body: bytes, signature_header: str) -> bool:
    """X-Hub-Signature-256 = sha256=<hex(HMAC-SHA256(app_secret, body))>"""
    if not signature_header:
        return False
    expected = "sha256=" + hmac.new(
        APP_SECRET.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature_header)


@app.get("/webhooks/whatsapp")
async def webhook_verify(
    hub_mode: str, hub_verify_token: str, hub_challenge: str):
    """Meta 首次配置时的订阅验证握手"""
    if hub_mode == "subscribe" and hub_verify_token == VERIFY_TOKEN:
        return Response(content=hub_challenge, media_type="text/plain")
    raise HTTPException(status_code=403, detail="Verify token mismatch")


@app.post("/webhooks/whatsapp")
async def webhook_handler(request: Request):
    raw = await request.body()
    if not verify_signature(raw, request.headers.get("X-Hub-Signature-256", "")):
        raise HTTPException(status_code=403, detail="Invalid signature")

    payload = json.loads(raw)
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            field = change.get("field")
            if field == "messages":
                dispatch_messages(value)          # 入站消息 + 状态
            elif field == "conversations":
                dispatch_conversation(value)      # 会话/计费/窗口
            elif field == "message_template_status_update":
                dispatch_template_status(value)   # 模板状态
            elif field == "phone_number_quality_updates":
                dispatch_quality(value)           # 质量评级
            elif field == "account_alerts":
                dispatch_alerts(value)            # 账号告警
    return {"status": "ok"}   # 务必 2xx，否则 Meta 会重试
```

**幂等去重（wamid 幂等锁）：**

```python
import redis
r = redis.Redis.from_url("redis://localhost:6379")


def is_duplicate(wamid: str, ttl: int = 3600) -> bool:
    """同一条消息事件只处理一次；返回 True 表示已处理过"""
    return bool(r.set(f"wa_msg:{wamid}", "1", nx=True, ex=ttl) is None)
```

**入站消息分派（含按钮回传、媒体下载）：**

```python
def dispatch_messages(value: dict):
    # 出站状态回执
    for st in value.get("statuses", []):
        handle_status(st)          # sent/delivered/read/failed，失败取 errors
        continue
    # 入站新消息
    for msg in value.get("messages", []):
        if is_duplicate(msg["id"]):
            continue
        from_wa = msg["from"]
        mtype = msg.get("type")
        if mtype == "text":
            handle_text(from_wa, msg["text"]["body"])
        elif mtype == "image":
            handle_image(from_wa, msg["image"]["id"])
        elif mtype == "button":
            route_interactive_reply(msg)
        elif mtype == "interactive":
            route_interactive_reply(msg)
        elif mtype == "document":
            handle_document(from_wa, msg["document"]["id"])
```

**状态回执处理：**

```python
def handle_status(status: dict):
    status_type = status.get("status")     # sent/delivered/read/failed
    msg_id = status.get("id")              # 发送时的 wamid
    if status_type == "failed":
        err = (status.get("errors") or [{}])[0]
        record_failure(msg_id, err.get("code"))
        alert_on_failure(msg_id, err.get("code"))
    else:
        update_delivery_status(msg_id, status_type)
```

> **踩坑经验**：Webhook 服务必须**返回 2xx 且尽快返回**。Meta 有重试机制，但若你处理逻辑超时（下载大媒体、调用外部慢接口），会阻塞回调线程、拉长返回，导致 Meta 重试风暴 → 重复投递 → 幂等锁必须兜底。**接收即回 2xx，业务处理异步化**（MQ 消费）。

### 3.10 会话窗口状态机与追踪器

自维护窗口是避免 131026/131051 的关键。核心状态：

```
会话窗口状态机（每号码 × 每客户）
┌──────────┐   客户来消息/回复    ┌──────────────┐
│  NON_OPEN │──────────────────▶│   OPEN(24h)   │─────────┐
└──────────┘                    └──────┬───────┘         │
      ▲                                │ 到 24h 且无新回复 │
      │                                ▼                  │
      │                         ┌──────────────┐          │
      │   模板发送开启新会话       │  EXPIRED      │         │
      └─────────────────────────│  (需模板)      │◀────────┘
                                 └──────────────┘
   状态: NON_OPEN → OPEN → EXPIRED → (模板) → 新会话
```

**实现：**

```python
class SessionWindowTracker:
    """基于 Redis 维护会话窗口，防止窗口外自由文本"""

    SERVICE_WINDOW = 24 * 3600      # service 窗口 24h

    def __init__(self, redis, phone_number_id: str):
        self.r = redis
        self.pn = phone_number_id

    def _key(self, wa_id: str) -> str:
        return f"wa_window:{self.pn}:{wa_id}"

    def touch_open(self, wa_id: str):
        """客户来消息/企业窗口内回复 → 重置 24h 锚点"""
        self.r.set(self._key(wa_id), "open", ex=self.SERVICE_WINDOW)

    def is_open(self, wa_id: str) -> bool:
        return self.r.exists(self._key(wa_id)) == 1

    def send_with_fallback(self, client, to, text, template_plan):
        """发送优先 free 文本，窗口关闭自动降级模板"""
        if self.is_open(to):
            client.meta_send_whatsapp_message(self.pn, to, text)
            self.touch_open(to)
        else:
            # 窗口外 → 用模板（开启新会话），绝不发自由文本
            client.meta_send_whatsapp_template(
                self.pn, to, template_plan["name"],
                template_plan["language"], template_plan["params"])
```

**接入 Webhook 联动：**

```python
def on_inbound_message(value: dict, tracker: SessionWindowTracker):
    for msg in value.get("messages", []):
        tracker.touch_open(msg["from"])     # 客户来消息 → 窗口打开/重置
        # ... 其余业务处理


def on_conversation(value: dict, tracker):
    conv = value.get("conversations", {})
    origin = conv.get("origin", {}).get("type")
    if origin == "service":
        # 服务会话开始（客户发起，免费入口），记录用于计费/成本
        record_conversation(conv.get("id"), origin,
                            expiry=conv.get("expiration_timestamp"))
```

### 3.11 限流、重试与幂等

**限流处理（130429 / 80004）：**

```python
import random
import time


def call_with_retry(self, fn, *args, max_retries: int = 3, **kwargs):
    """带指数退避 + 抖动 的重试封装，处理瞬时限流/网络抖动"""
    delay = 0.5
    for attempt in range(max_retries):
        try:
            return fn(*args, **kwargs)
        except MetaApiError as e:
            if e.code in (130429, 80004) and attempt < max_retries - 1:
                time.sleep(delay + random.uniform(0, 0.5))
                delay *= 2
                continue
            raise
    raise  # pragma: no cover
```

**幂等 —— 发送侧防重复入账：**

```python
def send_idempotent(self, req_key: str, send_fn, *args):
    """以业务唯一键(req_key)保证同一业务动作只发一次"""
    if r.set(f"wa_sent:{req_key}", "1", nx=True, ex=86400) is None:
        return {"duplicate": True}   # 已发过
    resp = send_fn(*args)
    return resp
```

**限流护栏（单号码 TPS 限量）：**

```python
import threading

class RateLimiter:
    """单号码漏桶，防止突发打爆 80 msg/s 级别吞吐"""
    def __init__(self, rate: float):
        self.rate = rate          # 每秒许可数
        self.lock = threading.Lock()
        self.tokens = rate
        self.last = time.monotonic()

    def acquire(self):
        with self.lock:
            now = time.monotonic()
            self.tokens = min(
                self.rate,
                self.tokens + (now - self.last) * self.rate)
            self.last = now
            if self.tokens >= 1:
                self.tokens -= 1
                return
        time.sleep(1.0 / self.rate)   # 节流等待
        self.acquire()
```

### 3.12 生产踩坑清单

以下为真实项目服务 WhatsApp Cloud API 时最高频的坑，按上线前后排列：

**上线前（配置/认证）：**

1. **用了短期 Token 上生产**：几小时就失效，导致批量发送中断。生产必须用 System User 长期令牌。
2. **忘了 `appsecret_proof`**：开启后所有请求都要带，否则报认证错误；且 `_appsecret_proof` 每请求实时算，别缓存。
3. **URL 里填电话号码而非 `phone_number_id`**：报 `(#100) Invalid parameter`。
4. **测试号码当生产用**：二维码、campaign 落地都指向测试号码，真实客服收不到。上线前切换到生产号码并重新注册。

**上线中（发送/模板）：**

5. **窗口未维护**：按自然日而非"相对最后一条消息 24h"实现，导致窗口外自由文本大量 `131051`。
6. **模板未提前过审就发**：发送 REJECTED/PENDING 模板报 `133010`；模板要提前 1~2 天提交。
7. **变量与模板不匹配**：多传/少传/顺序错 → `132000`；用"模板变量 schema"登记规避。
8. **模板名与 language 冲突**：同 name+language 重复创建失败；跨语言保持 name 一致、language 区分。

**上线中（媒体）：**

9. **不压缩就上传**：图片 8MB+ 直接上传超限；统一压缩到 image<5MB、video<16MB。
10. **保存 Meta 临时下载 URL**：5 分钟失效；拿到立即下载到自建对象存储。
11. **下载入站媒体忘带 Authorization 头**：403 空文件。

**上线后（投递/质量/成本）：**

12. **不看 failed 状态**：`statuses` 里 `status=failed` 携带错误码，必须监控并告警，否则投递率悄无声息下滑。
13. **Webhook 返回慢/业务处理阻塞**：导致 Meta 重试风暴、重复投递；接收即 2xx + 异步消费 + `wamid` 幂等。
14. **忽略质量评级**：大促无限触达 → 质量掉到 LOW → 限额骤降 + 模板被 pause；要监控 `phone_number_quality_updates`。
15. **类别用错**：促销塞进 utility 省钱/省审核，被 Meta 定位违规 → 模板被拒/号码受限；类别要合规。
16. **成本不按市场分层**：Tier 1~4 国家价格差异大，用单一均价核算会严重失真。

---
