# 用户留存引擎设计 - 资深专家深度实现

## 一、留存模型

```
┌─────────────────────────────────────────────────────────────────────────┐
│                   用户留存曲线类型                                         │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   类型              │ 曲线特征           │ 适用产品                    │
│   ─────────────────┼───────────────────┼─────────────────────────────│
│   渐近留存          │ 趋近稳定值         │ 社交/工具类                 │
│   (Asymptotic)     │                    │                             │
│   ─────────────────┼───────────────────┼─────────────────────────────│
│   自然衰减          │ 持续下降           │ 游戏/内容类                 │
│   (Natural Decay)  │                    │                             │
│   ─────────────────┼───────────────────┼─────────────────────────────│
│   波动留存          │ 周期性波动         │ 电商/季节性产品             │
│   (Seasonal)       │                    │                             │
│   ─────────────────┼───────────────────┼─────────────────────────────│
│   网络效应留存      │ 随时间增长         │ 平台/社区类                 │
│   (Network Effect) │                    │                             │
│                                                                         →
└─────────────────────────────────────────────────────────────────────────┘
```

## 二、留存预测模型

```python
import numpy as np
from scipy.optimize import curve_fit

class RetentionPredictor:
    def __init__(self):
        self.params = None
    
    def exponential_decay(self, t: np.ndarray, a: float, b: float) -> np.ndarray:
        """指数衰减模型"""
        return a * np.exp(-b * t) + 0.5  # 最低保留50%
    
    def fit(self, days: np.ndarray, retention_rates: np.ndarray):
        """拟合留存曲线"""
        self.params, _ = curve_fit(
            self.exponential_decay,
            days,
            retention_rates,
            p0=[1.0, 0.1]
        )
        return self
    
    def predict(self, day: int) -> float:
        """预测某日留存率"""
        if self.params is None:
            return 0.5
        a, b = self.params
        return self.exponential_decay(day, a, b)
    
    def calculate_dau_mau(self, daily_retention: list) -> float:
        """计算DAU/MAU比值"""
        dau = sum(1 for r in daily_retention if r > 0.5)
        mau = len(daily_retention)
        return dau / mau if mau > 0 else 0
    
    def segment_retention(self, users: list, segments: list) -> dict:
        """分群留存分析"""
        result = {}
        for seg in segments:
            seg_users = [u for u, s in zip(users, segments) if s == seg]
            result[seg] = self.calculate_average_retention(seg_users)
        return result
```

## 三、留存策略

```python
class RetentionStrategy:
    def __init__(self):
        self.push_config = {
            'frequency': 'daily',
            'time': '20:00',
            'personalized': True
        }
        self.email_config = {
            'welcome_series': True,
            're_engagement': True
        }
    
    def design_onboarding(self, user_type: str) -> dict:
        """设计新手引导"""
        strategies = {
            'free': {
                'steps': 3,
                'duration': '5分钟',
                'incentive': '首单优惠'
            },
            'paid': {
                'steps': 5,
                'duration': '10分钟',
                'incentive': 'VIP服务'
            }
        }
        return strategies.get(user_type, strategies['free'])
    
    def create_push_campaign(self) -> dict:
        """创建推送活动"""
        return {
            'segment': '沉睡用户',
            'message': '我们想你了',
            'offer': '专属优惠',
            'timing': '活跃时段',
            'frequency_cap': '1次/天'
        }
    
    def measure_impact(self, before: float, after: float) -> dict:
        """衡量留存影响"""
        return {
            'absolute_lift': after - before,
            'relative_lift': (after - before) / before * 100,
            'statistical_significance': self.p_value_test(before, after)
        }
    
    def p_value_test(self, group_a: list, group_b: list) -> float:
        """显著性检验"""
        from scipy import stats
        _, p_value = stats.ttest_ind(group_a, group_b)
        return p_value
```

## 四、召回系统

```python
class ReengagementSystem:
    def __init__(self):
        self.channels = ['push', 'sms', 'email', 'in_app']
    
    def predict_churn(self, user_features: dict) -> float:
        """预测流失概率"""
        # 简化版模型
        risk_score = 0.0
        
        if user_features.get('days_since_last_login', 0) > 7:
            risk_score += 0.3
        if user_features.get('purchase_count', 0) == 0:
            risk_score += 0.2
        if user_features.get('support_tickets', 0) > 2:
            risk_score += 0.2
        
        return min(1.0, risk_score)
    
    def select_channel(self, user: dict, risk: float) -> str:
        """选择召回渠道"""
        if risk > 0.7:
            return 'sms'  # 高流失风险用短信
        elif risk > 0.5:
            return 'push'  # 中风险用推送
        else:
            return 'email'  # 低风险用邮件
    
    def create_offer(self, user: dict, channel: str) -> dict:
        """创建召回优惠"""
        offers = {
            'push': {'type': '优惠券', 'value': '10%'},
            'sms': {'type': '现金券', 'value': '¥20'},
            'email': {'type': '专属折扣', 'value': '30%'}
        }
        return offers.get(channel, offers['push'])
    
    def run_campaign(self, users: list) -> dict:
        """运行召回活动"""
        results = {'sent': 0, 'reactivated': 0}
        
        for user in users:
            risk = self.predict_churn(user)
            if risk > 0.5:
                channel = self.select_channel(user, risk)
                offer = self.create_offer(user, channel)
                
                # 发送召回
                if self.send_reengagement(user, channel, offer):
                    results['sent'] += 1
                    if user['activated_again']:
                        results['reactivated'] += 1
        
        return results
```

## 五、面试高频题

### Q1: 如何计算DAU/MAU？

```
DAU/MAU = 日活跃用户数 / 月活跃用户数
健康值: > 20%
```

### Q2: 什么是Churn Rate？

```
Churn Rate = 流失用户数 / 期初用户数
```

## 六、自测题

1. 如何预测用户流失？
2. 召回系统如何设计？
3. 如何评估召回效果？

---

## 参考文档

- [Retention Analysis](https://amplitude.com/help/how-to/calculate-retention-rate)
- [Churn Prediction](https://www.kissmetrics.io/blog/how-to-calculate-churn-rate/)
