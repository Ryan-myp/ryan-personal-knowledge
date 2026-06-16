# 大数据架构深度：Hadoop/Spark/Flink

> 逐行源码解析 + 生产排障案例 + 对比分析 + 动手验证

---

## 第一部分：入门引导（5 分钟速览）

### 类比理解大数据

```
大数据 = 处理海量数据的工厂

Hadoop = 传统工厂
  → 批量处理，离线计算
  → MapReduce：分而治之

Spark = 高速工厂
  → 内存计算，比 Hadoop 快 100 倍
  → DAG：有向无环图

Flink = 实时工厂
  → 流式处理，实时计算
  → 事件驱动，低延迟
```

### 大数据核心挑战

```
1. 数据量：PB 级数据
2. 多样性：结构化/半结构化/非结构化
3. 速度：实时 vs 离线
4. 价值：从数据中提取价值
```

---

## 第二部分：Hadoop 深度

### 2.1 HDFS 架构

```
HDFS = Hadoop Distributed File System

NameNode：
→ 管理元数据（文件/目录/块信息）
→ 维护文件到块的映射
→ 管理副本策略

DataNode：
→ 存储实际数据块
→ 定期向 NameNode 汇报
→ 处理读写请求

Secondary NameNode：
→ 合并 fsimage 和 edits log
→ 不备份 NameNode
```

### 2.2 Go 实现简化 HDFS

```go
package hdfs

import (
    "context"
    "fmt"
    "sync"
)

// NameNode 名称节点
type NameNode struct {
    mu          sync.RWMutex
    metadata    map[string]*FileMetadata
    blockManager *BlockManager
}

type FileMetadata struct {
    Name     string
    Blocks   []BlockID
    Replicas int
    Owner    string
}

type BlockID string

// BlockManager 块管理器
type BlockManager struct {
    blocks      map[BlockID]*DataBlock
    replicas    map[BlockID][]string
    mu          sync.RWMutex
}

type DataBlock struct {
    ID        BlockID
    Data      []byte
    LocatedOn []string // 存储在哪些 DataNode
}

// WriteFile 写入文件
func (nn *NameNode) WriteFile(ctx context.Context, filename string, data []byte, replicas int) error {
    nn.mu.Lock()
    defer nn.mu.Unlock()
    
    // 分块
    blockSize := int64(128 * 1024 * 1024) // 128MB
    numBlocks := (len(data) + int(blockSize) - 1) / int(blockSize)
    
    blocks := make([]BlockID, numBlocks)
    for i := 0; i < numBlocks; i++ {
        start := i * int(blockSize)
        end := start + int(blockSize)
        if end > len(data) {
            end = len(data)
        }
        
        blockID := BlockID(fmt.Sprintf("%s-%d", filename, i))
        blocks[i] = blockID
        
        // 存储块
        nn.blockManager.StoreBlock(blockID, data[start:end], replicas)
    }
    
    // 更新元数据
    nn.metadata[filename] = &FileMetadata{
        Name:     filename,
        Blocks:   blocks,
        Replicas: replicas,
    }
    
    return nil
}

// ReadFile 读取文件
func (nn *NameNode) ReadFile(ctx context.Context, filename string) ([]byte, error) {
    nn.mu.RLock()
    defer nn.mu.RUnlock()
    
    meta, ok := nn.metadata[filename]
    if !ok {
        return nil, fmt.Errorf("file not found: %s", filename)
    }
    
    var data []byte
    for _, blockID := range meta.Blocks {
        block := nn.blockManager.GetBlock(blockID)
        data = append(data, block.Data...)
    }
    
    return data, nil
}
```

### 2.3 MapReduce 深度

```
MapReduce 工作流程：
1. Split：输入数据分片
2. Map：并行处理每个分片
3. Shuffle：按 key 排序和分区
4. Reduce：聚合结果

Shuffle 是关键：
→ 数据在网络间传输
→ 影响性能和可扩展性
```

```go
// MapReduce 实现
type MapReduce struct {
    mapper   func(key, value []byte) ([]byte, []byte)
    reducer  func(key []byte, values [][]byte) []byte
}

func (mr *MapReduce) Execute(input []byte) []byte {
    // Map 阶段
    type KV struct {
        Key   []byte
        Value []byte
    }
    
    var mapped []KV
    for _, line := range bytes.Split(input, []byte("\n")) {
        k, v := mr.mapper(nil, line)
        mapped = append(mapped, KV{k, v})
    }
    
    // Shuffle + Sort
    sort.Slice(mapped, func(i, j int) bool {
        return bytes.Compare(mapped[i].Key, mapped[j].Key) < 0
    })
    
    // Reduce 阶段
    var result []byte
    currentKey := mapped[0].Key
    var values [][]byte
    
    for _, kv := range mapped {
        if !bytes.Equal(kv.Key, currentKey) {
            result = append(result, mr.reducer(currentKey, values)...)
            currentKey = kv.Key
            values = nil
        }
        values = append(values, kv.Value)
    }
    
    // 处理最后一个 key
    result = append(result, mr.reducer(currentKey, values)...)
    
    return result
}
```

