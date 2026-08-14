# WhatsApp 营销自动化深度学习笔记

> 创建日期: 2026-08-14
> 作者: Ryan
> 定位: 资深专家级 — WhatsApp 商业营销自动化

---

## 第一部分: WhatsApp 营销生态全景与定位

### 1.1 为什么 WhatsApp 是私域营销的"最后一公里"

在 Meta 广告体系中，Facebook / Instagram 承担"广覆盖、抢心智"的拉新职能，而 WhatsApp
承担"高触达、强转化、重留存"的私域承接职能。二者结合构成完整营销闭环。

```
┌────────────────────────────────────────────────────────────────────┐
│                  WhatsApp 在营销漏斗中的定位                            │
│                                                                    │
│   ┌─────────┐   ┌───────────┐   ┌─────────────┐   ┌───────────┐    │
│   │ 拉新     │──▶│ 认知/兴趣   │──▶│ 私域承接     │──▶│ 复购/裂变   │    │
│   │ Ads 竞价 │   │ Click-to-  │   │ WhatsApp   │   │ WhatsApp  │    │
│   │ FB/IG    │   │ WhatsApp   │   │ 机器人/对话  │   │ 群发/Catalog│   │
│   └─────────┘   └───────────┘   └─────────────┘   └───────────┘    │
│        ↑              ↑               ↑               ↑            │
│   paid social     CTA 跳转       24h 窗口承接      留存/增量       │
└────────────────────────────────────────────────────────────────────┘
```

**为什么偏偏是 WhatsApp：**

| 维度 | Facebook/IG 私信 | WhatsApp | 说明 |
|------|------------------|----------|------|
| 触达率 | 广告触达受影响 | 消息必达、打开率高 | WhatsApp 无算法稀释 |
| 即时性 | 用户被动浏览 | 主动推送、实时 | 适合限时、补货、催付 |
| 私密性 | 公开评论/公开主页 | 端到端加密、一对一 | 信任度更高 |
| 留存 | 弱（回访靠刷 Feed） | 强（内置会话） | 适合会员运营 |
| 转化率 | 广告点击 1-3% | 消息转化可达 10-30% | 高意向流量 |
| 成本 | 按曝光/点击计费 | 24h 服务会话免费 | 会话类消息极低成本 |

### 1.2 WhatsApp 商业产品的三条产品线

要理解营销自动化，必须先分清 WhatsApp 的三条商业产品线，它们是权限、计费和 API
行为的根源：

```
WhatsApp 商业产品三线:
│
├─ 1. WhatsApp Business App (免费 App)
│   ├── 面向: 小型商家 (个人店主)
│   ├── 限制: 单设备登录、最多 4 个用户、无官方 API 批量化
│   ├── 功能: 快捷回复、标签、自动问候、目录 (Catalog)
│   └── 适用: 起步验证 MVP, 通过 meta_send_whatsapp_message 手工维护
│
├─ 2. WhatsApp Business Platform (API/Cloud API)  ← 本笔记重点
│   ├── 面向: 中大型商家、电商、SaaS、服务商
│   ├── 能力: 消息模板、会话窗口、机器人、多媒体、交互按钮、目录
│   ├── 权限: 需要 Business Verification + 电话号码认证
│   └── 计费: 模板消息按量计费 (conversation-based pricing)
│
└─ 3. WhatsApp Business API 本地部署 (On-Premises)
    ├── 面向: 高合规、高吞吐、跨境大客户
    ├── 区别: 自建服务器/容器, 数据不出企业, 成本高
    └── 现状: 新客户推荐 Cloud API, 本地版趋于维护模式
```

### 1.3 本笔记范围与营销视角

> 本笔记定位：**资深专家级 — WhatsApp 商业营销自动化**。
> 区别于 meta-05 的"API 高级用法"和 meta-04 的"功能全貌"，本笔记从**营销增量**
> 与**自动化工作流**切入，聚焦：消息模板、会话窗口、自动回复机器人、批量群发、
> QR 获客、商业资料、Click-to-WhatsApp 广告落地、留存策略，以及一套完整的
> **营销自动化工作流设计**。
>
> 涉及脚本方法按既有 meta_* 命名习惯扩展，例如：
> `meta_list_conversation_templates`、`meta_create_conversation_template`、
> `meta_send_whatsapp_message`、`meta_send_whatsapp_interactive`、
> `meta_generate_whatsapp_qr`、`meta_get_whatsapp_business_profile` 等。
> 这些方法名在本文中作为"脚本层命名约定"出现，用于串联逻辑，非 Meta 官方 SDK 名。

---

## 第二部分: WhatsApp Business API 核心原理

### 2.1 从"个人号"到"官方 API"的能力跃迁

理解 WhatsApp Business API 的核心，是理解它与个人号/App 的根本区别：

```
               个人号/App                Business API
─────────────────────────────────────────────────────────────
消息发起      双方平等               商家只能通过"模板"主动发起
会话窗口      无概念                 24 小时服务窗口内可自由回复
批量发送      手动、易封号           受模板 + 节流 + 质量评分约束
数据接入      无 Webhook            支持 Webhook 实时事件回传
身份识别      手机号                 Phone Number ID + WABA ID
多坐席        App 单人              支持多用户、多机器人协作
计费          免费                  按会话/模板计费
```

**核心结论：** Business API 用"模板 + 会话窗口"机制换取规模化与合规。营销自动化的
一切约束（不能随意群发、24h 窗口、模板审核）都源于这套机制。

### 2.2 关键对象体系

在 WhatsApp Cloud API 中，一切操作围绕三层对象展开：

```
┌───────────────────────────────────────────────────────────────┐
│                 三层对象体系                                      │
│                                                              │
│   Business Manager (BM)                                       │
│   ├── WABA (WhatsApp Business Account, 业务账户)                │
│   │   ├── Phone Number (电话号码, 需认证 + 唯一绑定)              │
│   │   │   └── Phone Number ID (发送/接收消息的实体)              │
│   │   ├── Message Template (消息模板, 需审核)                    │
│   │   ├── Conversational Pricing (会话计费)                     │
│   │   └── Business Profile (商业资料: 描述/网站/分类/营业时间)      │
│   └── System User / 权限                                         │
└───────────────────────────────────────────────────────────────┘
```

**必须记住的 ID：**

| 对象 | ID 字段 | 用途 | 获取方式 |
|------|---------|------|----------|
| WABA | WABA ID | 承载消息、模板、电话号码 | BM 后台或 `GET /{bm}/owned_whatsapp_business_accounts` |
| 电话号码 | Phone Number ID | API 发送消息的目标身份 | `GET /{waba_id}/phone_numbers` |
| 模板 | Template ID / Name | 主动消息的唯一载体 | `meta_list_conversation_templates` |
| 商业资料 | Business Profile | 展示在聊天窗口头部 | `meta_get_whatsapp_business_profile` |

### 2.3 会话窗口（Conversation Window）与 24h 规则

会话窗口是 WhatsApp 营销自动化**最重要的合规边界**，必须吃透。

```
会话窗口时序图:

  t0                t0+24h                      t0+72h
  │                  │                           │
  ▼                  ▼                           ▼
  ├──────────────────┼───────────────────────────┤
  │  业务发起窗口      │   24h 服务会话窗口           │
  │  (模板消息, 付费)  │   (用户回复后开启, 免费)      │
  └──────────────────┴───────────────────────────┘
       ▲                                          ▲
  marketing/utility/                      用户 24h 内再次回复,
  authentication 模板                      窗口重新计时付费模板

  ● marketing 模板:  主动促销/营销, 一次性会话, 最贵
  ● utility 模板:    事务/催单/物流/订单确认, 可含营销尾巴, 较便宜
  ● authentication:  一次性验证码 OTP/两步验证, 24h 有效
  ● service 会话:    用户动作(回复/点击按钮/下单)开启, 24h 窗口内免费
```

**24h 窗口的触发动作**（用户以下任一动作都会开启 24 小时服务会话窗口）：

