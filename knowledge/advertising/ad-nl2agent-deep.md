# 广告 NL2Agent 深度：自然语言创建广告 + 智能出价 + 自动投放

> 用户说人话，Agent 自动创建广告组/设置出价/分配预算/自动优化

---

## 第一部分：NL2AD 的核心价值

### 传统 vs NL2AD

```
传统创建广告：
1. 登录广告后台
2. 新建广告组
3. 选择投放目标（品牌认知/流量/转化）
4. 设置预算和日程
5. 选择定向（年龄/性别/地域/兴趣）
6. 设置出价策略
7. 上传创意素材
8. 填写文案
9. 提交审核
→ 耗时 30 分钟，需要专业知识

NL2AD（自然语言创建）：
用户说："帮我创建一个服装广告，预算每天 500，投给 25-35 岁女性"
→ Agent 自动完成所有步骤
→ 耗时 5 秒，零门槛
```

### 业务场景

```
1. 广告主自助创建：
   → 不懂专业术语的小商家
   → 说人话就能创建广告

2. 客服辅助创建：
   → 客服帮客户创建广告
   → 只需转发客户的话

3. 批量创建：
   → "帮我创建 10 个广告，每个品类一个"
   → Agent 自动拆分执行
```

---

## 第二部分：NL2AD 架构

### 2.1 整体架构

```
┌─────────────────────────────────────────────────────────────┐
│                    用户输入（自然语言）                        │
│  "帮我创建一个服装广告，预算每天 500，投给 25-35 岁女性"      │
└──────────────────────────┬──────────────────────────────────┘
                           │
              ┌────────────▼────────────┐
              │     NLU 理解层           │
              │  - 意图识别              │
              │  - 实体抽取              │
              │  - 槽位填充              │
              └────────────┬────────────┘
                           │
              ┌────────────▼────────────┐
              │   广告创建 Agent         │
              │  - 参数校验              │
              │  - 智能推荐              │
              │  - 创意生成              │
              └────────────┬────────────┘
                           │
              ┌────────────▼────────────┐
              │   执行层                 │
              │  - 创建广告组            │
              │  - 上传创意              │
              │  - 设置出价              │
              │  - 提交审核              │
              └────────────┬────────────┘
                           │
              ┌────────────▼────────────┐
              │   反馈层                 │
              │  - 创建结果              │
              │  - 优化建议              │
              │  - 预览效果              │
              └─────────────────────────┘
```

### 2.2 意图识别

```
用户输入 → 意图分类 → 执行对应 Agent

意图类型：
1. CREATE_AD          → 创建广告 Agent
2. OPTIMIZE_AD        → 优化 Agent
3. PAUSE_AD           → 暂停广告 Agent
4. CHECK_PERFORMANCE  → 查询表现 Agent
5. GENERATE_CREATIVE  → 创意生成 Agent
6. ANALYZE_COMPETITOR → 竞品分析 Agent
```

---

## 第三部分：NL2AD 核心实现

### 3.1 NLU 意图识别

