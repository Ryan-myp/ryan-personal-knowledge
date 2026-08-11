# 日志系统设计深度解析

> 深入日志系统：采集、传输、存储、查询、分析。
> 包含 ELK、Loki、Opentelemetry 等主流方案。
> 适用对象：SRE、后端工程师、可观测性工程师

---

## 1. 日志系统架构

### 1.1 经典架构

```
┌─────────────────────────────────────────────────────────────┐
│                  日志系统架构                                │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  采集层 (Collection)                                         │
│  ├── Filebeat: 文件采集                                     │
│  ├── Fluentd: 日志转发                                      │
│  ├── Logstash: 日志处理                                     │
│  └── OpenTelemetry: 可观测性采集                             │
│                                                             │
│  传输层 (Transport)                                          │
│  ├── Kafka: 消息队列缓冲                                     │
│  ├── Redis: 快速缓冲                                        │
│  └── Redis Stream: 流式处理                                 │
│                                                             │
│  存储层 (Storage)                                            │
│  ├── Elasticsearch: 全文检索                                │
│  ├── Loki: 低成本存储                                       │
│  └── ClickHouse: 分析查询                                   │
│                                                             │
│  查询层 (Query)                                              │
│  ├── Kibana: 可视化                                         │
│  ├── Grafana: 监控面板                                      │
│  └── Lucene Query: 查询语言                                 │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 1.2 数据流

```
应用 → Agent → Queue → Processor → Storage → Query

1. 应用产生日志
2. Agent 采集日志（Filebeat/Fluentd）
3. 日志推送到消息队列（Kafka）
4. Processor 处理日志（Logstash/OpenTelemetry）
5. 存储到搜索引擎（ES/Loki）
6. 查询和可视化（Kibana/Grafana）
```

---

## 2. 日志采集

### 2.1 Filebeat 架构

```yaml
# filebeat.yml