- 用户主动发送任意消息
- 用户点击模板中的按钮（含 CTA URL / Phone / Quick Reply）
- 用户通过 Catalog 下单
- 用户点击 Click-to-WhatsApp 广告

**窗口内/窗口外能力对比：**

| 场景 | 窗口内（服务会话） | 窗口外（主动触达） |
|------|-------------------|--------------------|
| 消息类型 | 任意自由文本/媒体/交互 | 仅限已审核模板 |
| 费用 | 免费（计入服务会话） | 按模板类型计费 |
| 频率 | 无硬性限制（受质量评分约束） | 受节流 + 频率上限约束 |
| 适用 | 客服、答疑、购物车补全 | 营销、催付、物流、注册验证 |

**踩坑与经验教训 #1（24h 窗口）：**

```
场景: 运营同学想"周一早上统一给 5 万名老客户推新品"
结论: 不可行 —— 没有 24h 窗口 = 只能发模板, 而营销模板会触发计费 + 频率上限
对策:
  1. 把"主动推新品"设计成 marketing 模板但严格控制批次
  2. 更优: 通过 Catalog/WhatsApp Store 承载, 只发双倍转化价值的折价提醒
  3. 利用用户上一次交互(点击/回复)顺手把"下一次触达窗口"叠进去
```

### 2.4 会话计费（Conversation-Based Pricing）

自 2023 年起 WhatsApp 采用**按会话计费**而非按条计费。理解计费模型对营销 ROI
测算至关重要。

```
计费模型速记:

  会话 = 24h 时间盒 + 一次计费
  ├─ marketing 会话:  由 marketing 模板触发, 24h 内所有消息归入该会话, 计 1 次
  ├─ utility 会话:    由 utility 模板触发, 计 1 次
  ├─ authentication:  由验证码模板触发, 24h 有效期, 计 1 次
  └─ service 会话:    由用户动作触发, 24h 窗口, 免费

  例外: 同一 24h 会话从 marketing 转成 service 不会二次计费;
        但若用户在窗口内触发新的 marketing 模板, 会新开会话并再次计费。

  全球分区域价目 (示意, 以官方为准):
  ├─ marketing:  北美 $0.025/会话, 印度 ₹0.0075/会话, 拉美 $0.064/会话
  ├─ utility:    北美 $0.0060/会话, 印度 ₹0.0015/会话
  └─ authentication: 北美 $0.0050/会话, 印度 ₹0.0010/会话
```

**营销 ROI 测算公式：**

```
单会话边际利润 = 客单价 × 转化率 − 会话单价

例: 促销模板, 会话单价 $0.025, 转化率 3%, 客单价 $80
    边际利润 = 80 × 0.03 − 0.025 ≈ $2.375
    即每会话约赚 $2.4, 只要转化率大于 0.03% 就不亏
    (0.025 / 80 = 0.03125%)

优化方向:
  1. 用 utility 模板带营销尾巴 → 便宜且必要
  2. 把多步营销合并进一个会话 → 避免重复开窗付费
  3. 提高首屏模板相关性 → 提升转化率摊薄单价
```

---

## 第三部分: 消息模板（Message Template）体系

### 3.1 模板的本质与类型

消息模板是 WhatsApp 主动触达用户的**唯一合法入口**。没有模板 = 无法发主动消息。

```
模板类型矩阵:

  ┌─────────────────┬──────────────┬───────────────┬─────────────┐
  │ 类型            │ 时效性        │ 主要用途        │ 典型计费档位 │
  ├─────────────────┼──────────────┼───────────────┼─────────────┤
  │ marketing       │ 无时效        │ 促销/新品/召回   │ 最贵        │
  │ utility         │ 强时效        │ 物流/催单/OTP   │ 中          │
  │ authentication  │ 一次性 24h    │ 验证码/两步验证  │ 低/限量      │
  │ service (新)    │ 用户动作触发   │ 客服回执 (试验中) │ 免费/低      │
  └─────────────────┴──────────────┴───────────────┴─────────────┘

  模板结构 (Cloud API):
  ├─ name: 名称 (小写字母+下划线, 全局唯一)
  ├─ language: 语言 (如 en_US, zh_CN, zh_HK)
  ├─ category: marketing / utility / authentication
  ├─ components: 组件的有序列表
  │   ├─ HEADER: 标题(文本/图片/视频/文档/位置)
  │   ├─ BODY: 正文 (文本, 支持 {{1}} {{2}} 占位变量)
  │   ├─ FOOTER: 底部文本 (无变量)
  │   └─ BUTTONS: 按钮 (QUICK_REPLY/URL/PHONE_NUMBER/COPY_CODE)
  └─ example: 示例数据 (用于审核体验)
```

### 3.2 创建模板：meta_create_conversation_template

沿用脚本层命名约定，创建模板的方法示意：

```python
# meta_create_conversation_template.py — 创建营销模板示例
import requests
import json

GRAPH_API = "https://graph.facebook.com/v19.0"

def meta_create_conversation_template(
    waba_id: str,
    token: str,
    name: str,
    language: str,
    category: str,
    body: str,
    header_payload=None,
    buttons=None,
) -> dict:
    """创建 WhatsApp 消息模板。

    Args:
        waba_id: WhatsApp Business Account ID
        token: 系统用户访问令牌 (System User Token)
        name: 模板名称, 如 'flash_sale_coupon_v3'
        language: 语言代码, 如 'zh_CN'
        category: 'MARKETING' | 'UTILITY' | 'AUTHENTICATION'
        body: 正文, 用 {{1}} 表示占位变量
        header_payload: 可选, 头部组件媒体
        buttons: 可选, 按钮列表

    Returns:
        Meta 响应字典, 含 template name 与 status
    """
    components = []
    if header_payload:
        components.append({
            "type": "HEADER",
            "format": header_payload.get("format", "TEXT"),
            "text": header_payload.get("text", header_payload.get("example", {})),
        })
    components.append({
        "type": "BODY",
        "text": body,
        "example": {"body_text": [["京东全场 8.8 折"]]},  # 示例变量
    })
    if buttons:
        components.append({"type": "BUTTONS", "buttons": buttons})

    url = f"{GRAPH_API}/{waba_id}/message_templates"
    payload = {
        "name": name,
        "language": language,
        "category": category,
        "components": json.dumps(components),
    }
    resp = requests.post(url, params={"access_token": token}, json=payload)
    resp.raise_for_status()
    data = resp.json()
    print(f"[meta_create_conversation_template] 模板 {name} 已提交, "
          f"status={data.get('status')} id={data.get('id')}")
    return data
```

### 3.3 列出模板：meta_list_conversation_templates

```python
# meta_list_conversation_templates.py — 分页拉取全部模板
def meta_list_conversation_templates(waba_id: str, token: str,
                                     status: str = None,
                                     category: str = None) -> list:
    """列出 WABA 名下所有模板, 支持状态与类别过滤。

    Returns:
        模板列表, 每项含 id/name/language/category/status/components
    """
    url = f"{GRAPH_API}/{waba_id}/message_templates"
    params = {"access_token": token, "limit": 100}
    if status:
        params["status"] = status          # APPROVED / PENDING / REJECTED
    if category:
        params["category"] = category
    templates, cursor = [], None
    while True:
        params["after"] = cursor if cursor else None
        resp = requests.get(url, params=params)
        resp.raise_for_status()
        data = resp.json()
        batch = data.get("data", [])
        templates.extend(batch)
        paging = data.get("paging", {})
        cursor = paging.get("cursors", {}).get("after")
        if not paging.get("next") or not cursor:
            break
    return templates


def summarize_templates(templates: list) -> None:
    """按类别统计模板库存, 帮助运营决策。"""
    from collections import Counter
    by_cat = Counter(t["category"] for t in templates)
    by_status = Counter(t["status"] for t in templates)
    print("模板库存统计:")
    for cat, n in by_cat.items():
        print(f"  - {cat}: {n} 个")
    print("状态分布:")
    for st, n in by_status.items():
        print(f"  - {st}: {n} 个")


if __name__ == "__main__":
    ts = meta_list_conversation_templates(WABA_ID, TOKEN, status="APPROVED")
    summarize_templates(ts)
```

