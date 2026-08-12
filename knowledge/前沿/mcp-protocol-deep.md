---
title: MCP 协议深度实现
date: 2026-08-13
status: production
tags: [前沿, 深度实现, 源码级]
domain: 前沿
---

# MCP 协议深度实现

## 一、协议概述

Model Context Protocol (MCP) 是 AI 模型与外部工具/数据源的标准通信协议。

```
┌─────────────────────────────────────────────────────────────────┐
│                    MCP 架构                                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   ┌─────────────┐          ┌─────────────┐          ┌────────┐ │
│   │   Host      │          │   MCP       │          │ Server │ │
│   │  (Claude)   │◄────────▶│  Client     │◄────────▶│        │ │
│   └─────────────┘          └─────────────┘          └───┬────┘ │
│                                                         │      │
│                    ┌──────────────────────────┐         │      │
│                    │      Transport Layer     │◄────────┘      │
│                    │  • Stdio / HTTP / SSE   │                │
│                    └──────────────────────────┘                │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## 二、传输层实现

### 2.1 Stdio 传输

```python
import json
import asyncio
import sys
from typing import Optional, Dict, Any, Callable

class StdioTransport:
    """Stdio 传输层实现"""
    
    def __init__(self, process: asyncio.subprocess.Process):
        self.process = process
        self._stdin = process.stdin
        self._stdout = process.stdout
        self._message_id = 0
        self._callbacks: Dict[int, asyncio.Future] = {}
    
    async def send(self, message: Dict[str, Any]) -> Any:
        """发送消息"""
        self._message_id += 1
        msg_id = self._message_id
        
        # 构建请求
        request = {
            "jsonrpc": "2.0",
            "id": msg_id,
            **message
        }
        
        # 发送
        self._stdin.write(json.dumps(request).encode() + b'\n')
        await self._stdin.drain()
        
        # 等待响应
        loop = asyncio.get_event_loop()
        future = loop.create_future()
        self._callbacks[msg_id] = future
        
        try:
            return await asyncio.wait_for(future, timeout=30)
        finally:
            self._callbacks.pop(msg_id, None)
    
    async def receive_loop(self):
        """接收消息循环"""
        while True:
            line = await self._stdout.readline()
            if not line:
                break
            
            try:
                data = json.loads(line.decode())
                await self._handle_message(data)
            except json.JSONDecodeError:
                continue
    
    async def _handle_message(self, data: Dict):
        """处理收到的消息"""
        msg_type = data.get("method")
        
        if "id" in data:
            # 响应
            future = self._callbacks.get(data["id"])
            if future and not future.done():
                result = data.get("result")
                error = data.get("error")
                if error:
                    future.set_exception(Exception(error["message"]))
                else:
                    future.set_result(result)
        else:
            # 通知
            handler = self._get_notification_handler(msg_type)
            if handler:
                await handler(data.get("params", {}))
    
    def _get_notification_handler(self, method: str) -> Optional[Callable]:
        """获取通知处理器"""
        handlers = {
            "notifications/initialized": self._on_initialized,
            "notifications/message": self._on_message,
        }
        return handlers.get(method)
    
    async def _on_initialized(self, params: Dict):
        """初始化回调"""
        pass
    
    async def _on_message(self, params: Dict):
        """消息回调"""
        print(f"Message: {params.get('message')}")
```

### 2.2 HTTP 传输

```python
import aiohttp
from typing import Optional

class HTTPTransport:
    """HTTP/SSE 传输层"""
    
    def __init__(self, base_url: str):
        self.base_url = base_url
        self._session: Optional[aiohttp.ClientSession] = None
    
    async def __aenter__(self):
        self._session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc, tb):
        if self._session:
            await self._session.close()
    
    async def send(self, message: Dict) -> Any:
        """发送请求"""
        async with self._session.post(
            f"{self.base_url}/message",
            json={"message": message}
        ) as resp:
            return await resp.json()
    
    async def connect_sse(self, callback: Callable):
        """连接 SSE 流"""
        async with self._session.get(
            f"{self.base_url}/sse"
        ) as resp:
            async for line in resp.content.iter_decode():
                if line.startswith("data: "):
                    data = json.loads(line[6:])
                    await callback(data)
