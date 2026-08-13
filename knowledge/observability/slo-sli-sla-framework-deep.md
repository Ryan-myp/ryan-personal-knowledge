# SLO/SLI/SLA 可观测性框架深度解析

> 深入 SRE 核心实践：SLO（服务等级目标）、SLI（服务等级指标）、SLA（服务等级协议）的设计与实施。
> 适用对象：SRE 工程师、技术负责人

---

## 1. 核心概念

### 1.1 三者关系

```
┌─────────────────────────────────────────────────────────────────┐
│                     SRE 等级体系                                │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   SLA (Service Level Agreement)                                │
│   ├── 对外承诺，具有法律约束力                                  │
│   ├── 客户/业务方约定                                           │
│   └── 违约通常有赔偿条款                                        │
│                                                                 │
│       ↓ 拆解为                                                  │
│                                                                 │
│   SLO (Service Level Objective)                                │
│   ├── 内部目标，技术团队承诺                                    │
│   ├── 基于 SLI 度量                                            │
│   └── 留有 Buffer 应对意外                                     │
│                                                                 │
│       ↓ 通过                                                    │
│                                                                 │
│   SLI (Service Level Indicator)                                │
│   ├── 实际测量的技术指标                                        │
│   ├── 可量化的、实时的                                          │
│   └── 计算 SLO 达成率的依据                                     │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘

示例:
┌──────────────┬──────────────────┬──────────────────┬─────────────────┐
│    层级       │     定义          │     示例         │    责任人       │
├──────────────┼──────────────────┼──────────────────┼─────────────────┤
│ SLA          │ 对外承诺         │ 99.9% 可用性     │ 业务方/客户     │
│ SLO          │ 内部目标         │ 99.95% 可用性    │ 技术团队        │
│ SLI          │ 实际指标         │ 成功率 = 成功数  │ 监控系统        │
│              │                  │ / 总请求数       │                 │
└──────────────┴──────────────────┴──────────────────┴─────────────────┘
```

---

## 2. SLI 设计

### 2.1 四类 SLI

```go
package sli

import (
    "context"
    "time"
)

// SLI 类型定义
type SLIType int

const (
    // 用户视角 SLI
    SLI_USER_VIEW SLIType = iota
    // 基础设施视角 SLI  
    SLI_INFRA_VIEW
    // 应用视角 SLI
    SLI_APP_VIEW
    // 链路视角 SLI
    SLI_TRACE_VIEW
)

// UserVisibleLatency 用户可见延迟
type UserVisibleLatency struct {
    Service    string
    Endpoint   string
    Threshold  time.Duration // P99 阈值
}

func (u *UserVisibleLatency) Compute(ctx context.Context) float64 {
    // 从 Prometheus 获取 P99 延迟
    query := fmt.Sprintf(`
        histogram_quantile(0.99, 
            rate(http_request_duration_seconds_bucket{
                service="%s", endpoint="%s"
            }[5m])
        )
    `, u.Service, u.Endpoint)
    
    result := queryPrometheus(ctx, query)
    return result
}

func (u *UserVisibleLatency) IsSatisfied() bool {
    latency := u.Compute(context.Background())
    return latency <= float64(u.Threshold)
}

// RequestSuccessRate 请求成功率
type RequestSuccessRate struct {
    Service  string
    ErrorThresh float64 // 错误率阈值 (如 0.001 = 0.1%)
}

func (r *RequestSuccessRate) Compute(ctx context.Context) float64 {
    query := fmt.Sprintf(`
        sum(rate(http_requests_total{service="%s", status=~"2.."}[5m])) /
        sum(rate(http_requests_total{service="%s"}[5m]))
    `, r.Service, r.Service)
    
    successRate := queryPrometheus(ctx, query)
    errorRate := 1.0 - successRate
    return errorRate
}

func (r *RequestSuccessRate) IsSatisfied() bool {
    errorRate := r.Compute(context.Background())
    return errorRate <= r.ErrorThresh
}

// ResourceUtilization 资源利用率
type ResourceUtilization struct {
    Service      string
    MetricType   string // cpu/memory/network
    Threshold    float64 // 使用率阈值
}

func (r *ResourceUtilization) Compute(ctx context.Context) float64 {
    var query string
    switch r.MetricType {
    case "cpu":
        query = fmt.Sprintf(`
            sum(rate(process_cpu_seconds_total{service="%s"}[5m])) /
            count(process_cpu_seconds_total{service="%s"})
        `, r.Service, r.Service)
    case "memory":
        query = fmt.Sprintf(`
            process_resident_memory_bytes{service="%s"} /
            process_virtual_memory_bytes{service="%s"}
        `, r.Service, r.Service)
    }
    return queryPrometheus(ctx, query)
}
```

