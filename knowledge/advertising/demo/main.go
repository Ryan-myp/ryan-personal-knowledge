package main

import (
	"context"
	"encoding/json"
	"fmt"
	"os"
	"strings"
	"sync"
	"time"
)

// ============================================================
// 广告 Agent 优化器 - 可运行的演示
// ============================================================

// ---- 数据模型 ----

type AdMetrics struct {
	CampaignID  string  `json:"campaign_id"`
	Day         string  `json:"day"`
	Impressions int64   `json:"impressions"`
	Clicks      int64   `json:"clicks"`
	Conversions int64   `json:"conversions"`
	Spend       float64 `json:"spend"`
	CTR         float64 `json:"ctr"`
	CPC         float64 `json:"cpc"`
	CPA         float64 `json:"cpa"`
	ROAS        float64 `json:"roas"`
}

type Anomaly struct {
	Type        string    `json:"type"`
	Severity    string    `json:"severity"`
	Description string    `json:"description"`
	Suggestion  string    `json:"suggestion"`
	DetectedAt  time.Time `json:"detected_at"`
}

type BidAdjustment struct {
	CampaignID string  `json:"campaign_id"`
	OldBid     float64 `json:"old_bid"`
	NewBid     float64 `json:"new_bid"`
	Adjustment float64 `json:"adjustment"`
	Reason     string  `json:"reason"`
}

type BudgetAllocation struct {
	CampaignID    string  `json:"campaign_id"`
	CurrentBudget float64 `json:"current_budget"`
	ROAS          float64 `json:"roas"`
	NewBudget     float64 `json:"new_budget"`
	Change        float64 `json:"change"`
}

type Report struct {
	Title           string      `json:"title"`
	GeneratedAt     time.Time   `json:"generated_at"`
	Summary         string      `json:"summary"`
	Metrics         interface{} `json:"metrics"`
	Recommendations []string    `json:"recommendations"`
}

// ---- 核心引擎 ----

type SmartOptimizerAgent struct {
	mu         sync.RWMutex
	tools      map[string]interface{}
	recentActs []string
}

func NewSmartOptimizerAgent() *SmartOptimizerAgent {
	return &SmartOptimizerAgent{
		tools: make(map[string]interface{}),
	}
}

// Run 执行完整优化流程
func (a *SmartOptimizerAgent) Run(ctx context.Context, goal string) ([]map[string]string, error) {
	fmt.Printf("\n🤖 Agent 接收指令: \"%s\"\n", goal)
	fmt.Println("📋 生成执行计划...")

	// 生成计划
	plan := a.plan(goal)
	lines := strings.Split(plan, "\n")
	for i, line := range lines {
		fmt.Printf("   %d. %s\n", i+1, strings.TrimSpace(line))
	}

	// 执行步骤
	records := make([]map[string]string, 0)

	// Step 1: 获取表现
	fmt.Println("\n── 第 1 步：获取广告表现数据 ──")
	metrics := a.getPerformance(ctx)
	records = append(records, map[string]string{
		"step":   "获取表现数据",
		"result": fmt.Sprintf("获取到 %d 条数据", len(metrics)),
	})

	// Step 2: 检测异常
	fmt.Println("\n── 第 2 步：检测异常 ──")
	anomalies := a.detectAnomalies(ctx, metrics)
	records = append(records, map[string]string{
		"step":   "异常检测",
		"result": fmt.Sprintf("发现 %d 个异常", len(anomalies)),
	})

	// Step 3: 自动调价
	fmt.Println("\n── 第 3 步：自动调价 ──")
	adjustments := a.adjustBid(ctx, metrics, anomalies)
	records = append(records, map[string]string{
		"step":   "自动调价",
		"result": fmt.Sprintf("执行 %d 次调价", len(adjustments)),
	})

	// Step 4: 预算分配
	fmt.Println("\n── 第 4 步：预算分配 ──")
	allocations := a.allocateBudget(ctx, metrics)
	records = append(records, map[string]string{
		"step":   "预算分配",
		"result": fmt.Sprintf("重新分配 %d 个广告组预算", len(allocations)),
	})

	// Step 5: 生成报告
	fmt.Println("\n── 第 5 步：生成优化报告 ──")
	report := a.generateReport(ctx, metrics, anomalies, adjustments, allocations)
	records = append(records, map[string]string{
		"step":   "生成报告",
		"result": fmt.Sprintf("报告: %s", report.Summary),
	})

	return records, nil
}

// plan 生成执行计划
func (a *SmartOptimizerAgent) plan(goal string) string {
	return "1. 获取所有广告组表现数据\n2. 检测表现异常\n3. 根据表现调整出价\n4. 优化预算分配\n5. 生成优化报告"
}