```

## 三、服务端实现

### 3.1 MCP Server 基础

```python
from typing import List, Dict, Any, Optional
import json

class MCPServer:
    """MCP 服务端"""
    
    def __init__(self, name: str, version: str = "1.0.0"):
        self.name = name
        self.version = version
        self._tools: Dict[str, Dict] = {}
        self._resources: Dict[str, Dict] = {}
        self._prompts: Dict[str, Dict] = {}
    
    def tool(self, name: str, description: str, parameters: Dict):
        """注册工具"""
        def decorator(func: Callable):
            self._tools[name] = {
                "name": name,
                "description": description,
                "inputSchema": parameters,
                "handler": func
            }
            return func
        return decorator
    
    def resource(self, uri: str, name: str, description: str = ""):
        """注册资源"""
        def decorator(func: Callable):
            self._resources[uri] = {
                "uri": uri,
                "name": name,
                "description": description,
                "handler": func
            }
            return func
        return decorator
    
    async def handle_initialize(self, params: Dict) -> Dict:
        """处理初始化请求"""
        return {
            "protocolVersion": "2024-11-05",
            "capabilities": self._get_capabilities(),
            "serverInfo": {
                "name": self.name,
                "version": self.version
            }
        }
    
    def _get_capabilities(self) -> Dict:
        """获取能力列表"""
        return {
            "tools": {"listChanged": True},
            "resources": {"subscribe": True, "listChanged": True},
            "prompts": {"listChanged": True}
        }
    
    async def handle_list_tools(self) -> Dict:
        """列出所有工具"""
        return {
            "tools": [
                {
                    "name": t["name"],
                    "description": t["description"],
                    "inputSchema": t["inputSchema"]
                }
                for t in self._tools.values()
            ]
        }
    
    async def handle_call_tool(self, name: str, arguments: Dict) -> Dict:
        """调用工具"""
        if name not in self._tools:
            raise ValueError(f"Tool not found: {name}")
        
        tool = self._tools[name]
        result = await tool["handler"](arguments)
        
        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(result) if isinstance(result, dict) else str(result)
                }
            ]
        }
```

### 3.2 完整 Server 示例

```python
import asyncio
import subprocess
import sys

class FileSystemServer(MCPServer):
    """文件系统 MCP Server"""
    
    def __init__(self):
        super().__init__("filesystem", "1.0.0")
        
        @self.tool("read_file", "读取文件内容", {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "文件路径"}
            },
            "required": ["path"]
        })
        async def read_file(args: Dict) -> str:
            path = args["path"]
            with open(path, 'r') as f:
                return f.read()
        
        @self.tool("write_file", "写入文件", {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "content": {"type": "string"}
            },
            "required": ["path", "content"]
        })
        async def write_file(args: Dict) -> str:
            path = args["path"]
            with open(path, 'w') as f:
                f.write(args["content"])
            return f"Written {len(args['content'])} bytes to {path}"
        
        @self.tool("list_directory", "列出目录内容", {
            "type": "object",
            "properties": {
                "path": {"type": "string"}
            },
            "required": ["path"]
        })
        async def list_directory(args: Dict) -> List[str]:
            import os
            return os.listdir(args["path"])

async def main():
    server = FileSystemServer()
    transport = StdioTransport(None)  # 实际使用时会传入process
    
    # 启动消息循环
    await transport.receive_loop()

if __name__ == "__main__":
    asyncio.run(main())
