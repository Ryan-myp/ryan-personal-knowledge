# Agent 安全护栏 v2 深度实现 - 多层防护体系

> **版本**: v2.1 (更新)  
> **日期**: 2026-08-13  
> **作者**: Ryan  
> **分类**: Agent/安全  
> **代码密度**: 35%

---

## 一、四层防护架构

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Agent 四层安全防护                                 │
│                                                                     │
│  Layer 4: 输出层 (Output Guard)                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │ • 敏感信息过滤 (PII/PII)                                    │   │
│  │ • 输出安全校验                                              │   │
│  │ • 合规性检查                                                │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                           │                                        │
│  Layer 3: 工具层 (Tool Guard)                                       │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │ • 权限校验 (RBAC/ABAC)                                      │   │
│  │ • 参数白名单                                                │   │
│  │ • 操作审计                                                  │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                           │                                        │
│  Layer 2: 推理层 (Reasoning Guard)                                  │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │ • 意图检测 (Jailbreak 检测)                                  │   │
│  │ • 思维链验证                                                │   │
│  │ • 幻觉检测                                                  │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                           │                                        │
│  Layer 1: 输入层 (Input Guard)                                      │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │ • Prompt 注入检测                                            │   │
│  │ • 内容安全过滤                                               │   │
│  │ • 输入长度/格式校验                                          │   │
│  └─────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 二、Jailbreak 检测

```go
// guard/jailbreak.go
package guard

import (
    "strings"
    "unicode"
)

// JailbreakDetector 注入攻击检测
type JailbreakDetector struct {
    patterns []Pattern
}

// Pattern 检测模式
type Pattern struct {
    Name     string
    Regex    string
    Severity int // 1-5
}

// Check 检测注入攻击
func (d *JailbreakDetector) Check(input string) *CheckResult {
    results := make([]Match, 0)
    
    for _, p := range d.patterns {
        if strings.Contains(input, p.Regex) {
            results = append(results, Match{
                Pattern:  p.Name,
                Severity: p.Severity,
                Text:     input,
            })
        }
    }
    
    // Base64 解码检测
    if containsBase64(input) {
        decoded := decodeBase64(input)
        for _, p := range d.patterns {
            if strings.Contains(decoded, p.Regex) {
                results = append(results, Match{
                    Pattern:  p.Name,
                    Severity: p.Severity + 1,
                    Text:     "[Base64 decoded]",
                })
            }
        }
    }
    
    return &CheckResult{
        IsMalicious: len(results) > 0,
        MaxSeverity: maxSeverity(results),
        Matches:    results,
    }
}

func containsBase64(s string) bool {
    b64chars := "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/="
    count := 0
    for _, r := range s {
        if strings.ContainsRune(b64chars, r) {
            count++
        }
    }
    return count > len(s)*0.8 && len(s) > 20
}
```

---

## 三、敏感信息过滤

```go
// guard/pii_filter.go
package guard

import (
    "regexp"
    "strings"
)

// PIIFilter 敏感信息过滤
type PIIFilter struct {
    patterns map[string]*regexp.Regexp
}

func NewPIIFilter() *PIIFilter {
    return &PIIFilter{
        patterns: map[string]*regexp.Regexp{
            "email":      regexp.MustCompile(`[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}`),
            "phone":      regexp.MustCompile(`\+?[\d\s\-()]{10,}`),
            "id_card":    regexp.MustCompile(`\d{17}[\dXx]`),
            "credit_card": regexp.MustCompile(`\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}`),
            "ip_address": regexp.MustCompile(`\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}`),
        },
    }
}

// Filter 过滤敏感信息
func (f *PIIFilter) Filter(text string) (string, []PIIMatch) {
    matches := make([]PIIMatch, 0)
    result := text
    
    for name, pattern := range f.patterns {
        found := pattern.FindAllString(text, -1)
        for _, match := range found {
            matches = append(matches, PIIMatch{
                Type:  name,
                Value: match,
            })
            // 脱敏替换
            result = strings.Replace(result, match, "***"+name+"***", 1)
        }
    }
    
    return result, matches
}
```

---

## 四、工具权限控制

```go
// guard/tool_guard.go
package guard

import (
    "context"
)

// ToolPermission 工具权限
type ToolPermission struct {
    ToolName string
    Levels   []string // read/write/admin
    Roles    []string // 允许的角色
}

// ToolGuard 工具防护
type ToolGuard struct {
    permissions map[string]*ToolPermission
    userRoles   map[string][]string // userID -> roles
}

// CheckPermission 检查权限
func (g *ToolGuard) CheckPermission(ctx context.Context, userID, toolName, action string) bool {
    perm, ok := g.permissions[toolName]
    if !ok {
        return false
    }
    
    userRoles := g.userRoles[userID]
    for _, role := range userRoles {
        for _, allowedRole := range perm.Roles {
            if role == allowedRole {
                for _, allowedAction := range perm.Levels {
                    if action == allowedAction {
                        return true
                    }
                }
            }
        }
    }
    return false
}
```

---

## 五、自测题

1. **为什么要多层防护？**
   - 单一防线容易被绕过，多层纵深防御提高安全性

2. **Jailbreak 检测的关键是什么？**
   - 覆盖常见攻击模式 + 隐式编码 (Base64/Unicode)

