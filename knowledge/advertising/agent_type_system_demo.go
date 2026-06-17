package main

import (
	"context"
	"encoding/json"
	"fmt"
	"strings"
	"sync"
	"time"
)

// ============================================================
// 广告 Agent 类型体系 - 完整可运行演示
// ============================================================

// ----------------------------
// 1. 基础类型定义
// ----------------------------

// AgentType Agent 类型
type AgentType string

const (
	AgentCoordinator AgentType = "coordinator"
	AgentQuery       AgentType = "query"
	AgentDiagnostic  AgentType = "diagnostic"
	AgentCustom      AgentType = "custom"
)

// IntentType 意图类型
type IntentType string

const (
	IntentOperation  IntentType = "operation"
	IntentKnowledge  IntentType = "knowledge"
	IntentDiagnostic IntentType = "diagnostic"
	IntentChat       IntentType = "chat"
)

// Intent 意图
type Intent struct {
	Type   IntentType `json:"type"`
	Action string     `json:"action"`
}

// AgentRequest Agent 请求
type AgentRequest struct {
	UserID    string                 `json:"user_id"`
	Message   string                 `json:"message"`
	Context   map[string]interface{} `json:"context"`
	Channel   string                 `json:"channel"`
	AccountID string                 `json:"account_id"`
}

// AgentResponse Agent 响应
type AgentResponse struct {
	Text       string                 `json:"text"`
	Structured map[string]interface{} `json:"structured,omitempty"`
	Metadata   map[string]interface{} `json:"metadata,omitempty"`
}

// AgentInterface Agent 接口
type AgentInterface interface {
	Handle(ctx context.Context, request AgentRequest) (*AgentResponse, error)
	GetType() AgentType
	GetName() string
	GetDescription() string
}

// ----------------------------
// 2. Intent Classifier（意图分类器）
// ----------------------------

func classifyIntent(message string) *Intent {
	if strings.Contains(message, "异常") || strings.Contains(message, "问题") || strings.Contains(message, "诊断") {
		return &Intent{Type: IntentDiagnostic, Action: "diagnose_issue"}
	}
	if strings.Contains(message, "查询") || strings.Contains(message, "查看") || strings.Contains(message, "数据") {
		return &Intent{Type: IntentKnowledge, Action: "query_data"}
	}
	if strings.Contains(message, "优化") || strings.Contains(message, "调整") {
		return &Intent{Type: IntentOperation, Action: "optimize_ad"}
	}
	if strings.Contains(message, "创建") || strings.Contains(message, "新建") {
		return &Intent{Type: IntentOperation, Action: "create_campaign"}
	}
	return &Intent{Type: IntentOperation, Action: "unknown"}
}

// ----------------------------
// 3. Coordinator Agent（协调者）
// ----------------------------

type CoordinatorAgent struct {
	agents map[AgentType]AgentInterface
	mu     sync.Mutex
}

func NewCoordinatorAgent() *CoordinatorAgent {
	return &CoordinatorAgent{
		agents: make(map[AgentType]AgentInterface),
	}
}

func (c *CoordinatorAgent) RegisterAgent(agent AgentInterface) {
	c.mu.Lock()
	defer c.mu.Unlock()
	c.agents[agent.GetType()] = agent
}

func (c *CoordinatorAgent) Handle(ctx context.Context, request AgentRequest) (*AgentResponse, error) {
	// 1. 意图分类
	intent := classifyIntent(request.Message)
	fmt.Printf("🤖 意图分类: %s → %s\n", intent.Type, intent.Action)

	// 2. 选择 Agent
	agentType := c.selectAgent(intent)
	fmt.Printf("🤖 选择 Agent: %s\n", agentType)

	// 3. 获取 Agent
	c.mu.Lock()
	agent, ok := c.agents[agentType]
	c.mu.Unlock()

	if !ok {
		return &AgentResponse{
			Text: fmt.Sprintf("抱歉，暂不支持处理此类请求（意图: %s）", intent.Action),
		}, nil
	}

	// 4. 执行
	response, err := agent.Handle(ctx, request)
	if err != nil {
		return nil, err
	}

	// 5. 添加元数据
	if response.Metadata == nil {
		response.Metadata = make(map[string]interface{})
	}
	response.Metadata["agent_name"] = agent.GetName()
	response.Metadata["agent_type"] = string(agent.GetType())

	return response, nil
}

func (c *CoordinatorAgent) selectAgent(intent *Intent) AgentType {
	switch intent.Type {
	case IntentDiagnostic:
		return AgentDiagnostic
	case IntentKnowledge:
		return AgentQuery
	default:
		return AgentQuery
	}
}

// ----------------------------
// 4. Query Agent（查询者）
// ----------------------------

type QueryAgent struct {
	tools map[string]func(ctx context.Context, params map[string]interface{}) (interface{}, error)
}

