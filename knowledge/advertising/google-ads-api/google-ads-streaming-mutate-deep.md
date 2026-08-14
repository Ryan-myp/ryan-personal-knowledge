# Google Ads API Streaming Mutate 深度指南：批量写入、流式API、错误处理

> **领域**: 广告投放 / GOOGLE_ADS
> **深度**: ⭐⭐⭐⭐⭐ 实战级指南
> **标签**: GOOGLE_ADS, 广告投放
> **更新时间**: 2026-08-14
> **类型**: 深度知识文档

---

## 一、核心概念与架构

### 1.1 什么是 Streaming Mutate

Streaming Mutate 是 Google Ads API 提供的双向流式批量写入接口。

它属于 gRPC 的 Bidirectional Streaming RPC。

客户端与服务器之间建立一条长期存活的流。

客户端不断向流里写入 MutateOperation。

服务器不断从流里读操作并执行。

结果以流式响应逐批返回。

这和传统的一次性 Mutate RPC 有本质区别。

```ascii
┌────────────────────────────────────────────────────────────┐
│                 Google Ads API 写入模型                      │
│                                                            │
│  传统 Mutate (Unary RPC)         Streaming Mutate (BiDi)    │
│  ┌──────────┐                    ┌──────────┐               │
│  │ 客户端    │                    │ 客户端    │               │
│  │          │                    │          │               │
│  │  request │                    │  stream  │               │
│  │  ──────▶ │                    │  ──────▶ │  op1          │
│  │          │                    │  ──────▶ │  op2          │
│  │  response│                    │  ──────▶ │  op3 ...      │
│  │  ◀────── │                    │  ──────▶ │               │
│  │          │                    │  ◀────── │  result1      │
│  └──────────┘                    │  ◀────── │  result2 ...  │
│                                  │          │               │
│  请求→响应 一次完成                │  write→  │  双向实时      │
│  结果整体返回                     │  read 循环               │
│                                  └──────────┘               │
└────────────────────────────────────────────────────────────┘
```

Streaming Mutate 的核心价值：

1. 支持海量操作而不受单请求大小限制。
2. 结果可以边写入边读取，无需等待整个请求结束。
3. 配合 partial_failure 可以做细粒度错误处理。
4. 底层走 HTTP/2，支持多路复用与头部压缩。

在 Google Ads API 中，凡是支持 mutate 的 Service。

几乎都配套提供了 Streaming Mutate 版本。

例如 CampaignService.StreamMutateCampaigns。

以及 AdGroupCriterionService.StreamMutateAdGroupCriteria。

### 1.2 为什么需要双向流

传统 Unary RPC 的问题：

1. 单次请求体有大小上限。
2. 操作越多，单次响应越慢，越容易超时。
3. 一旦部分失败，整体响应逻辑变复杂。
4. 无法在请求途中追加操作。

双向流解决了这些问题。

客户端可以分批写入操作。

服务器分批处理并分批返回。

流内还可以动态控制节奏。

发现限流时，可以暂停写入而不是放弃整批。

```ascii
单次请求体大小 vs 流式写入

Unary Mutate:
┌────────────────────────────┐
│ [op1 op2 ... op10000]  ← 一次性全部塞进一个请求
└────────────────────────────┘
   ▲ 请求体越大越容易超限/超时

Streaming Mutate:
┌────────────────────────────┐
│ write([op1..op500])        │
│ write([op501..op1000])     │  ← 分批、可控、可续
│ write([op1001..op1500])    │
│ ...                        │
└────────────────────────────┘
```

### 1.3 总体架构图

整个 Streaming Mutate 的调用链如下。

```ascii
┌──────────────────────────────────────────────────────────┐
│                     业务层 (你的服务)                       │
│  ┌──────────┐  ┌───────────┐  ┌──────────────────────┐   │
│  │ 任务队列   │  │ 批量生成器 │  │ 调度器/限速器         │   │
│  │ (Redis/KV)│  │ (ops批量) │  │ (令牌桶+并发控制)     │   │
│  └──────────┘  └───────────┘  └──────────────────────┘   │
└──────────────────────┬───────────────────────────────────┘
                       │ 构造 MutateOperation 列表
                       ▼
┌──────────────────────────────────────────────────────────┐
│                 Google Ads Python 客户端                   │
│  GoogleAdsClient.load_from_storage('google-ads.yaml')     │
│  get_service('AdGroupCriterionService')                   │
│  stream_mutate_ad_group_criteria(...)                     │
└──────────────────────┬───────────────────────────────────┘
                       │ gRPC (HTTP/2)
                       ▼
┌──────────────────────────────────────────────────────────┐
│              googleads.googleapis.com                     │
│              (v24 / 端点)                                 │
│  header: Authorization / developer-token /                │
│          login-customer-id                                │
│  请求: customer_id + operations[] + partial_failure       │
│  响应: results[] + partial_failure_error                  │
└──────────────────────────────────────────────────────────┘
```

### 1.4 与普通 Mutate 的对比

| 维度 | 普通 Mutate | Streaming Mutate |
|------|-------------|------------------|
| RPC 类型 | Unary（一元） | 双向流（BiDi stream） |
| 请求模型 | 一次性全量提交 | 分批写入流 |
| 响应模型 | 整体返回 | 边写边读 |
| 单请求操作数 | 有官方上限 | 流内可分批，总量更大 |
| 超时敏感性 | 高（大请求易超时） | 低（分批后单批小） |
| 错误处理 | partial_failure | partial_failure + 流级错误 |
| 底层协议 | REST/JSON 或 gRPC | gRPC over HTTP/2 |
| 适用场景 | 中小批量 | 十万级~百万级 |
| 复杂度 | 低 | 中（需管理流生命周期） |

### 1.5 适用场景

Streaming Mutate 适合以下业务场景。

1. 大批量创建关键词、广告、广告组。
2. 大批量更新出价、暂停/启用操作。
3. 需要实时获知每条操作结果的场景。
4. 需要精细记录失败原因并单独重试的场景。
5. 需要长时间运行的批量任务。

不适合的场景：

1. 单次只提交几十个操作的小任务。
2. 对延迟极其敏感、需要立即拿到单条结果。
3. 没有流管理能力的简单脚本。

| 场景 | 操作量 | 推荐方案 |
|------|--------|----------|
| 新增 50 个关键词 | 小 | 普通 Mutate |
| 更新 2000 个出价 | 中 | 普通 Mutate 分批 |
| 建 5 万关键词 | 大 | Streaming Mutate |
| 100 万关键词扩词 | 超大 | Streaming + 分布式任务 |
| 全账户资产迁移 | 大 | Streaming + partial_failure |

### 1.6 关键概念词汇表

| 术语 | 含义 |
|------|------|
| MutateOperation | 一次写操作的描述（create/update/remove） |
| partial_failure | 部分失败模式，允许批内部分操作失败 |
| GoogleAdsFailure | 部分失败时的错误详情对象 |
| quota units | API 配额消耗单位，每个请求消耗若干 |
| batch | 一批操作的集合 |
| stream | gRPC 双向流 |
| BiDi | Bidirectional，双向 |
| HTTP/2 | gRPC 底层传输协议 |
| resource_name | 资源唯一标识，如 customers/123/campaigns/456 |

## 二、深度原理解析

### 2.1 RPC 方法形态：StreamMutate

Google Ads API v24 中，每个 Service 提供 stream 版本。

以 AdGroupCriterionService 为例。

普通方法：`MutateAdGroupCriteria`。

流式方法：`StreamMutateAdGroupCriteria`。

请求消息：`StreamMutateAdGroupCriteriaRequest`。

响应流：`StreamMutateAdGroupCriteriaResponse`。

```ascii
RPC 方法形态 (gRPC proto):

service AdGroupCriterionService {
  // 普通一元方法
  rpc MutateAdGroupCriteria(MutateAdGroupCriteriaRequest)
      returns (MutateAdGroupCriteriaResponse);

  // 流式方法：请求是流，响应也是流
  rpc StreamMutateAdGroupCriteria(
      stream StreamMutateAdGroupCriteriaRequest)
      returns (stream StreamMutateAdGroupCriteriaResponse);
}

service CampaignService {
  rpc MutateCampaigns(MutateCampaignsRequest)
      returns (MutateCampaignsResponse);

  rpc StreamMutateCampaigns(
      stream StreamMutateCampaignsRequest)
      returns (stream StreamMutateCampaignsResponse);
}
```

在 Python google-ads 库中。

`stream_mutate_*` 方法返回一个迭代器。

每次迭代返回一个响应。

响应里包含该批操作的结果。

```python
# 示例：流式更新广告系列状态
from google.ads.googleads.client import GoogleAdsClient

client = GoogleAdsClient.load_from_storage("google-ads.yaml")
service = client.get_service("CampaignService")

# 构造一批操作
operations = []
for campaign_id in campaign_ids:
    op = client.get_type("CampaignOperation")
    campaign = op.update
    campaign.resource_name = (
        f"customers/{customer_id}/campaigns/{campaign_id}"
    )
    campaign.status = client.enums.CampaignStatusEnum.PAUSED
    op.update_mask.append("status")
    operations.append(op)

# 流式写入（每批一个请求，依次写入流）
with service.stream_mutate_campaigns(
    customer_id=customer_id,
    operations=operations,
    enable_partial_failure=True,
) as responses:
    for response in responses:
        for result in response.results:
            print(f"已暂停: {result.resource_name}")
```

### 2.2 流内分批写入的原理

流式接口在底层其实是"多次 write"。

Python 库的 `stream_*` 方法帮你封装了细节。

但理解底层分批非常重要。

每个请求（流中的一个 write）可以携带一批操作。

服务端按请求顺序处理。

每个响应对应一个请求的结果。

```ascii
流内分批模型:

Client                                 Server
  │                                      │
  │── write(req1: ops[0..999]) ────────▶ │ 处理批1
  │◀───── resp1 (批1结果) ──────────────│
  │── write(req2: ops[1000..1999]) ────▶ │ 处理批2
  │◀───── resp2 (批2结果) ──────────────│
  │── write(req3: ops[2000..2999]) ────▶ │ 处理批3
  │◀───── resp3 (批3结果) ──────────────│
  │── end stream (close) ──────────────▶│
  │◀───── stream end ───────────────────│
```

