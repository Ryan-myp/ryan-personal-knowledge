# 广告 Agent 深度：NL2AD/对话式广告/Agent 编排竞价

> 从 RAG 到 Agent 编排，解析广告系统中 AI Agent 的完整技术栈

---

## 第一部分：为什么广告系统需要 Agent？

### 广告运营痛点

```
传统广告运营流程：
1. 创建广告 → 手动设置预算/出价/定向
2. 监控数据 → 每天看 Dashboard
3. 优化调整 → 手动调价/换创意/改定向
4. 归因分析 → 每周/月看归因报告
5. 跨平台管理 → Meta/Google/TikTok 分别登录

痛点：
- 重复劳动多（每天花 2-3 小时看数据）
- 决策慢（发现问题时已经损失了预算）
- 专业门槛高（需要懂竞价/定向/创意）
- 跨平台割裂（每个平台操作方式不同）

Agent 解决方案：
- 自然语言操作（"帮我把 Facebook 的 CPA 降到 $5"）
- 实时监控 + 自动优化（发现异常立即调价）
- 跨平台统一管理（一个 Agent 管所有平台）
- 智能决策（基于历史数据和 AI 模型）
```

### Agent 在广告系统中的位置

```
┌─────────────────────────────────────────────────────────────────────┐
│ 用户（广告主/优化师）                                                 │
│ "帮我把 Campaign A 的 CPA 从 $8 降到 $5"                            │
│ "分析过去 30 天的广告表现，给出优化建议"                              │
│ "自动调整三个平台的预算分配"                                         │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    Agent 编排层                                       │
│                                                                     │
│  ┌────────────┐    ┌────────────┐    ┌────────────┐                │
│  │ Intent     │───►│ Planner    │───►│ Executor   │                │
│  │ Classifier │    │ (任务规划)  │    │ (工具调用)  │                │
│  └────────────┘    └────────────┘    └────────────┘                │
│                                                                     │
│  能力：                                                              │
│  • 理解自然语言意图                                                   │
│  • 拆解为子任务（查数据→分析→决策→执行）                               │
│  • 调用 MCP Tools 执行操作                                           │
│  • 生成自然语言报告                                                   │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    MCP Tool Layer                                   │
│                                                                     │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐              │
│  │ Meta API │ │ Google   │ │ TikTok   │ │ DAP      │              │
│  │ Tools    │ │ Ads API  │ │ Ads API  │ │ Platform │              │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘              │
│                                                                     │
│  工具：                                                              │
│  • getCampaigns / updateBudget / pauseCampaign                      │
│  • getReport / optimizeBid / generateCreative                       │
│  • getAnalytics / suggestKeywords / monitorFraud                    │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 第二部分：NL2AD（Natural Language to Ad Creation）

### NL2AD 架构

```
NL2AD 流程：
用户输入 → Intent 理解 → Prompt 构建 → LLM 生成 → 创意审核 → 上架

示例：
用户："帮我创建一个 Facebook 广告，推广夏季促销，预算 $1000/天"

1. Intent 理解：
   - 动作：创建广告
   - 平台：Facebook
   - 主题：夏季促销
   - 预算：$1000/天

2. Prompt 构建：
   系统提示：你是一个广告创意生成助手
   用户输入：帮我创建一个 Facebook 广告，推广夏季促销，预算 $1000/天
   上下文：
   - 产品：[从产品库获取]
   - 目标受众：[从历史数据推断]
   - 品牌调性：[从品牌指南获取]

3. LLM 生成：
   - 标题："Summer Sale! Up to 50% Off!"
   - 正文："Don't miss our biggest summer sale..."
   - 视觉建议：沙滩/阳光/折扣标签
   - CTA："Shop Now"

4. 创意审核：
   - 平台政策检查（Facebook Ads Policy）
   - 品牌合规检查
   - 敏感词过滤

5. 上架：
   - 调用 Meta API 创建广告
   - 返回广告 ID 和预览链接
```

### NL2AD 实现

```go
package nl2ad

import (
	"context"
	"fmt"
)

// NL2AD 自然语言创建广告
type NL2AD struct {
	llm        LLMClient
	policy     PolicyEngine
	productDB  ProductDatabase
}

// Intent 用户意图
type Intent struct {
	Action    string // create/update/optimize/pause/delete
	Platform  string // facebook/google/tiktok
	Campaign  string
	Budget    float64
	Targeting Targeting
	Creative  CreativeBrief
}