func NewQueryAgent() *QueryAgent {
	qa := &QueryAgent{
		tools: make(map[string]func(ctx context.Context, params map[string]interface{}) (interface{}, error)),
	}

	// 注册工具
	qa.RegisterTool("get_campaign", qa.handleGetCampaign)
	qa.RegisterTool("get_performance", qa.handleGetPerformance)
	qa.RegisterTool("create_campaign", qa.handleCreateCampaign)
	qa.RegisterTool("optimize_ad", qa.handleOptimizeAd)

	return qa
}

func (q *QueryAgent) RegisterTool(name string, handler func(ctx context.Context, params map[string]interface{}) (interface{}, error)) {
	q.tools[name] = handler
}

func (q *QueryAgent) Handle(ctx context.Context, request AgentRequest) (*AgentResponse, error) {
	intent := classifyIntent(request.Message)
	toolName := q.resolveTool(intent)

	handler, ok := q.tools[toolName]
	if !ok {
		return &AgentResponse{
			Text: fmt.Sprintf("未找到工具: %s", toolName),
		}, nil
	}

	result, err := handler(ctx, map[string]interface{}{
		"account_id": request.AccountID,
	})
	if err != nil {
		return nil, err
	}

	return &AgentResponse{
		Text:       fmt.Sprintf("✅ %v", result),
		Structured: result.(map[string]interface{}),
	}, nil
}

func (q *QueryAgent) resolveTool(intent *Intent) string {
	switch intent.Action {
	case "query_data":
		return "get_performance"
	case "optimize_ad":
		return "optimize_ad"
	case "create_campaign":
		return "create_campaign"
	default:
		return "get_campaign"
	}
}

func (q *QueryAgent) handleGetCampaign(ctx context.Context, params map[string]interface{}) (interface{}, error) {
	return map[string]interface{}{
		"campaign_id": "camp_789",
		"name":        "服装广告",
		"status":      "enabled",
		"daily_budget": 500,
	}, nil
}

func (q *QueryAgent) handleGetPerformance(ctx context.Context, params map[string]interface{}) (interface{}, error) {
	return map[string]interface{}{
		"impressions": 155000,
		"clicks":      4650,
		"ctr":         0.03,
		"conversions": 464,
		"spend":       6115.0,
		"cpa":         13.18,
		"roas":        4.3,
	}, nil
}

func (q *QueryAgent) handleCreateCampaign(ctx context.Context, params map[string]interface{}) (interface{}, error) {
	return map[string]interface{}{
		"campaign_id": "camp_new_001",
		"name":        "新广告系列",
		"status":      "enabled",
		"created_at":  time.Now().Format(time.RFC3339),
	}, nil
}

func (q *QueryAgent) handleOptimizeAd(ctx context.Context, params map[string]interface{}) (interface{}, error) {
	return map[string]interface{}{
		"optimized_count": 3,
		"bid_adjustments": []map[string]interface{}{
			{"campaign_id": "camp_001", "old_bid": 0.50, "new_bid": 0.45, "change": "-10%"},
			{"campaign_id": "camp_002", "old_bid": 0.30, "new_bid": 0.35, "change": "+17%"},
		},
	}, nil
}

func (q *QueryAgent) GetType() AgentType       { return AgentQuery }
func (q *QueryAgent) GetName() string          { return "QueryAgent" }
func (q *QueryAgent) GetDescription() string   { return "负责数据查询和报表生成的 Agent" }

// ----------------------------
// 5. Diagnostic Agent（诊断者）
// ----------------------------

type DiagnosticAgent struct {
	anomalies []string
	suggestions []string
}

func NewDiagnosticAgent() *DiagnosticAgent {
	return &DiagnosticAgent{
		anomalies: []string{
			"CPA 超过目标 50%",
			"CTR 下降 20%",
			"转化率低于预期",
		},
		suggestions: []string{
			"建议降低出价 15%，优化定向",
			"建议更换创意素材，优化落地页",
			"建议优化转化目标，调整出价策略",
		},
	}
}

func (d *DiagnosticAgent) Handle(ctx context.Context, request AgentRequest) (*AgentResponse, error) {
	return &AgentResponse{
		Text: d.formatResponse(),
		Structured: map[string]interface{}{
			"anomalies":   d.anomalies,
			"suggestions": d.suggestions,
		},
	}, nil
}

func (d *DiagnosticAgent) formatResponse() string {
	var sb strings.Builder
	sb.WriteString("🔍 诊断结果:\n\n")
	sb.WriteString("异常:\n")
	for _, a := range d.anomalies {
		sb.WriteString(fmt.Sprintf("  - %s\n", a))
	}
	sb.WriteString("\n建议:\n")
	for i, s := range d.suggestions {
		sb.WriteString(fmt.Sprintf("  %d. %s\n", i+1, s))
	}
	return sb.String()
}

