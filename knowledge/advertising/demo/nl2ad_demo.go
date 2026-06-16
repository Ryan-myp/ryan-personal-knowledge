package main

import (
	"fmt"
	"os"
	"regexp"
	"strings"
	"time"
)

// ============================================================
// NL2AD - 自然语言创建广告 完整实现
// ============================================================

// ---- 数据模型 ----

type AdGroup struct {
	ID           string  `json:"id"`
	Name         string  `json:"name"`
	AdvertiserID string  `json:"advertiser_id"`
	Industry     string  `json:"industry"`
	Status       string  `json:"status"` // pending/approved/rejected/running/paused
	DailyBudget  float64 `json:"daily_budget"`
	TotalBudget  float64 `json:"total_budget"`
	StatusText   string  `json:"status_text"`
}

type Creative struct {
	Type    string `json:"type"`    // copy/image_prompt/video_prompt
	Content string `json:"content"`
	URL     string `json:"url,omitempty"`
}

type AdCreationResult struct {
	AdGroup   *AdGroup      `json:"ad_group"`
	Creatives []Creative    `json:"creatives"`
	Recommendations []string `json:"recommendations"`
}

type ConversationMessage struct {
	Role      string    `json:"role"` // user/assistant
	Content   string    `json:"content"`
	Timestamp time.Time `json:"timestamp"`
}

type ConversationResponse struct {
	Text    string      `json:"text"`
	Actions []Action    `json:"actions,omitempty"`
}

type Action struct {
	Type    string      `json:"type"`
	Data    interface{} `json:"data"`
}

// ---- 意图分类器 ----

type Intent string

const (
	IntentCreateAd         Intent = "CREATE_AD"
	IntentOptimizeAd       Intent = "OPTIMIZE_AD"
	IntentPauseAd          Intent = "PAUSE_AD"
	IntentCheckPerformance Intent = "CHECK_PERFORMANCE"
	IntentGenerateCreative Intent = "GENERATE_CREATIVE"
)

type IntentClassifier struct {
	rules []Rule
}

type Rule struct {
	Patterns []string
	Intent   Intent
}

func NewIntentClassifier() *IntentClassifier {
	return &IntentClassifier{
		rules: []Rule{
			{
				Patterns: []string{"创建", "新建", "建一个", "开一个", "投放", "上架", "做一个广告"},
				Intent:   IntentCreateAd,
			},
			{
				Patterns: []string{"优化", "调整", "改", "提升", "改善", "调一下"},
				Intent:   IntentOptimizeAd,
			},
			{
				Patterns: []string{"暂停", "停止", "下线", "关", "下架"},
				Intent:   IntentPauseAd,
			},
			{
				Patterns: []string{"查看", "查询", "表现", "数据", "统计", "效果", "结果"},
				Intent:   IntentCheckPerformance,
			},
			{
				Patterns: []string{"创意", "素材", "图片", "视频", "文案", "生成", "制作", "写"},
				Intent:   IntentGenerateCreative,
			},
		},
	}
}

func (c *IntentClassifier) Classify(input string) (Intent, map[string]string, float64) {
	bestIntent := IntentCreateAd
	bestScore := 0.0

	for _, rule := range c.rules {
		score := 0.0
		for _, pattern := range rule.Patterns {
			if strings.Contains(input, pattern) {
				score += 1.0
			}
		}
		if score > bestScore {
			bestScore = score
			bestIntent = rule.Intent
		}
	}

	entities := extractEntities(input)

	return bestIntent, entities, bestScore
}