```go
package nl2ad

import (
	"context"
	"fmt"
	"strings"
)

// Intent 意图类型
type Intent string

const (
	IntentCreateAd         Intent = "CREATE_AD"
	IntentOptimizeAd       Intent = "OPTIMIZE_AD"
	IntentPauseAd          Intent = "PAUSE_AD"
	IntentCheckPerformance Intent = "CHECK_PERFORMANCE"
	IntentGenerateCreative Intent = "GENERATE_CREATIVE"
	IntentAnalyzeCompetitor Intent = "ANALYZE_COMPETITOR"
)

// NLUResult NLU 解析结果
type NLUResult struct {
	Intent    Intent            `json:"intent"`
	Entities  map[string]string `json:"entities"`
	Score     float64           `json:"score"`
	RawInput  string            `json:"raw_input"`
}

// IntentClassifier 意图分类器
type IntentClassifier struct {
	rules []Rule
	model *LLMModel
}

// Rule 规则
type Rule struct {
	Patterns []string
	Intent   Intent
	Weight   float64
}

// NewIntentClassifier 创建意图分类器
func NewIntentClassifier() *IntentClassifier {
	return &IntentClassifier{
		rules: []Rule{
			{
				Patterns: []string{"创建", "新建", "建一个", "开一个", "投放", "上架"},
				Intent:   IntentCreateAd,
				Weight:   1.0,
			},
			{
				Patterns: []string{"优化", "调整", "改", "提升", "改善"},
				Intent:   IntentOptimizeAd,
				Weight:   1.0,
			},
			{
				Patterns: []string{"暂停", "停止", "下线", "关", "下架"},
				Intent:   IntentPauseAd,
				Weight:   1.0,
			},
			{
				Patterns: []string{"查看", "查询", "表现", "数据", "统计", "报告"},
				Intent:   IntentCheckPerformance,
				Weight:   1.0,
			},
			{
				Patterns: []string{"创意", "素材", "图片", "视频", "文案", "生成", "制作"},
				Intent:   IntentGenerateCreative,
				Weight:   1.0,
			},
		},
	}
}

// Classify 分类意图
func (c *IntentClassifier) Classify(input string) *NLUResult {
	bestIntent := IntentCreateAd
	bestScore := 0.0
	bestEntities := make(map[string]string)

	// 基于规则匹配
	for _, rule := range c.rules {
		score := 0.0
		for _, pattern := range rule.Patterns {
			if strings.Contains(input, pattern) {
				score += rule.Weight
			}
		}

		if score > bestScore {
			bestScore = score
			bestIntent = rule.Intent
		}
	}

	// 实体抽取
	entities := c.extractEntities(input, bestIntent)

	return &NLUResult{
		Intent:   bestIntent,
		Entities: entities,
		Score:    bestScore,
		RawInput: input,
	}
}

// extractEntities 抽取实体
func (c *IntentClassifier) extractEntities(input string, intent Intent) map[string]string {
	entities := make(map[string]string)

	// 提取预算
	if budget := extractBudget(input); budget != "" {
		entities["budget"] = budget
	}

	// 提取时长
	if duration := extractDuration(input); duration != "" {
		entities["duration"] = duration
	}

	// 提取行业
	if industry := extractIndustry(input); industry != "" {
		entities["industry"] = industry
	}

	// 提取人群
	if audience := extractAudience(input); audience != "" {
		entities["audience"] = audience
	}

	// 提取产品
	if product := extractProduct(input); product != "" {
		entities["product"] = product
	}

	return entities
}

// extractBudget 提取预算
func extractBudget(input string) string {
	// 匹配 "每天500" / "日预算500" / "预算1000"
	if strings.Contains(input, "每天") {
		idx := strings.Index(input, "每天")
		rest := input[idx+2:]
		for i, ch := range rest {
			if ch >= '0' && ch <= '9' {
				num := ""
				for j := i; j < len(rest) && rest[j] >= '0' && rest[j] <= '9'; j++ {
					num += string(rest[j])
				}
				return num
			}
		}
	}
	return ""
}

// extractDuration 提取时长
func extractDuration(input string) string {
	if strings.Contains(input, "天") {
		idx := strings.Index(input, "天")
		if idx > 0 {
			num := ""
			for i := idx - 1; i >= 0 && input[i] >= '0' && input[i] <= '9'; i-- {
				num = string(input[i]) + num
			}
			if num != "" {
				return num
			}
		}
	}
	return ""
}

// extractIndustry 提取行业
func extractIndustry(input string) string {
	industries := map[string]string{
		"服装": "clothing",
		"衣服": "clothing",
		"鞋": "shoes",
		"餐饮": "food",
		"美食": "food",
		"酒店": "hotel",
		"旅游": "travel",
		"教育": "education",
		"培训": "education",
		"美妆": "beauty",
		"护肤": "beauty",
	}

	for keyword, industry := range industries {
		if strings.Contains(input, keyword) {
			return industry
		}
	}
	return ""
}

// extractAudience 提取人群
func extractAudience(input string) string {
	audiences := []string{}

	// 年龄
	if strings.Contains(input, "岁") {
		start := 0
		end := 0
		found := false
		for i, ch := range input {
			if ch >= '0' && ch <= '9' {
				if !found {
					start = i
					found = true
				}
				end = i
			}
		}
		if found && start > 0 && end > start {
			ageRange := input[start : end+1]
			audiences = append(audiences, ageRange)
		}
	}

	// 性别
	if strings.Contains(input, "女性") || strings.Contains(input, "女生") {
		audiences = append(audiences, "female")
	}
	if strings.Contains(input, "男性") || strings.Contains(input, "男生") {
		audiences = append(audiences, "male")
	}

	if len(audiences) > 0 {
		return strings.Join(audiences, ",")
	}
	return ""
}

// extractProduct 提取产品
func extractProduct(input string) string {
	// 提取产品关键词（简单实现）
	products := []string{"服装", "鞋子", "包包", "化妆品", "手机", "电脑", "家具", "食品"}
	for _, p := range products {
		if strings.Contains(input, p) {
			return p
		}
	}
	return ""
}
```

