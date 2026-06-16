# Spark 深度：RDD/DF/SQL/调优实战

> 逐行源码解析 + 生产排障案例 + 对比分析 + 动手验证

---

## 第一部分：入门引导（5 分钟速览）

### 类比理解 Spark

```
Spark = 超级工厂

MapReduce（传统）：
→ 每个工序都要写硬盘
→ 慢，因为磁盘 IO 频繁

Spark（内存计算）：
→ 工序间内存传递
→ 快 10-100 倍
→ DAG 优化执行计划
```

### Spark 核心概念

```
1. RDD：弹性分布式数据集
2. DataFrame：带 Schema 的 RDD
3. Dataset：类型安全的 DataFrame
4. DAG：有向无环图
5. Stage：DAG 切分的执行单元
```

---

## 第二部分：Spark 架构深度

### 2.1 Spark 架构

```
Driver Program：
→ 创建 SparkContext
→ 构建 DAG
→ 提交作业
→ 调度 Task

Cluster Manager：
→ YARN：Hadoop 资源管理器
→ Standalone：Spark 自带
→ Mesos：通用资源管理器

Executor：
→ 运行 Task
→ 缓存数据
→ 定期心跳
```

### 2.2 Go 实现简化 Spark

```go
package spark

import (
    "context"
    "fmt"
    "sync"
)

// SparkContext Spark 上下文
type SparkContext struct {
    master     string
    appName    string
    scheduler  *Scheduler
    cache      map[string]interface{}
    mu         sync.RWMutex
}

// DAG DAG 调度器
type DAGScheduler struct {
    stages []*Stage
}

// Stage DAG 阶段
type Stage struct {
    ID        int
    Type      string // map/reduce/shuffle
    DependsOn []int
    Tasks     []*Task
}

// Task 任务
type Task struct {
    ID       int
    StageID  int
    Partition int
    Fn       func(context.Context, []interface{}) ([]interface{}, error)
}

// SubmitJob 提交作业
func (sc *SparkContext) SubmitJob(ctx context.Context, stages []*Stage) error {
    // 1. 构建 DAG
    dag := &DAGScheduler{stages: stages}
    
    // 2. 切分 Stage（基于 shuffle）
    dag.splitStages(stages)
    
    // 3. 调度执行
    for _, stage := range dag.stages {
        // 等待依赖完成
        for _, dep := range stage.DependsOn {
            // 等待 Stage dep 完成
        }
        
        // 4. 提交 Task
        for _, task := range stage.Tasks {
            sc.scheduler.Submit(task)
        }
        
        // 5. 等待 Stage 完成
        sc.scheduler.WaitStage(stage.ID)
    }
    
    return nil
}
```

---

## 第三部分：RDD 深度

### 3.1 RDD 操作

```
Transformation（懒执行）：
→ map/filter/groupBy/join/coalesce/repartition

Action（触发执行）：
→ collect/count/saveAsTextFile/persist

Cache 策略：
→ MEMORY_ONLY：只内存
→ MEMORY_AND_DISK：内存+磁盘
→ DISK_ONLY：只磁盘
```

### 3.2 Go 实现 RDD

