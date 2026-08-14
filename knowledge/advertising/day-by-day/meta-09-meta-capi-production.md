# CAPI 生产环境部署深度学习笔记

> 创建日期: 2026-08-14
> 作者: Ryan
> 定位: 资深专家级 — CAPI 生产落地
> 前置阅读: meta-05-meta-ads-api-advanced.md（API 基础）、capi-deep-dive.md（CAPI 深度全链路解析）

---

## 学习路线图（Day-by-Day）

```
Day-09 主题: CAPI 生产环境部署

┌─────────────────────────────────────────────────────────────────────┐
│  Day 9.1  原理层   CAPI 为什么存在 / S2S 事件为何要自建            │
│  Day 9.2  发送层   事件哈希、签名、发送管线、幂等键                 │
│  Day 9.3  架构层   队列 + 重试 + 幂等 + 去重 的生产级后端           │
│  Day 9.4  协同层   Pixel 双通道 / event_source 优先级              │
│  Day 9.5  质量层   Test Events / Event Quality / 匹配率监控         │
│  Day 9.6  上线层   Checklist / 灰度 / 回滚 / 案例                   │
└─────────────────────────────────────────────────────────────────────┘

本笔记定位: 介于「capi-deep-dive.md（全链路深度指南）」与「业务落地」之间
的学习总结视角。相比指南，这里强调:
  1. 生产部署流程（环境、灰度、回滚）而非 API 字段罗列
  2. 后端架构形态（队列、重试、幂等）而非单次发请求
  3. 学习脉络与心得（每个 Part 结尾有「我的体会」）
  4. 踩坑记录与上线 Checklist（可直接抄作业的工作流）
```

---

## 第一部分：认识 CAPI 生产部署的真实战场

### 1.1 从「发事件」到「生产部署」的思维切换

很多人在学习 Conversion API 时，最大的误区是把它当成"调一个接口、发一个
事件"就完成任务。真正到了生产环境，事情完全不是这样：

```
学习阶段（Demo）:                     生产阶段（Production）:
─────────────────────                ─────────────────────────
meta_send_capi(...)                  meta_send_capi(...) 只是冰山一角
1 次 POST 请求                       ├─ 每秒成百上千事件
print(response)                      ├─ 网络抖动、超时、429 限流
单机脚本 ctrl+C 能停                  ├─ 服务重启、进程崩溃、机器宕机
数据量小无压力                        ├─ 重复发送导致转化重复记账
---------------------------------    ├─ 哈希要稳定、Token 要轮换
关键差异:                              ├─ 幂等键要全局唯一
"发送" 是功能实现                      └─ 要监控匹配率、去重率、送达率
"部署" 是工程系统
```

一句话：**CAPI 生产部署 = 把"发事件"这件事变成一套可靠、可观测、可回滚、
可幂等的分布式系统。** 后面所有 Part 都是围绕这句话展开。

### 1.2 CAPI 为什么必须存在（客户视角的业务动因）

从业务视角，自建 CAPI 的目的通常是由几个现实压力一起推出来的：

```
第 1 个压力: 浏览器端丢数据
└─ ITP (Intelligent Tracking Prevention)、ETP、广告拦截器
   → Pixel 在浏览器里丢 20%~50% 的事件
   → 广告优化缺数据 → 学习阶段不稳定

第 2 个压力: iOS 14.5+ ATT 限制
└─ IDFA 获取率暴跌（很多 App < 50%）
   ├─ 归因困难
   └─ Aggregated Event Measurement 限制 8 个事件

第 3 个压力: 合规与第一方数据诉求
└─ 更细的用户信息（email、phone）不能直接放浏览器
   └─ 必须走服务器端、加密、受控的通道

第 4 个压力: 时效性
└─ 服务器端可以拿到「支付成功」「下单」等强购买信号
   └─ 但浏览器未必能拿到，或用回传慢
```

**核心结论（我的体会）**：CAPI 不是"替代 Pixel"，而是"补回浏览器丢的，
并让服务器端能表达更强、更可信的转化信号"。生产部署时始终要记住这一点——
部署的**价值锚点**是"数据完整性 + 信号强度"，而不是"多发了多少条"。

### 1.3 Conversions API 生产架构总览（先建立全局图景）

在看任何细节之前，先用一张 ASCII 架构图把自己"挂"进全局：

```
┌────────────────────────── 业务侧（你自己的系统）─────────────────────────┐
│                                                                        │
│  用户行为事件流                                                        │
│  (下单/支付/注册/加购...)                                                │
│     │                                                                  │
│     ▼                                                                  │
│  ┌────────────────────┐     ┌──────────────────────────────────────┐  │
│  │  事件采集层         │     │          CAPI 后端服务 (你的)           │  │
│  │  - App / Web SDK   │ ──► │  - 哈希/归一化                         │  │
│  │  - 业务中间件       │     │  - 校验 (meta_validate_event_data)     │  │
│  └────────────────────┘     │  - 入队 (Queue)                        │  │
│                            │  - 幂等键 (Idempotency Key)             │  │
│                            │  - 重试/退避/去重                        │  │
│                            │  - 发送 (meta_send_capi / _batch)       │  │
│                            └───────────────┬──────────────────────┤  │
│                                            │ HTTPS / Graph API      │  │
└────────────────────────────────────────────┼──────────────────────────┘
                                             ▼
                                   ┌─────────────────────┐
                                   │   Meta 服务器         │
                                   │  /{pixel}/events      │
                                   │  归因、去重、建模       │
                                   └─────────────────────┘
                                             │
                                             ▼
                                   ┌─────────────────────┐
                                   │  Events Manager      │
                                   │ 测试事件/事件质量/匹配率 │
                                   └─────────────────────┘
```

这张图是全文的"骨架"。下面每个 Part 都是在给这张图"填肉"。

---

## 第二部分：Server-to-Server 事件发送原理

### 2.1 什么是 Server-to-Server（S2S）事件发送

CAPI 的本质是：**你的服务器**直接把事件 HTTPS POST 到
`https://graph.facebook.com/v{version}/{pixel_id}/events`，
不经过浏览器，不依赖客户端 JavaScript。

```python
# 示意：一次最朴素的 CAPI 发送（生产会做大量包装，见后续 Part）
import requests

def raw_send(pixel_id: str, token: str, event: dict) -> dict:
    url = f"https://graph.facebook.com/v20.0/{pixel_id}/events"
    payload = {
        "data": [event],
        "access_token": token,
    }
    resp = requests.post(url, json=payload, timeout=10)
    return resp.json()
```

与 Pixel 的区别（一张表讲清楚）：

