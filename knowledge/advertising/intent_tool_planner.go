package main

import (
	"context"
	"encoding/json"
	"fmt"
	"strings"
)

// ============================================================
// Intent Classifier + Tool Planner 双阶段
// ============================================================

// ToolDescriptor MCP 工具描述（前向声明）
type ToolDescriptor struct {
	Name        string
	Description string
	Parameters  []ToolParameter
	ServerName  string
	Category    string
	Channel     string
}

// ToolParameter 工具参数（前向声明）
type ToolParameter struct {
	Name        string
	Type        string
	Description string
	Required    bool
}

// RoutingService 路由服务（前向声明）
type RoutingService struct{}

func (r *RoutingService) CallTool(ctx context.Context, toolName string, params map[string]interface{}) (interface{}, error) {
	return nil, fmt.Errorf("mock call: %s", toolName)
}

func NewRoutingService(fallback interface{}) *RoutingService {
	return &RoutingService{}
}

// DefaultRecorder 默认记录器（前向声明）
type DefaultRecorder struct{}

// IntentType 意图类型
type IntentType string

const (
	IntentOperation IntentType = "operation"
	IntentKnowledge IntentType = "knowledge"
	IntentDiagnostic IntentType = "diagnostic"
	IntentChat      IntentType = "chat"
)

// Intent 意图
type Intent struct {
	Type               IntentType         `json:"type"`
	Confidence         float64            `json:"confidence"`
	Action             string             `json:"action"`
	ShouldInheritCtx   bool               `json:"should_inherit_context"`
	Entities           map[string]string  `json:"entities"`
	Channel            string             `json:"channel"`
}

// LLMService LLM 服务接口
type LLMService interface {
	Call(ctx context.Context, prompt string) (string, error)
}

// MockLLMService 模拟 LLM 服务
type MockLLMService struct{}

func (m *MockLLMService) Call(ctx context.Context, prompt string) (string, error) {
	// 判断是意图分类还是工具规划
	if strings.Contains(prompt, "**意图分类结果：**") {
		// 工具规划 → 根据意图返回对应的工具
		if strings.Contains(prompt, "动作: optimize_ad") {
			return `{"tool_name":"optimize_ad","parameters":{"account_id":"act_123456"},"reasoning":"用户想优化广告组表现"}`, nil
		}
		if strings.Contains(prompt, "动作: diagnose_issue") {
			return `{"tool_name":"detect_anomalies","parameters":{"entity_type":"CAMPAIGN","entity_ids":["camp_789"]},"reasoning":"用户想检测异常"}`, nil
		}
		if strings.Contains(prompt, "动作: query_campaign") {
			return `{"tool_name":"get_campaign","parameters":{"id":"camp_789","fields":"name,status,impressions,clicks,conversions,spend"},"reasoning":"用户想查询广告系列表现数据"}`, nil
		}
		if strings.Contains(prompt, "动作: create_campaign") {
			return `{"tool_name":"create_campaign","parameters":{"name":"新广告系列","objective":"CONVERSIONS","daily_budget":500},"reasoning":"用户想创建广告系列"}`, nil
		}
		if strings.Contains(prompt, "动作: get_performance") {
			return `{"tool_name":"get_performance","parameters":{"ids":["camp_789"],"date_range":"2024-01-01,2024-01-07"},"reasoning":"用户想查看表现数据"}`, nil
		}
		// 默认 fallback
		return `{"tool_name":"get_campaign","parameters":{"id":"camp_default"},"reasoning":"默认工具"}`, nil
	}
	
	// 意图分类响应
	if strings.Contains(prompt, "意图分类助手") {
		input := extractInput(prompt)
		
		if strings.Contains(input, "查询") || strings.Contains(input, "查看") || strings.Contains(input, "获取") {
			return `{"type":"operation","confidence":0.95,"action":"query_campaign","should_inherit_context":false,"entities":{"account_id":"act_123456","campaign_id":"camp_789"},"channel":"meta"}`, nil
		}
		
		if strings.Contains(input, "创建") || strings.Contains(input, "新建") {
			return `{"type":"operation","confidence":0.92,"action":"create_campaign","should_inherit_context":false,"entities":{"account_id":"act_123456","name":"新广告系列","objective":"CONVERSIONS"},"channel":"meta"}`, nil
		}
		
		if strings.Contains(input, "优化") || strings.Contains(input, "调整") {
			return `{"type":"operation","confidence":0.88,"action":"optimize_ad","should_inherit_context":false,"entities":{"account_id":"act_123456"},"channel":"meta"}`, nil
		}
		
		if strings.Contains(input, "效果") || strings.Contains(input, "表现") || strings.Contains(input, "数据") {
			return `{"type":"operation","confidence":0.90,"action":"get_performance","should_inherit_context":false,"entities":{"account_id":"act_123456","date_range":"2024-01-01,2024-01-07"},"channel":"meta"}`, nil
		}
		
		if strings.Contains(input, "异常") || strings.Contains(input, "问题") || strings.Contains(input, "诊断") {
			return `{"type":"diagnostic","confidence":0.85,"action":"diagnose_issue","should_inherit_context":false,"entities":{"account_id":"act_123456"},"channel":"meta"}`, nil
		}
		
		if strings.Contains(input, "你好") || strings.Contains(input, "嗨") || strings.Contains(input, "hello") {
			return `{"type":"chat","confidence":0.98,"action":"chat","should_inherit_context":false,"entities":{},"channel":""}`, nil
		}
		
		// fallback
		return `{"type":"operation","confidence":0.50,"action":"unknown","should_inherit_context":false,"entities":{},"channel":""}`, nil
	}
	
	// 默认返回
	return `{
		"type": "operation",
		"confidence": 0.50,
		"action": "unknown",
		"should_inherit_context": false,
		"entities": {},
		"channel": ""
	}`, nil
}

