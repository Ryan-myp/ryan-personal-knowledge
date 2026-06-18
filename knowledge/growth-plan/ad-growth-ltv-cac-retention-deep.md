# 广告增长深度：LTV预测/用户获取/留存/裂变

> 从商业视角，深度解析广告系统的用户增长策略

---

## 第一部分：LTV 预测模型

### 为什么需要 LTV 预测？

```
LTV（用户终身价值）在广告系统中的角色：
1. 出价决策：LTV > CAC 才能盈利
2. 预算分配：高 LTV 用户群分配更多预算
3. 用户分层：按 LTV 分层，差异化运营
4. 投资回报：评估营销活动的 ROI

LTV 计算公式：
LTV = Σ (每月 ARPU × 留存率^月数 × 折扣因子^月数)

简化版（稳定 ARPU 和留存率）：
LTV = ARPU × 毛利率 × LTV_multiplier
LTV_multiplier = 1 / (1 - retention_rate)
```

### LTV 预测模型

```python
# LTV 预测模型（基于生存分析）
import pandas as pd
import numpy as np
from lifelines import CoxPHFitter, WeibullAFTFitter

class LTVPredictor:
    def __init__(self):
        self.cox_model = CoxPHFitter()
        self.weibull_model = WeibullAFTFitter()
    
    def prepare_data(self, user_data):
        """准备生存分析数据"""
        # 特征：
        # - age: 用户注册天数
        # - total_spent: 累计花费
        # - num_sessions: 会话次数
        # - avg_session_duration: 平均会话时长
        # - churned: 是否流失（1=流失，0=删失）
        # - tenure: 用户生命周期
        
        data = user_data.copy()
        data['tenure'] = (pd.Timestamp.now() - data['registration_date']).dt.days
        data['churned'] = data['last_active_date'].isna().astype(int)
        data['tenure_days'] = (
            data['last_active_date'].fillna(pd.Timestamp.now()) - 
            data['registration_date']
        ).dt.days
        
        return data[['age', 'total_spent', 'num_sessions', 
                     'avg_session_duration', 'tenure_days', 'churned']]
    
    def fit_survival_model(self, data):
        """拟合生存分析模型"""
        # Cox 比例风险模型
        self.cox_model.fit(data, 
                          duration_col='tenure_days', 
                          event_col='churned')
        
        # Weibull AFT 模型
        self.weibull_model.fit(data,
                              duration_col='tenure_days',
                              event_col='churned')
        
        return self
    
    def predict_ltv(self, user_features, monthly_arpu=5.0, 
                   discount_rate=0.01, months=24):
        """预测用户 LTV"""
        # 1. 预测生存概率
        survival_probs = self.weibull_model.predict_survival_function(
            user_features
        )
        
        # 2. 计算 LTV
        ltv = 0
        for t in range(1, months + 1):
            survival_prob = survival_probs(t)
            ltv += monthly_arpu * survival_prob * (1 + discount_rate) ** (-t)
        
        return ltv
    
    def segment_users(self, users, n_segments=4):
        """用户分层"""
        ltv_scores = []
        for _, user in users.iterrows():
            ltv = self.predict_ltv(
                user[['age', 'total_spent', 'num_sessions', 
                      'avg_session_duration']],
                monthly_arpu=user.get('monthly_arpu', 5.0)
            )
            ltv_scores.append(ltv)
        
        users['predicted_ltv'] = ltv_scores
        users['segment'] = pd.qcut(users['predicted_ltv'], 
                                   n_segments, 
                                   labels=['low', 'mid-low', 'mid-high', 'high'])
        
        return users
```

---

## 第二部分：用户获取策略

### CAC 优化

```
CAC（获客成本）优化策略：
┌─────────────────────────────────────────────────────────────────────┐
│ 渠道分析：                                                          │
│ • 搜索广告（Google/Bing）：高意图，高 CAC，高 LTV                     │
│ • 展示广告（Facebook/Instagram）：中意图，中 CAC，中 LTV              │
│ • 社交广告（TikTok/Snapchat）：低意图，低 CAC，低 LTV                 │
│ • 原生广告（Taboola/Outbrain）：低意图，低 CAC，低 LTV                │
│ • 联盟营销：低意图，极低 CAC，极低 LTV                               │
│                                                                     │
│ 优化策略：                                                          │
│ 1. 渠道组合：平衡高 CAC 高 LTV 和低 CAC 低 LTV 渠道                   │
│ 2. 出价策略：基于 LTV 出价，而不是固定 CPC                           │
│ 3. 定向优化：高 LTV 人群提高出价，低 LTV 人群降低出价                  │
│ 4. 创意优化：高 CTR 创意降低 CAC                                    │
│ 5. 落地页优化：高转化率落地页降低 CAC                                │
└─────────────────────────────────────────────────────────────────────┘
```

