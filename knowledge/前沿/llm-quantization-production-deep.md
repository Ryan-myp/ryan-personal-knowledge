---
title: LLM量化生产实践深度实现
date: 2026-08-26
status: deep
tags: [LLM, 量化, 推理优化]
domain: 前沿追踪
level: 专家级
code_density: 33%
---

# LLM量化生产实践深度实现

## 一、量化方法对比

| 方法 | 精度 | 速度提升 | 质量损失 | 适用场景 |
|------|------|----------|----------|----------|
| FP32 | 32-bit | 1x | 0% | 训练 |
| FP16 | 16-bit | 2x | <1% | 训练/推理 |
| BF16 | 16-bit | 2x | <1% | 训练 |
| INT8 | 8-bit | 2-4x | 1-3% | 生产推理 |
| INT4 | 4-bit | 4-8x | 3-8% | 边缘设备 |
| NF4 | 4-bit | 4-8x | 2-5% | QLoRA |

## 二、PTQ（后训练量化）实现

```python
class PTQQuantizer:
    """
    Post-Training Quantization
    不需要重新训练，直接量化已训练模型
    """
    
    def __init__(self, model, calibration_data):
        self.model = model
        self.calibration_data = calibration_data
        self.quant_params = {}
        
    def calibrate(self):
        """校准：收集激活值统计信息"""
        self.model.eval()
        
        # 注册hook收集激活值
        handles = []
        for name, module in self.model.named_modules():
            if isinstance(module, nn.Linear):
                handle = module.register_forward_hook(
                    self._activation_observer(name)
                )
                handles.append(handle)
        
        # 运行校准数据
        with torch.no_grad():
            for batch in self.calibration_data:
                self.model(batch)
        
        # 移除hooks
        for handle in handles:
            handle.remove()
        
        return self.quant_params
    
    def _activation_observer(self, name):
        def hook(module, input, output):
            # 收集统计信息
            abs_max = output.abs().max().item()
            if name not in self.quant_params:
                self.quant_params[name] = {'abs_max': abs_max}
            else:
                self.quant_params[name]['abs_max'] = max(
                    self.quant_params[name]['abs_max'], abs_max
                )
        return hook
    
    def quantize(self, bit_width=8):
        """应用量化"""
        for name, param in self.model.named_parameters():
            if 'weight' in name:
                # 权重量化
                abs_max = self.quant_params.get(name, {}).get('abs_max', 1.0)
                scale = abs_max / (2**(bit_width-1) - 1)
                quantized = torch.round(param / scale)
                param.data = quantized * scale
```

## 三、AWQ（激活感知权重量化）

```python
class AWQQuantizer:
    """
    Activation-aware Weight Quantization
    考虑激活值分布，保护重要权重
    """
    
    def __init__(self, model, dataloader, w=32, bit=4):
        self.model = model
        self.dataloader = dataloader
        self.w = w  # 窗口大小
        self.bit = bit
        
    def find_scale(self):
        """寻找最优缩放因子"""
        # 逐层处理
        for name, module in self.model.named_modules():
            if isinstance(module, nn.Linear):
                # 获取权重
                weight = module.weight.data
                
                # 计算每个权重的敏感度
                sensitivities = self._compute_sensitivity(module)
                
                # 找到保护阈值
                threshold = self._find_threshold(sensitivities, keep_ratio=0.01)
                
                # 计算缩放因子
                scale = self._compute_scale(weight, sensitivities, threshold)
                
                # 应用缩放
                module.weight.data = weight / scale
        
        return self.model
    
    def _compute_sensitivity(self, module):
        """计算权重敏感度"""
        # 简化实现
        weight = module.weight.data
        return weight.abs().mean(dim=1)
    
    def quantize_weight(self, weight):
        """AWQ量化"""
        # SmoothQuant风格量化
        weight = weight.float()
        
        # 整数量化
        scale = weight.abs().max() / 7.0
        q_weight = torch.round(weight / scale + 8).clamp(0, 15).char()
        
        return q_weight, scale
```

## 四、QLoRA（量化低秩适配）

