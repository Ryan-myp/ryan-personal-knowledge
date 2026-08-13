# LLM量化技术 - 资深专家深度实现

## 一、量化方法对比

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      LLM量化方法对比                                       │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   方法            | 精度损失 | 速度提升 | 压缩率 | 适用场景                  │
│   ────────────────┼──────────┼──────────┼───────┼───────────────────────── │
│   FP16            | 极低     | 1.5x     | 2x    | GPU推理                   │
│   INT8            | 低       | 2-3x     | 4x    | 通用推理                    │
│   INT4            | 中       | 4-6x     | 8x    | 边缘设备                    │
│   NF4 (bitsandbytes)| 低     | 3x       | 4x    | 微调                      │
│   GPTQ            | 低       | 2-4x     | 4x    | 生产部署                    │
│   AWQ             | 低       | 2-3x     | 4x    | 大模型                      │
│   SmoothQuant     | 低       | 2x       | 2x    | 混合精度                    │
│                                                                         →
└─────────────────────────────────────────────────────────────────────────┘
```

## 二、GPTQ实现

```python
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
from auto_gptq import GPTQQuantizer

class GPTQQuantizerImpl:
    """GPTQ量化实现"""
    
    def __init__(self, model_path, bits=4):
        self.model_path = model_path
        self.bits = bits
        self.quantizer = GPTQQuantizer(
            bits=bits,
            desc_act=False,  # 设为False以提高速度
        )
    
    def quantize(self, dataset, batch_size=1):
        """量化模型"""
        # 加载模型
        model = AutoModelForCausalLM.from_pretrained(
            self.model_path,
            torch_dtype=torch.float16,
            device_map="auto"
        )
        tokenizer = AutoTokenizer.from_pretrained(self.model_path)
        
        # 准备数据集
        def preprocess_dataset(samples):
            texts = [tokenizer.decode(tok) for tok in samples['tokens']]
            return tokenizer(texts, truncation=True, padding=True)
        
        dataset = dataset.map(preprocess_dataset, batch_size=batch_size)
        
        # 执行量化
        self.quantizer.quantize(
            model,
            corpus_dataset=dataset,
            cache_examples_on_gpu=False,
        )
        
        # 保存量化模型
        quant_path = f"{self.model_path}-{self.bits}bit"
        model.save_pretrained(quant_path)
        tokenizer.save_pretrained(quant_path)
        
        return quant_path
    
    def infer(self, prompt, max_new_tokens=100):
        """推理"""
        model = AutoModelForCausalLM.from_pretrained(
            f"{self.model_path}-{self.bits}bit",
            device_map="auto",
            torch_dtype=torch.float16,
        )
        tokenizer = AutoTokenizer.from_pretrained(self.model_path)
        
        inputs = tokenizer(prompt, return_tensors="pt").to(model.device)
        outputs = model.generate(**inputs, max_new_tokens=max_new_tokens)
        
        return tokenizer.decode(outputs[0], skip_special_tokens=True)
```

## 三、AWQ实现

```python
from awq import AutoAWQForCausalLM
from transformers import AutoTokenizer

class AWQQuantizer:
    """AWQ量化实现"""
    
    def __init__(self, model_path):
        self.model_path = model_path
        self.model = AutoAWQForCausalLM.from_pretrained(model_path)
        self.tokenizer = AutoTokenizer.from_pretrained(model_path)
    
    def quantize(self, dataset, quant_config={"w_bit": 4, "group_size": 128}):
        """量化模型"""
        self.model.quantize(
            dataset,
            quant_config=quant_config,
        )
        
        quant_path = f"{self.model_path}-awq-{quant_config['w_bit']}bit"
        self.model.save_quantized(quant_path)
        self.tokenizer.save_pretrained(quant_path)
        
        return quant_path
    
    def load_quantized(self, quant_path):
        """加载量化模型"""
        return AutoAWQForCausalLM.from_quantized(
            quant_path,
            device_map="auto",
            torch_dtype=torch.float16,
        )
```

## 四、面试高频题

### Q1: GPTQ和AWQ有什么区别？

```
A:
1. GPTQ: 逐层量化，使用Hessian矩阵
2. AWQ: 权重平滑，感知异常值
```

### Q2: 量化会导致什么性能损失？

```
A:
1. 精度下降: 回答质量略有降低
2. 长尾场景: 复杂推理可能下降
3. 可控: 通过校准数据集优化
```

## 五、自测题

1. 解释GPTQ原理
2. 如何实现AWQ量化？
3. 如何评估量化效果？

---

## 参考文档

- [GPTQ论文](https://arxiv.org/abs/2210.17323)
- [AWQ论文](https://arxiv.org/abs/2306.00978)
