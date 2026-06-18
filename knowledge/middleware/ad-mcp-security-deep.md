# MCP 安全策略深度：凭证管理/权限检查/审计日志/三层防护

> 从凭证安全到权限控制，逐层解析 MCP 工具调用的安全防护体系

---

## 第一部分：为什么 MCP 安全是致命的

### MCP 调用的攻击面

```
MCP 工具调用攻击面：
┌─────────────────────────────────────────────────────────────────────┐
│ 1. 凭证泄露                                                        │
│    - 硬编码 token 提交到 git                                        │
│    - 环境变量未设置 → 默认值泄露                                    │
│    - 日志打印了敏感参数                                             │
│                                                                     │
│ 2. 未授权调用                                                      │
│    - 低权限用户调用了高权限工具                                     │
│    - 没有角色检查就执行写操作                                       │
│    - 跨租户数据泄露                                                 │
│                                                                     │
│ 3. 注入攻击                                                        │
│    - 用户输入直接拼接到工具参数                                     │
│    - 工具名称注入（绕过路由校验）                                    │
│    - 参数注入（SQL/命令注入）                                       │
│                                                                     │
│ 4. 滥用                                                            │
│    - 高频调用导致 API 限额超限                                      │
│    - 批量删除/批量修改造成数据破坏                                  │
│    - 敏感操作没有二次确认                                           │
└─────────────────────────────────────────────────────────────────────┘
```

### 广告平台 MCP 安全风险

```
广告平台 MCP 工具的风险分级：
┌─────────────────────────────────────────────────────────────────────┐
│ 🔴 高风险（必须二次确认 + 权限检查 + 审计日志）                       │
│    - publish_campaign: 发布广告，直接影响投放                         │
│    - delete_campaign: 删除广告                                      │
│    - transfer_budget: 转移预算                                      │
│    - bulk_update: 批量更新                                          │
│                                                                     │
│ 🟡 中风险（需要权限检查 + 审计日志）                                  │
│    - create_campaign: 创建广告                                      │
│    - update_budget: 修改预算                                        │
│    - create_creative: 上传创意素材                                   │
│    - request_creative: 发起素材请求                                  │
│                                                                     │
│ 🟢 低风险（只需要审计日志）                                          │
│    - list_campaigns: 查询广告列表                                   │
│    - get_performance: 获取性能数据                                  │
│    - get_status: 查询状态                                           │
│    - query_reports: 查询报表                                        │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 第二部分：三层安全防护架构

### 防护层 1：指令过滤（Input Filtering）

```go
package security

import (
    "strings"
    "regexp"
)

// InstructionFilter 指令过滤器
type InstructionFilter struct {
    // 系统指令注入检测
    systemInjectionPatterns []*regexp.Regexp
    
    // 敏感词列表
    sensitiveWords []string
    
    // 危险操作模式
    dangerousPatterns []*regexp.Regexp
}

// NewInstructionFilter 创建指令过滤器
func NewInstructionFilter() *InstructionFilter {
    return &InstructionFilter{
        systemInjectionPatterns: []*regexp.Regexp{
            regexp.MustCompile(`(?i)(ignore\s+(all\s+)?(previous|earlier|above)\s+instructions?)`),
            regexp.MustCompile(`(?i)(you\s+are\s+now\s+(unrestricted|unlimited|without\s+limits))`),
            regexp.MustCompile(`(?i)(forget\s+all\s+(rules|constraints|safety))`),
            regexp.MustCompile(`(?i)(你\s*是\s*不受\s*限制\s*的)`),
            regexp.MustCompile(`(?i)(忽略\s*(所有\s*)?(之前\s*)?(指令|规则|限制))`),
        },
        
        sensitiveWords: []string{
            "api_key", "secret", "password", "token",
            "database_password", "private_key",
            "数据库密码", "API密钥", "私钥", "access_token",
        },
        
        dangerousPatterns: []*regexp.Regexp{
            regexp.MustCompile(`(?i)(delete|drop|truncate)\s+(all|everything)`),
            regexp.MustCompile(`(?i)(bulk\s+delete|bulk\s+remove)`),
            regexp.MustCompile(`(?i)(transfer\s+all\s+budget)`),
            regexp.MustCompile(`(?i)(disable\s+all\s+accounts)`),
        },
    }
}