### 3.4 模板审核：死穴与踩坑

模板审核是营销自动化的**最大拦路虎**。以下是 Ryan 整理的实战经验：

**模板审核四大关键规则：**

```
1. 功能对等性 (functional equivalence)
   └─ VCF/卡片/折扣/真实品牌 等附加内容必须"可用"且与功能对等
   └─ 模板正文/按钮必须真实可用, 不夸大不虚假

2. 可读性与参数化
   └─ 不要在模板里写死时间价格 (必须用 {{1}} 占位变量)
   └─ 占位符要语义清晰: {{1}}入会礼, {{2}}优惠码, 而非 {{1}} {{2}} 无命名

3. 避免承诺/误导
   └─ "保证中奖""100%返现" 等极易被拒
   └─ 金融/医疗/博彩类内容触发更严格审查

4. 变量示例必须真实
   └─ example.body_text 里的样例要像一个真实用户收到的话
```

**meta_delete_conversation_template()** 删除不再使用的模板（避免模板库存膨胀，
也便于版本迭代）：`DELETE /{waba_id}/message_templates?name={name}`。

**踩坑与经验教训 #2（模板审核）：**

```
真实案例: 促销模板 body = "全场 5 折, 折扣码: {{1}}, 截止 {{2}}"
被拒原因: 时间用变量但没有告诉审核方这是时间戳/无示例
修正方案:
  body = "今日限时 5 折, 专享码 {{1}} 享折上折, 优惠截止 {{2}}"
  example.body_text = [["FANS88", "2026-08-15 23:59"]]
  component 变量备注: {{1}}=折扣码(字母数字), {{2}}=截止时间(YYYY-MM-DD HH:mm)
结果: 补示例与格式说明后 1 小时通过

黄金法则: 审核员看到的是"无示例的变量"最容易误判, 永远把 example 填满。
```

### 3.5 模板设计的营销最佳实践

| 模板类型 | 最佳实践 | 反面典型 |
|----------|----------|----------|
| Marketing | 单一 CTA、稀缺性话术、参数化 | 多按钮分散、无促动理由 |
| Utility | 事务+交付类、可带轻量营销尾巴 | 纯硬广滥用 utility 逃费 |
| Authentication | 只放验证码+防钓鱼说明 | 夹带营销内容（违规） |
| 按钮 | URL 按钮带追踪参数 | 长链接无 UTM |
| 频次 | 同一用户营销模板 ≤ 每周 1-2 条 | 一天多条营销触发封禁风险 |

---

## 第四部分: 自动回复机器人（Chatbot）设计

### 4.1 机器人架构：从"规则"到"人机协作"

WhatsApp 自动回复机器人的价值在于：**在 24h 窗口内承接海量高意向用户在聊**，
把人工从重复问答中解放出来，专注高价值订单。

```
┌─────────────────────────────────────────────────────────────────┐
│          WhatsApp 自动回复机器人总体架构                              │
│                                                                 │
│   用户 ──▶ WhatsApp ──▶ Cloud API ──▶ Webhook(消息事件)             │
│                                        │                        │
│                                        ▼                        │
│                              ┌──────────────────┐               │
│                              │ 消息路由器 Router  │               │
│                              │ 意图识别/关键词/按钮 │               │
│                              └──────┬───────────┘               │
│                                     │                          │
│                   ┌──────────────┬───┴─────┬────────────────┐   │
│                   ▼              ▼         ▼                ▼   │
│             ┌──────────┐  ┌─────────┐ ┌────────┐      ┌────────┐│
│             │ 常见问题   │  │ 订单查询  │ │ 人工转接 │      │ 营销联动 ││
│             │ FAQ 树    │  │ 商品/物流 │ │ 客服坐席 │      │ 优惠/复购││
│             └──────────┘  └─────────┘ └────────┘      └────────┘│
└─────────────────────────────────────────────────────────────────┘
```

### 4.2 消息接收与解析（Webhook）

接 Webhook 是所有机器人的起点。订阅 `messages` 字段并正确解密。

```python
# whatsapp_webhook.py — 消息事件接收与解析
import hashlib, hmac, json

def verify_signature(req_headers: dict, raw_body: bytes, app_secret: str) -> bool:
    """校验 Webhook 签名, 防止伪造投递。"""
    signature = req_headers.get("X-Hub-Signature-256", "")
    expected = "sha256=" + hmac.new(
        app_secret.encode(), raw_body, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(signature, expected)


def parse_message(payload: dict) -> list:
    """把 Webhook payload 解析成内部消息事件列表。"""
    events = []
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            for msg in value.get("messages", []):
                events.append({
                    "from": msg.get("from"),          # 用户手机号
                    "type": msg.get("type"),           # text/image/button/...
                    "text": msg.get("text", {}).get("body"),
                    "timestamp": int(msg.get("timestamp", 0)),
                    "message_id": msg.get("id"),
                    "previous_id": msg.get("context", {}).get("id"),
                })
            # 用户点击模板按钮也会以 button 类型消息进来
            for status in value.get("statuses", []):
                events.append({
                    "type": "status",
                    "message_id": status.get("id"),
                    "status": status.get("status"),    # delivered/read/sent/failed
                })
    return events
```

**消息类型总览（机器人需要区分处理）：**

| message.type | 含义 | 机器人处理 |
|--------------|------|------------|
| text | 自由文本 | 意图识别 / 关键词匹配 |
| image/video/audio | 多媒体 | 转人工 / 存档 |
| button | 点击模板按钮 | 触发对应流程 |
| interactive | 交互消息回复（list/reply） | 分支跳转 |
| contacts/location | 名片/位置 | 转人工 |
| order | Catalog 下单 | 触发订单流程 |

### 4.3 意图识别与 FAQ 树

对中文电商场景，机器人先做**关键词+正则**的轻量意图识别，再叠加可选的大模型兜底：

```python
# intent_router.py — 轻量意图识别
import re

INTENT_RULES = [
    ("order_status",   re.compile(r"(订单|物流|快递|发货|到哪|track)")),
    ("price_promo",    re.compile(r"(价格|折扣|优惠|券|便宜|多少|price)")),
    ("return_refund",  re.compile(r"(退货|退款|售后|投诉|换货|return)")),
    ("human_agent",    re.compile(r"(人工|客服|真人|转接|human|agent|help)")),
    ("product_inquiry",re.compile(r"(尺码|颜色|规格|配置|参数|size)")),
]

def detect_intent(text: str) -> str:
    for name, pattern in INTENT_RULES:
        if pattern.search(text):
            return name
    return "other"


def route_message(ev: dict) -> str:
    """路由: 根据意图与上下文决定机器人动作或转人工。"""
    if "human_agent" in ev.get("text", ""):
        return "escalate"
    intent = detect_intent(ev.get("text", ""))
    prior_intent = ev.get("state", {}).get("current_intent")
    return intent or prior_intent or "greeting"
```

**对话状态机（State Machine）**：把连续多轮对话建模为状态跳转。

```
状态机示例 (下单引导):
  GREETING ──▶ ASK_SKU ──▶ ASK_QTY ──▶ CONFIRM ──▶ DONE
                    ▲         │            │
                    └─────────┴────────────┘ (修改数量回跳)

状态定义:
  ┌──────────┬────────────────┬────────────────────────┐
  │ 状态      │ 触发           │ 机器人动作               │
  ├──────────┼────────────────┼────────────────────────┤
  │ GREETING │ 新用户/发"你好"  │ 欢迎语+主菜单按钮         │
  │ ASK_SKU  │ 选择商品        │ 发 Catalog 卡片         │
  │ ASK_QTY  │ 命中商品        │ 询问数量（数字校验）       │
  │ CONFIRM  │ 拿到数量        │ 复核订单+下单按钮          │
  │ DONE     │ 用户确认        │ 生成订单+推送支付链接       │
  └──────────┴────────────────┴────────────────────────┘
```

