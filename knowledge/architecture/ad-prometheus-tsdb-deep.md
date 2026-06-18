# Prometheus 深度：TSDB/Scrape/Rule 源码级

> 逐行解析 Prometheus 核心组件：TSDB、Scrape、Rule Evaluation

---

## 第一部分：TSDB 源码深度

### TSDB 架构

```
Prometheus TSDB 结构：
┌─────────────────────────────────────────────────────────────────────┐
│ TSDB Directory                                                       │
│ ├── chunks/                                                          │
│ │   └── 000001/                                                      │
│ │       ├── 000001.prometheus                                       │
│ │       └── ...                                                      │
│ ├── wal/                                                             │
│ │   ├── 00000001                                                     │
│ │   ├── 00000002                                                     │
│ │   └── ...                                                          │
│ ├── meta.json                                                        │
│ └── index/                                                           │
│     ├── 000004.index                                                 │
│     └── ...                                                          │
│                                                                     │
│ 数据模型：                                                           │
│ • Series: {__name__, job, instance, ...} → 唯一标识                  │
│ • Sample: (timestamp, value) → 时序数据点                            │
│ • Chunk: 一组连续的 samples（压缩存储）                               │
│ • Block: 一组 chunks（可删除、可 compact）                            │
└─────────────────────────────────────────────────────────────────────┘
```

### tsdb.go 源码逐行解析

```go
// Prometheus 源码：tsdb/tsdb.go
type TSDB struct {
    dir              string
    head             *Head
    compacters       []Compactor
    l                prometheus.Labels
    logger           log.Logger
    metrics          *tsdbMetrics
    opts             *Options
    chunkPool        chunk.Pool
    wal              *wal.WAL
    indexWriters     []indexWriter
    activeAppenders  int32
    closed           chan struct{}
    quit             chan struct{}
    reloadables      []Reloadable
}

// Open 打开 TSDB
func Open(dir string, l log.Logger, r prometheus.Registerer, opts *Options) (*TSDB, error) {
    // 1. 创建 head
    head, err := NewHead(nil, l, r, opts)
    if err != nil {
        return nil, err
    }
    
    // 2. 打开 WAL
    wal, err := wal.NewWAL(l, r, dir)
    if err != nil {
        return nil, err
    }
    
    // 3. 回放 WAL
    if err := head replaysamples(wal); err != nil {
        return nil, err
    }
    
    // 4. 创建 TSDB 实例
    db := &TSDB{
        dir:       dir,
        head:      head,
        wal:       wal,
        logger:    l,
        metrics:   newTsdbMetrics(r),
        opts:      opts,
        closed:    make(chan struct{}),
        quit:      make(chan struct{}),
    }
    
    // 5. 启动 compactor
    go db.compactLoop()
    
    // 6. 启动 retention
    go db.retentionLoop()
    
    return db, nil
}

// Append 追加样本
func (db *TSDB) Append(ctx context.Context, ref storage.SeriesRef, lset labels.Labels, t int64, v float64) (storage.SeriesRef, error) {
    // 1. 增加 active appenders 计数
    atomic.AddInt32(&db.activeAppenders, 1)
    defer atomic.AddInt32(&db.activeAppenders, -1)
    
    // 2. 写入 head
    ref, err := db.head.Append(ref, lset, t, v)
    if err != nil {
        return 0, err
    }
    
    // 3. 写入 WAL
    if err := db.wal.Log(&wal.Record{
        Type: wal.Checkpoint,
        Data: &wal.MmapRef{
            Offset: int64(ref),
            Len:    int64(ref),
        },
    }); err != nil {
        return 0, err
    }
    
    return ref, nil
}
```

### Head 源码逐行解析

```go
// Prometheus 源码：tsdb/head.go
type Head struct {
    opts         *HeadOptions
    minTime      int64
    maxTime      int64
    series       *memSeries
    chunks       []chunkDiskMapper
    appender     storage.Appender
    wal          *wal.WAL
    index        *indexWriter
    mmappedChunks map[uint64][]*mmappedChunk
    stats        *HeadStats
}

// Append 追加样本到 head
func (h *Head) Append(ref storage.SeriesRef, lset labels.Labels, t int64, v float64) (storage.SeriesRef, error) {
    // 1. 查找或创建 series
    s := h.getOrCreate(lset)
    if s == nil {
        return 0, errors.New("series not found")
    }
    
    // 2. 检查时间戳是否递增
    if t <= s.maxTime {
        return 0, errors.New("out of order sample")
    }
    
    // 3. 追加到 memChunk
    if s.memChunk == nil {
        s.memChunk = &memChunk{
            chunks: make([]chunk.Chunk, 0, 2),
        }
    }
    
    // 4. 写入 chunk
    s.memChunk.chunks = append(s.memChunk.chunks, chunk.Chunk{
        Timestamp: t,
        Value:     v,
    })
    
    // 5. 更新 maxTime
    h.maxTime = t
    
    return storage.SeriesRef(s.hash), nil
}
```

---

