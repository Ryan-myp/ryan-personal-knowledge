# CDC 深度：Change Data Capture 架构、Debezium、Flink CDC 与广告实时数据管道

> 从广告系统视角，深度解析 CDC 的原理、实现、生产排障与 Go 源码级实现
>
> **知识来源**：MySQL binlog 规范 / Debezium 官方文档 / PostgreSQL WAL / Flink CDC / 广告实时数据管道架构
>
> **蒸馏日期**：2026-07-14

---

## 第一部分：为什么广告系统需要 CDC？

### 类比理解

```
传统 ETL vs CDC：

传统 ETL（定时全量扫描）：
┌──────────┐     每晚 2:00      ┌──────────┐
│  MySQL   │ ──────────────────▶ │ ClickHouse│
│  业务库   │                    │  数仓     │
└──────────┘                    └──────────┘
         ↑ 延迟：8-24 小时
         ↑ 资源：每晚全表扫描，IO 爆炸
         ↑ 问题：漏数据、重复数据、窗口期数据丢失

CDC（实时捕获变更）：
┌──────────┐  binlog/WAL  ┌──────────┐  Kafka  ┌──────────┐
│  MySQL   │ ─────────────▶ │ Debezium │ ──────▶ │ Flink    │
│  业务库   │               │  CDC     │         │  计算    │
└──────────┘               └──────────┘         └──────────┘
                                                          │
                                                    ┌──────────┐
                                                    │ ClickHouse│
                                                    │  实时看板  │
                                                    └──────────┘
         ↑ 延迟：秒级（< 3s）
         ↑ 资源：只处理变更，IO 极低
         ↑ 优势：Exactly-Once、顺序保证、断点续传
```

### 广告系统的 CDC 场景

```
场景 1：广告实时看板
  用户投放 campaign → MySQL 写入 impression/click 记录
  → Debezium 捕获 binlog → Kafka → Flink 实时聚合
  → ClickHouse 秒级更新看板数据
  → 广告主看到实时消耗和 ROI

场景 2：归因分析
  用户点击广告 → MySQL ads.clicks 表
  → CDC 捕获点击事件 → Kafka → Flink 关联转化事件
  → 实时计算归因窗口内的转化
  → 更新 ad_platform.ad_attribution 汇总表

场景 3：数据同步
  MySQL（业务库）→ Iceberg（数据湖）
  → Debezium CDC 捕获 DDL/DML
  → Flink CDC Sink 写入 Iceberg
  → 支持 Spark/Trino 实时查询

场景 4：缓存同步
  MySQL 订单/库存变更 → CDC → Kafka
  → Flink 消费 → 更新 Redis 缓存
  → 解决缓存与数据库不一致问题
```

### 核心挑战

```
1. 顺序保证：binlog 是全局有序的吗？
   → InnoDB 的 binlog 是全局有序的（单线程写入）
   → 多表并发写入时，binlog position 严格递增

2.  Exactly-Once：重复消费怎么办？
   → Debezium 维护 offset 到 MySQL binlog position
   → Kafka consumer group 提交 offset
   → Flink checkpoint 保证端到端 EO

3.  Schema 演进：DDL 变更如何处理？
   → Debezium 捕获 DDL 事件 → 更新 Kafka schema
   → Flink CDC 自动感知 schema 变化
   → Iceberg native 支持 schema evolution

4.  断点续传：Debezium 挂了怎么办？
   → offset 持久化到 MySQL debezium_offset 表
   → 重启后从上次 position 继续
   → 不会遗漏也不会重复

5.  性能影响：binlog 对 MySQL 的影响？
   → binlog_format=ROW 时，InnoDB 每 commit 一次写一次 binlog
   → sync_binlog=1 保证 durability（性能开销约 5-10%）
   → max_binlog_size=1G 避免单个文件过大
```

---

## 第二部分：MySQL Binlog 深度

### Binlog 格式

```
MySQL 有三种 binlog 格式：

1. STATEMENT（语句级）
   - 记录原始 SQL 语句
   - 优点：binlog 小
   - 缺点：不确定性问题（NOW()、UUID() 等）
   - 不适用于 CDC

2. MIXED（混合）
   - 默认用 STATEMENT，不确定语句自动用 ROW
   - 兼容性好但不可控

3. ROW（行级）⭐ 推荐用于 CDC
   - 记录每一行变更前后的值
   - 优点：确定性、精确还原
   - 缺点：binlog 较大
   - Debezium/Flink CDC 都依赖 ROW 格式

配置：
  binlog_format = ROW
  binlog_row_image = FULL  (默认：记录所有列)
  # binlog_row_image = MINIMAL (只记录变更列 + PK，节省空间)
  # binlog_row_image = NOBLOB (不记录 BLOB/TEXT)
```

### Row Event 结构

```
Binlog Event 结构（v4 格式）：

┌──────────────────────────────────────────────────┐
│ Header (19 bytes)                                 │
│   timestamp (4) - 事件发生时间                     │
│   event_type (1)  - 事件类型                       │
│   server_id (4)   - 产生事件的 server id           │
│   event_size (4)  - 整个 event 的大小             │
│   log_pos (4)     - 下一个 event 的位置            │
│   flags (2)       - 标志位                        │
├──────────────────────────────────────────────────┤
│ Payload (变长)                                     │
│   Format Description Event (固定)                 │
│   Previous-GTIDs Event (可选)                     │
│   Rotate Event (切换 binlog 文件时)               │
│   Table Map Event (表结构映射)                    │
│   Write Rows Event / Update Rows Event / Delete Rows Event
│   Xid Event (事务提交)                            │
│   Gtid Event (GTID 模式)                          │
│   Heartbeat Event (可选)                          │
└──────────────────────────────────────────────────┘

事件类型 ID：
  0x01 = FORMAT_DESCRIPTION_EVENT  (格式化描述)
  0x02 = TABLE_MAP_EVENT           (表映射)
  0x19 = WRITE_ROWS_EVENT v2       (插入)
  0x1a = UPDATE_ROWS_EVENT v2      (更新)
  0x1b = DELETE_ROWS_EVENT v2      (删除)
  0x0e = XID_EVENT                 (事务提交)
  0x20 = GTID_EVENT                (GTID)
```

### Go 实现 Binlog Parser

