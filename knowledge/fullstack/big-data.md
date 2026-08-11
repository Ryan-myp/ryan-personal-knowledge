# Big Data 深度解析 — 从架构到实战

> 本文档深入解析大数据技术栈：Hadoop、Spark、Flink、Kafka 的架构原理、核心算法和实战经验。
> 适用对象：大数据工程师、数据平台架构师、后端工程师

---

## 1. 大数据技术栈概览

### 1.1 技术选型矩阵

```
┌─────────────────────────────────────────────────────────────────────┐
│                      大数据技术栈                                    │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  批处理          流处理          存储          计算引擎      调度    │
│  ┌─────────┐   ┌─────────┐   ┌─────────┐  ┌─────────┐   ┌──────┐  │
│  │  Hadoop │   │  Spark  │   │  HDFS   │  │  Spark  │   │Airflow│ │
│  │  MapReduce│   │  Batch  │   │  S3     │  │  Flink  │   │Azkaban│ │
│  └─────────┘   └─────────┘   └─────────┘  └─────────┘   └──────┘  │
│                                                                     │
│  数据仓库        数据湖          查询引擎      消息队列      调度    │
│  ┌─────────┐   ┌─────────┐   ┌─────────┐  ┌─────────┐   ┌──────┐  │
│  │ Hive    │   │ Iceberg │   │ Presto  │  │  Kafka  │   │ Luigi│  │
│  │ SparkSQL│   │ Hudi    │   │ Trino   │  │  Pulsar │   └──────┘  │
│  └─────────┘   └─────────┘   └─────────┘  └─────────┘             │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### 1.2 技术对比

| 场景 | 推荐技术 | 说明 |
|------|----------|------|
| 离线批处理 | Spark | 生态完善，API 友好 |
| 实时流处理 | Flink | 低延迟，Exactly-Once |
| 交互查询 | Presto/Trino | 即席查询，亚秒级响应 |
| 消息队列 | Kafka | 高吞吐，持久化 |
| 数据湖 | Iceberg/Hudi | ACID 事务，时序回溯 |

---

## 2. Hadoop 核心原理

### 2.1 HDFS 架构

```
┌─────────────────────────────────────────────────────────────────────┐
│                        HDFS 架构                                    │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│                    ┌─────────────┐                                  │
│                    │   NameNode  │  (主节点，管理元数据)               │
│                    │  (Metadata) │                                  │
│                    └──────┬──────┘                                  │
│                           │                                         │
│         ┌─────────────────┼─────────────────┐                       │
│         │                 │                 │                       │
│  ┌──────▼──────┐  ┌──────▼──────┐  ┌──────▼──────┐                 │
│  │ DataNode 1  │  │ DataNode 2  │  │ DataNode 3  │                 │
│  │  (Block 存储)│  │  (Block 存储)│  │  (Block 存储)│                 │
│  └─────────────┘  └─────────────┘  └─────────────┘                 │
│                                                                     │
│  关键特性：                                                          │
│  - Block Size: 默认 128MB                                           │
│  - 副本策略: 本地机架优先 (3副本)                                     │
│  - 写流程: Client → NN → DN1 → DN2 → DN3                           │
│  - 读流程: Client ← DN (就近读取)                                    │
└─────────────────────────────────────────────────────────────────────┘
```

### 2.2 MapReduce 原理

```go
// MapReduce 核心接口
type Mapper interface {
    Map(key, value []byte, context Context)
}

type Reducer interface {
    Reduce(key []byte, values [][]byte, context Context)
}

// WordCount 示例
type WordCountMapper struct{}

func (m *WordCountMapper) Map(key, value []byte, ctx Context) {
    words := strings.Fields(string(value))
    for _, word := range words {
        ctx.Emit([]byte(word), []byte("1"))
    }
}

type WordCountReducer struct{}

func (r *WordCountReducer) Reduce(key []byte, values [][]byte, ctx Context) {
    count := 0
    for _, v := range values {
        count += parseInt(string(v))
    }
    ctx.Emit(key, []byte(strconv.Itoa(count)))
}
```

### 2.3 Shuffle 过程

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Shuffle 过程                                  │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  Map 阶段                    Shuffle                     Reduce 阶段 │
│  ┌─────────┐              ┌─────────┐                 ┌─────────┐  │
│  │ Map 1   │──┐        ┌──▼──┐      │                 │ Reduce 1│  │
│  │ Map 2   │──┤  Sort ├──►│ Buff│────┤ Sort &  ────►│ Reduce 2│  │
│  │ Map 3   │──┘        └──▲──┘      │  Merge        └─────────┘  │
│  └─────────┘              │         │                             │
│        │                  │         │                             │
│        └──────────────────┘         │                             │
│                                   └───────────────────────────────┘
│
│  关键优化：
│  - Spill: 内存数据写到磁盘
│  - Combiner: Map 端预聚合
│  - Partition: 按 Key 分区
└─────────────────────────────────────────────────────────────────────┘
```

