# Messenger 机器人开发完整深度文档

> **领域**: 广告投放 / Meta
> **深度**: ⭐⭐⭐⭐⭐ 实战级指南
> **标签**: meta-ads, messenger, chatbot, bot-framework, click-to-messenger
> **更新时间**: 2026-08-14
> **类型**: 实战深度文档

---

## 目录速览

本深度文档面向负责"点击进入 Messenger 对话（Click-to-Messenger）广告"落地、以及从零构建 Messenger 机器人服务的后端开发 / 广告投放工程师。全文分为五大板块：

| 板块 | 内容 | 阅读优先级 |
|------|------|-----------|
| 一、核心概念与架构 | Messenger Platform 全景、Bot 模型、PSID、架构分层 | 必读 |
| 二、深度原理解析 | Profile API / Thread Settings / Thumbnails / Send API / Webhooks / Handover | 重点 |
| 三、生产环境实战 | Flask 接收端、Send API 封装、CTA 广告对接、会话状态机、上线 | 重点 |
| 四、常见问题与排查 | 权限、Webhook 校验、限流、回执、审核合规 | 排查手册 |
| 五、自测题 | 3-5 道深入问题与答案 | 巩固 |

---

## 一、核心概念与架构

### 1.1 Messenger Platform 是什么

Messenger Platform 是 Meta（原 Facebook）提供的官方 API 集合，允许第三方开发者 / 品牌通过机器人（Bot）在 Messenger 上收发消息、配置页面体验（Profile/Thread）、挂载网页插件与广告入口。它不是一个独立的广告 API，而是"对话式商业（Conversational Commerce）"的载体，与 Marketing API 的 `messages`（消息）目标紧密配合：

- **Marketing API（广告侧）**：负责用 `click_to_messenger` 广告把用户带进对话，归因、投放、受众。
- **Messenger Platform（消息侧）**：负责在对话产生之后，用机器人自动回复、接待、成交。

> 一句话理解两者边界：**广告负责把人"导流"进 Messenger，Messenger 机器人负责把人"转化"成交**。本文聚焦后者，但第三节会用一整节讲两者如何打通。

#### 1.1.1 核心组成

```
Messenger Platform（Graph API 消息子集）
├── Webhooks（回调接收）            ← 机器人"耳朵"
│   ├── messages（收到用户消息）
│   ├── messaging_postbacks（按钮回调）
│   ├── message_deliveries（投递回执）
│   ├── message_reads（已读回执）
│   ├── messaging_handovers（接管事件）
│   └── ...（referral、optin、account_linking 等）
├── Send API（主动发送）            ← 机器人"嘴巴"
│   ├── text（纯文本）
│   ├── quick_replies（快捷回复）
│   ├── generic / button / media（结构化模板）
│   └── sender_action（输入状态：typing_on / typing_off / mark_seen）
├── Messenger Profile API（页面形象）← 机器人"门面"
│   ├── get_started（开始按钮）
│   ├── persistent_menu（常驻菜单）
│   ├── greeting（问候语）
│   ├── whitelisted_domains（白名单域名）
│   ├── ice_breakers（破冰短语）
│   ├── phone_number / home_url（企业信息）
│   └── account_linking_url（账号绑定）
├── Thread Settings（会话设置）      ← 会话级行为
├── Handover Protocol（接管协议）    ← 人机协作分工
├── Page/App 设置（权限与订阅）      ← 运行前提
└── Domain Links + Thumbnails        ← m.me 短链与缩略图
```

### 1.2 Bot 的消息模型：Page Scoped ID（PSID）

Messenger 机器人与"用户"交互的关键前提，是理解 **PSID（Page-Scoped User ID）** 这一核心标识。

```
Graph API 用户标识体系
├── user_id（全站级，需 app 权限，机器人拿不到）
├── PSID / recipient.id（页面级，随 page 变化，机器人主用）
└── 用户在不同 Page 下，PSID 各不相同
```

**要点（实战必知）：**

1. 你**永远无法**通过 Messenger API 拿到用户的全局 Facebook ID 或邮箱、手机号。机器人只能拿到 **PSID**——一个仅对"当前页面 + 当前应用"有效的稳定标识。
2. PSID 的"稳定"是有条件的：它在用户主动与机器人首次对话后即存在，且在页面/应用组合内长期有效；但**若用户删除对话、或（极少见）被清洗，PSID 可能失效**。
3. 同一用户访问两个不同品牌 Page，会有两个不同的 PSID——**无法跨页面对接用户**。若需要统一，必须通过 `account_linking` 走你自己的登录体系。
4. PSID 不能作为广告/DCRM 的归因键直接使用，但它可以在机器人服务内作为用户档案主键。

```python
# 结构示意：webhook 事件中的 PSID 位置
webhook_event = {
    "sender": {"id": "100000123456789"},      # ← 这就是 PSID
    "recipient": {"id": "123456789012345"},   # ← 页面 ID
    "message": {"text": "你好"}
}
```

### 1.3 三种主要的机器人形态

生产环境里，Messenger 机器人通常以三种形态被部署，理解它们的差异有助于选择架构：

| 形态 | 交互方式 | 典型场景 | 是否需要 Webhook |
|------|----------|----------|------------------|
| 原生 Bot | 用户直接与页面消息 | 客服、FAQ、售前 | 是 |
| Click-to-Messenger 广告 Bot | 广告点击后进入对话 | 线索收集、销售 | 是 |
| Messenger 网页插件（Customer Chat） | 网站右下角浮窗 | 官网客服 | 是（+网页 SDK） |

> **小知识**：网页插件（Customer Chat Plugin）本质上也是走 Messenger 对话，但入口从"网站浮窗"进入，需要把站点域名加入 `whitelisted_domains`。

### 1.4 请求链路与数据流

一次完整的"用户发消息 → 机器人回复"的链路如下：

```
                ┌──────────────────────────────────────────┐
                │           Facebook / Messenger 客户端      │
                └───────────────────┬───────────────────────┘
                                    │ 用户输入 "你好"
                                    ▼
                ┌──────────────────────────────────────────┐
                │          Meta 消息后端 / Graph 边缘服务     │
                │  1. 生成 PSID 事件                          │
                │  2. 命中该 Page 的 Webhook 订阅            │
                │  3. 组包成 POST 请求                        │
                └───────────────────┬───────────────────────┘
                                    │ HTTPS POST（带 X-Hub-Signature）
                                    ▼
                ┌──────────────────────────────────────────┐
                │           你的 Webhook 服务器（HTTPS）      │
                │  - 校验签名                                │
                │  - 解析 event                             │
                │  - 走业务逻辑 / 意图识别                    │
                │  - 组装回复                                │
                └───────────────────┬───────────────────────┘
                                    │ POST /me/messages（带 Page Token）
                                    ▼
                ┌──────────────────────────────────────────┐
                │          Messenger Send API（Graph）       │
                └───────────────────┬───────────────────────┘
                                    ▼
                ┌──────────────────────────────────────────┐
                │         用户 Messenger 客户端收到回复       │
                └──────────────────────────────────────────┘
```

**关键观察：**

- Webhook 是**拉式推送**（Meta -> 你），Send API 是**推式发送**（你 -> Meta）。
- 两者都在 HTTPS 上跑，Webhook 必须可被公网访问且有**有效证书**。
- Send API 的回复并不保证以"收到消息的同一顺序"展示——因为有网络与队列抖动，**生产要用 `message_deliveries` 或产品层面设计幂等**。

### 1.5 运行前提：权限与审核（Permission 全图）

构建机器人前，先盘点运行所需的权限。这是新手最容易踩坑的地方。

```
需要准备的权限 / 资产
├── Facebook 页面（Page）  —— 机器人挂载的宿主
├── Facebook 开发者应用（App）—— 管理 Webhook、Token 的容器
├── Page Token（页面访问令牌）—— Send/Profile/Thread 调用的凭证
│   └── 由 App 生成，需 App 与 Page 绑定且拥有 manage_pages + pages_messaging
├── 权限（Permissions）
│   ├── pages_messaging            —— 收发消息权限（核心，需审核）
│   ├── pages_manage_metadata      —— 管理页面元数据
│   ├── pages_read_engagement      —— 读取互动
│   ├── pages_manage_ads           —— 管理页面广告
│   └── pages_show_list            —— 展示页面列表
├── Webhook 订阅字段
│   ├── messages
│   ├── messaging_postbacks
│   ├── message_deliveries
│   ├── message_reads
│   └── messaging_handovers ...
└── 【关键】Page 进入"开发模式"即可调通；对外发布需审核
    └── 标准访问权限（Standard Access）— 由 Meta 审核页面/应用后才能面向公众
```

> **踩坑提示**：很多团队搭建好机器人后，只在"开发者模式"下自测，一上线发现真实用户无法触发——因为 `pages_messaging` 的标准访问权限未过审。审核与发布必须早做规划。

### 1.6 架构分层全景

生产级机器人服务建议按如下分层组织（示例目录结构）：

```
messenger-bot-service/
├── app.py                    # 入口：Flask 应用 + 路由注册
├── config.py                 # 配置：APP_ID / APP_SECRET / PAGE_TOKEN / VERIFY_TOKEN
├── webhook.py                # Webhook 接收与事件分派
├── send.py                   # Send API 封装（meta_send_messenger_message 等）
├── profile.py                # Profile API 封装（meta_set_messenger_profile 等）
├── thumbnail.py              # 缩略图管理（meta_create_thumbnail 等）
├── domain_links.py           # 域链接 / m.me 短链（meta_create_domain_link 等）
├── state.py                  # 会话状态机
├── handlers/
│   ├── text_handler.py       # 文本意图处理
│   ├── postback_handler.py   # 按钮回调处理
│   ├── delivery_handler.py   # 回执处理
│   └── handover_handler.py   # 接管协议处理
├── db/
│   └── models.py             # PSID 档案、会话持久化
├── ad/
│   └── cta_helpers.py        # Click-to-Messenger 广告对接辅助
└── tests/
    └── test_webhook.py       # 签名校验 / 逻辑单测
```

> 该分层与 Ryan 知识库里 `meta_*` 的命名风格一脉相承：**每个"能力域"一个模块，模块内统一 `meta_` 前缀的顶层函数**，便于后续扩展到 Instagram / WhatsApp Business 对话 API。

---

## 二、深度原理解析

> 本节是本文的重点，按"门面 → 会话 → 发送 → 接收 → 协作"五条线彻底讲透。

### 2.1 Messenger Profile API 深度解析

**Messenger Profile API** 通过 Graph API 的 `/me/messenger_profile` 端点配置"页面级"的机器人门面。它影响的是**所有**与该页面对话的用户，与单个会话无关。

#### 2.1.1 端点总览

| 操作 | 方法 | 端点 | 说明 |
|------|------|------|------|
| 设置属性 | POST | `/me/messenger_profile?access_token=<PAGE_TOKEN>` | 全量或增量设置 |
| 查询属性 | GET | `/me/messenger_profile?fields=...` | 查看当前配置 |
| 删除属性 | DELETE | `/me/messenger_profile?access_token=<PAGE_TOKEN>` | 移除某属性 |
| 查询可设置字段 | GET | `/me/messenger_profile` | 返回字段列表 |

**支持的属性字段（8 大类）：**

```
get_started            开始按钮（含 payload）
persistent_menu        常驻菜单（最多 5 项顶级）
greeting               问候语（多 locale 版本，最多 20 个字符/条）
whitelisted_domains    网页插件/按钮跳转白名单域名
ice_breakers           破冰短语（最多 5 条，各 20 字符内）
phone_number           企业联系电话
home_url               主页 URL（Messenger 桌面端信息区）
account_linking_url    账号绑定 URL（配合 Account Linking）
```

#### 2.1.2 get_started：开始按钮

开始按钮是用户**首次**对话前，Messenger 对话界面底部的"开始"按钮。点击后触发一个 postback 事件（payload 自定义），是机器人"首次握手"的标准入口。

**POST 请求：**

```bash
curl -X POST "https://graph.facebook.com/v22.0/me/messenger_profile?access_token=EAAxxx" \
  -H "Content-Type: application/json" \
  -d '{
    "get_started": {
      "payload": "GET_STARTED"
    }
  }'
```

**JSON 结构说明：**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| payload | string | 是 | 点击按钮后回调给 Webhook 的自定义字符串，建议用大写常量如 `GET_STARTED`，避免与其它按钮 payload 冲突 |
| （无其它字段） | - | - | 开始按钮**不能**自定义文字，官方固定显示"开始"（Get Started） |

**Webhook 侧收到的 postback 事件：**

