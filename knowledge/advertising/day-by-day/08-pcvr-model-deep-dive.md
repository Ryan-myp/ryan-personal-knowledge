# pCVR 模型深度：从特征工程到在线学习

> 创建日期: 2026-06-10
> 作者: Ryan
> 定位: 资深专家级 — pCVR 模型核心

---

## 第一部分：pCVR 问题的本质

### 1.1 pCVR 是什么

```
pCVR = P(convert | click, features) = 用户点击后转化为购买的概率

核心挑战:
┌──────────────────────────────────────────────────────────────┐
│              pCVR 的核心挑战                                   │
│                                                              │
│  1. 数据稀疏 (Data Sparsity):                                │
│  ├── 展示 → 点击: ~2-5%                                     │
│  ├── 点击 → 转化: ~1-10%                                    │
│  └─ 展示 → 转化: ~0.02-0.5% (极度稀疏)                       │
│                                                              │
│  2. 样本偏差 (Sample Bias):                                  │
│  ├── 我们只有 Clicked 用户的转化标签                           │
│  └─ Impressed 但没 Click 的用户没有标签                       │
│                                                              │
│  3. 延迟反馈 (Delayed Feedback):                             │
│  ├── 点击后可能需要数小时/数天才能看到转化                      │
│  └─ 实时竞价时没有转化反馈                                    │
│                                                              │
│  4. 归因问题 (Attribution):                                  │
│  ├── 用户可能点击多个广告才转化                                │
│  └─ 如何分配转化功劳到每个点击                                 │
│                                                              │
│  5. 数据漂移 (Data Drift):                                   │
│  ├── 用户行为随时间变化                                        │
│  ├── 季节性效应                                                │
│  └─ 广告疲劳                                                  │
└──────────────────────────────────────────────────────────────┘
```

### 1.2 pCVR vs CTR

```
CTR (Click-Through Rate) vs CVR (Conversion Rate):

┌──────────────────────────────────────────────────────────────┐
│              CTR vs CVR                                       │
│                                                              │
│  CTR = P(click | impression)                                 │
│  ├── 数据丰富: 每次展示都有 click/no-click 标签               │
│  ├── 标签即时: 点击在几毫秒内发生                              │
│  ├── 样本无偏差: 所有展示都有标签                              │
│  └─ 模型相对简单: 线性/浅层模型即可                            │
│                                                              │
│  CVR = P(convert | click)                                    │
│  ├── 数据稀疏: 只有点击后才可能转化                            │
│  ├── 标签延迟: 点击后数小时/数天才出现                         │
│  ├── 样本偏差: 只有 clicked 用户有标签                        │
│  └─ 需要更复杂的模型                                          │
│                                                              │
│  关系:                                                        │
│  ├── Expected CPA = Target CPA / (pCTR × pCVR)              │
│  ├── pCTR × pCVR = pAction = P(action | impression)          │
│  └─ pCVR 的误差会被放大 (因为数据稀疏)                         │
└──────────────────────────────────────────────────────────────┘
```

---

## 第二部分：pCVR 模型架构

### 2.1 ESMM (Entire Space Multi-Task Model)