```

## 四、客户端实现

### 4.1 MCP Client

```python
class MCPClient:
    """MCP 客户端"""
    
    def __init__(self, transport):
        self.transport = transport
        self._initialized = False
    
    async def initialize(self) -> Dict:
        """初始化连接"""
        result = await self.transport.send({
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {
                    "name": "mcp-client",
                    "version": "1.0.0"
                }
            }
        })
        
        self._initialized = True
        return result
    
    async def list_tools(self) -> List[Dict]:
        """列出可用工具"""
        result = await self.transport.send({
            "method": "tools/list"
        })
        return result.get("tools", [])
    
    async def call_tool(self, name: str, arguments: Dict) -> Any:
        """调用工具"""
        result = await self.transport.send({
            "method": "tools/call",
            "params": {
                "name": name,
                "arguments": arguments
            }
        })
        content = result.get("content", [])
        if content and content[0].get("type") == "text":
            return json.loads(content[0]["text"])
        return result
    
    async def list_resources(self) -> List[Dict]:
        """列出可用资源"""
        result = await self.transport.send({
            "method": "resources/list"
        })
        return result.get("resources", [])
    
    async def read_resource(self, uri: str) -> str:
        """读取资源"""
        result = await self.transport.send({
            "method": "resources/read",
            "params": {"uri": uri}
        })
        return result.get("contents", [{}])[0].get("text", "")
```

## 五、安全与权限

```python
class MCPAuthenticator:
    """MCP 认证与授权"""
    
    def __init__(self):
        self._allowed_servers = set()
        self._user_permissions = {}
    
    def add_allowed_server(self, server_name: str):
        """添加允许的服务"""
        self._allowed_servers.add(server_name)
    
    def check_permission(self, user: str, tool: str) -> bool:
        """检查用户权限"""
        user_perms = self._user_permissions.get(user, set())
        return tool in user_perms or "*" in user_perms
    
    def authenticate(self, token: str) -> Optional[str]:
        """验证 token"""
        # 简化实现
        if token.startswith("mcp_"):
            return "user_123"
        return None

class PermissionManager:
    """权限管理器"""
    
    def __init__(self):
        self._scope_restrictions = {}
        self._rate_limits = {}
    
    def set_scope(self, tool: str, allowed_paths: List[str]):
        """设置工具作用域"""
        self._scope_restrictions[tool] = allowed_paths
    
    def check_scope(self, tool: str, path: str) -> bool:
        """检查路径权限"""
        if tool not in self._scope_restrictions:
            return True
        allowed = self._scope_restrictions[tool]
        return any(path.startswith(p) for p in allowed)
    
    def check_rate_limit(self, tool: str, user: str) -> bool:
        """检查速率限制"""
        key = f"{tool}:{user}"
        current = self._rate_limits.get(key, 0)
        if current >= 100:  # 100次/分钟
            return False
        self._rate_limits[key] = current + 1
        return True
```

## 六、性能监控

```python
import time
from collections import defaultdict

class MCPMonitor:
    """MCP 监控"""
    
    def __init__(self):
        self._latencies = defaultdict(list)
        self._errors = defaultdict(int)
        self._call_counts = defaultdict(int)
    
    def record_call(self, tool: str, latency: float, success: bool):
        """记录调用"""
        self._latencies[tool].append(latency)
        self._call_counts[tool] += 1
        if not success:
            self._errors[tool] += 1
    
    def get_stats(self) -> Dict:
        """获取统计"""
        stats = {}
        for tool in self._latencies:
            lats = self._latencies[tool]
            stats[tool] = {
                "calls": self._call_counts[tool],
                "avg_latency_ms": sum(lats) / len(lats) * 1000,
                "p99_latency_ms": sorted(lats)[-1] * 1000 if lats else 0,
                "error_rate": self._errors[tool] / max(self._call_counts[tool], 1)
            }
        return stats
```

## 七、自测题

### Q1: MCP 协议的三层架构是什么？
**答案**: 应用层（Tools/Resources/Prompts）、传输层（Stdio/HTTP/SSE）、数据层（JSON-RPC 2.0）。

### Q2: 如何实现工具调用的权限控制？
**答案**: 通过 MCPAuthenticator 验证用户身份，PermissionManager 检查工具权限和作用域。

### Q3: Stdio 传输和 HTTP 传输的区别是什么？
**答案**: Stdio 适合本地进程通信，低延迟；HTTP/SSE 适合远程服务，支持跨网络。

---

**关键词**: MCP, Model Context Protocol, 工具调用, 标准协议

**参考**:
- [MCP 规范](https://modelcontextprotocol.io/)
- [Anthropic MCP 博客](https://www.anthropic.com/news/model-context-protocol)