```json
{
  "object": "page",
  "entry": [{
    "id": "123456789012345",
    "time": 1723600000000,
    "messaging": [{
      "sender": {"id": "100000123456789"},
      "recipient": {"id": "123456789012345"},
      "timestamp": 1723600000000,
      "postback": {
        "title": "Get Started",
        "payload": "GET_STARTED",
        "mid": "m_GET_STARTED_xxxx"
      }
    }]
  }]
}
```

> **踩坑经验**：`get_started` 的 payload 会在每个新用户首次点击时触发。若用户是**老用户**（已对话过），再次点击开始按钮会返回 `postback` 但不会重发问候语——逻辑上要自行判断"首次 vs 回归"。

#### 2.1.3 persistent_menu：常驻菜单

常驻菜单显示在对话输入框左侧的"≡"菜单中，是机器人最常用的导航入口。**顶级菜单项最多 5 个**，每个顶级项可以是"动作按钮"或"二级菜单"（嵌套子项最多 5 个）。

**菜单项类型：**

| type | 含义 | 补充字段 |
|------|------|----------|
| postback | 点击触发 postback 事件 | `payload` |
| web_url | 打开网页（需白名单域名） | `url`、可选 `webview_height_ratio`、`messenger_extensions` |
| nested | 二级菜单（仅顶级可用） | `call_to_actions`（子项数组） |
| （企业消息） | 企业会话专属菜单 | 需先开通"企业消息"功能 |

**POST 请求示例（含二级菜单）：**

```bash
curl -X POST "https://graph.facebook.com/v22.0/me/messenger_profile?access_token=EAAxxx" \
  -H "Content-Type: application/json" \
  -d '{
    "persistent_menu": [{
      "locale": "default",
      "composer_input_disabled": false,
      "call_to_actions": [
        {
          "type": "postback",
          "title": "查看产品",
          "payload": "VIEW_PRODUCTS"
        },
        {
          "type": "nested",
          "title": "客服支持",
          "call_to_actions": [
            {"type": "postback", "title": "常见问题", "payload": "FAQ"},
            {"type": "postback", "title": "人工客服", "payload": "HUMAN_AGENT"},
            {"type": "web_url", "title": "帮助中心", "url": "https://help.example.com", "webview_height_ratio": "full"}
          ]
        },
        {
          "type": "web_url",
          "title": "访问官网",
          "url": "https://www.example.com",
          "webview_height_ratio": "full"
        }
      ]
    }]
  }'
```

**限制速查表：**

| 限制项 | 数值 |
|--------|------|
| 顶级菜单项 | ≤ 5 |
| 每个嵌套子菜单项 | ≤ 5 |
| 菜单项标题长度 | ≤ 30 字符 |
| payload 长度 | ≤ 1000 字符 |
| 多语言版本 | 每个 locale 一个数组，`default` 兜底 |

> **踩坑经验**：`persistent_menu` 是**整体替换**语义——一次 POST 会覆盖该 locale 的全部菜单，不是增量合并。改菜单务必先 GET 再全量 POST，避免误删线上菜单。

#### 2.1.4 greeting：问候语

问候语是用户**首次**打开对话时，在输入框上方显示的欢迎文案。支持多语言版本，由 Meta 根据用户的语言环境自动选择。

**POST 请求：**

```bash
curl -X POST "https://graph.facebook.com/v22.0/me/messenger_profile?access_token=EAAxxx" \
  -H "Content-Type: application/json" \
  -d '{
    "greeting": [
      {"locale": "default", "text": "你好！欢迎来到 Example 品牌，请问有什么可以帮您？"},
      {"locale": "en_US", "text": "Hi there! Welcome to Example. How can we help you?"},
      {"locale": "zh_CN", "text": "你好！欢迎来到 Example 品牌，请问有什么可以帮您？"}
    ]
  }'
```

**规则：**

| 规则 | 值 |
|------|-----|
| 每条 text 长度 | ≤ 160 字符（实际前端展示约 80 字符内最佳） |
| locale 数量 | 最多 20 个（含 default） |
| 匹配逻辑 | 按用户端语言优先匹配非 default 项，否则用 default |

> **踩坑经验**：Greeting 里**不能**包含 Emoji 之外的特殊格式？——实际可以含 Emoji，但**不能**包含链接（会被拒）。另外 Greeting 展示有长度截断，务必把核心价值主张放前 30 字符。

#### 2.1.5 whitelisted_domains：白名单域名

凡是在 Messenger 内通过 `web_url` 按钮 / 网页插件 / 域链接跳转的网页，其域名必须加入白名单，否则按钮点击会报错或跳转失败。

**POST 请求：**

```bash
curl -X POST "https://graph.facebook.com/v22.0/me/messenger_profile?access_token=EAAxxx" \
  -H "Content-Type: application/json" \
  -d '{
    "whitelisted_domains": [
      "https://www.example.com",
      "https://help.example.com",
      "https://shop.example.com"
    ]
  }'
```

**规则：**

| 规则 | 值 |
|------|-----|
| 域名必须带协议 | `https://`（或 `http://`，但生产必须 https） |
| 不带路径 | 域名级匹配，`https://www.example.com` 覆盖其所有子路径 |
| 子域是否自动覆盖 | **不自动**——`example.com` 不等于 `shop.example.com`，需分别加入 |
| 单次 POST 上限 | 一次性提交多个即可，无逐条上限（官方建议 ≤ 10 个常用域名） |
| 生效时间 | 秒级生效，无需重启 |

> **踩坑经验**：网页插件（Customer Chat）页面加载会校验白名单，**域名大小写、末尾斜杠**都会导致匹配失败。统一用"小写 + 无末尾斜杠"的规范写法入库。

#### 2.1.6 ice_breakers：破冰短语

破冰短语是用户打开对话、尚未发言时，输入框上方可点击的引导短句（配合 Greeting 展示）。

**POST 请求：**

```bash
curl -X POST "https://graph.facebook.com/v22.0/me/messenger_profile?access_token=EAAxxx" \
  -H "Content-Type: application/json" \
  -d '{
    "ice_breakers": [
      {"locale": "default", "question": "你们有什么新品？", "payload": "NEW_PRODUCTS"},
      {"locale": "default", "question": "怎么联系人工客服？", "payload": "HUMAN_AGENT"},
      {"locale": "default", "question": "物流要多久？", "payload": "SHIPPING_FAQ"}
    ]
  }'
```

**规则：**

| 规则 | 值 |
|------|-----|
| 最多条数 | 5 条 / locale |
| question 长度 | ≤ 20 字符 |
| payload 长度 | ≤ 1000 字符 |
| 与 Greeting 关系 | 展示在 Greeting 下方，点击后直接向机器人发送该 payload 对应的意图 |

> **踩坑经验**：ice_breakers 的 `question` 是用户**看得到**的文案，`payload` 是**发给机器人**的指令。很多团队把 payload 写得像内部代号，导致用户点"新品"机器人却收到 `NEW_PRODUCTS` 无法匹配——payload 也要设计成可读、可归一化的意图键。

#### 2.1.7 phone_number / home_url：企业信息

这两个属性用于在 Messenger 桌面端与移动端的"信息"区域展示企业联系信息。

```bash
curl -X POST "https://graph.facebook.com/v22.0/me/messenger_profile?access_token=EAAxxx" \
  -H "Content-Type: application/json" \
  -d '{
    "phone_number": "+8613800138000",
    "home_url": {
      "url": "https://www.example.com",
      "webview_height_ratio": "tall",
      "webview_share_button": "hide",
      "in_test": false
    }
  }'
```

| 字段 | 类型 | 说明 |
|------|------|------|
| phone_number | string | 国际格式电话号码，需与页面公开电话一致或可校验 |
| home_url.url | string | 主页 URL，需在 whitelisted_domains 内 |
| home_url.webview_height_ratio | enum | compact / tall / full |
| home_url.webview_share_button | enum | show / hide（是否显示分享按钮） |
| home_url.in_test | bool | 是否仅测试模式可见 |

> **注意**：`home_url` 属于较冷门属性，部分地区 / 部分客户端不展示，不要把它当作关键入口。

#### 2.1.8 account_linking_url：账号绑定

Account Linking 用于把 Messenger PSID 与用户在你的网站/App 上的自有账号打通（例如电商会员体系）。

**流程：**

```
用户点击 "绑定账号" 按钮（web_url 类型，url 指向你的站点）
        │
        ▼
站点页面要求登录 → 登录成功 → 生成 redirect_uri 跳回
        │
        ▼
https://www.facebook.com/v22.0/dialog/oauth?client_id=<APP_ID>
  &redirect_uri=<YOUR_REDIRECT_URI>&state=<PSID>&scope=...
        │
        ▼
Meta 回调你的 redirect_uri 并携带 authorization_code
        │
        ▼
你调用 Graph API 用 code 换取 access_token → 完成绑定
```

**Profile 端配置：**

```bash
curl -X POST "https://graph.facebook.com/v22.0/me/messenger_profile?access_token=EAAxxx" \
  -H "Content-Type: application/json" \
  -d '{
    "account_linking_url": "https://www.example.com/auth/messenger-link?state=__PSID__"
  }'
```

**配套的绑定按钮（Send API）：**

```json
{
  "recipient": {"id": "<PSID>"},
  "message": {
    "attachment": {
      "type": "template",
      "payload": {
        "template_type": "button",
        "text": "绑定你的会员账号",
        "buttons": [{
          "type": "account_link",
          "url": "https://www.example.com/auth/messenger-link?state=__PSID__"
        }]
      }
    }
  }
}
```

> **踩坑经验**：`state` 参数必须用 `__PSID__` 占位符，Meta 会在跳转时自动替换为真实 PSID。自己拼 PSID 会因 URL 编码问题导致跳转失败。

#### 2.1.9 GET 查询与 DELETE 清理

```bash
# 查询当前配置（可指定 fields）
curl -X GET "https://graph.facebook.com/v22.0/me/messenger_profile?fields=get_started,persistent_menu,greeting&access_token=EAAxxx"

# 删除开始按钮
curl -X DELETE "https://graph.facebook.com/v22.0/me/messenger_profile?access_token=EAAxxx" \
  -H "Content-Type: application/json" \
  -d '{"fields": ["get_started"]}'

# 批量删除多个属性
curl -X DELETE "https://graph.facebook.com/v22.0/me/messenger_profile?access_token=EAAxxx" \
  -H "Content-Type: application/json" \
  -d '{"fields": ["get_started", "persistent_menu", "greeting"]}'
```

**GET 响应示例：**

```json
{
  "data": [
    {"get_started": {"payload": "GET_STARTED"}},
    {"persistent_menu": [{"locale": "default", "composer_input_disabled": false, "call_to_actions": [...]}]},
    {"greeting": [{"locale": "default", "text": "你好！..."}]}
  ]
}
```

> **踩坑经验**：GET 默认返回全部字段。生产环境用 `fields` 参数收窄，避免大响应拖慢配置面板；`DELETE` 的 `fields` 是**数组**格式，写错成字符串会报 `(#100) Param fields must be an array`。

### 2.2 Thread Settings 深度解析

Thread Settings 与 Profile API 同属"页面级配置"，但语义不同：Profile 描述"门面形象"，Thread Settings 描述"会话行为"。历史上 Thread Settings 是独立端点，现在其能力大多并入 Messenger Profile 的对应字段，但理解其概念仍然重要。

#### 2.2.1 Thread Settings 能力清单

| 能力 | 端点（历史） | 现等价 Profile 字段 | 作用 |
|------|--------------|---------------------|------|
| Greeting | POST /me/thread_settings (setting_type=greeting) | greeting | 会话欢迎语 |
| Get Started | POST /me/thread_settings (setting_type=call_to_actions) | get_started | 开始按钮 |
| Persistent Menu | POST /me/thread_settings (setting_type=call_to_actions) | persistent_menu | 常驻菜单 |
| Domain 白名单 | POST /me/thread_settings (setting_type=domain_whitelisting) | whitelisted_domains | 网页跳转白名单 |
| Account Linking | POST /me/thread_settings (setting_type=account_linking) | account_linking_url | 账号绑定 |

**历史端点（已废弃，仅作兼容认知）：**

```bash
# 历史写法（注意：新应用应使用 messenger_profile）
curl -X POST "https://graph.facebook.com/v2.6/me/thread_settings?access_token=EAAxxx" \
  -H "Content-Type: application/json" \
  -d '{
    "setting_type": "greeting",
    "greeting": {"text": "Hello!"}
  }'
```

> **踩坑经验**：网上大量旧教程仍教你打 `/me/thread_settings`，新应用一律报错或行为异常。**统一走 `/me/messenger_profile`**，只有极老的 App（API 版本绑定）才需要兼容。

#### 2.2.2 composer_input_disabled：输入框禁用