```go
package cdc

import (
	"bytes"
	"encoding/binary"
	"fmt"
	"io"
)

// BinlogEvent 类型
const (
	EventFormatDescription EventType = 0x02
	EventXID               EventType = 0x0e
	EventGTID              EventType = 0x20
	EventTableMap          EventType = 0x1f
	EventWriteRows         EventType = 0x19
	EventUpdateRows        EventType = 0x1a
	EventDeleteRows        EventType = 0x1b
	EventRotate            EventType = 0x0d
)

type EventType uint8

// BinlogHeader 二进制日志事件头
type BinlogHeader struct {
	Timestamp uint32     // 事件发生时间
	Type      EventType  // 事件类型
	ServerID  uint32     // 源服务器 ID
	EventSize uint32     // 事件总大小
	LogPos    uint32     // 下一个事件位置
	Flags     uint16     // 标志位
}

// ParseHeader 解析 binlog header（19 bytes）
func ParseHeader(data []byte) (*BinlogHeader, error) {
	if len(data) < 19 {
		return nil, fmt.Errorf("insufficient data for header: %d bytes", len(data))
	}
	return &BinlogHeader{
		Timestamp: binary.LittleEndian.Uint32(data[0:4]),
		Type:      EventType(data[4]),
		ServerID:  binary.LittleEndian.Uint32(data[5:9]),
		EventSize: binary.LittleEndian.Uint32(data[9:13]),
		LogPos:    binary.LittleEndian.Uint32(data[13:17]),
		Flags:     binary.LittleEndian.Uint16(data[17:19]),
	}, nil
}

// BinlogParser 解析 binlog 流
type BinlogParser struct {
	reader   io.Reader
	pos      uint32
	serverID uint32
	tableMap map[uint64]*TableMapEvent // table_id -> TableMapEvent
}

// TableMapEvent 表映射事件 - 记录表结构
type TableMapEvent struct {
	Database []byte        // 数据库名
	Table    []byte        // 表名
	TableID  uint64        // 表 ID（跨 event 唯一标识一张表）
	Columns  []ColumnMeta  // 列元信息
	Flags    uint16        // 标志位
	Metadata []byte        // 可变长度元数据
}

// ColumnMeta 列元信息
type ColumnMeta struct {
	Name       string
	Type       int8  // MySQL column type ID
	Nullabled  bool  // 是否允许 NULL
	MetadataLen uint16 // 元数据长度
}

// RowsEvent 行变更事件
type RowsEvent struct {
	TableID     uint64
	EventType   EventType // WRITE/UPDATE/DELETE
	Flags       uint16
	ColumnCount uint64
	ColumnMask  []bool // 哪些列被包含
	BeforeImage [][]byte // UPDATE 时的旧值
	AfterImage  [][]byte // UPDATE 时的新值
}

// ParseRowsEvent 解析行变更事件
func (p *BinlogParser) ParseRowsEvent(data []byte) (*RowsEvent, error) {
	idx := 0
	
	// Table ID (6 bytes)
	tableID := binary.LittleEndian.Uint64(data[idx : idx+6])
	idx += 6
	
	// Event type (1 byte)
	eventType := EventType(data[idx])
	idx++
	
	// Flags (2 bytes)
	flags := binary.LittleEndian.Uint16(data[idx : idx+2])
	idx += 2
	
	// Database length + 1
	dbLen := int(data[idx])
	idx++
	
	// Name length + 1
	nameLen := int(data[idx])
	idx++
	
	// Table name
	tableName := string(data[idx : idx+nameLen])
	idx += nameLen
	
	// Transaction metadata length + 1
	txnMetaLen := int(data[idx])
	idx++
	
	// Fixed data length
	fixedLen := int(binary.LittleEndian.Uint16(data[idx : idx+2]))
	idx += 2
	
	// Column count (varint)
	colCount, _ := parseVarint(data[idx:])
	idx += varintSize(colCount)
	
	// Column mask
	numBytes := (colCount + 7) / 8
	columnMask := make([]bool, colCount)
	for i := 0; i < numBytes; i++ {
		byteVal := data[idx+i]
		for j := 0; j < 8; j++ {
			if i*8+j < int(colCount) {
				columnMask[i*8+j] = (byteVal & (1 << j)) != 0
			}
		}
	}
	idx += numBytes
	
	// Number of columns in "before" image
	beforeColCount, _ := parseVarint(data[idx:])
	idx += varintSize(beforeColCount)
	
	var beforeImage, afterImage [][]byte
	
	// Before image (only for UPDATE)
	if beforeColCount > 0 {
		beforeImage = p.decodeRowImages(data[idx:], columnMask, beforeColCount)
		afterStart := idx + fixedLen
		numAfterCols, _ := parseVarint(data[afterStart:])
		afterColStart := afterStart + varintSize(numAfterCols) + 2
		afterFixedLen := int(binary.LittleEndian.Uint16(data[afterColStart:afterColStart+2]))
		afterImage = p.decodeRowImages(data[afterColStart+2:], columnMask, uint64(numAfterCols))
		idx = afterColStart + 2 + afterFixedLen
	} else {
		// No before image (INSERT)
		idx += fixedLen
	}
	
	// After image
	afterColCount, _ := parseVarint(data[idx:])
	idx += varintSize(afterColCount)
	
	afterFixedLen := int(binary.LittleEndian.Uint16(data[idx : idx+2]))
	idx += 2
	
	afterImage = p.decodeRowImages(data[idx:idx+afterFixedLen], columnMask, uint64(afterColCount))
	
	return &RowsEvent{
		TableID:     tableID,
		EventType:   eventType,
		Flags:       flags,
		ColumnCount: colCount,
		ColumnMask:  columnMask,
		BeforeImage: beforeImage,
		AfterImage:  afterImage,
	}, nil
}

// decodeRowImages 解码行数据（简化版）
func (p *BinlogParser) decodeRowImages(data []byte, mask []bool, colCount uint64) [][]byte {
	results := make([][]byte, colCount)
	idx := 0
	
	// Null bitmap (每 8 列 1 byte)
	nullBitmapLen := (int(colCount) + 7) / 8
	nullBitmap := data[idx : idx+nullBitmapLen]
	idx += nullBitmapLen
	
	for i := uint64(0); i < colCount; i++ {
		if !mask[i] {
			continue
		}
		
		// Check if column is NULL
		if (nullBitmap[i/8] & (1 << (i % 8))) != 0 {
			results[i] = nil
			continue
		}
		
		// Read length-encoded string or fixed-length data
		if data[idx] < 251 {
			// Single byte value
			results[i] = []byte{data[idx]}
			idx++
		} else if data[idx] == 251 {
			// NULL
			results[i] = nil
			idx++
		} else if data[idx] == 252 {
			// 2-byte integer
			results[i] = data[idx+1 : idx+3]
			idx += 3
		} else if data[idx] == 253 {
			// 3-byte integer
			results[i] = data[idx+1 : idx+4]
			idx += 4
		} else {
			// 8-byte integer
			results[i] = data[idx+1 : idx+9]
			idx += 9
		}
	}
	
	return results
}

// parseVarint 解析 varint（简化版）
func parseVarint(data []byte) (uint64, int) {
	if data[0] < 251 {
		return uint64(data[0]), 1
	}
	return 0, 0
}

func varintSize(v uint64) int {
	if v < 251 {
		return 1
	}
	return 9
}

```

### Binlog Position 管理

```
GTID vs Position：

方案 1：Position + Filename（传统方式）
  master_log_file = "mysql-bin.000012"
  master_log_pos = 1234567
  
  优点：简单
  缺点：
    - 切换主从时需要手动找 position
    - 多源复制时 position 不唯一
    - 断点续传需要记录 filename + position

方案 2：GTID（推荐）⭐
  gtid_next = "auto"
  gtid_set = "3E11FA47-71CA-11E1-9E33-C80AA94295D0:1-56"
  
  GTID 格式：source_id:transaction_id
    source_id = server_uuid (每个 MySQL 实例唯一)
    transaction_id = 自增序号
  
  优点：
    - 全局唯一，不依赖 position
    - 自动追踪已执行的事务
    - 主从切换无缝衔接
    - 多源复制天然支持
  
  Debezium 配置：
    gtid.new.mode = "adaptive"  (自动检测是否启用 GTID)
    gtid.source.id = "3E11FA47..."  (显式指定 server UUID)
```

---

