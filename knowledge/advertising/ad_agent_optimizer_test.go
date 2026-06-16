package agent

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"os"
	"strings"
	"sync"
	"testing"
	"time"
)

// ============================================================
// 广告 Agent 优化器 - 完整可运行实现
// ============================================================

// ---- 数据模型 ----

// Campaign 广告组
type Campaign struct {
	ID             string    `json:"id"`
	Name           string    `json:"name"`
	Status         string    `json:"status"` // running/paused/completed
	BidType        string    `json:"bid_type"` // manual/auto/target_cpa
	BidValue       float64   `json:"bid_value"`
	TargetCPA      float64   `json:"target_cpa"`
	DailyBudget    float64   `json:"daily_budget"`
	TotalSpend     float64   `json:"total_spend"`
	TodaySpend     float64   `json:"today_spend"`
	YesterdaySpend float64   `json:"yesterday_spend"`
	CreatedAt      time.Time `json:"created_at"`
}

// AdMetrics 广告指标
type AdMetrics struct {
	CampaignID  string    `json:"campaign_id"`
	Day         string    `json:"day"`
	Impressions int64     `json:"impressions"`
	Clicks      int64     `json:"clicks"`
	Conversions int64     `json:"conversions"`
	Spend       float64   `json:"spend"`
	CTR         float64   `json:"ctr"`
	CPC         float64   `json:"cpc"`
	CPA         float64   `json:"cpa"`
	ROAS        float64   `json:"roas"`
}

// User 用户画像
type User struct {
	UserID    string    `json:"user_id"`
	Age       int       `json:"age"`
	Gender    string    `json:"gender"`
	City      string    `json:"city"`
	Interests []string  `json:"interests"`
	FraudScore float64  `json:"fraud_score"`
}

// Product 产品信息
type Product struct {
	Name          string    `json:"name"`
	Category      string    `json:"category"`
	Price         float64   `json:"price"`
	SellingPoints []string  `json:"selling_points"`
	Description   string    `json:"description"`
}

// Creative 创意
type Creative struct {
	ID       string    `json:"id"`
	Type     string    `json:"type"` // image/video/copy
	Content  string    `json:"content"`
	URL      string    `json:"url"`
	CTR      float64   `json:"ctr"`
	Status   string    `json:"status"`
}

// Anomaly 异常
type Anomaly struct {
	Type        string    `json:"type"`
	Severity    string    `json:"severity"` // critical/warning/info
	Description string    `json:"description"`
	Suggestion  string    `json:"suggestion"`
	DetectedAt  time.Time `json:"detected_at"`
}

// ---- 工具接口 ----

// Tool 工具基类
type Tool interface {
	Name() string
	Description() string
	Execute(ctx context.Context, args map[string]interface{}) (interface{}, error)
}

// ---- 智能优化师 Agent ----

// SmartOptimizerAgent 智能优化师 Agent
type SmartOptimizerAgent struct {
	mu          sync.RWMutex
	memory      *AgentMemory
	tools       map[string]Tool
	llm         *MockLLM
	recentActs  []ActionRecord
	maxHistory  int
}

// ActionRecord 操作记录
type ActionRecord struct {
	Timestamp time.Time `json:"timestamp"`
	Action    string    `json:"action"`
	Args      string    `json:"args"`
	Result    string    `json:"result"`
}

// NewSmartOptimizerAgent 创建智能优化师
func NewSmartOptimizerAgent() *SmartOptimizerAgent {
	agent := &SmartOptimizerAgent{
		memory:     NewAgentMemory(),
		tools:      make(map[string]Tool),
		llm:        NewMockLLM(),
		maxHistory: 100,
	}

	// 注册工具
	agent.RegisterTool(&GetPerformanceTool{})
	agent.RegisterTool(&AdjustBidTool{})
	agent.RegisterTool(&DetectAnomalyTool{})
	agent.RegisterTool(&AllocateBudgetTool{})
	agent.RegisterTool(&GenerateReportTool{})

	return agent
}