属于 persistent_menu 的附加行为：当 `composer_input_disabled: true` 时，用户**不能自由输入文字**，只能通过菜单/按钮/快捷回复交互。适合"纯菜单引导"场景（如活动入口页）。

```json
{
  "persistent_menu": [{
    "locale": "default",
    "composer_input_disabled": true,
    "call_to_actions": [
      {"type": "postback", "title": "开始", "payload": "START"}
    ]
  }]
}
```

> **注意**：禁用输入框后，ice_breakers 等引导文案依然可点。要小心"用户想打字却打不了"的体验伤害，一般只用于强流程场景。

### 2.3 Thumbnails（缩略图）深度解析

**Thumbnails** 是 Messenger 域链接（m.me 短链）的**自定义图片缩略图**：当 m.me 链接在 Facebook/Messenger 内被分享时，默认展示页面头像；通过 Thumbnails API 可让每个短链附带专属图片（如产品图、活动图），显著提升分享转化。

#### 2.3.1 缩略图生命周期

```
1. 上传图片文件（multipart/form-data）到 /{app-id}/thumbnails
        │
        ▼
2. 获得 thumbnail_id
        │
        ▼
3. 创建域链接时绑定 thumbnail_id
        │
        ▼
4. 该 m.me 短链被分享时展示专属缩略图
        │
        ▼
5. 可随时删除缩略图（已绑定的链接会回退到默认头像）
```

**创建缩略图（POST /{app-id}/thumbnails）：**

```bash
# 上传图片
curl -X POST "https://graph.facebook.com/v22.0/<APP_ID>/thumbnails" \
  -F "access_token=<APP_TOKEN>" \
  -F "file=@/path/to/product-banner.png" \
  -F "caption=2026 夏季新品主图"

# 响应
{
  "id": "123456789012345678"
}
```

**查询缩略图：**

```bash
curl -X GET "https://graph.facebook.com/v22.0/<APP_ID>/thumbnails?access_token=<APP_TOKEN>"
```

**删除缩略图：**

```bash
curl -X DELETE "https://graph.facebook.com/v22.0/<APP_ID>/thumbnails/<THUMBNAIL_ID>?access_token=<APP_TOKEN>"
```

#### 2.3.2 缩略图与域链接的绑定关系

```
域链接（Domain Link）
├── id            : 短链唯一标识
├── uri           : m.me/ExampleBrand?ref=xxx（短链）
├── name          : 展示名
├── host          : 宿主类型（messenger / facebook）
├── platform      : ios / android / web / all
├── image_url     : 缩略图 URL（可选）
└── thumbnail_id  : 绑定到缩略图资源的 id（可选）
```

> **踩坑经验**：Thumbnails 资源与 **App**（而非 Page）绑定，创建时需要 **App Token**（`<APP_ID>|<APP_SECRET>` 拼接）而不是 Page Token。用 Page Token 调用会报权限错误。图片建议 1200×630 左右、JPG/PNG，超 8MB 会失败。

### 2.4 Domain Links（m.me 域链接）深度解析

**Domain Links**（也叫 `me_code` / `m.me` 短链）是 Messenger 官方的"扫码/短链进入对话"能力，是线下物料、外投内容、活动页引流到 Messenger 的标准入口。

#### 2.4.1 两类域链接

| 类型 | 形态 | 典型场景 |
|------|------|----------|
| 页面域链接 | `m.me/ExampleBrand` | 品牌入口，扫/点即打开与该页面的对话 |
| 参数化域链接（带 ref） | `m.me/ExampleBrand?ref=summer2026` | 区分渠道/活动来源，ref 会通过 webhook 的 `referral` 事件回传 |

**创建域链接（POST /{app-id}/domain_links）：**

```bash
curl -X POST "https://graph.facebook.com/v22.0/<APP_ID>/domain_links" \
  -H "Content-Type: application/json" \
  -d '{
    "access_token": "<APP_TOKEN>",
    "name": "2026 夏季活动",
    "uri": "https://m.me/ExampleBrand?ref=summer2026",
    "image_url": "https://cdn.example.com/banners/summer2026.png",
    "platform": "all",
    "thumbnail_id": "123456789012345678"
  }'
```

**查询 / 删除：**

```bash
curl -X GET "https://graph.facebook.com/v22.0/<APP_ID>/domain_links?access_token=<APP_TOKEN>"
curl -X DELETE "https://graph.facebook.com/v22.0/<APP_ID>/domain_links/<DOMAIN_LINK_ID>?access_token=<APP_TOKEN>"
```

#### 2.4.2 ref 参数回传机制

用户通过 `?ref=summer2026` 进入对话后，Webhook 会收到 `messaging_referrals` 事件，**ref 原样回传**，可用于渠道归因、自动化欢迎语分流：

```json
{
  "object": "page",
  "entry": [{
    "id": "123456789012345",
    "messaging": [{
      "sender": {"id": "100000123456789"},
      "recipient": {"id": "123456789012345"},
      "timestamp": 1723600000000,
      "referral": {
        "ref": "summer2026",
        "source": "SHORTLINK",
        "type": "OPEN_THREAD"
      }
    }]
  }]
}
```

> **踩坑经验**：`ref` 只能由你**预先创建**的参数化链接产生，网页里临时拼的 `?ref=xxx` **不保证回传**。要精确归因，请走 `messenger_code`（m.me 码）或平台归因（CTA 广告自带 `referral`，见第三节）。

#### 2.4.3 m.me 码（Messenger Code）

除了 URL 短链，还有图片形态的 **Messenger Code**（m.me 码，扫码即进对话），适合印刷物料：

```bash
curl -X POST "https://graph.facebook.com/v22.0/me/messenger_codes?access_token=EAAxxx" \
  -H "Content-Type: application/json" \
  -d '{"type": "standard", "image_size": 1000, "data": {"ref": "print-summer2026"}}'
```

| 参数 | 说明 |
|------|------|
| type | standard / waveform（音频波形码，仅部分场景） |
| image_size | 100~1000，建议 ≥ 500 保证印刷清晰 |
| data.ref | 扫码后回传的渠道标记（≤ 1000 字符） |
| data.cta | 可选，扫码后按钮文案 |

### 2.5 Send API 深度解析

Send API（`POST /me/messages`）是机器人"说话"的唯一通道。理解它的消息模板体系是开发的核心。

#### 2.5.1 基础调用形态

```bash
curl -X POST "https://graph.facebook.com/v22.0/me/messages?access_token=EAAxxx" \
  -H "Content-Type: application/json" \
  -d '{
    "recipient": {"id": "<PSID>"},
    "message": {"text": "你好，欢迎咨询！"}
  }'
```

**Send API 消息载体总览：**

```
message 载体
├── text                      纯文本（≤ 2000 字符）
├── attachment: image         图片
├── attachment: audio         音频
├── attachment: video         视频
├── attachment: file          文件
├── attachment: template
│   ├── generic               通用模板（横向滑动卡片）
│   ├── button                按钮模板
│   ├── media                 媒体模板（带按钮的图片/视频）
│   ├── receipt               收据模板（电商订单）
│   ├── airline_*             航旅模板
│   └── ...
├── quick_replies             快捷回复（文本/图片）
├── text + quick_replies      文本附带快捷回复
└── sender_action             输入状态
```

#### 2.5.2 text 与 sender_action

**纯文本：**

```json
{
  "recipient": {"id": "<PSID>"},
  "message": {
    "text": "感谢你的咨询！我们的客服将在 5 分钟内回复。",
    "quick_replies": [
      {"content_type": "text", "title": "继续聊", "payload": "CONTINUE"},
      {"content_type": "text", "title": "结束", "payload": "END"}
    ]
  }
}
```

**sender_action（输入状态，用于"正在输入"体验）：**

```bash
curl -X POST "https://graph.facebook.com/v22.0/me/messages?access_token=EAAxxx" \
  -H "Content-Type: application/json" \
  -d '{"recipient": {"id": "<PSID>"}, "sender_action": "typing_on"}'
```

| sender_action | 含义 | 备注 |
|---------------|------|------|
| typing_on | 显示"正在输入…" | 发送真实消息后自动消失 |
| typing_off | 关闭输入状态 | 一般无需手动调用 |
| mark_seen | 标记"已读" | 需消息回执权限，企业会话常用 |

> **踩坑经验**：typing_on 是**易失效**的——如果 20 秒内没发真实消息，状态自动消失；且高频调用会被限流。正确节奏：收到消息 → typing_on → 业务处理 → 发消息，一次流程只开一次。

#### 2.5.3 quick_replies：快捷回复

快捷回复显示在输入框上方，用户点击后**以普通消息形式**把 payload 发给机器人（不是 postback）。

| 字段 | 类型 | 说明 |
|------|------|------|
| content_type | enum | text / user_phone_number / user_email |
| title | string | 按钮文案（≤ 20 字符） |
| payload | string | 点击后发送的负载（≤ 1000 字符） |
| image_url | string | 可选，按钮配图（≤ 80 字符的短 URL 或 CDN） |

```json
{
  "recipient": {"id": "<PSID>"},
  "message": {
    "text": "请问您想了解哪方面？",
    "quick_replies": [
      {"content_type": "text", "title": "产品", "payload": "TOPIC_PRODUCT"},
      {"content_type": "text", "title": "价格", "payload": "TOPIC_PRICE"},
      {"content_type": "text", "title": "售后", "payload": "TOPIC_AFTERSALE"},
      {"content_type": "user_phone_number", "title": "留电话"}
    ]
  }
}
```

> **规则**：单条消息最多 **13 个**快捷回复；`user_phone_number` / `user_email` 类型点击后**直接发送**电话号码/邮箱给机器人（需 `pages_messaging` 权限，部分地区需审核说明用途）。

#### 2.5.4 generic template：通用模板

通用模板是"卡片流"，每条消息最多 **10 张卡片**，横向滑动，是电商/内容推荐的主力模板。

**JSON 模板：**

```json
{
  "recipient": {"id": "<PSID>"},
  "message": {
    "attachment": {
      "type": "template",
      "payload": {
        "template_type": "generic",
        "image_aspect_ratio": "horizontal",
        "elements": [
          {
            "title": "夏季新品 002 号",
            "image_url": "https://cdn.example.com/products/summer002.png",
            "subtitle": "¥299 · 现货 · 顺丰包邮",
            "default_action": {
              "type": "web_url",
              "url": "https://www.example.com/p/summer002",
              "messenger_extensions": true,
              "webview_height_ratio": "tall"
            },
            "buttons": [
              {"type": "web_url", "title": "查看详情", "url": "https://www.example.com/p/summer002", "webview_height_ratio": "full"},
              {"type": "postback", "title": "立即咨询", "payload": "BUY_SUMMER002"},
              {"type": "phone_number", "title": "致电客服", "payload": "+8613800138000"}
            ]
          }
        ]
      }
    }
  }
}
```

**element 字段详解：**

| 字段 | 必填 | 说明 |
|------|------|------|
| title | 是 | 卡片标题（≤ 80 字符） |
| image_url | 否 | 卡片配图（HTTPS，建议 1.91:1 或 1:1） |
| subtitle | 否 | 副标题（≤ 80 字符） |
| default_action | 否 | 点击卡片整体跳转的动作 |
| buttons | 否 | 按钮数组（≤ 3 个） |
| image_aspect_ratio | - | horizontal / square（payload 级） |

**按钮类型（buttons）：**

| type | 用途 | 关键字段 |
|------|------|----------|
| postback | 触发机器人回调 | payload |
| web_url | 打开网页 | url, webview_height_ratio, messenger_extensions |
| phone_number | 拨打电话 | payload（电话号码） |
| account_link | 账号绑定 | url |
| account_unlink | 解绑 | 无 |
| share | 分享卡片 | 无 |

> **踩坑经验**：卡片 `title`/`subtitle` 超长会被截断显示但**不报错**——文案要按字符预算设计；`image_url` 必须 HTTPS 且可被 Meta 抓取（私有 IP、内网域名、带鉴权 URL 都会导致图片加载失败）。

#### 2.5.5 button template：按钮模板

按钮模板是"文本 + 最多 3 个按钮"，比 generic 更轻，适合单点行动号召。

```json
{
  "recipient": {"id": "<PSID>"},
  "message": {
    "attachment": {
      "type": "template",
      "payload": {
        "template_type": "button",
        "text": "加入我们的会员计划，享受专属折扣！",
        "buttons": [
          {"type": "web_url", "title": "立即加入", "url": "https://www.example.com/member", "webview_height_ratio": "full"},
          {"type": "postback", "title": "了解更多", "payload": "MEMBER_MORE"}
        ]
      }
    }
  }
}
```

#### 2.5.6 media template：媒体模板

媒体模板是"大图/大视频 + 可选按钮"，视觉冲击力强，适合活动主视觉。