### 基于 LTV 的出价策略

```go
package bidding

import (
    "math"
)

// LTBBidStrategy LTV 导向的出价策略
type LTBBidStrategy struct {
    ltvPredictor *LTVPredictor
    targetROAS   float64
    maxCPA       float64
}

func (s *LTBBidStrategy) CalculateBid(user *User, inventory *Inventory) float64 {
    // 1. 预测用户 LTV
    ltv := s.ltvPredictor.Predict(user)
    
    // 2. 预测 CTR 和 CVR
    ctr := s.predictCTR(user, inventory)
    cvr := s.predictCVR(user, inventory)
    
    // 3. 基于 LTV 计算目标 CPA
    // CPA 应该是 LTV 的 1/targetROAS
    targetCPA := ltv / s.targetROAS
    if targetCPA > s.maxCPA {
        targetCPA = s.maxCPA
    }
    
    // 4. 计算出价
    // bid = CVR * 目标 CPA * (1 + 竞争系数)
    competitionFactor := s.calculateCompetitionFactor(inventory)
    bid := cvr * targetCPA * (1 + competitionFactor)
    
    // 5. 基于 CTR 调整
    bid *= (1 + (ctr - 0.02) * 10) // CTR 每偏离 2% 调整 10%
    
    return math.Max(0.01, bid)
}

func (s *LTBBidStrategy) calculateCompetitionFactor(inventory *Inventory) float64 {
    // 基于库存的竞争程度
    if inventory.Competition == "high" {
        return 0.3
    } else if inventory.Competition == "medium" {
        return 0.1
    }
    return 0.0
}
```

---

## 第三部分：用户留存策略

### 留存分析

```
留存分析框架：
┌─────────────────────────────────────────────────────────────────────┐
│ 留存曲线：                                                          │
│ Day 1:  80%  (首日留存)                                              │
│ Day 7:  40%  (周留存)                                                │
│ Day 30: 15%  (月留存)                                                │
│ Day 90: 5%   (季度留存)                                              │
│                                                                     │
│ 留存优化策略：                                                       │
│ 1. Onboarding：优化新手引导，提高首日留存                             │
│ 2. Push Notification：个性化推送，提高次日留存                        │
│ 3. Email Marketing：定期邮件，提高周留存                              │
│ 4. Loyalty Program：积分/会员，提高月留存                             │
│ 5. Community：社群运营，提高长期留存                                  │
└─────────────────────────────────────────────────────────────────────┘
```

### 留存模型实现

```python
# 留存率预测模型
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
import pandas as pd

class RetentionPredictor:
    def __init__(self):
        self.model = RandomForestClassifier(n_estimators=100)
    
    def train(self, user_data):
        """训练留存预测模型"""
        # 特征：
        # - first_session_duration: 首次会话时长
        # - first_actions_count: 首次操作次数
        # - onboarding_completed: 是否完成引导
        # - referral_source: 来源渠道
        # - device_type: 设备类型
        
        features = ['first_session_duration', 'first_actions_count',
                    'onboarding_completed', 'referral_source_encoded',
                    'device_type_encoded']
        
        X = user_data[features]
        y = user_data['retained_7d']  # 7 天留存标签
        
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42
        )
        
        self.model.fit(X_train, y_train)
        
        # 评估
        accuracy = self.model.score(X_test, y_test)
        print(f"Retention prediction accuracy: {accuracy:.2%}")
        
        # 特征重要性
        importance = pd.DataFrame({
            'feature': features,
            'importance': self.model.feature_importances_
        }).sort_values('importance', ascending=False)
        
        print("\nFeature Importance:")
        print(importance)
        
        return self
    
    def predict_retention(self, user_features):
        """预测用户留存概率"""
        return self.model.predict_proba(user_features)[:, 1]
    
    def identify_risky_users(self, user_data, threshold=0.3):
        """识别高风险流失用户"""
        user_data['retention_prob'] = self.predict_retention(
            user_data[['first_session_duration', 'first_actions_count',
                       'onboarding_completed', 'referral_source_encoded',
                       'device_type_encoded']]
        )
        
        risky_users = user_data[user_data['retention_prob'] < threshold]
        return risky_users
```

