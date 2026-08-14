# Meta Conversions API (CAPI) 生产级指南：事件匹配、去重与批量落地的深度实践

> **领域**: 广告投放 / Meta
> **深度**: ⭐⭐⭐⭐⭐ 实战级指南
> **标签**: meta-ads, capi, conversion-api, server-side, dedup, production
> **更新时间**: 2026-08-14
> **类型**: 生产级指南

---

## 一、核心概念与架构

### 1.1 为什么需要 CAPI：信号丢失时代的必然选择

自 iOS 14 / ATT（App Tracking Transparency）上线以来，浏览器端追踪的信号质量大幅衰减。Pixel 依赖浏览器执行 JavaScript，受到以下多重限制：

| 限制因素 | 影响范围 | 说明 |
|---------|---------|------|
| ATT 弹窗拒绝 | iOS 用户 | 拒绝追踪后浏览器几乎不暴露任何可匹配信息 |
| ITP（智能防追踪） | Safari | 7 天（后 24 小时）限制第三方 Cookie 存活期 |
| 广告拦截器 | 全平台 | 直接阻止 pixel.js / fbevents.js 加载 |
| ETP / 隐私沙盒 | Firefox / Chrome | 逐步淘汰第三方 Cookie |
| 网络断开 / 页面未完成加载 | 全平台 | 事件可能根本来不及发出 |
| 表单预填关闭 | 全平台 | 浏览器不自动填充用户信息，匹配率下降 |

**CAPI（Conversions API）** 的核心价值：把事件直接从你的服务器（server-side）发往 Meta，不依赖浏览器、不经过用户设备、不被广告拦截器拦截。它解决的问题本质上是**信号丢失（signal loss）**——当 Pixel 无法看到转化时，广告系统的归因、优化、学习全部失真。

> 关键认知：CAPI 不是"替代 Pixel"，而是与 Pixel **并行**的第二个信号通道。两者的关系是互补去重，而不是二选一。

### 1.2 CAPI 事件发送原理：Server-to-Server 数据流

CAPI 的事件从你的服务器发出，走 HTTPS POST 请求到 Meta 的 Graph API / Events API 端点，全程不经过用户的浏览器：

```
                          ┌─────────────────────────────────────────┐
                          │            你的业务后端                    │
                          │  ┌─────────────┐  ┌──────────────────┐  │
  用户下单 ───► 订单服务 ──►│  │ 事件整形/哈希  │  │ 队列 / 异步任务   │  │
                          │  └──────┬──────┘  └────────┬─────────┘  │
                          │         │                   │           │
                          └─────────┼───────────────────┼───────────┘
                                    │  HTTPS POST  (TLS 1.2+)
                                    ▼
                    ┌──────────────────────────────┐
                    │  graph.facebook.com          │
                    │  /v23.0/{pixel_id}/events    │
                    │  Events API (CAPI 端点)       │
                    └──────────────┬───────────────┘
                                   │
                                   ▼
                    ┌──────────────────────────────┐
                    │  Meta 事件处理管线              │
                    │  匹配(Matching) → 排序          │
                    │  去重(Deduplication Rules)     │
                    │  聚合 → 归因 → 优化            │
                    └──────────────────────────────┘
```

与浏览器端相对照：

```
【Meta Pixel（浏览器端）】
用户浏览器 ──(fbevents.js)──► graph.facebook.com

【CAPI（服务端）】
你的后端服务器 ──(HTTPS + access_token)──► graph.facebook.com
```

CAPI 请求的两个认证要素缺一不可：

| 要素 | 位置 | 说明 |
|------|------|------|
| `access_token` | URL query / Header | 由系统用户（System User）生成，需赋予对应 Pixel 的 `manage` 权限 |
| `pixel_id` | URL path | 像素 ID，即事件要发往的容器 |

### 1.3 CAPI 与 Pixel 的能力对照

| 维度 | Meta Pixel | CAPI |
|------|-----------|------|
| 数据来源 | 浏览器 JS | 服务端业务数据 |
| 受 ATT / ITP 影响 | 严重 | 无 |
| 受广告拦截器影响 | 严重 | 无 |
| 可携带深度业务字段 | 有限 | 任意（购物车、商品、金额、数量） |
| 匹配信息 | 浏览器上下文（fbp/fbc）+ 用户输入 | 后台数据库中的已登录用户信息 |
| iOS 14.5+ 可用性 | 受限（需 AEM 聚合） | 完全可用 |
| 与 CRM / 订单数据打通 | 难 | 天然可对接 |
| 事件发送时机 | 页面事件点 | 业务事件点（下单、发货、退款） |
| 延迟控制 | 实时 | 可批量、可实时 |
| 可恢复性 | 无（丢了就丢了） | 可重试 |

### 1.4 CAPI 事件流的完整链路

一个 CAPI 事件从产生到影响广告系统的生命周期：

```
① 业务事件发生（用户下单）
        │
        ▼
② 事件数据收集：用户信息(em/ph/fn/ln)+ 业务数据(currency/value) + 上下文(fbp/fbc/ip/ua)
        │
        ▼
③ 数据规范化 + 哈希(SHA-256) → 生成 event_id + event_time
        │
        ▼
④ HTTP POST → POST /{pixel_id}/events  （或批量 &batch）
        │
        ▼
⑤ Meta 应答：{ events_received: N, messages: [...] }
        │
        ▼
⑥ 匹配引擎：用 user_data 找 Meta 用户（匹配键命中）→ 打上 dedup key
        │
        ▼
⑦ 与 Pixel 事件按 (event_id, event_source_id) 比对去重
        │
        ▼
⑧ 归因 → 优化（出价 / 学习）→ 报表(Ads Manager)
```

这条链路中，**③④⑥⑦ 是生产团队最常出错**的环节，也是本文第二、第三大部分展开的主题。

### 1.5 事件类型：标准事件与自定义事件

Meta 预定义了 9+ 个标准事件（Standard Events），全部可以直接作为 `event_name` 使用：

| 事件名 | 业务含义 | 建议必带 custom_data |
|--------|---------|---------------------|
| `ViewContent` | 浏览内容/商品页 | content_ids, content_type, value, currency |
| `Search` | 搜索 | search_string |
| `AddToCart` | 加购 | content_ids, value, currency |
| `AddToWishlist` | 加入心愿单 | content_ids, value, currency |
| `InitiateCheckout` | 发起结账 | num_items, value, currency |
| `AddPaymentInfo` | 添加付款信息 | value, currency |
| `Purchase` | 完成购买 | value, currency, num_items, content_ids |
| `Lead` | 产生表单线索 | value, currency（可选） |
| `CompleteRegistration` | 完成注册 | status, value |
| `Contact` | 联系（线索广告） | — |
| `CustomizeProduct` | 定制商品（Advantage+ 目录广告） | — |
| `FindLocation` | 查找门店 | — |
| `Schedule` | 预约 | value, currency |
| `StartTrial` | 开始试用 | value, currency |
| `Subscribe` | 订阅 | value, currency, predicted_ltv |
| `Donate` | 捐赠 | value, currency |
| `ViewContent` | 浏览内容 | content_ids, contents |

自定义事件直接给任意字符串，如 `"PremiumUpsellOffer2"`，但注意：**只有标准事件 + 建立了自定义转化时，优化目标才能使用它**。生产建议：

1. 核心转化（Purchase/AddToCart/InitiateCheckout）用标准事件名；
2. 细化业务（如分渠道来源）放 `custom_data` 里，而不要发明新事件名；
3. 事件名区分大小写，官方文档约定使用 PascalCase。

### 1.6 核心组件与账号链路

发送 CAPI 事件需要的最小权限链路：

```
Business Manager (BM)
├── 系统用户 System User (非个人信息，防离职)
│   └── 角色: Pixel 管理员 (Pixel 级别 Advertiser or Admin)
│   └── access_token (长期有效，可轮换)
└── Pixel
    └── 事件容器（Event Container）
```

| 组件 | 获取方式 | 作用 |
|------|---------|------|
| `access_token` | BM → 系统用户 → 生成令牌 | 认证 |
| `pixel_id` | Events Manager → 像素 | 事件归属 |
| `test_event_code` | Events Manager → 测试事件 | 测试模式不落真实数据 |
| `event_source_id` | 同上像素 | 与 Pixel 去重的关键字段 |

> 生产环境**禁止**用员工个人账号 token。个人 token 离职即失效，且无法做细粒度审计。系统用户 token 才是生产标准。

### 1.7 事件数据最小集合与完整集合

| 字段 | 最小可用集合 | 推荐生产集合 |
|------|------------|-------------|
| `event_name` | ✔ 必须 | ✔ |
| `event_time` | ✔ 必须（Unix 秒） | ✔ |
| `user_data` | `client_ip_address` + `client_user_agent` | ✔ + 已登录 `em`/`ph` 等 |
| `custom_data` | 可选 | 订单金额、商品、货币 |
| `event_id` | 强烈建议 | ✔ 必（去重用） |
| `event_source_id | 与 Pixel 同时使用时必须 | ✔ |
| `event_source_url` | 建议 | ✔ |
| `action_source` | 建议 | ✔ |

**重要的生产认知**：即使没有任何可匹配的用户身份信息（email/phone），只要发送 `client_ip_address` + `client_user_agent` + `fbp`/`fbc`，Meta 也会尽力做**浏览器指纹级匹配**（browser fingerprint），这是 CAPI 匹配链的兜底层级。

### 1.8 单事件与批量端点概览

CAPI 既支持单事件，也支持批量：

```
单事件:  POST /{pixel_id}/events
                   {"data": [ <1个事件> ]}

批量:    POST /{pixel_id}/events?data_processing_options=[]
                   {"data": [ <最多1000个事件> ]}
```

| 通道 | 上限 | 用途 | 延迟 |
|------|------|------|------|
| 单事件 | 1 个/请求 | 实时事件（下单瞬间即发） | 秒级 |
| Batch | 1000 个/请求（推荐 500 以下） | 回填、批量补发 | 分钟级 |

---

### 1.10 认证与权限体系详解

```ascii
Business Manager（BM）
│
├── 系统用户（System User）             ← 推荐生产主体
│     ├── 角色：Pixel 管理员/分析员
│     ├── 生成 access_token（长期）
│     └── 90 天轮换（可选做循环令牌）
│
├── 员工个人账号（即用户身份）           ← 不推荐用于生产
│     └── 离职即失效、难审计
│
└── Pixel（事件容器）
      └── event_source_id（= pixel_id）
```

**在 BM 里创建并授权系统用户获取 token 的命令思路**（Graph API）：

```
# 1) 在 BM 下创建系统用户
POST /{business_id}/system_users
   ?name=capi-prod-bot
   &role=ADMIN             # 建议最小权限职员：EMPLOYEE 即可
   &access_token={admin_token}

# 2) 为系统用户生成长期令牌（自行签 JWT 或调用 create_access_token 扩展）
POST /{system_user_id}/issued_access_tokens  （或 social 权限扩展）

# 3) 给像素授权
POST /{pixel_id}/shared_accounts?account_type=SYSTEM_USER&business={bm_id}
```

**权限清单（最小可用）**：

| 权限 | 用途 |
|------|------|
| `pixel_selected_assets` | 读/写指定像素 |
| （BM 级别）`advertiser` | 广告主角色，编辑像素事件 |
| （像素级别）`manage` | 发送事件、读取口径 |

**token 的放置与轮换**：

```python
# 生产禁止硬编码：从 Secrets Manager / Vault 读取，支持自动轮换
import os, boto3
def _get_token() -> str:
    if os.getenv("META_CAPI_TOKEN"):
        return os.environ["META_CAPI_TOKEN"]
    # KMS/SSM 取当前版本；可在此基础上做 2-token 轮换窗口
    return ssm.get_parameter(Name="/meta/capi/token",
                             WithDecryption=True)["Parameter"]["Value"]