| 维度 | Pixel（浏览器端） | CAPI（服务器端） |
|------|------------------|------------------|
| 位置 | 浏览器 JS 脚本 | 你的服务器 |
| 受浏览器限制 | 受影响（ITP/拦截器） | 不受影响 |
| 数据信任度 | 客户端可篡改 | 服务器端更可信 |
| 可用字段 | 受限 | 更全（可含 email/phone） |
| 适用 | Web 站 | Web + App 服务端事件 |
| 时效 | 即时 | 可缓冲/批量/重试 |
| 生产职责 | 前端埋点 | 后端可靠性系统 |

### 2.2 用户数据哈希（PII → SHA-256）原理

Meta 要求 PII（如 email、phone、first name）在发送前**必须哈希**。
原因：不让明文 PII 进入 Meta 系统，同时支持跨设备匹配。

```
哈希规则（必须严格遵守，否则匹配不上）:
┌────────────────────────────────────────────────────────────┐
│ 1. 小写化:      Ryan@Mail.com  → ryan@mail.com             │
│ 2. 去除首尾空格: " ryan@mail.com " → "ryan@mail.com"        │
│ 3. phone 归一化: 去掉 + - ( ) 空格                            │
│    +86 138 1234 5678 → 8613812345678                          │
│ 4. SHA-256 (hex, 小写, 64 位)                               │
│    sha256("ryan@mail.com".encode()) → f6f8...               │
└────────────────────────────────────────────────────────────┘
```

**生产注意点（踩坑）**：哈希规则不一致是"匹配率惨不忍睹"的头号原因。
同一个邮箱，前端 JS SDK 有一套归一化逻辑，你自己写服务端又写一遍，两边
算法略有差异 → 同一个用户在前端和后端哈希出**不同的值** → Meta 无法去重、
无法归因。生产务必：**同一套归一化函数在所有通道复用**。

```python
import hashlib
import re

def sha256_hex(value: str) -> str:
    """按 Meta 规范对 PII 做 SHA-256。"""
    normalized = normalize_pii(value)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

def normalize_pii(value: str) -> str:
    value = value.strip().lower()
    # phone: 去掉 + - ( ) 空格，仅保留数字
    if re.search(r"[0-9]", value):
        value = re.sub(r"[^0-9]", "", value)
    return value

def build_user_data(email: str, phone: str = None, fbp: str = None) -> dict:
    """组装 user_data，生产环境用 meta_validate_event_data 二次校验。"""
    user_data = {"em": [sha256_hex(email)]}
    if phone:
        user_data["ph"] = [sha256_hex(phone)]
    if fbp:
        user_data["fbp"] = fbp          # fbp 不哈希，直接从 cookie 取
    return user_data
```

### 2.3 关联 ID：event_id 与 event_source_url

生产发送时，两个字段至关重要：

```
event_id:             事件唯一标识（幂等键，去重核心，见第三/五部分）
event_source_url:     事件发生的页面 URL（辅助归因、校验浏览器端与 CAPI 是否同源）
event_source:         事件来源标签，如 "website" / "app" / "business_platform"
```

```python
def build_event(event_name: str,
                user_data: dict,
                custom_data: dict,
                event_time: int,
                event_id: str,
                action_source: str = "website") -> dict:
    """构造一个完整、可供发送的 CAPI 事件对象。"""
    return {
        "event_name": event_name,               # 如 Purchase
        "event_time": event_time,               # unix 时间戳
        "event_id": event_id,                    # 幂等键（全局唯一）
        "user_data": user_data,                  # em/ph/fbp/...
        "custom_data": custom_data,              # value, currency, content_ids...
        "action_source": action_source,
        "event_source_url": f"https://shop.example.com/checkout",
    }
```

### 2.4 发送管线：从「裸 POST」到「生产级发送」

前面 `raw_send` 太简陋。生产级发送（用脚本里的 `meta_send_capi`）至少要做
这几件事（详见第五部分的队列/重试/幂等，这里先建立直觉）：

```python
# 抽象：生产级发送管线的「心智模型」，本笔记第五部分会给出完整落地代码
def production_send_flow(event: dict) -> None:
    1. 校验        meta_validate_event_data(event)        # 字段合法性
    2. 幂等键       确保 event["event_id"] 全局唯一
    3. 入队         推入 worker/队列，不在请求线程里同步发送
    4. 分片/批量    meta_send_capi_batch(...)             # 合并批处理
    5. 带重试       429/5xx → 指数退避重试
    6. 幂等去重     落库 event_id，防止重复记账
    7. 观测         计指标：成功率/延迟/去重率/匹配率
```

**我的体会**：千万别为了"简单"而把发送逻辑塞进业务请求里同步等返回。
生产 CAPI 的正确姿势是**异步管道**：业务只要"确认入队成功"就返回，真正
发送交给后台 worker。这样业务请求快、不背锅，发送失败可控可重试。

### 2.5 发送频率与限流（Rate Limit / Throttling）

Meta 对不同 Pixel 有速率和规模的限制，生产必须理解：

```
限流分层:
├─ 每像素每秒事件上限（会随授权规模变化）
├─ 单次请求 data 数组长度限制（batch 上限，典型 1000 条）
├─ 429 响应: 触发限流 → 必须退避，不能硬刷
├─ 4xx 业务错误: 永久失败 → 记录，不重试

处理策略:
├─ Eager 批处理合并多条事件（meta_send_capi_batch）
├─ 分布式限流（令牌桶）避免瞬时打爆
├─ 429 → 指数退避 + Jitter（后面给实现）
└─ 永久错误 → 死信队列（DLQ）人工排查
```

这里先点一句：**限流不是"坏事"而是"保护"**。遵守它，Meta 会给你更大额度；
无视它，反而被风控。生产部署要把限流考虑进去，而不是上线后被 429 打醒。

---

## 第三部分：事件匹配与去重

### 3.1 事件匹配（Matching）是怎么回事

Meta 收到事件后，要把它「匹配」到某个真实用户（用于归因、建模）。
匹配靠 `user_data` 里的指纹字段：

```
匹配指纹字段（按强度大致排序）:
├─ em        (email)             — 最强、最常用
├─ ph        (phone)             — 强
├─ fn / ln   (first/last name)   — 强（通常配合 ge 等）
├─ external_id                   — 你自己的用户 ID（外部 ID）
├─ ct / st / zip                 — 弱
├─ fbp / fbc                     — 浏览器 cookie，介于强弱之间
├─ client_ip_address / client_user_agent — 辅助匹配
└─ app 侧: anon_id / madid / device_id 等
```

`meta_list_matched_fields`（读匹配字段）在生产里常用来**核对**：

```python
def inspect_matched_fields(pixel_id: str) -> list:
    """拉取当前可用的匹配字段，确认 user_data 覆盖度（示意）。"""
    fields = client.meta_list_matched_fields(pixel_id)   # 脚本方法
    for f in fields:
        print(f"{f['name']:<20} enabled={f.get('enabled')}")
    return fields
```

**匹配率 = 能匹配上的事件 / 总事件**。生产必须有这个指标的仪表盘，匹配率
过低说明 user_data 不够、或哈希规则错了。

