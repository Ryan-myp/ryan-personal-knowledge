# 分布式事务深度解析

> 深入分布式事务：2PC、TCC、Saga、本地消息表、Seata。
> 源码级分析，包含生产环境实现。
> 适用对象：分布式系统工程师、架构师

---

## 1. 分布式事务类型

### 1.1 事务模型对比

```
┌─────────────────────────────────────────────────────────────┐
│                  分布式事务模型对比                          │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  模型              │ 一致性  │ 可用性  │ 复杂度  │ 适用场景  │
├─────────────────────────────────────────────────────────────┤
│  2PC              │ 强      │ 低      │ 中      │ 数据库    │
│  TCC              │ 强      │ 高      │ 高      │ 金融      │
│  Saga            │ 最终    │ 高      │ 中      │ 微服务    │
│  本地消息表        │ 最终    │ 高      │ 中      │ 通用      │
│  Maxwell/CDC      │ 最终    │ 高      │ 低      │ 数据同步  │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. 两阶段提交（2PC）

### 2.1 协议流程

```
两阶段提交协议：

Prepare 阶段：
1. 事务协调者向所有参与者发送 Prepare 消息
2. 参与者执行事务，但不提交
3. 参与者回复 OK 或 Abort

Commit 阶段：
1. 协调者收到所有 OK → 发送 Commit
2. 协调者收到任一 Abort → 发送 Abort
3. 参与者执行 Commit 或 Rollback
```

### 2.2 Go 实现

```go
// two_phase_commit.go

package transaction

import (
    "context"
    "sync"
)

type Participant interface {
    Prepare(ctx context.Context) error
    Commit(ctx context.Context) error
    Abort(ctx context.Context) error
}

type Coordinator struct {
    participants []Participant
    mu           sync.Mutex
}

func (c *Coordinator) Execute(ctx context.Context) error {
    // Phase 1: Prepare
    var wg sync.WaitGroup
    errors := make(chan error, len(c.participants))
    
    for _, p := range c.participants {
        wg.Add(1)
        go func(participant Participant) {
            defer wg.Done()
            if err := participant.Prepare(ctx); err != nil {
                errors <- err
            }
        }(p)
    }
    
    wg.Wait()
    close(errors)
    
    // 检查是否有失败
    for err := range errors {
        if err != nil {
            // Phase 2: Abort
            c.abort(ctx)
            return err
        }
    }
    
    // Phase 2: Commit
    return c.commit(ctx)
}

func (c *Coordinator) commit(ctx context.Context) error {
    for _, p := range c.participants {
        if err := p.Commit(ctx); err != nil {
            return err
        }
    }
    return nil
}

func (c *Coordinator) abort(ctx context.Context) error {
    for _, p := range c.participants {
        p.Abort(ctx)
    }
    return nil
}
```

---

## 3. TCC 事务

### 3.1 三阶段

```
TCC 三阶段：

Try:
├── 预留资源
└── 业务检查

Confirm:
├── 使用预留资源
└── 提交事务

Cancel:
├── 释放预留资源
└── 回滚事务
```

### 3.2 Go 实现

```go
// tcc.go

package transaction

type TCC interface {
    Try(ctx context.Context) error
    Confirm(ctx context.Context) error
    Cancel(ctx context.Context) error
}

type TCCCoordinator struct {
    tccs []TCC
}

func (c *TCCCoordinator) Execute(ctx context.Context) error {
    // Try 阶段
    for _, tcc := range c.tccs {
        if err := tcc.Try(ctx); err != nil {
            // 取消已执行的
            c.cancel(ctx)
            return err
        }
    }
    
    // Confirm 阶段
    for _, tcc := range c.tccs {
        if err := tcc.Confirm(ctx); err != nil {
            // 补偿
            c.compensate(ctx)
            return err
        }
    }
    
    return nil
}

func (c *TCCCoordinator) cancel(ctx context.Context) {
    // 从后往前取消
    for i := len(c.tccs) - 1; i >= 0; i-- {
        c.tccs[i].Cancel(ctx)
    }
}
```

---

## 4. Saga 事务

### 4.1 编排模式

```
Saga 编排模式：

