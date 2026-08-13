# 增长实验平台设计 - 资深专家深度实现

## 一、平台架构

```
┌─────────────────────────────────────────────────────────────────────────┐
│                   增长实验平台架构                                         │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   ┌─────────────┐    ┌─────────────┐    ┌─────────────┐               │
│   │  实验配置   │───►│  流量分配   │───►│  数据采集   │               │
│   │  Console    │    │  Engine     │    │  Pipeline   │               │
│   └─────────────┘    └─────────────┘    └─────────────┘               │
│         │                   │                   │                      │
│         ▼                   ▼                   ▼                      │
│   ┌─────────────┐    ┌─────────────┐    ┌─────────────┐               │
│   │  策略引擎   │    │  实验桶     │    │  实时看板   │               │
│   │  Strategy   │    │  Bucketing  │    │  Dashboard  │               │
│   └─────────────┘    └─────────────┘    └─────────────┘               │
│                                                                         →
└─────────────────────────────────────────────────────────────────────────┘
```

## 二、流量分配实现

```python
import hashlib
import json

class TrafficAllocator:
    def __init__(self, algorithm: str = 'hash'):
        self.algorithm = algorithm
        self.buckets = {}
    
    def assign(self, user_id: str, experiment_id: str, variants: list) -> str:
        """分配用户到实验组"""
        key = f"{experiment_id}:{user_id}"
        
        if self.algorithm == 'hash':
            hash_value = int(hashlib.md5(key.encode()).hexdigest(), 16)
            bucket = hash_value % len(variants)
        else:
            bucket = self.consistent_hash(key, len(variants))
        
        self.buckets[key] = {
            'user_id': user_id,
            'experiment_id': experiment_id,
            'variant': variants[bucket],
            'bucket': bucket
        }
        
        return variants[bucket]
    
    def consistent_hash(self, key: str, n_buckets: int) -> int:
        """一致性哈希"""
        hash_value = int(hashlib.sha256(key.encode()).hexdigest(), 16)
        return hash_value % n_buckets
    
    def get_allocation(self, user_id: str, experiment_id: str) -> dict:
        """查询分配结果"""
        key = f"{experiment_id}:{user_id}"
        return self.buckets.get(key, None)
    
    def ensure_consistency(self, user_id: str, experiment_id: str, variants: list) -> str:
        """确保用户多次访问分配到同一组"""
        return self.assign(user_id, experiment_id, variants)
```

## 三、实验配置管理

```python
class ExperimentManager:
    def __init__(self):
        self.experiments = {}
    
    def create_experiment(self, config: dict) -> str:
        """创建实验"""
        experiment_id = hashlib.md5(json.dumps(config, sort_keys=True).encode()).hexdigest()[:16]
        
        self.experiments[experiment_id] = {
            'id': experiment_id,
            'name': config['name'],
            'variants': config['variants'],
            'targeting': config.get('targeting', {}),
            'status': 'active',
            'created_at': datetime.now(),
            'metrics': config.get('metrics', [])
        }
        
        return experiment_id
    
    def pause_experiment(self, experiment_id: str):
        """暂停实验"""
        if experiment_id in self.experiments:
            self.experiments[experiment_id]['status'] = 'paused'
    
    def stop_experiment(self, experiment_id: str, winner: str = None):
        """停止实验"""
        if experiment_id in self.experiments:
            self.experiments[experiment_id]['status'] = 'completed'
            self.experiments[experiment_id]['winner'] = winner
    
    def get_experiment(self, experiment_id: str) -> dict:
        """获取实验详情"""
        return self.experiments.get(experiment_id, {})
    
    def list_experiments(self, status: str = None) -> list:
        """列出实验"""
        experiments = list(self.experiments.values())
        if status:
            experiments = [e for e in experiments if e['status'] == status]
        return experiments
```

## 四、数据收集管道

```python
class ExperimentDataPipeline:
    def __init__(self, storage: str = 'clickhouse'):
        self.storage = storage
    
    def collect_event(self, event: dict):
        """收集实验事件"""
        # 验证事件
        if not self.validate_event(event):
            return
        
        # 存储
        self.store_event(event)
    
    def validate_event(self, event: dict) -> bool:
        """验证事件格式"""
        required_fields = ['user_id', 'experiment_id', 'variant', 'event_type', 'timestamp']
        return all(field in event for field in required_fields)
    
    def store_event(self, event: dict):
        """存储事件"""
        # 简化版实现
        pass
    
    def query_results(self, experiment_id: str, metric: str) -> dict:
        """查询实验结果"""
        # 返回聚合数据
        return {
            'experiment_id': experiment_id,
            'metric': metric,
            'variants': {
                'control': {'users': 1000, 'conversions': 50, 'rate': 0.05},
                'variant_a': {'users': 1000, 'conversions': 65, 'rate': 0.065},
                'variant_b': {'users': 1000, 'conversions': 58, 'rate': 0.058}
            }
        }
```

## 五、实时看板

```python
class RealtimeDashboard:
    def __init__(self):
        self.caches = {}
    
    def get_live_metrics(self, experiment_id: str) -> dict:
        """获取实时指标"""
        if experiment_id not in self.caches:
            self.refresh_cache(experiment_id)
        return self.caches[experiment_id]
    
    def refresh_cache(self, experiment_id: str):
        """刷新缓存"""
        # 从数据库聚合数据
        pass
    
    def calculate_significance(self, variant_a: dict, variant_b: dict) -> dict:
        """计算显著性"""
        from scipy import stats
        
        n_a, x_a = variant_a['users'], variant_a['conversions']
        n_b, x_b = variant_b['users'], variant_b['conversions']
        
        p_a = x_a / n_a
        p_b = x_b / n_b
        
        # Z检验
        p_pool = (x_a + x_b) / (n_a + n_b)
        se = np.sqrt(p_pool * (1 - p_pool) * (1/n_a + 1/n_b))
        z = (p_b - p_a) / se if se > 0 else 0
        
        from scipy.stats import norm
        p_value = 2 * (1 - norm.cdf(abs(z)))
        
        return {
            'lift': (p_b - p_a) / p_a * 100,
            'p_value': p_value,
            'significant': p_value < 0.05,
            'confidence': (1 - p_value) * 100
        }
```

## 六、面试高频题

### Q1: 如何确保实验一致性？

```
1. 使用一致性哈希
2. 用户维度绑定
3. 持久化存储
4. 定期校验
```

### Q2: 实验平台核心组件？

```
1. 实验配置管理
2. 流量分配引擎
3. 数据采集管道
4. 实时分析看板
5. 结果归档
```

## 七、自测题

1. 如何实现流量均匀分配？
2. 实验数据如何保证准确性？
3. 如何处理实验冲突？

---

## 参考文档

- [Experiment Platform](https://github.com/etsy/statsd)
- [A/B Testing Infrastructure](https://growthhackers.com/articles/ab-testing)