### 3.2 事件去重（Dedup）的核心：EventID

当同一个事件既被 Pixel 发、又被 CAPI 发（双通道，见第六部分），Meta 必须
识别"这是同一个事件"，否则转化会**重复记账**，广告优化被污染。

去重的核心机制是 **event_id（EventID）**：

```
去重规则:
└─ 相同 pixel + 相同 event_id → Meta 视为同一事件 → 只算一次

EventID 生成原则（生产铁律）:
├─ 必须全局唯一（跨 Pixel 与 CAPI 一致）
├─ 必须稳定（同一次业务行为多次重发 → 同一个 event_id）
├─ 建议: 由业务行为的自然标识生成
│   例如下单行为 → f"{order_id}:{event_name}" 或 uuid5(namespace, order_id)
└─ 切忌用随机 uuid（每次重发都不一样 → 去重失效）
```

```python
import uuid

def build_event_id(business_signal: str, event_name: str) -> str:
    """
    幂等 EventID: 同一业务行为(如 order_id) + 同一事件 → 同一 EventID。
    这样 CAPI 与 Pixel 双通道、以及 CAPI 重试，都能被 Meta 去重。
    """
    ns = uuid.uuid5(uuid.NAMESPACE_URL, "ryan-capi:2026")
    return str(uuid.uuid5(ns, f"{business_signal}:{event_name}"))
```

**踩坑案例**：某团队用 `uuid4()` 每秒生成新值当 event_id，结果同一次下单
的前端 Pixel 与后端 CAPI 是两个不同 id → 转化被记了 2 次 → CPA 虚高 →
优化器把目标当"已达成"甚至调低出价。改成分确定性 event_id 后，去重率
从 20% 升到 90%+。**EventID 的确定性是生产命脉。**

### 3.3 去重率指标与诊断

Events Manager 里有一个关键数字：**去重率 / 匹配率**。生产监控要拆开看：

```
值得监控的「三率」:
├─ 送达率 Delivery rate     = 送达的事件 / 期望发送的事件
├─ 匹配率 Match rate        = 匹配到用户的事件 / 送达事件
└─ 去重率 Dedup rate        = 去重后事件 / 去重前事件（双通道场景）

排查路径（当三率异常）:
└─ 送达率低  → 发送失败/限流/超时 → 检查队列与重试
└─ 匹配率低  → user_data 不够 or 哈希规则不一致 → 检查归一化函数
└─ 去重率低  → event_id 不稳定/不唯一 → 检查 EventID 生成逻辑
```

---

## 第四部分：批量处理与发送引擎

### 4.1 为什么需要批量（Batch）发送

单条 HTTP 发送的缺陷：
- 每条请求有固定开销（TLS 握手、HTTP 头、RTT），吞吐低
- 突发流量下请求数爆炸，容易触发限流
- 低频低价值场景没必要逐条实时发

批量发送把多条事件放进一个 `data` 数组，一次 POST：

```python
# meta_send_capi_batch: 把多条事件合并成一次请求（脚本方法语义）
def send_batch(pixel_id: str, events: list, token: str) -> dict:
    url = f"https://graph.facebook.com/v20.0/{pixel_id}/events"
    payload = {"data": events, "access_token": token}
    resp = requests.post(url, json=payload, timeout=15)
    return resp.json()
```

使用脚本方法 `meta_send_capi_batch`（它会回落到 `meta_send_capi`）的
生产姿势：**先 Eager 聚合成批，再由 worker 批量发送**。

### 4.2 批量分片与大小策略

```
批量策略:
├─ 批量大小: 典型 50~900 条/请求，按业务节奏与限流余量调
├─ 分片:     内存/队列累积事件，达到阈值或超时窗口即触发 flush
├─ Flush 触发:  count>=N OR 距上次>=T 秒 → 满足其一就发
└─ 权衡:
   ├─ 批太大 → 单请求风险大、限流惩罚大
   └─ 批太小 → 请求开销大、吞吐上不去
```

分片/Flush 的经典实现（伪代码骨架）：

```python
class BatchFlusher:
    def __init__(self, max_batch=500, flush_interval=5.0):
        self._buf = []
        self._max_batch = max_batch
        self._last_flush = time.monotonic()
        self._flush_interval = flush_interval

    def add(self, event: dict) -> None:
        self._buf.append(event)
        if len(self._buf) >= self._max_batch:
            self.flush()
        elif time.monotonic() - self._last_flush >= self._flush_interval:
            self.flush()

    def flush(self) -> None:
        if not self._buf:
            return
        batch = self._buf
        self._buf = []
        self._last_flush = time.monotonic()
        self._dispatch(batch)   # 交给 worker 发送（第五部分）

    def _dispatch(self, batch): ...
```

### 4.3 吞吐与并发（生产规模直觉）

给出一个"生产规模"的心智模型，帮助你做容量设计：

```
单机/单 worker 能力参考（经验值，非精确）:
├─ 批大小 500: 单请求 ~200ms（含网络）
├─ 单 worker 每秒可发 ~2~5 批 → ~1000~2500 事件/秒
├─ 10 worker 并发: ~1~2.5 万事件/秒
├─ 若日事件量 1000 万 → 峰值需预留 5~10 倍余量
└─ 超过单机能力 → 横向扩容 + 队列削峰（第五部分）

扩容瓶颈检查清单:
├─ 是否有队列解耦（否则打满 HTTP 连接池）
├─ 连接池大小（urllib3 / httpx 连接数）
├─ Meta 每像素限流能否跟上涨量（超了要申请提额）
└─ 客户端超时/重试是否只吃退避不吃吞吐
```

**我的体会**：很多人上线后才发现"发不出去/被限流/超时"，本质是**没做容量
规划**。生产部署前先估量：日事件量、峰值 QPS、单请求耗时、限流余量，四者
对齐后再订 worker 数与批量策略。

---

## 第五部分：生产级后端架构设计（核心章节）

### 5.1 总体架构：队列 + 重试 + 幂等 + 去重

这一部分是本笔记的重中之重。生产 CAPI 后端，本质上是一个**可靠的
异步事件管道**。四个支柱：Queue（队列）、Retry（重试）、Idempotency
（幂等）、Dedup（去重）。

```
┌──────────────────────────── CAPI 后端（你的服务）────────────────────────────┐
│                                                                          │
│  业务事件 ──► [Producer] ──► (Queue/Kafka) ──► [Consumer/Worker]         │
│      │                          │                     │                  │
│      │                    ┌─────┴─────┐         ┌─────┴─────┐           │
│      │                    │ 持久化/削峰 │         │ 幂等检查    │           │
│      │                    └───────────┘         │ (event_id)│           │
│      │                                          └─────┬─────┘           │
│      │                                                ▼                 │
│      │                                          [Sender/Retry]          │
│      │                                                │ (指数退避)       │
│      │                                                ▼                 │
│      │                                         Meta /events (batch)     │
│      │                                                │                 │
│      └───────── 429/5xx ──► 重试队列 / DLQ ◄───────────┘                 │
│                              │  永久失败 → 人工排查(死信)                  │
└──────────────────────────────────────────────────────────────────────────┘
```