关键点：

1. 批大小决定单次 write 的请求体大小。
2. 批越大，单批耗时越长，越容易触发超时。
3. 批太小，write 次数多，网络往返开销大。
4. 需要找到吞吐与稳定性的平衡点。

### 2.3 官方限制详解

Google Ads API 对 mutate 操作有明确限制。

#### 2.3.1 单请求操作数限制

普通 Mutate 单请求有操作数上限。

大量操作必须分批。

具体上限在不同服务与配置下可能不同。

推荐的做法是不超过官方文档标注的阈值。

#### 2.3.2 请求体大小限制

单个请求的请求体有大小上限。

超大文本、Base64 图片都会占请求体空间。

#### 2.3.3 流内总操作数

Streaming Mutate 单条流内可写入大量操作。

但仍建议分批写入。

保持单批在安全阈值内。

```ascii
限制与建议:

┌────────────────────────────────┐
│ 单批操作数: 建议 ≤ 1000~2000    │
│ 单批请求体: 建议 ≤ 几 MB        │
│ 流内总操作: 可大，但分批         │
│ 超时: 单批处理超时会断流         │
│ 配额: 每个请求消耗 quota units  │
└────────────────────────────────┘
```

| 限制维度 | 官方约束 | 实践建议 |
|----------|---------|---------|
| 单请求操作数 | 有硬上限 | 每批 500~2000 |
| 单请求大小 | 有上限 | 控制文本/图片大小 |
| 流内操作总数 | 宽松 | 分批写入 |
| 单批处理时长 | 超时风险 | 批内操作保持精简 |
| 配额消耗 | 每请求计费 | 合并小批、控制频率 |

### 2.4 partial_failure 原理

partial_failure 是流式批量操作的核心机制。

开启后，一批操作中允许部分失败。

失败的操作用错误对象描述。

成功的操作照常返回结果。

#### 2.4.1 开启方式

请求中设置 `enable_partial_failure=True`。

```python
request = client.get_type("MutateAdGroupCriteriaRequest")
request.customer_id = customer_id
request.enable_partial_failure = True
request.operations.extend(operations)
```

#### 2.4.2 响应结构

当部分操作失败时。

响应里出现 `partial_failure_error` 字段。

它是一个 `google.rpc.Status`。

其中 `details` 里是 `GoogleAdsFailure` 对象。

```ascii
partial_failure_error 结构:

google.rpc.Status
├── code: 3 (INVALID_ARGUMENT)
├── message: "partial failure occurred"
└── details: [
      Any(
        type: "type.googleapis.com/google.ads.googleads.v24.errors.GoogleAdsFailure"
        value: GoogleAdsFailure {
          errors: [
            ErrorDetails {
              error_code: { campaign_error: DUPLICATE_CAMPAIGN_NAME }
              message: "...",
              trigger: "...",
              location: { field_path_elements: [...] }
            },
            ...
          ]
        }
      )
    ]
```

#### 2.4.3 错误与操作的对应关系

每个错误对象没有直接的"操作索引"字段。

需要通过 `location` 中的字段路径来定位。

更常见的做法是遍历失败错误。

根据错误内容分类处理。

```python
if response.partial_failure_error:
    for error in response.partial_failure_error.details:
        # error 是 GoogleAdsFailure 类型
        failure = error
        for e in failure.errors:
            print("错误码:", e.error_code)
            print("消息:", e.message)
            print("触发值:", e.trigger)
            # 提取字段路径
            for element in e.location.field_path_elements:
                print("  字段:", element.field_name,
                      "索引:", element.index)
```

#### 2.4.4 成功/失败分类

判断操作是否成功：

1. 结果在 `response.results` 中 → 成功。
2. 错误在 `partial_failure_error` 中 → 失败。

需要注意索引对齐。

当批内操作部分失败时。

results 里只包含成功的操作。

失败的不会出现在 results。

```python
def classify_batch(ops, response):
    """把操作按成功/失败分类"""
    success = list(response.results)

    failures = []
    if response.partial_failure_error:
        for detail in response.partial_failure_error.details:
            google_ads_failure = detail
            for error in google_ads_failure.errors:
                failures.append(error)

    # 使用 location 索引来匹配原始操作
    failed_indices = set()
    for error in failures:
        for element in error.location.field_path_elements:
            if element.index is not None:
                failed_indices.add(element.index)

    failed_ops = [ops[i] for i in failed_indices if i < len(ops)]
    success_ops = [op for i, op in enumerate(ops)
                   if i not in failed_indices]
    return success_ops, failed_ops, failures
```

### 2.5 常见错误类型与错误码

#### 2.5.1 错误码分类

Google Ads API 错误按 domain 分类。

常见错误码枚举：

| 枚举 | 示例错误码 | 含义 |
|------|-----------|------|
| AdGroupCriterionError | DUPLICATE_KEYWORD | 关键词重复 |
| AdGroupError | INVALID_STATUS | 广告组状态非法 |
| CampaignError | DUPLICATE_CAMPAIGN_NAME | 系列名重复 |
| QuotaError | RESOURCE_EXHAUSTED | 配额耗尽 |
| AuthenticationError | INVALID_TOKEN | 令牌无效 |
| AuthorizationError | USER_PERMISSION_DENIED | 权限不足 |
| InternalError | INTERNAL_ERROR | 服务端内部错误 |
| RequestError | INVALID_RESOURCE_NAME | 资源名非法 |
| RangeError | TOO_MANY_RESULTS | 结果过多 |
| ResourceCountLimitExceededError | LIMIT_EXCEEDED | 资源数量超限 |

#### 2.5.2 可重试与不可重试错误

判断错误是否可以重试是错误处理的关键。

| 错误类别 | 示例 | 是否可重试 |
|----------|------|-----------|
| 配额/限流 | RESOURCE_EXHAUSTED | 是（退避后重试） |
| 瞬时错误 | INTERNAL_ERROR | 是（退避后重试） |
| 超时 | DEADLINE_EXCEEDED | 是 |
| 网络错误 | UNAVAILABLE | 是 |
| 权限错误 | USER_PERMISSION_DENIED | 否 |
| 认证错误 | INVALID_TOKEN | 否（需换 token） |
| 校验错误 | DUPLICATE_KEYWORD | 否（需修正数据） |
| 资源不存在 | NOT_FOUND | 否 |
| 非法参数 | INVALID_ARGUMENT | 否 |

### 2.6 重试与退避策略

#### 2.6.1 指数退避公式

```text
sleep = min(cap, base * 2^attempt) + jitter
```

其中：

- base：初始等待，通常 1 秒。
- cap：最大等待，通常 30~60 秒。
- jitter：随机抖动，避免惊群。

```python
import random
import time
from google.ads.googleads.errors import GoogleAdsException


def retry_with_backoff(fn, max_retries=5, base=1.0, cap=30.0):
    """带指数退避和抖动的通用重试"""
    for attempt in range(max_retries):
        try:
            return fn()
        except GoogleAdsException as e:
            if not is_retryable(e):
                raise
            sleep_time = min(cap, base * (2 ** attempt))
            sleep_time += random.uniform(0, sleep_time * 0.3)
            print(f"[retry {attempt+1}/{max_retries}] "
                  f"等待 {sleep_time:.2f}s")
            time.sleep(sleep_time)
    raise RuntimeError("重试次数用尽")


def is_retryable(exc):
    """判断错误是否可重试"""
    for err in exc.failure.errors:
        code = err.error_code
        # RESOURCE_EXHAUSTED / INTERNAL_ERROR / UNAVAILABLE
        if code.quota_error == code.QuotaErrorEnum.RESOURCE_EXHAUSTED:
            return True
        if code.internal_error == code.InternalErrorEnum.INTERNAL_ERROR:
            return True
    return False
```

#### 2.6.2 抖动类型

| 抖动类型 | 公式 | 特点 |
|----------|------|------|
| 无抖动 | base * 2^n | 多个客户端同时重试会撞车 |
| 全抖动 | random(0, base*2^n) | 平均等待减半，惊群最小 |
| 等量抖动 | base*2^n + random(0, 固定) | 下限保证，防过频 |

推荐使用全抖动。

#### 2.6.3 重试时的幂等性

create 类操作重试会重复创建。

update/remove 类操作天然幂等。

对策：

1. 优先使用 update 而非 create。
2. create 前先查询是否已存在。
3. 用外部业务 ID 去重。

```python
def upsert_keyword(client, customer_id, ad_group_id, keyword_text):
    """幂等创建关键词：先查后建"""
    gaql = f"""
        SELECT ad_group_criterion.keyword.text
        FROM ad_group_criterion
        WHERE ad_group_criterion.type = 'KEYWORD'
          AND ad_group_criterion.keyword.text = '{keyword_text}'
          AND ad_group_criterion.status != 'REMOVED'
    """
    resp = client.google_ads_service.search(
        customer_id=customer_id, query=gaql
    )
    if list(resp):
        print("已存在,跳过创建")
        return None
    # 不存在才创建
    return create_keyword(client, customer_id, ad_group_id, keyword_text)
```

### 2.7 速率限制与配额原理

#### 2.7.1 配额单位

Google Ads API 每个请求消耗配额单位。

配额策略按账户、按开发者令牌等维度管控。

超限返回 `RESOURCE_EXHAUSTED`。

```ascii
配额消耗路径:

请求 → 配额桶 → 消耗 units
              │
              ├─ 超过每分钟桶 → 429 限流
              ├─ 超过每小时桶 → 429 限流
              └─ 超过每日桶  → 429 限流
```

#### 2.7.2 流式请求的配额

每条流式请求（每个 write）都消耗配额。

所以流式写入也要控制频率。

不能无限快速 write。

#### 2.7.3 削峰与平滑

为应对配额，需要做客户端削峰。

常见做法：

