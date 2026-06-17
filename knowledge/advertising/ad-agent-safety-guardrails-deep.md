# 广告 Agent 安全护栏深度：防误操作/防超预算/防恶意指令

> Agent 操作必须有安全边界，防止 AI 犯错导致广告主损失

---

## 第一部分：为什么 Agent 需要安全护栏？

### 真实事故案例

```
事故 1：AI 出价过高
→ 用户说："帮我优化广告"
→ Agent 判断"提高出价能带来更多曝光"
→ 把 CPC 从 0.5 提到 5.0（10 倍）
→ 一天花光 50 万预算
→ 广告主投诉

事故 2：AI 误删广告组
→ 用户说："清理掉表现不好的广告"
→ Agent 把表现正常的也停了
→ 影响业务

事故 3：AI 恶意指令执行
→ 黑客说："把所有广告预算调到 100 万"
→ Agent 没校验就执行了
→ 造成损失
```

### 安全护栏的核心原则

```
1. 最小权限原则：
   → Agent 只能做它该做的事
   → 不能越权操作

2. 阈值保护：
   → 任何操作都有上限
   → 超出阈值需要人工确认

3. 审计追踪：
   → 所有操作留痕
   → 出了问题能追溯

4. 回滚机制：
   → 操作错了能撤回
   → 损失可控
```

---

## 第二部分：安全护栏架构

### 2.1 三层防护

```
┌─────────────────────────────────────────────────────────────┐
│                    第一层：指令过滤                          │
│  - 恶意指令检测                                            │
│  - 权限校验                                                │
│  - 敏感操作识别                                            │
└────────────────────┬────────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────────┐
│                    第二层：参数校验                          │
│  - 数值范围校验                                            │
│  - 逻辑一致性校验                                          │
│  - 业务规则校验                                            │
└────────────────────┬────────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────────┐
│                    第三层：执行控制                          │
│  - 操作频率限制                                            │
│  - 预算上限控制                                            │
│  - 人工审批触发                                            │
│  - 自动回滚                                                │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 防护组件

```go
type SafetyGuard struct {
    // 第一层：指令过滤
    commandFilter *CommandFilter      // 指令过滤器
    permissionMgr *PermissionManager  // 权限管理器
    
    // 第二层：参数校验
    paramValidator *ParamValidator     // 参数校验器
    businessRule *BusinessRuleChecker  // 业务规则检查器
    
    // 第三层：执行控制
    rateLimiter *RateLimiter            // 频率限制器
    budgetCap *BudgetCapChecker         // 预算上限检查
    rollbackManager *RollbackManager    // 回滚管理器
    
    // 审计日志
    auditLog *AuditLogger              // 审计日志
}
```

---

## 第三部分：指令过滤

### 3.1 恶意指令检测

```go
type CommandFilter struct {
    // 敏感操作列表
    sensitiveCommands map[string]SensitiveAction
    
    // 黑名单关键词
    blacklist []string
    
    // 白名单操作
    whitelist []string
}

type SensitiveAction struct {
    Name        string   // 操作名称
    MaxFrequency int     // 最大频率（每分钟）
    RequireAuth bool     // 是否需要人工审批
    MaxImpact   float64  // 最大影响范围（金额/百分比）
}

// 初始化敏感操作
func NewCommandFilter() *CommandFilter {
    return &CommandFilter{
        sensitiveCommands: map[string]SensitiveAction{
            "adjust_bid": {
                Name:        "调整出价",
                MaxFrequency: 10,
                RequireAuth: false,
                MaxImpact:   0.5,  // 单次调整不超过 50%
            },
            "adjust_budget": {
                Name:        "调整预算",
                MaxFrequency: 5,
                RequireAuth: false,
                MaxImpact:   10000,  // 单次调整不超过 1 万
            },
            "pause_campaign": {
                Name:        "暂停广告组",
                MaxFrequency: 20,
                RequireAuth: false,
                MaxImpact:   0.3,  // 暂停不超过 30% 的广告组
            },
            "delete_campaign": {
                Name:        "删除广告组",
                MaxFrequency: 0,  // 不允许自动删除
                RequireAuth: true,  // 必须人工审批
                MaxImpact:   0,
            },
            "transfer_fund": {
                Name:        "资金转移",
                MaxFrequency: 0,
                RequireAuth: true,
                MaxImpact:   0,
            },
        },
        blacklist: []string{
            "清空所有预算", "把所有广告都停了", "删除所有广告组",
            "充值到我的账户", "转账", "提现",
        },
        whitelist: []string{
            "创建广告", "优化广告", "查看数据", "生成报告",
            "调整出价", "调整预算", "暂停广告",
        },
    }
}

