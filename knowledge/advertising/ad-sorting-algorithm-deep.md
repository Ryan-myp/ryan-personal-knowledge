# 广告排序算法 - 资深专家深度实现

## 一、多级漏斗

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      广告排序漏斗                                         │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   Phase 1: 召回                                                         │
│   ├── 粗排: 10万候选 → 1000                                              │
│   ├── 特征: 用户画像/广告素材/上下文                                      │
│   └── 模型: 双塔模型                                                     │
│                                                                         →
│   Phase 2: 预排序                                                       │
│   ├── 精排: 1000候选 → 100                                                │
│   ├── 特征: 交叉特征/序列特征                                             │
│   └── 模型: DeepFM/DCN                                                   │
│                                                                         →
│   Phase 3: 重排序                                                       │
│   ├── 规则: 频控/多样性/业务策略                                          │
│   ├── 模型: Learning to Rank                                             │
│   └── 优化: 业务目标组合                                                   │
│                                                                         →
└─────────────────────────────────────────────────────────────────────────┘
```

## 二、DeepFM模型

```python
import torch
import torch.nn as nn

class DeepFM(nn.Module):
    def __init__(self, feature_dims, embed_dim=8):
        super().__init__()
        # FM部分
        self.fm = SimpleFM(feature_dims, embed_dim)
        # Deep部分
        self.deep = nn.Sequential(
            nn.Linear(feature_dims * embed_dim, 256),
            nn.ReLU(),
            nn.Linear(256, 64),
            nn.ReLU(),
            nn.Linear(64, 1)
        )
        
    def forward(self, x):
        fm_out = self.fm(x)
        deep_out = self.deep(x.view(x.size(0), -1))
        return torch.sigmoid(fm_out + deep_out)
```

## 三、面试高频题

### Q1: DeepFM优势？

```
A:
1. 自动特征交叉
2. FM+Deep结合
3. 稀疏数据友好
```

### Q2: 如何处理冷启动？

```
A:
1. 用户侧: 兴趣标签
2. 广告侧: 素材Embedding
3. 上下文: 时间段/地点
```

## 四、自测题

1. 解释多级漏斗
2. 如何实现DeepFM？
3. 如何处理冷启动？

---

## 参考文档

- [DeepFM论文](https://arxiv.org/abs/1703.04247)
- [Google Doubledeep](https://ai.google/research/pubs/pub45446)