## 第三部分：Debezium 架构深度

### Debezium 整体架构

```
┌─────────────────────────────────────────────────────────────────┐
│                         Debezium Cluster                         │
│                                                                  │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐                  │
│  │ Connector │    │ Connector │    │ Connector │   ... N 个      │
│  │ (MySQL-1) │    │ (MySQL-2) │    │ (PG-1)   │                  │
│  └────┬─────┘    └────┬─────┘    └────┬─────┘                  │
│       │               │               │                          │
│  ┌────▼─────┐    ┌────▼─────┐    ┌────▼─────┐                  │
│  │ MySQL-1  │    │ MySQL-2  │    │ PG-1     │                  │
│  │ Source DB│    │ Source DB│    │ Source DB│                  │
│  └──────────┘    └──────────┘    └──────────┘                  │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                  Kafka (Change Events)                    │    │
│  │  dbserver1.inventory.customers → Kafka Topic              │    │
│  │  dbserver2.ads.impressions → Kafka Topic                  │    │
│  │  pgserver1.public.users → Kafka Topic                     │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │              Offset Storage (MySQL)                       │    │
│  │  debezium_offsets table:                                │    │
│  │  - server.name, source.file, source.pos, source.gtid   │    │
│  │  - 每个 connector 一个 offset 记录                       │    │
│  └─────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
```

### Debezium MySQL Connector 核心组件

```
┌──────────────────────────────────────────────────────────────┐
│                   MySQL Connector                             │
│                                                              │
│  ┌─────────────────┐    ┌─────────────────┐                 │
│  │  Binlog Reader   │───▶│  Event Deserializer │            │
│  │  (net/read.go)  │    │  (JSON format)     │            │
│  └────────┬────────┘    └────────┬──────────┘            │
│           │                     │                          │
│  ┌────────▼────────┐    ┌───────▼──────────┐            │
│  │  Schema History  │    │  Topic Routing    │            │
│  │  (缓存表结构)     │    │  (db.server1.db.table) │      │
│  └────────┬────────┘    └───────┬──────────┘            │
│           │                     │                          │
│  ┌────────▼─────────────────────▼──────────┐            │
│  │       ChangeEventPump (发送线程)         │            │
│  │  - 序列化变更事件                        │            │
│  │  - 发送到 Kafka                          │            │
│  │  - 维护 offset                           │            │
│  └─────────────────┬───────────────────────┘            │
│                    │                                       │
│  ┌─────────────────▼───────────────────────┐            │
│  │       OffsetCommitTask (持久化线程)       │            │
│  │  - 定期提交 offset 到 MySQL              │            │
│  │  - 保证 Exactly-Once                     │            │
│  └─────────────────────────────────────────┘            │
└──────────────────────────────────────────────────────────────┘
```

### Debezium 配置详解

```json
{
  "name": "mysql-ad-platform-connector",
  "config": {
    "connector.class": "io.debezium.connector.mysql.MySqlConnector",
    
    // ===== 基础配置 =====
    "tasks.max": "1",
    "database.hostname": "mysql-primary.ad-platform.internal",
    "database.port": "3306",
    "database.user": "debezium",
    "database.password": "${secret:debezium_mysql_password}",
    "database.server.id": "184054",
    "database.server.name": "dbserver1",
    
    // ===== 过滤配置 =====
    "database.include.list": "ad_platform",
    "table.include.list": "ad_platform.impressions,ad_platform.clicks,ad_platform.conversions,ad_platform.campaigns",
    "column.include.list": "",
    
    // ===== Topic 配置 =====
    "topic.prefix": "dbserver1",
    "topic.creation.default.replication.factor": "3",
    "topic.creation.default.partitions": "12",
    
    // ===== Snapshot 配置 =====
    "snapshot.mode": "initial",
    "snapshot.locking.mode": "none",
    "snapshot.isolation.mode": "read_committed",
    "snapshot.max.threads": "4",
    
    // ===== 事务配置 =====
    "transactions.timeout.ms": "60000",
    "heartbeat.interval.ms": "10000",
    
    // ===== Offset 存储 =====
    "offset.storage": "mysql",
    "offset.storage.mysqldbname": "debezium",
    "offset.storage.table": "offsets",
    
    // ===== Schema 历史 =====
    "schema.history.internal": "io.debezium.relational.history.memory.MemorySchemaHistory",
    
    // ===== 序列化 =====
    "key.converter": "org.apache.kafka.connect.json.JsonConverter",
    "value.converter": "org.apache.kafka.connect.json.JsonConverter",
    "key.converter.schemas.enable": "false",
    "value.converter.schemas.enable": "false",
    
    // ===== 转换 SMT =====
    "transforms": "route",
    "transforms.route.type": "org.apache.kafka.connect.transforms.RegexRouter",
    "transforms.route.regex": "([^.]+)\\.([^.]+)\\.([^.]+)",
    "transforms.route.replacement": "ad.$2.$3"
  }
}
```

### Debezium Snapshot 机制

```
Snapshot 四种模式：

1. "initial" (默认)
   - 首次启动时全量快照
   - 之后从 binlog 继续
   - 适用：大多数场景

2. "when_needed"
   - 仅在检测到 offset 不存在时快照
   - 适用：connector 重启后 offset 丢失

3. "never"
   - 从不快照，直接从 binlog 开始
   - 适用：数据已经存在，只需要捕获变更

4. "exported"
   - 使用 mysqldump 导出的文件
   - 适用：需要精确控制快照数据

Snapshot 过程（并行快照）：
┌─────────────────────────────────────────────────────┐
│ Phase 1: 准备阶段                                     │
│   - 设置 READ COMMITTED isolation                    │
│   - 获取表锁（locking.mode=none 时不加锁）           │
│   - 记录 binlog position                             │
│                                                     │
│ Phase 2: 快照阶段（多线程并行）                        │
│   Thread-1: SELECT * FROM campaigns                 │
│   Thread-2: SELECT * FROM creatives                 │
│   Thread-3: SELECT * FROM targeting_rules           │
│   Thread-4: SELECT * FROM budget_schedules          │
│                                                     │
│ Phase 3: 收尾阶段                                     │
│   - 释放锁                                           │
│   - 发送 snapshot.complete 事件到 Kafka              │
│   - 切换到 binlog 读取模式                           │
└─────────────────────────────────────────────────────┘

并行快照 Go 实现：
*/
package cdc

import (
	"context"
	"database/sql"
	"fmt"
	"sync"
	"time"
)

// SnapshotTask 快照任务
type SnapshotTask struct {
	Database string
	Table    string
	Query    string
}

// ParallelSnapshoter 并行快照器
type ParallelSnapshoter struct {
	db          *sql.DB
	taskChan    chan SnapshotTask
	resultChan  chan SnapshotResult
	workerCount int
	timeout     time.Duration
}

type SnapshotResult struct {
	Task    SnapshotTask
	Rows    int64
	Duration time.Duration
	Err     error
}

// NewParallelSnapshoter 创建并行快照器
func NewParallelSnapshoter(db *sql.DB, workerCount int, timeout time.Duration) *ParallelSnapshoter {
	return &ParallelSnapshoter{
		db:          db,
		taskChan:    make(chan SnapshotTask, 1000),
		resultChan:  make(chan SnapshotResult, 1000),
		workerCount: workerCount,
		timeout:     timeout,
	}
}

// Execute 执行并行快照
func (s *ParallelSnapshoter) Execute(ctx context.Context, tasks []SnapshotTask) ([]SnapshotResult, error) {
	var wg sync.WaitGroup
	results := make([]SnapshotResult, len(tasks))
	
	// 启动 worker
	for w := 0; w < s.workerCount; w++ {
		wg.Add(1)
		go s.worker(ctx, &wg)
	}
	
	// 发送任务
	for i, task := range tasks {
		select {
		case s.taskChan <- task:
			// 任务已入队
		case <-ctx.Done():
			return nil, ctx.Err()
		}
	}
	close(s.taskChan)
	
	// 收集结果
	done := make(chan struct{})
	go func() {
		for r := range s.resultChan {
			// 找到对应的任务索引
			for i, t := range tasks {
				if t.Database == r.Task.Database && t.Table == r.Task.Table {
					results[i] = r
					break
				}
			}
		}
		close(done)
	}()
	
	wg.Wait()
	close(s.resultChan)
	<-done
	
	return results, nil
}

func (s *ParallelSnapshoter) worker(ctx context.Context, wg *sync.WaitGroup) {
	defer wg.Done()
	for {
		select {
		case task, ok := <-s.taskChan:
			if !ok {
				return
			}
			s.processTask(ctx, task)
		case <-ctx.Done():
			return
		}
	}
}

func (s *ParallelSnapshoter) processTask(ctx context.Context, task SnapshotTask) {
	start := time.Now()
	rows := int64(0)
	var err error
	
	queryCtx, cancel := context.WithTimeout(ctx, s.timeout)
	defer cancel()
	
	// 执行查询
	rows, err = s.executeQuery(queryCtx, task)
	
	s.resultChan <- SnapshotResult{
		Task:     task,
		Rows:     rows,
		Duration: time.Since(start),
		Err:      err,
	}
}

func (s *ParallelSnapshoter) executeQuery(ctx context.Context, task SnapshotTask) (int64, error) {
	rows, err := s.db.QueryContext(ctx, task.Query)
	if err != nil {
		return 0, fmt.Errorf("query failed for %s.%s: %w", task.Database, task.Table, err)
	}
	defer rows.Close()
	
	count := int64(0)
	for rows.Next() {
		count++
	}
	return count, rows.Err()
}

```
---

