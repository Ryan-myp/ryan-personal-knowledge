# Google Ads — 展示广告 RTB 全流程：从 OpenRTB 到 WinBack

> 创建日期: 2026-06-09
> 作者: Ryan
> 定位: 资深专家级

---

## 第一部分：Display 广告的技术架构

### 1.1 RTB 竞价的时间线

```
每次展示请求的 RTB 流程（总预算 ~100ms）：

┌──────────────────────────────────────────────────────────────┐
│  时间线 (毫秒)                                               │
│                                                              │
│  0ms    ┃ 用户访问网站/APP                                   │
│  1ms    ┃ Publisher 发送 OpenRTB 请求到 Ad Exchange           │
│  5ms    ┃ Ad Exchange 转发请求到 SSP                          │
│  10ms   ┃ SSP 广播竞价请求到所有 DSP                           │
│  15ms   ┃ DSP 开始决策：                                      │
│         │   ├── 查询用户画像数据库                            │
│         │   ├── 计算用户-广告匹配度                            │
│         │   ├── 预测 pCTR/pCVR                               │
│         │   └── 计算出价                                     │
│  50ms   ┃ DSP 返回 Bid                                       │
│  55ms   ┃ Ad Exchange 收集所有 Bid                            │
│  70ms   ┃ Ad Exchange 执行拍卖 (Second Price)                 │
│  80ms   ┃ 胜出 DSP 收到通知 (Win Notice)                      │
│  85ms   ┃ Ad Exchange 返回胜出广告创意                          │
│  90ms   ┃ Publisher 渲染广告                                   │
│  100ms  ┃ 广告展示完成                                        │
│                                                              │
│  关键路径: 0 → 85ms (展示给用户)                              │
│  后台路径: 80ms → 85ms (Win Notice + 回传数据)                 │
└──────────────────────────────────────────────────────────────┘
```

### 1.2 OpenRTB 协议深度解析

```
OpenRTB 是 RTB 的核心协议：

OpenRTB Request 结构：
┌──────────────────────────────────────────────────────────────┐
│  {                                                           │
│    "id": "bid-request-12345",                                │
│    "imp": [                                                   │
│      {                                                       │
│        "id": "imp-1",                                       │
│        "banner": {                                          │
│          "w": 300,                                          │
│          "h": 250,                                          │
│          "format": [                                        │
│            {"w": 300, "h": 250},                            │
│            {"w": 320, "h": 50}                              │
│          ]                                                  │
│        },                                                   │
│        "bidfloor": 1.00,  // 最低出价 ($1 CPM)               │
│        "secure": true,                                       │
│        "instl": 0,  // 0=页面内, 1=Interstitial              │
│        "topframe": 1,  // 是否在顶层框架中                    │
│        "at": 1  // 1=First Price, 2=Second Price             │
│      }                                                      │
│    ],                                                       │
│    "site": {                                                │
│      "domain": "example.com",                               │
│      "name": "Example Site",                                │
│      "page": "https://example.com/article",                 │
│      "cat": ["IAB19"],  // 内容类别                          │
│      "keywords": "sports,football",                         │
│      "publisher": {                                         │
│        "id": "pub-123",                                     │
│        "name": "Example Publisher"                          │
│      }                                                      │
│    },                                                       │
│    "app": {  // 如果是 APP 请求                              │
│      "bundle": "com.example.app",                           │
│      "name": "Example App",                                 │
│      "storeurl": "https://itunes.apple.com/app/...",        │
│      "cat": ["IAB8"],                                       │
│      "keywords": "games,puzzle"                              │
│    },                                                       │
│    "device": {                                              │
│      "ua": "Mozilla/5.0 ...",                               │
│      "ip": "192.168.1.1",                                   │
│      "ipv6": "2001:db8::1",                                 │
│      "dnt": 0,  // Do Not Track                             │
│      "devicetype": 1,  // 1=Mobile, 2=Tablet, 3=Desktop     │
│      "carrier": "Verizon",                                  │
│      "connectiontype": 2,  // 2=LTE, 3=WIFI                  │
│      "geo": {                                               │
│        "lat": 40.7128,                                      │
│        "lon": -74.0060,                                     │
│        "country": "US",                                     │
│        "region": "NY",                                      │
│        "city": "New York"                                   │
│      }                                                      │
│    },                                                       │
│    "user": {                                                │
│      "id": "hashed-user-id",                                │
│      "buyeruid": "dsp-user-123",                            │
│      "gender": "M",                                         │
│      "youth": 25,                                           │
│      "ext": {"data": {"segments": ["auto_interest"]}}       │
│    },                                                       │
│    "regs": {                                                │
│      "ext": {                                               │
│        "gdpr": 1,  // GDPR 同意                              │
│        "ccpa": 0  // CCPA 不限制                             │
│      }                                                      │
│    },                                                       │
│    "ext": {                                                 │
│      "prebid": {...},  // Prebid.js 扩展                    │
│      "schain": {  // Supply Chain                           │
│        "complete": 1,                                       │
│        "nodes": [                                           │
│          {                                                  │
│            "asi": "publisher.com",                           │
│            "sid": "publisher-123",                          │
│            "hp": 1                                          │
│          }                                                  │
│        ]                                                    │
│      }                                                      │
│    }                                                        │
│  }                                                          │
└──────────────────────────────────────────────────────────────┘

OpenRTB Response 结构：
┌──────────────────────────────────────────────────────────────┐
│  {                                                           │
│    "id": "bid-response-12345",                               │
│    "seatbid": [                                              │
│      {                                                       │
│        "bid": [                                              │
│          {                                                  │
│            "id": "bid-1",                                   │
│            "impid": "imp-1",                                │
│            "price": 2.50,  // CPM ($2.50)                   │
│            "adm": "<div>...</div>",  // 广告 HTML/JSON      │
│            "adid": "creative-123",                          │
│            "cid": "campaign-456",                           │
│            "crid": "ad-789",                                │
│            "adomain": ["example.com"],                      │
│            "bundle": "com.example.app",                     │
│            "imprid": "impression-tracking-123",             │
│            "nurl": "https://dsp.com/win-notice?bid=123",    │
│            "lurl": "https://dsp.com/lost-notice?bid=123",   │
│            "murl": "https://dsp.com/impression?bid=123",    │
│            "duid": "user-123",  // DSP 用户 ID               │
│            "attr": [1, 2, 3],  // 广告属性                   │
│            "api": 2,  // API 框架                            │
│            "mtype": 1,  // 媒体类型                          │
│            "protocol": 5  // 协议版本                        │
│          }                                                  │
│        ],                                                   │
│        "seat": "dsp-1",  // DSP ID                          │
│        "group": 0  // 0=不限制次数, >0=限制次数              │
│      }                                                      │
│    ],                                                       │
│    "cur": "USD",  // 货币                                    │
│    "nurl": "https://dsp.com/bid-warning",  // 警告 URL       │
│    "adid": "allowed-creative-123"  // 允许的广告 ID           │
│  }                                                          │
└──────────────────────────────────────────────────────────────┘
```

