# 时序数据库实战指南

> InfluxDB/TimescaleDB/Prometheus 对比与选型。

---

## 1. 核心概念

| 概念 | 说明 |
|------|------|
| Time Series | 带时间戳的数据序列 |
| Metric | 度量指标名称 |
| Tag | 维度标签（索引） |
| Field | 数值字段 |
| Timestamp | 时间戳 |

---

## 2. InfluxDB 使用

```influxql
-- 写入数据
INSERT metrics,host=server01,cpu=cpu0 usage_user=45.4,usage_system=12.3

-- 查询数据
SELECT mean("usage_user") FROM "metrics"
WHERE time >= now() - 1h
GROUP BY time(10s), "host"

-- 聚合函数
SELECT last(), min(), max(), percentile()
```

---

## 3. TimescaleDB (PostgreSQL 扩展)

```sql
-- 创建超表
CREATE TABLE metrics (
    time TIMESTAMPTZ NOT NULL,
    metric_id TEXT,
    value DOUBLE PRECISION
);

SELECT create_hypertable('metrics', 'time');

-- 查询
SELECT time_bucket('1h', time) AS hour,
       avg(value) 
FROM metrics 
WHERE time > now() - 24h
GROUP BY hour ORDER BY hour;
```

---

## 4. Prometheus 查询 (PromQL)

```promql
# 瞬时向量
http_requests_total

# 区间向量
http_requests_total[5m]

# 聚合
sum by (job) (http_requests_total)
rate(http_requests_total[5m])

# 函数
rate, increase, avg, sum, histogram_quantile
```

---

## 5. 选型建议

| 场景 | 推荐 |
|------|------|
| 应用监控 | Prometheus |
| 业务指标 | TimescaleDB |
| IoT 数据 | InfluxDB |
| 日志分析 | Loki + Promtail |

---

**参考**: 各数据库官方文档、时序数据最佳实践