### 3.2 广告创建 Agent

```go
// AdCreatorAgent 广告创建 Agent
type AdCreatorAgent struct {
	db        *Database
	llm       *LLMClient
	creative  *CreativeGenerator
	bidOptimizer *BidOptimizer
}

// CreateAdFromNL 从自然语言创建广告
func (a *AdCreatorAgent) CreateAdFromNL(ctx context.Context, userInput string, advertiserID string) (*AdCreationResult, error) {
	// Step 1: NLU 解析
	nlu := a.classifier.Classify(userInput)
	if nlu.Intent != IntentCreateAd {
		return nil, fmt.Errorf("意图不匹配: %s", nlu.Intent)
	}

	// Step 2: 参数提取和补全
	params, err := a.extractAndFillParams(nlu, advertiserID)
	if err != nil {
		return nil, err
	}

	// Step 3: 参数校验
	if err := a.validateParams(params); err != nil {
		return nil, err
	}

	// Step 4: 智能推荐
	a.applyRecommendations(params)

	// Step 5: 生成创意
	creatives, err := a.creative.Generate(ctx, params.Product, params.Industry)
	if err != nil {
		return nil, err
	}
	params.Creatives = creatives

	// Step 6: 推荐出价
	recommendedBid := a.bidOptimizer.RecommendBid(params.Industry, params.TargetCPA)
	params.BidValue = recommendedBid

	// Step 7: 创建广告
	result, err := a.db.CreateAdGroup(params)
	if err != nil {
		return nil, err
	}

	// Step 8: 生成反馈
	feedback := a.generateFeedback(result, params, creatives)

	return feedback, nil
}

// extractAndFillParams 提取并补全参数
func (a *AdCreatorAgent) extractAndFillParams(nlu *NLUResult, advertiserID string) (*AdParams, error) {
	params := &AdParams{
		AdvertiserID: advertiserID,
	}

	// 从 NLU 结果提取
	if budget, ok := nlu.Entities["budget"]; ok {
		params.DailyBudget, _ = parseFloat(budget)
	}
	if duration, ok := nlu.Entities["duration"]; ok {
		params.DurationDays, _ = parseInt(duration)
	}
	if industry, ok := nlu.Entities["industry"]; ok {
		params.Industry = industry
	}
	if audience, ok := nlu.Entities["audience"]; ok {
		params.Audience = audience
	}
	if product, ok := nlu.Entities["product"]; ok {
		params.Product = product
	}

	// 补全默认值
	if params.DailyBudget == 0 {
		params.DailyBudget = 100 // 默认日预算 100
	}
	if params.DurationDays == 0 {
		params.DurationDays = 30 // 默认 30 天
	}
	if params.TargetCPA == 0 {
		params.TargetCPA = 20 // 默认 CPA 20
	}

	return params, nil
}

// validateParams 参数校验
func (a *AdCreatorAgent) validateParams(params *AdParams) error {
	if params.DailyBudget < 10 {
		return fmt.Errorf("日预算不能低于 10 元")
	}
	if params.DurationDays < 1 {
		return fmt.Errorf("投放天数不能少于 1 天")
	}
	if params.TargetCPA < 1 {
		return fmt.Errorf("目标 CPA 不能低于 1 元")
	}
	if params.Product == "" {
		return fmt.Errorf("请提供产品信息")
	}
	return nil
}

// applyRecommendations 应用智能推荐
func (a *AdCreatorAgent) applyRecommendations(params *AdParams) {
	// 根据行业推荐出价
	if params.Industry == "clothing" {
		if params.BidValue == 0 {
			params.BidValue = 0.8 // 服装行业推荐 CPC 0.8
		}
	} else if params.Industry == "food" {
		if params.BidValue == 0 {
			params.BidValue = 0.5
		}
	}

	// 根据预算推荐定向范围
	if params.DailyBudget > 1000 {
		params.TargetingScope = "broad" // 预算充足，放宽定向
	} else if params.DailyBudget < 200 {
		params.TargetingScope = "narrow" // 预算有限，精准定向
	}
}
```

