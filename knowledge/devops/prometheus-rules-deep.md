# Prometheus 规则设计 - 资深专家深度实现

## 一、规则类型

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    Prometheus 规则类型                                     │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   规则类型          | 用途                   | 示例                       │
│   ──────────────────┼───────────────────────┼───────────────────────────│
│   AlertRule         | 告警规则               | 当CPU>80%持续5分钟           │
│   RecordingRule     | 预计算规则             | 每秒请求率                   │
│   GroupRule         | 规则组                 | 按业务分组                   │
│                                                                         →
└─────────────────────────────────────────────────────────────────────────┘
```

## 二、规则配置

```yaml
groups:
  - name: infrastructure
    rules:
      # 告警规则
      - alert: HighCPUUsage
        expr: 100 - (avg by(instance) (rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100) > 80
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "高CPU使用率"
          description: "{{ $labels.instance }} CPU使用率超过80%"
      
      # 记录规则
      - record: job:http_requests_total:rate5m
        expr: rate(http_requests_total[5m])
        
  - name: application
    rules:
      - alert: HighErrorRate
        expr: rate(http_requests_total{status=~"5.."}[5m]) / rate(http_requests_total[5m]) > 0.05
        for: 10m
        labels:
          severity: critical
```

## 三、面试高频题

### Q1: 如何设计告警规则？

```
A:
1. 关键指标选择
2. 阈值设置
3. 避免告警风暴
```

### Q2: RecordingRule有什么用？

```
A:
1. 预计算常用查询
2. 减少实时计算压力
3. 提升查询性能
```

## 四、自测题

1. 解释三种规则类型
2. 如何设计告警规则？
3. 如何避免告警风暴？

---

## 参考文档

- [Prometheus Rules](https://prometheus.io/docs/prometheus/latest/configuration/recording_rules/)
- [Alertmanager](https://prometheus.io/docs/alerting/latest/configuration/)
