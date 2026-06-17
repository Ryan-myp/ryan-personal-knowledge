package main

import (
	"fmt"
	"math"
	"strings"
	"sync"
	"time"
)

// ============================================================
// 广告 Agent 安全护栏 - 完整可运行实现
// ============================================================

// ---- 数据模型 ----

type AuditEntry struct {
	ID        string                 `json:"id"`
	UserID    string                 `json:"user_id"`
	Action    string                 `json:"action"`
	Target    string                 `json:"target"`
	Details   map[string]interface{} `json:"details"`
	Before    map[string]interface{} `json:"before"`
	After     map[string]interface{} `json:"after"`
	Timestamp time.Time              `json:"timestamp"`
	Status    string                 `json:"status"`
	Cost      float64                `json:"cost"`
}

type Alert struct {
	Level     string    `json:"level"`
	Message   string    `json:"message"`
	Target    string    `json:"target"`
	Timestamp time.Time `json:"timestamp"`
}

type CommandCheckResult struct {
	IsSafe       bool     `json:"is_safe"`
	RiskLevel    string   `json:"risk_level"`
	Intent       string   `json:"intent"`
	Reason       string   `json:"reason"`
	RequireAuth  bool     `json:"require_auth"`
	IsSensitive  bool     `json:"is_sensitive"`
	MaxImpact    float64  `json:"max_impact"`
}

type ActionRecord struct {
	ID           string                 `json:"id"`
	Type         string                 `json:"type"`
	UserID       string                 `json:"user_id"`
	CampaignID   string                 `json:"campaign_id"`
	OldBid       float64                `json:"old_bid"`
	NewBid       float64                `json:"new_bid"`
	OldBudget    float64                `json:"old_budget"`
	NewBudget    float64                `json:"new_budget"`
	Status       string                 `json:"status"`
	Timestamp    time.Time              `json:"timestamp"`
	PreviousState map[string]interface{} `json:"previous_state"`
}

// ---- 第一层：指令过滤 ----

type CommandFilter struct {
	sensitiveCommands map[string]SensitiveAction
	blacklist         []string
}

type SensitiveAction struct {
	Name         string
	MaxFrequency int
	RequireAuth  bool
	MaxImpact    float64
}

func NewCommandFilter() *CommandFilter {
	return &CommandFilter{
		sensitiveCommands: map[string]SensitiveAction{
			"adjust_bid": {
				Name:         "调整出价",
				MaxFrequency: 10,
				RequireAuth:  false,
				MaxImpact:    0.5,
			},
			"adjust_budget": {
				Name:         "调整预算",
				MaxFrequency: 5,
				RequireAuth:  false,
				MaxImpact:    10000,
			},
			"pause_campaign": {
				Name:         "暂停广告组",
				MaxFrequency: 20,
				RequireAuth:  false,
				MaxImpact:    0.3,
			},
			"delete_campaign": {
				Name:         "删除广告组",
				MaxFrequency: 0,
				RequireAuth:  true,
				MaxImpact:    0,
			},
		},
		blacklist: []string{
			"清空所有预算", "把所有广告都停了", "删除所有广告组",
			"充值到我的账户", "转账", "提现",
		},
	}
}

func (f *CommandFilter) CheckCommand(input string, userID string) (*CommandCheckResult, error) {
	result := &CommandCheckResult{IsSafe: true, RiskLevel: "low"}

	// 黑名单检测
	for _, keyword := range f.blacklist {
		if strings.Contains(input, keyword) {
			result.IsSafe = false
			result.RiskLevel = "critical"
			result.Reason = fmt.Sprintf("包含黑名单关键词: %s", keyword)
			return result, fmt.Errorf("blocked: %s", result.Reason)
		}
	}

	// 意图识别（简化）
	intent := f.identifyIntent(input)
	result.Intent = intent

	// 敏感度检测
	if action, ok := f.sensitiveCommands[strings.ToLower(intent)]; ok {
		result.IsSensitive = true
		result.RequireAuth = action.RequireAuth
		result.MaxImpact = action.MaxImpact

		if action.MaxFrequency == 0 {
			result.RiskLevel = "critical"
			result.IsSafe = false
			return result, fmt.Errorf("操作 %s 需要人工审批", action.Name)
		}
	}

	return result, nil
}