```

### 1.11 请求/响应格式逐字段详解

**请求（POST /{pixel_id}/events）**：

| 顶层字段 | 类型 | 必填 | 说明 |
|---------|------|------|------|
| `data` | array | ✔ | 事件数组（单事件也可放数组） |
| `access_token` | string | ✔ | 认证 |
| `test_event_code` | string | 可选 | 测试管道 |
| `data_processing_options` | array | 批量时必 | `[]` 或 `["LDU"]` |
| `data_processing_options_country` | int | 配合 LDU | 1=US |
| `data_processing_options_state` | int | 配合 LDU | 1000=CA |

`data[0]`（单个事件）内字段：

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `event_name` | string | ✔ | 标准/自定义事件名 |
| `event_time` | string(unixtime) | ✔ | Unix 秒 |
| `event_id` | string | 建议 | 幂等/去重键 |
| `user_data` | object | ✔ | 含匹配键 |
| `custom_data` | object | 建议 | 业务参数 |
| `action_source` | enum | 建议 | 见 2.15 |
| `event_source_url` | string | 建议 | 含 query 的完整 URL |
| `event_source_id` | string | 与 Pixel 同用 | = pixel_id |

**响应（成功）**：

```json
{
  "events_received": 2,
  "messages": [],
  "fbtrace_id": "DeW0t2a..."
}
```

- `events_received` 指被接收的事件数；`messages` 里往往是警告（如某事件 user_data 缺失会 drop 时给 message）。

**响应（出错）**：HTTP 4xx 时 body：

```json
{
  "error": {
    "message": "Invalid parameter",
    "type": "OAuthException",
    "code": 100,
    "error_subcode": 1810001,
    "fbtrace_id": "Ah3f..."
  }
}
```

### 1.12 CAPI 数据流中的脱敏与合规总览

```
用户数据（Email/Phone）──► 你服务器 ──► SHA-256+base64 ──► Meta
                                   │
                                   ▼
                         关键原则（数据最小化）：
                         - 只传给优化所需的键
                         - 敏感字段（身份证/银行卡/社保）绝不发送
                         - 可区分处理的用户走 LDU
                         - 明文只在内部短暂保留（对账）
```

合规清单（生产上线 checklist）：

| # | 事项 |
|---|------|
| 1 | 删除权：用户请求删除时，同步删明文 + 停发该用户事件 |
| 2 | 听取权（CCPA opt-out）：返回 LDU 而非直接不匹配 |
| 3 | 传输：HTTPS（TLS 1.2+）、token 仅存 Secrets |
| 4 | 用途：CAPI 事件仅用于广告优化/归因，不得用于其他用途 |
| 5 | 文件：记录 数据流图 + 保留期限（7 天窗口内可删） |

---

## 二、深度原理解析

### 2.1 事件匹配（Event Matching）与匹配质量评分（EMQ）

事件匹配把服务器端收到的 `user_data` 与 Meta 上的真实用户档案匹配。匹配质量直接决定：

- **归因准确性**：匹配得上才能关联到广告点击；
- **优化效率**：`Event Match Quality`（EMQ）作为模型信号，低质量会被降权；
- **转化建模**：未匹配事件只能进"无匹配"桶，只能用于建模无法归因。

```
                    user_data 输入
        ┌──────────────┬──────────────┬──────────────┐
        ▼              ▼              ▼              ▼
     email(em)     phone(ph)     name(fn+ln)     ext_id(external_id)
        │              │              │              │
        └──────────────┴──────┬───────┴──────────────┘
                              ▼
                   SHA-256 标准化哈希后逐键尝试匹配
                              │
                ┌─────────────┴─────────────┐
                ▼                           ▼
         命中 ≥1 个键（single match）        全部未命中
                │                           │
                ▼                           ▼
        确定到唯一用户 → 高质量事件        降级到 IP/UA 指纹匹配
                                                    │
                                          (更低质量，不建议作为主信号)
```

**EMQ 评分的官方口径**（Events Manager → 数据源 → 事件 → 质量）：

| 分数区间 | 含义 | 典型原因 |
|---------|------|---------|
| 8.0+ | 优秀 | 大量精确匹配（em/ph/external_id 命中） |
| 5.0 - 7.9 | 良好 | 部分匹配，混合了这个网页浏览 |
| 3.0 - 4.9 | 一般 | 主要靠 IP/UA 兜底，或哈希方式不一致 |
| < 3.0 | 差 | 几乎无匹配键、重复发送或测试数据污染 |

**生产铁律**：EMQ 是一个**信号质量指标**，不是"数字越高越好的游戏"。很多团队为了刷 EMQ 会把浏览事件也带上完整邮件，这会稀释 `Purchase` 类事件的精度。正确姿势是分级发送（见 3.17 数据分层）。

### 2.2 匹配键全解：`fn`, `ln`, `em`, `ph` 等

`user_data`（注意：不是 `custom_data`）内支持的匹配键（Matching Keys）：

| 键 | 中文 | 规范化规则（发送前必须做！） | 哈希要求 |
|----|------|------------------------------|---------|
| `em` | 邮箱 | 全小写、去首尾空格（`strip().lower()`） | 必须 SHA-256 |
| `ph` | 手机号 | 只留数字、去掉 `+`/`-`/空格/括号，统一 E.164 格式（+86… 去 + 号） | 必须 SHA-256 |
| `fn` | 名字 | 首字母大写其余小写（去除重音/特殊符号） | 必须 SHA-256 |
| `ln` | 姓氏 | 同上 | 必须 SHA-256 |
| `ge` | 性别 | 小写：`m` / `f` | 必须 SHA-256 |
| `db` | 出生日期 | `YYYYMMDD`，去符号 | 必须 SHA-256 |
| `ct` | 城市 | 小写、去空格/标点 | 必须 SHA-256 |
| `st` | 州/省 | ISO 3166-2（如 `CA`） | 必须 SHA-256 |
| `zp` | 邮编 | 去空格、去破折号、小写 | 必须 SHA-256 |
| `country` | 国家 | 两位 ISO 3166-1 alpha-2（如 `US`） | 必须 SHA-256 |
| `external_id` | 第一方 ID | 业务系统用户 ID / CRM ID | 必须 SHA-256 |
| `client_ip_address` | 客户端 IP | 无需哈希 | 不哈希 |
| `client_user_agent` | 浏览器 UA | 无需哈希 | 不哈希 |
| `fbc` | Facebook 浏览器 Cookie | 从浏览器获取，无需哈希 | 不哈希 |
| `fbp` | Facebook 浏览器 Pixel | 从浏览器获取，无需哈希 | 不哈希 |

路由：`em`/`ph`/`fn`/`ln`/`ge`/`db`/`ct`/`st`/`zp`/`country`/`external_id` 称之为 **哈希字段（hashed fields）**；`client_ip_address`/`client_user_agent`/`fbc`/`fbp` 称 **明文字段（plaintext fields）**。

### 2.3 哈希规则（Hash Spec）——最常被踩坑的地方

Meta 规定：**除了 client_ip_address、client_user_agent、fbc、fbp 之外的所有键，都必须先规范化再 SHA-256 哈希，且 base64 编码**。

**规范化是比哈希更致命的环节**。同一个用户的邮箱，你哈希前没小写，Meta 那边档案存的是小写，两个 hash 完全不同——直接匹配不上。规范化控制器：

```python
import hashlib
import re

def _sha256_b64(value: str) -> str:
    """统一哈希：SHA-256 → 二进制 → base64（不可只 hex）"""
    raw = hashlib.sha256(value.encode("utf-8")).digest()
    return base64.b64encode(raw).decode("utf-8")  # Meta 要求 base64，不是 hex

def normalize_email(raw: str) -> str:
    """邮箱规范化：去首尾空白 + 小写"""
    return str(raw or "").strip().lower()

def normalize_phone(raw: str) -> str:
    """手机号规范化：只留数字，去掉+、空格、破折号、括号；统一 E.164（含国家码）"""
    s = re.sub(r"[^0-9]", "", str(raw or ""))
    # 美国就业：10 位补齐 +1；北京、上海 11 位保留；其他国家按 E.164 处理
    if len(s) == 10:          # 美国本地号码
        s = "1" + s
    elif len(s) == 11 and s.startswith("0"):
        s = s[1:]             # 去掉国内长途前导 0
    return s

def normalize_name(raw: str) -> str:
    """姓名规范化：首字母大写其余小写、去重音符号与叹号"""
    return re.sub(r"[^a-zA-Z]", "", str(raw or "").strip().lower()).title()

def normalize_city(raw: str) -> str:
    """城市规范化：小写、去空格与标点"""
    return re.sub(r"[^a-z]", "", str(raw or "").lower())

def normalize_country(raw: str) -> str:
    """国家规范化：ISO 3166-1 alpha-2 大写"""
    return str(raw or "").strip().upper()
```

**铁律（全 Meta 团队生产共识）**：

1. email → 小写 → hash；phone → strip 非数字 → 去前导 0/加 1 → hash；
2. fn/ln → 首字母大写其余小写 → hash；
3. **永远不要 hash 空串**，空值直接从字典删除；
4. `external_id` 必须是同一用户在你的第一方系统中稳定的 ID（如用户 ID），hash 后发送；
5. 强烈建议：**先内部明文存一份（未 hash），仅对外（发 Facebook）时才 hash**。原因：后续要做 CRM 对账、重复账号合并、二次营销都必须拿到明文才能再规范化；一旦只存 hash，规范化的错误就永远无法修正了。

### 2.4 Advanced Matching（高级匹配）

**Meta Pixel** 的"高级匹配"（Automatic Advanced Matching / Manual Advanced Matching）是浏览器侧特性：把可识别的用户信息（登录态）附加到 Pixel 事件中，再在前端完成哈希发给 Meta。

而 **CAPI 的 Advanced Matching 概念**指的是：

- 在 `user_data` 里提供比浏览器侧更丰富的键（`external_id`、`country`、`zp` 等）；
- 服务端拿到的是**数据库里的权威数据**，不是浏览器推断值；
- 每个键必须是 **UTF-8 字符串数组**，如 `"em": [hash1, hash2]`（一个用户可能多个邮箱）。

CAPI 高级匹配的收益对比：

| 匹配方式 | 能否写 server-side | 能提供 external_id | 数据质量 | 典型效果 |
|---------|------|----|------|------|
| 仅 Standard（无 AM） | ✖ | ✖ | 只靠 Pixel | 归因下降 20-40%（iOS14+） |
| 标准 Pixel + AM（advanced） | ✔ | 部分 | 中 | 有所提升 |
| Pixel + CAPI 双道 | ✔ | ✔ | 高 | 最稳 |
| Pixel + CAPI + AM 后端 | ✔ | ✔ | 最高 | 归因模型最准确 |

### 2.5 事件去重原理（Deduplication）

Pixel 和 CAPI 双通道发送同一事件时，**Meta 会收到两份**。如果不做去重，推论：

```
模拟：1 次下单被报了 2 次（Pixel 1 次 + CAPI 1 次）

后果：报告里 Purchase 变为 2
      → 学习阶段 ROAS 虚高
      → 优化器把预算烧在没有增量的量上
      → 出价失真（bidder 认为转化多，压低 CPA 竞价空间）
```

**去重机制**：Meta 用 `(event_id + event_source_id)` 作为 **dedup key**：

- `event_source_id` = Pixel ID（两个通道事件发往同一个 pixel_id 即自然相同）；
- `event_id` = 业务侧自定义的全局唯一 ID（例如订单号、UUID）。

两条通道必须使用**相同的 event_id** 才能命中去重。判定规则：

```
事件到达 Meta 事件管线
        │
        ▼
  能提取到 event_id 吗？
        ├── 否 ──► 进入无 dedup 模式：
        │              │
        │              ├── Pixel 与 CAPI 的 user_data 相同
        │              │     且事件信息高度一致（event_name+event_time 差值 < 2min、无冲突字段）
        │              │     → 判定为重复 → 保留质量更高的那个
        │              │
        │              └── 否则 → 两条都保留（重复）
        │
        ▼
  能（同一 pixel，同一 event_id）
        │
        ▼
  Pixel 与 CAPI 谁先到？
        ├── 先到的保留，后到的丢弃（保留**先到**的）
        └── 同时到 → 保留 CAPI（server 数据更全）
