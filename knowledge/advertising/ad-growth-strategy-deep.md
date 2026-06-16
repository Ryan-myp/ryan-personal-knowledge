# 广告增长策略深度：拉新/促活/留存/转化/挽回

> 增长飞轮 + 用户生命周期管理 + 策略引擎 + 实战案例

---

## 第一部分：增长策略为什么重要？

### 广告系统的增长逻辑

```
普通广告系统：
广告主投放 → 用户看到广告 → 点击 → 转化
→ 线性增长

增长策略广告系统：
广告主投放 → 用户看到广告 → 点击 → 转化 → 复购 → 推荐
→ 指数增长（增长飞轮）

核心问题：
1. 如何吸引更多广告主？（供给端增长）
2. 如何让广告主花更多钱？（ARPU 提升）
3. 如何让更多用户看到广告？（需求端增长）
4. 如何提高广告效果？（ROI 提升）
5. 如何挽回流失广告主？（留存）
```

### 增长框架：AARRR

```
Acquisition（获客）：
→ 如何让用户/广告主发现我们？
→ SEO/SEM/社交媒体/口碑推荐

Activation（激活）：
→ 如何让新用户完成首次关键行为？
→ 广告主：首次投放
→ 用户：首次点击

Retention（留存）：
→ 如何让用户/广告主持续使用？
→ 广告主：持续投放
→ 用户：持续点击

Revenue（收入）：
→ 如何最大化收入？
→ 提高 eCPM/填充率/转化率

Referral（推荐）：
→ 如何让用户/广告主推荐他人？
→ 老带新/口碑传播
```

---

## 第二部分：增长策略引擎

### 2.1 策略引擎架构

```
┌─────────────────────────────────────────────────────────────┐
│                    增长策略引擎                               │
└─────────────────────────────────────────────────────────────┘

                    ┌───────────────────────────────────────┐
                    │         策略配置中心                    │
                    │  - 拉新策略                            │
                    │  - 促活策略                            │
                    │  - 留存策略                            │
                    │  - 转化策略                            │
                    │  - 挽回策略                            │
                    └──────────────┬────────────────────────┘
                                   │
                    ┌──────────────▼────────────────────────┐
                    │       策略执行引擎                      │
                    │  - 规则引擎                             │
                    │  - 条件判断                             │
                    │  - 优先级排序                           │
                    └──────┬──────────┬──────────┬──────────┘
                           │          │          │
              ┌────────────▼──┐ ┌─────▼────┐ ┌───▼────────┐
              │  拉新策略      │ │ 促活策略  │ │ 挽回策略   │
              │  - 新人优惠    │ │ 推送通知  │ │ 流失预警   │
              │  - 邀请奖励    │ │ 活动营销  │ │ 召回广告   │
              │  - 渠道投放    │ │ 内容营销  │ │ 客服跟进   │
              └───────────────┘ └──────────┘ └────────────┘
```

### 2.2 核心数据结构

```go
package growth

import (
    "time"
)

// Strategy 增长策略
type Strategy struct {
    ID          string      `json:"id"`
    Name        string      `json:"name"`
    Type        string      `json:"type"` // acquisition/activation/retention/revenue/referral
    Target      Target      `json:"target"`
    Conditions  []Condition `json:"conditions"`
    Actions     []Action    `json:"actions"`
    Priority    int         `json:"priority"` // 优先级，数字越小优先级越高
    Budget      float64     `json:"budget"`   // 策略预算
    StartTime   time.Time   `json:"start_time"`
    EndTime     time.Time   `json:"end_time"`
    Enabled     bool        `json:"enabled"`
}

// Target 目标用户/广告主
type Target struct {
    UserSegment   string    `json:"user_segment"`   // 用户分群
    AdvertiserSeg string    `json:"advertiser_seg"` // 广告主分群
    MinSpend      float64   `json:"min_spend"`      // 最小花费
    MaxSpend      float64   `json:"max_spend"`      // 最大花费
}

// Condition 策略条件
type Condition struct {
    Field    string      `json:"field"`    // 字段名
    Operator string      `json:"operator"` // 操作符（gt/lt/eq/in）
    Value    interface{} `json:"value"`    // 值
}

// Action 策略动作
type Action struct {
    Type    string      `json:"type"`     // 动作类型（discount/push/notification）
    Params  map[string]interface{} `json:"params"` // 参数
}
```