func (f *CommandFilter) identifyIntent(input string) string {
	if strings.Contains(input, "出价") || strings.Contains(input, "调价") {
		return "adjust_bid"
	}
	if strings.Contains(input, "预算") || strings.Contains(input, "花费") {
		return "adjust_budget"
	}
	if strings.Contains(input, "暂停") || strings.Contains(input, "停") {
		return "pause_campaign"
	}
	if strings.Contains(input, "创建") || strings.Contains(input, "新建") {
		return "create_ad"
	}
	return "unknown"
}

// ---- 第二层：参数校验 ----

type ParamValidator struct {
	BidRange struct {
		Min float64
		Max float64
	}
	BudgetRange struct {
		MinDaily float64
		MaxDaily float64
	}
	AdjustmentLimit struct {
		BidChangeMax    float64
		BudgetChangeMax float64
	}
}

func NewParamValidator() *ParamValidator {
	return &ParamValidator{
		BidRange: struct{ Min, Max float64 }{0.01, 100.00},
		BudgetRange: struct{ MinDaily, MaxDaily float64 }{10, 100000},
		AdjustmentLimit: struct {
			BidChangeMax    float64
			BudgetChangeMax float64
		}{0.5, 0.3},
	}
}

func (v *ParamValidator) ValidateBid(value float64, oldBid float64) error {
	if value < v.BidRange.Min {
		return fmt.Errorf("出价不能低于 ¥%.2f", v.BidRange.Min)
	}
	if value > v.BidRange.Max {
		return fmt.Errorf("出价不能高于 ¥%.2f", v.BidRange.Max)
	}
	if oldBid > 0 {
		changePct := math.Abs(value-oldBid) / oldBid
		if changePct > v.AdjustmentLimit.BidChangeMax {
			return fmt.Errorf("出价调整幅度不能超过 %.0f%%", v.AdjustmentLimit.BidChangeMax*100)
		}
	}
	return nil
}

func (v *ParamValidator) ValidateBudgetChange(newBudget, oldBudget float64) error {
	if newBudget < v.BudgetRange.MinDaily {
		return fmt.Errorf("日预算不能低于 ¥%.0f", v.BudgetRange.MinDaily)
	}
	if newBudget > v.BudgetRange.MaxDaily {
		return fmt.Errorf("日预算不能高于 ¥%.0f", v.BudgetRange.MaxDaily)
	}
	if oldBudget > 0 {
		changePct := math.Abs(newBudget-oldBudget) / oldBudget
		if changePct > v.AdjustmentLimit.BudgetChangeMax {
			return fmt.Errorf("预算调整幅度不能超过 %.0f%%", v.AdjustmentLimit.BudgetChangeMax*100)
		}
	}
	return nil
}

// ---- 第三层：执行控制 ----

type RateLimiter struct {
	mu       sync.Mutex
	operations map[string][]time.Time
	limits   map[string]int
}

func NewRateLimiter() *RateLimiter {
	return &RateLimiter{
		operations: make(map[string][]time.Time),
		limits: map[string]int{
			"adjust_bid":     10,
			"adjust_budget":  5,
			"pause_campaign": 20,
		},
	}
}

func (r *RateLimiter) Allow(userID string, operation string) bool {
	key := userID + ":" + operation
	limit := r.limits[operation]

	r.mu.Lock()
	defer r.mu.Unlock()

	now := time.Now()
	windowStart := now.Add(-time.Minute)

	validOps := make([]time.Time, 0)
	for _, t := range r.operations[key] {
		if t.After(windowStart) {
			validOps = append(validOps, t)
		}
	}

	if len(validOps) >= limit {
		r.operations[key] = validOps
		return false
	}

	validOps = append(validOps, now)
	r.operations[key] = validOps
	return true
}

