# 分群体系设计深度实现 - 资深专家深度实现

## 一、分群模型

```
┌─────────────────────────────────────────────────────────────────────────┐
│                   RFM 用户分群模型                                         │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   维度              │ 定义                      │ 计算方式            │
│   ─────────────────┼───────────────────────┼─────────────────────│
│   R (Recency)     │ 最近一次消费              │ 距今天数            │
│   ─────────────────┼───────────────────────┼─────────────────────│
│   F (Frequency)   │ 消费频率                  │ 次数/周期           │
│   ─────────────────┼───────────────────────┼─────────────────────│
│   M (Monetary)    │ 消费金额                  │ 总金额              │
│                                                                         │
│   评分: 1-5分 (按四分位数)                                                │
│   分群: 8类核心用户群                                                   │
│                                                                         →
└─────────────────────────────────────────────────────────────────────────┘
```

## 二、RFM实现

```python
import pandas as pd
import numpy as np

class RFMSegmenter:
    def __init__(self, transactions: pd.DataFrame):
        self.transactions = transactions
    
    def calculate_rfm(self, user_id_col: str = 'user_id', 
                     date_col: str = 'transaction_date',
                     amount_col: str = 'amount') -> pd.DataFrame:
        """计算RFM值"""
        # 最近消费日期
        r = self.transactions.groupby(user_id_col)[date_col].max()
        r = (r.max() - r).dt.days
        
        # 消费频率
        f = self.transactions.groupby(user_id_col).size()
        
        # 消费金额
        m = self.transactions.groupby(user_id_col)[amount_col].sum()
        
        rfm = pd.DataFrame({'R': r, 'F': f, 'M': m})
        return rfm
    
    def score_rfm(self, rfm: pd.DataFrame) -> pd.DataFrame:
        """评分 (1-5)"""
        rfm['R_score'] = pd.qcut(rfm['R'], q=5, labels=[5,4,3,2,1], duplicates='drop')
        rfm['F_score'] = pd.qcut(rfm['F'].rank(method='first'), q=5, labels=[1,2,3,4,5])
        rfm['M_score'] = pd.qcut(rfm['M'].rank(method='first'), q=5, labels=[1,2,3,4,5])
        return rfm
    
    def segment_users(self, rfm: pd.DataFrame) -> dict:
        """分群"""
        segments = {}
        
        for idx, row in rfm.iterrows():
            key = f"{row['R_score']}{row['F_score']}{row['M_score']}"
            
            if key.startswith('5'):
                segments['高价值用户'] = segments.get('高价值用户', []) + [idx]
            elif key.startswith('4') and row['F_score'] >= 4:
                segments['潜力用户'] = segments.get('潜力用户', []) + [idx]
            elif key[1] in ['1', '2']:
                segments['流失风险'] = segments.get('流失风险', []) + [idx]
            else:
                segments['普通用户'] = segments.get('普通用户', []) + [idx]
        
        return segments
```

## 三、生命周期分群

```python
class LifecycleSegmenter:
    def __init__(self):
        self.stages = ['新用户', '活跃用户', '沉默用户', '流失用户']
    
    def classify_user(self, signup_days: int, last_active_days: int, 
                     purchase_count: int) -> str:
        """用户生命周期分类"""
        if signup_days <= 7:
            return '新用户'
        elif last_active_days <= 7 and purchase_count >= 1:
            return '活跃用户'
        elif last_active_days <= 30:
            return '沉默用户'
        else:
            return '流失用户'
    
    def calculate_metrics(self, users: list) -> dict:
        """计算分群指标"""
        metrics = {}
        for user in users:
            stage = self.classify_user(
                user['signup_days'],
                user['last_active_days'],
                user['purchase_count']
            )
            if stage not in metrics:
                metrics[stage] = {'count': 0, 'revenue': 0}
            metrics[stage]['count'] += 1
            metrics[stage]['revenue'] += user['revenue']
        return metrics
```

## 四、面试高频题

### Q1: RFM模型如何应用？

```
1. 计算R/F/M值
2. 评分 (1-5)
3. 分群
4. 针对性策略
```

### Q2: 如何识别高价值用户？

```
R高 + F高 + M高
或 综合得分排名前20%
```

## 五、自测题

1. RFM各维度含义？
2. 如何分群？
3. 生命周期阶段？

---

## 参考文档

- [RFM Model](https://www.barilliance.com/rfm-analysis/)
- [User Segmentation](https://amplitude.com/help/analytics/user-segmentation)
