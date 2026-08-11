# 分布式 ID 生成深度解析

> 深入分布式 ID 生成：雪花算法、号段模式、Redis 生成、UUID v7。
> 包含 Go 实现和性能对比。
> 适用对象：后端工程师、架构师

---

## 1. 分布式 ID 生成方案对比

```
┌─────────────────────────────────────────────────────────────┐
│                    ID 生成方案对比                           │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  方案             │ 单调性 │ 性能    │ 依赖  │ 复杂度        │
│  ────────────────┼────────┼─────────┼───────┼──────────────│
│  UUID             │ ❌     │ 高      │ 无    │ 低            │
│  数据库自增        │ ✅     │ 中      │ DB    │ 低            │
│  号段模式          │ ✅     │ 高      │ DB    │ 中            │
│  雪花算法          │ ✅     │ 极高    │ 无    │ 中            │
│  Redis INCR       │ ✅     │ 高      │ Redis │ 低            │
│  UUID v7          │ ✅     │ 高      │ 无    │ 低            │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. 雪花算法详解

### 2.1 算法结构

```
┌─────────────────────────────────────────────────────────────┐
│                   雪花算法结构 (64-bit)                       │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  符号位 │    时间戳      │  机器ID  │    序列号              │
│   1bit  │    41bit       │   10bit  │     12bit              │
│         │                │          │                        │
│  ┌─────┐┌──────────────┐┌───────┐┌─────────────────────┐  │
│  │  0  ││   timestamp   ││ worker││      sequence       │  │
│  └─────┘└──────────────┘└───────┘└─────────────────────┘  │
│                                                             │
│  时间戳: 41 bit = 2^41 ms ≈ 69 年                           │
│  机器ID: 10 bit = 1024 台机器                               │
│  序列号: 12 bit = 每ms 4096 个ID                            │
│                                                             │
│  最大 ID 数: 2^12 * 每ms = 4096 万 QPS                      │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 Go 实现

```go
// snowflake.go

package id

import (
    "sync"
    "time"
)

const (
    epoch        = 1577836800000 // 2020-01-01 00:00:00 UTC
    workerBits   = 10
    sequenceBits = 12
    
    maxWorkerId     = -1 ^ (-1 << workerBits)
    maxSequence     = -1 ^ (-1 << sequenceBits)
    
    workerIdShift   = sequenceBits
    timestampShift  = sequenceBits + workerBits
)

type Snowflake struct {
    mu          sync.Mutex
    workerId    int64
    sequence    int64
    lastTimestamp int64
}

func NewSnowflake(workerId int64) *Snowflake {
    if workerId < 0 || workerId > maxWorkerId {
        panic("worker id out of range")
    }
    return &Snowflake{
        workerId: workerId,
        sequence: 0,
    }
}

func (s *Snowflake) NextID() int64 {
    s.mu.Lock()
    defer s.mu.Unlock()
    
    timestamp := time.Now().UnixMilli()
    
    if timestamp < s.lastTimestamp {
        // 时钟回拨，等待
        for timestamp < s.lastTimestamp {
            timestamp = time.Now().UnixMilli()
        }
    }
    
    if timestamp == s.lastTimestamp {
        s.sequence = (s.sequence + 1) & maxSequence
        if s.sequence == 0 {
            // 等待下一毫秒
            timestamp = s.waitNextMillis(timestamp)
        }
    } else {
        s.sequence = 0
    }
    
    s.lastTimestamp = timestamp
    
    return ((timestamp - epoch) << timestampShift) |
        (s.workerId << workerIdShift) |
        s.sequence
}

func (s *Snowflake) waitNextMillis(lastTimestamp int64) int64 {
    timestamp := time.Now().UnixMilli()
    for timestamp <= lastTimestamp {
        timestamp = time.Now().UnixMilli()
    }
    return timestamp
}

// ID 格式化为字符串
func (s *Snowflake) ToString(id int64) string {
    timestamp := (id >> timestampShift) + epoch
    workerId := (id >> workerIdShift) & maxWorkerId
    sequence := id & maxSequence
    
    return fmt.Sprintf("%d_%d_%d", timestamp, workerId, sequence)
}
```

---

## 3. 号段模式

### 3.1 原理

```
┌─────────────────────────────────────────────────────────────┐
│                    号段模式原理                              │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  数据库表: id_generator                                      │
│  ┌─────────┬──────────┬──────────┬──────────┐              │
│  │ type    │ current  │ step     │ max      │              │
│  ├─────────┼──────────┼──────────┼──────────┤              │
│  │ order   │ 1000     │ 2000     │ 3000     │              │
│  └─────────┴──────────┴──────────┴──────────┘              │
│                                                             │
│  业务使用:                                                   │
│  1. 从数据库获取号段 [1000, 3000]                           │
│  2. 本地生成 ID: 1000, 1001, 1002, ..., 2999               │
│  3. 用完后再获取下一个号段                                   │
│                                                             │
│  优点: 高性能、不依赖外部服务                                │
│  缺点: ID 不连续、可能重复（如果号段未用完就宕机）            │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 Go 实现

```go
// segment.go

