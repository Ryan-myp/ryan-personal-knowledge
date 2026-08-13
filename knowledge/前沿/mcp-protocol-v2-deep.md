# MCP 协议进阶 - 资深专家深度实现

## 一、协议架构

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     MCP 协议架构 v2                                        │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   ┌─────────────┐      ┌─────────────┐      ┌─────────────┐           │
│   │  Client     │ ←───→ │  Host       │ ←───→ │  Server     │           │
│   │  (Pi/Cursor)│      │  (运行时)    │      │  (工具服务)  │           │
│   └─────────────┘      └─────────────┘      └─────────────┘           │
│          │                      │                      │                │
│          │    JSON-RPC 2.0      │    stdio / HTTP      │                │
│          └──────────────────────┼──────────────────────┘                │
│                                 ▼                                       │
│   ┌─────────────────────────────────────────────────────────────────┐   │
│   │                    核心协议层                                      │   │
│   │  • Initialization (初始化)                                        │   │
│   │  • Tools (工具定义与调用)                                           │   │
│   │  • Resources (资源管理)                                            │   │
│   │  • Prompts (提示词模板)                                            │   │
│   │  • Sampling (采样请求)                                             │   │
│   └─────────────────────────────────────────────────────────────────┘   │
│                                                                         →
└─────────────────────────────────────────────────────────────────────────┘
```

## 二、MCP Server 实现

```typescript
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";

// 定义MCP Server
const server = new McpServer({
  name: "my-mcp-server",
  version: "1.0.0",
});

// 注册工具
server.tool(
  "search_documents",
  { query: z.string(), limit: z.number().default(10) },
  async ({ query, limit }) => {
    const results = await searchDocs(query);
    return {
      content: results.map(doc => ({
        type: "text" as const,
        text: JSON.stringify(doc),
      })),
    };
  }
);

// 注册资源
server.resource(
  "document",
  "doc://{id}",
  async (uri, params) => {
    const doc = await getDocument(params.id);
    return {
      contents: [{
        uri: uri.href,
        mimeType: "application/json",
        text: JSON.stringify(doc),
      }],
    };
  }
);

// 启动服务器
const transport = new StdioServerTransport();
await server.connect(transport);
```

## 三、MCP Client 实现

```typescript
import { McpClient } from "@modelcontextprotocol/sdk/client/mcp.js";
import { StdioClientTransport } from "@modelcontextprotocol/sdk/client/stdio.js";

// 连接MCP Server
const transport = new StdioClientTransport({
  command: "npx",
  args: ["-y", "@myorg/my-mcp-server"],
});

const client = new McpClient({ name: "my-client", version: "1.0.0" });
await client.connect(transport);

// 调用工具
const result = await client.callTool({
  name: "search_documents",
  arguments: { query: "如何设计高并发系统", limit: 5 },
});

console.log(result.content);

// 读取资源
const resource = await client.readResource("doc://123");
console.log(resource.contents);
```

## 四、面试高频题

### Q1: MCP协议相比其他协议有什么优势？

```
A:
1. 标准化: 统一的接口规范
2. 可扩展: 支持Tools/Resources/Prompts
3. 生态: 客户端和服务端分离
```

### Q2: 如何实现MCP安全？

```
A:
1. 传输加密: TLS
2. 认证授权: OAuth2/JWT
3. 审计日志: 操作记录
```

## 五、自测题

1. 解释MCP协议架构
2. 如何实现MCP Server？
3. 如何确保MCP安全？

---

## 参考文档

- [MCP Spec](https://modelcontextprotocol.io/specification)
- [MCP TypeScript SDK](https://github.com/modelcontextprotocol/typescript-sdk)