### 4.4 发送交互消息：meta_send_whatsapp_interactive

交互消息（按钮、列表、商品）是机器人承接转化的核心。沿用脚本层命名：

```python
# meta_send_whatsapp_interactive.py — 发送交互式按钮消息
def meta_send_whatsapp_interactive(
    phone_number_id: str,
    token: str,
    to: str,
    body_text: str,
    buttons: list,
    header_text: str = None,
    footer_text: str = None,
) -> dict:
    """发送带按钮的交互消息。

    buttons 示例:
      [{"type":"reply","reply":{"id":"btn_yes","title":"我要下单"}},
       {"type":"reply","reply":{"id":"btn_no","title":"再想想"}}]
    Reply Button 上限: 每消息 <= 3 个按钮。
    """
    url = f"{GRAPH_API}/{phone_number_id}/messages"
    interactive = {
        "type": "button",
        "body": {"text": body_text},
        "action": {"buttons": buttons},
    }
    if header_text:
        interactive["header"] = {"type": "text", "text": header_text}
    if footer_text:
        interactive["footer"] = {"text": footer_text}
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to,
        "type": "interactive",
        "interactive": interactive,
    }
    resp = requests.post(url, params={"access_token": token}, json=payload)
    resp.raise_for_status()
    return resp.json()


def meta_send_whatsapp_list(
    phone_number_id: str, token: str, to: str,
    body_text: str, sections: list, button_text: str = "选择",
) -> dict:
    """发送 List Message (列表选择), 适合多选项分支。
    sections = [{"title": "服务", "rows": [{"id":"r1","title":"查订单","description":"..."}]}]
    单个 List 最多 10 个 section, 每 section 最多 10 行。
    """
    url = f"{GRAPH_API}/{phone_number_id}/messages"
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "interactive",
        "interactive": {
            "type": "list",
            "body": {"text": body_text},
            "action": {"button": button_text, "sections": sections},
        },
    }
    resp = requests.post(url, params={"access_token": token}, json=payload)
    resp.raise_for_status()
    return resp.json()
```

**按钮 vs 列表选型：**

| 选择 | 场景 | 上限 |
|------|------|------|
| Reply Button | 2-3 个明确选项 | 每消息 ≤ 3 按钮 |
| List Message | 4 个以上分支/菜单 | ≤ 10 section × 10 row |
| CTA URL Button | 跳转落地页/H5 | 模板与交互均可 |
| Quick Reply（模板）| 模板内引导下文 | ≤ 10 个 |

### 4.5 人机协作：机器人阈值转人工

单纯机器人天然有兜底缺口，必须具备**成功率高时人工接管 + 兜底触发条件**：

```
转人工触发条件 (任一命中即转):
├─ 意图 = human_agent / 用户 2 次表达"人工"
├─ 机器人兜底意图 other 连续 2 轮
├─ 涉及退款/投诉/加急等高敏动作
├─ 订单金额超阈值 (如 > ¥2000)
└─ 会话进入死循环 (状态机重入 > 3 次)

转人工动作:
  1. 发一条"正在为您转接人工客服, 请稍候"的即时文本(窗口内)
  2. 把会话上下文(意图/状态/关键字段)带到客服工作台
  3. 队列内分配坐席, 人工接管后机器人暂停
```

**踩坑与经验教训 #3（机器人）：**

```
真实案例: 机器人把所有不匹配问题都回复"请问还有什么可以帮您"
结果: 用户反复问售后 → 每次都收到同一句 → 用户投诉量上升, 满意度下滑
修正:
  1. 加入"重复意图兜底": 同一意图命中 2 次直接转人工
  2. 加入"情绪识别": 出现"投诉/差评/退款"强制走人工 + 优先队列
  3. 所有未命中意图一律记录标签, 每周复盘扩充 FAQ
```

---

## 第五部分: 批量发送（群发）与合规节流

### 5.1 群发不是"群发"，是"受控批量"

很多运营把"批量发送"理解成"越越多越好"，但在 WhatsApp 商业体系里，批量发送是
**最具封号风险**的操作。核心矛盾：规模 vs 质量评分。

```
为什么不能盲目群发:
├─ 用户主动消息频率判断: 官方监测模板被"不读/快速移除/举报"
├─ 质量评分 (quality rating): 低分 → 消息触达受限 → 封号
├─ 频率上限 (throughput): 认证后 80 msg/s 起步, 按需提升
└─ 举报率: 大量不相关营销易被举报, 直接拉低账户健康度

科学群发的三本书:
  1. 先分层 (只给高意向/历史交互用户发)
  2. 再节流 (控制速率与频率)
  3. 后复盘 (跟踪打开/回复/退订)
```

### 5.2 发送单条消息：meta_send_whatsapp_message

```python
# meta_send_whatsapp_message.py — 发送单条文本/模板消息
def meta_send_whatsapp_message(
    phone_number_id: str,
    token: str,
    to: str,
    body: str = None,
    template: str = None,
    language: str = "zh_CN",
    components: list = None,
    media: dict = None,
    reply_to: str = None,
) -> dict:
    """发送 WhatsApp 消息。

    两种模式:
      - 窗口内自由文本: body 非空, template 为 None
      - 窗口外模板: template 非空 (必须是已审核模板)
    media 示例: {"type":"image","link":"https://.../a.jpg","caption":"xxx"}
    """
    url = f"{GRAPH_API}/{phone_number_id}/messages"
    payload = {"messaging_product": "whatsapp", "recipient_type": "individual", "to": to}
    if reply_to:
        payload["context"] = {"message_id": reply_to}   # 引用回复
    if template:
        payload["type"] = "template"
        payload["template"] = {
            "name": template,
            "language": {"code": language},
            "components": components or [],
        }
    elif media:
        payload["type"] = media["type"]
        payload[media["type"]] = {"link": media["link"], "caption": media.get("caption")}
    else:
        payload["type"] = "text"
        payload["text"] = {"body": body, "preview_url": True}
    resp = requests.post(url, params={"access_token": token}, json=payload)
    resp.raise_for_status()
    return resp.json()


def meta_send_whatsapp_template(
    phone_number_id: str, token: str, to: str,
    template_name: str, params: list, language: str = "zh_CN",
) -> dict:
    """发送带变量填充的模板消息 (批量群发的基本原语)。
    params 按模板 BODY 的 {{1}},{{2}} 顺序传入。
    """
    components = [
        {"type": "BODY", "parameters": [{"type": "text", "text": p} for p in params]}
    ]
    return meta_send_whatsapp_message(
        phone_number_id, token, to,
        template=template_name, language=language, components=components,
    )
```

### 5.3 批量发送引擎 + 节流

批量发送最忌讳"一把梭"。设计一个带令牌桶节流 + 失败重试 + 合规退订的引擎：

