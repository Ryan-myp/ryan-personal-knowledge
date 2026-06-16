# 广告系统诊断深度：广告投不出/用户看不到/性能劣化的根因定位

> 广告排查工具箱 + 诊断引擎 + 自动归因 + 根因分析

---

## 第一部分：为什么要做自动诊断？

### 典型问题场景

```
场景 1：广告投不出去
广告主：「我设置了投放，但 0 展示」
→ 可能的原因：
   a) 广告审核未通过
   b) 预算已耗尽
   c) 出价太低，竞价失败
   d) 定向太窄，没人匹配
   e) 广告位没有流量
   f) 账户余额不足
   g) 投放时间未到
   h) 广告组被暂停

场景 2：用户看不到广告
用户：「我打开 App 怎么没有广告？」
→ 可能的原因：
   a) 用户被频次限制（今天看了太多）
   b) 用户画像不匹配（定向条件不满足）
   c) 广告位填充率低（没有竞价的广告）
   d) 用户触发了反作弊（疑似刷量）
   e) 广告创意审核被拒
   f) 广告主暂停了投放

场景 3：eCPM 突然下降
运营：「昨天 eCPM 还是 ¥50，今天变成 ¥30 了」
→ 可能的原因：
   a) 竞争加剧（新对手进入）
   b) CTR 下降（创意疲劳）
   c) CVR 下降（落地页问题）
   d) 流量质量变化（新用户占比上升）
   e) 出价策略变更
   f) 季节性波动
```

### 诊断的价值

```
传统方式：
→ 人工逐层排查（DB → Redis → 日志 → 代码）
→ 平均耗时：30 分钟
→ 需要资深工程师

自动诊断：
→ 一键诊断，自动定位
→ 耗时：< 5 秒
→ 任何人都能用
```

---

## 第二部分：诊断引擎架构

### 2.1 整体架构

```
                    ┌─────────────────────────────────────┐
                    │         诊断请求                     │
                    │  广告主ID / 用户ID / 广告ID           │
                    └──────────────┬──────────────────────┘
                                   │
                    ┌──────────────▼──────────────────────┐
                    │       诊断引擎                       │
                    │                                      │
                    │  ┌──────────────────────────────┐   │
                    │  │ 模块 1: 账户状态检查          │   │
                    │  │ - 账户余额                    │   │
                    │  │ - 账户状态                    │   │
                    │  │ - 支付方式                    │   │
                    │  └──────────────────────────────┘   │
                    │  ┌──────────────────────────────┐   │
                    │  │ 模块 2: 广告组状态检查        │   │
                    │  │ - 广告组状态                  │   │
                    │  │ - 预算/出价                   │   │
                    │  │ - 投放时间                    │   │
                    │  └──────────────────────────────┘   │
                    │  ┌──────────────────────────────┐   │
                    │  │ 模块 3: 广告状态检查          │   │
                    │  │ - 审核状态                    │   │
                    │  │ - 创意状态                    │   │
                    │  │ - 频次限制                    │   │
                    │  └──────────────────────────────┘   │
                    │  ┌──────────────────────────────┐   │
                    │  │ 模块 4: 竞价能力检查          │   │
                    │  │ - 出价竞争力                  │   │
                    │  │ - 预估 CTR/CVR               │   │
                    │  │ - 历史 eCPM 趋势             │   │
                    │  └──────────────────────────────┘   │
                    │  ┌──────────────────────────────┐   │
                    │  │ 模块 5: 流量匹配检查          │   │
                    │  │ - 用户画像匹配                │   │
                    │  │ - 广告位匹配                  │   │
                    │  │ - 地域/时间匹配               │   │
                    │  └──────────────────────────────┘   │
                    └──────────────┬──────────────────────┘
                                   │
                    ┌──────────────▼──────────────────────┐
                    │       诊断报告                       │
                    │  - 问题根因                          │
                    │  - 影响程度                          │
                    │  - 解决建议                          │
                    │  - 相关指标趋势                      │
                    └─────────────────────────────────────┘
```