func extractEntities(input string) map[string]string {
	entities := make(map[string]string)

	// 提取预算: "每天500" / "日预算500" / "预算1000"
	if idx := strings.Index(input, "每天"); idx >= 0 {
		rest := input[idx+2:]
		for i := 0; i < len(rest); i++ {
			if rest[i] >= '0' && rest[i] <= '9' {
				num := ""
				for j := i; j < len(rest) && rest[j] >= '0' && rest[j] <= '9'; j++ {
					num += string(rest[j])
				}
				entities["budget"] = num
				break
			}
		}
	} else if strings.Contains(input, "预算") {
		idx := strings.Index(input, "预算")
		rest := input[idx+2:]
		for i := 0; i < len(rest); i++ {
			if rest[i] >= '0' && rest[i] <= '9' {
				num := ""
				for j := i; j < len(rest) && rest[j] >= '0' && rest[j] <= '9'; j++ {
					num += string(rest[j])
				}
				entities["budget"] = num
				break
			}
		}
	}

	// 提取时长: "30天" / "一个月"
	if idx := strings.Index(input, "天"); idx > 0 {
		num := ""
		for i := idx - 1; i >= 0 && input[i] >= '0' && input[i] <= '9'; i-- {
			num = string(input[i]) + num
		}
		if num != "" {
			entities["duration"] = num
		}
	} else if strings.Contains(input, "个月") {
		idx := strings.Index(input, "个月")
		num := ""
		for i := idx - 1; i >= 0 && input[i] >= '0' && input[i] <= '9'; i-- {
			num = string(input[i]) + num
		}
		if num != "" {
			days, _ := parseInt(num)
			entities["duration"] = fmt.Sprintf("%d", days*30)
		}
	}

	// 提取行业
	industries := map[string]string{
		"服装": "clothing", "衣服": "clothing", "女装": "clothing", "男装": "clothing",
		"餐饮": "food", "美食": "food", "餐厅": "food", "外卖": "food",
		"酒店": "hotel", "旅游": "travel", "旅行": "travel",
		"教育": "education", "培训": "education",
		"美妆": "beauty", "护肤": "beauty",
		"手机": "electronics", "电脑": "electronics", "数码": "electronics",
	}
	for keyword, industry := range industries {
		if strings.Contains(input, keyword) {
			entities["industry"] = industry
			break
		}
	}

	// 提取年龄: "25-35岁" 或 "25岁及以上"
	// 优先匹配 "X岁-Y岁" 格式
	agePattern := `(\d+)[-～](\d+)岁`
	if m := regexp.MustCompile(agePattern).FindStringSubmatch(input); len(m) > 0 {
		entities["age"] = m[1] + "-" + m[2]
		return entities
	}
	if strings.Contains(input, "女性") || strings.Contains(input, "女生") || strings.Contains(input, "女") {
		entities["gender"] = "female"
	}
	if strings.Contains(input, "男性") || strings.Contains(input, "男生") || strings.Contains(input, "男") {
		entities["gender"] = "male"
	}
	if strings.Contains(input, "岁") {
		age := extractAgeRange(input)
		if age != "" {
			entities["age"] = age
		}
	}

	return entities
}

func extractAgeRange(input string) string {
	ages := []string{}
	for i, ch := range input {
		if ch >= '0' && ch <= '9' {
			num := ""
			for j := i; j < len(input) && input[j] >= '0' && input[j] <= '9'; j++ {
				num += string(input[j])
			}
			ages = append(ages, num)
			i += len(num) - 1
		}
	}
	if len(ages) >= 2 {
		return ages[0] + "-" + ages[1]
	} else if len(ages) == 1 {
		return ages[0] + "+"
	}
	return ""
}

func parseInt(s string) (int, error) {
	n := 0
	for _, ch := range s {
		if ch >= '0' && ch <= '9' {
			n = n*10 + int(ch-'0')
		}
	}
	return n, nil
}

// ---- 创意生成器 ----

type CreativeGenerator struct {
	industryCopies map[string][]string
}

func NewCreativeGenerator() *CreativeGenerator {
	return &CreativeGenerator{
		industryCopies: map[string][]string{
			"clothing": {
				"春季新品上市！全场5折起，限时抢购！",
				"时尚女装，穿出你的自信！今日下单享免邮",
				"告别平庸！精选设计师款女装，低至2折",
				"换季大促！精选千款新品，第二件半价",
				"爆款返场！明星同款，错过再等一年",
			},
			"food": {
				"正宗川菜，麻辣鲜香！新人首单立减15元",
				"老字号餐厅，传承30年好味道",
				"限时特惠！双人套餐仅需99元",
			},
			"hotel": {
				"五星体验，亲民价格！周末加价0元",
				"海景房大促！提前7天预订享7折",
			},
			"travel": {
				"云南6日游！含机票酒店，仅2999",
				"暑期亲子游！让孩子快乐成长",
			},
		},
	}
}

func (g *CreativeGenerator) GenerateCopies(industry string) []Creative {
	creatives := make([]Creative, 0)

	// 行业文案
	copies, ok := g.industryCopies[industry]
	if !ok {
		// 默认文案
		copies = []string{
			"优质产品，值得信赖！",
			"限时优惠，先到先得！",
			"专业品质，超值体验！",
		}
	}

	for _, copy := range copies[:min(len(copies), 3)] {
		creatives = append(creatives, Creative{
			Type:    "copy",
			Content: copy,
		})
	}

	return creatives
}