```json
{
  "recipient": {"id": "<PSID>"},
  "message": {
    "attachment": {
      "type": "template",
      "payload": {
        "template_type": "media",
        "elements": [
          {
            "media_type": "image",
            "url": "https://cdn.example.com/banners/summer-sale-2026.jpg",
            "attachment_id": null,
            "buttons": [
              {"type": "web_url", "title": "去逛逛", "url": "https://www.example.com", "webview_height_ratio": "full"}
            ]
          }
        ]
      }
    }
  }
}
```

| 字段 | 说明 |
|------|------|
| media_type | image / video |
| url 或 attachment_id | 二选一（attachment_id 需先上传资源） |
| buttons | ≤ 1 个（媒体模板只允许 1 个按钮） |

#### 2.5.7 附件上传与 attachment_id

对于视频、大文件，官方推荐**先上传再引用**，避免 URL 不稳定与时效问题：

```bash
# 1. 上传到 Message Attachments 端点
curl -X POST "https://graph.facebook.com/v22.0/me/message_attachments?access_token=EAAxxx" \
  -F "recipient={'id':'<PSID>'}" \
  -F "message={'attachment':{'type':'video','payload':{'is_reusable':true}}}" \
  -F "filedata=@/path/to/promo.mp4"

# 响应
{"attachment_id": "1234567890123456789"}

# 2. 用 attachment_id 发送（可复用）
curl -X POST "https://graph.facebook.com/v22.0/me/messages?access_token=EAAxxx" \
  -H "Content-Type: application/json" \
  -d '{
    "recipient": {"id": "<PSID>"},
    "message": {
      "attachment": {"type": "video", "payload": {"attachment_id": "1234567890123456789"}}
    }
  }'
```

> **踩坑经验**：`is_reusable: true` 才能跨用户复用 attachment_id；视频建议 H.264/MP4、≤ 25MB；大文件上传会超时，务必用**异步任务**处理并做重试。

#### 2.5.8 限流与配额（Send API 硬约束）

Send API 有严格的速率与配额限制，超限返回 `(#613) Calls to this api have exceeded the rate limit.`：

| 维度 | 限制（典型值，随账户状态浮动） |
|------|-------------------------------|
| 消息发送速率 | 单页约 100 条消息/秒（消息推送上限） |
| 标准消息窗口 | 用户最后一条消息后 24 小时内可自由回复 |
| 24h+1 规则 | 超过 24 小时窗口后，仅可发"1 条附加消息"用于获取订阅/提醒 |
| 订阅消息（Messaging Subscription） | 需用户显式 opt-in（`OPT_IN` 事件），用于长期推送 |
| 企业消息（Business Messaging） | 审核通过后放宽窗口（如电商订单、航班通知等用例） |

**窗口示意图：**

```
用户最后消息 T0
├── [T0, T0+24h)     标准消息窗口：自由发送
├── T0+24h 之后
│   ├── 1 条附加消息（追回/订阅引导）
│   └── 之后必须依赖：
│       ├── opt-in 订阅消息（长期推送，需审核）
│       └── 企业消息权限（按用例审核）
```

> **踩坑经验**：广告投放团队最常见的误伤是——用户在广告里聊完后 25 小时再发消息，机器人回复被拒。**"24h 窗口"的计时起点是用户最后一条 inbound 消息**，不是广告点击时间。窗口内必须完成核心转化流程。

### 2.6 Webhooks / 回调机制深度解析

Webhook 是机器人的"耳朵"，Meta 把事件通过 HTTPS POST 推送给你的端点。理解事件结构与签名校验是可靠性的根基。

#### 2.6.1 订阅与校验

**1) 在开发者后台订阅：** App → Messenger → Webhooks → 选择事件字段，绑定到目标 Page。

**2) 首次配置时的 Verify Token 校验（GET 请求）：**

```bash
# 你的端点需要实现这个 GET：
# GET /webhook?hub.mode=subscribe&hub.verify_token=<VERIFY_TOKEN>&hub.challenge=<CHALLENGE>
```

当你在后台填 `Callback URL` 和 `Verify Token` 后，Meta 会 GET 你的端点。你的服务必须校验 `hub.verify_token` 与配置一致，然后**原样返回** `hub.challenge`，否则订阅失败。

```python
# Flask 中的校验
@app.route("/webhook", methods=["GET"])
def webhook_verify():
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")
    if mode == "subscribe" and token == VERIFY_TOKEN:
        return challenge, 200
    return "Verification failed", 403
```

#### 2.6.2 事件顶层结构

所有 Page 事件都遵循统一信封：

```
POST /webhook
正文:
{
  "object": "page",
  "entry": [
    {
      "id": "<PAGE_ID>",
      "time": <unix_ms>,
      "messaging": [
        { ...单个事件... },
        { ...另一个事件... }
      ]
    }
  ]
}
```

**关键结构语义：**

| 层级 | 说明 |
|------|------|
| object | 固定 `page`（订阅了 Page 对象） |
| entry | 数组（通常 1 个 entry），携 id=页面 ID |
| messaging | **数组，可能一次含多个事件**，逐条处理才可靠 |
| entry[].id | 页面 ID（用于多页共收时的路由，见后） |

> **踩坑经验**：`messaging` 是数组，可能批量到达。**逐条循环处理**，不要只取 `[0]`。另外同一 `mid`（消息 ID）可能因重试收到多次，处理逻辑要**幂等**（去重）。

#### 2.6.3 事件类型全集

| 事件类型 | 触发时机 | 关键字段 |
|----------|----------|----------|
| message | 用户发来消息（含 quick_reply 点击、附件的消息） | message.text / message.attachments / message.quick_reply |
| postback | 点击按钮 / Get Started / 菜单项（postback 类） | postback.payload / postback.referral |
| messaging_referrals | 通过 m.me 链接 / CTA 广告进入 | referral.ref / referral.source |
| message_deliveries | 消息送达 | delivery.mids / delivery.watermark |
| message_reads | 消息已读 | read.watermark |
| messaging_handovers | 会话被接管/退回 | handover 事件（暂存/移交） |
| messaging_optins | 用户订阅消息（opt-in） | optin.ref |
| account_linking | 账号绑定状态变化 | account_linking.status / authorization_code |
| messaging_account_linking | 绑定流程回调 | 同上 |
| messaging_game_play | 即时游戏 | 游戏相关 |
| messaging_checkout_updates | 支付更新 | 电商支付 |

**message 事件的完整结构（含附件 / 快捷回复命中）：**

```json
{
  "sender": {"id": "100000123456789"},
  "recipient": {"id": "123456789012345"},
  "timestamp": 1723600000000,
  "message": {
    "mid": "m_xxxxx",
    "text": "TOPIC_PRICE",
    "quick_reply": {"payload": "TOPIC_PRICE"},
    "attachments": [
      {"type": "image", "payload": {"url": "https://..."}}
    ],
    "is_echo": false
  }
}
```

> **注意**：点击快捷回复后，机器人收到的是**普通 message**，其 `quick_reply.payload` 才是命中项，`text` 可能是 payload 原文。区分"文本意图"与"快捷回复意图"时优先读 `quick_reply`。

#### 2.6.4 message_deliveries / message_reads：回执事件

回执用于追踪消息全链路（送达→已读），是企业客服与"钉住转化"必用数据。

```json
{
  "sender": {"id": "100000123456789"},
  "recipient": {"id": "123456789012345"},
  "timestamp": 1723600100000,
  "delivery": {
    "mids": ["m_xxxxx1", "m_xxxxx2"],
    "watermark": 1723600050000,
    "seq": 12
  }
}
```

```json
{
  "sender": {"id": "100000123456789"},
  "recipient": {"id": "123456789012345"},
  "timestamp": 1723600200000,
  "read": {
    "watermark": 1723600180000,
    "seq": 13
  }
}
```

| 事件 | 语义 |
|------|------|
| delivery（投递） | 消息已投递到设备，`watermark` 表示该时刻之前的所有消息都已投递 |
| read（已读） | 消息已被用户查看，`watermark` 表示已读时间戳 |

> **踩坑经验**：`watermark` 是**时间戳**而非逐个 mid——表示"该时刻之前发出的消息都已送达/已读"。用 watermark 做"是否已读到某条答复"的判断即可，不必逐 mid 统计。回执事件**不保证必达**（依赖用户端），只能作为增强信号，不能作为唯一业务触发。

#### 2.6.5 X-Hub-Signature 签名校验（安全底线）

所有 Webhook POST 都带 `X-Hub-Signature-256` 头，由 **App Secret** 对原始 body 做 HMAC-SHA256 生成。必须校验，否则任何人都能伪装 Meta 打你的端点刷垃圾逻辑/触发计费。

```bash
# 签名生成算法
X-Hub-Signature-256 = "sha256=" + hex(HMAC-SHA256(key=APP_SECRET, msg=raw_body))
```

**Flask 校验实现：**

```python
import hashlib
import hmac
from flask import request, abort

APP_SECRET = "YOUR_APP_SECRET"  # 永不泄露前端

def verify_webhook_signature():
    signature = request.headers.get("X-Hub-Signature-256", "")
    if not signature:
        abort(403, "Missing signature")

    expected = "sha256=" + hmac.new(
        key=APP_SECRET.encode("utf-8"),
        msg=request.get_data(),          # 必须是原始字节，不能用 request.json
        digestmod=hashlib.sha256
    ).hexdigest()

    # 用 hmac.compare_digest 防时序攻击
    if not hmac.compare_digest(expected, signature):
        abort(403, "Invalid signature")
```

> **踩坑经验（关键）**：签名校验必须用 `request.get_data()` 拿到的**原始字节**做 HMAC，而不能用 `request.json` 转字符串——因为**后处理过、空格/顺序**都可能改变，导致校验失败或被伪造绕过。先校验签名，**再**解析 JSON。

#### 2.6.6 应答要求与重试

- 收到 POST 后应**尽快**返回 `200 OK`。Meta 期待 20 秒内的 200；**返回 200 即视为成功，无论你是否已回复用户**。
- 若超时 / 返回非 2xx / 网络失败，Meta 会**退避重试**（多次递增间隔），相同事件可能重复到达。
- 因此：**你的 Webhook 处理器应"先 ACK、后异步处理"**——立即 200，把事件丢进队列/后台，避免业务耗时拖垮 20 秒上限。

```
HTTP 层面时序
POST /webhook ──────────► 你
               你校验签名 + 入队
               你返回 200（<20s）
                        │
                        └─ 后台 worker 处理业务、调 Send API、更新 DB
```

> **踩坑经验**：如果同步地"收到→推理→发送→再返回 200"，遇到慢推理（LLM 客服）会超时触发重试，造成重复回复。**必须 200 先行、业务后置**，并在业务端按 `mid`/`entry_id` 做幂等去重。

#### 2.6.7 多 Page 共收：entry[].id 路由

生产环境常常一个 App 绑定多个 Page（多品牌）。此时要用 `entry[].id` 路由到对应 Page 的 Token 与业务：

```python
def route_event(event):
    page_id = event.get("id")
    conf = PAGE_CONFIGS.get(page_id)     # {page_id: {"token":..., ...}}
    if not conf:
        log.warning("未知页面 %s", page_id)
        return
    for msg in event.get("messaging", []):
        handle_messaging(msg, conf)
```

> **踩坑经验**：不同 Page 的 PSID 体系相互独立，**绝不能**把 A 页面的 PSID 拿去给 B 页面发消息（会报"no such user"或发错人）。Token 与 PSID 必须**按页面配对**。

### 2.7 Handover Protocol 与 Page Inbox 深度解析

当机器人需要"人机协作"（机器人处理简单诉求，人工接管复杂/敏感诉求）时，使用 **Handover Protocol（接管协议）** 与 **Page Inbox（页面收件箱）**。

#### 2.7.1 为什么需要 Handover

Messenger 支持**多个接收方**同时订阅同一页面的消息（机器人、Page Inbox 人工、第三方 CRM 等）。若不协调，用户一条消息会同时被机器人和人工处理 → 重复回复、状态冲突。

**Handover Protocol 的三种接收方角色：**

| 角色 | 说明 |
|------|------|
| Primary Receiver（主要接收方） | 新消息默认先到它这里（通常是机器人） |
| Secondary Receiver（次要接收方） | 等待被托管，通常指 Page Inbox 人工 |
| Tertiary（接管夥伴，App 层） | 第三方集成应用，通过 `take_threadcontrol` 等接管 |

> 简言之：**新消息默认给 Primary（机器人）**；机器人可把会话**暂存**给 Page Inbox（Secondary）让人工处理；处理完再**收回控制权**。**同一时刻只有一个接收方**拥有某会话。

#### 2.7.2 主要端点