```python
# batch_sender.py — 分级节流批量发送引擎
import time, random, logging
from collections import deque

log = logging.getLogger("whatsapp_batch")


class TokenBucket:
    """令牌桶节流器: 控制每秒/每用户发送速率。"""
    def __init__(self, rate: float, capacity: int):
        self.rate = rate            # 每秒补充令牌数
        self.capacity = capacity    # 桶容量 (突发上限)
        self._tokens = capacity
        self._last = time.monotonic()

    def take(self, n: int = 1) -> bool:
        now = time.monotonic()
        self._tokens = min(self.capacity, self._tokens + (now - self._last) * self.rate)
        self._last = now
        if self._tokens >= n:
            self._tokens -= n
            return True
        return False


class BoundedBatchSender:
    """对已分层用户列表执行批量模板发送。"""

    def __init__(self, send_fn, rate: float, capacity: int):
        self.send = send_fn
        self.bucket = TokenBucket(rate, capacity)
        self.failed = deque()

    def send_all(self, targets: list, template_name: str, params_fn) -> dict:
        """targets: [{'to':..., 'consent':True}, ...]
        params_fn(user) -> 该用户的变量列表
        """
        stats = {"sent": 0, "failed": 0, "no_consent": 0}
        for user in targets:
            # 合规: 只发给已授权用户 (有 consent), 尊重退订标记
            if not user.get("consent") or user.get("unsubscribed"):
                stats["no_consent"] += 1
                continue
            # 节流: 等待令牌
            while not self.bucket.take(1):
                time.sleep(0.05)
            try:
                params = params_fn(user)
                self.send(user["to"], template_name, params)
                stats["sent"] += 1
            except Exception as exc:                     # noqa
                stats["failed"] += 1
                self.failed.append(user["to"])
                log.warning("send failed %s: %s", user["to"], exc)
                if isinstance(exc, requests.exceptions.HTTPError) and _is_rate_limited(exc):
                    time.sleep(10)   # 429/频率限流退避
        return stats


def _is_rate_limited(exc) -> bool:
    code = exc.response.status_code if exc.response is not None else None
    return code in (429, 500, 503)


# 使用示例: 分 5 批, 每批之间停 30 秒, 每次 20 条
# engine = BoundedBatchSender(meta_send_whatsapp_template, rate=20/60, capacity=20)
# for chunk in chunks(eligible_users, 1000):
#     engine.send_all(chunk, "flash_sale_v3", params_fn)
#     time.sleep(30)
```

### 5.4 节流参数与频率上限

```
认证漏斗 (Business Verification) 决定 throughput:

  未验证商家:
  ├─ 单机测试: 1 msg/s, 每分钟 15 条 (很有限)
  ├─ 可申请提升: 提交业务信息
  已验证商家:
  ├─ 标准: 80 msg/s, 每分钟 2000 条 (按业务规模浮动)
  ├─ 高吞吐: 可申请最高 ~1,000 msg/s (仅规模化客户)

  日常运营建议速率:
  ├─ 冷启动: 5-10 msg/s, 小批量灰度
  ├─ 正常营销: 20-50 msg/s 按业务评估
  └─ 大促: 需提前与 Meta 申请临时提升

  同一用户的频控 (维护健康度):
  ├─ 营销模板: 建议每周 <= 1-2 条
  ├─ 会话消息: 24h 内不受模板频控
  └─ 退订/opt-out: 必须实时生效, 一旦退订任何营销都不可发
```

### 5.5 群发的用户分层（营销视角）

群发的成败 8 成在"发给谁"，而非"怎么发"。合理分层：

```
群发对象分层模型:

  S1 高意向活跃 (近7天交互/下单)  ──▶ 主推新品+复购券   [营销模板]
  S2 历史成交 (30-90天未回购)    ──▶ 唤醒+专属折扣     [营销模板]
  S3 有过询价未成交             ──▶ 补货/逼单+答疑     [utility/service]
  S4 仅广告点击未到店           ──▶ 培养期, 轻触达      [低频]
  S5 已退订/无授权              ──▶ 不发 (合规必守)     [禁止]

  ┌─────────┬──────────────┬──────────────┬─────────────┐
  │ 分层     │ 规模占比       │ 营销频率       │ 触达目标     │
  ├─────────┼──────────────┼──────────────┼─────────────┤
  │ S1      │ ~5%          │ 周更          │ 复购率       │
  │ S2      │ ~15%         │ 双周          │ 召回率       │
  │ S3      │ ~20%         │ 事件驱动       │ 成交率       │
  │ S4      │ ~30%         │ 月更          │ 意向培育     │
  │ S5      │ ~30%         │ 禁止          │ 合规         │
  └─────────┴──────────────┴──────────────┴─────────────┘
```

**踩坑与经验教训 #4（批量群发封号）：**

```
真实案例: 某跨境卖家一次向 3 万"清洗过的历史数据库"推大促模板
结果: 大量号码是空号/停机/陌生人 → 高未送达 + 高举报 → 该 WABA 质量评分
     跌至 Low → 触达被算法限流 → 账户进入风控观察
修正:
  1. 所有群发对象必须"最近有真实交互或显式订阅", 不洗库式盲发
  2. 冷数据先做小样本(测试 100 条)看送达率/报告率再放大
  3. 设置硬止损: 单次送达失败>10% 立即暂停排查
  4. 每条营销都带"回复 STOP 退订"能力并程序化执行
```

---

## 第六部分: QR 码获客与商业资料

### 6.1 QR 码：线下/线上低成本获客入口

QR 码是连接"任意媒介 → WhatsApp 会话"的关键桥梁。用 `meta_generate_whatsapp_qr`
（脚本层命名约定）生成带参数的链接与二维码：

```python
# meta_generate_whatsapp_qr.py — 生成 wa.me 短链与二维码
import qrcode
from urllib.parse import urlencode

def wa_link(phone: str, text: str = None, source: str = None) -> str:
    """构造 https://wa.me/{phone}?text=...&source=... 链接。"""
    base = f"https://wa.me/{phone}"
    params = {}
    if text:
        params["text"] = text
    if source:
        params["source"] = source     # 追踪渠道: qr_sticker/qr_post/ad_fb...
    return base + ("?" + urlencode(params) if params else "")


def meta_generate_whatsapp_qr(phone: str, text: str, out_path: str,
                              source: str = "default") -> str:
    """生成可扫码的 WhatsApp 二维码并落盘。
    wa.me 统一格式: https://wa.me/<country_code><number>
    中国大陆号码需带国家码 86, 如 https://wa.me/8613800138000
    """
    link = wa_link(phone, text, source)
    img = qrcode.QRCode(version=None, error_correction=qrcode.constants.ERROR_CORRECT_M)
    img.add_data(link)
    img.make(fit=True)
    qr = img.make_image(fill_color="black", back_color="white")
    qr.save(out_path)
    print(f"QR 已生成: {out_path}\n链接: {link}")
    return link
```

**QR 码使用场景：**

| 媒介 | 落点 | 追踪参数 |
|------|------|----------|
| 线下货架/FM 贴纸 | 商品详情页直聊 | `source=sticker_shelf` |
| 产品外包装 | 扫码领保修/防伪 | `source=packaging` |
| 电梯/户外海报 | 加购/领取优惠券 | `source=ooh_poster` |
| 电商包裹内夹单 | 复购入口 | `source=parcel_leaflet` |
| 直播间/短视频挂链 | 私域承接 | `source=live_stream` |
| 门店桌贴 | 点单/预约 | `source=table_tent` |

**踩坑与经验教训 #5（QR）：**

```
真实案例: 把所有二维码都指向同一个 wa.me 号码, 无法区分哪个渠道进人
修正:
  1. 每个渠道一个 source 参数, 到店后落标签 (QR_渠道名)
  2. 不同渠道不同话术 (text 预填: "我在电梯广告看到...")
  3. 关键: 二维码扫描后要能稳定触发 24h 窗口的承接(自动欢迎+首次交互)
```

### 6.2 商业资料（Business Profile）

商业资料是用户点开聊天时看到的第一屏"名片"，直接影响信任与回复率。

```python
# meta_get_whatsapp_business_profile.py — 读取与更新商业资料
def meta_get_whatsapp_business_profile(phone_number_id: str, token: str) -> dict:
    """读取商业资料字段。"""
    url = f"{GRAPH_API}/{phone_number_id}/whatsapp_business_profile"
    params = {
        "access_token": token,
        "fields": "about,address,description,email,profile_picture_url,"
                  "websites,vertical,greeting,language",
    }
    resp = requests.get(url, params=params)
    resp.raise_for_status()
    data = resp.json().get("data", [])
    return data[0] if data else {}


def meta_update_whatsapp_business_profile(
    phone_number_id: str, token: str, profile: dict
) -> dict:
    """更新商业资料。
    profile 支持: description, address, email, websites, vertical, greeting
    """
    url = f"{GRAPH_API}/{phone_number_id}/whatsapp_business_profile"
    resp = requests.post(url, params={"access_token": token}, json=profile)
    resp.raise_for_status()
    return resp.json()
```