---

## 第三部分：Spark 深度

### 3.1 Spark 架构

```
Spark 架构：
Driver Program：
→ 创建 SparkContext
→ 提交作业
→ 调度任务

Cluster Manager：
→ YARN
→ Mesos
→ Standalone

Executor：
→ 运行任务
→ 缓存数据
→ 报告状态
```

### 3.2 RDD 深度

```
RDD（Resilient Distributed Dataset）：
→ 弹性分布式数据集
→ 不可变
→ 可分区并行操作
→ 容错（血统重建）

操作类型：
Transformation（懒执行）：
→ map/filter/groupBy/join

Action（触发执行）：
→ collect/count/save
```

```go
// Spark RDD 模拟
type RDD struct {
    partitions []Partition
    dependencies []Dependency
    funcName   string
}

type Partition struct {
    ID   int
    Data []interface{}
}

type Dependency interface {
    ParentRDDs() []*RDD
}

type NarrowDependency struct {
    parent *RDD
}

func (nd *NarrowDependency) ParentRDDs() []*RDD {
    return []*RDD{nd.parent}
}

type WideDependency struct {
    parent *RDD
    partitioner func(interface{}) int
}

func (wd *WideDependency) ParentRDDs() []*RDD {
    return []*RDD{wd.parent}
}

// Transform 转换
func (rdd *RDD) Transform(name string, fn func([]interface{}) []interface{}) *RDD {
    var newPartitions []Partition
    for i, p := range rdd.partitions {
        newPartitions = append(newPartitions, Partition{
            ID:   i,
            Data: fn(p.Data),
        })
    }
    
    return &RDD{
        partitions:   newPartitions,
        dependencies: []Dependency{&NarrowDependency{parent: rdd}},
        funcName:     name,
    }
}

// Action 触发执行
func (rdd *RDD) Collect() []interface{} {
    var result []interface{}
    for _, p := range rdd.partitions {
        result = append(result, p.Data...)
    }
    return result
}
```

### 3.3 DataFrame/Dataset 深度

```
DataFrame = 带 Schema 的分布式数据集
Dataset = 类型安全的 DataFrame

优势：
1. Catalyst 优化器：自动优化查询
2. Tungsten：内存管理优化
3. 代码生成：避免反射
```

```go
// DataFrame 操作
type DataFrame struct {
    schema Schema
    rdd    *RDD
}

type Schema struct {
    Fields []Field
}

type Field struct {
    Name string
    Type string
}

func (df *DataFrame) Select(columns ...string) *DataFrame {
    // 选择列
    return &DataFrame{
        schema: df.schema,
        rdd:    df.rdd,
    }
}

func (df *DataFrame) Filter(predicate func(interface{}) bool) *DataFrame {
    // 过滤
    return &DataFrame{
        schema: df.schema,
        rdd:    df.rdd.Transform("filter", func(data []interface{}) []interface{} {
            var result []interface{}
            for _, item := range data {
                if predicate(item) {
                    result = append(result, item)
                }
            }
            return result
        }),
    }
}

func (df *DataFrame) GroupBy(key string) *GroupedDataFrame {
    // 分组
    return &GroupedDataFrame{
        df: df,
        key: key,
    }
}

type GroupedDataFrame struct {
    df  *DataFrame
    key string
}

func (gdf *GroupedDataFrame) Count() *DataFrame {
    // 计数
    return &DataFrame{
        schema: Schema{
            Fields: []Field{
                {Name: gdf.key, Type: "string"},
                {Name: "count", Type: "long"},
            },
        },
        rdd: gdf.df.rdd,
    }
}
```

---

## 第四部分：Flink 深度

### 4.1 Flink 架构

```
Flink 架构：
JobManager：
→ 协调分布式执行
→ 检查点协调

TaskManager：
→ 执行任务
→ 管理资源

DataStream API：
→ 流式处理
→ 窗口操作
→ 状态管理
```

### 4.2 Flink 窗口深度

```
窗口类型：
1. Tumbling Window：滚动窗口
2. Sliding Window：滑动窗口
3. Session Window：会话窗口
4. Global Window：全局窗口

Watermark：
→ 处理乱序数据
→ 定义事件时间
→ 触发计算
```

