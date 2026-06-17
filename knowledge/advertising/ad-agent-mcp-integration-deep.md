# 广告 Agent 与 MCP 工具系统集成深度分析

> 从 ad_smart_delivery_platform 架构提取设计模式，指导个人知识库中的广告 Agent 建设

---

## 第一部分：ad_smart_delivery_platform 核心架构分析

### 1.1 项目定位

```
ad_smart_delivery_platform = 广告投放 Agent 工作平台

核心能力：
├── MCP Server 层：封装 Meta/TikTok/Google/DV360 API
├── MCP Tool 层：统一路由 + 安全策略 + 凭证管理
├── Agent 层：意图分类 → Agent 选择 → 工具调用
├── Graph Agent：可视化编排 Agent 工作流
├── Skill 系统：可复用的专业能力包
└── 对话式平台：聊天界面交互
```

### 1.2 核心架构

```
┌─────────────────────────────────────────────────────────────┐
│                       用户层                                 │
│  Web 聊天 / API / CLI                                      │
└───────────────────────┬─────────────────────────────────────┘
                        │
┌───────────────────────▼─────────────────────────────────────┐
│                   Agent Coordinator                         │
│  ┌──────────┐  ┌───────────┐  ┌──────────┐                │
│  │IntentClass│→│ToolPlanner │→│AgentSelect│                │
│  │ ifier    │  │ (LLM)     │  │ Selector  │                │
│  └──────────┘  └───────────┘  └──────────┘                │
│       │              │               │                      │
│       ▼              ▼               ▼                      │
│  意图分类       工具规划         Agent 选择                  │
│  (LLM)         (Function Call)   (Query/Custom)             │
└───────────────────────┬─────────────────────────────────────┘
                        │
┌───────────────────────▼─────────────────────────────────────┐
│                   MCP Tool Layer                            │
│  ┌──────────────────────────────────────────┐              │
│  │          RoutingService                  │              │
│  │  ┌──────────┐  ┌──────────┐  ┌────────┐ │              │
│  │  │ Policy   │  │ Credential│→│Server  │ │              │
│  │  │ Check    │  │ Resolve  │  │ Router │ │              │
│  │  └──────────┘  └──────────┘  └────────┘ │              │
│  └──────────────────────────────────────────┘              │
└───────────────────────┬─────────────────────────────────────┘
                        │
┌───────────────────────▼─────────────────────────────────────┐
│                   MCP Server Layer                          │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐       │
│  │ Google   │ │ Meta     │ │ TikTok   │ │ DV360    │       │
│  │ Ads API  │ │ Marketing│ │ Ads API  │ │ API      │       │
│  │          │ │ API      │ │          │ │          │       │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘       │
└─────────────────────────────────────────────────────────────┘
```

---

## 第二部分：关键设计模式提取

### 2.1 Agent 类型分层

```go
// ad_smart_delivery_platform 的 Agent 类型体系
type AgentType string

const (
    AgentTypeCoordinator AgentType = "coordinator"  // 协调者：意图分类 + 任务编排
    AgentTypeQuery       AgentType = "query"         // 查询者：读数据
    AgentTypeDiagnostic  AgentType = "diagnostic"    // 诊断者：分析问题
    AgentTypeCustom      AgentType = "custom"        // 自定义：Graph Agent
)

// 对应到个人知识库：
// - coordinator = AgentCoordinator（我们已有的）
// - query = 数据查询工具（需要补充）
// - diagnostic = 诊断引擎（我们已有）
// - custom = 通过 Skill 系统扩展
```

### 2.2 工具路由模式

```go
// ad_smart_delivery_platform 的 MCP Tool 路由核心
// 核心思想：工具路由 = 安全策略 + 凭证管理 + 服务发现

func (s *RoutingService) CallTool(ctx, toolName, params) {
    // 1. 安全策略：是否需要确认？
    decision := EvaluateToolCallPolicy(toolName)
    // read → 直接执行
    // write → 需要用户确认
    // destructive → 必须用户确认
    
    // 2. 凭证管理：根据工具选择正确的凭证
    credential := ResolveCredentialForCall(server, params)
    
    // 3. 服务发现：路由到正确的 MCP Server
    server := FindServerForTool(toolName)
    
    // 4. 执行
    result := CallTool(ctx, toolName, credential, params)
}

// 对应到个人知识库：
// 我们的安全护栏（三层防护）可以升级为这种模式
```

