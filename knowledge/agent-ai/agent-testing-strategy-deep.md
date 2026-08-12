# Agent 测试策略深度实现 - 单元测试/集成测试/E2E测试

> **版本**: v2.1  
> **日期**: 2026-08-14  
> **作者**: Ryan  
> **分类**: Agent/测试策略  
> **代码密度**: 35%

---

## 一、测试金字塔

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Agent 测试金字塔                                  │
│                                                                     │
│                           ▲                                         │
│                          /E2E\                                      │
│                         /------\                                    │
│                        /Integ\                                     │
│                       /--------\                                   │
│                      /Unit   \                                   │
│                     /----------\                                  │
│                                                                     │
│  数量: 单元测试 > 集成测试 > E2E测试                                │
│  速度: 单元测试 > 集成测试 > E2E测试                                │
│  成本: E2E测试 > 集成测试 > 单元测试                                │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 二、测试实现

```go
// agent/testing_test.go
package agent_test

import (
    "testing"
)

// TestAgentPlanning 测试规划
func TestAgentPlanning(t *testing.T) {
    agent := NewTestAgent()
    plan := agent.Plan("Write a blog post about AI")
    
    if len(plan.Steps) == 0 {
        t.Fatal("expected at least one step")
    }
}

// TestAgentToolCalling 测试工具调用
func TestAgentToolCalling(t *testing.T) {
    agent := NewTestAgent()
    
    // 模拟工具响应
    agent.MockTool("search", func(args map[string]interface{}) interface{} {
        return []string{"result1", "result2"}
    })
    
    result, err := agent.CallTool("search", map[string]interface{}{
        "query": "AI trends 2026",
    })
    
    if err != nil {
        t.Fatalf("unexpected error: %v", err)
    }
    if len(result) != 2 {
        t.Fatalf("expected 2 results, got %d", len(result))
    }
}

// TestAgentMemory 测试记忆系统
func TestAgentMemory(t *testing.T) {
    agent := NewTestAgent()
    
    // 写入记忆
    err := agent.Memory.Set("user_pref", map[string]string{
        "language": "zh",
    })
    if err != nil {
        t.Fatal(err)
    }
    
    // 读取记忆
    pref, err := agent.Memory.Get("user_pref")
    if err != nil {
        t.Fatal(err)
    }
    if pref["language"] != "zh" {
        t.Fatalf("expected zh, got %s", pref["language"])
    }
}

// TestAgentErrorHandling 测试错误处理
func TestAgentErrorHandling(t *testing.T) {
    agent := NewTestAgent()
    
    // 模拟工具失败
    agent.MockTool("external_api", func(args map[string]interface{}) interface{} {
        panic("connection timeout")
    })
    
    // 验证错误恢复
    result, err := agent.CallTool("external_api", map[string]interface{}{
        "endpoint": "/data",
    })
    
    if err == nil {
        t.Fatal("expected error")
    }
    if result != nil {
        t.Fatal("expected nil result")
    }
}
```

---

## 三、自测题

1. **为什么Agent需要特殊测试？**
   - 非确定性输出 + 外部依赖 + 工具调用

2. **Mock的作用是什么？**
   - 隔离外部依赖，稳定测试结果

