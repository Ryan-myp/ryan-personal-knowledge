# 用户分群体系深度实现 - 资深专家深度实现

## 一、分群策略

```
┌─────────────────────────────────────────────────────────────────────────┐
│                   用户分群维度                                            │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   分群类型        │ 维度                    │ 应用场景                 │
│   ───────────────┼───────────────────────┼─────────────────────────│
│   RFM模型         │ 最近消费/频率/金额    │ 价值分层                 │
│   ───────────────┼───────────────────────┼─────────────────────────│
│   行为分群        │ 使用路径/功能偏好     │ 个性化推荐               │
│   ───────────────┼───────────────────────┼─────────────────────────│
│   生命周期分群    │ 新客/活跃/沉睡/流失   │ 召回策略                 │
│   ───────────────┼───────────────────────┼─────────────────────────│
│   渠道分群        │ 来源渠道              │ 渠道评估                 │
│   ───────────────┼───────────────────────┼─────────────────────────│
│   设备分群        │ iOS/Android/Web       │ 体验优化                 │
│                                                                         →
└─────────────────────────────────────────────────────────────────────────┘
```

## 二、RFM模型实现

```python
import pandas as pd
import numpy as np

class RFMAnalyzer:
    def __init__(self, transactions: pd.DataFrame):
        self.transactions = transactions
        self.rfm_scores = None
    
    def calculate_rfm(self) -> pd.DataFrame:
        """计算RFM值"""
        rfm = self.transactions.groupby('user_id').agg({
            'last_order_date': 'max',  # Recency
            'order_count': 'count',     # Frequency
            'total_amount': 'sum'       # Monetary
        }).reset_index()
        
        rfm.columns = ['user_id', 'R', 'F', 'M']
        
        # 计算R值 (天数越小越好)
        rfm['R'] = (rfm['R'] - rfm['R'].min()).dt.days
        rfm['R'] = rfm['R'].max() - rfm['R'] + 1  # 反转使越大越好
        
        return rfm
    
    def score_rfm(self, rfm: pd.DataFrame, n_bins: int = 5) -> pd.DataFrame:
        """RFM评分"""
        for col in ['R', 'F', 'M']:
            rfm[f'{col}_score'] = pd.qcut(rfm[col], q=n_bins, labels=range(1, n_bins+1), duplicates='drop')
        
        return rfm
    
    def segment_users(self, rfm: pd.DataFrame) -> dict:
        """用户分群"""
        segments = {}
        
        for idx, row in rfm.iterrows():
            r_score = int(row['R_score'])
            f_score = int(row['F_score'])
            m_score = int(row['M_score'])
            
            # 分群逻辑
            if r_score >= 4 and f_score >= 4 and m_score >= 4:
                segment = '重要价值用户'
            elif r_score >= 4 and f_score < 4:
                segment = '重要发展用户'
            elif r_score < 4 and f_score >= 4:
                segment = '重要保持用户'
            elif r_score < 4 and f_score < 4:
                segment = '重要挽留用户'
            elif r_score >= 4:
                segment = '新价值用户'
            else:
                segment = '一般用户'
            
            if segment not in segments:
                segments[segment] = []
            segments[segment].append(row['user_id'])
        
        return segments
    
    def get_segment_size(self, segments: dict) -> dict:
        """各分群规模"""
        return {seg: len(users) for seg, users in segments.items()}
```

## 三、行为分群

