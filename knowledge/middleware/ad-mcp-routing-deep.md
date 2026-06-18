# MCP 路由规则深度：RoutingMCPToolCaller/策略/优先级

> 从路由匹配到多服务器编排，逐行解析 MCP 路由层

---

## 第一部分：MCP 路由架构

### 为什么需要路由层

```
没有路由层的问题：
1. Agent 需要知道每个工具的具体 URL
2. 工具迁移需要改 Agent 代码
3. 多 MCP Server 无法统一管理
4. 路由策略无法动态调整

有路由层的好处：
1. Agent 只调工具名，不关心 URL
2. 工具迁移只需改路由配置
3. 多 MCP Server 统一入口
4. 路由策略可热更新
```

### MCP 路由架构

```
Agent 调用
    ↓
MCPToolCaller.CallTool(toolName, args)
    ↓
RoutingMCPToolCaller（路由决策）
    ├── 精确匹配 → HTTPMCPToolCaller (server_A)
    ├── 前缀匹配 → HTTPMCPToolCaller (server_B)
    ├── 包含匹配 → HTTPMCPToolCaller (server_C)
    └── 默认路由 → HTTPMCPToolCaller (server_default)
    ↓
HTTPMCPToolCaller.POST(baseURL/toolName/call, args)
    ↓
MCP Server (JSON-RPC 2.0)
```

---

## 第二部分：RoutingMCPToolCaller 源码深度

### 路由规则定义

```go
// MCPToolRoute 路由规则
type MCPToolRoute struct {
    // 精确匹配的工具名列表
    ToolNames []string `json:"tool_names"`
    
    // 前缀匹配的工具名前缀列表
    ToolPrefixes []string `json:"tool_prefixes"`
    
    // 包含匹配的工具名关键词
    ToolContains []string `json:"tool_contains"`
    
    // 目标 MCP Server 地址
    ServerURL string `json:"server_url"`
    
    // 优先级（数字越小优先级越高）
    Priority int `json:"priority"`
    
    // 超时时间
    Timeout time.Duration `json:"timeout"`
    
    // 是否启用
    Enabled bool `json:"enabled"`
}
```

### 路由匹配算法

```
路由匹配优先级：
1. 精确匹配（ToolNames）— 最高优先级
2. 前缀匹配（ToolPrefixes）— 中等优先级
3. 包含匹配（ToolContains）— 最低优先级
4. 默认路由 — 兜底

匹配过程：
1. 遍历所有路由规则（按 Priority 排序）
2. 对每条规则：
   a. 检查 ToolNames（精确匹配）
   b. 检查 ToolPrefixes（前缀匹配）
   c. 检查 ToolContains（包含匹配）
3. 第一条匹配的规则被选中
4. 没有匹配 → 使用默认路由
```

### 路由管理器实现

