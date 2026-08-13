# 告警策略设计 - 资深专家深度实现

## 一、告警分层

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    告警分层策略                                            │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   层级                |  severity   | 通知方式           | 响应时间     │
│   ────────────────────┼─────────────┼───────────────────┼─────────────│
│   P0 (致命)           | critical    | 电话+短信+群       │ < 5min      │
│   P1 (严重)           | warning     | 短信+群           │ < 15min     │
│   P2 (一般)           | info        | 群+邮件           │ < 1h        │
│   P3 (提示)           | notice      | 邮件              │ < 24h       │
│                                                                         →
└─────────────────────────────────────────────────────────────────────────┘
```

## 二、实现代码

```go
package alerting

import (
    "context"
)

// AlertRule 告警规则
type AlertRule struct {
    Name        string
    Metric      string
    Operator    string
    Threshold   float64
    Duration    time.Duration
    Severity    Severity
    Channels    []Channel
}

type Severity string

const (
    Critical Severity = "critical"
    Warning  Severity = "warning"
    Info     Severity = "info"
)

type Channel string

const (
    Phone   Channel = "phone"
    SMS     Channel = "sms"
    Group   Channel = "group"
    Email   Channel = "email"
)

// AlertManager 告警管理器
type AlertManager struct {
    rules  map[string]*AlertRule
    history map[string][]Alert
}

// Evaluate 评估告警
func (m *AlertManager) Evaluate(ctx context.Context, metric string, value float64) ([]Alert, error) {
    var alerts []Alert
    
    for _, rule := range m.rules {
        if rule.Metric != metric {
            continue
        }
        
        triggered := m.checkCondition(value, rule.Operator, rule.Threshold)
        if triggered {
            alert := Alert{
                Rule:     rule.Name,
                Metric:   metric,
                Value:    value,
                Severity: rule.Severity,
                Channels: rule.Channels,
                Time:     time.Now(),
            }
            alerts = append(alerts, alert)
            
            // 发送通知
            m.notify(ctx, alert)
        }
    }
    
    return alerts, nil
}

func (m *AlertManager) checkCondition(value float64, operator string, threshold float64) bool {
    switch operator {
    case ">":
        return value > threshold
    case "<":
        return value < threshold
    case ">=":
        return value >= threshold
    case "<=":
        return value <= threshold
    default:
        return false
    }
}
```

## 三、面试高频题

### Q1: 如何设计告警策略？

```
A:
1. 分层分级
2. 避免告警疲劳
3. 自动抑制
```

### Q2: 如何处理告警风暴？

```
A:
1. 去重聚合
2. 抑制规则
3. 静默期
```

## 四、自测题

1. 解释告警分层
2. 如何实现评估？
3. 如何抑制风暴？

---

## 参考文档

- [Alertmanager](https://prometheus.io/docs/alerting/alertmanager/)
- [PagerDuty](https://www.pagerduty.com/)