---

## 3. Spark 核心原理

### 3.1 架构图

```
┌─────────────────────────────────────────────────────────────────────┐
│                      Spark 架构                                      │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                     Driver Program                          │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │   │
│  │  │  SQL        │  │  Streaming  │  │  MLlib      │         │   │
│  │  │  Analyzer   │  │  Processor  │  │  Algorithm  │         │   │
│  │  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘         │   │
│  │         └─────────────────┼─────────────────┘                │   │
│  │                          │                                   │   │
│  │                   ┌──────▼──────┐                           │   │
│  │                   │  DAG       │                           │   │
│  │                   │  Scheduler │                           │   │
│  │                   └──────┬──────┘                           │   │
│  │                          │                                   │   │
│  └──────────────────────────┼──────────────────────────────────┘   │
│                              │                                      │
│                 ┌────────────▼────────────┐                       │
│                 │     Cluster Manager     │                       │
│                 │  (YARN/K8s/Standalone)  │                       │
│                 └────────────┬────────────┘                       │
│                              │                                      │
│         ┌────────────────────┼────────────────────┐               │
│         │                    │                    │               │
│  ┌──────▼──────┐     ┌──────▼──────┐     ┌──────▼──────┐         │
│  │  Executor 1 │     │  Executor 2 │     │  Executor N │         │
│  │  (JVM)      │     │  (JVM)      │     │  (JVM)      │         │
│  │  - Task     │     │  - Task     │     │  - Task     │         │
│  │  - Block    │     │  - Block    │     │  - Block    │         │
│  │  - Shuffle  │     │  - Shuffle  │     │  - Shuffle  │         │
│  └─────────────┘     └─────────────┘     └─────────────┘         │
└─────────────────────────────────────────────────────────────────────┘
```

### 3.2 RDD 原理

```go
// RDD（弹性分布式数据集）核心接口
type RDD[T any] interface {
    // 分区
    Partitions() []Partition
    
    // 计算分区数据
    Compute(partition Partition, context TaskContext) Iterator[T]
    
    // 依赖关系
    Dependencies() []Dependency
    
    // 缓存
    Cache() *RDD[T]
    
    // 持久化级别
    Persist(level StorageLevel) *RDD[T]
}

// 持久化级别
type StorageLevel struct {
    Disk     bool
    Memory   bool
    OffHeap  bool
    Replicated int
}

const (
    MEMORY_ONLY      = StorageLevel{Memory: true}
    MEMORY_AND_DISK  = StorageLevel{Memory: true, Disk: true}
    DISK_ONLY        = StorageLevel{Disk: true}
)
```

### 3.3 Catalyst 优化器

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Catalyst 优化器流程                              │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  1. Parse         2. Analysis       3. Logical Plan                │
│  SQL String  ──►  AST         ──►   Optimized Plan                 │
│      │             │                  │                             │
│      │             │              (规则优化)                         │
│      │             │                  │                             │
│  4. Planning      5. Physical Plan    6. Code Gen                   │
│      │             │                  │                             │
│      └─────────────┴──────────────────┘                             │
│                         │                                            │
│                    Execution Plan                                    │
│                                                                     │
│  优化规则示例：                                                       │
│  - Predicate Pushdown                                               │
│  - Column Pruning                                                   │
│  - Constant Folding                                                 │
│  - Join Reordering                                                  │
└─────────────────────────────────────────────────────────────────────┘
```

### 3.4 Tungsten 执行引擎

```go
// Tungsten 核心优化
type TungstenExecution struct {
    // 1. 内存管理
    memoryManager *MemoryManager
    
    // 2. 二进制格式
    serializer *BinarySerializer
    
    // 3. 代码生成
    codeGen *CodeGenerator
}

