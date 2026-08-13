# EFK日志系统 - 资深专家深度实现

## 一、架构设计

```
┌─────────────────────────────────────────────────────────────────────┐
│                         EFK架构                                      │
│                                                                     │
│  ┌─────────┐    ┌──────────┐    ┌─────────────┐                   │
│  │  App A  │───►│ Filebeat │───►│ Elasticsearch │                   │
│  │  App B  │───►│ (采集)    │    │ (存储/搜索)   │                   │
│  └─────────┘    └──────────┘    └──────┬──────┘                   │
│                                         │                           │
│                                      ┌──┴──┐                      │
│                                      │Kibana│                      │
│                                      │(可视化)│                     │
│                                      └───────┘                     │
└─────────────────────────────────────────────────────────────────────┘
```

## 二、Filebeat配置

### 2.1 基本配置

```yaml
filebeat.inputs:
- type: log
  enabled: true
  paths:
    - /var/log/myapp/*.log
  fields:
    app: myapp
    env: production
  fields_under_root: true
  json.keys_under_root: true
  json.add_error_key: true

output.elasticsearch:
  hosts: ["es:9200"]
  index: "myapp-%{+yyyy.MM.dd}"
  
processors:
- add_cloud_metadata: ~
- add_docker_metadata: ~
- drop_fields:
    fields: ["agent", "ecs", "host"]
```

### 2.2 多行匹配

```yaml
filebeat.inputs:
- type: log
  enable: true
  paths:
    - /var/log/myapp/*.log
  multiline.pattern: '^\['
  multiline.match: after
  multiline.max_lines: 10
```

## 三、Elasticsearch索引策略

### 3.1 索引生命周期

```json
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
          "shrink": { "number_of_shards": 1 },
          "forcemerge": { "max_num_segments": 1 }
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

### 3.2 模板配置

```json
{
  "index_patterns": ["myapp-*"],
  "settings": {
    "number_of_shards": 3,
    "number_of_replicas": 1,
    "refresh_interval": "30s"
  },
  "mappings": {
    "properties": {
      "timestamp": { "type": "date" },
      "level": { "type": "keyword" },
      "message": { "type": "text" },
      "app": { "type": "keyword" },
      "host": { "type": "keyword" }
    }
  }
}
```

## 四、性能优化

### 4.1 Filebeat优化

```yaml
# 调整缓冲区大小
filebeat.harvester.buffer_size: 16384
filebeat.prospector.scanner.buffer_size: 256

# 批量发送
output.elasticsearch.batch_max_size: 2048
output.elasticsearch.bulk_max_size: 2048
```

### 4.2 ES优化

```yaml
# JVM堆内存 (不超过32GB)
-Xms16g
-Xmx16g

# 索引调优
index.refresh_interval: 30s
index.translog.durability: async
index.translog.sync_interval: 5s
```

## 五、故障排查

### 5.1 常见问题

```
问题1: Filebeat丢失日志
解决: 检查磁盘空间，调整flush_timeout

问题2: ES写入慢
解决: 增加分片数，调整bulk size

问题3: Kibana查询慢
解决: 减少时间范围，优化查询语句
```

### 5.2 监控指标

```yaml
# Prometheus指标
filebeat_beats_output_write_errors
filebeat_libbeat_output_requests
elasticsearch_indices_docs
elasticsearch_indices_store_size
```

## 六、面试高频题

### Q1: EFK和ELK有什么区别？

```
A: EFK使用Filebeat代替Logstash，更轻量。
```

### Q2: 如何处理日志爆炸？

```
A:
1. 采样采集
2. 冷热分离
3. 设置索引生命周期
```

## 七、自测题

1. 解释EFK架构各组件作用
2. 如何实现日志滚动删除？

---

## 参考文档

- [Filebeat文档](https://www.elastic.co/guide/en/beats/filebeat/current/index.html)
- [ES索引生命周期](https://www.elastic.co/guide/en/elasticsearch/reference/current/index-lifecycle-management.html)