```go
package mcp

import (
    "context"
    "fmt"
    "strings"
    "sync"
    "time"
)

// RoutingMCPToolCaller 路由 MCP 调用器
type RoutingMCPToolCaller struct {
    routes     []MCPToolRoute
    servers    map[string]*HTTPMCPToolCaller
    mu         sync.RWMutex
    defaultURL string
}

// NewRoutingMCPToolCaller 创建路由调用器
func NewRoutingMCPToolCaller(defaultURL string) *RoutingMCPToolCaller {
    return &RoutingMCPToolCaller{
        routes:     make([]MCPToolRoute, 0),
        servers:    make(map[string]*HTTPMCPToolCaller),
        defaultURL: defaultURL,
    }
}

// AddRoute 添加路由规则
func (r *RoutingMCPToolCaller) AddRoute(route MCPToolRoute) {
    r.mu.Lock()
    defer r.mu.Unlock()
    
    // 创建或复用 HTTPMCPToolCaller
    if _, ok := r.servers[route.ServerURL]; !ok {
        r.servers[route.ServerURL] = NewHTTPMCPToolCallerWithTimeout(
            route.ServerURL, nil, route.Timeout,
        )
    }
    
    r.routes = append(r.routes, route)
    
    // 按优先级排序
    sort.Slice(r.routes, func(i, j int) bool {
        return r.routes[i].Priority < r.routes[j].Priority
    })
}

// CallTool 调用工具（带路由）
func (r *RoutingMCPToolCaller) CallTool(ctx context.Context, req MCPToolRequest) (*MCPToolResult, error) {
    r.mu.RLock()
    defer r.mu.RUnlock()
    
    // 1. 查找匹配的路由
    route := r.findRoute(req.ToolName)
    if route == nil {
        return nil, fmt.Errorf("no route found for tool: %s", req.ToolName)
    }
    
    // 2. 获取目标服务器
    server, ok := r.servers[route.ServerURL]
    if !ok {
        return nil, fmt.Errorf("server not configured: %s", route.ServerURL)
    }
    
    // 3. 调用工具
    return server.CallTool(ctx, req)
}

// findRoute 查找匹配的路由
func (r *RoutingMCPToolCaller) findRoute(toolName string) *MCPToolRoute {
    // 1. 精确匹配
    for _, route := range r.routes {
        for _, name := range route.ToolNames {
            if name == toolName {
                return &route
            }
        }
    }
    
    // 2. 前缀匹配
    for _, route := range r.routes {
        for _, prefix := range route.ToolPrefixes {
            if strings.HasPrefix(toolName, prefix) {
                return &route
            }
        }
    }
    
    // 3. 包含匹配
    for _, route := range r.routes {
        for _, keyword := range route.ToolContains {
            if strings.Contains(toolName, keyword) {
                return &route
            }
        }
    }
    
    // 4. 默认路由
    if r.defaultURL != "" {
        return &MCPToolRoute{
            ServerURL: r.defaultURL,
            Priority:  9999,
        }
    }
    
    return nil
}
```

---

## 第三部分：路由策略

### 路由策略对比

