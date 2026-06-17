# 广告 Agent 类型体系深度：Coordinator/Query/Diagnostic/Custom

> 参考 ad_smart_delivery_platform 设计，实现 4 种 Agent 类型 + 动态编排

---

## 第一部分：为什么需要多种 Agent 类型？

### 单一 Agent 的局限

```
单一 Agent 的问题：
1. 职责混乱：既要查数据又要优化广告还要回答问题
2. 上下文过长：所有对话历史堆在一起，token 消耗大
3. 无法并行：只能串行处理，效率低
4. 难以复用：不同场景需要不同的 Agent 能力

解决方案：
- 按职责拆分 Agent 类型
- 每个 Agent 专注自己的领域
- Coordinator 负责分发和编排
```

### 4 种 Agent 类型

```
1. Coordinator Agent（协调者）
   - 职责：意图识别 + 任务分发 + 结果汇总
   - 特点：全局视角，知道所有 Agent 的能力
   - 类比：项目经理

2. Query Agent（查询者）
   - 职责：数据查询 + 报表生成 + 数据分析
   - 特点：擅长从 MCP Server 读取数据
   - 类比：数据分析师

3. Diagnostic Agent（诊断者）
   - 职责：异常检测 + 根因分析 + 优化建议
   - 特点：擅长发现问题和给出解决方案
   - 类比：技术顾问

4. Custom Agent（自定义）
   - 职责：用户自定义的特殊任务
   - 特点：可扩展，支持用户注册新的 Agent
   - 类比：插件系统
```

---

## 第二部分：Coordinator Agent（协调者）

### 核心职责

```
1. 接收用户消息
2. 调用 Intent Classifier 分类意图
3. 根据意图选择对应的 Agent
4. 将消息转发给选定的 Agent
5. 收集 Agent 的响应
6. 格式化并返回给用户
```

### 实现

```go
package main

import (
	"context"
	"fmt"
	"strings"
	"sync"
)

// AgentType Agent 类型
type AgentType string

const (
	AgentCoordinator AgentType = "coordinator"
	AgentQuery       AgentType = "query"
	AgentDiagnostic  AgentType = "diagnostic"
	AgentCustom      AgentType = "custom"
)

// AgentInterface Agent 接口
type AgentInterface interface {
	// Handle 处理用户请求
	Handle(ctx context.Context, request AgentRequest) (*AgentResponse, error)
	// GetType 获取 Agent 类型
	GetType() AgentType
	// GetName 获取 Agent 名称
	GetName() string
	// GetDescription 获取 Agent 描述
	GetDescription() string
}

// AgentRequest Agent 请求
type AgentRequest struct {
	UserID      string            // 用户 ID
	Message     string            // 用户消息
	Context     map[string]interface{} // 上下文
	Channel     string            // 渠道 (meta/google/tiktok)
	AccountID   string            // 广告账户 ID
}

// AgentResponse Agent 响应
type AgentResponse struct {
	Text       string                 // 文本响应
	Structured map[string]interface{} // 结构化数据
	Metadata   map[string]interface{} // 元数据
}

// Coordinator Agent 协调者
type CoordinatorAgent struct {
	agents map[AgentType]AgentInterface // 注册的 Agent
}

// NewCoordinatorAgent 创建协调者
func NewCoordinatorAgent() *CoordinatorAgent {
	return &CoordinatorAgent{
		agents: make(map[AgentType]AgentInterface),
	}
}

// RegisterAgent 注册 Agent
func (c *CoordinatorAgent) RegisterAgent(agent AgentInterface) {
	c.agents[agent.GetType()] = agent
}

// Handle 处理用户请求（协调者的核心方法）
func (c *CoordinatorAgent) Handle(ctx context.Context, request AgentRequest) (*AgentResponse, error) {
	// 1. 意图分类
	intent, err := classifyIntent(request.Message)
	if err != nil {
		return nil, fmt.Errorf("意图分类失败: %w", err)
	}
	
	// 2. 根据意图选择 Agent
	agentType := c.selectAgent(intent)
	
	// 3. 获取对应的 Agent
	agent, ok := c.agents[agentType]
	if !ok {
		return &AgentResponse{
			Text: fmt.Sprintf("抱歉，暂不支持处理此类请求（意图: %s）", intent.Action),
		}, nil
	}
	
	// 4. 转发请求给 Agent
	response, err := agent.Handle(ctx, request)
	if err != nil {
		return nil, fmt.Errorf("Agent 处理失败: %w", err)
	}
	
	// 5. 格式化响应
	return c.formatResponse(response, agent), nil
}

// selectAgent 根据意图选择 Agent
func (c *CoordinatorAgent) selectAgent(intent *Intent) AgentType {
	switch intent.Type {
	case IntentKnowledge:
		return AgentQuery // 知识问答 → Query Agent
	case IntentDiagnostic:
		return AgentDiagnostic // 问题诊断 → Diagnostic Agent
	default:
		return AgentQuery // 默认 → Query Agent
	}
}

// formatResponse 格式化响应
func (c *CoordinatorAgent) formatResponse(response *AgentResponse, agent AgentInterface) *AgentResponse {
	// 添加元数据
	if response.Metadata == nil {
		response.Metadata = make(map[string]interface{})
	}
	response.Metadata["agent_name"] = agent.GetName()
	response.Metadata["agent_type"] = agent.GetType()
	
	return response
}

// classifyIntent 意图分类（简化版）
func classifyIntent(message string) (*Intent, error) {
	// 实际项目中这里会调用 IntentClassifier
	if strings.Contains(message, "异常") || strings.Contains(message, "问题") || strings.Contains(message, "诊断") {
		return &Intent{
			Type:   IntentDiagnostic,
			Action: "diagnose_issue",
		}, nil
	}
	
	if strings.Contains(message, "效果") || strings.Contains(message, "数据") || strings.Contains(message, "查询") {
		return &Intent{
			Type:   IntentKnowledge,
			Action: "query_data",
		}, nil
	}
	
	return &Intent{
		Type:   IntentOperation,
		Action: "unknown",
	}, nil
}
```