## 第四部分：Flink CDC 深度

### Flink CDC 架构

```
Flink CDC = Flink + Debezium Engine

与传统 Kafka Connect 的区别：

Kafka Connect 架构：
  MySQL ──▶ Debezium Connector (Java) ──▶ Kafka Topic ──▶ Flink Job
  ↑          独立进程，需要 ZooKeeper/Kafka        独立消费
  ↑          offset 由 Kafka 管理               有延迟

Flink CDC 架构：
  MySQL ──▶ Flink Source (Debezium Engine embedded) ──▶ Flink Operator
  ↑          嵌入 Flink 任务，无 Kafka 中间层         直接计算

优势：
  - 端到端延迟更低（无 Kafka hop）
  - 运维更简单（少一个 Kafka topic）
  - 天然支持 Flink checkpoint
  - 支持 schema evolution
  - 支持 exactly-once sink

劣势：
  - 吞吐量受限于 Flink 并行度
  - 不适合跨 Flink job 共享变更数据
```

### Flink CDC MySQL Source (Java API)

```java
// Maven: flink-cdc-runtime 3.x
// import org.apache.flink.cdc.connectors.mysql.source.MySqlSource;
// import org.apache.flink.cdc.debezium.JsonDebeziumDeserializationSchema;

MySqlSource<String> mysqlSource = MySqlSource.<String>builder()
    .hostname("mysql-primary.ad-platform.internal")
    .port(3306)
    .username("flink_cdc")
    .password("${secret}")
    .databaseList("ad_platform")
    .tableList("ad_platform.impressions", 
               "ad_platform.clicks", 
               "ad_platform.conversions")
    .deserializer(new JsonDebeziumDeserializationSchema())
    .startupOptions(StartupOptions.initial())
    .splitSize(5000)      // 每个 split 的行数
    .chunkKeySize(10000)  // chunk key 大小
    .build();

// Debezium JSON 事件格式：
// {
//   "source": {
//     "version": "2.3.0",
//     "server": "dbserver1",
//     "db": "ad_platform",
//     "table": "impressions",
//     "ts_ms": 1720000000000,
//     "file": "mysql-bin.000012",
//     "pos": 1234567,
//     "gtid": "xxx:1-56"
//   },
//   "op": "c",  // c=create, u=update, d=delete, r=read(snapshot)
//   "ts_ms": 1720000000000,
//   "before": {...},  // UPDATE 时有
//   "after": {...}    // INSERT/UPDATE 时有
// }
```

### Go 实现 Flink CDC Source