```

**生产血泪经验**：去重的正确姿势是**你自己先去重，再让 Meta 去重**。

1. 后端生成 `event_id = f"{order_id}:{event_name}"`（同订单多次事件不同名，各自 id）；
2. CAPI 与前端 Pixel 用**同一个 generator** 生成 `event_id`（如把 `event_id` 通过 dataLayer / 模板变量传给 fbevents.js）；
3. 客户端（浏览器）在发 Pixel 时把 `event_id` 塞进 event；
4. 服务端在发 CAPI 时用同一 `event_id`。

详见 3.5 节完整代码。

### 2.6 事件时间戳与服务器时钟漂移

`event_time` 必须为 **Unix 时间戳（秒）**。事件延迟超过 7 天 Meta 会拒绝（`event_time` 相对当前时间 > 7 天报错）。

常见时间戳坑：

| 坑 | 现象 | 修复 |
|----|------|------|
| 用毫秒当秒 | 事件时间变为 1970 年，被当作过期 | `int(time.time())` |
| 时区转换错 | 事件归到前一天/后一天，日报分错 | 一律 UTC，`datetime.now(timezone.utc)` |
| 服务器时钟漂移 | 事件时间戳与真实时间差出几小时/几天 | 上 NTP / chrony，监控 offset |
| 重试后时间戳不变 | 补发用原始 event_time | CAPI 支持带**原时间戳**补发（≤48h），这正是幂等补发的意义 |

**服务器时钟（clock skew）是生产事故高发区**：如果 Web 容器时钟比真实时间慢 10 分钟，且事件处理在 30 分钟后，`event_time + 处理延迟` 与 `now` 的差值会破坏归因窗口的边界判断。生产中要：

1. 所有节点配置 `chronyd/ntpd`，并在部署清单里校验；
2. 事件入库时间用 `NOW()`,事件发生时间单独存 `event_ts`；
3. CAPI 发送的 `event_time` 用 **业务事件发生时间**，而非发送时间。

### 2.7 事件参数详解：`custom_data` 与 `user_data` 的边界

**不要在 user_data 里塞业务参数，也不要在 custom_data 里塞用户身份**。混淆两者的结果就是数据被丢弃或毛利率计算错乱。

| 参数 | 核心用途 | 常见键 |
|------|---------|--------|
| `user_data` | 匹配用（identity） | em, ph, fn, ln, external_id, fbc, fbp, client_ip_address, client_user_agent |
| `custom_data` | 事件本身的可量化属性 | currency, value, content_ids, contents, num_items, search_string, status, order_id, predicted_ltv |
| `event_source_url` | 归因用（原始 URL） | 完整 URL（含 query），不能只回域名 |
| `action_source` | 事件来源渠道 | `website` / `email` / `app` / `phone_call` / `chat` / `physical_store` / `system_generated` / `business_messaging` / `other` |
| `event_id` | 去重键 | 同源全局唯一 |
| `event_source_id` | 去重键的 Pixel 维度 | pixel_id |

**value/currency 规范**：

- `currency` 必须是 ISO 4217 3 字母，`USD` / `EUR` / `SGD`，不要写 `$`；
- `value` 是浮点数，`美刀`归一：
  - 金额统一转换到**整数倍的分/厘**再除 100（避免浮点误差）；
  - 多货币站点需在发送层做汇率换算成**店铺货币**（Meta 报表按店铺货币）。

示例完整事件（来自生产代码思路）：

```json
{
  "event_name": "Purchase",
  "event_time": 1784031600,
  "event_id": "order-88231-purchase",
  "event_source_url": "https://shop.example.com/checkout/success?orderid=88231",
  "action_source": "website",
  "user_data": {
    "em": ["WzIwMTUyMDA5Mj...=="],
    "ph": ["MTg4ODg4ODg4ODg="],
    "external_id": ["M2M5YjZlNjIxM..."],
    "client_ip_address": "192.168.1.88",
    "client_user_agent": "Mozilla/5.0 (Macintosh...)",
    "fbp": "fb.1.1784031600.1234567890",
    "fbc": "fb.1.1784031500.AbCdEfGhIjKlMnOpQrStUvWx"
  },
  "custom_data": {
    "currency": "USD",
    "value": 129.99,
    "num_items": 2,
    "contents": [
      {"id": "SKU-77", "quantity": 1, "item_price": 45.99},
      {"id": "SKU-99", "quantity": 1, "item_price": 44.00}
    ],
    "status": "paid",
    "order_id": "88231"
  }
}
```

### 2.8 噪声（noise）：Meta 在信号里故意加入的毛刺

Meta 在部分场景会给 CAPI 事件加入**随机扰动（noise）**，特别是：

- 使用 `action_source=website` 且未声明 `event_source_id`；
- 事件在**测试**模式下（test_event_code）；
- 某些 AEM（Aggregated Event Measurement）场景。

噪声的作用：

1. 保护用户隐私（防止通过精确事件逆推个体）；
2. **平滑广告主对数据的过度解读**（今天的上报 = 今天真实 + 少量随机扰动）。

**吐槽点（行业共识）**：广告主报表里看到的转化数其实已含噪声，因此：

| 噪声来源 | 影响 | 应对 |
|---------|------|------|
| AEM 聚合 | 归因方式受限于 8 大事件 | 合理配置事件优先级 |
| 测试流量污染 | 测试期内事件报表失真 | 用 test_event_code 与生产隔离 |
| 采样 | iOS 流量按比例采样 | 接受，不可控 |
| 阈值 | 极小量事件走聚合 | 保证单事件总量规模 |

### 2.9 幂等性：事件最大重试语义

CAPI 是 **at-least-once（至少一次）** 语义：网络超时、重试、队列重放都可能导致**同一事件送达多次**。Meta 不会隐式去重所有事件（只有 `event_id` 存在 + 同源才去重）。因此：

**幂等键设计**：

- `event_id` 必须是稳定的（可重复）唯一值；
- 对**同一业务事件**的每次重试，必须复用同一个 `event_id`，**不能每次生成新 UUID**；
- 幂等键建议组成：`<业务域>:<实体ID>:<事件类型>`，如 `cart:user_001:AddToCart:2026-08-14T10:00:00Z`。

伪代码 / Python 完整示例见 3.8。这一设计直接决定重试安全不可靠，也决定"补发昨天数据"不会造成双计。

### 2.10 `data_processing_options`：加州/科罗拉多隐私处理开关

`data_processing_options` 是专门为 CCPA（加州消费者隐私法）/ CDPA（弗吉尼亚）/ Colorado 设计的字段：

```json
{
  "data_processing_options": ["LDU"],
  "data_processing_options_country": 1,
  "data_processing_options_state": 1000
}
```

| 参数 | 取值 | 含义 |
|------|------|------|
| `data_processing_options` | `[]`（空数组，默认） | 不做受限数据处理 |
| 同上 | `["LDU"]` | Limited Data Use：开启"受限数据使用"（Meta 会缩减 user_data 的使用） |
| `data_processing_options_country` | `1`=美国, `0`=其他 | CCPA 国家 |
| `data_processing_options_state` | `1000`=CA（加利福尼亚） | CCPA 州代码 |

**生产注意**：

1. 仅在**用户真实行使 CCPA 拒绝权**（opt-out）时才返回 `LDU`，不要默认全量开启——否则所有事件的匹配质量与效果都会下降；
2. 该参数必须**逐事件**判断（有的用户还没 opt-out）；
3. 开启 LDU 的事件在 Meta 端匹配会降级，且无法取消（**不可逆**）。

### 2.11 批量处理（Batch Endpoint）原理

批量端点 `POST /{pixel_id}/events?data_processing_options=[]` 就是普通端点加一个**空数组**参数——官方规定："Batch 时必须在 URL 里带 `data_processing_options=` （哪怕为空）"。

```
PUT/POST /{pixel_id}/events?data_processing_options=[]
Content-Type: application/json

{
  "data": [
    { "event_name": "Purchase", ... },       # 事件1
    { "event_name": "AddToCart", ... },      # 事件2
    ...                                     # 最多 1000 个
  ]
}
```

| 批量限制 | 值 |
|---------|-----|
| 单请求最大事件数 | 1000 |
| 官方建议值 | 每个事件**不要 > 500** |
| 请求体上限 | ~8 MB |
| 响应 | 每事件 status（`accepted` / `dropped`） |

**批量与去重的微妙关系**：批量不会降低去重能力（只要 event_id 正确）；批量只影响**吞吐与失败原子性**——1000 个事件里 1 个失败，其 999 个照常受理（部分成功）。所以批量回填时必须逐个检查 `response["events"][i]["status"]`。

### 2.12 数据最小化与隐私配置总览

| 隐私维度 | 操作 | 落地要点 |
|---------|------|---------|
| 敏感数据（Sensitive Data） | `user_data` 中禁止内置身份证号、社保、银行卡、精确地理坐标等 | CAPI 本身不接收；必须在源头剥离 |
| LDU (data_processing_options) | 处理 opt-out | 见 2.10 |
| 匹配降级 | 不发送 `em/ph`，仅 IP/UA | 用**测试事件**验证降级效果 |
| 存储 | 服务器端不下传原始 IP/UA | 仅传 hash 后的键，明文只在需对账时短暂保留 |
| GDPR/个人信息 | 提供用户删除权 | 删除时同步删除明文 + 让 CAPI 停发 |

敏感数据处理示例（服务端剥离）：

```python
BANNED_SENSITIVE_FIELDS = {
    "id_card", "credit_card", "iban", "latitude", "longitude",
    "passport", "national_id", "license_plate", "health_status",
}

def sanitize_user_data(raw: dict) -> dict:
    """事件发往 Meta 前剥离敏感字段（数据最小化）"""
    return {k: v for k, v in raw.items()
            if k not in BANNED_SENSITIVE_FIELDS
            and not isinstance(v, (dict, list))}
```

---

### 2.13 去重决策树：Meta 到底怎么判定"重复"（ASCII 全图）

```
事件进入 Meta 管线
       │
       ▼
 事件来自哪个源？
 ├── CAPI（Server） ──► 源=API
 └── Pixel（Browser）─► 源=Browser
       │
       ▼
  能解析出 event_id 吗？
 ├── 否 ──────────────────────────────┐
 │                                   ▼
 │                    ┌→ 特殊去重（仅供参考，不可靠）：
 │                    │   比较另一通道事件的 (event_name, event_time)
 │                    │   + user_data 高度相似（同 em/ph/hash） 
 │                    │   + |Δt| ≤ 60s
 │                    │   → 视为重复：保留"高置信"（CAPI 优先）
 │                    ▼
 └── 是 ──► 有 event_source_id、event_id
            │
            ▼
 两条事件能否归到同一 (event_id, source)？
 ├── CAPI event_id = 前端 eventID？───── 否 → 不去重 → 双计 ⚠️
 │
 └── 是
     │
     ▼
  到达时序（arrival time）比较
 ├── CAPI 与 Pixel 谁先 received？
 │    ├── 先到者 → 保留
 │    └── 同时（或 CAPI 明显更全）→ 保留 CAPI
 │
 └── 确定级别：dedup 成功
```

**生产中"去重不生效"的两大必然原因**（我们在第一节 4.1 再展开）：

1. 前端 `fbevents.js` 的 `eventID` 没传（或传了但格式与后端不同）；
2. CAPI 重试时 `event_id` 每次都变（幂等键断裂）。

| 你的配置 | 去重结果 |
|----------|---------|
| 只有 Pixel | 单通道，无重复问题，但信号丢失 |
| Pixel + CAPI，均带一致 event_id | ✔ 去重成功 |
| Pixel + CAPI，CAPI 无 event_id | ⚠️ 特殊去重（不可靠，可能双计） |
| Pixel + CAPI，event_id 不一致 | ✘ 双计 |
| 双 CAPI（两套服务）同 pixel | 必须各自 event_id 全局唯一，否则主观双计 |

### 2.14 时序与归因窗口：`event_time` 到底怎么影响归因

Meta 归因（attribution）依赖事件时间落在广告曝光/点击窗口内。CAPI 事件的 `event_time` 决定它在归因里"落位"：

```
广告点击 (t0)                    --- 7 天归因窗口 ---► 转化
   │                                            │
   │  <── 点击后 1 天归因 ──►                    │
   │   ┌───────────────────┐                    │
   ▼   ▼                   ▼                    ▼
  事件落在窗口内 → 归因给这个广告、优化生效
  事件落在窗口外 → 归因不到（只能进"未归因"）