```
ESMM: 解决 pCVR 数据稀疏问题的经典方案

核心思想:
├─ 同时建模三个任务:                                          │
│   ├── CTR: P(click | impression)                            │
│   ├── CTCVR: P(click & convert | impression)                │
│   └─ CVR: P(convert | click) = CTCVR / CTR                  │
│                                                              │
├─ 为什么有效:                                               │
│   ├── CTR 数据丰富 → CTR 模型准确                            │
│   ├── CTCVR 数据比 CVR 丰富 (多了一个 click 信号)             │
│   └─ 通过 CTR 模型约束 CVR 预测，缓解稀疏问题                 │
│                                                              │
├─ 模型架构:                                                 │
│   ┌───────────────────────────────────────────────┐          │
│   │  Input: features (500+ dim)                    │          │
│   │  ├─ Embedding Layer (user/category/query...)  │          │
│   │  ├─ Shared Encoder (DNN, 3 layers)            │          │
│   │  │  └─ h_shared = DNN(features)              │          │
│   │  ├─ CTR Tower                                  │          │
│   │  │  └─ pCTR = σ(W_ctr · h_shared + b_ctr)    │          │
│   │  ├─ CTCVR Tower                                │          │
│   │  │  └─ pCTCVR = σ(W_ctcvr · h_shared + b_ctcvr)│          │
│   │  └─ CVR Tower (可选):                          │          │
│   │     └─ pCVR = pCTCVR / pCTR (显式)             │          │
│   └───────────────────────────────────────────────┘          │
│                                                              │
├─ 损失函数:                                                   │
│   ├── L_CTR = -Σ [y_click · log(pCTR) + (1-y_click) · log(1-pCTR)] │
│   ├── L_CTCVR = -Σ [y_convert · log(pCTCVR) + (1-y_convert) · log(1-pCTCVR)] │
│   └─ L_Total = L_CTR + α · L_CTCVR                         │
│                                                              │
├─ 超参数 α:                                                  │
│   ├── α 控制 CTCVR 损失权重                                 │
│   └─ 通常 α = 0.5-2.0 (通过验证集调优)                      │
│                                                              │
└─ 推理:                                                      │
    ├── 实时: pCTR, pCTCVR 并行输出                            │
    └─ pCVR = pCTCVR / pCTR (除法, 避免显式 CVR Tower)        │
```

### 2.2 ESMM 代码实现