// RegisterTool 注册工具
func (a *SmartOptimizerAgent) RegisterTool(tool Tool) {
	a.mu.Lock()
	defer a.mu.Unlock()
	a.tools[tool.Name()] = tool
	log.Printf("工具已注册: %s - %s", tool.Name(), tool.Description())
}

// Run 执行优化任务
func (a *SmartOptimizerAgent) Run(ctx context.Context, goal string) ([]ActionRecord, error) {
	log.Printf("🤖 Agent 开始执行目标: %s", goal)

	plan := a.plan(goal)
	log.Printf("📋 执行计划: %s", plan)

	records := make([]ActionRecord, 0)
	steps := a.parsePlan(plan)

	for _, step := range steps {
		select {
		case <-ctx.Done():
			return records, ctx.Err()
		default:
			result, err := a.executeStep(ctx, step)
			record := ActionRecord{
				Timestamp: time.Now(),
				Action:    step,
				Result:    fmt.Sprintf("%v", result),
			}
			if err != nil {
				record.Result = fmt.Sprintf("错误: %v", err)
			}
			records = append(records, record)
			a.recentActs = append(a.recentActs, record)
			if len(a.recentActs) > a.maxHistory {
				a.recentActs = a.recentActs[len(a.recentActs)-a.maxHistory:]
			}
		}
	}

	log.Printf("✅ 目标执行完成，共 %d 步操作", len(records))
	return records, nil
}

// plan 生成执行计划
func (a *SmartOptimizerAgent) plan(goal string) string {
	// 简单规划逻辑
	if strings.Contains(goal, "优化") || strings.Contains(goal, "调价") {
		return "1. 获取所有广告组表现\n2. 检测异常\n3. 对表现差的广告组调整出价\n4. 对表现好的广告组增加预算\n5. 生成优化报告"
	} else if strings.Contains(goal, "预算") {
		return "1. 获取所有广告组 ROI\n2. 按 ROI 排序\n3. 将预算分配到高效广告组\n4. 生成预算分配报告"
	} else if strings.Contains(goal, "异常") {
		return "1. 扫描所有广告组\n2. 检测 CTR 骤降\n3. 检测 CPA 飙升\n4. 检测预算耗尽\n5. 生成异常报告"
	}
	
	return "1. 获取广告组表现\n2. 检测异常\n3. 生成报告"
}

// parsePlan 解析计划为步骤
func (a *SmartOptimizerAgent) parsePlan(plan string) []string {
	steps := make([]string, 0)
	for _, line := range strings.Split(plan, "\n") {
		line = strings.TrimSpace(line)
		if line != "" {
			// 移除编号
			idx := strings.Index(line, ".")
			if idx > 0 {
				line = line[idx+1:]
			}
			line = strings.TrimSpace(line)
			steps = append(steps, line)
		}
	}
	return steps
}

// executeStep 执行单步操作
func (a *SmartOptimizerAgent) executeStep(ctx context.Context, step string) (interface{}, error) {
	log.Printf("执行步骤: %s", step)

	switch {
	case strings.Contains(step, "获取") && strings.Contains(step, "表现"):
		return a.tools["get_performance"].Execute(ctx, map[string]interface{}{})
	case strings.Contains(step, "检测") && strings.Contains(step, "异常"):
		return a.tools["detect_anomaly"].Execute(ctx, map[string]interface{}{})
	case strings.Contains(step, "调整") && strings.Contains(step, "出价"):
		return a.tools["adjust_bid"].Execute(ctx, map[string]interface{}{
			"strategy": "auto",
		})
	case strings.Contains(step, "预算") && strings.Contains(step, "分配"):
		return a.tools["allocate_budget"].Execute(ctx, map[string]interface{}{})
	case strings.Contains(step, "报告"):
		return a.tools["generate_report"].Execute(ctx, map[string]interface{}{})
	default:
		return nil, fmt.Errorf("未知步骤: %s", step)
	}
}

// ---- 工具实现 ----

// GetPerformanceTool 获取广告表现工具
type GetPerformanceTool struct{}

func (t *GetPerformanceTool) Name() string {
	return "get_performance"
}

func (t *GetPerformanceTool) Description() string {
	return "获取广告组的近期表现数据"
}

