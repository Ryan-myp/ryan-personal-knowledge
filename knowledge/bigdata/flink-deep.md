# Flink 深度：流处理/窗口/状态/Exactly-once

> 逐行源码解析 + 生产排障案例 + 对比分析 + 动手验证

---

## 第一部分：入门引导（5 分钟速览）

### 类比理解 Flink

```
Flink = 实时流水线

批处理（Batch）：
→ 一卡车货一起运
→ 等装满再出发
→ 延迟高，吞吐大

流处理（Streaming）：
→ 传送带，数据来了就处理
→ 实时性高
→ Flink 是真正的流处理
```

### Flink 核心概念

```
1. DataStream API：流处理
2. Table API：关系型查询
3. SQL：标准 SQL
4. State：状态管理
5. Checkpoint：容错机制
```

---

## 第二部分：Flink 架构深度

### 2.1 Flink 架构

```
JobManager（Master）：
→ 协调分布式执行
→ 检查点协调
→ 故障恢复

TaskManager（Worker）：
→ 执行 Task
→ 管理槽位
→ 数据缓冲

JobGraph：
→ Job → Task → 边
→ 提交给 JobManager
```

### 2.2 Go 实现简化 Flink

```go
package flink

import (
    "context"
    "fmt"
    "sync"
    "time"
)

// StreamExecutionEnvironment 流执行环境
type StreamExecutionEnvironment struct {
    parallelism int
    checkpoints CheckpointConfig
    sources     []Source
    sinks       []Sink
    operators   []Operator
}

// Operator 算子
type Operator struct {
    Name     string
    Parallel int
    Fn       func(context.Context, interface{}) interface{}
    State    map[string]interface{}
}

// Source 数据源
type Source interface {
    Open(ctx context.Context) error
    Next(ctx context.Context) (interface{}, bool)
    Close(ctx context.Context) error
}

// Sink 数据汇
type Sink interface {
    Open(ctx context.Context) error
    Write(ctx context.Context, data interface{}) error
    Close(ctx context.Context) error
}

// Execute 执行作业
func (env *StreamExecutionEnvironment) Execute(ctx context.Context) error {
    // 1. 构建 DAG
    dag := env.buildDAG()
    
    // 2. 调度执行
    for _, operator := range dag.Operators {
        go func(op *Operator) {
            for data := range op.Input {
                result := op.Fn(ctx, data)
                op.Output <- result
            }
        }(operator)
    }
    
    // 3. 等待完成
    <-ctx.Done()
    return nil
}

// buildDAG 构建有向无环图
func (env *StreamExecutionEnvironment) buildDAG() *DAG {
    dag := &DAG{
        Operators: make([]*Operator, len(env.operators)),
    }
    
    for i, op := range env.operators {
        dag.Operators[i] = &Operator{
            Name:     op.Name,
            Parallel: op.Parallel,
            Fn:       op.Fn,
            State:    make(map[string]interface{}),
            Input:    make(chan interface{}, 1000),
            Output:   make(chan interface{}, 1000),
        }
    }
    
    // 连接算子
    for i := 0; i < len(dag.Operators)-1; i++ {
        go func(from, to *Operator) {
            for data := range from.Output {
                to.Input <- data
            }
        }(dag.Operators[i], dag.Operators[i+1])
    }
    
    return dag
}
```

---

## 第三部分：窗口深度

### 3.1 窗口类型

```
1. Tumbling Window：滚动窗口（固定大小，不重叠）
2. Sliding Window：滑动窗口（固定大小，可重叠）
3. Session Window：会话窗口（无固定大小，按间隙分割）
4. Global Window：全局窗口（所有数据在一个窗口）
```

### 3.2 Go 实现窗口

```go
type WindowAssigner interface {
    AssignWindows(interface{}, time.Time, WindowContext) []Window
}

type TumblingEventTimeWindows struct {
    Size time.Duration
}

func (w *TumblingEventTimeWindows) AssignWindows(
    element interface{},
    timestamp time.Time,
    ctx WindowContext,
) []Window {
    start := timestamp.Tr(w.Size)
    end := start.Add(w.Size)
    
    return []Window{{
        Start: start,
        End:   end,
    }}
}

type Window struct {
    Start time.Time
    End   time.Time
}

type WindowContext interface {
    GetCurrentProcessingTime() time.Time
    GetCurrentWatermark() time.Time
}

// WindowOperator 窗口操作器
type WindowOperator struct {
    assigner WindowAssigner
    trigger  Trigger
    evictor  Evictor
    windowFn FoldFunction
    state    map[string]*WindowState
}

type WindowState struct {
    Elements []interface{}
    Window   Window
}

func (wo *WindowOperator) ProcessElement(element interface{}, timestamp time.Time, ctx WindowContext) {
    windows := wo.assigner.AssignWindows(element, timestamp, ctx)
    
    for _, window := range windows {
        key := fmt.Sprintf("%s-%d", element, window.Start.Unix())
        ws, ok := wo.state[key]
        if !ok {
            ws = &WindowState{Window: window}
            wo.state[key] = ws
        }
        ws.Elements = append(ws.Elements, element)
    }
    
    // 检查水位线，触发计算
    if ctx.GetCurrentWatermark().After(window.End) {
        wo.triggerWindow(key, ws)
        delete(wo.state, key)
    }
}

func (wo *WindowOperator) triggerWindow(key string, ws *WindowState) {
    result := wo.windowFn.Fold(ws.Elements)
    fmt.Printf("Window %s result: %v\n", key, result)
}
```