### 5.2 队列（Queue）：为什么必须异步

**核心动机**：CAPI 发送是外部 I/O，慢、会失败、会抖动。如果在业务请求线程
里同步发送，业务接口会被拖慢、甚至被外部抖动拖垮。

```
队列的价值:
├─ 削峰: 高峰瞬间上万事件，队列缓冲，worker 均匀消费
├─ 解耦: 业务与发送分离，互不拖累
├─ 缓冲重试: 失败事件留在队列，从容重试
├─ 持久化: 进程崩溃不丢事件（需要消息落盘/ACK）
└─ 水平扩展: 加 worker 即提升吞吐
```

选型直觉（生产）：
- 事件量小/dev → 内存队列 + 一次 ACK 落库
- 事件量大/高可用 → Kafka / RabbitMQ / SQS，消息持久化 + consumer group

### 5.3 重试（Retry）：指数退避 + Jitter

发送可能暂时失败（网络抖动、5xx、429 限流）。正确姿势是指数退避 + Jitter。

```python
import random
import time

def retry_with_backoff(attempt: int, base=1.0, cap=60.0) -> float:
    """指数退避 + 全抖动（Jitter），避免『惊群』式同时重试。"""
    sleep = min(cap, base * (2 ** attempt))      # 1,2,4,8,16,32,60...
    return random.uniform(0, sleep)              # 全抖动: [0, sleep)

def send_with_retry(send_fn, event, max_retries=5):
    last_err = None
    for attempt in range(max_retries):
        try:
            return send_fn(event)                # -> 调 meta_send_capi
        except RateLimitedError as e:
            last_err = e
            time.sleep(retry_with_backoff(attempt))
        except TransientError as e:
            last_err = e
            time.sleep(retry_with_backoff(attempt))
        # PermanentError(4xx) 不重试，直接抛给调用方记死信
    raise last_err

# 注意: 重试的前提是幂等 —— 否则重试 = 重复记账。
# event_id 确定性在这里再次体现价值（见 3.2、5.5）。
```

```
重试策略明细:
├─ 可重试错误:
│  ├─ 429 (限流)           → 退避 + Jitter，遵循 Retry-After
│  ├─ 5xx (服务器错误)      → 退避重试
│  └─ 网络超时/连接重置      → 退避重试
├─ 不可重试错误(4xx 业务):
│  ├─ 401/403 (令牌/权限)   → 告警，人工处理
│  ├─ 400 (字段非法)        → 丢入 DLQ，修数据
│  └─ 402 (付款/CAPI 未配)  → 检查 setup
└─ 重试上限后用尽 → 事件进死信队列(DLQ)，可看板+告警+重放
```

**踩坑案例**：某团队重试时没有 Jitter，高峰期 500 worker 同时失败同时
Sleep(1)、Sleep(2)……形成"重试风暴"，把 Meta 和自家 429 打得更狠。加上
`random.uniform(0, sleep)` 全抖动后，限流缓解一个数量级。**重试必须带
Jitter。**

### 5.4 幂等（Idempotency）：键的设计与落库

幂等 = 同一次业务行为无论被处理多少次，结果只体现一次。

```
幂等的两个层次:
├─ Meta 侧: 靠 event_id（EventID）让 Meta 去重（见 3.2）
└─ 你侧:   靠幂等键 + 存储，保证你自己不重复处理事件
           （例如不要在事件落库/下游业务时重复计价）
```

你自己的幂等键设计（落库避免重复写入）：

```python
CREATE TABLE IF NOT EXISTS capi_idem (
    event_id    VARCHAR(64) PRIMARY KEY,   -- 幂等键
    pixel_id    VARCHAR(32) NOT NULL,
    status      VARCHAR(16) NOT NULL,      -- pending/sent/dead/deduped
    try_count   INT DEFAULT 0,
    last_error  TEXT,
    created_at  TIMESTAMP DEFAULT now(),
    updated_at  TIMESTAMP DEFAULT now()
);

-- 处理前:
-- INSERT ... ON CONFLICT (event_id) DO NOTHING
--   已存在 → 跳过（幂等）; 新插入 → 继续处理
```

```python
def claim_event(conn, event_id: str) -> bool:
    """原子领取事件: 返回 False 表示已处理过（幂等去重）。"""
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO capi_idem (event_id, status)
        VALUES (%s, 'pending')
        ON CONFLICT (event_id) DO NOTHING
        """, (event_id,))
    conn.commit()
    return cur.rowcount == 1   # 1=首次领取, 0=重复
```

**幂等键（Idempotency Key）本质**：`event_id 或 (pixel + event_id)` 唯一
标识一条业务事件。它把"网络上可能重复送达"这个不确定性，变成"数据库里
唯一约束"这个确定性。**这是分布式系统里应对 at-least-once 语义的标配。**

### 5.5 去重（Dedup）：双通道同 id + 重试防重

去重要做两层：

```
第 1 层 生产发出去重（你侧）:
└─ claim_event(event_id) 原子抢占 → 同一事件只入队/只落库一次

第 2 层 Meta 侧去重（信任 Meta）:
└─ 同一 pixel + 同一 event_id → Meta 计一次
   └─ 因此双通道（Pixel + CAPI）用同一确定性 event_id 即可安全共存
```

去重率监控通常放 Events Manager（第六/七部分展开）。这里给出**你自己侧**
的可观测做法：`meta_list_capi_events` 回读对照。

```python
def audit_dedup(pixel_id: str, sent_ids: set) -> dict:
    """回读 CAPI 事件，对照本地已发放集，算出重复率（示意）。"""
    remote = client.meta_list_capi_events(pixel_id)
    remote_ids = {e.get("event_id") for e in remote if e.get("event_id")}
    dup = remote_ids & sent_ids
    return {
        "sent": len(sent_ids),
        "seen_on_meta": len(remote_ids),
        "duplicated": len(dup),
        "dup_rate": len(dup) / max(1, len(sent_ids)),
    }
```

### 5.6 完整生产发送 worker（把四支柱串起来）

把所有能力组装成一个线程安全的 worker。这是"生产级"的浓缩体现：