```
┌─────────────────────────────────────────────────────────────────────┐
│ 策略 1: 按平台路由                                                   │
│                                                                     │
│ TikTok Ads:                                                         │
│   ToolNames: [get_tiktok_ad_list, post_tiktok_ad_create]           │
│   ServerURL: https://tiktok-mcp.example.com                        │
│                                                                     │
│ Facebook Ads:                                                       │
│   ToolNames: [get_facebook_ad_list, post_facebook_ad_create]       │
│   ServerURL: https://facebook-mcp.example.com                      │
│                                                                     │
│ Google Ads:                                                         │
│   ToolNames: [get_google_ad_list, post_google_ad_create]           │
│   ServerURL: https://google-mcp.example.com                        │
│                                                                     │
│ 优点：平台隔离，故障不影响其他平台                                   │
│ 缺点：需要维护 3 个 MCP Server                                     │
│                                                                     │
│ ────────────────────────────────────────────────────────────────── │
│                                                                     │
│ 策略 2: 按功能前缀路由                                               │
│                                                                     │
│ 查询类:                                                             │
│   ToolPrefixes: [get_mkt_dap_adminapi_*_list, get_mkt_*_detail]    │
│   ServerURL: https://dap-query-mcp.example.com                     │
│                                                                     │
│ 创建类:                                                             │
│   ToolPrefixes: [post_mkt_dap_adminapi_*_create]                   │
│   ServerURL: https://dap-write-mcp.example.com                     │
│                                                                     │
│ 发布类:                                                             │
│   ToolPrefixes: [post_mkt_dap_adminapi_*_publish]                  │
│   ServerURL: https://dap-publish-mcp.example.com                   │
│                                                                     │
│ 优点：读写分离，查询/写操作不同服务器                                │
│ 缺点：路由规则较多                                                 │
│                                                                     │
│ ────────────────────────────────────────────────────────────────── │
│                                                                     │
│ 策略 3: 混合路由（推荐）                                             │
│                                                                     │
│ 精确匹配（高风险操作）:                                              │
│   ToolNames: [publish_campaign, delete_campaign, transfer_budget]  │
│   ServerURL: https://dap-admin-mcp.example.com                     │
│   Timeout: 60s                                                     │
│                                                                     │
│ 前缀匹配（查询操作）:                                                │
│   ToolPrefixes: [get_mkt_*_list, get_mkt_*_detail]                 │
│   ServerURL: https://dap-query-mcp.example.com                     │
│   Timeout: 30s                                                     │
│                                                                     │
│ 默认路由:                                                           │
│   ServerURL: https://dap-admin-mcp.example.com                     │
│   Timeout: 30s                                                     │
│                                                                     │
│ 优点：灵活，可按风险等级配置不同超时                                 │
│ 缺点：配置较复杂                                                   │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 第四部分：多 MCP Server 编排

### 多服务器配置

```yaml
# mcp_routes.yaml
routes:
  # TikTok Ads
  - tool_names:
      - get_mkt_dap_adminapi_ua_tiktok_ad_list
      - get_mkt_dap_adminapi_ua_tiktok_ad_detail
      - post_mkt_dap_adminapi_ua_tiktok_ad_create
    server_url: https://tiktok-mcp.shopee.ph
    priority: 1
    timeout: 30s

  # Facebook Ads
  - tool_names:
      - get_mkt_dap_adminapi_ua_facebook_ad_list
      - get_mkt_dap_adminapi_ua_facebook_ad_detail
      - post_mkt_dap_adminapi_ua_facebook_ad_create
    server_url: https://facebook-mcp.shopee.ph
    priority: 1
    timeout: 30s

  # Google Ads
  - tool_names:
      - get_mkt_dap_adminapi_ua_google_ad_list
      - get_mkt_dap_adminapi_ua_google_ad_detail
      - post_mkt_dap_adminapi_ua_google_ad_create
    server_url: https://google-mcp.shopee.ph
    priority: 1
    timeout: 30s

  # 查询操作（通用）
  - tool_prefixes:
      - get_mkt_dap_adminapi_*_list
      - get_mkt_dap_adminapi_*_detail
    server_url: https://dap-query-mcp.shopee.ph
    priority: 10
    timeout: 30s

  # 发布操作（高风险）
  - tool_names:
      - post_mkt_dap_adminapi_ua_marketing_plan_publish_campaign
      - post_mkt_dap_adminapi_ua_campaign_update
    server_url: https://dap-admin-mcp.shopee.ph
    priority: 1
    timeout: 60s

  # 默认路由
  - server_url: https://dap-admin-mcp.shopee.ph
    priority: 9999
    timeout: 30s
```

---

## 第五部分：自测题

### Q1: 路由匹配的优先级？

**A**: 精确匹配 > 前缀匹配 > 包含匹配 > 默认路由。同优先级按配置顺序。

### Q2: 为什么需要多 MCP Server？

**A**: 平台隔离（故障不影响其他平台）、读写分离（查询/写操作不同服务器）、按风险等级配置不同超时。

### Q3: 路由策略怎么选？

**A**: 简单场景用按平台路由，中等场景用按功能前缀路由，复杂场景用混合路由（精确+前缀+默认）。

---

## 第六部分：生产实践

### 1. 路由配置

```
路由配置要点：
1. 高风险操作精确匹配，配置长超时
2. 查询操作前缀匹配，配置短超时
3. 默认路由兜底
4. 定期审查路由规则
```

### 2. 故障转移

```
故障转移要点：
1. 主服务器超时 → 切换到备用服务器
2. 备用服务器也超时 → 返回错误
3. 记录故障日志
4. 发送告警
```

### 3. 监控

```
监控要点：
1. 路由命中率
2. 各服务器响应时间
3. 超时次数
4. 故障转移次数
```