```python
class BehavioralSegmentation:
    def __init__(self, user_events: pd.DataFrame):
        self.events = user_events
    
    def extract_features(self) -> pd.DataFrame:
        """提取行为特征"""
        features = self.events.groupby('user_id').agg({
            'event_type': 'count',           # 总事件数
            'session_duration': 'mean',      # 平均会话时长
            'feature_usage': lambda x: len(x.unique()),  # 使用功能数
            'days_since_last_active': 'min', # 距上次活跃天数
            'page_views': 'sum'              # 页面浏览量
        }).reset_index()
        
        return features
    
    def cluster_users(self, features: pd.DataFrame, n_clusters: int = 4) -> pd.DataFrame:
        """用户聚类"""
        from sklearn.cluster import KMeans
        
        feature_cols = ['event_type', 'session_duration', 'feature_usage', 
                       'days_since_last_active', 'page_views']
        
        X = features[feature_cols].values
        
        kmeans = KMeans(n_clusters=n_clusters, random_state=42)
        features['cluster'] = kmeans.fit_predict(X)
        
        return features
    
    def interpret_clusters(self, clusters: pd.DataFrame) -> dict:
        """解释聚类结果"""
        interpretations = {}
        
        for cluster_id in clusters['cluster'].unique():
            cluster_data = clusters[clusters['cluster'] == cluster_id]
            
            interpretations[f'cluster_{cluster_id}'] = {
                'size': len(cluster_data),
                'avg_session': cluster_data['session_duration'].mean(),
                'avg_events': cluster_data['event_type'].mean(),
                'description': self.describe_cluster(cluster_data)
            }
        
        return interpretations
    
    def describe_cluster(self, cluster_data: pd.DataFrame) -> str:
        """描述集群"""
        avg_session = cluster_data['session_duration'].mean()
        avg_events = cluster_data['event_type'].mean()
        
        if avg_session > 300 and avg_events > 50:
            return '高活跃度用户'
        elif avg_session > 100 and avg_events > 20:
            return '中度活跃用户'
        elif cluster_data['days_since_last_active'].mean() > 7:
            return '沉睡用户'
        else:
            return '新用户'
```

## 四、生命周期分群

```python
class LifecycleSegmentation:
    def __init__(self):
        self.thresholds = {
            'new': {'min_days': 0, 'max_days': 7},
            'active': {'min_days': 7, 'max_days': 30},
            'at_risk': {'min_days': 30, 'max_days': 60},
            'churned': {'min_days': 60, 'max_days': float('inf')}
        }
    
    def classify_user(self, first_login: pd.Timestamp, last_login: pd.Timestamp) -> str:
        """用户生命周期分类"""
        days_since_first = (last_login - first_login).days
        days_since_last = (pd.Timestamp.now() - last_login).days
        
        if days_since_last <= 7:
            return 'active'
        elif days_since_last <= 30:
            return 'at_risk'
        elif days_since_last <= 60:
            return 'churned'
        else:
            return 'dead'
    
    def build_lifecycle_funnel(self, users: pd.DataFrame) -> dict:
        """构建生命周期漏斗"""
        lifecycle_counts = users['lifecycle'].value_counts()
        
        total = len(users)
        funnel = {}
        
        for stage in ['new', 'active', 'at_risk', 'churned', 'dead']:
            count = lifecycle_counts.get(stage, 0)
            funnel[stage] = {
                'count': count,
                'percentage': count / total * 100 if total > 0 else 0,
                'conversion_to_next': self.calculate_conversion(users, stage)
            }
        
        return funnel
    
    def calculate_conversion(self, users: pd.DataFrame, current_stage: str) -> float:
        """计算阶段转化率"""
        current = users[users['lifecycle'] == current_stage]
        next_stage = self.get_next_stage(current_stage)
        
        if next_stage:
            moved = users[(users['lifecycle'] == current_stage) & 
                         (users['next_lifecycle'] == next_stage)]
            return len(moved) / len(current) if len(current) > 0 else 0
        
        return 0
    
    def get_next_stage(self, current: str) -> str:
        """获取下一阶段"""
        stages = ['new', 'active', 'at_risk', 'churned', 'dead']
        try:
            idx = stages.index(current)
            return stages[idx + 1] if idx < len(stages) - 1 else None
        except ValueError:
            return None
```

## 五、面试高频题

### Q1: RFM模型是什么？

```
R (Recency): 最近一次消费时间
F (Frequency): 消费频率
M (Monetary): 消费金额
```

### Q2: 用户分群的应用场景？

```
1. 精准营销
2. 个性化推荐
3. 流失预警
4. 价值提升
```

## 六、自测题

1. 如何计算RFM评分？
2. K-Means聚类的优缺点？
3. 生命周期各阶段策略？

---

## 参考文档

- [RFM Model](https://www.ibm.com/topics/rfm-model)
- [User Segmentation](https://amplitude.com/help/guides/user-segmentation)