```python
"""
ESMM (Entire Space Multi-Task Model) — PyTorch 实现
"""

import torch
import torch.nn as nn
import torch.nn.functional as F


class ESMM(nn.Module):
    """
    ESMM: Entire Space Multi-Task Model for CTR & CVR
    
    架构:
    ├── Shared Encoder: 共享底层表示
    ├── CTR Tower: 预测点击率
    └─ CTCVR Tower: 预测点击+转化率
    
    CVR = CTCVR / CTR (推理时计算)
    """
    
    def __init__(
        self,
        feature_dim: int = 500,
        embed_dim: int = 32,
        shared_hidden: list = [256, 128, 64],
        ctr_hidden: list = [64, 32],
        ctcvr_hidden: list = [64, 32],
    ):
        super().__init__()
        
        # Shared Encoder
        layers = [nn.Linear(feature_dim, shared_hidden[0])]
        for i in range(len(shared_hidden) - 1):
            layers.extend([
                nn.BatchNorm1d(shared_hidden[i]),
                nn.ReLU(),
                nn.Dropout(0.2),
                nn.Linear(shared_hidden[i], shared_hidden[i + 1]),
            ])
        self.shared_encoder = nn.Sequential(*layers)
        
        # CTR Tower
        ctr_layers = []
        in_dim = shared_hidden[-1]
        for h in ctr_hidden:
            ctr_layers.extend([
                nn.Linear(in_dim, h),
                nn.ReLU(),
                nn.Dropout(0.1),
            ])
            in_dim = h
        self.ctr_tower = nn.Sequential(*ctr_layers, nn.Sigmoid())
        
        # CTCVR Tower
        ctcvr_layers = []
        in_dim = shared_hidden[-1]
        for h in ctcvr_hidden:
            ctcvr_layers.extend([
                nn.Linear(in_dim, h),
                nn.ReLU(),
                nn.Dropout(0.1),
            ])
            in_dim = h
        self.ctcvr_tower = nn.Sequential(*ctcvr_layers, nn.Sigmoid())
        
    def forward(self, x):
        """
        Forward pass
        
        Args:
            x: input features (batch_size, feature_dim)
        
        Returns:
            p_ctr: click probability
            p_ctcvr: click&convert probability
        """
        # Shared encoding
        h_shared = self.shared_encoder(x)
        
        # Tower outputs
        p_ctr = self.ctr_tower(h_shared)
        p_ctcvr = self.ctcvr_tower(h_shared)
        
        return p_ctr, p_ctcvr
    
    def compute_cvr(self, p_ctr: torch.Tensor, p_ctcvr: torch.Tensor) -> torch.Tensor:
        """
        计算 pCVR = pCTCVR / pCTR
        
        数值稳定性: 使用 clip 防止除以零
        """
        p_ctr_clipped = p_ctr.clamp(min=1e-7)
        p_cvr = p_ctcvr / p_ctr_clipped
        return p_cvr.clamp(min=0.0, max=1.0)


def esmm_loss(
    p_ctr: torch.Tensor,
    p_ctcvr: torch.Tensor,
    y_click: torch.Tensor,
    y_convert: torch.Tensor,
    alpha: float = 1.0,
) -> torch.Tensor:
    """
    ESMM 损失函数
    
    L = L_CTR + α × L_CTCVR
    
    Args:
        p_ctr: 预测的点击率
        p_ctcvr: 预测的点击+转化率
        y_click: 点击标签 (0/1)
        y_convert: 转化标签 (0/1, 仅点击用户有值)
        alpha: CTCVR 损失权重
    
    Returns:
        总损失
    """
    # CTR Loss (BCE)
    p_ctr_clipped = p_ctr.clamp(min=1e-7, max=1-1e-7)
    l_ctr = -(
        y_click * torch.log(p_ctr_clipped) +
        (1 - y_click) * torch.log(1 - p_ctr_clipped)
    ).mean()
    
    # CTCVR Loss (BCE)
    p_ctcvr_clipped = p_ctcvr.clamp(min=1e-7, max=1-1e-7)
    l_ctcvr = -(
        y_convert * torch.log(p_ctcvr_clipped) +
        (1 - y_convert) * torch.log(1 - p_ctcvr_clipped)
    ).mean()
    
    # Total Loss
    total_loss = l_ctr + alpha * l_ctcvr
    
    return total_loss


class ESMMTrainer:
    """
    ESMM 训练器
    """
    
    def __init__(
        self,
        model: ESMM,
        alpha: float = 1.0,
        learning_rate: float = 1e-3,
        weight_decay: float = 1e-4,
    ):
        self.model = model
        self.alpha = alpha
        self.optimizer = torch.optim.Adam(
            model.parameters(),
            lr=learning_rate,
            weight_decay=weight_decay,
        )
        self.scheduler = torch.optim.lr_scheduler.StepLR(
            self.optimizer, step_size=10, gamma=0.5
        )
    
    def train_step(
        self,
        x: torch.Tensor,
        y_click: torch.Tensor,
        y_convert: torch.Tensor,
    ) -> dict:
        """
        训练一步
        
        Returns:
            损失和指标
        """
        self.model.train()
        self.optimizer.zero_grad()
        
        p_ctr, p_ctcvr = self.model(x)
        loss = esmm_loss(p_ctr, p_ctcvr, y_click, y_convert, self.alpha)
        
        loss.backward()
        self.optimizer.step()
        
        return {
            'loss': loss.item(),
            'p_ctr': p_ctr.mean().item(),
            'p_ctcvr': p_ctcvr.mean().item(),
        }
    
    def evaluate(
        self,
        x: torch.Tensor,
        y_click: torch.Tensor,
        y_convert: torch.Tensor,
    ) -> dict:
        """
        评估模型
        
        Returns:
            AUC, LogLoss 等指标
        """
        self.model.eval()
        with torch.no_grad():
            p_ctr, p_ctcvr = self.model(x)
            
            # CTR metrics
            l_ctr = F.binary_cross_entropy(p_ctr, y_click)
            
            # CTCVR metrics
            l_ctcvr = F.binary_cross_entropy(p_ctcvr, y_convert)
            
            # CVR (推导)
            p_cvr = self.model.compute_cvr(p_ctr, p_ctcvr)
            
            return {
                'l_ctr': l_ctr.item(),
                'l_ctcvr': l_ctcvr.item(),
                'l_total': l_ctr.item() + self.alpha * l_ctcvr.item(),
                'p_ctr_mean': p_ctr.mean().item(),
                'p_ctcvr_mean': p_ctcvr.mean().item(),
                'p_cvr_mean': p_cvr.mean().item(),
            }
```