1. 令牌桶限速。
2. 控制并发流数量。
3. 分批写入，控制每批大小。
4. 监控配额使用率动态调整。

```python
import threading
import time


class TokenBucket:
    """令牌桶限速器"""

    def __init__(self, rate, capacity):
        self.rate = rate           # 每秒补充令牌数
        self.capacity = capacity   # 桶容量
        self.tokens = capacity
        self.lock = threading.Lock()
        self.last = time.monotonic()

    def take(self, n=1):
        """取 n 个令牌，不足则阻塞等待"""
        with self.lock:
            now = time.monotonic()
            elapsed = now - self.last
            self.tokens = min(
                self.capacity,
                self.tokens + elapsed * self.rate
            )
            self.last = now
            if self.tokens >= n:
                self.tokens -= n
                return
            need = n - self.tokens
            wait = need / self.rate
            time.sleep(wait)
            self.tokens = 0
            self.last = time.monotonic()
```

### 2.8 认证与请求头

#### 2.8.1 必需头

每个 Google Ads API 请求都必须带：

1. `Authorization: Bearer <OAuth2 token>`
2. `developer-token`
3. `login-customer-id`（MCC 代理时）

```python
headers = {
    "Authorization": f"Bearer {access_token}",
    "developer-token": developer_token,
    "login-customer-id": login_customer_id,
    "Content-Type": "application/json",
}
```

#### 2.8.2 OAuth2 流程

```ascii
OAuth2 授权码流程:

┌─────────┐   1. 请求授权    ┌──────────────┐
│  用户    │ ──────────────▶ │  Google 授权  │
└─────────┘                 │  服务器       │
      ▲                     └──────────────┘
      │ 2. 授权码                  │ 3. 换取
      └────────────────────────────┘ token
                                   ▼
                     ┌──────────────────────┐
                     │  客户端存储 refresh   │
                     │  token + access token│
                     └──────────────────────┘
                           │ 4. 调用 API 带
                           ▼ access token
                     ┌──────────────────────┐
                     │   Google Ads API     │
                     └──────────────────────┘
```

#### 2.8.3 流内请求上下文

Streaming Mutate 的每条请求都是独立 RPC。

所以每条请求都要带完整 header。

在 Python 库中，`stream_mutate_*` 自动带上。

但自定义 gRPC 时要注意。

```python
from google.ads.googleads import util

# 自定义元数据
metadata = [
    ("developer-token", developer_token),
    ("login-customer-id", login_customer_id),
]

with service.stream_mutate_ad_group_criteria(
    request=request,
    metadata=metadata,
) as responses:
    for response in responses:
        handle(response)
```

### 2.9 超时与流生命周期

#### 2.9.1 超时设置

每个 RPC 有 deadline。

默认可能不够长。

长流任务要设置较大超时。

```python
from google.ads.googleads.client import GoogleAdsClient

client = GoogleAdsClient.load_from_storage("google-ads.yaml")

# 设置 RPC 超时（秒）
client.google_ads_service.search(
    customer_id=customer_id,
    query=query,
    timeout=120,
)
```

#### 2.9.2 流关闭

流使用完毕必须关闭。

Python 的 `with` 语句自动管理。

也可以手动 `close()`。

```python
# with 方式
with service.stream_mutate_campaigns(request=req) as responses:
    for resp in responses:
        pass

# 手动方式
stream = service.stream_mutate_campaigns(request=req)
try:
    for resp in stream:
        pass
finally:
    stream.close()
```

#### 2.9.3 断流与恢复

网络中断会导致流断开。

已发送未确认的操作状态不确定。

需要重新建立流。

配合幂等操作避免重复。

```ascii
断流恢复流程:

流断开
  │
  ▼
判断已发送操作是否确认
  │
  ├─ 已确认 → 不重发
  ├─ 未确认且幂等(update) → 安全重发
  └─ 未确认且非幂等(create) → 先查重再重发
```

### 2.10 HTTP/2 与多路复用

gRPC 基于 HTTP/2。

HTTP/2 提供多路复用。

多条流共享一个 TCP 连接。

头部压缩减少开销。

```ascii
HTTP/2 多路复用:

┌─────────── TCP 连接 ───────────┐
│  stream 1: 请求/响应           │
│  stream 2: 请求/响应           │
│  stream 3: 请求/响应           │
│  stream 4: 请求/响应           │
└────────────────────────────────┘

单连接并发多个流，互不阻塞。
```

对 Streaming Mutate 的意义：

1. 多个 stream 可并发。
2. 提高整体吞吐。
3. 减少连接建立开销。

但并发流也要受配额限制。

不能无限开流。

## 三、生产环境实战

### 3.1 业务场景一：代理商 10 万+ 关键词账户批量扩容

#### 3.1.1 场景描述

某代理商为跨境电商客户扩容关键词。

目标：在 100 个广告组中新增 10 万关键词。

每个广告组约 1000 个新关键词。

要求：

1. 全部在 2 小时内完成。
2. 失败的关键词单独记录，可重试。
3. 不能触发配额限流。

#### 3.1.2 架构设计

```ascii
代理商批量扩容架构:

┌──────────┐    生成任务      ┌─────────────┐
│ 业务数据库 │ ──────────────▶ │ 任务队列      │
│ (关键词词库)│                │ (100个广告组) │
└──────────┘                  └─────────────┘
                                    │
                                    ▼
                            ┌─────────────┐
                            │ 工作进程池    │
                            │ (4~8 workers)│
                            └─────────────┘
                                    │ 每个 worker 一条流
                                    ▼
                            ┌─────────────┐
                            │ Streaming   │
                            │ Mutate 客户端 │
                            └─────────────┘
                                    │
                                    ▼
                            ┌─────────────┐
                            │ Google Ads   │
                            │ API (v24)    │
                            └─────────────┘
```

#### 3.1.3 实现要点

1. 每个广告组一个子任务。
2. 每个 worker 一条流。
3. 每批 500 个操作。
4. 开启 partial_failure。
5. 失败操作写入失败队列。

#### 3.1.4 生产代码

```python
"""
代理商 10 万关键词批量扩容（生产级简化版）

前置：
pip install google-ads
配置 google-ads.yaml（developer_token / refresh_token /
client_id / client_secret）
"""
import concurrent.futures
import time
from collections import defaultdict

from google.ads.googleads.client import GoogleAdsClient
from google.ads.googleads.errors import GoogleAdsException

client = GoogleAdsClient.load_from_storage("google-ads.yaml")
criterion_service = client.get_service("AdGroupCriterionService")

CUSTOMER_ID = "1234567890"
BATCH_SIZE = 500
MAX_WORKERS = 8


def build_operations(ad_group_id, keywords):
    """把一个广告组的关键词构造为操作列表"""
    ops = []
    for kw in keywords:
        op = client.get_type("AdGroupCriterionOperation")
        criterion = op.create
        criterion.ad_group = (
            f"customers/{CUSTOMER_ID}/adGroups/{ad_group_id}"
        )
        criterion.keyword.text = kw["text"]
        criterion.keyword.match_type = (
            client.enums.KeywordMatchTypeEnum.PHRASE
        )
        ops.append(op)
    return ops


def streaming_create_keywords(ad_group_id, keywords):
    """用 Streaming Mutate 为单个广告组批量建词"""
    ops = build_operations(ad_group_id, keywords)
    success = []
    failed = []

    # 分批写入流
    for i in range(0, len(ops), BATCH_SIZE):
        batch = ops[i : i + BATCH_SIZE]
        try:
            with criterion_service.stream_mutate_ad_group_criteria(
                customer_id=CUSTOMER_ID,
                operations=batch,
                enable_partial_failure=True,
            ) as responses:
                for response in responses:
                    for result in response.results:
                        success.append(result.resource_name)
                    if response.partial_failure_error:
                        failed.extend(parse_failures(response))
        except GoogleAdsException as e:
            print(f"整批失败: {e}")
            failed.extend(batch)
    return success, failed


def parse_failures(response):
    """解析 partial_failure_error 中的失败信息"""
    failures = []
    for detail in response.partial_failure_error.details:
        google_ads_failure = detail
        for error in google_ads_failure.errors:
            failures.append(
                {
                    "code": error.error_code,
                    "message": error.message,
                    "trigger": error.trigger,
                }
            )
    return failures


def process_ad_group(args):
    """单个广告组的扩容任务"""
    ad_group_id, keywords = args
    t0 = time.time()
    success, failed = streaming_create_keywords(ad_group_id, keywords)
    return {
        "ad_group_id": ad_group_id,
        "total": len(keywords),
        "success": len(success),
        "failed": len(failed),
        "elapsed": time.time() - t0,
    }


def main():
    # 模拟任务：100 个广告组 × 1000 关键词 = 10 万
    tasks = [
        (
            ad_group_id,
            [{"text": f"kw-{ad_group_id}-{i}"} for i in range(1000)],
        )
        for ad_group_id in range(100001, 100101)
    ]

    results = []
    with concurrent.futures.ThreadPoolExecutor(
        max_workers=MAX_WORKERS
    ) as executor:
        futures = {
            executor.submit(process_ad_group, t): t for t in tasks
        }
        for future in concurrent.futures.as_completed(futures):
            results.append(future.result())

    total = sum(r["total"] for r in results)
    ok = sum(r["success"] for r in results)
    bad = sum(r["failed"] for r in results)
    print(f"任务完成: 总计 {total}, 成功 {ok}, 失败 {bad}")
    print(f"耗时: {max(r['elapsed'] for r in results):.1f}s")
    print(f"成功率: {ok / total * 100:.2f}%")


if __name__ == "__main__":
    main()
```

#### 3.1.5 量化指标

| 指标 | 数值 |
|------|------|
| 目标关键词量 | 100,000 |
| 广告组数 | 100 |
| 每广告组关键词 | 1,000 |
| 批大小 | 500 |
| worker 数 | 8 |
| 目标耗时 | < 2 小时 |
| 成功率目标 | > 99.9% |
| 失败重试次数 | 3 次指数退避 |

### 3.2 业务场景二：电商大促前批量调价

#### 3.2.1 场景描述

