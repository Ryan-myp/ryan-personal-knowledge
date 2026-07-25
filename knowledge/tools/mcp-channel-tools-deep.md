# MCP 工具技能：多渠道广告平台 API 集成

> 来源：ad_smart_delivery_platform 项目
> 状态：基于代码实现蒸馏
> 蒸馏日期：2026-06-18

---

## 第一部分：MCP 工具架构

### MCP 工具注册与管理

```
MCP 工具注册流程：
┌─────────────────────────────────────────────────────────────────────┐
│ 1. 工具定义                                                          │
│    ├── 工具名称：唯一标识符                                         │
│    ├── 工具描述：功能说明                                           │
│    ├── 输入参数：JSON Schema 定义                                   │
│    └── 返回值：结构化响应                                           │
│                                                                     │
│ 2. 工具注册                                                          │
│    ├── 注册中心：统一工具管理                                       │
│    ├── 版本控制：工具版本管理                                       │
│    └── 依赖注入：工具间依赖关系                                     │
│                                                                     │
│ 3. 工具调用                                                          │
│    ├── 参数验证：输入参数校验                                       │
│    ├── 权限检查：访问权限控制                                       │
│    └── 执行引擎：工具实际执行                                       │
└─────────────────────────────────────────────────────────────────────┘
```

### 工具分类

```
MCP 工具分类：
┌─────────────────────────────────────────────────────────────────────┐
│ 1. 代码知识库工具                                                    │
│    ├── 代码搜索：Repo 代码检索                                      │
│    ├── 知识图谱：代码关系分析                                       │
│    └── 向量检索：语义搜索                                           │
│                                                                     │
│ 2. 营销 API 工具                                                     │
│    ├── 账户管理：广告账户 CRUD                                      │
│    ├── 广告系列：Campaign 管理                                      │
│    ├── 广告组：Ad Group 管理                                        │
│    └── 创意管理：Ad Creative 管理                                   │
│                                                                     │
│ 3. 平台适配器工具                                                    │
│    ├── Google Ads：Google 平台适配器                                │
│    ├── Facebook Ads：Meta 平台适配器                                │
│    ├── TikTok Ads：TikTok 平台适配器                                │
│    └── DV360：Google 程序化工具适配器                               │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 第二部分：多渠道平台适配器

### Google Ads 适配器

```
Google Ads 适配器：
┌─────────────────────────────────────────────────────────────────────┐
│ 1. 认证管理                                                          │
│    ├── OAuth2 流程                                                    │
│    ├── 刷新令牌                                                       │
│    └── 权限范围                                                       │
│                                                                     │
│ 2. API 调用                                                          │
│    ├── 广告系列：CampaignService                                    │
│    ├── 广告组：AdGroupService                                       │
│    ├── 创意：CreativeService                                        │
│    └── 报告：ReportService                                          │
│                                                                     │
│ 3. 数据映射                                                          │
│    ├── 字段映射：平台字段到内部模型                                 │
│    ├── 类型转换：数据类型转换                                       │
│    └── 错误处理：API 错误映射                                       │
└─────────────────────────────────────────────────────────────────────┘
```

### Facebook Ads 适配器

```
Facebook Ads 适配器：
┌─────────────────────────────────────────────────────────────────────┐
│ 1. 认证管理                                                          │
│    ├── OAuth2 流程                                                    │
│    ├── 页面令牌                                                       │
│    └── 权限范围                                                       │
│                                                                     │
│ 2. API 调用                                                          │
│    ├── 广告账户：AdAccount                                          │
│    ├── 广告系列：Campaign                                           │
│    ├── 广告组：AdSet                                                │
│    └── 广告：Ad                                                     │
│                                                                     │
│ 3. 数据映射                                                          │
│    ├── 字段映射：平台字段到内部模型                                 │
│    ├── 类型转换：数据类型转换                                       │
│    └── 错误处理：API 错误映射                                       │
└─────────────────────────────────────────────────────────────────────┘
```

### TikTok Ads 适配器

```
TikTok Ads 适配器：
┌─────────────────────────────────────────────────────────────────────┐
│ 1. 认证管理                                                          │
│    ├── OAuth2 流程                                                    │
│    ├── 应用令牌                                                       │
│    └── 权限范围                                                       │
│                                                                     │
│ 2. API 调用                                                          │
│    ├── 广告账户：Advertiser                                         │
│    ├── 广告系列：Campaign                                           │
│    ├── 广告组：AdGroup                                              │
│    └── 创意：Creative                                               │
│                                                                     │
│ 3. 数据映射                                                          │
│    ├── 字段映射：平台字段到内部模型                                 │
│    ├── 类型转换：数据类型转换                                       │
│    └── 错误处理：API 错误映射                                       │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 第三部分：工具调用流程

