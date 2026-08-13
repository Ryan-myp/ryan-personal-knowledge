# ML 系统设计与面试题库

> 深入 ML 系统设计：特征工程、模型训练、在线推理、模型监控。
> 适用对象：ML 工程师、AI 架构师

---

## 1. 特征工程

### Q: 如何处理高基数 categorical 特征？

```python
# 方案1: Target Encoding
def target_encode(df, col, target, smooth=50):
    global_mean = df[target].mean()
    col_stats = df.groupby(col)[target].agg(['count', 'mean'])
    col_stats['smoothed'] = (col_stats['mean'] * col_stats['count'] + global_mean * smooth) / (col_stats['count'] + smooth)
    return df[col].map(col_stats['smoothed'])

# 方案2: Embedding
import torch.nn as nn
class EmbeddingLayer(nn.Module):
    def __init__(self, vocab_size, embedding_dim):
        super().__init__()
        self.embedding = nn.Embedding(vocab_size, embedding_dim)
    
    def forward(self, x):
        return self.embedding(x)
```

### Q: 特征交叉有哪些方法？

```
人工特征交叉:
- 多项式特征: x1 * x2
- 交叉桶: hash([x1, x2]) % buckets

自动特征交叉:
- DeepFM: Factorization-supported SVM
- DCN: Deep & Cross Network
- AutoInt: Attention-based
```

---

## 2. 模型训练

### Q: 分布式训练的数据并行 vs 模型并行？

```
数据并行:
- 每个 GPU 保存完整模型
- 数据分片到不同 GPU
- 梯度同步 (AllReduce)
- 适合: 模型小，数据量大

模型并行:
- 模型分片到不同 GPU
- 同一数据流经所有 GPU
- 适合: 模型大，单卡放不下
```

### Q: 如何处理训练数据倾斜？

```python
# 方案1: 重采样
oversample_majority = resample(majority_class, n_samples=minority_count, random_state=42)

# 方案2: 权重调整
class_weights = compute_class_weight('balanced', classes=np.unique(y), y=y)
model = LogisticRegression(class_weight=class_weights)

# 方案3: Focal Loss
class FocalLoss(nn.Module):
    def __init__(self, gamma=2.0):
        super().__init__()
        self.gamma = gamma
    
    def forward(self, inputs, targets):
        ce_loss = F.cross_entropy(inputs, targets)
        pt = torch.exp(-ce_loss)
        focal_loss = ((1 - pt) ** self.gamma) * ce_loss
        return focal_loss.mean()
```

---

## 3. 在线推理

### Q: 如何优化推理延迟？

```
模型优化:
- 量化 (INT8/FP16)
- 剪枝 (Pruning)
- 知识蒸馏 (Distillation)

服务优化:
- 批量推理 (Batching)
- 异步处理
- 模型缓存

基础设施:
- GPU 推理 (TensorRT, ONNX Runtime)
- 模型服务化 (TFServing, TorchServe)
```

### Q: A/B 测试如何设计？

```python
# 实验设计
experiment = {
    "name": "ranking_model_v2",
    "variants": [
        {"name": "control", "weight": 0.5},
        {"name": "treatment", "weight": 0.5}
    ],
    "metrics": [
        "ctr",
        "cvr", 
        "revenue",
        "user_retention"
    ],
    "duration": "7 days",
    "sample_size": 100000
}

# 显著性检验
from scipy import stats
def check_significance(control, treatment):
    stat, p_value = stats.ttest_ind(control, treatment)
    return p_value < 0.05
```

---

## 4. 模型监控

### Q: 如何检测模型漂移？

```python
class ModelMonitor:
    def __init__(self):
        self.baseline_dist = None
    
    def check_drift(self, current_data):
        # PSI (Population Stability Index)
        psi = calculate_psi(self.baseline_dist, current_data)
        
        # 阈值判断
        if psi < 0.1:
            return "No drift"
        elif psi < 0.2:
            return "Minor drift"
        else:
            return "Major drift"
    
    def calculate_psi(self, baseline, current, bins=10):
        baseline_bins = np.histogram(baseline, bins=bins)[0]
        current_bins = np.histogram(current, bins=bins)[0]
        
        baseline_pct = baseline_bins / len(baseline)
        current_pct = current_bins / len(current)
        
        psi = np.sum((current_pct - baseline_pct) * 
                     np.log(current_pct / baseline_pct))
        return psi
```

---

## 5. 实践 Checklist
- [ ] 掌握特征工程方法
- [ ] 理解分布式训练
- [ ] 优化推理性能
- [ ] 设计 A/B 测试
- [ ] 实现模型监控

**参考**: ML System Design 面试指南
