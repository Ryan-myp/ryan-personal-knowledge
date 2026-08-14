# Google Ads Streaming Mutate 深度指南

> **领域**: 广告投放 / Google Ads API
> **深度**: ⭐⭐⭐⭐⭐ 实战级指南
> **标签**: google-ads, streaming-mutate, api, batch, grpc
> **更新时间**: 2026-08-14
> **类型**: deep-dive/api

---

## 一、Streaming Mutate 的背景

### 1.1 为什么需要 Streaming Mutate？

```
传统 Mutate API 的局限性：

REST Mutate (同步):
├── 请求 → 响应 模式
├── 单次请求最多 10,000 个操作
├── 超时限制: 60 秒
├── 大批量操作容易超时
└── 错误处理困难（部分失败难以定位）

Streaming Mutate (gRPC 流式):
├── 流式请求 → 流式响应
├── 单次流可包含无限操作
├── 无硬性超时限制
├── 实时返回每个操作的结果
└── 细粒度错误处理
```

### 1.2 适用场景

```
必须使用 Streaming Mutate 的场景：

✅ 批量操作 > 10,000 条
   └── 例如: 批量更新 50,000 个关键词的出价

✅ 需要实时反馈的操作
   └── 例如: 实时创建广告并立即获取 ID

✅ 长时间运行的任务
   └── 例如: 跨账户批量操作

✅ 需要精细错误处理
   └── 例如: 每个操作的单独成功/失败状态

可以继续使用 REST Mutate 的场景：

✅ 小规模操作 (< 1,000 条)
✅ 简单的 CRUD 操作
✅ 开发阶段快速验证
✅ 不需要实时反馈
```

---

## 二、Streaming Mutate 架构

### 2.1 gRPC 流式通信

```
Streaming Mutate 通信模型：

Client (Go)                          Server (Google)
    │                                      │
    │  ┌────────────────────────────────┐  │
    │  │  MutateCampaignsRequest        │  │
    │  │  ├── customer_id: 123456789    │  │
    │  │  ├── operations: [...]         │  │
    │  │  │   ├── operation 1           │  │
    │  │  │   ├── operation 2           │  │
    │  │  │   └── ... (thousands)       │  │
    │  │  └── validate_only: false      │  │
    │  └────────────────────────────────┘  │
    │  ──────────────────────────────────▶ │
    │                                      │
    │  ◀────────────────────────────────── │
    │  ┌────────────────────────────────┐  │
    │  │  MutateCampaignsResponse       │  │
    │  │  ├── operation_index: 0         │  │
    │  │  ├── resource_name: ...         │  │
    │  │  └── results: [...]             │  │
    │  └────────────────────────────────┘  │
    │  (stream continues...)               │
    │                                      │
    └──────────────────────────────────────┘
```

### 2.2 请求/响应结构

```protobuf
// Streaming Mutate 请求流
message MutateCampaignRequest {
  string customer_id = 1;           // 客户账户 ID
  repeated CampaignOperation operations = 2;  // 操作列表
  bool validate_only = 3;           // 仅验证，不执行
  string request_id = 4;            // 请求唯一 ID (用于去重)
  bool partial_failure = 5;         // 部分失败时是否继续
}

// Streaming Mutate 响应流
message MutateCampaignResponse {
  int32 operation_index = 1;        // 操作索引
  string resource_name = 2;         // 创建的资源名称
  string mutate_operation_id = 3;   // 操作 ID
  PartialFailureError partial_failure_error = 4;  // 部分失败错误
  repeated OperationResult results = 5;           // 操作结果
}
```

---

## 三、Go 实现

### 3.1 基础实现