---

## 第三部分：六大增长策略

### 3.1 拉新策略（Acquisition）

```
目标：吸引新用户/广告主入驻

策略 1：新人优惠券
→ 广告主注册后赠送 ¥500 券
→ 首次投放满 ¥1000 可用
→ 转化率提升 30%

策略 2：邀请奖励
→ 老广告主邀请新广告主
→ 双方各得 ¥200 券
→ 裂变增长

策略 3：渠道投放
→ 搜索引擎投放（百度/Google）
→ 社交媒体投放（微信/微博）
→ 行业展会投放
```

```go
// NewUserDiscountStrategy 新人优惠策略
type NewUserDiscountStrategy struct {
    db       *Database
    couponGen *CouponGenerator
}

func (s *NewUserDiscountStrategy) Execute(advertiserID string) error {
    // 1. 检查是否是新用户
    isNewUser, _ := s.db.IsNewAdvertiser(advertiserID)
    if !isNewUser {
        return nil
    }
    
    // 2. 发放优惠券
    coupon, err := s.couponGen.Generate(advertiserID, 500.0, "new_user")
    if err != nil {
        return err
    }
    
    // 3. 发送通知
    s.notify(advertiserID, "您获得了 ¥500 新人优惠券！")
    
    return nil
}
```

### 3.2 激活策略（Activation）

```
目标：让用户/广告主完成首次关键行为

策略 1：新手引导
→ 广告主首次登录，引导创建第一个广告
→ 步骤：创建广告系列 → 创建广告组 → 创建创意 → 投放

策略 2：首投激励
→ 首次投放满 ¥100，返现 ¥20
→ 降低首次投放门槛

策略 3：效果保障
→ 首次投放保证最低 CTR
→ 达不到退款
```

### 3.3 留存策略（Retention）

```
目标：让用户/广告主持续使用

策略 1：效果报告
→ 每周发送投放效果报告
→ CTR/CVR/eCPM 趋势
→ 优化建议

策略 2：忠诚度计划
→ 月度消耗 ≥ ¥10,000：VIP 客服
→ 月度消耗 ≥ ¥50,000：专属优化师
→ 月度消耗 ≥ ¥100,000：定制策略

策略 3：功能更新通知
→ 新功能上线第一时间通知
→ 邀请参与内测
```

### 3.4 收入策略（Revenue）

```
目标：最大化收入

策略 1：动态定价
→ 高流量时段提高底价
→ 低流量时段降低底价
→ 最大化 eCPM

策略 2：套餐销售
→ 包月套餐：¥10,000/月，享受 9 折
→ 包季套餐：¥25,000/季，享受 8 折
→ 锁定长期预算

策略 3：交叉销售
→ 购买搜索广告的用户，推荐信息流广告
→ 购买 Banner 广告的用户，推荐开屏广告
```

### 3.5 推荐策略（Referral）

```
目标：让用户/广告主推荐他人

策略 1：老带新
→ 老广告主邀请新广告主入驻
→ 双方各得 ¥200 券
→ 被邀请人首投满 ¥500，邀请人再得 ¥100

策略 2：案例分享
→ 优秀广告主案例包装
→ 在平台上展示
→ 吸引同类广告主

策略 3：行业报告
→ 发布行业投放报告
→ 树立专业形象
→ 吸引广告主关注
```

### 3.6 挽回策略（Win-back）

```
目标：挽回流失用户/广告主

策略 1：流失预警
→ 连续 7 天无投放 → 预警
→ 连续 14 天无投放 → 联系
→ 连续 30 天无投放 → 召回

策略 2：召回优惠
→ 流失广告主回归，赠送 ¥1000 券
→ 限时 7 天有效

策略 3：效果诊断
→ 分析流失原因
→ 提供优化建议
→ 重新投放
```

