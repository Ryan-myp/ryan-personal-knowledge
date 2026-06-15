# 数据架构设计：数据湖/数据仓库/实时计算

> 逐行源码解析 + 生产排障案例 + 对比分析 + 动手验证

---

## 第一部分：入门引导（5 分钟速览）

### 类比理解数据架构

```
数据架构 = 物流系统

数据湖 = 原始仓库（所有数据都存）
数据仓库 = 分类仓库（结构化数据）
实时计算 = 快递分拣中心（流式处理）

广告平台数据流：
用户行为 → Kafka → Flink（实时） → ClickHouse
                    → Spark（离线） → Hive
```

### 数据架构核心挑战

```
1. 数据量：每日 TB 级日志
2. 实时性：竞价需要毫秒级响应
3. 一致性：报表数据需要准确
4. 成本：存储和计算的成本控制
5. 灵活性：支持多种查询模式
```

---

## 第二部分：Lambda 架构

### 2.1 Lambda 架构原理

```
Lambda = 批处理层 + 速度层 + 服务层

批处理层（Batch Layer）：
→ Hadoop/Spark
→ 全量数据处理
→ 准确但延迟高

速度层（Speed Layer）：
→ Kafka/Flink
→ 增量数据处理
→ 实时但可能有误差

服务层（Serving Layer）：
→ 合并批处理和速度层结果
→ 对外提供服务
```

### 2.2 Go 实现 Lambda 架构

```go
package lambda

import (
    "context"
    "sync"
    "time"
)

// LambdaArchitecture Lambda 架构
type LambdaArchitecture struct {
    batchLayer  *BatchLayer
    speedLayer  *SpeedLayer
    servingLayer *ServingLayer
}

// BatchLayer 批处理层
type BatchLayer struct {
    storage *Storage
    processor *Processor
}

func (bl *BatchLayer) Process(ctx context.Context) error {
    // 1. 读取原始数据
    rawData := bl.storage.Read(ctx)
    
    // 2. 批处理
    processedData := bl.processor.Process(rawData)
    
    // 3. 写入结果存储
    bl.storage.Write(ctx, processedData)
    
    return nil
}

// SpeedLayer 速度层
type SpeedLayer struct {
    stream *StreamProcessor
    cache  *Cache
}

func (sl *SpeedLayer) Process(ctx context.Context, event Event) error {
    // 1. 流处理
    result := sl.stream.Process(event)
    
    // 2. 写入缓存
    sl.cache.Set(event.Key, result)
    
    return nil
}

// ServingLayer 服务层
type ServingLayer struct {
    batchStore *Store
    speedStore *Store
}

func (sl *ServingLayer) Get(ctx context.Context, key string) (interface{}, error) {
    // 1. 查询速度层
    if value, ok := sl.speedStore.Get(key); ok {
        return value, nil
    }
    
    // 2. 查询批处理层
    return sl.batchStore.Get(key)
}
```

---

## 第三部分：Kappa 架构

### 3.1 Kappa 架构原理

```
Kappa = 只有速度层

与 Lambda 的区别：
- Lambda：批处理 + 速度
- Kappa：只有速度，历史数据重放

优势：
1. 架构简单
2. 维护成本低
3. 实时性和准确性一致

劣势：
1. 重放历史数据成本高
2. 不适合全量计算场景
```

### 3.2 Go 实现 Kappa 架构

```go
package kappa

import (
    "context"
)

// KappaArchitecture Kappa 架构
type KappaArchitecture struct {
    logStore   *LogStore
    processor  *StreamProcessor
}

// LogStore 日志存储
type LogStore struct {
    topic string
    kafka *KafkaClient
}

func (ls *LogStore) Append(ctx context.Context, event Event) error {
    return ls.kafka.Produce(ls.topic, event)
}

func (ls *LogStore) Read(ctx context.Context, offset int64) ([]Event, error) {
    return ls.kafka.Consume(ls.topic, offset)
}

// StreamProcessor 流处理器
type StreamProcessor struct {
    handlers []Handler
}

type Handler interface {
    Handle(ctx context.Context, event Event) error
}

func (sp *StreamProcessor) Process(ctx context.Context, events []Event) error {
    for _, event := range events {
        for _, handler := range sp.handlers {
            if err := handler.Handle(ctx, event); err != nil {
                return err
            }
        }
    }
    return nil
}
```

---

## 第四部分：数据仓库设计

### 4.1 数仓分层

```
ODS（操作数据层）：
→ 原始数据，不做处理

DWD（明细数据层）：
→ 清洗、标准化

DWS（服务数据层）：
→ 轻度汇总

ADS（应用数据层）：
→ 面向应用的宽表
```

### 4.2 Go 实现数据管道

```go
package pipeline

import (
    "context"
)

// DataPipeline 数据管道
type DataPipeline struct {
    stages []Stage
}

type Stage struct {
    name     string
    process  func(context.Context, []Record) ([]Record, error)
}

func (dp *DataPipeline) AddStage(name string, process func(context.Context, []Record) ([]Record, error)) {
    dp.stages = append(dp.stages, Stage{
        name:    name,
        process: process,
    })
}

func (dp *DataPipeline) Run(ctx context.Context, records []Record) ([]Record, error) {
    result := records
    
    for _, stage := range dp.stages {
        var err error
        result, err = stage.process(ctx, result)
        if err != nil {
            return nil, err
        }
    }
    
    return result, nil
}
```

---

## 第五部分：生产排障案例

### 5.1 数据延迟

```
现象：实时报表数据延迟严重

排查：
1. 检查 Kafka 消费 lag
2. 检查 Flink 任务状态
3. 检查 ClickHouse 写入性能

根因：Flink 任务背压

解决方案：
1. 增加并行度
2. 优化算子
3. 调整背压阈值
```

### 5.2 数据不一致

```
现象：批处理和实时数据不一致

排查：
1. 检查处理逻辑
2. 检查数据源
3. 检查时间窗口

根因：批处理和实时处理逻辑不一致

解决方案：
1. 统一处理逻辑
2. 添加数据校验
3. 定期比对数据
```

---

## 第六部分：自测题

### 问题 1
Lambda 和 Kappa 架构的区别？

<details>
<summary>查看答案</summary>

1. **Lambda**：批处理 + 速度层
2. **Kappa**：只有速度层
3. **Lambda 优势**：适合全量计算
4. **Kappa 优势**：架构简单
5. **Go 实现**：LambdaArchitecture/KappaArchitecture

</details>

### 问题 2
数据仓库分层的作用？

<details>
<summary>查看答案</summary>

1. **ODS**：原始数据
2. **DWD**：清洗标准化
3. **DWS**：轻度汇总
4. **ADS**：面向应用
5. **Go 实现**：DataPipeline

</details>

### 问题 3
如何保证数据一致性？

<details>
<summary>查看答案</summary>

1. **统一处理逻辑**：批处理和实时一致
2. **数据校验**：定期比对
3. **幂等性**：重复处理不影响
4. **监控告警**：及时发现不一致
5. **Go 实现**：校验逻辑

</details>

---

*本文档基于数据架构原理整理。*