```go
package main

import (
	"context"
	"fmt"
	"log"
	"time"

	googleads "google.golang.org/api/googleads/googleads/v16"
	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials/oauth"
)

// StreamingMutateClient 流式 mutate 客户端
type StreamingMutateClient struct {
	client       *googleads.GoogleAdsClient
	customerID   string
	batchSize    int
}

// NewStreamingMutateClient 创建客户端
func NewStreamingMutateClient(token, clientID, clientSecret, devToken string, customerID string) (*StreamingMutateClient, error) {
	gac, err := googleads.NewGoogleAdsClient(
		googleads.WithOAuth2Credentials(&oauth2 Credentials{
			ClientID:     clientID,
			ClientSecret: clientSecret,
			RefreshToken: token,
		}),
		googleads.WithDeveloperToken(devToken),
	)
	if err != nil {
		return nil, fmt.Errorf("failed to create client: %w", err)
	}
	return &StreamingMutateClient{
		client:     gac,
		customerID: customerID,
		batchSize:  1000,
	}, nil
}

// BatchMutateCampaigns 批量流式创建广告系列
func (c *StreamingMutateClient) BatchMutateCampaigns(ctx context.Context, campaigns []*ad.Campaign) error {
	totalCreated := 0
	totalFailed := 0
	startTime := time.Now()

	// 分批处理
	for i := 0; i < len(campaigns); i += c.batchSize {
		end := min(i+c.batchSize, len(campaigns))
		batch := campaigns[i:end]

		fmt.Printf("Processing batch %d-%d of %d\n", i, end, len(campaigns))

		// 创建流式请求
		req := &adpb.MutateCampaignsRequest{
			CustomerId: ptrInt64(int64(c.customerID)),
			Operations: make([]*adpb.CampaignOperation, len(batch)),
			PartialFailure: pb.Bool(true),
		}

		for j, camp := range batch {
			req.Operations[j] = &adpb.CampaignOperation{
				Update: camp,
				UpdateMask: allFieldMask(camp),
			}
		}

		// 执行流式 mutate
		client, err := c.client.GetGoogleAdsServiceClient()
		if err != nil {
			return fmt.Errorf("failed to get service client: %w", err)
		}

		stream, err := client.MutateCampaigns(ctx)
		if err != nil {
			return fmt.Errorf("failed to create stream: %w", err)
		}

		// 发送请求
		if err := stream.Send(req); err != nil {
			return fmt.Errorf("failed to send request: %w", err)
		}

		// 接收响应
		var batchCreated, batchFailed int
		for {
			resp, err := stream.Recv()
			if err == io.EOF {
				break
			}
			if err != nil {
				return fmt.Errorf("failed to receive response: %w", err)
			}

			if resp.PartialFailureError != nil {
				batchFailed++
				log.Printf("Operation %d failed: %v", resp.OperationIndex, resp.PartialFailureError)
			} else {
				batchCreated++
				if resp.ResourceName != "" {
					fmt.Printf("  Created: %s\n", resp.ResourceName)
				}
			}
		}

		totalCreated += batchCreated
		totalFailed += batchFailed
	}

	elapsed := time.Since(startTime)
	fmt.Printf("Batch complete: %d created, %d failed in %v\n", totalCreated, totalFailed, elapsed)
	return nil
}
```

### 3.2 高级实现（带重试和限流）