```python
import queue, threading, time, random, logging

log = logging.getLogger("capi.worker")

class CAPIWorker:
    """
    生产 CAPI 异步发送 worker。
    支柱: 队列(线程安全) + 幂等(claim) + 重试(退避Jitter) + 批量(flush)。
    """
    def __init__(self, client, db_conn, batch_size=500, flush_interval=5.0,
                 max_retries=5):
        self.client = client
        self.db = db_conn
        self.q = queue.Queue()
        self.batch = []
        self.batch_size = batch_size
        self.flush_interval = flush_interval
        self.max_retries = max_retries
        self._lock = threading.Lock()
        self._stop = False
        self.metrics = {"send": 0, "retry": 0, "dead": 0, "dedup": 0}

    # ---------- 生产者接口：业务调用 ----------
    def submit(self, event: dict) -> bool:
        """入队前先做幂等抢占，抢到才入队。"""
        if not claim_event(self.db, event["event_id"]):
            self.metrics["dedup"] += 1
            return False                      # 重复事件，幂等丢弃
        self.q.put(event)
        return True

    # ---------- 消费者主循环 ----------
    def run(self):
        while not self._stop:
            try:
                event = self.q.get(timeout=self.flush_interval)
            except queue.Empty:
                self.flush_batch()
                continue
            self.batch.append(event)
            if len(self.batch) >= self.batch_size:
                self.flush_batch()

    def flush_batch(self):
        if not self.batch:
            return
        batch, self.batch = self.batch, []
        self._dispatch(batch)

    def _dispatch(self, batch):
        for attempt in range(self.max_retries):
            try:
                # 批量发送: 走 meta_send_capi_batch
                self.client.meta_send_capi_batch(
                    self.client.pixel_id, events=batch)
                self.mark(batch, "sent")
                self.metrics["send"] += len(batch)
                return
            except PermanentError as e:
                self.mark(batch, "dead", str(e))
                self.metrics["dead"] += len(batch)
                log.error("permanent failure: %s", e)
                return
            except TransientError as e:
                self.metrics["retry"] += len(batch)
                delay = random.uniform(0, min(60, 1 * (2 ** attempt)))
                log.warning("retry#%d batch=%d err=%s", attempt, len(batch), e)
                time.sleep(delay)
        # 重试用尽 → 死信
        self.mark(batch, "dead", "max_retries")
        self.metrics["dead"] += len(batch)

    def mark(self, batch, status, err=""):
        for e in batch:
            cur = self.db.cursor()
            cur.execute(
                "UPDATE capi_idem SET status=%s, last_error=%s "
                "WHERE event_id=%s", (status, err, e["event_id"]))
            self.db.commit()
```

**我的体会**：第四/五部分是生产 CAPI 的"灵魂"。面试或做架构评审时，
能讲清楚"为什么异步、重试为什么带 Jitter、幂等键为什么必须确定性、去重
分两层"的人，才是真懂生产落地。代码可以精简，但**这套模型不能少**。

---

## 第六部分：与 Pixel 双通道的协同

### 6.1 为什么双通道（Pixel + CAPI）而不是互相替代

业界最佳实践是**两者共存**，各司其职、互相补足：

```
Pixel（浏览器端）:                   CAPI（服务器端）:
├─ 覆盖浏览器可观测的事件             ├─ 覆盖服务器可观测的事件
├─ 实时、带 fbp/fbc cookie           ├─ 绕过浏览器限制、更可信
├─ 补 fbp 关联                        ├─ 补 em/ph 等强 PII
└─ 容易丢（ITP/拦截器）              └─ 承接"强购买信号"
─────────────────────────────────────────────────────────
协同目标: 同一业务事件，两通道都发，Meta 用 event_id 去重归并。
```

### 6.2 event_source 与事件优先级

双通道下，Meta 判断"以哪条为准"的机制（生产要理解，不是你想的"后到先得"）：

```
核心点:
├─ EventID 相同 → Meta 去重，按规则取其一（通常更高优先级通道）
├─ EventID 不同 → 视为不同事件，都计入
├─ 各通道 event_source 标识来源(website/app/...)，影响归因与建模权重
└─ 生产建议:
   ├─ 关键转化(购买/支付) → CAPI 为主，可靠性高
   ├─ 低频浏览类 → 可仅 Pixel
   └─ 用 meta_validate_event_data 统一双通道字段，减少不可比
```

可以用脚本方法 `meta_list_event_source_types` 查看/管理可用的事件来源类型，
确保你用的 `action_source` 是受支持的枚举值：

```python
def inspect_event_sources() -> None:
    """列出受支持的事件来源类型，核对 action_source 取值（示意）。"""
    sources = client.meta_list_event_source_types()
    for s in sources:
        print(s)   # 如 website / app / phone_call / ...
```

### 6.3 双通道去重监控与目标

```
双通道健康目标（经验参考，按业务调）:
├─ CAPI 送达率   ≥ 99%       (靠队列+重试保证)
├─ 匹配率        ≥ 70~80%    (随 url 深度/移动端波动)
├─ 双通道去重率  ≥ 80%+      (说明 event_id 一致生效)
└─ 若去重率过低 → 检查前端 Pixel 与后端 CAPI 是否用同一确定性 event_id
```

### 6.4 用 Pixel 补 Cookie（fbp/fbc）的最佳姿势

双通道里一个很实用的技巧：让 Pixel 写的 `_fbp` cookie 由服务器端读取，
作为 `user_data["fbp"]` 传给 CAPI，大幅提升匹配率。

```
流程:
├─ 浏览器 Pixel 写入 _fbp cookie
├─ 后端拿到请求时读取 cookie 里的 fbp/fbc
├─ 组装 user_data 时带上 fbp (不哈希)
└─ CAPI 事件与 Pixel 归入同一用户 → 匹配率上升
```

```python
def build_user_data_with_cookie(email: str, fbp: str, fbc: str) -> dict:
    ud = {"em": [sha256_hex(email)]}
    if fbp:
        ud["fbp"] = fbp          # 原样直传，不哈希
    if fbc:
        ud["fbc"] = fbc
    return ud
```

**踩坑案例**：一开始只发 em，匹配率只有 45%；加上 fbp/fbc 后升到 75%+。
而 fbp 的获取依赖，必须**在后端能读到 cookie 的接口**里注入，不能只靠纯
后端事件。生产部署要把"哪个接口能拿到 cookie"提前梳理清楚。

---

## 第七部分：事件测试与质量监控

### 7.1 用 Test Events 联调（上线前必做）

上线前用 Events Manager 的 Test Events 功能验证：事件能否到达、字段、
匹配、去重。脚本侧可以把这套测试编排起来。

```
Test Events 两步:
├─ 1. 在 Events Manager → Test Events 生成一个 Test Event Code
└─ 2. 发送时把它带在请求里 → 该事件进测试流，不进生产归因
```

```python
def send_test_event(pixel_id: str, event: dict, test_code: str) -> dict:
    """带 Test Event Code 发送测试事件（不影响生产归因）。"""
    params = {
        "test_event_code": test_code,     # 测试令牌
        "access_token": token,
    }
    return client.meta_send_capi(pixel_id, data=[event], **params)
```