// ---- 审计日志 ----

type AuditLogger struct {
	mu      sync.Mutex
	entries []AuditEntry
	alerts  []Alert
}

func (l *AuditLogger) Log(action AuditEntry) {
	l.mu.Lock()
	defer l.mu.Unlock()

	l.entries = append(l.entries, action)

	// 高风险操作告警
	if action.Cost > 10000 {
		l.alerts = append(l.alerts, Alert{
			Level: "critical", Message: fmt.Sprintf("大额操作: %s 执行 %s，花费 ¥%.0f", action.UserID, action.Action, action.Cost),
			Target: action.Target, Timestamp: action.Timestamp,
		})
	}
}

func (l *AuditLogger) GetEntries() []AuditEntry {
	l.mu.Lock()
	defer l.mu.Unlock()
	result := make([]AuditEntry, len(l.entries))
	copy(result, l.entries)
	return result
}

func (l *AuditLogger) GetAlerts() []Alert {
	l.mu.Lock()
	defer l.mu.Unlock()
	result := make([]Alert, len(l.alerts))
	copy(result, l.alerts)
	return result
}

// ---- 回滚管理器 ----

type RollbackManager struct {
	history []ActionRecord
}

func (m *RollbackManager) Record(action ActionRecord) {
	m.history = append(m.history, action)
	if len(m.history) > 1000 {
		m.history = m.history[len(m.history)-1000:]
	}
}

func (m *RollbackManager) Rollback(actionID string) (float64, error) {
	for i := range m.history {
		if m.history[i].ID == actionID {
			oldBid := m.history[i].OldBid
			m.history[i].Status = "rolled_back"
			return oldBid, nil
		}
	}
	return 0, fmt.Errorf("操作 %s 不存在", actionID)
}

// ---- 安全护栏引擎 ----

type SafetyGuard struct {
	filter        *CommandFilter
	validator     *ParamValidator
	rateLimiter   *RateLimiter
	auditLogger   *AuditLogger
	rollbackMgr   *RollbackManager
}

func NewSafetyGuard() *SafetyGuard {
	return &SafetyGuard{
		filter:      NewCommandFilter(),
		validator:   NewParamValidator(),
		rateLimiter: NewRateLimiter(),
		auditLogger: &AuditLogger{},
		rollbackMgr: &RollbackManager{},
	}
}

// CheckAndExecute 安全检查并执行
func (sg *SafetyGuard) CheckAndExecute(userID string, operation string, params map[string]interface{}) (*ExecutionResult, error) {
	result := &ExecutionResult{
		UserID:    userID,
		Operation: operation,
		Timestamp: time.Now(),
	}

	// 第一层：指令过滤
	checkResult, err := sg.filter.CheckCommand(fmt.Sprintf("%v", params), userID)
	if err != nil {
		result.Success = false
		result.Error = err.Error()
		result.RiskLevel = checkResult.RiskLevel
		return result, err
	}
	result.RiskLevel = checkResult.RiskLevel

	// 第二层：参数校验
	if operation == "adjust_bid" {
		newBid, _ := params["new_bid"].(float64)
		oldBid, _ := params["old_bid"].(float64)
		if err := sg.validator.ValidateBid(newBid, oldBid); err != nil {
			result.Success = false
			result.Error = err.Error()
			return result, err
		}
	}
	if operation == "adjust_budget" {
		newBudget, _ := params["new_budget"].(float64)
		oldBudget, _ := params["old_budget"].(float64)
		if err := sg.validator.ValidateBudgetChange(newBudget, oldBudget); err != nil {
			result.Success = false
			result.Error = err.Error()
			return result, err
		}
	}

	// 第三层：频率限制
	if !sg.rateLimiter.Allow(userID, operation) {
		result.Success = false
		result.Error = fmt.Sprintf("操作频率超限: 每分钟最多 %d 次", sg.rateLimiter.limits[operation])
		return result, fmt.Errorf("rate limited")
	}

	// 执行操作（模拟）
	result.Success = true
	result.Message = fmt.Sprintf("操作 %s 执行成功", operation)

	// 记录审计日志
	sg.auditLogger.Log(AuditEntry{
		ID:        fmt.Sprintf("audit_%d", time.Now().UnixNano()),
		UserID:    userID,
		Action:    operation,
		Target:    params["campaign_id"].(string),
		Details:   params,
		Timestamp: time.Now(),
		Status:    "success",
		Cost:      0,
	})

	return result, nil
}

