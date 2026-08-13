# 分布式ID生成深度解析

> 深入分布式ID生成：雪花算法、UUID、号段模式、数据库生成。
> 源码级分析，包含生产环境实现。
> 适用对象：后端工程师、架构师

---

## 1. 分布式ID要求

### 1.1 核心需求

```
分布式ID需要满足：

1. 全局唯一
   └── 不同节点生成的ID不重复

2. 趋势递增
   └── 保证插入性能（聚簇索引）

3. 高可用
   └── 不依赖中心化服务

4. 高性能
   └── 生成速度快，低延迟

5. 安全有序
   └── 不易被猜测（可选）
```

---

## 2. 雪花算法

### 2.1 算法结构

```
雪花算法 (Snowflake) 结构：

┌─────────────────────────────────────────────────────────────┐
│  符号(1bit) │ 时间戳(41bit) │ 机器ID(10bit) │ 序列号(12bit)  │
├─────────────────────────────────────────────────────────────┤
│  0         │  2024-01-01   │  0000000001  │   000000000001  │
│            │  (41位)       │  (10位)      │   (12位)        │
└─────────────────────────────────────────────────────────────┘

时间戳：41位，可表示69年
机器ID：10位，最多1024台机器
序列号：12位，每毫秒最多4096个ID
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
    workerBits     = 10
    sequenceBits   = 12
    workerMax      = -1 ^ (-1 << workerBits)
    sequenceMax    = -1 ^ (-1 << sequenceBits)
    leftShift      = sequenceBits
    timestampLeft  = sequenceBits + workerBits
)

type Snowflake struct {
    mu          sync.Mutex
    workerId    int64
    lastTimestamp int64
    sequence    int64
}

func NewSnowflake(workerId int64) (*Snowflake, error) {
    if workerId < 0 || workerId > workerMax {
        return nil, ErrWorkerIdOutOfRange
    }
    return &Snowflake{
        workerId:   workerId,
        sequence:   0,
        lastTimestamp: -1,
    }, nil
}

func (s *Snowflake) NextID() (int64, error) {
    s.mu.Lock()
    defer s.mu.Unlock()
    
    timestamp := time.Now().UnixMilli()
    
    if timestamp < s.lastTimestamp {
        return 0, ErrClockBackward
    }
    
    if timestamp == s.lastTimestamp {
        s.sequence = (s.sequence + 1) & sequenceMax
        if s.sequence == 0 {
            timestamp = s.waitNextMillis(timestamp)
        }
    } else {
        s.sequence = 0
    }
    
    s.lastTimestamp = timestamp
    
    return ((timestamp << timestampLeft) |
        (s.workerId << leftShift) |
        s.sequence), nil
}

func (s *Snowflake) waitNextMillis(timestamp int64) int64 {
    for timestamp <= s.lastTimestamp {
        timestamp = time.Now().UnixMilli()
    }
    return timestamp
}
```

---

## 3. UUID

### 3.1 UUID 版本

```
┌─────────────────────────────────────────────────────────────┐
│                  UUID 版本对比                               │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  版本    │ 算法            │ 特点                           │
├─────────────────────────────────────────────────────────────┤
│  v1     │ 时间+MAC地址    │ 有序，可预测                     │
│  v4     │ 随机数          │ 无序，唯一                       │
│  v5     │ SHA-1+命名空间  │ 确定性生成                       │
│  v7     │ 时间序          │ 有序，兼容性好（推荐）            │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 UUID v7 实现

```go
// uuid_v7.go

package id

import (
    "encoding/binary"
    "time"
)

type UUID [16]byte

func NewUUIDv7() UUID {
    var u UUID
    
    timestamp := time.Now().UnixMilli()
    binary.BigEndian.PutUint64(u[0:6], uint64(timestamp)<<16|uint64(getCounter())&0xFFFF)
    
    // 设置版本和变体
    u[6] = 0x70 | (u[6] & 0x0F)
    u[8] = 0x80 | (u[8] & 0x3F)
    
    // 随机部分
    getRandomBytes(u[10:16])
    
    return u
}

