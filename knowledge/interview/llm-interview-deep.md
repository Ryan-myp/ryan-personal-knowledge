# LLM 面试题库深度实现 - 大模型专项面试

> **版本**: v2.1  
> **日期**: 2026-08-14  
> **作者**: Ryan  
> **分类**: 面试/LLM  
> **代码密度**: 28%

---

## 面试题目

### Q1. Transformer架构核心组件？

```go
// 核心组件
type Transformer struct {
    Embedding    EmbeddingLayer      // 词嵌入
    Attention    MultiHeadAttention  // 多头注意力
    FeedForward  FeedForwardNetwork  // 前馈网络
    Norm         LayerNormalization  // 层归一化
}
```

### Q2. 什么是Token？如何计算？

```go
// Token计算
func CountTokens(text string) int {
    // BPE分词
    tokens := bpe.Split(text)
    return len(tokens)
}

// Token成本估算
func EstimateCost(tokens int, model string) float64 {
    price := getModelPrice(model)
    return float64(tokens) / 1_000_000 * price
}
```

### Q3. 什么是长上下文问题？如何解决？

```go
// 解决方案
var solutions = map[string]string{
    "滑动窗口":   "只保留最近N个token",
    "长上下文模型": "使用支持32K/128K的模型",
    "检索增强":   "RAG检索相关片段",
    "压缩":     "摘要压缩早期内容",
}
```

### Q4. LoRA微调原理？

```go
// LoRA实现
type LoRALayer struct {
    original  nn.Linear
    loraA     nn.Linear  // 低秩矩阵A
    loraB     nn.Linear  // 低秩矩阵B
    alpha     float64
}

func (l *LoRALayer) Forward(x Tensor) Tensor {
    return l.original(x) + l.alpha * l.loraB(l.loraA(x))
}
```

### Q5. KV Cache是什么？

```go
// KV Cache
type KVCache struct {
    keys   [][]Tensor  // 每层的key缓存
    values [][]Tensor  // 每层的value缓存
}

// 加速生成
func (c *KVCache) Get(key, value int) (Tensor, Tensor) {
    return c.keys[key], c.values[value]
}
```

---

## 自测题

1. **Transformer为什么用多头注意力？**
   - 捕捉不同子空间的信息

2. **LoRA相比全量微调的优势？**
   - 参数量少，训练快，效果接近