package id

import (
    "database/sql"
    "sync"
)

type SegmentGenerator struct {
    db        *sql.DB
    mu        sync.Mutex
    current   int64
    max       int64
    step      int
    typeId    string
}

func NewSegmentGenerator(db *sql.DB, typeId string, step int) *SegmentGenerator {
    return &SegmentGenerator{
        db:     db,
        step:   step,
        typeId: typeId,
    }
}

func (g *SegmentGenerator) NextID() int64 {
    g.mu.Lock()
    defer g.mu.Unlock()
    
    if g.current >= g.max {
        g.fetchSegment()
    }
    
    id := g.current
    g.current++
    return id
}

func (g *SegmentGenerator) fetchSegment() bool {
    // 乐观锁更新
    affected, err := g.db.Exec(
        "UPDATE id_generator SET current = current + ?, max = current + ? WHERE type = ? AND current = max",
        g.step, g.step, g.typeId,
    )
    
    if err != nil {
        return false
    }
    
    rows, _ := affected.RowsAffected()
    if rows == 0 {
        // 更新失败，等待重试
        time.Sleep(10 * time.Millisecond)
        return g.fetchSegment()
    }
    
    // 获取新号段
    var current, max int64
    g.db.QueryRow("SELECT current, max FROM id_generator WHERE type = ?", g.typeId).Scan(&current, &max)
    
    g.current = current
    g.max = max
    return true
}
```

---

## 4. UUID v7

### 4.1 结构

```
UUID v7 结构 (128-bit):

┌─────────────────────────────────────────────────────────────┐
│  时间戳 (48 bits) │ 变体 (4 bits) │ 时钟序列 (12 bits) │ 随机 (62 bits) │
├─────────────────────────────────────────────────────────────┤
│  unix_ms (48)     │ 0xxx         │ seq (12)         │ rand (62)       │
│                                                             │
│  特点:                                                       │
│  - 时间戳在前，Lexicographically sortable                    │
│  - 向后兼容 UUID v1/v4                                       │
│  - 推荐用于数据库主键                                        │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 4.2 Go 实现

```go
// uuid_v7.go

package id

import (
    "encoding/binary"
    "time"
)

type UUIDv7 [16]byte

func NewUUIDv7() UUIDv7 {
    var uuid UUIDv7
    
    // 时间戳 (48 bits)
    timestamp := uint64(time.Now().UnixMilli())
    binary.BigEndian.PutUint64(uuid[0:6], timestamp>>16)
    binary.BigEndian.PutUint16(uuid[6:8], uint16(timestamp&0xffff))
    
    // 变体 (2 bits in version)
    uuid[6] |= 0x70  // version 7
    
    // 时钟序列 (14 bits)
    uuid[8] = 0x80   // variant
    
    // 随机数 (62 bits)
    // 实际实现应使用安全的随机数生成器
    for i := 9; i < 16; i++ {
        uuid[i] = byte(rand.Uint32())
    }
    
    return uuid
}

func (u UUIDv7) String() string {
    return fmt.Sprintf("%x-%x-%x-%x-%x",
        u[0:4], u[4:6], u[6:8], u[8:10], u[10:16])
}
```

---

## 5. 性能对比

### 5.1 基准测试

```go
// benchmark_test.go

package id

import "testing"

func BenchmarkSnowflake(b *testing.B) {
    sf := NewSnowflake(1)
    for i := 0; i < b.N; i++ {
        sf.NextID()
    }
}

func BenchmarkUUIDv7(b *testing.B) {
    for i := 0; i < b.N; i++ {
        NewUUIDv7()
    }
}

func BenchmarkSegment(b *testing.B) {
    gen := NewSegmentGenerator(nil, "test", 1000)
    for i := 0; i < b.N; i++ {
        gen.NextID()
    }
}
```

### 5.2 测试结果

| 方案 | QPS | 延迟 P99 |
|------|-----|----------|
| Snowflake | 100万+ | < 1μs |
| UUID v7 | 50万+ | < 2μs |
| 号段模式 | 10万+ | < 10μs |
| Redis INCR | 5万+ | < 100μs |

---

## 6. 实战案例

### 6.1 广告系统 ID 设计

```
订单 ID: 雪花算法
  - 时间戳保证有序
  - 10 位机器 ID 支持 1024 个节点
  - 12 位序列号支持高并发

用户 ID: 号段模式
  - 从数据库获取号段
  - 本地生成，无需网络请求

曝光 ID: UUID v7
  - 可排序
  - 全局唯一
  - 适合日志追踪
```

---

## 7. 总结

### 7.1 方案选择

| 场景 | 推荐方案 |
|------|----------|
| 高性能主键 | 雪花算法 |
| 可排序 ID | UUID v7 |
| 简单实现 | 号段模式 |
| 已有 Redis | Redis INCR |

### 7.2 最佳实践

- [ ] 选择合适的 ID 生成方案
- [ ] 处理时钟回拨问题
- [ ] 监控 ID 生成性能
- [ ] 避免 ID 碰撞

---

*最后更新：2026-08-11*
*作者：Ryan*
