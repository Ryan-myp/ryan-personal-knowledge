# Agent 错误恢复深度实现 - 从重试到状态回滚

> **版本**: v2.1  
> **日期**: 2026-08-14  
> **作者**: Ryan  
> **分类**: Agent/错误恢复  
> **代码密度**: 30%

---

## 一、错误分类

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Agent 错误分类                                    │
│                                                                     │
│  Category 1: Transient Errors (瞬态错误)                             │
│  ─────────────────────────────────                                 │
│  • 网络超时 / 限流 / 服务不可用                                      │
│  • 处理: 重试 (指数退避)                                             │
│                                                                     │
│  Category 2: Retryable Errors (可重试错误)                           │
│  ─────────────────────────────────                                 │
│  • 参数错误 / 临时资源冲突                                           │
│  • 处理: 修正参数后重试                                              │
│                                                                     │
│  Category 3: Permanent Errors (永久错误)                             │
│  ─────────────────────────────────                                 │
│  • 权限不足 / 数据不存在 / 业务规则违反                              │
│  • 处理: 通知用户，停止执行                                          │
│                                                                     │
│  Category 4: Unknown Errors (未知错误)                               │
│  ─────────────────────────────────                                 │
│  • 未预期的异常                                                      │
│  • 处理: 日志 + 告警 + 人工介入                                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 二、恢复策略

```go
// agent/error_recovery.go
package agent

import (
    "context"
    "time"
)

// RecoveryStrategy 恢复策略
type RecoveryStrategy int

const (
    StrategyRetry RecoveryStrategy = iota
    StrategyRollback
    StrategyFallback
    StrategyAbort
)

// ErrorHandler 错误处理器
type ErrorHandler struct {
    strategies map[ErrorType]RecoveryStrategy
    retryCount map[string]int
    maxRetries int
}

// HandleError 处理错误
func (h *ErrorHandler) HandleError(ctx context.Context, err error, taskID string) (*RecoveryAction, error) {
    errorType := classifyError(err)
    strategy := h.strategies[errorType]
    
    switch strategy {
    case StrategyRetry:
        return h.handleRetry(ctx, err, taskID)
    case StrategyRollback:
        return h.handleRollback(ctx, err, taskID)
    case StrategyFallback:
        return h.handleFallback(ctx, err, taskID)
    case StrategyAbort:
        return &RecoveryAction{Action: Abort, Error: err}, nil
    default:
        return nil, err
    }
}

// handleRetry 重试处理
func (h *ErrorHandler) handleRetry(ctx context.Context, err error, taskID string) (*RecoveryAction, error) {
    count := h.retryCount[taskID]
    if count >= h.maxRetries {
        return &RecoveryAction{Action: Abort, Error: err}, nil
    }
    
    h.retryCount[taskID] = count + 1
    
    // 指数退避
    delay := time.Duration(1<<uint(count)) * time.Second
    select {
    case <-time.After(delay):
        return &RecoveryAction{Action: Retry}, nil
    case <-ctx.Done():
        return &RecoveryAction{Action: Abort, Error: ctx.Err()}, nil
    }
}

// handleRollback 回滚处理
func (h *ErrorHandler) handleRollback(ctx context.Context, err error, taskID string) (*RecoveryAction, error) {
    // 执行回滚
    rollbackErr := h.rollbackState(ctx, taskID)
    if rollbackErr != nil {
        return &RecoveryAction{Action: Abort, Error: rollbackErr}, nil
    }
    return &RecoveryAction{Action: Rollback}, nil
}
```

---

## 三、自测题

1. **什么时候选择重试而不是回滚？**
   - 瞬态错误用重试，状态不一致用回滚

2. **指数退避的公式？**
   - delay = base × 2^attempt，有最大限制