某电商平台大促（双11/黑五）前。

需要把 5000 个关键词的出价批量调整。

目标：根据最近 30 天 ROAS 数据动态调价。

- ROAS > 3 的关键词：提高出价 20%。
- 1 < ROAS ≤ 3 的关键词：保持。
- ROAS ≤ 1 的关键词：降低出价 30%。

#### 3.2.2 实现代码

```python
"""
电商大促前批量调价

流程:
1. generate_report 拉取近30天关键词级 ROAS
2. 计算目标出价
3. Streaming Mutate 批量更新
"""
from google.ads.googleads.client import GoogleAdsClient

client = GoogleAdsClient.load_from_storage("google-ads.yaml")
service = client.get_service("AdGroupCriterionService")
google_ads_service = client.get_service("GoogleAdsService")

CUSTOMER_ID = "1234567890"


def fetch_keyword_roas():
    """拉取关键词级 ROAS 数据"""
    query = """
        SELECT
          ad_group_criterion.resource_name,
          ad_group_criterion.cpc_bid_micros,
          metrics.conversions_value,
          metrics.cost_micros,
          metrics.clicks,
          metrics.impressions,
          metrics.conversions,
          metrics.ctr
        FROM ad_group_criterion
        WHERE segments.date DURING LAST_30_DAYS
          AND ad_group_criterion.type = 'KEYWORD'
        ORDER BY metrics.cost_micros DESC
    """
    rows = google_ads_service.search(
        customer_id=CUSTOMER_ID, query=query
    )
    data = []
    for row in rows:
        cost = row.metrics.cost_micros
        value = row.metrics.conversions_value
        roas = value / cost if cost else 0
        data.append(
            {
                "resource_name": row.ad_group_criterion.resource_name,
                "cpc_bid_micros": row.ad_group_criterion.cpc_bid_micros,
                "roas": roas,
                "clicks": row.metrics.clicks,
            }
        )
    return data


def build_bid_operations(data):
    """根据 ROAS 计算新出价并构造操作"""
    ops = []
    for item in data:
        if item["clicks"] < 10:
            continue  # 数据太少，不动
        old_bid = item["cpc_bid_micros"]
        roas = item["roas"]

        if roas > 3.0:
            new_bid = int(old_bid * 1.2)
        elif roas <= 1.0:
            new_bid = int(old_bid * 0.7)
        else:
            continue

        op = client.get_type("AdGroupCriterionOperation")
        criterion = op.update
        criterion.resource_name = item["resource_name"]
        criterion.cpc_bid_micros = new_bid
        op.update_mask.append("cpc_bid_micros")
        ops.append(op)
    return ops


def stream_update_bids(operations):
    """流式批量更新出价"""
    success = 0
    failed = 0
    for i in range(0, len(operations), 1000):
        batch = operations[i : i + 1000]
        with service.stream_mutate_ad_group_criteria(
            customer_id=CUSTOMER_ID,
            operations=batch,
            enable_partial_failure=True,
        ) as responses:
            for response in responses:
                success += len(response.results)
                if response.partial_failure_error:
                    failed += count_failures(response)
    return success, failed


def count_failures(response):
    n = 0
    for detail in response.partial_failure_error.details:
        for _ in detail.errors:
            n += 1
    return n


def main():
    data = fetch_keyword_roas()
    ops = build_bid_operations(data)
    print(f"需要调整出价的关键词: {len(ops)}")

    # 模拟 ROAS 分布量化
    high = sum(1 for d in data if d["roas"] > 3.0)
    mid = sum(1 for d in data if 1.0 < d["roas"] <= 3.0)
    low = sum(1 for d in data if d["roas"] <= 1.0)
    print(f"ROAS>3: {high}, 1<ROAS≤3: {mid}, ROAS≤1: {low}")

    success, failed = stream_update_bids(ops)
    print(f"调价完成: 成功 {success}, 失败 {failed}")


if __name__ == "__main__":
    main()
```

#### 3.2.3 量化指标

| 指标 | 数值 |
|------|------|
| 调整关键词数 | ~5,000 |
| 调价幅度 | -30% / +20% |
| ROAS 分档 | >3 提价，≤1 降价 |
| 批大小 | 1,000 |
| 目标耗时 | < 10 分钟 |
| 期望效果 | 整体 ROAS 提升 15%+ |

### 3.3 业务场景三：游戏厂商批量创建 APP 广告系列

#### 3.3.1 场景描述

某游戏厂商要在 Google Ads 批量创建广告系列。

每个游戏有多个地区版本。

每个版本需要：

- 1 个 APP_CAMPAIGN 广告系列。
- 对应 APP_EXTENSION 资产。
- 预算与目标 CPA 配置。

批量创建 200 个广告系列。

#### 3.3.2 实现代码

```python
"""
游戏厂商批量创建 APP_CAMPAIGN 广告系列
"""
from google.ads.googleads.client import GoogleAdsClient

client = GoogleAdsClient.load_from_storage("google-ads.yaml")
campaign_service = client.get_service("CampaignService")

CUSTOMER_ID = "1234567890"


def build_campaign_operations(games):
    """为每个游戏版本构造广告系列创建操作"""
    ops = []
    for game in games:
        op = client.get_type("CampaignOperation")
        campaign = op.create

        campaign.name = f"{game['name']}-{game['region']}-iOS"
        campaign.advertising_channel_type = (
            client.enums.AdvertisingChannelTypeEnum.APP
        )
        campaign.advertising_channel_sub_type = (
            client.enums.AdvertisingChannelSubTypeEnum.APP_CAMPAIGN
        )
        campaign.status = client.enums.CampaignStatusEnum.PAUSED

        # 预算
        budget = client.get_type("CampaignBudget")
        budget.name = f"Budget-{game['name']}"
        budget.amount_micros = game["budget_micros"]
        budget.delivery_method = (
            client.enums.BudgetDeliveryMethodEnum.STANDARD
        )
        campaign.campaign_budget = budget

        # 目标 CPA 出价
        campaign.target_cpa.target_cpa_micros = game["target_cpa_micros"]

        # APP 相关设置
        campaign.app_campaign_setting.app_id = game["app_id"]
        campaign.app_campaign_setting.app_store = (
            client.enums.AppCampaignAppStoreEnum.APPLE_APP_STORE
        )
        campaign.app_campaign_setting.bidding_strategy_goal_type = (
            client.enums.AppCampaignBiddingStrategyGoalTypeEnum
            .OPTIMIZE_INSTALLS_TARGET_INSTALL_COST
        )

        ops.append(op)
    return ops


def stream_create_campaigns(ops):
    """流式批量创建广告系列"""
    results = []
    for i in range(0, len(ops), 50):
        batch = ops[i : i + 50]
        with campaign_service.stream_mutate_campaigns(
            customer_id=CUSTOMER_ID,
            operations=batch,
            enable_partial_failure=True,
        ) as responses:
            for response in responses:
                for result in response.results:
                    results.append(result.resource_name)
    return results


def main():
    games = [
        {
            "name": "KingdomRush",
            "region": "US",
            "budget_micros": 50_000_000,     # $50/天
            "target_cpa_micros": 3_500_000,  # $3.5
            "app_id": "com.studio.kingdomrush",
        }
        for _ in range(200)
    ]
    ops = build_campaign_operations(games)
    created = stream_create_campaigns(ops)
    print(f"成功创建 {len(created)} 个广告系列")
    print(f"首例: {created[0] if created else '无'}")


if __name__ == "__main__":
    main()
```

#### 3.3.3 量化指标

| 指标 | 数值 |
|------|------|
| 广告系列数 | 200 |
| 单日预算 | $50 |
| 目标 CPA | $3.5 |
| 批大小 | 50（创建类批小） |
| 目标耗时 | < 5 分钟 |
| 出价策略 | OPTIMIZE_INSTALLS_TARGET_INSTALL_COST |
| 系列子类型 | APP_CAMPAIGN |

### 3.4 业务场景四：APP 增长团队批量暂停/恢复

#### 3.4.1 场景描述

APP 增长团队每天按留存数据决定投放启停。

早上 9 点批量暂停表现差的广告组。

晚上 21 点批量恢复。

涉及 8000 个广告组。

#### 3.4.2 实现代码

```python
"""
APP 增长团队批量启停广告组
"""
from google.ads.googleads.client import GoogleAdsClient

client = GoogleAdsClient.load_from_storage("google-ads.yaml")
ad_group_service = client.get_service("AdGroupService")

CUSTOMER_ID = "1234567890"


def build_status_operations(ad_group_ids, status):
    """构造批量状态更新操作"""
    ops = []
    for ag_id in ad_group_ids:
        op = client.get_type("AdGroupOperation")
        ag = op.update
        ag.resource_name = f"customers/{CUSTOMER_ID}/adGroups/{ag_id}"
        ag.status = status
        op.update_mask.append("status")
        ops.append(op)
    return ops


def stream_update_status(ad_group_ids, status):
    """流式批量更新广告组状态"""
    ops = build_status_operations(ad_group_ids, status)
    ok = 0
    bad = 0
    for i in range(0, len(ops), 1000):
        batch = ops[i : i + 1000]
        with ad_group_service.stream_mutate_ad_groups(
            customer_id=CUSTOMER_ID,
            operations=batch,
            enable_partial_failure=True,
        ) as responses:
            for response in responses:
                ok += len(response.results)
                if response.partial_failure_error:
                    for detail in response.partial_failure_error.details:
                        bad += len(detail.errors)
    return ok, bad


def main():
    # 模拟 8000 个广告组
    paused_ids = list(range(200001, 208001))

    ok, bad = stream_update_status(
        paused_ids,
        client.enums.AdGroupStatusEnum.PAUSED,
    )
    print(f"批量暂停: 成功 {ok}, 失败 {bad}")


if __name__ == "__main__":
    main()
```

#### 3.4.3 量化指标

| 指标 | 数值 |
|------|------|
| 广告组数 | 8,000 |
| 操作类型 | 暂停/恢复 |
| 执行窗口 | 早 9:00 / 晚 21:00 |
| 批大小 | 1,000 |
| 单次耗时 | < 3 分钟 |
| 每日调用 | 2 次 |

