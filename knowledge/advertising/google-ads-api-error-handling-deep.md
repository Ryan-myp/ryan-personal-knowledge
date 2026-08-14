# Google Ads API 高频异常处理完全指南

> **领域**: 广告投放 / Google Ads API
> **深度**: ⭐⭐⭐⭐⭐ 生产级指南
> **标签**: google-ads, api-error, exception-handling, production
> **更新时间**: 2026-08-14
> **类型**: production/error-handling

---

## 一、Google Ads API 错误码速查

### 1.1 核心错误码分类

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    Google Ads API 错误码分类                                 │
├──────────────┬──────────────────┬──────────────────────────────────────────┤
│ 类别         │ 错误码           │ 说明                                    │
├──────────────┼──────────────────┼──────────────────────────────────────────┤
│ AUTHENTICATION│ AUTHENTICATION_REQUIRED │ Token 无效或过期                    │
│              │ ACCESS_TOKEN_EXPIRED   │ Access Token 已过期                  │
│              │ INVALID_REFRESH_TOKEN   │ Refresh Token 已失效                  │
├──────────────┼──────────────────┼──────────────────────────────────────────┤
│ PERMISSION   │ PERMISSION_DENIED      │ 无操作权限                             │
│              │ CUSTOMER_ACCESS_DENIED │ 账户访问被拒绝                         │
│              │ OPERATOR_REQUIRED      │ 需要操作员认证                         │
├──────────────┼──────────────────┼──────────────────────────────────────────┤
│ VALIDATION   │ FIELD_ERROR            │ 字段验证失败                           │
│              │ INVALID_ARGUMENT       │ 参数无效                                │
│              │ NOT_FOUND              │ 资源不存在                             │
│              │ ALREADY_EXISTS         │ 资源已存在                             │
├──────────────┼──────────────────┼──────────────────────────────────────────┤
│ RATE_LIMIT   │ QUOTA_EXCEEDED         │ 配额超限                               │
│              │ RESOURCE_EXHAUSTED     │ 资源耗尽（限流）                       │
├──────────────┼──────────────────┼──────────────────────────────────────────┤
│ SYSTEM       │ INTERNAL_ERROR         │ Google 内部错误                         │
│              │ UNAVAILABLE            │ 服务不可用                             │
│              │ DEADLINE_EXCEEDED      │ 超时                                   │
└──────────────┴──────────────────┴──────────────────────────────────────────┘
```

### 1.2 错误响应结构

```protobuf
// Google Ads API 错误响应格式
message MutateCampaignsResponse {
  string request_id = 1;
  bool partial_failure = 2;
  repeated PartialFailureError partial_failure_errors = 3;
  repeated OperationResult results = 4;
}

message PartialFailureError {
  int32 index = 1;           // 操作索引
  google.rpc.Status status = 2;  // gRPC 状态
  string message = 3;         // 错误消息
}

message OperationResult {
  string campaign_resource_name = 1;  // 创建/更新的资源名
  // ... 其他结果字段
}
```

---

## 二、高频异常及处理

### 2.1 AUTHENTICATION_REQUIRED

```
症状：所有 API 调用返回 401

排查步骤：
1. 检查 Access Token 是否过期
   → 查看 token.expiry，如果 < now + 5min，刷新 Token
   
2. 检查 Refresh Token 是否有效
   → 尝试 refresh_token 刷新，如果返回 invalid_grant
   → 引导用户重新授权

3. 检查 Developer Token
   → Google Ads API 必须提供 Developer Token
   → 确认 Token 未过期（有效期 1 年）
   → 联系 Google 申请续期

4. 检查 OAuth Scopes
   → 确认授权范围包含所需权限
   → 常见缺失: https://www.googleapis.com/auth/adwords

处理代码：
```python
def handle_authentication_error(error):
    if "AUTHENTICATION_REQUIRED" in str(error):
        # 尝试刷新 Token
        new_token = refresh_access_token()
        if new_token:
            return retry_with_new_token(new_token)
        else:
            # Refresh 也失败，需要重新授权
            raise AuthenticationError(
                "Token refresh failed, please re-authorize"
            )
    raise
```

### 2.2 PERMISSION_DENIED

