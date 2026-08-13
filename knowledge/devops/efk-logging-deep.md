# EFk日志系统 - 资深专家深度实现

## 一、架构设计

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    EFK 日志系统架构                                        │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   应用层                  Filebeat              Elasticsearch            │
│   ┌─────────┐         ┌──────────┐         ┌─────────────┐             │
│   │  App A  │────────►│  Filebeat │────────►│ Index: logs   │             │
│   │  App B  │────────►│  (采集)   │         │ (存储/搜索)   │             │
│   └─────────┘         └──────────┘         └──────┬──────┘             │
│                                                     │                   │
│                                                  ┌──┴──┐               │
│                                                  │ Kibana│               │
│                                                  │(可视化)│               │
│                                                  └───────┘               │
│                                                                         →
└─────────────────────────────────────────────────────────────────────────┘
```

## 二、Filebeat配置

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

output.elasticsearch:
  hosts: ["es:9200"]
  index: "myapp-%{+yyyy.MM.dd}"
  
processors:
- add_cloud_metadata: ~
- add_docker_metadata: ~
```

## 三、面试高频题

### Q1: EFK vs ELK区别？

```
A:
1. EFK: Filebeat采集
2. ELK: Logstash采集
3. Filebeat更轻量
```

### Q2: 如何处理日志爆炸？

```
A:
1. 采样采集
2. 滚动删除
3. 冷热分离
```

## 四、自测题

1. 解释EFK架构
2. 如何配置Filebeat？
3. 如何处理日志爆炸？

---

## 参考文档

- [Filebeat](https://www.elastic.co/guide/en/beats/filebeat/current/index.html)
- [Elasticsearch](https://www.elastic.co/guide/en/elasticsearch/reference/current/index.html)