```
Handover Protocol 端点
├── POST /me/pass_thread_control     将控制权交给新接收方
├── POST /me/take_thread_control     从当前接收方收回控制权
├── POST /me/request_thread_control  请求控制权（配合 pass 之后）
└── GET  /me/secondary_receivers     查询次要接收方列表
```

**把会话交给人工（Page Inbox）：**

```bash
curl -X POST "https://graph.facebook.com/v22.0/me/pass_thread_control?access_token=EAAxxx" \
  -H "Content-Type: application/json" \
  -d '{
    "recipient": {"id": "<PSID>"},
    "target_app_id": 263902037430900,
    "metadata": "用户要求人工客服"
  }'
```

> `target_app_id` 为 `263902037430900` 时表示交给 **Page Inbox（人工）**；交给某个第三方 App 则填该 App 的 id。

**收回控制权：**

```bash
curl -X POST "https://graph.facebook.com/v22.0/me/take_thread_control?access_token=EAAxxx" \
  -H "Content-Type: application/json" \
  -d '{"recipient": {"id": "<PSID>"}}'
```

**Webhook 侧的手势：**

```
m 事件（inbound message）   → 当前接收方收到用户消息
messaging_handovers 事件     → 控制权移交的通知
  ├── pass_thread_control   → 你交出了控制权
  └── take_thread_control   → 你收回了控制权
```

**接收 handover 事件：**

```json
{
  "messaging": [{
    "sender": {"id": "100000123456789"},
    "recipient": {"id": "123456789012345"},
    "timestamp": 1723600000000,
    "pass_thread_control": {
      "new_owner_app_id": 263902037430900,
      "metadata": "用户要求人工客服"
    }
  }]
}
```

#### 2.7.3 典型人机协作状态流

```
用户发消息 ──► Primary(机器人)
   │
   ├─ 简单诉求 → 机器人直接回复
   │
   └─ 复杂/敏感诉求 → 机器人回复"为您转接人工"
          │
          ▼
   pass_thread_control(id=PageInbox)
          │
          ▼（staking：应用层暂停对该会话的自动处理）
   人工在 Page Inbox 处理
          │
   （人工完成 / 或需机器人接续）→ take_thread_control
          │
          ▼
   机器人恢复对会话的处理
```

> **踩坑经验**：`pass_thread_control` 后，机器人在会话被接管期间**不应**继续给该用户主动发自动回复（除非接管状态判断错误）。接管期间若机器人收到 `m` 事件，通常是**路由到新 owner** 的信号，机器人侧要标记"已在人工处理中"。

#### 2.7.4 与广告引流组合的协作模式

Click-to-Messenger 广告常搭配"机器人首聊 → 人工转化客服"：

- 广告点击 → 机器人 welcome flow（收集意向、发产品卡）→ 有意向 → `pass_thread_control` 交给人工客服 → 人工成交。
- 非工作时间 → 机器人保留控制权自动回复，次日再转人工。
- 这种"机器人筛线索 + 人工精转化"的模式，是 `messages` 目标广告的黄金组合。

### 2.8 Page / App 设置深度解析

机器人运行前的"天时"：Page 与 App 的正确绑定、Token 的生成与续期、权限与发布模式。

#### 2.8.1 页面与 App 的绑定

```
开发者后台（developers.facebook.com）
├── 我的应用 → 选择 App → 产品 → Messenger → 设置
│   ├── 选择要接入的 Page（必须对该 Page 有 admin 权限）
│   ├── 授予后自动绑定
│   └── 生成/刷新 Page Token
└── App 级设置
    ├── 回调 URL（Callback URL）
    ├── 校验令牌（Verify Token）
    └── 订阅字段（messages, postbacks, ...）
```

**绑定失败的常见原因：**

| 原因 | 现象 | 解法 |
|------|------|------|
| 账号无该 Page 的 admin 权限 | 下拉选不到 Page | 用有 Page 角色的人操作 |
| App 未开启 Messenger 产品 | 菜单里没有 Messenger | 在 Products 中添加 Messenger |
| 域名/服务器不可达 | 校验 GET 失败 | 确保 HTTPS + 公网可达 + 证书有效 |
| Verify Token 不匹配 | 校验返回 403 | 核对两端配置一致 |

#### 2.8.2 Page Token 的生成与续期

Page Token 是调用 Send/Profile 的凭证，**来自 App 的 User Token 换取**：

```
1. 用户授权 App（需 manage_pages 权限）→ 得到 short-lived user token
2. 用 long-lived user token（60 天，通过 appsecret 换）调用：
   GET /me/accounts → 拿到 page 的 access_token
3. 该 page token 默认不过期（with pages_messaging），但
   - 若用户取消授权 / 改密码 / 删除 App → 失效
   - 可随时在后台重新生成
```

**用 user token 换 page token（curl）：**

```bash
# 换长期 user token
curl -X GET "https://graph.facebook.com/v22.0/oauth/access_token?grant_type=fb_exchange_token&client_id=<APP_ID>&client_secret=<APP_SECRET>&fb_exchange_token=<SHORT_TOKEN>"
# → long_lived_user_token

# 列出可管理的 page 与 token
curl -X GET "https://graph.facebook.com/v22.0/me/accounts?access_token=<LONG_USER_TOKEN>"
```

**Page Token 生命周期：**

| 状态 | 有效性 | 处理 |
|------|--------|------|
| 正常 | 长期有效 | - |
| 用户改密码 / 重授权 | 可能失效 | 检测 401 后触发重新授权 |
| 用户移除 App | 失效 | 监控并通知负责人 |
| Token 含敏感权限 | 需企业在后台维护 | 采用"长期 + 多冗余"策略 |

> **踩坑经验**：Page Token 千万别写进前端 / Git；用环境变量或密钥管理服务存储。**加解密与轮换**要纳入 CI。Token 泄露是被入侵后攻击者直接可以"假扮你的机器人"的通道。

#### 2.8.3 订阅字段的选择

在 Webhook 订阅页勾选字段时，**只勾需要的**：

```
messages                  ← 必备（收文本/附件/快捷回复）
messaging_postbacks       ← 必备（按钮/开始/菜单回调）
message_deliveries        ← 回执（客服分析用）
message_reads             ← 已读（客服分析用）
messaging_handovers       ← 人工协作必备
messaging_referrals       ← m.me/CTA 引流归因必备
messaging_optins          ← 订阅消息用
account_linking           ← 账号绑定用
```

> **踩坑经验**：勾选太多不需要的字段，会让生产 Webhook 收到大量无关事件，增加处理与存储成本；但**少了关键字段**（如忘勾 messaging_referrals）会导致引流归因拿不到 `referral.ref`。按业务精确勾选。

#### 2.8.4 开发模式 vs 发布模式（审核）

| 模式 | 用途 | 限制 |
|------|------|------|
| 开发模式（Development） | 开发者自测 | 仅限 App 管理员/开发者可见，可收发 |
| 标准访问（Standard Access） | 面向公众发布 | 需审核 `pages_messaging` 及广告相关用例 |
| 付费/世（Business Verification） | 企业认证 | 提升信任与放宽场景 |

**标准访问审核要点：**

- 提交理由必须**明确、具体**（例如"用于客户支持自动回复"），并附录屏/文档。
- 涉及 `user_phone_number` / `user_email` 快捷回复、订阅消息推送等敏感能力，需额外说明用途与合规措施。
- 审核状态可在后台查看，未过审时期限内 App 无法面向真实用户。

> **踩坑经验**：审核是**项目排期**的一部分，不是上线前一天才做。开发和发布最好**双 App**：dev App 用于日常联调，prod App 走审核并冻结设置，避免审核期间误改配置。

---

## 三、生产环境实战

> 本节用一套完整的 Python（Flask）示例，从零搭一个可直接上线的 Messenger 机器人，并补齐 Click-to-Messenger 广告对接与上线运维。方法命名沿用 Ryan 知识库 `meta_*` 的统一风格。

### 3.1 项目骨架与配置

**目录结构：**

```
messenger-bot-service/
├── app.py                  # 入口
├── config.py               # 配置读取（环境变量）
├── send.py                 # meta_send_messenger_message 等发送封装
├── profile.py              # meta_set_messenger_profile 等配置封装
├── thumbnail.py            # meta_create_thumbnail 等缩略图封装
├── domain_links.py         # meta_create_domain_link 等短链封装
├── webhook.py              # meta_handle_messenger_webhook 调度
├── state.py                # 会话状态机
├── handlers/               # 各事件处理器
├── db/models.py            # PSID 档案与会话持久化
├── ad/cta_helpers.py       # Click-to-Messenger 广告辅助
└── tests/test_webhook.py
```

**config.py：**

```python
import os


class Config:
    """从环境变量读取全部敏感配置，绝不硬编码。"""

    APP_ID = os.environ.get("META_APP_ID", "")
    APP_SECRET = os.environ.get("META_APP_SECRET", "")
    PAGE_ID = os.environ.get("META_PAGE_ID", "")

    # 单一 Page 场景可只配 PAGE_TOKEN；多页场景建议用 PAGE_CONFIGS 字典
    PAGE_TOKEN = os.environ.get("META_PAGE_TOKEN", "")

    # 多页面配置：{page_id: {"token": ..., "verify": ...}}
    PAGE_CONFIGS = {
        PAGE_ID: {"token": PAGE_TOKEN, "verify": os.environ.get("VERIFY_TOKEN", "")}
    } if PAGE_ID else {}

    # webhook 校验令牌（配置 Callback 时一致）
    VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "")

    # 白名单域名
    WHITELISTED_DOMAINS = [
        "https://www.example.com",
        "https://help.example.com",
    ]

    # 对外基础地址（用于回跳、域链接、日志）
    BASE_URL = os.environ.get("BASE_URL", "https://api.example.com")

    GRAPH_BASE = "https://graph.facebook.com/v22.0"
```

> **踩坑经验**：多个 Page 时，把 `PAGE_CONFIGS` 做成 `page_id → token` 的字典，并在 webhook 路由时按 `entry[].id` 选择对应 token（见 2.6.7），不要用单一全局 token 发所有消息。

### 3.2 Send API 封装（send.py）

统一封装 `meta_send_messenger_message`，屏蔽 curl、错误处理、限流重试。

```python
import requests
import time
import logging
from config import Config

logger = logging.getLogger(__name__)


class MessengerError(Exception):
    """Messenger API 调用异常，保留 error 详情便于排查。"""
    def __init__(self, message, error_data=None):
        super().__init__(message)
        self.error_data = error_data or {}


def _call_send_api(payload, page_token=None, retries=3, backoff=1.0):
    """调用 /me/messages 的统一底座：错误处理 + 指数退避重试。"""
    token = page_token or Config.PAGE_TOKEN
    url = f"{Config.GRAPH_BASE}/me/messages?access_token={token}"
    for attempt in range(retries):
        resp = requests.post(url, json=payload, timeout=15)
        if resp.status_code == 200:
            return resp.json()
        data = resp.json()
        err = data.get("error", {})
        if err.get("code") == 613:  # 限流，退避后重试
            wait = backoff * (2 ** attempt)
            logger.warning("限流(613)，%.1fs 后重试", wait)
            time.sleep(wait)
            continue
        if err.get("code") in (1, 2) and attempt < retries - 1:
            # 临时性服务器错误，可重试
            time.sleep(backoff * (2 ** attempt))
            continue
        raise MessengerError(
            f"SendAPI 失败 code={err.get('code')} msg={err.get('message')}",
            err,
        )
    raise MessengerError("重试次数用尽")


def meta_send_messenger_message(recipient_id, message, page_token=None):
    """发送任意 message 载体（text / attachment / template 均可）。"""
    if not message:
        raise ValueError("message 不能为空")
    payload = {
        "recipient": {"id": str(recipient_id)},
        "message": message,
    }
    return _call_send_api(payload, page_token)


def meta_send_text(recipient_id, text, page_token=None):
    """便捷：发纯文本。"""
    return meta_send_messenger_message(
        recipient_id, {"text": str(text)}, page_token
    )


def meta_send_text_with_quick_replies(recipient_id, text, quick_replies, page_token=None):
    """便捷：文本 + 快捷回复。quick_replies 上限 13 个。"""
    if len(quick_replies) > 13:
        quick_replies = quick_replies[:13]
    return meta_send_messenger_message(
        recipient_id, {"text": text, "quick_replies": quick_replies}, page_token
    )


def meta_send_sender_action(recipient_id, action, page_token=None):
    """发送输入状态。action ∈ {typing_on, typing_off, mark_seen}。"""
    payload = {"recipient": {"id": str(recipient_id)}, "sender_action": action}
    return _call_send_api(payload, page_token)
```

**通用模板（generic）封装：**

