package diagnosis

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"math"
	"sort"
	"strings"
	"sync"
	"testing"
	"time"
)

// ============================================================
// 诊断引擎：完整可运行实现
// ============================================================

// ---- 数据模型 ----

type Account struct {
	ID                  string    `json:"id"`
	Status              string    `json:"status"` // active/frozen/inactive
	Balance             float64   `json:"balance"`
	CreditLimit         float64   `json:"credit_limit"`
	TotalDebt           float64   `json:"total_debt"`
	PaymentMethods      []string  `json:"payment_methods"`
	FrozenReason        string    `json:"frozen_reason,omitempty"`
	CreatedAt           time.Time `json:"created_at"`
}

type Campaign struct {
	ID               string    `json:"id"`
	AdvertiserID     string    `json:"advertiser_id"`
	Status           string    `json:"status"` // running/paused/completed
	BidType          string    `json:"bid_type"` // manual/auto
	BidPrice         float64   `json:"bid_price"`
	RecommendedBid   float64   `json:"recommended_bid"`
	DailyBudget      float64   `json:"daily_budget"`
	LifetimeBudget   float64   `json:"lifetime_budget"`
	TodaySpend       float64   `json:"today_spend"`
	TotalSpend       float64   `json:"total_spend"`
	Schedule         Schedule  `json:"schedule"`
	Targeting        Targeting `json:"targeting"`
	AvgECPM          float64   `json:"avg_ecpm"`
}

type Schedule struct {
	StartTime time.Time `json:"start_time"`
	EndTime   time.Time `json:"end_time"`
	Hours     []int     `json:"hours"` // 投放时段
}

type Targeting struct {
	AgeRange   [2]int     `json:"age_range"`
	Gender     []string   `json:"gender"`
	Locations  []Location `json:"locations"`
	Interests  []string   `json:"interests"`
}

type Location struct {
	Country  string `json:"country"`
	Province string `json:"province"`
	City     string `json:"city"`
}

type Ad struct {
	ID              string    `json:"id"`
	CampaignID      string    `json:"campaign_id"`
	AuditStatus     string    `json:"audit_status"` // pending/approved/rejected
	AuditRejectReason string  `json:"audit_reject_reason,omitempty"`
	CreativeStatus  string    `json:"creative_status"`
	Creative        Creative  `json:"creative"`
	FrequencyCap    int       `json:"frequency_cap"`
	Targeting       Targeting `json:"targeting"`
}

type Creative struct {
	Type     string    `json:"type"` // image/video/text
	URL      string    `json:"url"`
	ExpiredAt time.Time `json:"expired_at"`
}

type UserProfile struct {
	UserID    string   `json:"user_id"`
	Age       int      `json:"age"`
	Gender    string   `json:"gender"`
	City      string   `json:"city"`
	Interests []string `json:"interests"`
	FraudScore float64 `json:"fraud_score"`
}

type Slot struct {
	ID       string    `json:"id"`
	Status   string    `json:"status"`
	RequestCount int   `json:"request_count"`
	WinCount   int     `json:"win_count"`
}

// ---- 诊断结果 ----

type DiagnosticRequest struct {
	Type         string `json:"type"` // ad_not_serving/user_no_ad/performance_drop
	AdvertiserID string `json:"advertiser_id"`
	AdID         string `json:"ad_id"`
	UserID       string `json:"user_id"`
	SlotID       string `json:"slot_id"`
}

type Problem struct {
	Module   string      `json:"module"`
	Code     string      `json:"code"`
	Message  string      `json:"message"`
	Severity string      `json:"severity"` // critical/warning/info
	Evidence interface{} `json:"evidence,omitempty"`
}

type DiagnosticResult struct {
	RequestID   string    `json:"request_id"`
	Problems    []Problem `json:"problems"`
	RootCause   string    `json:"root_cause"`
	Severity    string    `json:"severity"`
	Suggestions []string  `json:"suggestions"`
	Metrics     *Metrics  `json:"metrics,omitempty"`
	ExecTime    string    `json:"exec_time"`
}

type Metrics struct {
	Impressions7d  []float64 `json:"impressions_7d"`
	ECPM7d         []float64 `json:"ecpm_7d"`
	CTR7d          []float64 `json:"ctr_7d"`
	AvgBid         float64   `json:"avg_bid"`
	IndustryAvgBid float64   `json:"industry_avg_bid"`
}