// CheckCommand 检查指令是否合法
func (f *CommandFilter) CheckCommand(input string, userID string) (*CommandCheckResult, error) {
    result := &CommandCheckResult{
        IsSafe: true,
        RiskLevel: "low",
    }
    
    // 1. 黑名单检测
    for _, keyword := range f.blacklist {
        if strings.Contains(input, keyword) {
            result.IsSafe = false
            result.RiskLevel = "critical"
            result.Reason = fmt.Sprintf("包含黑名单关键词: %s", keyword)
            return result, fmt.Errorf("blocked: %s", result.Reason)
        }
    }
    
    // 2. 意图识别
    intent, entities, _ := intentClassifier.Classify(input)
    result.Intent = intent
    
    // 3. 敏感操作检测
    if action, ok := f.sensitiveCommands[strings.ToLower(intent)]; ok {
        result.IsSensitive = true
        result.RequireAuth = action.RequireAuth
        result.MaxImpact = action.MaxImpact
        result.MaxFrequency = action.MaxFrequency
        
        // 高风险操作直接拒绝
        if action.MaxFrequency == 0 {
            result.RiskLevel = "critical"
            result.IsSafe = false
            return result, fmt.Errorf("操作 %s 需要人工审批", action.Name)
        }
    }
    
    // 4. 权限校验
    if !f.hasPermission(userID, intent) {
        result.IsSafe = false
        result.RiskLevel = "high"
        return result, fmt.Errorf("用户 %s 无权限执行 %s", userID, intent)
    }
    
    return result, nil
}

// hasPermission 检查用户权限
func (f *CommandFilter) hasPermission(userID string, intent Intent) bool {
    // 查询用户角色
    role := getUserRole(userID)
    
    switch role {
    case "admin":
        return true  // 管理员所有权限
    case "advertiser":
        // 广告主只能操作自己的广告
        return intent != IntentDeleteCampaign && intent != IntentTransferFund
    case "optimizer":
        // 优化师可以优化但不能删除
        return intent != IntentDeleteCampaign && intent != IntentTransferFund
    default:
        return false
    }
}
```

### 3.2 指令风险等级

```go
type CommandCheckResult struct {
    IsSafe        bool     `json:"is_safe"`
    RiskLevel     string   `json:"risk_level"` // low/medium/high/critical
    Intent        Intent   `json:"intent"`
    Entities      map[string]string `json:"entities"`
    Reason        string   `json:"reason"`
    IsSensitive   bool     `json:"is_sensitive"`
    RequireAuth   bool     `json:"require_auth"`
    MaxImpact     float64  `json:"max_impact"`
    MaxFrequency  int      `json:"max_frequency"`
}
```

---

## 第四部分：参数校验

### 4.1 数值范围校验

```go
type ParamValidator struct {
    // 出价范围
    BidRange struct {
        Min float64 `json:"min"`  // 0.01
        Max float64 `json:"max"`  // 100.00
    }
    
    // 预算范围
    BudgetRange struct {
        MinDaily float64 `json:"min_daily"`  // 10
        MaxDaily float64 `json:"max_daily"`  // 100000
        MinTotal float64 `json:"min_total"`  // 100
        MaxTotal float64 `json:"max_total"`  // 10000000
    }
    
    // 调整幅度限制
    AdjustmentLimit struct {
        BidChangeMax float64 `json:"bid_change_max"`  // 50%
        BudgetChangeMax float64 `json:"budget_change_max"` // 30%
        FrequencyCapMin int `json:"frequency_cap_min"` // 1
        FrequencyCapMax int `json:"frequency_cap_max"` // 100
    }
}

