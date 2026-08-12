# LLM 微调生产实践深度实现 - LoRA到RLHF

> **版本**: v2.1  
> **日期**: 2026-08-14  
> **作者**: Ryan  
> **分类**: Agent/LLM  
> **代码密度**: 30%

---

## 一、微调方法对比

```
┌─────────────────────────────────────────────────────────────────────┐
│                    LLM 微调方法对比                                  │
│                                                                     │
│  ┌──────────────┬──────────┬──────────┬──────────────────────────┐ │
│  │    方法       │  参数量   │  训练速度 │        适用场景          │ │
│  ├──────────────┼──────────┼──────────┼──────────────────────────┤ │
│  │ Full Fine-tune│ 全部参数  │ 慢       │ 数据充足/领域差异大       │ │
│  │ LoRA         │ 0.1-1%   │ 快       │ 大多数场景推荐            │ │
│  │ QLoRA        │ 0.01-0.1% │ 最快     │ 资源受限                  │ │
│  │ RLHF         │ 少量     │ 中       │ 对齐人类偏好              │ │
│  │ DPO          │ 无       │ 快       │ 替代RLHF的新方法          │ │
│  └──────────────┴──────────┴──────────┴──────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 二、LoRA 实现

```python
# llm/finetuning/lora.py
import torch
import torch.nn as nn
import torch.nn.functional as F

class LoRALayer(nn.Module):
    """LoRA适配器层"""
    
    def __init__(self, in_features, out_features, r=8, alpha=16):
        super().__init__()
        self.r = r
        self.alpha = alpha
        
        # 低秩矩阵
        self.lora_A = nn.Parameter(torch.zeros(in_features, r))
        self.lora_B = nn.Parameter(torch.zeros(r, out_features))
        
        # 缩放因子
        self.scaling = alpha / r
        
        # 初始化
        nn.init.kaiming_uniform_(self.lora_A, a=5**0.5)
        nn.init.zeros_(self.lora_B)
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # 原始权重 + LoRA调整
        delta = self.lora_B @ self.lora_A
        return x @ delta.T * self.scaling


class LoRAModel(nn.Module):
    """带LoRA的模型包装"""
    
    def __init__(self, base_model, lora_layers=["q_proj", "v_proj"]):
        super().__init__()
        self.base_model = base_model
        self.lora_modules = {}
        
        # 注入LoRA层
        for name, module in base_model.named_modules():
            if isinstance(module, nn.Linear) and any(k in name for k in lora_layers):
                lora = LoRALayer(module.in_features, module.out_features)
                self.lora_modules[name] = lora
    
    def forward(self, x):
        # 这里简化实现，实际需要hook机制
        return self.base_model(x)
    
    def train_lora_only(self):
        """只训练LoRA参数"""
        for param in self.base_model.parameters():
            param.requires_grad = False
        for lora in self.lora_modules.values():
            for param in lora.parameters():
                param.requires_grad = True
```

---

## 三、RLHF 三阶段

```
┌─────────────────────────────────────────────────────────────────────┐
│                    RLHF 三阶段流程                                   │
│                                                                     │
│  Phase 1: SFT (Supervised Fine-Tuning)                              │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  输入: 高质量指令数据集                                       │   │
│  │  目标: 让模型学会遵循指令格式                                 │   │
│  │  输出: SFT模型                                              │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                           │                                         │
│                           ▼                                         │
│  Phase 2: Reward Model Training                                    │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  输入: 人类偏好标注数据 (A > B / A = B / B > A)             │   │
│  │  目标: 学习人类的奖励函数                                     │   │
│  │  输出: Reward Model                                         │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                           │                                         │
│                           ▼                                         │
│  Phase 3: PPO (Proximal Policy Optimization)                       │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  输入: SFT模型 + Reward Model                                 │   │
│  │  目标: 优化策略使期望奖励最大化                                │   │
│  │  输出: 最终对齐模型                                           │   │
│  └─────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 四、自测题

1. **LoRA为什么能减少参数量？**
   - 冻结原有权重，只训练低秩分解矩阵

2. **RLHF相比直接SFT的优势？**
   - 更好地对齐人类价值观，减少有害输出