验证脚本（生产排障也能复用）：
```python
def dry_run_validation(pixel_id: str, events: list) -> dict:
    """上线/排障前做 dry_run 式校验: 用 meta_validate_event_data + 测试事件。
    """
    # 1. 结构校验
    report = client.meta_validate_event_data(pixel_id, data=events)
    # 2. 测一条到 Test Events，检查到达
    code = "TEST_CODE_FROM_EVENTS_MANAGER"
    result = send_test_event(pixel_id, events[:1], code)
    return {"validation": report, "test_send": result}
```

用 `meta_list_pixel_events` / `meta_create_pixel_event` 做轻量回读与造数：

```python
def smoke_pixel(pixel_id: str) -> dict:
    """冒烟: 回读现有 pixel 事件 + 造一条测试事件验证链路。"""
    existing = client.meta_list_pixel_events(pixel_id)
    created = client.meta_create_pixel_event(
        pixel_id, event_name="TestPurchase", custom_data={"value": 1})
    return {"existing_count": len(existing), "created": created}
```

### 7.2 Event Quality（事件质量）与匹配字段健康

Events Manager → 每个事件的 "Event Quality" 分数，反映 `user_data` 的
完整度与匹配能力。生产要拉出来监控：

```python
def monitor_event_quality(pixel_id: str) -> list:
    """拉取各事件的质量分，识别 user_data 短板（示意）。"""
    rows = client.meta_get_event_quality(pixel_id)
    for r in rows:
        print(f"{r['event']:<20} quality={r['score']} "
              f"matched={r.get('matched_fields')}")
    return rows
```

```
质量分解读（经验）:
├─ 高分(>7/10 段): user_data 覆盖好，匹配强 → 维持
├─ 中分: 缺 ph / fn / fbp 等 → 补字段
└─ 低分: 基本没 user_data → 基本靠 IP/UA 弱匹配 → 优化方向明确
```

### 7.3 生产监控大盘（三率 + 链路）

把散落的指标汇总成一张 Dashboard，这是生产可运维性的核心：

```
CAPI 生产监控大盘
┌─────────────────────────────────────────────────────────────┐
│ 送达率 Delivery │ 匹配率 Match │ 去重率 Dedup │ 延迟 p95     │
│    99.2%        │   76.4%      │    91.8%     │    240ms      │
├─────────────────────────────────────────────────────────────┤
│ 发送量/秒 曲线  │ 429 频率     │ 死信队列 DLQ │ Worker 存活   │
│   ~1200/s       │   0.03%      │      12      │    8/8 up     │
├─────────────┬───────────────────────────────────────────────┤
│ 告警规则     │ 送达率<95% / 匹配率<60% / DLQ>N / 429 突增     │
├─────────────┴───────────────────────────────────────────────┤
│ 数据来源: worker metrics + meta_get_event_quality            │
│          + meta_list_capi_events 回读                          │
└─────────────────────────────────────────────────────────────┘
```

```
告警分级（可执行）:
├─ P0: 送达率骤降 / worker 全部宕 → 立即响应
├─ P1: 匹配率<阈值 / DLQ 增长 → 30 分钟内排查
├─ P2: 去重率异常下降 → 检查 event_id 变更
└─ P3: 延迟上升 → 观察限流与队列积压
```

**我的体会**：没有监控的 CAPI 等于"盲飞"。生产部署的**交付标准不是"能发
事件"，而是"三率可观测、异常能告警、失败能重放"**。先把大盘立起来，再谈
其他。

---

## 第八部分：Conversion API 配置管理（生产可运维必备）

### 8.1 配置的生命周期：从开发到灰度

CAPI 不是"配一次就一直跑"，而是有清晰的配置生命周期。生产环境要管理好
Pixel 配置、测试代码、Token 轮换、版本切换这些"会变化的东西"。

```
配置生命周期:
┌─────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐
│ 开发/沙箱 │→ │ 灰度试点  │→ │ 全量放量  │→ │ 持续运营  │
└─────────┘   └──────────┘   └──────────┘   └──────────┘
   含测试       小流量验证      完整流量      监控迭代/回滚
   test_code    双通道对比      三率达标      版本切换安全
```

脚本中提供了 `meta_get_conversion_api_config` 与
`meta_update_conversion_api_config`，用于读取/更新 Conversion API 配置。
生产里"读取配置、小步更新、可回滚"是铁律：

```python
def read_capi_config(pixel_id: str) -> dict:
    """读取当前 CAPI 配置（用于变更前快照、变更后核对/回滚）。"""
    return client.meta_get_conversion_api_config(pixel_id)

def update_capi_config(pixel_id: str, **changes) -> dict:
    """更新 CAPI 配置，并保留旧值以便回滚（示意）。"""
    before = read_capi_config(pixel_id)      # 快照旧配置
    try:
        resp = client.meta_update_conversion_api_config(pixel_id, **changes)
    except Exception:
        # 失败则回滚到快照（若接口支持）或记录待人工恢复
        client.meta_update_conversion_api_config(pixel_id, **before)
        raise
    return resp
```

```
变更安全三原则:
├─ 变更前   记快照 (get_conversion_api_config)
├─ 变更中   灰度/小流量，观察三率无回退
└─ 变更后   可一键回滚到快照
```

### 8.2 Token 轮换与 Secret 管理

生产 Token 是命门。做成可轮换、不外泄、自动续期：

```
Token 管理规范:
├─ 永不明文入库/提交代码/进日志
├─ 放 Secret Manager / 环境变量 / KMS 加密
├─ 轮换策略: 定期换 + 失效前自动换，双 Token 平滑过渡
├─ 每个环境(PROD/STAGE)独立 Token，互不串
└─ 变更 Token 不触发重建: 配置与代码分离
```

```python
import os

def get_token() -> str:
    """从安全位置取 Token，不从代码库读。"""
    # 生产不要用 os.environ 硬编码明文，放 Secret Manager 后注入
    return os.environ["META_CAPI_TOKEN"]

def rotate_token(new_token: str, old_token: str) -> None:
    """
    轮换策略(示意): 先在旧 Token 尚有效时申请新 Token，
    灰度切换一部分流量验证，成功后再全量切，最后吊销旧 Token。
    """
    # set new_token 到 Secret Manager
    #   → 用 new_token 发测试事件验证权限
    #   → 逐步切流量
    #   → 确认稳定后吊销 old_token
    pass
```

### 8.3 多环境隔离（Dev / Staging / Prod）

```
环境隔离建议:
├─ 每个环境独立 Pixel 或独立测试配置
├─ Prod 用正式 Pixel + 正式 Token；无法用独 Test Event Code 验证
├─ Staging 用测试 Pixel / Test Event Code，避免污染生产归因
└─ Dev 可完全 mock（meta_send_capi 打桩，不入量）
```