---

## 第二部分：DSP 出价决策内核

### 2.1 DSP 出价决策的数学模型

```
DSP 每次收到竞价请求时，需要在 35ms 内完成出价决策：

决策流程：
┌─────────────────────────────────────────────────────────────────┐
│  1. 用户查询 (User Lookup)                    [0-5ms]           │
│  ├── 从用户画像数据库查询用户信息                              │
│  ├── 查询用户的历史行为 (点击/转化)                             │
│  └── 查询用户的实时兴趣                                       │
│                                                               │
│  2. 创意查询 (Creative Query)                  [5-10ms]        │
│  ├── 根据广告活动匹配适合的创意                                 │
│  ├── 检查创意频率限制 (Frequency Cap)                          │
│  └── 选择最佳创意                                            │
│                                                               │
│  3. 出价计算 (Bid Calculation)              [10-50ms]          │
│  ├── 计算期望价值: EV = pConversion × Conversion_Value        │
│  ├── 考虑预算 pacing: Bid = EV × Pacing_Adjustment            │
│  ├── 考虑竞争环境: Bid = EV × (1 + Competitive_Factor)        │
│  ├── 考虑频次控制: Bid *= Frequency_Reduction                   │
│  └── 应用出价上限: Bid = min(Bid, Max_CPC)                    │
│                                                               │
│  4. 竞价响应 (Bid Response)                  [50-85ms]         │
│  └── 组装 OpenRTB Response 返回                               │
│                                                               │
│  总预算: ~85ms                                               │
└─────────────────────────────────────────────────────────────────┘

出价公式的完整推导：

Base_Bid = Target_CPA × pCVR × pClick

其中：
├─ Target_CPA: 广告主设置的目标 CPA
├─ pCVR: 预测转化率（用户点击后转化）
└─ pClick: 预测点击率（用户看到广告后点击）

调整因子：
├─ Pacing: 预算消耗速度调整 (0.5 - 2.0)
│   └─ 如果预算花太快 → Pacing < 1 → 降低出价
│   └─ 如果预算花太慢 → Pacing > 1 → 提高出价
├─ Competitive: 竞争调整 (0.8 - 1.5)
│   └─ 高竞争时段 → Competitive > 1
│   └─ 低竞争时段 → Competitive < 1
└─ Frequency: 频次调整 (0.2 - 1.0)
   └─ 用户已看过 N 次 → Frequency 递减
   └─ Frequency = exp(-λ × N)  (指数衰减)

Final_Bid = Base_Bid × Pacing × Competitive × Frequency
```

### 2.2 pCVR 预测模型（生产级）

```python
# dsp/prediction/cvr_model.py
# 生产级 pCVR 预测模型

import numpy as np
from typing import Dict, List, Tuple
import torch
import torch.nn as nn

class CVRModel(nn.Module):
    """
    pCVR 预测模型 - 生产级实现
    
    特征输入：
    ├── 用户特征: 历史行为、兴趣标签、人口统计
    ├── 上下文特征: 时间、设备、位置、网站
    ├── 广告特征: 创意 ID、广告主、类别
    └── 交叉特征: 用户 × 广告, 用户 × 上下文, 广告 × 上下文
    
    输出：
    └── pCVR ∈ [0, 1]
    """
    
    def __init__(
        self,
        user_feature_dim: int = 128,
        context_feature_dim: int = 64,
        ad_feature_dim: int = 64,
        hidden_dim: int = 256,
        num_layers: int = 3,
        dropout: float = 0.1,
    ):
        super().__init__()
        
        # 用户塔
        self.user_encoder = nn.Sequential(
            nn.Linear(user_feature_dim, hidden_dim),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.LayerNorm(hidden_dim),
        )
        
        # 上下文塔
        self.context_encoder = nn.Sequential(
            nn.Linear(context_feature_dim, hidden_dim),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.LayerNorm(hidden_dim),
        )
        
        # 广告塔
        self.ad_encoder = nn.Sequential(
            nn.Linear(ad_feature_dim, hidden_dim),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.LayerNorm(hidden_dim),
        )
        
        # 交叉特征塔
        self.cross_encoder = nn.Sequential(
            nn.Linear(hidden_dim * 3, hidden_dim * 2),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.LayerNorm(hidden_dim * 2),
        )
        
        # 输出层
        self.output = nn.Sequential(
            nn.Linear(hidden_dim * 2, 64),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(64, 1),
            nn.Sigmoid(),  # 输出 [0, 1]
        )
    
    def forward(self, user_features: torch.Tensor,
                context_features: torch.Tensor,
                ad_features: torch.Tensor) -> torch.Tensor:
        """
        前向传播
        
        参数:
        ├── user_features: [batch_size, user_feature_dim]
        ├── context_features: [batch_size, context_feature_dim]
        └── ad_features: [batch_size, ad_feature_dim]
        
        返回:
        └── pCVR: [batch_size, 1]
        """
        # 编码各塔
        user_emb = self.user_encoder(user_features)
        context_emb = self.context_encoder(context_features)
        ad_emb = self.ad_encoder(ad_features)
        
        # 交叉
        cross_input = torch.cat([user_emb, context_emb, ad_emb], dim=-1)
        cross_output = self.cross_encoder(cross_input)
        
        # 输出
        pcvr = self.output(cross_output)
        
        return pcvr.squeeze(-1)


class CVRPredictor:
    """
    pCVR 预测器 - 封装模型推理
    
    支持:
    ├── 批量预测 (推荐)
    ├── 单条预测
    └── 特征处理
    """
    
    def __init__(self, model: CVRModel, device: str = 'cpu'):
        self.model = model
        self.device = device
        self.model.eval()
    
    def predict_batch(self, 
                      user_features: np.ndarray,
                      context_features: np.ndarray,
                      ad_features: np.ndarray) -> np.ndarray:
        """
        批量预测 pCVR
        
        参数:
        ├── user_features: [batch, user_dim]
        ├── context_features: [batch, context_dim]
        └── ad_features: [batch, ad_dim]
        
        返回:
        └── pCVR: [batch]
        """
        with torch.no_grad():
            user_t = torch.tensor(user_features, device=self.device)
            context_t = torch.tensor(context_features, device=self.device)
            ad_t = torch.tensor(ad_features, device=self.device)
            
            pcvr = self.model(user_t, context_t, ad_t)
            return pcvr.cpu().numpy()
    
    def predict_single(self,
                       user_feature: np.ndarray,
                       context_feature: np.ndarray,
                       ad_feature: np.ndarray) -> float:
        """
        单条预测（用于实时竞价）
        
        参数:
        └── 各特征 [dim,]
        
        返回:
        └── pCVR (0-1)
        """
        return self.predict_batch(
            user_feature.reshape(1, -1),
            context_feature.reshape(1, -1),
            ad_feature.reshape(1, -1)
        )[0]
```