```go
type RDD struct {
    sc        *SparkContext
    partitions []Partition
    deps      []Dependency
}

type Partition struct {
    Index int
    Data  []interface{}
}

type Dependency interface {
    getDependencyType() string
    getRDD() *RDD
}

// NarrowDependency 窄依赖（无 Shuffle）
type NarrowDependency struct {
    rdd *RDD
}

func (nd *NarrowDependency) getDependencyType() string {
    return "narrow"
}

func (nd *NarrowDependency) getRDD() *RDD {
    return nd.rdd
}

// WideDependency 宽依赖（有 Shuffle）
type WideDependency struct {
    rdd *RDD
}

func (wd *WideDependency) getDependencyType() string {
    return "wide"
}

func (wd *WideDependency) getRDD() *RDD {
    return wd.rdd
}

// Map 转换
func (rdd *RDD) Map(fn func(interface{}) interface{}) *RDD {
    var newPartitions []Partition
    for _, p := range rdd.partitions {
        newData := make([]interface{}, len(p.Data))
        for i, v := range p.Data {
            newData[i] = fn(v)
        }
        newPartitions = append(newPartitions, Partition{
            Index: p.Index,
            Data:  newData,
        })
    }
    
    return &RDD{
        sc:         rdd.sc,
        partitions: newPartitions,
        deps:       []Dependency{&NarrowDependency{rdd: rdd}},
    }
}

// Filter 过滤
func (rdd *RDD) Filter(fn func(interface{}) bool) *RDD {
    var newPartitions []Partition
    for _, p := range rdd.partitions {
        var filtered []interface{}
        for _, v := range p.Data {
            if fn(v) {
                filtered = append(filtered, v)
            }
        }
        newPartitions = append(newPartitions, Partition{
            Index: p.Index,
            Data:  filtered,
        })
    }
    
    return &RDD{
        sc:         rdd.sc,
        partitions: newPartitions,
        deps:       []Dependency{&NarrowDependency{rdd: rdd}},
    }
}

// ReduceByKey 聚合
func (rdd *RDD) ReduceByKey(fn func(interface{}, interface{}) interface{}) *RDD {
    // 1. MapToPair
    type KVPair struct {
        Key   interface{}
        Value interface{}
    }
    
    var pairs []KVPair
    for _, p := range rdd.partitions {
        for _, v := range p.Data {
            pair := v.(KVPair)
            pairs = append(pairs, pair)
        }
    }
    
    // 2. Shuffle + Reduce
    groups := make(map[interface{}][]interface{})
    for _, p := range pairs {
        groups[p.Key] = append(groups[p.Key], p.Value)
    }
    
    var newPartitions []Partition
    result := make([]interface{}, 0)
    for key, values := range groups {
        result = append(result, fn(key, values))
    }
    newPartitions = append(newPartitions, Partition{
        Index: 0,
        Data:  result,
    })
    
    return &RDD{
        sc:         rdd.sc,
        partitions: newPartitions,
        deps:       []Dependency{&WideDependency{rdd: rdd}},
    }
}

// Collect 收集结果
func (rdd *RDD) Collect() []interface{} {
    var result []interface{}
    for _, p := range rdd.partitions {
        result = append(result, p.Data...)
    }
    return result
}

// Cache 缓存
func (rdd *RDD) Cache() *RDD {
    // 缓存逻辑
    return rdd
}
```

---

## 第四部分：DataFrame/SQL 深度

### 4.1 Catalyst 优化器

```
Catalyst 优化流程：
1. Analysis：解析 SQL，解析表/列
2. Logical Planning：生成逻辑计划
3. Optimization：优化逻辑计划
4. Physical Planning：生成物理计划
5. Codegen：生成字节码

优化规则：
→ 谓词下推
→ 列裁剪
→ 常量折叠
→ 投影合并
```

### 4.2 Go 实现 DataFrame

```go
type DataFrame struct {
    sc     *SparkContext
    schema Schema
    plan   LogicalPlan
}

type Schema struct {
    Fields []Field
}

type Field struct {
    Name string
    Type string
}

// Select 选择列
func (df *DataFrame) Select(columns ...string) *DataFrame {
    // 列裁剪优化
    newSchema := Schema{Fields: make([]Field, 0)}
    for _, col := range columns {
        for _, f := range df.schema.Fields {
            if f.Name == col {
                newSchema.Fields = append(newSchema.Fields, f)
            }
        }
    }
    
    return &DataFrame{
        sc:     df.sc,
        schema: newSchema,
        plan:   SelectPlan{parent: df.plan, columns: columns},
    }
}

// Filter 过滤
func (df *DataFrame) Filter(condition string) *DataFrame {
    return &DataFrame{
        sc:     df.sc,
        schema: df.schema,
        plan:   FilterPlan{parent: df.plan, condition: condition},
    }
}

// GroupBy 分组
func (df *DataFrame) GroupBy(key string) *GroupedData {
    return &GroupedData{
        df:    df,
        keys:  []string{key},
    }
}

type GroupedData struct {
    df   *DataFrame
    keys []string
}

func (gd *GroupedData) Count() *DataFrame {
    return &DataFrame{
        sc:     gd.df.sc,
        schema: append(gd.df.schema.Fields, Field{Name: "count", Type: "long"}),
        plan:   CountPlan{parent: gd.df.plan, keys: gd.keys},
    }
}

// Explain 查看执行计划
func (df *DataFrame) Explain(verbose bool) string {
    if verbose {
        return df.plan.ExplainDetailed()
    }
    return df.plan.ExplainSimple()
}
```

---

## 第五部分：Spark 调优

### 5.1 常见调优参数

