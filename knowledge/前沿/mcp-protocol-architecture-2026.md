# MCP 协议架构深度解析 - 2026 AI Agent 标准

> **版本**: v1.0  
> **日期**: 2026-08-13  
> **作者**: Ryan  
> **分类**: 前沿/AI Agent  
> **代码密度**: 25%

---

## 一、MCP 是什么？

```
MCP (Model Context Protocol) = AI 模型的"USB-C 接口"

┌─────────────────────────────────────────────────────────────┐
│                    MCP 架构概览                              │
│                                                             │
│   ┌──────────┐      ┌──────────┐      ┌──────────┐        │
│   │  AI      │      │  MCP     │      │  资源     │        │
│   │  Client  │ ←──→ │ Server   │ ←──→ │  提供方   │        │
│   │ (Claude  │      │ (工具/   │      │ (DB/     │        │
│   │  GPT)    │      │  提示词) │      │  文件/   │        │
│   └──────────┘      └──────────┘      └──────────┘        │
│                                                             │
│   传输层: STDIO / HTTP / SSE                                 │
│   数据格式: JSON-RPC 2.0                                    │
└─────────────────────────────────────────────────────────────┘
```

---

## 二、核心概念

### 2.1 三大基础原语

```typescript
// resources - 数据源
{
  uri: "file:///home/user/docs/notes.txt",
  name: "User Notes",
  description: "Personal notes",
  mimeType: "text/plain"
}

// tools - 可执行操作
{
  name: "search_docs",
  description: "Search documentation",
  inputSchema: {
    type: "object",
    properties: {
      query: { type: "string", description: "Search query" }
    },
    required: ["query"]
  }
}

// prompts - 提示词模板
{
  name: "code_review",
  description: "Review code changes",
  arguments: [
    { name: "diff", description: "Git diff to review" }
  ]
}
```

---

## 三、协议实现

### 3.1 Server 端实现 (Go)

```go
// mcp_server.go
package main

import (
    "context"
    "log"
    "github.com/modelcontextprotocol/go-sdk/mcp"
)

func main() {
    // 创建 MCP Server
    server := mcp.NewServer("my-server", "1.0.0")
    
    // 注册工具
    server.AddTool(&mcp.Tool{
        Name:        "get_weather",
        Description: "Get weather for a city",
        InputSchema: mcp.JSONSchema{
            Type: "object",
            Properties: map[string]mcp.JSONSchema{
                "city": {Type: "string", Description: "City name"},
            },
            Required: []string{"city"},
        },
        Handler: func(ctx context.Context, args mcp.ToolCall) (interface{}, error) {
            city := args.Arguments["city"].(string)
            // 调用天气 API
            return map[string]interface{}{
                "city":    city,
                "temp":    25.5,
                "weather": "sunny",
            }, nil
        },
    })
    
    // 注册资源
    server.AddResource(&mcp.Resource{
        URI:         "weather://beijing",
        Name:        "Beijing Weather",
        Description: "Current weather in Beijing",
        MimeType:    "application/json",
        ReadFunc: func(ctx context.Context, uri string) (string, error) {
            return `{"temp": 22, "weather": "sunny"}`, nil
        },
    })
    
    // 启动服务
    log.Println("Starting MCP server on stdio...")
    if err := server.RunStdio(context.Background()); err != nil {
        log.Fatal(err)
    }
}
```

### 3.2 Client 端实现 (Python)

```python
# mcp_client.py
import asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def main():
    # 连接 MCP Server
    server_params = StdioServerParameters(
        command="go",
        args=["run", "server.go"]
    )
    
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            # 初始化
            await session.initialize()
            
            # 列出工具
            tools = await session.list_tools()
            print(f"Available tools: {[t.name for t in tools]}")
            
            # 调用工具
            result = await session.call_tool(
                "get_weather", 
                {"city": "Beijing"}
            )
            print(f"Weather: {result}")
            
            # 读取资源
            resource = await session.read_resource("weather://beijing")
            print(f"Resource: {resource}")

if __name__ == "__main__":
    asyncio.run(main())
```

