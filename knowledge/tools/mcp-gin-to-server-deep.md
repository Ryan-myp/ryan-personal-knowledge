# MCP 工具技能：DAP Agent Gin Web 到 MCP Server 迁移

> 来源：dap 项目 devserver
> 状态：基于代码实现蒸馏
> 蒸馏日期：2026-06-18

---

## 第一部分：DAP Agent 架构

### Gin Web 服务

```
DAP Agent Gin Web 服务：
┌─────────────────────────────────────────────────────────────────────┐
│ 1. 路由管理                                                          │
│    ├── HTTP 端点：RESTful API                                       │
│    ├── 中间件：认证/日志/错误处理                                   │
│    └── 请求处理：Controller 层                                      │
│                                                                     │
│ 2. 服务注册                                                          │
│    ├── 依赖注入：Service 层注册                                     │
│    ├── 配置管理：环境变量/配置文件                                  │
│    └── 健康检查：/health 端点                                       │
│                                                                     │
│ 3. 生命周期管理                                                        │
│    ├── 启动：服务初始化                                               │
│    ├── 运行：HTTP 服务器监听                                        │
│    └── 关闭：优雅停机                                                 │
└─────────────────────────────────────────────────────────────────────┘
```

### MCP Server 架构

```
MCP Server 架构：
┌─────────────────────────────────────────────────────────────────────┐
│ 1. 协议层                                                            │
│    ├── JSON-RPC 2.0 协议                                            │
│    ├── 消息格式：Request/Response/Notification                      │
│    └── 传输层：Stdio/HTTP/WebSocket                                 │
│                                                                     │
│ 2. 工具层                                                            │
│    ├── 工具注册：Tool 定义与注册                                    │
│    ├── 工具调用：参数验证与执行                                     │
│    └── 工具响应：结果格式化                                         │
│                                                                     │
│ 3. 资源层                                                            │
│    ├── 资源定义：Resource 模型                                      │
│    ├── 资源访问：读取与写入                                         │
│    └── 资源订阅：变更通知                                           │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 第二部分：迁移策略

### Gin Web 到 MCP Server 迁移

```
迁移步骤：
┌─────────────────────────────────────────────────────────────────────┐
│ 1. 协议转换                                                          │
│    ├── HTTP → JSON-RPC 2.0                                          │
│    ├── RESTful → Tool Call                                          │
│    └── Response → MCP Response                                      │
│                                                                     │
│ 2. 工具封装                                                          │
│    ├── Controller → Tool Handler                                    │
│    ├── Service → Tool Logic                                         │
│    └── Model → Tool Parameter/Result                                │
│                                                                     │
│ 3. 配置管理                                                          │
│    ├── 环境变量 → MCP Config                                        │
│    ├── 路由表 → Tool Registry                                       │
│    └── 中间件 → MCP Middleware                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### 工具封装示例

```
工具封装流程：
┌─────────────────────────────────────────────────────────────────────┐
│ 1. 原始 Gin Handler                                                  │
│    ├── func GetCampaigns(c *gin.Context)                            │
│    ├── 参数：query params                                           │
│    └── 响应：JSON                                                   │
│                                                                     │
│ 2. MCP Tool 封装                                                     │
│    ├── Tool: list_campaigns                                         │
│    ├── Parameters: {page, limit, status}                            │
│    └── Result: {campaigns, total, page}                             │
│                                                                     │
│ 3. 调用方式                                                          │
│    ├── HTTP: GET /api/campaigns?page=1&limit=10                     │
│    └── MCP: CallTool("list_campaigns", {"page": 1, "limit": 10})    │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 第三部分：实现要点

### 认证与授权

```
认证授权流程：
┌─────────────────────────────────────────────────────────────────────┐
│ 1. 认证方式                                                          │
│    ├── JWT Token 验证                                               │
│    ├── OAuth2 Token 验证                                            │
│    └── API Key 验证                                                 │
│                                                                     │
│ 2. 权限控制                                                          │
│    ├── 角色权限：RBAC                                               │
│    ├── 资源权限：CRUD 控制                                          │
│    └── 操作权限：敏感操作二次确认                                   │
│                                                                     │
│ 3. 审计日志                                                          │
│    ├── 操作记录：谁在什么时候做了什么                               │
│    ├── 变更追踪：数据变更记录                                       │
│    └── 安全事件：异常行为检测                                       │
└─────────────────────────────────────────────────────────────────────┘
```

### 错误处理

```
错误处理策略：
┌─────────────────────────────────────────────────────────────────────┐
│ 1. 参数错误                                                          │
│    ├── 400 Bad Request                                              │
│    ├── 错误码：INVALID_PARAM                                        │
│    └── 错误信息：参数描述                                           │
│                                                                     │
│ 2. 认证错误                                                          │
│    ├── 401 Unauthorized                                             │
│    ├── 错误码：UNAUTHORIZED                                         │
│    └── 错误信息：认证失败                                           │
│                                                                     │
│ 3. 权限错误                                                          │
│    ├── 403 Forbidden                                                │
│    ├── 错误码：PERMISSION_DENIED                                    │
│    └── 错误信息：权限不足                                           │
│                                                                     │
│ 4. 服务错误                                                          │
│    ├── 500 Internal Server Error                                    │
│    ├── 错误码：INTERNAL_ERROR                                       │
│    └── 错误信息：服务异常                                           │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 第四部分：自测题

