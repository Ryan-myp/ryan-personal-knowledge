# Agent 任务交接深度实现 - 上下文传递与恢复

> **版本**: v2.1  
> **日期**: 2026-08-14  
> **作者**: Ryan  
> **分类**: Agent/任务交接  
> **代码密度**: 28%

---

## 一、交接模式

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Agent 任务交接模式                                │
│                                                                     │
│  Pattern 1: Hot Handoff (热交接)                                     │
│  ─────────────────────────────────                                 │
│  • 实时传递完整上下文                                                │
│  • 目标Agent立即接管                                                │
│  • 延迟: <100ms                                                     │
│  • 适用: 同集群内Agent                                               │
│                                                                     │
│  Pattern 2: Warm Handoff (温交接)                                    │
│  ─────────────────────────────────                                 │
│  • 保存中间状态                                                      │
│  • 目标Agent加载后恢复                                               │
│  • 延迟: 1-5s                                                       │
│  • 适用: 跨集群/跨服务                                               │
│                                                                     │
│  Pattern 3: Cold Handoff (冷交接)                                    │
│  ─────────────────────────────────                                 │
│  • 序列化完整状态到持久存储                                          │
│  • 目标Agent从存储恢复                                               │
│  • 延迟: 5-30s                                                      │
│  • 适用: 故障转移/重启                                               │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 二、上下文序列化

```go
// agent/handoff.go
package agent

import (
    "encoding/json"
)

// HandoffContext 交接上下文
type HandoffContext struct {
    // 任务信息
    TaskID      string            `json:"task_id"`
    Goal        string            `json:"goal"`
    Status      string            `json:"status"`
    
    // 对话历史
    Messages    []Message         `json:"messages"`
    
    // 记忆快照
    Memory      MemorySnapshot    `json:"memory"`
    
    // 工具状态
    ToolState   map[string][]byte `json:"tool_state"`
    
    // 时间戳
    CreatedAt   int64             `json:"created_at"`
    ExpiresAt   int64             `json:"expires_at"`
}

// Serialize 序列化上下文
func (h *HandoffContext) Serialize() ([]byte, error) {
    return json.Marshal(h)
}

// Deserialize 反序列化上下文
func Deserialize(data []byte) (*HandoffContext, error) {
    h := &HandoffContext{}
    err := json.Unmarshal(data, h)
    return h, err
}

// HandoffManager 交接管理器
type HandoffManager struct {
    store     StateStore
    serializers map[string]Serializer
}

// PerformHandoff 执行交接
func (m *HandoffManager) PerformHandoff(ctx Context, targetAgent string) error {
    // 1. 序列化当前状态
    snapshot := ctx.ExportState()
    data, err := json.Marshal(snapshot)
    if err != nil {
        return err
    }
    
    // 2. 存储交接上下文
    handoff := &HandoffContext{
        TaskID:    ctx.TaskID(),
        Goal:      ctx.Goal(),
        Messages:  ctx.Messages(),
        Memory:    ctx.ExportMemory(),
        CreatedAt: time.Now().Unix(),
        ExpiresAt: time.Now().Add(5 * time.Minute).Unix(),
    }
    
    // 3. 持久化
    key := fmt.Sprintf("handoff:%s:%s", targetAgent, handoff.TaskID)
    return m.store.Set(key, handoff, 10*time.Minute)
}

// ResumeHandoff 恢复交接
func (m *HandoffManager) ResumeHandoff(ctx Context, taskID string) error {
    key := fmt.Sprintf("handoff:%s:%s", ctx.AgentID(), taskID)
    data, err := m.store.Get(key)
    if err != nil {
        return err
    }
    
    // 反序列化并恢复状态
    handoff, err := Deserialize(data)
    if err != nil {
        return err
    }
    
    return ctx.ImportState(handoff)
}
```

---

## 三、自测题

1. **为什么需要三种交接模式？**
   - 不同场景对延迟和可靠性的要求不同

2. **交接时如何保证一致性？**
   - 序列化快照 + 原子存储 + TTL过期