// getPerformance 获取广告表现
func (a *SmartOptimizerAgent) getPerformance(ctx context.Context) []AdMetrics {
	return []AdMetrics{
		{CampaignID: "camp_001", Day: "2026-01-03", Impressions: 45000, Clicks: 1350, Conversions: 25, Spend: 675, CTR: 0.03, CPC: 0.50, CPA: 27.0, ROAS: 3.2},
		{CampaignID: "camp_002", Day: "2026-01-03", Impressions: 85000, Clicks: 3400, Conversions: 170, Spend: 1700, CTR: 0.04, CPC: 0.50, CPA: 10.0, ROAS: 8.7},
		{CampaignID: "camp_003", Day: "2026-01-03", Impressions: 25000, Clicks: 500, Conversions: 4, Spend: 250, CTR: 0.02, CPC: 0.50, CPA: 62.5, ROAS: 1.0},
	}
}

// detectAnomalies 检测异常
func (a *SmartOptimizerAgent) detectAnomalies(ctx context.Context, metrics []AdMetrics) []Anomaly {
	anomalies := make([]Anomaly, 0)

	for _, m := range metrics {
		switch m.CampaignID {
		case "camp_001":
			if m.CPA > 20 {
				anomalies = append(anomalies, Anomaly{
					Type:        "cpa_rising",
					Severity:    "warning",
					Description: fmt.Sprintf("camp_001 CPA 为 %.2f，高于目标 20.00", m.CPA),
					Suggestion:  "降低出价 10-15%",
				})
			}
		case "camp_002":
			// 表现优秀，无异常
		case "camp_003":
			if m.CPA > 40 {
				anomalies = append(anomalies, Anomaly{
					Type:        "cpa_exceeded",
					Severity:    "critical",
					Description: fmt.Sprintf("camp_003 CPA 为 %.2f，远超目标 40.00", m.CPA),
					Suggestion:  "暂停广告组或大幅降低出价",
				})
			}
		}
	}

	return anomalies
}

// adjustBid 自动调价
func (a *SmartOptimizerAgent) adjustBid(ctx context.Context, metrics []AdMetrics, anomalies []Anomaly) []BidAdjustment {
	adjustments := make([]BidAdjustment, 0)

	// 构建 CPA 映射
	cpaMap := make(map[string]float64)
	roasMap := make(map[string]float64)
	for _, m := range metrics {
		cpaMap[m.CampaignID] = m.CPA
		roasMap[m.CampaignID] = m.ROAS
	}

	targets := map[string]float64{
		"camp_001": 20.0,
		"camp_002": 10.0,
		"camp_003": 40.0,
	}

	for campID, target := range targets {
		actualCPA := cpaMap[campID]
		roas := roasMap[campID]
		var adj float64
		var reason string

		if actualCPA > target*1.2 {
			adj = -0.15
			reason = fmt.Sprintf("CPA (%.2f) 超过目标 (%.2f) 的 120%%", actualCPA, target)
		} else if roas > 5.0 {
			adj = 0.20
			reason = fmt.Sprintf("ROAS 极高 (%.2f)，加大投入", roas)
		} else if actualCPA < target*1.0 {
			adj = 0.10
			reason = fmt.Sprintf("CPA (%.2f) 达标，ROAS (%.2f) 良好", actualCPA, roas)
		} else {
			adj = 0.0
			reason = "表现稳定"
		}

		adjustments = append(adjustments, BidAdjustment{
			CampaignID: campID,
			OldBid:     0.50,
			NewBid:     0.50 * (1 + adj),
			Adjustment: adj,
			Reason:     reason,
		})
	}

	return adjustments
}

// allocateBudget 预算分配
func (a *SmartOptimizerAgent) allocateBudget(ctx context.Context, metrics []AdMetrics) []BudgetAllocation {
	// 按 ROI 排序分配
	allocations := []BudgetAllocation{
		{CampaignID: "camp_001", CurrentBudget: 3000, ROAS: 3.2, NewBudget: 2500, Change: -500},
		{CampaignID: "camp_002", CurrentBudget: 5000, ROAS: 8.7, NewBudget: 6500, Change: 1500},
		{CampaignID: "camp_003", CurrentBudget: 2000, ROAS: 1.0, NewBudget: 1000, Change: -1000},
	}
	return allocations
}