```python
ENV_META_PIXEL = {
    "dev":     "TEST_PIXEL_OR_MOCK",
    "staging": "TEST_PIXEL",
    "prod":    os.environ.get("META_PROD_PIXEL_ID"),
}

def get_pixel(env: str) -> str:
    return ENV_META_PIXEL[env]
```

**踩坑案例**：有团队把 Staging 的测试事件发到了生产 Pixel，导致大批
fake 转化进入归因，广告优化被污染、还误报了 CPA。**环境隔离不到位，
测试即事故。** 务必在发送层强制"环境 → 目标 Pixel"映射，并在非生产环境
出口加 `test_event_code`。

---

## 第九部分：上线前后 Checklist（可直接抄作业）

### 9.1 上线前 Checklist（Pre-flight）

```
CAPI 上线前 Checklist
────────────────────────────────────────────────────────────
[a] 需求与口径
   [ ] 明确要上报的事件清单(购买/支付/注册/加购...)与优先级
   [ ] 与 Pixel 双通道口径一致事件 & EventID 生成规则对齐
[b] 数据与匹配
   [ ] PII 归一化/哈希函数与前端 SDK 完全一致
   [ ] user_data 覆盖 em/ph/fbp 等关键字段（目标匹配率定好）
   [ ] fbp/fbc 里能从哪些接口取到已梳理
   [ ] 用 meta_validate_event_data 全量字段通过
[c] 配置与令牌
   [ ] 每个环境独立 Pixel/Token，多环境映射验证
   [ ] Token 走 Secret Manager，轮换机制就绪
   [ ] Conversion API 配置快照 + 可回滚
[d] 后端架构(第五部分)验收
   [ ] 队列 + 指数退避Jitter重试 + 幂等键落库 + 去重
   [ ] batch 分片/flush 策略定好
   [ ] 死信队列 DLQ + 重放能力就绪
[e] 测试与质量
   [ ] Test Events 跑通(到达/字段/匹配)
   [ ] 冒烟: meta_create_pixel_event / meta_list_pixel_events
   [ ] Event Quality 基线记录(meta_get_event_quality)
[f] 监控与告警
   [ ] 三率(送达/匹配/去重)大盘
   [ ] 429/DLQ/worker 存活告警
   [ ] 容量规划(日量/QPS/限流余量)核算
────────────────────────────────────────────────────────────
```

### 9.2 上线后 Checklist（Post-launch 灰度）

```
上线后灰度 Checklist
────────────────────────────────────────────────────────────
[a] 灰度节奏
   [ ] 小流量(如 5%) → 观察 30~60min 三率
   [ ] 逐步 25% → 50% → 100%
   [ ] 每级对比基线, 回退则一键回滚
[b] 双通道验证
   [ ] CAPI 送达率 ≥99%（队列+重试生效）
   [ ] 去重率正常（两通道同 event_id）
   [ ] Match rate 未回退
[c] 归因/业务校验
   [ ] 转化量未被重复记账/未被冲淡
   [ ] CPA/ROAS 与纯 Pixel 基线可比
   [ ] 与广告后台 KPI 交叉核对
[d] 24~72h 观察
   [ ] 高峰期队列积压/限流情况
   [ ] DLQ 是否增长、原因归类
   [ ] 匹配率稳定优化(补 ph/fbp 等)
────────────────────────────────────────────────────────────
```

**我的体会**：Checklist 的本质是把"经验/踩坑"变成"可执行的流程"。
不要只在"上线那天"用，而是作为每次 CAPI 变更(改字段/改配置/换 Token)的
固定关卡。**Ignore Checklist = 把踩过的坑再踩一遍。**

---

## 第十部分：完整 CAPI 生产部署案例（端到端）

### 10.1 业务背景

一家跨境电商独立站，面临：iOS 归因受限、浏览器 Pixel 丢数据、希望用
服务器端的支付信号提升购买转化优化。目标：把 CAPI 生产落地，双通道协同，
三率达标、可灰度可回滚。

```
需求与目标:
├─ 事件: Purchase(核心) / AddToCart / CompleteRegistration / ViewContent
├─ 目标: CAPI 送达≥99%、匹配率≥75%、双通道去重≥85%
├─ 约束: 峰值 QPS ~2000、午夜低峰、要有灰度与回滚
└─ 技术栈: Go 后端 + Kafka 事件流 + worker 发送 CAPI
```

### 10.2 架构落地

```
┌─ 用户下单 ─► 后端订单服务
│                │  发出 Purchase 事件(biz_event: order_id)
│                ▼
│          Kafka topic: capi.events       (削峰+持久化)
│                │
│                ▼
│          CAPI Worker (多实例, consumer group)
│                ├─ 幂等 claim(event_id) 落库
│                ├─ 归一化哈希 em/ph
│                ├─ 批量 flush (500条)
│                ├─ 指数退避Jitter重试
│                └─ 429/5xx → 重试; 4xx → DLQ
│                │
│                ▼
│          Meta /{pixel}/events  (batch)
│                │
│                ▼
│          监控: 三率大盘 + 告警; DLQ 看板可重放
│
└─ 前端 Pixel 同 event_id 双发 Purchase(带 fbp/fbc cookie)
          ▲ CAPI 侧从订单请求读取 fbp 一并带上
```

### 10.3 关键实现片段

订单完成后，生成确定性 EventID，保证前后端一致：

```python
def on_purchase(order: dict, fbp: str) -> None:
    event_id = build_event_id(str(order["order_id"]), "Purchase")
    user_data = build_user_data_with_cookie(order["email"], fbp, fbc=order.get("fbc"))
    event = build_event(
        event_name="Purchase",
        user_data=user_data,
        custom_data={
            "value": order["amount"],
            "currency": "USD",
            "content_ids": order["item_ids"],
            "content_type": "product",
        },
        event_time=int(order["paid_at"]),
        event_id=event_id,
        action_source="website",
    )
    # 幂等抢占后入队（重复订单/重发被去重）
    worker.submit(event)
```

生产 worker 发送（即 5.6 的 `CAPIWorker`），配合 `meta_send_capi_batch`
批量：`self.client.meta_send_capi_batch(pixel_id, events=batch)`。

### 10.4 灰度与上线过程实录

```
上线过程 (时间线):
├─ Day-0 Pre-flight: 按下「9.1 上线前 Checklist」逐项打勾
│    - Test Events 跑通 Purchase
│    - meta_validate_event_data 全过
│    - 事件质量基线记录
├─ Day-1 灰度 5%:
│    - 观察 30~60min: 送达 99.4%, 匹配 61%(偏低)
│    - 发现: 只有 em，缺 fbp → 补 fbp 后匹配升到 74%
├─ Day-2 灰度 50%:
│    - 送达 99.3%, 匹配 76%, 去重 88%
│    - 前端 Pixel 与 CAPI event_id 已对齐, 无双计
├─ Day-3 全量 100%:
│    - 三率全部达标
│    - 与纯 Pixel 基线对比: CPA 下降 ~8%(信号更足、学习更稳)
└─ 运营期: 持续监控三率, 每晚核对 DLQ, 按周微调匹配字段
```