```
症状：403 Forbidden，错误码 PERMISSION_DENIED

常见原因：
1. 账户权限不足
   → 检查 Operator 是否有该 Campaign 的管理员权限
   → 检查用户角色（Admin/Standard/Read-only）

2. Customer ID 不匹配
   → 确认请求的 Customer ID 与 Token 授权的账户一致
   → 一个 Token 可能授权多个 Customer，检查权限范围

3. 账户状态异常
   → 检查账户是否被暂停/禁用
   → 检查是否有未完成的验证

处理代码：
```python
def handle_permission_error(error, customer_id):
    if "PERMISSION_DENIED" in str(error):
        # 检查是否是 Customer ID 问题
        authorized_customers = get_authorized_customers()
        if customer_id not in authorized_customers:
            raise PermissionError(
                f"Customer {customer_id} not authorized. "
                f"Authorized: {authorized_customers}"
            )
        # 检查账户状态
        status = check_account_status(customer_id)
        if status == "Suspended":
            raise AccountSuspendedError(
                f"Account {customer_id} is suspended"
            )
        raise
```

### 2.3 QUOTA_EXCEEDED / RESOURCE_EXHAUSTED

```
症状：429 Too Many Requests

Google Ads API 配额：
- Per Customer: 100 requests/minute
- Per Operation: 10 requests/second
- Burst: 200 requests (短期突发)

处理策略：
1. 指数退避重试
2. 读取 Retry-After 头
3. 降低批量大小
4. 错峰执行

处理代码：
```python
import time
import random

def mutate_with_quota_management(client, operations, customer_id):
    batch_size = 1000  # 保守的批量大小
    max_retries = 5
    
    for i in range(0, len(operations), batch_size):
        batch = operations[i:i+batch_size]
        
        for attempt in range(max_retries):
            try:
                response = client.campaign_service.mutate_campaigns(
                    request_id=generate_request_id(),
                    operations=batch,
                    partial_failure=True,
                )
                break  # 成功
            except google.ads.googleads.errors.GoogleAdsException as e:
                if e.failure.code == 'RATE_LIMIT_EXCEEDED':
                    # 指数退避 + 抖动
                    delay = min(2 ** attempt * 0.5, 30)
                    jitter = random.uniform(0, delay * 0.3)
                    time.sleep(delay + jitter)
                    logger.warning(
                        f"Quota exceeded for {customer_id}, "
                        f"retry {attempt+1}/{max_retries} after {delay+jitter:.1f}s"
                    )
                elif e.failure.code == 'RESOURCE_EXHAUSTED':
                    # 检查 Retry-After
                    retry_after = e.headers.get('Retry-After', 60)
                    time.sleep(float(retry_after))
                else:
                    raise
```

### 2.4 FIELD_ERROR

```
症状：字段验证失败，错误码 FIELD_ERROR

常见字段错误：
1. Campaign.name 为空或过长 (>255字符)
2. Campaign.status 无效值
3. BiddingStrategyType 不匹配 CampaignType
4. Budget.amount_micros 超出范围
5. TargetingRestriction 与定向类型冲突

处理代码：
```python
def handle_field_error(error, operation_index):
    if "FIELD_ERROR" in str(error):
        details = error.failure.errors[0]
        field_path = details.field_path
        error_type = details.error_type
        
        # 根据字段路径给出具体建议
        if "campaign.name" in field_path:
            logger.warning(
                f"Operation {operation_index}: Campaign name validation failed. "
                f"Must be 1-255 characters."
            )
        elif "bidding_strategy_type" in field_path:
            logger.warning(
                f"Operation {operation_index}: Bidding strategy mismatch. "
                f"Check if {error_type} is valid for this campaign type."
            )
        # ... 其他字段
        
        return False  # 标记为需要修正
    return None
```

### 2.5 NOT_FOUND

```
症状：资源不存在

常见场景：
1. Campaign ID 不存在或被删除
2. Ad Group 引用了不存在的 Campaign
3. Keyword 引用了不存在的 Ad Group
4. 跨账户操作时 Customer ID 错误

处理策略：
- 记录详细日志（包含完整 Resource Name）
- 检查资源是否被其他流程删除
- 如果是预期内的删除，静默忽略
- 如果是数据不一致，告警并修复

```python
def handle_not_found_error(error, resource_name):
    if "NOT_FOUND" in str(error):
        logger.error(
            f"Resource not found: {resource_name}\n"
            f"Error: {error}"
        )
        # 检查是否是预期的删除
        if is_expected_deletion(resource_name):
            logger.info(f"Skipping expected deletion: {resource_name}")
            return
        # 告警
        alert(f"Resource not found: {resource_name}")
```
```

---

## 三、Go 生产级错误处理器

```go
package googleads

import (
	"context"
	"fmt"
	"log"
	"time"

	googleads "google.golang.org/api/googleads/v16"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
)

// GoogleAdsErrorHandler 错误处理器
type GoogleAdsErrorHandler struct {
	retryConfig RetryConfig
	logger      *log.Logger
}