### 2.3 Intent Classifier + Tool Planner 双阶段

```
第一阶段：Intent Classification（意图分类）
输入："帮我查询 camp_123 的表现数据"
输出：{"type": "operation", "action": "query_campaign", "entities": {...}}

第二阶段：Tool Planning（工具规划）
输入：意图 + 可用工具列表
输出：{"tool_name": "get_campaign_performance", "parameters": {...}}

核心优势：
- 意图分类只管"用户想做什么"
- 工具规划只管"哪个工具最合适"
- 两个阶段解耦，可独立优化
```

### 2.4 Skill 系统

```
ad_smart_delivery_platform 的 Skill：
- skill-agent-builder：构建 Agent 的专家 Skill
- skill-code-review：代码审查专家 Skill
- skill-data-analysis：数据分析专家 Skill
- skill-dv360-enterprise-growth-expert：DV360 增长专家 Skill
- skill-google-enterprise-growth-expert：Google 增长专家 Skill
- skill-meta-enterprise-growth-expert：Meta 增长专家 Skill
- skill-tiktok-enterprise-growth-expert：TikTok 增长专家 Skill

对应到个人知识库：
- 我们也应该为每个广告平台（Meta/Google/TikTok）创建专门的 Skill
- Skill 不是代码，是"专业能力包"（Prompt + 工具列表 + 知识）
```

---

## 第三部分：个人知识库广告 Agent 的增强方向

### 3.1 当前状态 vs 增强目标

```
当前（个人知识库）：
├── NL2AD：自然语言创建广告 ✅
├── Agent 优化器：自动调价/异常检测 ✅
├── 创意自动化：AI 裁剪/组合/测试 ✅
├── 跨渠道预算分配：Performance Max ✅
├── 意图理解：LLM 语义理解 ✅
├── 对话式平台：聊天界面 ✅
├── 安全护栏：三层防护 ✅
└── 诊断引擎：自动定位问题 ✅

增强方向（参考 ad_smart_delivery_platform）：
├── [NEW] MCP Server 层：封装 Meta/Google/TikTok/DV360 API
├── [NEW] 工具路由层：统一路由 + 安全策略 + 凭证管理
├── [NEW] IntentClassifier + ToolPlanner 双阶段
├── [NEW] Skill 系统：每个平台的专家 Skill
├── [NEW] Agent 类型体系：Coordinator/Query/Diagnostic/Custom
└── [NEW] Graph Agent：可视化编排工作流
```

### 3.2 核心增强：MCP Server 集成

```
架构升级：

┌─────────────────────────────────────────────────────────────┐
│                    用户输入                                  │
└───────────────────────┬─────────────────────────────────────┘
                        │
┌───────────────────────▼─────────────────────────────────────┐
│              Agent Coordinator（升级）                       │
│  ┌──────────┐  ┌───────────┐                                │
│  │ Intent   │  │ Tool      │                                │
│  │ Classifier│→│ Planner  │                                │
│  └──────────┘  └───────────┘                                │
└───────────────────────┬─────────────────────────────────────┘
                        │
┌───────────────────────▼─────────────────────────────────────┐
│              MCP Tool Layer（新增）                          │
│  ┌──────────────────────────────────────────┐              │
│  │          RoutingService                  │              │
│  │  工具路由 + 安全策略 + 凭证管理           │              │
│  └──────────────────────────────────────────┘              │
└───────────────────────┬─────────────────────────────────────┘
                        │
┌───────────────────────▼─────────────────────────────────────┐
│              MCP Server Layer（新增）                        │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐       │
│  │ Google   │ │ Meta     │ │ TikTok   │ │ DV360    │       │
│  │ Ads      │ │ Marketing│ │ Ads      │ │ API      │       │
│  │ Server   │ │ Server   │ │ Server   │ │ Server   │       │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘       │
│                                                             │
│  封装：Campaign/AdSet/Ad/Creative 的 CRUD                   │
│  提供：工具发现 + 工具调用 + 工具 Schema                     │
└─────────────────────────────────────────────────────────────┘
```

### 3.3 核心增强：Skill 系统