### 10.5 上线遇过的坑与解决（经验教训汇总）

```
坑 1: 匹配率只有 45%
  原因: 归一化/哈希与前端 SDK 不一致, 且缺 fbp
  解决: 复用同一 normalize_pii + 加 fbp/fbc → 匹配 76%
坑 2: 转化重复记账
  原因: event_id 用随机 uuid4(), 前后端不一致
  解决: 改成分确定性 event_id(order_id:event) → 去重 88%
坑 3: 高峰期 429 打爆
  原因: 重试无 Jitter + 无限流保护
  解决: 指数退避 + 全抖动 + 令牌桶 → 429 降一个量级
坑 4: Staging 测试事件污染生产
  原因: 环境未隔离, 测试发到了生产 Pixel
  解决: 环境→Pixel 映射 + 非生产强制 test_event_code
坑 5: 上线即盲飞
  原因: 没监控, 出问题不知道
  解决: 立三率大盘 + 告警 + DLQ 看板(先可见再放量)
```

**我的体会**：这个案例的每个"坑"都能在本文前面 Part 找到理论对应——
这就是把底层原理(topics)与生产落地(tactics)打通的价值。真正能落地的
团队，不是背 API 字段，而是**把原理转成防坑流程**。

---

## 第十一部分：自测题

### Q1：CAPI 生产发送为什么必须"异步 + 队列"，而不是在业务请求线程里同步发？

<details><summary>答案</summary>

CAPI 发送是外部 I/O，慢、会失败、会抖动。若在业务请求线程里同步发送，
业务接口会被外部延迟拖垮、被抖动牵连。异步队列的价值：削峰（高峰事件
缓冲、worker 均匀消费）、解耦（业务与发送互不拖累）、缓冲重试（失败事件
停留从容重试）、持久化（崩溃不丢）、水平扩展（加 worker 即升吞吐）。
生产姿势是业务"确认入队成功"即返回，真正发送交给后台 worker。
</details>

### Q2：为什么 EventID（幂等键）必须是"确定性"而非随机生成的？

<details><summary>答案</summary>

Meta 用"相同 pixel + 相同 event_id"判定为同一事件并去重。同一业务行为
（如同一 order_id 的 Purchase）无论被 Pixel 发、被 CAPI 发、还是重试重发，
都必须生成**同一个** event_id 才能被 Meta 识别为同一事件、只记一次。若用
随机 uuid4()，每次生成都不同 → 双通道/重试会被当成不同事件 → 转化重复
记账 → CPA 虚高、优化被污染。正确做法是 `uuid5(namespace, f"{order_id}:
{event_name}")` 这类确定性生成。
</details>

### Q3：双通道（Pixel + CAPI）下为什么还要同时关注"匹配率"和"去重率"？两者目标分别是什么？

<details><summary>答案</summary>

这是两个不同维度：
- **匹配率** = 匹配到真实用户的事件 / 送达事件，反映 user_data 的覆盖质量
  （em/ph/fbp 是否够、哈希规则是否一致），太低则归因与建模弱。
- **去重率** = 去重后事件 / 去重前事件，反映双通道/重试是否被正确归并
  （event_id 是否稳定唯一），太低则转化被重复记账。
两者要分开监控：匹配率低 → 查 user_data 与哈希；去重率低 → 查 event_id
生成。生产大盘两者都看，缺一不可。
</details>

### Q4：重试（Retry）为什么必须加 Jitter（随机抖动）？不加会怎样？

<details><summary>答案</summary>

不加 Jitter 时，大量 worker 同时失败会按相同的退避时长（如 1s,2s,4s...）
同时醒来重试，形成"重试风暴"（惊群效应），把 Meta 和自己的 429/负载打得
更狠，限流雪上加霜。加全抖动（`random.uniform(0, sleep)`）后，各 worker
重试时刻随机错开，限流大幅缓解。经验案例：高峰期加 Jitter 后 429 降一个
量级。重试的另一个前提是幂等（确定事件 id），否则重试=重复记账。
</details>

### Q5：生产 CAPI 上线前，最重要的可运维性交付标准是什么？

<details><summary>答案</summary>

不是"能发事件"，而是**三率可观测、异常能告警、失败能重放**：
- 三率（送达/Delivery、匹配/Match、去重/Dedup）要进监控大盘；
- 异常（送达<95%、匹配<阈值、DLQ 增长、429 突增、worker 宕）要能告警分级；
- 失败事件要进死信队列 DLQ 且能重放。

配合上线前 Checklist（环境隔离、Token 管理、Test Events、Event Quality
基线）和灰度节奏，才叫真正"生产就绪"。
</details>

---

## 附：本笔记方法速查（脚本方法 ↔ 用途）

| 脚本方法 | 用途 | 本文相关 |
|---------|------|---------|
| `meta_send_capi` | 发送单条 CAPI 事件 | 2.4 / 5.6 |
| `meta_send_capi_batch` | 批量发送 CAPI 事件 | 4.x / 5.6 / 10.3 |
| `meta_track_pixel` | 追踪 Pixel 事件 | 6.x |
| `meta_validate_event_data` | 校验事件字段合法性 | 2.2 / 9.1 |
| `meta_list_capi_events` | 回读 CAPI 事件 | 5.5 / 7.3 |
| `meta_list_matched_fields` | 查看匹配字段 | 3.1 |
| `meta_get_event_quality` | 拉取事件质量分 | 7.2 / 9.1 |
| `meta_list_event_source_types` | 列出事件来源类型 | 6.2 |
| `meta_get_conversion_api_config` | 读取 CAPI 配置 | 8.1 |
| `meta_update_conversion_api_config` | 更新 CAPI 配置 | 8.1 |
| `meta_list_pixel_events` | 回读 Pixel 事件 | 7.1 |
| `meta_create_pixel_event` | 造一条 Pixel 事件(冒烟) | 7.1 / 9.1 |

---

## 附：学习路线串联（Day-by-Day 整体视角）

```
meta-01  API 基础原理
   ↓
meta-05  API 高级用法 (Graph API 深厚)
   ↓
capi-deep-dive  CAPI 全链路深度指南 (原理/源码级)
   ↓
meta-09 本笔记 CAPI 生产部署 (部署流程/架构/上线) ★你在这里
   ↓
业务落地: 三率大盘、灰度放量、持续优化
```

本笔记之所以叫 meta-09 而不是重复 capi-deep-dive，是因为它的**视角是
生产部署流程与架构**：从"发事件"上升到"可靠异步管道 + 三率可观测 +
灰度可回滚的工程系统"。学完本章，你应能在面试或架构评审中，系统讲清
CAPI 生产落地的完整链路。