```go
package cdc

import (
	"context"
	"database/sql"
	"encoding/json"
	"fmt"
	"math/rand"
	"time"
	
	_ "github.com/go-sql-driver/mysql"
)

// FlinkCDCSource 模拟 Flink CDC 的 MySQL Source
type FlinkCDCSource struct {
	db          *sql.DB
	database    string
	tables      []string
	splitSize   int64
	startupMode StartupMode
}

// StartupMode 启动模式
type StartupMode int

const (
	StartupInitial StartupMode = iota
	StartupLatest
	StartupTimestamp
	StartupSpecific
)

// ChangeEvent 变更事件（Debezium JSON 格式）
type ChangeEvent struct {
	Source   SourceInfo      `json:"source"`
	Op       OperationType   `json:"op"`
	TsMs     int64           `json:"ts_ms"`
	Before   json.RawMessage `json:"before,omitempty"`
	After    json.RawMessage `json:"after,omitempty"`
	Schema   *SchemaChange   `json:"schema,omitempty"`
}

// OperationType 操作类型
type OperationType string

const (
	OpCreate OperationType = "c"
	OpRead   OperationType = "r"
	OpUpdate OperationType = "u"
	OpDelete OperationType = "d"
	OpToast  OperationType = "T" // blob 数据被截断
)

// SourceInfo 源信息
type SourceInfo struct {
	Version  string `json:"version"`
	Server   string `json:"server"`
	DB       string `json:"db"`
	Table    string `json:"table"`
	TsMS     int64  `json:"ts_ms"`
	File     string `json:"file"`
	Pos      int64  `json:"pos"`
	GTID     string `json:"gtid,omitempty"`
	ThreadID int    `json:"thread_id,omitempty"`
}

// NewFlinkCDCSource 创建 CDC Source
func NewFlinkCDCSource(dsn, database string, tables []string, splitSize int64, mode StartupMode) *FlinkCDCSource {
	db, err := sql.Open("mysql", dsn)
	if err != nil {
		panic(fmt.Sprintf("open mysql: %v", err))
	}
	db.SetMaxIdleConns(5)
	db.SetMaxOpenConns(10)
	return &FlinkCDCSource{
		db:          db,
		database:    database,
		tables:      tables,
		splitSize:   splitSize,
		startupMode: mode,
	}
}

// Start 启动 CDC 读取
func (s *FlinkCDCSource) Start(ctx context.Context, handler EventHandler) error {
	switch s.startupMode {
	case StartupInitial:
		if err := s.snapshot(ctx, handler); err != nil {
			return fmt.Errorf("snapshot: %w", err)
		}
		fallthrough
	case StartupLatest, StartupTimestamp, StartupSpecific:
		return s.stream(ctx, handler)
	default:
		return fmt.Errorf("unknown startup mode: %d", s.startupMode)
	}
}

// snapshot 全量快照
func (s *FlinkCDCSource) snapshot(ctx context.Context, handler EventHandler) error {
	for _, table := range s.tables {
		if err := s.snapshotTable(ctx, table, handler); err != nil {
			return err
		}
	}
	return nil
}

func (s *FlinkCDCSource) snapshotTable(ctx context.Context, table string, handler EventHandler) error {
	query := fmt.Sprintf("SELECT * FROM %s", table)
	rows, err := s.db.QueryContext(ctx, query)
	if err != nil {
		return fmt.Errorf("query table %s: %w", table, err)
	}
	defer rows.Close()

	columns, err := rows.Columns()
	if err != nil {
		return err
	}

	types, err := s.getColumnTypes(ctx, table)
	if err != nil {
		return err
	}

	count := int64(0)
	for rows.Next() {
		values := make([]interface{}, len(columns))
		valuePtrs := make([]interface{}, len(columns))
		for i := range values {
			valuePtrs[i] = &values[i]
		}

		if err := rows.Scan(valuePtrs...); err != nil {
			return fmt.Errorf("scan row: %w", err)
		}

		after := make(map[string]interface{})
		for i, col := range columns {
			after[col] = s.convertValue(values[i], types[col])
		}

		event := ChangeEvent{
			Source: SourceInfo{
				DB:     s.database,
				Table:  table,
				TsMS:   time.Now().UnixMilli(),
			},
			Op:   OpRead,
			TsMs: time.Now().UnixMilli(),
			After: marshalJSON(after),
		}

		if err := handler.Handle(ctx, event); err != nil {
			return fmt.Errorf("handle event: %w", err)
		}

		count++
		if count%s.splitSize == 0 {
			fmt.Printf("snapshot progress: %s (%d rows)\n", table, count)
		}
	}

	fmt.Printf("snapshot complete: %s (%d rows)\n", table, count)
	return rows.Err()
}

func (s *FlinkCDCSource) stream(ctx context.Context, handler EventHandler) error {
	reader := NewBinlogReader(s.db, s.database)
	return reader.Start(ctx, func(event BinlogEvent) error {
		changeEvent := s.binlogToChangeEvent(event)
		return handler.Handle(ctx, changeEvent)
	})
}

func (s *FlinkCDCSource) getColumnTypes(ctx context.Context, table string) (map[string]int, error) {
	types := make(map[string]int)
	rows, err := s.db.QueryContext(ctx, fmt.Sprintf("DESCRIBE %s", table))
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	for rows.Next() {
		var field, typ, null, key, def string
		var extra sql.NullString
		if err := rows.Scan(&field, &typ, &null, &key, &def, &extra); err != nil {
			return nil, err
		}
		types[field] = mysqlTypeToInt(typ)
	}
	return types, nil
}

func (s *FlinkCDCSource) convertValue(val interface{}, colType int) interface{} {
	if val == nil {
		return nil
	}
	switch v := val.(type) {
	case []byte:
		if colType == TYPE_LONG_BLOB || colType == TYPE_MEDIUM_BLOB {
			return string(v)
		}
		return v
	case time.Time:
		return v.UnixMilli()
	default:
		return v
	}
}

// EventHandler 变更事件处理器接口
type EventHandler interface {
	Handle(ctx context.Context, event ChangeEvent) error
}

// MultiEventHandler 多处理器
type MultiEventHandler struct {
	handlers []EventHandler
	mu       sync.Mutex
}

func (m *MultiEventHandler) Add(h EventHandler) {
	m.mu.Lock()
	defer m.mu.Unlock()
	m.handlers = append(m.handlers, h)
}

func (m *MultiEventHandler) Handle(ctx context.Context, event ChangeEvent) error {
	m.mu.Lock()
	defer m.mu.Unlock()
	for _, h := range m.handlers {
		if err := h.Handle(ctx, event); err != nil {
			return err
		}
	}
	return nil
}

// ClickHouseSink 变更事件写入 ClickHouse（批量 + 幂等）
type ClickHouseSink struct {
	db      *sql.DB
	batch   []*ChangeEvent
	bufSize int
	mu      sync.Mutex
}

func NewClickHouseSink(dsn string, bufSize int) (*ClickHouseSink, error) {
	db, err := sql.Open("clickhouse", dsn)
	if err != nil {
		return nil, err
	}
	return &ClickHouseSink{db: db, bufSize: bufSize}, nil
}

func (s *ClickHouseSink) Handle(ctx context.Context, event ChangeEvent) error {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.batch = append(s.batch, &event)
	if len(s.batch) >= s.bufSize {
		return s.flush(ctx)
	}
	return nil
}

func (s *ClickHouseSink) flush(ctx context.Context) error {
	if len(s.batch) == 0 {
		return nil
	}
	insert := "INSERT INTO ad_changes (gtid, op, db, tbl, ts_ms, before_json, after_json) VALUES"
	args := []interface{}{}
	for i, evt := range s.batch {
		if i > 0 {
			insert += ","
		}
		insert += "(?,?,?,?,?,?,?)"
		args = append(args, evt.Source.GTID, string(evt.Op), evt.Source.DB,
			evt.Source.Table, evt.TsMs, string(evt.Before), string(evt.After))
	}
	_, err := s.db.ExecContext(ctx, insert, args...)
	if err != nil {
		return fmt.Errorf("flush to ClickHouse: %w", err)
	}
	s.batch = s.batch[:0]
	return nil
}

func marshalJSON(v interface{}) json.RawMessage {
	b, _ := json.Marshal(v)
	return b
}

```
---

## 第五部分：Flink Checkpoint 与 Exactly-Once

### Flink Checkpoint 流程（CDC 场景）

```
┌─────────────────────────────────────────────────────────────┐
│                    Flink Job Manager                         │
│                                                              │
│  1. Trigger Checkpoint (每 10s)                              │
│     CheckpointBarrier ──▶ Source ──▶ Map ──▶ Sink           │
│                                                              │
│  2. Source 对齐（Barrier Alignment）                         │
│     - MySQL binlog position 快照                             │
│     - 暂停读取直到 barrier 到达                               │
│     - 记录 checkpoint ID → binlog position 映射              │
│                                                              │
│  3. Sink 预提交（Two-Phase Commit）                          │
│     - Pre-commit: 写入临时表 / 标记 pending                   │
│     - Commit: barrier 全部到达后正式提交                      │
│     - Abort: 超时则回滚                                       │
│                                                              │
│  4. Checkpoint 完成                                          │
│     - Job Manager 确认所有 operator 对齐                      │
│     - 持久化 checkpoint metadata 到 State Backend            │
│     - 触发 Sink 正式 commit                                   │
└─────────────────────────────────────────────────────────────┘
```

### Two-Phase Commit Sink 实现

