# Meta Marketing API 高频异常处理完全指南

> **领域**: 广告投放 / Meta Ads API
> **深度**: ⭐⭐⭐⭐⭐ 生产级指南
> **标签**: meta-ads, api-error, exception-handling, graph-api
> **更新时间**: 2026-08-14
> **类型**: production/error-handling

---

## 一、Meta API 错误码速查

### 1.1 核心错误码

```
┌─────────────────────────────────────────────────────────────────────┐
│                   Meta Marketing API 错误码                          │
├────────┬──────────────────┬─────────────────────────────────────────┤
│ Code   │ Error Type       │ 说明                                    │
├────────┼──────────────────┼─────────────────────────────────────────┤
│ 4      │ OAuthException   │ OAuth 认证失败                           │
│ 10     │ Validation Error │ 参数验证失败                             │
│ 17     │ Rate Limit       │ 限流                                     │
│ 613    │ App Limit        │ 应用级别限制                             │
│ 8000   │ Business Limit   │ 商务限制                                 │
│ 200    │ Permissions Error│ 权限不足                                 │
│ 190    │ Token Expired    │ Token 过期                               │
│ 368    │ Duplicate        │ 重复操作                                 │
│ 457    │ Feature Not Enabled│ 功能未启用                            │
│ 458    │ Page Unavailable │ 页面不可用                               │
└────────┴──────────────────┴─────────────────────────────────────────┘
```

### 1.2 错误响应结构

```json
{
  "error": {
    "message": "(#17) Rate limit exceeded",
    "type": "OAuthException",
    "code": 17,
    "error_subcode": 2018003,
    "is_transient": false,
    "error_user_title": "Rate Limit",
    "error_user_msg": "You have hit your rate limit...",
    "fbtrace_id": "Abc123..."
  }
}
```

---

## 二、高频异常及处理

### 2.1 Error Code 17: Rate Limit

```
限流规则：
- Per App: 2000 requests/hour
- Per User: 100 requests/minute
- Per Ad Account: 根据不同操作类型

触发响应：
- HTTP 429
- error.code = 17
- error.error_subcode = 2018003 (Burst) 或 2018004 (Rate limit)

处理策略：
1. 检查 Retry-After 头
2. 指数退避 + 抖动
3. 降低请求速率
4. 错峰执行

```python
import time
import random

class MetaRateLimitHandler:
    def __init__(self, max_retries=5):
        self.max_retries = max_retries

    def handle(self, response, attempt=0):
        if response.status_code != 429:
            return response

        if attempt >= self.max_retries:
            raise RateLimitExceededError(
                f"Rate limited after {self.max_retries} retries"
            )

        # 解析 Retry-After
        retry_after = self._parse_retry_after(response)

        # 添加抖动 (0-30%)
        jitter = retry_after * random.uniform(0, 0.3)
        wait_time = retry_after + jitter

        print(f"Meta rate limited, waiting {wait_time:.1f}s (attempt {attempt+1})")
        time.sleep(wait_time)
        return None  #  caller 负责重试

    def _parse_retry_after(self, response):
        # 优先使用 Retry-After 头
        retry_header = response.headers.get('Retry-After')
        if retry_header:
            return float(retry_header)

        # 从错误消息中解析
        try:
            data = response.json()
            error = data.get('error', {})
            subcode = error.get('error_subcode')

            if subcode == 2018003:  # Burst limit
                return 60.0  # 固定等待 60 秒
            elif subcode == 2018004:  # Rate limit
                return 60.0
        except:
            pass

        return 60.0  # 默认等待 60 秒
```

### 2.2 Error Code 4: OAuthException

```
常见子错误：
- #4_OAuthTokenExpired: Access Token 已过期
- #4_InvalidToken: Token 无效
- #190: Token 权限不足

处理策略：
1. 检测到过期 → 立即刷新 Token
2. 刷新失败 → 引导用户重新授权
3. 权限不足 → 检查 OAuth scopes

```python
def handle_oauth_error(error_code, error_msg):
    if error_code == 190:  # Token expired
        new_token = refresh_access_token()
        if new_token:
            return retry_with_token(new_token)
        else:
            raise AuthenticationError("Token refresh failed")

    elif error_code == 4 and "OAuthTokenExpired" in error_msg:
        # Access Token 过期
        return handle_oauth_error(190, error_msg)

    elif error_code == 4 and "InvalidToken" in error_msg:
        # Token 无效，需要重新授权
        raise ReauthorizationRequiredError(
            "Invalid token, please re-authorize"
        )

    elif error_code == 200:  # Permissions error
        missing_perms = extract_missing_permissions(error_msg)
        raise PermissionError(
            f"Missing permissions: {missing_perms}. "
            f"Please re-authorize with: {build_auth_url(missing_perms)}"
        )
```

### 2.3 Error Code 10: Validation Error