```

| 归因窗口 | 覆盖 | event_time 与 now 的容忍 |
|---------|------|------------------------|
| 实时归因 | 秒级 | 建议 < 5 min（batch 保存事件很大风险） |
| 7 天点击 / 1 天浏览 | 点击 | `now - event_time` 必须 < 7 天，否则拒绝 |
| 28 天 | 某些 | 超窗直接 error code 2326 |

**生产要点**：

1. 大促补发用原始 `event_time`——放到真实发生的时间点上，`Event Manager` 才展示正确归因；
2. 使用 `H TTL` 时处理"延迟事件"：如果消费者处理滞后，事件会晚于业务发生 30 分钟，但这不影响归因（归因用 event_time）；
3. **禁止**把 `now()` 当作所有事件的 `event_time`（那是#1 的时间戳篡改事故）。

### 2.15 `action_source` 与 `event_source_url` 的语义边界

| action_source | 含义 | 典型配合 |
|---------------|------|---------|
| `website` | 网站上的转化（最常见） | event_source_url + fbp/fbc |
| `email` | 邮件营销转化 | 用户点邮件链接 |
| `app` | App 内转化 | 需 App 事件（AppEvents） |
| `phone_call` | 电话转化 | 配合来电追踪 |
| `physical_store` | 门店到店转化 | 配合 Offline Event Sets 或 POS |
| `system_generated` | 系统（后台）生成 — 无页面来源 | 发货、退货 |
| `business_messaging` | WhatsApp/Messenger | 配合 Message 转化 |
| `other` | 其他 | 兜底 |

`event_source_url` 建议保留**完整 query string**：

- 归因引擎用 `fbc`（fbclid）追踪广告点击来源；
- 前端 `fbevents.js` 会自动带 `event_source_url`；CAPI 后端如果拿到登录会话里的 URL 就原样传；
- 不要把 URL 里 PII（如 `email=` 明文）留在 `event_source_url`，会造成数据分享隐私问题。

### 2.16 浏览器 Cookie 参数 `fbc` / `fbp` 的建模含义

| 参数 | 全称 | 作用 | 获取 |
|------|------|------|------|
| `fbp` | Facebook Pixel cookie | 标识**该浏览器第一次访问**你的站 | 前端读 `_fbp` |
| `fbc` | Facebook Click cookie | 标识**广告点击来源**（含 fbclid） | 前端读 `_fbc` 或 URL 的 `fbclid` |

- `fbc` 格式：`fb.1.<时间戳>.<base64码>`，内含 `fbclid`；
- **哈希规则**：`fbc`/`fbp` 是明文直接传，不要 hash（它们本身就是追踪标识）。

**生产落地**：CAPI 后端若拿不到 fbc（用户从 Google 进来，无 fbclid），就只传 fbp；`fbp` 能帮 Meta 找回浏览器早期浏览上下文，它是"低成本匹配"的重要来源。缺 fbc 会降低"点击-转化"的因果归因能力。

### 2.17 幂等表（去重表）设计：让"至少一次"变成"最多一次"

为了对抗 CAPI 的 at-least-once 语义，你**自己**也要维护一张去重表：

```python
# 本地事件幂等表（生产用 Redis SETNX 或 DB 唯一约束）
import redis

def record_and_check(event_id: str, pixel_id: str) -> bool:
    """
    返回 True=允许发送（首次）；False=已发过（跳过）。
    幂等键 = (event_id, pixel_id) 联合唯一。
    """
    key = f"capi:dedup:{pixel_id}:{event_id}"
    return r.set(key, "1", nx=True, ex=7 * 24 * 3600)  # 7 天过期对齐归因窗
```

生产上线前必须思考：

- **用 DB 唯一约束**（`UNIQUE(event_id, pixel_id)`）兜底，Redis 仅作快速路径，因为 Redis 丢数据时 DB 还能拦；
- 补发（backfill）场景：老订单的 event_id 已在去年；补发时这两个事件应**允许**（URL 历史）但要幂等——补发端自己要去重（同一订单同一事件只放一次进队列）。

### 2.18 常见信号质量陷阱总结（Ryan 项目实测）

| # | 陷阱 | 触发场景 | 规避 |
|---|------|---------|------|
| 1 | 把事件时间设成现在 | 回填 | 用原始 event_time |
| 2 | 事件名大小写不一致 | CM 与后端双写 | 统一 PascalCase 映射表 |
| 3 | `em` 用原始串未 hash | 测试态查询量小 | 验证 hash=base64(SHA256) |
| 4 | 空字符串 hash | 用户无手机却传 `ph:[""]` | 空值剔除 |
| 5 | 微信/注册用户没 external_id | 登录用户 | 传 `external_id=user_id` |
| 6 | 多 pixel 混杂 | 多币种多店铺 | 每店独立 pixel，event_source_id 对齐 |
| 7 | 测试流量真库混用 | 联调 | 单独影子 pixel / test_event_code |
| 8 | 收款与实时只做 CAPI | 只做实时 | 回填 + 每日闭环对账 |

---

## 三、生产环境实战

### 3.0 前置条件清单

| # | 项 | 状态检查方式 |
|---|----|-------------|
| 1 | BM 系统用户 + 长期 token | `meta_auth` / 手动生成 |
| 2 | Pixel ID | 已开户 |
| 3 | Python 环境 + `requests` | `pip install requests` |
| 4 | 服务器到 graph.facebook.com 网络可通 | `curl -I https://graph.facebook.com/` |
| 5 | 测试事件码 `test_event_code` | Events Manager → 测试事件 |
| 6 | 时钟同步（NTP） | `timedatectl` / `chronyc` |

### 3.1 环境初始化与统一入口

```python
# scripts/ad_platform_api.py → api_common.py 的初始 token 与公共常量
import time, hashlib, base64, json, re, uuid
from typing import Dict, List, Optional, Any

import requests

GRAPH_URL = "https://graph.facebook.com"
API_VERSION = "v23.0"   # 按需换更高版本；v19 已过 reactor
EVENTS_BATCH_LIMIT = 500   # 推荐批量上限
REQUEST_TIMEOUT_S = 30
MAX_RETRIES = 3
RETRY_BACKOFF_BASE_S = 1.5
IDEMPOTENCY_KEY_PREFIX = "capi"

# 系统用户 token（密钥管理里存，别硬编码！生产建议 SSM/KeyVault 轮换）
ACCESS_TOKEN = os.getenv("META_CAPI_TOKEN", "")
```

> 说明：本文代码里的函数摘录自 `scripts/ad_platform_api.py` / `scripts/meta_api.py` 中对应的 CAPI/pixel 方法族：`meta_track_pixel`、`meta_send_capi`、`meta_send_capi_batch`、`meta_list_capi_events`、`meta_list_matched_fields`、`meta_validate_event_data`、`meta_get_event_quality`、`meta_list_event_source_types`、`meta_get_conversion_api_config`、`meta_update_conversion_api_config`、`meta_list_pixel_events`、`meta_create_pixel_event` 等，并做了**生产级完整展开**（含哈希、签名、重试、幂等、去重）。

### 3.2 事件数据规范层（Normalize + Hash + Build）

```python
def _b64_sha256(text: str) -> str:
    """SHA-256 后 base64（Meta 要求 base64 而非 hex）"""
    return base64.b64encode(hashlib.sha256(text.encode("utf-8")).digest()).decode()

def _normalize_email(v: str) -> str:
    return (v or "").strip().lower()

def _normalize_phone(v: str) -> str:
    digits = re.sub(r"\D", "", v or "")
    if len(digits) == 11 and digits.startswith("0"):
        digits = digits[1:]          # 去掉国家前缀 0（如美国 10 位补 1）
    if len(digits) == 10:
        digits = "1" + digits         # 美国本地号补 +1
    return digits

def _normalize_name(v: str) -> str:
    # 去重音符号、小写、去空格
    return re.sub(r"[^a-zA-Z]", "", (v or "").lower())

def _normalize_city(v: str) -> str:
    return re.sub(r"[^a-z]", "", (v or "").lower())

def _normalize_zip(v: str) -> str:
    return (v or "").strip().replace(" ", "").replace("-", "").lower()

def _hash_if(payload: Dict[str, Any], keys: tuple) -> Dict[str, Any]:
    """对 keys 中的字段做规范化 + SHA-256；空值直接抹除"""
    out = {}
    for k in keys:
        val = payload.get(k)
        if val is None or (isinstance(val, str) and not val.strip()):
            continue
        norm = {
            "em": _normalize_email, "ph": _normalize_phone,
            "fn": _normalize_name, "ln": _normalize_name,
            "ge": lambda x: (x or "").strip().lower(),
            "db": lambda x: re.sub(r"\D", "", x or ""),
            "ct": _normalize_city, "st": _normalize_name,
            "zp": _normalize_zip,
            "country": lambda x: (x or "").strip().upper(),
            "external_id": lambda x: (x or "").strip(),
        }[k]
        out[k] = [_camel_sha256(norm(val))]   # hash 后必须是数组
    return out

def build_capi_user_data(user: Dict[str, Any]) -> Dict[str, Any]:
    """
    组装 user_data：
      - 可哈希字段（em/ph/...）→ 规范化 + SHA-256（每项数组）
      - 明文字段（ip/ua/fbp/fbc）原样传
    """
    hashed = _hash(user, ("em", "ph", "fn", "ln", "ge", "db",
                          "ct", "st", "zp", "country", "external_id"))
    plain = {}
    for k in ("client_ip_address", "client_user_agent", "fbp", "fbc"):
        if user.get(k):
            plain[k] = user[k]
    return {**hashed, **plain}
```

### 3.3 数据分层：浏览 vs 转化，别把高价值信号稀释

```
┌────────────────────────────────────────────────────────┐
│  事件分层（生产级必须）                                  │
│                                                        │
│  类目A：关键转化（Purchase / InitiateCheckout）         │
│      → 最高质量 user_data（em + ph + external_id）      │
│      → 实时单条发送（< 5s），必带 event_id             │
│                                                        │
│  类目B：高价值动作（AddToCart / AddPaymentInfo）        │
│      → user_data 提供 em（若有）+ ip/ua                 │
│      → 实时或近实时（< 60s）批量                       │
│                                                        │
│  类目C：浏览类（PageView / ViewContent）                │
│      → 只发 ip/ua/fbp/fbc + user_id（不发给 em/ph）    │
│        —— 防止把浏览流量都变成"高匹配"稀释关键信号      │
│      → 批量 500/批                                     │
│                                                        │
│  类目D：异步/大促补发                                 │
│      → 走队列 + 批量 + event_id 幂等                    │
└────────────────────────────────────────────────────────┘
```

**踩坑实录**（Ryan 项目实录）：某次把 `ViewContent` 也全部带上 `em`+`ph`，EMQ 从 6.3 冲上 8.8，看着很好——但 `Purchase` 的**匹配率反而下降**（优化器收到大量高置信浏览信号稀释转化建模），且触发了 Meta 的噪声机制，CPI 反而涨了 12%。结论：**分层发送是必须项，不是优化项**。

### 3.4 单事件发送：`meta_send_capi`

```python
# scripts/ad_platform_api.py 中的生产级实现（原方法：meta_send_capi）
def meta_send_capi(self, pixel_id: str, *, event_name: str,
                   event_time: int, event_id: str,
                   user_data: Dict[str, Any], custom_data: Dict[str, Any],
                   action_source: str = "website",
                   event_source_url: str = "",
                   test_event_code: Optional[str] = None,
                   data_processing_options: List[str] = None) -> Dict[str, Any]:
    """发送单个 CAPI 事件（完整生产流程：整形→哈希→ POST→超时重试）"""
    if data_processing_options is None:
        data_processing_options = []

    payload = {
        "event_name": event_name,
        "event_time": int(event_time),      # 必须 Unix 秒
        "event_id": event_id,               # 幂等键（重试复用同一个）
        "action_source": action_source,
        "user_data": user_data,             # 已是标准化的（hash 数组）
        "custom_data": custom_data,
    }
    if event_source_url:
        payload["event_source_url"] = event_source_url

    url = f"{GRAPH_URL}/{API_VERSION}/{pixel_id}/events"
    body = {"data": [payload]}
    access_token = self._get_token()          # meta 凭证
    headers = {"Content-Type": "application/json"}

    last_exc = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.post(
                url,
                json=body,
                headers={**headers, "Authorization": f"Bearer {access_token}"},
                timeout=REQUEST_TIMEOUT_S,
            )
            data = resp.json()
            if resp.status_code == 200 and data.get("events_received", 0) > 0:
                return {"ok": True, "response": data, "attempt": attempt}
            # 对可重试错误重试
            if resp.status_code in (429, 500, 502, 503, 504):
                time.sleep(RETRY_BACKOFF * (2 ** (attempt - 1)))
                continue
            # 4xx（权限/参数）不可重试
            return {"ok": False, "error": data, "status": resp.status_code}
        except requests.exceptions.RequestException as e:
            last_exc = e
            time.sleep(RETRY_BACKOFF * (2 ** (attempt - 1)))
    return {"ok": False, "error": f"after retries: {last_exc}"}
```