// Targeting 定向信息
type Targeting struct {
	AgeRange    [2]int   // [18, 35]
	Genders     []string // ["male", "female"]
	Locations   []string // ["US", "CA"]
	Interests   []string // ["shopping", "fashion"]
	Lookalike   float64  // 0.0-1.0
}

// CreativeBrief 创意简报
type CreativeBrief struct {
	Title       string
	Description string
	VisualStyle string // minimalist, colorful, lifestyle
	CTA         string // shop_now, learn_more, sign_up
	BrandTone   string // professional, casual, fun
}

// ParseIntent 解析自然语言为意图
func (n *NL2AD) ParseIntent(ctx context.Context, userInput string) (*Intent, error) {
	// 1. 构建 LLM prompt
	prompt := fmt.Sprintf(`
你是一个广告创意助手。请将用户的自然语言请求解析为结构化数据。

用户输入: %s

请返回以下 JSON 格式:
{
  "action": "create|update|optimize|pause|delete",
  "platform": "facebook|google|tiktok",
  "campaign": "广告系列名称",
  "budget": 预算金额,
  "targeting": {
    "age_range": [最小年龄, 最大年龄],
    "genders": ["gender1", ...],
    "locations": ["country_code", ...],
    "interests": ["interest1", ...],
    "lookalike": 0.0-1.0
  },
  "creative": {
    "title": "标题",
    "description": "描述",
    "visual_style": "minimalist|colorful|lifestyle",
    "cta": "shop_now|learn_more|sign_up",
    "brand_tone": "professional|casual|fun"
  }
}`, userInput)

	// 2. 调用 LLM
	response, err := n.llm.Generate(ctx, prompt)
	if err != nil {
		return nil, err
	}

	// 3. 解析 JSON
	intent := &Intent{}
	if err := json.Unmarshal([]byte(response), intent); err != nil {
		return nil, err
	}

	return intent, nil
}

// GenerateCreative 生成创意
func (n *NL2AD) GenerateCreative(ctx context.Context, intent *Intent) (*CreativeBrief, error) {
	// 1. 获取产品上下文
	products, err := n.productDB.Search(ctx, intent.Campaign)
	if err != nil {
		return nil, err
	}

	// 2. 构建 prompt
	prompt := fmt.Sprintf(`
生成一个 %s 广告创意。

产品信息: %v
预算: $%.0f/天
目标受众: %v

请生成:
- 标题 (不超过 40 字符)
- 描述 (不超过 150 字符)
- 视觉风格建议
- CTA 按钮文案
- 品牌语调建议`,
		intent.Platform, products, intent.Budget, intent.Targeting)

	// 3. 调用 LLM
	response, err := n.llm.Generate(ctx, prompt)
	if err != nil {
		return nil, err
	}

	creative := &CreativeBrief{}
	if err := json.Unmarshal([]byte(response), creative); err != nil {
		return nil, err
	}

	return creative, nil
}

// ValidateCreative 审核创意
func (n *NL2AD) ValidateCreative(creative *CreativeBrief) error {
	// 1. 检查标题长度
	if len(creative.Title) > 40 {
		return fmt.Errorf("title too long: %d chars", len(creative.Title))
	}

	// 2. 检查敏感词
	if n.policy.ContainsSensitiveWords(creative.Description) {
		return fmt.Errorf("sensitive words detected")
	}

	// 3. 检查品牌合规
	if !n.policy.CheckBrandCompliance(creative) {
		return fmt.Errorf("brand compliance failed")
	}

	return nil
}

// CreateAd 创建广告
func (n *NL2AD) CreateAd(ctx context.Context, intent *Intent, creative *CreativeBrief) (string, error) {
	// 1. 审核创意
	if err := n.ValidateCreative(creative); err != nil {
		return "", err
	}

	// 2. 调用对应平台 API
	switch intent.Platform {
	case "facebook":
		return n.createFacebookAd(ctx, intent, creative)
	case "google":
		return n.createGoogleAd(ctx, intent, creative)
	case "tiktok":
		return n.createTikTokAd(ctx, intent, creative)
	default:
		return "", fmt.Errorf("unsupported platform: %s", intent.Platform)
	}
}