```python
def meta_send_generic_template(recipient_id, elements, image_aspect_ratio="horizontal", page_token=None):
    """发送 generic 卡片流。elements 为 list，最多 10 张卡片。"""
    if len(elements) > 10:
        elements = elements[:10]
    message = {
        "attachment": {
            "type": "template",
            "payload": {
                "template_type": "generic",
                "image_aspect_ratio": image_aspect_ratio,
                "elements": elements,
            },
        }
    }
    return meta_send_messenger_message(recipient_id, message, page_token)


def meta_send_button_template(recipient_id, text, buttons, page_token=None):
    """发送按钮模板。buttons 最多 3 个。"""
    if len(buttons) > 3:
        buttons = buttons[:3]
    message = {
        "attachment": {
            "type": "template",
            "payload": {
                "template_type": "button",
                "text": text,
                "buttons": buttons,
            },
        }
    }
    return meta_send_messenger_message(recipient_id, message, page_token)
```

**媒体模板与附件复用封装：**

```python
def meta_send_media_template(recipient_id, media_type, url=None, attachment_id=None, buttons=None, page_token=None):
    """发送媒体模板。media_type ∈ {image, video}。url 与 attachment_id 二选一。"""
    elem = {"media_type": media_type}
    if url:
        elem["url"] = url
    if attachment_id:
        elem["attachment_id"] = attachment_id
    if buttons:
        elem["buttons"] = buttons[:1]   # 媒体模板仅允许 1 个按钮
    message = {
        "attachment": {
            "type": "template",
            "payload": {"template_type": "media", "elements": [elem]},
        }
    }
    return meta_send_messenger_message(recipient_id, message, page_token)


def meta_upload_message_attachment(recipient_id, attachment_type, file_path, is_reusable=True, page_token=None):
    """上传可复用附件，返回 attachment_id。attachment_type ∈ {image, video, audio, file}。"""
    token = page_token or Config.PAGE_TOKEN
    url = f"{Config.GRAPH_BASE}/me/message_attachments?access_token={token}"
    files = {"filedata": open(file_path, "rb")}
    data = {
        "recipient": json.dumps({"id": str(recipient_id)}),
        "message": json.dumps({
            "attachment": {"type": attachment_type, "payload": {"is_reusable": is_reusable}}
        }),
    }
    resp = requests.post(url, data=data, files=files, timeout=60)
    resp.raise_for_status()
    return resp.json().get("attachment_id")
```

> **踩坑经验**：`meta_send_messenger_message` 里的 `recipient_id` 一定要 `str()` 处理——Graph API 对非字符串 id 会报类型错误。发送前最好校验 PSID 是纯数字字符串，防止 XSS/注入式参数。

### 3.3 Profile / 配置封装（profile.py）

把 Profile API 的几个常用能力封装为 `meta_*` 函数。

```python
import requests
from config import Config
from send import MessengerError


def _profile_request(method, payload=None, fields=None, page_token=None):
    """调用 /me/messenger_profile 的统一底座。method ∈ {POST, GET, DELETE}。"""
    token = page_token or Config.PAGE_TOKEN
    url = f"{Config.GRAPH_BASE}/me/messenger_profile?access_token={token}"
    if fields:
        url += "&fields=" + ",".join(fields)
    if method == "POST":
        resp = requests.post(url, json=payload, timeout=15)
    elif method == "DELETE":
        resp = requests.delete(url, json=payload, timeout=15)
    else:
        resp = requests.get(url, timeout=15)
    if resp.status_code != 200:
        err = resp.json().get("error", {})
        raise MessengerError(
            f"messenger_profile {method} 失败 code={err.get('code')} msg={err.get('message')}",
            err,
        )
    return resp.json()


def meta_set_get_started(payload="GET_STARTED", page_token=None):
    """设置开始按钮。payload 为点击后回调的 postback 标记。"""
    return _profile_request("POST", {"get_started": {"payload": payload}}, page_token=page_token)


def meta_set_greeting(texts, page_token=None):
    """设置问候语。texts 为 [{"locale","text"}, ...]，最多 20 条，default 兜底。"""
    return _profile_request("POST", {"greeting": texts}, page_token=page_token)


def meta_set_whitelisted_domains(domains, page_token=None):
    """设置白名单域名。domains 需带协议、小写、无末尾斜杠。"""
    return _profile_request("POST", {"whitelisted_domains": domains}, page_token=page_token)


def meta_set_ice_breakers(questions, page_token=None):
    """设置破冰短语。questions 为 [{"locale","question","payload"}, ...]，最多 5 条。"""
    return _profile_request("POST", {"ice_breakers": questions}, page_token=page_token)
```

**持久菜单封装（meta_set_persistent_menu）：**

```python
def meta_set_persistent_menu(
    call_to_actions,
    locale="default",
    composer_input_disabled=False,
    page_token=None,
):
    """
    设置常驻菜单（整体替换语义）。
    call_to_actions: 菜单项数组，顶级最多 5 个；nested 类型的子项最多 5 个。
    """
    if len(call_to_actions) > 5:
        raise ValueError("顶级菜单项最多 5 个")
    menu = [{
        "locale": locale,
        "composer_input_disabled": composer_input_disabled,
        "call_to_actions": call_to_actions,
    }]
    return _profile_request("POST", {"persistent_menu": menu}, page_token=page_token)


# 示例：构建菜单项
product_menu = [
    {"type": "postback", "title": "查看产品", "payload": "VIEW_PRODUCTS"},
    {
        "type": "nested",
        "title": "客服支持",
        "call_to_actions": [
            {"type": "postback", "title": "常见问题", "payload": "FAQ"},
            {"type": "postback", "title": "人工客服", "payload": "HUMAN_AGENT"},
            {"type": "web_url", "title": "帮助中心", "url": "https://help.example.com", "webview_height_ratio": "full"},
        ],
    },
    {"type": "web_url", "title": "访问官网", "url": "https://www.example.com", "webview_height_ratio": "full"},
]

# meta_set_persistent_menu(product_menu)

def meta_get_messenger_profile(fields=None, page_token=None):
    """查询当前 messenger_profile 配置。fields 如 ["get_started","greeting"]。"""
    return _profile_request("GET", fields=fields, page_token=page_token)


def meta_clear_messenger_profile(fields, page_token=None):
    """删除指定 profile 属性。fields 为数组，如 ["get_started"]。"""
    return _profile_request("DELETE", {"fields": fields}, page_token=page_token)
```

> **踩坑经验**：`meta_set_persistent_menu` 是**整体替换**，调用前若不确定当前菜单，先 `meta_get_messenger_profile(["persistent_menu"])` 再合并。

### 3.4 缩略图与域链接封装（thumbnail.py / domain_links.py）

```python
# thumbnail.py —— 注意：缩略图用 App Token（不是 Page Token）
import requests
from config import Config
from send import MessengerError


def _app_token():
    # App Token 由 App ID + App Secret 拼接
    return f"{Config.APP_ID}|{Config.APP_SECRET}"


def meta_create_thumbnail(file_path, caption=None):
    """上传缩略图，返回 thumbnail_id。"""
    url = f"{Config.GRAPH_BASE}/{Config.APP_ID}/thumbnails"
    files = {"file": open(file_path, "rb")}
    data = {"access_token": _app_token()}
    if caption:
        data["caption"] = caption
    resp = requests.post(url, data=data, files=files, timeout=60)
    if resp.status_code != 200:
        err = resp.json().get("error", {})
        raise MessengerError(f"创建缩略图失败 {err.get('message')}", err)
    return resp.json().get("id")


def meta_list_thumbnails():
    url = f"{Config.GRAPH_BASE}/{Config.APP_ID}/thumbnails?access_token={_app_token()}"
    resp = requests.get(url, timeout=15)
    resp.raise_for_status()
    return resp.json().get("data", [])


def meta_delete_thumbnail(thumbnail_id):
    url = f"{Config.GRAPH_BASE}/{Config.APP_ID}/thumbnails/{thumbnail_id}?access_token={_app_token()}"
    resp = requests.delete(url, timeout=15)
    resp.raise_for_status()
    return resp.json()
```

```python
# domain_links.py
import requests
from config import Config
from send import MessengerError


def _app_token():
    return f"{Config.APP_ID}|{Config.APP_SECRET}"


def meta_create_domain_link(name, uri, image_url=None, platform="all", thumbnail_id=None):
    """创建 m.me 参数化域链接，可绑定缩略图。uri 形如 https://m.me/ExampleBrand?ref=xxx"""
    payload = {
        "access_token": _app_token(),
        "name": name,
        "uri": uri,
        "platform": platform,
    }
    if image_url:
        payload["image_url"] = image_url
    if thumbnail_id:
        payload["thumbnail_id"] = thumbnail_id
    url = f"{Config.GRAPH_BASE}/{Config.APP_ID}/domain_links"
    resp = requests.post(url, json=payload, timeout=15)
    if resp.status_code != 200:
        err = resp.json().get("error", {})
        raise MessengerError(f"创建域链接失败 {err.get('message')}", err)
    return resp.json()


def meta_list_domain_links():
    url = f"{Config.GRAPH_BASE}/{Config.APP_ID}/domain_links?access_token={_app_token()}"
    resp = requests.get(url, timeout=15)
    resp.raise_for_status()
    return resp.json().get("data", [])


def meta_delete_domain_link(domain_link_id):
    url = f"{Config.GRAPH_BASE}/{Config.APP_ID}/domain_links/{domain_link_id}?access_token={_app_token()}"
    resp = requests.delete(url, timeout=15)
    resp.raise_for_status()
    return resp.json()
```

> **踩坑经验（关键）**：**缩略图与域链接的创建都必须用 App Token**（`APP_ID|APP_SECRET`），而**不是** Page Token。反之，发消息/配 Profile 用的是 Page Token。两类 Token 混用是高频报错来源。

### 3.5 Webhook 接收端（webhook.py + app.py）

**完整 Flask 应用与事件调度（meta_handle_messenger_webhook）：**

```python
# app.py —— 入口
import logging
from flask import Flask, request, abort, jsonify

from config import Config
from webhook import meta_handle_messenger_webhook, verify_webhook_signature

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)


@app.route("/webhook", methods=["GET"])
def webhook_verify():
    """Meta 首次配置时回填 challenge 用的 GET。"""
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")
    if mode == "subscribe" and token == Config.VERIFY_TOKEN:
        return challenge, 200
    return "Verification failed", 403


@app.route("/webhook", methods=["POST"])
def webhook_receive():
    """接收 Meta 事件：先验签，先 ACK 200，再异步处理业务。"""
    if not verify_webhook_signature(request):
        abort(403, "Invalid signature")
    body = request.get_json(force=True)
    # 同步只入队 + ACK；业务在 worker 里异步执行，避免拖垮 20s 上限
    enqueue_events(body)
    return jsonify({"status": "ok"}), 200
```

```python
# webhook.py
import hashlib
import hmac
import logging
from flask import request

from config import Config
from send import MessengerError

logger = logging.getLogger(__name__)


def verify_webhook_signature(req) -> bool:
    """校验 X-Hub-Signature-256。必须用原始字节做 HMAC。"""
    expected = req.headers.get("X-Hub-Signature-256", "")
    if not expected.startswith("sha256="):
        return False
    digest = hmac.new(
        key=Config.APP_SECRET.encode("utf-8"),
        msg=req.get_data(),          # 原始请求体字节
        digestmod=hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected[len("sha256="):], digest)


def enqueue_events(body):
    """把事件入队（此处简化为直接调用；生产可换成 celery / Redis queue）。"""
    # 注意：真实生产里 enqueue 后立即返回 200，由 worker 调 handle
    meta_handle_messenger_webhook(body)


def meta_handle_messenger_webhook(body):
    """核心调度：遍历 entry/event，按类型分发给对应 handler。"""
    if body.get("object") != "page":
        logger.warning("非 page object: %s", body.get("object"))
        return

    for entry in body.get("entry", []):
        page_id = entry.get("id")
        page_conf = Config.PAGE_CONFIGS.get(page_id)
        if not page_conf:
            logger.warning("未配置页面 %s，跳过", page_id)
            continue
        context = {"page_id": page_id, "page_token": page_conf["token"]}

        for event in entry.get("messaging", []):
            try:
                route_messaging_event(event, context)
            except Exception:
                logger.exception("处理事件失败 sender=%s", event.get("sender"))


def route_messaging_event(event, context):
    if "message" in event and not event["message"].get("is_echo"):
        handle_message_event(event, context)
    elif "postback" in event:
        handle_postback_event(event, context)
    elif "referral" in event:
        handle_referral_event(event, context)
    elif "delivery" in event:
        handle_delivery_event(event, context)
    elif "read" in event:
        handle_read_event(event, context)
    elif "pass_thread_control" in event or "take_thread_control" in event:
        handle_handover_event(event, context)
    elif "optin" in event:
        handle_optin_event(event, context)
    else:
        logger.info("未识别事件类型: %s", list(event.keys()))
```