### 2.3 预算 pacing 的深层控制

```
预算 pacing 是 DSP 控制花费速度核心算法：

问题：如果上午就把预算花光，下午就完全没有展示

Pacing 算法：

1. 目标速率模型:
   Target_Rate(t) = Daily_Budget / (24h × Time_Proportion(t))

2. 实际速率:
   Actual_Rate(t) = Spend(0,t) / t

3. 速率偏差:
   Bias(t) = Actual_Rate(t) / Target_Rate(t)

4. 出价调整:
   Bid_Adjustment(t) = f(Bias(t))

实现方式:

A. 简单线性调整:
   Bid_Adjustment = max(0.1, min(3.0, Target_Rate / Actual_Rate))

B. 指数平滑 (推荐):
   Smooth_Bias(t) = α × Bias(t) + (1-α) × Smooth_Bias(t-1)
   Bid_Adjustment = max(0.1, min(3.0, 1.0 / Smooth_Bias))
   
   α 是平滑因子 (0.1-0.3)

C. PID 控制 (高级):
   P (比例): 当前偏差 → 直接调整
   I (积分): 累积偏差 → 消除稳态误差
   D (微分): 偏差变化率 → 预测未来趋势
   
   Bid_Adjustment = Kp × Error + Ki × ∫Error + Kd × d(Error)/dt

生产实现注意事项：
├─ 更新频率: 每 5-10 分钟更新一次 pacing
├─ 边界: Bid_Adjustment ∈ [0.1, 3.0]
├─ 回退: 如果 pacing 持续 > 3 → 提高出价
└─ 监控: 实时跟踪 Actual vs Target
```

---

## 第三部分：实时竞价中的竞争分析

### 3.1 竞争环境的量化

```
如何在竞价时估计竞争强度？

方法 1: 基于历史 Bid 数据
──────────────────────────────
竞争指数 = Σ (其他_Bid / 自己的_Bid)

如果竞争指数 > 1.0 → 竞争激烈 → 提高出价
如果竞争指数 < 0.5 → 竞争较弱 → 降低出价

方法 2: 基于 Win Rate
──────────────────────────────
历史 Win Rate = Wins / Bids_Sent

Win Rate < 5% → 出价太低或竞争太强
Win Rate > 80% → 出价过高，有优化空间
Win Rate 15-40% → 理想区间

方法 3: 基于市场价格估算
──────────────────────────────
Estimated_Price = Σ (Second_Highest_Bid) / Bids_Sent

如果 Estimated_Price > 自己的 Bid → 没赢
如果 Estimated_Price << 自己的 Bid → 出价过高

方法 4: 基于 SSP 反馈
──────────────────────────────
SSP 会返回:
├─ Rank: 你的竞价排名 (1-10)
├─ Last_Win_Price: 上次胜出价格
└─ Bids_Sent: 本次有多少家竞价

Rank 1 且 price 低 = 完美胜出
Rank 2-5 = 竞争激烈，需要提高出价
Rank > 5 = 出价太低
```

### 3.2 WinBack 策略

```
WinBack (挽回策略): 在竞价后根据结果调整出价

竞价结果分析:
├─ Won (胜出):
│   ├── 实际支付价格 vs 预期价格
│   ├── 如果实际 << 预期 → 出价过高 → 下次降低
│   └── 如果实际 >> 预期 → 竞争强 → 下次提高
│
├─ Lost (落选):
│   ├── 排名太低 → 下次提高出价
│   ├── 排名合适但输给了更高价 → 竞争强 → 下次提高
│   └── 排名太高但输给了更低价 → 可能有其他过滤条件
│
└─ No_Bid (不竞价):
    ├── 超出预算 →  pacing 控制
    ├── 频次限制 → 跳过
    └── 不符合定向 → 跳过

WinBack 算法:

if won:
    if actual_price << expected_price:
        # 出价过高，下次降低
        bid *= 0.95
    elif actual_price >> expected_price:
        # 竞争强，下次提高
        bid *= 1.05
elif lost:
    # 检查 Rank
    if rank < 5:
        # 排名低但输了，竞争强
        bid *= 1.1
    elif rank > 10:
        # 排名很低，直接提高
        bid *= 1.2

# 边界控制
bid = max(min_bid, min(max_bid, bid))
```

---

## 第四部分：广告创意与实时渲染

### 4.1 广告创意的实时传递