// extractInput 从 prompt 提取用户输入
func extractInput(prompt string) string {
	prefixes := []string{"用户输入：", "用户输入:", "**用户输入：**", "**用户输入:**"}
	for _, prefix := range prefixes {
		idx := strings.Index(prompt, prefix)
		if idx != -1 {
			return prompt[idx+len(prefix):]
		}
	}
	return prompt
}

// IntentClassifier 意图分类器
type IntentClassifier struct {
	llm LLMService
}

// NewIntentClassifier 创建意图分类器
func NewIntentClassifier(llm LLMService) *IntentClassifier {
	return &IntentClassifier{llm: llm}
}

// Classify 分类用户意图
func (c *IntentClassifier) Classify(ctx context.Context, input string, context map[string]interface{}) (*Intent, error) {
	if c.llm == nil {
		return nil, fmt.Errorf("LLM service is nil")
	}
	
	prompt := c.buildPrompt(input, context)
	response, err := c.llm.Call(ctx, prompt)
	if err != nil {
		return nil, fmt.Errorf("LLM call failed: %w", err)
	}
	
	intent, err := c.parseResponse(response)
	if err != nil {
		// 降级：返回默认意图
		return c.defaultIntent(input), nil
	}
	
	return intent, nil
}

// buildPrompt 构建分类提示
func (c *IntentClassifier) buildPrompt(input string, context map[string]interface{}) string {
	contextStr := ""
	if len(context) > 0 {
		if lastAction, ok := context["last_action"].(string); ok {
			contextStr += fmt.Sprintf("\n上一次操作：%s", lastAction)
		}
		if lastParams, ok := context["last_parameters"].(map[string]interface{}); ok {
			contextStr += fmt.Sprintf("\n上一次参数：%v", lastParams)
		}
	}
	
	return fmt.Sprintf(`你是一个广告投放平台的意图分类助手。请分析用户输入，判断意图类型。

意图类型：
1. operation - 操作类（查询、创建、更新广告）
2. knowledge - 知识问答（如何使用、最佳实践、概念解释）
3. diagnostic - 问题诊断（CTR低、CPC高、转化率下降等问题分析）
4. chat - 闲聊（问候、感谢等）

用户输入：%s
%s

请返回 JSON 格式（仅返回 JSON，不要其他内容）：
{
  "type": "operation|knowledge|diagnostic|chat",
  "confidence": 0.0-1.0,
  "action": "具体动作（如 query_campaign、create_campaign 等）",
  "should_inherit_context": true|false,
  "entities": {
    "account_id": "账户ID（如果提到）",
    "campaign_id": "广告系列ID",
    "campaign_name": "广告系列名称",
    "date_range": "日期范围",
    ...其他实体
  },
  "channel": "google|meta|tiktok（如果提到）"
}

should_inherit_context 判断规则：
- true: 用户想在上一次操作的基础上继续（如"第二页"、"继续"、"下一页"、"只看启用的"）
- false: 新的独立操作`, input, contextStr)
}