### 统一调用接口

```
工具调用流程：
┌─────────────────────────────────────────────────────────────────────┐
│ 1. 请求处理                                                          │
│    ├── 参数解析：JSON 参数解析                                      │
│    ├── 验证：输入参数校验                                           │
│    └── 路由：工具分发                                               │
│                                                                     │
│ 2. 执行引擎                                                          │
│    ├── 权限检查：访问控制                                           │
│    ├── 工具执行：调用实际工具                                       │
│    └── 结果处理：响应格式化                                         │
│                                                                     │
│ 3. 响应处理                                                          │
│    ├── 错误处理：异常捕获                                           │
│    ├── 日志记录：操作审计                                           │
│    └── 返回结果：结构化响应                                         │
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
│ 2. 权限错误                                                          │
│    ├── 403 Forbidden                                                │
│    ├── 错误码：PERMISSION_DENIED                                    │
│    └── 错误信息：权限不足                                           │
│                                                                     │
│ 3. 服务错误                                                          │
│    ├── 500 Internal Server Error                                    │
│    ├── 错误码：INTERNAL_ERROR                                       │
│    └── 错误信息：服务异常                                           │
│                                                                     │
│ 4. 第三方 API 错误                                                   │
│    ├── 429 Too Many Requests                                        │
│    ├── 错误码：RATE_LIMITED                                         │
│    └── 错误信息：请求频率限制                                       │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 第四部分：自测题

### Q1: MCP 工具的三大组成部分？

**A**: 工具定义（名称/描述/参数/返回值）、工具注册（注册中心/版本控制/依赖注入）、工具调用（参数验证/权限检查/执行引擎）。

### Q2: 三大平台适配器的共同点？

**A**: 都使用 OAuth2 认证、都有 API 调用层、都有数据映射层、都有错误处理机制。

### Q3: 工具调用的三步流程？

**A**: 请求处理（参数解析/验证/路由）、执行引擎（权限检查/工具执行/结果处理）、响应处理（错误处理/日志记录/返回结果）。

---

## Go 代码实战：MCP 通道与工具注册

### 1. MCP Stdio 传输层实现

```go
package mcp

import (
	"bufio"
	"encoding/json"
	"fmt"
	"io"
	"os"
	"sync"
)

// StdioTransport stdio 传输层（MCP 默认传输）
type StdioTransport struct {
	stdin  io.Reader
	stdout io.Writer
	mu     sync.Mutex
}

func NewStdioTransport() *StdioTransport {
	return &StdioTransport{
		stdin:  os.Stdin,
		stdout: os.Stdout,
	}
}

func (t *StdioTransport) ReadMessage() (*Message, error) {
	reader := bufio.NewReader(t.stdin)
	
	// 读取 Content-Length header
	line, err := reader.ReadString('\n')
	if err != nil {
		return nil, err
	}
	
	// 解析 Content-Length: <number>
	var length int
	fmt.Sscanf(line, "Content-Length: %d", &length)
	
	// 读取空行分隔符
	reader.ReadString('\n')
	reader.ReadString('\n')
	
	// 读取 JSON body
	body := make([]byte, length)
	io.ReadFull(reader, body)
	
	var msg Message
	if err := json.Unmarshal(body, &msg); err != nil {
		return nil, err
	}
	
	return &msg, nil
}