---

## 第三部分：pCVR 特征工程

### 3.1 特征体系

```
pCVR 特征工程 (500+ 维):

┌──────────────────────────────────────────────────────────────┐
│              pCVR 特征体系                                     │
│                                                              │
│  用户特征 (User Features):                                   │
│  ├── 用户画像: 年龄/性别/收入/教育 (20 维)                    │
│  ├── 历史点击行为:                                             │
│  │   ├── 近 1h 点击数/CTR                                    │
│  │   ├── 近 24h 点击数/CTR                                   │
│  │   ├── 近 7d 点击数/CTR                                   │
│  │   └─ 近 30d 点击数/CTR                                   │
│  ├── 历史转化行为:                                             │
│  │   ├── 近 7d 转化数/转化率                                  │
│  │   ├── 近 30d 转化数/转化率                                │
│  │   └─ 平均订单价值                                          │
│  ├── 用户活跃度: 登录频率/使用时长                             │
│  └─ 用户分层: 新用户/活跃用户/流失用户                         │
│                                                              │
│  查询特征 (Query Features):                                  │
│  ├── 搜索词: TF-IDF (50 维) + BERT embedding (50 维)        │
│  ├── 商业意图: 是否包含购买相关词 (buy/price/deal)            │
│  ├── 搜索量: 搜索热度                                          │
│  └─ 搜索新鲜度: 新查询/历史查询                                │
│                                                              │
│  广告特征 (Ad Features):                                     │
│  ├── 广告文案: BERT embedding (50 维)                        │
│  ├── 广告类型: Search/Display/Video                          │
│  ├── 广告主历史表现:                                           │
│  │   ├── 广告主历史 CTR                                      │
│  │   ├── 广告主历史 CVR                                      │
│  │   └─ 广告主历史 CPA                                       │
│  ├── 广告系列历史表现:                                         │
│  │   ├── 广告系列历史 CTR                                    │
│  │   ├── 广告系列历史 CVR                                    │
│  │   └─ 广告系列历史 ROI                                      │
│  ├── 广告质量 Score                                          │
│  └─ 广告新鲜度: 新广告/老广告                                  │
│                                                              │
│  上下文特征 (Context Features):                              │
│  ├── 页面: URL/内容/类别/广告数量                              │
│  ├── 时间: 小时/星期/季节                                     │
│  ├── 位置: 城市/地区/国家                                     │
│  ├── 设备: 手机/平板/桌面                                     │
│  └─ 网络: WiFi/4G/5G                                        │
│                                                              │
│  交叉特征 (Cross Features):                                  │
│  ├── User × Query: 用户兴趣匹配                               │
│  ├── User × Ad: 用户历史对该广告主的互动                       │
│  ├── Query × Ad: 搜索词与广告文案相关性                       │
│  └─ User × Ad × Query: 三维交叉                              │
│                                                              │
│  特征工程技巧:                                               │
│  ├── 离散特征: One-Hot / Target Encoding / Embedding          │
│  ├── 连续特征: Log 变换 / 分箱 / 标准化                      │
│  ├── 序列特征: 用户行为序列 → RNN/Transformer                 │
│  └─ 特征交叉: 高阶交叉 (FM/DCN)                             │
└──────────────────────────────────────────────────────────────┘
```

### 3.2 用户行为序列特征