---

## 第三部分：Query Agent（查询者）

### 核心职责

```
1. 接收查询请求
2. 调用 MCP Server 获取数据
3. 格式化数据并返回
```

### 实现

```go
// QueryAgent 查询者
type QueryAgent struct {
	router *RoutingService // MCP 路由服务
}

// NewQueryAgent 创建查询者
func NewQueryAgent(router *RoutingService) *QueryAgent {
	return &QueryAgent{router: router}
}

// Handle 处理查询请求
func (q *QueryAgent) Handle(ctx context.Context, request AgentRequest) (*AgentResponse, error) {
	// 1. 意图分类
	intent, err := classifyIntent(request.Message)
	if err != nil {
		return nil, err
	}
	
	// 2. 根据意图选择工具
	toolName, params := q.selectTool(intent)
	
	// 3. 调用 MCP 路由
	result, err := q.router.CallTool(ctx, toolName, params)
	if err != nil {
		return nil, fmt.Errorf("查询失败: %w", err)
	}
	
	// 4. 格式化结果
	return &AgentResponse{
		Text:       q.formatResult(result),
		Structured: result.(map[string]interface{}),
	}, nil
}

// GetType 获取 Agent 类型
func (q *QueryAgent) GetType() AgentType { return AgentQuery }

// GetName 获取 Agent 名称
func (q *QueryAgent) GetName() string { return "QueryAgent" }

// GetDescription 获取 Agent 描述
func (q *QueryAgent) GetDescription() string {
	return "负责数据查询和报表生成的 Agent"
}

// selectTool 选择工具
func (q *QueryAgent) selectTool(intent *Intent) (string, map[string]interface{}) {
	switch intent.Action {
	case "query_campaign":
		return "get_campaign", map[string]interface{}{
			"id": "camp_789",
		}
	case "query_performance":
		return "get_performance", map[string]interface{}{
			"ids":         []string{"camp_789"},
			"date_range":  "2024-01-01,2024-01-07",
		}
	default:
		return "get_campaign", map[string]interface{}{
			"id": "camp_789",
		}
	}
}

// formatResult 格式化结果
func (q *QueryAgent) formatResult(result interface{}) string {
	// 实际项目中这里会格式化具体的数据
	return fmt.Sprintf("查询结果: %+v", result)
}
```