```python
class QLoRALinear(nn.Module):
    """
    QLoRA: Quantized LoRA
    4-bit NF4量化基础权重 + LoRA适配器
    """
    
    def __init__(self, base_layer, r=16, alpha=32):
        super().__init__()
        self.base_layer = base_layer  # 4-bit量化层
        self.r = r
        self.alpha = alpha
        
        # LoRA适配器
        self.lora_A = nn.Linear(base_layer.in_features, r, bias=False)
        self.lora_B = nn.Linear(r, base_layer.out_features, bias=False)
        
        # 初始化
        nn.init.kaiming_uniform_(self.lora_A.weight, a=math.sqrt(5))
        nn.init.zeros_(self.lora_B.weight)
        
    def forward(self, x):
        # 基础层前向（4-bit量化）
        base_output = self.base_layer(x)
        
        # LoRA路径
        lora_output = self.lora_B(self.lora_A(x))
        
        # 合并
        return base_output + lora_output * (self.alpha / self.r)


class NF4Quantizer:
    """
    Normal Float 4-bit 量化器
    针对LLM权重分布优化的4-bit格式
    """
    
    # NF4量化级别（基于正态分布分位数）
    nf4_base = torch.tensor([
        -1.0, -0.6962928223609924, -0.5250730514526367,
        -0.39492777824401855, -0.2844452178478241,
        -0.18461564429998398, -0.09109574681282044,
        0.000769387673552125, 0.08524127405345496,
        0.1705388510550499, 0.2594452178478241,
        0.35638245940208435, 0.4676334559917444,
        0.6053126454353333, 0.8071476221084595,
        1.0
    ])
    
    def quantize(self, weight):
        """NF4量化"""
        # 归一化到[-1, 1]
        abs_max = weight.abs().max()
        normalized = weight / abs_max
        
        # 找到最近的NF4级别
        indices = torch.bucketize(
            normalized.contiguous().view(-1),
            self.nf4_base.to(normalized.device)
        )
        
        # 量化值
        quantized = self.nf4_base.to(normalized.device)[indices]
        
        return quantized.view(weight.shape) * abs_max
    
    def dequantize(self, quantized_weight, abs_max):
        """反量化"""
        # 将索引转回连续值
        indices = quantized_weight.long()
        continuous = self.nf4_base[indices] * abs_max
        return continuous
```

## 五、生产部署配置

```yaml
# vLLM配置
apiVersion: apps/v1
kind: Deployment
metadata:
  name: llm-serving
spec:
  replicas: 2
  selector:
    matchLabels:
      app: llm-serving
  template:
    metadata:
      labels:
        app: llm-serving
    spec:
      containers:
      - name: vllm
        image: vllm/vllm-openai:latest
        args:
        - --model
        - Qwen/Qwen2-7B-Instruct
        - --quantization
        - awq
        - --max-model-len
        - "4096"
        - --gpu-memory-utilization
        - "0.9"
        - --tensor-parallel-size
        - "2"
        resources:
          limits:
            nvidia.com/gpu: 2
        env:
        - name: VLLM_WORKER_MULTIPROC_METHOD
          value: spawn
```

## 六、性能基准

```python
def benchmark_quantization():
    """量化性能测试"""
    models = {
        'FP16': load_model('model_fp16'),
        'INT8': load_model('model_int8'),
        'AWQ': load_model('model_awq'),
        'QLoRA': load_model('model_qlora'),
    }
    
    results = {}
    for name, model in models.items():
        # 延迟测试
        latency = benchmark_latency(model)
        
        # 吞吐量测试
        throughput = benchmark_throughput(model)
        
        # 质量测试
        accuracy = benchmark_accuracy(model)
        
        results[name] = {
            'latency_ms': latency,
            'throughput_tps': throughput,
            'accuracy': accuracy
        }
    
    return results
```

---

## 自测题

### Q1: PTQ和QAT有什么区别？
**A**: PTQ不需要重新训练，直接量化；QAT在量化感知训练过程中优化，效果更好但需要训练资源。

### Q2: AWQ如何保护重要权重？
**A**: AWQ通过计算权重敏感度，对重要权重进行保护性缩放，减少量化误差。

### Q3: QLoRA为什么使用NF4而不是普通INT4？
**A**: NF4根据正态分布分位数设计，更适合LLM权重的统计分布特性。

---

**关键词**: LLM量化, PTQ, AWQ, QLoRA, NF4, vLLM