```go
// WinbackStrategy 挽回策略
type WinbackStrategy struct {
    db       *Database
    notifier *Notifier
}

func (s *WinbackStrategy) Execute(advertiserID string) error {
    // 1. 检查是否流失
    daysInactive, _ := s.db.GetDaysInactive(advertiserID)
    if daysInactive < 7 {
        return nil // 还未流失
    }
    
    // 2. 根据流失天数执行不同策略
    if daysInactive >= 30 {
        // 严重流失：发送召回优惠
        s.sendWinbackCoupon(advertiserID, 1000.0)
        s.notifier.SendSMS(advertiserID, "您有一张 ¥1000 召回优惠券待领取！")
    } else if daysInactive >= 14 {
        // 轻度流失：发送效果报告
        s.sendPerformanceReport(advertiserID)
    } else {
        // 预警：发送优化建议
        s.sendOptimizationTips(advertiserID)
    }
    
    return nil
}
```

---

## 第四部分：策略执行引擎

### 4.1 规则引擎

```go
// RuleEngine 规则引擎
type RuleEngine struct {
    strategies []*Strategy
}

// Execute 执行策略
func (re *RuleEngine) Execute(entityType string, entityID string) {
    // 1. 获取实体信息
    entity := re.getEntity(entityType, entityID)
    
    // 2. 按优先级排序策略
    sort.Slice(re.strategies, func(i, j int) bool {
        return re.strategies[i].Priority < re.strategies[j].Priority
    })
    
    // 3. 执行匹配的策略
    for _, strategy := range re.strategies {
        if re.matches(strategy.Conditions, entity) {
            re.executeAction(strategy.Actions, entity)
        }
    }
}

// matches 检查条件是否匹配
func (re *RuleEngine) matches(conditions []Condition, entity Entity) bool {
    for _, cond := range conditions {
        value := re.getFieldValue(entity, cond.Field)
        if !re.compare(value, cond.Operator, cond.Value) {
            return false
        }
    }
    return true
}

// compare 比较值
func (re *RuleEngine) compare(a interface{}, operator string, b interface{}) bool {
    switch operator {
    case "gt":
        return a.(float64) > b.(float64)
    case "lt":
        return a.(float64) < b.(float64)
    case "eq":
        return a == b
    case "in":
        for _, v := range b.([]interface{}) {
            if a == v {
                return true
            }
        }
        return false
    }
    return false
}
```

### 4.2 策略监控

```go
// StrategyMonitor 策略监控
type StrategyMonitor struct {
    db *Database
}

// Monitor 监控策略效果
func (m *StrategyMonitor) Monitor(strategyID string) (*StrategyReport, error) {
    // 1. 获取策略执行数据
    executions := m.db.GetStrategyExecutions(strategyID)
    
    // 2. 计算指标
    report := &StrategyReport{
        TotalExecutions: len(executions),
        SuccessRate:     m.calculateSuccessRate(executions),
        Cost:            m.calculateCost(executions),
        ROI:             m.calculateROI(executions),
    }
    
    return report, nil
}
```

---

## 第五部分：实战案例

### 5.1 案例 1：广告主拉新

```
背景：
→ 平台广告主数量停滞
→ 需要拉新

策略：
1. 新人 ¥500 优惠券
2. 老带新双方各得 ¥200
3. 首投满 ¥1000 返现 ¥200

结果：
→ 月新增广告主从 1000 提升到 3000
→ 转化率提升 50%
→ ROI 3:1
```

### 5.2 案例 2：广告主挽回

```
背景：
→ 月流失广告主 500 个
→ 收入下降

策略：
1. 流失 7 天：发送优化建议
2. 流失 14 天：发送效果报告
3. 流失 30 天：发送 ¥1000 召回券

结果：
→ 挽回率从 10% 提升到 35%
→ 月收入恢复
```

---

## 第六部分：自测题

### 问题 1
增长策略的 AARRR 模型是什么？

<details>
<summary>查看答案</summary>

1. **Acquisition**：获客
2. **Activation**：激活
3. **Retention**：留存
4. **Revenue**：收入
5. **Referral**：推荐
</details>

### 问题 2
流失预警的策略是什么？

<details>
<summary>查看答案</summary>

1. **7 天**：发送优化建议
2. **14 天**：发送效果报告
3. **30 天**：发送召回优惠券
4. **目标**：挽回率 > 30%
5. **监控**：策略效果持续优化
</details>

---

*本文档基于广告增长策略生产实战整理。*