filebeat.inputs:
- type: log
  enabled: true
  paths:
    - /var/log/*.log
    - /var/log/app/*.log
  multiline.pattern: '^\['
  multiline.negate: false
  multiline.match: after

output.kafka:
  hosts: ["kafka1:9092", "kafka2:9092"]
  topic: 'logs'
  partition.round_robin:
    reachable_only: true

processors:
- add_cloud_metadata: ~
- add_docker_metadata: ~
- timestamp:
    field: time
    layouts:
      - '2006-01-02T15:04:05.000Z'
```

### 2.2 Go 实现日志采集器

```go
// log_collector.go

package collector

import (
    "os"
    "path/filepath"
    "time"
)

type LogCollector struct {
    paths    []string
    channel  chan LogEntry
    stopChan chan struct{}
}

type LogEntry struct {
    Timestamp time.Time
    Level     string
    Message   string
    Source    string
}

func NewLogCollector(paths []string) *LogCollector {
    return &LogCollector{
        paths:   paths,
        channel: make(chan LogEntry, 1000),
    }
}

func (c *LogCollector) Start() {
    c.stopChan = make(chan struct{})
    
    for _, path := range c.paths {
        go c.watchFile(path)
    }
}

func (c *LogCollector) watchFile(path string) {
    // 跟踪文件位置
    pos := 0
    
    for {
        select {
        case <-c.stopChan:
            return
        default:
        }
        
        // 读取新行
        lines, newPos, err := readNewLines(path, pos)
        if err != nil {
            time.Sleep(time.Second)
            continue
        }
        
        for _, line := range lines {
            entry := parseLogLine(line, path)
            c.channel <- entry
        }
        
        pos = newPos
    }
}

func (c *LogCollector) Entries() <-chan LogEntry {
    return c.channel
}

func (c *LogCollector) Stop() {
    close(c.stopChan)
}
```

---

## 3. 日志存储

### 3.1 Elasticsearch 设计

```json
{
  "mappings": {
    "properties": {
      "timestamp": { "type": "date" },
      "level": { "type": "keyword" },
      "service": { "type": "keyword" },
      "message": { 
        "type": "text",
        "fields": {
          "keyword": { "type": "keyword", "ignore_above": 256 }
        }
      },
      "trace_id": { "type": "keyword" },
      "user_id": { "type": "keyword" }
    }
  },
  "settings": {
    "number_of_shards": 5,
    "number_of_replicas": 1,
    "index.lifecycle.name": "logs-policy"
  }
}
```

### 3.2 Loki 设计

```yaml
# loki-config.yaml

schema_config:
  configs:
    - from: 2020-10-24
      store: tsdb
      object_store: s3
      schema: v13
      index:
        prefix: index_
        period: 24h

ruler:
  storage:
    type: s3
    s3:
      endpoint: s3.amazonaws.com
  rule_path: /tmp/loki/rules

storage_config:
  aws:
    s3: s3://loki-bucket/
  tsdb_shipper:
    active_index_directory: /loki/index
    cache_location: /loki/cache
```

---

## 4. 日志查询

### 4.1 LogQL 查询

```
# 基础查询
{service="api"} |= "error"

# 时间范围
{service="api"} |= "timeout" |~ "2024-01-01.*"

# 聚合统计
count_over_time({service="api"} |= "error"[5m])

# 按级别统计
count by (level) ({service="api"})

# 顶部错误
topk(10, sum by (message) (count_over_time({service="api"} |= "error"[1h])))
```

### 4.2 Lucene 查询

```
# 基础查询
service:api AND level:error

# 模糊查询
message:"connection timeout"

# 范围查询
timestamp:[2024-01-01T00:00:00Z TO 2024-01-31T23:59:59Z]

# 正则查询
message:.*Exception.*
```

---

## 5. 日志分析

### 5.1 异常检测

```go
// anomaly_detection.go

package analysis

import (
    "math"
)

type AnomalyDetector struct {
    windowSize int
    threshold  float64
}

func (d *AnomalyDetector) Detect(logs []LogEntry) []Anomaly {
    var anomalies []Anomaly
    
    // 滑动窗口统计
    for i := d.windowSize; i < len(logs); i++ {
        window := logs[i-d.windowSize : i]
        
        // 计算错误率
        errorCount := 0
        for _, log := range window {
            if log.Level == "ERROR" {
                errorCount++
            }
        }
        
        errorRate := float64(errorCount) / float64(d.windowSize)
        
        // 检测异常
        if errorRate > d.threshold {
            anomalies = append(anomalies, Anomaly{
                Timestamp: logs[i].Timestamp,
                Rate:      errorRate,
                Type:      "error_spike",
            })
        }
    }
    
    return anomalies
}

type Anomaly struct {
    Timestamp time.Time
    Rate      float64
    Type      string
}
```

### 5.2 日志模式识别

```
日志模式识别算法：

1. 提取日志模板
   - 去除动态部分（ID、时间、IP）
   - 保留固定部分

2. 聚类相似日志
   - 使用编辑距离
   - 使用哈希指纹

3. 统计频率
   - 识别常见模式
   - 发现异常模式
```

---

## 6. 性能优化

### 6.1 采集优化

```go
// 批量发送
func (c *Collector) BatchSend(entries []LogEntry) error {
    // 批量缓冲
    batchSize := 100
    batch := make([]LogEntry, 0, batchSize)
    
    for _, entry := range entries {
        batch = append(batch, entry)
        
        if len(batch) >= batchSize {
            c.sendBatch(batch)
            batch = batch[:0]
        }
    }
    
    // 发送剩余
    if len(batch) > 0 {
        c.sendBatch(batch)
    }
    
    return nil
}
```

### 6.2 存储优化

```yaml
# 索引生命周期管理
PUT _ilm/policy/logs-policy
{
  "policy": {
    "phases": {
      "hot": {
        "actions": {
          "rollover": {
            "max_size": "50gb",
            "max_age": "7d"
          }
        }
      },
      "warm": {
        "min_age": "7d",
        "actions": {
          "shrink": {
            "number_of_shards": 1
          }
        }
      },
      "cold": {
        "min_age": "30d",
        "actions": {
          "freeze": {}
        }
      },
      "delete": {
        "min_age": "90d",
        "actions": {
          "delete": {}
        }
      }
    }
  }
}
```

---

## 7. 故障排查

### 7.1 常见问题

| 问题 | 症状 | 排查命令 | 解决方案 |
|------|------|----------|----------|
| 采集延迟 | 日志滞后 | 检查 Agent 状态 | 调整 buffer |
| 查询慢 | 响应时间长 | 分析慢查询 | 优化索引 |
| 存储满 | 写入失败 | 检查磁盘使用 | 清理旧索引 |
| 数据丢失 | 日志缺失 | 检查传输链路 | 增加重试 |

---

## 8. 总结

### 8.1 核心原理回顾

| 模块 | 核心机制 |
|------|----------|
| 采集 | Filebeat/Fluentd |
| 传输 | Kafka 缓冲 |
| 存储 | ES/Loki |
| 查询 | LogQL/Lucene |
| 分析 | 异常检测 |

### 8.2 最佳实践

- [ ] 合理设计索引
- [ ] 配置生命周期管理
- [ ] 优化查询性能
- [ ] 监控存储使用
- [ ] 建立告警机制

---

*最后更新：2026-08-11*
*作者：Ryan*