**商业资料字段速查：**

| 字段 | 用途 | 营销建议 |
|------|------|----------|
| description | 商家简介 | 一句话定位 + 卖点 + 时效福利 |
| address | 地址 | 线下门店务必填 |
| websites | 官网 | 多语言官网数组 |
| vertical | 行业分类 | 影响展示与推荐 |
| greeting | 自动招呼语 | 设置问候话术（可选变量） |
| profile_picture_url | 头像 | 品牌 logo，清晰 |
| email | 客服邮箱 | 便于售后 |

### 6.3 自动问候语与离开消息

在商业资料 + App 设置里配置 **Greeting（问候语）** 和 **Away Message（离开消息）**，
是第一层"无人值守接待"：

```
自动问候最佳实践:
├─ 首次进入: "您好, 我是 XX 的智能助手小 Wa 🌟 请问想了解新品/优惠/售后?"
├─ 用变量问候: 可设 {{1}}=星期, {{2}}=时间个性化
├─ 离开消息: 营业时间外 + 非工作时段自动回复
│   ├─ "感谢留言! 现在是休息时间 (10:00-22:00 在线), 我们会在上班第一时间回复"
│   └─ 重要: 离开消息回复后要能保持窗口 / 引导留下问题
└─ 集成: 问候语触发即进入 Chatbot 状态机入口
```

---

## 第七部分: Click-to-WhatsApp 广告落地

### 7.1 从广告到会话的转化链路

Click-to-WhatsApp（点击直达 WhatsApp）是拉新 → 私域承接的核心桥梁，也是
WhatsApp 营销自动化的"流量入口侧"。

```
Click-to-WhatsApp 链路:

   FB/IG 广告 (Click to WhatsApp 目标)
      │  用户点击 "发消息" CTA
      ▼
   WhatsApp 打开预填文本 (可选预填话术)
      │
      ▼
   Cloud API Webhook 收到新消息事件 (from=用户)
      │   ← 这时开启 24h 服务会话窗口 (窗口免费!)
      ▼
   Chatbot 首次响应: 欢迎语 + 承接流程
      │
      ▼
   自动化: 打标签 / 记录广告归因 / 分发优惠券
```

**关键洞察：** 用户点击 CTA 本身就会开启 24h 窗口。**窗口内能发自由文本（免费）**，
所以广告带来的新会话是"黄金窗口"——第一分钟内的承接质量决定转化。

### 7.2 广告归因与参数传递

Click-to-WhatsApp 广告的难点在于**归因**：要能回答"这个会话从哪条广告来"。

```
归因方案对比:
  ├─ Meta 侧: 广告报表提供 "Card" / "Clicks" 归因
  │   └─ 用 WhatsApp 会话数 / 新增会话数作为转化目标 (CTWA 事件)
  ├─ 链路参数: 预填文本带追踪参数进入会话
  │   └─ 如 "text=想了解【pro_id:sku999】的优惠"
  └─ 唯一识别: 通过 message 上下文 + 会话创建时间戳关联广告

  推荐: 以 "WA 新会话数" 和 "会话→成交" 两项指标看 CTWA 全程 ROAS
```

### 7.3 CTWA 广告落地 checklist

```
Click-to-WhatsApp 广告落地七步清单:
┌── 1. 确认广告目标支持 CTWA
│     ├─ 主目标: Leads(线索) / Messages / Sales
│     └─ 展示位置: Facebook / Instagram / Messenger / WhatsApp
├── 2. 关联正确的 WABA + 电话号码
│     └─ 确保电话号码已是已验证商家商业号码
├── 3. 制作高转化创意 (首帧即戳需求)
│     ├─ 前 3 条 demo 用语给用户"点开即享"的理由
│     └─ 预填文本 (prefilled text) 引导用户主动打招呼
├── 4. 配置转化事件 (CAPI / 像素 / CTWA 转化)
│     └─ 把所有"会话开始/成交"回传, 供自动出价优化
├── 5. 承接机器人上线后再放量 (关键!)
│     └─ 没有机器人兜底之前先小预算测接待质量
├── 6. 埋点归因 + 分流实验 (A/B 话术/创意/落地承接)
│     └─ source 参数区分广告 vs 自然流量
└── 7. 冷启动节奏: 小预算 → 看会话成本 → 逐步放量
```

**踩坑与经验教训 #6（CTWA）：**

```
真实案例: 广告预算很高但"会话→下单"极低
诊断: 广告把用户带进 WhatsApp 后, 没有及时承接, 用户等 10 分钟没回复就走了
修正:
  1. 广告放量前必须配置自动回复机器人(秒回)
  2. 冷启动阶段客服人力值守高意向时段
  3. 用 "会话开启后 60 秒内机器人首响" 作为 SLA 指标
  4. 广告预填文本里给出明确下一步, 降低用户决策成本
```

### 7.4 会话 → 成交的承接策略

广告带来的高意向会话，要用**漏斗式承接**最大化成交：

```
CTWA 会话承接漏斗:

  进入会话 (100%)
   │  首响 < 30s + 提取需求
   ▼
  命中商品/服务 (60-80%)
   │  Catalog 卡片 + 实时报价
   ▼
  意向确认 (30-50%)
   │  提供优惠 / 逼单 / 稀缺
   ▼
  支付转化 (15-30%)
   │  支付链接 / 转账引导 / 订单确认
   ▼
  追加销售 (10-20%)
   │  关联推荐 + 复购券

每层的关键动作都应当自动化 (机器人) + 关键节点人工兜底。
```

---

## 第八部分: 客户留存与复购策略

### 8.1 留存不是"发消息"，是"经营关系"

WhatsApp 留存的核心不是群发轰炸，而是**在正确时机用正确语义触达**。

```
WhatsApp 留存杠杆图谱:
  ├─ 订单后 (咸鱼变朋友): 发货/物流/好评引导
  ├─ 生命周期: 新客培育 → 首购 → 复购 → 沉睡唤醒
  ├─ 事件驱动: 补货/降价/生日/会员日
  ├─ 会员体系: 积分/等级/专属价 沉淀在会话里
  └─ 沉默预警: 90 天未交互 → 分层唤醒

  ┌──────────────┬───────────────────┬──────────────────┐
  │ 阶段          │ 触达内容           │ 频率/渠道         │
  ├──────────────┼───────────────────┼──────────────────┤
  │ 新客 0-7 天    │ 欢迎+首单券+使用指南 │ 密集培育(有授权)   │
  │ 复购 30 天内   │ 复购提醒+关联推荐    │ 事件驱动           │
  │ 沉睡 31-90 天  │ 召回+专属折扣       │ 双周低频           │
  │ 流失 >90 天    │ 大额召回+调研       │ 月更, 谨慎         │
  └──────────────┴───────────────────┴──────────────────┘
```

### 8.2 事件驱动的自动化触发（留存核心）

保留的核心是**事件驱动**而非定时群发。以下是留存自动化的事件触发表：

| 触发事件 | 自动化动作 | 消息类型 |
|----------|------------|----------|
| 用户下单成功 | 发送订单确认 + 预计发货日 | utility 模板 |
| 物流状态更新 | 推送物流轨迹 + 收货提醒 | utility 模板 |
| 发货后 N 天未确认 | 询问体验 + 求好评 | utility/service |
| 购物车滞留 | 窗口内补全引导 + 优惠 | service（若窗口内）|
| 会员等级临近 | 升级提醒 + 冲刺目标 | marketing 模板 |
| 生日/周年 | 生日券 + 专属祝福 | marketing 模板 |
| 补货到货 | 缺货登记用户提醒 | utility 模板 |
| 沉唤醒 90 天 | 大额召回 + 调研 | marketing 模板 |

### 8.3 好评与口碑裂变

