# Agent 系统深度：MCP/技能/图编排/NL2AD 源码级

> 从 MCP 协议到图编排，逐行解析广告 Agent 系统核心

---

## 第一部分：MCP（Model Context Protocol）深度

### MCP 架构

```
MCP 三层架构：
┌─────────────────────────────────────────────────────────────────────┐
│  Transport 层（传输层）                                               │
│  • STDIO: 本地进程通信                                               │
│  • HTTP: 远程 HTTP 通信                                              │
│  • SSE: 服务端发送事件（Server-Sent Events）                          │
│                                                                     │
│  Protocol 层（协议层）                                               │
│  • Initialize: 握手协商                                             │
│  • Tools: 工具调用（List/Call）                                      │
│  • Resources: 资源访问                                               │
│  • Prompts: 提示词模板                                               │
│  • Sampling: LLM 采样                                                │
│                                                                     │
│  Implementation 层（实现层）                                          │
│  • Server: 暴露工具/资源/提示词                                      │
│  • Client: 调用工具/资源/提示词                                     │
│  • Host: 管理 MCP 生命周期（Hermes/Claude Desktop）                  │
└─────────────────────────────────────────────────────────────────────┘
```

### MCP Server 实现

```go
package mcp

import (
	"context"
	"encoding/json"
	"fmt"
	"net"
	"sync"
)

// MCPRequest MCP 请求
type MCPRequest struct {
	JSONRPC string          `json:"jsonrpc"`
	ID      json.RawMessage `json:"id"`
	Method  string          `json:"method"`
	Params  json.RawMessage `json:"params,omitempty"`
}

// MCPResponse MCP 响应
type MCPResponse struct {
	JSONRPC string      `json:"jsonrpc"`
	ID      json.RawMessage `json:"id"`
	Result  interface{} `json:"result,omitempty"`
	Error   *MCPError   `json:"error,omitempty"`
}

type MCPError struct {
	Code    int    `json:"code"`
	Message string `json:"message"`
}

// Tool MCP 工具
type Tool struct {
	Name        string          `json:"name"`
	Description string          `json:"description"`
	InputSchema json.RawMessage `json:"inputSchema"`
	Handler     func(context.Context, json.RawMessage) (interface{}, error)
}

// Resource MCP 资源
type Resource struct {
	URI         string          `json:"uri"`
	Name        string          `json:"name"`
	Description string          `json:"description"`
	MimeType    string          `json:"mimeType"`
	Read        func(context.Context) (string, error)
}

// MCPServer MCP 服务器
type MCPServer struct {
	version     string
	tools       map[string]*Tool
	resources   map[string]*Resource
	mu          sync.RWMutex
}

// NewMCPServer 创建 MCP 服务器
func NewMCPServer(version string) *MCPServer {
	return &MCPServer{
		version: version,
		tools:   make(map[string]*Tool),
		resources: make(map[string]*Resource),
	}
}

// AddTool 添加工具
func (s *MCPServer) AddTool(tool *Tool) {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.tools[tool.Name] = tool
}

// AddResource 添加资源
func (s *MCPServer) AddResource(resource *Resource) {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.resources[resource.URI] = resource
}

// HandleRequest 处理请求
func (s *MCPServer) HandleRequest(ctx context.Context, req MCPRequest) (*MCPResponse, error) {
	var resp MCPResponse
	resp.JSONRPC = "2.0"
	resp.ID = req.ID
	
	switch req.Method {
	case "initialize":
		result := map[string]interface{}{
			"protocolVersion": "2024-11-05",
			"serverInfo": map[string]string{
				"name":    "ad-platform-mcp",
				"version": s.version,
			},
			"capabilities": map[string]interface{}{
				"tools": map[string]interface{}{},
				"resources": map[string]interface{}{},
			},
		}
		resp.Result = result
		
	case "tools/list":
		tools := make([]map[string]interface{}, 0, len(s.tools))
		for name, tool := range s.tools {
			tools = append(tools, map[string]interface{}{
				"name":        name,
				"description": tool.Description,
				"inputSchema": json.RawMessage(tool.InputSchema),
			})
		}
		resp.Result = map[string]interface{}{"tools": tools}
		
	case "tools/call":
		var params struct {
			Name   string          `json:"name"`
			Args   json.RawMessage `json:"arguments"`
		}
		json.Unmarshal(req.Params, &params)
		
		tool, ok := s.tools[params.Name]
		if !ok {
			return &MCPResponse{
				JSONRPC: "2.0",
				ID:      req.ID,
				Error: &MCPError{
					Code:    -32601,
					Message: fmt.Sprintf("tool not found: %s", params.Name),
				},
			}, nil
		}
		
		result, err := tool.Handler(ctx, params.Args)
		if err != nil {
			return &MCPResponse{
				JSONRPC: "2.0",
				ID:      req.ID,
				Error: &MCPError{
					Code:    -32603,
					Message: err.Error(),
				},
			}, nil
		}
		
		resp.Result = result
		
	case "resources/list":
		resources := make([]map[string]interface{}, 0, len(s.resources))
		for uri, resource := range s.resources {
			resources = append(resources, map[string]interface{}{
				"uri":         uri,
				"name":        resource.Name,
				"description": resource.Description,
				"mimeType":    resource.MimeType,
			})
		}
		resp.Result = map[string]interface{}{"resources": resources}
		
	case "resources/read":
		var params struct {
			URI string `json:"uri"`
		}
		json.Unmarshal(req.Params, &params)
		
		resource, ok := s.resources[params.URI]
		if !ok {
			return &MCPResponse{
				JSONRPC: "2.0",
				ID:      req.ID,
				Error: &MCPError{
					Code:    -32602,
					Message: fmt.Sprintf("resource not found: %s", params.URI),
				},
			}, nil
		}
		
		content, err := resource.Read(ctx)
		if err != nil {
			return &MCPResponse{
				JSONRPC: "2.0",
				ID:      req.ID,
				Error: &MCPError{
					Code:    -32603,
					Message: err.Error(),
				},
			}, nil
		}
		
		resp.Result = map[string]interface{}{
			"contents": []map[string]interface{}{
				{"uri": params.URI, "text": content},
			},
		}
		
	default:
		return &MCPResponse{
			JSONRPC: "2.0",
			ID:      req.ID,
			Error: &MCPError{
				Code:    -32601,
				Message: fmt.Sprintf("method not found: %s", req.Method),
			},
		}, nil
	}
	
	return &resp, nil
}

// StartHTTPServer 启动 HTTP 服务器
func (s *MCPServer) StartHTTPServer(addr string) error {
	listener, err := net.Listen("tcp", addr)
	if err != nil {
		return err
	}
	
	http.HandleFunc("/mcp", func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost {
			http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
			return
		}
		
		var req MCPRequest
		if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
			http.Error(w, err.Error(), http.StatusBadRequest)
			return
		}
		
		ctx := r.Context()
		resp, err := s.HandleRequest(ctx, req)
		if err != nil {
			http.Error(w, err.Error(), http.StatusInternalServerError)
			return
		}
		
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(resp)
	})
	
	return http.Serve(listener, nil)
}
```

