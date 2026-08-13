# 向量数据库架构 - 资深专家深度实现

## 一、核心架构

```
┌─────────────────────────────────────────────────────────────────────────┐
│                   向量数据库架构                                           │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   写入路径                  查询路径                                      │
│   ┌─────────┐             ┌─────────┐                                    │
│   │ Embed   │──►│  Index   │──►│ Search   │                            │
│   │ 生成    │   │ 构建    │   │ 检索     │                              │
│   └─────────┘   └────┬────┘   └────┬────┘                            │
│                      │              │                                  │
│                ┌─────┴─────┐    ┌────┴────┐                            │
│                │ HNSW/IVF  │    │ 排序    │                            │
│                │ 索引      │    │ 返回    │                            │
│                └───────────┘    └─────────┘                            │
│                                                                         →
└─────────────────────────────────────────────────────────────────────────┘
```

## 二、HNSW索引实现

```go
package vector

import (
    "container/heap"
)

// HNSW 图索引
type HNSW struct {
    layers    [][]*Node
    entry     *Node
    M         int       // 最大连接数
    efConstruct int    // 构建时搜索宽度
}

type Node struct {
    ID       uint64
    Vector   []float32
    Layers   [][]*Neighbor
}

type Neighbor struct {
    Node    *Node
    Distance float32
}

// Search 近似最近邻搜索
func (h *HNSW) Search(query []float32, ef int) ([]*Node, error) {
    // 从入口点开始搜索
    candidates := make(PriorityQueue, 0, ef)
    heap.Init(&candidates)
    
    visited := make(map[uint64]bool)
    current := h.entry
    
    // 贪婪搜索
    for {
        dist := cosineDistance(current.Vector, query)
        heap.Push(&candidates, &Item{Node: current, Dist: dist})
        visited[current.ID] = true
        
        // 扩展到邻居
        for layer := range current.Layers {
            for _, neighbor := range current.Layers[layer] {
                if !visited[neighbor.Node.ID] {
                    heap.Push(&candidates, &Item{
                        Node: neighbor.Node,
                        Dist: cosineDistance(neighbor.Node.Vector, query),
                    })
                }
            }
        }
        
        if candidates.Len() > ef {
            heap.Pop(&candidates)
        }
        
        if candidates.Len() == 0 {
            break
        }
        current = candidates[0].(*Item).Node
    }
    
    return candidates.items, nil
}
```

## 三、面试高频题

### Q1: 为什么用HNSW而不是 brute force？

```
A:
1. O(log N)查询复杂度
2. 内存友好
3. 近似但有保证
```

### Q2: 如何选择维度？

```
A:
1. 384-1536常见
2. 高维需降维
3. 考虑精度需求
```

## 四、自测题

1. 解释HNSW算法
2. 如何选择参数？
3. 如何扩展？

---

## 参考文档

- [Milvus](https://milvus.io/)
- [Qdrant](https://qdrant.tech/)
- [Weaviate](https://weaviate.io/)