业务流程：
  Step1 → Step2 → Step3 → Step4

补偿流程：
  Step1⁻¹ ← Step2⁻¹ ← Step3⁻¹ ← Step4⁻¹

特点：
├── 长期事务
├── 无锁
└── 最终一致性
```

### 4.2 Go 实现

```go
// saga.go

package transaction

type Step struct {
    Name       string
    Action     func(context.Context) error
    Compensation func(context.Context) error
}

type Saga struct {
    steps []Step
}

func (s *Saga) Execute(ctx context.Context) error {
    executed := make([]int, 0)
    
    // 正向执行
    for i, step := range s.steps {
        if err := step.Action(ctx); err != nil {
            // 回滚已执行的步骤
            for j := len(executed) - 1; j >= 0; j-- {
                s.steps[executed[j]].Compensation(ctx)
            }
            return err
        }
        executed = append(executed, i)
    }
    
    return nil
}
```

---

## 5. 本地消息表

### 5.1 实现原理

```
本地消息表模式：

1. 业务表和消息表在同一事务
2. 定时任务扫描未发送消息
3. 发送消息到 MQ
4. 更新消息状态

优点：
├── 简单可靠
├── 不依赖中间件
└── 可恢复

缺点：
├── 轮询开销
└── 消息表增长
```

### 5.2 Go 实现

```go
// local_message_table.go

package transaction

import (
    "context"
    "time"
)

type Message struct {
    ID        int64
    Topic     string
    Payload   string
    Status    int // 0: pending, 1: sent, 2: failed
    RetryCount int
}

type LocalMessageTable struct {
    db     *Database
    mq     *MessageQueue
}

func (m *LocalMessageTable) ExecuteInTransaction(ctx context.Context, businessData, message string) error {
    // 1. 插入业务数据
    // 2. 插入消息记录
    // 两个操作在同一事务
    return m.db.Transaction(func(tx *Transaction) error {
        tx.InsertBusiness(businessData)
        tx.InsertMessage(message)
        return nil
    })
}

func (m *LocalMessageTable) StartSender() {
    ticker := time.NewTicker(1 * time.Second)
    for range ticker.C {
        m.sendPendingMessages()
    }
}

func (m *LocalMessageTable) sendPendingMessages() {
    messages := m.db.FindPendingMessages()
    for _, msg := range messages {
        if err := m.mq.Send(msg.Topic, msg.Payload); err != nil {
            msg.RetryCount++
            m.db.UpdateMessageStatus(msg.ID, msg.RetryCount)
        } else {
            m.db.MarkMessageSent(msg.ID)
        }
    }
}
```

---

## 6. Seata 框架

### 6.1 架构

```
Seata 架构：

┌─────────────────────────────────────────────────────────────┐
│                    TC (Transaction Coordinator)             │
│  ├── 事务协调者                                              │
│  └── 全局锁管理                                             │
├─────────────────────────────────────────────────────────────┤
│                    TM (Transaction Manager)                 │
│  ├── 开启全局事务                                            │
│  └── 提交/回滚全局事务                                      │
├─────────────────────────────────────────────────────────────┤
│                    RM (Resource Manager)                    │
│  ├── 分支事务管理                                            │
│  └── 注册分支事务                                            │
└─────────────────────────────────────────────────────────────┘
```

---

## 7. 总结

### 7.1 核心原理回顾

| 模型 | 核心机制 | 适用场景 |
|------|----------|----------|
| 2PC | 两阶段提交 | 强一致性 |
| TCC | 预留-确认-取消 | 金融场景 |
| Saga | 编排/协同 | 微服务 |
| 本地消息表 | 事务消息 | 通用场景 |

### 7.2 最佳实践

- [ ] 根据场景选择事务模型
- [ ] 考虑可用性和一致性权衡
- [ ] 实现补偿机制
- [ ] 监控事务状态
- [ ] 定期压力测试

---

*最后更新：2026-08-11*
*作者：Ryan*