---

## 第二部分：技能系统

```go
package skill

// Skill 技能
type Skill struct {
	ID          string            `json:"id"`
	Name        string            `json:"name"`
	Description string            `json:"description"`
	Version     string            `json:"version"`
	Inputs      []SkillInput      `json:"inputs"`
	Outputs     []SkillOutput     `json:"outputs"`
	Execute     func(context.Context, map[string]interface{}) (map[string]interface{}, error)
}

type SkillInput struct {
	Name        string `json:"name"`
	Type        string `json:"type"` // string/number/boolean/object
	Description string `json:"description"`
	Required    bool   `json:"required"`
}

type SkillOutput struct {
	Name        string `json:"name"`
	Type        string `json:"type"`
	Description string `json:"description"`
}

// SkillRegistry 技能注册中心
type SkillRegistry struct {
	skills map[string]*Skill
	mu     sync.RWMutex
}

func NewSkillRegistry() *SkillRegistry {
	return &SkillRegistry{
		skills: make(map[string]*Skill),
	}
}

func (r *SkillRegistry) Register(skill *Skill) {
	r.mu.Lock()
	defer r.mu.Unlock()
	r.skills[skill.ID] = skill
}

func (r *SkillRegistry) Get(name string) (*Skill, bool) {
	r.mu.RLock()
	defer r.mu.RUnlock()
	skill, ok := r.skills[name]
	return skill, ok
}

func (r *SkillRegistry) Execute(ctx context.Context, name string, inputs map[string]interface{}) (map[string]interface{}, error) {
	skill, ok := r.skills[name]
	if !ok {
		return nil, fmt.Errorf("skill not found: %s", name)
	}
	
	return skill.Execute(ctx, inputs)
}
```

