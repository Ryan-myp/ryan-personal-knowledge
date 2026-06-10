# Google Ads API — 高级功能深度指南

> 创建日期: 2026-06-09
> 作者: Ryan
> 定位: 资深专家级 — API 高级用法

---

## 第一部分: 认证体系

### 1.1 OAuth2 认证流程

```
Google Ads API 认证采用 OAuth2 + Developer Token 双认证:

┌──────────────────────────────────────────────────────────────┐
│              Google Ads API 认证流程                          │
│                                                              │
│  Step 1: 获取 Developer Token                                  │
│  ────────────────────────────────────────────────────────────  │
│  ├── 通过 Google Ads 账户申请                                   │
│  ├── 需要广告账户有管理权限                                     │
│  ├── 审核周期: 3-5 工作日                                     │
│  └─ 获得 Developer Token                                     │
│                                                              │
│  Step 2: 创建 OAuth2 凭据                                     │
│  ────────────────────────────────────────────────────────────  │
│  ├── Google Cloud Console → Credentials                      │
│  ├── OAuth Consent Screen                                    │
│  └─ 创建 OAuth Client ID (Web Application)                   │
│                                                              │
│  Step 3: 获取 Refresh Token                                    │
│  ────────────────────────────────────────────────────────────  │
│  ├── 用户授权 (consent)                                       │
│  ├── 获取 authorization_code                                  │
│  ├── 用 code 换取 access_token + refresh_token                │
│  └─ refresh_token 长期有效 (需用户重新授权时刷新)               │
│                                                              │
│  Step 4: 使用 Refresh Token 获取 Access Token                  │
│  ────────────────────────────────────────────────────────────  │
│  ├── access_token: 短期有效 (1 小时)                          │
│  ├── refresh_token: 长期有效 (30-60 天, 需刷新)                │
│  └─ 自动刷新: refresh() 方法自动处理                          │
└──────────────────────────────────────────────────────────────┘
```

### 1.2 认证代码实现

```python
from google.ads.googleads.client import GoogleAdsClient
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
import os

# 配置认证
client = GoogleAdsClient.load_from_storage(
    oauth2_client_id=os.environ['GOOGLE_OAUTH2_CLIENT_ID'],
    oauth2_client_secret=os.environ['GOOGLE_OAUTH2_CLIENT_SECRET'],
    developer_token=os.environ['GOOGLE_DEVELOPER_TOKEN'],
    refresh_token=os.environ['GOOGLE_REFRESH_TOKEN'],
    login_customer_id='YOUR_CUSTOMER_ID',  # 可选, MCC 模式
)

# 获取服务
google_ads_service = client.get_service('GoogleAdsService')

# 自动刷新 token
creds = Credentials(
    token='access_token',
    refresh_token='refresh_token',
    token_uri='https://oauth2.googleapis.com/token',
    client_id='client_id',
    client_secret='client_secret',
)
creds.refresh(Request())
```

---

## 第二部分: 查询与数据获取

### 2.1 GoogleAdsService 高级用法

```
GoogleAdsService 支持两种查询方式:

1. search (标准查询):
   ├── 每次最多返回 10,000 条记录
   ├── 适合中小数据集
   └─ 使用 page_token 分页

2. search_stream (流式查询):
   ├── 适合大数据集
   ├── 流式返回, 内存友好
   ├── 自动处理分页
   └─ 推荐: 99% 场景使用

示例:
```python
from google.ads.googleads.client import GoogleAdsClient

client = GoogleAdsClient.load_from_storage()
ga_service = client.get_service("GoogleAdsService")

# 标准查询 (中小数据)
query = """
    SELECT campaign.id, campaign.name,
           metrics.impressions, metrics.clicks,
           metrics.cost_micros, metrics.conversions
    FROM campaign
    WHERE segments.date BETWEEN 2026-01-01 AND 2026-01-31
"""

response = ga_service.search(
    customer_id='YOUR_CUSTOMER_ID',
    query=query,
    page_size=10000,
)

for row in response:
    campaign = row.campaign
    metrics = row.metrics
    print(f"{campaign.name}: {metrics.impressions} impressions")