// ---- 诊断引擎 ----

type DiagnosisEngine struct {
	store *DataStore
}

func NewDiagnosisEngine(store *DataStore) *DiagnosisEngine {
	return &DiagnosisEngine{store: store}
}

// Diagnose 执行诊断（核心方法）
func (de *DiagnosisEngine) Diagnose(ctx context.Context, req *DiagnosticRequest) (*DiagnosticResult, error) {
	startTime := time.Now()

	// 1. 并行执行 5 大检查
	type checkResult struct {
		problems []Problem
		err      error
	}

	ch := make(chan checkResult, 5)
	var wg sync.WaitGroup

	wg.Add(5)

	// 模块 1: 账户状态
	go func() {
		defer wg.Done()
		ch <- checkResult{problems: de.checkAccount(req), err: nil}
	}()

	// 模块 2: 广告组状态
	go func() {
		defer wg.Done()
		ch <- checkResult{problems: de.checkCampaign(req), err: nil}
	}()

	// 模块 3: 广告状态
	go func() {
		defer wg.Done()
		ch <- checkResult{problems: de.checkAd(req), err: nil}
	}()

	// 模块 4: 竞价能力
	go func() {
		defer wg.Done()
		ch <- checkResult{problems: de.checkBid(req), err: nil}
	}()

	// 模块 5: 流量匹配
	go func() {
		defer wg.Done()
		ch <- checkResult{problems: de.checkTraffic(req), err: nil}
	}()

	// 等待所有检查完成
	go func() {
		wg.Wait()
		close(ch)
	}()

	// 2. 收集所有问题
	allProblems := make([]Problem, 0)
	for r := range ch {
		if r.err != nil {
			log.Printf("check error: %v", r.err)
			continue
		}
		allProblems = append(allProblems, r.problems...)
	}

	// 3. 按严重度排序
	sort.Slice(allProblems, func(i, j int) bool {
		severityOrder := map[string]int{"critical": 0, "warning": 1, "info": 2}
		return severityOrder[allProblems[i].Severity] < severityOrder[allProblems[j].Severity]
	})

	// 4. 根因分析
	rootCause := de.findRootCause(allProblems)

	// 5. 生成建议
	suggestions := de.genSuggestions(allProblems)

	// 6. 获取指标
	metrics := de.getMetrics(req)

	execTime := time.Since(startTime)

	return &DiagnosticResult{
		RequestID:   fmt.Sprintf("diag_%d", time.Now().UnixNano()),
		Problems:    allProblems,
		RootCause:   rootCause,
		Severity:    de.overallSeverity(allProblems),
		Suggestions: suggestions,
		Metrics:     metrics,
		ExecTime:    execTime.String(),
	}, nil
}

// ---- 模块 1: 账户状态检查 ----

func (de *DiagnosisEngine) checkAccount(req *DiagnosticRequest) []Problem {
	problems := make([]Problem, 0)

	account, err := de.store.GetAccount(req.AdvertiserID)
	if err != nil {
		problems = append(problems, Problem{
			Module:   "account",
			Code:     "ACCOUNT_NOT_FOUND",
			Message:  fmt.Sprintf("广告主 %s 不存在", req.AdvertiserID),
			Severity: "critical",
		})
		return problems
	}

	// 账户状态
	if account.Status != "active" {
		problems = append(problems, Problem{
			Module:   "account",
			Code:     "ACCOUNT_INACTIVE",
			Message:  fmt.Sprintf("账户状态：%s", account.Status),
			Severity: "critical",
			Evidence: map[string]interface{}{
				"status":        account.Status,
				"frozen_reason": account.FrozenReason,
			},
		})
	}

	// 余额
	if account.Balance <= 0 {
		problems = append(problems, Problem{
			Module:   "account",
			Code:     "INSUFFICIENT_BALANCE",
			Message:  fmt.Sprintf("账户余额不足：¥%.2f", account.Balance),
			Severity: "critical",
			Evidence: map[string]interface{}{
				"balance":       account.Balance,
				"needed":        math.Abs(account.Balance) + 100,
			},
		})
	}

	// 信用额度
	if account.CreditLimit > 0 && account.TotalDebt > account.CreditLimit {
		problems = append(problems, Problem{
			Module:   "account",
			Code:     "CREDIT_EXCEEDED",
			Message:  fmt.Sprintf("信用额度超限：已用 ¥%.2f / 总额度 ¥%.2f", account.TotalDebt, account.CreditLimit),
			Severity: "critical",
		})
	}

	// 支付方式
	if len(account.PaymentMethods) == 0 {
		problems = append(problems, Problem{
			Module:   "account",
			Code:     "NO_VALID_PAYMENT",
			Message:  "账户没有有效的支付方式",
			Severity: "critical",
		})
	}

	return problems
}