```
DSP 返回的创意格式：

Banner 广告:
├─ adm (HTML): <div><img src="..."><p>...</p></div>
├─ adm (JSON): {"body": "<img src='...'>", "link": "https://..."}
└─ adm (VAST): 视频广告的描述 XML

视频广告 (VAST 格式):
┌──────────────────────────────────────────────────────────────┐
│  <VAST version="3.0">                                       │
│    <Ad>                                                      │
│      <InLine>                                               │
│        <AdSystem>Google Ad Manager</AdSystem>                │
│        <AdTitle>Product Ad</AdTitle>                         │
│        <Creatives>                                          │
│          <Creative id="123">                                │
│            <Linear>                                         │
│              <Duration>00:00:15</Duration>                   │
│              <MediaFiles>                                   │
│                <MediaFile                          │
│                  delivery="progressive"                     │
│                  type="video/mp4"                           │
│                  width="640" height="360">                  │
│                  <![CDATA[https://.../video.mp4]]>          │
│                </MediaFile>                                │
│              </MediaFiles>                                  │
│              <TrackingEvents>                               │
│                <Impression>https://dsp.com/imp?bid=123</Impression> │
│                <Start>https://dsp.com/start?bid=123</Start> │
│                <FirstQuartile>https://dsp.com/1q?bid=123</FirstQuartile> │
│                <Midpoint>https://dsp.com/mp?bid=123</Midpoint> │
│                <ThirdQuartile>https://dsp.com/3q?bid=123</ThirdQuartile> │
│                <Complete>https://dsp.com/done?bid=123</Complete> │
│                <Viewable>https://dsp.com/viewable?bid=123</Viewable> │
│              </TrackingEvents>                              │
│              <ClickThrough>https://landing.page</ClickThrough> │
│              <ClickTracking>https://dsp.com/click?bid=123</ClickTracking> │
│            </Linear>                                       │
│          </Creative>                                       │
│        </Creatives>                                        │
│      </InLine>                                             │
│    </Ad>                                                   │
│  </VAST>                                                   │
└──────────────────────────────────────────────────────────────┘

追踪像素 (Impression Tracking):
├─ murl (M Pixel): 每次展示触发
├─ nurl (N Pixel): 每次胜出触发
├─ lurl (L Pixel): 每次落选触发
└─ iurl (I Pixel): 每次点击触发
```

### 4.2 频率控制 (Frequency Cap)

```
频率控制防止用户过度暴露于同一广告：

策略层级:
├─ 用户级别: 同一用户 N 天内最多看到 N 次
├─ 会话级别: 同一会话中最多看到 N 次
└─ 频次上限: 同一广告组 N 天内最多 N 次

实现:
┌──────────────────────────────────────────────────────────────┐
│  FrequencyManager:                                            │
│                                                               │
│  ├── 数据结构:                                                │
│  │   ├── UserFrequencyCache: {user_id: {ad_id: count}}       │
│  │   ├── SessionFrequencyCache: {session_id: {ad_id: count}} │
│  │   └── TTL: 7 天 (可配置)                                  │
│  │                                                           │
│  ├── 检查:                                                   │
│  │   ├── GetUserFrequency(user_id, ad_id) → count           │
│  │   └── count < Max_Frequency → 允许竞价                    │
│  │   └── count >= Max_Frequency → 跳过                       │
│  │                                                           │
│  ├── 更新:                                                   │
│  │   └── 竞价成功后: IncrementFrequency(user_id, ad_id)     │
│  │                                                           │
│  └── 优化:                                                  │
│      ├── 使用 Bloom Filter 减少内存                          │
│      ├── 定期清理过期数据                                    │
│      └── 使用 Redis 分布式缓存                               │
└──────────────────────────────────────────────────────────────┘

频率衰减函数:
Response_Reduction = exp(-λ × Frequency)

其中 λ 是衰减因子 (0.3-0.5)
频率越高，用户响应越低
```

---

## 第五部分：RTB 生态系统

### 5.1 完整的 RTB 链路

```
RTB 的完整参与者：

┌──────────────────────────────────────────────────────────────────┐
│                     RTB Ecosystem                               │
│                                                                  │
│  User (用户)                                                    │
│     ↓                                                            │
│  Publisher (网站/APP 所有者)                                     │
│     ├── Ad Server (广告服务器): Google Ad Manager, OpenX        │
│     │   └── 管理广告位、创意、价格                               │
│     │                                                          │
│     └── SSP (Supply Side Platform):                          │
│         ├── Prebid.js (开源)                                  │
│         ├── AppNexus (Amazon)                                 │
│         ├── Rubicon Project                                   │
│         └── ─── 聚合 SSP 的库存，向 DSP 发出竞价请求           │
│                                                                  │
│  Ad Exchange (广告交易平台):                                     │
│  ├── Google AdX                                                  │
│  ├── PubMatic                                                    │
│  ├── OpenX                                                      │
│  └── ─── 执行竞价、结算、归因                                   │
│                                                                  │
│  DSP (Demand Side Platform):                                    │
│  ├── Google DV360                                               │
│  ├── The Trade Desk                                             │
│  ├── Amazon DSP                                                 │
│  └── ─── 接收竞价请求、出价、返回创意                            │
│                                                                  │
│  DMP (Data Management Platform):                                │
│  ├── 用户画像、兴趣标签、行为数据                                 │
│  └── ─── 为 DSP 提供用户数据                                    │
│                                                                  │
│  Ad Network (广告网络):                                         │
│  ├── 聚合多个 SSP/Exchange 的库存                               │
│  └── ─── 简化 DSP 的接入                                        │
└──────────────────────────────────────────────────────────────────┘
```

### 5.2 归因与转化回传

```
展示广告的归因挑战：

问题：用户在看到广告后没有立即转化，而是在几天后通过其他方式转化

归因方式:
├─ Last Click: 最后点击的广告获得 100% 功劳
│   └─ 问题: 忽略了展示广告的作用
│
├─ View-Through Conversion (VTC): 展示后 N 天内转化
│   └─ 问题: 高估了展示广告的价值
│
└─ Incremental Measurement: 实验设计测量增量
   └─ 最优但最复杂

转化回传流程:
1. DSP 跟踪转化 (通过 Pixel 或 SDK)
2. 收集转化数据:
   ├── 转化类型: 购买、注册、下载
   ├── 转化价值: 订单金额
   ├── 时间: 转化时间
   └── 来源: 哪个广告/创意
3. 回传到 SSP/Exchange (可选)
4. 优化出价模型
```