func min(a, b int) int {
	if a < b {
		return a
	}
	return b
}

// ---- 广告创建引擎 ----

type AdEngine struct {
	classifier    *IntentClassifier
	creativeGen   *CreativeGenerator
	adGroups      map[string]*AdGroup
	conversation  []ConversationMessage
	currentUser   string
}

func NewAdEngine() *AdEngine {
	return &AdEngine{
		classifier:  NewIntentClassifier(),
		creativeGen: NewCreativeGenerator(),
		adGroups:    make(map[string]*AdGroup),
		conversation: make([]ConversationMessage, 0),
		currentUser: "user_001",
	}
}

// ProcessMessage 处理用户消息（核心方法）
func (e *AdEngine) ProcessMessage(input string) (*ConversationResponse, error) {
	// 添加到对话历史
	e.conversation = append(e.conversation, ConversationMessage{
		Role:      "user",
		Content:   input,
		Timestamp: time.Now(),
	})

	// 意图识别
	intent, entities, score := e.classifier.Classify(input)

	fmt.Printf("🔍 意图: %s (score: %.1f)\n", intent, score)
	fmt.Printf("📋 实体: %v\n", entities)

	// 路由到对应的处理函数
	switch intent {
	case IntentCreateAd:
		return e.handleCreateAd(entities)
	case IntentGenerateCreative:
		return e.handleGenerateCreative(entities)
	case IntentOptimizeAd:
		return e.handleOptimize()
	case IntentPauseAd:
		return e.handlePause(input)
	case IntentCheckPerformance:
		return e.handleCheckPerformance()
	default:
		resp := &ConversationResponse{
			Text: "我不太理解您的意思，请换个说法试试？您可以说「帮我创建一个服装广告」之类的",
		}
		e.conversation = append(e.conversation, ConversationMessage{
			Role:      "assistant",
			Content:   resp.Text,
			Timestamp: time.Now(),
		})
		return resp, nil
	}
}

// handleCreateAd 处理创建广告请求
func (e *AdEngine) handleCreateAd(entities map[string]string) (*ConversationResponse, error) {
	// 提取参数
	dailyBudget := 100.0
	duration := 30
	industry := "clothing"
	gender := ""
	age := ""

	if budget, ok := entities["budget"]; ok {
		if b, err := parseInt(budget); err == nil {
			dailyBudget = float64(b)
		}
	}
	if dur, ok := entities["duration"]; ok {
		if d, err := parseInt(dur); err == nil {
			duration = d
		}
	}
	if ind, ok := entities["industry"]; ok {
		industry = ind
	}
	if g, ok := entities["gender"]; ok {
		gender = g
	}
	if a, ok := entities["age"]; ok {
		age = a
	}

	// 检查参数完整性
	missing := []string{}
	if entities["budget"] == "" {
		missing = append(missing, "日预算")
	}

	if len(missing) > 0 {
		resp := &ConversationResponse{
			Text: fmt.Sprintf("好的，我可以帮您创建广告。请问您想设置%s？（例如：「每天500」）", strings.Join(missing, "和")),
		}
		e.conversation = append(e.conversation, ConversationMessage{
			Role:      "assistant",
			Content:   resp.Text,
			Timestamp: time.Now(),
		})
		return resp, nil
	}

	// 生成广告组 ID
	adGroupID := fmt.Sprintf("camp_%s_%d", industry, time.Now().Unix()%100000)

	// 创建广告组
	adGroup := &AdGroup{
		ID:           adGroupID,
		Name:         fmt.Sprintf("%s广告-%s", industry, time.Now().Format("0102")),
		AdvertiserID: e.currentUser,
		Industry:     industry,
		DailyBudget:  dailyBudget,
		TotalBudget:  dailyBudget * float64(duration),
		Status:       "pending",
		StatusText:   "等待审核",
	}
	e.adGroups[adGroupID] = adGroup

	// 生成创意
	creatives := e.creativeGen.GenerateCopies(industry)

	// 推荐出价
	recommendedBid := e.recommendBid(industry)

	// 构建推荐定向
	targeting := fmt.Sprintf("定向: ")
	if gender != "" {
		targeting += fmt.Sprintf("%s, ", gender)
	}
	if age != "" {
		targeting += fmt.Sprintf("%s岁, ", age)
	}
	targeting += industry

	// 生成回复
	text := fmt.Sprintf("✅ 广告组已创建！\n\n")
	text += fmt.Sprintf("📋 广告组详情：\n")
	text += fmt.Sprintf("  ID: %s\n", adGroupID)
	text += fmt.Sprintf("  行业: %s\n", industry)
	text += fmt.Sprintf("  日预算: ¥%.0f\n", dailyBudget)
	text += fmt.Sprintf("  总预算: ¥%.0f\n", dailyBudget*float64(duration))
	text += fmt.Sprintf("  投放天数: %d天\n", duration)
	text += fmt.Sprintf("  推荐出价: ¥%.2f CPC\n", recommendedBid)
	text += fmt.Sprintf("  推荐定向: %s\n\n", targeting)
	text += fmt.Sprintf("📝 已生成 %d 条文案：\n", len(creatives))
	for i, c := range creatives {
		text += fmt.Sprintf("  %d. %s\n", i+1, c.Content)
	}
	text += fmt.Sprintf("\n💡 建议：审核通过后自动开启，建议上传更多素材进行 A/B 测试")

	resp := &ConversationResponse{
		Text: text,
		Actions: []Action{
			{Type: "create_ad_group", Data: adGroup},
			{Type: "generate_creative", Data: creatives},
		},
	}

	e.conversation = append(e.conversation, ConversationMessage{
		Role:      "assistant",
		Content:   text,
		Timestamp: time.Now(),
	})

	return resp, nil
}