```
用户行为序列 → 序列建模:

设定:
├─ 用户最近的行为序列: [impression_1, click_1, impression_2, ..., convert_n]
├─ 目标: 基于历史行为预测本次点击后的转化率
└─ 模型: Transformer / GRU / LSTM

Transformer 架构:
┌──────────────────────────────────────────────────────────────┐
│              用户行为序列建模                                    │
│                                                              │
│  Input: 行为序列 [e1, e2, ..., eT]                           │
│  ├── e_t = Embedding(action_type, ad_id, query, time_gap)    │
│  ├── 位置编码: Positional Encoding                            │
│  └─ Self-Attention: 捕获行为间依赖                            │
│                                                              │
│  Architecture:                                               │
│  ├── Embedding Layer: 行为 → embedding                       │
│  ├── Positional Encoding                                    │
│  ├── Transformer Encoder (6 layers)                         │
│  │   ├── Multi-Head Attention                               │
│  │   └─ Feed-Forward Network                                │
│  ├── Attention Pooling (聚合序列)                              │
│  └─ MLP: 预测 pCVR                                           │
│                                                              │
│  Loss: BCE (Binary Cross Entropy)                            │
│                                                              │
│  时间编码 (Time Encoding):                                    │
│  ├── time_gap = log(current_time - event_time)                │
│  ├── 近期行为权重更高                                          │
│  └─ Exponential Decay: weight = exp(-λ × time_gap)           │
│                                                              │
│  注意:                                                       │
│  ├── 序列长度: 通常截断到 50-100                              │
│  ├── padding: 不足长度的填充                                   │
│  └─ Masking: 忽略 padding 位置                               │
└──────────────────────────────────────────────────────────────┘
```

---

## 第四部分：pCVR 训练与在线学习

### 4.1 训练策略

```
pCVR 训练策略:

1. 标签构建 (Label Construction):
├─ 点击标签: y_click = 1 (如果用户点击了广告)                  │
│   └─ 即时获取 (点击发生时)                                     │
│                                                              │
├─ 转化标签: y_convert = 1 (如果用户点击后转化)                 │
│   └─ 延迟获取 (点击后数小时/数天)                               │
│                                                              │
├─ 处理延迟标签:                                                │
│   ├── 方法 1: 等待 (最简单)                                    │
│   │   └─ 等待 24-72 小时再标注                                │
│   │   └─ 缺点: 训练延迟                                      │
│   │                                                      │
│   ├── 方法 2: 代理标签 (Proxy Labels)                        │
│   │   ├── 用短期行为作为代理:                                │
│   │   │   ├── 添加购物车 = 转化                              │
│   │   │   ├── 开始结算 = 转化                                │
│   │   │   └─ 浏览商品详情页 = 弱转化信号                       │
│   │   └─ 缺点: 噪声大                                        │
│   │                                                      │
│   └─ 方法 3: 多任务学习 (Multi-Task Learning)                │
│       ├── 同时学习短期和长期转化                               │
│       ├── 短期: 点击后 1h 内转化                              │
│       └─ 长期: 点击后 7d 内转化                               │
│                                                              │
├─ 负采样 (Negative Sampling):                                │
│   ├── CVR 是正负样本极度不平衡 (1:100~1:1000)                │
│   ├── 策略 1: 随机负采样 (Random Sampling)                    │
│   │   └─ 从所有点击中采样不转化的作为负样本                     │
│   ├── 策略 2: 难负采样 (Hard Negative Sampling)              │
│   │   └─ 采样与正样本相似但不转化的                            │
│   └─ 策略 3: 分层采样 (Stratified Sampling)                   │
│       └─ 按用户/广告/时间分层采样                              │
│                                                              │
└─ 样本权重 (Sample Weighting):                                │
    ├── 高价值转化权重更高 (如高价商品)                           │
    ├── 近期样本权重更高 (减少数据漂移)                          │
    └─ 不同渠道权重不同                                          │
```

