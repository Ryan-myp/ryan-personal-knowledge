# 大数据组件深度：Hive/Presto/Kafka Streams

> 逐行源码解析 + 生产排障案例 + 对比分析 + 动手验证

---

## 第一部分：入门引导（5 分钟速览）

### 类比理解大数据组件

```
Hive = SQL 翻译器
→ 把 SQL 翻译成 MapReduce
→ 适合离线批处理

Presto = 分布式 SQL 引擎
→ 直接查询数据
→ 适合交互式查询

Kafka Streams = 流处理库
→ 轻量级流处理
→ 适合实时数据管道
```

---

## 第二部分：Hive 深度

### 2.1 Hive 架构

```
Hive 组件：
1. CLI/WebUI：用户接口
2. Metastore：元数据存储
3. Driver：驱动器
4. Compiler：编译器
5. Executor：执行器
```

### 2.2 Go 实现简化 Hive

```go
package hive

import (
    "context"
    "fmt"
)

type Hive struct {
    metastore *Metastore
    driver    *Driver
}

type Metastore struct {
    tables map[string]TableMeta
}

type TableMeta struct {
    Name    string
    Columns []Column
    Location string
}

type Column struct {
    Name string
    Type string
}

func (h *Hive) Execute(ctx context.Context, sql string) ([]interface{}, error) {
    // 1. 解析 SQL
    plan, err := h.driver.Parse(sql)
    if err != nil {
        return nil, err
    }
    
    // 2. 优化执行计划
    optimized := h.driver.Optimize(plan)
    
    // 3. 执行
    return h.driver.Execute(ctx, optimized)
}
```

---

## 第三部分：Presto 深度

### 3.1 Presto 架构

```
Coordinator：
→ 解析 SQL
→ 生成执行计划
→ 分配任务

Worker：
→ 执行 Task
→ 数据交换
```

### 3.2 Go 实现简化 Presto

```go
type Presto struct {
    coordinator *Coordinator
    workers     []*Worker
}

type Coordinator struct {
    scheduler *Scheduler
}

type Worker struct {
    ID string
    Memory int64
}

func (p *Presto) Execute(sql string) ([]interface{}, error) {
    // 1. 解析 SQL
    plan, err := p.coordinator.Parse(sql)
    if err != nil {
        return nil, err
    }
    
    // 2. 分配任务
    tasks := p.coordinator.Schedule(plan)
    
    // 3. 执行
    results := make([][]interface{}, len(tasks))
    for i, task := range tasks {
        results[i] = task.Execute()
    }
    
    // 4. 合并结果
    return mergeResults(results), nil
}
```

---

## 第四部分：Kafka Streams 深度

### 4.1 Kafka Streams 架构

```
Kafka Streams = 客户端库
→ 嵌入应用
→ 不需要额外集群
→ 轻量级
```

### 4.2 Go 实现简化 Kafka Streams

```go
type KafkaStreams struct {
    consumer *Consumer
    producer *Producer
    processors []Processor
}

type Processor interface {
    Process(message interface{}) interface{}
}

func (ks *KafkaStreams) Start() error {
    for {
        // 1. 消费消息
        message := ks.consumer.Poll()
        if message == nil {
            continue
        }
        
        // 2. 处理消息
        for _, proc := range ks.processors {
            message = proc.Process(message)
        }
        
        // 3. 生产结果
        ks.producer.Send(message)
    }
}
```

---

## 第五部分：生产排障案例

### 5.1 Hive 慢查询

```
现象：Hive SQL 执行很慢

排查：
1. 检查执行计划
2. 检查数据倾斜
3. 检查小文件

根因：数据倾斜

解决方案：
1. 增加并行度
2. 优化 JOIN
3. 过滤无用数据
```

### 5.2 Presto OOM

```
现象：Presto Worker OOM

排查：
1. 检查查询复杂度
2. 检查数据量
3. 检查内存配置

根因：大表 JOIN

解决方案：
1. 减少 JOIN 数据量
2. 增加 Worker 内存
3. 使用广播 JOIN
```

---

## 第六部分：自测题

### 问题 1
Hive 和 Presto 的区别？

<details>
<summary>查看答案</summary>

1. **Hive**：离线批处理
2. **Presto**：交互式查询
3. **Hive**：MapReduce/Tez
4. **Presto**：内存计算
5. **Go 实现**：Hive/Presto

</details>

### 问题 2
Kafka Streams 的优势？

<details>
<summary>查看答案</summary>

1. **轻量级**：客户端库
2. **嵌入式**：无需额外集群
3. **状态管理**：内置状态
4. **Exactly-once**：端到端保证
5. **Go 实现**：KafkaStreams

</details>

### 问题 3
大数据组件选型建议？

<details>
<summary>查看答案</summary>

1. **离线批处理**：Hive/Spark
2. **交互式查询**：Presto/Trino
3. **实时流处理**：Flink/Kafka Streams
4. **数据湖**：Iceberg/Delta Lake
5. **Go 实现**：根据场景选择
</details>

---

*本文档基于大数据组件原理整理。*