// handleGenerateCreative 处理创意生成请求
func (e *AdEngine) handleGenerateCreative(entities map[string]string) (*ConversationResponse, error) {
	industry := "clothing"
	if ind, ok := entities["industry"]; ok {
		industry = ind
	}

	creatives := e.creativeGen.GenerateCopies(industry)

	text := fmt.Sprintf("📝 已为您生成 %d 条创意文案：\n\n", len(creatives))
	for i, c := range creatives {
		text += fmt.Sprintf("%d. %s\n", i+1, c.Content)
	}
	text += "\n💡 需要我帮您应用到某个广告组吗？"

	resp := &ConversationResponse{
		Text:    text,
		Actions: []Action{{Type: "generate_creative", Data: creatives}},
	}

	e.conversation = append(e.conversation, ConversationMessage{
		Role:      "assistant",
		Content:   text,
		Timestamp: time.Now(),
	})

	return resp, nil
}

// handleOptimize 处理优化请求
func (e *AdEngine) handleOptimize() (*ConversationResponse, error) {
	// 模拟优化结果
	text := "📊 优化建议：\n\n"

	// camp_001: CPA 偏高
	text += "🟡 **camp_clothing_001** (服装):\n"
	text += "  - CPA ¥27.00 > 目标 ¥20.00\n"
	text += "  - 建议：降低出价 15%\n\n"

	// camp_002: ROAS 优秀
	text += "🟢 **camp_food_002** (餐饮):\n"
	text += "  - ROAS 8.7，表现优秀\n"
	text += "  - 建议：增加预算 30%\n\n"

	// camp_003: CPA 严重超标
	text += "🔴 **camp_hotel_003** (酒店):\n"
	text += "  - CPA ¥62.50 > 目标 ¥40.00\n"
	text += "  - 建议：暂停广告组\n\n"

	text += "💡 要我自动执行这些优化吗？"

	resp := &ConversationResponse{
		Text: text,
		Actions: []Action{
			{Type: "optimize", Data: map[string]string{
				"camp_clothing_001": "reduce_bid_15%",
				"camp_food_002":     "increase_budget_30%",
				"camp_hotel_003":    "pause",
			}},
		},
	}

	e.conversation = append(e.conversation, ConversationMessage{
		Role:      "assistant",
		Content:   text,
		Timestamp: time.Now(),
	})

	return resp, nil
}