### 4.2 在线学习 (Online Learning)

```
在线学习 (Online Learning) for pCVR:

问题:
├─ 用户行为随时间变化 → 模型需要持续更新                         │
├─ 离线训练延迟 → 无法实时响应变化                               │
└─ 需要: 在线学习 (数据到达即更新模型)                           

算法: Online Gradient Descent (OGD) + 弹性遗忘 (Elastic Forgetting)

设定:
├─ 每收到一个样本 (点击/转化)，更新模型参数                       │
├─ 学习率: η_t (随时间衰减)                                    │
└─ 遗忘因子: γ (控制历史样本权重)                              

算法:
├─ 初始化: θ_0 (离线训练得到的初始参数)                         │
│                                                              │
├─ 对于每个新样本 (x_t, y_t):                                  │
│   ├── 预测: p_t = σ(x_t^T θ_t)                              │
│   ├── 计算梯度: g_t = (p_t - y_t) × x_t                     │
│   ├── 更新: θ_{t+1} = θ_t - η_t × g_t                      │
│   └─ 遗忘: θ_{t+1} = γ × θ_t + (1-γ) × (θ_t - η_t × g_t)   │
│                                                              │
├─ 关键超参数:                                                 │
│   ├── η (学习率): 0.001-0.01 (初始), 随时间衰减               │
│   ├── γ (遗忘因子): 0.999-0.9999 (越小遗忘越快)              │
│   └─ 批次大小: 1 (完全在线) 或 64-256 (mini-batch)            │
│                                                              │
├─ 挑战:                                                      │
│   ├── 灾难性遗忘 (Catastrophic Forgetting): 新数据覆盖旧知识   │
│   │   └─ 解决: 弹性权重巩固 (EWC), 经验回放 (Replay Buffer)   │
│   ├── 概念漂移 (Concept Drift): 用户行为变化                   │
│   │   └─ 解决: 遗忘因子, 漂移检测                            │
│   └─ 在线评估: 需要实时 A/B 测试                              │
│                                                              │
├─ 实现 (Python):                                              │
│   └─ 见下方代码                                               │
│                                                              │
└─ 实际系统:                                                   │
    ├── Google: 在线学习 + 定期全量重训练                         │
    ├── Meta: Online Learning + Shadow Testing                  │
    └─ TikTok: 增量训练 (Incremental Training)                  │
```