**各事件处理器示意（handlers/）：**

```python
# handlers/text_handler.py
def handle_message_event(event, context):
    sender = event["sender"]["id"]
    msg = event.get("message", {})
    # 幂等：按 mid 去重
    mid = msg.get("mid")
    if not seen_mid(sender, mid):
        return None
    mark_mid_seen(sender, mid)

    # 快捷回复优先于纯文本意图
    qr = msg.get("quick_reply", {}).get("payload")
    text = msg.get("text", "")

    intent = qr or normalize_intent(text)
    state = load_state(sender, context["page_id"])

    # 触发输入状态 + 按状态机分发
    meta_send_sender_action(sender, "typing_on", context["page_token"])
    answer = dispatch(state, intent, text, msg.get("attachments"))
    if answer:
        for piece in answer:
            meta_send_messenger_message(sender, piece, context["page_token"])
```

**postback 处理：**

```python
def handle_postback_event(event, context):
    sender = event["sender"]["id"]
    postback = event["postback"]
    payload = postback.get("payload", "")
    logger.info("postback %s → %s", sender, payload)

    if payload == "GET_STARTED":
        meta_send_sender_action(sender, "typing_on", context["page_token"])
        meta_send_text_with_quick_replies(
            sender,
            "你好！我是 Example 智能助手，请问您想了解什么？",
            [
                {"content_type": "text", "title": "产品", "payload": "TOPIC_PRODUCT"},
                {"content_type": "text", "title": "价格", "payload": "TOPIC_PRICE"},
                {"content_type": "text", "title": "人工客服", "payload": "HUMAN_AGENT"},
            ],
            context["page_token"],
        )
    elif payload == "HUMAN_AGENT":
        # 转人工：先回执告知，再把控制权交给 Page Inbox
        meta_send_text(sender, "正在为您转接人工客服，请稍候…", context["page_token"])
        pass_thread_control(sender, target_inbox=True, meta=payload, page_token=context["page_token"])
    else:
        # 其它业务 payload 走状态机
        pass
```

**回执处理（投递 / 已读）：**

```python
def handle_delivery_event(event, context):
    delivery = event.get("delivery", {})
    watermark = delivery.get("watermark")
    mids = delivery.get("mids", [])
    logger.info("delivery watermark=%s mids=%s", watermark, mids[:5])
    # 可用于"发出答复后确认送达"的仪表盘埋点


def handle_read_event(event, context):
    read = event.get("read", {})
    logger.info("read watermark=%s", read.get("watermark"))
    # 可触发"已读后 N 分钟未回复"的跟进提醒
```

**接管处理（Handover）：**

```python
def handle_handover_event(event, context):
    if "pass_thread_control" in event:
        info = event["pass_thread_control"]
        owner = info.get("new_owner_app_id")
        meta = info.get("metadata")
        logger.info("控制权移交给 app=%s meta=%s", owner, meta)
        mark_inbox_mode(event["sender"]["id"], True)
    elif "take_thread_control" in event:
        logger.info("控制权已被收回，恢复机器人接管")
        mark_inbox_mode(event["sender"]["id"], False)
```

**referral / optin 处理：**

```python
def handle_referral_event(event, context):
    sender = event["sender"]["id"]
    ref = event.get("referral", {}).get("ref", "")
    source = event.get("referral", {}).get("source", "")
    # CTA 广告 / m.me 短链归因：ref 常为 ad/渠道标记，持久化到用户档案
    record_referral(sender, ref, source)
    meta_send_text(sender, f"欢迎通过 {ref or '外部链接'} 进来！", context["page_token"])


def handle_optin_event(event, context):
    sender = event["sender"]["id"]
    ref = event.get("optin", {}).get("ref", "")
    # 用户 opt-in 订阅 → 可长期推送（需 `pages_messaging_subscriptions` 审核能力）
    record_optin(sender, ref)
```

> **踩坑经验**：**先 ACK 200 再异步处理**是架构纪律。若在 webhook 里同步跑完整业务（尤其接 LLM 推理），极易超 20 秒触发 Meta 重试，重复事件叠加。生产用队列（Celery + Redis）解耦。

### 3.6 会话状态机（state.py）

机器人对话本质是**状态机**：同一句"在吗？"在不同流程阶段含义不同。用显式状态机避免"一锅粥"式的 if 嵌套。

**状态定义：**

```python
# state.py
import enum


class BotState(enum.Enum):
    INIT = "INIT"                # 初始/空闲
    ASKED_TOPIC = "ASKED_TOPIC"  # 已问意向类别
    ASKED_CONTACT = "ASKED_CONTACT"  # 正在收集联系方式
    WAITING_AGENT = "WAITING_AGENT"  # 已转人工，等待接管结束
    FINAL = "FINAL"              # 会话结束


# 状态迁移表：状态 → 意图 → (新状态, 回复策略)
TRANSITIONS = {
    BotState.INIT: {
        "TOPIC_PRODUCT": (BotState.ASKED_TOPIC, "show_products"),
        "TOPIC_PRICE": (BotState.ASKED_TOPIC, "show_prices"),
        "HUMAN_AGENT": (BotState.WAITING_AGENT, "transfer_to_agent"),
        "FAQ": (BotState.INIT, "show_faq"),
    },
    BotState.ASKED_TOPIC: {
        "BUY_*": (BotState.ASKED_CONTACT, "ask_contact"),
        "HUMAN_AGENT": (BotState.WAITING_AGENT, "transfer_to_agent"),
    },
    BotState.ASKED_CONTACT: {
        "PHONE_*": (BotState.FINAL, "save_contact_and_done"),
        "CANCEL": (BotState.INIT, "reset"),
    },
    BotState.WAITING_AGENT: {
        "*": (BotState.WAITING_AGENT, "ignore_or_queue"),
    },
}
```

**状态机核心：**

```python
def dispatch(state, intent, text, attachments):
    """根据当前状态与意图决定回复策略。返回 message 载体列表（可为空）。"""
    table = TRANSITIONS.get(state, {})
    # 支持通配：先精确匹配，再试 BUY_* / PHONE_* 前缀，最后 *
    action = table.get(intent)
    if action is None:
        for key, cand in table.items():
            if key.endswith("*") and (intent or "").startswith(key[:-1]):
                action = cand
                break
    if action is None and "*" in table:
        action = table["*"]

    if action is None:
        return [{"text": "抱歉，我没有完全理解。您可以直接点击下方按钮，或输入'人工客服'。"}]

    new_state, strategy = action
    save_state(state_owner(), new_state)   # state_owner 返回 (psid,page_id) 定位
    return getattr(ReplyFactory, strategy)()
```

**回复工厂（ReplyFactory）：**

```python
class ReplyFactory:
    @staticmethod
    def show_products():
        return [{
            "attachment": {
                "type": "template",
                "payload": {
                    "template_type": "generic",
                    "elements": [
                        {"title": "新品 A", "image_url": "https://cdn.example.com/a.png",
                         "subtitle": "¥199",
                         "buttons": [{"type": "postback", "title": "咨询", "payload": "BUY_A"}]},
                        {"title": "新品 B", "image_url": "https://cdn.example.com/b.png",
                         "subtitle": "¥299",
                         "buttons": [{"type": "postback", "title": "咨询", "payload": "BUY_B"}]},
                    ],
                },
            }
        }]

    @staticmethod
    def ask_contact():
        return [{
            "text": "好的，请问怎么称呼您？也可以点击下方直接留联系方式：",
            "quick_replies": [
                {"content_type": "user_phone_number", "title": "留电话"},
                {"content_type": "user_email", "title": "留邮箱"},
            ],
        }]

    @staticmethod
    def transfer_to_agent():
        # 处理在 postback/webhook 里调用 pass_thread_control，这里返回话术
        return [{"text": "正在为您转接人工客服…"}]

    @staticmethod
    def show_faq():
        return [{"text": "常见问题：\n1. 物流 2-3 天\n2. 支持 7 天退换\n更多请咨询人工。"}]

    @staticmethod
    def save_contact_and_done():
        return [{"text": "已收到您的联系方式，客服将尽快与您联系。"}]
```

> **踩坑经验**：状态必须**持久化**（Redis/DB），并绑定 `(psid, page_id)`，不能只放内存——Webhook worker 可能多实例、多进程，内存态会丢。状态迁移要**防呆**：`WAITING_AGENT` 状态下把新消息交还给人工（忽略或提示），避免机器人抢回控制权。

### 3.7 与 Click-to-Messenger 广告的深度结合

这是与广告投放团队协同的核心场景：**广告点击 → 进入 Messenger 对话 → 机器人承接 → 线索/成交**。

#### 3.7.1 广告跳转与 referral 事件

Click-to-Messenger 广告点击后，用户进入对话并触发 `messaging_referrals` 事件，其中：

```
referral.source = "ADS"
referral.type   = "OPEN_THREAD"
referral.ad_id  = <广告 ID>       # CTA 广告自带
referral.adtracking ?           # 部分场景有额外跟踪
```

```json
{
  "messaging": [{
    "sender": {"id": "100000123456789"},
    "recipient": {"id": "123456789012345"},
    "referral": {
      "ref": "SUMMER_SALE_2026",
      "source": "ADS",
      "type": "OPEN_THREAD",
      "ad_id": "238498277238947"
    }
  }]
}
```

**据此可以：**
- 按广告/活动（`ad_id` / `ref`）分流不同的欢迎话术。
- 把来源标记持久化到用户档案，供成交归因。
- 结合 Marketing API 用 `ad_id` 反查广告维度，形成"广告 → 对话 → 转化"闭环数据。

#### 3.7.2 广告侧配置要点（Marketing API）

创建 Click-to-Messenger 广告（`click_to_messenger` 创意类型），关键字段：

```bash
# 创意：click_to_messenger 类型（示意字段）
curl -X POST "https://graph.facebook.com/v22.0/<AD_ACCOUNT_ID>/adcreatives" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "夏季大促 CTA-广告",
    "object_story_spec": {
      "page_id": "<PAGE_ID>",
      "link_data": {
        "message": "夏季大促，点击与我们对话获取专属优惠券！",
        "link": "https://fb.me/ExampleBrand",
        "name": "立即咨询",
        "call_to_action": {
          "type": "MESSAGE_PAGE",
          "value": {
            "app_id": "<APP_ID>",
            "page_id": "<PAGE_ID>"
          }
        }
      }
    }
  }'
```

**CTA 类型**：`MESSAGE_PAGE`（到页面对话）是 Click-to-Messenger 的核心；`LEARN_MORE`+Message 混合也常见。

#### 3.7.3 广告归因闭环（数据打通）

```
Ads Manager 视图：CTR / CPM / 对话转化率（Messages 目标优化）
        │
        └── 触发引擎：广告 → 点击 → Messenger referral(ad_id)
                │
                ▼
        Bot 服务：记录 (PSID, ad_id, ref, 时间)
                │
                ▼
        对话转化：机器人产出线索（留资/下单/转人工）
                │
                ▼
        回写：用 Marketing API 与页面事件做转化归因
                │
                ▼
        Ads 报表：messages 目标 + 转化事件 → 持续优化预算
```

> **踩坑经验**：广告团队常抱怨"对话很多但没有转化"——多半是**广告到机器人承接的断裂**：欢迎语没按广告分流、机器人没收集线索、或没触发转化事件。**广告的 promise 必须与机器人的第一步话术强一致**（例如广告承诺优惠券，机器人第一条消息就发优惠券领取入口），否则跳出率极高。

### 3.8 上线运维要点

#### 3.8.1 健康检查与可观测

- 提供 `/health` 端点做探活。
- 记录 Send API 错误 / 限流 / 回执指标到监控系统。
- 关键告警：Send API 长时间失败、Webhook 处理延迟、Token 失效（401）。

```python
@app.route("/health", methods=["GET"])
def health():
    ok = ping_messenger_api()   # 可轻量调一次 GET /me/accounts 验证 token 有效
    if not ok:
        return jsonify({"status": "down"}), 503
    return jsonify({"status": "up"}), 200
```

#### 3.8.2 灰度与蓝绿发布

- 机器人话术 / 状态机变更走**灰度**：按 PSID 哈希 % N 分流到新旧策略，A/B 比对话术。
- 配置（Profile/菜单/问候语）变更要**可回滚**：先 `GET` 存基线，变更后留备份，出问题用基线恢复。

#### 3.8.3 幂等与并发

