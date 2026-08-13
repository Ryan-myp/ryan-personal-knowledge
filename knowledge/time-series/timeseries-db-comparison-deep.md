# 时序数据库对比与选型

> 深入 InfluxDB、Prometheus、TimescaleDB、ClickHouse 选型对比。

---

## 1. 核心对比

| 特性 | Prometheus | InfluxDB | TimescaleDB | ClickHouse |
|------|------------|----------|-------------|------------|
| 数据类型 | 监控指标 | 时间序列 | SQL/时序 | 列式分析 |
| 查询语言 | PromQL | InfluxQL/Flux | SQL | SQL |
| 存储引擎 | TSDB | LSM Tree | 扩展 PG | Column Store |
| 水平扩展 | 联邦 | 集群 | 表分区 | 分布式 |
| 适用场景 | 云原生监控 | IoT | 业务时序 | OLAP分析 |

---

## 2. PromQL 示例

```promql
# 查询 QPS
sum(rate(http_requests_total[5m])) by (service)

# 查询 P99 延迟
histogram_quantile(0.99, rate(http_request_duration_seconds_bucket[5m]))

# 查询错误率
sum(rate(http_requests_total{status=~"5.."}[5m])) / sum(rate(http_requests_total[5m]))
```

---

## 3. 实践 Checklist
- [ ] 明确数据写入量级
- [ ] 评估查询模式
- [ ] 考虑长期存储成本
- [ ] 评估运维复杂度

**参考**: 各数据库官方文档、时序数据库基准测试