### 2.2 SLI 设计原则

```
✅ 好的 SLI 特征:
   • 用户可感知（User-perceived）
   • 可直接度量（Directly measurable）
   • 持续监控（Continuously monitored）
   • 有明确阈值（Well-defined threshold）

❌ 差的 SLI 特征:
   • 内部指标（如 CPU 使用率）
   • 难以量化（如"系统稳定性"）
   • 滞后指标（如平均响应时间）
   • 过于复杂（需要多个系统关联）
```

---

## 3. SLO 设计

### 3.1 SLO 计算方法

```go
package slo

import (
    "time"
)

// SLOBudget SLO 预算
type SLOBudget struct {
    Target       float64    // 目标值 (如 0.999)
    Period       time.Duration // 评估周期 (如 30天)
    ErrorBudget  float64    // 错误预算 = (1 - Target) × Period
}

// 计算月度错误预算
func (s *SLOBudget) MonthlyErrorBudget() float64 {
    daysInMonth := 30.0
    totalSeconds := daysInMonth * 24 * 60 * 60
    return totalSeconds * (1.0 - s.Target)
}

// 示例: 99.9% SLO 的月度预算
func ExampleSLOBudget() {
    budget := SLOBudget{
        Target: 0.999,
        Period: 30 * 24 * time.Hour,
    }
    
    monthlyBudget := budget.MonthlyErrorBudget()
    // = 30 * 24 * 3600 * 0.001
    // = 2592 秒 ≈ 43 分钟
    
    println(fmt.Sprintf("月度错误预算: %.0f 秒 (%.1f 分钟)", 
        monthlyBudget, monthlyBudget/60))
}

// SLO 达成率计算
func CalculateSLOAchievement(sliValue float64, target float64) float64 {
    // 对于正向指标（如成功率）
    if sliValue >= target {
        return 1.0
    }
    return sliValue / target
}
```

### 3.2 错误预算消耗策略

```go
package errorbudget

import (
    "context"
    "time"
)

// BudgetConsumer 预算消费策略
type BudgetConsumer int

const (
    // 保守策略：预算消耗快时冻结新功能
    CONSERVATIVE BudgetConsumer = iota
    // 均衡策略：按比例限制流量
    BALANCED
    // 激进策略：只告警不限制
    AGGRESSIVE
)

// BudgetPolicy 预算政策
type BudgetPolicy struct {
    Consumer    BudgetConsumer
    Thresholds  map[float64]Action // 消耗比例 → 行动
}

// Action 预算耗尽时的行动
type Action struct {
    Name        string
    Description string
    Critical    bool // 是否阻断发布
}

var DefaultPolicies = map[BudgetConsumer]BudgetPolicy{
    CONSERVATIVE: {
        Consumer: CONSERVATIVE,
        Thresholds: map[float64]Action{
            0.5:  {Name: "warning", Description: "预算消耗超过50%，警告"},
            0.8:  {Name: "freeze", Description: "预算消耗超过80%，冻结非关键变更"},
            1.0:  {Name: "block", Description: "预算耗尽，阻断所有发布"},
        },
    },
    BALANCED: {
        Consumer: BALANCED,
        Thresholds: map[float64]Action{
            0.5:  {Name: "warning", Description: "预算消耗超过50%，警告"},
            0.8:  {Name: "rate_limit", Description: "预算消耗超过80%，限速非核心流量"},
            1.0:  {Name: "block", Description: "预算耗尽，阻断所有发布"},
        },
    },
}

// 检查是否可发布
func (p *BudgetPolicy) CanDeploy(remainingBudget float64) (bool, Action) {
    for threshold, action := range p.Thresholds {
        if remainingBudget < threshold {
            return !action.Critical, action
        }
    }
    return true, Action{}
}
```

---

## 4. 告警规则设计

### 4.1 基于 SLO 的告警

