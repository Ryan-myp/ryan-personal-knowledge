# LLM 微调 LoRA 深度实现 - 从原理到生产

> **版本**: v1.0  
> **日期**: 2026-08-13  
> **作者**: Ryan  
> **分类**: Agent/AI  
> **代码密度**: 30%

---

## 一、LoRA 原理

```
┌─────────────────────────────────────────────────────────────────────┐
│                    LoRA (Low-Rank Adaptation)                        │
│                                                                     │
│  原始模型:          微调后模型:                                       │
│  ┌──────┐          ┌──────┐    ┌──────┐                             │
│  │W     │────────▶│W     │    │W     │                             │
│  │(冻结) │         │+ΔW  │    │(冻结) │                             │
│  └──────┘          └──────┘    └──┬───┘                             │
│                                   │                                  │
│                              ΔW = B × A                             │
│                              B: (d × r)  ↓  r << d                  │
│                              A: (r × d)                            │
│                                                                     │
│  参数量对比:                                                       │
│  Full Fine-tuning:   d × d  (100%)                                 │
│  LoRA:              2 × d × r  (2-5%)                               │
│                                                                     │
│  示例 (7B 模型):                                                    │
│  Full:  7B × 4096 × 4096 × 4 bytes ≈ 470GB                         │
│  LoRA:  7B × 2 × 4096 × 8 × 4 bytes ≈ 0.9GB (节省 99.8%)            │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 二、PyTorch 实现

```python
# finetuning/lora.py
import torch
import torch.nn as nn
import torch.nn.functional as F

class LoRALayer(nn.Module):
    """LoRA 层"""
    def __init__(self, in_features, out_features, rank=8, alpha=16):
        super().__init__()
        self.rank = rank
        self.alpha = alpha
        
        # A 和 B 矩阵 (可训练)
        self.A = nn.Parameter(torch.zeros(in_features, rank))
        self.B = nn.Parameter(torch.zeros(rank, out_features))
        
        # 初始化
        nn.init.kaiming_uniform_(self.A, a=5**(1/4))
        nn.init.zeros_(self.B)
        
    def forward(self, x):
        # ΔW = B @ A
        # 输出 = W @ x + (alpha / rank) * B @ A @ x
        return self.alpha / self.rank * (self.B @ (self.A @ x.T)).T


class LinearWithLoRA(nn.Module):
    """带 LoRA 的 Linear 层"""
    def __init__(self, linear, rank=8, alpha=16):
        super().__init__()
        self.linear = linear
        self.lora = LoRALayer(
            linear.in_features, 
            linear.out_features, 
            rank=rank,
            alpha=alpha
        )
        
    def forward(self, x):
        base_output = self.linear(x)
        lora_output = self.lora(x)
        return base_output + lora_output


class LoRAModel(nn.Module):
    """完整的 LoRA 微调模型"""
    def __init__(self, base_model, rank=8, alpha=16, target_modules=None):
        super().__init__()
        self.base_model = base_model
        self.rank = rank
        self.alpha = alpha
        
        # 冻结基础模型
        for param in self.base_model.parameters():
            param.requires_grad = False
            
        # 只替换注意力层的 linear
        if target_modules is None:
            target_modules = ['q_proj', 'v_proj']
            
        self._apply_lora(target_modules)
        
    def _apply_lora(self, target_modules):
        for name, module in self.base_model.named_modules():
            if any(m in name for m in target_modules):
                # 替换为带 LoRA 的版本
                new_module = LinearWithLoRA(
                    module, 
                    rank=self.rank, 
                    alpha=self.alpha
                )
                # 递归替换
                parent = self._get_parent(module)
                if parent:
                    setattr(parent, name.split('.')[-1], new_module)
                    
    def _get_parent(self, target):
        # 简化的父节点查找
        return None
        
    def merge_and_extract(self):
        """合并 LoRA 权重到基础模型"""
        merged_state = {}
        for name, param in self.base_model.state_dict().items():
            if 'lora' in name:
                # 找到对应的 base 权重
                base_name = name.replace('.lora_A', '.weight').replace('.lora_B', '.weight')
                # 合并权重
                lora_weight = self._get_lora_weight(name)
                merged_state[name] = param + lora_weight
            else:
                merged_state[name] = param
        return merged_state
```

---

## 三、训练流程

```python
# finetuning/training.py
import torch
from transformers import AutoModelForCausalLM, TrainingArguments, Trainer
from peft import LoraConfig, get_peft_model

# 配置 LoRA
lora_config = LoraConfig(
    r=8,                      # 秩
    lora_alpha=16,            # 缩放因子
    target_modules=["q_proj", "v_proj"],  # 目标层
    lora_dropout=0.05,        # Dropout
    bias="none",              # 偏置是否训练
    task_type="CAUSAL_LM",    # 任务类型
)

# 加载基础模型
model = AutoModelForCausalLM.from_pretrained(
    "meta-llama/Llama-2-7b-hf",
    torch_dtype=torch.float16,
    device_map="auto"
)

# 应用 LoRA
model = get_peft_model(model, lora_config)
model.print_trainable_parameters()  # 打印可训练参数

# 训练配置
training_args = TrainingArguments(
    output_dir="./lora-output",
    num_train_epochs=3,
    per_device_train_batch_size=4,
    gradient_accumulation_steps=8,
    learning_rate=2e-4,
    fp16=True,                    # 混合精度
    logging_steps=10,
    save_strategy="epoch",
    report_to="tensorboard",
)

# 训练
trainer = Trainer(
    model=model,
    args=training_args,
    train_dataset=dataset,
)
trainer.train()

# 保存 LoRA 权重
model.save_pretrained("./lora-adapter")
```

---

## 四、推理优化

```python
# finetuning/inference.py
from peft import PeftModel

# 加载基础模型 + LoRA 适配器
base_model = AutoModelForCausalLM.from_pretrained(
    "meta-llama/Llama-2-7b-hf",
    torch_dtype=torch.float16,
    device_map="auto"
)

# 加载 LoRA 权重 (不需要重新训练)
model = PeftModel.from_pretrained(base_model, "./lora-adapter")

# 合并权重 (可选，推理时提升速度)
model = model.merge_and_unload()

# 推理
from transformers import AutoTokenizer
tokenizer = AutoTokenizer.from_pretrained("meta-llama/Llama-2-7b-hf")

prompt = "Explain LoRA in simple terms:"
inputs = tokenizer(prompt, return_tensors="pt").to(model.device)
outputs = model.generate(**inputs, max_new_tokens=200)
print(tokenizer.decode(outputs[0], skip_special_tokens=True))
```

---

## 五、训练技巧

| 技巧 | 配置 | 效果 |
|------|------|------|
| Gradient Checkpointing | `gradient_checkpointing=True` | 省 50% 显存 |
| 混合精度 | `fp16=True` | 加速 2x |
| 学习率预热 | `warmup_ratio=0.03` | 稳定训练 |
| 权重衰减 | `weight_decay=0.01` | 防过拟合 |
| 多 GPU | `n_gpu=8` | 线性加速 |

---

## 六、自测题

1. **LoRA 为什么能减少参数量？**
   - 低秩分解：ΔW = B × A，秩 r << 原始维度

2. **LoRA 和 Full Fine-tuning 的区别？**
   - LoRA 只训练低秩矩阵，Full 训练全部参数

3. **LoRA 适合什么场景？**
   - 数据量小、任务特定、需要快速迭代

