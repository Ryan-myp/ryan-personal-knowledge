# 分布式事务深度解析

> 深入分布式事务核心：CAP理论、2PC/3PC、TCC、Saga、本地消息表。
> 包含Go实现和实战案例。
> 适用对象：分布式系统工程师、架构师

---

## 1. CAP 定理深度解析

### 1.1 定理证明

```
定理：分布式系统最多同时满足以下三个特性中的两个：
- C (Consistency)：所有节点同一时刻看到相同数据
- A (Availability)：每个请求都能获得非错误响应
- P (Partition Tolerance)：系统继续运作尽管有网络分区

证明：
假设系统同时满足 C、A、P
1. 分区发生时(P成立)，节点N1和N2无法通信
2. 写请求到达N1，读请求到达N2
3. 若C成立，N1和N2必须看到相同数据
4. 但分区导致N1的写无法同步到N2
5. 若保证A，N2必须响应，但响应可能是旧数据
6. 矛盾！所以C、A、P不能同时满足
```

### 1.2 系统分类

| 系统类型 | 特性组合 | 典型场景 | 代表系统 |
|----------|----------|----------|----------|
| CP系统 | C + P | 金融交易、注册中心 | ZooKeeper、Consul |
| AP系统 | A + P | 社交网络、缓存 | Dynamo、Cassandra |
| CA系统 | C + A | 单机数据库 | MySQL、PostgreSQL |

---

## 2. 两阶段提交 (2PC)

### 2.1 协议流程

```
协调者                    参与者1      参与者2
   │                       │           │
   │─── PREPARE ──────────►│           │
   │                       │           │
   │◄── VOTE COMMIT ───────┤           │
   │                       │           │
   │─── PREPARE ──────────────────────►│
   │                       │           │
   │◄──────────────── VOTE COMMIT ─────┤
   │                       │           │
   │                       │           │
   │─── COMMIT ───────────►│           │
   │◄── ACK ───────────────┤           │
   │                       │           │
   │─── COMMIT ───────────────────────►│
   │◄──────────────── ACK ─────────────┤
```

### 2.2 Go 实现

```go
// 2pc/coordinator.go

type Coordinator struct {
    participants []Participant
    txID         string
    state        TxState
}

type TxState int

const (
    Prepared TxState = iota
    Committed
    Aborted
)

func (c *Coordinator) Begin() error {
    c.state = Prepared
    // 1. 准备阶段
    for _, p := range c.participants {
        if err := p.Prepare(c.txID); err != nil {
            c.Abort()
            return err
        }
    }
    return nil
}

func (c *Coordinator) Commit() error {
    // 2. 提交阶段
    for _, p := range c.participants {
        if err := p.Commit(c.txID); err != nil {
            // 补偿
            c.rollback()
            return err
        }
    }
    c.state = Committed
    return nil
}

func (c *Coordinator) Abort() {
    for _, p := range c.participants {
        p.Rollback(c.txID)
    }
    c.state = Aborted
}
```

### 2.3 优缺点

| 优点 | 缺点 |
|------|------|
| 强一致性 | 阻塞型协议 |
| 实现简单 | 单点故障 |
| 原子性好 | 性能较差 |

---

## 3. TCC 事务

### 3.1 三阶段语义

```
Try: 完成所有业务检查（一致性）
     预留业务资源
         
Confirm: 真正执行业务
         不使用本地锁
         
Cancel: 释放预留资源
        补偿已完成的业务
```

### 3.2 Go 实现

```go
// tcc/interface.go

type TCC interface {
    Try(ctx context.Context, args interface{}) error
    Confirm(ctx context.Context, args interface{}) error
    Cancel(ctx context.Context, args interface{}) error
}

// tcc/transaction.go

type Transaction struct {
    tcc      TCC
    txID     string
    phase    Phase
}

type Phase int

const (
    Try Phase = iota
    Confirm
    Cancel
)

func (t *Transaction) Execute(ctx context.Context) error {
    // Try阶段
    if err := t.tcc.Try(ctx, nil); err != nil {
        return err
    }
    t.phase = Try
    
    // 执行业务逻辑
    if err := t.businessLogic(ctx); err != nil {
        // 取消
        t.tcc.Cancel(ctx, nil)
        return err
    }
    
    // Confirm阶段
    return t.tcc.Confirm(ctx, nil)
}
```

---

## 4. Saga 模式

### 4.1 长事务分解

```
Saga1 ──► Saga2 ──► Saga3 ──► Saga4
  │         │         │         │
  ▼         ▼         ▼         ▼
 commit  commit    commit    commit
  │         │         │         │
  ▼         ▼         ▼         ▼
 compens  compens   compens   compens
```

### 4.2 Go 实现

```go
// saga/saga.go

type Saga struct {
    steps []Step
}

type Step struct {
    name       string
    action     func(ctx context.Context) error
    compensate func(ctx context.Context) error
}

func (s *Saga) Execute(ctx context.Context) error {
    executed := make([]int, 0)
    
    // 正向执行
    for i, step := range s.steps {
        if err := step.action(ctx); err != nil {
            // 反向补偿
            for j := len(executed) - 1; j >= 0; j-- {
                s.steps[executed[j]].compensate(ctx)
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

### 5.1 原理

```
业务表     消息表     MQ         消费者
  │          │         │            │
  │──写入───►│         │            │
  │          │         │            │
  │──事务提交──┤         │            │
  │          │──扫描──►│──发送───►│──处理──►
  │          │         │            │
  │          │◄─确认───┤            │
```

### 5.2 Go 实现

```go
// local_message/message_table.go

type MessageTable struct {
    db *sql.DB
}

func (m *MessageTable) AddMessage(txID string, topic string, payload []byte) error {
    return m.db.Transaction(func(tx *sql.Tx) error {
        // 1. 写入业务表
        _, err := tx.Exec("INSERT INTO orders (...) VALUES (...)", txID)
        if err != nil {
            return err
        }
        // 2. 写入消息表
        _, err = tx.Exec("INSERT INTO messages (tx_id, topic, payload, status) VALUES (?, ?, ?, 'pending')", 
            txID, topic, payload)
        return err
    })
}

func (m *MessageTable) ScanAndSend() error {
    // 扫描 pending 消息
    rows, err := m.db.Query("SELECT id, topic, payload FROM messages WHERE status = 'pending'")
    if err != nil {
        return err
    }
    
    for rows.Next() {
        var id, topic, payload string
        rows.Scan(&id, &topic, &payload)
        
        // 发送到MQ
        if err := m.sendToMQ(topic, payload); err != nil {
            continue
        }
        
        // 更新状态
        m.db.Exec("UPDATE messages SET status = 'sent' WHERE id = ?", id)
    }
    return nil
}
```

---

## 6. 实战案例

### 6.1 电商订单事务

```
下单 → 扣库存 → 支付 → 发货

方案：Saga + TCC
- Try: 预留库存、冻结金额
- Confirm: 扣减库存、扣款
- Cancel: 释放库存、解冻金额
```

### 6.2 性能对比

| 方案 | 吞吐量 | 延迟 | 一致性 |
|------|--------|------|--------|
| 2PC | 低 | 高 | 强 |
| TCC | 中 | 中 | 最终 |
| Saga | 高 | 低 | 最终 |
| 本地消息表 | 高 | 低 | 最终 |

---

## 7. 总结

### 7.1 方案选择

| 场景 | 推荐方案 |
|------|----------|
| 强一致性要求 | 2PC |
| 高性能要求 | Saga |
| 业务复杂 | TCC |
| 异步解耦 | 本地消息表 |

---

*最后更新：2026-08-11*
*作者：Ryan*