// 代码生成示例
func (t *TungstenExecution) GenerateCode(plan PhysicalPlan) []byte {
    // 将物理计划编译为 Java/Scala 字节码
    // 避免对象开销，直接操作堆外内存
    return t.codeGen.Compile(plan)
}
```

---

## 4. Flink 核心原理

### 4.1 架构图

```
┌─────────────────────────────────────────────────────────────────────┐
│                      Flink 架构                                      │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                     JobManager                              │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │   │
│  │  │  Dispatcher │  │  ResourceManager │  │  JobManager │         │   │
│  │  └─────────────┘  └─────────────┘  └─────────────┘         │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                           │                                          │
│         ┌─────────────────┼─────────────────┐                      │
│         │                 │                 │                       │
│  ┌──────▼──────┐  ┌──────▼──────┐  ┌──────▼──────┐                │
│  │  TaskManager│  │  TaskManager│  │  TaskManager│                │
│  │    (Slot 0) │  │    (Slot 1) │  │    (Slot N) │                │
│  │  ┌───────┐  │  │  ┌───────┐  │  │  ┌───────┐  │                │
│  │  │Task 1 │  │  │  │Task 2 │  │  │  │Task N │  │                │
│  │  │Task 2 │  │  │  │Task 3 │  │  │  │Task 4 │  │                │
│  │  └───────┘  │  │  └───────┘  │  │  └───────┘  │                │
│  └─────────────┘  └─────────────┘  └─────────────┘                │
└─────────────────────────────────────────────────────────────────────┘
```

### 4.2 状态管理

```go
type StateBackend interface {
    // 创建状态
    CreateState(ctx Context, name string) State
    
    // 提交事务
    Commit(transaction Transaction) error
    
    // 快照
    Snapshot(checkpointID uint64) error
    
    // 恢复
    Restore(checkpointID uint64) error
}

// RocksDB State Backend
type RocksDBStateBackend struct {
    db       *badger.DB
    options  badger.Options
}

func (r *RocksDBStateBackend) CreateState(ctx Context, name string) State {
    key := fmt.Sprintf("%s:%s", ctx.taskID, name)
    return &RocksDBState{
        db:    r.db,
        key:   key,
        value: nil,
    }
}
```

### 4.3 背压机制

```go
type Backpressure struct {
    samplingEnabled bool
    interval        time.Duration
}

func (b *Backpressure) Sample(channel Channel) BackpressureStats {
    // 监控每个 channel 的背压
    stats := BackpressureStats{
        inputRate:   channel.InputRate(),
        outputRate:  channel.OutputRate(),
        queueSize:   channel.QueueSize(),
        utilization: channel.Utilization(),
    }
    return stats
}

// 背压可视化
func (b *Backpressure) Visualize() string {
    // 在 Web UI 中显示每个算子的背压情况
    return fmt.Sprintf("Input: %.2f req/s, Output: %.2f req/s", 
        b.stats.inputRate, b.stats.outputRate)
}
```

---

## 5. Kafka 核心原理

### 5.1 架构

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Kafka 架构                                    │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐            │
│  │  Producer 1 │    │  Producer 2 │    │  Producer N │            │
│  └──────┬──────┘    └──────┬──────┘    └──────┬──────┘            │
│         │                  │                  │                    │
│         └──────────────────┼──────────────────┘                    │
│                            │                                        │
│                    ┌───────▼───────┐                               │
│                    │   Broker 1    │  ───┐                       │
│                    │  (Topic A)    │     │                       │
│                    └───────┬───────┘     │                       │
│                            │             │                        │
│                    ┌───────▼───────┐    │                        │
│                    │   Broker 2    │  ───┤                        │
│                    │  (Topic B)    │     │                        │
│                    └───────┬───────┘     │                        │
│                            │             │                        │
│                    ┌───────▼───────┐    │                        │
│                    │   Broker 3    │  ───┘                       │
│                    │  (Topic C)    │                             │
│                    └───────┬───────┘                             │
│                            │                                      │
│         ┌──────────────────┼──────────────────┐                  │
│         │                  │                  │                  │
│  ┌──────▼──────┐  ┌───────▼──────┐  ┌───────▼──────┐            │
│  │  Consumer 1 │  │  Consumer 2  │  │  Consumer 3  │            │
│  └─────────────┘  └─────────────┘  └─────────────┘            │
│                                                                     │
│  ZooKeeper / KRaft 集群                                            │
└─────────────────────────────────────────────────────────────────────┘
```

### 5.2 持久化机制

