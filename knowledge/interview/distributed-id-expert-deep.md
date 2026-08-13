# 分布式ID生成 - 资深专家深度实现

## 一、核心概念

### 1.1 为什么需要分布式ID

在分布式系统中，单机自增ID无法满足需求：
- 多节点并发生成ID
- ID全局唯一
- ID趋势递增（利于索引）
- 高可用、高性能

### 1.2 常见方案对比

| 方案 | 优点 | 缺点 | 适用场景 |
|------|------|------|----------|
| 数据库自增 | 简单可靠 | 单点瓶颈 | 小规模系统 |
| UUID | 全局唯一 | 无序、存储空间大 | 临时标识 |
| Snowflake | 高性能、有序 | 时钟回拨问题 | 大规模系统 |
| Redis INCR | 高性能 | 依赖Redis | 缓存友好场景 |
| 号段模式 | 性能好、容错 | 复杂性高 | 金融级场景 |

## 二、Snowflake算法详解

### 2.1 位结构

```
┌──────────────────┬───────────────┬─────────────┬──────────┐
│   Timestamp      │  DatacenterId │  WorkerId   │ Sequence │
│   (41 bits)      │  (5 bits)     │  (5 bits)   │ (12 bits)│
└──────────────────┴───────────────┴─────────────┴──────────┘
```

- **Timestamp**: 41位，可容纳69年（从2020年开始）
- **DatacenterId**: 5位，支持32个数据中心
- **WorkerId**: 5位，支持32个节点
- **Sequence**: 12位，每毫秒最多4096个ID

### 2.2 Go实现

```go
package snowflake

import (
	"sync"
	"time"
)

// Worker 分布式ID生成器
type Worker struct {
	mu           sync.Mutex
	lastTS       int64
	sequence     int64
	workerID     int64
	datacenterID int64
}

const (
	// 起始时间 (2020-01-01 00:00:00 UTC)
	epoch = 1577836800000

	// 各字段位数
	workerIDBits      = 5
	datacenterIDBits  = 5
	sequenceBits      = 12

	// 各字段最大值
	maxWorkerID      = -1 ^ (-1 << workerIDBits)  // 31
	maxDatacenterID  = -1 ^ (-1 << datacenterIDBits) // 31
	maxSequence      = -1 ^ (-1 << sequenceBits)    // 4095

	// 各字段移位
	workerIDShift      = sequenceBits
	datacenterIDShift  = sequenceBits + workerIDBits
	timestampLeftShift = sequenceBits + workerIDBits + datacenterIDBits

	// 时钟回拨最大容忍: 10ms
	maxDrift = int64(10)
)

// NewWorker 创建新的Worker
func NewWorker(workerID, datacenterID int64) (*Worker, error) {
	if workerID < 0 || workerID > maxWorkerID {
		return nil, ErrInvalidWorkerID
	}
	if datacenterID < 0 || datacenterID > maxDatacenterID {
		return nil, ErrInvalidDatacenterID
	}
	return &Worker{
		workerID:     workerID,
		datacenterID: datacenterID,
	}, nil
}

// NextID 生成下一个ID
func (w *Worker) NextID() (int64, error) {
	w.mu.Lock()
	defer w.mu.Unlock()

	ts := time.Now().UnixMilli()

	// 时钟回拨处理
	if ts < w.lastTS {
		drift := w.lastTS - ts
		if drift > maxDrift {
			return 0, ErrClockBackward
		}
		time.Sleep(drift * time.Millisecond)
		ts = time.Now().UnixMilli()
	}

	// 同一毫秒内处理
	if ts == w.lastTS {
		w.sequence = (w.sequence + 1) & maxSequence
		if w.sequence == 0 {
			ts = w.waitNextMillis(ts)
		}
	} else {
		w.sequence = 0
	}

	w.lastTS = ts

	// 组合ID
	id := ((ts - epoch) << timestampLeftShift) |
		(w.datacenterID << datacenterIDShift) |
		(w.workerID << workerIDShift) |
		w.sequence

	return id, nil
}

// waitNextMillis 等待下一毫秒
func (w *Worker) waitNextMillis(ts int64) int64 {
	for {
		newTs := time.Now().UnixMilli()
		if newTs > ts {
			return newTs
		}
	}
}
```

### 2.3 性能测试

```go
func BenchmarkSnowflake(b *testing.B) {
	w, _ := NewWorker(1, 1)
	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		w.NextID()
	}
}

// 测试结果: ~100万 QPS/单机
```

## 三、UUID v7

