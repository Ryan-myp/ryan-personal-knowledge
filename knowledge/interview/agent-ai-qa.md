# Agent AI 面试题库

> **文档级别**: Level 4  
> **创建日期**: 2026-08-13  
> **状态**: ✅ 已创建

---

## 一、Agent 架构

### Q1: LangGraph vs CrewAI vs AutoGen 怎么选？

| 维度 | LangGraph | CrewAI | AutoGen |
|------|-----------|--------|---------|
| 架构 | 状态机图 | 多智能体 | 对话驱动 |
| 循环支持 | ✅ | ❌ | ✅ |
| 人类介入 | 中 | 低 | 高 |
| 适用场景 | 复杂工作流 | 团队协作 | 代码执行 |
| 学习曲线 | 陡峭 | 平缓 | 中等 |

### Q2: RAG 优化有哪些手段？

```
优化策略:
├── 查询优化
│   ├── HyDE: 假设文档生成
│   ├── 查询重写
│   └── 查询分解
├── 召回优化
│   ├── 多路召回 (向量+关键词)
│   ├── RRF 融合
│   └── 混合检索
├── 重排优化
│   ├── Cross-Encoder
│   └── 规则排序
└── 评估优化
    ├── RAGAS 指标
    ├── 自动化测试
    └── 人工评估
```

### Q3: Agent 记忆系统如何设计？

```
三层架构:
├── 短期记忆 (Working Memory)
│   ├── 当前对话上下文
│   ├── Token 限制: ~4K
│   └── 实现: 消息历史
├── 中长期记忆 (Episodic)
│   ├── 事件存储
│   ├── 时间序列
│   └── 实现: Vector DB
└── 长期记忆 (Semantic)
    ├── 知识库
    ├── 事实存储
    └── 实现: Knowledge Graph
```

---

## 二、参考资料

```
核心框架:
├── LangGraph: https://langchain-ai.github.io/langgraph/
├── LlamaIndex: https://www.llamaindex.ai/
└── Haystack: https://haystack.deepset.ai/
```

---

*文档版本: v1.0*  
*最后更新: 2026-08-13*  
*作者: Ryan*