---

## 自测题

### 问题 1
RTB 竞价的总预算是多少毫秒？

<details>
<summary>查看答案</summary>

- 总预算约 100ms
- 关键路径 0-85ms (展示给用户)
- DSP 决策时间 10-50ms
</details>

### 问题 2
pCVR 预测模型中，交叉特征的作用是什么？

<details>
<summary>查看答案</summary>

- 捕获用户 × 广告 × 上下文的交互效应
- 单独的用户/广告特征不够，需要交叉
- 例如：年轻用户 × 游戏广告 × 移动端 = 高 pCVR
</details>

### 问题 3
WinBack 策略中，如果实际支付价格远低于预期价格，说明什么？

<details>
<summary>查看答案</summary>

- 出价过高，花冤枉钱
- 下次应该降低出价 (约 5%)
- 可以通过 WinBack 逐步优化
</details>

---

## 动手验证

### 5.1 出价决策模拟

```python
import numpy as np

class Bidder:
    """简化的 RTB 出价器"""
    
    def __init__(self, target_cpa: float = 20.0, 
                 max_bid: float = 5.0,
                 min_bid: float = 0.01):
        self.target_cpa = target_cpa
        self.max_bid = max_bid
        self.min_bid = min_bid
        self.win_count = 0
        self.lose_count = 0
    
    def calculate_bid(self, p_click: float, p_cvr: float,
                      pacing: float = 1.0) -> float:
        """计算出价"""
        base_bid = self.target_cpa * p_cvr * p_click
        adjusted_bid = base_bid * pacing
        return max(self.min_bid, min(self.max_bid, adjusted_bid))
    
    def winback(self, actual_price: float, expected_price: float) -> float:
        """WinBack 调整"""
        if actual_price < expected_price * 0.7:
            # 出价过高
            return 0.95
        elif actual_price > expected_price * 1.3:
            # 竞争强
            return 1.05
        return 1.0
    
    def record_bid(self, won: bool):
        """记录竞价结果"""
        if won:
            self.win_count += 1
        else:
            self.lose_count += 1

# 模拟
bidder = Bidder(target_cpa=20.0, max_bid=3.0)

# 用户点击概率 5%, 转化概率 2%
p_click = 0.05
p_cvr = 0.02

bid = bidder.calculate_bid(p_click, p_cvr)
print(f"出价: ${bid:.4f}")
print(f"期望 CPA: ${bidder.target_cpa:.2f}")
```

### 5. Go 实现：RTB 竞价引擎