func (n *NL2AD) createFacebookAd(ctx context.Context, intent *Intent, creative *CreativeBrief) (string, error) {
	// 调用 Meta Marketing API
	// ...
	return "ad_id_12345", nil
}
```

---

## 第三部分：对话式广告平台

### 架构设计

```
对话式广告平台：
┌─────────────────────────────────────────────────────────────────────┐
│ 用户界面（Slack/Discord/Web）                                         │
│                                                                     │
│  用户: "帮我看看过去 7 天的广告表现"                                  │
│                                                                     │
│  Agent 处理流程:                                                    │
│  1. 意图识别 → 查询广告数据                                           │
│  2. 工具选择 → getAdAnalytics                                         │
│  3. 参数提取 → {days: 7, metrics: ["impressions", "clicks", "spend"]}│
│  4. 执行查询 → 调用 DAP API                                          │
│  5. 数据分析 → 计算 CTR/CPC/CPA/ROAS                                 │
│  6. 生成报告 → 自然语言 + 图表                                        │
│                                                                     │
│  用户: "CTR 下降了，什么原因？"                                      │
│                                                                     │
│  Agent 处理流程:                                                    │
│  1. 意图识别 → 根因分析                                               │
│  2. 工具选择 → diagnoseCTRFall                                        │
│  3. 参数提取 → {campaign: "summer_sale", platform: "facebook"}       │
│  4. 执行诊断 → 检查定向/出价/创意/竞争                                 │
│  5. 生成建议 → "CTR 下降主要是因为创意疲劳，建议更换新素材"            │
└─────────────────────────────────────────────────────────────────────┘
```

### 对话管理源码

```go
package conversational

import (
	"context"
	"strings"
)

// Conversation 对话状态
type Conversation struct {
	ID          string
	UserID      string
	Platform    string // slack/discord/web
	Messages    []Message
	Context     map[string]interface{}
	LastAction  string
	WaitingFor  string // 等待用户输入的内容
}

// Message 对话消息
type Message struct {
	Role    string // user/assistant/system
	Content string
	Timestamp time.Time
}

// DialogManager 对话管理器
type DialogManager struct {
	intentClassifier IntentClassifier
	planner          ToolPlanner
	executor         ToolExecutor
	analytics        AnalyticsEngine
}

// ProcessMessage 处理用户消息
func (dm *DialogManager) ProcessMessage(ctx context.Context, conv *Conversation, msg string) (*AssistantResponse, error) {
	// 1. 添加用户消息
	conv.Messages = append(conv.Messages, Message{
		Role:    "user",
		Content: msg,
	})

	// 2. 意图识别
	intent, entities, err := dm.intentClassifier.Classify(msg)
	if err != nil {
		return nil, err
	}

	// 3. 更新对话上下文
	dm.updateContext(conv, intent, entities)

	// 4. 根据意图选择响应策略
	switch intent {
	case "query_analytics":
		return dm.handleQueryAnalytics(conv, entities)
	case "diagnose_issue":
		return dm.handleDiagnoseIssue(conv, entities)
	case "optimize_campaign":
		return dm.handleOptimizeCampaign(conv, entities)
	case "create_ad":
		return dm.handleCreateAd(conv, entities)
	case "budget_allocation":
		return dm.handleBudgetAllocation(conv, entities)
	case "general_chat":
		return dm.handleGeneralChat(conv, msg)
	default:
		return &AssistantResponse{
			Message: "抱歉，我不理解这个请求。请重新描述。",
			Actions: []Action{},
		}, nil
	}
}

// handleQueryAnalytics 处理查询分析请求
func (dm *DialogManager) handleQueryAnalytics(conv *Conversation, entities map[string]interface{}) (*AssistantResponse, error) {
	// 1. 提取参数
	campaignID, _ := entities["campaign"].(string)
	days, _ := entities["days"].(int)
	if days == 0 {
		days = 7 // 默认 7 天
	}

	// 2. 查询数据
	data, err := dm.analytics.GetCampaignData(campaignID, days)
	if err != nil {
		return nil, err
	}

	// 3. 计算关键指标
	metrics := dm.analytics.ComputeMetrics(data)

	// 4. 生成自然语言报告
	report := dm.generateReport(metrics)

	return &AssistantResponse{
		Message: report,
		Actions: []Action{
			{
				Type:  "chart",
				Data:  metrics.ChartData(),
			},
			{
				Type:  "suggestion",
				Text:  "建议优化 CTR 低的广告组",
			},
		},
	}, nil
}