### 3.3 创意自动生成

```go
// CreativeGenerator 创意生成器
type CreativeGenerator struct {
	llm *LLMClient
}

// Generate 生成创意
func (g *CreativeGenerator) Generate(ctx context.Context, product string, industry string) ([]Creative, error) {
	creatives := make([]Creative, 0)

	// 生成文案
	copies, err := g.generateCopies(ctx, product, industry)
	if err != nil {
		return nil, err
	}
	creatives = append(creatives, copies...)

	// 生成图片提示
	imagePrompts, err := g.generateImagePrompts(ctx, product, industry)
	if err != nil {
		return nil, err
	}
	creatives = append(creatives, imagePrompts...)

	return creatives, nil
}

// generateCopies 生成文案
func (g *CreativeGenerator) generateCopies(ctx context.Context, product, industry string) ([]Creative, error) {
	prompts := []string{
		fmt.Sprintf("为%s行业的'%s'产品生成3条广告文案，要求：简短有力、突出卖点、包含行动号召", industry, product),
		fmt.Sprintf("为'%s'写5个广告标题，每个不超过20字", product),
		fmt.Sprintf("为'%s'产品生成落地页描述，100字以内", product),
	}

	creatives := make([]Creative, 0)
	for _, prompt := range prompts {
		response, err := g.llm.Chat(ctx, &ChatRequest{
			Prompt: prompt,
			Model:  "gpt-4",
		})
		if err != nil {
			continue
		}

		// 解析返回的文案
		lines := strings.Split(response, "\n")
		for _, line := range lines {
			line = strings.TrimSpace(line)
			if line != "" && len(line) > 5 {
				creatives = append(creatives, Creative{
					Type:    "copy",
					Content: line,
				})
			}
		}
	}

	return creatives, nil
}

// generateImagePrompts 生成图片提示
func (g *CreativeGenerator) generateImagePrompts(ctx context.Context, product, industry string) ([]Creative, error) {
	prompt := fmt.Sprintf(
		"为%s行业的'%s'产品生成3个图片创意描述，每个描述包含：颜色搭配、布局风格、主体元素",
		industry, product,
	)

	response, err := g.llm.Chat(ctx, &ChatRequest{
		Prompt: prompt,
		Model:  "gpt-4",
	})
	if err != nil {
		return nil, err
	}

	creatives := make([]Creative, 0)
	lines := strings.Split(response, "\n")
	for _, line := range lines {
		line = strings.TrimSpace(line)
		if line != "" {
			creatives = append(creatives, Creative{
				Type:    "image_prompt",
				Content: line,
			})
		}
	}

	return creatives, nil
}
```

---

## 第四部分：对话式优化 Agent

### 4.1 多轮对话优化

```
用户：帮我优化广告
Agent：发现 3 个问题：
  1. camp_001 CPA 偏高（27 vs 目标 20）
  2. camp_002 ROAS 优秀（8.7），可增加预算
  3. camp_003 CPA 严重超标（62.5），建议暂停

用户：先把 camp_003 暂停，camp_002 加 20% 预算
Agent：✅ 已执行：
  - camp_003: 已暂停
  - camp_002: 预算从 5000 → 6000
  是否需要我继续优化其他广告组？

用户：好的，剩下的也帮我优化
Agent：✅ 已完成全部优化...
```

### 4.2 实现

