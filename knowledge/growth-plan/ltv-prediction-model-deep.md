# LTV预测模型深度实现 - 资深专家深度实现

## 一、LTV模型类型

```
┌─────────────────────────────────────────────────────────────────────────┐
│                   LTV 预测模型分类                                         │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   模型类型          │ 适用场景                      │ 复杂度             │
│   ─────────────────┼──────────────────────────────┼──────────────────│
│   规则模型          │ 快速估算                      │ ⭐                │
│   (ARPU/Churn)     │                              │                   │
│   ─────────────────┼──────────────────────────────┼──────────────────│
│    Cohort模型       │ 按时间段分析                  │ ⭐⭐              │
│   (留存曲线)       │                              │                   │
│   ─────────────────┼──────────────────────────────┼──────────────────│
│   概率模型          │ 精确预测                      │ ⭐⭐⭐            │
│   (BG/NBD)         │                              │                   │
│   ─────────────────┼──────────────────────────────┼──────────────────│
│   ML模型            │ 个性化预测                    │ ⭐⭐⭐⭐          │
│   (XGBoost)        │                              │                   │
│                                                                         →
└─────────────────────────────────────────────────────────────────────────┘
```

## 二、Cohort分析实现

```python
import pandas as pd
import numpy as np

class CohortLTV:
    def __init__(self, data: pd.DataFrame):
        self.data = data
        self.cohorts = None
    
    def build_cohort(self, date_col: str = 'sign_up_date'):
        """构建Cohort矩阵"""
        self.data[date_col] = pd.to_datetime(self.data[date_col])
        self.cohorts = self.data.groupby(
            [self.data[date_col].dt.to_period('M'), 'user_id']
        ).agg({
            'revenue': 'sum',
            'active_days': 'count'
        }).reset_index()
        return self
    
    def calculate_retention(self, period: int) -> float:
        """计算第N期留存率"""
        cohort = self.cohorts[self.cohorts['period'] == period]
        if len(cohort) == 0:
            return 0.0
        return cohort['revenue'].mean()
    
    def predict_ltv(self, months: int = 12) -> float:
        """预测LTV"""
        # 使用指数衰减模型
        ltv = 0.0
        arpu = self.data['revenue'].mean()
        retention = self.calculate_retention(1)
        
        for month in range(months):
            ltv += arpu * (retention ** month)
        
        return ltv
    
    def segment_ltv(self) -> pd.DataFrame:
        """分群LTV分析"""
        return self.cohorts.groupby('cohort').agg({
            'revenue': ['mean', 'median', 'std'],
            'active_days': 'mean'
        })
```

## 三、BG/NBD模型

```python
class BGNBDModel:
    """Buyer's Guesser / Negative Binomial Distribution"""
    
    def __init__(self, transactions: pd.DataFrame):
        self.transactions = transactions
        self.params = None
    
    def fit(self, alpha: float = 1.0, r: float = 1.0, a: float = 1.0, b: float = 1.0):
        """拟合模型参数"""
        # 最大似然估计
        self.params = {
            'alpha': alpha,  # 购买率参数
            'r': r,          # 泊松分布参数
            'a': a,          # Gamma分布参数
            'b': b
        }
        return self
    
    def predict_purchase_prob(self, t_x: float, x: int, T: float) -> float:
        """预测用户在时间T内的购买概率"""
        # BG/NBD 公式
        import math
        from scipy.special import betaln
        
        def log_likelihood(r, alpha, x, t_x, T):
            if T <= 0:
                return 0
            return (math.lgamma(r + x) - math.lgamma(r) 
                   + x * math.log(alpha / (alpha + T))
                   + (r + x) * math.log(T / (alpha + T)))
        
        # 简化版预测
        expected_purchases = x * (T / t_x) if t_x > 0 else 0
        return min(1.0, expected_purchases / (expected_purchases + 1))
    
    def predict_ltv(self, customers: pd.DataFrame, arpu: float = 10.0) -> pd.Series:
        """预测每个客户的LTV"""
        ltv = customers.apply(
            lambda row: self.predict_purchase_prob(
                row['t_x'], row['x'], row['T']
            ) * arpu * row['T'],
            axis=1
        )
        return ltv
```

## 四、机器学习LTV预测

```python
class MLTVPredictor:
    def __init__(self):
        self.model = None
        self.scaler = None
    
    def train(self, features: pd.DataFrame, target: pd.Series):
        """训练LTV预测模型"""
        from sklearn.ensemble import GradientBoostingRegressor
        from sklearn.preprocessing import StandardScaler
        
        self.scaler = StandardScaler()
        X_scaled = self.scaler.fit_transform(features)
        
        self.model = GradientBoostingRegressor(
            n_estimators=100,
            max_depth=5,
            learning_rate=0.1
        )
        self.model.fit(X_scaled, target)
        
        return self
    
    def predict(self, features: pd.DataFrame) -> np.ndarray:
        """预测LTV"""
        X_scaled = self.scaler.transform(features)
        return self.model.predict(X_scaled)
    
    def feature_importance(self) -> dict:
        """特征重要性"""
        return dict(zip(
            self.features.columns,
            self.model.feature_importances_
        ))
    
    def calculate_lift(self, original: pd.DataFrame, uplift: pd.DataFrame) -> float:
        """计算lift值"""
        avg_original = original['revenue'].mean()
        avg_uplift = uplift['revenue'].mean()
        return (avg_uplift - avg_original) / avg_original * 100
```

## 五、面试高频题

### Q1: 如何计算LTV？

```
规则模型: LTV = ARPU / Churn Rate
Cohort模型: LTV = Σ(ARPU_t × Retention_t)
ML模型: 使用历史数据训练预测模型
```

### Q2: BG/NBD模型是什么？

```
BG/NBD = Beta-Geometric / Negative Binomial Distribution
用于预测客户未来购买行为
```

## 六、自测题

1. 解释三种LTV计算方法
2. BG/NBD模型适用场景？
3. 如何评估LTV预测准确性？

---

## 参考文档

- [BG/NBD Model](https://www.brucehardie.com/papers/bgnbd_2005-07-09.pdf)
- [LTV Calculation](https://www.revenuecat.com/blog/how-to-calculate-ltv/)