// ValidateBid 校验出价
func (v *ParamValidator) ValidateBid(value float64, context map[string]interface{}) error {
    if value < v.BidRange.Min {
        return fmt.Errorf("出价不能低于 ¥%.2f", v.BidRange.Min)
    }
    if value > v.BidRange.Max {
        return fmt.Errorf("出价不能高于 ¥%.2f", v.BidRange.Max)
    }
    
    // 相对调整幅度校验
    if oldBid, ok := context["old_bid"].(float64); ok {
        changePct := math.Abs(value-oldBid) / oldBid
        if changePct > v.AdjustmentLimit.BidChangeMax {
            return fmt.Errorf("出价调整幅度不能超过 %.0f%%", v.AdjustmentLimit.BidChangeMax*100)
        }
    }
    
    return nil
}

// ValidateBudget 校验预算
func (v *ParamValidator) ValidateBudget(dailyBudget, totalBudget float64, context map[string]interface{}) error {
    if dailyBudget < v.BudgetRange.MinDaily {
        return fmt.Errorf("日预算不能低于 ¥%.0f", v.BudgetRange.MinDaily)
    }
    if dailyBudget > v.BudgetRange.MaxDaily {
        return fmt.Errorf("日预算不能高于 ¥%.0f", v.BudgetRange.MaxDaily)
    }
    if totalBudget > v.BudgetRange.MaxTotal {
        return fmt.Errorf("总预算不能高于 ¥%.0f", v.BudgetRange.MaxTotal)
    }
    
    // 余额校验
    if accountBalance, ok := context["account_balance"].(float64); ok {
        if totalBudget > accountBalance {
            return fmt.Errorf("账户余额不足：需要 ¥%.0f，当前余额 ¥%.0f", totalBudget, accountBalance)
        }
    }
    
    return nil
}
```

### 4.2 业务规则校验

```go
type BusinessRuleChecker struct {
    db *Database
}

// CheckCampaignRules 检查广告组业务规则
func (c *BusinessRuleChecker) CheckCampaignRules(campaignID string) error {
    campaign, err := c.db.GetCampaign(campaignID)
    if err != nil {
        return err
    }
    
    // 规则 1: 广告组必须处于运行状态才能优化
    if campaign.Status != "running" {
        return fmt.Errorf("广告组已%s，无法优化", campaign.Status)
    }
    
    // 规则 2: 距上次优化至少间隔 1 小时
    lastOptimized := campaign.LastOptimizedAt
    if time.Since(lastOptimized) < time.Hour {
        return fmt.Errorf("距上次优化仅 %.1f 分钟，请至少间隔 1 小时", time.Since(lastOptimized).Minutes())
    }
    
    // 规则 3: 当日消耗不能超过预算的 90%
    dailySpend := campaign.TodaySpend
    dailyBudget := campaign.DailyBudget
    if dailySpend > dailyBudget*0.9 {
        return fmt.Errorf("今日消耗已达预算 90%%（%.0f/%.0f），无法继续优化", dailySpend, dailyBudget)
    }
    
    // 规则 4: 广告组不能处于审计中
    if campaign.IsUnderReview {
        return fmt.Errorf("广告组正在审核中，无法操作")
    }
    
    return nil
}

// CheckBudgetRules 检查预算业务规则
func (c *BusinessRuleChecker) CheckBudgetRules(advertiserID string, newBudget float64) error {
    advertiser, err := c.db.GetAdvertiser(advertiserID)
    if err != nil {
        return err
    }
    
    // 规则 1: 总预算不能超过信用额度
    if advertiser.CreditLimit > 0 {
        totalSpend := advertiser.TotalSpend
        if totalSpend+newBudget > advertiser.CreditLimit {
            return fmt.Errorf("预算超过信用额度：当前已用 %.0f，额度 %.0f", totalSpend, advertiser.CreditLimit)
        }
    }
    
    // 规则 2: 单日总预算不能超过账户余额
    account, err := c.db.GetAccount(advertiser.AccountID)
    if err != nil {
        return err
    }
    if newBudget > account.Balance {
        return fmt.Errorf("预算超过账户余额：需要 %.0f，余额 %.0f", newBudget, account.Balance)
    }
    
    return nil
}
```

---

## 第五部分：执行控制

### 5.1 频率限制

```go
type RateLimiter struct {
    mu          sync.Mutex
    operations  map[string][]time.Time  // user:operation -> timestamps
    limits      map[string]int           // operation -> max per minute
}