```go
package streaming

import (
	"context"
	"fmt"
	"math"
	"math/rand"
	"sync"
	"time"

	"google.golang.org/api/googleads/googleads/v16"
	"google.golang.org/grpc"
	"google.golang.org/grpc/metadata"
	"google.golang.org/grpc/status"
)

// RetryConfig 重试配置
type RetryConfig struct {
	MaxRetries    int
	InitialDelay  time.Duration
	MaxDelay      time.Duration
	BackoffFactor float64
}

// StreamingMutateOptions 流式 mutate 配置
type StreamingMutateOptions struct {
	BatchSize     int
	RetryConfig   RetryConfig
	Timeout       time.Duration
	RequestID     string
	ValidateOnly  bool
}

// DefaultOptions 默认配置
func DefaultOptions() StreamingMutateOptions {
	return StreamingMutateOptions{
		BatchSize: 1000,
		RetryConfig: RetryConfig{
			MaxRetries:    3,
			InitialDelay:  time.Second,
			MaxDelay:      30 * time.Second,
			BackoffFactor: 2.0,
		},
		Timeout:    5 * time.Minute,
		ValidateOnly: false,
	}
}

// BatchMutateWithRetry 带重试的批量流式 mutate
func BatchMutateWithRetry(
	ctx context.Context,
	client *googleads.GoogleAdsClient,
	customerID int64,
	operations []*mutateOp,
	opts StreamingMutateOptions,
) (*BatchResult, error) {
	result := &BatchResult{
		Created:  make([]string, 0),
		Failed:   make([]FailedOp, 0),
		Skipped:  make([]string, 0),
	}

	// 生成请求 ID
	requestID := opts.RequestID
	if requestID == "" {
		requestID = generateRequestID()
	}

	ctx, cancel := context.WithTimeout(ctx, opts.Timeout)
	defer cancel()

	// 分批处理
	for i := 0; i < len(operations); i += opts.BatchSize {
		end := min(i+opts.BatchSize, len(operations))
		batch := operations[i:end]

		batchCtx, batchCancel := context.WithTimeout(ctx, 2*time.Minute)
		
		// 构建请求
		req := buildMutateRequest(customerID, batch, requestID, opts.ValidateOnly)

		// 带重试的执行
		var batchResult *BatchResult
		var lastErr error
		
		for attempt := 0; attempt <= opts.RetryConfig.MaxRetries; attempt++ {
			batchResult, lastErr = executeStream(batchCtx, client, req)
			if lastErr == nil {
				break
			}

			// 判断是否可重试
			if !isRetryable(lastErr) {
				break
			}

			// 指数退避
			delay := calculateBackoff(attempt, opts.RetryConfig)
			select {
			case <-batchCtx.Done():
				return nil, batchCtx.Err()
			case <-time.After(delay):
			}
		}

		if lastErr != nil {
			// 所有重试失败，记录为失败
			for _, op := range batch {
				result.Failed = append(result.Failed, FailedOp{
					Index:   i + op.Index,
					Error:   lastErr.Error(),
					Attempt: opts.RetryConfig.MaxRetries + 1,
				})
			}
		} else if batchResult != nil {
			// 合并结果
			result.Created = append(result.Created, batchResult.Created...)
			result.Failed = append(result.Failed, batchResult.Failed...)
			result.Skipped = append(result.Skipped, batchResult.Skipped...)
		}

		batchCancel()

		// 进度日志
		if (i+len(batch))%5000 == 0 || (i+len(batch)) == len(operations) {
			fmt.Printf("Progress: %d/%d (%.1f%%)\n", i+len(batch), len(operations),
				float64(i+len(batch))/float64(len(operations))*100)
		}
	}

	return result, nil
}

// executeStream 执行单次流式 mutate
func executeStream(ctx context.Context, client *googleads.GoogleAdsClient, req *mutateRequest) (*BatchResult, error) {
	service := client.GetCampaignService()
	stream, err := service.MutateCampaigns(ctx, req)
	if err != nil {
		return nil, fmt.Errorf("stream creation failed: %w", err)
	}

	result := &BatchResult{}
	
	for {
		resp, err := stream.Recv()
		if err == io.EOF {
			break
		}
		if err != nil {
			return result, fmt.Errorf("stream receive error: %w", err)
		}

		if resp.PartialFailureError != nil {
			result.Failed = append(result.Failed, FailedOp{
				Index: int(resp.OperationIndex),
				Error: resp.PartialFailureError.String(),
			})
		} else if resp.ResourceName != "" {
			result.Created = append(result.Created, resp.ResourceName)
		}
	}

	return result, nil
}

// isRetryable 判断错误是否可重试
func isRetryable(err error) bool {
	if err == nil {
		return false
	}
	
	st, ok := status.FromError(err)
	if !ok {
		return false
	}
	
	// 可重试的状态码
	retryableCodes := []codes.Code{
		codes.Unavailable,    // 服务不可用
		codes.DeadlineExceeded, // 超时
		codes.ResourceExhausted, // 限流
		codes.Aborted,         // 操作被中止
	}
	
	for _, code := range retryableCodes {
		if st.Code() == code {
			return true
		}
	}
	return false
}

// calculateBackoff 计算退避延迟
func calculateBackoff(attempt int, config RetryConfig) time.Duration {
	delay := float64(config.InitialDelay)
	for i := 0; i < attempt; i++ {
		delay *= config.BackoffFactor
	}
	// 添加抖动
	jitter := rand.Float64() * 0.5 * delay
	delay += jitter
	// 限制最大延迟
	if delay > float64(config.MaxDelay) {
		delay = float64(config.MaxDelay)
	}
	return time.Duration(delay)
}
```

