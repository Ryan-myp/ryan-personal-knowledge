# 留存引擎设计深度实现 - 资深专家深度实现

## 一、留存模型

```
┌─────────────────────────────────────────────────────────────────────────┐
│                   用户留存曲线类型                                         │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   曲线类型          │ 特点                      │ 产品类型            │
│   ─────────────────┼─────────────────────────┼─────────────────────│
│   渐近留存          │ 趋近稳定值                │ 社交/工具类         │
│   (Asymptotic)     │ 20-30%长期留存            │                     │
│   ─────────────────┼─────────────────────────┼─────────────────────│
│   自然衰减          │ 持续下降                  │ 游戏/内容类         │
│   (Natural Decay)  │ 无稳定值                  │                     │
│   ─────────────────┼─────────────────────────┼─────────────────────│
│   波动留存          │ 周期性波动                │ 电商/季节性         │
│   (Seasonal)       │ 受活动影响                │                     │
│   ─────────────────┼─────────────────────────┼─────────────────────│
│   网络效应留存      │ 随时间增长                │ 平台/社区           │
│   (Network Effect) │ 用户越多越留得住          │                     │
│                                                                         →
└─────────────────────────────────────────────────────────────────────────┘
```

## 二、留存预测模型

```python
import numpy as np
from scipy.optimize import curve_fit

class RetentionPredictor:
    def __init__(self):
        self.model_params = None
    
    def exponential_decay(self, t: np.ndarray, a: float, b: float) -> np.ndarray:
        """指数衰减模型"""
        return a * np.exp(-b * t) + 0.5
    
    def fit(self, days: np.ndarray, retention_rates: np.ndarray):
        """拟合留存曲线"""
        self.model_params, _ = curve_fit(
            self.exponential_decay,
            days,
            retention_rates,
            p0=[1.0, 0.1]
        )
        return self
    
    def predict(self, day: int) -> float:
        """预测留存率"""
        if self.model_params is None:
            return 0.5
        a, b = self.model_params
        return float(self.exponential_decay(day, a, b))
    
    def calculate_dau_mau(self, daily_retention: list) -> float:
        """计算DAU/MAU"""
        dau = sum(1 for r in daily_retention if r > 0.5)
        mau = len(daily_retention)
        return dau / mau if mau > 0 else 0
    
    def segment_retention(self, users: list, segments: list) -> dict:
        """分群留存"""
        result = {}
        for seg in set(segments):
            seg_users = [u for u, s in zip(users, segments) if s == seg]
            result[seg] = self.calculate_average_retention(seg_users)
        return result
```

## 三、召回系统

```python
class ReengagementSystem:
    def __init__(self):
        self.channels = ['push', 'sms', 'email', 'in_app']
    
    def predict_churn(self, user_features: dict) -> float:
        """预测流失概率"""
        risk_score = 0.0
        
        # 行为特征
        if user_features.get('days_since_last_login', 0) > 7:
            risk_score += 0.3
        if user_features.get('purchase_count', 0) == 0:
            risk_score += 0.2
        if user_features.get('support_tickets', 0) > 2:
            risk_score += 0.2
        
        # 历史特征
        if user_features.get('past_churned', False):
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
            'email': {'type': '专属折扣', 'value': '30%'},
            'in_app': {'type': '弹窗优惠', 'value': '首单免邮'}
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
                
                if self.send_reengagement(user, channel, offer):
                    results['sent'] += 1
                    if user.get('activated_again', False):
                        results['reactivated'] += 1
        
        return results
```

## 四、面试高频题

### Q1: 如何计算DAU/MAU？

```
DAU/MAU = 日活跃用户数 / 月活跃用户数
健康值: > 20%
```

### Q2: 召回策略有哪些？

```
1. Push通知
2. 短信
3. 邮件
4. App内消息
5. 电话召回
```

## 五、自测题

1. 如何预测用户流失？
2. 召回渠道如何选择？
3. 如何评估召回效果？

---

## 参考文档

- [Retention Analysis](https://amplitude.com/help/how-to/calculate-retention-rate)
- [Churn Prediction](https://www.kissmetrics.io/blog/how-to-calculate-churn-rate/)