// parseResponse 解析响应
func (c *IntentClassifier) parseResponse(response string) (*Intent, error) {
	var intent Intent
	err := json.Unmarshal([]byte(response), &intent)
	if err != nil {
		return nil, err
	}
	return &intent, nil
}

// defaultIntent 默认意图
func (c *IntentClassifier) defaultIntent(input string) *Intent {
	return &Intent{
		Type:               IntentOperation,
		Confidence:         0.5,
		Action:             "unknown",
		ShouldInheritCtx:   false,
		Entities:           map[string]string{"input": input},
		Channel:            "",
	}
}

// ============================================================
// Tool Planner - 工具调用规划器
// ============================================================

// ToolCallPlan 工具调用计划
type ToolCallPlan struct {
	ToolName   string                 `json:"tool_name"`
	Parameters map[string]interface{} `json:"parameters"`
	Reasoning  string                 `json:"reasoning"`
}

// ToolRegistry 工具注册表
type ToolRegistry struct {
	tools map[string]ToolDescriptor
}

// NewToolRegistry 创建工具注册表
func NewToolRegistry() *ToolRegistry {
	return &ToolRegistry{
		tools: make(map[string]ToolDescriptor),
	}
}

// RegisterTool 注册工具
func (r *ToolRegistry) RegisterTool(tool ToolDescriptor) {
	r.tools[tool.Name] = tool
}

// ListTools 列出所有工具
func (r *ToolRegistry) ListTools() []ToolDescriptor {
	var tools []ToolDescriptor
	for _, tool := range r.tools {
		tools = append(tools, tool)
	}
	return tools
}

// GetTool 获取工具
func (r *ToolRegistry) GetTool(name string) (*ToolDescriptor, bool) {
	tool, ok := r.tools[name]
	return &tool, ok
}

// ToolCallPlanner 工具调用规划器
type ToolCallPlanner struct {
	llm          LLMService
	toolRegistry *ToolRegistry
}

// NewToolCallPlanner 创建工具规划器
func NewToolCallPlanner(llm LLMService, registry *ToolRegistry) *ToolCallPlanner {
	return &ToolCallPlanner{
		llm:          llm,
		toolRegistry: registry,
	}
}

// PlanToolCall 规划工具调用
func (p *ToolCallPlanner) PlanToolCall(ctx context.Context, userInput string, intent *Intent, context map[string]interface{}) (*ToolCallPlan, error) {
	// 1. 获取所有可用工具
	allTools := p.toolRegistry.ListTools()
	if len(allTools) == 0 {
		return nil, fmt.Errorf("no tools available")
	}
	
	// 2. 构建工具列表描述
	toolsDesc := p.buildToolsDescription(allTools)
	
	// 3. 构建提示
	prompt := p.buildToolPlanningPrompt(userInput, intent, toolsDesc, context)
	
	// 4. 调用 LLM
	response, err := p.llm.Call(ctx, prompt)
	if err != nil {
		return nil, fmt.Errorf("LLM call failed: %w", err)
	}
	
	// 5. 解析响应
	plan, err := p.parseToolCallResponse(response)
	if err != nil {
		// 降级：根据意图选择默认工具
		fmt.Printf("   ⚠️  LLM 解析失败，使用默认工具: %v\n", err)
		return p.defaultToolPlan(intent), nil
	}
	
	return plan, nil
}

// buildToolsDescription 构建工具描述
func (p *ToolCallPlanner) buildToolsDescription(tools []ToolDescriptor) string {
	var sb strings.Builder
	for _, tool := range tools {
		sb.WriteString(fmt.Sprintf("- **%s**: %s\n", tool.Name, tool.Description))
		sb.WriteString("  参数:\n")
		for _, param := range tool.Parameters {
			required := ""
			if param.Required {
				required = " (必填)"
			}
			sb.WriteString(fmt.Sprintf("    - %s (%s)%s: %s\n", param.Name, param.Type, required, param.Description))
		}
		sb.WriteString("\n")
	}
	return sb.String()
}