### Q1: Gin Web 到 MCP Server 迁移的三大步骤？

**A**: 协议转换（HTTP→JSON-RPC 2.0）、工具封装（Controller→Tool Handler）、配置管理（环境变量→MCP Config）。

### Q2: MCP 协议的三大组成部分？

**A**: 协议层（JSON-RPC 2.0/消息格式/传输层）、工具层（工具注册/调用/响应）、资源层（资源定义/访问/订阅）。

### Q3: 认证授权的三个层面？

**A**: 认证方式（JWT/OAuth2/API Key）、权限控制（RBAC/资源权限/操作权限）、审计日志（操作记录/变更追踪/安全事件）。

---

## Go 代码实战：Gin Web API 迁移到 MCP Server

### 1. MCP Server 核心实现

```go
package mcp

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"sync"
)

// Message JSON-RPC 2.0 消息
type Message struct {
	JSONRPC string          `json:"jsonrpc"`
	ID      *int64          `json:"id,omitempty"`
	Method  string          `json:"method"`
	Params  json.RawMessage `json:"params,omitempty"`
	Result  json.RawMessage `json:"result,omitempty"`
	Error   *RPCError       `json:"error,omitempty"`
}

type RPCError struct {
	Code    int    `json:"code"`
	Message string `json:"message"`
}

// Tool MCP 工具定义
type Tool struct {
	Name        string          `json:"name"`
	Description string          `json:"description"`
	InputSchema json.RawMessage `json:"inputSchema"`
	Handler     func(context.Context, json.RawMessage) (json.RawMessage, error)
}

// Resource MCP 资源定义
type Resource struct {
	URI         string          `json:"uri"`
	Name        string          `json:"name"`
	Description string          `json:"description"`
	MIMEType    string          `json:"mimeType,omitempty"`
	ReadFunc    func(context.Context) (string, error)
}

// Server MCP 服务器
type Server struct {
	tools      map[string]*Tool
	resources  map[string]*Resource
	subscriptions map[string][]func(*Event)
	mu       sync.RWMutex
	handlers map[string]func(*Message) (*Message, error)
}

func NewServer() *Server {
	s := &Server{
		tools:       make(map[string]*Tool),
		resources:   make(map[string]*Resource),
		subscriptions: make(map[string][]func(*Event)),
		handlers:    make(map[string]func(*Message) (*Message, error)),
	}
	
	// 注册内置 handler
	s.RegisterHandler("initialize", s.handleInitialize)
	s.RegisterHandler("tools/list", s.handleToolsList)
	s.RegisterHandler("tools/call", s.handleToolCall)
	s.RegisterHandler("resources/list", s.handleResourcesList)
	s.RegisterHandler("resources/read", s.handleResourceRead)
	
	return s
}

func (s *Server) RegisterHandler(method string, handler func(*Message) (*Message, error)) {
	s.handlers[method] = handler
}

func (s *Server) RegisterTool(tool *Tool) {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.tools[tool.Name] = tool
}

func (s *Server) RegisterResource(res *Resource) {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.resources[res.URI] = res
}

func (s *Server) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	var msg Message
	if err := json.NewDecoder(r.Body).Decode(&msg); err != nil {
		w.WriteHeader(400)
		json.NewEncoder(w).Encode(map[string]string{"error": "invalid JSON"})
		return
	}
	
	handler, ok := s.handlers[msg.Method]
	if !ok {
		w.WriteHeader(404)
		json.NewEncoder(w).Encode(map[string]string{"error": "method not found"})
		return
	}
	
	result, err := handler(&msg)
	if err != nil {
		w.WriteHeader(500)
		json.NewEncoder(w).Encode(map[string]string{"error": err.Error()})
		return
	}
	
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(result)
}

func (s *Server) handleInitialize(msg *Message) (*Message, error) {
	resp := &Message{
		JSONRPC: "2.0",
		Result: json.RawMessage(`{
			"protocolVersion": "2024-11-05",
			"serverInfo": {"name": "ad-platform-mcp", "version": "1.0.0"},
			"capabilities": {
				"tools": {},
				"resources": {}
			}
		}`),
	}
	return resp, nil
}

func (s *Server) handleToolsList(msg *Message) (*Message, error) {
	s.mu.RLock()
	tools := make([]map[string]interface{}, 0, len(s.tools))
	for name, tool := range s.tools {
		tools = append(tools, map[string]interface{}{
			"name":        name,
			"description": tool.Description,
			"inputSchema": json.RawMessage(tool.InputSchema),
		})
	}
	s.mu.RUnlock()
	
	return &Message{
		JSONRPC: "2.0",
		Result:  json.RawMessage(fmt.Sprintf(`{"tools": %v}`, tools)),
	}, nil
}

func (s *Server) handleToolCall(msg *Message) (*Message, error) {
	var params struct {
		Name      string          `json:"name"`
		Arguments json.RawMessage `json:"arguments"`
	}
	json.Unmarshal(msg.Params, &params)
	
	tool, ok := s.tools[params.Name]
	if !ok {
		return &Message{
			JSONRPC: "2.0",
			Error:   &RPCError{Code: -32601, Message: fmt.Sprintf("tool not found: %s", params.Name)},
		}, nil
	}
	
	result, err := tool.Handler(context.Background(), params.Arguments)
	if err != nil {
		return &Message{
			JSONRPC: "2.0",
			Error:   &RPCError{Code: -32603, Message: err.Error()},
		}, nil
	}
	
	return &Message{
		JSONRPC: "2.0",
		Result:  result,
	}, nil
}

func (s *Server) handleResourcesList(msg *Message) (*Message, error) {
	s.mu.RLock()
	resources := make([]map[string]interface{}, 0, len(s.resources))
	for uri, res := range s.resources {
		resources = append(resources, map[string]interface{}{
			"uri":         uri,
			"name":        res.Name,
			"description": res.Description,
		})
	}
	s.mu.RUnlock()
	
	return &Message{
		JSONRPC: "2.0",
		Result:  json.RawMessage(fmt.Sprintf(`{"resources": %v}`, resources)),
	}, nil
}

func (s *Server) handleResourceRead(msg *Message) (*Message, error) {
	var params struct {
		URI string `json:"uri"`
	}
	json.Unmarshal(msg.Params, &params)
	
	res, ok := s.resources[params.URI]
	if !ok {
		return &Message{
			JSONRPC: "2.0",
			Error:   &RPCError{Code: -32601, Message: fmt.Sprintf("resource not found: %s", params.URI)},
		}, nil
	}
	
	content, err := res.ReadFunc(context.Background())
	if err != nil {
		return &Message{
			JSONRPC: "2.0",
			Error:   &RPCError{Code: -32603, Message: err.Error()},
		}, nil
	}
	
	return &Message{
		JSONRPC: "2.0",
		Result:  json.RawMessage(fmt.Sprintf(`{"content": %q}`, content)),
	}, nil
}
```