---

## 四、性能优化

### 4.1 批量大小调优

```
批量大小对性能的影响：

批量大小    内存占用    网络开销    重试代价    推荐场景
─────────────────────────────────────────────────────
100         低          高          低         开发/测试
500         中          中          中         常规场景
1000        中高        中          中高       生产环境推荐
5000        高          低          高         大批量操作
10000       很高        很低        很高       不建议（接近 REST 上限）

推荐配置：
- 常规操作: batchSize = 1000
- 大批量操作: batchSize = 5000
- 内存受限: batchSize = 500
```

### 4.2 并发控制

```
Streaming Mutate 并发模型：

单流模式（推荐）：
┌─────────────────────────────────────┐
│  Main Thread                         │
│  ├── 创建 1 个 gRPC stream          │
│  ├── 发送请求（包含数千操作）         │
│  ├── 接收响应（流式返回）             │
│  └── 处理结果                        │
└─────────────────────────────────────┘
优点：简单、有序、易于调试
缺点：串行处理，速度受限

多线程模式（高级）：
┌─────────────────────────────────────┐
│  Orchestrator                        │
│  ├── Worker 1: stream[0-999]        │
│  ├── Worker 2: stream[1000-1999]    │
│  ├── Worker 3: stream[2000-2999]    │
│  └── Merge Results                   │
└─────────────────────────────────────┘
优点：并行处理，速度快
缺点：复杂、无序、需要处理并发冲突
注意：同一账户的操作不能并发执行（可能冲突）
```

---

## 五、错误处理

### 5.1 错误类型

```
Streaming Mutate 错误分类：

传输层错误:
├── Unavailable: gRPC 连接断开
├── DeadlineExceeded: 超时
├── ResourceExhausted: 速率限制 (HTTP 429)
└── Internal: Google 服务端错误

业务层错误（Partial Failure）:
├── INVALID_ARGUMENT: 参数无效
├── NOT_FOUND: 资源不存在
├── PERMISSION_DENIED: 权限不足
├── ALREADY_EXISTS: 资源已存在
├── FIELD_ERROR: 字段级别错误
└── SIZE_LIMIT_EXCEEDED: 超出大小限制

去重错误:
├── DUPLICATE_MUTATE_OPERATION: 相同 request_id + operation 重复提交
└── 处理: 检查 operation hash 或跳过
```

### 5.2 错误恢复策略

```
错误恢复决策树：

收到错误
    │
    ├─ 传输层错误？
    │   ├─ Yes → 重试（指数退避）
    │   │   ├─ 重试 3 次仍失败？
    │   │   │   ├─ Yes → 记录失败 + 继续下一批
    │   │   │   └─ No → 成功重试
    │   │   └─ 限流 (429)？
    │   │       ├─ Yes → 等待 Retry-After 头
    │   │       └─ No → 标准退避
    │   │
    │   └─ No → 检查业务错误
    │
    ├─ Partial Failure？
    │   ├─ Yes → 继续处理其他操作（partial_failure=true）
    │   │   └─ 记录失败的操作详情
    │   │
    │   └─ No → 中断处理
    │
    └─ 最终状态
        ├─ 成功操作: 记录 resource_name
        ├─ 失败操作: 记录错误信息
        └─ 汇总报告
```