func (t *GetPerformanceTool) Execute(ctx context.Context, args map[string]interface{}) (interface{}, error) {
	// 模拟数据
	metrics := []AdMetrics{
		{CampaignID: "camp_001", Day: "2026-01-01", Impressions: 50000, Clicks: 1500, Conversions: 30, Spend: 750, CTR: 0.03, CPC: 0.50, CPA: 25.0, ROAS: 3.5},
		{CampaignID: "camp_001", Day: "2026-01-02", Impressions: 48000, Clicks: 1440, Conversions: 28, Spend: 720, CTR: 0.03, CPC: 0.50, CPA: 25.71, ROAS: 3.4},
		{CampaignID: "camp_001", Day: "2026-01-03", Impressions: 45000, Clicks: 1350, Conversions: 25, Spend: 675, CTR: 0.03, CPC: 0.50, CPA: 27.0, ROAS: 3.2},
		{CampaignID: "camp_002", Day: "2026-01-01", Impressions: 80000, Clicks: 3200, Conversions: 160, Spend: 1600, CTR: 0.04, CPC: 0.50, CPA: 10.0, ROAS: 8.5},
		{CampaignID: "camp_002", Day: "2026-01-02", Impressions: 82000, Clicks: 3280, Conversions: 164, Spend: 1640, CTR: 0.04, CPC: 0.50, CPA: 10.0, ROAS: 8.6},
		{CampaignID: "camp_002", Day: "2026-01-03", Impressions: 85000, Clicks: 3400, Conversions: 170, Spend: 1700, CTR: 0.04, CPC: 0.50, CPA: 10.0, ROAS: 8.7},
		{CampaignID: "camp_003", Day: "2026-01-01", Impressions: 30000, Clicks: 600, Conversions: 6, Spend: 300, CTR: 0.02, CPC: 0.50, CPA: 50.0, ROAS: 1.2},
		{CampaignID: "camp_003", Day: "2026-01-02", Impressions: 28000, Clicks: 560, Conversions: 5, Spend: 280, CTR: 0.02, CPC: 0.50, CPA: 56.0, ROAS: 1.1},
		{CampaignID: "camp_003", Day: "2026-01-03", Impressions: 25000, Clicks: 500, Conversions: 4, Spend: 250, CTR: 0.02, CPC: 0.50, CPA: 62.5, ROAS: 1.0},
	}

	log.Printf("📊 获取到 %d 条广告表现数据", len(metrics))
	return metrics, nil
}

// AdjustBidTool 调整出价工具
type AdjustBidTool struct{}

func (t *AdjustBidTool) Name() string {
	return "adjust_bid"
}

func (t *AdjustBidTool) Description() string {
	return "根据广告表现自动调整出价"
}

func (t *AdjustBidTool) Execute(ctx context.Context, args map[string]interface{}) (interface{}, error) {
	strategy := "auto"
	if s, ok := args["strategy"].(string); ok {
		strategy = s
	}

	adjustments := make([]BidAdjustment, 0)

	// 模拟调价逻辑
	campaigns := []struct {
		ID       string
		CurrentBid float64
		TargetCPA  float64
		ActualCPA  float64
		ROAS       float64
	}{
		{"camp_001", 0.50, 20.0, 27.0, 3.2},
		{"camp_002", 0.50, 10.0, 10.0, 8.7},
		{"camp_003", 0.50, 40.0, 62.5, 1.0},
	}

	for _, c := range campaigns {
		var adjustment float64
		var reason string

		if strategy == "auto" {
			if c.ActualCPA > c.TargetCPA*1.2 {
				// CPA 超标，降低出价
				adjustment = -0.15
				reason = fmt.Sprintf("CPA (%.2f) 超过目标 (%.2f) 的 120%%", c.ActualCPA, c.TargetCPA)
			} else if c.ActualCPA < c.TargetCPA*1.0 && c.ROAS > 3.0 {
				// CPA 达标且 ROAS 高，提高出价获取更多流量
				adjustment = 0.10
				reason = fmt.Sprintf("CPA (%.2f) 达标，ROAS (%.2f) 优秀", c.ActualCPA, c.ROAS)
			} else if c.ROAS > 5.0 {
				// ROAS 极高，大幅提高出价抢流量
				adjustment = 0.20
				reason = fmt.Sprintf("ROAS 极高 (%.2f)，加大投入", c.ROAS)
			} else {
				adjustment = 0.0
				reason = "表现稳定，无需调整"
			}
		}

		newBid := c.CurrentBid * (1 + adjustment)
		adjustments = append(adjustments, BidAdjustment{
			CampaignID: c.ID,
			OldBid:     c.CurrentBid,
			NewBid:     newBid,
			Adjustment: adjustment,
			Reason:     reason,
		})
	}

	log.Printf("💰 执行 %d 次出价调整", len(adjustments))
	return adjustments, nil
}