### 自测题

<details>
<summary>Q1: MCP Server 的 JSON-RPC 2.0 协议中，为什么用 id 字段关联请求和响应？</summary>

**答案**：

**JSON-RPC 2.0 规范**要求：
- 请求必须有 `id`（用于关联响应）
- 通知（Notification）没有 `id`（单向发送，不需要响应）
- 响应必须回传相同的 `id`

广告平台 MCP Server 中，id 用来追踪哪个 Agent 调用了哪个工具——这对审计和调试至关重要。

</details>

<details>
<summary>Q2: Server 的 RegisterTool 为什么用 mutex 保护？handlers map 呢？</summary>

**答案**：

**tools map**：在 handleToolCall 中被并发读取（多个 goroutine 同时处理请求），需要 RWMutex。

**handlers map**：只在初始化时写入，之后只读——可以用普通 map 或 init 时一次性写入。

生产环境推荐：**所有共享 map 都用 RWMutex**，避免忘记加锁导致 race condition。

</details>

<details>
<summary>Q3: Gin Controller 迁移到 MCP Tool 的核心转换规则是什么？</summary>

**答案**：

| Gin Controller | MCP Tool |
|---------------|----------|
| HTTP Handler func(w, r) | Tool Handler func(ctx, params) |
| URL path + method | Tool name |
| Query/Body params | InputSchema (JSON Schema) |
| HTTP Response | JSON-RPC Result |
| HTTP Error | RPCError |

核心转换：**把 HTTP 路由逻辑抽象为工具调用逻辑**。

</details>
