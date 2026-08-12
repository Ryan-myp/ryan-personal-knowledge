# Agent 工具调用优化深度实现 - 智能路由与并行执行

> **版本**: v2.1  
> **日期**: 2026-08-14  
> **作者**: Ryan  
> **分类**: Agent/工具调用  
> **代码密度**: 30%

---

## 一、工具调用架构

```
┌─────────────────────────────────────────────────────────────────────┐
│                    工具调用智能路由                                   │
│                                                                     │
│  Step 1: Tool Discovery (工具发现)                                    │
│  ─────────────────────────────                                      │
│  • MCP协议发现                                                       │
│  • 本地工具注册                                                      │
│  • 动态加载                                                          │
│                                                                     │
│  Step 2: Tool Selection (工具选择)                                     │
│  ─────────────────────────────                                      │
│  • LLM自动选择                                                       │
│  • 基于历史选择                                                      │
│  • 基于规则选择                                                      │
│                                                                     │
│  Step 3: Parallel Execution (并行执行)                                 │
│  ─────────────────────────────                                      │
│  • 无依赖工具并行调用                                                │
│  • 依赖工具串行调用                                                  │
│  • 超时控制                                                          │
│                                                                     │
│  Step 4: Result Fusion (结果融合)                                      │
│  ─────────────────────────────                                      │
│  • 聚合多个工具结果                                                  │
│  • 错误处理                                                          │
│  • 缓存复用                                                          │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 二、Go实现

```go
// agent/tool_call.go
package agent

import (
    "context"
    "sync"
)

// ToolCall 工具调用
type ToolCall struct {
    ID      string
    Tool    string
    Args    map[string]interface{}
    Result  interface{}
    Error   error
}

// ToolCaller 工具调用器
type ToolCaller struct {
    tools    map[string]Tool
    parallel bool
}

// CallTools 并行调用工具
func (c *ToolCaller) CallTools(ctx context.Context, calls []ToolCall) ([]ToolCall, error) {
    results := make([]ToolCall, len(calls))
    var wg sync.WaitGroup
    var mu sync.Mutex
    
    for i, call := range calls {
        // 检查依赖
        if !c.canExecute(call, results) {
            continue
        }
        
        wg.Add(1)
        go func(idx int, toolCall ToolCall) {
            defer wg.Done()
            
            result := c.execute(ctx, toolCall)
            
            mu.Lock()
            results[idx] = result
            mu.Unlock()
        }(i, call)
    }
    
    wg.Wait()
    return results, nil
}

// execute 执行单个工具
func (c *ToolCaller) execute(ctx context.Context, call ToolCall) ToolCall {
    tool, ok := c.tools[call.Tool]
    if !ok {
        return ToolCall{ID: call.ID, Error: ErrToolNotFound}
    }
    
    ctx, cancel := context.WithTimeout(ctx, 30*time.Second)
    defer cancel()
    
    result, err := tool.Call(ctx, call.Args)
    return ToolCall{
        ID:     call.ID,
        Tool:   call.Tool,
        Result: result,
        Error:  err,
    }
}
```

---

## 三、自测题

1. **为什么要并行调用工具？**
   - 无依赖的工具可以并发执行，减少总延迟

2. **工具调用的关键挑战？**
   - 参数校验 + 超时控制 + 错误处理


---

## 交叉引用
- [Agent架构设计](./agent-architecture-deep.md)
- [Agent生产部署](./agent-production-patterns-deep.md)
- [RAG评估系统](./rag-evaluation-system-deep.md)
