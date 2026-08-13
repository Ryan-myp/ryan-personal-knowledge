# MCP协议深度实现 - 资深专家深度实现

## 一、协议架构

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        MCP协议架构                                       │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   ┌─────────────┐         ┌─────────────┐         ┌─────────────┐      │
│   │   Client    │◄───────►│  Transport  │◄───────►│  Server     │      │
│   │  (AI Agent) │         │ (Stdio/HTTP)│         │ (Tools)     │      │
│   └─────────────┘         └─────────────┘         └─────────────┘      │
│           │                         │                         │        │
│           │    ┌────────────────────┼────────────────────┐    │        │
│           │    │    Message Types    │                   │    │        │
│           │    │  • Initialize       │                   │    │        │
│           │    │  • Tools/List       │                   │    │        │
│           │    │  • Tools/Call       │                   │    │        │
│           │    │  • Resources/Read   │                   │    │        │
│           │    └─────────────────────┴───────────────────┘    │        │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

## 二、工具注册

```typescript
// MCP Server实现
import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";

const server = new Server({
  name: "my-tools",
  version: "1.0.0",
}, {
  capabilities: {
    tools: {},
  },
});

// 注册工具
server.setRequestHandler(ListToolsRequestSchema, async () => {
  return {
    tools: [
      {
        name: "get_weather",
        description: "Get weather information",
        inputSchema: {
          type: "object",
          properties: {
            city: { type: "string" },
          },
          required: ["city"],
        },
      },
    ],
  };
});

// 工具实现
server.setRequestHandler(CallToolRequestSchema, async (request) => {
  if (request.params.name === "get_weather") {
    const weather = await fetchWeather(request.params.arguments.city);
    return { content: [{ type: "text", text: JSON.stringify(weather) }] };
  }
});
```

## 三、资源访问

```typescript
// 注册资源
server.setRequestHandler(ListResourcesRequestSchema, async () => {
  return {
    resources: [
      {
        uri: "file:///data/config.json",
        name: "Config",
        mimeType: "application/json",
      },
    ],
  };
});

server.setRequestHandler(ReadResourceRequestSchema, async (request) => {
  const content = await readFile(request.params.uri);
  return {
    contents: [
      {
        uri: request.params.uri,
        mimeType: "application/json",
        text: content,
      },
    ],
  };
});
```

## 四、面试高频题

### Q1: MCP协议解决了什么问题？

```
A:
1. 标准化工具调用接口
2. 跨平台工具集成
3. AI Agent与外部工具通信
```

### Q2: 如何实现工具安全？

```
A:
1. 权限控制
2. 输入验证
3. 审计日志
4. 超时控制
```

## 五、自测题

1. 解释MCP协议架构
2. 如何实现工具调用？
3. 如何保证安全性？

---

## 参考文档

- [MCP规范](https://modelcontextprotocol.io/spec)
- [MCP SDK](https://github.com/modelcontextprotocol/sdk)
