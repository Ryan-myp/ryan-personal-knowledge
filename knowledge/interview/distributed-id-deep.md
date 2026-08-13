# 分布式ID生成器 --- 资深专家深度实现

## 概述

分布式ID生成是分布式系统的核心组件。本文深入剖析雪花算法、UUID、数据库等多种方案。

## 一、ID生成方案对比

```
┌─────────────────────────────────────────────────────────┐
│                  ID生成方案对比                          │
├──────────────┬──────────┬──────────┬────────────────────┤
│   方案       │ 性能     │ 可用性   │ 适用场景             │
├──────────────┼──────────┼──────────┼────────────────────┤
│ UUID         │ 高       │ 高       │ 短ID、全局唯一       │
│ 雪花算法     │ 极高     │ 高       │ 长整型ID、有序       │
│ 数据库序列   │ 中       │ 中       │ 需要递增、事务支持   │
│ Redis incr   │ 高       │ 中       │ 简单场景、分布式     │
│ 美团Leaf     │ 极高     │ 极高     │ 生产级、高可用       │
└──────────────┴──────────┴──────────┴────────────────────┘
```

## 二、雪花算法

### 2.1 位结构

```
┌─────────────────────────────────────────────────────────┐
│                  雪花算法位结构                          │
├─────────────────────────────────────────────────────────┤
│  0 | 41位时间戳      | 5位数据中心 | 5位机器ID | 12位序列 │
│  ─┼───────────────┼───────────┼───────────┼─────────── │
│    符号位(0为正)   毫秒级时间  数据中心编号  机器编号    序列号│
│                  41位 = 2^41 ≈ 69年                              │
└─────────────────────────────────────────────────────────┘
```

### 2.2 实现代码

```go
package snowflake

import (
    "sync"
    "time"
)

const (
    epoch        = 1577836800000  // 2020-01-01 00:00:00
    workerBits   = uint8(5)
    datacenterBits = uint8(5)
    sequenceBits = uint8(12)
    
    workerMax    = int64(-1) ^ (int64(-1) << workerBits)      // 31
    datacenterMax = int64(-1) ^ (int64(-1) << datacenterBits)  // 31
    sequenceMax  = int64(-1) ^ (int64(-1) << sequenceBits)     // 4095
    
    workerShift    = sequenceBits
    datacenterShift = sequenceBits + workerBits
    timestampShift = sequenceBits + workerBits + datacenterBits
)

type Snowflake struct {
    mu           sync.Mutex
    workerID     int64
    datacenterID int64
    sequence     int64
    lastTimestamp int64
}

func NewSnowflake(workerID, datacenterID int64) *Snowflake {
    if workerID > workerMax {
        panic("worker ID too large")
    }
    if datacenterID > datacenterMax {
        panic("datacenter ID too large")
    }
    return &Snowflake{
        workerID:     workerID,
        datacenterID: datacenterID,
        sequence:     0,
        lastTimestamp: -1,
    }
}

func (s *Snowflake) Generate() int64 {
    s.mu.Lock()
    defer s.mu.Unlock()
    
    timestamp := time.Now().UnixMilli()
    
    if timestamp < s.lastTimestamp {
        // 时钟回拨，拒绝生成
        return s.Generate()
    }
    
    if timestamp == s.lastTimestamp {
        // 同一毫秒内递增序列
        s.sequence = (s.sequence + 1) & sequenceMax
        if s.sequence == 0 {
            // 序列溢出，等待下一毫秒
            timestamp = s.waitNextMillis(timestamp)
        }
    } else {
        // 新毫秒，序列重置
        s.sequence = 0
    }
    
    s.lastTimestamp = timestamp
    
    // 组装ID
    return (timestamp-epoch)<<timestampShift | 
           s.datacenterID<<datacenterShift | 
           s.workerID<<workerShift | 
           s.sequence
}

func (s *Snowflake) waitNextMillis(timestamp int64) int64 {
    for timestamp <= s.lastTimestamp {
        timestamp = time.Now().UnixMilli()
    }
    return timestamp
}
```

## 三、其他方案

### 3.1 UUID

```go
import "github.com/google/uuid"

// UUID v4: 随机UUID
func GenerateUUID() string {
    return uuid.New().String()
}

// UUID v7: 时间有序UUID (推荐)
func GenerateUUIDv7() string {
    return uuid.Must(uuid.NewV7()).String()
}
```

### 3.2 Redis INCRC

```go
func GenerateID(redis *redis.Client, prefix string) (int64, error) {
    key := fmt.Sprintf("id:%s", prefix)
    id, err := redis.Incr(context.Background(), key).Result()
    if err != nil {
        return 0, err
    }
    
    // 设置过期时间
    if id == 1 {
        redis.Expire(context.Background(), key, 24*time.Hour)
    }
    
    return id, nil
}
```

## 四、美团Leaf

### 4.1 架构设计

```
┌─────────────────────────────────────────────────────────┐
│                   美团Leaf架构                           │
├─────────────────────────────────────────────────────────┤
│                                                          │
│   ┌──────────┐    ┌──────────┐    ┌──────────┐        │
│   │ Segment  │    │  Snowflake│    │  Cache   │        │
│   │ Server   │◄──►│ Server   │◄──►│  (本地)  │        │
│   │ (号段模式)│    │ (雪花算法)│    │          │        │
│   └────┬─────┘    └────┬─────┘    └────┬─────┘        │
│        │               │               │               │
│   ┌────▼─────┐    ┌────▼─────┐    ┌────▼─────┐        │
│   │  MySQL   │    │  MySQL   │    │  应用服务  │        │
│   │ (号段)   │    │ (工作节点)│    │          │        │
│   └──────────┘    └──────────┘    └──────────┘        │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

### 4.2 号段模式

```java
// Segment模式：批量获取ID
public class SegmentIdGenerator {
    private long segmentSize = 2000;  // 每次获取2000个ID
    private long current = 0;
    private long max = 0;
    
    public synchronized long nextId() {
        if (current >= max) {
            current = fetchFromDB();  // 从数据库获取新的号段
            max = current + segmentSize;
        }
        return current++;
    }
}
```

## 五、面试高频题

### 5.1 高频问题

**Q1: 雪花算法的优点是什么？**

A: 
- 高性能：纯内存计算，无网络开销
- 有序性：时间戳在前，保证全局有序
- 唯一性：机器ID+序列号保证不重复

**Q2: 雪花算法有哪些问题？**

A:
- 时钟回拨：需要处理时钟回退
- 依赖机器ID：需要预先分配
- 64位限制：2^63-1约922亿

**Q3: 如何选择ID方案？**

A:
- 短ID(32位): UUID
- 长ID(64位): 雪花算法
- 高可用: 美团Leaf
- 事务强一致: 数据库序列

### 5.2 自测题

1. 实现一个雪花算法ID生成器
2. 分析时钟回拨的处理方案
3. 比较雪花算法和UUID的优缺点
4. 设计一个高可用的ID生成服务
5. 解释号段模式的原理

---

**创建时间**: 2026-10-17
**作者**: Ryan
**领域**: Interview / 分布式系统
**关键词**: distributed-id, snowflake, uuid, leaf, segment