// generateReport 生成报告
func (a *SmartOptimizerAgent) generateReport(ctx context.Context, metrics []AdMetrics, anomalies []Anomaly, adjustments []BidAdjustment, allocations []BudgetAllocation) Report {
	return Report{
		Title:       "广告优化日报",
		GeneratedAt: time.Now(),
		Summary:     fmt.Sprintf("3 个广告组 | %d 个异常 | 优化建议 3 条", len(anomalies)),
		Metrics: map[string]interface{}{
			"total_impressions": 155000,
			"total_clicks":      5250,
			"total_conversions": 199,
			"total_spend":       2625,
			"avg_ctr":           0.032,
			"avg_cpa":           13.19,
			"avg_roas":          4.3,
		},
		Recommendations: []string{
			"camp_002: ROAS 8.7，建议增加预算 30%，提高出价 20%",
			"camp_001: CPA 缓慢上升，建议降低出价 15%",
			"camp_003: CPA 严重超标，建议暂停或大幅降价",
		},
	}
}

// ============================================================
// 主函数 - 直接运行看效果
// ============================================================

func main() {
	agent := NewSmartOptimizerAgent()

	// 1. 完整优化流程
	records, _ := agent.Run(context.Background(), "优化所有广告组表现，降低 CPA 提升 ROAS")

	// 2. 打印执行摘要
	fmt.Println("\n========================================")
	fmt.Println("📊 执行摘要")
	fmt.Println("========================================")
	for _, r := range records {
		fmt.Printf("  ✅ %s → %s\n", r["step"], r["result"])
	}

	// 3. 详细展示每个工具的输出
	fmt.Println("\n========================================")
	fmt.Println("📊 详细输出")
	fmt.Println("========================================")

	// 表现数据
	fmt.Println("\n【广告表现】")
	metrics := agent.getPerformance(context.Background())
	for _, m := range metrics {
		fmt.Printf("  %-8s | 展示:%6d | 点击:%5d | 转化:%3d | 花费:¥%5.0f | CTR:%.2f%% | CPA:¥%.1f | ROAS:%.1f\n",
			m.CampaignID, m.Impressions, m.Clicks, m.Conversions, m.Spend, m.CTR*100, m.CPA, m.ROAS)
	}

	// 异常
	fmt.Println("\n【异常检测】")
	anomalies := agent.detectAnomalies(context.Background(), metrics)
	for _, a := range anomalies {
		emoji := "🔵"
		if a.Severity == "warning" {
			emoji = "🟡"
		} else if a.Severity == "critical" {
			emoji = "🔴"
		}
		fmt.Printf("  %s [%s] %s\n", emoji, a.Severity, a.Description)
		fmt.Printf("     建议: %s\n", a.Suggestion)
	}

	// 调价
	fmt.Println("\n【自动调价】")
	adjustments := agent.adjustBid(context.Background(), metrics, anomalies)
	for _, a := range adjustments {
		sign := ""
		if a.Adjustment > 0 {
			sign = "+"
		}
		fmt.Printf("  %s: ¥%.4f → ¥%.4f (%s%.0f%%)\n", a.CampaignID, a.OldBid, a.NewBid, sign, a.Adjustment*100)
		fmt.Printf("     原因: %s\n", a.Reason)
	}

	// 预算
	fmt.Println("\n【预算分配】")
	allocations := agent.allocateBudget(context.Background(), metrics)
	for _, a := range allocations {
		change := "+"
		if a.Change < 0 {
			change = ""
		}
		fmt.Printf("  %s: ¥%.0f → ¥%.0f (%s¥%.0f) | ROAS %.1f\n",
			a.CampaignID, a.CurrentBudget, a.NewBudget, change, a.Change, a.ROAS)
	}

	// 报告
	fmt.Println("\n【优化报告】")
	report := agent.generateReport(context.Background(), metrics, anomalies, adjustments, allocations)
	fmt.Printf("  标题: %s\n", report.Title)
	fmt.Printf("  摘要: %s\n", report.Summary)
	fmt.Printf("  汇总指标:\n")
	for k, v := range report.Metrics.(map[string]interface{}) {
		fmt.Printf("    %s: %v\n", k, v)
	}
	fmt.Printf("  优化建议:\n")
	for i, rec := range report.Recommendations {
		fmt.Printf("    %d. %s\n", i+1, rec)
	}

	// 4. 保存 JSON 输出
	fmt.Println("\n========================================")
	fmt.Println("💾 保存 JSON 输出")
	fmt.Println("========================================")

	output := map[string]interface{}{
		"report":      report,
		"metrics":     metrics,
		"anomalies":   anomalies,
		"adjustments": adjustments,
		"allocations": allocations,
	}
	b, _ := json.MarshalIndent(output, "", "  ")
	os.WriteFile("/tmp/ad-agent-output.json", b, 0644)
	fmt.Println("  ✅ 已保存到 /tmp/ad-agent-output.json")
}