// Validate 验证用户输入
func (f *InstructionFilter) Validate(input string) *ValidationResult {
    result := &ValidationResult{
        IsSafe: true,
        Issues: []string{},
    }
    
    // 1. 检测系统指令注入
    for _, pattern := range f.systemInjectionPatterns {
        if pattern.MatchString(input) {
            result.IsSafe = false
            result.Issues = append(result.Issues, "检测到系统指令注入")
            return result
        }
    }
    
    // 2. 检测敏感词
    inputLower := strings.ToLower(input)
    for _, word := range f.sensitiveWords {
        if strings.Contains(inputLower, strings.ToLower(word)) {
            result.IsSafe = false
            result.Issues = append(result.Issues, "检测到敏感词: "+word)
            return result
        }
    }
    
    // 3. 检测危险操作模式
    for _, pattern := range f.dangerousPatterns {
        if pattern.MatchString(input) {
            result.IsSafe = false
            result.Issues = append(result.Issues, "检测到危险操作模式")
            return result
        }
    }
    
    return result
}

type ValidationResult struct {
    IsSafe   bool
    Issues   []string
    Severity string // low/medium/high/critical
}
```

### 防护层 2：参数校验（Parameter Validation）

```go
package security

import (
    "fmt"
    "strings"
    "unicode"
)

// ParameterValidator 参数校验器
type ParameterValidator struct {
    // 工具参数白名单
    toolParamWhitelist map[string]map[string][]string
    
    // 参数长度限制
    maxParamLength int
    
    // 特殊字符过滤
    disallowedChars []rune
}

// NewParameterValidator 创建参数校验器
func NewParameterValidator() *ParameterValidator {
    return &ParameterValidator{
        toolParamWhitelist: map[string]map[string][]string{
            "publish_campaign": {
                "campaign_id":   {"^[a-zA-Z0-9_-]+$"},
                "ad_account_id": {"^[a-zA-Z0-9_-]+$"},
            },
            "create_campaign": {
                "campaign_name": {"^[a-zA-Z0-9_\s\-\.]{1,100}$"},
                "daily_budget":  {"^[0-9]+(\.[0-9]+)?$"},
                "ad_account_id": {"^[a-zA-Z0-9_-]+$"},
            },
            "delete_campaign": {
                "campaign_id":   {"^[a-zA-Z0-9_-]+$"},
                "ad_account_id": {"^[a-zA-Z0-9_-]+$"},
            },
        },
        maxParamLength: 10000,
        disallowedChars: []rune{
            ';', '|', '&', '$', '`', '\'', '"', '\\',
        },
    }
}

// ValidateToolParams 校验工具参数
func (v *ParameterValidator) ValidateToolParams(toolName string, params map[string]interface{}) *ValidationError {
    // 1. 检查工具是否在白名单中
    allowedParams, ok := v.toolParamWhitelist[toolName]
    if !ok {
        return &ValidationError{
            Field:   "tool_name",
            Message: fmt.Sprintf("工具 %s 未在白名单中", toolName),
        }
    }
    
    // 2. 检查参数长度
    for key, value := range params {
        strValue := fmt.Sprintf("%v", value)
        if len(strValue) > v.maxParamLength {
            return &ValidationError{
                Field:   key,
                Message: fmt.Sprintf("参数 %s 超过最大长度 %d", key, v.maxParamLength),
            }
        }
        
        // 3. 检查特殊字符
        for _, r := range strValue {
            for _, disallowed := range v.disallowedChars {
                if r == disallowed {
                    return &ValidationError{
                        Field:   key,
                        Message: fmt.Sprintf("参数 %s 包含不允许的字符: %c", key, r),
                    }
                }
            }
        }
    }
    
    // 4. 检查参数类型
    for key, patternStr := range allowedParams {
        if value, ok := params[key]; ok {
            strValue := fmt.Sprintf("%v", value)
            for _, pattern := range patternStr {
                if matched, _ := regexp.MatchString(pattern, strValue); !matched {
                    return &ValidationError{
                        Field:   key,
                        Message: fmt.Sprintf("参数 %s 格式不合法", key),
                    }
                }
            }
        }
    }
    
    return nil
}