# 流式查询 (大数据)
response_iterator = ga_service.search_stream(
    customer_id='YOUR_CUSTOMER_ID',
    query=query,
)

for batch in response_iterator:
    for row in batch.results:
        campaign = row.campaign
        metrics = row.metrics
        print(f"{campaign.name}: {metrics.impressions} impressions")
```

### 2.2 查询优化最佳实践

```
查询优化策略:

1. 只 SELECT 需要的字段:
   ├── 减少数据传输量
   ├── 提高查询速度
   └─ 避免 SELECT *

2. 使用合适的过滤条件:
   ├── WHERE 限制返回范围
   ├── 避免返回不必要的数据
   └─ 使用 date_range 限制日期

3. 分页处理:
   ├── 每页 10,000 条
   ├── 使用 page_token 继续查询
   └─ 大数据集使用 search_stream

4. 缓存策略:
   ├── 高频数据缓存 (分钟级)
   ├── 低频数据缓存 (小时/天级)
   └─ 变更检测 (ETag/Last-Modified)

5. 并行查询:
   ├── 同时查询多个广告系列
   ├── 不同维度的数据
   └─ 但注意速率限制
```

---

## 第三部分: 批量操作

### 3.1 Mutate 批量操作

```
Google Ads API 支持批量修改操作:

┌──────────────────────────────────────────────────────────────┐
│              Mutate 操作类型                                   │
│                                                              │
│  资源操作:                                                   │
│  ├── CREATE — 创建新资源                                     │
│  ├── REMOVE — 删除资源                                       │
│  └─ SET — 更新资源                                            │
│                                                              │
│  批量限制:                                                   │
│  ├── 每次操作最多 10,000 个操作                               │
│  ├── 所有操作原子性 (全部成功或全部失败)                       │
│  └─ 每个广告系列每 100 秒最多 50 次 mutate 调用               │
└──────────────────────────────────────────────────────────────┘

批量操作示例:
```python
from google.ads.googleads.enums import OperationTypeEnum

operations = []

# 批量创建广告组
for ad_group_name in ['AG_1', 'AG_2', 'AG_3']:
    operation = client.get_type("AdGroupOperation")
    operation.create.name = ad_group_name
    operation.create.campaign = f"customers/{customer_id}/campaigns/{campaign_id}"
    operation.create.status = client.enums.AdGroupStatusEnum.ENABLED
    operations.append(operation)

# 批量执行
response = ga_service.mutate_ad_groups(
    customer_id=customer_id,
    operations=operations,
)

for result in response.results:
    print(f"Created ad group: {result.resource_name}")
```

### 3.2 异步操作 (Async Mutate)

```
对于大量操作 (超过 10,000):

1. 分批次:
   ├── 每批最多 10,000
   ├── 串行执行
   └─ 监控成功率

2. 异步提交 (Beta):
   ├── 提交异步操作请求
   ├── 轮询状态
   └─ 适合超大数据量
```

---

## 第四部分: 错误处理

### 4.1 错误类型

```
Google Ads API 错误类型:

┌──────────────────────────────────────────────────────────────┐
│              错误分类                                         │
│                                                              │
│  请求错误 (Request Errors):                                   │
│  ├── VALIDATION_ERROR — 字段验证失败                          │
│  ├── AUTHENTICATION_ERROR — 认证失败                          │
│  ├── PERMISSION_DENIED — 权限不足                             │
│  └─ RESOURCE_EXHAUSTED — 速率限制                            │
│                                                              │
│  操作错误 (Operation Errors):                                 │
│  ├── DURING_OPERATIONS_ERROR — 操作期间错误                   │
│  ├── MUTATE_ERROR — 单个操作失败                              │
│  └─ MUTATE_LIMIT_EXCEEDED — 单个操作过多                     │
│                                                              │
│  资源错误 (Resource Errors):                                 │
│  ├── DUPLICATE_ENTRY — 重复创建                               │
│  ├── RESOURCE_NOT_FOUND — 资源不存在                          │
│  └─ RESOURCE_REACHABILITY_ERROR — 资源不可达                  │
└──────────────────────────────────────────────────────────────┘
```

### 4.2 错误处理策略