// generateReport 生成自然语言报告
func (dm *DialogManager) generateReport(metrics *AnalyticsMetrics) string {
	var sb strings.Builder

	sb.WriteString("📊 过去 ")
	sb.WriteString(fmt.Sprintf("%d", metrics.Days))
	sb.WriteString(" 天广告表现:\n\n")

	sb.WriteString(fmt.Sprintf("💰 花费: $%.2f\n", metrics.TotalSpend))
	sb.WriteString(fmt.Sprintf("👁️ 曝光: %d\n", metrics.Impressions))
	sb.WriteString(fmt.Sprintf("👆 点击: %d (CTR: %.2f%%)\n", metrics.Clicks, metrics.CTR))
	sb.WriteString(fmt.Sprintf("💵 CPA: $%.2f\n", metrics.CPA))
	sb.WriteString(fmt.Sprintf("📈 ROAS: %.2fx\n", metrics.ROAS))

	// 趋势分析
	if metrics.CTRChange < -0.5 {
		sb.WriteString("\n⚠️ CTR 下降了 " + fmt.Sprintf("%.1f", -metrics.CTRChange) + "%，建议检查创意质量。\n")
	}
	if metrics.CPAChange > 0.5 {
		sb.WriteString("⚠️ CPA 上升了 " + fmt.Sprintf("%.1f", metrics.CPAChange) + "%，建议优化出价策略。\n")
	}

	return sb.String()
}
```

---

## 第四部分：Agent 编排竞价

### 架构设计

```
Agent 编排竞价：
┌─────────────────────────────────────────────────────────────────────┐
│ 目标：自动优化竞价策略，最大化 ROI                                    │
│                                                                     │
│  Agent 循环:                                                        │
│  1. 观察：获取当前广告数据（CTR/CPC/CPA/ROAS）                       │
│  2. 思考：分析数据，识别问题                                          │
│  3. 决策：选择优化动作（调价/暂停/换创意）                            │
│  4. 执行：调用 API 执行操作                                           │
│  5. 反馈：观察效果，更新策略                                          │
│                                                                     │
│  多 Agent 协作:                                                     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │
│  │ Budget Agent │  │ Bid Agent    │  │ Creative Agent│              │
│  │ 管理预算分配  │  │ 优化出价策略  │  │ 生成/测试创意  │              │
│  └──────────────┘  └──────────────┘  └──────────────┘              │
│         │                  │                  │                      │
│         └──────────────────┼──────────────────┘                      │
│                            ▼                                          │
│                   ┌─────────────────┐                                │
│                   │ Coordinator     │                                │
│                   │ 协调多 Agent    │                                │
│                   └─────────────────┘                                │
└─────────────────────────────────────────────────────────────────────┘
```

### Agent 编排实现

```go
package agent

import (
	"context"
	"sync"
)

// Agent 广告 Agent 接口
type Agent interface {
	Name() string
	Observe(ctx context.Context) (*Observation, error)
	Think(observation *Observation) (*Decision, error)
	Execute(ctx context.Context, decision *Decision) error
	UpdatePolicy(ctx context.Context, feedback *Feedback) error
}

// Observation 观察结果
type Observation struct {
	CampaignID   string
	Platform     string
	Impressions  int64
	Clicks       int
	Conversions  int
	Spend        float64
	CTR          float64
	CPC          float64
	CPA          float64
	ROAS         float64
	Trend        string // improving/stable/degrading
}

// Decision 决策
type Decision struct {
	Action    string // increase_bid/decrease_bid/pause/creative_change
	Platform  string
	Campaign  string
	Parameter float64 // 新出价/新预算
	Reason    string
}

// Feedback 反馈
type Feedback struct {
	DecisionID   string
	Outcome      string // success/failed
	MetricsChange map[string]float64 // CTR_change, CPA_change, ROAS_change
}

// BudgetAgent 预算 Agent
type BudgetAgent struct {
	analytics AnalyticsEngine
	optimizer Optimizer
}

func (a *BudgetAgent) Name() string { return "budget" }

func (a *BudgetAgent) Observe(ctx context.Context) (*Observation, error) {
	data, err := a.analytics.GetBudgetData(ctx)
	if err != nil {
		return nil, err
	}
	return &Observation{
		Spend:     data.TotalSpend,
		Budget:    data.TotalBudget,
		ROAS:      data.AvgROAS,
		Trend:     data.Trend,
	}, nil
}

func (a *BudgetAgent) Think(obs *Observation) (*Decision, error) {
	if obs.ROAS < 2.0 {
		// ROAS 低，减少预算
		return &Decision{
			Action:    "decrease_budget",
			Parameter: obs.Budget * 0.8, // 减少 20%
			Reason:    "ROAS 低于目标，减少预算",
		}, nil
	}
	if obs.ROAS > 4.0 {
		// ROAS 高，增加预算
		return &Decision{
			Action:    "increase_budget",
			Parameter: obs.Budget * 1.2, // 增加 20%
			Reason:    "ROAS 高于目标，增加预算",
		}, nil
	}
	return nil, nil
}

