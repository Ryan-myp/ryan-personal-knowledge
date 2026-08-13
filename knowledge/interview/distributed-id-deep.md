# 分布式ID生成 - 资深专家深度实现

## 一、常见方案对比

| 方案 | 性能 | 可用性 | 复杂度 | 适用场景 |
|------|------|--------|--------|----------|
| UUID | 高 | 高 | 低 | 全局唯一 |
| Snowflake | 高 | 中 | 中 | 分布式系统 |
| Redis INCR | 高 | 中 | 低 | 简单场景 |
| DB Auto Increment | 低 | 高 | 低 | 低并发 |
| ULID | 中 | 高 | 低 | 时序友好 |

## 二、Snowflake算法

```go
type Snowflake struct {
    mu          sync.Mutex
    lastTS      int64
    sequence    int64
    workerID    int64
    workerBits  uint8
    stepBits    uint8
}

func (s *Snowflake) NextID() int64 {
    s.mu.Lock()
    defer s.mu.Unlock()
    
    ts := time.Now().UnixMilli()
    if ts < s.lastTS {
        panic("clock moved backwards")
    }
    
    if ts == s.lastTS {
        s.sequence = (s.sequence + 1) & mask
        if s.sequence == 0 {
            ts = s.waitNextMillis()
        }
    } else {
        s.sequence = 0
    }
    
    s.lastTS = ts
    return ((ts - epoch) << timestampShift) | 
           (s.workerID << workerShift) | 
           s.sequence
}
```

## 三、生产级实现

```go
// 支持时钟回拨
func (s *Snowflake) waitNextMillis() int64 {
    ts := time.Now().UnixMilli()
    for ts <= s.lastTS {
        ts = time.Now().UnixMilli()
    }
    return ts
}

// 支持节点IP作为workerID
func getWorkerID() int64 {
    addrs, _ := net.InterfaceAddrs()
    for _, addr := range addrs {
        if ipnet, ok := addr.(*net.IPNet); ok && !ipnet.IP.IsLoopback() {
            return int64(crc32.ChecksumIEEE(ipnet.IP.To4())) % 1024
        }
    }
    return 0
}
```

## 四、面试高频题

### Q1: Snowflake时钟回拨如何处理？

```
A: 等待时钟追上，或提高sequence速率。
```

### Q2: UUID和Snowflake有什么区别？

```
A: UUID全局唯一但无序，Snowflake有序且性能更高。
```

## 五、自测题

1. 实现一个带时钟回拨处理的Snowflake
2. 如何设计一个ID生成服务？

---

## 参考文档

- [Snowflake论文](https://github.com/twitter/snowflake)
