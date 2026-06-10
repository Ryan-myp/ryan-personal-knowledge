# TikTok Ads — 竞价策略与深度优化

> 创建日期: 2026-06-09
> 作者: Ryan

---

## 第一部分：TikTok 竞价机制深度解析

### 1.1 TikTok 竞价机制

```
TikTok 采用的是实时竞价 (RTB) + 预测模型
核心逻辑与 Meta 类似，但有自己的特色

┌────────────────────────────────────────────────────────────┐
│              TikTok 竞价流程                                │
│                                                            │
│  1. 用户刷 TikTok 短视频 Feed                               │
│       │                                                    │
│       ▼                                                    │
│  2. TikTok 召回候选广告                                     │
│     - 基于用户兴趣和行为                                    │
│     - 基于广告定向条件                                      │
│     - 基于广告创意类型                                      │
│       │                                                    │
│       ▼                                                    │
│  3. 计算 Bid Score                                         │
│     Bid Score = Bid × pCVR × Bid Adjustment                │
│                                                            │
│     关键因素:                                               │
│     ├── Bid: 出价                                          │
│     ├── pCVR: 预测转化率                                    │
│     │   └── P(conversion | user, creative)                │
│     └── Bid Adjustment: 出价调整                            │
│         └── 考虑广告类型 (In-Feed/TopView...)               │
│       │                                                    │
│       ▼                                                    │
│  4. 排序并展示                                             │
│     - Bid Score 最高的广告展示                               │
└────────────────────────────────────────────────────────────┘
```

### 1.2 TikTok 竞价策略详解

```
┌─────────────────────────────────────────────────────────┐
│                  TikTok 竞价策略                          │
│                                                         │
│  智能竞价 (Smart Bidding):                               │
│  ├── Lowest Bid: 最低成本竞价（默认）                    │
│  ├── Cost Cap: 目标每次行动费用上限                      │
│  ├── Bid Cap: 最高出价限制                               │
│  └── Target ROI: 目标投资回报率                          │
│                                                         │
│  手动竞价 (Manual Bidding):                              │
│  ├── CPC: 每次点击付费                                   │
│  └── CPM: 每千次展示付费                                 │
│                                                         │
│  特殊竞价:                                                │
│  └── OCPM: 优化千次展示付费（TikTok 特色）               │
│      ├── 系统预测转化概率                                │
│      ├── 基于预测调整实际出价                            │
│      └── 优化目标: 转化/点击/展示                        │
└─────────────────────────────────────────────────────────┘
```

### 1.3 pCVR 预测模型源码

```python
# tiktok_ads/pcvr.py
# pCVR (Predicted Conversion Rate) 预测模型

class PCVREstimator:
    """
    pCVR 预测模型
    
    pCVR = P(user converts | user, creative, placement)
    
    影响因素:
    ├── 用户特征 (兴趣、年龄、设备、地理位置)
    ├── 创意特征 (视频类型、时长、标签、音乐)
    ├── 广告组特征 (定向、出价、目标)
    └── 环境特征 (时段、设备、网络)
    """
    
    def __init__(self):
        self.model_version = 'v2.1'
    
    def predict(self, user_features: dict, 
                creative_features: dict,
                ad_group_features: dict) -> float:
        """
        预测 pCVR
        
        流程:
        1. 提取特征
        2. 输入模型
        3. 输出转化概率
        
        参数:
        ├── user_features: 用户特征
        ├── creative_features: 创意特征
        └── ad_group_features: 广告组特征
        
        返回:
        └── pCVR (0-1)
        """
        # 用户特征
        user_interest_score = user_features.get('interest_match', 0.5)
        user_engagement = user_features.get('engagement_rate', 0.1)
        
        # 创意特征
        creative_type = creative_features.get('type', 'video')
        creative_duration = creative_features.get('duration', 15)
        creative_has_music = creative_features.get('has_music', True)
        
        # 广告组特征
        bid = ad_group_features.get('bid', 1.0)
        target_type = ad_group_features.get('target', 'conversion')
        
        # 简化版预测模型
        base_pcvr = 0.02  # 基础转化率 2%
        
        # 用户兴趣匹配度调整
        pcvr = base_pcvr * (1 + user_interest_score * 2)
        
        # 创意类型调整
        type_adj = {'video': 1.0, 'image': 0.7, 'carousel': 0.8}
        pcvr *= type_adj.get(creative_type, 1.0)
        
        # 视频时长调整 (15-30s 最佳)
        if 15 <= creative_duration <= 30:
            pcvr *= 1.2
        elif creative_duration > 60:
            pcvr *= 0.8
        
        # 音乐调整
        if creative_has_music:
            pcvr *= 1.1
        
        # 出价调整 (高出价获得更多曝光，提升模型信心)
        if bid > 2.0:
            pcvr *= 1.1
        
        return max(0.0, min(1.0, pcvr))


class BidScoreCalculator:
    """
    TikTok 出价分数计算
    
    Bid Score = Bid × pCVR × Bid Adjustment
    """
    
    def __init__(self):
        self.creative_adjustments = {
            'video': 1.0,
            'image': 0.8,
            'topview': 1.5,
            'brand_takeover': 2.0,
        }
    
    def calculate_bid_score(self, bid: float, 
                            pcvr: float,
                            creative_type: str = 'video') -> float:
        """
        计算 Bid Score
        
        参数:
        ├── bid: 出价 (USD)
        ├── pcvr: 预测转化率
        └── creative_type: 创意类型
        
        返回:
        └── bid_score
        """
        adj = self.creative_adjustments.get(creative_type, 1.0)
        bid_score = bid * pcvr * adj
        
        return bid_score
```