## 第二部分：Block Compaction 源码深度

### Compaction 流程

```
Compaction 流程：
1. 收集所有活跃的 head chunks
2. 合并为 block（默认 2 小时）
3. 写入磁盘（chunks + index）
4. 标记旧 block 为 compacted
5. 后台 goroutine 持续 compact
```

### compact.go 源码逐行解析

```go
// Prometheus 源码：tsdb/block.go
type BlockMeta struct {
    ULID            ulid.ULID          `json:"ulid"`
    MinTime         int64              `json:"minTime"`
    MaxTime         int64              `json:"maxTime"`
    Stats           BlockStats         `json:"stats"`
    Compaction      CompactionMeta     `json:"compaction"`
    Series          SeriesReference    `json:"series"`
    Chunks          ChunksMeta         `json:"chunks"`
    IndexHeader     IndexHeader        `json:"indexHeader"`
}

// Compact 合并 blocks
func (b *BlockWriter) Compact(blocks []*Block) (*Block, error) {
    // 1. 收集所有 series
    allSeries := make(map[uint64]*Series)
    for _, block := range blocks {
        for _, series := range block.series {
            allSeries[series.ref] = series
        }
    }
    
    // 2. 合并 chunks
    for ref, series := range allSeries {
        series.chunks = mergeChunks(series.chunks)
    }
    
    // 3. 创建新 block
    newBlock := &Block{
        meta: &BlockMeta{
            ULID:    generateULID(),
            MinTime: blocks[0].meta.MinTime,
            MaxTime: blocks[len(blocks)-1].meta.MaxTime,
            Stats: BlockStats{
                NumSamples: countSamples(allSeries),
                NumSeries:  len(allSeries),
            },
        },
        series: allSeries,
    }
    
    // 4. 写入磁盘
    if err := b.write(newBlock); err != nil {
        return nil, err
    }
    
    return newBlock, nil
}

// mergeChunks 合并 chunks
func mergeChunks(chunks []chunk.Chunk) []chunk.Chunk {
    merged := make([]chunk.Chunk, 0, len(chunks))
    for _, chunk := range chunks {
        merged = append(merged, chunk)
    }
    return merged
}
```

---

## 第三部分：Rule Evaluation 源码深度

### Rule Evaluation 流程

```
Rule Evaluation 流程：
1. 定时触发（默认 15s）
2. 解析 PromQL 表达式
3. 执行查询
4. 写入结果到 TSDB
5. 更新 Alertmanager
```

### rule.go 源码逐行解析

```go
// Prometheus 源码：rules/rules.go
type RuleGroup struct {
    name     string
    file     string
    rules    []Rule
    interval time.Duration
    queryEngine *query.Engine
    sampleAppender storage.Appender
    logger log.Logger
    ctx context.Context
}

// Run 运行 rule group
func (g *RuleGroup) Run() {
    ticker := time.NewTicker(g.interval)
    defer ticker.Stop()
    
    for {
        select {
        case <-g.ctx.Done():
            return
        case <-ticker.C:
            g.eval()
        }
    }
}

// eval 评估规则
func (g *RuleGroup) eval() {
    for _, rule := range g.rules {
        start := time.Now()
        
        // 1. 执行 PromQL 查询
        ctx, cancel := context.WithTimeout(g.ctx, g.interval)
        result, err := g.queryEngine.Exec(ctx, rule.query)
        cancel()
        
        if err != nil {
            g.logger.Error("eval error", "rule", rule.name, "err", err)
            continue
        }
        
        // 2. 写入结果
        appender := g.sampleAppender.Begin()
        for _, sample := range result {
            appender.Append(sample)
        }
        appender.Commit()
        
        // 3. 更新 rule state
        rule.update(result, time.Since(start))
    }
}
```

---

## 第四部分：自测题

### Q1: Prometheus 为什么用 TSDB 而不是 MySQL？

**A**:
- TSDB 专为时序数据优化
- 列式存储，压缩率高
- 原生支持 PromQL
- 单机可扩展到 PB 级

### Q2: TSDB 的 block 大小怎么设置？

**A**:
- 默认 2 小时
- 根据数据量和查询需求调整
- 太小：频繁 compaction
- 太大：查询慢

### Q3: Rule Evaluation 的延迟怎么优化？

**A**:
- 减少 rule group 数量
- 优化 PromQL 查询
- 增加 query engine 并发
- 使用 recording rules

---

## 第五部分：生产实践

### 1. TSDB 调优

```
TSDB 调优要点：
1. 合理设置 block 大小
2. 监控 disk usage
3. 定期 compact
4. 设置 retention period
```

### 2. Scrape 调优

```
Scrape 调优要点：
1. 合理设置 scrape_interval
2. 监控 scrape 延迟
3. 使用 service discovery
4. 设置 scrape_timeout
```

### 3. Rule 调优

```
Rule 调优要点：
1. 避免复杂查询
2. 使用 recording rules
3. 监控 rule 执行时间
4. 合理设置 evaluation_interval
```
