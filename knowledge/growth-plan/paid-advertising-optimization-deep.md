# 付费投放优化深度实现 - 资深专家深度实现

## 一、投放策略框架

```
┌─────────────────────────────────────────────────────────────────────────┐
│                   付费广告投放流程                                         │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   账户搭建 → 素材制作 → 定向设置 → 出价策略 → 监控优化 → 数据归因       │
│      ↓         ↓         ↓         ↓         ↓         ↓              │
│   结构规划   创意生产   人群包    智能出价  实时优化  ROI计算           │
│                                                                         →
└─────────────────────────────────────────────────────────────────────────┘
```

## 二、智能出价算法

```python
import numpy as np
from scipy.optimize import minimize

class SmartBidding:
    def __init__(self, target_roas: float = 3.0):
        self.target_roas = target_roas  # 目标ROAS
        self.budget = 10000.0
        self.campaigns = {}
    
    def calculate_bid(self, historical_cvr: float, historical_cpm: float) -> float:
        """计算智能出价"""
        # 基于目标ROAS的出价公式
        # ROAS = Revenue / Cost = (CVR × AOV) / Bid
        # Bid = (CVR × AOV) / Target_ROAS
        
        aov = 100.0  # 平均订单价值
        bid = (historical_cvr * aov) / self.target_roas
        return max(0.1, bid)
    
    def optimize_budget_allocation(self, campaigns: list) -> dict:
        """预算优化分配"""
        # 使用线性规划优化
        def objective(x):
            return -sum(c['expected_roi'] * x[i] for i, c in enumerate(campaigns))
        
        constraints = [
            {'type': 'eq', 'fun': lambda x: sum(x) - self.budget}
        ]
        bounds = [(0, self.budget) for _ in campaigns]
        
        result = minimize(objective, np.ones(len(campaigns)), 
                         bounds=bounds, constraints=constraints)
        
        return {campaign['id']: float(result.x[i]) for i, campaign in enumerate(campaigns)}
    
    def pso_optimization(self, search_space: dict, iterations: int = 100) -> dict:
        """粒子群优化出价策略"""
        n_particles = 50
        particles = []
        
        for _ in range(n_particles):
            particle = {key: np.random.uniform(val['min'], val['max']) 
                       for key, val in search_space.items()}
            particles.append(particle)
        
        best_solution = None
        best_score = -float('inf')
        
        for _ in range(iterations):
            for particle in particles:
                score = self.evaluate_bid_strategy(particle)
                if score > best_score:
                    best_score = score
                    best_solution = particle.copy()
        
        return best_solution
    
    def evaluate_bid_strategy(self, strategy: dict) -> float:
        """评估出价策略"""
        # 模拟投放效果
        expected_roas = self.simulate_campaign(strategy)
        return expected_roas
```

## 三、人群定向策略

```python
class AudienceTargeting:
    def __init__(self):
        self.demographics = {
            'age': {'min': 18, 'max': 55},
            'gender': ['male', 'female', 'all'],
            'location': ['beijing', 'shanghai', 'guangzhou'],
            'interests': ['shopping', 'tech', 'fashion']
        }
    
    def build_audience(self, criteria: dict) -> dict:
        """构建目标人群"""
        audience = {
            'reach': 0,
            'frequency_cap': criteria.get('frequency_cap', 3),
            'lookalike': criteria.get('lookalike', True)
        }
        
        # 基础定向
        for key in ['age', 'gender', 'location']:
            if key in criteria:
                audience[key] = criteria[key]
        
        # 兴趣定向
        if 'interests' in criteria:
            audience['interests'] = criteria['interests']
        
        return audience
    
    def lookalike_expansion(self, seed_audience: list, expansion_rate: float = 0.1) -> list:
        """扩展相似人群"""
        import random
        expanded = seed_audience.copy()
        
        for user in seed_audience:
            if random.random() < expansion_rate:
                # 生成相似用户
                similar_user = self.generate_similar_user(user)
                expanded.append(similar_user)
        
        return expanded
    
    def generate_similar_user(self, seed: dict) -> dict:
        """生成相似用户"""
        return {
            'age': seed.get('age', 25) + np.random.randint(-5, 5),
            'gender': seed.get('gender', 'female'),
            'interests': seed.get('interests', [])[:3]
        }
```

## 四、创意优化

```python
class CreativeOptimizer:
    def __init__(self):
        self creativetypes = ['image', 'video', 'carousel', 'story']
    
    def analyze_creative_performance(self, creatives: list) -> dict:
        """分析创意表现"""
        results = {}
        for creative in creatives:
            ctr = creative['clicks'] / creative['impressions']
            cvr = creative['conversions'] / creative['clicks']
            roi = creative['revenue'] / creative['cost']
            
            results[creative['id']] = {
                'ctr': ctr,
                'cvr': cvr,
                'roi': roi,
                'score': self.calculate_score(ctr, cvr, roi)
            }
        
        return results
    
    def calculate_score(self, ctr: float, cvr: float, roi: float) -> float:
        """计算创意综合评分"""
        return ctr * 0.3 + cvr * 0.3 + min(roi / 5, 1.0) * 0.4
    
    def auto_generate_creative(self, product_info: dict) -> dict:
        """自动创意生成"""
        return {
            'title': f"{product_info['name']} - 限时优惠",
            'description': product_info['highlight'],
            'cta': '立即抢购',
            'images': self.generate_images(product_info),
            'video_duration': 15
        }
    
    def generate_images(self, product: dict) -> list:
        """生成创意图片"""
        return [
            {'type': 'primary', 'url': product['main_image']},
            {'type': 'detail', 'url': product['detail_image_1']},
            {'type': 'social_proof', 'url': product['review_screenshot']}
        ]
```

## 五、面试高频题

### Q1: 如何优化投放ROI？

```
1. 精准定向减少浪费
2. 智能出价提升效率
3. 创意优化提高转化
4. 数据归因准确核算
```

### Q2: 什么是智能出价？

```
基于机器学习，自动调整出价
目标: 在预算内最大化转化
```

## 六、自测题

1. 解释智能出价原理
2. 如何优化创意表现？
3. 人群包如何构建？

---

## 参考文档

- [Smart Bidding](https://support.google.com/google-ads/answer/2490327)
- [Audience Targeting](https://blog.hubspot.com/marketing/audience-targeting)