func getCounter() uint16 {
    // 使用线程安全的计数器
    return atomic.AddUint16(&counter, 1)
}
```

---

## 4. 号段模式

### 4.1 原理

```
号段模式原理：

1. 从数据库获取号段
   └── 每次获取一批ID（如1000个）

2. 本地缓存号段
   └── 用完后再从数据库获取下一批

3. 优点
   ├── 减少数据库访问
   └── 高性能

4. 缺点
   ├── ID不连续
   └── 需要数据库支持
```

### 4.2 Go 实现

```go
// segment.go

package id

import (
    "sync"
    "sync/atomic"
)

type SegmentGenerator struct {
    mu          sync.Mutex
    currentMin  int64
    currentMax  int64
    current     int64
    step        int64
    db          *Database
}

func (g *SegmentGenerator) NextID() int64 {
    if g.current >= g.currentMax {
        g.refresh()
    }
    return atomic.AddInt64(&g.current, 1)
}

func (g *SegmentGenerator) refresh() {
    g.mu.Lock()
    defer g.mu.Unlock()
    
    // 从数据库获取新号段
    min, max := g.db.GetSegment(g.step)
    g.currentMin = min
    g.currentMax = max
    g.current = min
}
```

---

## 5. 数据库生成

### 5.1 自增ID

```sql
-- 最简单的分布式ID方案
CREATE TABLE id_generator (
    id BIGINT NOT NULL AUTO_INCREMENT,
    PRIMARY KEY (id)
);

-- 获取最后插入的ID
SELECT LAST_INSERT_ID();
```

### 5.2 分布式ID表

```sql
CREATE TABLE distributed_id (
    id BIGINT NOT NULL,
    value BIGINT NOT NULL,
    PRIMARY KEY (id)
);

-- 获取ID
UPDATE distributed_id 
SET value = value + step 
WHERE id = 'biz_type' 
RETURNING value - step;
```

---

## 6. 选型建议

### 6.1 对比分析

```
┌─────────────────────────────────────────────────────────────┐
│                  ID生成方案对比                              │
├─────────────────────────────────────────────────────────────┤
│  方案        │ 性能   │ 唯一性 │ 有序性 │ 依赖    │ 推荐场景  │
├─────────────────────────────────────────────────────────────┤
│  雪花算法    │ 高     │ 强    │ 强    │ 无      │ 通用      │
│  UUID v4     │ 高     │ 强    │ 无    │ 无      │ 不需要有序 │
│  UUID v7     │ 高     │ 强    │ 强    │ 无      │ 推荐      │
│  号段模式    │ 高     │ 强    │ 弱    │ 数据库  │ 需要数据库 │
│  数据库自增  │ 中     │ 强    │ 强    │ 数据库  │ 简单场景  │
└─────────────────────────────────────────────────────────────┘
```

### 6.2 推荐方案

```
推荐方案：

1. 首选：UUID v7
   ├── 有序性
   ├── 分布式友好
   └── 无需依赖

2. 备选：雪花算法
   ├── 高性能
   ├── 可控性强
   └── 需要分配机器ID

3. 特殊场景：号段模式
   ├── 需要数据库持久化
   └── 需要号段刷新机制
```

---

## 7. 总结

### 7.1 核心原理回顾

| 方案 | 核心机制 |
|------|----------|
| 雪花算法 | 时间戳+机器ID+序列号 |
| UUID | 随机数/时间序 |
| 号段模式 | 批量获取+本地缓存 |
| 数据库 | 自增/号段表 |

### 7.2 最佳实践

- [ ] 优先使用 UUID v7
- [ ] 高并发场景用雪花算法
- [ ] 需要持久化用号段模式
- [ ] 避免使用纯随机UUID v4

---

*最后更新：2026-08-11*
*作者：Ryan*
