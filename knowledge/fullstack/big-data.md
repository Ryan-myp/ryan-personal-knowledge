- 实时流处理: Flink
- 交互式查询: Spark SQL / Presto / Hive
- 事件处理: Flink / Storm
- 混合场景: Spark Structured Streaming / Flink
```

---

### 大数据的 Go 实现

```go
package bigdata

import (
	"fmt"
	"sync"
)

type SparkJob struct {
	ID       string
	Status   string
	Executor int
	Memory   int
}

type SparkEngine struct {
	clusterSize int
	runningJobs map[string]*SparkJob
	mu          sync.Mutex
}

func NewSparkEngine(clusterSize int) *SparkEngine {
	return &SparkEngine{clusterSize: clusterSize, runningJobs: make(map[string]*SparkJob)}
}

func (e *SparkEngine) SubmitJob(name string, executors, memory int) *SparkJob {
	e.mu.Lock()
	defer e.mu.Unlock()
	job := &SparkJob{ID: name, Status: "PENDING", Executor: executors, Memory: memory}
	e.runningJobs[name] = job
	return job
}

type KafkaProducer struct {
	brokers  []string
	produced int
	mu       sync.Mutex
}

func (p *KafkaProducer) Send(topic, key, value string) {
	p.mu.Lock()
	defer p.mu.Unlock()
	p.produced++
}

func main() {
	engine := NewSparkEngine(5)
	job := engine.SubmitJob("etl_001", 3, 4096)
	fmt.Printf("Job %s: %s (execs: %d)\n", job.ID, job.Status, job.Executor)

	producer := &KafkaProducer{brokers: []string{"broker1:9092"}}
	producer.Send("events", "user1", "click")
	fmt.Printf("Produced: %d messages\n", producer.produced)
}
```

---

## 自测题

### 问题 1
Spark 的宽依赖（Wide Dependency）和窄依赖（Narrow Dependency）在 Shuffle 时有何不同？

<details>
<summary>查看答案</summary>

1. **窄依赖**：父 RDD 的每个分区最多被子 RDD 的一个分区使用，无需 shuffle（如 map、filter）
2. **宽依赖**：父 RDD 的分区被子 RDD 的多个分区使用，必须 shuffle（如 groupByKey、reduceByKey）
3. **容错**：窄依赖丢失一个分区只需重算一个，宽依赖需要重算所有相关分区
4. **执行优化**：窄依赖可 pipeline 合并执行，宽依赖必须等待 shuffle write 完成

</details>

### 问题 2
Go 的并发模型（goroutine + channel）和 MapReduce 的 map/reduce 范式有什么异同？

<details>
<summary>查看答案</summary>

**相同点**：
1. 都强调计算与数据的解耦
2. 都支持并行执行

**不同点**：
1. goroutine 是轻量级协程（2KB 栈），MapReduce 是进程级任务
2. channel 提供流式数据传递，MapReduce 依赖磁盘 shuffle
3. Go 适合实时/低延迟场景，MapReduce 适合批量/离线处理
4. Go 的 channel 天然支持 backpressure，MapReduce 需要显式控制

</details>