type ValidationError struct {
    Field   string
    Message string
}
```

### 防护层 3：执行控制（Execution Control）

```go
package security

import (
    "context"
    "time"
)

// PermissionChecker 权限检查器
type PermissionChecker struct {
    roleManager *RoleManager
    auditLogger *AuditLogger
}

// RoleManager 角色管理器
type RoleManager struct {
    // 角色 → 工具映射
    roleToolMap map[string][]string
    // 用户 → 角色映射
    userRoleMap map[string]string
}

// AuditLogger 审计日志
type AuditLogger struct {
    entries []AuditEntry
}

type AuditEntry struct {
    Timestamp  time.Time
    UserID     string
    ToolName   string
    Parameters map[string]interface{}
    Result     string
    RiskLevel  string // low/medium/high/critical
    Approved   bool
}

// NewPermissionChecker 创建权限检查器
func NewPermissionChecker() *PermissionChecker {
    return &PermissionChecker{
        roleManager: &RoleManager{
            roleToolMap: map[string][]string{
                "admin": {
                    "publish_campaign", "delete_campaign", "transfer_budget",
                    "bulk_update", "create_campaign", "update_budget",
                },
                "operator": {
                    "create_campaign", "update_budget", "request_creative",
                    "list_campaigns", "get_performance",
                },
                "viewer": {
                    "list_campaigns", "get_performance", "get_status",
                    "query_reports",
                },
            },
            userRoleMap: map[string]string{
                "user_001": "admin",
                "user_002": "operator",
                "user_003": "viewer",
            },
        },
        auditLogger: &AuditLogger{
            entries: make([]AuditEntry, 0),
        },
    }
}

// CheckPermission 检查权限
func (pc *PermissionChecker) CheckPermission(ctx context.Context, userID, toolName string) (*PermissionResult, error) {
    // 1. 获取用户角色
    role, ok := pc.roleManager.userRoleMap[userID]
    if !ok {
        return &PermissionResult{
            Allowed: false,
            Reason:  "用户角色未定义",
        }, nil
    }
    
    // 2. 检查角色是否有工具权限
    allowedTools, ok := pc.roleManager.roleToolMap[role]
    if !ok {
        return &PermissionResult{
            Allowed: false,
            Reason:  "角色权限未定义",
        }, nil
    }
    
    for _, tool := range allowedTools {
        if tool == toolName {
            return &PermissionResult{
                Allowed: true,
                Role:    role,
            }, nil
        }
    }
    
    return &PermissionResult{
        Allowed: false,
        Reason:  fmt.Sprintf("角色 %s 无权调用工具 %s", role, toolName),
    }, nil
}

// LogAudit 记录审计日志
func (pc *PermissionChecker) LogAudit(entry AuditEntry) {
    pc.auditLogger.entries = append(pc.auditLogger.entries, entry)
    
    // 记录到日志系统
    if entry.RiskLevel == "high" || entry.RiskLevel == "critical" {
        // 高风险操作发送告警
        pc.sendAlert(entry)
    }
}

// RequireApproval 需要审批的操作
func (pc *PermissionChecker) RequireApproval(toolName string) bool {
    criticalTools := []string{
        "publish_campaign", "delete_campaign", "transfer_budget",
        "bulk_update",
    }
    
    for _, tool := range criticalTools {
        if tool == toolName {
            return true
        }
    }
    return false
}

type PermissionResult struct {
    Allowed bool
    Role    string
    Reason  string
}
```

---

## 第三部分：凭证管理

### 凭证安全最佳实践

```
凭证管理原则：
1. 绝不硬编码凭证
2. 凭证从环境变量读取
3. .gitignore 排除所有凭证文件
4. 生产环境使用密钥管理服务
5. 演示代码用占位符
```

### 凭证管理器实现

```go
package security

import (
    "os"
    "sync"
)

// CredentialManager 凭证管理器
type CredentialManager struct {
    mu       sync.RWMutex
    cache    map[string]string  // key → value
    envPrefix string            // 环境变量前缀
}