---

## 第二部分：TikTok 竞价优化源码

### 2.1 OCPM 竞价

```python
# tiktok_ads/bidding/ocpm.py
# OCPM (Optimized CPM) 竞价

class OCPMBidder:
    """
    OCPM 竞价器
    
    TikTok 特色竞价方式
    用户选择优化目标 (转化/点击/展示)，系统自动优化
    
    流程:
    1. 用户选择优化目标
    2. 系统根据 pCVR 自动调整实际 CPC
    3. 按实际 CPC 竞价
    """
    
    def __init__(self, optimization_goal: str, bid: float):
        """
        初始化 OCPM 竞价器
        
        参数:
        ├── optimization_goal: 优化目标
        │   ├── CONVERSION: 转化
        │   ├── LINK_CLICK: 点击
        │   └── IMPRESSION: 展示
        └── bid: 出价 (CPM 价格)
        """
        self.optimization_goal = optimization_goal
        self.bid = bid  # CPM 价格
        self.actual_bid = bid
    
    def calculate_actual_cpc(self, pcvr: float) -> float:
        """
        计算实际 CPC
        
        公式:
        actual_cpc = bid × pCVR × 1000 / 1000
                   = bid × pCVR
        
        但实际会考虑:
        ├── 竞价竞争
        ├── 广告质量
        └── 预算限制
        """
        # 基础实际 CPC
        actual_cpc = self.bid * pcvr
        
        # 竞争调整
        if pcvr > 0.05:
            actual_cpc *= 1.2  # 高转化概率，提高出价
        elif pcvr < 0.01:
            actual_cpc *= 0.7  # 低转化概率，降低出价
        
        return max(0, actual_cpc)
    
    def optimize(self, impressions: int, clicks: int, 
                 conversions: int, spend: float):
        """
        优化竞价
        
        根据实际表现调整出价
        """
        actual_ctr = clicks / max(impressions, 1)
        actual_cvr = conversions / max(clicks, 1)
        
        # 如果实际表现优于预期，提高出价
        if actual_cvr > 0.05:  # 转化率 > 5%
            self.bid *= 1.1
        elif actual_cvr < 0.01:  # 转化率 < 1%
            self.bid *= 0.9
```

### 2.2 出价调整策略

```python
# tiktok_ads/bidding/adjustment.py
# 出价调整策略

class BidAdjuster:
    """
    出价调整器
    
    策略:
    ├── 时间段调整 (高峰时段提高出价)
    ├── 设备调整 (移动端 vs PC)
    ├── 地域调整 (高价值地域提高出价)
    └── 创意调整 (高表现创意提高出价)
    """
    
    def __init__(self, base_bid: float):
        self.base_bid = base_bid
    
    def adjust_for_time(self, hour: int, day_of_week: int) -> float:
        """
        时间调整
        
        高峰时段 (20:00-23:00): +20%
        工作日 (Mon-Fri): +10%
        周末: +5%
        """
        multiplier = 1.0
        
        # 高峰时段
        if 20 <= hour <= 23:
            multiplier += 0.2
        elif 12 <= hour <= 14:
            multiplier += 0.1
        
        # 工作日
        if day_of_week < 5:  # Mon-Fri
            multiplier += 0.1
        
        return self.base_bid * multiplier
    
    def adjust_for_device(self, device_type: str) -> float:
        """
        设备调整
        
        iOS: +10% (高价值用户)
        Android: 基准
        PC: -10%
        """
        adjustments = {
            'ios': 1.1,
            'android': 1.0,
            'pc': 0.9,
        }
        return self.base_bid * adjustments.get(device_type, 1.0)
    
    def adjust_for_geo(self, country: str) -> float:
        """
        地域调整
        
        高价值市场 (US/UK/AU): +20%
        中等市场 (DE/FR/JP): +10%
        其他: 基准
        """
        high_value = ['US', 'UK', 'AU', 'CA']
        mid_value = ['DE', 'FR', 'JP', 'KR']
        
        if country in high_value:
            return self.base_bid * 1.2
        elif country in mid_value:
            return self.base_bid * 1.1
        else:
            return self.base_bid
```

---