### 2.2 诊断流水线

```
诊断请求 → 并行检查 → 收集问题 → 排序严重度 → 生成报告
```

---

## 第三部分：诊断模块实现

### 3.1 诊断引擎核心

```go
package diagnosis

import (
    "context"
    "fmt"
    "time"
)

// DiagnosisEngine 诊断引擎
type DiagnosisEngine struct {
    accountChecker  *AccountChecker
    campaignChecker *CampaignChecker
    adChecker       *AdChecker
    bidChecker      *BidChecker
    trafficChecker  *TrafficChecker
    metricAnalyzer  *MetricAnalyzer
}

// DiagnosticRequest 诊断请求
type DiagnosticRequest struct {
    Type      string      `json:"type"` // ad_not_serving/user_no_ad/performance_drop
    AdvertiserID string    `json:"advertiser_id"`
    AdID       string      `json:"ad_id"`
    UserID     string      `json:"user_id"`
    SlotID     string      `json:"slot_id"`
    TimeRange  TimeRange   `json:"time_range"`
}

// TimeRange 时间范围
type TimeRange struct {
    Start time.Time `json:"start"`
    End   time.Time `json:"end"`
}

// DiagnosticResult 诊断结果
type DiagnosticResult struct {
    RequestID  string         `json:"request_id"`
    Problems   []Problem      `json:"problems"`
    RootCause  string         `json:"root_cause"`
    Severity   string         `json:"severity"` // critical/warning/info
    Suggestions []string      `json:"suggestions"`
    Metrics    MetricTrend    `json:"metrics"`
    ExecTime   time.Duration  `json:"exec_time"`
}

// Problem 问题
type Problem struct {
    Module     string        `json:"module"`     // 检查模块
    Code       string        `json:"code"`       // 问题代码
    Message    string        `json:"message"`    // 问题描述
    Severity   string        `json:"severity"`   // critical/warning/info
    Evidence   interface{}   `json:"evidence"`   // 证据数据
}
```

### 3.2 并行诊断

```go
// Diagnose 执行诊断
func (de *DiagnosisEngine) Diagnose(ctx context.Context, req *DiagnosticRequest) (*DiagnosticResult, error) {
    startTime := time.Now()
    
    // 1. 并行执行所有检查模块
    type result struct {
        problems []Problem
        err error
    }
    
    ch := make(chan result, 5)
    
    go func() {
        problems, err := de.accountChecker.Check(req)
        ch <- result{problems, err}
    }()
    
    go func() {
        problems, err := de.campaignChecker.Check(req)
        ch <- result{problems, err}
    }()
    
    go func() {
        problems, err := de.adChecker.Check(req)
        ch <- result{problems, err}
    }()
    
    go func() {
        problems, err := de.bidChecker.Check(req)
        ch <- result{problems, err}
    }()
    
    go func() {
        problems, err := de.trafficChecker.Check(req)
        ch <- result{problems, err}
    }()
    
    // 2. 收集结果
    allProblems := make([]Problem, 0)
    for i := 0; i < 5; i++ {
        r := <-ch
        if r.err != nil {
            log.Warn("diagnosis module failed: %v", r.err)
            continue
        }
        allProblems = append(allProblems, r.problems...)
    }
    
    // 3. 排序严重度
    sortProblemsBySeverity(allProblems)
    
    // 4. 分析根因
    rootCause := de.analyzeRootCause(allProblems)
    
    // 5. 生成建议
    suggestions := de.generateSuggestions(allProblems)
    
    // 6. 获取指标趋势
    metrics := de.metricAnalyzer.GetTrend(req)
    
    execTime := time.Since(startTime)
    
    return &DiagnosticResult{
        RequestID:   generateRequestID(),
        Problems:    allProblems,
        RootCause:   rootCause,
        Severity:    getOverallSeverity(allProblems),
        Suggestions: suggestions,
        Metrics:     metrics,
        ExecTime:    execTime,
    }, nil
}
```

---

## 第四部分：各诊断模块