type BidAdjustment struct {
	CampaignID string  `json:"campaign_id"`
	OldBid     float64 `json:"old_bid"`
	NewBid     float64 `json:"new_bid"`
	Adjustment float64 `json:"adjustment"`
	Reason     string  `json:"reason"`
}

// DetectAnomalyTool 异常检测工具
type DetectAnomalyTool struct{}

func (t *DetectAnomalyTool) Name() string {
	return "detect_anomaly"
}

func (t *DetectAnomalyTool) Description() string {
	return "检测广告表现异常"
}

func (t *DetectAnomalyTool) Execute(ctx context.Context, args map[string]interface{}) (interface{}, error) {
	anomalies := make([]Anomaly, 0)

	// 模拟异常检测
	// 1. camp_001 CPA 持续上升
	anomalies = append(anomalies, Anomaly{
		Type:        "cpa_rising",
		Severity:    "warning",
		Description: "广告组 camp_001 CPA 连续 3 天上升：25.0 → 25.71 → 27.0",
		Suggestion:  "建议降低出价 10-15% 或优化创意提升 CTR",
		DetectedAt:  time.Now(),
	})

	// 2. camp_003 CPA 严重超标
	anomalies = append(anomalies, Anomaly{
		Type:        "cpa_exceeded",
		Severity:    "critical",
		Description: "广告组 camp_003 CPA 为 62.5，远超目标 40.0",
		Suggestion:  "建议暂停该广告组或大幅降低出价",
		DetectedAt:  time.Now(),
	})

	// 3. camp_003 表现持续恶化
	anomalies = append(anomalies, Anomaly{
		Type:        "performance_declining",
		Severity:    "warning",
		Description: "广告组 camp_003 展示量连续下降：30000 → 28000 → 25000",
		Suggestion:  "检查创意是否疲劳，考虑更换素材",
		DetectedAt:  time.Now(),
	})

	log.Printf("🚨 检测到 %d 个异常", len(anomalies))
	return anomalies, nil
}

// AllocateBudgetTool 预算分配工具
type AllocateBudgetTool struct{}

func (t *AllocateBudgetTool) Name() string {
	return "allocate_budget"
}

func (t *AllocateBudgetTool) Description() string {
	return "根据 ROI 优化预算分配"
}

func (t *AllocateBudgetTool) Execute(ctx context.Context, args map[string]interface{}) (interface{}, error) {
	totalBudget := 10000.0

	// 模拟预算分配
	allocations := []BudgetAllocation{
		{CampaignID: "camp_001", CurrentBudget: 3000, ROAS: 3.2, NewBudget: 2500, Change: -500},
		{CampaignID: "camp_002", CurrentBudget: 5000, ROAS: 8.7, NewBudget: 6500, Change: 1500},
		{CampaignID: "camp_003", CurrentBudget: 2000, ROAS: 1.0, NewBudget: 1000, Change: -1000},
	}

	// 验证总预算
	totalNew := 0.0
	for _, a := range allocations {
		totalNew += a.NewBudget
	}

	log.Printf("💰 预算分配完成：总额 %.2f → %.2f", totalBudget, totalNew)
	return allocations, nil
}

type BudgetAllocation struct {
	CampaignID    string  `json:"campaign_id"`
	CurrentBudget float64 `json:"current_budget"`
	ROAS          float64 `json:"roas"`
	NewBudget     float64 `json:"new_budget"`
	Change        float64 `json:"change"`
}