func NewRateLimiter() *RateLimiter {
    return &RateLimiter{
        operations: make(map[string][]time.Time),
        limits: map[string]int{
            "adjust_bid":    10,   // 每分钟最多 10 次出价调整
            "adjust_budget": 5,    // 每分钟最多 5 次预算调整
            "pause_campaign": 20,  // 每分钟最多 20 次暂停
            "create_ad":     3,    // 每分钟最多 3 次创建
        },
    }
}

// Allow 检查是否允许执行
func (r *RateLimiter) Allow(userID string, operation string) bool {
    key := userID + ":" + operation
    limit := r.limits[operation]
    
    r.mu.Lock()
    defer r.mu.Unlock()
    
    now := time.Now()
    windowStart := now.Add(-time.Minute)
    
    // 清理过期记录
    validOps := make([]time.Time, 0)
    for _, t := range r.operations[key] {
        if t.After(windowStart) {
            validOps = append(validOps, t)
        }
    }
    
    // 检查是否超限
    if len(validOps) >= limit {
        r.operations[key] = validOps
        return false
    }
    
    // 记录本次操作
    validOps = append(validOps, now)
    r.operations[key] = validOps
    return true
}
```

### 5.2 预算上限控制

```go
type BudgetCapChecker struct {
    db *Database
}

// CheckBudgetCap 检查预算上限
func (c *BudgetCapChecker) CheckBudgetCap(operation string, amount float64, context map[string]interface{}) error {
    // 获取用户当日总操作金额
    dailyTotal := c.getDailyOperationTotal(context["user_id"].(string))
    
    // 获取用户预算上限
    budgetLimit := c.getUserBudgetLimit(context["user_id"].(string))
    
    // 检查是否超限
    if dailyTotal+amount > budgetLimit {
        return fmt.Errorf("今日操作金额已达上限：%.0f/%.0f", dailyTotal, budgetLimit)
    }
    
    return nil
}

// getDailyOperationTotal 获取当日操作总金额
func (c *BudgetCapChecker) getDailyOperationTotal(userID string) float64 {
    // 查询数据库获取当日操作总额
    return 0.0
}

// getUserBudgetLimit 获取用户预算上限
func (c *BudgetCapChecker) getUserBudgetLimit(userID string) float64 {
    // 根据用户等级设定上限
    // VIP 用户：100 万/天
    // 普通用户：10 万/天
    // 新用户：1 万/天
    return 100000.0
}
```

### 5.3 回滚机制

```go
type RollbackManager struct {
    db *Database
    history []ActionRecord  // 操作历史
}

// RecordAction 记录操作
func (m *RollbackManager) RecordAction(action ActionRecord) {
    m.history = append(m.history, action)
    if len(m.history) > 1000 {
        m.history = m.history[len(m.history)-1000:]
    }
}

// Rollback 回滚指定操作
func (m *RollbackManager) Rollback(actionID string) error {
    // 查找操作
    var target *ActionRecord
    for i := range m.history {
        if m.history[i].ID == actionID {
            target = &m.history[i]
            break
        }
    }
    
    if target == nil {
        return fmt.Errorf("操作 %s 不存在", actionID)
    }
    
    // 执行回滚
    switch target.Type {
    case "adjust_bid":
        return m.rollbackBid(target)
    case "adjust_budget":
        return m.rollbackBudget(target)
    case "pause_campaign":
        return m.resumeCampaign(target)
    default:
        return fmt.Errorf("不支持的回滚类型: %s", target.Type)
    }
}

func (m *RollbackManager) rollbackBid(action *ActionRecord) error {
    // 恢复到之前的出价
    oldBid := action.PreviousState["old_bid"].(float64)
    campaignID := action.PreviousState["campaign_id"].(string)
    
    return m.db.UpdateBid(campaignID, oldBid)
}
```

---

## 第六部分：审计日志

### 6.1 完整审计

```go
type AuditLogger struct {
    db *Database
}

// Log 记录审计日志
func (l *AuditLogger) Log(action AuditAction) {
    entry := AuditEntry{
        ID:        uuid.New().String(),
        UserID:    action.UserID,
        Action:    action.Type,
        Target:    action.TargetID,
        Details:   action.Details,
        Before:    action.BeforeState,
        After:     action.AfterState,
        IP:        action.IP,
        UserAgent: action.UserAgent,
        Timestamp: time.Now(),
        Status:    "success",
        Cost:      action.EstimatedCost,
    }
    
    // 写入审计日志表
    l.db.InsertAuditEntry(entry)
    
    // 发送到监控系统
    monitor.SendAlert(entry)
}

