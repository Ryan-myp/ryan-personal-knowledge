# Agent 安全护栏 V3 深度实现 - 多层防护与对抗防御

> **版本**: v3.0  
> **日期**: 2026-08-14  
> **作者**: Ryan  
> **分类**: Agent/安全  
> **代码密度**: 35%

---

## 一、四层防护架构

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Agent 四层安全防护                                 │
│                                                                     │
│  Layer 1: Input Guard (输入防护)                                      │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  • Prompt Injection 检测                                     │   │
│  │  • Jailbreak 模式识别                                        │   │
│  │  • 恶意关键词过滤                                            │   │
│  │  • 敏感信息提取 (PII)                                        │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                           │                                         │
│                           ▼                                         │
│  Layer 2: Reasoning Guard (推理防护)                                 │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  • 思维链完整性验证                                          │   │
│  │  • 逻辑一致性检查                                            │   │
│  │  • 幻觉检测                                                  │   │
│  │  • 越狱尝试识别                                              │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                           │                                         │
│                           ▼                                         │
│  Layer 3: Tool Guard (工具防护)                                      │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  • RBAC 权限控制                                             │   │
│  │  • 工具调用审计                                              │   │
│  │  • 参数校验                                                  │   │
│  │  • 危险操作拦截                                              │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                           │                                         │
│                           ▼                                         │
│  Layer 4: Output Guard (输出防护)                                    │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  • 敏感信息过滤                                              │   │
│  │  • 有害内容检测                                              │   │
│  │  • 格式验证                                                  │   │
│  │  • 合规性检查                                                │   │
│  └─────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 二、Jailbreak 检测

```go
// agent/jailbreak_detect.go
package agent

import (
    "strings"
    "unicode"
)

// JailbreakDetector Jailbreak检测器
type JailbreakDetector struct {
    patterns []JailbreakPattern
}

// JailbreakPattern 逃逸模式
type JailbreakPattern struct {
    Name        string
    Regex       string
    Severity    int  // 1-3
    Description string
}

// Detect 检测jailbreak
func (d *JailbreakDetector) Detect(input string) *JailbreakResult {
    results := make([]JailbreakHit, 0)
    
    // 1. 角色扮演检测
    if detectRoleplay(input) {
        results = append(results, JailbreakHit{
            Pattern: "角色扮演",
            Severity: 2,
        })
    }
    
    // 2. 指令覆盖检测
    if detectInstructionOverride(input) {
        results = append(results, JailbreakHit{
            Pattern: "指令覆盖",
            Severity: 3,
        })
    }
    
    // 3. 编码绕过检测
    if detectEncodingBypass(input) {
        results = append(results, JailbreakHit{
            Pattern: "编码绕过",
            Severity: 2,
        })
    }
    
    // 4. 多语言攻击
    if detectMultiLanguageAttack(input) {
        results = append(results, JailbreakHit{
            Pattern: "多语言攻击",
            Severity: 1,
        })
    }
    
    return &JailbreakResult{
        Hits:       results,
        IsJailbreak: len(results) > 0,
        RiskScore:  d.calculateRiskScore(results),
    }
}

// detectInstructionOverride 检测指令覆盖
func detectInstructionOverride(input string) bool {
    signals := []string{
        "ignore previous", "forget all", "system prompt",
        "你现在的角色是", "从今以后", "作为开发者",
    }
    for _, s := range signals {
        if strings.Contains(strings.ToLower(input), s) {
            return true
        }
    }
    return false
}

// detectEncodingBypass 检测编码绕过
func detectEncodingBypass(input string) bool {
    // Base64, Hex, Unicode 等编码检测
    if isBase64(input) || isHexEncoded(input) {
        return true
    }
    // Unicode 控制字符
    for _, r := range input {
        if unicode.IsControl(r) && r != '\n' && r != '\t' {
            return true
        }
    }
    return false
}
```

---

## 三、PII 过滤

```python
# agent/pii_filter.py
import re
from typing import List, Tuple

class PIIFilter:
    """PII敏感信息过滤器"""
    
    # 正则模式
    PATTERNS = {
        'email': r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}',
        'phone': r'(?:\+?86[-\s]?)?1[3-9]\d{9}',
        'id_card': r'\d{17}[\dXx]',
        'bank_card': r'\d{13,19}',
        'ip_address': r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}',
    }
    
    def filter(self, text: str) -> Tuple[str, List[dict]]:
        """过滤PII并返回脱敏文本和匹配信息"""
        matched = []
        filtered = text
        
        for pii_type, pattern in self.PATTERNS.items():
            matches = re.findall(pattern, filtered)
            for match in matches:
                # 脱敏处理
                masked = self.mask(match, pii_type)
                filtered = filtered.replace(match, masked)
                matched.append({
                    'type': pii_type,
                    'original': match,
                    'masked': masked,
                })
        
        return filtered, matched
    
    def mask(self, value: str, pii_type: str) -> str:
        """根据类型脱敏"""
        if pii_type == 'email':
            parts = value.split('@')
            return f"{parts[0][0]}***@{parts[1]}"
        elif pii_type == 'phone':
            return value[:3] + '****' + value[7:]
        elif pii_type == 'id_card':
            return value[:6] + '******' + value[14:]
        return '***REDACTED***'
```

---

## 四、自测题

1. **为什么需要多层防护而不是单层？**
   - 攻击者可能绕过单层检测，多层提供纵深防御

2. **Jailbreak检测的关键特征？**
   - 角色覆盖指令、编码绕过、多语言混合