```
好评/裂变策略:
  ├─ 旺好评: 售后满意后引导"方便给我们一个好评吗" (带链接)
  ├─ 晒单有礼: 鼓励晒单截图 → 返券/抽奖
  ├─ 邀请裂变: 老带新 → 双方得券 (通过 wa.me 专属邀请链接)
  ├─ 社群运营: 建 VIP 群 (需满足群组件/群邀请规则)
  └─ 复购激励: 满额赠券 / 会员积分在会话里沉淀

裂变链接: 每个老客一个专属邀请链接 + 追踪 (code=uid123)
  首次受邀用户授权后打上"来自 uid123" 标签, 用于归因返利
```

### 8.4 退订与合规（留存的反面）

```
退订/合规底线:
├─ 每条营销模板必须让用户能轻松退订
│   └─ 按钮 "回复 STOP 退订" 或模板内退订入口
├─ 用户回复 STOP/退订 → 程序化拉黑此用户, 不再发营销
├─ 保留 24h 服务能力: 退订仅停营销, 事务类(物流)仍可发
├─ 数据: 用户授权记录 / 退订时间要入库可审计
└─ 隐私: 遵守 GDPR/个保法, 获取 explicit consent 再营销

opting-out 处理伪代码:
  if msg.text.upper() in ("STOP","退订","UNSUBSCRIBE"):
      mark_unsubscribed(user)
      meta_send_whatsapp_message(..., body="好的, 已为您退订营销推送, 感谢关注!")
      return  # 不再进入营销队列
```

---

## 第九部分: 营销自动化工作流设计（总纲）

### 9.1 一站式架构总览

把以上能力组装成完整营销自动化工作流：

```
┌──────────────────────────────────────────────────────────────────────┐
│            WhatsApp 营销自动化工作流 (端到端)                             │
│                                                                      │
│  [获客层]                                                            │
│  CTWA 广告 ──▶ Click-to-WhatsApp ──▶ wa.me QR / 外链 ──▶ 自然搜索      │
│       │              │                     │                          │
│       └──────────────┴─────────┬───────────┘                          │
│                                ▼                                      │
│  [承接层]  Cloud API Webhook ──▶ Chatbot (意图/状态机) ──▶ 打标签/建档    │
│                                │                                      │
│                                ▼                                      │
│  [转化层]   Catalog 商品 ─▶ 报价/逼单 ─▶ 支付链接 ─▶ 订单闭环(ERP 回写)    │
│                                │                                      │
│                                ▼                                      │
│  [留存层]   事件驱动 ─▶ 物流/好评/复购券 ─▶ VIP 会话 ─▶ 沉睡唤醒           │
│                                │                                      │
│                                ▼                                      │
│  [数据层]   会话指标/归因/ROAS/质量评分 ─▶ 报表 ─▶ 优化迭代 (小步快跑)      │
└──────────────────────────────────────────────────────────────────────┘
```

### 9.2 工作流引擎设计（编排伪代码）

把上述环节编排成一个可运行的工作流引擎：

```python
# whatsapp_marketing_workflow.py — 营销自动化工作流编排
from dataclasses import dataclass, field
from enum import Enum


class Stage(Enum):
    ACQUIRE = "acquire"      # 获客
    ONBOARD = "onboard"      # 承接建档
    CONVERT = "convert"      # 转化
    RETAIN = "retain"        # 留存
    REACTIVATE = "reactivate"  # 唤醒


@dataclass
class Conversation:
    uid: str
    phone: str
    tags: set = field(default_factory=set)
    stage: Stage = Stage.ONBOARD
    state: str = "GREETING"
    context: dict = field(default_factory=dict)


class WhatsAppMarketingWorkflow:
    """编排各模块的营销自动化工作流。"""

    def __init__(self, send_fn, profile_fn, qr_fn):
        self.send = send_fn
        self.get_profile = profile_fn
        self.make_qr = qr_fn
        self.conversations: dict[str, Conversation] = {}

    # ---------- 获客层 ----------
    def on_new_lead(self, ev: dict) -> Conversation:
        """CTWA/QR 带来的新会话: 建档 + 最高优先级承接。"""
        conv = Conversation(uid=ev["from"], phone=ev["from"])
        conv.tags.add("lead_new")
        self.conversations[conv.uid] = conv
        # 首响: 秒回欢迎 + 提取意图
        self.send(conv.phone, body="您好! 我是智能助手小 Wa, 请问想了解哪款产品? 🛒")
        conv.state = "GREETING"
        return conv

    # ---------- 承接层 ----------
    def handle_message(self, ev: dict) -> None:
        conv = self.conversations.get(ev["from"])
        if not conv:
            conv = self.on_new_lead(ev)
        intent = detect_intent(ev.get("text", ""))
        conv.context["last_intent"] = intent
        # 意图分派
        if intent == "order_status":
            conv.state = "ORDER_STATUS"
            self.send(conv.phone, body="正在为您查询订单, 请稍候 🚚")
            self.query_order(conv)
        elif intent == "price_promo":
            conv.state = "PROMO"
            self.send(conv.phone, body="专享优惠来啦 👉 领取专属券 {{券码}}(demo)")
        elif intent == "human_agent":
            self.escalate(conv)
        else:
            self.send(conv.phone, body="您说的是想了解这个吗? 点击下方按钮选择 ⬇️")
            self.send_interactive(conv)

    # ---------- 转化层 ----------
    def query_order(self, conv: Conversation) -> None:
        """对接 ERP/订单系统查询, 回写状态。"""
        order = self.erp_lookup(conv.phone)
        if order:
            conv.stage = Stage.CONVERT
            self.send(conv.phone, body=f"您的订单 {order['no']} 已 {order['status']} 📦")
        else:
            self.send(conv.phone, body="未查询到订单, 已为您转接人工客服 😊")
            self.escalate(conv)

    # ---------- 留存层 ----------
    def on_order_done(self, uid: str) -> None:
        """下单成功触发: 发物流引导 + 求好评 + 复购券(事件驱动)。"""
        conv = self.conversations.get(uid)
        if conv is None:
            return
        conv.stage = Stage.RETAIN
        # utility 模板: 发货通知 + 尾随营销
        self.send_template(conv.phone, "order_shipment", params=["快递单号"])
        # 72h 后满意度 + 复购券 (营销模板, 受频控)
        self.schedule(conv.phone, delay_h=72, action=self.send_repurchase_coupon)

    def send_repurchase_coupon(self, phone: str) -> None:
        if self.is_unsubscribed(phone):
            return
        self.send_template(phone, "repurchase_coupon_v2", params=["FANS50"])

    # ---------- 唤醒层 ----------
    def reactivate_sleeping(self) -> None:
        """每周末对 90 天未交互用户做唤醒 (分层, 节流, 合规)。"""
        eligible = [u for u in self.users if u.last_active < now - 90 * 86400
                    and u.consent and not u.unsubscribed]
        for batch in chunks(eligible, 1000):
            for u in batch:
                self.send_template(u.phone, "reactivate_gift_v1", params=[u.gift])
            self.sleep(30)     # 批次间隔, 控制速率

    # ---- 工具方法占位 (与外部系统对接) ----
    def escalate(self, conv): ...
    def send_interactive(self, conv): ...
    def erp_lookup(self, phone): ...
    def schedule(self, phone, **kw): ...
    def is_unsubscribed(self, phone): ...
    def sleep(self, s): ...
    def chunks(self, seq, n): ...
```

### 9.3 完整部署清单（从 0 到 1）