---

## 第三部分：图编排

```go
package orchestration

// Node 图节点
type Node struct {
	ID       string
	Type     string // tool/skill/router/condition
	Config   map[string]interface{}
	Next     []string
}

// Graph 编排图
type Graph struct {
	Nodes  map[string]*Node
	Start  string
	End    string
}

// Executor 执行器
type Executor struct {
	graph *Graph
	state map[string]interface{}
}

func (e *Executor) Execute(ctx context.Context) error {
	current := e.graph.Start
	
	for current != e.graph.End {
		node := e.graph.Nodes[current]
		
		// 执行节点
		result, err := e.executeNode(ctx, node)
		if err != nil {
			return err
		}
		
		// 更新状态
		e.state[node.ID] = result
		
		// 路由到下一个节点
		nextNode, err := e.route(ctx, node, result)
		if err != nil {
			return err
		}
		
		current = nextNode
	}
	
	return nil
}
```

---

## 第四部分：NL2AD

```go
package nl2ad

// NL2AD 自然语言创建广告
type NL2AD struct {
	llm        LLMClient
	policy     PolicyEngine
	templateDB TemplateDatabase
}

type Intent struct {
	Action    string
	Platform  string
	Campaign  string
	Budget    float64
	Targeting Targeting
	Creative  CreativeBrief
}

type Targeting struct {
	AgeRange  [2]int
	Genders   []string
	Locations []string
	Interests []string
}

type CreativeBrief struct {
	Title       string
	Description string
	VisualStyle string
	CTA         string
	BrandTone   string
}

func (n *NL2AD) ParseIntent(ctx context.Context, userInput string) (*Intent, error) {
	prompt := fmt.Sprintf(`
解析以下自然语言请求为结构化数据:
%s

返回 JSON:
{
  "action": "create|update|optimize",
  "platform": "facebook|google|tiktok",
  "campaign": "广告系列名称",
  "budget": 预算金额,
  "targeting": {
    "age_range": [最小年龄, 最大年龄],
    "genders": ["gender1"],
    "locations": ["country_code"],
    "interests": ["interest1"]
  },
  "creative": {
    "title": "标题",
    "description": "描述",
    "visual_style": "minimalist|colorful|lifestyle",
    "cta": "shop_now|learn_more",
    "brand_tone": "professional|casual|fun"
  }
}`, userInput)
	
	response, err := n.llm.Generate(ctx, prompt)
	if err != nil {
		return nil, err
	}
	
	intent := &Intent{}
	json.Unmarshal([]byte(response), intent)
	return intent, nil
}
```

---

## 第五部分：自测题

### Q1: MCP 的三层架构是什么？

**A**: Transport（传输层）/ Protocol（协议层）/ Implementation（实现层）。Transport 负责通信，Protocol 定义消息格式，Implementation 暴露工具/资源。

### Q2: 技能系统和 MCP 的关系？

**A**: 技能是 MCP 的工具的一种抽象。技能注册中心管理技能的生命周期，MCP Server 暴露技能给 LLM。

### Q3: 图编排的优势？

**A**: 可视化工作流、支持条件分支、并行执行、故障恢复、易于调试。

---

## 第六部分：生产实践

### 1. MCP 安全

```
MCP 安全要点：
1. 认证：JWT/OAuth 2.0
2. 限流：每分钟请求数限制
3. 审计：记录所有工具调用
4. 沙箱：工具执行在隔离环境
```

### 2. 技能管理

```
技能管理要点：
1. 版本控制：语义化版本号
2. 依赖管理：技能间依赖关系
3. 测试：单元测试 + 集成测试
4. 文档：使用说明 + 示例
```

### 3. 图编排

```
图编排要点：
1. 可视化编辑器：拖拽编排
2. 执行监控：实时查看进度
3. 故障恢复：自动重试 + 回滚
4. 性能优化：并行执行 + 缓存
```