### 4.1 账户状态检查

```go
// AccountChecker 账户状态检查器
type AccountChecker struct {
    db *Database
}

func (c *AccountChecker) Check(req *DiagnosticRequest) ([]Problem, error) {
    problems := make([]Problem, 0)
    
    // 1. 检查账户是否存在
    account, err := c.db.GetAccount(req.AdvertiserID)
    if err != nil {
        problems = append(problems, Problem{
            Module:   "account",
            Code:     "ACCOUNT_NOT_FOUND",
            Message:  fmt.Sprintf("广告主 %s 不存在", req.AdvertiserID),
            Severity: "critical",
        })
        return problems, nil
    }
    
    // 2. 检查账户状态
    if account.Status != "active" {
        problems = append(problems, Problem{
            Module:   "account",
            Code:     "ACCOUNT_INACTIVE",
            Message:  fmt.Sprintf("账户状态：%s（需要激活）", account.Status),
            Severity: "critical",
            Evidence: map[string]interface{}{
                "status":      account.Status,
                "freeze_reason": account.FreezeReason,
            },
        })
    }
    
    // 3. 检查余额
    if account.Balance <= 0 {
        problems = append(problems, Problem{
            Module:   "account",
            Code:     "INSUFFICIENT_BALANCE",
            Message:  fmt.Sprintf("账户余额不足：¥%.2f（需要充值）", account.Balance),
            Severity: "critical",
            Evidence: map[string]interface{}{
                "balance": account.Balance,
                "threshold": account.BalanceThreshold,
            },
        })
    }
    
    // 4. 检查信用额度
    if account.CreditLimit > 0 && account.TotalDebt > account.CreditLimit {
        problems = append(problems, Problem{
            Module:   "account",
            Code:     "CREDIT_EXCEEDED",
            Message:  fmt.Sprintf("信用额度超限：已用 ¥%.2f / 总额度 ¥%.2f", account.TotalDebt, account.CreditLimit),
            Severity: "critical",
        })
    }
    
    // 5. 检查支付方式
    if !account.HasValidPaymentMethod() {
        problems = append(problems, Problem{
            Module:   "account",
            Code:     "NO_VALID_PAYMENT",
            Message:  "账户没有有效的支付方式",
            Severity: "critical",
        })
    }
    
    return problems, nil
}
```

### 4.2 广告组状态检查

