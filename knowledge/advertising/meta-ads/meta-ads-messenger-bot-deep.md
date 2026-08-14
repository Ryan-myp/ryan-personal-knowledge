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