```go
type Log struct {
    dir       string              // 日志目录
    segments  []*Segment          // 段文件
    baseOffset int64              // 基础偏移量
    maxOffset  int64              // 最大偏移量
}

type Segment struct {
    baseOffset int64
    index      *Index            // 偏移量索引
    data       *Index          // 消息索引
    lock       sync.RWMutex
}

// 零拷贝传输
func (s *Segment) TransferTo(client *Client, offset int64, maxSize int) ([]byte, error) {
    // sendfile() 系统调用，内核态直接传输
    return syscall.Sendfile(client.fd, s.fd, &offset, maxSize)
}
```

---

## 6. 性能优化

### 6.1 Spark 优化

```sql
-- 1. 数据倾斜优化
SET spark.sql.adaptive.enabled=true;
SET spark.sql.adaptive.coalescePartitions.enabled=true;

-- 2. 内存优化
SET spark.memory.fraction=0.6;
SET spark.memory.storageFraction=0.3;

-- 3. 并行度优化
SET spark.sql.shuffle.partitions=200;
```

### 6.2 Flink 优化

```yaml
# flink-conf.yaml
taskmanager.numberOfTaskSlots: 8
parallelism.default: 16
state.backend: rocksdb
state.checkpoints.dir: hdfs:///checkpoints
execution.checkpointing.interval: 60000
execution.checkpointing.timeout: 600000
```

### 6.3 Kafka 优化

```properties
# broker 配置
num.partitions=12
replication.factor=3
log.retention.hours=168
log.segment.bytes=1073741824

# producer 配置
acks=all
retries=3
batch.size=16384
linger.ms=5
compression.type=lz4

# consumer 配置
max.poll.records=500
fetch.min.bytes=1048576
fetch.max.wait.ms=500
```

---

## 7. 实战案例

### 7.1 实时数仓架构

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   业务 DB   │───►│   Canal     │───►│   Kafka     │
│  (MySQL)    │    │  (CDC)      │    │  (Topic)    │
└─────────────┘    └─────────────┘    └──────┬──────┘
                                              │
                              ┌───────────────┼───────────────┐
                              │               │               │
                     ┌────────▼─────┐ ┌──────▼─────┐ ┌──────▼─────┐
                     │   Flink     │ │   Flink    │ │   Flink    │
                     │  (ETL)      │ │ (聚合)     │ │ ( CEP )    │
                     └──────┬──────┘ └──────┬─────┘ └──────┬─────┘
                            │              │              │
                     ┌──────▼──────┐ ┌─────▼──────┐ ┌────▼──────┐
                     │  ClickHouse │ │  Kafka     │ │  Doris   │
                     │  (DWS)      │ │  (结果)    │ │ (ODS)    │
                     └─────────────┘ └────────────┘ └──────────┘
```

### 7.2 数据质量监控

```go
type DataQualityMonitor struct {
    checks []QualityCheck
}

type QualityCheck interface {
    Name() string
    Check(data DataFrame) (QualityResult, error)
}

// 常见质量检查
type NullCheck struct {
    Column   string
    Threshold float64  // 空值比例阈值
}

func (c *NullCheck) Check(data DataFrame) (QualityResult, error) {
    total := data.Count()
    nulls := data.Filter(c.Column + " IS NULL").Count()
    ratio := float64(nulls) / float64(total)
    
    return QualityResult{
        Passed:  ratio < c.Threshold,
        Metric:  ratio,
        Message: fmt.Sprintf("Null ratio: %.2f%%", ratio*100),
    }, nil
}
```

---

## 8. 总结

### 8.1 技术选型建议

| 场景 | 推荐方案 | 理由 |
|------|----------|------|
| 离线批处理 | Spark | 生态完善，API 友好 |
| 实时流处理 | Flink | 低延迟，Exactly-Once |
| 即席查询 | Presto | 亚秒级响应 |
| 消息队列 | Kafka | 高吞吐，持久化 |
| 数据湖 | Iceberg | ACID 事务，时序回溯 |

### 8.2 性能优化 Checklist

- [ ] 合理设置并行度
- [ ] 避免数据倾斜
- [ ] 使用合适的数据格式（Parquet/ORC）
- [ ] 启用压缩（Snappy/LZ4）
- [ ] 监控背压和 backlog
- [ ] 合理设置 checkpoint 间隔

---

*最后更新：2026-08-11*
*作者：Ryan*