---

## 第四部分：裂变增长

### 裂变模型

```
裂变增长模型（Viral Loop）：
┌─────────────────────────────────────────────────────────────────────┐
│ 裂变系数 K = i × c × r                                               │
│ i: 邀请人数（每个用户邀请多少人）                                      │
│ c: 邀请转化率（被邀请人中有多少人注册）                                 │
│ r: 激活率（注册后有多少人完成关键行为）                                 │
│                                                                     │
│ K > 1: 病毒式增长                                                    │
│ K = 1: 稳定增长                                                      │
│ K < 1: 增长放缓                                                      │
│                                                                     │
│ 裂变策略：                                                          │
│ 1. 邀请奖励：邀请好友双方都得奖励                                      │
│ 2. 社交分享：一键分享到社交媒体                                        │
│ 3.  referral program：推荐返利                                        │
│ 4. UGC：用户生成内容吸引新用户                                        │
│ 5. 限时活动：制造紧迫感，促进分享                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### 裂变效果分析

```python
# 裂变效果分析
class ViralGrowthAnalyzer:
    def __init__(self):
        self.invite_data = []  # 邀请数据
    
    def add_invite_record(self, inviter_id, invitee_id, 
                          converted, activated):
        self.invite_data.append({
            'inviter_id': inviter_id,
            'invitee_id': invitee_id,
            'converted': converted,
            'activated': activated
        })
    
    def calculate_k_factor(self):
        """计算裂变系数 K"""
        total_invites = len(self.invite_data)
        if total_invites == 0:
            return 0
        
        total_converted = sum(1 for d in self.invite_data if d['converted'])
        total_activated = sum(1 for d in self.invite_data if d['activated'])
        
        i = total_invites / total_invites  # 平均邀请人数（简化）
        c = total_converted / total_invites  # 转化率
        r = total_activated / total_converted if total_converted > 0 else 0
        
        k = i * c * r
        return k
    
    def analyze_inviter_segments(self):
        """分析不同邀请者的效果"""
        segments = {}
        for record in self.invite_data:
            inviter = record['inviter_id']
            if inviter not in segments:
                segments[inviter] = {'invites': 0, 'converted': 0, 'activated': 0}
            
            segments[inviter]['invites'] += 1
            if record['converted']:
                segments[inviter]['converted'] += 1
            if record['activated']:
                segments[inviter]['activated'] += 1
        
        # 计算每个 segment 的 K 因子
        for seg_id, data in segments.items():
            c_rate = data['converted'] / data['invites'] if data['invites'] > 0 else 0
            r_rate = data['activated'] / data['converted'] if data['converted'] > 0 else 0
            data['k_factor'] = c_rate * r_rate
        
        return segments
    
    def recommend_optimization(self):
        """推荐优化策略"""
        k = self.calculate_k_factor()
        
        if k > 1:
            return "Viral growth achieved! Scale up the program."
        elif k > 0.5:
            return "Moderate growth. Focus on improving conversion rate."
        else:
            return "Low growth. Need to significantly improve invitation incentive."
```

---

## 第五部分：自测题

### Q1: LTV 和 CAC 的关系？

**A**: LTV > CAC 才能盈利。理想比例 LTV:CAC = 3:1。LTV < CAC 说明获客成本过高，需要优化渠道或提高 ARPU。

### Q2: 如何提高用户留存？

**A**: 优化 Onboarding、个性化推送、Email Marketing、Loyalty Program、Community 运营。关键是找到影响留存的关键行为（Aha Moment）。

### Q3: 裂变系数 K 怎么算？

**A**: K = i × c × r（邀请人数 × 转化率 × 激活率）。K > 1 是病毒式增长，K < 1 需要优化邀请激励或转化率。

---

## 第六部分：生产实践

### 1. LTV 预测

```
LTV 预测要点：
• 使用生存分析模型（Cox/Weibull）
• 定期重新训练模型
• 按用户分层，差异化运营
• 结合业务规则调整预测结果
```

### 2. CAC 优化

```
CAC 优化要点：
• 多渠道组合，平衡 CAC 和 LTV
• 基于 LTV 出价，动态调整
• 高价值人群提高出价，低价值人群降低
• 定期分析渠道 ROI，淘汰低效渠道
```

### 3. 裂变增长

```
裂变增长要点：
• 设计双向奖励（邀请人和被邀请人都得利）
• 降低分享门槛（一键分享）
• 制造紧迫感（限时活动）
• 监控 K 因子，及时调整策略
```