**接口要点**：`event_id` 必须在重试中复用，否则重试会变双计。这是**幂等的最小实现**。

### 3.5 幂等键生成策略（生产硬规范）

不重复拿 `uuid4()` 当幂等键。规范是**业务可追溯 + 稳定可重放**：

```
event_id = "<业务域>|<实体ID>|<事件类型>|<事件时间戳(秒)>"
```

| 场景 | 生成的 event_id 示例 |
|------|---------------------|
| 订单购买 | `order:88231:purchase:1784031600` |
| 下单（重试同一次） | 同 `order:88231:purchase:1784031600`（严禁换成新 UUID） |
| 加购 | `cart:u-77:add_to_cart:1784031500` |
| 注册 | `acct:user_001:complete_registration:1784031400` |

```python
def make_event_id(domain: str, entity: str, event_type: str,
                  ts: int | None = None) -> str:
    """稳定幂等键：同一业务事件每次重放得到同一个 id"""
    return f"{domain}:{entity}:{event_type}:{ts or int(datetime.now(timezone.utc).timestamp())}"
```

### 3.6 浏览器端（Pixel / fbevents.js）与 CAPI 用同一个 `event_id`

```
┌───────────────────── 前端 ─────────────────────┐
│  <script>                                       │
│  fbq("track", "Purchase", { value: 89.99,      │
│      currency: "USD" }, { eventID: "order:88231:purchase:1784031830" }); │
│  </script>                                     │
└───────────────────────┬────────────────────────┘
                        │ 同一 event_id
                        ▼
┌───────────────────── CAPI 后端 ────────────────┐
│  meta_send_capi(..., event_id="order:88231:purchase:1784031830") │
└───────────────────────┬────────────────────────┘
                        ▼
              Meta 去重：同一 (event_id, pixel_id)
```

关键技术点：前端 `fbevents.js` 传入的 `eventID` 必须与后端 `event_id` **逐字节一致**（大小写、分隔符、时间戳都不要差），否则去重失败。

### 3.7 批量发送：`meta_send_capi_batch`

```python
def meta_send_capi_batch(self, pixel_id: str, events: List[Dict[str, Any]],
                         *, data_processing_options=None,
                         test_event_code: Optional[str] = None) -> Dict[str, Any]:
    """
    批量发送 CAPI 事件。
    官方要求：批量请求 URL 必须带 data_processing_options=
    （哪怕为空数组）。
    """
    if data_processing_options is None:
        data_processing_options = []

    # 切片保护
    batches = [events[i:i + EVENTS_BASE_LIMIT] for i in
               range(0, len(events), EVENTS_BASE_LIMIT)]
    results = []
    for batch in batches:
        url = f"{GRAPH_URL}/{API_VERSION}/{pixel_id}/events"
        body = {"data": batch}
        params = {"data_processing_options": json.dumps(data_processing_options)}
        if test_event_code:
            params["test_event_code"] = test_event_code
        resp = self._post_with_retry(url, body=body, params=params)
        results.append(resp)
    return {"batches": results}   # 逐批可看 accepted / dropped
```

- 批量返回的 `events`（数组）里每项有 `status`：`accepted` / `dropped`，`dropped` 的项会有 `message`；
- **批量失败不原子回滚**——必须逐项检查状态，把失败的丢回队列下一轮重试；
- 推荐 200-500/批，1000 是上限；奇数异常时建议 250~500 压限。

### 3.8 队列与异步处理（生产核心架构）

真实生产里你**不能让业务请求同步阻塞**在 CAPI 的 RTT 上（CAPI 的 RTT 常见 200ms-2s）。所以要：

1. 业务落库 → 事件**写队列**（如 Redis Stream / Kafka / SQS）→ 立即返回；
2. 独立的 worker 消费 → 规范化/hash → 批量发送 → 失败重试（指数退避）→ 死信（DLQ）。

```
用户下单
   │
   ▼
[API 网关] ──► [订单服务]
                 │ ① 落库（source of truth）
                 │ ② 写事件队列
                 ▼
        ┌───────────────────┐
        │  Queue: capi.events│（Kafka Topic / SQS / Redis Stream）
        └─────────┬─────────┘
                  │ 消费者（worker，3~10 并发）
                  ▼
         [ 事件整形 Worker ]
         ├─ 规范化 + SHA-256 hash
         ├─ 幂等（event_id 本地去重表 或 落库唯一键）
         ├─ 批量 500/批
         ▼
   POST /{pixel_id}/events
         │
    ┌────┴─────────────┐
    │ 成功 → 记录已发   │
    │ 429/5xx → 退避重试（≤3 次） │
    │ 4xx → 进 DLQ（人肉分析）   │
    └──────────────────┘
```

**为什么要队列不直接同步发**（三次真实教训）：

1. **幂等**：队列的重放消费配合去重表（`(event_id, pixel_id)` 唯一键）可做到端到端幂等；
2. **解耦**：Meta 抖一波（5xx 或 429）不影响用户下单；
3. **大小突发**：大促期间并发降到 10k QPS，队列让 CAPI 稳定在 Meta 限流之下；
4. **可审计**：每个事件的时间戳、原始 payload、发送状态全在队列/日志里可查。

### 3.9 失败重试、退避与降级策略

```python
def _post_with_retry(self, url: str, *, body=None, params=None,
                     retries: int = MAX_RETRIES, base: float = 1.0):
    for attempt in range(retries):
        try:
            r = requests.post(url, json=body, params=params,
                              headers=self._auth_headers(),
                              timeout=REQUEST_TIMEOUT_S)
        except requests.exceptions.Timeout:
            pass  # 落到退避，同一 event_id 重发（幂等兜底）
        else:
            j = r.json()
            if r.status_code == 200:
                return j
            if r.status_code in (429, 500, 502, 503, 504):
                time.sleep(base * (2 ** attempt))
                continue
            # 4xx 不重试
            return j
    raise MetaCapiRetryFailed(url)
```

| 代码 | 含义 | 处理 |
|------|------|------|
| 200 | 成功 | 检查 `message`/`fbtrace_id` |
| 400 | 参数错（哈希错、event_time 过期） | 修数据，不重试 |
| 401 | token 无效 | 换 token，告警 |
| 403 | 权限不足（App 未授权该像素） | 检查权限 → 修复后台 |
| 429 | 频率限制 | 退避重试 + 降级到小批量 |
| 5xx | 服务器问题 | 退避重试（指数） |

**退避经验**：429 时按 `Retry-After` header 退避；5xx 指数退避 1s/2s/4s；超时按"网络层超时"处理，**必须用幂等键重发**，绝不用新 event_id。

### 3.10 时钟：NTP + 时间戳重放设计

```bash
# 服务器统一 NTP
sudo apt install -y ntpdate chrony
sudo timedatectl set-ntp true
chronyc sources -v   # 检查偏移 < 100ms

# 每 10 分钟告警如果偏移 > 300ms
0 * * * * root chronyc tracking | awk '$1=="Leap" && $4>0.3 {print}'
```

核心规则：**`event_time` 用业务发生时间**，不是"发送时间"。补发（< 7 天）时依然用原始 `event_time`，这样：

- 归因窗口内的转化仍然合理归属；
- 与 `event_id` 组合，补发不会造成"同一秒多个事件"。

### 3.11 与光板前端整合的 `meta_track_pixel`（像素侧）

```python
def meta_track_pixel(self, pixel_id: str, event_name: str, **kwargs) -> Dict:
    """浏览器侧 Pixel 事件（fbevents.js 由前端完成；后端兜底双录）"""
    event_id = kwargs.pop("event_id", None) or make_event_id(
        "px", kwargs.get("order_id", uuid.uuid4().hex), event_name, int(time.time()))
    payload = {
        "event_name": event_name,
        "event_time": int(time.time()),
        "event_source_url": kwargs.get("event_source_url", ""),
        "event_id": event_id,
        "user_data": kwargs.get("user_data", {}),
        "custom_data": kwargs.get("custom_data", {}),
    }
    # 调用真实浏览器像素端点：POST /{pixel_id}/events
    return self.meta_send_capi(pixel_id, **payload)
```

前端 fbevents.js 的完整（含 eventID）：

```html
<script>
  fbq('init', 'PIXEL_ID_THAT_MATCHES_BACKEND');
  fbq('track', 'Purchase', {
    value: 89.99,
    currency: 'USD',
    contents: [{ id: 'SKU-77', quantity: 1 }]
  }, { eventID: 'order:88231:purchase:1784083354' });
</script>
```

### 3.12 `meta_get_conversion_api_config` / `meta_update_conversion_api_config`

当前像素的 CAPI 配置管理与（如 `allow_high_match_link`、`allow_organic`、`allow_email_link` 等键的可编程化前提下生产运维的重要补充，代码示意）：

```python
def meta_get_conversion_api_config(self, pixel_id: str, **kwargs) -> Dict:
    """读取像素事件的 CAPI 相关配置（字段以 Graph API 返回为准）"""
    url = f"{GRAPH_URL}/{API_VERSION}/{pixel_id}"
    resp = requests.get(url, params={"fields": "data_processing_options,trusted_domains,aggressive_tip_enabled,allow_advanced_matching"},
                        headers=self._auth_headers(), timeout=15)
    return resp.json()

def meta_update_conversion_api_config(self, pixel_id: str, *, enabled: bool = True,
                                      test_event_code: Optional[str] = None,
                                      **kwargs) -> Dict:
    """更新像素 CAPI 配置（谨慎：影响全站事件行为，生产勿在高峰改）"""
    url = f"{GRAPH_URL}/{API_VERSION}/{pixel_id}"
    params: Dict[str, Any] = {"access_token": self.token}
    if test_event_code:
        params["test_event_code"] = test_event_code
    resp = requests.post(url, params=params, timeout=15)
    return resp.json()

def meta_list_event_source_types(self, **kwargs) -> List[Dict]:
    """列出可选事件源类型（website / app / offline ...）"""
    return ["website", "app", "offline", "physical_store",
            "phone_call", "chat", "customer_service", "system_generated"]
```

### 3.12 与第三方平台集成

#### 3.11.1 GTM Server-Side（Google Tag Manager 服务端）

```
 前端（GTM Web）
    │ 发送事件到自有 server container
    ▼
[GTM SS Container (你的 GCS/LB)] 
    │ 统一转换：规范化 + 哈希（server-side 可做 raw data → hash）
    │ CAPI 标记：官方 template "Meta Pixel - Conversions API"
    │ 参数映射：unified event → CAPI event（如 GTM 的 "purchase" → "Purchase"）
    ▼
POST graph.facebook.com/{pixel_id}/events
```

GTM SS 的关键点：

| 步骤 | 坑 | 建议 |
|------|-----|------|
| 事件名映射 | GTM 事件名未必是标准名 | 建映射表（自上而下） |
| user_data 来源 | 前端 login 后已有 em | GTM SS 可以拼 `external_id` |
| 去重 | GTM 与你的后端 CAPI 双发 | event_id 必须在 GTM 内也用相同的合成 |
| 批量 | GTM 默认逐条 | 用 Cloud函数/脚本批量转发 |

#### 3.11.2 Shopify（Shopify + CAPI）

Shopify 已内建 "Shopify Conversions API"（App "Facebook & Instagram"）：

- 事件名自动映射：`checkout_completed` → `Purchase`；
- `client_ip` / UA 由 Shopify 侧给出；
- **重点**：如果你用自己的服务器同时发 CAPI（复购场景、订阅场景），必须和 Shopify App 的像素协作 event_id，否则重复。
- Shopify 商店用 `Facebook Conversions API` App 内可开关；**Server-side 自建通道必须让 Shopify 端关闭重复的事件源（同一 pixel 双发）**，否则全靠 event_id。