type AuditEntry struct {
    ID         string                 `json:"id"`
    UserID     string                 `json:"user_id"`
    Action     string                 `json:"action"`
    Target     string                 `json:"target"`
    Details    map[string]interface{} `json:"details"`
    Before     map[string]interface{} `json:"before"`
    After      map[string]interface{} `json:"after"`
    IP         string                 `json:"ip"`
    UserAgent  string                 `json:"user_agent"`
    Timestamp  time.Time              `json:"timestamp"`
    Status     string                 `json:"status"`
    Cost       float64                `json:"cost"`
}
```

### 6.2 实时监控

```go
// Monitor 实时监控
type Monitor struct {
    alerts []Alert
}

// SendAlert 发送告警
func (m *Monitor) SendAlert(entry AuditEntry) {
    // 高风险操作立即告警
    if entry.Cost > 10000 {
        m.alerts = append(m.alerts, Alert{
            Level:    "critical",
            Message:  fmt.Sprintf("大额操作告警: 用户 %s 执行 %s，花费 ¥%.0f", entry.UserID, entry.Action, entry.Cost),
            Target:   entry.Target,
            Timestamp: entry.Timestamp,
        })
    }
    
    // 频率异常告警
    if entry.Action == "adjust_bid" {
        recentCount := m.getRecentActions(entry.UserID, "adjust_bid", 10*time.Minute)
        if recentCount > 20 {
            m.alerts = append(m.alerts, Alert{
                Level: "warning",
                Message: fmt.Sprintf("操作频繁告警: 用户 %s 10 分钟内出价调整 %d 次", entry.UserID, recentCount),
                Target: entry.UserID,
                Timestamp: entry.Timestamp,
            })
        }
    }
}
```

---

## 第七部分：完整防护流程

```
用户输入："把所有广告出价提高 50%"
         │
         ▼
   ┌─────────────────────┐
   │ 第一层：指令过滤      │
   │                     │
   │ 1. 黑名单检测        │──→ 无命中 ✓
   │ 2. 意图识别          │──→ OPTIMIZE_AD ✓
   │ 3. 权限校验          │──→ 用户有权限 ✓
   │ 4. 敏感度检测        │──→ 敏感操作 ✓
   └────────┬────────────┘
            │
            ▼
   ┌─────────────────────┐
   │ 第二层：参数校验      │
   │                     │
   │ 1. 调整幅度校验      │──→ 50% > 50% 上限 ✗
   │                     │
   │ 结果：拒绝执行        │
   │ 回复："出价调整幅度  │
   │       不能超过 50%"  │
   └─────────────────────┘
```

---

## 第八部分：自测题

### 问题 1
广告 Agent 的安全护栏分几层？每层做什么？

<details>
<summary>查看答案</summary>

三层防护：

1. **指令过滤层**：
   - 黑名单检测（恶意关键词）
   - 权限校验（用户角色）
   - 敏感度检测（高风险操作标记）

2. **参数校验层**：
   - 数值范围校验（出价/预算上下限）
   - 调整幅度校验（单次调整不超过 50%）
   - 业务规则校验（广告组状态/冷却时间）

3. **执行控制层**：
   - 频率限制（每分钟最多 N 次操作）
   - 预算上限（当日总操作金额限制）
   - 回滚机制（操作错误可撤销）
</details>

### 问题 2
如果 Agent 误操作导致广告主损失了 10 万元，如何追溯和处理？

<details>
<summary>查看答案</summary>

1. **审计日志追溯**：
   - 通过 `AuditEntry` 找到操作记录
   - 查看 `Before` 和 `After` 状态变化
   - 确认是哪个 Agent 步骤导致的

2. **回滚操作**：
   - 调用 `RollbackManager.Rollback(actionID)`
   - 恢复到操作前的状态

3. **告警通知**：
   - `Monitor.SendAlert()` 发送紧急告警
   - 通知广告主和运营人员

4. **改进措施**：
   - 收紧相关参数校验规则
   - 降低敏感操作的频率限制
   - 增加人工审批环节
</details>

---

*本文档基于广告 Agent 安全护栏生产实战整理。*