// BidAgent 出价 Agent
type BidAgent struct {
	biddingEngine BiddingEngine
	rlPolicy      RLPolicy
}

func (a *BidAgent) Name() string { return "bid" }

func (a *BidAgent) Observe(ctx context.Context) (*Observation, error) {
	data, err := a.biddingEngine.GetCurrentBidData(ctx)
	if err != nil {
		return nil, err
	}
	return &Observation{
		CTR:     data.CTR,
		CPC:     data.CurrentCPC,
		ROAS:    data.ROAS,
		Trend:   data.Trend,
	}, nil
}

func (a *BidAgent) Think(obs *Observation) (*Decision, error) {
	// RL 策略决策
	newBid := a.rlPolicy.SelectAction(obs)
	return &Decision{
		Action:    "update_bid",
		Parameter: newBid,
		Reason:    "RL 策略优化出价",
	}, nil
}

// Coordinator 协调器
type Coordinator struct {
	agents  []Agent
	mu      sync.Mutex
	history []Decision
}

// RunCycle 执行一轮 Agent 循环
func (c *Coordinator) RunCycle(ctx context.Context) ([]Decision, error) {
	c.mu.Lock()
	defer c.mu.Unlock()

	var decisions []Decision

	// 1. 所有 Agent 观察
	var observations []*Observation
	for _, agent := range c.agents {
		obs, err := agent.Observe(ctx)
		if err != nil {
			continue
		}
		observations = append(observations, obs)
	}

	// 2. 所有 Agent 思考
	for i, agent := range c.agents {
		decision, err := agent.Think(observations[i])
		if err != nil || decision == nil {
			continue
		}
		decisions = append(decisions, *decision)
	}

	// 3. 冲突检测与消解
	decisions = c.resolveConflicts(decisions)

	// 4. 执行决策
	for _, decision := range decisions {
		if err := c.executeDecision(ctx, decision); err != nil {
			continue
		}
		c.history = append(c.history, decision)
	}

	return decisions, nil
}

// resolveConflicts 冲突消解
func (c *Coordinator) resolveConflicts(decisions []Decision) []Decision {
	// 简单策略：预算 Agent 优先于出价 Agent
	// 实际生产中需要更复杂的冲突消解策略
	return decisions
}
```

---

## 第五部分：自测题

### Q1: NL2AD 和传统广告创建的区别？

**A**:
- **传统**: 手动填写表单，选择定向，上传创意
- **NL2AD**: 自然语言描述，LLM 自动生成创意和定向
- NL2AD 降低了广告创建门槛，让非专业人士也能创建高质量广告

### Q2: 对话式广告平台的关键技术？

**A**:
- **意图识别**: 理解用户自然语言请求
- **对话管理**: 维护对话上下文和历史
- **工具调用**: 调用 MCP Tools 执行操作
- **报告生成**: 将数据转化为自然语言报告

### Q3: 多 Agent 协作的挑战？

**A**:
- **冲突消解**: 多个 Agent 可能做出矛盾决策
- **状态同步**: 需要共享观察数据和决策历史
- **性能**: 多 Agent 串行执行增加延迟
- **评估**: 如何评估多 Agent 系统的整体效果

---

## 第六部分：生产实践

### 1. Agent 安全

```
Agent 安全策略：
1. 权限控制：Agent 只能操作授权的平台和广告系列
2. 审批流程：大额预算变更需要人工审批
3. 审计日志：记录所有 Agent 操作
4. 回滚机制：支持撤销 Agent 的操作
5. 频率限制：限制 Agent 的操作频率
```

### 2. Agent 评估

```
Agent 评估指标：
1. 意图识别准确率：> 90%
2. 工具调用成功率：> 95%
3. 决策 ROI 提升：> 10%
4. 用户满意度：> 4.5/5
5. 操作延迟：< 5s
```

### 3. 典型使用场景

```
场景 1: 日常监控
用户: "今天广告表现怎么样？"
Agent: 生成日报，指出异常

场景 2: 预算优化
用户: "帮我把三个平台的预算分配到最优比例"
Agent: 分析历史数据，推荐分配方案

场景 3: 创意测试
用户: "帮我测试 5 个不同的广告创意"
Agent: 创建 A/B 测试，监控结果

场景 4: 问题诊断
用户: "为什么上周 CPA 上升了 30%？"
Agent: 分析原因，给出建议
```