#### 3.11.3 Adobe（Adobe Experience Platform / Launch / Data collection + Meta 连接器）

- 使用 Meta 官方连接器（Meta Ads 扩展）发 Server-side 事件；
- XDM schema 要映射为 CAPI 字段（`xdm:commerce.purchases.value` → `value`/`currency`）；
- 注意：AEP 侧的数据可能带敏感字段，传输前做 数据最小化 和字段白名单。
- 与 AEP Web SDK（浏览器侧）**共享同一 event_id**：客户浏览的 `xdm:event.token` 尽量映射到 event_id。

### 3.13 测试工具：Test Events / Event Manager / Graph API Explorer

#### 测试事件（Test Events）三步：

1. Events Manager → 数据源 → 你的 Pixel → 设置 → 测试事件；
2. 复制 `test_event_code`（URL 参数带 `test_event_code=TEST...`）；
3. 发送，测试事件页面实时收数（True 事件 / Test 事件分开）。

Python 里带测试码发送：

```python
def meta_validate_event_data(self, pixel_id: str, *, payload: Dict[str, Any],
                              test_event_code: Optional[str] = None) -> Dict:
    """发送但校验不落真实: 传 test_event_code 即走测试管道"""
    url = f"{GRAPH_URL}/{API_VERSION}/{pixel_id}/events"
    params = {"test_event_code": test_event_code or TEST_EVENT_CODE}
    resp = self._post_with_retry(url, body=payload, params=params)
    return resp
```

**测试事件（True/False）的意义**：验证你发送的 event 与 Meta 标准事件的字段是否对齐（比如 `Purchase` 缺 `value` 会有 warning）。**生产型建议**：测试事件用专门建的**影子 Pixel**（shadow pixel）来跑，避免污染生产像素数据。

#### Graph API Explorer 的 curl 手测

```bash
TOKEN=你的系统用户token
PIXEL_ID=123456789012345
curl -s -X POST \
  "https://graph.facebook.com/v23.0/${PIXEL_ID}/events" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "data": [{
      "event_name": "Purchase",
      "event_time": 1784080004,
      "event_id": "curl-test:1",
      "action_source": "website",
      "user_data": {
        "em": ["3e1f0a0f3a7ecf1b5a2b8f4a6d0b2f1e3c9c3c4f1a2b3c4d5e6f7a8b9c0d1e2f"],
        "ph": ["2a1b3c4d5e6f7a8b90c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6a7b8c9d0e1f2"],
        "client_ip_address": "1.2.3.4",
        "client_user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"
      },
      "custom_data": {"value": 99.99, "currency": "USD"},
      "event_source_url": "https://www.example.com/checkout"
    }]
  }'
```

正确的响应：

```json
{"events_received":1,"messages":[],"fbtrace_id":"Aq8f9x..."}
```

错误响应示例：

```json
{"error":{"message":"Invalid parameter","code":100,"error_subcode":1810001,...}}
```

#### Events Manager 数据质量看板（Event Manages）

- **活跃事件**：你发的 8 大事件的近期计数；
- **匹配质量**（各事件 Matched / Unmatched）；
- **去重统计**：Pixel 事件 & CAPI 事件「去重」比例；
- **`filters` 字段**：查看哪些事件的 `user_data` 匹配上了哪些键。

### 3.14 事件健康度巡检（每天/每周）

```python
def meta_get_event_quality(self, pixel_id: str, **kwargs) -> Dict[str, Any]:
    """从 Events Manager 拉事件质量评分（同步 EMQ）"""
    # 对应代理：graph/{pixel_id}/stats 或 /pixel_events（字段视版本而定）
    return {
        "pixel_id": pixel_id,
        "emq": ...,
        "matched_events": ...,
        "unmatched_events": ...,
        "top_matched_fields": ...
    }

def meta_list_matched_fields(self, pixel_id: str) -> List[Dict]:
    """列出当前像素匹配键的命中分布（em/ph/...）"""
    raw = requests.get(f"{GRAPH_URL}/{API_VERSION}/{pixel_id}/matched_fields",
                       headers=self._auth_headers()).json()
    return raw.get("data", [])

def meta_list_capi_events(self, pixel_id: str, *, since: int = None,
                           until: int = None, limit: int = 100) -> List[Dict]:
    """列出像素近期接收的事件（调试 vs 生产跟踪），带时间窗过滤"""
    url = f"{GRAPH_URL}/{API_VERSION}/{pixel_id}/events"
    params = {"limit": limit}
    if since: params["since"] = since
    if until: params["until"] = until
    return self._get_json(url, params).get("data", [])
```

**建议巡检指标**

| 指标 | 目标值 | 告警阈值 |
|------|-------|---------|
| 发送成功率 | > 99.5% | < 99% 连续 15min |
| 429 频率 | 0-1 次/时 | > 5 次/时 |
| `event_id` 与 Pixel 的匹配率 | > 90% | < 85% 说明去重键断裂 |
| EMQ（关键转化） | > 7.0 | < 5.0 查数据源 |
| 延迟（下单→送达） | < 5min | > 15min |
| 重复率（报表 vs SDK计数） | < 5% | > 15% |

### 3.15 生产部署架构（完整拓扑）

```
                     ┌────────────────────────────────────────┐
                     │           广告主后端（多可用区）          │
                     │                                        │
                     │  [API GW] ──► [订单/账户Svc]            │
                     │                     │  事件写入            │
                     │                     ▼                   │
                     │          [Kafka Topic: capi-events]     │
                     │                         分区 3           │
                     │                     ▼                   │
                     │  [consumer-1] [consumer-2] [consumer-3] │
                     │                     │                   │
                     │                     ▼                   │
                     │          [事件聚合Worker 批量500]        │
                     │                     │                   │
                     └─────────────────────┼───────────────────┘
                                           │ HTTPS（token SSO 注入）
                        ┌──────────────────▼───────────────────┐
                        │    graph.facebook.com                 │
                        │    POST /{pixel_id}/events            │
                        │            │                          │
                        │    [成功/失败回执]                    │
                        └──────────────────┬───────────────────┘
                                           ▼
                                死信队列 DLQ → SRE 值班盘
```

**架构规范**：

1. **多区容错**：队列跨 AZ，消费者至少 2；
2. **token 轮换**：系统用户 token 90 天轮换（定时任务更新写入 Secret Manager，业务无感）；
3. **限流客户端**：令牌桶 200 QPS 上限（Meta 单像素限流参见文档）；
4. **网络**：进单出口（NAT）或 App 级 IP 白名单；
5. **日志**：结构化日志（request_id + event_id），可重放。

### 3.16 回灌 / 大促补发：用历史 event_time 批量

大促后拿订单表（含下单时间）一次性补发（特例：72h 内尽量；7d 是极限）：

```python
def backfill_orders(pixel_id: str, orders: List[dict]) -> List[Dict]:
    events = []
    for o in orders:
        # event_time 必须带**原始下单时间**（Unix 秒），不能是 now()
        events.append({
            "event_name": "Purchase",
            "event_time": o["ordered_at"],          # 原始时间戳
            "event_id": f"order:{o['id']}:purchase:{o['ordered_at']}",
            "user_data": build_capi_user_data(o["user"]),
            "custom_data": {"currency": o["ccy"], "value": o["amount"],
                            "order_id": str(o["id"])},
        })
    return meta_send_capi_batch(pixel_id, events, data_processing_options=[])
```

---

### 3.17 完整生产级发送流程：哈希 → 签名 → 重试 → 幂等 → 去重（串讲代码）

把前面散落的环节串成一个**单一生产入口**。这是 `meta_send_capi` / `meta_send_capi_batch` 的服务端总装线：

```python
import hashlib, base64, re, time, json, logging
from dataclasses import dataclass, field
from typing import Optional
import requests

logger = logging.getLogger("capi.producer")

# ---------------- 规范化 + 哈希 ----------------
def _b64sha(t: str) -> str:
    return base64.b64encode(hashlib.sha256(t.encode()).digest()).decode()

def norm_email(v: str) -> str: return (v or "").strip().lower()
def norm_phone(v: str) -> str:
    d = re.sub(r"\D", "", v or "")
    return d
def norm_name(v: str) -> str:
    return re.sub(r"[^a-z]", "", (v or "").lower())

def build_user_data(u: dict) -> dict:
    out = {}
    for k in ("em", "ph", "fn", "ln"):
        raw = u.get(k)
        if raw:
            norm = {"em": norm_email, "ph": norm_phone,
                    "fn": norm_name, "ln": norm_name}[k](raw)
            out[k] = [_b64sha(norm)]
    if u.get("external_id"):
        out["external_id"] = [_b64sha(str(u["external_id"]).strip().lower())]
    # 明文键
    for k in ("client_ip_address", "client_user_agent", "fbp", "fbc"):
        if u.get(k):
            out[k] = u[k]
    return out

# ---------------- 事件对象 + 事件 ID 生成 ----------------
@dataclass
class CapiEvent:
    event_name: str
    event_time: int
    user: dict
    custom: dict
    event_source_url: str = ""
    action_source: str = "website"
    order_id: str = ""
    event_id: str = field(default="")

    def __post_init__(self):
        if not self.event_id:
            self.event_id = f"evt:{self.order_id or 'x'}:{self.event_name}:{self.event_time}"

    def to_payload(self) -> dict:
        return {
            "event_name": self.event_name,
            "event_time": int(self.event_time),
            "event_id": self.event_id,
            "action_source": self.action_source,
            "event_source_url": self.event_source_url,
            "user_data": build_user_data(self.user),
            "custom_data": self.custom,
        }

# ---------------- 发送器：重试 + 幂等 + 去重 ----------------
class CapiSender:
    def __init__(self, pixel_id, token, dedup=None, retries=3):
        self.pixel_id = pixel_id
        self.token = token
        self.dedup = dedup          # 去重表（set 语义）
        self.retries = retries

    def _send_one(self, payload, params) -> dict:
        url = f"https://graph.facebook.com/v23.0/{self.pixel_id}/events"
        last = None
        for att in range(self.retries):
            try:
                r = requests.post(
                    url, json={"data": [payload]}, params=params, timeout=30,
                    headers={"Authorization": f"Bearer {self.token}"})
                j = r.json()
                if r.status_code == 200 and j.get("events_received", 0) > 0:
                    return {"ok": True, "resp": j}
                if r.status_code in (429, 500, 502, 503, 504):
                    time.sleep(1.5 * (2 ** att)); continue
                return {"ok": False, "http": r.status_code, "err": j}
            except requests.RequestException as e:
                last = e; time.sleep(1.5 * (2 ** att))
        return {"ok": False, "err": str(last)}

    def dispatch(self, evt: CapiEvent, test_event_code=None) -> dict:
        # 幂等 + 去重：同一 event_id 只发一次（生产用 Redis/DB 实现真实原子）
        if self.dedup is not None:
            key = f"{self.pixel_id}:{evt.event_id}"
            if key in self.dedup:
                logger.info("skip dup event_id=%s", evt.event_id)
                return {"ok": True, "skipped": "dedup"}
            self.dedup.add(key)
        params = {}
        if test_event_code:
            params["test_event_code"] = test_event_code
        result = self._send_one(evt.to_payload(), params)
        logger.info("capi event_id=%s result=%s", evt.event_id, result)
        return result

    def dispatch_batch(self, events, data_processing_options=None) -> dict:
        dp = data_processing_options if data_processing_options is not None else []
        results = []
        for i in range(0, len(events), 500):
            chunk = [e.to_payload() for e in events[i:i + 500]]
            url = f"https://graph.facebook.com/v23.0/{self.pixel_id}/events"
            r = requests.post(
                url, json={"data": chunk},
                params={"data_processing_options": json.dumps(dp)},
                headers={"Authorization": f"Bearer {self.token}"}, timeout=60)
            j = r.json()
            results.append({"status": r.status_code, "body": j})
        return {"batches": results}

# ---------------- 调用示例 ----------------
sender = CapiSender(pixel_id="1234567890", token=ACCESS_TOKEN,
                    dedup=set())   # 生产换 Redis SETNX

sender.dispatch(CapiEvent(
    event_name="Purchase",
    event_time=int(time.time()),
    order_id="order-88231",
    user={"em": "alice@example.com", "ph": "15551234567",
          "client_ip_address": "203.0.113.9",
          "client_user_agent": "Mozilla/5.0 ..."},
    custom={"currency": "USD", "value": 89.99, "order_id": "88231"},
    event_source_url="https://shop.example.com/checkout?s=ok",
))
```