func (t *StdioTransport) WriteMessage(msg *Message) error {
	t.mu.Lock()
	defer t.mu.Unlock()
	
	data, err := json.Marshal(msg)
	if err != nil {
		return err
	}
	
	fmt.Fprintf(t.stdout, "Content-Length: %d\r\n\r\n", len(data))
	t.stdout.Write(data)
	t.stdout.Write([]byte{'\r', '\n'})
	
	return nil
}
```

### 2. 工具注册中心

```go
package registry

import (
	"context"
	"encoding/json"
	"fmt"
	"sync"
)

// ToolRegistry 工具注册中心
type ToolRegistry struct {
	mu       sync.RWMutex
	tools    map[string]*RegisteredTool
	schemas  map[string]json.RawMessage // name -> JSON Schema
}

type RegisteredTool struct {
	Name        string
	Description string
	InputSchema json.RawMessage
	Version     string
	Category    string
	Handler     func(context.Context, json.RawMessage) (json.RawMessage, error)
	Metadata    map[string]interface{}
}

func NewToolRegistry() *ToolRegistry {
	return &ToolRegistry{
		tools:   make(map[string]*RegisteredTool),
		schemas: make(map[string]json.RawMessage),
	}
}

func (r *ToolRegistry) Register(tool *RegisteredTool) error {
	r.mu.Lock()
	defer r.mu.Unlock()
	
	if _, exists := r.tools[tool.Name]; exists {
		return fmt.Errorf("tool already registered: %s", tool.Name)
	}
	
	r.tools[tool.Name] = tool
	r.schemas[tool.Name] = tool.InputSchema
	return nil
}

func (r *ToolRegistry) Call(ctx context.Context, name string, args json.RawMessage) (json.RawMessage, error) {
	r.mu.RLock()
	tool, ok := r.tools[name]
	r.mu.RUnlock()
	
	if !ok {
		return nil, fmt.Errorf("tool not found: %s", name)
	}
	
	return tool.Handler(ctx, args)
}

func (r *ToolRegistry) List() []*RegisteredTool {
	r.mu.RLock()
	defer r.mu.RUnlock()
	
	result := make([]*RegisteredTool, 0, len(r.tools))
	for _, tool := range r.tools {
		result = append(result, tool)
	}
	return result
}

func (r *ToolRegistry) GetSchema(name string) (json.RawMessage, bool) {
	r.mu.RLock()
	defer r.mu.RUnlock()
	schema, ok := r.schemas[name]
	return schema, ok
}
```

### 自测题

<details>
<summary>Q1: MCP Stdio 传输的 Content-Length header 为什么是必需的？</summary>

**答案**：

**问题**：JSON 消息可能包含任意字符（包括换行符），stdin 是字节流，无法从内容本身判断消息边界。

**Content-Length 的作用**：告诉客户端要读多少字节才是完整消息。这是 HTTP/1.1 也用的技术——在二进制协议中解决文本消息的定界问题。

</details>

<details>
<summary>Q2: ToolRegistry 的 Register 为什么用锁而 Call 用 RLock？</summary>

**答案**：

**读写锁优化**：
- Register 写操作少（初始化时调用一次）→ 用 Lock
- Call 读操作多（每次工具调用都读）→ 用 RLock，允许多个并发调用

这是标准的 **read-heavy workload** 优化模式。

</details>

<details>
<summary>Q3: MCP 的 InputSchema 为什么用 JSON Schema 而不是 Go struct？</summary>

**答案**：

**跨语言兼容**：MCP 是协议层标准，客户端可能是 Python、Node.js 等。JSON Schema 是通用描述格式，所有语言都能解析。

Go struct 只能在 Go 内部使用，无法序列化到协议层。JSON Schema 让 Agent 可以在运行时动态理解工具的参数结构。

</details>