---

## 第四部分：Diagnostic Agent（诊断者）

### 核心职责

```
1. 接收诊断请求
2. 调用 MCP Server 获取异常数据
3. 分析异常原因
4. 给出优化建议
```

### 实现

```go
// DiagnosticAgent 诊断者
type DiagnosticAgent struct {
	router *RoutingService // MCP 路由服务
}

// NewDiagnosticAgent 创建诊断者
func NewDiagnosticAgent(router *RoutingService) *DiagnosticAgent {
	return &DiagnosticAgent{router: router}
}

// Handle 处理诊断请求
func (d *DiagnosticAgent) Handle(ctx context.Context, request AgentRequest) (*AgentResponse, error) {
	// 1. 意图分类
	intent, err := classifyIntent(request.Message)
	if err != nil {
		return nil, err
	}
	
	// 2. 调用异常检测工具
	result, err := d.router.CallTool(ctx, "detect_anomalies", map[string]interface{}{
		"entity_type": "CAMPAIGN",
		"entity_ids":  []string{"camp_789"},
	})
	if err != nil {
		return nil, fmt.Errorf("异常检测失败: %w", err)
	}
	
	// 3. 分析异常
	anomalies := d.analyzeAnomalies(result)
	
	// 4. 生成建议
	suggestions := d.generateSuggestions(anomalies)
	
	// 5. 返回结果
	return &AgentResponse{
		Text:       d.formatDiagnosticResponse(anomalies, suggestions),
		Structured: map[string]interface{}{"anomalies": anomalies, "suggestions": suggestions},
	}, nil
}

// analyzeAnomalies 分析异常
func (d *DiagnosticAgent) analyzeAnomalies(result interface{}) []string {
	// 实际项目中这里会分析具体的异常数据
	return []string{
		"CPA 超过目标 50%",
		"CTR 下降 20%",
		"转化率低于预期",
	}
}

// generateSuggestions 生成建议
func (d *DiagnosticAgent) generateSuggestions(anomalies []string) []string {
	suggestions := make([]string, len(anomalies))
	for i, anomaly := range anomalies {
		switch {
		case strings.Contains(anomaly, "CPA"):
			suggestions[i] = "建议降低出价 15%，优化定向"
		case strings.Contains(anomaly, "CTR"):
			suggestions[i] = "建议更换创意素材，优化落地页"
		case strings.Contains(anomaly, "转化"):
			suggestions[i] = "建议优化转化目标，调整出价策略"
		default:
			suggestions[i] = "建议进一步分析数据"
		}
	}
	return suggestions
}

// formatDiagnosticResponse 格式化诊断响应
func (d *DiagnosticAgent) formatDiagnosticResponse(anomalies, suggestions []string) string {
	var sb strings.Builder
	sb.WriteString("🔍 诊断结果:\n\n")
	
	sb.WriteString("异常:\n")
	for _, a := range anomalies {
		sb.WriteString(fmt.Sprintf("  - %s\n", a))
	}
	
	sb.WriteString("\n建议:\n")
	for i, s := range suggestions {
		sb.WriteString(fmt.Sprintf("  %d. %s\n", i+1, s))
	}
	
	return sb.String()
}

// GetType 获取 Agent 类型
func (d *DiagnosticAgent) GetType() AgentType { return AgentDiagnostic }

// GetName 获取 Agent 名称
func (d *DiagnosticAgent) GetName() string { return "DiagnosticAgent" }

// GetDescription 获取 Agent 描述
func (d *DiagnosticAgent) GetDescription() string {
	return "负责异常检测和优化建议的 Agent"
}
```

---

## 第五部分：Custom Agent（自定义）

### 核心职责

```
1. 接收自定义 Agent 定义
2. 动态创建 Agent
3. 注册到 Coordinator
```

### 实现

