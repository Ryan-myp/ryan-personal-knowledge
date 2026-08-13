# AI安全与鲁棒性 - 资深专家深度实现

## 一、威胁矩阵

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    AI安全威胁矩阵                                          │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   威胁类型              | 攻击方式                  | 防御策略          │
│   ──────────────────────┼─────────────────────────┼───────────────────│
│   Prompt注入           | 恶意提示词                | 输入过滤          │
│   数据投毒             | 污染训练数据              | 数据清洗          │
│   模型窃取             | API调用提取              | 访问控制          │
│   对抗样本             | 扰动输入                  | 鲁棒训练          │
│   成员推断             | 推断训练数据              | 差分隐私          │
│                                                                         →
└─────────────────────────────────────────────────────────────────────────┘
```

## 二、防御实现

```go
package ai_security

import (
    "context"
)

// SecurityGuard 安全护栏
type SecurityGuard struct {
    inputFilter   *InputFilter
    outputMonitor *OutputMonitor
    auditLog      *AuditLog
}

// InputFilter 输入过滤器
type InputFilter struct {
    patterns []string
    model    *DetectionModel
}

func (f *InputFilter) Filter(ctx context.Context, input string) (*FilterResult, error) {
    // 关键词过滤
    if contains(input, f.patterns) {
        return &FilterResult{Blocked: true, Reason: "pattern_match"}, nil
    }
    
    // 语义检测
    isMalicious := f.model.Detect(input)
    if isMalicious {
        return &FilterResult{Blocked: true, Reason: "semantic_malicious"}, nil
    }
    
    return &FilterResult{Blocked: false}, nil
}

// OutputMonitor 输出监控
type OutputMonitor struct {
    sensitivity float32
}

func (m *OutputMonitor) Monitor(output string) (*MonitorResult, error) {
    // PII检测
    piiCount := countPII(output)
    
    // 毒性检测
    toxicity := detectToxicity(output)
    
    return &MonitorResult{
        PIICount: piiCount,
        Toxicity: toxicity,
    }, nil
}
```

## 三、面试高频题

### Q1: 如何防御Prompt注入？

```
A:
1. 输入验证
2. 角色隔离
3. 输出监控
```

### Q2: 如何实现差分隐私？

```
A:
1. 噪声添加
2. 敏感度控制
3. 预算分配
```

## 四、自测题

1. 解释安全威胁类型
2. 如何实现输入过滤？
3. 如何实现输出监控？

---

## 参考文档

- [OWASP Top 10 LLM](https://owasp.org/www-project-top-10-for-large-language-model-applications/)
- [LLM Security](https://github.com/gotomaybee/awesome-llm-security)
