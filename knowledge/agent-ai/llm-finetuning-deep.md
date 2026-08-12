# LLM 微调与提示工程深度实现

> **文档级别**: Level 5 - 专家级  
> **创建日期**: 2026-08-13  
> **状态**: ✅ 已补齐

---

## 一、微调策略选择

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     微调策略对比矩阵                                        │
├─────────────────┬─────────────┬─────────────┬─────────────┬─────────────────┤
│     策略        │   成本      │   效果      │   速度      │     适用场景    │
├─────────────────┼─────────────┼─────────────┼─────────────┼─────────────────┤
│ Prompt Tuning   │ 低          │ 中等        │ 快          │ 格式转换        │
│ LoRA            │ 中          │ 高          │ 中          │ 领域适配        │
│ Full Fine-tune  │ 高          │ 最高        │ 慢          │ 深度定制        │
│ RAG + Fine-tune │ 中高        │ 最高        │ 中          │ 知识密集型      │
└─────────────────┴─────────────┴─────────────┴─────────────┴─────────────────┘
```

---

## 二、LoRA 微调实现

```python
# 文件: finetuning/lora_ad_bidding.py

from peft import LoraConfig, get_peft_model
from transformers import AutoModelForCausalLM, Trainer, TrainingArguments
import torch

# ─── 配置 LoRA ───
lora_config = LoraConfig(
    r=16,                    # 低秩维度
    lora_alpha=32,           # 缩放因子
    target_modules=["q_proj", "v_proj"],  # 目标层
    lora_dropout=0.1,        #  dropout
    bias="none",
    task_type="CAUSAL_LM"
)

# ─── 加载基础模型 ───
base_model = AutoModelForCausalLM.from_pretrained(
    "Qwen/Qwen2-7B",
    torch_dtype=torch.bfloat16,
    device_map="auto"
)

# ─── 应用 LoRA ───
model = get_peft_model(base_model, lora_config)
model.print_trainable_parameters()
# trainable params: 0.17% || all params: 7,468,315,136

# ─── 训练配置 ───
training_args = TrainingArguments(
    output_dir="./ad-bidding-lora",
    num_train_epochs=3,
    per_device_train_batch_size=4,
    gradient_accumulation_steps=8,
    learning_rate=2e-4,
    fp16=True,
    logging_steps=10,
    save_strategy="epoch",
    report_to="wandb"
)

# ─── 准备广告竞价数据集 ───
from datasets import Dataset

data = {
    "text": [
        "Budget: $1000, CTR: 2%, CVR: 10%, Calculate optimal bid",
        "Budget: $500, CTR: 3%, CVR: 8%, Calculate optimal bid",
        # ... 更多样本
    ]
}
dataset = Dataset.from_dict(data)

# ─── 训练 ───
trainer = Trainer(
    model=model,
    args=training_args,
    train_dataset=dataset,
    tokenizer=AutoTokenizer.from_pretrained("Qwen/Qwen2-7B")
)

trainer.train()

# ─── 保存 LoRA 适配器 ───
model.save_pretrained("./ad-bidding-lora-final")
```

---

## 三、提示工程最佳实践

```python
# 文件: prompting/best_practices.py

# ─── 1. 结构化提示模板 ───
AD_BIDDING_PROMPT = """
你是一个专业的广告竞价优化专家。

## 任务
根据以下参数计算最优竞价：

## 输入参数
- 预算: {budget} USD
- 预估 CTR: {ctr}%
- 预估 CVR: {cvr}%
- 目标 CPA: {target_cpa} USD

## 约束条件
- 竞价必须在 [min_bid, max_bid] 范围内
- 考虑市场竞争因素
- 平衡曝光量与成本

## 输出格式
请按照以下 JSON 格式输出：
{{
  "bid": <number>,
  "reasoning": "<string>",
  "expected_impressions": <number>,
  "confidence": <float 0-1>
}}

## 计算
预算: {budget}, CTR: {ctr}%, CVR: {cvr}%, Target CPA: {target_cpa}
"""

# ─── 2. Few-shot 示例 ───
FEW_SHOT_PROMPT = """
请根据示例计算竞价：

示例 1:
输入: 预算=$1000, CTR=2%, CVR=10%, Target CPA=$50
输出: {"bid": 2.5, "reasoning": "标准竞价策略", ...}

示例 2:
输入: 预算=$500, CTR=3%, CVR=8%, Target CPA=$30
输出: {"bid": 3.2, "reasoning": "高价值用户溢价", ...}

当前任务:
输入: 预算={budget}, CTR={ctr}%, CVR={cvr}%, Target CPA={target_cpa}
输出:
"""

# ─── 3. 思维链提示 ───
CHAIN_OF_THOUGHT_PROMPT = """
让我们一步步思考：

1. 首先分析预算约束...
2. 然后评估 CTR/CVR 对产品价值的影响...
3. 考虑市场竞争环境...
4. 计算最优竞价...

最终输出:
"""

def generate_ad_bid(budget: float, ctr: float, cvr: float, target_cpa: float) -> dict:
    prompt = AD_BIDDING_PROMPT.format(
        budget=budget, ctr=ctr, cvr=cvr, target_cpa=target_cpa
    )
    response = call_llm(prompt)
    return parse_json(response)
```

---

## 四、参考资料

```
微调工具:
├── HuggingFace PEFT: https://huggingface.co/docs/peft/
├── LoRA Paper: "LoRA: Low-Rank Adaptation of Large Language Models"
└── Unsloth: 高效微调框架

提示工程:
├── Prompt Engineering Guide (Andrew Ng)
├── Instructor: 结构化输出
└── LangChain Prompt Templates
```

---

*文档版本: v1.0*  
*最后更新: 2026-08-13*  
*作者: Ryan*