```go
// CampaignChecker 广告组状态检查器
type CampaignChecker struct {
    db *Database
}

func (c *CampaignChecker) Check(req *DiagnosticRequest) ([]Problem, error) {
    problems := make([]Problem, 0)
    
    // 获取广告组信息
    campaign, err := c.db.GetCampaign(req.AdID)
    if err != nil {
        return nil, err
    }
    
    // 1. 检查广告组状态
    if campaign.Status != "running" {
        problems = append(problems, Problem{
            Module:   "campaign",
            Code:     "CAMPAIGN_NOT_RUNNING",
            Message:  fmt.Sprintf("广告组状态：%s（需要设置为运行中）", campaign.Status),
            Severity: "critical",
            Evidence: map[string]interface{}{
                "status": campaign.Status,
                "paused_at": campaign.PausedAt,
            },
        })
    }
    
    // 2. 检查预算
    if campaign.DailyBudget > 0 && campaign.TodaySpend >= campaign.DailyBudget {
        problems = append(problems, Problem{
            Module:   "campaign",
            Code:     "DAILY_BUDGET_EXHAUSTED",
            Message:  fmt.Sprintf("今日预算已耗尽：已花 ¥%.2f / 预算 ¥%.2f", campaign.TodaySpend, campaign.DailyBudget),
            Severity: "critical",
            Evidence: map[string]interface{}{
                "today_spend": campaign.TodaySpend,
                "daily_budget": campaign.DailyBudget,
                "budget_remaining": campaign.DailyBudget - campaign.TodaySpend,
            },
        })
    }
    
    // 3. 检查总预算
    if campaign.LifetimeBudget > 0 && campaign.TotalSpend >= campaign.LifetimeBudget {
        problems = append(problems, Problem{
            Module:   "campaign",
            Code:     "LIFETIME_BUDGET_EXHAUSTED",
            Message:  fmt.Sprintf("总预算已耗尽：已花 ¥%.2f / 总预算 ¥%.2f", campaign.TotalSpend, campaign.LifetimeBudget),
            Severity: "critical",
        })
    }
    
    // 4. 检查出价
    if campaign.BidType == "manual" && campaign.BidPrice < 0.01 {
        problems = append(problems, Problem{
            Module:   "campaign",
            Code:     "BID_TOO_LOW",
            Message:  fmt.Sprintf("出价过低：¥%.4f（建议 ≥ ¥%.4f）", campaign.BidPrice, campaign.RecommendedBid),
            Severity: "warning",
            Evidence: map[string]interface{}{
                "current_bid":  campaign.BidPrice,
                "recommended_bid": campaign.RecommendedBid,
                "avg_ecpm":     campaign.AvgECPM,
            },
        })
    }
    
    // 5. 检查投放时间
    now := time.Now()
    if campaign.Schedule.StartTime.After(now) {
        problems = append(problems, Problem{
            Module:   "campaign",
            Code:     "SCHEDULE_NOT_STARTED",
            Message:  fmt.Sprintf("投放尚未开始：预计 %s 开始", campaign.Schedule.StartTime.Format("2006-01-02 15:04")),
            Severity: "info",
        })
    }
    if campaign.Schedule.EndTime.Before(now) {
        problems = append(problems, Problem{
            Module:   "campaign",
            Code:     "SCHEDULE_ENDED",
            Message:  fmt.Sprintf("投放已结束：已于 %s 结束", campaign.Schedule.EndTime.Format("2006-01-02 15:04")),
            Severity: "critical",
        })
    }
    
    // 6. 检查投放时段
    if !campaign.Schedule.AllowsHour(now.Hour()) {
        problems = append(problems, Problem{
            Module:   "campaign",
            Code:     "OUT_OF_SCHEDULE_HOURS",
            Message:  fmt.Sprintf("当前不在投放时段内：当前 %02d:00", now.Hour()),
            Severity: "info",
            Evidence: map[string]interface{}{
                "current_hour": now.Hour(),
                "schedule_hours": campaign.Schedule.Hours,
            },
        })
    }
    
    return problems, nil
}
```

### 4.3 广告状态检查

```go
// AdChecker 广告状态检查器
type AdChecker struct {
    db       *Database
    redis    *RedisClient
}

func (c *AdChecker) Check(req *DiagnosticRequest) ([]Problem, error) {
    problems := make([]Problem, 0)
    
    // 1. 检查审核状态
    ad, err := c.db.GetAd(req.AdID)
    if err != nil {
        return nil, err
    }
    
    if ad.AuditStatus != "approved" {
        problems = append(problems, Problem{
            Module:   "ad",
            Code:     "AD_NOT_APPROVED",
            Message:  fmt.Sprintf("广告审核状态：%s（%s）", ad.AuditStatus, ad.AuditRejectReason),
            Severity: "critical",
            Evidence: map[string]interface{}{
                "audit_status":    ad.AuditStatus,
                "reject_reason":   ad.AuditRejectReason,
                "submitted_at":    ad.AuditSubmittedAt,
            },
        })
    }
    
    // 2. 检查创意状态
    if ad.CreativeStatus != "active" {
        problems = append(problems, Problem{
            Module:   "ad",
            Code:     "CREATIVE_INACTIVE",
            Message:  fmt.Sprintf("创意状态：%s", ad.CreativeStatus),
            Severity: "warning",
        })
    }
    
    // 3. 检查频次限制（针对用户诊断）
    if req.UserID != "" {
        freq, err := c.redis.Get(fmt.Sprintf("freq:%s:%s", req.UserID, req.AdID))
        if err == nil && freq > 0 {
            maxFreq := ad.FrequencyCap
            if freq >= maxFreq {
                problems = append(problems, Problem{
                    Module:   "ad",
                    Code:     "FREQUENCY_CAP_REACHED",
                    Message:  fmt.Sprintf("用户对广告 %s 已达频次上限：今日已看 %d 次 / 上限 %d 次", req.AdID, freq, maxFreq),
                    Severity: "warning",
                    Evidence: map[string]interface{}{
                        "user_id":   req.UserID,
                        "ad_id":     req.AdID,
                        "current_freq": freq,
                        "max_freq":  maxFreq,
                    },
                })
            }
        }
    }
    
    // 4. 检查创意有效性
    if ad.Creative.ExpiredAt.Before(time.Now()) {
        problems = append(problems, Problem{
            Module:   "ad",
            Code:     "CREATIVE_EXPIRED",
            Message:  "广告创意已过期",
            Severity: "warning",
            Evidence: map[string]interface{}{
                "expired_at": ad.Creative.ExpiredAt,
            },
        })
    }
    
    return problems, nil
}
```