- Webhook 事件可能重试：按 `mid` / `(entry_id,event)` 去重，DB 唯一键约束。
- Send API 调用串行/限流保护：给 `meta_send_messenger_message` 加信号量或令牌桶，避免突增触发 613。
- 多实例部署时，状态迁移用 Redis 乐观锁，防并发改状态。

#### 3.8.4 数据合规

- PSID 属于个人信息，存储需脱敏与权限控制。
- 涉及 `user_phone_number` / `user_email` / 订阅推送，需在审核中明确用途，落地隐私政策。
- 跨境业务注意当地法律（如 GDPR / 中国《个保法》）对收集用户联系方式的要求。

---

## 四、常见问题与排查

### 4.1 Webhook 收不到 / 校验失败

| 症状 | 可能原因 | 排查/解法 |
|------|----------|-----------|
| Callback 配置报"校验失败" | Verify Token 不匹配 | 核对后台与代码常量一致，GET 返回 challenge |
| Callback 校验成功但收不到事件 | 未订阅对应字段 | 后台勾选 messages / postbacks 等 |
| 收得到但 403 | 签名校验失败 | 确认用 `X-Hub-Signature-256` + 原始字节 HMAC |
| 偶发收到重复事件 | Meta 重试机制 | 业务端按 mid 幂等去重 |

**签名校验排错口诀：** 用 `request.get_data()`（字节）做 HMAC，不要用 `request.json`；用 `hmac.compare_digest` 比较；确认 `APP_SECRET` 是 App Secret（后台可重置）而非 Page Token。

### 4.2 发消息报错（Send API）

常见错误码速查：

| error code | message 关键字 | 含义 | 解法 |
|-----------|----------------|------|------|
| 100 | Param recipient id / no such user | PSID 无效或过期 | 核对 PSID、确认页面配对、用户可能删对话 |
| 613 | rate limit | 限流 | 退避重试，检查发送节奏 |
| 10 | has not authorized / no permission | Token 无权限 | 检查 pages_messaging、token 归属 |
| 190 | token expired / invalid | Token 失效 | 重新授权/刷新 Page Token |
| 200 | Permission | 权限不足 | 配置对应权限并审核 |
| 191 | Does not match any dominant right | 页面无管理权 | 用有 Page admin 权限的账号 |
| 1200 | 24h window 超时 | 超出消息窗口 | 用企业消息/订阅消息，或引导用户先发消息 |

**"no such user" 深入：** 大概率是**用 A 页面 Token 给 B 页面拿到的 PSID 发消息**——PSID 页面级隔离，务必按 `entry[].id` 配对 token 与 PSID。

### 4.3 Page Token 与 App Token 混用

```
错误示范
├── 用 Page Token 调 /{app-id}/thumbnails   → 权限报错
└── 用 App Token 调 /me/messages             → 报 invalid / no permission

正确分工
├── /me/messages、/me/messenger_profile     → Page Token
└── /{app-id}/thumbnails、/{app-id}/domain_links → App Token (APP_ID|APP_SECRET)
```

### 4.4 persistent_menu / greeting 报错

| 症状 | 原因 | 解法 |
|------|------|------|
| 顶级菜单超 5 项报错 | 违反限制 | 收敛为 5 项内，合并子菜单 |
| greeting 含链接被拒 | 不允许链接 | 去掉链接或放入 message |
| 菜单整体被替换 | 整体替换语义 | POST 前先 GET 合并且留备份 |
| JSON 结构校验失败 | 字段/类型错 | 逐字段核对（type、payload、url） |

### 4.5 24 小时消息窗口命中

**现象**：用户 25 小时前发过消息，你现在发回复被拒（1200）。

**归一化解法：**
1. 窗口内（<24h）完成核心转化。
2. 窗口将到而转化未完 → 发"1 条附加消息"引导（例如"要不要继续？回复 1 继续"）。
3. 长期触达 → 走 **Messaging Subscription（opt-in）**：让用户点击订阅按钮（`PROMPT_SUBSCRIBE` 或 `OPT_IN` 事件），之后可在窗口外推送。
4. 电商/航班等用例 → 申请 **企业消息（Business Messaging）** 放宽窗口。

```json
// 订阅按钮：企业消息/订阅场景
{
  "recipient": {"id": "<PSID>"},
  "message": {
    "attachment": {
      "type": "template",
      "payload": {
        "template_type": "button",
        "text": "想要接收新品与优惠提醒吗？",
        "buttons": [{"type": "postback", "title": "订阅", "payload": "PROMPT_SUBSCRIBE"}]
      }
    }
  }
}
```

> `PROMPT_SUBSCRIBE` 点击后用户会收到官方"订阅"确认，同意后产生 `OPT_IN` 事件，此后可发订阅消息。

### 4.6 转人工（Handover）失效

| 症状 | 原因 | 解法 |
|------|------|------|
| 转人工后机器人还在回复 | 未正确处理接管状态 | 接管期间屏蔽自动回复，按 handover 事件置位 |
| 人工处理完机器人不接管 | 未调用 take_thread_control | 按需收回控制权 |
| pass_thread_control 报错 | target_app_id 写错 | Page Inbox 用 263902037430900 |

### 4.7 广告引流没拿到 referral

- **确认订阅字段**包含 `messaging_referrals`。
- Click-to-Messenger 广告自带 `referral.source=ADS`；临时网页拼的 `ref` 可能不回传。
- 归因请用 `ad_id` + 平台归因，不要依赖手拼 ref。

### 4.8 常用调试工具清单

| 工具 | 用途 |
|------|------|
| Graph API Explorer | 免写代码测试端点 |
| Messaging Review Status | 查权限与审核进度 |
| Webhook 事件查看器（后台） | 回放最近事件、查 event JSON |
| 后台"Send/Receive"测试（to your Page） | 快速发一条消息验证链路 |
| ngrok / 内网穿透 | 本地联调 Webhook |

---

## 五、自测题

### 问题 1

**场景**：你运营两个品牌 Page（A 和 B）。用户先在 A 页面与机器人聊过（拿到 PSID_1），又点击 B 页面的 CTA 广告进入（拿到 PSID_2）。请问 PSID_1 与 PSID_2 是否相同？如果你要用 B 页面 Token 给该用户发消息，应该用哪个 PSID 和 Token 组合？若想跨页面识别同一会员，应该怎么做？

<details><summary>答案</summary>

**不同**。PSID 是"页面级"标识，同一 Facebook 用户在 A、B 两个页面下是**两个不同的 PSID**（PSID_1 和 PSID_2），并且每次只有"页面+应用"组合内的 PSID 有效。

给该用户发消息必须用 **B 页面的 Token + PSID_2**（该 PSID 是从 B 页面事件中拿到的）。用 PSID_1 + B Token 会报"no such user"，用 PSID_2 + A Token 同样会出错——**Token 与 PSID 必须按页面配对**（在 `entry[].id` 路由中按页面取对应 token。

想在跨页面识别同一会员，不能靠 PSID，必须走 **Account Linking（账号绑定）**：通过 `account_linking_url` 让用户在你自己的站点登录，拿到唯一会员号，然后把 PSID 与该会员号在**你的数据库**里映射，从而跨页面统一画像。
</details>

### 问题 2

**场景**：你的 Webhook 收到用户消息后，需要调用一个耗时的 LLM 客服推理（平均 3 秒，最长 15 秒）再回复。你当前是在 Webhook 请求线程里同步完成"推理 → 发送 → 返回 200"。最近发现用户经常收到**重复回复**。请分析根因并给出架构上的正确做法，以及幂等去重应基于什么键。

<details><summary>答案</summary>

**根因**：Webhook 的 HTTP 应答有约 20 秒上限。同步执行时，LLM 慢推理很容易超过 20 秒，导致 Meta 认为发送失败并**退避重试**，相同事件重复到达，每次重试都又跑一遍推理和发送，于是用户看到重复回复。

**正确架构**：**先 ACK 后异步**——Webhook 端**只做验签 + 入队 + 立刻返回 200**，真正的业务（推理、发送）放到后台 worker（如 Celery + Redis 队列）执行。这样无论业务多慢都不影响 200 的及时性，从根上消除服务端重试。

**幂等去重**：worker 处理事件时，以事件的**消息 ID（`mid`）**（或 `(sender+mid)`）作为去重键，在 DB/Redis 加唯一约束，处理过就跳过，防止队列自身或手动重放造成重复。
</details>

### 问题 3

**场景**：你用 Page Token 调用 `POST /{app-id}/thumbnails` 上传缩略图，返回权限错误。同时你用 App Token 调用 `POST /me/messages` 发送消息也被拒。请解释为什么会失败，以及缩略图/域链接与消息发送分别该用哪种 Token，为什么。

<details><summary>答案</summary>

**两类 Token 用途不同，用反必然报错：**

- **Thumbnails（缩略图）与 Domain Links（域链接）资源归属 App**（由 App 创建并管理），创建时需用 **App Token**，格式为 `APP_ID|APP_SECRET` 拼接。用 Page Token 会因"该页面无权管理 App 级资源"而报权限错误。
- **Send API（`/me/messages`）与 Messenger Profile（`/me/messenger_profile`）** 是**页面级**操作，必须用 **Page Token**（拥有 `pages_messaging` 等权限）。用 App Token 发送会因"无对应页面权限"被拒。

**判断口诀**：看资源属于"App"还是"Page"——缩略图/短链按 App 维度创建管理 → App Token；给某页面用户发消息/配页面门面 → Page Token。二者不可混用。
</details>

### 问题 4

**场景**：你的机器人功能正常，但真实用户通过 CTA 广告进来后，机器人回复被拒绝，错误码 `1200`。而你在开发者模式下自测却一切正常。请分析可能的原因，并给出广告引流场景下"24 小时消息窗口"的正确理解与规避方案。

<details><summary>答案</summary>

**1200 是"超出 24 小时消息窗口"**：即用户最后一条**主动（inbound）消息**已经超过 24 小时，你不能再自由回复。它与你自测时很快回复不同——真实用户可能点完广告很久才回来再次互动，或你的回复排队拖过了窗口。

**关键理解**：窗口计时起点是**用户最后一条 inbound 消息**，而不是广告点击时间。广告点击后才第一次建立会话的场景，其实窗口从用户点击/首条消息开始算；但若机器人的回复链路上有延迟、或用户隔天再回来补发，就容易命中 1200。开发模式下你自己在高频短时内测试不会触发，掩盖了问题。

**规避方案**：
1. 窗口内完成核心转化流程；
2. 窗口将尽时发"1 条附加消息"引导用户回复以重置窗口；
3. 需要窗口外主动触达 → 走 **Messaging Subscription（opt-in）**，让用户显式订阅，获得订阅消息能力；
4. 电商/订单/航班等用例 → 申请 **企业消息（Business Messaging）** 权限放宽窗口。
</details>

### 问题 5

**场景**：你希望用户在点击"人工客服"按钮后，会话从机器人交给 Page Inbox 的人工客服处理；人工结束后再交回机器人继续。请列出需要调用的 API 端点、关键参数，以及 Webhook 侧需要订阅并处理的接管事件，并说明"同一时刻只有谁拥有会话"。

<details><summary>答案</summary>

**交接用 Handover Protocol：**

1. **交给人工（Page Inbox）**：`POST /me/pass_thread_control`
   - 参数：`recipient.id`（PSID）、`target_app_id`（交给 Page Inbox 时固定为 `263902037430900`）、可选 `metadata`（如"用户要求人工客服"）。
2. **收回控制权**：`POST /me/take_thread_control`，参数 `recipient.id`。
3. **（可选）请求控制权**：`POST /me/request_thread_control`，用于从其它接收方要回控制权。

**Webhook 需订阅** `messaging_handovers`，处理两类事件：
- `pass_thread_control`：通知你已把控制权交给新 owner（`new_owner_app_id`）——此时**暂停**对该会话的自动回复。
- `take_thread_control`：你已收回控制权——**恢复**机器人接管。

**核心原则**：**同一时刻只有一个接收方（Primary）拥有该会话**。新消息默认到 Primary（机器人）；移交后由人工处理期间机器人不得自动回复，直到用 `take_thread_control` 收回。在 `WAITING_AGENT` 状态下，机器人对用户新消息应按"已在人工处理"策略处理，避免抢回会话造成重复。
</details>

---

> **结语**：Messenger 机器人开发的核心不在于"会不会调 API"，而在于 **归属与权限的正确认知（PSID/Token/审核）、可靠的事件处理（验签/幂等/异步）、以及人机协作与广告归因的闭环**。本文提供的 `meta_*` 系列封装与状态机足以支撑一个可上线的 Click-to-Messenger 转化机器人。建议结合 Marketing API 的 `messages` 目标与广告报表，把"广告 → 对话 → 线索 → 成交"跑成完整飞轮。