// GenerateReportTool 生成报告工具
type GenerateReportTool struct{}

func (t *GenerateReportTool) Name() string {
	return "generate_report"
}

func (t *GenerateReportTool) Description() string {
	return "生成广告优化报告"
}

func (t *GenerateReportTool) Execute(ctx context.Context, args map[string]interface{}) (interface{}, error) {
	report := Report{
		Title:       "广告优化日报",
		GeneratedAt: time.Now(),
		Summary:     "3 个广告组，2 个需要优化，1 个表现优秀",
		Metrics:     t.generateMetrics(),
		Recommendations: []string{
			"camp_002: ROI 优秀（8.7），建议增加预算 30%",
			"camp_001: CPA 缓慢上升，建议降低出价 10%",
			"camp_003: CPA 严重超标（62.5 vs 40），建议暂停或大幅降价",
		},
	}

	jsonData, _ := json.MarshalIndent(report, "", "  ")
	log.Printf("📄 报告生成完成: %s", string(jsonData))
	return report, nil
}

type Report struct {
	Title           string      `json:"title"`
	GeneratedAt     time.Time   `json:"generated_at"`
	Summary         string      `json:"summary"`
	Metrics         interface{} `json:"metrics"`
	Recommendations []string    `json:"recommendations"`
}

func (t *GenerateReportTool) generateMetrics() map[string]interface{} {
	return map[string]interface{}{
		"total_campaigns": 3,
		"total_impressions": 313000,
		"total_clicks": 11190,
		"total_conversions": 397,
		"total_spend": 5600,
		"avg_ctr": 0.032,
		"avg_cpa": 22.42,
		"avg_roas": 3.63,
	}
}

// ---- Agent 记忆系统 ----

// AgentMemory Agent 记忆系统
type AgentMemory struct {
	mu          sync.RWMutex
	actions     []ActionRecord
	knowledge   map[string]interface{}
	lastOptimized time.Time
}

// NewAgentMemory 创建记忆系统
func NewAgentMemory() *AgentMemory {
	return &AgentMemory{
		actions:   make([]ActionRecord, 0),
		knowledge: make(map[string]interface{}),
	}
}

// AddAction 添加操作记录
func (m *AgentMemory) AddAction(action ActionRecord) {
	m.mu.Lock()
	defer m.mu.Unlock()
	m.actions = append(m.actions, action)
	if len(m.actions) > 1000 {
		m.actions = m.actions[len(m.actions)-1000:]
	}
}

// GetRecentActions 获取最近 N 条操作
func (m *AgentMemory) GetRecentActions(n int) []ActionRecord {
	m.mu.RLock()
	defer m.mu.RUnlock()
	
	if n > len(m.actions) {
		n = len(m.actions)
	}
	
	result := make([]ActionRecord, n)
	copy(result, m.actions[len(m.actions)-n:])
	return result
}

// SetKnowledge 设置知识
func (m *AgentMemory) SetKnowledge(key string, value interface{}) {
	m.mu.Lock()
	defer m.mu.Unlock()
	m.knowledge[key] = value
}

// GetKnowledge 获取知识
func (m *AgentMemory) GetKnowledge(key string) interface{} {
	m.mu.RLock()
	defer m.mu.RUnlock()
	return m.knowledge[key]
}

// ---- Mock LLM ----

// MockLLM 模拟 LLM
type MockLLM struct{}

func NewMockLLM() *MockLLM {
	return &MockLLM{}
}

func (l *MockLLM) Generate(prompt string) string {
	// 根据 prompt 生成不同的回复
	if strings.Contains(prompt, "优化") {
		return "建议优化方案：1. 提高 camp_002 预算 2. 降低 camp_001 出价 3. 暂停 camp_003"
	}
	if strings.Contains(prompt, "创意") {
		return "建议创意方向：1. 突出产品卖点 2. 使用真实用户评价 3. 添加限时优惠"
	}
	return "分析完成，建议按当前策略继续执行"
}

// ---- 主函数（可直接运行） ----