### 4.4 竞价能力检查

```go
// BidChecker 竞价能力检查器
type BidChecker struct {
    db      *Database
    predictor *Predictor
}

func (c *BidChecker) Check(req *DiagnosticRequest) ([]Problem, error) {
    problems := make([]Problem, 0)
    
    ad, _ := c.db.GetAd(req.AdID)
    campaign, _ := c.db.GetCampaign(req.AdID)
    
    // 1. 检查出价竞争力
    avgBid := c.db.GetAvgBidForSlot(req.SlotID, time.Now().Add(-24*time.Hour))
    if campaign.BidPrice < avgBid*0.8 {
        problems = append(problems, Problem{
            Module:   "bid",
            Code:     "BID_NOT_COMPETITIVE",
            Message:  fmt.Sprintf("出价缺乏竞争力：当前 ¥%.4f / 行业均价 ¥%.4f", campaign.BidPrice, avgBid),
            Severity: "warning",
            Evidence: map[string]interface{}{
                "current_bid":  campaign.BidPrice,
                "avg_bid":      avgBid,
                "p50_bid":      c.db.GetPBidForSlot(req.SlotID, 50),
                "p90_bid":      c.db.GetPBidForSlot(req.SlotID, 90),
            },
        })
    }
    
    // 2. 检查预估 CTR
    ctrPred, _ := c.predictor.PredictCTR(req.AdID, req.UserID)
    if ctrPred < 0.005 {
        problems = append(problems, Problem{
            Module:   "bid",
            Code:     "LOW_CTR_PREDICTION",
            Message:  fmt.Sprintf("预估 CTR 过低：%.4f（行业平均 %.4f）", ctrPred, 0.02),
            Severity: "warning",
            Evidence: map[string]interface{}{
                "predicted_ctr": ctrPred,
                "industry_avg":  0.02,
                "creative_type": ad.Creative.Type,
            },
        })
    }
    
    // 3. 检查 eCPM 趋势
    ecpmTrend := c.db.GetECPMTrend(req.AdID, 7)
    if ecpmTrend.Change7d < -0.3 {
        problems = append(problems, Problem{
            Module:   "bid",
            Code:     "ECPM_DECLINING",
            Message:  fmt.Sprintf("eCPM 持续下降：近 7 天下降 %.1f%%", ecpmTrend.Change7d*100),
            Severity: "warning",
            Evidence: map[string]interface{}{
                "ecpm_7d_ago": ecpmTrend.ECPM7DAgo,
                "ecpm_now":    ecpmTrend.ECPMNow,
                "change_pct":  ecpmTrend.Change7d,
            },
        })
    }
    
    return problems, nil
}
```

### 4.5 流量匹配检查