```yaml
# Prometheus AlertManager 配置
groups:
  - name: slo_alerts
    rules:
      # SLO 即将违反告警
      - alert: SLOBurnRateHigh
        expr: |
          (
            1 - (
              sum(rate(http_requests_total{status=~"2.."}[1h]))
              /
              sum(rate(http_requests_total[1h]))
            )
          ) / (1 - 0.999) > 2
        for: 2m
        labels:
          severity: warning
          slo: "99.9%"
        annotations:
          summary: "SLO 燃烧率过高"
          description: "过去1小时错误率导致SLO剩余{{ $value }}天的预算"

      # SLO 严重违反告警
      - alert: SLOBurnRateCritical
        expr: |
          (
            1 - (
              sum(rate(http_requests_total{status=~"2.."}[6h]))
              /
              sum(rate(http_requests_total[6h]))
            )
          ) / (1 - 0.999) > 6
        for: 15m
        labels:
          severity: critical
          slo: "99.9%"
        annotations:
          summary: "SLO 严重违反风险"
          description: "按当前速率，SLO将在今天内被违反"

      # 错误预算消耗告警
      - alert: ErrorBudgetDepleted
        expr: |
          (
            1 - (
              sum(rate(http_requests_total{status=~"2.."}[28d]))
              /
              sum(rate(http_requests_total[28d]))
            )
          ) * 30 > 0.99
        labels:
          severity: critical
        annotations:
          summary: "月度错误预算已耗尽"
```

### 4.2 多级告警策略

```
┌─────────────────────────────────────────────────────────────────┐
│                      告警分级策略                               │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Level 1: 静默监控 (Silent)                                     │
│  ├── 错误预算消耗 < 50%                                        │
│  ├── 仅 Dashboard 可见                                         │
│  └── 无需人工干预                                              │
│                                                                 │
│  Level 2: 警告 (Warning)                                        │
│  ├── 错误预算消耗 50-80%                                       │
│  ├── Slack #sre-alerts 通知                                    │
│  ├── 建议关注                                                  │
│  └── 不强制响应                                                │
│                                                                 │
│  Level 3: 紧急 (Critical)                                       │
│  ├── 错误预算消耗 > 80% 或 SLO 即将违反                         │
│  ├── PagerDuty 触发                                             │
│  ├── 必须响应                                                  │
│  └── 考虑启动变更冻结                                          │
│                                                                 │
│  Level 4: 预算耗尽 (Depleted)                                   │
│  ├── 错误预算 = 0                                              │
│  ├── 自动阻断发布                                               │
│  ├── 强制 Root Cause 分析                                      │
│  └── 修复前不得发布                                            │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 5. 仪表板设计

### 5.1 Grafana 仪表板配置

```json
{
  "annotations": {
    "list": [{
      "builtIn": 1,
      "datasource": "-- Grafana --",
      "enable": true,
      "hide": true,
      "iconColor": "rgba(0, 211, 255, 1)",
      "name": "Annotations & Alerts",
      "type": "dashboard"
    }]
  },
  "editable": true,
  "gnetId": null,
  "panels": [
    {
      "title": "SLO 达成率",
      "type": "gauge",
      "targets": [{
        "expr": "sum(rate(http_requests_total{status=~\"2..\"}[5m])) / sum(rate(http_requests_total[5m]))",
        "legendFormat": "Success Rate"
      }],
      "options": {
        "min": 0.99,
        "max": 1.0,
        "thresholds": [
          {"color": "red", "value": null},
          {"color": "yellow", "value": 0.995},
          {"color": "green", "value": 0.999}
        ]
      }
    },
    {
      "title": "错误预算剩余",
      "type": "stat",
      "targets": [{
        "expr": "1 - (sum(rate(http_requests_total{status!~\"2..\"}[28d])) / sum(rate(http_requests_total[28d])))",
        "legendFormat": "Budget Remaining"
      }]
    }
  ],
  "schemaVersion": 30,
  "version": 1
}
```

---

## 6. 实践 Checklist

- [ ] 定义用户可感知的 SLI
- [ ] 设定合理的 SLO 目标（基于 SLA 留出 Buffer）
- [ ] 计算并公开错误预算
- [ ] 建立基于燃烧率的告警规则
- [ ] 创建 SLO 专用仪表板
- [ ] 制定预算耗尽时的响应流程
- [ ] 定期 Review SLO 达成情况

---

**参考**: Google SRE Workbook、Google SLO 实践指南