### 3.1 标准UUID v4 vs v7

```
UUID v4 (随机):
┌────────────────────────────────────────┐
│  Time (0)  │  Clock Seq (0) │  Random  │
│  (0000)    │  (0000)        │  (random)│
└────────────────────────────────────────┘
❌ 无序，存储效率低

UUID v7 (时间有序):
┌────────────────────────────────────────┐
│  Timestamp (48) │ CRC (4) │ Ver (4)    │
│                 │ Counter │            │
└────────────────────────────────────────┘
✅ 有序，适合InnoDB索引
```

### 3.2 Go实现

```go
package uuidv7

import (
	"crypto/rand"
	"encoding/binary"
	"time"
)

func NewV7() [16]byte {
	var u [16]byte
	
	// 获取时间戳 (毫秒)
	ts := uint64(time.Now().UnixMilli())
	
	// 前48位: 时间戳
	binary.BigEndian.PutUint64(u[0:8], ts<<16)
	
	// 版本位: 7 (UUID v7)
	u[6] = (u[6] & 0x0F) | 0x70
	
	// 变体位: RFC 4122
	u[8] = (u[8] & 0x3F) | 0x80
	
	// 随机部分
	rand.Read(u[4:6])
	rand.Read(u[9:16])
	
	return u
}
```

## 四、号段模式

### 4.1 核心思想

预先从数据库获取一段ID，本地使用完毕后再次获取：

```
┌─────────────────────────────────────────────────────────┐
│  数据库 sequence 表                                     │
│  ┌─────────┬────────┬────────┬────────┐                │
│  │ name    │ min_val│ max_val│ step   │                │
│  ├─────────┼────────┼────────┼────────┤                │
│  │ order   │ 1     │ 1000   │ 1000   │                │
│  │ user    │ 1     │ 500    │ 500    │                │
│  └─────────┴────────┴────────┴────────┘                │
│                                                         │
│  应用层缓存:                                             │
│  order_id: [1, 1000] → 使用完后 [1001, 2000]           │
└─────────────────────────────────────────────────────────┘
```

### 4.2 Go实现

```go
package segment

import (
	"sync"
	"time"
)

// Segment 号段
type Segment struct {
	mu        sync.Mutex
	minVal    int64
	maxVal    int64
	current   int64
	step      int
}

// Manager 号段管理器
type Manager struct {
	segments map[string]*Segment
	mu       sync.RWMutex
	db       Database
}

// GetID 获取ID
func (m *Manager) GetID(name string) (int64, error) {
	m.mu.RLock()
	seg, ok := m.segments[name]
	m.mu.RUnlock()

	if !ok {
		m.mu.Lock()
		seg = &Segment{step: 1000}
		m.segments[name] = seg
		m.mu.Unlock()
	}

	seg.mu.Lock()
	defer seg.mu.Unlock()

	if seg.current >= seg.maxVal {
		// 号段用完，从DB获取新的
		newMin, newMax, err := m.db.FetchSegment(name, seg.step)
		if err != nil {
			return 0, err
		}
		seg.minVal = newMin
		seg.maxVal = newMax
		seg.current = newMin
	}

	id := seg.current
	seg.current++
	return id, nil
}
```

## 五、面试高频题

### Q1: Snowflake时钟回拨怎么处理？

```
A: 三种方案:
1. 等待时钟同步 (NTP)
2. 升级WorkerID (分配新节点)
3. 直接使用错误码返回失败
```

### Q2: UUID v7相比v4有什么优势？

```
A:
1. 时间有序，适合InnoDB聚簇索引
2. 查询性能更好 (范围查询)
3. 存储密度更高
```

### Q3: 号段模式的优缺点？

```
A:
优点: 容错性好，DB故障不影响
缺点: 有ID空洞，需要维护状态
```

### Q4: 如何选择ID生成方案？

```
A:
- 小规模: 数据库自增
- 中等规模: Snowflake
- 高并发: 号段模式
- 临时标识: UUID v7
```

## 六、自测题

1. 实现一个带时钟回拨处理的Snowflake
2. 设计一个基于Redis的ID生成器
3. 比较UUID v4和v7的性能差异
4. 号段模式如何保证高可用？

---

## 参考文档

- [Snowflake源码](https://github.com/bwmarrin/snowflake)
- [UUID v7 RFC](https://datatracker.ietf.org/doc/html/draft-ietf-uuidrev-rfc4122-bis)
- [美团Leaf方案](https://tech.meituan.com/2017/04/21/mt-leaf.html)