```
WhatsApp 营销自动化从 0 到 1 部署清单:
┌── Phase 0: 基础设施
│   ├─ 注册 Business Manager + 创建 WABA
│   ├─ 申请 Business Verification (营业执照/域名验证)
│   ├─ 认证电话号码 + 获取 Phone Number ID
│   └─ 创建系统用户 (System User) + 长期令牌
├── Phase 1: 模板与资料
│   ├─ 设计首批模板 (marketing/utility/authentication)
│   ├─ 提交审核 + 用 example 填满变量
│   ├─ 配置商业资料 (描述/头像/网站/问候)
│   └─ 上线自动问候 + 离开消息
├── Phase 2: 机器人
│   ├─ 接 Webhook 收消息事件
│   ├─ 实现意图识别 + 状态机 (FAQ/订单/优惠/转人工)
│   ├─ 接 Catalog 商品卡片 + 交互按钮
│   └─ 压测: 并发 TPS, 转人工阈值
├── Phase 3: 批量群发
│   ├─ 用户分层 (S1-S5) + consent/退订管理
│   ├─ 实现令牌桶节流 + 失败重试
│   └─ 小样本灰度验证送达率/报告率再放量
├── Phase 4: 获客
│   ├─ 上线 Click-to-WhatsApp 广告 (Lead/Messages 目标)
│   ├─ 配置 QR 码多渠道 (source 追踪)
│   └─ 埋点归因 + 会话→成交漏斗看板
└── Phase 5: 留存优化
    ├─ 事件驱动自动化 (订单/物流/好评/复购)
    ├─ 沉睡唤醒 + 裂变邀请
    └─ 周报复盘: 会话成本 / 转化率 / 质量评分 / 退订率
```

### 9.4 指标看板（Marketing KPI）

```
WhatsApp 营销自动化核心指标:
  ├─ 获客: 会话成本 / 新会话数 / 触发来源分布 (CTWA/QR/自然)
  ├─ 承接: 首响耗时 (P95) / 机器人自助解决率 / 转人工率
  ├─ 转化: 会话→成交率 / 客单价 / 会话 ROAS / 支付放弃率
  ├─ 留存: 复购率 / 激活率 / 流失率 / 唤醒响应率
  ├─ 质量: 质量评分 (green/yellow/red) / 举报率 / 退订率
  └─ 成本: 会话单价 / 单成交获客成本 (CPA) / 单位经济 (LTV/CAC)

  北极星指标建议: "月有效会话→成交 GMV" 
  辅助风控: 质量评分必须 >= 绿色, 否则触达被限.

  公式速记:
    会话成本 = 广告花费 / 新增会话数
    会话转化率 = 会话成交数 / 会话总数
    会话ROI = (成交GMV - 会话/广告成本) / 会话/广告成本
    CAC = 广告花费 / 新客户数
    LTV = 客单价 × 年购买次数 × 客户年限
    LTV/CAC > 3 为健康; 1-3 需优化; <1 加快偏离
```

### 9.5 常见问题排查（Troubleshooting）

| 症状 | 可能原因 | 排查动作 |
|------|----------|----------|
| 模板一直 PENDING | 审核积压 / 组件不合规 | 查 component 结构, 补 example, 联系支持 |
| 消息发不出 | 模板未审核 / 号码未认证 / 频率限流 | 校验状态 + 看 error code (131026 等) |
| 高失败送达 | 号码无效 / 质量评分低 | 清洗数据库, 检查质量评分 |
| 24h 触发可疑 | 会话窗口理解偏差 | 查 Webhook 状态事件 + 计费明细 |
| 收不到 Webhook | 订阅字段缺失 / 签名失效 | 校验订阅 messages, 签名算法 |
| 机器人答非所问 | 意图规则覆盖不足 | 加兜底 + 转人工 + 复盘扩充 |
| 广告没转化 | 承接慢 / 落地承接差 | 秒回 SLA, 预填文本, 漏斗优化 |
| 被封/限流 | 群发过猛 / 举报率高 | 停群发, 降频, 拉高质量号码 |

---

## 第十部分: 自测题与总结

### 10.1 自测题

**Q1.** WhatsApp Business API 中，商家在"24 小时服务会话窗口"之外，能对用户
发送什么样的消息？

<details><summary>答案</summary>

窗口外只能发送**已审核的消息模板（Message Template）**，且模板按
marketing / utility / authentication 分类计费。窗口内（用户 24h 内主动动作
触发）可发送任意自由文本、媒体与交互消息，且免费。因此营销自动化必须合理
利用窗口 + 模板双轨。
</details>

**Q2.** 为什么批量群发会造成 WABA 质量评分下降乃至封号？请列出至少三项
可操作的降险措施。

<details><summary>答案</summary>

风险源于：① 向无效/陌生号码盲发导致高未送达与高举报率；② 营销过于频繁
触发隐私反感；③ 未及时处理退订。可操作措施：① 先分层（S1-S5）只给有
授权/近交互用户发；② 用令牌桶节流控制速率并分批灰度，设硬止损（单次
失败>10% 暂停）；③ 每条营销带退订能力并程序化执行；④ 冷数据先小样本
看送达率/报告率再放大。
</details>

**Q3.** 一个 marketing 模板被拒审，常见原因有哪些？审核前应检查什么？

<details><summary>答案</summary>

常见原因：正文写死价格/时间而不是用 {{1}} 参数化；变量无语义、example
未填；内容夸大承诺（"保证中奖"）；医疗/金融等敏感类别；按钮/链接不可用。
审核前检查：component 结构正确、每个变量有 example 示例、话术合规真实、
按钮有效、类别（marketing/utility/authentication）选择正确。
</details>

**Q4.** 请描述 Click-to-WhatsApp 广告带来的新会话与自然会话在处理上的关键
区别，以及为什么广告会话必须"秒回承接"。

<details><summary>答案</summary>

点击 CTA 本身即开启 24h 服务会话窗口（窗口内自由消息免费）。区别在于广告
会话是高意向付费流量（每会话有广告成本），若承接慢，用户离开就造成广告费
浪费。必须让自动回复机器人在 60 秒内首响，提取需求、发 Catalog/报价、
逼单成单，从而把每会话成本摊薄成成交 ROI。归因上还需通过 source/预填文本
区分广告与自然流量。
</details>

**Q5.** 简述完整 WhatsApp 营销自动化工作流包含哪些"层"，并给出北极星指标建议。

<details><summary>答案</summary>

获客层（CTWA/QR/自然）→ 承接层（Webhook + Chatbot 建档/意图）→ 转化层
（Catalog/报价/支付/订单闭环）→ 留存层（事件驱动物流/好评/复购券）→
唤醒层（沉睡召回/裂变）→ 数据层（会话/归因/ROAS/质量评分）循环优化。
北极星指标建议用"月有效会话→成交 GMV"，配合质量评分（须绿色）与
LTV/CAC 作为健康度护栏。
</details>

### 10.2 避坑速查表（踩坑汇编）

```
本期踩坑 TOP 清单:
  ├─ 24h 窗口: 窗口外只能发模板, 别指望自由文本群发
  ├─ 模板审核: 变量必须填 example, 否则审核员误判被拒
  ├─ 批量群发: 盲发→高举报→评分跌→限流封号, 必须先分层+节流
  ├─ QR 码: 每个渠道一个 source 追踪, 别共用裸链接
  ├─ CTWA: 广告放量前先上机器人秒回承接, 否则高成本流失
  ├─ 机器人: 无兜底=死循环, 重复意图/高敏动作必须转人工
  ├─ 留存: 事件驱动>定时群发, 先获授权后营销
  └─ 合规: STOP 退订程序化执行 + consent 可审计
```

### 10.3 结语

WhatsApp 不是又一个"群发工具"，而是**私域营销的最高触达 + 高转化通道**。
营销自动化的成败，关键在三条主线：

1. **懂规则** —— 会话窗口、模板、计费、节流是合规底座；
2. **会承接** —— 机器人 + 人工兜底 + 秒回 SLA 决定转化；
3. **善经营** —— 事件驱动留存 + 分层群发 + 指标复盘决定增长。

本笔记从原理到编码、从踩坑到工作流，给出了 WhatsApp 营销自动化的完整地图。
后续可在此基础上扩展：WhatsApp Catalog 深度、社群/群组件、本地部署
On-Prem 迁移、以及与 Meta 广告/CAPI 的联合增量分析等专题。

---

> 本文档为 meta-07 day-by-day 学习笔记，聚焦 WhatsApp 营销自动化与工作流设计。
> 方法名（meta_*）沿用脚本层命名约定用于串联逻辑示例，具体 API 以 Meta 官方文档为准。