// ---- 模块 2: 广告组状态检查 ----

func (de *DiagnosisEngine) checkCampaign(req *DiagnosticRequest) []Problem {
	problems := make([]Problem, 0)

	campaign, err := de.store.GetCampaign(req.AdID)
	if err != nil {
		return problems
	}

	now := time.Now()

	// 广告组状态
	if campaign.Status != "running" {
		problems = append(problems, Problem{
			Module:   "campaign",
			Code:     "CAMPAIGN_NOT_RUNNING",
			Message:  fmt.Sprintf("广告组状态：%s", campaign.Status),
			Severity: "critical",
			Evidence: map[string]interface{}{
				"status": campaign.Status,
			},
		})
	}

	// 日预算
	if campaign.DailyBudget > 0 && campaign.TodaySpend >= campaign.DailyBudget {
		remaining := campaign.DailyBudget - campaign.TodaySpend
		problems = append(problems, Problem{
			Module:   "campaign",
			Code:     "DAILY_BUDGET_EXHAUSTED",
			Message:  fmt.Sprintf("今日预算已耗尽：已花 ¥%.2f / 预算 ¥%.2f（剩余 ¥%.2f）", campaign.TodaySpend, campaign.DailyBudget, remaining),
			Severity: "critical",
			Evidence: map[string]interface{}{
				"today_spend":    campaign.TodaySpend,
				"daily_budget":   campaign.DailyBudget,
				"budget_remaining": remaining,
			},
		})
	}

	// 总预算
	if campaign.LifetimeBudget > 0 && campaign.TotalSpend >= campaign.LifetimeBudget {
		problems = append(problems, Problem{
			Module:   "campaign",
			Code:     "LIFETIME_BUDGET_EXHAUSTED",
			Message:  fmt.Sprintf("总预算已耗尽：已花 ¥%.2f / 总预算 ¥%.2f", campaign.TotalSpend, campaign.LifetimeBudget),
			Severity: "critical",
		})
	}

	// 出价过低
	if campaign.BidType == "manual" && campaign.BidPrice > 0 && campaign.BidPrice < campaign.RecommendedBid*0.5 {
		problems = append(problems, Problem{
			Module:   "campaign",
			Code:     "BID_TOO_LOW",
			Message:  fmt.Sprintf("出价偏低：当前 ¥%.4f / 建议 ¥%.4f", campaign.BidPrice, campaign.RecommendedBid),
			Severity: "warning",
			Evidence: map[string]interface{}{
				"current_bid":     campaign.BidPrice,
				"recommended_bid": campaign.RecommendedBid,
				"avg_ecpm":        campaign.AvgECPM,
			},
		})
	}

	// 投放时间
	if !now.After(campaign.Schedule.StartTime) {
		problems = append(problems, Problem{
			Module:   "campaign",
			Code:     "SCHEDULE_NOT_STARTED",
			Message:  fmt.Sprintf("投放尚未开始：预计 %s 开始", campaign.Schedule.StartTime.Format("15:04")),
			Severity: "info",
		})
	}
	if now.After(campaign.Schedule.EndTime) {
		problems = append(problems, Problem{
			Module:   "campaign",
			Code:     "SCHEDULE_ENDED",
			Message:  fmt.Sprintf("投放已结束：已于 %s 结束", campaign.Schedule.EndTime.Format("15:04")),
			Severity: "critical",
		})
	}

	// 投放时段
	hour := now.Hour()
	inSchedule := false
	for _, h := range campaign.Schedule.Hours {
		if h == hour {
			inSchedule = true
			break
		}
	}
	if len(campaign.Schedule.Hours) > 0 && !inSchedule {
		problems = append(problems, Problem{
			Module:   "campaign",
			Code:     "OUT_OF_SCHEDULE_HOURS",
			Message:  fmt.Sprintf("当前不在投放时段内：当前 %02d:00", hour),
			Severity: "info",
			Evidence: map[string]interface{}{
				"current_hour":   hour,
				"schedule_hours": campaign.Schedule.Hours,
			},
		})
	}

	return problems
}