```
# Executor 配置
spark.executor.memory=4g
spark.executor.cores=4
spark.executor.instances=10

# Shuffle 配置
spark.sql.shuffle.partitions=200
spark.serializer=org.apache.spark.serializer.KryoSerializer

# Cache 配置
spark.sql.adaptive.enabled=true
spark.sql.adaptive.coalescePartitions.enabled=true
```

### 5.2 Go 实现 Spark 调优

```go
type SparkConfig struct {
    ExecutorMemory   string
    ExecutorCores    int
    ExecutorInstances int
    ShufflePartitions int
    Serializer       string
}

func NewSparkConfig() *SparkConfig {
    return &SparkConfig{
        ExecutorMemory:    "4g",
        ExecutorCores:     4,
        ExecutorInstances: 10,
        ShufflePartitions: 200,
        Serializer:        "java",
    }
}

// tuneForDataSkew 针对数据倾斜调优
func (cfg *SparkConfig) tuneForDataSkew() {
    // 1. 增加 shuffle partitions
    cfg.ShufflePartitions = cfg.ShufflePartitions * 4
    
    // 2. 使用 salting 解决倾斜
    // ...
    
    // 3. 启用 AQE
    // cfg.AdaptiveExecution = true
}

// tuneForMemory 针对内存调优
func (cfg *SparkConfig) tuneForMemory() {
    // 1. 增加 executor 内存
    cfg.ExecutorMemory = "8g"
    
    // 2. 使用 Kryo 序列化
    cfg.Serializer = "kryo"
    
    // 3. 启用内存管理
    // cfg.MemoryManager = "tungsten"
}
```

---

## 第六部分：生产排障案例

### 6.1 数据倾斜

```
现象：部分 Task 执行时间远长于其他 Task

排查：
1. 检查 Task 执行时间分布
2. 检查 Key 分布
3. 检查是否有热点 Key

根因：某个 Key 数据量特别大

解决方案：
1. 增加 shuffle partitions
2. Salting：给 Key 加随机前缀
3. 广播小表
```

```go
// Salting 解决数据倾斜
func (rdd *RDD) Salting(fn func(interface{}) interface{}, numSalt int) *RDD {
    type KVPair struct {
        Key   interface{}
        Value interface{}
    }
    
    var salted []KVPair
    for _, p := range rdd.partitions {
        for _, v := range p.Data {
            pair := v.(KVPair)
            salt := rand.Intn(numSalt)
            saltedKey := fmt.Sprintf("%s-%d", pair.Key, salt)
            salted = append(salted, KVPair{
                Key:   saltedKey,
                Value: pair.Value,
            })
        }
    }
    
    // 聚合
    groups := make(map[interface{}][]interface{})
    for _, p := range salted {
        groups[p.Key] = append(groups[p.Key], p.Value)
    }
    
    // 去除 salt
    var result []interface{}
    for key, values := range groups {
        originalKey := strings.Split(key.(string), "-")[0]
        agg := fn(originalKey, values)
        result = append(result, agg)
    }
    
    return &RDD{
        partitions: []Partition{{Data: result}},
    }
}
```

### 6.2 OOM

```
现象：Executor OOM

排查：
1. 检查 executor-memory
2. 检查是否有大对象
3. 检查是否有数据倾斜

根因：内存不足

解决方案：
1. 增加 executor-memory
2. 使用 off-heap 内存
3. 优化数据结构
```

---

## 第七部分：自测题

### 问题 1
Spark 相比 MapReduce 有什么优势？

<details>
<summary>查看答案</summary>

1. **内存计算**：比磁盘快 100 倍
2. **DAG 优化**：减少中间存储
3. **丰富的 API**：SQL/Streaming/MLlib
4. **增量计算**：CDC
5. **Go 实现**：Spark RDD

</details>

### 问题 2
如何优化 Spark 数据倾斜？

<details>
<summary>查看答案</summary>

1. **增加 partitions**：分散数据
2. **Salting**：加随机前缀
3. **广播小表**：Broadcast Join
4. **过滤热点 Key**：特殊处理
5. **Go 实现**：Salting

</details>

### 问题 3
Catalyst 优化器做了什么？

<details>
<summary>查看答案</summary>

1. **Analysis**：解析 SQL
2. **Logical Planning**：逻辑计划
3. **Optimization**：规则优化
4. **Physical Planning**：物理计划
5. **Codegen**：字节码生成

</details>

---

*本文档基于 Spark 原理整理。*