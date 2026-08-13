# 分布式ID生成器 - 资深专家深度实现

## 一、方案设计

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      分布式ID生成器架构                                    │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   方案对比:                                                              │
│   ┌──────────┬──────────┬──────────┬──────────┬──────────┐            │
│   │  方案    │  唯一性  │  单调性  │  安全性  │  性能    │            │
│   ├──────────┼──────────┼──────────┼──────────┼──────────┤            │
│   │ UUID     │ ✅       │ ❌       │ ❌       │ ⭐⭐⭐   │            │
│   │ 自增ID   │ ✅       │ ✅       │ ❌       │ ⭐⭐⭐   │            │
│   │ Snowflake│ ✅       │ ✅       │ ⚠️      │ ⭐⭐     │            │
│   │ 号段模式 │ ✅       │ ✅       │ ✅       │ ⭐⭐     │            │
│   │ 短链接   │ ✅       │ ⚠️       │ ✅       │ ⭐⭐⭐   │            │
│   └──────────┴──────────┴──────────┴──────────┴──────────┘            │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

## 二、Snowflake算法

```go
package idgen

import (
    "fmt"
    "sync"
    "time"
)

type Snowflake struct {
    mu            sync.Mutex
    workerID      int64
    datacenterID  int64
    sequence      int64
    lastTimestamp int64
}

const (
    workerBits     = 10
    datacenterBits = 5
    sequenceBits   = 12
    
    workerMask     = int64(-1) ^ (int64(-1) << workerBits)
    datacenterMask = int64(-1) ^ (int64(-1) << datacenterBits)
    sequenceMask   = int64(-1) ^ (int64(-1) << sequenceBits)
    
    workerShift    = sequenceBits
    datacenterShift = sequenceBits + workerBits
    timestampShift = sequenceBits + workerBits + datacenterBits
    
    epoch int64 = 1609459200000 // 2021-01-01
)

func NewSnowflake(workerID, datacenterID int64) *Snowflake {
    return &Snowflake{
        workerID:     workerID & workerMask,
        datacenterID: datacenterID & datacenterMask,
        sequence:     0,
        lastTimestamp: -1,
    }
}

func (s *Snowflake) NextID() (int64, error) {
    s.mu.Lock()
    defer s.mu.Unlock()
    
    timestamp := time.Now().UnixMilli()
    
    if timestamp < s.lastTimestamp {
        return 0, fmt.Errorf("clock moved backwards")
    }
    
    if timestamp == s.lastTimestamp {
        s.sequence = (s.sequence + 1) & sequenceMask
        if s.sequence == 0 {
            timestamp = s.waitNextMillis(timestamp)
        }
    } else {
        s.sequence = 0
    }
    
    s.lastTimestamp = timestamp
    
    return ((timestamp - epoch) << timestampShift) |
           (s.datacenterID << datacenterShift) |
           (s.workerID << workerShift) |
           s.sequence, nil
}

func (s *Snowflake) waitNextMillis(timestamp int64) int64 {
    for timestamp <= s.lastTimestamp {
        timestamp = time.Now().UnixMilli()
    }
    return timestamp
}
```

## 三、号段模式

```go
type SegmentIDGen struct {
    mu          sync.Mutex
    base        int64
    end         int64
    step        int64
    db          *Database
}

func (s *SegmentIDGen) NextID() (int64, error) {
    s.mu.Lock()
    defer s.mu.Unlock()
    
    if s.base >= s.end {
        if err := s.refill(); err != nil {
            return 0, err
        }
    }
    
    id := s.base
    s.base += 1
    return id, nil
}

func (s *SegmentIDGen) refill() error {
    newBase, newEnd, err := s.db.AllocateSegment(s.step)
    if err != nil {
        return err
    }
    s.base = newBase
    s.end = newEnd
    return nil
}
```

## 四、面试高频题

### Q1: Snowflake的时间戳溢出问题？

```
A: 
• 41位时间戳支持约69年
• 通过设置epoch可以延长使用时间
• 时钟回退会失败，需要处理
```

### Q2: 号段模式和Snowflake各有什么优缺点？

```
A:
• Snowflake: 本地生成，无网络开销，依赖时钟
• 号段模式: 不依赖时钟，需要数据库，可预测
```

## 五、自测题

1. Snowflake的ID结构是什么？
2. 如何处理时钟回退问题？
3. 号段模式的优缺点是什么？

---

## 参考文档

- [Snowflake论文](https://twitter.github.io/snowflake/)
- [美团Leaf](https://github.com/Meituan-Dianping/Leaf)