```go
// TrafficChecker 流量匹配检查器
type TrafficChecker struct {
    db *Database
}

func (c *TrafficChecker) Check(req *DiagnosticRequest) ([]Problem, error) {
    problems := make([]Problem, 0)
    
    ad, _ := c.db.GetAd(req.AdID)
    
    // 1. 检查用户画像匹配（针对用户诊断）
    if req.UserID != "" {
        profile, err := c.db.GetUserProfile(req.UserID)
        if err == nil {
            mismatches := c.checkProfileMatch(ad, profile)
            if len(mismatches) > 0 {
                problems = append(problems, Problem{
                    Module:   "traffic",
                    Code:     "PROFILE_MISMATCH",
                    Message:  fmt.Sprintf("用户画像不匹配：%s", strings.Join(mismatches, "、")),
                    Severity: "info",
                    Evidence: map[string]interface{}{
                        "user_id":       req.UserID,
                        "user_profile":  profile,
                        "ad_targeting":  ad.Targeting,
                        "mismatches":    mismatches,
                    },
                })
            }
        }
    }
    
    // 2. 检查广告位流量
    if req.SlotID != "" {
        slotTraffic := c.db.GetSlotTraffic(req.SlotID, time.Now().Add(-24*time.Hour))
        if slotTraffic.RequestCount == 0 {
            problems = append(problems, Problem{
                Module:   "traffic",
                Code:     "SLOT_NO_TRAFFIC",
                Message:  fmt.Sprintf("广告位 %s 过去 24 小时无请求", req.SlotID),
                Severity: "warning",
                Evidence: map[string]interface{}{
                    "slot_id":       req.SlotID,
                    "request_count": 0,
                },
            })
        } else if slotTraffic.FillRate < 0.5 {
            problems = append(problems, Problem{
                Module:   "traffic",
                Code:     "SLOT_LOW_FILL_RATE",
                Message:  fmt.Sprintf("广告位填充率低：%.1f%%", slotTraffic.FillRate*100),
                Severity: "warning",
                Evidence: map[string]interface{}{
                    "slot_id":       req.SlotID,
                    "fill_rate":     slotTraffic.FillRate,
                    "request_count": slotTraffic.RequestCount,
                    "win_count":     slotTraffic.WinCount,
                },
            })
        }
    }
    
    // 3. 检查地域匹配
    if ad.Targeting.Geography != nil && ad.Targeting.Geography.Locations != nil {
        geoMatch := c.checkGeographyMatch(ad.Targeting.Geography)
        if !geoMatch {
            problems = append(problems, Problem{
                Module:   "traffic",
                Code:     "GEOGRAPHY_RESTRICTED",
                Message:  "广告限定地域，当前流量不在投放范围内",
                Severity: "info",
                Evidence: map[string]interface{}{
                    "target_geography": ad.Targeting.Geography,
                },
            })
        }
    }
    
    return problems, nil
}
```

---

## 第五部分：根因分析

### 5.1 根因分析引擎

```go
// AnalyzeRootCause 根因分析
func (de *DiagnosisEngine) AnalyzeRootCause(problems []Problem) string {
    // 按严重度排序
    critical := filterBySeverity(problems, "critical")
    warning := filterBySeverity(problems, "warning")
    info := filterBySeverity(problems, "info")
    
    // 根因优先级：critical > warning > info
    if len(critical) > 0 {
        // 找第一个 critical 问题作为根因
        return critical[0].Message
    }
    
    if len(warning) > 0 {
        // 多个 warning，找最影响收入的
        return warning[0].Message
    }
    
    if len(info) > 0 {
        return info[0].Message
    }
    
    return "未发现问题"
}

// GenerateSuggestions 生成解决建议
func (de *DiagnosisEngine) GenerateSuggestions(problems []Problem) []string {
    suggestions := make([]string, 0)
    
    for _, p := range problems {
        switch p.Code {
        case "ACCOUNT_INACTIVE":
            suggestions = append(suggestions, "请联系客服激活账户")
        case "INSUFFICIENT_BALANCE":
            suggestions = append(suggestions, "请充值账户余额")
        case "DAILY_BUDGET_EXHAUSTED":
            suggestions = append(suggestions, "请提高日预算或等待明日重置")
        case "BID_TOO_LOW":
            suggestions = append(suggestions, "建议提高出价至 ¥0.50 以上")
        case "AD_NOT_APPROVED":
            suggestions = append(suggestions, "请修改创意内容后重新提交审核")
        case "FREQUENCY_CAP_REACHED":
            suggestions = append(suggestions, "频次限制是正常现象，可扩大定向范围")
        case "BID_NOT_COMPETITIVE":
            suggestions = append(suggestions, "建议提高出价或优化创意提升 CTR")
        case "PROFILE_MISMATCH":
            suggestions = append(suggestions, "建议放宽定向条件或更换目标人群")
        }
    }
    
    return suggestions
}
```