---

## 四、传输层实现

### 4.1 STDIO 传输

```go
// stdio_transport.go
package mcp

import (
    "bufio"
    "context"
    "encoding/json"
    "io"
    "os"
)

type StdioTransport struct {
    stdin  io.ReadCloser
    stdout io.WriteCloser
    scanner *bufio.Scanner
}

func NewStdioTransport() *StdioTransport {
    return &StdioTransport{
        stdin:  os.Stdin,
        stdout: os.Stdout,
        scanner: bufio.NewScanner(os.Stdin),
    }
}

func (t *StdioTransport) Receive(ctx context.Context) (*Message, error) {
    t.scanner.Scan()
    var msg Message
    if err := json.Unmarshal(t.scanner.Bytes(), &msg); err != nil {
        return nil, err
    }
    return &msg, nil
}

func (t *StdioTransport) Send(ctx context.Context, msg *Message) error {
    data, _ := json.Marshal(msg)
    _, err := t.stdout.Write(append(data, '\n'))
    return err
}
```

### 4.2 HTTP/SSE 传输

```go
// sse_transport.go
package mcp

import (
    "context"
    "encoding/json"
    "net/http"
)

type SSETransport struct {
    endpoint string
    client   *http.Client
}

func NewSSETransport(endpoint string) *SSETransport {
    return &SSETransport{
        endpoint: endpoint,
        client:   &http.Client{},
    }
}

func (t *SSETransport) Send(ctx context.Context, msg *Message) error {
    data, _ := json.Marshal(msg)
    resp, err := t.client.Post(
        t.endpoint+"/message",
        "application/json",
        bytes.NewReader(data),
    )
    defer resp.Body.Close()
    return err
}
```

---

## 五、最佳实践

### 5.1 工具设计原则

```
✅ GOOD:
- 单一职责：每个工具做一件事
- 参数清晰：input schema 明确
- 错误处理：返回结构化错误
- 幂等性：相同输入产生相同输出

❌ BAD:
- 工具过多：超过 20 个难以管理
- 参数复杂：嵌套对象难以理解
- 副作用大：改变状态不可逆
- 文档缺失：LLM 无法理解用途
```

### 5.2 安全考虑

```go
// security.go
package mcp

import (
    "context"
    "errors"
)

var (
    ErrUnauthorized = errors.New("unauthorized")
    ErrRateLimit    = errors.New("rate limited")
)

// 认证中间件
func WithAuth(next Handler) Handler {
    return func(ctx context.Context, req *Request) (*Response, error) {
        token := ctx.Value("token")
        if token == nil {
            return nil, ErrUnauthorized
        }
        return next(ctx, req)
    }
}

// 限流中间件
func WithRateLimit(maxPerMinute int) Middleware {
    // 实现令牌桶限流
    bucket := NewTokenBucket(maxPerMinute)
    return func(next Handler) Handler {
        return func(ctx context.Context, req *Request) (*Response, error) {
            if !bucket.Allow() {
                return nil, ErrRateLimit
            }
            return next(ctx, req)
        }
    }
}
```

---

## 六、生态工具

| 项目 | 语言 | 说明 |
|------|------|------|
| mcp-go | Go | 官方 Go SDK |
| mcp-python | Python | 官方 Python SDK |
| mcp-typescript | TypeScript | 官方 JS SDK |
| Claude MCP | - | Anthropic 客户端 |
| Cursor MCP | - | IDE 集成 |

---

## 七、自测题

1. **MCP 解决的核心问题是什么？**
   - AI 模型与外部工具/数据的标准化连接

2. **三种传输方式各适用什么场景？**
   - STDIO: 本地进程, HTTP: 远程服务, SSE: 流式推送

3. **如何设计一个安全的 MCP Server？**
   - 认证 + 限流 + 权限控制

