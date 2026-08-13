# LLM微调生产实践 - 资深专家深度实现

## 一、微调策略

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    LLM 微调策略对比                                        │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   方法                | 参数量    | 成本      | 效果       | 适用场景      │
│   ────────────────────┼───────────┼───────────┼────────────┼──────────────│
│   Full Fine-tuning    | 全部      | 高        | 最佳       | 数据充足      │
│   LoRA                | 0.1-1%   | 中        | 良好       | 大多数场景    │
│   QLoRA               | 0.1-1%   | 低        | 良好       | 资源受限      │
│   Prompt Tuning       | 0.01%    | 极低      | 一般       | 简单任务      │
│   Adapter             | 1-5%     | 中        | 良好       | 多任务        │
│                                                                         →
└─────────────────────────────────────────────────────────────────────────┘
```

## 二、LoRA实现

```go
package lora

import (
    "torch"
)

// LoRALayer LoRA层
type LoRALayer struct {
    base   torch.nn.Module
    rank   int
    alpha  float32
    
    // LoRA参数
    A torch.nn.Parameter  // 降维矩阵
    B torch.nn.Parameter  // 升维矩阵
}

func NewLoRALayer(base torch.nn.Module, rank int) *LoRALayer {
    in_features := base.InFeatures()
    out_features := base.OutFeatures()
    
    scale := float32(2.0 / float32(in_features+out_features))
    
    return &LoRALayer{
        base: base,
        rank: rank,
        A:    torch.randn(out_features, in_features) * scale,
        B:    torch.zeros(in_features, rank),
    }
}

func (l *LoRALayer) Forward(x torch.Tensor) torch.Tensor {
    // 原始输出
    base_output := l.base.Forward(x)
    
    // LoRA输出
    lora_output := torch.matmul(
        torch.matmul(x, l.A), 
        l.B,
    ) * (l.alpha / float32(l.rank))
    
    return base_output + lora_output
}
```

## 三、面试高频题

### Q1: LoRA原理是什么？

```
A:
1. 低秩分解
2. 冻结原始权重
3. 只训练低秩矩阵
```

### Q2: 如何选择Rank？

```
A:
1. Rank越大表达能力越强
2. 但需要更多显存
3. 通常8-64足够
```

## 四、自测题

1. 解释微调策略
2. 如何实现LoRA？
3. 如何调优？

---

## 参考文档

- [QLoRA](https://arxiv.org/abs/2305.14314)
- [LoRA](https://arxiv.org/abs/2106.09685)