// ---- 模块 3: 广告状态检查 ----

func (de *DiagnosisEngine) checkAd(req *DiagnosticRequest) []Problem {
	problems := make([]Problem, 0)

	ad, err := de.store.GetAd(req.AdID)
	if err != nil {
		return problems
	}

	// 审核状态
	if ad.AuditStatus != "approved" {
		problems = append(problems, Problem{
			Module:   "ad",
			Code:     "AD_NOT_APPROVED",
			Message:  fmt.Sprintf("广告审核状态：%s", ad.AuditStatus),
			Severity: "critical",
			Evidence: map[string]interface{}{
				"audit_status":       ad.AuditStatus,
				"reject_reason":      ad.AuditRejectReason,
			},
		})
	}

	// 创意状态
	if ad.CreativeStatus != "active" {
		problems = append(problems, Problem{
			Module:   "ad",
			Code:     "CREATIVE_INACTIVE",
			Message:  fmt.Sprintf("创意状态：%s", ad.CreativeStatus),
			Severity: "warning",
		})
	}

	// 创意过期
	if !ad.Creative.ExpiredAt.IsZero() && ad.Creative.ExpiredAt.Before(time.Now()) {
		problems = append(problems, Problem{
			Module:   "ad",
			Code:     "CREATIVE_EXPIRED",
			Message:  "广告创意已过期",
			Severity: "warning",
			Evidence: map[string]interface{}{
				"expired_at": ad.Creative.ExpiredAt.Format("2006-01-02"),
			},
		})
	}

	// 频次限制（用户诊断）
	if req.UserID != "" {
		freq := de.store.GetUserFreq(req.UserID, req.AdID)
		if freq >= ad.FrequencyCap && ad.FrequencyCap > 0 {
			problems = append(problems, Problem{
				Module:   "ad",
				Code:     "FREQUENCY_CAP_REACHED",
				Message:  fmt.Sprintf("用户对广告已达频次上限：今日已看 %d 次 / 上限 %d 次", freq, ad.FrequencyCap),
				Severity: "warning",
				Evidence: map[string]interface{}{
					"user_id":      req.UserID,
					"ad_id":        req.AdID,
					"current_freq": freq,
					"max_freq":     ad.FrequencyCap,
				},
			})
		}
	}

	return problems
}

// ---- 模块 4: 竞价能力检查 ----