func main() {
	ctx := context.Background()
	
	// 创建 Agent
	agent := NewSmartOptimizerAgent()
	
	// 执行优化任务
	fmt.Println("========================================")
	fmt.Println("🤖 广告 Agent 优化器演示")
	fmt.Println("========================================")
	
	records, err := agent.Run(ctx, "优化所有广告组表现，降低 CPA 提升 ROAS")
	if err != nil {
		log.Fatal(err)
	}
	
	fmt.Println("\n========================================")
	fmt.Println("📋 执行记录")
	fmt.Println("========================================")
	for i, r := range records {
		fmt.Printf("\n[%d] %s\n", i+1, r.Action)
		fmt.Printf("    结果: %s\n", r.Result)
	}
	
	// 执行预算分配
	fmt.Println("\n========================================")
	fmt.Println("💰 预算分配优化")
	fmt.Println("========================================")
	budgetResult, _ := agent.tools["allocate_budget"].Execute(ctx, nil)
	budgets, _ := json.MarshalIndent(budgetResult, "", "  ")
	fmt.Println(string(budgets))
	
	// 执行异常检测
	fmt.Println("\n========================================")
	fmt.Println("🚨 异常检测")
	fmt.Println("========================================")
	anomalyResult, _ := agent.tools["detect_anomaly"].Execute(ctx, nil)
	anomalies, _ := json.MarshalIndent(anomalyResult, "", "  ")
	fmt.Println(string(anomalies))
	
	// 生成报告
	fmt.Println("\n========================================")
	fmt.Println("📄 优化报告")
	fmt.Println("========================================")
	reportResult, _ := agent.tools["generate_report"].Execute(ctx, nil)
	report, _ := json.MarshalIndent(reportResult, "", "  ")
	fmt.Println(string(report))
}

// ============================================================
// 单元测试
// ============================================================