```go
package cdc

import (
	"context"
	"database/sql"
	"fmt"
	"math/rand"
	"time"
)

// TwoPhaseCommitSink 两阶段提交 Sink
type TwoPhaseCommitSink struct {
	db          *sql.DB
	pendingMaps map[string]string // txnID → tempTableName
}

func NewTwoPhaseCommitSink(db *sql.DB) *TwoPhaseCommitSink {
	return &TwoPhaseCommitSink{
		db:          db,
		pendingMaps: make(map[string]string),
	}
}

// BeginTransaction 开启事务（预提交）
func (s *TwoPhaseCommitSink) BeginTransaction(ctx context.Context) (string, error) {
	tx, err := s.db.BeginTx(ctx, nil)
	if err != nil {
		return "", err
	}

	txnID := fmt.Sprintf("txn_%d_%d", time.Now().UnixNano(), rand.Intn(100000))
	tableName := "_cdc_pending_" + txnID

	_, err = tx.ExecContext(ctx,
		"CREATE TEMPORARY TABLE IF NOT EXISTS "+tableName+" LIKE ad_changes")
	if err != nil {
		tx.Rollback()
		return "", err
	}
	tx.Commit()

	s.pendingMaps[txnID] = tableName
	return txnID, nil
}

// PreCommit 预提交（写入临时表）
func (s *TwoPhaseCommitSink) PreCommit(ctx context.Context, txnID string, events []ChangeEvent) error {
	tableName := s.pendingMaps[txnID]
	if tableName == "" {
		return fmt.Errorf("unknown txn: %s", txnID)
	}

	for _, evt := range events {
		_, err := s.db.ExecContext(ctx,
			"INSERT INTO "+tableName+" (gtid, op, db, tbl, ts_ms, before_json, after_json)"+
				" VALUES (?, ?, ?, ?, ?, ?, ?)",
			evt.Source.GTID, string(evt.Op), evt.Source.DB, evt.Source.Table,
			evt.TsMs, string(evt.Before), string(evt.After),
		)
		if err != nil {
			return err
		}
	}
	return nil
}

// Commit 正式提交（从临时表 MERGE 到主表）
func (s *TwoPhaseCommitSink) Commit(ctx context.Context, txnID string) error {
	tableName := s.pendingMaps[txnID]
	delete(s.pendingMaps, txnID)

	_, err := s.db.ExecContext(ctx,
		"INSERT INTO ad_changes (gtid, op, db, tbl, ts_ms, before_json, after_json)"+
			" SELECT gtid, op, db, tbl, ts_ms, before_json, after_json"+
			" FROM "+tableName+
			" ON DUPLICATE KEY UPDATE op = VALUES(op), db = VALUES(db),"+
			" tbl = VALUES(tbl), ts_ms = VALUES(ts_ms),"+
			" before_json = VALUES(before_json), after_json = VALUES(after_json)")

	if err != nil {
		return fmt.Errorf("commit txn %s: %w", txnID, err)
	}

	s.db.ExecContext(ctx, "DROP TABLE IF EXISTS "+tableName)
	return nil
}

// Abort 中止事务
func (s *TwoPhaseCommitSink) Abort(ctx context.Context, txnID string) error {
	tableName := s.pendingMaps[txnID]
	delete(s.pendingMaps, txnID)
	_, err := s.db.ExecContext(ctx, "DROP TABLE IF EXISTS "+tableName)
	return err
}

```

---

## 第六部分：PostgreSQL WAL CDC

### PostgreSQL 与 MySQL CDC 的区别

```
MySQL (binlog) vs PostgreSQL (WAL)：

┌─────────────────┬──────────────────────┬──────────────────────┐
│     特性         │   MySQL Binlog       │   PostgreSQL WAL     │
├─────────────────┼──────────────────────┼──────────────────────┤
│ 日志格式         │  自定义二进制格式     │  自定义二进制格式     │
│ 解析复杂度       │  中等                │  较高（Logical       │
│                 │                      │  Decoding）          │
│ 插件机制         │  无                  │  decoding plugin     │
│                 │                      │  (pgoutput/wal2json) │
│ 事务边界         │  Xid Event           │  BEGIN/COMMIT        │
│                 │                      │  Record              │
│ 并发控制         │  ROW_FORMAT=ROW      │  Replication Slot    │
│                 │                      │  + xmin              │
│ 断点续传         │  GTID / Position     │  LSN (Log Sequence   │
│                 │                      │  Number)             │
│ 性能影响         │  ~5-10%              │  ~2-5% (wal_level=   │
│                 │                      │  logical)            │
└─────────────────┴──────────────────────┴──────────────────────┘

PostgreSQL 配置：
  wal_level = logical          # 必须设置为 logical
  max_replication_slots = 10   # 最多 10 个 replication slot
  max_wal_senders = 10         # 最多 10 个 WAL sender
  wal_keep_size = 1GB          # 保留的 WAL 大小
```

### PostgreSQL Logical Decoding

```
WAL → Logical Decoding → Change Events

┌─────────────────────────────────────────────────────────┐
│ PostgreSQL Server                                        │
│                                                          │
│  ┌──────────┐    ┌──────────────────┐                   │
│  │ WAL File │───▶│ Logical Decoder  │                   │
│  │ (pg_wal) │    │ (pgoutput plugin)│                   │
│  └──────────┘    └───────┬──────────┘                   │
│                          │                               │
│                  ┌───────▼──────────┐                   │
│                  │  Replication     │                   │
│                  │  Slot            │                   │
│                  │  (物理 + 逻辑)    │                   │
│                  └───────┬──────────┘                   │
│                          │                               │
│                  ┌───────▼──────────┐                   │
│                  │  Streaming       │                   │
│                  │  to Debezium     │                   │
│                  └──────────────────┘                   │
└─────────────────────────────────────────────────────────┘

Logical Decoder 输出格式（pgoutput）：
  BEGIN 48923
    table public.impressions: INSERT: (id=[12345], campaign_id=[678],
      platform=[facebook], creative_id=[abc], ts=[2024-07-14 10:00:00])
    table public.impressions: UPDATE: id=[12345] NEW:
      (id=[12345], campaign_id=[678], platform=[google],
       creative_id=[def], ts=[2024-07-14 10:00:01])
    table public.clicks: INSERT: (id=[99999], impression_id=[12345],
      user_id=[555], ts=[2024-07-14 10:00:02])
  COMMIT 48923
```

### Go 实现 PostgreSQL WAL Consumer