---

## 第六部分：诊断报告示例

### 6.1 广告投不出去的诊断报告

```json
{
    "request_id": "diag_20240101_001",
    "problems": [
        {
            "module": "account",
            "code": "INSUFFICIENT_BALANCE",
            "message": "账户余额不足：¥-50.00（需要充值）",
            "severity": "critical",
            "evidence": {
                "balance": -50.0,
                "threshold": 0
            }
        },
        {
            "module": "campaign",
            "code": "DAILY_BUDGET_EXHAUSTED",
            "message": "今日预算已耗尽：已花 ¥1000.00 / 预算 ¥1000.00",
            "severity": "critical",
            "evidence": {
                "today_spend": 1000.0,
                "daily_budget": 1000.0,
                "budget_remaining": 0
            }
        }
    ],
    "root_cause": "账户余额不足：¥-50.00（需要充值）",
    "severity": "critical",
    "suggestions": [
        "请充值账户余额",
        "请提高日预算或等待明日重置"
    ],
    "metrics": {
        "impressions_7d": [10000, 12000, 11000, 0, 0, 0, 0],
        "ecpm_7d": [45.2, 48.5, 42.1, 0, 0, 0, 0]
    },
    "exec_time": "0.023s"
}
```

### 6.2 用户看不到广告的诊断报告

```json
{
    "request_id": "diag_20240101_002",
    "problems": [
        {
            "module": "ad",
            "code": "FREQUENCY_CAP_REACHED",
            "message": "用户对广告 ad_123 已达频次上限：今日已看 5 次 / 上限 3 次",
            "severity": "warning",
            "evidence": {
                "user_id": "user_456",
                "ad_id": "ad_123",
                "current_freq": 5,
                "max_freq": 3
            }
        },
        {
            "module": "traffic",
            "code": "PROFILE_MISMATCH",
            "message": "用户画像不匹配：年龄不符",
            "severity": "info",
            "evidence": {
                "user_age": 20,
                "target_age_range": "25-35"
            }
        }
    ],
    "root_cause": "用户对广告 ad_123 已达频次上限：今日已看 5 次 / 上限 3 次",
    "severity": "warning",
    "suggestions": [
        "频次限制是正常现象，可扩大定向范围"
    ],
    "exec_time": "0.018s"
}
```

---

## 第七部分：自测题

### 问题 1
广告投不出去的可能原因有哪些？

<details>
<summary>查看答案</summary>

1. **账户问题**：余额不足/账户冻结/无支付方式
2. **广告组问题**：预算耗尽/出价过低/未开始/已结束
3. **广告问题**：审核未通过/创意过期/被暂停
4. **竞价问题**：出价缺乏竞争力/CTR 过低
5. **流量问题**：定向太窄/频次限制/广告位无流量
</details>

### 问题 2
诊断引擎的工作流程是什么？

<details>
<summary>查看答案</summary>

1. **接收请求**：广告主ID/用户ID/广告ID
2. **并行检查**：账户/广告组/广告/竞价/流量 5 个模块
3. **收集问题**：汇总所有模块发现的问题
4. **排序严重度**：critical > warning > info
5. **根因分析**：找到最关键的问题
6. **生成建议**：给出解决建议
7. **输出报告**：包含问题/根因/建议/指标趋势
</details>

---

*本文档基于广告系统诊断生产实战整理。*