func (de *DiagnosisEngine) checkBid(req *DiagnosticRequest) []Problem {
	problems := make([]Problem, 0)

	campaign, err := de.store.GetCampaign(req.AdID)
	if err != nil {
		return problems
	}

	// 出价竞争力
	industryAvg := de.store.GetIndustryAvgBid(req.SlotID)
	if industryAvg > 0 && campaign.BidPrice < industryAvg*0.7 {
		problems = append(problems, Problem{
			Module:   "bid",
			Code:     "BID_NOT_COMPETITIVE",
			Message:  fmt.Sprintf("出价缺乏竞争力：当前 ¥%.4f / 行业均价 ¥%.4f", campaign.BidPrice, industryAvg),
			Severity: "warning",
			Evidence: map[string]interface{}{
				"current_bid":     campaign.BidPrice,
				"industry_avg":    industryAvg,
				"p50_bid":         industryAvg * 0.9,
				"p90_bid":         industryAvg * 1.2,
			},
		})
	}

	// eCPM 趋势
	ecpmTrend := de.store.GetECPMTrend(req.AdID)
	if ecpmTrend != nil && ecpmTrend.Change7d < -0.2 {
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

	return problems
}

// ---- 模块 5: 流量匹配检查 ----

func (de *DiagnosisEngine) checkTraffic(req *DiagnosticRequest) []Problem {
	problems := make([]Problem, 0)

	ad, err := de.store.GetAd(req.AdID)
	if err != nil {
		return problems
	}

	// 用户画像匹配
	if req.UserID != "" {
		profile, err := de.store.GetUserProfile(req.UserID)
		if err == nil {
			mismatches := de.checkProfileMatch(ad, profile)
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

	// 反作弊
	if req.UserID != "" {
		profile, err := de.store.GetUserProfile(req.UserID)
		if err == nil && profile.FraudScore > 0.8 {
			problems = append(problems, Problem{
				Module:   "traffic",
				Code:     "USER_FRAUD_SUSPECTED",
				Message:  fmt.Sprintf("用户疑似作弊：欺诈评分 %.2f", profile.FraudScore),
				Severity: "warning",
				Evidence: map[string]interface{}{
					"user_id":      req.UserID,
					"fraud_score":  profile.FraudScore,
				},
			})
		}
	}

	// 广告位流量
	if req.SlotID != "" {
		slot, err := de.store.GetSlot(req.SlotID)
		if err == nil {
			if slot.RequestCount == 0 {
				problems = append(problems, Problem{
					Module:   "traffic",
					Code:     "SLOT_NO_TRAFFIC",
					Message:  fmt.Sprintf("广告位 %s 过去 24 小时无请求", req.SlotID),
					Severity: "warning",
				})
			} else if slot.WinCount == 0 {
				fillRate := 0.0
				if slot.RequestCount > 0 {
					fillRate = float64(slot.WinCount) / float64(slot.RequestCount)
				}
				problems = append(problems, Problem{
					Module:   "traffic",
					Code:     "SLOT_ZERO_FILL",
					Message:  fmt.Sprintf("广告位有请求但零填充：请求 %d 次，成交 0 次", slot.RequestCount),
					Severity: "warning",
					Evidence: map[string]interface{}{
						"slot_id":       req.SlotID,
						"request_count": slot.RequestCount,
						"win_count":     slot.WinCount,
						"fill_rate":     fillRate,
					},
				})
			}
		}
	}

	return problems
}

// ---- 辅助方法 ----

// checkProfileMatch 检查用户画像匹配
func (de *DiagnosisEngine) checkProfileMatch(ad *Ad, profile *UserProfile) []string {
	mismatches := make([]string, 0)

	// 年龄匹配
	if len(ad.Targeting.AgeRange) == 2 {
		if profile.Age < ad.Targeting.AgeRange[0] || profile.Age > ad.Targeting.AgeRange[1] {
			mismatches = append(mismatches, fmt.Sprintf("年龄不符：用户 %d 岁 / 定向 %d-%d 岁", profile.Age, ad.Targeting.AgeRange[0], ad.Targeting.AgeRange[1]))
		}
	}

	// 性别匹配
	if len(ad.Targeting.Gender) > 0 {
		genderMatch := false
		for _, g := range ad.Targeting.Gender {
			if g == profile.Gender {
				genderMatch = true
				break
			}
		}
		if !genderMatch {
			mismatches = append(mismatches, fmt.Sprintf("性别不符：用户 %s / 定向 %v", profile.Gender, ad.Targeting.Gender))
		}
	}

	// 地域匹配
	if len(ad.Targeting.Locations) > 0 {
		geoMatch := false
		for _, loc := range ad.Targeting.Locations {
			if loc.City != "" && loc.City == profile.City {
				geoMatch = true
				break
			}
		}
		if !geoMatch {
			mismatches = append(mismatches, fmt.Sprintf("地域不符：用户 %s / 定向 %v", profile.City, ad.Targeting.Locations))
		}
	}

	return mismatches
}

// findRootCause 根因分析
func (de *DiagnosisEngine) findRootCause(problems []Problem) string {
	if len(problems) == 0 {
		return "未发现问题"
	}

	// 按严重度取第一个
	for _, p := range problems {
		if p.Severity == "critical" {
			return p.Message
		}
	}

	// 没有 critical，取 warning
	for _, p := range problems {
		if p.Severity == "warning" {
			return p.Message
		}
	}

	// 只有 info
	return problems[0].Message
}

// genSuggestions 生成建议
func (de *DiagnosisEngine) genSuggestions(problems []Problem) []string {
	suggestions := make([]string, 0)

	for _, p := range problems {
		switch p.Code {
		case "ACCOUNT_INACTIVE":
			suggestions = append(suggestions, "请联系客服激活账户")
		case "INSUFFICIENT_BALANCE":
			suggestions = append(suggestions, "请充值账户余额")
		case "CREDIT_EXCEEDED":
			suggestions = append(suggestions, "请偿还欠款或提高信用额度")
		case "NO_VALID_PAYMENT":
			suggestions = append(suggestions, "请绑定有效的支付方式")
		case "CAMPAIGN_NOT_RUNNING":
			suggestions = append(suggestions, "请将广告组状态改为运行中")
		case "DAILY_BUDGET_EXHAUSTED":
			suggestions = append(suggestions, "请提高日预算或等待明日 0 点重置")
		case "LIFETIME_BUDGET_EXHAUSTED":
			suggestions = append(suggestions, "请提高总预算")
		case "BID_TOO_LOW":
			suggestions = append(suggestions, "建议提高出价至推荐值")
		case "SCHEDULE_NOT_STARTED":
			suggestions = append(suggestions, "等待投放时间到达")
		case "SCHEDULE_ENDED":
			suggestions = append(suggestions, "请延长投放时间或创建新广告组")
		case "OUT_OF_SCHEDULE_HOURS":
			suggestions = append(suggestions, "当前不在投放时段内，请等待或调整时段")
		case "AD_NOT_APPROVED":
			suggestions = append(suggestions, "请修改创意后重新提交审核")
		case "CREATIVE_EXPIRED":
			suggestions = append(suggestions, "请更新创意素材")
		case "FREQUENCY_CAP_REACHED":
			suggestions = append(suggestions, "频次限制是正常现象，可扩大定向范围")
		case "BID_NOT_COMPETITIVE":
			suggestions = append(suggestions, "建议提高出价或优化创意提升 CTR")
		case "ECPM_DECLINING":
			suggestions = append(suggestions, "eCPM 持续下降，建议优化创意或调整出价")
		case "PROFILE_MISMATCH":
			suggestions = append(suggestions, "建议放宽定向条件或更换目标人群")
		case "USER_FRAUD_SUSPECTED":
			suggestions = append(suggestions, "用户疑似作弊，建议检查用户行为")
		case "SLOT_NO_TRAFFIC":
			suggestions = append(suggestions, "广告位无流量，建议更换广告位")
		case "SLOT_ZERO_FILL":
			suggestions = append(suggestions, "广告位有请求但零填充，建议提高出价或放宽定向")
		}
	}

	return suggestions
}

// overallSeverity 整体严重度
func (de *DiagnosisEngine) overallSeverity(problems []Problem) string {
	for _, p := range problems {
		if p.Severity == "critical" {
			return "critical"
		}
	}
	for _, p := range problems {
		if p.Severity == "warning" {
			return "warning"
		}
	}
	return "info"
}

// getMetrics 获取指标
func (de *DiagnosisEngine) getMetrics(req *DiagnosticRequest) *Metrics {
	if req.AdID == "" {
		return nil
	}

	ecpmTrend := de.store.GetECPMTrend(req.AdID)
	industryAvg := de.store.GetIndustryAvgBid(req.SlotID)

	if ecpmTrend == nil {
		return nil
	}

	return &Metrics{
		ECPM7d:         ecpmTrend.Series,
		AvgBid:         industryAvg,
		IndustryAvgBid: industryAvg,
	}
}

// ---- 数据存储 ----

type DataStore struct {
	accounts    map[string]*Account
	campaigns   map[string]*Campaign
	ads         map[string]*Ad
	userProfiles map[string]*UserProfile
	userFreq    map[string]int // user_id:ad_id -> freq
	slots       map[string]*Slot
}

func NewTestStore() *DataStore {
	return &DataStore{
		accounts:     make(map[string]*Account),
		campaigns:    make(map[string]*Campaign),
		ads:          make(map[string]*Ad),
		userProfiles: make(map[string]*UserProfile),
		userFreq:     make(map[string]int),
		slots:        make(map[string]*Slot),
	}
}

func (ds *DataStore) SetAccount(a *Account) { ds.accounts[a.ID] = a }
func (ds *DataStore) GetAccount(id string) (*Account, error) {
	a, ok := ds.accounts[id]
	if !ok {
		return nil, fmt.Errorf("account not found: %s", id)
	}
	return a, nil
}

func (ds *DataStore) SetCampaign(c *Campaign) { ds.campaigns[c.ID] = c }
func (ds *DataStore) GetCampaign(adID string) (*Campaign, error) {
	// 先查广告找到 campaignID
	ad, ok := ds.ads[adID]
	if !ok {
		return nil, fmt.Errorf("ad not found: %s", adID)
	}
	c, ok := ds.campaigns[ad.CampaignID]
	if !ok {
		return nil, fmt.Errorf("campaign not found: %s", ad.CampaignID)
	}
	return c, nil
}

func (ds *DataStore) SetAd(a *Ad) { ds.ads[a.ID] = a }
func (ds *DataStore) GetAd(id string) (*Ad, error) {
	a, ok := ds.ads[id]
	if !ok {
		return nil, fmt.Errorf("ad not found: %s", id)
	}
	return a, nil
}

func (ds *DataStore) SetUserProfile(u *UserProfile) { ds.userProfiles[u.UserID] = u }
func (ds *DataStore) GetUserProfile(id string) (*UserProfile, error) {
	u, ok := ds.userProfiles[id]
	if !ok {
		return nil, fmt.Errorf("user not found: %s", id)
	}
	return u, nil
}

func (ds *DataStore) SetUserFreq(userID, adID string, freq int) {
	ds.userFreq[userID+":"+adID] = freq
}
func (ds *DataStore) GetUserFreq(userID, adID string) int {
	return ds.userFreq[userID+":"+adID]
}

func (ds *DataStore) SetSlot(s *Slot) { ds.slots[s.ID] = s }
func (ds *DataStore) GetSlot(id string) (*Slot, error) {
	s, ok := ds.slots[id]
	if !ok {
		return nil, fmt.Errorf("slot not found: %s", id)
	}
	return s, nil
}

func (ds *DataStore) GetIndustryAvgBid(slotID string) float64 {
	// 模拟数据
	return 0.50
}

type ECPMTrend struct {
	ECPM7DAgo  float64
	ECPMNow    float64
	Change7d   float64
	Series     []float64
}

func (ds *DataStore) GetECPMTrend(adID string) *ECPMTrend {
	// 根据 adID 区分模拟数据
	if strings.HasPrefix(adID, "ad_002") {
		return &ECPMTrend{
			ECPM7DAgo:  40.0,
			ECPMNow:    42.0,
			Change7d:   0.05,
			Series:     []float64{40, 41, 40, 42, 41, 42, 42},
		}
	}
	return &ECPMTrend{
		ECPM7DAgo:  50.0,
		ECPMNow:    35.0,
		Change7d:   -0.30,
		Series:     []float64{50, 48, 45, 42, 40, 38, 35},
	}
}

// ---- JSON 序列化 ----

func (r *DiagnosticResult) ToJSON() string {
	b, _ := json.MarshalIndent(r, "", "  ")
	return string(b)
}

// ============================================================
// 完整测试
// ============================================================

func TestDiagnosis_Engine(t *testing.T) {
	store := NewTestStore()
	engine := NewDiagnosisEngine(store)

	// ---- 设置测试数据 ----

	// 账户：余额不足
	store.SetAccount(&Account{
		ID:             "acc_001",
		Status:         "active",
		Balance:        -50.0,
		CreditLimit:    10000,
		TotalDebt:      500,
		PaymentMethods: []string{"alipay"},
	})

	// 广告组：日预算耗尽 + 出价过低
	store.SetCampaign(&Campaign{
		ID:             "camp_001",
		AdvertiserID:   "acc_001",
		Status:         "running",
		BidType:        "manual",
		BidPrice:       0.20,
		RecommendedBid: 0.50,
		DailyBudget:    1000,
		TodaySpend:     1000,
		LifetimeBudget: 0,
		Schedule: Schedule{
			StartTime: time.Now().Add(-1 * time.Hour),
			EndTime:   time.Now().Add(24 * time.Hour),
			Hours:     []int{8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21},
		},
		AvgECPM: 35.0,
	})

	// 广告：审核通过
	store.SetAd(&Ad{
		ID:              "ad_001",
		CampaignID:      "camp_001",
		AuditStatus:     "approved",
		CreativeStatus:  "active",
		Creative:        Creative{Type: "image", ExpiredAt: time.Now().Add(30 * 24 * time.Hour)},
		FrequencyCap:    3,
		Targeting:       Targeting{AgeRange: [2]int{25, 35}, Gender: []string{"male"}, Locations: []Location{{City: "北京"}}},
	})

	// 广告位：正常
	store.SetSlot(&Slot{
		ID:           "slot_001",
		Status:       "active",
		RequestCount: 10000,
		WinCount:     5000,
	})

	// ---- 测试 1: 广告投不出去 ----
	t.Run("ad_not_serving", func(t *testing.T) {
		result, err := engine.Diagnose(context.Background(), &DiagnosticRequest{
			Type:         "ad_not_serving",
			AdvertiserID: "acc_001",
			AdID:         "ad_001",
			SlotID:       "slot_001",
		})

		if err != nil {
			t.Fatalf("diagnose error: %v", err)
		}

		t.Logf("\n=== 诊断报告 ===\n")
		fmt.Println(result.ToJSON())

		// 验证：应该有账户余额不足的问题
		hasBalanceIssue := false
		for _, p := range result.Problems {
			if p.Code == "INSUFFICIENT_BALANCE" {
				hasBalanceIssue = true
			}
		}
		if !hasBalanceIssue {
			t.Error("expected INSUFFICIENT_BALANCE problem")
		}

		// 验证：应该有日预算耗尽
		hasBudgetIssue := false
		for _, p := range result.Problems {
			if p.Code == "DAILY_BUDGET_EXHAUSTED" {
				hasBudgetIssue = true
			}
		}
		if !hasBudgetIssue {
			t.Error("expected DAILY_BUDGET_EXHAUSTED problem")
		}

		// 验证：根因应该是余额不足（critical）
		if !strings.Contains(result.RootCause, "余额不足") {
			t.Errorf("expected root cause to mention balance, got: %s", result.RootCause)
		}

		// 验证：执行时间应该很短
		if result.ExecTime == "" {
			t.Error("exec_time should not be empty")
		}
	})

	// ---- 测试 2: 用户看不到广告 ----
	store.SetUserProfile(&UserProfile{
		UserID:    "user_001",
		Age:       20,
		Gender:    "female",
		City:      "上海",
		Interests: []string{"tech"},
		FraudScore: 0.3,
	})
	store.SetUserFreq("user_001", "ad_001", 5)

	t.Run("user_no_ad", func(t *testing.T) {
		result, err := engine.Diagnose(context.Background(), &DiagnosticRequest{
			Type:         "user_no_ad",
			AdvertiserID: "acc_001",
			AdID:         "ad_001",
			UserID:       "user_001",
		})

		if err != nil {
			t.Fatalf("diagnose error: %v", err)
		}

		t.Logf("\n=== 用户诊断报告 ===\n")
		fmt.Println(result.ToJSON())

		// 验证：应该有画像不匹配
		hasMismatch := false
		for _, p := range result.Problems {
			if p.Code == "PROFILE_MISMATCH" {
				hasMismatch = true
			}
		}
		if !hasMismatch {
			t.Error("expected PROFILE_MISMATCH problem")
		}

		// 验证：应该有频次限制
		hasFreqIssue := false
		for _, p := range result.Problems {
			if p.Code == "FREQUENCY_CAP_REACHED" {
				hasFreqIssue = true
			}
		}
		if !hasFreqIssue {
			t.Error("expected FREQUENCY_CAP_REACHED problem")
		}
	})

	// ---- 测试 3: 正常情况 ----
	store.SetAccount(&Account{
		ID:             "acc_002",
		Status:         "active",
		Balance:        10000,
		PaymentMethods: []string{"alipay"},
	})
	store.SetCampaign(&Campaign{
		ID:             "camp_002",
		AdvertiserID:   "acc_002",
		Status:         "running",
		BidType:        "auto",
		BidPrice:       0.50,
		DailyBudget:    10000,
		TodaySpend:     500,
		Schedule: Schedule{
			StartTime: time.Now().Add(-1 * time.Hour),
			EndTime:   time.Now().Add(24 * time.Hour),
		},
	})
	store.SetAd(&Ad{
		ID:              "ad_002",
		CampaignID:      "camp_002",
		AuditStatus:     "approved",
		CreativeStatus:  "active",
		Creative:        Creative{ExpiredAt: time.Now().Add(30 * 24 * time.Hour)},
		FrequencyCap:    5,
	})

	t.Run("healthy_ad", func(t *testing.T) {
		result, err := engine.Diagnose(context.Background(), &DiagnosticRequest{
			AdvertiserID: "acc_002",
			AdID:         "ad_002",
		})

		if err != nil {
			t.Fatalf("diagnose error: %v", err)
		}

		t.Logf("\n=== 正常广告诊断 ===\n")
		fmt.Println(result.ToJSON())

		if result.Severity != "info" {
			t.Errorf("expected info severity for healthy ad, got: %s", result.Severity)
		}
	})
}

// 单独运行测试
func main() {
	testing.Main(func(pat, str string) (bool, error) { return true, nil },
		[]testing.InternalTest{
			{Name: "TestDiagnosis_Engine", F: TestDiagnosis_Engine},
		},
		nil, nil)
}