## 第三部分：TikTok 广告优化实战

### 3.1 创意优化

```python
# tiktok_ads/optimization/creative.py
# TikTok 创意优化

class TikTokCreativeOptimizer:
    """
    TikTok 创意优化器
    
    TikTok 特色:
    ├── 原生感 (Authentic) > 精致感 (Polished)
    ├── 前 3 秒决定生死
    ├── 音乐/音效至关重要
    └─ UGC 风格表现最好
    """
    
    def analyze_creative(self, creative_data: dict) -> dict:
        """
        分析创意表现
        
        关键指标:
        ├── 3s 播放率 (前 3 秒留存)
        ├── 完整播放率
        ├── 互动率 (点赞/评论/分享)
        └── 转化率
        """
        metrics = {
            'play_3s_rate': creative_data.get('play_3s_rate', 0),
            'full_play_rate': creative_data.get('full_play_rate', 0),
            'interaction_rate': creative_data.get('interaction_rate', 0),
            'conversion_rate': creative_data.get('conversion_rate', 0),
        }
        
        # 评估创意质量
        quality_score = (
            metrics['play_3s_rate'] * 0.4 +
            metrics['full_play_rate'] * 0.3 +
            metrics['interaction_rate'] * 0.2 +
            metrics['conversion_rate'] * 0.1
        )
        
        return {
            'quality_score': quality_score,
            'metrics': metrics,
            'recommendations': self._get_recommendations(metrics),
        }
    
    def _get_recommendations(self, metrics: dict) -> list:
        """获取优化建议"""
        recommendations = []
        
        if metrics['play_3s_rate'] < 0.3:
            recommendations.append(
                "前 3 秒留存率低，建议加强开头吸引力 (hook)"
            )
        if metrics['full_play_rate'] < 0.1:
            recommendations.append(
                "完整播放率低，建议缩短视频或提升内容质量"
            )
        if metrics['interaction_rate'] < 0.05:
            recommendations.append(
                "互动率低，建议添加互动元素 (提问/挑战)"
            )
        
        return recommendations
```

### 3.2 视频素材优化

```python
# tiktok_ads/optimization/video.py
# 视频素材优化

class VideoCreativeOptimizer:
    """
    TikTok 视频素材优化
    
    视频结构:
    ├── 0-3s: Hook (钩子) - 抓住注意力
    ├── 3-15s: Value (价值) - 展示产品/服务
    └── 15-30s: CTA (行动号召) - 引导转化
    """
    
    def optimize_video_structure(self, video_data: dict) -> dict:
        """
        优化视频结构
        
        参数:
        └── video_data: 视频数据
            ├── duration: 时长
            ├── has_music: 是否有音乐
            ├── has_text: 是否有文字
            ├── hook_strength: 钩子强度 (0-1)
            └── cta_type: CTA 类型
        """
        recommendations = {
            'optimal_duration': 15,  # 15-30s 最佳
            'music_recommendation': 'trending',  # 使用 trending 音乐
            'text_overlay': True,  # 需要文字覆盖
            'hook_improvement': '加强前 3 秒',
            'cta_improvement': '明确行动号召',
        }
        
        if video_data.get('duration', 15) > 30:
            recommendations['optimal_duration'] = 15
            recommendations['cut_suggestions'] = '删除冗余片段'
        
        if not video_data.get('has_music', True):
            recommendations['music_recommendation'] = 'add_trending_music'
        
        return recommendations
```

---

## 第四部分：自测

### 问题 1
TikTok OCPM 竞价中，实际 CPC 如何计算？
<details>
<summary>查看答案</summary>

- 实际 CPC = CPM × pCVR
- 系统根据预测转化率自动调整
- 高 pCVR 的广告实际 CPC 更高
</details>

### 问题 2
TikTok 广告创意的核心优化原则是什么？
<details>
<summary>查看答案</summary>

- 原生感 > 精致感
- 前 3 秒决定生死
- UGC 风格表现最好
- 音乐/音效至关重要
</details>

### 问题 3
TikTok 视频的最佳时长是多少？
<details>
<summary>查看答案</summary>

- 15-30 秒最佳
- 超过 60 秒转化率会下降
- 前 3 秒必须有 hook
</details>

---

## 第五部分：动手验证

### 5.1 创意分析

```python
from tiktok_ads.optimization.creative import TikTokCreativeOptimizer

optimizer = TikTokCreativeOptimizer()
creative_data = {
    'play_3s_rate': 0.25,
    'full_play_rate': 0.15,
    'interaction_rate': 0.08,
    'conversion_rate': 0.03,
}

result = optimizer.analyze_creative(creative_data)
print(f"创意质量分: {result['quality_score']:.2f}")
for rec in result['recommendations']:
    print(f"  建议: {rec}")
```

---

*今天花 60-90 分钟：深入理解 TikTok 竞价机制，实践优化策略*
*答不出自测题？回去重读对应章节。*