### 3.5 业务场景五：品牌客户全账户资产迁移

#### 3.5.1 场景描述

某品牌客户更换代理商。

需要把旧账户的所有广告资产迁移。

涉及：

- 10 万关键词。
- 5 万广告（含响应式搜索广告 RSA）。
- 2 万广告组。
- 资产（SITELINK/CALLOUT/IMAGE 等）。

分批、带依赖顺序迁移。

#### 3.5.2 依赖顺序

```ascii
迁移依赖顺序:

Campaign ──▶ AdGroup ──▶ Keyword
   │             │
   │             └──▶ Ad (RSA等)
   │
   ├──▶ Budget
   ├──▶ Asset (SITELINK/CALLOUT/IMAGE)
   └──▶ ConversionAction
```

必须先建父资源，拿到 resource_name。

再建子资源。

#### 3.5.3 迁移引擎代码

```python
"""
品牌客户全账户迁移引擎（阶段化 + 流式写入）
"""
import time
from google.ads.googleads.client import GoogleAdsClient

client = GoogleAdsClient.load_from_storage("google-ads.yaml")
campaign_service = client.get_service("CampaignService")
ad_group_service = client.get_service("AdGroupService")
criterion_service = client.get_service("AdGroupCriterionService")

CUSTOMER_ID = "1234567890"


class MigrationEngine:
    def __init__(self, customer_id):
        self.customer_id = customer_id
        self.phase_stats = {}

    def run_phase(self, name, service, stream_method, ops):
        """执行一个迁移阶段"""
        t0 = time.time()
        ok, bad, errors = self._stream_mutate(
            service, stream_method, ops, name
        )
        self.phase_stats[name] = {
            "total": len(ops),
            "ok": ok,
            "bad": bad,
            "elapsed": time.time() - t0,
        }
        print(
            f"[阶段:{name}] 成功 {ok} 失败 {bad} "
            f"耗时 {self.phase_stats[name]['elapsed']:.1f}s"
        )
        return errors

    def _stream_mutate(self, service, stream_method, ops, phase):
        ok = 0
        bad = 0
        errors = []
        for i in range(0, len(ops), 500):
            batch = ops[i : i + 500]
            stream_fn = getattr(service, stream_method)
            with stream_fn(
                customer_id=self.customer_id,
                operations=batch,
                enable_partial_failure=True,
            ) as responses:
                for response in responses:
                    ok += len(response.results)
                    if response.partial_failure_error:
                        for detail in (
                            response.partial_failure_error.details
                        ):
                            for error in detail.errors:
                                bad += 1
                                errors.append(
                                    f"{phase}: {error.message}"
                                )
        return ok, bad, errors


def build_campaigns():
    """阶段1：创建 Campaign（模拟）"""
    ops = []
    for i in range(100):
        op = client.get_type("CampaignOperation")
        c = op.create
        c.name = f"Migrated-Campaign-{i}"
        c.advertising_channel_type = (
            client.enums.AdvertisingChannelTypeEnum.SEARCH
        )
        c.status = client.enums.CampaignStatusEnum.PAUSED
        ops.append(op)
    return ops


def build_ad_groups():
    """阶段2：创建 AdGroup（模拟）"""
    ops = []
    for i in range(200):
        op = client.get_type("AdGroupOperation")
        ag = op.create
        ag.name = f"Migrated-AdGroup-{i}"
        ag.campaign = (
            f"customers/{CUSTOMER_ID}/campaigns/900000001"
        )
        ops.append(op)
    return ops


def build_keywords():
    """阶段3：创建 Keyword（模拟）"""
    ops = []
    for i in range(500):
        op = client.get_type("AdGroupCriterionOperation")
        criterion = op.create
        criterion.ad_group = (
            f"customers/{CUSTOMER_ID}/adGroups/800000001"
        )
        criterion.keyword.text = f"migrated-kw-{i}"
        criterion.keyword.match_type = (
            client.enums.KeywordMatchTypeEnum.PHRASE
        )
        ops.append(op)
    return ops


def main():
    engine = MigrationEngine(CUSTOMER_ID)

    engine.run_phase(
        "campaigns", campaign_service,
        "stream_mutate_campaigns", build_campaigns()
    )
    engine.run_phase(
        "ad_groups", ad_group_service,
        "stream_mutate_ad_groups", build_ad_groups()
    )
    engine.run_phase(
        "keywords", criterion_service,
        "stream_mutate_ad_group_criteria", build_keywords()
    )

    print("阶段统计:", engine.phase_stats)


if __name__ == "__main__":
    main()
```

#### 3.5.4 迁移检查清单

| 阶段 | 资源 | 建议批大小 | 依赖 |
|------|------|-----------|------|
| 1 | Campaign + Budget | 100 | 无 |
| 2 | AdGroup | 500 | Campaign |
| 3 | Keyword | 500 | AdGroup |
| 4 | Ad (RSA) | 200 | AdGroup |
| 5 | Asset (SITELINK 等) | 500 | Campaign |
| 6 | ConversionAction | 100 | 无 |

### 3.6 业务场景六：直播带货实时加词

#### 3.6.1 场景描述

某直播带货团队在直播期间实时加词。

主播提到某个商品，运营立即加对应关键词。

要求毫秒级响应、低延迟。

单次加词量小（1~20 个）。

这类场景适合普通 Mutate，而非流式。

用流式反而增加复杂度。

结论：实时小批量用普通 Mutate。

Streaming Mutate 用于直播后的批量沉淀。

```python
"""
直播带货实时加词（普通 Mutate，低延迟）
"""
from google.ads.googleads.client import GoogleAdsClient

client = GoogleAdsClient.load_from_storage("google-ads.yaml")
service = client.get_service("AdGroupCriterionService")

CUSTOMER_ID = "1234567890"


def realtime_add_keywords(ad_group_id, keyword_texts):
    """直播中实时加词，立即返回结果"""
    ops = []
    for text in keyword_texts:
        op = client.get_type("AdGroupCriterionOperation")
        criterion = op.create
        criterion.ad_group = (
            f"customers/{CUSTOMER_ID}/adGroups/{ad_group_id}"
        )
        criterion.keyword.text = text
        criterion.keyword.match_type = (
            client.enums.KeywordMatchTypeEnum.BROAD
        )
        ops.append(op)

    response = service.mutate_ad_group_criteria(
        customer_id=CUSTOMER_ID,
        operations=ops,
        enable_partial_failure=True,
    )

    created = [r.resource_name for r in response.results]
    failed = []
    if response.partial_failure_error:
        for detail in response.partial_failure_error.details:
            for e in detail.errors:
                failed.append(e.message)
    return created, failed


def main():
    # 直播中实时添加 10 个关键词
    created, failed = realtime_add_keywords(
        ad_group_id=300001,
        keyword_texts=[
            "直播新款连衣裙", "夏季连衣裙爆款", "显瘦连衣裙",
        ],
    )
    print("实时加词成功:", created)
    print("失败:", failed)


if __name__ == "__main__":
    main()
```

#### 3.6.2 实时 vs 批量选型

| 维度 | 实时加词 | 批量沉淀 |
|------|---------|---------|
| 操作量 | 1~20 | 数千~十万 |
| 接口 | 普通 Mutate | Streaming Mutate |
| 延迟要求 | 毫秒级 | 分钟级 |
| 错误处理 | 单次返回 | partial_failure 流式 |
| 典型触发 | 主播话术 | 直播结束脚本 |

### 3.7 分布式设计：百万级操作

#### 3.7.1 架构

当操作量达到百万级时。

单机单流无法在合理时间内完成。

需要分布式写入。

```ascii
百万级分布式写入架构:

┌─────────────────────────────────────┐
│             任务分发中心               │
│  ┌───────────┐  ┌─────────────────┐ │
│  │ 操作生成器  │  │ 分片器 (按客户ID/ │ │
│  │ (百万ops)  │  │  广告组/业务键)   │ │
│  └───────────┘  └─────────────────┘ │
└──────────────┬──────────────────────┘
               │ 分片后进入队列
               ▼
        ┌──────────────┐
        │  任务队列      │  (Kafka / Redis Stream)
        │  partition 0  │──▶ Worker 0
        │  partition 1  │──▶ Worker 1
        │  partition 2  │──▶ Worker 2
        │  partition 3  │──▶ Worker 3
        └──────────────┘
               │
               ▼
        ┌──────────────────────────┐
        │ 每个 Worker:              │
        │  - 令牌桶限速              │
        │  - Streaming Mutate 流    │
        │  - partial_failure 解析   │
        │  - 失败重试队列            │
        └──────────────────────────┘
```

#### 3.7.2 分片策略

| 分片键 | 优点 | 缺点 |
|--------|------|------|
| 客户 ID | 天然隔离 | 大客户成热点 |
| 广告组 ID | 细粒度 | 同一广告组并发冲突 |
| 业务键（SKU/游戏ID） | 业务友好 | 需自建映射 |
| 哈希取模 | 均匀分布 | 无业务语义 |

推荐：按广告组分片 + 哈希取模扩容。

#### 3.7.3 Worker 职责

1. 从队列消费任务分片。
2. 令牌桶限速。
3. 构造操作并分批写入流。
4. 解析 partial_failure。
5. 可重试错误退避重试。
6. 不可重试错误落库。

#### 3.7.4 Go 并发实现示例

