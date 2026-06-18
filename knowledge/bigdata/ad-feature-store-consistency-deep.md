# 广告特征平台深度：Feature Store/在线离线一致性/特征治理

> 从特征定义到在线服务，逐行解析广告特征平台架构

---

## 第一部分：Feature Store 架构

```
广告 Feature Store 架构：
┌─────────────────────────────────────────────────────────────────────┐
│ Feature Definition Layer                                             │
│ ├── feature_groups: 特征组定义                                        │
│ ├── feature_views: 特征视图定义                                       │
│ └── feature_registry: 特征注册中心                                    │
│                                                                     │
│ Storage Layer                                                        │
│ ├── Online Store (Redis): 低延迟特征服务                              │
│ ├── Offline Store (ClickHouse): 历史特征查询                          │
│ └── Event Store (Kafka): 实时特征流入                                 │
│                                                                     │
│ Serving Layer                                                        │
│ ├── Feature Lookup API: 批量/实时查询                                 │
│ ├── Feature Join: 多特征组合                                         │
│ └── Feature Monitoring: 特征漂移监控                                  │
└─────────────────────────────────────────────────────────────────────┘
```

### FeatureStore 源码逐行解析

```python
# Feature Store 核心
class FeatureStore:
    def __init__(self, online_store, offline_store, event_store):
        self.online = online_store  # Redis
        self.offline = offline_store  # ClickHouse
        self.event_store = event_store  # Kafka
        self.registry = FeatureRegistry()
    
    def get_online_features(self, feature_names: list, 
                            entity_keys: list) -> dict:
        """
        获取在线特征（低延迟）
        
        Args:
            feature_names: 特征名称列表
            entity_keys: 实体键列表（如 user_id, device_id）
        
        Returns:
            {
                "user_id_123": {
                    "ctr": 0.05,
                    "cvr": 0.02,
                    "frequency_7d": 15,
                    ...
                },
                ...
            }
        """
        # 1. 批量查询 Redis
        pipeline = self.online.pipeline()
        
        for key in entity_keys:
            for feature in feature_names:
                pipe.hget(f"feature:{key}:{feature}", "value")
        
        results = pipeline.execute()
        
        # 2. 组装结果
        output = {}
        for i, key in enumerate(entity_keys):
            output[key] = {}
            for j, feature in enumerate(feature_names):
                value = results[i * len(feature_names) + j]
                if value is not None:
                    output[key][feature] = float(value)
        
        return output
    
    def get_offline_features(self, feature_names: list,
                              entity_keys: list,
                              start_time: str,
                              end_time: str) -> pd.DataFrame:
        """
        获取离线特征（历史数据）
        
        Args:
            feature_names: 特征名称
            entity_keys: 实体键
            start_time: 开始时间
            end_time: 结束时间
        
        Returns:
            DataFrame with historical features
        """
        query = f"""
        SELECT 
            entity_key,
            feature_name,
            feature_value,
            timestamp
        FROM feature_events
        WHERE entity_key IN ({','.join(entity_keys)})
          AND feature_name IN ({','.join(feature_names)})
          AND timestamp BETWEEN '{start_time}' AND '{end_time}'
        ORDER BY entity_key, timestamp
        """
        
        return self.offline.execute(query)
    
    def update_feature(self, entity_key: str, 
                       feature_name: str, value: float):
        """
        更新特征值
        
        同时写入在线和离线存储
        """
        # 1. 写入在线存储
        self.online.hset(
            f"feature:{entity_key}:{feature_name}",
            "value",
            str(value)
        )
        
        # 2. 写入事件流
        event = {
            "entity_key": entity_key,
            "feature_name": feature_name,
            "value": value,
            "timestamp": datetime.now().isoformat(),
        }
        self.event_store.produce(json.dumps(event))
        
        # 3. 注册到特征目录
        self.registry.register(feature_name, entity_key)
```

---

## 第二部分：在线离线一致性

### 一致性架构

```
在线/离线特征一致性：
┌─────────────────────────────────────────────────────────────────────┐
│ 训练时（Offline）:                                                   │
│ 1. 从 ClickHouse 查询历史特征                                        │
│ 2. 特征计算：Spark SQL                                               │
│ 3. 模型训练：TensorFlow/PyTorch                                      │
│                                                                     │
│ 预测时（Online）:                                                    │
│ 1. 从 Redis 查询实时特征                                             │
│ 2. 特征计算：Go/Java 代码                                            │
│ 3. 模型推理：TensorRT/TFLite                                         │
│                                                                     │
│ 一致性挑战：                                                         │
│ • 特征计算逻辑不一致                                                 │
│ • 时间窗口不一致                                                     │
│ • 缺失值处理不一致                                                   │
│ • 特征编码不一致                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### FeatureConsistency 源码逐行解析

```python
class FeatureConsistencyChecker:
    """在线离线特征一致性检查"""
    
    def __init__(self, online_store, offline_store):
        self.online = online_store
        self.offline = offline_store
    
    def check_consistency(self, feature_name: str,
                          entity_keys: list,
                          time_window: str = "24h") -> dict:
        """
        检查特征一致性
        
        Returns:
            {
                "consistent": True/False,
                "drift_score": 0.05,
                "max_diff": 0.01,
                "samples": [...],
            }
        """
        # 1. 获取在线特征
        online_features = self.online.get_recent(
            feature_name, entity_keys, time_window
        )
        
        # 2. 获取离线特征
        offline_features = self.offline.get_recent(
            feature_name, entity_keys, time_window
        )
        
        # 3. 对齐时间窗口
        aligned = self._align_time_windows(
            online_features, offline_features
        )
        
        # 4. 计算差异
        diffs = []
        for sample in aligned:
            diff = abs(sample["online"] - sample["offline"])
            diffs.append(diff)
        
        max_diff = max(diffs) if diffs else 0
        mean_diff = sum(diffs) / len(diffs) if diffs else 0
        
        # 5. 判断一致性
        drift_score = mean_diff / (mean(abs(online_features)) + 1e-8)
        
        return {
            "consistent": drift_score < 0.1,  # 漂移 < 10%
            "drift_score": drift_score,
            "max_diff": max_diff,
            "mean_diff": mean_diff,
            "samples": aligned[:10],  # 前 10 个样本
        }
    
    def _align_time_windows(self, online, offline):
        """对齐时间窗口"""
        # 简化：按 entity_key 对齐
        aligned = []
        for key in set(online.keys()) & set(offline.keys()):
            aligned.append({
                "entity_key": key,
                "online": online[key],
                "offline": offline[key],
            })
        return aligned
```

---

## 第三部分：自测题

### Q1: Feature Store 为什么需要在线和离线两套存储？

**A**: 离线存储（ClickHouse）适合批量查询历史数据，在线存储（Redis）适合低延迟实时查询。

### Q2: 在线离线一致性的难点？

**A**: 特征计算逻辑、时间窗口、缺失值处理、编码方式都可能不一致。

### Q3: 特征漂移怎么检测？

**A**: 对比在线和离线特征的统计分布，计算漂移分数。

---

## 第四部分：生产实践

### 1. 特征治理

```
特征治理要点：
1. 特征注册中心
2. 特征血缘追踪
3. 特征版本管理
4. 特征质量监控
```

### 2. 性能优化

```
性能优化要点：
1. 批量查询
2. 特征缓存
3. 预计算
4. 异步更新
```

### 3. 一致性保障

```
一致性保障要点：
1. 统一特征计算逻辑
2. 标准化时间窗口
3. 自动化测试
4. 定期巡检
```