type ExecutionResult struct {
	Success   bool    `json:"success"`
	Error     string  `json:"error,omitempty"`
	Message   string  `json:"message"`
	RiskLevel string  `json:"risk_level"`
	UserID    string  `json:"user_id"`
	Operation string  `json:"operation"`
	Timestamp time.Time `json:"timestamp"`
}

// ============================================================
// Demo
// ============================================================

func main() {
	sg := NewSafetyGuard()
	userID := "user_001"

	fmt.Println("╔══════════════════════════════════════════════════════════╗")
	fmt.Println("║         🛡️  广告 Agent 安全护栏演示                       ║")
	fmt.Println("╚══════════════════════════════════════════════════════════╝")

	// 测试 1: 合法操作
	fmt.Println("\n── 测试 1: 正常调价 ──")
	result, _ := sg.CheckAndExecute(userID, "adjust_bid", map[string]interface{}{
		"campaign_id": "camp_001",
		"old_bid":     0.50,
		"new_bid":     0.55,
	})
	fmt.Printf("  结果: %v | 风险: %s\n", result.Success, result.RiskLevel)
	if result.Error != "" {
		fmt.Printf("  错误: %s\n", result.Error)
	}

	// 测试 2: 调整幅度过大
	fmt.Println("\n── 测试 2: 调整幅度过大 (100%) ──")
	result, err := sg.CheckAndExecute(userID, "adjust_bid", map[string]interface{}{
		"campaign_id": "camp_001",
		"old_bid":     0.50,
		"new_bid":     1.00,
	})
	fmt.Printf("  结果: %v | 风险: %s\n", result.Success, result.RiskLevel)
	if err != nil {
		fmt.Printf("  拦截: %s\n", err.Error())
	}

	// 测试 3: 黑名单操作
	fmt.Println("\n── 测试 3: 黑名单操作 ──")
	result, err = sg.CheckAndExecute(userID, "adjust_budget", map[string]interface{}{
		"campaign_id": "camp_001",
		"new_budget":  1000000,
	})
	fmt.Printf("  结果: %v | 风险: %s\n", result.Success, result.RiskLevel)
	if err != nil {
		fmt.Printf("  拦截: %s\n", err.Error())
	}

	// 测试 4: 频率限制
	fmt.Println("\n── 测试 4: 频率限制 ──")
	for i := 0; i < 12; i++ {
		r, _ := sg.CheckAndExecute(userID, "adjust_bid", map[string]interface{}{
			"campaign_id": "camp_001",
			"old_bid":     0.50,
			"new_bid":     0.51,
		})
		if !r.Success {
			fmt.Printf("  第 %d 次: 被拦截 - %s\n", i+1, r.Error)
			break
		}
		if i == 11 {
			fmt.Printf("  第 %d 次: 成功\n", i+1)
		}
	}

	// 显示审计日志
	fmt.Println("\n── 审计日志 ──")
	entries := sg.auditLogger.GetEntries()
	for _, e := range entries {
		fmt.Printf("  [%s] %s: %s -> %s\n", e.Timestamp.Format("15:04:05"), e.UserID, e.Action, e.Target)
	}

	// 显示告警
	fmt.Println("\n── 告警 ──")
	alerts := sg.auditLogger.GetAlerts()
	if len(alerts) == 0 {
		fmt.Println("  无告警")
	}
	for _, a := range alerts {
		fmt.Printf("  [%s] %s: %s\n", a.Level, a.Target, a.Message)
	}
}