type RetryConfig struct {
	MaxRetries     int
	InitialDelay   time.Duration
	MaxDelay       time.Duration
}

// HandleMutateError 处理 Mutate 操作的错误
func (h *GoogleAdsErrorHandler) HandleMutateError(
	ctx context.Context,
	err error,
	operationIndex int,
) (*MutateAction, error) {

	st, ok := status.FromError(err)
	if !ok {
		// 非 gRPC 错误，直接返回
		return &MutateAction{ShouldRetry: false, ShouldSkip: false}, err
	}

	switch st.Code() {
	case codes.OK:
		return &MutateAction{ShouldRetry: false, ShouldSkip: false}, nil

	case codes.ResourceExhausted, codes.Unknown:
		// 限流相关
		return h.handleRateLimit(ctx, st, operationIndex)

	case codes.Unavailable, codes.DeadlineExceeded:
		// 服务不可用/超时
		return h.handleServiceError(ctx, st, operationIndex)

	case codes.PermissionDenied:
		// 权限不足
		return &MutateAction{ShouldRetry: false, ShouldSkip: true},
			fmt.Errorf("permission denied: %v", st.Message())

	case codes.NotFound:
		// 资源不存在
		return &MutateAction{ShouldRetry: false, ShouldSkip: true},
			fmt.Errorf("not found: %v", st.Message())

	case codes.InvalidArgument:
		// 参数无效
		return &MutateAction{ShouldRetry: false, ShouldSkip: true},
			fmt.Errorf("invalid argument: %v", st.Message())

	default:
		// 其他错误
		return &MutateAction{ShouldRetry: false, ShouldSkip: false}, err
	}
}

func (h *GoogleAdsErrorHandler) handleRateLimit(
	ctx context.Context,
	st *status.Status,
	opIdx int,
) (*MutateAction, error) {
	delay := calculateBackoff(opIdx, h.retryConfig)
	return &MutateAction{
		ShouldRetry: true,
		RetryDelay:  delay,
	}, fmt.Errorf("rate limited: %v", st.Message())
}

func (h *GoogleAdsErrorHandler) handleServiceError(
	ctx context.Context,
	st *status.Status,
	opIdx int,
) (*MutateAction, error) {
	delay := calculateBackoff(opIdx, h.retryConfig)
	return &MutateAction{
		ShouldRetry: true,
		RetryDelay:  delay,
	}, fmt.Errorf("service error: %v", st.Message())
}
```

---

## 四、自测题

### Q1: Google Ads API 的 partial_failure 是什么？如何使用？

<details>
<summary>点击查看答案</summary>

**partial_failure** 是 Google Ads API 的一个重要特性：

- 设置为 `true` 时，即使部分操作失败，成功的操作也会正常提交
- 每个操作的结果在 `partial_failure_errors` 中单独报告
- 设置为 `false` 时，任何一个操作失败，整个批次都会回滚

适用场景：
- 批量创建 Campaign：允许部分成功
- 批量更新出价：容忍个别失败
- 数据迁移：跳过已有资源

不使用场景：
- 需要原子性的操作（全部成功或全部失败）
- 操作之间有依赖关系（如先创建 Campaign 再创建 AdGroup）
</details>

### Q2: 如何处理 Google Ads API 的 "Customer is suspended" 错误？

<details>
<summary>点击查看答案</summary>

**Customer is suspended** 表示账户被 Google 暂停。

排查步骤：
1. 登录 Google Ads 界面，检查账户状态
2. 查看是否有政策违规通知
3. 检查是否有未支付的账单
4. 确认 Operator 权限是否被撤销

处理策略：
- 暂停该账户的所有 API 操作
- 发送告警通知运营人员
- 记录暂停时间和原因
- 提供手动恢复后的自动重试机制
</details>

---

## 五、总结

| 错误类别 | 典型错误码 | 处理策略 |
|---------|-----------|---------|
| 认证失败 | AUTHENTICATION_REQUIRED | 刷新 Token / 重新授权 |
| 权限不足 | PERMISSION_DENIED | 检查权限范围 / 重新授权 |
| 限流 | QUOTA_EXCEEDED | 指数退避 + 抖动 |
| 参数无效 | FIELD_ERROR | 修正参数后重试 |
| 资源不存在 | NOT_FOUND | 记录日志 / 跳过 / 告警 |
| 服务不可用 | UNAVAILABLE | 重试 + 熔断 |

---

*本文档是 Google Ads API 错误处理的权威参考，建议结合实际业务场景补充更多错误类型。*