func (d *DiagnosticAgent) GetType() AgentType       { return AgentDiagnostic }
func (d *DiagnosticAgent) GetName() string          { return "DiagnosticAgent" }
func (d *DiagnosticAgent) GetDescription() string   { return "负责异常检测和优化建议的 Agent" }

// ----------------------------
// 6. Custom Agent（自定义）
// ----------------------------

type CustomAgent struct {
	name        string
	description string
	handler     func(ctx context.Context, request AgentRequest) (*AgentResponse, error)
}

func NewCustomAgent(name, desc string, handler func(ctx context.Context, request AgentRequest) (*AgentResponse, error)) *CustomAgent {
	return &CustomAgent{name: name, description: desc, handler: handler}
}

func (c *CustomAgent) Handle(ctx context.Context, request AgentRequest) (*AgentResponse, error) {
	return c.handler(ctx, request)
}

func (c *CustomAgent) GetType() AgentType       { return AgentCustom }
func (c *CustomAgent) GetName() string          { return c.name }
func (c *CustomAgent) GetDescription() string   { return c.description }

// ----------------------------
// 7. 凭证管理（不提交到 git）
// ----------------------------

type CredentialManager struct {
	credentials map[string]map[string]map[string]string // provider -> account_id -> credentials
	mu          sync.RWMutex
}

func NewCredentialManager() *CredentialManager {
	return &CredentialManager{
		credentials: make(map[string]map[string]map[string]string),
	}
}

func (cm *CredentialManager) Store(provider, accountID string, creds map[string]string) {
	cm.mu.Lock()
	defer cm.mu.Unlock()
	if _, ok := cm.credentials[provider]; !ok {
		cm.credentials[provider] = make(map[string]map[string]string)
	}
	cm.credentials[provider][accountID] = creds
}

func (cm *CredentialManager) Get(provider, accountID string) (map[string]string, bool) {
	cm.mu.RLock()
	defer cm.mu.RUnlock()
	accounts, ok := cm.credentials[provider]
	if !ok {
		return nil, false
	}
	creds, ok := accounts[accountID]
	return creds, ok
}

// 注意：凭证文件 .env / credentials.json 已在 .gitignore 中排除
// 生产环境使用环境变量或密钥管理服务（AWS Secrets Manager / HashiCorp Vault）

// ----------------------------
// 8. 完整演示
// ----------------------------

func main() {
	fmt.Println("========================================")
	fmt.Println("  广告 Agent 类型体系完整演示")
	fmt.Println("========================================\n")

	// 创建 Coordinator
	coordinator := NewCoordinatorAgent()

	// 注册 Agent
	coordinator.RegisterAgent(NewQueryAgent())
	coordinator.RegisterAgent(NewDiagnosticAgent())
	coordinator.RegisterAgent(NewCustomAgent(
		"BudgetOptimizer",
		"自动预算优化 Agent",
		func(ctx context.Context, req AgentRequest) (*AgentResponse, error) {
			return &AgentResponse{
				Text: "✅ 预算已优化：总预算 ¥15000 → 按 ROI 分配",
			}, nil
		},
	))

	// 创建凭证管理器
	credMgr := NewCredentialManager()
	credMgr.Store("meta", "act_123456", map[string]string{
		"access_token": "EAAB...（实际从环境变量读取）",
	})
	fmt.Println("🔐 凭证管理: 已加载 meta/act_123456（从环境变量）\n")

	ctx := context.Background()
	baseContext := map[string]interface{}{
		"user_id": "user_123",
	}

	tests := []struct {
		message string
		want    string
	}{
		{"帮我查询 camp_789 的表现数据", "QueryAgent"},
		{"帮我优化所有广告组", "QueryAgent"},
		{"帮我检测一下有没有异常的广告组", "DiagnosticAgent"},
		{"帮我创建一个服装广告系列", "QueryAgent"},
		{"帮我优化预算分配", "CustomAgent"},
	}

	for i, tt := range tests {
		fmt.Printf("--- 测试 %d ---\n", i+1)
		fmt.Printf("📝 用户输入: %s\n", tt.message)

		req := AgentRequest{
			UserID:    "user_123",
			Message:   tt.message,
			Context:   baseContext,
			Channel:   "meta",
			AccountID: "act_123456",
		}

		resp, err := coordinator.Handle(ctx, req)
		if err != nil {
			fmt.Printf("❌ 错误: %v\n\n", err)
			continue
		}

		fmt.Printf("✅ Agent: %s\n", resp.Metadata["agent_name"])
		fmt.Printf("📋 结果: %s\n\n", resp.Text)
	}

	fmt.Println("========================================")
	fmt.Println("  演示完成!")
	fmt.Println("========================================")

	// 序列化输出
	fmt.Println("\n--- JSON 输出示例 ---")
	data, _ := json.MarshalIndent(coordinator, "", "  ")
	fmt.Printf("Coordinator: %s\n", string(data))
}