这段串讲可以当作你们代码库的 Reference Implementation（参考实现），把 规范化 / 哈希 / 幂等 / 去重 / 重试 / 批量 全部收口。

### 3.18 并发、异步 Worker 与客户端限流

```python
# 生产 Worker（用线程池 + 有界队列），防止打爆 Meta 频率限制
from concurrent.futures import ThreadPoolExecutor
import threading, queue

class CapiPipeline:
    def __init__(self, sender: CapiSender, max_workers=4, queue_cap=5000):
        self.sender = sender
        self.q = queue.Queue(maxsize=queue_cap)
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self._rate = queue.Queue()          # 简易令牌桶
        threading.Thread(target=self._consumer, daemon=True).start()

    def enqueue(self, evt: CapiEvent):
        # 背压：队列满则丢弃并记指标（生产会告警）
        try:
            self.q.put_nowait(evt)
        except queue.Full:
            logger.warning("capi queue full, dropping %s", evt.event_id)

    def _consumer(self):
        while True:
            evt = self.q.get()
            self.executor.submit(self.sender.dispatch, evt)
```

| 客户端限流要点 | 说明 |
|----------------|------|
| 令牌桶 | 200 QPS 以内（按 Meta 文档像素级上限） |
| 批量切片 | 500/批，避免单请求体过大 |
| 错误背压 | 429 时减慢；5xx 时暂停 30s |
| 降级 | 缓存 + 延后发送（不丢弃） |

### 3.19 日志、Trace 与可观测性

生产必须能回答三个问题：**发了没？发哪了？结果如何？**

```json
{
  "ts": "2026-08-14T10:00:00Z",
  "level": "info",
  "logger": "capi",
  "pixel_id": "1234567890",
  "event_id": "evt:order-88231:Purchase:1784085600",
  "event_name": "Purchase",
  "attempt": 1,
  "http_status": 200,
  "events_received": 1,
  "fbtrace_id": "DeW0t2a..."
}
```

| 指标（Prometheus） | 说明 | 告警 |
|---------------------|------|------|
| `capi_sent_total` | 发送数 | — |
| `capi_failed_total{reason="429|5xx|timeout"}` | 失败数 | >0.5% |
| `capi_latency_seconds` | RTT | p95 &gt; 3s |
| `capi_dropped_total` | 队列溢出丢弃 | >0（必须 0） |
| `capi_dedup_skipped_total` | 去重跳过 | — |
| `capi_clock_offset_seconds` | 时钟偏移 | \|offset\|>0.3 |

### 3.20 GTM Server-Side 与 Adobe XDM 事件映射细节

**GTM Server-Side（CAPI Tag）参数映射建议**：

| GTM 数据层变量 | CAPI 字段 | 说明 |
|----------------|-----------|------|
| `user.email` | `user_data.em` | 需在前端登录后用 hash（或用 CAPI 标记自动 hash） |
| `user.phone` | `user_data.ph` | 同上 |
| `transaction_id` | `event_id` | 与后端一致以去重 |
| `purchase.value` | `custom_data.value` | float |
| `purchase.currency` | `custom_data.currency` | ISO 4217 |
| `page.url` | `event_source_url` | 完整 URL |
| — | `action_source=website` | 固定 |

**注意**：GTM SS 是"前端事件经你的服务器"转发——它**没有**你数据库里的真实订单金额。若要做精准价值上报，仍需后端 CAPI（从订单库取 value）。推荐方案：

```
方案A（推荐）：前端 Pixel（含 eventID） + 后端 CAPI（真金白银）
方案B：前端 Pixel（含 eventID） + GTM SS（承接统一 hash）——针对无后端的轻量站
```

**Adobe（AEP Web SDK + Meta 连接器）映射**：

| AEP XDM | CAPI | 说明 |
|---------|------|------|
| `xdm:eventType`（commerce.purchases） | `event_name=Purchase` | 由连接器映射 |
| `xdm:commerce.order.purchaseID` | `event_id` | 用 purchaseID 做幂等键！ |
| `xdm:commerce.priceTotal` | `custom_data.value` | 单位、货币要对齐 |
| `identityMap.email` | `user_data.em`（hash） | 连接器应 hash |
| `xdm:web.webPageDetails.URL` | `event_source_url` | 原样 |

**多源双发去重的关键**：无论走 Pixel / GTM SS / AEP / 后端 CAPI，**必须共享同一个 event_id 生成规则和同一个像素 ID**，否则每个通道的事件在 Meta 里都是"另一条"，重复计费 / 重复归因。

### 3.21 多店铺 / 多币种 / 多像素生产策略

大型电商（Ryan 项目常打多站点）的落地方案：

```
┌─ 北美店 pixel=111（USD） ──► CAPI-A（us1 区域 Worker）
├─ 欧洲店 pixel=222（EUR） ──► CAPI-B（eu1 区域 Worker，含 GDPR/LDU）
├─ 东南亚店 pixel=333（SGD）─► CAPI-C（ap1 区域 Worker）
└─ 共享 WAF/NAT 出口
```

要点：

1. **每店独立 pixel**（归因隔离、币种隔离、地区合规隔离）；
2. 队列按 region 分区（`capi.{pixel_id}.events`），Worker 打标地域；
3. 汇率：统一在入队前折算成**店铺结算货币**，避免报表币种混乱；
4. token 按 pixel 分权限系统用户，最小化爆破面；
5. 灰度：新店先 `test_event_code` → 影子像素 → 逐步放量。

### 3.22 灰度上线与回滚

```
上线顺序（每步验证）：
1. 影子 pixel + test_event_code（不落真实）
2. 同 pixel test_event_code=true（真像素测试）
3. 5% 流量单通道（只 CAPI 覆盖一部分订单）
4. 双通道（Pixel + CAPI）+ event_id 去重校验
5. 全量
回滚：关 CAPI 开关（feature flag），Pixel 继续兜底；事件不丢不双计。
```

---

## 四、常见问题与排查

### 4.1 重复计数（最典型生产事故）

**症状**：报表 Purchase 是业务数据库的 1.5~2 倍。

**排查步骤**：

| 步骤 | 方法 |
|------|------|
| 1 | 确认 Pixel 与 CAPI 双通道存在 |
| 2 | 每次事件是否带 `event_id`？ |
| 3 | 前端 `eventID` 与后端 `event_id` 是否完全一致？ |
| 4 | 重试逻辑是否复用了 event_id？ |
| 5 | 是否有多源（App + Web + 线下 POS）对 同 pixel 双发？ |

**修复清单**：

- 统一 event_id 规范（见 3.5）；
- 前端模板把 eventID 传入 fbevents.js（后台数据源下发）；
- CAPI 重试模板幂等。

### 4.2 匹配率低（EMQ < 5 / match rate drop）

| 现象 | 可能原因 | 排查 |
|------|---------|------|
| EMQ 骤降 | 哈希规范化错误（大小写/格式） | 校验 hash 输入，用已知邮箱 hash 比对 Meta 的 hash 示例 |
| 无用户数据 | 只发 IP/UA | 检查登录率、后台是否取不到用户 |
| 字段全是 IP | 前端不传 fbp/fbc | 检查 Cookie 是否禁用 |
| 国家与数据不符 | 国家键大写 vs `US` | 规范化正确 |

**用 `meta_list_matched_fields` 定位**：看哪些键命中最多。

### 4.3 事件不显示 / 延迟

| 症状 | 原因 | 处理 |
|------|------|------|
| 测试事件里没有 | test_event_code 配错 | 复制完整 code |
| 有 CAPI 无 Pixel | 前端代码未部署 | 检查页面源码 |
| 延迟 1-3h | 队列堆积 | 消费者扩容 |
| 永远没有 | hash 错误 | 用真实数据 re-check |

### 4.4 批量 429 / 频率限制

- 把批量从 1000 降到 250~500；依赖退避；
- 遇到 `error_subcode 1487057`（频率）必须指数退避并降低批次速率；
- 峰值瞬时的 60s 窗口内控制发送频率。

### 4.5 时区/时间戳伪问题

- 排除 `event_time` 单位错误（毫秒）导致时间 0；
- 服务器时钟偏移；`timedatectl` / chrony；
- 跨天补发注意 `until` 窗口用的是 UTC 还是本地时区。

### 4.6 通用错误码速查表

| code | 含义 | 处理 |
|------|------|------|
| 100 | 参数错误（event_name 为空等） | 修字段 |
| 109 | 调用频率限制二级 | 退避 |
| 190 | 无效 access_token | 换新 token |
| 200 | 权限不足 | 检查系统用户权限 |
| 2326 | 场景不符（事件时间 > 7d） | 检查 event_time |
| 2215 | AR 2.0C 的一些 |
| 400 | iOS 用户不感兴趣/受限 | 无操作，接受 |

### 4.7 测试事件常见误导

- 测试事件在线对 **1:1** 模拟事件，但在报表里不可见——别拿测试数据当生产；
- 测试事件会让 EMQ 波动（测试流量 hash 可能不规范）；
- 上线切换时必须先灰度：`test_event_code` 跑通 → 去掉 → 观察 1 天。

### 4.8 死信处理器（DLQ）检查清单

1. 检查是否是 hash 错误（用测试事件复现）；
2. 检查 event_id 幂等冲突（数据被重复 + 或修 event_id 后重放）；
3. 检查是否大促积压导致 429 退避；
4. 人工修数据 → `campaign`。

---

### 4.9 一张图排查事件没到 / 报错

```
CAPI 事件没到 / 报错？
      │
      ├─ 4xx 参数错误 ──► ① event_time 是否为秒（非毫秒）？
      │                       ② em/ph 是否 hash？（明文会 100 错）
      │                       ③ event_name 是否合法？
      │                       ④ 空字段剔除了吗？
      │                          ├─ 凭 fbtrace_id 在 Graph 报错明细定位
      │                          └─ 用手工 curl + test_event_code 复现
      │
      ├─ 4xx 权限 ────► ① token 是系统用户/员工？是否过期？
      │                   ② 系统用户对该 pixel 有无 manage 权限？
      │                   ③ App（facebook 的 app）是否绑定像素？→ 授权
      │
      ├─ 429 ────────► 降批量、退避、看 Retry-After
      │
      ├─ 5xx ────────► 退避重试 + 幂等键（同一 event_id）重发
      │
      └─ 200 但有 events_received=0
                          │
                          ▼
                  test_event_code 是否传了？（测试流量不进生产）
                  data 数组是否非空？JSON 是否可解析？
```

### 4.10 CAPI 与 Pixel 对账：怎么知道数据对不对

对账（reconciliation）是生产团队每天/每周的必备动作：

```python
def reconcile(db_orders, meta_events):
    """对比业务订单数与 Meta 报表事件数，定位缺口"""
    db_total = sum(o["purchase"] for o in db_orders)   # 业务真实下单数
    meta_total = sum(1 for e in meta_events
                     if e["event_name"] == "Purchase")
    ratio = meta_total / db_total if db_total else 0
    # 期望 ~= 1.0（双通道去重后），小于 0.9 说明有丢失
    if ratio < 0.9:
        logger.error("purchase reconciliation low: %s%%", round(ratio * 100))
    return {"db": db_total, "meta": meta_total, "coverage": ratio}
```

| 对账情况 | 含义 | 动作 |
|----------|------|------|
| ratio ≈ 1.0 | 完美 | 无 |
| ratio < 0.9 | 有事件丢失（队列 / hash 错 / 晚了 >7d） | 按订单时间窗口排查 |
| ratio > 1.1 | 双计（去重键断裂） | 查 event_id（见 4.1） |
| ratio 波动大 | 有噪声 / 测试流量 | 看 test_event_code 是否误开 |

### 4.11 常见 Graph API 错误码深表（CAPI 专属）