```python
"""
在线学习实现 - pCVR 模型
"""

import torch
import torch.nn as nn


class OnlineCVRTrainer:
    """
    在线 pCVR 训练器
    
    使用 Online Gradient Descent + Elastic Forgetting
    """
    
    def __init__(
        self,
        model: nn.Module,
        learning_rate: float = 0.001,
        forget_factor: float = 0.9999,
        warmup_steps: int = 1000,
    ):
        self.model = model
        self.learning_rate = learning_rate
        self.forget_factor = forget_factor
        self.warmup_steps = warmup_steps
        self.step_count = 0
        
        self.optimizer = torch.optim.SGD(
            model.parameters(),
            lr=learning_rate,
            momentum=0.9,
        )
    
    def _get_learning_rate(self) -> float:
        """学习率调度: warmup → decay"""
        if self.step_count < self.warmup_steps:
            # Warmup: 线性增加
            return self.learning_rate * (self.step_count / self.warmup_steps)
        else:
            # Decay: 随时间衰减
            decay = 1.0 / (1.0 + 0.001 * (self.step_count - self.warmup_steps))
            return self.learning_rate * decay
    
    def train_step(
        self,
        x: torch.Tensor,  # features
        y_click: torch.Tensor,  # click label
        y_convert: torch.Tensor,  # convert label
    ) -> dict:
        """
        在线训练一步
        
        Args:
            x: 特征
            y_click: 点击标签
            y_convert: 转化标签
        
        Returns:
            损失和指标
        """
        self.step_count += 1
        self.model.train()
        
        # 获取当前学习率
        lr = self._get_learning_rate()
        
        # 前向传播
        p_ctr, p_ctcvr = self.model(x)
        p_cvr = self.model.compute_cvr(p_ctr, p_ctcvr)
        
        # 计算损失
        loss = self._compute_loss(p_ctr, p_ctcvr, y_click, y_convert)
        
        # 反向传播
        self.optimizer.zero_grad()
        loss.backward()
        
        # 梯度裁剪 (防止梯度爆炸)
        torch.nn.utils.clip_grad_norm_(self.model.parameters(), max_norm=1.0)
        
        self.optimizer.step()
        
        # 弹性遗忘: 对参数应用遗忘因子
        self._apply_forgetting()
        
        return {
            'loss': loss.item(),
            'p_ctr': p_ctr.mean().item(),
            'p_cvr': p_cvr.mean().item(),
            'lr': lr,
        }
    
    def _compute_loss(
        self,
        p_ctr: torch.Tensor,
        p_ctcvr: torch.Tensor,
        y_click: torch.Tensor,
        y_convert: torch.Tensor,
    ) -> torch.Tensor:
        """计算损失"""
        p_ctr_clipped = p_ctr.clamp(min=1e-7, max=1-1e-7)
        p_ctcvr_clipped = p_ctcvr.clamp(min=1e-7, max=1-1e-7)
        
        l_ctr = -(
            y_click * torch.log(p_ctr_clipped) +
            (1 - y_click) * torch.log(1 - p_ctr_clipped)
        ).mean()
        
        l_ctcvr = -(
            y_convert * torch.log(p_ctcvr_clipped) +
            (1 - y_convert) * torch.log(1 - p_ctcvr_clipped)
        ).mean()
        
        return l_ctr + l_ctcvr
    
    def _apply_forgetting(self):
        """
        弹性遗忘: 对模型参数应用遗忘因子
        
        θ_new = γ × θ_old
        """
        with torch.no_grad():
            for param in self.model.parameters():
                param.mul_(self.forget_factor)


class ReplayBuffer:
    """
    经验回放缓冲区: 存储历史样本，防止灾难性遗忘
    
    实现: FIFO (先进先出)
    """
    
    def __init__(self, capacity: int = 10000):
        self.capacity = capacity
        self.buffer = []
    
    def push(self, x: torch.Tensor, y_click: torch.Tensor, y_convert: torch.Tensor):
        """添加样本"""
        if len(self.buffer) >= self.capacity:
            self.buffer.pop(0)  # FIFO: 移除最旧的
        self.buffer.append((x, y_click, y_convert))
    
    def sample(self, batch_size: int = 64) -> tuple:
        """采样 batch"""
        if len(self.buffer) == 0:
            return None
        
        indices = torch.randint(0, len(self.buffer), (batch_size,))
        samples = [self.buffer[i] for i in indices]
        
        x_list, y_click_list, y_convert_list = zip(*samples)
        return (
            torch.stack(x_list),
            torch.stack(y_click_list),
            torch.stack(y_convert_list),
        )
    
    def __len__(self):
        return len(self.buffer)
```

---

## 第五部分：pCVR 评估与优化

### 5.1 评估指标