---

## 第四部分：状态管理深度

### 4.1 Flink 状态类型

```
1. Keyed State：键控状态
   → ValueState：单个值
   → ListState：列表
   → MapState：映射
   → ReducingState：聚合

2. Operator State：算子状态
   → 用于 Source/Sink
   → 并行度可变

3. Checkpoint State：检查点状态
   → 定期快照
   → 故障恢复
```

### 4.2 Go 实现状态管理

```go
type StateBackend interface {
    Put(key string, value interface{}) error
    Get(key string) (interface{}, error)
    Delete(key string) error
    Snapshot() error
    Restore() error
}

type MemoryStateBackend struct {
    state map[string]interface{}
}

func (mb *MemoryStateBackend) Put(key string, value interface{}) error {
    mb.state[key] = value
    return nil
}

func (mb *MemoryStateBackend) Get(key string) (interface{}, error) {
    val, ok := mb.state[key]
    if !ok {
        return nil, fmt.Errorf("key not found")
    }
    return val, nil
}

type RocksDBStateBackend struct {
    db *badger.DB
}

func (rb *RocksDBStateBackend) Put(key string, value interface{}) error {
    data, _ := json.Marshal(value)
    return rb.db.Update(func(txn *badger.Txn) error {
        return txn.Set([]byte(key), data)
    })
}

func (rb *RocksDBStateBackend) Get(key string) (interface{}, error) {
    item, err := rb.db.Get([]byte(key))
    if err != nil {
        return nil, err
    }
    
    var value interface{}
    err = item.Value(func(val []byte) error {
        return json.Unmarshal(val, &value)
    })
    return value, err
}

// ValueState 值状态
type ValueState struct {
    backend StateBackend
    key     string
}

func (vs *ValueState) Value() (interface{}, error) {
    return vs.backend.Get(vs.key)
}

func (vs *ValueState) Update(value interface{}) error {
    return vs.backend.Put(vs.key, value)
}

// ListState 列表状态
type ListState struct {
    backend StateBackend
    key     string
}

func (ls *ListState) Add(value interface{}) error {
    current, err := ls.backend.Get(ls.key)
    if err != nil {
        current = []interface{}{}
    }
    
    list := current.([]interface{})
    list = append(list, value)
    
    return ls.backend.Put(ls.key, list)
}

func (ls *ListState) All() ([]interface{}, error) {
    val, err := ls.backend.Get(ls.key)
    if err != nil {
        return []interface{}{}, nil
    }
    return val.([]interface{}), nil
}
```

---

## 第五部分：Exactly-once 深度

### 5.1 Two-Phase Commit

```
两阶段提交保证 Exactly-once：
1. Prepare 阶段：预提交
2. Commit 阶段：正式提交

配合 Checkpoint：
1. 触发 Checkpoint
2. Barrier 插入数据流
3. Operator 保存状态
4. Sink 预提交
5. Checkpoint 完成
6. Sink 正式提交
```

### 5.2 Go 实现两阶段提交

```go
type TwoPhaseCommitSink struct {
    backend   StateBackend
    checkpointID int64
}

func (s *TwoPhaseCommitSink) Write(data interface{}) error {
    // 1. 预提交
    err := s.prepareCommit(data)
    if err != nil {
        return err
    }
    
    // 2. 写入数据
    return s.backend.Put(fmt.Sprintf("data-%d", s.checkpointID), data)
}

func (s *TwoPhaseCommitSink) prepareCommit(data interface{}) error {
    // 预提交逻辑
    // ...
    return nil
}

func (s *TwoPhaseCommitSink) commit(checkpointID int64) error {
    // 正式提交
    // ...
    return nil
}

func (s *TwoPhaseCommitSink) abort(checkpointID int64) error {
    // 回滚
    // ...
    return nil
}
```

---

## 第六部分：生产排障案例

### 6.1 背压

```
现象：Flink 任务出现背压

排查：
1. 检查 Flink Web UI 的 Backpressure
2. 检查 Task 执行时间
3. 检查网络带宽

根因：下游处理速度慢

解决方案：
1. 增加并行度
2. 优化算子
3. 增加网络带宽
```

### 6.2 Checkpoint 失败

```
现象：Checkpoint 超时

排查：
1. 检查状态大小
2. 检查后端存储
3. 检查网络带宽

根因：状态太大

解决方案：
1. 使用 RocksDBStateBackend
2. 增量 Checkpoint
3. 增加超时时间
```

---

## 第七部分：自测题

### 问题 1
Flink 相比 Spark Streaming 有什么优势？

<details>
<summary>查看答案</summary>

1. **真正的流处理**：微批 vs 真流
2. **低延迟**：毫秒级
3. **状态管理**：内置状态
4. **Exactly-once**：端到端保证
5. **Go 实现**：StreamExecutionEnvironment

</details>

### 问题 2
Flink 的窗口有哪些类型？

<details>
<summary>查看答案</summary>

1. **Tumbling**：滚动窗口
2. **Sliding**：滑动窗口
3. **Session**：会话窗口
4. **Global**：全局窗口
5. **Go 实现**：TumblingEventTimeWindows

</details>

### 问题 3
如何保证 Flink 的 Exactly-once？

<details>
<summary>查看答案</summary>

1. **Checkpoint**：定期快照
2. **Two-Phase Commit**：两阶段提交
3. **幂等写入**：重复写入不影响
4. **状态后端**：RocksDB
5. **Go 实现**：TwoPhaseCommitSink

</details>

---

*本文档基于 Flink 原理整理。*