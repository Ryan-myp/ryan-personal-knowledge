# LTV计算实战深度实现 - 资深专家深度实现

## 一、LTV计算方法对比

```
┌─────────────────────────────────────────────────────────────────────────┐
│                   LTV 计算方法对比                                         │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   方法              │ 公式                      │ 优点              │ 缺点          │
│   ─────────────────┼───────────────────────┼─────────────────┼─────────────│
│   简单公式法        │ ARPU / Churn Rate      │ 简单易用          │ 假设恒定      │
│   (Simple)         │                        │                   │             │
│   ─────────────────┼───────────────────────┼─────────────────┼─────────────│
│   Cohort分析法      │ Σ(ARPU_t × Retention)  │ 精确              │ 数据需求高    │
│   (Cohort)         │                        │                   │             │
│   ─────────────────┼───────────────────────┼─────────────────┼─────────────│
│   概率模型法        │ P(购买) × ARPU         │ 考虑不确定性      │ 复杂          │
│   (BG/NBD)         │                        │                   │             │
│   ─────────────────┼───────────────────────┼─────────────────┼─────────────│
│   机器学习法        │ 预测模型               │ 个性化            │ 需要大量数据  │
│   (ML)             │                        │                   │             │
│                                                                         →
└─────────────────────────────────────────────────────────────────────────┘
```

## 二、Cohort LTV计算

```python
import pandas as pd
import numpy as np

class CohortLTV:
    def __init__(self, transactions: pd.DataFrame):
        self.transactions = transactions
    
    def build_cohort(self, date_col: str = 'transaction_date'):
        """构建Cohort矩阵"""
        self.transactions[date_col] = pd.to_datetime(self.transactions[date_col])
        self.transactions['cohort'] = self.transactions[date_col].dt.to_period('M')
        
        cohort_matrix = self.transactions.groupby(
            ['cohort', self.transactions[date_col].dt.month]
        )['revenue'].mean().unstack()
        
        return cohort_matrix
    
    def calculate_retention_curve(self, cohort: pd.Series) -> np.ndarray:
        """计算留存曲线"""
        retention = np.array(cohort)
        
        # 指数衰减拟合
        from scipy.optimize import curve_fit
        def exp_decay(x, a, b):
            return a * np.exp(-b * x)
        
        x = np.arange(len(retention))
        try:
            params, _ = curve_fit(exp_decay, x, retention, p0=[1.0, 0.1])
            return exp_decay(x, *params)
        except:
            return retention
    
    def calculate_ltv(self, arpu: float, retention_curve: np.ndarray, months: int = 12) -> float:
        """计算LTV"""
        ltv = 0
        for t in range(min(months, len(retention_curve))):
            ltv += arpu * retention_curve[t]
        return ltv
    
    def segment_ltv(self) -> pd.DataFrame:
        """分群LTV分析"""
        results = {}
        
        for cohort in self.transactions['cohort'].unique():
            cohort_data = self.transactions[self.transactions['cohort'] == cohort]
            arpu = cohort_data['revenue'].mean()
            retention = self.calculate_retention_curve(
                cohort_data.groupby(cohort_data.index // 30).size()
            )
            ltv = self.calculate_ltv(arpu, retention)
            results[cohort] = {'arpu': arpu, 'ltv': ltv}
        
        return pd.DataFrame(results).T
```

## 三、机器学习LTV预测

```python
class MLTVPredictor:
    def __init__(self):
        self.model = None
    
    def prepare_features(self, users: pd.DataFrame) -> pd.DataFrame:
        """准备特征"""
        features = pd.DataFrame()
        
        # 行为特征
        features['signup_days'] = (pd.Timestamp.now() - users['signup_date']).dt.days
        features['total_purchases'] = users['purchase_count']
        features['avg_order_value'] = users['total_spent'] / users['purchase_count']
        features['last_purchase_days'] = (pd.Timestamp.now() - users['last_purchase_date']).dt.days
        
        # 行为模式
        features['purchase_frequency'] = users['purchase_count'] / features['signup_days']
        features['recency_score'] = 1 / (1 + features['last_purchase_days'])
        
        return features
    
    def train_model(self, features: pd.DataFrame, target: pd.Series):
        """训练模型"""
        from sklearn.ensemble import GradientBoostingRegressor
        
        self.model = GradientBoostingRegressor(
            n_estimators=100,
            max_depth=5,
            learning_rate=0.1,
            random_state=42
        )
        self.model.fit(features, target)
        
        return self
    
    def predict(self, features: pd.DataFrame) -> np.ndarray:
        """预测LTV"""
        return self.model.predict(features)
    
    def feature_importance(self) -> dict:
        """特征重要性"""
        importance = dict(zip(
            self.feature_cols,
            self.model.feature_importances_
        ))
        return dict(sorted(importance.items(), key=lambda x: x[1], reverse=True))
```

## 四、LTV应用

```python
class LTVApplication:
    def __init__(self, ltv: float, cac: float):
        self.ltv = ltv
        self.cac = cac
    
    def calculate_roi(self) -> float:
        """计算ROI"""
        return (self.ltv - self.cac) / self.cac * 100
    
    def is_profitable(self, threshold: float = 3.0) -> bool:
        """是否盈利"""
        return self.ltv / self.cac > threshold
    
    def max_cac(self, min_roas: float = 3.0) -> float:
        """最大可接受CAC"""
        return self.ltv / min_roas
    
    def optimize_acquisition(self) -> dict:
        """优化获客"""
        return {
            'current_ltv_cac': self.ltv / self.cac,
            'max_cac': self.max_cac(),
            'recommendation': self.get_recommendation()
        }
    
    def get_recommendation(self) -> str:
        """建议"""
        ratio = self.ltv / self.cac
        if ratio >= 5:
            return '加大投放，当前LTV:CAC健康'
        elif ratio >= 3:
            return '保持当前策略'
        elif ratio >= 1:
            return '优化获客成本或提升LTV'
        else:
            return '停止投放，单位经济学不健康'
```

## 五、面试高频题

### Q1: LTV如何计算？

```
简单公式: LTV = ARPU / Churn Rate
精确计算: LTV = Σ(ARPU_t × Retention_t)
```

### Q2: LTV:CAC健康值是多少？

```
一般要求 LTV:CAC ≥ 3:1
即LTV是CAC的3倍以上
```

## 六、自测题

1. 解释Cohort LTV计算
2. 机器学习LTV的优势？
3. 如何优化LTV？

---

## 参考文档

- [LTV Calculation](https://www.revenuecat.com/blog/how-to-calculate-ltv/)
- [Cohort Analysis](https://amplitude.com/help/how-to/calculate-retention-rate)
