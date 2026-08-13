# 事后复盘模板 - 资深专家深度实现

## 一、复盘框架

```
┌─────────────────────────────────────────────────────────────────────────┐
│                   事后复盘 (Postmortem) 框架                               │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   阶段                | 活动                                    │
│   ────────────────────┼──────────────────────────────────────────────│
│   1. 信息收集         | 时间线还原、影响范围、根因分析            │
│   2. 根因分析         | 5 Whys、鱼骨图、故障树                    │
│   3. 改进措施         | 短期止血、长期预防                        │
│   4. 跟踪执行         | 任务分配、进度跟踪、效果验证              │
│                                                                         →
└─────────────────────────────────────────────────────────────────────────┘
```

## 二、复盘模板实现

```go
package postmortem

import (
    "context"
)

// Postmortem 事后复盘
type Postmortem struct {
    IncidentID    string
    Title         string
    Timeline      []TimelineEntry
    RootCause     string
    Impact        ImpactAssessment
    Actions       []ActionItem
    LessonsLearned []string
}

type TimelineEntry struct {
    Time    time.Time
    Event   string
    Source  string
}

type ImpactAssessment struct {
    Duration      time.Duration
    AffectedUsers int
    RevenueLoss   float64
    SLAViolation  bool
}

type ActionItem struct {
    ID          string
    Description string
    Owner       string
    Priority    string
    DueDate     time.Time
    Status      string
}

// CreatePostmortem 创建复盘报告
func (p *Postmortem) Create(ctx context.Context, incident *Incident) error {
    // 收集时间线
    timeline := p.collectTimeline(ctx, incident)
    
    // 分析根因
    rootCause := p.analyzeRootCause(timeline)
    
    // 评估影响
    impact := p.assessImpact(incident)
    
    // 制定改进措施
    actions := p.createActions(rootCause)
    
    p.IncidentID = incident.ID
    p.Timeline = timeline
    p.RootCause = rootCause
    p.Impact = impact
    p.Actions = actions
    
    return nil
}

// conductBlamelessReview 进行无责复盘
func (p *Postmortem) conductBlamelessReview(ctx context.Context) []string {
    questions := []string{
        "系统哪里失败了?",
        "我们如何检测到的?",
        "响应是否及时?",
        "根因是什么?",
        "如何防止再次发生?",
    }
    
    var lessons []string
    for _, q := range questions {
        answer := askTeam(ctx, q)
        lessons = append(lessons, answer)
    }
    
    return lessons
}
```

## 三、面试高频题

### Q1: 如何进行无责复盘？

```
A:
1. 关注系统而非个人
2. 寻找系统性原因
3. 制定改进措施
```

### Q2: 如何确保改进落地？

```
A:
1. 明确责任人
2. 设定 deadline
3. 跟踪验收
```

## 四、自测题

1. 解释复盘框架
2. 如何进行分析？
3. 如何确保改进？

---

## 参考文档

- [Google SRE Postmortem](https://sre.google/workbook/incident-postmortem/)
- [ blameless Postmortems](https://landing.gitlab.com/handbook/engineering/sre/blameless-postmortem/)