```
pCVR 模型评估:

┌──────────────────────────────────────────────────────────────┐
│              评估指标                                          │
│                                                              │
│  校准 (Calibration):                                         │
│  ├── Reliability Diagram (可靠性图)                          │
│  │   └─ x: 预测概率, y: 实际频率                             │
│  │   └─ 越接近对角线越好                                      │
│  ├── ECE (Expected Calibration Error)                         │
│  │   └─ ECE = Σ (|pred - actual| × bin_weight)               │
│  └─ Brier Score: E[(p - y)²]                                │
│                                                              │
│  排序 (Discrimination):                                      │
│  ├── AUC-ROC: 区分正负样本的能力                              │
│  ├── AUC-PR: 正负不平衡时的更好的指标                          │
│  └─ LogLoss: 概率质量的度量                                   │
│                                                              │
│  业务指标 (Business Metrics):                                │
│  ├── ROI Impact: 模型对广告 ROI 的影响                         │
│  ├── Revenue Uplift: 模型带来的额外收入                        │
│  └─ CPA Improvement: 模型对 CPA 的改善                         │
│                                                              │
│  线上 A/B 测试:                                              │
│  ├── 实验组: 使用新模型                                        │
│  ├── 对照组: 使用旧模型/基线                                   │
│  └─ 指标: ROI, CPA, Revenue, Conv Rate                       │
│                                                              │
│  在线监控 (Online Monitoring):                               │
│  ├── 预测分布漂移 (Prediction Drift)                          │
│  ├── 特征分布漂移 (Feature Drift)                            │
│  ├── 转化率监控 (Conversion Rate)                             │
│  └─ 延迟监控 (Latency)                                       │
└──────────────────────────────────────────────────────────────┘
```

### 5.2 pCVR 优化

```
pCVR 优化策略:

1. 模型改进:
├── 更深/更宽的 DNN → 更好的非线性拟合                          │
├── 引入 FM/DCN → 更好的特征交叉                                │
├── 引入 Attention → 更好的序列建模                              │
└─ 多任务学习 (MMOE/PLE) → 更好的任务间共享                      │

2. 特征改进:
├── 更多用户行为特征 → 更好的个性化                              │
├── 引入实时特征 → 更好的上下文感知                              │
├── 引入交叉特征 → 更好的捕获交互                                │
└─ 特征选择 → 减少噪声和过拟合                                  │

3. 训练改进:
├── 更好的负采样策略 → 处理类别不平衡                            │
├── 更好的损失函数 → Focal Loss / Class-Balanced Loss           │
├── 更好的优化器 → AdamW / LAMB                                  │
└─ 更好的正则化 → Dropout / Weight Decay / Label Smoothing      │

4. 部署优化:
├── 模型量化 (Quantization) → 推理加速                          │
├── 模型剪枝 (Pruning) → 减小模型大小                           │
├── 知识蒸馏 (Knowledge Distillation) → 小模型近似大模型          │
└─ 特征缓存 → 减少特征计算延迟                                  │

5. 在线优化:
├── 在线学习 → 实时适应数据漂移                                 │
├── 漂移检测 → 自动触发重训练                                   │
└─ A/B 测试 → 持续优化模型                                      │
```

---

## 第六部分：自测题

### 问题 1
ESMM 如何解决 CVR 数据稀疏问题？

<details>
<summary>查看答案</summary>

同时建模三个任务:
- CTR: P(click | impression) — 数据丰富
- CTCVR: P(click & convert | impression) — 比 CVR 丰富
- CVR: P(convert | click) = CTCVR / CTR

通过 CTR 模型约束 CVR 预测，缓解数据稀疏问题。
</details>

### 问题 2
在线学习中的"弹性遗忘"是什么？

<details>
<summary>查看答案</summary>

θ_new = γ × θ_old，其中 γ < 1 (如 0.9999)
对新模型参数应用遗忘因子，避免灾难性遗忘，让模型逐步"忘记"过时数据。
</details>

### 问题 3
pCVR 和 CTR 的主要区别是什么？

<details>
<summary>查看答案</summary>

CTR:
- 数据丰富: 每次展示都有 click/no-click 标签
- 标签即时: 点击在几毫秒内发生
- 样本无偏差: 所有展示都有标签

CVR:
- 数据稀疏: 只有点击后才可能转化
- 标签延迟: 点击后数小时/数天才出现
- 样本偏差: 只有 clicked 用户有标签
- 需要更复杂的模型
</details>

---

*今天花 90 分钟：深入掌握 pCVR 模型技术*
*答不出自测题？回去重读对应章节。*
