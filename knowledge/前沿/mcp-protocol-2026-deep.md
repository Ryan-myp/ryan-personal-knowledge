# MCP 协议深度实现 - 2026年AI Agent标准通信协议

> **版本**: v2.1  
> **日期**: 2026-08-13  
> **作者**: Ryan  
> **分类**: 前沿/MCP  
> **代码密度**: 28%

---

## 一、MCP 协议架构

```
┌─────────────────────────────────────────────────────────────────────┐
│                    MCP 协议分层架构                                  │
│                                                                     │
│  Layer 4: Transport (传输层)                                         │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │ • Stdio (标准输入输出)                                       │   │
│  │ • HTTP/SSE (Server-Sent Events)                             │   │
│  │ • WebSocket (双向通信)                                       │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                           │                                        │
│  Layer 3: Protocol (协议层)                                         │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │ • JSON-RPC 2.0 消息格式                                      │   │
│  │ • 初始化握手 (Initialize)                                    │   │
│  │ • 能力协商 (Capabilities)                                    │   │
│  │ • 生命周期管理                                               │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                           │                                        │
│  Layer 2: Core (核心层)                                             │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │ • Resources (资源: 文件/数据/流)                              │   │
│  │ • Tools (工具: 函数调用)                                      │   │
│  │ • Prompts (提示词模板)                                       │   │
│  │ • Sampling (模型采样)                                        │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                           │                                        │
│  Layer 1: Semantic (语义层)                                         │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │ • 数据类型系统                                                │   │
│  │ • Schema 校验                                                 │   │
│  │ • 错误处理                                                    │   │
│  └─────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 二、Go MCP Server 实现

```go
// mcp/server.go
package mcp

import (
    "context"
    "encoding/json"
    "fmt"
)

// Server MCP服务器
type Server struct {
    name    string
    version string
    
    // 已注册的资源
    resources map[string]*Resource
    
    // 已注册的工具
    tools map[string]*Tool
    
    // 已注册的prompt
    prompts map[string]*Prompt
    
    // 客户端连接
    client *Client
}

// NewServer 创建服务器
func NewServer(name, version string) *Server {
    return &Server{
        name:    name,
        version: version,
        resources: make(map[string]*Resource),
        tools:     make(map[string]*Tool),
        prompts:   make(map[string]*Prompt),
    }
}

// RegisterTool 注册工具
func (s *Server) RegisterTool(tool *Tool) {
    s.tools[tool.Name] = tool
}

// RegisterResource 注册资源
func (s *Server) RegisterResource(resource *Resource) {
    s.resources[resource.URI] = resource
}

// HandleRequest 处理请求
func (s *Server) HandleRequest(ctx context.Context, req *Request) (*Response, error) {
    switch req.Method {
    case "initialize":
        return s.handleInitialize(req)
    case "tools/list":
        return s.handleToolsList(req)
    case "tools/call":
        return s.handleToolCall(req)
    case "resources/list":
        return s.handleResourcesList(req)
    case "resources/read":
        return s.handleResourceRead(req)
    case "prompts/list":
        return s.handlePromptsList(req)
    case "prompts/get":
        return s.handlePromptGet(req)
    default:
        return nil, fmt.Errorf("unknown method: %s", req.Method)
    }
}

// handleToolCall 处理工具调用
func (s *Server) handleToolCall(req *Request) (*Response, error) {
    var params struct {
        Name      string                 `json:"name"`
        Arguments map[string]interface{} `json:"arguments"`
    }
    json.Unmarshal(req.Params, &params)
    
    tool, ok := s.tools[params.Name]
    if !ok {
        return nil, fmt.Errorf("tool not found: %s", params.Name)
    }
    
    result, err := tool.Execute(params.Arguments)
    if err != nil {
        return &Response{Error: &Error{Code: -32000, Message: err.Error()}}, nil
    }
    
    return &Response{Result: result}, nil
}
```

---

## 三、MCP Client 实现

```go
// mcp/client.go
package mcp

import (
    "context"
    "encoding/json"
)

// Client MCP客户端
type Client struct {
    conn   Connection
    server *ServerInfo
    
    // 已发现的能力
    capabilities ServerCapabilities
}

// Connect 连接服务器
func (c *Client) Connect(ctx context.Context, addr string) error {
    conn, err := c.dial(ctx, addr)
    if err != nil {
        return err
    }
    c.conn = conn
    
    // 初始化握手
    initReq := &Request{
        Method: "initialize",
        Params: json.RawMessage(`{"protocolVersion":"2024-11-05","capabilities":{}}`),
    }
    resp, err := c.sendRequest(ctx, initReq)
    if err != nil {
        return err
    }
    
    json.Unmarshal(resp.Result, &c.server)
    return nil
}

// CallTool 调用工具
func (c *Client) CallTool(ctx context.Context, name string, args map[string]interface{}) (*ToolResult, error) {
    params, _ := json.Marshal(map[string]interface{}{
        "name":      name,
        "arguments": args,
    })
    
    req := &Request{
        Method: "tools/call",
        Params: params,
    }
    
    resp, err := c.sendRequest(ctx, req)
    if err != nil {
        return nil, err
    }
    
    var result ToolResult
    json.Unmarshal(resp.Result, &result)
    return &result, nil
}
```

---

## 四、自测题

1. **MCP为什么选择JSON-RPC 2.0？**
   - 成熟、轻量、支持错误处理和异步通知

2. **Transport层为什么支持多种协议？**
   - 不同场景需求不同 (stdio适合本地, SSE适合远程)

