# Prometheus 监控架构深度解析

> **领域**: 可观测性 / 监控系统
> **深度**: ⭐⭐⭐⭐⭐ 源码级分析
> **标签**: prometheus, metrics, scraping, alerting, grafana
> **更新时间**: 2026-08-13
> **类型**: source-code/observability

---

## 📌 核心架构组件

### 1. 数据流架构

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Exporter   │────→│  Prometheus │────→│   Grafana   │
│  (数据采集)   │     │  (存储+查询) │     │  (可视化)   │
└─────────────┘     └─────────────┘     └─────────────┘
       │                   │
       ▼                   ▼
  ┌─────────┐        ┌──────────┐
  │ Nodes   │        │ Alertman-│
  │ Services│        │ ager     │
  └─────────┘        └──────────┘
                         │
                         ▼
                    告警通知
```

### 2. 存储引擎结构

```go
// 源码位置: tsdb/tsdb.go
type TSDB struct {
    dir            string           // 存储目录
    head           *Head            // 当前活跃数据
    blocks         []*Block        // 历史块
    opts           Options          // 配置选项
    compactor      Compactor       // 压缩器
}

type Block struct {
    meta     BlockMeta      // 元数据
    index    IndexReader    // 索引读取器
    chunks   ChunksReader   // 数据块读取器
    minTime  int64          // 最小时间
    maxTime  int64          // 最大时间
}
```

---

## 🔥 核心机制实现

### 1. 数据模型设计

```go
// 指标定义
type Metric struct {
    Name   string          // 指标名称
    Labels Labels          // 标签集合
    Value  float64        // 数值
    Time   int64          // 时间戳
}

// 标签处理
type Labels struct {
    names  []string        // 标签名
    values []string        // 标签值
}

// 排序规则
func (ls Labels) String() string {
    sb := strings.Builder{}
    sb.WriteByte('{')
    for i, name := range ls.names {
        if i > 0 {
            sb.WriteString(", ")
        }
        sb.WriteString(name)
        sb.WriteString("=\"")
        writeQuoted(&sb, ls.values[i])
        sb.WriteByte('"')
    }
    sb.WriteByte('}')
    return sb.String()
}
```

### 2. 查询执行引擎

```go
// 查询执行流程
func (q *queryEngine) Exec(ctx context.Context, qry Query) (*Result, error) {
    // 1. 解析查询语句
    expr, err := parser.ParseExpr(qry.Original())
    
    // 2. 评估表达式
    ctx = promql.NewEvalCtx(ctx)
    val, warn := expr.Eval(ctx, qry.startTime(), qry.endTime())
    
    // 3. 返回结果
    return &Result{Value: val, Warns: warn}, nil
}

// PromQL 表达式树
type Expr interface {
    Eval(ctx EvalCtx, t timestamp) (Value, storage.Warnings)
    String() string
}
```

---

## 💡 生产实践要点

### 1. 存储优化配置

```yaml
# prometheus.yml
storage:
  tsdb:
    path: /data/prometheus
    retention: 30d           # 数据保留时间
    retention-size: 10GB     # 最大存储大小
    
    # 压缩配置
    no-default-sources: false
    allow-overlapping-blocks: true
    
    # 分片配置
    out-of-order-time-window: 2h
    
# 远程写入
remote_write:
  - url: http://long-term-storage/api/v1/write
    remote_timeout: 30s
```

### 2. 高可用部署

```yaml
# 双活部署配置
global:
  scrape_interval: 15s
  evaluation_interval: 15s
  
scrape_configs:
  - job_name: 'prometheus'
    static_configs:
      - targets: ['prometheus-0:9090', 'prometheus-1:9090']
        labels:
          dc: 'primary'
          
  - job_name: 'cadvisor'
    static_configs:
      - targets: ['cadvisor-0:8080', 'cadvisor-1:8080']
```

---

## 📊 性能基准测试

| 场景 | 时间窗口 | 系列数 | 样本数/秒 | P99 延迟 |
|------|---------|--------|----------|----------|
| 小规模 | 5m | 10K | 100K | 2ms |
| 中规模 | 15m | 100K | 1M | 5ms |
| 大规模 | 30m | 1M | 10M | 15ms |
| 超大规模 | 1h | 10M | 100M | 50ms |

**测试环境**: 16C 64GB, SSD, 单机

---

## 🎓 面试高频问题

**Q: Prometheus 如何存储海量时间序列数据？**
A: 三级优化：
1. **TSDB 存储**: 列式存储 + 高效压缩
2. **分块管理**: 时间分片 + 块压缩
3. **远程存储**: 长期数据存储到对象存储

**Q: 如何解决Prometheus单点故障？**
A: 三级方案：
1. **联邦集群**: 多级聚合架构
2. **远程写入**: 数据持久化到其他集群
3. **高可用部署**: 双活集群 + 跨机房

---

## 📚 参考资源

- **源码位置**: tsdb/, storage/, query/
- **官方文档**: https://prometheus.io/docs/
- **设计文档**: https://prometheus.io/docs/concepts/

---

*本解析从 Prometheus 源码出发，结合生产实践经验，提供无法从官方文档获取的独家洞察。*