// buildToolPlanningPrompt 构建工具规划提示
func (p *ToolCallPlanner) buildToolPlanningPrompt(userInput string, intent *Intent, toolsDesc string, context map[string]interface{}) string {
	contextStr := ""
	if len(context) > 0 {
		for k, v := range context {
			contextStr += fmt.Sprintf("%s: %v\n", k, v)
		}
	}
	
	return fmt.Sprintf(`你是一个广告投放平台的智能助手。根据用户的输入和意图，选择合适的 MCP 工具并提取参数。

**意图分类结果：**
- 类型: %s
- 动作: %s
- 置信度: %.2f

**可用工具：**%s

**用户输入：** %s

**上下文：** %s

**任务：**
1. 分析用户输入，识别意图
2. 从用户输入中提取关键信息：
   - 账户 ID (account_id)
   - 广告系列 ID (campaign_id)
   - 广告组 ID (ad_group_id)
   - 其他相关参数
3. 选择最合适的工具
4. 返回 JSON 格式（仅返回 JSON，不要其他内容）：

{
  "tool_name": "工具名称",
  "parameters": {
    "param1": "value1",
    "param2": "value2"
  },
  "reasoning": "选择该工具的原因"
}`,
		intent.Type, intent.Action, intent.Confidence,
		toolsDesc, userInput, contextStr)
}

// parseToolCallResponse 解析工具调用响应
func (p *ToolCallPlanner) parseToolCallResponse(response string) (*ToolCallPlan, error) {
	var plan ToolCallPlan
	err := json.Unmarshal([]byte(response), &plan)
	if err != nil {
		return nil, err
	}
	return &plan, nil
}

// defaultToolPlan 默认工具计划
func (p *ToolCallPlanner) defaultToolPlan(intent *Intent) *ToolCallPlan {
	switch intent.Action {
	case "query_campaign":
		return &ToolCallPlan{
			ToolName: "get_campaign",
			Parameters: map[string]interface{}{
				"id": "camp_default",
			},
			Reasoning: "默认查询广告系列",
		}
	case "create_campaign":
		return &ToolCallPlan{
			ToolName: "create_campaign",
			Parameters: map[string]interface{}{
				"name":     "新广告系列",
				"objective": "CONVERSIONS",
			},
			Reasoning: "默认创建广告系列",
		}
	case "optimize_ad":
		return &ToolCallPlan{
			ToolName: "optimize_ad",
			Parameters: map[string]interface{}{
				"account_id": "act_default",
			},
			Reasoning: "默认优化广告",
		}
	case "get_performance":
		return &ToolCallPlan{
			ToolName: "get_performance",
			Parameters: map[string]interface{}{
				"ids":         []string{"camp_default"},
				"date_range":  "2024-01-01,2024-01-07",
			},
			Reasoning: "默认查询表现数据",
		}
	case "diagnose_issue":
		return &ToolCallPlan{
			ToolName: "detect_anomalies",
			Parameters: map[string]interface{}{
				"entity_type": "CAMPAIGN",
				"entity_ids":  []string{"camp_default"},
			},
			Reasoning: "默认异常检测",
		}
	default:
		return &ToolCallPlan{
			ToolName:   "unknown",
			Parameters: map[string]interface{}{},
			Reasoning:  "未知操作",
		}
	}
}

// ============================================================
// 完整对话流程演示
// ============================================================

// ConversationFlow 对话流程
type ConversationFlow struct {
	classifier *IntentClassifier
	planner    *ToolCallPlanner
	router     *RoutingService
	recorder   *DefaultRecorder
}