// NewCredentialManager 创建凭证管理器
func NewCredentialManager(envPrefix string) *CredentialManager {
    return &CredentialManager{
        cache:     make(map[string]string),
        envPrefix: envPrefix,
    }
}

// Get 获取凭证
func (cm *CredentialManager) Get(key string) (string, error) {
    cm.mu.RLock()
    if value, ok := cm.cache[key]; ok {
        cm.mu.RUnlock()
        return value, nil
    }
    cm.mu.RUnlock()
    
    // 从环境变量读取
    envKey := cm.envPrefix + "_" + strings.ToUpper(key)
    value := os.Getenv(envKey)
    
    if value == "" {
        return "", fmt.Errorf("credential not found: %s (env: %s)", key, envKey)
    }
    
    // 缓存
    cm.mu.Lock()
    cm.cache[key] = value
    cm.mu.Unlock()
    
    return value, nil
}

// Store 存储凭证（用于动态更新）
func (cm *CredentialManager) Store(key, value string) {
    cm.mu.Lock()
    defer cm.mu.Unlock()
    cm.cache[key] = value
}

// Invalidate 使凭证失效（重新从环境变量读取）
func (cm *CredentialManager) Invalidate(key string) {
    cm.mu.Lock()
    defer cm.mu.Unlock()
    delete(cm.cache, key)
}

// ListKeys 列出所有已配置的凭证 key
func (cm *CredentialManager) ListKeys() []string {
    cm.mu.RLock()
    defer cm.mu.RUnlock()
    
    keys := make([]string, 0, len(cm.cache))
    for key := range cm.cache {
        keys = append(keys, key)
    }
    return keys
}
```

### .gitignore 配置

```gitignore
# 凭证文件
.env
.env.*
!.env.example
credentials.json
tokens.json
*.pem
*.key
*.p12
*.pfx

# MCP 凭证
mcp_credentials/
*.mcp.json

# 临时凭证文件
.tmp_credentials
*.tmp_token
```

---

## 第四部分：审计日志

### 审计日志架构

```
审计日志记录的内容：
┌─────────────────────────────────────────────────────────────────────┐
│ 1. 谁（Who）: 用户 ID + 角色                                         │
│ 2. 做了什么（What）: 工具名称 + 参数摘要                             │
│ 3. 什么时候（When）: 时间戳                                         │
│ 4. 在哪里（Where）: 源 IP + 请求 ID                                  │
│ 5. 结果（Result）: 成功/失败/被拒绝                                  │
│ 6. 风险等级（Risk）: low/medium/high/critical                       │
│ 7. 是否审批（Approval）: 是否需要/已经审批                           │
└─────────────────────────────────────────────────────────────────────┘
```

### 审计日志实现

```go
package security

import (
    "context"
    "encoding/json"
    "fmt"
    "os"
    "sync"
    "time"
)

// AuditLogger 审计日志记录器
type AuditLogger struct {
    mu       sync.Mutex
    entries  []AuditEntry
    writer   *os.File
}

// NewAuditLogger 创建审计日志记录器
func NewAuditLogger(filePath string) (*AuditLogger, error) {
    file, err := os.OpenFile(filePath, os.O_CREATE|os.O_WRONLY|os.O_APPEND, 0644)
    if err != nil {
        return nil, err
    }
    
    return &AuditLogger{
        entries: make([]AuditEntry, 0),
        writer:  file,
    }, nil
}

// Log 记录审计日志
func (l *AuditLogger) Log(ctx context.Context, entry AuditEntry) error {
    entry.Timestamp = time.Now()
    entry.RequestID = getTraceID(ctx)
    
    l.mu.Lock()
    l.entries = append(l.entries, entry)
    l.mu.Unlock()
    
    // 写入文件
    data, err := json.Marshal(entry)
    if err != nil {
        return err
    }
    
    _, err = l.writer.Write(append(data, '\n'))
    return err
}

// GetEntries 获取审计日志条目
func (l *AuditLogger) GetEntries(filter Filter) []AuditEntry {
    l.mu.Lock()
    defer l.mu.Unlock()
    
    result := make([]AuditEntry, 0)
    for _, entry := range l.entries {
        if filter.Matches(entry) {
            result = append(result, entry)
        }
    }
    return result
}

