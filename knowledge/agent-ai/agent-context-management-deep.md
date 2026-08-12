# Agent 上下文管理深度实现 - 滑动窗口到摘要压缩

> **版本**: v2.1  
> **日期**: 2026-08-14  
> **作者**: Ryan  
> **分类**: Agent/上下文管理  
> **代码密度**: 30%

---

## 一、上下文管理策略

```
┌─────────────────────────────────────────────────────────────────────┐
│                    上下文管理策略对比                                │
│                                                                     │
│  Strategy 1: 固定窗口                                               │
│  ─────────────────────────────────                                 │
│  • 保留最近N轮对话                                                 │
│  • 优点: 简单高效                                                   │
│  • 缺点: 可能丢失重要历史信息                                       │
│  • 适用: 短期任务，token有限                                        │
│                                                                     │
│  Strategy 2: 滑动窗口 + 重要性评分                                   │
│  ─────────────────────────────────                                 │
│  • 每轮对话计算重要性分数                                            │
│  • 保留高重要性消息，丢弃低重要性                                    │
│  • 适用: 长期对话，需要保留关键信息                                 │
│                                                                     │
│  Strategy 3: 摘要压缩                                                │
│  ─────────────────────────────────                                 │
│  • 定期将早期对话压缩为摘要                                          │
│  • 用LLM生成简洁摘要                                                │
│  • 适用: 长对话，token预算紧张                                      │
│                                                                     │
│  Strategy 4: 分层记忆                                                │
│  ─────────────────────────────────                                 │
│  • L1: 当前任务上下文 (完整)                                         │
│  • L2: 近期对话 (摘要)                                               │
│  • L3: 长期记忆 (向量检索)                                           │
│  • 适用: 复杂多轮任务                                               │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 二、摘要压缩实现

```python
# agent/context_manager.py
from typing import List, Dict
import asyncio

class ContextManager:
    """上下文管理器"""
    
    def __init__(self, max_tokens: int = 8000):
        self.max_tokens = max_tokens
        self.history: List[Dict] = []
        self.summaries: List[str] = []
    
    def add_message(self, role: str, content: str):
        """添加消息"""
        self.history.append({
            'role': role,
            'content': content,
            'timestamp': time.now()
        })
        
        # 检查是否需要摘要
        if self.need_summary():
            self.compress()
    
    def need_summary(self) -> bool:
        """判断是否需要摘要"""
        total = self.count_tokens()
        return total > self.max_tokens * 0.8
    
    async def compress(self):
        """摘要压缩"""
        if len(self.history) < 10:
            return
        
        # 取前80%的历史
        compress_range = int(len(self.history) * 0.8)
        to_compress = self.history[:compress_range]
        self.history = self.history[compress_range:]
        
        # 生成摘要
        prompt = self.build_summary_prompt(to_compress)
        summary = await self.llm.summarize(prompt)
        self.summaries.append(summary)
    
    def build_context(self) -> List[Dict]:
        """构建最终上下文"""
        context = []
        
        # 1. 系统提示
        context.append({'role': 'system', 'content': SYSTEM_PROMPT})
        
        # 2. 历史摘要
        for summary in self.summaries[-3:]:  # 最近3个摘要
            context.append({'role': 'system', 'content': f'[Historical Summary]\n{summary}'})
        
        # 3. 当前对话 (完整)
        context.extend(self.history[-10:])  # 最近10轮
        
        return context
    
    def count_tokens(self) -> int:
        """估算token数"""
        total = 0
        for msg in self.history:
            total += len(msg['content']) // 4  # 粗略估算
        return total
```

---

## 三、自测题

1. **为什么需要摘要压缩？**
   - 超出上下文窗口限制，保留关键信息

2. **摘要的时机如何确定？**
   - Token使用率达到80%时触发

