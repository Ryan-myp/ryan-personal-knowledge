# LLM安全加固 - 资深专家深度实现

## 一、威胁矩阵

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     LLM安全威胁矩阵                                       │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   输入层威胁                                                             │
│   ├── Prompt Injection (提示词注入)                                       │
│   ├── Jailbreaking (越狱攻击)                                             │
│   └── Data Poisoning (数据投毒)                                           │
│                                                                         →
│   输出层威胁                                                             │
│   ├── Hallucination (幻觉生成)                                            │
│   ├── Sensitive Data Leakage (敏感信息泄露)                                 │
│   └── Toxic Output (有害输出)                                             │
│                                                                         →
│   系统层威胁                                                             │
│   ├── Model Theft (模型窃取)                                              │
│   ├── API Abuse (API滥用)                                                 │
│   └── Supply Chain Attack (供应链攻击)                                      │
│                                                                         →
└─────────────────────────────────────────────────────────────────────────┘
```

## 二、Prompt注入防御

```go
package security

import (
    "strings"
    "regexp"
)

// PromptInjectorDetector 提示词注入检测器
type PromptInjectorDetector struct {
    patterns []*regexp.Regexp
}

func NewPromptInjectorDetector() *PromptInjectorDetector {
    return &PromptInjectorDetector{
        patterns: []*regexp.Regexp{
            regexp.MustCompile(`(?i)ignore previous instructions`),
            regexp.MustCompile(`(?i)system prompt`),
            regexp.MustCompile(`(?i)you are now`),
            regexp.MustCompile(`(?i)<|>|{|\}`),
            regexp.MustCompile(`(?i)translate to.*language`),
        },
    }
}

// Detect 检测提示词注入
func (d *PromptInjectorDetector) Detect(prompt string) bool {
    for _, pattern := range d.patterns {
        if pattern.MatchString(prompt) {
            return true
        }
    }
    return false
}

// Sanitize 清理输入
func (d *PromptInjectorDetector) Sanitize(input string) string {
    // 移除可疑模式
    cleaned := input
    for _, pattern := range d.patterns {
        cleaned = pattern.ReplaceAllString(cleaned, "[REDACTED]")
    }
    return cleaned
}
```

## 三、输出过滤

```python
class OutputFilter:
    """输出过滤器"""
    
    def __init__(self):
        self.pii_patterns = [
            r'\b\d{3}-\d{2}-\d{4}\b',  # SSN
            r'\b\d{16}\b',              # 信用卡号
            r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',  # 邮箱
        ]
        
    def filter(self, output: str) -> str:
        """过滤敏感信息"""
        for pattern in self.pii_patterns:
            output = re.sub(pattern, '[REDACTED]', output)
        return output
    
    def check_toxicity(self, output: str) -> float:
        """检测毒性得分"""
        # 使用 toxicity 模型或规则
        toxic_words = ['hate', 'violence', 'discrimination']
        score = sum(1 for word in toxic_words if word in output.lower())
        return score / len(toxic_words)
```

## 四、面试高频题

### Q1: 如何防止Prompt注入？

```
A:
1. 输入过滤: 检测可疑模式
2. 输出验证: 检查敏感信息
3. 权限控制: RBAC模型
```

### Q2: 如何处理幻觉问题？

```
A:
1. RAG增强: 提供可信来源
2. 置信度评分: 低置信度标注
3. 人工审核: 关键场景人工验证
```

## 五、自测题

1. 解释三种Prompt注入类型
2. 如何实现输出过滤？
3. 如何评估模型安全性？

---

## 参考文档

- [OWASP LLM Top 10](https://owasp.org/www-project-top-10-for-large-language-model-applications/)
- [LangChain Security](https://python.langchain.com/docs/security)