```go
// ConversationOptimizer 对话式优化 Agent
type ConversationOptimizer struct {
	agent       *SmartOptimizerAgent
	conversation *ConversationHistory
}

// ProcessMessage 处理用户消息
func (c *ConversationOptimizer) ProcessMessage(ctx context.Context, message string) (*Response, error) {
	// 添加到对话历史
	c.conversation.AddUserMessage(message)

	// 意图识别
	nlu := c.agent.classifier.Classify(message)

	var response *Response
	switch nlu.Intent {
	case IntentOptimizeAd:
		response = c.handleOptimize(ctx, nlu)
	case IntentPauseAd:
		response = c.handlePause(ctx, nlu)
	case IntentCheckPerformance:
		response = c.handleCheck(ctx, nlu)
	default:
		response = &Response{
			Text:    "我不太理解您的意思，请换个说法",
			Actions: []Action{},
		}
	}

	// 添加到对话历史
	c.conversation.AddAssistantMessage(response.Text)

	return response, nil
}

// handleOptimize 处理优化请求
func (c *ConversationOptimizer) handleOptimize(ctx context.Context, nlu *NLUResult) *Response {
	// 执行优化
	records, err := c.agent.Run(ctx, nlu.RawInput)
	if err != nil {
		return &Response{
			Text:    fmt.Sprintf("优化失败: %v", err),
			Actions: []Action{},
		}
	}

	// 生成回复
	text := c.formatOptimizationResult(records)

	return &Response{
		Text:    text,
		Actions: c.extractActions(records),
	}
}

// formatOptimizationResult 格式化优化结果
func (c *ConversationOptimizer) formatOptimizationResult(records []ActionRecord) string {
	sb := strings.Builder()
	sb.WriteString("优化完成！以下是执行结果：\n\n")

	for _, r := range records {
		sb.WriteString(fmt.Sprintf("**%s**: %s\n", r.Action, r.Result))
	}

	sb.WriteString("\n是否需要我帮您查看优化后的效果？")
	return sb.String()
}
```

---

## 第五部分：完整对话流程

### 5.1 从创建到优化的全流程

```
用户：我想做一个服装广告，预算每天500
  → Agent: 好的！请问您想投放多久？
  
用户：30天吧
  → Agent: 收到！我来为您创建广告组
  
  📋 广告组详情：
  - 行业：服装
  - 日预算：¥500
  - 投放时长：30天
  - 推荐出价：¥0.80 CPC
  - 推荐定向：25-45岁女性
  
  ✅ 广告组已创建：camp_20260115_001
  💡 建议：上传 3-5 个素材进行 A/B 测试

用户：帮我生成 3 个文案
  → Agent: 已生成以下文案：
  1. "春季新品上市！全场5折起，限时抢购！"
  2. "时尚女装，穿出你的自信！今日下单享免邮"
  3. "告别平庸！精选设计师款女装，低至2折"
  
  📸 需要我帮您生成图片素材吗？

用户：要的，帮我生成 3 张
  → Agent: 已生成 3 张创意素材
  🎨 素材 1: 简约风，白色背景+模特展示
  🎨 素材 2: 促销风，红色背景+折扣标签
  🎨 素材 3: 生活方式，户外场景+穿搭展示
  
  ✅ 素材已上传，等待审核

用户：审核通过后帮我开启
  → Agent: ✅ 已设置审核通过后自动开启

[2 小时后]
用户：广告效果怎么样？
  → Agent: 
  📊 广告表现（2小时）：
  - 展示：15,234
  - 点击：456 (CTR 3.0%)
  - 花费：¥228
  - 转化：12 (CPA ¥19)
  - ROAS：4.2
  
  💡 建议：CTR 表现良好，ROAS 超过目标，可增加预算！

用户：预算加到 800 每天
  → Agent: ✅ 预算已从 ¥500 → ¥800/天
  📈 预计每日展示量增加 60%
```

---

## 第六部分：自测题

### 问题 1
NL2AD 的核心流程是什么？

<details>
<summary>查看答案</summary>

1. **NLU 解析**：意图识别 + 实体抽取
2. **参数提取**：从自然语言中提取预算/时长/行业/人群
3. **参数补全**：缺失参数用默认值填充
4. **参数校验**：检查合法性
5. **智能推荐**：推荐出价/定向/创意
6. **创意生成**：LLM 生成文案和图片描述
7. **创建广告**：调用 API 创建广告组
8. **反馈结果**：向用户汇报创建结果
</details>

### 问题 2
对话式优化的核心优势是什么？

<details>
<summary>查看答案</summary>

1. **多轮对话**：可以逐步细化需求
2. **上下文理解**：记住之前的对话内容
3. **灵活调整**：随时修改参数
4. **实时反馈**：每步操作都有确认
5. **自然交互**：说人话就行，不需要填表单
</details>

---

*本文档基于广告 NL2Agent 生产实战整理。*