```python
from google.ads.googleads.errors import GoogleAdsException

def safe_execute(func, max_retries=3, backoff=2):
    """
    带重试机制的安全执行
    """
    import time
    
    for attempt in range(max_retries):
        try:
            return func()
        except GoogleAdsException as e:
            if e.code == GoogleAdsExceptionCode.RESOURCE_EXHAUSTED:
                # 速率限制, 等待后重试
                wait_time = backoff ** attempt
                print(f"Rate limited. Waiting {wait_time}s...")
                time.sleep(wait_time)
            elif e.code == GoogleAdsExceptionCode.VALIDATION_ERROR:
                # 验证错误, 不重试
                print(f"Validation error: {e}")
                raise
            elif e.code == GoogleAdsExceptionCode.PERMISSION_DENIED:
                # 权限错误, 不重试
                print(f"Permission denied: {e}")
                raise
            else:
                # 其他错误, 重试
                if attempt < max_retries - 1:
                    time.sleep(backoff ** attempt)
                else:
                    raise

# 使用
safe_execute(lambda: ga_service.search(...))
```

---

## 第五部分: 速率限制

### 5.1 速率限制规则

```
Google Ads API 速率限制:

┌──────────────────────────────────────────────────────────────┐
│              速率限制规则                                       │
│                                                              │
│  限制类型:                                                   │
│  ├── Requests per day: 每天 50,000 次 (客户级别)              │
│  ├── Requests per 100 seconds: 100 秒内 50 次                 │
│  ├── Mutates per 100 seconds: 100 秒内 50 次                 │
│  ├── Mutate requests per 100 seconds: 100 秒内 50 次         │
│  └─ Mutates per customer per 100 seconds: 100 秒内 50 次      │
│                                                              │
│  响应头 (Rate Limit Headers):                                │
│  ├── x-google-quota-remaining: 剩余配额                        │
│  ├── x-google-quota-limit: 总配额                             │
│  └─ x-google-quota-reset: 重置时间 (秒)                       │
│                                                              │
│  处理速率限制:                                               │
│  ├── 监控响应头                                             │
│  ├── 指数退避 (Exponential Backoff)                          │
│  └─ 批量操作减少请求次数                                       │
└──────────────────────────────────────────────────────────────┘
```

### 5.2 指数退避

```python
import time
import random

def exponential_backoff(func, max_retries=5, base_delay=1, max_delay=60):
    """指数退避重试"""
    for attempt in range(max_retries):
        try:
            return func()
        except GoogleAdsException as e:
            if e.code == GoogleAdsExceptionCode.RESOURCE_EXHAUSTED:
                delay = min(base_delay * (2 ** attempt), max_delay)
                jitter = delay * random.uniform(0.5, 1.5)  # 随机抖动
                print(f"Rate limited. Retry in {jitter:.1f}s...")
                time.sleep(jitter)
            else:
                raise
```

---

## 第六部分: 报告 API

### 6.1 ReportService

```
ReportService 用于生成和下载报告:

1. 生成报告:
   ├── 使用预定义报告模板
   ├── 自定义报告 (指定字段和维度)
   └─ 异步生成 (大数据量)

2. 下载报告:
   ├── 同步下载 (小报告)
   ├── 异步下载 (大报告)
   └─ 支持 CSV/TSV/JSON/Protobuf

3. 预定义报告:
   ├── Campaign performance
   ├── Ad group performance
   ├── Ad performance
   ├── Keyword performance
   ├── Search term report
   └─ Audience performance

示例:
```python
from google.ads.googleads.services import ReportServiceClient

report_service = client.get_service("ReportService")

# 生成报告
response = report_service.generate_report(
    customer_id=customer_id,
    query="""
        SELECT campaign.id, campaign.name,
               metrics.impressions, metrics.clicks
        FROM campaign
        WHERE segments.date BETWEEN 2026-01-01 AND 2026-01-31
    """,
    return_total_results_count=True,
    request_output_format="CSV",
)

# 下载报告
report = report_service.download_report(
    customer_id=customer_id,
    report_download_path=response.report_download_path,
    return_total_results_count=True,
)

print(report.text)
```

---

## 第七部分: 转化回传 API

### 7.1 ConversionUploadService

```
通过 API 回传转化数据:

1. upload_click_conversions:
   ├── 基于 gclid 上传
   ├── 适合: 网页转化
   └─ 参数: gclid/conversion_action/conversion_date/value

2. upload_conversions:
   ├── 基于 email/电话等 (Enhanced Conversions)
   ├── 适合: 增强转化追踪
   └─ 参数: user_data/conversion_action/conversion_date/value

3. upload_enhanced_conversions:
   ├── 上传 enhanced conversion 数据
   ├── 需要用户同意 (GDPR/CCPA)
   └─ 自动哈希 PII 数据

示例:
```python
from google.ads.googleads.services import ConversionUploadService

upload_service = client.get_service("ConversionUploadService")

response = upload_service.upload_click_conversions(
    customer_id=customer_id,
    conversions=[
        {
            "gclid": "gclid_123",
            "conversion_action": f"customers/{customer_id}/conversionActions/{action_id}",
            "conversion_date_time": "2026-06-09 15:30:00+00:00",
            "conversion_value": 100.0,
            "currency_code": "USD",
            "match_user_data": False,  # 如果需要 enhanced conversion 设为 True
        }
    ]
)

for conversion in response.conversions:
    print(f"Uploaded: {conversion.resource_name}")
```

---

## 第八部分: BigQuery 集成

### 8.1 BigQuery 导出

```
将 Google Ads 数据导出到 BigQuery:

1. 启用 BigQuery 链接:
   ├── Google Ads 账户 → 链接 → BigQuery
   ├── 免费导出数据
   ├── 数据保留 120 天
   └─ 每日自动更新

2. 查询导出数据:
   ├── 原始数据表: googleads.microsoft.com
   ├── 按日期分区
   ├── 可自定义字段
   └─ 适合: 自定义分析/ML

3. 使用 SQL 分析:
```sql
-- 示例: 每日各广告系列花费
SELECT
  date,
  campaign_name,
  SUM(cost) / 1000000 as cost_usd,
  SUM(impressions) as impressions,
  SUM(clicks) as clicks,
  SUM(conversions) as conversions
FROM `your_project.your_dataset.YourTable`
WHERE date BETWEEN '2026-01-01' AND '2026-01-31'
GROUP BY date, campaign_name
ORDER BY cost_usd DESC;
```
```

---

## 第九部分: 最佳实践清单

```
Google Ads API 最佳实践:

1. 认证管理:
   ├── 安全存储 credentials (环境变量)
   ├── 自动刷新 token
   └─ 定期轮换 refresh token

2. 查询优化:
   ├── 只 SELECT 需要的字段
   ├── 使用 search_stream 处理大数据
   ├── 缓存高频数据
   └─ 使用 date_range 限制范围

3. 错误处理:
   ├── 监控 RESOURCE_EXHAUSTED
   ├── 指数退避
   ├── 重试可重试错误
   └─ 日志记录所有错误

4. 批量操作:
   ├── 批量处理 (最多 10,000)
   ├── 监控操作成功率
   └─ 分批次处理超大操作

5. 监控与告警:
   ├── 监控 API 配额使用
   ├── 监控错误率
   ├── 监控转化率数据
   └─ 设置告警阈值
```

---

*今天花 90 分钟：深入掌握 Google Ads API 高级功能*
*答不出自测题？回去重读对应章节。*

---

## 自测题

### 问题 1
Google Ads API 每次 mutate 操作最多可包含多少个操作？

<details>
<summary>查看答案</summary>

10,000 个操作。超过此数量需要分批次。
</details>

### 问题 2
RESOURCE_EXHAUSTED 错误应该如何处理？

<details>
<summary>查看答案</summary>

- 指数退避 (Exponential Backoff)
- 等待后重试
- 监控响应头 x-google-quota-remaining
</details>

### 问题 3
search 和 search_stream 的区别是什么？

<details>
<summary>查看答案</summary>

- search: 每次最多返回 10,000 条, 适合中小数据集
- search_stream: 流式返回, 内存友好, 适合大数据集
- 推荐: 99% 场景使用 search_stream
</details>

---

*今天花 90 分钟：深入掌握 Google Ads API 高级功能*
*答不出自测题？回去重读对应章节。*
