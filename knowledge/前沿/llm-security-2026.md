# LLM 安全与防御趋势

> **文档级别**: Level 4  
> **创建日期**: 2026-08-13  
> **状态**: ✅ 已更新

---

## 一、安全威胁矩阵

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        LLM 安全威胁分类                                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  输入层                                                                     │
│  ├── Prompt Injection (提示注入)                                             │
│  ├── Jailbreak (越狱攻击)                                                   │
│  └── Data Poisoning (数据投毒)                                              │
│                                                                             │
│  输出层                                                                     │
│  ├── Hallucination (幻觉)                                                   │
│  ├── Toxic Output (有毒输出)                                                 │
│  └── Privacy Leak (隐私泄露)                                                 │
│                                                                             │
│  系统层                                                                     │
│  ├── RAG Injection (检索注入)                                                │
│  ├── Tool Manipulation (工具操控)                                            │
│  └── Resource Exhaustion (资源耗尽)                                          │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 二、参考资料

```
核心资源:
├── OWASP LLM Top 10: https://owasp.org/www-project-top-10-for-large-language-model-applications/
├── LLM Security: https://github.com/jthgenius/awesome-llm-security
└── Prompt Injection: https://www.promptingguide.ai/
```

---

*文档版本: v1.0*  
*最后更新: 2026-08-13*  
*作者: Ryan*