```go
package main

import (
	"context"
	"encoding/json"
	"fmt"
	"math"
	"sync"
	"time"
)

// BidRequest 竞价请求 (OpenRTB 格式)
type BidRequest struct {
	ID            string          `json:"id"`
	Impressions   []Impression    `json:"imp"`
	Site          *Site           `json:"site,omitempty"`
	App           *App            `json:"app,omitempty"`
	User          *User           `json:"user,omitempty"`
	Device        *Device         `json:"device,omitempty"`
	Source        *BidRequestSource `json:"source,omitempty"`
	SellerNetwork SellerNetwork   `json:"seller_network,omitempty"`
	Test          int             `json:"test,omitempty"`
}

type BidRequestSource struct {
	ContactData string `json:"contact_data,omitempty"`
	Codec         string `json:"codec,omitempty"`
}

type SellerNetwork struct {
	ID      string `json:"id"`
	Name    string `json:"name"`
	Version string `json:"version"`
}

// Impression 展示位信息
type Impression struct {
	ID            string          `json:"id"`
	Banner        *Banner         `json:"banner,omitempty"`
	Video         *Video          `json:"video,omitempty"`
	Native        *Native         `json:"native,omitempty"`
	Instl         int             `json:"instl,omitempty"`
	TagID         string          `json:"tag_id,omitempty"`
	BidFloor      float64         `json:"bidfloor"`
	BidFloorMicro int64           `json:"bidfloormicros,omitempty"`
	Secure        int             `json:"secure,omitempty"`
	VideoMimes    []string        `json:"video_mimes,omitempty"`
	Placement     int             `json:"placement,omitempty"`
	QASettings    json.RawMessage `json:"qasettings,omitempty"`
	Attrs         []string        `json:"attrs,omitempty"`
}

type Banner struct {
	W     int     `json:"w,omitempty"`
	H     int     `json:"h,omitempty"`
	WMax  int     `json:"wmax,omitempty"`
	HMax  int     `json:"hmax,omitempty"`
	Format []BannerFormat `json:"format,omitempty"`
}

type BannerFormat struct {
	W int `json:"w"`
	H int `json:"h"`
}

type Video struct {
	Mimes  []string  `json:"mimes"`
	Protocols []int  `json:"protocols"`
	MaxBitrate int `json:"maxbitrate"`
	MaxDuration int `json:"maxduration"`
	W      int `json:"w,omitempty"`
	H      int `json:"h,omitempty"`
	StartDelay int `json:"startdelay,omitempty"`
	Linearity int `json:"linearity"`
}

type Native struct {
	Request string `json:"request"`
	ResponseTypes []string `json:"response_types,omitempty"`
}

type Site struct {
	ID       string `json:"id,omitempty"`
	Name     string `json:"name,omitempty"`
	Domain   string `json:"domain,omitempty"`
	Cat      []string `json:"cat,omitempty"`
	SectionCat []string `json:"sectioncat,omitempty"`
	PageCat  []string `json:"pagecat,omitempty"`
}

type App struct {
	ID     string `json:"id,omitempty"`
	Name   string `json:"name,omitempty"`
	Domain string `json:"domain,omitempty"`
	Cat    []string `json:"cat,omitempty"`
}

type User struct {
	ID     string   `json:"id,omitempty"`
	BuyerUID string `json:"buyeruid,omitempty"`
	Keywords string   `json:"keywords,omitempty"`
	Guest  int      `json:"guest,omitempty"`
	YOB    int      `json:"yob,omitempty"`
	Gender string   `json:"gender,omitempty"`
}

type Device struct {
	UA       string `json:"ua,omitempty"`
	IP       string `json:"ip,omitempty"`
	DPID     string `json:"dpid,omitempty"`
	Model    string `json:"model,omitempty"`
	DeviceType int  `json:"devicetype"`
	ConnectionType int `json:"connectiontype"`
	Carrier string   `json:"carrier,omitempty"`
}

// BidResponse 竞价响应
type BidResponse struct {
	ID      string        `json:"id"`
	BidID   string        `json:"bidid,omitempty"`
	Budget  []BudgetResult `json:"budget,omitempty"`
	SeatBid []SeatBid     `json:"seatbid"`
	Seat    string        `json:"seat,omitempty"`
	NBanner int           `json:"nbanner,omitempty"`
	NVideo  int           `json:"nvideo,omitempty"`
	NNative int           `json:"nnative,omitempty"`
}

type BudgetResult struct {
	ID     string `json:"id"`
	Status string `json:"status"`
	Budget int64  `json:"budget"`
}

type SeatBid struct {
	Bid  []Bid     `json:"bid"`
	Seat string    `json:"seat"`
}

type Bid struct {
	ID            string  `json:"id"`
	BidID         string  `json:"bidid,omitempty"`
 impID         string  `json:"impid"`
	Price         float64 `json:"price"`
	AdM           string  `json:"adm"`
	AdID          string  `json:"adid,omitempty"`
	Adomain       []string `json:"adomain,omitempty"`
	Iurl          string  `json:"iurl,omitempty"`
	Crid          string  `json:"crid,omitempty"`
	W             int     `json:"w,omitempty"`
	H             int     `json:"h,omitempty"`
	Qur           string  `json:"qurl,omitempty"`
	Cat           []string `json:"cat,omitempty"`
	Mtype         int     `json:"mtype,omitempty"`
	DealID        string  `json:"dealid,omitempty"`
	Bundle        string  `json:"bundle,omitempty"`
	Ver           string  `json:"ver,omitempty"`
}

// AdBidder 广告竞价器
type AdBidder struct {
	mu             sync.Mutex
	pClickModels   map[string]*pClickModel
	pCvrModels     map[string]*pCvrModel
	bidHistory     []BidRecord
	maxBid         float64
	targetCPA      float64
	timeout        time.Duration
}

type pClickModel struct {
	features map[string]float64
	weights  map[string]float64
	bias     float64
}

type pCvrModel struct {
	features map[string]float64
	weights  map[string]float64
	bias     float64
}

type BidRecord struct {
	RequestID string
	ImpID     string
	BidPrice  float64
	Won       bool
	Timestamp time.Time
}

// NewAdBidder 创建竞价器
func NewAdBidder(maxBid, targetCPA float64) *AdBidder {
	return &AdBidder{
		pClickModels: make(map[string]*pClickModel),
		pCvrModels:   make(map[string]*pCvrModel),
		maxBid:       maxBid,
		targetCPA:    targetCPA,
		timeout:      100 * time.Millisecond, // RTB 竞价通常 100ms 内完成
	}
}

// RegisterModel 注册 pCTR/pCVR 模型
func (b *AdBidder) RegisterModel(modelType, name string, weights map[string]float64, bias float64) {
	b.mu.Lock()
	defer b.mu.Unlock()
	if modelType == "pctr" {
		b.pClickModels[name] = &pClickModel{features: map[string]float64{}, weights: weights, bias: bias}
	} else {
		b.pCvrModels[name] = &pCvrModel{features: map[string]float64{}, weights: weights, bias: bias}
	}
}

// sigmoid sigmoid 函数
func sigmoid(x float64) float64 {
	return 1.0 / (1.0 + math.Exp(-x))
}

// PredictCTR 预测点击率
func (b *AdBidder) PredictCTR(features map[string]float64, modelName string) float64 {
	b.mu.Lock()
	model, ok := b.pClickModels[modelName]
	b.mu.Unlock()
	if !ok {
		return 0.01 // 默认 1%
	}
	score := model.bias
	for k, v := range model.weights {
		score += v * features[k]
	}
	return sigmoid(score)
}

// PredictCVR 预测转化率
func (b *AdBidder) PredictCVR(features map[string]float64, modelName string) float64 {
	b.mu.Lock()
	model, ok := b.pCvrModels[modelName]
	b.mu.Unlock()
	if !ok {
		return 0.005 // 默认 0.5%
	}
	score := model.bias
	for k, v := range model.weights {
		score += v * features[k]
	}
	return sigmoid(score)
}

// CalculateBid 计算最优出价
func (b *AdBidder) CalculateBid(ctr, cvr float64) float64 {
	// eCPA = bid * pClick * pCVR → bid = targetCPA * pCVR / pClick
	eCPA := ctr * cvr * b.targetCPA
	bid := b.targetCPA * cvr / (ctr + 1e-10)
	// 限制最大出价
	if bid > b.maxBid {
		bid = b.maxBid
	}
	return bid
}

// RecordBid 记录竞价结果
func (b *AdBidder) RecordBid(requestID, impID string, price float64, won bool) {
	b.mu.Lock()
	defer b.mu.Unlock()
	b.bidHistory = append(b.bidHistory, BidRecord{
		RequestID: requestID,
		ImpID:     impID,
		BidPrice:  price,
		Won:       won,
		Timestamp: time.Now(),
	})
}

// RTBBidder 完整的 RTB 竞价流水线
type RTBBidder struct {
	bidder *AdBidder
	tracker *BidTracker
}

type BidTracker struct {
	mu           sync.Mutex
	impressions  int
	clicks       int
	conversions  int
	totalSpent   float64
}

func (t *BidTracker) Impression() {
	t.mu.Lock()
	defer t.mu.Unlock()
	t.impressions++
}

func (t *BidTracker) Click() {
	t.mu.Lock()
	defer t.mu.Unlock()
	t.clicks++
}

func (t *BidTracker) Conversion(value float64) {
	t.mu.Lock()
	defer t.mu.Unlock()
	t.conversions++
	t.totalSpent += value
}

func (t *BidTracker) Stats() (float64, float64, float64) {
	t.mu.Lock()
	defer t.mu.Unlock()
	cvr := float64(t.conversions) / float64(t.clicks+1)
	cpc := t.totalSpent / float64(t.clicks+1)
	return float64(t.impressions), cvr, cpc
}

func NewRTBBidder(maxBid, targetCPA float64) *RTBBidder {
	return &RTBBidder{
		bidder:  NewAdBidder(maxBid, targetCPA),
		tracker: &BidTracker{},
	}
}

// Process 处理单个竞价请求
func (r *RTBBidder) Process(ctx context.Context, req *BidRequest) (*BidResponse, error) {
	if len(req.Impressions) == 0 {
		return nil, fmt.Errorf("no impressions in request")
	}
	imp := req.Impressions[0]

	// 提取特征
	features := map[string]float64{
		"device_type": float64(req.Device.DeviceType),
		"connection":  float64(req.Device.ConnectionType),
	}

	// 1. 预测 CTR
	ctr := r.bidder.PredictCTR(features, "default")

	// 2. 预测 CVR
	cvr := r.bidder.PredictCVR(features, "default")

	// 3. 计算出价
	bidPrice := r.bidder.CalculateBid(ctr, cvr)

	// 4. 考虑底价
	if bidPrice < imp.BidFloor {
		return nil, nil // 出价低于底价，放弃竞价
	}

	// 5. 构建响应
	seatBid := SeatBid{
		Bid: []Bid{
			{
				ID:     "bid-" + time.Now().Format("20060102150405"),
				impID:  imp.ID,
				Price:  bidPrice,
				AdM:    "<creative><img src=\"https://ads.example.com/c?id=123\"/></creative>",
				Adomain: []string{"example.com"},
				W:      300,
				H:      250,
			},
		},
		Seat: "dsp-1",
	}

	return &BidResponse{
		ID:      req.ID,
		BidID:   fmt.Sprintf("bid-response-%d", time.Now().UnixNano()),
		SeatBid: []SeatBid{seatBid},
		Seat:    "dsp-1",
	}, nil
}

// main 演示
func main() {
	bidder := NewRTBBidder(5.0, 20.0)
	bidder.bidder.RegisterModel("pctr", "default", map[string]float64{
		"device_type": 0.1,
		"connection":  0.05,
	}, 0.01)
	bidder.bidder.RegisterModel("pcvr", "default", map[string]float64{
		"device_type": 0.2,
	}, 0.005)

	// 模拟竞价请求
	req := &BidRequest{
		ID:   "req-001",
		Test: 1,
		Impressions: []Impression{
			{
				ID:          "imp-001",
				BidFloor:    0.5,
				BidFloorMicro: 500000,
				TagID:       "ad-slot-123",
				Instl:       0,
				Banner: &Banner{
					W: 300,
					H: 250,
					Format: []BannerFormat{{W: 300, H: 250}},
				},
			},
		},
		Device: &Device{
			DeviceType:   2,    // MOBILE
			ConnectionType: 5,  // WIF
			IP:           "192.168.1.1",
			UA:           "Mozilla/5.0",
		},
		Site: &Site{
			Domain: "example.com",
			Name:   "Example Site",
		},
	}

	resp, err := bidder.Process(context.Background(), req)
	if err != nil {
		fmt.Printf("error: %v\n", err)
		return
	}
	if resp == nil {
		fmt.Println("no bid")
		return
	}
	for _, sb := range resp.SeatBid {
		for _, bid := range sb.Bid {
			fmt.Printf("Bid: impID=%s price=%.4f ad=%.20s\n", bid.impID, bid.Price, bid.AdM)
		}
	}
}
```

