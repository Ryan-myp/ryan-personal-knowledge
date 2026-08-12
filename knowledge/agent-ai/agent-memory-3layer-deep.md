# Agent 记忆系统三层架构深度实现 - 短期/向量/图谱

> **版本**: v2.1  
> **日期**: 2026-08-14  
> **作者**: Ryan  
> **分类**: Agent/记忆  
> **代码密度**: 33%

---

## 一、三层记忆架构

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Agent 三层记忆系统                                 │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  L1: 短期记忆 (Working Memory)                               │   │
│  │  • 存储: 对话历史、当前任务上下文                             │   │
│  │  • 容量: 几百到几千token                                     │   │
│  │  • 持久性: 会话级别                                          │   │
│  │  • 检索: 直接访问 / 滑动窗口                                 │   │
│  │  • 实现: Redis String / 内存列表                             │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                              │                                      │
│                              ▼ (定期汇总)                            │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  L2: 向量记忆 (Semantic Memory)                              │   │
│  │  • 存储: 长期知识、经验、用户画像                             │   │
│  │  • 容量: 百万级向量                                          │   │
│  │  • 持久性: 持久化存储                                        │   │
│  │  • 检索: 向量相似度搜索 (Faiss/Qdrant)                       │   │
│  │  • 实现: embedding模型 + 向量数据库                          │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                              │                                      │
│                              ▼ (知识抽取)                            │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  L3: 图谱记忆 (Episodic Memory)                              │   │
│  │  • 存储: 实体关系、结构化知识                                 │   │
│  │  • 容量: 千万级节点边                                        │   │
│  │  • 持久性: 图数据库持久化                                     │   │
│  │  • 检索: 图遍历 / Cypher查询                                 │   │
│  │  • 实现: Neo4j / NebulaGraph                                 │   │
│  └─────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 二、遗忘曲线实现

```python
# memory/forgetting_curve.py
import math
from datetime import datetime, timedelta

class ForgettingCurve:
    """艾宾浩斯遗忘曲线"""
    
    # 关键时间点 (分钟)
    TIMEPOINTS = [1, 5, 30, 60*24, 60*24*2, 60*24*4, 60*24*7, 60*24*15, 60*24*30]
    
    # 各时间点的保留率
    RETENTION = [58, 44, 36, 33, 28, 25, 21, 17, 14]
    
    @classmethod
    def get_retention(cls, minutes_since_create: int) -> float:
        """计算当前保留率"""
        if minutes_since_create <= 0:
            return 1.0
        
        # 线性插值
        for i in range(len(cls.TIMEPOINTS) - 1):
            if cls.TIMEPOINTS[i] <= minutes_since_create <= cls.TIMEPOINTS[i+1]:
                t0, r0 = cls.TIMEPOINTS[i], cls.RETENTION[i]
                t1, r1 = cls.TIMEPOINTS[i+1], cls.RETENTION[i+1]
                ratio = (minutes_since_create - t0) / (t1 - t0)
                return r0 + (r1 - r0) * ratio
        
        # 超过最长周期
        return cls.RETENTION[-1]
    
    @classmethod
    def should_forget(cls, created_at: datetime, threshold: float = 0.15) -> bool:
        """判断是否需要遗忘"""
        minutes = (datetime.now() - created_at).total_seconds() / 60
        retention = cls.get_retention(int(minutes))
        return retention < threshold
    
    @classmethod
    def schedule_review(cls, last_reviewed: datetime) -> datetime:
        """安排下次复习时间"""
        # 简单策略: 间隔递增
        now = datetime.now()
        days_since = (now - last_reviewed).days
        
        if days_since < 1:
            return now + timedelta(hours=1)
        elif days_since < 3:
            return now + timedelta(days=2)
        elif days_since < 7:
            return now + timedelta(days=4)
        else:
            return now + timedelta(days=7)


class MemoryManager:
    """记忆管理器"""
    
    def __init__(self):
        self.short_term = []  # L1
        self.vector_db = None  # L2
        self.graph_db = None   # L3
    
    def store(self, content: str, metadata: dict):
        """存储到三层记忆"""
        # L1: 短期记忆
        self.short_term.append({
            'content': content,
            'created_at': datetime.now(),
            'metadata': metadata
        })
        
        # L2: 向量存储 (异步)
        self._store_to_vector(content, metadata)
        
        # L3: 图谱存储 (异步)
        self._store_to_graph(content, metadata)
    
    def retrieve(self, query: str, top_k: int = 5) -> list:
        """多路召回记忆"""
        results = []
        
        # L1: 短期记忆 (最近N条)
        recent = self.short_term[-20:]
        results.extend(recent)
        
        # L2: 向量搜索
        vector_results = self._vector_search(query, top_k)
        results.extend(vector_results)
        
        # L3: 图谱查询
        graph_results = self._graph_query(query)
        results.extend(graph_results)
        
        # 去重 + 排序
        return self._dedup_and_rank(results)[:top_k]
    
    def cleanup(self):
        """清理过期记忆"""
        self.short_term = [
            m for m in self.short_term
            if not ForgettingCurve.should_forget(m['created_at'])
        ]
```

---

## 三、自测题

1. **三层记忆为什么需要不同存储介质？**
   - 性能/成本/检索方式不同

2. **遗忘曲线的意义？**
   - 模拟人类记忆衰退，自动清理低价值信息