```go
package flink

import (
    "time"
)

// Watermark 水位线
type Watermark struct {
    Timestamp time.Time
}

// Window 窗口
type Window struct {
    Start    time.Time
    End      time.Time
    Elements []interface{}
}

// WindowOperator 窗口操作器
type WindowOperator struct {
    windowSize time.Duration
    windows    map[string]*Window
}

func (wo *WindowOperator) ProcessElement(element interface{}, timestamp time.Time) {
    windowStart := timestamp.Tr(wo.windowSize)
    windowEnd := windowStart.Add(wo.windowSize)
    key := fmt.Sprintf("%d", windowStart.Unix())
    
    window, ok := wo.windows[key]
    if !ok {
        window = &Window{
            Start:    windowStart,
            End:      windowEnd,
            Elements: make([]interface{}, 0),
        }
        wo.windows[key] = window
    }
    
    window.Elements = append(window.Elements, element)
}

func (wo *WindowOperator) ProcessWatermark(wm Watermark) {
    // 触发过期窗口的计算
    for key, window := range wo.windows {
        if wm.Timestamp.After(window.End) {
            // 触发计算
            wo.triggerWindow(key, window)
            delete(wo.windows, key)
        }
    }
}

func (wo *WindowOperator) triggerWindow(key string, window *Window) {
    // 聚合计算
    result := wo.aggregate(window.Elements)
    fmt.Printf("Window %s result: %v\n", key, result)
}

func (wo *WindowOperator) aggregate(elements []interface{}) interface{} {
    // 聚合逻辑
    return len(elements)
}
```

### 4.3 Flink 状态管理

```
状态类型：
1. Keyed State：键控状态
2. Operator State：算子状态

状态后端：
1. MemoryStateBackend：内存
2. FsStateBackend：文件系统
3. RocksDBStateBackend：RocksDB

Checkpoint：
→ 定期快照
→ 故障恢复
→ Exactly-once 语义
```

```go
// Flink 状态管理
type StateBackend struct {
    state map[string]interface{}
}

func (sb *StateBackend) Get(key string) (interface{}, bool) {
    val, ok := sb.state[key]
    return val, ok
}

func (sb *StateBackend) Put(key string, value interface{}) {
    sb.state[key] = value
}

// KeyedState 键控状态
type KeyedState struct {
    backend *StateBackend
    key     string
}

func (ks *KeyedState) Get() (interface{}, bool) {
    return ks.backend.Get(ks.key)
}

func (ks *KeyedState) Put(value interface{}) {
    ks.backend.Put(ks.key, value)
}

// ValueState 值状态
type ValueState struct {
    backend *StateBackend
    key     string
}

func (vs *ValueState) Value() (interface{}, bool) {
    return vs.backend.Get(vs.key)
}

func (vs *ValueState) Update(value interface{}) {
    vs.backend.Put(vs.key, value)
}

// ListState 列表状态
type ListState struct {
    backend *StateBackend
    key     string
}

func (ls *ListState) Add(value interface{}) {
    current, ok := ls.backend.Get(ls.key)
    if !ok {
        current = []interface{}{}
    }
    
    list := current.([]interface{})
    list = append(list, value)
    
    ls.backend.Put(ls.key, list)
}

func (ls *ListState) All() []interface{} {
    val, ok := ls.backend.Get(ls.key)
    if !ok {
        return []interface{}{}
    }
    return val.([]interface{})
}
```

---

## 第五部分：生产排障案例

### 5.1 Spark OOM

```
现象：Spark Executor OOM

排查：
1. 检查 executor-memory
2. 检查 shuffle 数据量
3. 检查数据倾斜

根因：数据倾斜导致某个分区数据过大

解决方案：
1. 增加 executor 内存
2. 调整分区数
3. 使用 salting 解决倾斜
```

### 5.2 Flink Checkpoint 失败

```
现象：Checkpoint 经常超时

排查：
1. 检查 checkpoint 间隔
2. 检查状态大小
3. 检查后端存储

根因：状态太大，写入太慢

解决方案：
1. 使用 RocksDBStateBackend
2. 增加 checkpoint 超时时间
3. 优化状态访问模式
```

---

## 第六部分：自测题

### 问题 1
Hadoop MapReduce 的 Shuffle 阶段做了什么？

<details>
<summary>查看答案</summary>

1. **排序**：按 key 排序
2. **分区**：分配到不同的 reduce
3. **合并**：合并相同 key
4. **网络传输**：map 到 reduce 的数据传输
5. **Go 实现**：MapReduce Shuffle

</details>

### 问题 2
Spark 相比 Hadoop MapReduce 有什么优势？

<details>
<summary>查看答案</summary>

1. **内存计算**：比磁盘快 100 倍
2. **DAG 执行**：优化执行计划
3. **CDC**：增量计算
4. **丰富的 API**：SQL/Streaming/MLlib
5. **Go 实现**：Spark RDD

</details>

### 问题 3
Flink 的 Watermark 是什么？

<details>
<summary>查看答案</summary>

1. **事件时间**：定义数据到达顺序
2. **乱序处理**：允许一定延迟
3. **触发计算**：水位线到达触发
4. **Exactly-once**：保证一致性
5. **Go 实现**：WindowOperator

</details>

---

*本文档基于大数据架构原理整理。*