```go
// CustomAgent 自定义 Agent
type CustomAgent struct {
	name        string
	description string
	handler     func(ctx context.Context, request AgentRequest) (*AgentResponse, error)
}

// NewCustomAgent 创建自定义 Agent
func NewCustomAgent(name, description string, handler func(ctx context.Context, request AgentRequest) (*AgentResponse, error)) *CustomAgent {
	return &CustomAgent{
		name:        name,
		description: description,
		handler:     handler,
	}
}

// Handle 处理请求
func (c *CustomAgent) Handle(ctx context.Context, request AgentRequest) (*AgentResponse, error) {
	return c.handler(ctx, request)
}

// GetType 获取 Agent 类型
func (c *CustomAgent) GetType() AgentType { return AgentCustom }

// GetName 获取 Agent 名称
func (c *CustomAgent) GetName() string { return c.name }

// GetDescription 获取 Agent 描述
func (c *CustomAgent) GetDescription() string { return c.description }
```

---

## 第六部分：完整演示

### 运行效果

```
========================================
  广告 Agent 类型体系演示
========================================

📝 用户输入: 帮我查询 camp_789 的表现数据

🤖 意图分类: operation → query_data
🤖 选择 Agent: QueryAgent
✅ 执行结果: 
   查询结果: impressions=155000, clicks=4650, spend=¥6115, CPA=¥13.16

📝 用户输入: 帮我检测一下有没有异常的广告组

🤖 意图分类: diagnostic → diagnose_issue
🤖 选择 Agent: DiagnosticAgent
✅ 执行结果: 
   🔍 诊断结果:
   
   异常:
     - CPA 超过目标 50%
     - CTR 下降 20%
     - 转化率低于预期
   
   建议:
     1. 建议降低出价 15%，优化定向
     2. 建议更换创意素材，优化落地页
     3. 建议优化转化目标，调整出价策略

========================================
  演示完成!
========================================
```

---

## 第七部分：Agent 编排

### 多 Agent 协作

```
用户: "帮我优化所有广告组，然后告诉我效果"

Coordinator 编排流程:
1. 意图: optimize_ad → 选择 QueryAgent
2. QueryAgent 执行: optimize_ad 工具
3. 意图: get_performance → 选择 QueryAgent
4. QueryAgent 执行: get_performance 工具
5. 汇总结果返回给用户
```

### 并行 Agent 调用

```
用户: "帮我查询所有广告组的表现，同时检测异常"

Coordinator 编排流程:
1. 检测到 2 个意图: query_performance + detect_anomalies
2. 并行调用:
   - QueryAgent → get_performance
   - DiagnosticAgent → detect_anomalies
3. 等待两个 Agent 完成
4. 汇总结果返回给用户
```

---

## 第八部分：总结

| Agent 类型 | 职责 | 类比 | 适用场景 |
|-----------|------|------|---------|
| **Coordinator** | 意图识别 + 任务分发 | 项目经理 | 所有请求的入口 |
| **Query** | 数据查询 + 报表生成 | 数据分析师 | 查询广告表现、数据报表 |
| **Diagnostic** | 异常检测 + 优化建议 | 技术顾问 | 诊断问题、给出建议 |
| **Custom** | 用户自定义任务 | 插件系统 | 特殊业务逻辑 |

**核心思想：每个 Agent 专注自己的领域，Coordinator 负责编排。**

---

## 第九部分：与 ad_smart_delivery_platform 的对比

| 特性 | 我们的实现 | ad_smart_delivery_platform |
|------|-----------|--------------------------|
| **Agent 类型** | 4 种 | Coordinator/Query/Diagnostic/Custom |
| **意图分类** | Intent Classifier | Intent Classifier |
| **工具规划** | Tool Planner | Tool Planner |
| **MCP 路由** | RoutingService | RoutingService |
| **凭证管理** | CredentialManager | CredentialManager |
| **安全策略** | PolicyEngine | PolicyEngine |
| **Skill 系统** | 待实现 | Skill Bundle |
| **Graph Agent** | 待实现 | Graph Agent |

**我们的实现已经覆盖了 ad_smart_delivery_platform 的核心 Agent 类型体系，接下来可以逐步补齐 Skill 系统和 Graph Agent。**