```go
// 百万级关键词写入 Worker（Go 并发示例）
package main

import (
	"context"
	"fmt"
	"log"
	"sync"
	"time"
)

// 生产环境请使用 google.golang.org/api 生成的
// googleads/v24 services 客户端代码。
// 此处以伪代码结构展示并发写入骨架。

const (
	customerID     = "1234567890"
	developerToken = "your-developer-token"
	loginCustomer  = "1234567890"
	batchSize      = 500
	workers        = 4
)

// TokenBucket 令牌桶限速器
type TokenBucket struct {
	mu       sync.Mutex
	rate     float64
	capacity float64
	tokens   float64
	last     time.Time
}

func NewTokenBucket(rate, capacity float64) *TokenBucket {
	return &TokenBucket{
		rate:     rate,
		capacity: capacity,
		tokens:   capacity,
		last:     time.Now(),
	}
}

func (b *TokenBucket) take(n float64) {
	b.mu.Lock()
	defer b.mu.Unlock()
	for {
		now := time.Now()
		elapsed := now.Sub(b.last).Seconds()
		b.tokens += elapsed * b.rate
		if b.tokens > b.capacity {
			b.tokens = b.capacity
		}
		b.last = now
		if b.tokens >= n {
			b.tokens -= n
			return
		}
		need := n - b.tokens
		wait := time.Duration(need / b.rate * float64(time.Second))
		time.Sleep(wait)
	}
}

// writeKeywords 单个 worker 的流式写入主循环
// 伪代码：conn 为 gRPC 连接，client 为生成的 Service 客户端
func writeKeywords(ctx context.Context,
	limiter *TokenBucket,
	adGroupID int64,
	keywords []string) (ok, bad int, err error) {

	// 1. 建立流（携带 developer-token / login-customer-id metadata）
	// stream, err := client.StreamMutateAdGroupCriteria(ctx)
	// 伪代码示意:
	_ = adGroupID
	_ = developerToken
	_ = loginCustomer

	// 2. 分批写入
	for i := 0; i < len(keywords); i += batchSize {
		end := i + batchSize
		if end > len(keywords) {
			end = len(keywords)
		}
		limiter.take(1) // 限速

		// batchOps := buildOps(adGroupID, keywords[i:end])
		// req := &StreamMutateAdGroupCriteriaRequest{
		//   CustomerId:           customerID,
		//   Operations:           batchOps,
		//   EnablePartialFailure: true,
		// }
		// if err := stream.Send(req); err != nil { return }
		// resp, err := stream.Recv()
		// ok += len(resp.GetResults())
		// bad += countFailures(resp.GetPartialFailureError())

		// 伪代码推进
		ok += end - i
	}
	return ok, bad, nil
}

// buildOps 构造 AdGroupCriterionOperation 列表
// 伪代码：真实代码引用生成的 proto 类型
func buildOps(adGroupID int64, texts []string) []interface{} {
	ops := make([]interface{}, 0, len(texts))
	for _, t := range texts {
		// ops = append(ops, &AdGroupCriterionOperation{
		//   Create: &AdGroupCriterion{
		//     AdGroup: fmt.Sprintf(
		//        "customers/%s/adGroups/%d", customerID, adGroupID),
		//     Criterion: &AdGroupCriterion_Keyword{
		//       Keyword: &KeywordInfo{
		//         Text:      t,
		//         MatchType: KeywordMatchType_PHRASE,
		//       },
		//     },
		//   },
		// })
		_ = t
	}
	return ops
}

// countFailures 解析 partial failure 的错误条数
func countFailures(status interface{ GetDetails() []interface{} }) int {
	if status == nil {
		return 0
	}
	return len(status.GetDetails())
}

func main() {
	ctx := context.Background()
	limiter := NewTokenBucket(20, 20) // 每秒 20 个请求

	// conn, err := grpc.NewClient("googleads.googleapis.com:443",
	//   grpc.WithTransportCredentials(credentials.NewTLS(nil)))
	// client := adgroupcriterionservice.NewAdGroupCriterionServiceClient(conn)

	var wg sync.WaitGroup
	for w := 0; w < workers; w++ {
		wg.Add(1)
		go func(worker int) {
			defer wg.Done()
			keywords := make([]string, 25000)
			for i := range keywords {
				keywords[i] = fmt.Sprintf(
					"worker%d-keyword-%d", worker, i)
			}
			ok, bad, err := writeKeywords(
				ctx, limiter, int64(300000+worker), keywords)
			log.Printf(
				"worker %d: 成功 %d 失败 %d err=%v",
				worker, ok, bad, err)
		}(w)
	}
	wg.Wait()
	log.Println("全部 worker 完成")
	_ = ctx
}
```

#### 3.7.5 分布式注意事项

| 注意事项 | 说明 |
|----------|------|
| 配额共享 | 所有 worker 共享账户配额，需全局限速 |
| 幂等 | 重试需先查重 |
| 失败隔离 | 单 worker 崩溃不影响其他 |
| 进度记录 | 每批完成写进度到 Redis |
| 断点续传 | 崩溃后从进度点继续 |
| 监控 | 成功率、耗时、配额用量告警 |

### 3.8 生产级 Python：流内 batch + partial_failure 循环

完整生产模式：

```python
"""
生产级 Streaming Mutate 完整模式

特性:
- 流内分批
- partial_failure 解析
- 失败分类重试
- 令牌桶限速
- 进度记录
"""
import time
from collections import Counter

from google.ads.googleads.client import GoogleAdsClient
from google.ads.googleads.errors import GoogleAdsException

client = GoogleAdsClient.load_from_storage("google-ads.yaml")
service = client.get_service("AdGroupCriterionService")

CUSTOMER_ID = "1234567890"
BATCH = 500
MAX_RETRIES = 3


class StreamingMutateRunner:
    def __init__(self, service, customer_id, batch_size=BATCH):
        self.service = service
        self.customer_id = customer_id
        self.batch_size = batch_size
        self.stats = Counter()

    def run(self, operations, retryable=True):
        """执行流式批量写入，返回 (成功数, 失败明细)"""
        success = 0
        failures = []
        for i in range(0, len(operations), self.batch_size):
            batch = operations[i : i + self.batch_size]
            s, f = self._stream_batch(batch, retryable)
            success += s
            failures.extend(f)
        return success, failures

    def _stream_batch(self, batch, retryable):
        for attempt in range(MAX_RETRIES):
            try:
                return self._send_batch(batch)
            except GoogleAdsException as e:
                if not retryable or not self._is_retryable(e):
                    self.stats["unretryable"] += 1
                    return 0, [str(e)]
                wait = min(30, 1 * 2 ** attempt) + (time.time() % 1)
                print(f"整批重试 {attempt+1},等待 {wait:.1f}s")
                time.sleep(wait)
        return 0, [f"重试耗尽: {len(batch)} 个操作"]

    def _send_batch(self, batch):
        ok = 0
        fails = []
        with self.service.stream_mutate_ad_group_criteria(
            customer_id=self.customer_id,
            operations=batch,
            enable_partial_failure=True,
        ) as responses:
            for response in responses:
                ok += len(response.results)
                if response.partial_failure_error:
                    for detail in (
                        response.partial_failure_error.details
                    ):
                        for e in detail.errors:
                            fails.append(
                                {
                                    "code": self._code_name(
                                        e.error_code),
                                    "message": e.message,
                                    "trigger": e.trigger,
                                }
                            )
                            self.stats[
                                self._code_name(e.error_code)
                            ] += 1
        return ok, fails

    def _code_name(self, code):
        """把 error_code 转成可读字符串"""
        for field in (
            "quota_error", "ad_group_criterion_error",
            "campaign_error", "request_error",
        ):
            v = getattr(code, field, None)
            if v:
                return f"{field}:{v}"
        return "unknown"

    def _is_retryable(self, exc):
        for err in exc.failure.errors:
            c = err.error_code
            if c.quota_error == c.QuotaErrorEnum.RESOURCE_EXHAUSTED:
                return True
            if c.internal_error == c.InternalErrorEnum.INTERNAL_ERROR:
                return True
        return False


def main():
    ops = []
    for i in range(3000):
        op = client.get_type("AdGroupCriterionOperation")
        criterion = op.create
        criterion.ad_group = (
            f"customers/{CUSTOMER_ID}/adGroups/300001"
        )
        criterion.keyword.text = f"prod-keyword-{i}"
        criterion.keyword.match_type = (
            client.enums.KeywordMatchTypeEnum.PHRASE
        )
        ops.append(op)

    runner = StreamingMutateRunner(service, CUSTOMER_ID)
    ok, fails = runner.run(ops)
    print(f"成功: {ok}, 失败: {len(fails)}")
    print("错误分布:", dict(runner.stats))


if __name__ == "__main__":
    main()
```

### 3.9 最佳实践清单

#### 3.9.1 写前

1. 用 search 查重，减少无效 create。
2. 设计好批大小与并发流数量。
3. 准备令牌桶限速器。
4. 确保 OAuth2 token 有效且 developer-token 正确。

#### 3.9.2 写中

1. 始终开启 partial_failure。
2. 每批处理后立即解析结果。
3. 记录每批的成功/失败计数。
4. 发现 429 立即降速。

#### 3.9.3 写后

1. 用 GAQL 抽查写入结果。
2. 对账：成功 + 失败 = 总数。
3. 失败数据落库，供重试。
4. 生成报告（耗时、成功率、错误分布）。

#### 3.9.4 常见陷阱

| 陷阱 | 后果 | 对策 |
|------|------|------|
| 忘记 update_mask | 字段不生效 | 显式声明 |
| create 盲目重试 | 重复资源 | 先查重 |
| 批过大 | 超时/限流 | 500~1000 |
| 忽略 partial_failure | 数据静默丢失 | 必开必解析 |
| 并发流过多 | 配额打爆 | 2~8 条流 |
| 长流不关闭 | 连接泄漏 | with/finally |

## 四、常见问题与排查

### Q1: Streaming Mutate 和普通 Mutate 选哪个？

A:

以操作量和工作模式为准。

| 条件 | 选择 |
|------|------|
| 操作量 < 1000，单次 | 普通 Mutate |
| 操作量 1000~5 万 | 普通 Mutate 分批 |
| 操作量 > 5 万 | Streaming Mutate |
| 需要实时逐条结果 | Streaming Mutate |
| 需要精细失败重试 | Streaming Mutate |
| 简单脚本 | 普通 Mutate |

普通 Mutate 实现简单。

Streaming Mutate 需要管理流生命周期。

不建议无脑用流式。

### Q2: partial_failure 为什么没有生效？

A:

常见原因：

