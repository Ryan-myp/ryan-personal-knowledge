# 分布式ID生成深度解析

> 深入分布式ID生成：雪花算法、UUID v7、YITID、Leaf。
> 源码级分析，包含生产环境实践。
> 适用对象：分布式系统工程师、架构师

---

## 1. 雪花算法

### 1.1 算法原理

```
雪花算法 (Snowflake) 结构：

┌─────────────────────────────────────────────────────────────┐
│  符号(1bit) | 时间戳(41bit) | 机器ID(10bit) | 序列号(12bit) │
│  0         | milliseconds   | worker_id     | sequence     │
└─────────────────────────────────────────────────────────────┘

总长度：64位 (long)
时间戳：41位 = 可用约69年
机器ID：10位 = 1024台机器
序列号：12位 = 每毫秒4096个ID
```

### 1.2 Go 实现雪花算法

```go
// snowflake.go

package distributed

import (
    "sync"
    "time"
)

type Snowflake struct {
    mu           sync.Mutex
    workerID     int64
    sequence     int64
    lastTimestamp int64
}

const (
    workerIDBits   = int64(10)
    sequenceBits   = int64(12)
    workerIDShift  = sequenceBits
    timestampLeftShift = sequenceBits + workerIDBits
    sequenceMask   = int64(-1) ^ (-1 << sequenceBits)
    maxWorkerID    = int64(-1) ^ (-1 << workerIDBits)
)

func NewSnowflake(workerID int64) (*Snowflake, error) {
    if workerID < 0 || workerID > maxWorkerID {
        return nil, ErrInvalidWorkerID
    }
    return &Snowflake{
        workerID: workerID,
        sequence: 0,
    }, nil
}

func (sf *Snowflake) NextID() (int64, error) {
    sf.mu.Lock()
    defer sf.mu.Unlock()
    
    timestamp := time.Now().UnixMilli()
    
    if timestamp == sf.lastTimestamp {
        sf.sequence = (sf.sequence + 1) & sequenceMask
        if sf.sequence == 0 {
            // 等待下一毫秒
            for timestamp <= sf.lastTimestamp {
                timestamp = time.Now().UnixMilli()
            }
        }
    } else {
        sf.sequence = 0
    }
    
    sf.lastTimestamp = timestamp
    
    // 生成ID
    id := ((timestamp - epoch) << timestampLeftShift) |
           (sf.workerID << workerIDShift) |
           sf.sequence
    
    return id, nil
}
```

---

## 2. UUID v7

### 2.1 设计理念

```
UUID v7 设计：

├── 时间有序
│   └── 基于Unix时间戳

├── 可排序
│   └── 数据库索引友好

├── 唯一性
│   └── 12位随机数

└── 兼容性
    └── RFC 9562标准
```

### 2.2 Go 实现 UUID v7

```go
// uuid_v7.go

package distributed

import (
    "crypto/rand"
    "encoding/binary"
    "time"
)

type UUIDv7 [16]byte

func NewUUIDv7() UUIDv7 {
    var uuid UUIDv7
    
    // 获取时间戳（毫秒）
    timestamp := uint64(time.Now().UnixMilli())
    
    // 填充时间戳（48位）
    binary.BigEndian.PutUint16(uuid[0:2], uint16(timestamp>>32))
    binary.BigEndian.PutUint16(uuid[2:4], uint16(timestamp>>16))
    binary.BigEndian.PutUint16(uuid[4:6], uint16(timestamp))
    
    // 设置版本 (7)
    uuid[6] = 0x70
    
    // 填充随机数
    rand.Read(uuid[8:16])
    
    // 设置变体 (10)
    uuid[8] = (uuid[8] & 0x3F) | 0x80
    
    return uuid
}

func (u UUIDv7) String() string {
    return sprintf("%x-%x-%x-%x-%x", 
        u[0:4], u[4:6], u[6:8], u[8:10], u[10:16])
}
```

---

## 3. YITID

### 3.1 设计理念

```
YITID 设计特点：

├── 纯数字
│   └── 数据库索引友好

├── 短长度
│   └── 19位数字

├── 高吞吐
│   └── 支持万级QPS

└── 有序性
    └── 递增有序
```

### 3.2 Go 实现 YITID

```go
// yitid.go

package distributed

import (
    "sync"
    "time"
)

type YITID struct {
    mu            sync.Mutex
    workerID      int64
    sequence      int64
    lastTimestamp int64
    base          int64 = 1483200000000 // 2017-01-01
}

func NewYITID(workerID int64) *YITID {
    return &YITID{
        workerID: workerID,
    }
}

func (y *YITID) NextID() int64 {
    y.mu.Lock()
    defer y.mu.Unlock()
    
    timestamp := time.Now().UnixMilli() - y.base
    
    if timestamp == y.lastTimestamp {
        y.sequence++
        if y.sequence >= 4096 {
            for timestamp <= y.lastTimestamp {
                timestamp = time.Now().UnixMilli() - y.base
            }
        }
    } else {
        y.sequence = 0
    }
    
    y.lastTimestamp = timestamp
    
    // 组合ID
    id := (timestamp << 22) | (y.workerID << 12) | y.sequence
    return id
}
```

---

## 4. Leaf 服务

### 4.1 架构设计

```
美团 Leaf 架构：

┌─────────────────────────────────────────────────────────────┐
│                    Leaf 架构                                 │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Segment 模式                                                │
│  ├── 从DB获取ID段                                             │
│  ├── 本地分配                                                  │
│  └── 段用完自动刷新                                            │
│                                                             │
│  Snowflake 模式                                              │
│  ├── 基于时间戳                                                │
│  ├── 机器ID配置                                                │
│  └── 序列号自增                                                │
│                                                             │
│  协调服务                                                      │
│  └── ZooKeeper管理                                            │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 4.2 Go 实现 Leaf

```go
// leaf.go

package distributed

import (
    "sync"
    "time"
)

type LeafService struct {
    mode         string // segment, snowflake
    segment      *SegmentGenerator
    snowflake    *Snowflake
    mu           sync.Mutex
}

type SegmentGenerator struct {
    db         *Database
    maxStep    int
    current    int64
    end        int64
    mu         sync.Mutex
}

func NewLeafService(mode string) *LeafService {
    service := &LeafService{mode: mode}
    
    switch mode {
    case "segment":
        service.segment = NewSegmentGenerator()
    case "snowflake":
        service.snowflake = NewSnowflake(1)
    }
    
    return service
}

func (ls *LeafService) NextID() (int64, error) {
    ls.mu.Lock()
    defer ls.mu.Unlock()
    
    switch ls.mode {
    case "segment":
        return ls.segment.NextID()
    case "snowflake":
        return ls.snowflake.NextID()
    default:
        return 0, ErrInvalidMode
    }
}
```

---

## 5. 总结

### 5.1 核心原理回顾

| 方案 | 长度 | 特点 | 适用场景 |
|------|------|------|----------|
| 雪花算法 | 64位 | 分布式、有序 | 通用场景 |
| UUID v7 | 128位 | 时间有序 | 数据库 |
| YITID | 19位 | 纯数字 | 国内场景 |
| Leaf | 可变 | 高可用 | 大规模场景 |

### 5.2 最佳实践

- [ ] 根据场景选择合适的ID生成方案
- [ ] 监控ID生成服务的健康状态
- [ ] 设计合理的机器ID分配策略
- [ ] 考虑时钟回拨问题

---

*最后更新：2026-08-11*
*作者：Ryan*