### Google Display RTB 的 Go 实现

```go
// Google Display RTB: 展示广告竞价引擎
// 覆盖 RTB 请求解析、出价决策、创意渲染
package displayrtb

import (
	"encoding/json"
	"fmt"
	"sync"
	"time"
)

// ==================== Display BidRequest ====================

// DisplayBidRequest 展示广告竞价请求
type DisplayBidRequest struct {
	ID        string      `json:"id"`
	TMax      int         `json:"tmax"`
	Impressions []Impression `json:"imp"`
	Site      *Site       `json:"site,omitempty"`
	App       *App        `json:"app,omitempty"`
	Device    *Device     `json:"device"`
	User      *User       `json:"user,omitempty"`
	At        int         `json:"at"` // 竞价类型
}

// Impression 展示位
type Impression struct {
	ID        string  `json:"id"`
	Banner    *Banner `json:"banner"`
	BidFloor  float64 `json:"bidfloor"`
	Secure    int     `json:"secure"`
}

// Banner 展示位尺寸
type Banner struct {
	W    int    `json:"w,omitempty"`
	H    int    `json:"h,omitempty"`
	Pos  string `json:"pos"`  // above_fold, below_fold, sidebar
	BType []string `json:"btype"`
}

// ==================== 创意格式 ====================

// CreativeType 创意格式
type CreativeType string

const (
	CreativeBanner    CreativeType = "banner"
	CreativeVideo     CreativeType = "video"
	CreativeNative    CreativeType = "native"
	CreativeHTML      CreativeType = "html"
	CreativeRewarded  CreativeType = "rewarded"
)

// Creative 创意内容
type Creative struct {
	Type        CreativeType `json:"type"`
	HTML        string       `json:"html,omitempty"`        // HTML5 创意
	VideoURL    string       `json:"video_url,omitempty"`   // 视频 URL
	NativeAds   *NativeAd    `json:"native,omitempty"`      // 原生广告
	Width       int          `json:"w"`
	Height      int          `json:"h"`
	ClickURLs   []string     `json:"clicktracking_urls"`
	ImpURLs     []string     `json:"imptracking_urls"`
	VideoSeq    int          `json:"videoseq,omitempty"` // 视频序号 (预加载/中插/后贴)
	Duration    int          `json:"duration,omitempty"` // 视频时长 (秒)
}

// NativeAd 原生广告
type NativeAd struct {
	Title     string   `json:"title"`
	Body      string   `json:"body"`
	Image     string   `json:"image"`
	CTA       string   `json:"cta"`
	Icon      string   `json:"icon"`
	Sponsored string   `json:"sponsored"`
}

// ==================== DSP 出价决策 ====================

// DisplayBidEngine 展示广告竞价引擎
type DisplayBidEngine struct {
	models   *ModelClient
	budget   *BudgetMgr
	freqCap  *FreqCap
	beta     float64
}

// BidResult 出价结果
type BidResult struct {
	ShouldBid bool
	Price     float64
	Creative  *Creative
	Rejection string
}

// Bid 执行展示广告竞价
func (e *DisplayBidEngine) Bid(req *DisplayBidRequest) (*BidResult, error) {
	imp := req.Impressions[0]

	// 1. 频控检查
	if e.freqCap.ShouldBlock(req.User.ID, imp.ID) {
		return &BidResult{Rejection: "freq_cap"}, nil
	}

	// 2. 创意匹配（根据 slot size + context）
	creative := e.matchCreative(imp, req)
	if creative == nil {
		return &BidResult{Rejection: "no_creative"}, nil
	}

	// 3. 模型预测: pCTR, pCVR
	pCTR, pCVR, err := e.models.Predict(req, imp)
	if err != nil {
		pCTR, pCVR = 0.001, 0.02
	}

	// 4. 展示广告出价 = pCTR × TargetCPM × β
	// 注意：展示广告用 CPM 出价而非 CPA
	targetCPM := 5.0
	price := pCTR * targetCPM * e.beta

	// 5. 底价保护
	if price < imp.BidFloor {
		return &BidResult{Rejection: "below_floor"}, nil
	}

	// 6. 预算检查
	if !e.budget.Check(price) {
		return &BidResult{Rejection: "budget_exhausted"}, nil
	}

	return &BidResult{
		ShouldBid: true,
		Price:     price,
		Creative:  creative,
	}, nil
}

// matchCreative 根据 slot 尺寸和内容匹配创意
func (e *DisplayBidEngine) matchCreative(imp Impression, req *DisplayBidRequest) *Creative {
	// 简单实现：匹配第一个符合条件的创意
	// 生产环境用 Redis 预加载 + 内容标签匹配
	for _, c := range e.availableCreatives {
		if c.Width == imp.Banner.W && c.Height == imp.Banner.H {
			return &c
		}
	}
	return nil
}

// ==================== 实时渲染 ====================

// RenderEngine 广告创意实时渲染
type RenderEngine struct {
	creativeDB *CreativeDB
	cache      *sync.Map // creativeID -> *Creative
}

// RenderResponse 渲染响应
type RenderResponse struct {
	Creative *Creative
	Tracking []string // 追踪像素 URL
}

// Render 渲染广告创意
func (r *RenderEngine) Render(creativeID string, req *DisplayBidRequest) (*RenderResponse, error) {
	// 1. 从缓存/DB 获取创意
	creative, ok := r.cache.Load(creativeID)
	if !ok {
		creative = r.creativeDB.Get(creativeID)
		r.cache.Store(creativeID, creative)
	}

	// 2. 根据用户上下文替换动态变量
	rendered := r.interpolate(creative.HTML, req)

	// 3. 生成追踪像素
	tracking := r.generateTracking(rendered, req)

	return &RenderResponse{
		Creative: &Creative{HTML: rendered, Type: "html"},
		Tracking: tracking,
	}, nil
}

// interpolate 替换 HTML 中的动态变量
func (r *RenderEngine) interpolate(html string, req *DisplayBidRequest) string {
	html = replaceVar(html, "{click_url}", "https://dsp.com/c?click=123")
	html = replaceVar(html, "{impression_url}", "https://dsp.com/i?imp=456")
	return html
}

func replaceVar(s, tag, val string) string {
	// 简单字符串替换，实际用模板引擎
	return s
}

func (r *RenderEngine) generateTracking(creative *Creative, req *DisplayBidRequest) []string {
	// 生成 impression tracking + click tracking URL
	return append(creative.ImpURLs, creative.ClickURLs...)
}

// ==================== 广告竞价响应 ====================

// DisplayBidResponse 展示广告竞价响应
type DisplayBidResponse struct {
	ID       string     `json:"id"`
	SeatBid  []SeatBid  `json:"seatsbid"`
}

// SeatBid 席位出价
type SeatBid struct {
	Bid  []DisplayBid `json:"bid"`
}

// DisplayBid 展示广告出价
type DisplayBid struct {
	ID     string `json:"id"`
	ImpID  string `json:"impid"`
	Price  float64 `json:"price"`
	AdM    string  `json:"adm"`    // HTML 创意
	NURL   string  `json:"nurl"`   // 中标通知
	AdID   string  `json:"adid"`
}

// ==================== 使用示例 ====================

func main() {
	engine := &DisplayBidEngine{
		models: &ModelClient{},
		beta:   0.95,
	}

	req := &DisplayBidRequest{
		ID:   "req-001",
		TMax: 100,
		Impressions: []Impression{{
			ID:       "imp-001",
			BidFloor: 2.0,
			Banner:   &Banner{W: 300, H: 250, Pos: "above_fold"},
		}},
	}

	result, _ := engine.Bid(req)
	if result.ShouldBid {
		fmt.Printf("Bid: $%.3f CPM, Creative: %s\n", result.Price, result.Creative.Type)
	}
}

type ModelClient struct{}
func (m *ModelClient) Predict(req *DisplayBidRequest, imp Impression) (float64, float64, error) { return 0.02, 0.05, nil }

type BudgetMgr struct{}
func (b *BudgetMgr) Check(float64) bool { return true }

type FreqCap struct{}
func (f *FreqCap) ShouldBlock(_, _ string) bool { return false }

type CreativeDB struct{}
func (c *CreativeDB) Get(id string) *Creative { return &Creative{Width: 300, Height: 250, HTML: "<div>Ad</div>"} }

var availableCreatives = []Creative{{Width: 300, Height: 250, HTML: "<div>300x250 Ad</div>"}}