1. 请求里没设置 `enable_partial_failure=True`。
2. 整批操作都成功，没有失败，自然没有错误。
3. 错误发生在流级别而非操作级别。

排查：

```python
print("partial_failure_error:", response.partial_failure_error)
```

如果为 None：

1. 确认开启了 partial_failure。
2. 确认确有操作失败（构造一个必然失败的操作验证）。

注意：流级错误（配额、认证）不会进入 partial_failure。

### Q3: 如何把失败操作和原始操作对应起来？

A:

利用 `location.field_path_elements` 的 index。

或者按顺序对齐：

```python
def map_errors_to_ops(ops, response):
    failed_indices = set()
    for detail in response.partial_failure_error.details:
        for e in detail.errors:
            for element in e.location.field_path_elements:
                if element.index is not None:
                    failed_indices.add(element.index)
    return [ops[i] for i in failed_indices if i < len(ops)]
```

注意：

索引是相对批内操作的位置。

不是全局索引。

### Q4: 出现 RESOURCE_EXHAUSTED 怎么办？

A:

RESOURCE_EXHAUSTED 表示配额耗尽。

处理步骤：

1. 停止新请求。
2. 指数退避等待（初始 1s，加倍）。
3. 降低请求频率。
4. 检查配额监控面板。

```python
def handle_quota(e, attempt):
    wait = min(60, 2 ** attempt) + random.uniform(0, 1)
    print(f"配额耗尽，等待 {wait}s")
    time.sleep(wait)
```

长期方案：

1. 令牌桶限速。
2. 合并请求减少请求次数。
3. 错峰执行（避开整点）。
4. 联系 Google 申请配额提升。

### Q5: 为什么批量创建出现大量重复？

A:

原因通常是：

1. 网络超时后盲目重发 create。
2. 同一数据被多个任务重复消费。

对策：

1. create 前先 search 查重。
2. 用幂等键（业务 ID）判重。
3. update 优于 create。

```python
def dedupe_existing(client, customer_id, keywords):
    """查询已存在关键词，跳过重复"""
    existing = set()
    for i in range(0, len(keywords), 5000):
        batch = keywords[i : i + 5000]
        texts = "', '".join(k["text"] for k in batch)
        query = f"""
            SELECT ad_group_criterion.keyword.text
            FROM ad_group_criterion
            WHERE ad_group_criterion.type = 'KEYWORD'
              AND ad_group_criterion.keyword.text IN ('{texts}')
              AND ad_group_criterion.status != 'REMOVED'
        """
        rows = client.google_ads_service.search(
            customer_id=customer_id, query=query
        )
        existing.update(
            r.ad_group_criterion.keyword.text for r in rows
        )
    return [k for k in keywords if k["text"] not in existing]
```

### Q6: 流在中间断开怎么办？

A:

流断开后：

1. 已收到响应的操作：确认成功。
2. 已发送未收到响应的操作：状态未知。
3. 未发送的操作：可重发。

处理：

```python
def robust_stream(ops, on_result, on_error):
    """带断流恢复的流式写入"""
    sent = 0
    while sent < len(ops):
        try:
            with service.stream_mutate_ad_group_criteria(
                customer_id=CUSTOMER_ID,
                operations=ops[sent:],
                enable_partial_failure=True,
            ) as responses:
                for response in responses:
                    for r in response.results:
                        on_result(r)
                    if response.partial_failure_error:
                        on_error(response.partial_failure_error)
            break  # 正常结束
        except (GoogleAdsException, Exception):
            # 断流：重连，从未确认处继续
            print("流中断，重连...")
            time.sleep(2)
            # 注意: create 类操作需查重后再重发
```

对于 create 类操作，重连后建议先查重。

### Q7: 认证错误 INVALID_TOKEN 怎么排查？

A:

INVALID_TOKEN 表示 access token 无效。

排查步骤：

1. 检查 token 是否过期。
2. 检查刷新逻辑。
3. 检查 developer-token 是否正确。

```python
def refresh_if_needed(credentials):
    """自动刷新 access token"""
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request

    creds = Credentials(
        token=credentials["access_token"],
        refresh_token=credentials["refresh_token"],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=credentials["client_id"],
        client_secret=credentials["client_secret"],
    )
    if creds.expired:
        creds.refresh(Request())
        credentials["access_token"] = creds.token
    return credentials
```

### Q8: developer-token 与 login-customer-id 的区别？

A:

| 头 | 用途 | 示例 |
|----|------|------|
| developer-token | 开发者身份，API 接入方令牌 | 需申请 |
| login-customer-id | 登录账户（通常是 MCC） | 1234567890 |
| Authorization | OAuth2 用户授权 | Bearer xxx |
| customer_id | 实际操作的目标账户 | 在请求体里 |

login-customer-id 是请求头。

customer_id 是请求体字段。

两者不同。

### Q9: 批量操作超时怎么办？

A:

超时原因与对策：

| 原因 | 对策 |
|------|------|
| 单批操作过多 | 减小批大小 |
| 单操作体过大（大文本/图片） | 压缩或拆分 |
| 网络差 | 增加超时时间 |
| 服务器繁忙 | 退避重试 |
| 流空闲太久 | 保持流活跃 |

```python
# 增大超时
service.mutate_ad_group_criteria(
    customer_id=customer_id,
    operations=batch,
    timeout=120,  # 秒
)
```

### Q10: 如何监控配额使用？

A:

1. 用 API 响应头看配额信息。
2. 用 Google Cloud 配额面板。
3. 客户端统计请求频率。

```python
def check_quota_headers(response):
    """读取响应头中的配额元数据"""
    for key, value in response.raw.headers.items():
        if "quota" in key.lower():
            print(f"{key}: {value}")
```

出现 429 时的通用处理：

1. 记录时间戳。
2. 指数退避。
3. 触发告警。

### Q11: 不同服务之间的 Streaming Mutate 有区别吗？

A:

语义一致，只是资源不同。

| Service | 流式方法 | 操作对象 |
|---------|---------|---------|
| CampaignService | StreamMutateCampaigns | 广告系列 |
| AdGroupService | StreamMutateAdGroups | 广告组 |
| AdGroupCriterionService | StreamMutateAdGroupCriteria | 关键词 |
| AdService | StreamMutateAds | 广告 |
| AssetService | StreamMutateAssets | 资产 |
| CampaignAssetService | StreamMutateCampaignAssets | 系列-资产关联 |

错误码枚举不同。

例如关键词错误走 AdGroupCriterionError。

### Q12: 一个账户同时开多个流可以吗？

A:

可以，但要注意：

1. 所有流共享账户配额。
2. 并发流会加速配额消耗。
3. 可能触发限流。

建议：

1. 控制并发流数量（如 2~8）。
2. 每流配令牌桶限速。
3. 监控整体配额消耗。

### Q13: 如何提高批量写入吞吐？

A:

提升手段：

1. 增大批大小（但别超限）。
2. 增加并发流。
3. 减少无关字段。
4. 复用连接。
5. 与配额峰值匹配。

```text
吞吐 = 批大小 × 每秒批次
     = 批大小 × (并发流 × 每流速率)

瓶颈通常在:
- 配额（最硬约束）
- 单批处理时间
- 网络带宽
```

### Q14: 出现 INTERNAL_ERROR 怎么处理？

A:

INTERNAL_ERROR 是服务端内部错误。

处理策略：

1. 退避重试（通常 2~3 次）。
2. 若持续，检查是否请求体过大。
3. 联系 Google Ads API 支持。

### Q15: 如何避免重复创建广告组？

A:

建组前查询同名下是否已有。

```python
def ad_group_exists(client, customer_id, campaign_id, name):
    query = f"""
        SELECT ad_group.id, ad_group.name
        FROM ad_group
        WHERE ad_group.campaign = 'customers/{customer_id}/campaigns/{campaign_id}'
          AND ad_group.name = '{name}'
          AND ad_group.status != 'REMOVED'
    """
    rows = client.google_ads_service.search(
        customer_id=customer_id, query=query
    )
    return any(list(rows))
```

建组时用唯一命名（如带时间戳或业务 ID）。

### Q16: 数据量大时内存怎么控制？

A:

1. 分批构造操作，别一次性全放内存。
2. 用生成器惰性生成操作。
3. 处理完一批即释放。

```python
def generate_operations():
    """惰性生成操作，节省内存"""
    for row in read_keywords_from_db():  # 数据库游标
        op = client.get_type("AdGroupCriterionOperation")
        criterion = op.create
        criterion.ad_group = (
            f"customers/{CUSTOMER_ID}/adGroups/{row['ad_group_id']}"
        )
        criterion.keyword.text = row["text"]
        yield op


def stream_lazy(gen, batch_size=500):
    """从生成器分批取操作"""
    batch = []
    for op in gen:
        batch.append(op)
        if len(batch) >= batch_size:
            yield batch
            batch = []
    if batch:
        yield batch
```

### Q17: 如何处理 update_mask？

A:

update 操作必须声明更新哪些字段。

漏掉 update_mask 会导致字段不生效。

```python
op = client.get_type("AdGroupOperation")
ag = op.update
ag.resource_name = f"customers/{CUSTOMER_ID}/adGroups/{ag_id}"
ag.status = client.enums.AdGroupStatusEnum.PAUSED
# 必须声明
op.update_mask.append("status")
```

多个字段：

```python
op.update_mask.append("status")
op.update_mask.append("name")
```

### Q18: 响应结果顺序和请求顺序一致吗？

A:

一致。

批内结果按请求操作顺序返回。

但 partial_failure 时，results 只含成功操作。

失败操作要用错误索引对齐。

```python
# 请求: [opA, opB, opC, opD]
# 若 opB、opD 失败
# results = [A的result, C的result]
# errors 索引: 1, 3
```

### Q19: 批大小到底选多少？

A:

经验值：

| 场景 | 批大小 |
|------|--------|
| 创建关键词 | 500~1000 |
| 更新出价 | 1000~2000 |
| 创建广告 | 100~500 |
| 创建广告系列 | 50~100 |
| 删除操作 | 1000~5000 |

原则：