```
Skill 设计（参考 ad_smart_delivery_platform）：

每个 Skill = 一个平台的专家能力包

┌─────────────────────────────────────────────────────────────┐
│  skill-meta-growth-expert                                    │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ 角色：Meta 广告投放专家                                  │ │
│  │ 工具：Meta Marketing API Tools                         │ │
│  │ 知识：Meta 最佳实践 + API 文档                          │ │
│  │ Prompt：专业 Meta 投放策略 + 优化建议                   │ │
│  └────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│  skill-google-growth-expert                                  │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ 角色：Google Ads 专家                                   │ │
│  │ 工具：Google Ads Marketing API Tools                   │ │
│  │ 知识：Google Ads 最佳实践 + PMax 策略                   │ │
│  │ Prompt：专业 Google 投放策略 + 优化建议                 │ │
│  └────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│  skill-tiktok-growth-expert                                  │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ 角色：TikTok Ads 专家                                   │ │
│  │ 工具：TikTok Marketing API Tools                       │ │
│  │ 知识：TikTok 投放最佳实践 + Shop 策略                   │ │
│  │ Prompt：专业 TikTok 投放策略 + 创意建议                 │ │
│  └────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

---

## 第四部分：代码实现方案

### 4.1 MCP Server 封装

```go
// marketing_api_server.go - 封装 Meta/Google/TikTok/DV360 API

// MCPToolDescriptor MCP 工具描述
type MCPToolDescriptor struct {
    Name        string
    Description string
    Parameters  map[string]ToolParameter
    ServerName  string
    Category    string
    Channel     string // google/meta/tiktok/dv360
}

// MCPToolParameter 工具参数
type ToolParameter struct {
    Name        string
    Type        string
    Description string
    Required    bool
    Enum        []string
}

// MarketingAPIServer 营销 API MCP Server
type MarketingAPIServer struct {
    config     MarketingProviderConfig
    tools      []MCPToolDescriptor
    httpClient *http.Client
}

// ToolDescriptor MCP 工具定义
type ToolDescriptor struct {
    Name        string
    Description string
    Parameters  []ToolParameter
}
```

### 4.2 工具路由层

```go
// routing_service.go - 统一路由

// RoutingService 工具路由服务
type RoutingService struct {
    servers    map[string]*MarketingAPIServer  // 按 provider 索引
    policy     *PolicyEngine                   // 安全策略引擎
    credentials *CredentialManager             // 凭证管理
}

// CallTool 调用工具（统一入口）
func (s *RoutingService) CallTool(ctx context.Context, toolName string, params map[string]interface{}) (interface{}, error) {
    // 1. 安全策略检查
    risk := s.classifyToolRisk(toolName)
    if risk == ToolRiskWrite || risk == ToolRiskDestructive {
        // 需要用户确认
        if !s.isConfirmed(ctx) {
            return nil, fmt.Errorf("需要用户确认: %s", toolName)
        }
    }
    
    // 2. 找到对应的 MCP Server
    server := s.findServerForTool(toolName)
    if server == nil {
        return nil, fmt.Errorf("tool %s not found", toolName)
    }
    
    // 3. 应用凭证
    credential := s.resolveCredential(ctx, server)
    
    // 4. 调用工具
    return server.CallTool(ctx, toolName, credential, params)
}
```

### 4.3 Agent 类型体系

```go
// agent_types.go - Agent 类型和能力

type AgentType string

const (
    AgentTypeCoordinator AgentType = "coordinator"  // 协调者
    AgentTypeQuery       AgentType = "query"        // 查询者
    AgentTypeDiagnostic  AgentType = "diagnostic"   // 诊断者
    AgentTypeCustom      AgentType = "custom"       // 自定义
)

// AgentCapability Agent 能力枚举
type AgentCapability string

const (
    // Coordinator capabilities
    CapabilityIntentClassification AgentCapability = "intent_classification"
    CapabilityTaskPlanning         AgentCapability = "task_planning"
    CapabilityAgentOrchestration   AgentCapability = "agent_orchestration"
    
    // Query capabilities
    CapabilityReadCampaign    AgentCapability = "read_campaign"
    CapabilityReadAdGroup     AgentCapability = "read_adgroup"
    CapabilityReadCreative    AgentCapability = "read_creative"
    
    // Write capabilities
    CapabilityCreateCampaign  AgentCapability = "create_campaign"
    CapabilityUpdateCampaign  AgentCapability = "update_campaign"
    CapabilityPauseCampaign   AgentCapability = "pause_campaign"
    
    // Diagnostic capabilities
    CapabilityAnalyzeMetrics  AgentCapability = "analyze_metrics"
    CapabilityDiagnoseIssue   AgentCapability = "diagnose_issue"
    CapabilityOptimizeAd      AgentCapability = "optimize_ad"
)