func TestSmartOptimizerAgent(t *testing.T) {
	agent := NewSmartOptimizerAgent()
	ctx := context.Background()

	t.Run("注册工具", func(t *testing.T) {
		if len(agent.tools) != 5 {
			t.Errorf("期望 5 个工具，实际 %d 个", len(agent.tools))
		}
	})

	t.Run("获取表现数据", func(t *testing.T) {
		result, err := agent.tools["get_performance"].Execute(ctx, nil)
		if err != nil {
			t.Fatalf("获取表现数据失败: %v", err)
		}
		
		metrics, ok := result.([]AdMetrics)
		if !ok {
			t.Fatalf("结果类型错误: %T", result)
		}
		
		if len(metrics) == 0 {
			t.Error("没有返回任何数据")
		}
		
		t.Logf("✅ 获取到 %d 条指标数据", len(metrics))
	})

	t.Run("异常检测", func(t *testing.T) {
		result, err := agent.tools["detect_anomaly"].Execute(ctx, nil)
		if err != nil {
			t.Fatalf("异常检测失败: %v", err)
		}
		
		anomalies, ok := result.([]Anomaly)
		if !ok {
			t.Fatalf("结果类型错误: %T", result)
		}
		
		// 应该检测到至少 1 个异常
		if len(anomalies) == 0 {
			t.Error("没有检测到任何异常")
		}
		
		// 检查严重级别
		hasCritical := false
		for _, a := range anomalies {
			if a.Severity == "critical" {
				hasCritical = true
			}
		}
		
		if !hasCritical {
			t.Error("应该检测到至少 1 个 critical 级别异常")
		}
		
		t.Logf("✅ 检测到 %d 个异常（含 %d 个 critical）", len(anomalies), countBySeverity(anomalies, "critical"))
	})

	t.Run("调价", func(t *testing.T) {
		result, err := agent.tools["adjust_bid"].Execute(ctx, map[string]interface{}{"strategy": "auto"})
		if err != nil {
			t.Fatalf("调价失败: %v", err)
		}
		
		adjustments, ok := result.([]BidAdjustment)
		if !ok {
			t.Fatalf("结果类型错误: %T", result)
		}
		
		// 应该有至少 1 次调价
		if len(adjustments) == 0 {
			t.Error("没有生成任何调价建议")
		}
		
		// 检查调价逻辑
		for _, adj := range adjustments {
			t.Logf("   %s: %.4f → %.4f (%.1f%%) - %s",
				adj.CampaignID, adj.OldBid, adj.NewBid, adj.Adjustment*100, adj.Reason)
		}
		
		// camp_003 应该被降低出价（CPA 超标）
		for _, adj := range adjustments {
			if adj.CampaignID == "camp_003" && adj.Adjustment >= 0 {
				t.Error("camp_003 CPA 严重超标，应该降低出价")
			}
		}
		
		// camp_002 应该提高出价（ROAS 优秀）
		for _, adj := range adjustments {
			if adj.CampaignID == "camp_002" && adj.Adjustment <= 0 {
				t.Error("camp_002 ROAS 优秀，应该提高出价")
			}
		}
	})

	t.Run("预算分配", func(t *testing.T) {
		result, err := agent.tools["allocate_budget"].Execute(ctx, nil)
		if err != nil {
			t.Fatalf("预算分配失败: %v", err)
		}
		
		allocations, ok := result.([]BudgetAllocation)
		if !ok {
			t.Fatalf("结果类型错误: %T", result)
		}
		
		// 检查预算分配逻辑
		for _, alloc := range allocations {
			t.Logf("   %s: %.0f → %.0f (%s, ROAS=%.1f)",
				alloc.CampaignID, alloc.CurrentBudget, alloc.NewBudget,
				formatChange(alloc.Change), alloc.ROAS)
			
			// ROAS 高的应该增加预算
			if alloc.ROAS > 5.0 && alloc.Change < 0 {
				t.Errorf("ROAS %.1f 的广告组不应该减少预算", alloc.ROAS)
			}
			
			// ROAS 低的应该减少预算
			if alloc.ROAS < 2.0 && alloc.Change > 0 {
				t.Errorf("ROAS %.1f 的广告组不应该增加预算", alloc.ROAS)
			}
		}
	})

	t.Run("生成报告", func(t *testing.T) {
		result, err := agent.tools["generate_report"].Execute(ctx, nil)
		if err != nil {
			t.Fatalf("生成报告失败: %v", err)
		}
		
		report, ok := result.(Report)
		if !ok {
			t.Fatalf("结果类型错误: %T", result)
		}
		
		if report.Title == "" {
			t.Error("报告标题为空")
		}
		
		if len(report.Recommendations) == 0 {
			t.Error("没有生成任何建议")
		}
		
		t.Logf("✅ 报告生成完成: %s", report.Summary)
		for _, rec := range report.Recommendations {
			t.Logf("   • %s", rec)
		}
	})

	t.Run("完整优化流程", func(t *testing.T) {
		records, err := agent.Run(ctx, "优化广告表现")
		if err != nil {
			t.Fatalf("优化流程失败: %v", err)
		}
		
		if len(records) == 0 {
			t.Error("没有执行任何操作")
		}
		
		// 检查是否有异常检测和调价
		hasAnomaly := false
		hasBid := false
		for _, r := range records {
			if strings.Contains(r.Action, "异常") {
				hasAnomaly = true
			}
			if strings.Contains(r.Action, "出价") {
				hasBid = true
			}
		}
		
		if !hasAnomaly {
			t.Error("应该执行异常检测")
		}
		if !hasBid {
			t.Error("应该执行调价")
		}
		
		t.Logf("✅ 完整流程执行 %d 步", len(records))
	})
}

// 辅助函数
func countBySeverity(anomalies []Anomaly, severity string) int {
	count := 0
	for _, a := range anomalies {
		if a.Severity == severity {
			count++
		}
	}
	return count
}

func formatChange(change float64) string {
	if change > 0 {
		return fmt.Sprintf("+%.0f", change)
	}
	return fmt.Sprintf("%.0f", change)
}

// 运行测试
func TestMain(m *testing.M) {
	// 设置日志输出到文件
	logFile, err := os.Create("/tmp/ad-agent-test.log")
	if err == nil {
		defer logFile.Close()
		log.SetOutput(logFile)
	}
	
	os.Exit(m.Run())
}