```go
package cdc

import (
	"context"
	"database/sql"
	"fmt"
	"time"

	_ "github.com/lib/pq"
)

// PGWALConsumer PostgreSQL WAL 消费者
type PGWALConsumer struct {
	db              *sql.DB
	slotName        string
	plugin          string // pgoutput
	startLSN        string
	currentLSN      string
	notificationCh  chan PGChangeEvent
}

// PGChangeEvent PostgreSQL 变更事件
type PGChangeEvent struct {
	EventType  PGEventType
	Schema     string
	Table      string
	ColumnNames []string
	OldValues  []interface{}
	NewValues  []interface{}
	TxID       int64
	CommitLSN  string
	Ts         time.Time
}

// PGEventType 事件类型
type PGEventType string

const (
	PGInsert  PGEventType = "INSERT"
	PGUpdate  PGEventType = "UPDATE"
	PGDelete  PGEventType = "DELETE"
	PGBegin   PGEventType = "BEGIN"
	PGCommit  PGEventType = "COMMIT"
)

// NewPGWALConsumer 创建 WAL 消费者
func NewPGWALConsumer(dsn, slotName, plugin string) *PGWALConsumer {
	db, err := sql.Open("postgres", dsn)
	if err != nil {
		panic(err)
	}
	return &PGWALConsumer{
		db:             db,
		slotName:       slotName,
		plugin:         plugin,
		notificationCh: make(chan PGChangeEvent, 1000),
	}
}

// CreateReplicationSlot 创建 replication slot
func (c *PGWALConsumer) CreateReplicationSlot(ctx context.Context) error {
	var confirmedLSN string
	err := c.db.QueryRowContext(ctx,
		`SELECT pg_create_logical_replication_slot($1, $2, false)
		 AS confirmed_lsn`,
		c.slotName, c.plugin,
	).Scan(&confirmedLSN)
	if err != nil {
		// slot 已存在
		return nil
	}
	c.currentLSN = confirmedLSN
	return nil
}

// StartStreaming 开始流式复制
func (c *PGWALConsumer) StartStreaming(ctx context.Context) error {
	if c.currentLSN == "" {
		// 获取现有 slot 的 lsn
		var lsn string
		err := c.db.QueryRowContext(ctx,
			`SELECT confirmed_lsn FROM pg_replication_slots
			 WHERE slot_name = $1`, c.slotName).Scan(&lsn)
		if err != nil {
			return fmt.Errorf("get slot lsn: %w", err)
		}
		c.currentLSN = lsn
	}

	// 使用 pg_recvlogical 或直接连接 replication 端口
	// 这里用 SQL 轮询方式（简化版）
	go c.pollChanges(ctx)
	return nil
}

// pollChanges 轮询变更（简化版，生产用 streaming replication）
func (c *PGWALConsumer) pollChanges(ctx context.Context) {
	ticker := time.NewTicker(100 * time.Millisecond)
	defer ticker.Stop()

	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
			c.pollOne(ctx)
		}
	}
}

func (c *PGWALConsumer) pollOne(ctx context.Context) {
	// 查询 pg_logical_slot_get_changes
	rows, err := c.db.QueryContext(ctx,
		`SELECT lsn, transaction_end_lsn, commit_time,
		        type, relation, data
		 FROM pg_logical_slot_get_changes($1, $2, NULL,
		        'include-xids', '0', 'include-timestamp', 'false')`,
		c.slotName, c.currentLSN)
	if err != nil {
		return
	}
	defer rows.Close()

	for rows.Next() {
		var lsn, rel, dataType string
		var txEndLSN sql.NullString
		var commitTime time.Time
		var data []byte

		if err := rows.Scan(&lsn, &txEndLSN, &commitTime, &dataType, &rel, &data); err != nil {
			continue
		}

		c.currentLSN = lsn

		// 解析 pgoutput 格式的 data
		event := c.parsePGOutput(rel, dataType, data)
		event.Ts = commitTime
		if txEndLSN.Valid {
			event.EventType = PGCommit
		}

		select {
		case c.notificationCh <- event:
		default:
			// buffer full, drop
		}
	}
}

func (c *PGWALConsumer) parsePGOutput(rel, dataType string, data []byte) PGChangeEvent {
	return PGChangeEvent{
		EventType:  PGEventType(dataType),
		Schema:     "public",
		Table:      rel,
		NewValues:  nil,
		OldValues:  nil,
		CommitLSN:  c.currentLSN,
	}
}

// GetNotificationChannel 获取变更通知通道
func (c *PGWALConsumer) GetNotificationChannel() <-chan PGChangeEvent {
	return c.notificationCh
}

```

---

## 第七部分：CDC 在广告系统的生产实践

### 广告数据管道 CDC 架构

```
完整广告 CDC 数据管道：

┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│  MySQL (主)   │    │  MySQL (从)   │    │  PostgreSQL  │
│  ad_platform  │    │  ad_platform  │    │  analytics   │
└──────┬───────┘    └──────┬───────┘    └──────┬───────┘
       │                   │                    │
       ▼                   ▼                    ▼
┌──────────────────────────────────────────────────────┐
│              Debezium Cluster                         │
│  ┌────────────┐ ┌────────────┐ ┌────────────┐       │
│  │ MySQL-1    │ │ MySQL-2    │ │ PG-1       │       │
│  │ Connector  │ │ Connector  │ │ Connector  │       │
│  └─────┬──────┘ └─────┬──────┘ └─────┬──────┘       │
└────────┼──────────────┼──────────────┼───────────────┘
         │              │              │
         ▼              ▼              ▼
┌──────────────────────────────────────────────────────┐
│                 Kafka Cluster                         │
│  ┌────────────────┐ ┌────────────────┐               │
│  │ dbserver1.imps │ │ dbserver1.click│               │
│  │ dbserver1.conv │ │ dbserver1.camp │               │
│  │ pgserver1.anly │ │              │                 │
│  └────────────────┘ └────────────────┘               │
└──────────────────────────┬───────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────┐
│               Flink Cluster                           │
│                                                       │
│  ┌───────────────────────────────────────────────┐   │
│  │ Flink Job: Ad Realtime Aggregation            │   │
│  │                                               │   │
│  │  Source (CDC) ──▶ Map ──▶ KeyBy ──▶ Window   │   │
│  │       │                                    │   │
│  │       ▼                                    │   │
│  │  TumblingWindow(1min)                      │   │
│  │  SUM(impressions), SUM(clicks),            │   │
│  │  COUNT(DISTINCT campaign_id)               │   │
│  │       │                                    │   │
│  │       ▼                                    │   │
│  │  Sink (Two-Phase Commit)                   │   │
│  └───────────────────────────────────────────────┘   │
└──────────────────────────┬───────────────────────────┘
                           │
              ┌────────────┼────────────┐
              ▼            ▼            ▼
       ┌──────────┐ ┌──────────┐ ┌──────────┐
       │ClickHouse│ │ Iceberg  │ │ Redis    │
       │ 实时看板  │ │ 数据湖   │ │ 缓存     │
       └──────────┘ └──────────┘ └──────────┘
```

### Debezium 性能调优

```
Debezium MySQL Connector 关键配置：

# 吞吐量优化
max.queue.size=16384          # 内存缓冲区大小（默认 8192）
max.batch.size=2048           # 每次批量发送的事件数（默认 2048）
poll.interval.ms=50           # 轮询间隔（默认 50ms）
buffer.memory=33554432        # 缓冲区内存（32MB，默认 10MB）

# 快照优化
snapshot.fetch.size=2048      # 每次 SELECT fetch 行数
snapshot.max.threads=8        # 并行快照线程数
snapshot.locking.mode=none    # 不加表锁（InnoDB 行级锁）

# Binlog 读取优化
connect.backoff.initial.delay=1000ms
connect.backoff.max.delay=60000ms
heartbeat.interval.ms=10000   # 心跳间隔

# Offset 提交优化
offset.flush.interval.ms=10000  # offset 刷新间隔（默认 60000ms）
offset.flush.timeout.ms=5000    # offset 刷新超时

# 广告系统推荐配置（高吞吐场景）：
max.queue.size=65536
max.batch.size=4096
poll.interval.ms=10
buffer.memory=134217728  # 128MB
snapshot.max.threads=16
snapshot.fetch.size=4096
```

### CDC 监控与告警