type Filter struct {
    UserID      string
    ToolName    string
    RiskLevel   string
    StartTime   time.Time
    EndTime     time.Time
    Approved    *bool
}

func (f Filter) Matches(entry AuditEntry) bool {
    if f.UserID != "" && entry.UserID != f.UserID {
        return false
    }
    if f.ToolName != "" && entry.ToolName != f.ToolName {
        return false
    }
    if f.RiskLevel != "" && entry.RiskLevel != f.RiskLevel {
        return false
    }
    if !f.StartTime.IsZero() && entry.Timestamp.Before(f.StartTime) {
        return false
    }
    if !f.EndTime.IsZero() && entry.Timestamp.After(f.EndTime) {
        return false
    }
    if f.Approved != nil && entry.Approved != *f.Approved {
        return false
    }
    return true
}
```

---

## 第五部分：速率限制

### 速率限制器

```go
package security

import (
    "sync"
    "time"
)

// RateLimiter 速率限制器
type RateLimiter struct {
    mu         sync.Mutex
    requestLog map[string][]time.Time  // user_id → 请求时间列表
    maxPerMin  int                     // 每分钟最大请求数
    maxPerHour int                     // 每小时最大请求数
}

// NewRateLimiter 创建速率限制器
func NewRateLimiter(maxPerMin, maxPerHour int) *RateLimiter {
    return &RateLimiter{
        requestLog: make(map[string][]time.Time),
        maxPerMin:  maxPerMin,
        maxPerHour: maxPerHour,
    }
}

// Allow 检查是否允许请求
func (rl *RateLimiter) Allow(userID string) bool {
    rl.mu.Lock()
    defer rl.mu.Unlock()
    
    now := time.Now()
    oneMinAgo := now.Add(-time.Minute)
    oneHourAgo := now.Add(-time.Hour)
    
    // 清理过期记录
    var recentMinutes []time.Time
    var recentHours []time.Time
    
    for _, t := range rl.requestLog[userID] {
        if t.After(oneMinAgo) {
            recentMinutes = append(recentMinutes, t)
        }
        if t.After(oneHourAgo) {
            recentHours = append(recentHours, t)
        }
    }
    
    rl.requestLog[userID] = recentMinutes
    
    // 检查每分钟限制
    if len(recentMinutes) >= rl.maxPerMin {
        return false
    }
    
    // 检查每小时限制
    if len(recentHours) >= rl.maxPerHour {
        return false
    }
    
    // 记录本次请求
    rl.requestLog[userID] = append(recentMinutes, now)
    return true
}

// Reset 重置用户请求计数
func (rl *RateLimiter) Reset(userID string) {
    rl.mu.Lock()
    defer rl.mu.Unlock()
    delete(rl.requestLog, userID)
}
```

---

## 第六部分：自测题

### Q1: MCP 安全的三层防护是什么？

**A**:
1. **指令过滤**：检测系统指令注入、敏感词、危险操作模式
2. **参数校验**：工具白名单、参数长度、特殊字符、类型校验
3. **执行控制**：权限检查、审批流程、审计日志、速率限制

### Q2: 凭证管理的原则？

**A**:
- 绝不硬编码
- 从环境变量读取
- .gitignore 排除凭证文件
- 生产用密钥管理服务
- 演示用占位符

### Q3: 审计日志记录什么？

**A**: 谁（用户+角色）、做了什么（工具+参数）、什么时候（时间戳）、在哪里（IP+请求ID）、结果（成功/失败/拒绝）、风险等级、是否审批。

---

## 第七部分：生产实践

### 1. 安全配置

```
安全配置要点：
1. 高风险工具必须二次确认
2. 所有写操作记录审计日志
3. 凭证从环境变量读取
4. 定期轮换凭证
5. 监控异常调用模式
```

### 2. 权限管理

```
权限管理要点：
1. 角色最小权限原则
2. 定期审计权限分配
3. 临时权限自动过期
4. 跨租户隔离
```

### 3. 监控告警

```
监控告警要点：
1. 高风险操作实时告警
2. 异常调用模式检测
3. 速率限制告警
4. 凭证泄露检测
```
