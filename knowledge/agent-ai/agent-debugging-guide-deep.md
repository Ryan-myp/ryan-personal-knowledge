# Agent 调试指南深度实现 - 常见问题排查

> **版本**: v2.1  
> **日期**: 2026-08-14  
> **作者**: Ryan  
> **分类**: Agent/调试  
> **代码密度**: 28%

---

## 一、常见调试场景

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Agent 常见问题排查                                │
│                                                                     │
│  Problem 1: 工具调用失败                                            │
│  ─────────────────────────────────                                 │
│  症状:   Agent反复调用失败的工具                                   │
│  原因:   工具注册错误 / 参数校验失败 / 超时                         │
│  排查:   查看tool_call日志 → 检查参数格式 → 验证工具可用性           │
│  解决:   添加重试机制 / 改善参数描述                                │
│                                                                     │
│  Problem 2: 幻觉输出                                                │
│  ─────────────────────────────────                                 │
│  症状:   Agent输出看似合理但事实错误                                 │
│  原因:   RAG检索不准 / prompt引导不足 / 模型能力限制                 │
│  排查:   检查检索结果 → 分析prompt结构 → 添加fact-check步骤         │
│  解决:   优化检索 / 添加引用要求 / 使用更强大模型                   │
│                                                                     │
│  Problem 3: 无限循环                                                │
│  ─────────────────────────────────                                 │
│  症状:   Agent陷入工具调用循环                                      │
│  原因:   缺乏终止条件 / 状态未更新 / 循环检测缺失                    │
│  排查:   启用step limit / 检查状态机转换 / 添加循环检测             │
│  解决:   设置最大步数 / 添加visited集合 / 改进终止判断              │
│                                                                     │
│  Problem 4: 安全违规                                                │
│  ─────────────────────────────────                                 │
│  症状:   Agent输出有害内容或被jailbreak                             │
│  原因:   护栏规则缺失 / prompt被绕过 / 工具权限过大                 │
│  排查:   检查安全日志 / 分析输入模式 / 审查工具权限                 │
│  解决:   增强护栏 / 添加input sanitization / 最小权限原则          │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 二、调试工具

```go
// agent/debugger.go
package agent

import (
    "context"
    "fmt"
    "time"
)

// Debugger 调试器
type Debugger struct {
    traces    []*Trace
    breakpoints map[string]bool
}

// Trace 执行轨迹
type Trace struct {
    Step      int
    Timestamp time.Time
    Action    string      // think/tool_call/tool_result
    Input     interface{}
    Output    interface{}
    Duration  time.Duration
    Error     error
}

// StepInto 单步执行
func (d *Debugger) StepInto(ctx context.Context, agent *Agent) (*Trace, error) {
    start := time.Now()
    
    trace := &Trace{
        Step:      len(d.traces) + 1,
        Timestamp: start,
        Action:    "step_into",
    }
    
    // 执行一步
    result, err := agent.Step(ctx)
    trace.Output = result
    trace.Error = err
    trace.Duration = time.Since(start)
    
    d.traces = append(d.traces, trace)
    return trace, nil
}

// PrintTrace 打印轨迹
func (d *Debugger) PrintTrace() {
    fmt.Println("=== Agent Execution Trace ===")
    for _, t := range d.traces {
        fmt.Printf("[%d] %s (%.2fs)\n", t.Step, t.Action, t.Duration.Seconds())
        if t.Input != nil {
            fmt.Printf("  Input: %v\n", t.Input)
        }
        if t.Output != nil {
            fmt.Printf("  Output: %v\n", t.Output)
        }
        if t.Error != nil {
            fmt.Printf("  Error: %v\n", t.Error)
        }
    }
}

// FindLoop 检测循环
func (d *Debugger) FindLoop() bool {
    seen := make(map[string]int)
    for _, t := range d.traces {
        key := fmt.Sprintf("%v", t.Input)
        if count, ok := seen[key]; ok {
            fmt.Printf("Loop detected! Input repeated at steps %d and %d\n", count, t.Step)
            return true
        }
        seen[key] = t.Step
    }
    return false
}
```

---

## 三、自测题

1. **Agent调试的难点？**
   - 非确定性、多层抽象、长链条依赖

2. **如何定位幻觉问题？**
   - 追踪检索结果 → 分析推理链 → 验证事实