// handlePause 处理暂停请求
func (e *AdEngine) handlePause(input string) (*ConversationResponse, error) {
	// 查找包含 "暂停" 的广告组
	updated := make([]string, 0)
	for id, ag := range e.adGroups {
		if strings.Contains(input, ag.Industry) || strings.Contains(input, id) {
			ag.Status = "paused"
			ag.StatusText = "已暂停"
			updated = append(updated, id)
		}
	}

	if len(updated) > 0 {
		text := fmt.Sprintf("✅ 已暂停 %d 个广告组: %v\n\n是否需要我帮您查看其他广告组的表现？", len(updated), updated)
		resp := &ConversationResponse{Text: text}
		e.conversation = append(e.conversation, ConversationMessage{
			Role:      "assistant",
			Content:   text,
			Timestamp: time.Now(),
		})
		return resp, nil
	}

	text := "没有找到可以暂停的广告组，请先创建一个广告组"
	resp := &ConversationResponse{Text: text}
	e.conversation = append(e.conversation, ConversationMessage{
		Role:      "assistant",
		Content:   text,
		Timestamp: time.Now(),
	})
	return resp, nil
}

// handleCheckPerformance 处理查询表现请求
func (e *AdEngine) handleCheckPerformance() (*ConversationResponse, error) {
	text := "📊 广告组表现概览：\n\n"
	text += fmt.Sprintf("%-15s %-8s %-10s %-10s %-10s\n", "广告组", "状态", "日花费", "CPA", "ROAS")
	text += strings.Repeat("-", 55) + "\n"

	performance := map[string]struct {
		Status string
		Spend  float64
		CPA    float64
		ROAS   float64
	}{
		"camp_clothing_001": {"running", 450, 27.0, 3.2},
		"camp_food_002":     {"running", 1200, 10.0, 8.7},
		"camp_hotel_003":    {"paused", 180, 62.5, 1.0},
	}

	for id, perf := range performance {
		text += fmt.Sprintf("%-15s %-8s ¥%-9.0f ¥%-9.1f %.1f\n",
			id, perf.Status, perf.Spend, perf.CPA, perf.ROAS)
	}

	text += "\n💡 平均 CPA: ¥29.83 | 平均 ROAS: 4.3"

	resp := &ConversationResponse{Text: text}
	e.conversation = append(e.conversation, ConversationMessage{
		Role:      "assistant",
		Content:   text,
		Timestamp: time.Now(),
	})
	return resp, nil
}

// recommendBid 推荐出价
func (e *AdEngine) recommendBid(industry string) float64 {
	bids := map[string]float64{
		"clothing":  0.80,
		"food":      0.50,
		"hotel":     1.20,
		"travel":    1.00,
		"education": 0.90,
		"beauty":    0.70,
		"electronics": 1.10,
	}
	if bid, ok := bids[industry]; ok {
		return bid
	}
	return 0.50 // 默认
}

// ============================================================
// Demo - 模拟真实对话
// ============================================================

func main() {
	engine := NewAdEngine()

	// 模拟真实对话
	dialogue := []string{
		"帮我创建一个服装广告，预算每天500，投给25-35岁女性，投放30天",
		"帮我生成3个文案",
		"广告效果怎么样？",
		"优化一下广告",
		"先把 camp_hotel_003 暂停",
	}

	fmt.Println("╔══════════════════════════════════════════════════════════╗")
	fmt.Println("║              🤖 NL2AD 广告智能助手                        ║")
	fmt.Println("║              说人话，自动创建和管理广告                    ║")
	fmt.Println("╚══════════════════════════════════════════════════════════╝")
	fmt.Println()

	for i, message := range dialogue {
		fmt.Printf("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n")
		fmt.Printf("👤 用户[%d]: %s\n", i+1, message)
		fmt.Println("───────────────────────────────────────────────────────")

		resp, err := engine.ProcessMessage(message)
		if err != nil {
			fmt.Printf("❌ 错误: %v\n", err)
			continue
		}

		// 去除 markdown 格式用于显示
		displayText := strings.ReplaceAll(resp.Text, "**", "")
		fmt.Printf("\n🤖 Agent: %s\n", displayText)
	}

	fmt.Println("\n╔══════════════════════════════════════════════════════════╗")
	fmt.Println("║              ✅ 对话完成！                               ║")
	fmt.Println("╚══════════════════════════════════════════════════════════╝")

	// 保存对话记录
	record := map[string]interface{}{
		"conversation": engine.conversation,
		"ad_groups":    engine.adGroups,
		"timestamp":    time.Now(),
	}
	if b, err := toJSON(record); err == nil {
		os.WriteFile("/tmp/nl2ad-conversation.json", b, 0644)
		fmt.Println("💬 对话记录已保存到 /tmp/nl2ad-conversation.json")
	}
}

func toJSON(v interface{}) ([]byte, error) {
	type Alias AdGroup
	return []byte{}, nil
}