1. 创建类批小（失败回滚成本高）。
2. 更新类批大（幂等，安全）。
3. 以单批处理时间 < 数秒为目标。

### Q20: 如何验证批量写入成功？

A:

写入后用 GAQL 抽查。

```python
def verify_count(client, customer_id, ad_group_id):
    """统计某广告组关键词数，用于对账"""
    query = f"""
        SELECT COUNT(ad_group_criterion.resource_name)
        FROM ad_group_criterion
        WHERE ad_group_criterion.ad_group =
              'customers/{customer_id}/adGroups/{ad_group_id}'
          AND ad_group_criterion.type = 'KEYWORD'
          AND ad_group_criterion.status != 'REMOVED'
    """
    rows = client.google_ads_service.search(
        customer_id=customer_id, query=query
    )
    for row in rows:
        return getattr(
            row.ad_group_criterion, "resource_name", None
        )
    return 0
```

对账：写入成功数 + 失败数 = 操作总数。

### Q21: 报表如何与写入做闭环验证？

A:

用 generate_report 拉取 metrics 做验证。

```python
def report_after_write(client, customer_id, dates):
    """写入后拉取报表核对"""
    report = client.generate_report(
        customer_id=customer_id,
        date_range=dates,
    )
    for row in report.data:
        print(
            f"campaign={row.get('campaign.name')} "
            f"impressions={row.get('metrics.impressions')} "
            f"clicks={row.get('metrics.clicks')} "
            f"cost={row.get('metrics.cost_micros')} "
            f"cvr={row.get('metrics.conversions')}"
        )
```

注意报表数据有延迟。

写入后立即查可能查不到。

一般在 T+1 后核对。


## 五、自测题

### 题目 1：概念题

Streaming Mutate 与普通 Mutate 相比，在通信模型、适用场景、错误处理三方面各有什么核心差异？

分别在什么量级下选择哪种方案？

### 题目 2：代码题

请写出使用 Python google-ads 库对 10000 个关键词进行流式批量创建的核心代码片段。

要求：

1. 分批写入（每批 500）。
2. 开启 partial_failure。
3. 解析失败错误。
4. 统计成功/失败数量。

### 题目 3：场景设计题

某代理商要在 2 小时内为 100 个广告组各新增 1000 个关键词。

请设计架构（含并发、批大小、限速、失败重试）。

并说明如何保证不触发配额限流。

### 题目 4：排错题

批量创建关键词时出现大量重复关键词。

可能的原因有哪些？

如何从代码层面避免？

### 题目 5：原理题

partial_failure_error 的数据结构是什么？

如何将失败错误与批内原始操作对应起来？

哪些错误不会出现在 partial_failure_error 中？

### 题目 6：计算题

已知令牌桶速率为 20 请求/秒，桶容量 20。

广告组每批 500 个操作。

一个广告组 1000 个关键词需要 2 批。

100 个广告组共需要多少个请求？

在不考虑其他开销的情况下，理论上需要多久才能发完？

<details>
<summary>答案</summary>

### 答案 1

通信模型：

普通 Mutate 是 Unary RPC，一次请求一次响应，结果整体返回。

Streaming Mutate 是双向流 RPC，客户端分批写入操作，服务器边处理边返回结果。

适用场景：

- 操作量 < 1000：用普通 Mutate。
- 1000~5 万：普通 Mutate 分批。
- > 5 万或需要实时逐条结果：Streaming Mutate。
- 百万级：Streaming Mutate + 分布式 worker。

错误处理：

普通 Mutate 也支持 partial_failure，但整体响应、失败定位复杂。

Streaming Mutate 天然适合 partial_failure，可实时获取每个批次的成功/失败明细，便于精细重试。

核心选择依据是操作量级、实时性需求和失败处理粒度。

### 答案 2

```python
from google.ads.googleads.client import GoogleAdsClient

client = GoogleAdsClient.load_from_storage("google-ads.yaml")
service = client.get_service("AdGroupCriterionService")

CUSTOMER_ID = "1234567890"
AD_GROUP_ID = 300001
BATCH_SIZE = 500


def create_keywords_stream(keyword_texts):
    success = 0
    failures = []
    for i in range(0, len(keyword_texts), BATCH_SIZE):
        batch_texts = keyword_texts[i : i + BATCH_SIZE]
        ops = []
        for text in batch_texts:
            op = client.get_type("AdGroupCriterionOperation")
            criterion = op.create
            criterion.ad_group = (
                f"customers/{CUSTOMER_ID}/adGroups/{AD_GROUP_ID}"
            )
            criterion.keyword.text = text
            criterion.keyword.match_type = (
                client.enums.KeywordMatchTypeEnum.PHRASE
            )
            ops.append(op)

        with service.stream_mutate_ad_group_criteria(
            customer_id=CUSTOMER_ID,
            operations=ops,
            enable_partial_failure=True,
        ) as responses:
            for response in responses:
                success += len(response.results)
                if response.partial_failure_error:
                    for detail in (
                        response.partial_failure_error.details
                    ):
                        for e in detail.errors:
                            failures.append(
                                {
                                    "code": e.error_code,
                                    "message": e.message,
                                    "trigger": e.trigger,
                                }
                            )
    return success, failures


success, failures = create_keywords_stream(
    [f"keyword-{i}" for i in range(10000)]
)
print(f"成功: {success}, 失败: {len(failures)}")
```

要点：

1. 每批 500 个操作，共 20 批。
2. 开启 enable_partial_failure。
3. 用 stream_mutate_ad_group_criteria 的 with 上下文管理流。
4. 遍历 responses，统计 results 与 partial_failure_error。

### 答案 3

架构设计：

1. 任务切分：100 个广告组 = 100 个任务，每个任务 1000 个关键词。
2. 并发：ThreadPoolExecutor 8 个 worker，每 worker 处理一个广告组。
3. 每 worker 开一条流，批大小 500，每广告组 2 批。
4. 限速：全局令牌桶，速率按配额估算（例如 20 req/s）。
5. 失败重试：partial_failure 内的失败分类，可重试错误指数退避 3 次。

防限流策略：

1. 令牌桶平滑速率，避免瞬时打爆配额桶。
2. 控制并发流数量 ≤ 8。
3. 监控 429 响应，动态降低速率。
4. 错峰：避开整点批量任务高峰期。

耗时估算：

100 广告组 × 2 批 = 200 个请求。

按 20 req/s 需要 10 秒。

加上重试与解析，远小于 2 小时目标。

瓶颈在配额而非计算。

### 答案 4

可能原因：

1. 网络超时后盲目重发 create 操作。
2. 同一关键词被多个 worker/任务重复消费。
3. 上游数据源本身有重复。
4. 重试逻辑不幂等。

代码层面避免：

1. create 前先 search 查重，跳过已存在关键词。
2. 用业务唯一键（广告组 + 文本 + 匹配类型）做去重集合。
3. 优先用 update 而非 create。
4. 任务消费时记录已处理键（Redis set），防止重复消费。

```python
existing = set()  # 已存在业务键
seen = set()      # 本批去重
for kw in keyword_list:
    key = (ad_group_id, kw["text"], kw["match_type"])
    if key in seen or key in existing:
        continue
    seen.add(key)
    ops.append(build_op(kw))
```

### 答案 5

数据结构：

partial_failure_error 是 google.rpc.Status。

details 数组里是 Any 包装的 GoogleAdsFailure。

GoogleAdsFailure.errors 是 ErrorDetails 列表。

每个 ErrorDetails 含：

1. error_code（领域枚举，如 AdGroupCriterionError.DUPLICATE_KEYWORD）。
2. message（可读消息）。
3. trigger（触发值）。
4. location（field_path_elements，含字段名与 index）。

对应方法：

遍历 errors，读取 location.field_path_elements 中的 index。

index 是批内操作的索引。

用该索引映射回原始操作列表。

不会出现在 partial_failure_error 的错误：

1. 流级错误：配额耗尽（RESOURCE_EXHAUSTED）、认证失败。
2. 整批校验失败：请求格式错误。
3. 网络层错误：超时、断流。

这些以异常或流错误形式抛出。

### 答案 6

计算过程：

1. 请求总数：100 广告组，每个广告组 1000 关键词。
2. 批大小 500，每个广告组需 2 批。
3. 100 × 2 = 200 个请求。

4. 令牌桶速率 20 req/s，桶容量 20。

前 20 个请求可立即发出（桶满）。

剩余 180 个请求按每 1/20 秒一个的速率发出。

总时长 = 20 × 0 + 180 / 20 = 9 秒。

考虑桶容量平滑，理论约 9~10 秒。

若不限速，200 个请求可在极短时间发出。

但会被配额桶拒绝，触发 RESOURCE_EXHAUSTED。

这正说明令牌桶的必要性。

</details>

---

## 参考与延伸阅读

| 主题 | 说明 |
|------|------|
| Google Ads API 官方文档 | developers.google.com/google-ads/api |
| Python 客户端库 | github.com/googleapis/google-ads-python |
| GAQL 参考 | developers.google.com/google-ads/api/docs/query/overview |
| 配额与限制 | developers.google.com/google-ads/api/docs/best-practices/quotas |
| partial_failure 指南 | developers.google.com/google-ads/api/docs/best-practices/partial-failures |
| 错误码参考 | developers.google.com/google-ads/api/docs/reference/errors |
| 本库基础指南 | google-ads-api-production-guide.md（基础用法） |

## 差异化说明

本文件为专属 Streaming Mutate 深度指南。

聚焦以下领域：

1. 双向流语义（BiDi stream / HTTP/2）。
2. partial_failure 逐操作错误处理。
3. 批量限制与分批策略。
4. 速率配额与削峰限速。
5. 分布式百万级写入架构。

基础 API 认证与入门用法参见同目录基础文档。

不做重复。

本文件的定位：

从"能调 API"升级到"能安全高效地写百万级数据"。

是生产级批量写入的工程参考手册。

---

> **END OF DOCUMENT**
> 撰写完成，总行数 2884。
> 覆盖五大部分与 21 个 Q&A、6 道自测题。
> API 端点为 https://googleads.googleapis.com/v24。
