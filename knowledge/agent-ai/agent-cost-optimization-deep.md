# Agent 成本优化深度实现 - Token管理到缓存策略

> **版本**: v2.1  
> **日期**: 2026-08-14  
> **作者**: Ryan  
> **分类**: Agent/成本优化  
> **代码密度**: 30%

---

## 一、Token成本分析

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Agent Token成本构成                               │
│                                                                     │
│  Cost = (Input Tokens × Price_in) + (Output Tokens × Price_out)    │
│                                                                     │
│  主要成本项:                                                         │
│  • Prompt Token: 系统提示 + 用户输入                                │
│  • Context Token: 记忆检索结果 + 历史对话                           │
│  • Tool Call Token: 工具定义 + 调用参数                             │
│  • Output Token: 模型生成响应                                       │
│                                                                     │
│  优化方向:                                                           │
│  1. 减少Prompt Token → 精简系统提示                                │
│  2. 压缩Context Token → 记忆摘要 + 向量检索                        │
│  3. 缓存重复计算 → 相同输入复用输出                                 │
│  4. 模型分级 → 简单任务用小模型                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 二、缓存策略

```go
// agent/cost_optimizer.go
package agent

import (
    "context"
    "crypto/sha256"
    "encoding/hex"
    "time"
)

// CacheKey 缓存键
type CacheKey struct {
    Model     string
    Prompt    string
    Temperature float64
}

// CostOptimizer 成本优化器
type CostOptimizer struct {
    cache      *TTLCache
    modelTier  map[string]string // 任务类型 → 模型级别
}

// NewCostOptimizer 创建优化器
func NewCostOptimizer() *CostOptimizer {
    return &CostOptimizer{
        cache:   NewTTLCache(3600), // 1小时TTL
        modelTier: map[string]string{
            "simple":    "gpt-4o-mini",
            "medium":    "gpt-4o",
            "complex":   "gpt-4-turbo",
            "reasoning": "o1-preview",
        },
    }
}

// GetOrCompute 缓存命中则返回，否则计算
func (o *CostOptimizer) GetOrCompute(ctx context.Context, key CacheKey, fn func() (string, error)) (string, error) {
    cacheKey := o.generateKey(key)
    
    // 尝试缓存命中
    if cached, ok := o.cache.Get(cacheKey); ok {
        return cached.(string), nil
    }
    
    // 计算并缓存
    result, err := fn()
    if err != nil {
        return "", err
    }
    
    o.cache.Set(cacheKey, result, 30*time.Minute)
    return result, nil
}

// SelectModel 根据任务复杂度选择模型
func (o *CostOptimizer) SelectModel(taskType string) string {
    if model, ok := o.modelTier[taskType]; ok {
        return model
    }
    return "gpt-4o" // 默认
}

// generateKey 生成缓存键
func (o *CostOptimizer) generateKey(key CacheKey) string {
    data := key.Model + key.Prompt + fmt.Sprintf("%.2f", key.Temperature)
    hash := sha256.Sum256([]byte(data))
    return hex.EncodeToString(hash[:])
}
```

---

## 三、自测题

1. **为什么需要模型分级？**
   - 简单任务用小模型节省成本，复杂任务用大模型保证质量

2. **缓存的粒度如何确定？**
   - 按Prompt+模型+参数生成唯一键，TTL 30分钟