```
常见验证错误：
- 字段值无效
- 字段类型不匹配
- 必填字段缺失
- 字段值超出范围

处理策略：
1. 解析错误消息中的字段名
2. 修正参数后重试
3. 记录详细错误日志

```python
def handle_validation_error(error_msg):
    # 解析字段名
    import re
    field_match = re.search(r'\[([^\]]+)\]', error_msg)
    if field_match:
        field_name = field_match.group(1)
        logger.error(f"Validation error on field: {field_name}, msg: {error_msg}")
        return {
            'should_retry': False,
            'should_fix': True,
            'field': field_name,
            'message': error_msg,
        }
    return {'should_retry': False, 'should_fix': False}
```

### 2.4 Error Code 613: App Limit

```
App Limit 错误：
- 应用级别的功能限制
- 某些 API 端点需要应用审核通过才能使用
- 某些功能需要 Business Manager 授权

处理策略：
1. 检查应用是否在 App Review 中
2. 确认所需的 OAuth scopes 已授权
3. 如果是新功能，可能需要申请白名单

```python
def handle_app_limit_error(error_msg):
    if "feature_not_enabled" in error_msg.lower():
        return {
            'should_retry': False,
            'action': 'request_feature_access',
            'message': 'Feature requires approval, contact Meta support',
        }
    elif "business_manager_required" in error_msg.lower():
        return {
            'should_retry': False,
            'action': 'use_business_manager',
            'message': 'This endpoint requires Business Manager',
        }
```

### 2.5 Error Code 368: Duplicate

```
重复操作错误：
- 创建已存在的资源
- 重复提交同一请求
- 幂等性问题

处理策略：
1. 检查是否已存在相同资源
2. 如果是幂等操作，返回现有资源
3. 记录重复请求，防止业务逻辑错误

```python
def handle_duplicate_error(error_msg, resource_type, resource_id):
    # 尝试获取现有资源
    existing = get_existing_resource(resource_type, resource_id)
    if existing:
        logger.info(f"Duplicate create skipped, using existing: {existing['id']}")
        return {'should_retry': False, 'result': existing}
    else:
        raise
```

---

## 三、Meta API 特殊错误处理

### 3.1 CAPI 事件匹配失败

```
CAPI 事件匹配问题：
- 用户数据哈希不匹配
- event_id 重复
- action_source 错误

处理：
```python
def handle_capi_match_failure(event_data, match_result):
    if match_result.get('event_match_weight', 1.0) < 0.5:
        logger.warning(
            f"Low event match weight: {match_result.get('event_match_weight')}. "
            f"Consider adding more user_data fields (email, phone)."
        )
        # 建议增加 user_data 字段
        return suggest_additional_fields(event_data)
```

### 3.2 Insight 数据延迟

```
Meta Insight 数据延迟：
- 通常 T+1 更新
- 高峰期间可能延迟更久
- Conversion API 数据可能有 1-2 小时延迟

处理：
```python
def get_insights_safely(ad_account_id, fields, date_preset='last_7d'):
    # Meta 建议只查询 T-2 及之前的数据
    since = (datetime.now() - timedelta(days=2)).strftime('%Y-%m-%d')
    until = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')

    try:
        insights = AdAccount(ad_account_id).get_insights(
            fields=fields,
            params={'date_preset': 'custom', 'since': since, 'until': until},
        )
        return insights
    except FacebookRequestError as e:
        if e.api_error_code() == 8000:  # Business limit
            time.sleep(60)
            return get_insights_safely(ad_account_id, fields, date_preset)
        raise
```

---

## 四、自测题

### Q1: Meta API 的 error_subcode 2018003 和 2018004 有什么区别？

<details>
<summary>点击查看答案</summary>

**2018003 (BURST_LIMIT_EXCEEDED)**:
- 短期突发限流
- 通常在短时间内发送大量请求触发
- 建议等待 60 秒后重试
- 这是"突发"保护，不是长期限流

**2018004 (PER_USER_LIMIT_EXCEEDED)**:
- 用户级别的长期限流
- 每分钟请求数超限
- 需要降低整体请求速率
- 建议等待更长（2-5 分钟）

处理区别：
- BURST: 快速重试（60s）
- PER_USER: 降低速率，错峰执行
</details>

### Q2: 如何处理 Meta 的 " (#200) Permissions error"？

<details>
<summary>点击查看答案</summary>

步骤：
1. 从错误消息中提取缺失的 scope
   ```
   Missing permissions: read_audience_network_insights, manage_pages
   ```

2. 构建重新授权 URL
   ```python
   auth_url = (
       "https://www.facebook.com/dialog/oauth?"
       f"client_id={APP_ID}&"
       f"redirect_uri={REDIRECT_URI}&"
       f"scope={','.join(missing_scopes)}&"
       f"response_type=token"
   )
   ```

3. 提示用户重新授权
4. 授权完成后，用新 Token 重试
</details>

---

*本文档是 Meta Marketing API 错误处理的完整指南。*
