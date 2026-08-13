# 技术领导力 - 资深专家深度实现

## 一、领导力模型

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    技术领导力模型                                          │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   Level 1: 个人贡献 (Individual Contributor)                              │
│   ├── 技术深度: 成为领域专家                                             │
│   ├── 代码质量: 编写高质量代码                                           │
│   └── 问题解决: 独立解决复杂问题                                         │
│                                                                         →
│   Level 2: 团队影响 (Team Impact)                                          │
│   ├── 代码审查: 提升团队代码质量                                         │
│   ├── 技术分享: 传播知识                                                 │
│   └── 指导新人: 帮助团队成员成长                                         │
│                                                                         →
│   Level 3: 技术管理 (Tech Leadership)                                      │
│   ├── 架构决策: 技术选型和架构设计                                       │
│   ├── 团队建设: 招聘和培养人才                                           │
│   └── 跨团队协作: 推动跨团队项目                                         │
│                                                                         →
│   Level 4: 战略影响 (Strategic Impact)                                     │
│   ├── 技术战略: 制定长期技术规划                                         │
│   ├── 商业洞察: 理解业务需求                                             │
│   └── 行业影响: 开源贡献、技术演讲                                       │
│                                                                         →
└─────────────────────────────────────────────────────────────────────────┘
```

## 二、团队管理

```go
package leadership

// TeamLeader 技术负责人
type TeamLeader struct {
    team       []Engineer
    goals      []Goal
    feedbacks  []Feedback
}

// 设定目标
func (l *TeamLeader) SetGoals(goals []Goal) {
    l.goals = goals
    // 确保目标符合SMART原则
    for _, g := range goals {
        if !g.IsSMART() {
            log.Warn("Goal is not SMART", g)
        }
    }
}

// 提供反馈
func (l *TeamLeader) ProvideFeedback(member Engineer, feedback Feedback) {
    l.feedbacks = append(l.feedbacks, feedback)
    // 反馈应该是具体、可操作、及时的
    member.ReceiveFeedback(feedback)
}

// 招聘
func (l *TeamLeader) Hire(candidate Candidate) bool {
    // 技能匹配
    skillMatch := l.assessSkills(candidate)
    // 文化匹配
    cultureFit := l.assessCultureFit(candidate)
    // 决策
    return skillMatch && cultureFit
}

// 评估技能
func (l *TeamLeader) assessSkills(c Candidate) bool {
    // 评估技术深度和广度
    return c.Level >= l.requiredLevel
}
```

## 三、面试高频题

### Q1: 如何管理技术团队？

```
A:
1. 设定清晰目标
2. 建立信任文化
3. 持续反馈改进
```

### Q2: 如何培养技术人才？

```
A:
1. 提供挑战性任务
2. 定期技术分享
3. 一对一辅导
```

## 四、自测题

1. 解释领导力模型
2. 如何管理团队？
3. 如何培养人才？

---

## 参考文档

- [Tech Leadership](https://www.leadership-skills.com/)
- [Engineering Management](https://engmanagement.dev/)