---

## 六、最佳实践

### 6.1 操作设计原则

```
Streaming Mutate 最佳实践：

1. 幂等性设计
   ├── 每个操作应该是幂等的（重复执行结果相同）
   ├── 使用 request_id 去重
   └── 检查操作结果避免重复创建

2. 批量设计
   ├── 按业务逻辑分组（如同一 campaign 的操作）
   ├── 单个 batch 控制在 1000-5000 个操作
   └── 避免跨 campaign 的大批量操作

3. 错误处理
   ├── 始终设置 partial_failure=true
   ├── 记录每个操作的详细错误
   └── 实现自动重试机制

4. 性能优化
   ├── 复用 gRPC 连接
   ├── 设置合理的 timeout
   ├── 避免在 stream 中处理过多操作
   └── 使用 validate_only 先验证再执行

5. 监控告警
   ├── 记录操作成功率
   ├── 监控处理耗时
   ├── 设置失败率告警阈值
   └── 定期 audit 操作结果
```

### 6.2 监控指标

```
Streaming Mutate 关键监控指标：

实时指标：
├── Operations per second (OPS)
├── Success rate (%)
├── Average latency per operation (ms)
├── Error rate by type
└── Stream duration

累计指标：
├── Total operations processed
├── Total time spent
├── Total errors
├── Retry count
└── Throughput trend

告警阈值：
├── Success rate < 95% → 警告
├── Success rate < 90% → 严重
├── Error rate > 10% → 停止执行
└── Avg latency > 5s → 性能告警
```

---

## 七、自测题

### Q1: Streaming Mutate 和 REST Mutate 的主要区别是什么？什么时候应该用哪个？

<details>
<summary>点击查看答案</summary>

**主要区别**：

| 维度 | REST Mutate | Streaming Mutate |
|------|------------|-----------------|
| 协议 | HTTP/REST | gRPC |
| 模式 | 请求-响应（同步） | 流式（异步） |
| 操作数限制 | 单次最多 10,000 | 无硬性限制 |
| 超时 | 60 秒 | 无硬性超时 |
| 错误处理 | 整体失败/成功 | 逐操作报告 |
| 适用规模 | 小规模 (< 10K) | 大规模 (> 10K) |

**选择建议**：
- REST: 日常小规模操作、开发调试、简单 CRUD
- Streaming: 大批量操作、生产环境批量任务、需要实时反馈的场景
</details>

### Q2: 如何处理 Streaming Mutate 中的部分失败？

<details>
<summary>点击查看答案</summary>

处理策略：

1. 设置 `partial_failure=true`
   - 即使部分操作失败，其余操作仍会执行
   
2. 逐操作检查响应
   ```go
   for resp := range stream {
       if resp.PartialFailureError != nil {
           // 记录失败
           logError(resp.OperationIndex, resp.PartialFailureError)
       } else {
           // 记录成功
           logSuccess(resp.ResourceName)
       }
   }
   ```

3. 汇总报告
   - 生成操作结果汇总
   - 区分成功/失败/跳过
   - 输出详细日志

4. 失败重试
   - 对失败操作单独重试
   - 使用不同的 request_id
   - 设置重试上限
</details>

---

## 八、总结

| 主题 | 核心要点 |
|------|---------|
| 协议 | gRPC 流式通信，比 REST 更适合大批量操作 |
| 批量 | 推荐 1000-5000 操作/批，平衡内存和性能 |
| 重试 | 指数退避 + 抖动，针对 Unavailable/429 等错误 |
| 错误 | partial_failure=true 逐操作报告 |
| 监控 | OPS、成功率、延迟、错误类型分布 |

---

*本文档是 Google Ads Streaming Mutate 的生产级指南，建议结合实际业务场景调整。*