// NewConversationFlow 创建对话流程
func NewConversationFlow(router *RoutingService) *ConversationFlow {
	// 初始化 LLM 服务
	llm := &MockLLMService{}
	
	// 初始化工具注册表
	registry := NewToolRegistry()
	
	// 注册一些示例工具
	registry.RegisterTool(ToolDescriptor{
		Name:        "get_campaign",
		Description: "查询广告系列详情",
		Parameters: []ToolParameter{
			{Name: "id", Type: "string", Description: "广告系列 ID", Required: true},
			{Name: "fields", Type: "string", Description: "要返回的字段", Required: false},
		},
		ServerName: "Meta Marketing API MCP Server",
		Category:   "read",
		Channel:    "meta",
	})
	
	registry.RegisterTool(ToolDescriptor{
		Name:        "create_campaign",
		Description: "创建广告系列",
		Parameters: []ToolParameter{
			{Name: "name", Type: "string", Description: "广告系列名称", Required: true},
			{Name: "objective", Type: "string", Description: "广告目标", Required: true},
			{Name: "daily_budget", Type: "number", Description: "日预算", Required: false},
		},
		ServerName: "Meta Marketing API MCP Server",
		Category:   "write",
		Channel:    "meta",
	})
	
	registry.RegisterTool(ToolDescriptor{
		Name:        "get_performance",
		Description: "获取广告表现数据",
		Parameters: []ToolParameter{
			{Name: "ids", Type: "array", Description: "广告组 ID 列表", Required: true},
			{Name: "date_range", Type: "string", Description: "日期范围", Required: true},
		},
		ServerName: "Meta Marketing API MCP Server",
		Category:   "read",
		Channel:    "meta",
	})
	
	registry.RegisterTool(ToolDescriptor{
		Name:        "detect_anomalies",
		Description: "检测广告异常",
		Parameters: []ToolParameter{
			{Name: "entity_type", Type: "string", Description: "实体类型", Required: true},
			{Name: "entity_ids", Type: "array", Description: "实体 ID 列表", Required: true},
		},
		ServerName: "Meta Marketing API MCP Server",
		Category:   "read",
		Channel:    "meta",
	})
	
	return &ConversationFlow{
		classifier: NewIntentClassifier(llm),
		planner:    NewToolCallPlanner(llm, registry),
		router:     router,
		recorder:   &DefaultRecorder{},
	}
}

// ProcessMessage 处理用户消息
func (cf *ConversationFlow) ProcessMessage(ctx context.Context, userInput string, context map[string]interface{}) (interface{}, error) {
	fmt.Printf("\n📝 用户输入: %s\n\n", userInput)
	
	// 阶段 1: 意图分类
	fmt.Println("🔍 阶段 1: 意图分类")
	intent, err := cf.classifier.Classify(ctx, userInput, context)
	if err != nil {
		return nil, err
	}
	
	fmt.Printf("   意图类型: %s\n", intent.Type)
	fmt.Printf("   动作: %s\n", intent.Action)
	fmt.Printf("   置信度: %.2f\n", intent.Confidence)
	fmt.Printf("   实体: %+v\n\n", intent.Entities)
	
	// 阶段 2: 工具规划
	fmt.Println("🔧 阶段 2: 工具规划")
	plan, err := cf.planner.PlanToolCall(ctx, userInput, intent, context)
	if err != nil {
		return nil, err
	}
	
	fmt.Printf("   工具: %s\n", plan.ToolName)
	fmt.Printf("   参数: %+v\n", plan.Parameters)
	fmt.Printf("   理由: %s\n\n", plan.Reasoning)
	
	// 阶段 3: 工具执行
	fmt.Println("⚙️  阶段 3: 工具执行")
	result, err := cf.router.CallTool(ctx, plan.ToolName, plan.Parameters)
	if err != nil {
		fmt.Printf("   ❌ 错误: %v\n", err)
		return nil, err
	}
	
	fmt.Printf("   ✅ 执行成功\n")
	fmt.Printf("   结果: %+v\n\n", result)
	
	return result, nil
}

// ============================================================
// 演示入口
// ============================================================

func main() {
	fmt.Println("========================================")
	fmt.Println("  广告 Agent 双阶段意图 + 工具规划演示")
	fmt.Println("========================================")
	
	// 创建路由服务
	router := NewRoutingService(nil)
	
	// 创建对话流程
	flow := NewConversationFlow(router)
	
	ctx := context.Background()
	context := map[string]interface{}{
		"user_id": "user_123",
		"account_id": "act_123456",
	}
	
	// 演示 1: 查询广告系列
	flow.ProcessMessage(ctx, "帮我查询 camp_789 的广告系列表现数据", context)
	
	// 演示 2: 创建广告系列
	flow.ProcessMessage(ctx, "帮我创建一个服装广告系列，目标转化，预算500元/天", context)
	
	// 演示 3: 优化广告
	flow.ProcessMessage(ctx, "帮我优化所有广告组表现", context)
	
	// 演示 4: 查询表现
	flow.ProcessMessage(ctx, "查看过去 7 天的广告效果数据", context)
	
	// 演示 5: 异常检测
	flow.ProcessMessage(ctx, "帮我检测一下有没有异常的广告组", context)
	
	fmt.Println("\n========================================")
	fmt.Println("  演示完成!")
	fmt.Println("========================================")
}
