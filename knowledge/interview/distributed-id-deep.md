# 系统设计：分布式ID生成器 - 资深专家深度实现

## 一、Snowflake算法

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     Snowflake ID结构 (64位)                              │
├─────────────────────────────────────────────────────────────────────────┤
│  符号  │            时间戳            │ 机器ID │     序列号      │
│   1    │              41             │   10  │       12        │
│        │                             │       │                 │
│  负数  │         41位 = 69年         │ 1024台│    4096/毫秒    │
└─────────────────────────────────────────────────────────────────────────┘
```

## 二、Go实现

```go
package snowflake

import (
    "sync"
    "time"
)

const (
    epoch       = 1420041600000 // 2015-01-01
    machineBits = 10
    stepBits    = 12
    
    maxMachineId = -1 ^ (-1 << machineBits) // 1024
    maxStep      = -1 ^ (-1 << stepBits)    // 4096
)

type Snowflake struct {
    mu         sync.Mutex
    machineID  int64
    lastTime   int64
    step       int64
}

func NewSnowflake(machineID int64) *Snowflake {
    if machineID < 0 || machineID > maxMachineId {
        panic("machineID out of range")
    }
    return &Snowflake{
        machineID: machineID,
    }
}

func (s *Snowflake) NextID() int64 {
    s.mu.Lock()
    defer s.mu.Unlock()
    
    now := time.Now().UnixMilli()
    
    // 时钟回拨检测
    if now < s.lastTime {
        panic("clock moved backwards")
    }
    
    if now == s.lastTime {
        s.step++
        if s.step > maxStep {
            // 等待下一毫秒
            for now <= s.lastTime {
                now = time.Now().UnixMilli()
            }
        }
    } else {
        s.step = 0
    }
    
    s.lastTime = now
    
    // 生成ID
    id := (now-epoch)<<22 | (s.machineID << 12) | s.step
    return id
}
```

## 三、面试高频题

### Q1: Snowflake的问题是什么？

```
A:
1. 时钟回拨问题
2. 机器ID分配
3. 单点故障
```

### Q2: 如何解决时钟回拨？

```
A:
1. 等待时钟同步
2. 记录回拨时间
3. 使用NTP同步
```

## 四、自测题

1. 解释Snowflake算法原理
2. 如何实现分布式ID生成器？
3. 有哪些其他方案？

---

## 参考文档

- [Twitter Snowflake](https://github.com/twitter/snowflake)
- [Leaf项目](https://github.com/Meituan-Dianping/Leaf)