```go
package cdc

import (
	"context"
	"database/sql"
	"fmt"
	"time"
)

// CDCMonitor CDC 健康监控
type CDCMonitor struct {
	db              *sql.DB
	alertThreshold  time.Duration // lag 告警阈值
}

func NewCDCMonitor(db *sql.DB, threshold time.Duration) *CDCMonitor {
	return &CDCMonitor{
		db:             db,
		alertThreshold: threshold,
	}
}

// CheckLag 检查 CDC lag
func (m *CDCMonitor) CheckLag(ctx context.Context) ([]LagMetric, error) {
	var metrics []LagMetric

	// 1. 检查 Debezium connector lag
	lags, err := m.checkDebeziumLag(ctx)
	if err != nil {
		return nil, err
	}
	metrics = append(metrics, lags...)

	// 2. 检查 MySQL binlog lag
	binlogLag, err := m.checkBinlogLag(ctx)
	if err != nil {
		return nil, err
	}
	metrics = append(metrics, binlogLag)

	// 3. 检查 Kafka consumer lag
	kafkaLag, err := m.checkKafkaConsumerLag(ctx)
	if err != nil {
		return nil, err
	}
	metrics = append(metrics, kafkaLag...)

	return metrics, nil
}

type LagMetric struct {
	Component string
	Table     string
	Lag       time.Duration
	Severity  string // info, warning, critical
}

func (m *CDCMonitor) checkDebeziumLag(ctx context.Context) ([]LagMetric, error) {
	var metrics []LagMetric

	rows, err := m.db.QueryContext(ctx, `
		SELECT server_name, source_file, source_pos,
		       COALESCE(source_gtid, '') as gtid,
		       UNIX_TIMESTAMP(NOW()) * 1000 - last_ts as lag_ms
		FROM debezium_offsets
		ORDER BY lag_ms DESC
	`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	for rows.Next() {
		var name, file, gtid string
		var pos int64
		var lagMs int64

		if err := rows.Scan(&name, &file, &pos, &gtid, &lagMs); err != nil {
			continue
		}

		severity := "info"
		if lagMs > int64(m.alertThreshold) {
			severity = "critical"
		} else if lagMs > int64(m.alertThreshold)/2 {
			severity = "warning"
		}

		metrics = append(metrics, LagMetric{
			Component: "debezium",
			Table:     name,
			Lag:       time.Duration(lagMs) * time.Millisecond,
			Severity:  severity,
		})
	}

	return metrics, nil
}

func (m *CDCMonitor) checkBinlogLag(ctx context.Context) LagMetric {
	var currentPos string
	var readPos string

	m.db.QueryRowContext(ctx, "SHOW MASTER STATUS").Scan(
		&currentPos, &readPos,
	)

	// 计算 binlog position 差异
	return LagMetric{
		Component: "binlog",
		Lag:       0, // 简化：实际应比较 timestamp
		Severity:  "info",
	}
}

func (m *CDCMonitor) checkKafkaConsumerLag(ctx context.Context) ([]LagMetric, error) {
	// 实际应调用 Kafka Admin API
	// 这里简化为 placeholder
	return []LagMetric{}, nil
}

// Alert 发送告警
func (m *CDCMonitor) Alert(ctx context.Context, metric LagMetric) {
	if metric.Severity == "info" {
		return
	}
	fmt.Printf("[ALERT] %s: %s lag=%s severity=%s\n",
		metric.Component, metric.Table, metric.Lag, metric.Severity)
}

```
---

## 第八部分：自测题

### Q1：CDC 的 Exactly-Once 如何保证？

**答：** CDC 的 EO 是一个链条，每一步都要保证：

1. **MySQL → Debezium**：offset 持久化到 MySQL/Kafka，崩溃后从上次 position 恢复
2. **Debezium → Kafka**：Kafka partition 有序，producer 批量发送 + ack=all
3. **Kafka → Flink**：Flink checkpoint 机制，barrier alignment 保证算子对齐
4. **Flink → Sink**：Two-Phase Commit，pre-commit 到临时表，commit 时 MERGE

关键点：**GTID 作为幂等键**。每条变更都有唯一的 GTID，sink 端使用 INSERT ... ON DUPLICATE KEY UPDATE 保证幂等。

### Q2：MySQL binlog 是全局有序的吗？

**答：** 是的，InnoDB 的 binlog 是全局有序的。

- MySQL 服务端只有一个 binlog writer 线程
- 所有事务的变更都按 commit 顺序写入同一个 binlog 文件
- 即使多表并发写入，binlog position 也严格递增
- 这意味着：从 binlog 重放的变更顺序与原始 commit 顺序完全一致

**但是**，如果使用了多源复制（multi-source replication），不同 master 的 binlog 之间没有全局顺序。

### Q3：Snapshot 和 Incremental 阶段如何无缝衔接？

**答：** 关键在于 **binlog position 的记录时机**：

```
时间线：
T0: Debezium 启动
T1: 开始 snapshot，记录 binlog position P1
T2: snapshot 完成（读取了所有存量数据）
T3: 切换到 binlog 读取，从 position P1 继续
T4: 业务在 T1-T3 期间产生了新的变更 → binlog 中已有记录
T5: Debezium 从 P1 读取到这些增量变更 → 补上快照期间的数据

关键：snapshot 完成后、切换到 binlog 之前，必须记录当前的 binlog position
Debezium 在 snapshot 完成后立即读取当前的 binlog position，确保不会遗漏
```

---

## 第九部分：与知识库的对照

### 已有内容

| 文件 | 覆盖情况 | 说明 |
|------|---------|------|
| `bigdata/ad-bigdata-lakehouse-iceberg-realtime-deep.md` | 部分 | 提到 Iceberg 但不涉及 CDC 源 |
| `bigdata/big-data-architecture-deep.md` | 部分 | 提到 Hadoop/Spark/Flink 但不涉及 CDC |
| `bigdata/ad-bigdata-lake-flink-governance-deep.md` | 少量 | 仅 1 处提及 CDC |
| `bigdata/data-warehouse-deep.md` | 少量 | 仅 1 处提及 CDC |
| `advertising/mysql-innodb-source-deep.md` | 部分 | 有 binlog 相关内容 |
| `fullstack/weread-programmer-to-architect-deep.md` | 少量 | 提到 CDC 概念 |

### 本文件补充的内容

1. **CDC 全景架构**：从 MySQL binlog → Debezium → Kafka → Flink → ClickHouse 的完整链路
2. **Binlog 源码级解析**：Go 实现的 Binlog Parser，包括 header 解析、rows event 解码
3. **Debezium 深度**：配置详解、snapshot 机制、offset 管理、并行快照实现
4. **Flink CDC**：与 Kafka Connect 架构对比、Flink CDC Source 实现、Two-Phase Commit Sink
5. **PostgreSQL WAL CDC**：与 MySQL 对比、Logical Decoding、pgoutput 插件
6. **广告系统实践**：完整的广告 CDC 数据管道架构、性能调优参数、监控告警
7. **Exactly-Once 保证链**：从 binlog 到 sink 的完整 EO 保证分析

### 缺失内容（下一步可扩展）

1. **Kafka Connect 源码级**：connector 生命周期、task 分配、rebalance
2. **Debezium DDL 处理**：schema evolution 的具体实现
3. **CDC 性能基准测试**：不同配置下的 TPS/Latency 对比数据
4. **Flink State Backend 选择**：RocksDB vs Memory 在 CDC 场景下的差异
