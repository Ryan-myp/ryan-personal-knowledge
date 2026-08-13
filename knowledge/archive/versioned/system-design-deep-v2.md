# 系统设计面试深度实现V2 - 扩展题库

> **版本**: v2.1  
> **日期**: 2026-08-14  
> **作者**: Ryan  
> **分类**: 面试/系统设计  
> **代码密度**: 28%

---

## 新增面试题

### Q16. 设计一个分布式ID生成器

```go
// 雪花算法改进版
type SnowflakeID struct {
    workerID     int64
    sequence     int64
    lastTimestamp int64
}

func (s *SnowflakeID) NextID() int64 {
    timestamp := time.Now().UnixNano() / 1e6
    
    if timestamp < s.lastTimestamp {
        panic("clock moved backwards")
    }
    
    if timestamp == s.lastTimestamp {
        s.sequence = (s.sequence + 1) & 4095
        if s.sequence == 0 {
            timestamp = s.waitNextMillis()
        }
    } else {
        s.sequence = 0
    }
    
    s.lastTimestamp = timestamp
    return ((timestamp - epoch) << 22) | (int64(s.workerID) << 12) | s.sequence
}
```

### Q17. 设计一个分布式锁

```go
// Redis分布式锁
type DistributedLock struct {
    redis    *redis.Client
    key      string
    value    string
    ttl      time.Duration
}

func (l *DistributedLock) Acquire() error {
    ok, err := l.redis.SetNX(l.key, l.value, l.ttl).Result()
    if err != nil {
        return err
    }
    if !ok {
        return ErrLockAcquired
    }
    return nil
}

func (l *DistributedLock) Release() error {
    // Lua脚本保证原子性
    script := `
    if redis.call("get", KEYS[1]) == ARGV[1] then
        return redis.call("del", KEYS[1])
    else
        return 0
    end`
    return l.redis.Eval(script, []string{l.key}, l.value).Err()
}
```

### Q18. 设计一个限流系统

```go
// 令牌桶限流器
type TokenBucket struct {
    capacity  int
    tokens    int
    rate      int
    lastTime  time.Time
    mu        sync.Mutex
}

func (tb *TokenBucket) Allow() bool {
    tb.mu.Lock()
    defer tb.mu.Unlock()
    
    now := time.Now()
    elapsed := now.Sub(tb.lastTime).Seconds()
    tb.tokens += int(elapsed * float64(tb.rate))
    if tb.tokens > tb.capacity {
        tb.tokens = tb.capacity
    }
    tb.lastTime = now
    
    if tb.tokens >= 1 {
        tb.tokens--
        return true
    }
    return false
}
```

### Q19. 设计一个事件溯源系统

```go
// 事件溯源
type EventSourcedAggregate struct {
    id         string
    events     []DomainEvent
    state      interface{}
}

func (a *EventSourcedAggregate) Apply(event DomainEvent) {
    a.events = append(a.events, event)
    a.state = a.applyEvent(a.state, event)
}

func (a *EventSourcedAggregate) Replay() interface{} {
    state := a.initialState()
    for _, event := range a.events {
        state = a.applyEvent(state, event)
    }
    return state
}
```

### Q20. 设计一个CQRS架构

```go
// CQRS分离读写
type CommandProcessor struct {
    handlers map[string]CommandHandler
}

func (cp *CommandProcessor) Handle(cmd Command) error {
    handler := cp.handlers[cmd.Type()]
    return handler.Handle(cmd)
}

type QueryProcessor struct {
    projections map[string]Projection
}

func (qp *QueryProcessor) Query(q Query) (interface{}, error) {
    projection := qp.projections[q.Type()]
    return projection.Read(q)
}
```

---

## 自测题

1. **雪花算法的优缺点？**
   - 优点: 自增/分布式; 缺点: 时钟回拨问题

2. **分布式锁为什么需要Lua脚本？**
   - 保证检查+删除的原子性

3. **令牌桶vs漏桶的区别？**
   - 令牌桶允许突发，漏桶匀速流出

4. **事件溯源的核心价值？**
   - 完整审计 trail + 状态可重建