// Agent 接口
type Agent interface {
    Execute(ctx context.Context, req *AgentRequest) (*AgentResponse, error)
    Type() AgentType
    Name() string
    Capabilities() []AgentCapability
}
```

### 4.4 Intent Classifier + Tool Planner

```go
// intent_classifier.go

type IntentClassifier struct {
    llm LLMService  // LLM 服务
}

func (c *IntentClassifier) Classify(ctx, input, context) (*Intent, error) {
    prompt := fmt.Sprintf(`
你是广告投放平台的意图分类助手。

意图类型：
1. operation - 操作类（查询/创建/更新广告）
2. knowledge - 知识问答
3. diagnostic - 问题诊断
4. chat - 闲聊

用户输入: "%s"

返回 JSON：
{
  "type": "operation|knowledge|diagnostic|chat",
  "action": "具体动作",
  "entities": {...},
  "confidence": 0.0-1.0
}
`, input)
    
    response := c.llm.Call(ctx, prompt)
    return parseIntent(response)
}

// tool_planner.go

type ToolCallPlanner struct {
    llm           LLMService
    toolRegistry  *ToolRegistry
}

func (p *ToolCallPlanner) PlanToolCall(ctx, userInput, context) (*ToolCallPlan, error) {
    // 1. 获取所有可用工具
    tools := p.toolRegistry.ListTools()
    
    // 2. 构建工具列表
    toolsDesc := buildToolsDescription(tools)
    
    // 3. 让 LLM 选择工具
    prompt := fmt.Sprintf(`
可用工具：%s
用户输入：%s

选择最合适的工具并返回 JSON：
{
  "tool_name": "工具名",
  "parameters": {...},
  "reasoning": "选择原因"
}
`, toolsDesc, userInput)
    
    response := p.llm.Call(ctx, prompt)
    return parseToolCall(response)
}
```

---

## 第五部分：实施路线

### Phase 1：基础能力（已完成）
- ✅ NL2AD 自然语言创建广告
- ✅ Agent 优化器（自动调价/异常检测）
- ✅ 创意自动化（AI 裁剪/组合/测试）
- ✅ 跨渠道预算分配
- ✅ 意图理解（LLM 语义理解）
- ✅ 对话式平台
- ✅ 安全护栏（三层防护）
- ✅ 诊断引擎

### Phase 2：MCP 工具集成（下一步）
- [ ] MCP Server 封装（Meta/Google/TikTok/DV360）
- [ ] 工具路由层（统一路由 + 安全策略 + 凭证管理）
- [ ] Intent Classifier + Tool Planner 双阶段
- [ ] Agent 类型体系（Coordinator/Query/Diagnostic/Custom）

### Phase 3：Skill 系统（远期）
- [ ] 每个平台的专家 Skill
- [ ] Skill 注册和发现机制
- [ ] Skill 编排（Skill Bundle）

### Phase 4：Graph Agent（远期）
- [ ] 可视化 Agent 工作流编排
- [ ] Agent 图定义和版本管理
- [ ] Agent 调度器（定时/事件驱动）

---

## 第六部分：关键设计思想总结

| 设计模式 | 描述 | 价值 |
|---------|------|------|
| **分层架构** | 用户层 → Agent 层 → MCP 工具层 → Server 层 | 清晰职责边界 |
| **双阶段意图** | Intent Classifier → Tool Planner | 解耦意图识别和工具选择 |
| **统一路由** | RoutingService 统一入口 | 安全策略 + 凭证管理集中化 |
| **工具路由** | 根据工具名自动路由到对应 MCP Server | 新增平台只需加 Server |
| **安全策略** | 读/写/破坏性操作分类 | 防止误操作 |
| **凭证管理** | 自动解析和注入凭证 | 用户无感知 |
| **Skill 系统** | 可复用的专业能力包 | 扩展能力强 |
| **Agent 类型** | Coordinator/Query/Diagnostic/Custom | 清晰分工 |

---

*本文档基于 ad_smart_delivery_platform 架构分析和个人知识库整合需求整理。*