| code / subcode | 消息特征 | 根因 | 处理 |
|----------------|----------|------|------|
| 100 / 1805001 | `event_name` invalid | 空/非法名 | 检查映射表 |
| 100 / 1810001 | invalid parameter | 字段类型错（event_time 字符串 vs int） | 强类型化 |
| 100 / 2301001 | `Invalid hash` | em/ph 未正确 hash / hash 形式错 | 用规范 hash（base64 而非 hex） |
| 190 | Session has expired | token 过期 | 轮换 token |
| 200 | Permissions error | 系统用户权限不足 | 赋 pixel manage |
| 429 | App/Page rate limit | 频率超限 | 降批量、退避 |
| 2326 | 事件时间太旧 | `now - event_time > 7天` | 检查 event_time 单位/时区 |
| 431 | 请求过大 | batch 超 8MB | 缩小批量件数 |

### 4.12 从"信号质量差"反向定位到数据链路

用反向排查表逐节定位 EMQ 低：

```
信号质量低 ──► 查 user_data 是否够
                 ├─ 登录率低？→ 传 external_id + ip/ua + fbp
                 ├─ hash 规范化错？→ meta_validate_event_data 校验
                 ├─ 只发浏览事件？→ 关键转化没传 user_data
                 └─ Pixel 与 CAPI 里 user_data 冲突 → 去重后保留哪条？
                     （同时发不同 user_data，Meta 会取舍）
```

**专坑**：Pixel 和 CAPI 给**同一事件发了不同的 user_data**（比如前端有 em 但后端没传 em，只有 ip）——去重后 Meta 可能保留先到/质量更高的，导致后端精心准备的字段没被用上。规范：**双通道的 user_data 应同源同构**（前端尽量从后端下发的字段取）。

### 4.13 上线 Checklist（给即将投产的团队）

| # | 检查项 | 状态 |
|---|--------|------|
| 1 | 系统用户 token 已授权目标 pixel | ☐ |
| 2 | 时钟已 NTP 同步（offset < 100ms） | ☐ |
| 3 | event_id 规范统一（前端=后端） | ☐ |
| 4 | 关键转化带完整 user_data + external_id | ☐ |
| 5 | 敏感字段已剥离、LDU 逻辑已接入 | ☐ |
| 6 | 批量 URL 带 `data_processing_options=[]` | ☐ |
| 7 | 429/5xx 退避 + 幂等重发已测 | ☐ |
| 8 | 队列 / 去重表 / DLQ 已部署 | ☐ |
| 9 | 指标与告警（capi_*）已上线 | ☐ |
| 10 | 灰度计划（影子 pixel→5%→全量）已就绪 | ☐ |

---

## 五、自测题

### 5.1 去重键不生效

**问题**：明明给事件加了 `event_id`，报表里还是双计，可能是什么？

<details><summary>答案</summary>

事件的原因有多种：

1. **event_id 不一致**：前端 `fbevents.js` 传入的 `eventID` 与后端 CAPI 的 `event_id` 不逐字节一致（大小写、时间戳格式不同）→ Meta 无法匹配到同一条；
2. **像素 ID 不一致**：Pixel 与 CAPI 发往不同 pixel_id（如临时像素/测试像素），事件没有落在同一源头，去重基座不同；
3. **重复发送无去重**：CAPI 重试时每轮都换新的 `event_id`（比如用 `uuid4()` 重试）——幂等键断裂；
4. **消息语义**：误把事件类型不一致（Purchase 发给 Pixel，另个发给 CAPI 不同 event_name），去重失效；
5. **事件时间相去甚远**：即使 event_id 相同，`event_time` 差距过大（>7 天）事件在边界上被当两条。

排查路径：查 Meta 报表→按 event_id 过滤（可以用 `Event Manager → 事件`防护日志里查该订单的两次事件 ID 对比）。
</details>

### 5.2 哈希规范化的坑

**：同一用户邮箱，你哈希成 `Abc@Example.`(大小写未处理)，Meta 端为什么匹配不到？**

<details><summary>答案</summary>

任何标准化的前后不一致，最终都是 hash 不一致 → 匹配必然失败：

- 你的哈希输入是原始字符串，Meta 的匹配引擎侧是**规范化后**的字符串（比如全小写去空格）做哈希；
- 两个不同字符串的 SHA-256 完全不同；即使与"正确"实体一致，也匹配不到；
- 必须严格：email → 去首尾空格 → 小写；phone → 去符号 → 去前导 0/按国码；fn/ln → 保留字母小写。

同一用户两次规范化的哈希值还必须**完全一致**（为了对账与补发幂等）。

扩展：用测试事件两步验证——先在测试事件里发规范化的 hash，Event Manager 里查看"匹配成功/未匹配"来校验自己的规范化。
</details>

### 5.3 批量请求为什么必须写 `data_processing_options=[]`？

<details><summary>答案</summary>

官方规定：**并发事件的批量请求 URL 必须显式携带 `data_processing_options` 参数（哪怕是空数组）**，缺省时部分（批量）路由可能被当单事件处理或拒绝。空数组表示"不做受限数据处理（LDU）"，也就是默认处理。开启 LDU（`["LDU"]`）则表示针对该用户应用 CCPA 等受限处理（仅用户行使拒绝权时）。

所以格式化：批量 = URL 带 `data_processing_options=[]`（必须 JSON 编码传 `%5B%5D`），`Content-Type: application/json`，`data` 里最多 1000（建议 200-500）。
</details>

### 5.4 模拟事件时间戳的坑

**问题：为什么 CAPI 补发（回填）时，必须用原始 `event_time` 而不是当前时间？**

<details><summary>答案</summary>

1. 归因：Meta 会把 `event_time` 放进归因窗口的计算逻辑（例如 7 天点击归因、24h）。如果用当前时间，事件会被算进"刚转化"，丢失真正的归因对准包括广告周期；
2. 去重：`event_id` 与 `event_time` 一起构成事件的语义键；原始时间保持一致才能与已存在的 Pixel 事件去重；
3. 时序：`event_time` > 7 天的事件会被拒绝（time_delay error）；
4. 优化器：模型看到"今天"有大量补发，会误判跑量（实际是三天前的订单），造成 CPA 计算可笑。

正确做法：补发时 event_time = 业务发生时间（原始时间戳），发送时间用当前时间变量记录在日志里。
</details>

### 5.5 双发时先验顺序

**：Pixel 与 CAPI 双向都已发送同一事件。去重时 Meta 保留哪一条？**

<details><summary>答案</summary>

Meta 的规则是**保留先到的**（无论 Pixel 还是 CAPI），并且：

- 相同 `(event_id, event_source_id)` 的事件，**先到达者保留**；
- **同时（<极少时差）**，或无法比较「先到」时，Meta 保留**质量更高**的那条（CAPI 通常被视为更高质量）；
- 前端事件（Pixel）通常先于 CAPI（CAPI 可能因为异步/批量有一个延迟窗口）。

生产含义：把 CAPI 发送尽量贴近业务事件发生时间（实时发送 <3s），或确保直接用 CAPI 作为主要通道（关闭 Pixel double-了 event）。如果 CAPI 落后太多（分钟级），Meta 会保留先到的 Pixel，导致 CAPI 的质量优势丢失。
</details>
---

## 六、附录

### 附录 A：术语对照表（CAPI 相关）

| 缩写/术语 | 全称/中文 | 说明 |
|-----------|-----------|------|
| CAPI | Conversions API | 服务端转化事件发送接口 |
| AEM | Aggregated Event Measurement | iOS14+ 聚合事件测量 |
| EMQ | Event Match Quality | 事件匹配质量评分 |
| dedup | Deduplication | 去重 |
| event_id | 事件幂等/去重键 | 同源唯一 |
| event_source_id | 事件源 ID | = pixel_id |
| user_data | 用户匹配数据 | em/ph/fn/ln 等 |
| custom_data | 自定义业务数据 | 金额、商品等 |
| action_source | 事件来源渠道 | website/email/app… |
| fbc/fbp | Facebook Cookie | 浏览器追踪标识 |
| LDU | Limited Data Use | 受限数据使用（CCPA） |
| ATT | App Tracking Transparency | iOS 应用追踪透明 |
| ITP | Intelligent Tracking Prevention | Safari 智能防追踪 |
| DLQ | Dead Letter Queue | 死信队列 |
| S2S | Server-to-Server | 服务器到服务器（即 CAPI 本质） |

### 附录 B：官方参考链接与文档

- Conversions API 官方介绍：https://developers.facebook.com/docs/marketing-api/conversions-api
- 事件上报格式与哈希规范（Hash Spec）：https://developers.facebook.com/docs/marketing-api/conversions-api/parameters
- 事件匹配与 EMQ：https://www.facebook.com/business/help/321447189719770
- 去重（Deduplication）说明：https://developers.facebook.com/docs/marketing-api/conversions-api/deduplicate-pixel-and-server-events
- 数据源健康与测试事件（Events Manager / Test Events）：https://www.facebook.com/business/help/967854296931383
- 服务器端事件批量与 data_processing_options：https://developers.facebook.com/docs/marketing-api/conversions-api/parameters#data-processing-options
- 与 Shopify / GTM / Adobe 集成文档（Meta 官方收购方案）：
  - GTM SS 标记：https://developers.facebook.com/docs/marketing-api/conversions-api/gtm-server-side
  - Shopify：https://www.facebook.com/business/help/1415243376047650

> 提示：文档撰写于 2026-08-14，Graph API 已到 v23.0 左右；接入时以 Meta 开发者文档最新版本字段为准，URL 版本号请随官方更新。

### 附录 C：日常运维快速命令卡

```bash
# 1) 手测事件（带测试码，不落真实）
curl -s -X POST \
  "https://graph.facebook.com/v23.0/${PIXEL_ID}/events" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d "{\"data\":[{\"event_name\":\"PageView\",\"event_time\":$(date +%s),\"test_event_code\":\"${TEST_CODE}\",\"user_data\":{\"client_ip_address\":\"1.2.3.4\",\"client_user_agent\":\"curl\"},\"custom_data\":{}}]}"

# 2) 检查 token 是否有效
curl -s "https://graph.facebook.com/v23.0/me?fields=id,name" \
  -H "Authorization: Bearer ${TOKEN}"

# 3) 读取像素配置
curl -s "https://graph.facebook.com/v23.0/${PIXEL_ID}?fields=id,name,data_processing_options" \
  -H "Authorization: Bearer ${TOKEN}"

# 4) 查看像素近期事件
curl -s "https://graph.facebook.com/v23.0/${PIXEL_ID}/events?limit=20" \
  -H "Authorization: Bearer ${TOKEN}"

# 5) 定时对账（cron 里调 reconcile）
python3 scripts/ad_platform_api.py --reconcile --pixel $PIXEL_ID --days 1
```

### 附录 D：本文涉及的脚本方法族索引

以下方法分布于 `scripts/ad_platform_api.py`（主实现）与 `scripts/meta_api.py`，供团队对照阅读与扩展：

| 方法 | 用途 | 关联章节 |
|------|------|----------|
| `meta_send_capi` | 单事件 CAPI 发送 | 3.4 / 3.17 |
| `meta_send_capi_batch` | 批量 CAPI 发送 | 3.7 / 3.16 |
| `meta_track_pixel` | 浏览器像素事件（后端兜底双录） | 3.11 |
| `meta_list_capi_events` | 列出近期 CAPI 事件 | 3.14 |
| `meta_list_matched_fields` | 匹配键命中分布 | 3.14 / 4.2 |
| `meta_validate_event_data` | 测试校验事件字段 | 3.13 / 4.12 |
| `meta_get_event_quality` | EMQ 评分拉取 | 3.14 |
| `meta_list_event_source_types` | 事件源类型枚举 | 3.12 |
| `meta_get_conversion_api_config` | 读取像素 CAPI 配置 | 3.12 |
| `meta_update_conversion_api_config` | 更新像素 CAPI 配置 | 3.12 |
| `meta_list_pixel_events` | 列出像素事件 | 1.9 / 3.14 |
| `meta_create_pixel_event` | 手动创建像素事件（调试） | 3.13 |

> **收尾提醒**：CAPI 是**信号通道**不是"报表抄数"。真正的生产闭环 = 事件准确（匹配/去重/时间戳）+ 队列可靠（幂等/重试/监控）+ 长期对账（数字与业务库一致）。把这条链路做成可观测、可回滚、可补发的体系，CAPI 才会成为 ROAS 优化的坚实底座，而不是又一个数据失控点。

*学习日期：2026-08-14 | 上一篇：Meta Advantage+ 全深度指南 | 下一篇：Meta 广告账户结构与权限生产指南*
