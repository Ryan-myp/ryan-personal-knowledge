# 广告数据管道：从数据采集到归因的完整架构

> 创建日期: 2026-06-10
> 作者: Ryan
> 定位: 资深专家级 — 数据管道与增长黑客

---

## 第一部分：广告数据管道架构

### 1.1 数据管道全景

```
┌──────────────────────────────────────────────────────────────┐
│              广告数据管道全景                                   │
│                                                              │
│  数据管道是广告系统的"神经系统"                                │
│  从曝光到归因，每个环节都有数据流                              │
│                                                              │
│  四个阶段:                                                   │
│  ├── 数据采集 (Collection)                                    │
│  ├── 数据传输 (Transport)                                    │
│  ├── 数据处理 (Processing)                                    │
│  └─ 数据消费 (Consumption)                                    │
│                                                              │
│  关键指标 (KPIs):                                             │
│  ├── 数据延迟: 端到端 < 30s (实时), < 5min (近实时)           │
│  ├── 数据完整性: > 99.9% (无丢失)                            │
│  ├── 数据准确性: > 99.5% (无重复/错误)                        │
│  └─ 吞吐量: 10M+ events/s (峰值)                             │
└──────────────────────────────────────────────────────────────┘
```

### 1.2 数据采集层

```
数据采集层: 从哪里采集数据

┌──────────────────────────────────────────────────────────────┐
│              采集类型                                          │
│                                                              │
│  1. 服务器端采集 (Server-Side):                               │
│  ├── 展示日志: DSP/SSP/Ad Exchange 记录每次展示               │
│  ├── 点击日志: 点击事件 → 追踪服务器                          │
│  ├── 转化日志: 转化事件 (购买/注册/安装)                      │
│  └─ 竞价日志: Bid Request/Response 记录                      │
│                                                              │
│  2. 客户端采集 (Client-Side):                                 │
│  ├── Impression Pixel: 1x1 透明图片                           │
│  ├── Click Redirect: 点击 URL → 追踪 → 落地页                 │
│  ├── Viewability Beacon: 可见性信号                           │
│  └─ JavaScript SDK: 深度用户行为追踪                          │
│                                                              │
│  3. API 回调 (Callback):                                     │
│  ├── Server-to-Server (S2S): DSP → Advertiser API            │
│  ├── Conversion API (CAPI): Meta/Google 转化API               │
│  └─ Webhooks: 实时事件推送                                    │
│                                                              │
│  4. 离线数据 (Offline Data):                                  │
│  ├── CRM 数据: 一方客户数据                                   │
│  ├── 销售数据: 线下转化记录                                   │
│  └─ 第三方数据: DMP/数据提供商                                 │
│                                                              │
│  采集协议:                                                   │
│  ├── HTTP POST (实时事件):                                   │
│  │   POST /api/v1/events                                     │
│  │   {                                                        │
│  │     "event_type": "impression",                            │
│  │     "timestamp": 1234567890000,                            │
│  │     "user_id": "user_123",                                 │
│  │     "ad_id": "ad_456",                                     │
│  │     "placement_id": "plc_789",                            │
│  │     "ip": "192.168.1.1",                                   │
│  │     "user_agent": "...",                                   │
│  │     "ext": {"device_id": "..."}                           │
│  │   }                                                       │
│  │                                                           │
│  └─ WebSocket (实时流):                                      │
│      └─ 实时 bid event streaming                              │
└──────────────────────────────────────────────────────────────┘
```

### 1.3 数据传输层

```
数据传输层: 从采集到存储的通道

┌──────────────────────────────────────────────────────────────┐
│              传输架构                                          │
│                                                              │
│  架构:                                                       │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐              │
│  │ Collectors│───▶│  Kafka   │───▶│ Processors│             │
│  │ (API)    │    │ (Bus)    │    │ (Flink)   │             │
│  └──────────┘    └──────────┘    └──────────┘              │
│                              │          │                    │
│                              ▼          ▼                    │
│                        ┌──────────┐ ┌──────────┐            │
│                        │  Stream  │ │  Batch   │            │
│                        │  Store   │ │  Store   │            │
│                        │(Kinesis) │ │(HDFS/S3) │            │
│                        └──────────┘ └──────────┘            │
│                              │          │                    │
│                              ▼          ▼                    │
│                        ┌──────────────────────┐             │
│                        │     Data Warehouse    │             │
│                        │  (BigQuery/Snowflake) │             │
│                        └──────────────────────┘             │
│                              │                              │
│                              ▼                              │
│                        ┌──────────────┐                    │
│                        │  Analytics   │                    │
│                        │  / ML / BI   │                    │
│                        └──────────────┘                    │
│                                                              │
│  Kafka 配置 (生产级别):                                      │
│  ├── Partition: 按 user_id/ad_id 分区                        │
│  ├── Replication: 3x (跨可用区)                              │
│  ├── Retention: 7d (实时), 30d (离线)                       │
│  └─ Throughput: 100K+ events/s per partition                │
│                                                              │
│  延迟保证:                                                   │
│  ├── 实时流: P99 < 5s (Flink + Kafka)                       │
│  ├── 近实时: P99 < 30s (Spark Streaming)                    │
│  └─ 批量: P99 < 5min (Spark Batch)                         │
└──────────────────────────────────────────────────────────────┘
```

---

## 第二部分：数据处理与特征工程

### 2.1 实时处理 (Flink)

```
Flink 实时处理: 从事件流到实时特征

┌──────────────────────────────────────────────────────────────┐
│              Flink 实时处理流水线                              │
│                                                              │
│  Source (Kafka Topics):                                      │
│  ├── ad_impressions — 展示事件                                │
│  ├── ad_clicks — 点击事件                                    │
│  ├── ad_conversions — 转化事件                               │
│  ├── bid_requests — 竞价请求                                 │
│  └─ bid_responses — 竞价响应                                 │
│                                                              │
│  Processing:                                                 │
│  ├── Step 1: 数据清洗                                         │
│  │   ├── 过滤 Bot 流量                                       │
│  │   ├── 去重 (同一 user+ad+time 窗口)                       │
│  │   └─ 填充缺失值                                           │
│  │                                                      │
│  ├── Step 2: 窗口聚合 (Windows)                              │
│  │   ├── Tumbling Window: 每 1 分钟聚合                      │
│  │   ├── Sliding Window: 每 10s 滑动 (1min 窗口)            │
│  │   └─ Session Window: 用户会话 (30min 无活动)              │
│  │                                                      │
│  ├── Step 3: 实时特征计算                                    │
│  │   ├── 用户过去 1h 点击数                                  │
│  │   ├── 用户过去 24h 展示数                                 │
│  │   ├── 广告过去 1h CTR                                    │
│  │   ├── 广告过去 24h CVR                                   │
│  │   └─ IP 过去 1h 请求数                                   │
│  │                                                      │
│  └─ Step 4: 写回特征存储                                     │
│      ├── Redis (实时特征): TTL = 1h                         │
│      └─ Flink State (内部状态):                              │
│          └─ RocksDB (大规模状态)                             │
│                                                              │
│  Flink SQL 示例:                                             │
│  ┌───────────────────────────────────────────────────────┐   │
│  │  -- 计算用户过去 1h 点击率                              │   │
│  │  CREATE VIEW user_ctr AS                               │   │
│  │  SELECT                                                │   │
│  │    user_id,                                           │   │
│  │    COUNT(CASE WHEN event_type = 'click' THEN 1 END)   │   │
│  │      / COUNT(*) AS ctr_1h,                            │   │
│  │    COUNT(*) AS total_1h,                              │   │
│  │    TUMBLE_END(rowtime, INTERVAL '1' HOUR) AS window_end│   │
│  │  FROM events                                           │   │
│  │  WHERE rowtime >= NOW() - INTERVAL '1' HOUR           │   │
│  │  GROUP BY                                              │   │
│  │    user_id,                                           │   │
│  │    TUMBLE(rowtime, INTERVAL '1' HOUR)                 │   │
│  └───────────────────────────────────────────────────────┘   │
│                                                              │
│  输出:                                                       │
│  ├── 实时特征 → Redis (供 DSP 竞价使用)                      │
│  ├── 实时Dashboard → Kibana/Grafana                         │
│  └─ 异常检测 → Alerting (欺诈/异常流量)                      │
└──────────────────────────────────────────────────────────────┘
```

### 2.2 批量处理 (Spark)

```
Spark 批量处理: 历史数据处理 + 模型训练特征

┌──────────────────────────────────────────────────────────────┐
│              Spark 处理流水线                                  │
│                                                              │
│  Source:                                                     │
│  ├── Kafka (历史数据)                                        │
│  ├── HDFS/S3 (离线存储)                                      │
│  └─ 外部 API (一方数据/第三方数据)                            │
│                                                              │
│  Processing:                                                 │
│  ├── Step 1: ETL (Extract/Transform/Load)                    │
│  │   ├── 数据清洗 (null/异常值)                               │
│  │   ├── 数据标准化 (单位/格式)                               │
│  │   └─ 数据分区 (按日期/渠道/广告系列)                       │
│  │                                                      │
│  ├── Step 2: 特征工程                                       │
│  │   ├── 用户历史行为特征 (30d/90d/365d)                    │
│  │   ├── 广告历史性能特征                                   │
│  │   ├── 交叉特征 (User×Ad×Context)                         │
│  │   └─ 聚合特征 (统计/百分位/排名)                          │
│  │                                                      │
│  └─ Step 3: 模型训练                                        │
│      ├── CTR/CVR 模型训练 (XGBoost/DeepFM/MMoE)            │
│      ├── 特征重要性分析                                     │
│      └─ 模型评估 (AUC/LogLoss)                              │
│                                                              │
│  Spark MLlib 示例:                                           │
│  ┌───────────────────────────────────────────────────────┐   │
│  │  from pyspark.ml.feature import VectorAssembler       │   │
│  │  from pyspark.ml.classification import LogisticRegression│   │
│  │                                                      │   │
│  │  # 加载历史数据                                        │   │
│  │  df = spark.read.parquet("s3://data/events/2026-06/*") │   │
│  │                                                      │   │
│  │  # 特征工程                                            │   │
│  │  feature_cols = [                                       │   │
│  │    'user_age', 'user_gender',                          │   │
│  │    'user_ctr_30d', 'user_cvr_30d',                     │   │
│  │    'ad_cpa_history', 'ad_category',                    │   │
│  │    'query_text_embed_50', 'page_category',             │   │
│  │    'device_type', 'geo_country',                       │   │
│  │    'is_top_rank', 'time_hour'                          │   │
│  │  ]                                                     │   │
│  │                                                      │   │
│  │  assembler = VectorAssembler(                         │   │
│  │    inputCols=feature_cols,                            │   │
│  │    outputCol='features'                               │   │
│  │  )                                                     │   │
│  │                                                      │   │
│  │  df_features = assembler.transform(df)               │   │
│  │                                                      │   │
│  │  # 训练 CTR 模型                                       │   │
│  │  lr = LogisticRegression(                              │   │
│  │    labelCol='clicked',                                 │   │
│  │    featuresCol='features',                            │   │
│  │    maxIter=10,                                        │   │
│  │    regParam=0.01                                      │   │
│  │  )                                                     │   │
│  │                                                      │   │
│  │  model = lr.fit(df_features)                          │   │
│  │  print(f"AUC: {model.summary.areaUnderROC}")           │   │
│  └───────────────────────────────────────────────────────┘   │
│                                                              │
│  输出:                                                       │
│  ├── 模型文件 → S3 (用于在线推理)                             │
│  ├── 特征表 → Feature Store (Feast)                         │
│  └─ 报告 → BI Dashboard                                     │
└──────────────────────────────────────────────────────────────┘
```

---

## 第三部分：实时特征存储

### 3.1 特征存储架构

```
特征存储 (Feature Store): 实时 + 离线特征的统一管理

┌──────────────────────────────────────────────────────────────┐
│              Feature Store 架构                                │
│                                                              │
│  三层存储:                                                   │
│  ┌───────────────────────────────────────────────────────┐   │
│  │  Layer 1: Online Store (Redis/Memcached)               │   │
│  │  ├── 延迟: < 1ms                                       │   │
│  │  ├── 用途: 实时推理 (DSP/RTB)                          │   │
│  │  ├── TTL: 1h-7d (短期特征)                             │   │
│  │  └─ 数据: 用户画像/广告表现/实时计数                     │   │
│  │                                                      │   │
│  │  Layer 2: Batch Store (S3/HDFS)                        │   │
│  │  ├── 延迟: 秒级                                         │   │
│  │  ├── 用途: 模型训练                                     │   │
│  │  ├── 数据: 历史行为/全量特征                            │   │
│  │  └─ 格式: Parquet + Avro                              │   │
│  │                                                      │   │
│  │  Layer 3: Feature Registry (元数据管理)                │   │
│  │  ├── 特征定义: name, type, description, owner          │   │
│  │  ├── 特征血缘: 数据来源 → 计算逻辑                      │   │
│  │  └─ 版本管理: 特征版本控制                              │   │
│  └───────────────────────────────────────────────────────┘   │
│                                                              │
│  典型特征:                                                   │
│  ├── 用户特征:                                               │
│  │   ├── user_age_bucket (int)                               │   │
│  │   ├── user_gender (string)                               │   │
│  │   ├── user_ctr_1h (float) — 过去 1h CTR                  │   │
│  │   ├── user_ctr_24h (float) — 过去 24h CTR                │   │
│  │   ├── user_ctr_7d (float) — 过去 7d CTR                  │   │
│  │   ├── user_cvr_7d (float) — 过去 7d CVR                  │   │
│  │   └─ user_device_type (string) — mobile/desktop/tablet   │   │
│  │                                                      │   │
│  ├── 广告特征:                                               │   │
│  │   ├── ad_adomain (string)                               │   │
│  │   ├── ad_category (string)                              │   │
│  │   ├── ad_ctr_24h (float) — 过去 24h CTR                  │   │
│  │   ├── ad_cvr_7d (float) — 过去 7d CVR                    │   │
│  │   └─ ad_cpa_30d (float) — 过去 30d CPA                   │   │
│  │                                                      │   │
│  └─ 上下文特征:                                              │
│      ├── context_hour (int) — 小时                          │   │
│      ├── context_dayofweek (int) — 星期                      │   │
│      ├── context_geo_city (string) — 城市                    │   │
│      └─ context_page_category (string) — 页面类别            │   │
└──────────────────────────────────────────────────────────────┘
```

---

## 第四部分：增长黑客 — 数据驱动的投放优化

### 4.1 增长黑客核心框架

```
增长黑客 (Growth Hacking) 框架:

┌──────────────────────────────────────────────────────────────┐
│              增长飞轮                                          │
│                                                              │
│         ┌─────────────┐                                      │
│         │  数据洞察     │                                      │
│         │(Data Insights)│                                     │
│         └──────┬──────┘                                      │
│                │                                              │
│                ▼                                              │
│         ┌─────────────┐                                      │
│         │  实验设计     │                                      │
│         │ (Experiments)│                                     │
│         └──────┬──────┘                                      │
│                │                                              │
│                ▼                                              │
│         ┌─────────────┐                                      │
│         │  快速迭代     │                                      │
│         │ (Iteration)  │                                      │
│         └──────┬──────┘                                      │
│                │                                              │
│                ▼                                              │
│         ┌─────────────┐                                      │
│         │  规模扩张     │                                      │
│         │ (Scale)      │                                      │
│         └──────┬──────┘                                      │
│                │                                              │
│                └──▶ 新数据洞察 → (循环)                        │
│                                                              │
│  核心原则:                                                   │
│  ├── 数据驱动: 所有决策基于数据，不是直觉                      │
│  ├── 快速实验: 小步快跑，快速验证假设                         │
│  ├── 杠杆思维: 找到高 ROI 的增长点，全力投入                  │
│  └─ 自动化: 用自动化代替手动优化                              │
└──────────────────────────────────────────────────────────────┘
```

### 4.2 增长黑客策略

```
增长黑客关键策略:

1. 获客 (Acquisition):
├── 低成本渠道测试: TikTok/Reddit/Discord                        │
├── 病毒式传播: 推荐裂变 (Referral)                               │
├── SEO/ASO: 自然搜索优化                                        │
├── 内容营销: 博客/视频/播客                                     │
└─ 联盟营销: Affiliate Network                                  

2. 激活 (Activation):
├── 新用户 Onboarding: 引导流程优化                              │
├── Aha Moment: 让用户快速体验核心价值                             │
├── 首单激励: 首次购买折扣                                       │
└─ 社交证明: 评价/星级/销量                                     

3. 留存 (Retention):
├── 推送通知 (Push): 个性化召回                                  │
├── 邮件营销 (Email): 弃购挽回/复购激励                           │
├── 会员体系: 积分/等级/特权                                     │
└─ 个性化推荐: 基于行为的推荐引擎                               

4. 收入 (Revenue):
├── 交叉销售 (Cross-sell): 相关商品推荐                           │
├── 向上销售 (Upsell): 更高价位推荐                               │
├── 动态定价: 基于需求/竞争的定价                                 │
└─ LTV 优化: 提升客户终身价值                                  

5. 推荐 (Referral):
├── 推荐奖励: 双方都获得折扣                                      │
├── 社交分享: 一键分享链接                                        │
└─ UGC (用户生成内容): 评价/照片/视频                           

AARRR 漏斗:                                                    │
│                                                              │
│  Acquisition → Activation → Retention → Revenue → Referral  │
│     │            │               │           │           │    │
│     │            │               │           │           │    │
│  降低获客成本   提高激活率      提升留存率   提高 ARPU    降低流失率
```

### 4.3 增长黑客代码实现

```python
"""
增长黑客核心: 实验平台 + 自动化优化
"""

import numpy as np
import pandas as pd
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from enum import Enum
import time


class ExperimentStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    STOPPED = "stopped"
    COMPLETED = "completed"


@dataclass
class Experiment:
    """A/B 测试实验"""
    experiment_id: str
    name: str
    variant_a: dict  # 对照组
    variant_b: dict  # 实验组
    metric: str  # 'ctr', 'cvr', 'roas', 'revenue'
    target_improvement: float  # 期望提升 (e.g., 0.1 = 10%)
    status: ExperimentStatus = ExperimentStatus.PENDING
    traffic_allocation: Dict[str, float] = field(default_factory=dict)
    results: Dict[str, dict] = field(default_factory=dict)
    
    def allocate_traffic(self, variant: str, user_id: str) -> str:
        """
        流量分配: 将用户分配到对照组或实验组
        使用一致性哈希，确保同一用户始终分配到同一组
        """
        import hashlib
        hash_val = int(hashlib.md5(
            f"{experiment_id}:{user_id}".encode()
        ).hexdigest(), 16)
        
        allocation = sum(self.traffic_allocation.values())
        current = 0
        for v, ratio in self.traffic_allocation.items():
            current += ratio
            if hash_val % 10000 < current * 100:
                return v
        return list(self.traffic_allocation.keys())[0]
    
    def record_result(self, variant: str, event: str):
        """记录实验结果"""
        if variant not in self.results:
            self.results[variant] = {'impressions': 0, 'events': 0}
        
        self.results[variant]['impressions'] += 1
        if event:
            self.results[variant]['events'] += 1
    
    def get_results(self) -> Dict[str, float]:
        """计算实验结果"""
        results = {}
        for variant, data in self.results.items():
            imp = data['impressions']
            events = data['events']
            rate = events / imp if imp > 0 else 0
            results[f'{variant}_{self.metric}'] = rate
            results[f'{variant}_impressions'] = imp
            results[f'{variant}_events'] = events
        return results
    
    def is_significant(self) -> Tuple[bool, float]:
        """
        检查统计显著性
        
        使用 Z-test 比较两个比例的差异
        """
        if not self.results.get('variant_a') or not self.results.get('variant_b'):
            return False, 0.0
        
        a = self.results['variant_a']
        b = self.results['variant_b']
        
        p_a = a['events'] / a['impressions'] if a['impressions'] > 0 else 0
        p_b = b['events'] / b['impressions'] if b['impressions'] > 0 else 0
        
        # 合并比例
        p_pool = (a['events'] + b['events']) / (a['impressions'] + b['impressions'])
        
        if p_pool == 0 or p_pool == 1:
            return False, 0.0
        
        # 标准误差
        se = np.sqrt(p_pool * (1 - p_pool) * (1/a['impressions'] + 1/b['impressions']))
        
        if se == 0:
            return False, 0.0
        
        # Z 分数
        z = (p_b - p_a) / se
        
        # p-value (近似)
        p_value = 2 * (1 - self._normal_cdf(abs(z)))
        
        return p_value < 0.05, p_value
    
    def _normal_cdf(self, z: float) -> float:
        """近似正态分布 CDF"""
        return 0.5 * (1 + np.erf(z / np.sqrt(2)))


class AutoOptimizer:
    """
    自动优化工具: 基于数据自动调整投放策略
    """
    
    def __init__(self, campaigns: List[dict]):
        self.campaigns = {c['id']: c for c in campaigns}
        self.budget_per_day = {c['id']: c.get('daily_budget', 100) for c in campaigns}
    
    def optimize_budget_allocation(self) -> Dict[str, float]:
        """
        自动预算分配: 按 ROI 分配预算
        
        基于历史 ROI 数据，动态调整各广告系列的预算分配
        """
        total_budget = sum(self.budget_per_day.values())
        allocations = {}
        
        for cid, campaign in self.campaigns.items():
            roi = campaign.get('recent_roi', 1.0)
            if roi > 0:
                allocations[cid] = roi
            else:
                allocations[cid] = 0
        
        # 归一化
        total_roi = sum(allocations.values())
        if total_roi > 0:
            for cid in allocations:
                allocations[cid] = total_budget * (allocations[cid] / total_roi)
        else:
            # 等分
            for cid in allocations:
                allocations[cid] = total_budget / len(allocations)
        
        return allocations
    
    def optimize_bids(self, insights: dict) -> Dict[str, float]:
        """
        自动出价调整: 基于 CTR/CVR 数据
        
        规则:
        ├── CTR > 目标 → 出价 +10%
        ├── CTR < 目标/2 → 出价 -20%
        ├── CVR > 目标 → 出价 +15%
        └─ CVR < 目标/2 → 出价 -25%
        """
        adjustments = {}
        
        for cid, campaign in self.campaigns.items():
            target_ctr = campaign.get('target_ctr', 0.02)
            target_cvr = campaign.get('target_cvr', 0.05)
            
            current_ctr = insights.get(f'{cid}_ctr', target_ctr)
            current_cvr = insights.get(f'{cid}_cvr', target_cvr)
            
            adjustment = 1.0
            
            # CTR 调整
            if current_ctr > target_ctr * 1.5:
                adjustment *= 1.10
            elif current_ctr < target_ctr * 0.5:
                adjustment *= 0.80
            
            # CVR 调整
            if current_cvr > target_cvr * 1.5:
                adjustment *= 1.15
            elif current_cvr < target_cvr * 0.5:
                adjustment *= 0.75
            
            adjustments[cid] = adjustment
        
        return adjustments
    
    def detect_anomalies(self, metrics: dict) -> List[dict]:
        """
        异常检测: 监控指标波动
        
        使用移动平均 + 标准差检测
        """
        anomalies = []
        window_size = 24  # 24h 窗口
        
        for metric_name, values in metrics.items():
            if len(values) < window_size:
                continue
            
            # 计算移动平均和标准差
            recent = values[-window_size:]
            mean = np.mean(recent)
            std = np.std(recent)
            
            # 最新值
            latest = values[-1]
            
            # 超过 3 个标准差 → 异常
            if abs(latest - mean) > 3 * std:
                anomalies.append({
                    'metric': metric_name,
                    'latest': latest,
                    'mean': mean,
                    'std': std,
                    'z_score': (latest - mean) / std if std > 0 else 0,
                })
        
        return anomalies
```

---

## 第五部分：自测题

### 问题 1
数据管道的四个阶段？

<details>
<summary>查看答案</summary>

1. 数据采集 (Collection)
2. 数据传输 (Transport)
3. 数据处理 (Processing)
4. 数据消费 (Consumption)
</details>

### 问题 2
Feature Store 的三层存储？

<details>
<summary>查看答案</summary>

1. Online Store (Redis): < 1ms, 实时推理
2. Batch Store (S3/HDFS): 秒级, 模型训练
3. Feature Registry: 元数据管理/版本控制/血缘
</details>

### 问题 3
AARRR 漏斗的五个阶段？

<details>
<summary>查看答案</summary>

Acquisition → Activation → Retention → Revenue → Referral
获客 → 激活 → 留存 → 收入 → 推荐
</details>

---

### 广告数据管道的 Go 实现

```go
// 广告数据管道: 从数据采集到归因的 Go 实现
// 覆盖事件采集、流处理、特征管道、归因计算
package datapipeline

import (
	"encoding/json"
	"fmt"
	"sync"
	"time"
)

// ==================== 事件模型 ====================

// EventType 事件类型
type EventType string

const (
	EventImpression    EventType = "impression"
	EventClick         EventType = "click"
	EventConversion    EventType = "conversion"
	EventViewContent   EventType = "view_content"
	EventAddToCart     EventType = "add_to_cart"
	EventPurchase      EventType = "purchase"
	EventEngageAd      EventType = "engage_ad"
)

// AdEvent 广告事件
type AdEvent struct {
	ID          string    `json:"event_id"`
	Type        EventType `json:"event_type"`
	Timestamp   time.Time `json:"timestamp"`
	UserID      string    `json:"user_id"`
	CampaignID  string    `json:"campaign_id"`
	AdGroupID   string    `json:"ad_group_id"`
	AdID        string    `json:"ad_id"`
	CreativeID  string    `json:"creative_id"`
	Platform    string    `json:"platform"`
	IP          string    `json:"ip"`
	UserAgent   string    `json:"user_agent"`
	DeviceType  string    `json:"device_type"`
	Location    string    `json:"location"`
	Value       float64   `json:"value"`
	Currency    string    `json:"currency"`
	ConversionID string   `json:"conversion_id"`
	Extras      map[string]string `json:"extras,omitempty"`
}

// ==================== 事件采集 ====================

// EventCollector 事件采集器 — 支持批量上报 + 本地缓存
type EventCollector struct {
	batchSize  int
	buffer     []AdEvent
	flushCh    chan []AdEvent
	mu         sync.Mutex
	processed  int
	dropped    int
}

// NewEventCollector 创建采集器
func NewEventCollector(batchSize int) *EventCollector {
	if batchSize == 0 {
		batchSize = 100
	}
	c := &EventCollector{
		batchSize: batchSize,
		buffer:    make([]AdEvent, 0, batchSize),
		flushCh:   make(chan []AdEvent, 10),
	}
	go c.flushLoop()
	return c
}

// Collect 收集一个事件
func (c *EventCollector) Collect(event AdEvent) error {
	c.mu.Lock()
	defer c.mu.Unlock()

	c.buffer = append(c.buffer, event)
	c.processed++

	if len(c.buffer) >= c.batchSize {
		batch := make([]AdEvent, len(c.buffer))
		copy(batch, c.buffer)
		c.buffer = c.buffer[:0]
		c.flushCh <- batch
	}
	return nil
}

// Flush 强制刷新缓冲区
func (c *EventCollector) Flush() {
	c.mu.Lock()
	defer c.mu.Unlock()

	if len(c.buffer) == 0 {
		return
	}
	batch := make([]AdEvent, len(c.buffer))
	copy(batch, c.buffer)
	c.buffer = c.buffer[:0]
	c.flushCh <- batch
}

// flushLoop 后台刷新循环
func (c *EventCollector) flushLoop() {
	for batch := range c.flushCh {
		// 发送到 Kafka / HTTP API
		c.sendToPipe(batch)
	}
}

// sendToPipe 发送到管道
func (c *EventCollector) sendToPipe(batch []AdEvent) {
	for _, e := range batch {
		fmt.Printf("[pipe] %s: %s by %s (%.2f)\n",
			e.Type, e.CampaignID, e.UserID, e.Value)
	}
}

// ==================== 实时特征计算 ====================

// FeatureStore 实时特征存储
type FeatureStore struct {
	userFeatures map[string]*UserFeatures
	campaignFeatures map[string]*CampaignFeatures
	windowSize time.Duration
	mu         sync.RWMutex
}

type UserFeatures struct {
	UserID           string    `json:"user_id"`
	LastClickTime    time.Time `json:"last_click_time"`
	Clicks24h        int       `json:"clicks_24h"`
	Conversions24h   int       `json:"conversions_24h"`
	Spend24h         float64   `json:"spend_24h"`
	AvgOrderValue    float64   `json:"avg_order_value"`
	DeviceType       string    `json:"device_type"`
	TopPlatform      string    `json:"top_platform"`
}

type CampaignFeatures struct {
	CampaignID      string    `json:"campaign_id"`
	LastImpression  time.Time `json:"last_impression"`
	Impressions24h  int       `json:"impressions_24h"`
	Clicks24h       int       `json:"clicks_24h"`
	Conversions24h  int       `json:"conversions_24h"`
	Spend24h        float64   `json:"spend_24h"`
	CTR             float64   `json:"ctr"`
	CPA             float64   `json:"cpa"`
}

// NewFeatureStore 创建特征存储
func NewFeatureStore() *FeatureStore {
	return &FeatureStore{
		userFeatures:     make(map[string]*UserFeatures),
		campaignFeatures: make(map[string]*CampaignFeatures),
		windowSize:       24 * time.Hour,
	}
}

// Update 更新特征
func (f *FeatureStore) Update(event AdEvent) {
	f.mu.Lock()
	defer f.mu.Unlock()

	now := time.Now()
	windowStart := now.Add(-f.windowSize)

	// 更新用户特征
	if event.UserID != "" {
		uf, ok := f.userFeatures[event.UserID]
		if !ok {
			uf = &UserFeatures{UserID: event.UserID}
			f.userFeatures[event.UserID] = uf
		}
		uf.LastClickTime = now

		switch event.Type {
		case EventClick:
			uf.Clicks24h++
		case EventConversion, EventPurchase:
			uf.Conversions24h++
			if uf.AvgOrderValue == 0 {
				uf.AvgOrderValue = event.Value
			} else {
				uf.AvgOrderValue = uf.AvgOrderValue*0.9 + event.Value*0.1
			}
		}
		uf.Spend24h += event.Value
		uf.DeviceType = event.DeviceType
	}

	// 更新广告系列特征
	if event.CampaignID != "" {
		cf, ok := f.campaignFeatures[event.CampaignID]
		if !ok {
			cf = &CampaignFeatures{CampaignID: event.CampaignID}
			f.campaignFeatures[event.CampaignID] = cf
		}
		cf.LastImpression = now

		switch event.Type {
		case EventImpression:
			cf.Impressions24h++
		case EventClick:
			cf.Clicks24h++
		case EventConversion, EventPurchase:
			cf.Conversions24h++
			cf.CPA = cf.Spend24h / float64(cf.Conversions24h)
		}
		cf.Spend24h += event.Value
		cf.CTR = float64(cf.Clicks24h) / float64(cf.Impressions24h)
	}
}

// GetUserFeatures 获取用户特征
func (f *FeatureStore) GetUserFeatures(userID string) *UserFeatures {
	f.mu.RLock()
	defer f.mu.RUnlock()
	return f.userFeatures[userID]
}

// ==================== 增量归因 ====================

// AttributionModel 归因模型
type AttributionModel string

const (
	LastClick    AttributionModel = "LAST_CLICK"
	FirstClick   AttributionModel = "FIRST_CLICK"
	Linear       AttributionModel = "LINEAR"
	TimeDecay    AttributionModel = "TIME_DECAY"
 PositionBased AttributionModel = "POSITION_BASED"
)

// ConversionPath 转化路径
type ConversionPath struct {
	ConversionID string
	UserID       string
	Events       []AdEvent
	Value        float64
}

// IncrementalAttribution 增量归因引擎
type IncrementalAttribution struct {
	model  AttributionModel
	window time.Duration
}

// NewIncrementalAttribution 创建归因引擎
func NewIncrementalAttribution(model AttributionModel, window time.Duration) *IncrementalAttribution {
	if window == 0 {
		window = 7 * 24 * time.Hour // 7 天归因窗口
	}
	return &IncrementalAttribution{
		model:  model,
		window: window,
	}
}

// Attribute 对转化路径进行归因
func (a *IncrementalAttribution) Attribute(path *ConversionPath) map[string]float64 {
	credits := make(map[string]float64)

	switch a.model {
	case LastClick:
		// 最后点击归因: 100% 给最后一个点击
		lastClick := a.lastEvent(path, EventClick)
		if lastClick != nil {
			credits[lastClick.AdID] = 1.0
		}

	case FirstClick:
		// 首次点击归因
		firstClick := a.firstEvent(path, EventClick)
		if firstClick != nil {
			credits[firstClick.AdID] = 1.0
		}

	case Linear:
		// 线性归因: 所有点击平分
		clicks := a.clickEvents(path)
		if len(clicks) > 0 {
			for _, e := range clicks {
				credits[e.AdID] += 1.0 / float64(len(clicks))
			}
		}

	case TimeDecay:
		// 时间衰减: 越接近转化的点击权重越高
		clicks := a.clickEvents(path)
		if len(clicks) > 0 {
			totalWeight := 0.0
			for i := range clicks {
				t := clicks[i].Timestamp
				daysToConversion := path.Events[len(path.Events)-1].Sub(t).Hours() / 24
				weight := math.Exp(-0.5 * daysToConversion)
				clicks[i].extraWeight = weight
				totalWeight += weight
			}
			for _, e := range clicks {
				credits[e.AdID] += e.extraWeight / totalWeight
			}
		}

	case PositionBased:
		// 位置归因: 首 40% + 末 40% + 中间平分
		clicks := a.clickEvents(path)
		if len(clicks) > 0 {
			if len(clicks) == 1 {
				credits[clicks[0].AdID] = 1.0
			} else {
				credits[clicks[0].AdID] = 0.4
				credits[clicks[len(clicks)-1].AdID] = 0.4
				if len(clicks) > 2 {
					remaining := 0.2 / float64(len(clicks)-2)
					for i := 1; i < len(clicks)-1; i++ {
						credits[clicks[i].AdID] += remaining
					}
				}
			}
		}
	}

	return credits
}

// ==================== 归因工具函数 ====================

func (a *IncrementalAttribution) clickEvents(path *ConversionPath) []AdEvent {
	var clicks []AdEvent
	for _, e := range path.Events {
		if e.Type == EventClick {
			clicks = append(clicks, e)
		}
	}
	return clicks
}

func (a *IncrementalAttribution) lastEvent(path *ConversionPath, typ EventType) *AdEvent {
	for i := len(path.Events) - 1; i >= 0; i-- {
		if path.Events[i].Type == typ {
			return &path.Events[i]
		}
	}
	return nil
}

func (a *IncrementalAttribution) firstEvent(path *ConversionPath, typ EventType) *AdEvent {
	for i := range path.Events {
		if path.Events[i].Type == typ {
			return &path.Events[i]
		}
	}
	return nil
}

// ==================== 使用示例 ====================

func main() {
	// 1. 事件采集
	collector := NewEventCollector(100)
	collector.Collect(AdEvent{
		ID:         "evt_001",
		Type:       EventImpression,
		Timestamp:  time.Now(),
		UserID:     "user_123",
		CampaignID: "camp_summer",
		AdID:       "ad_456",
		Platform:   "tiktok",
	})

	// 2. 特征更新
	store := NewFeatureStore()
	store.Update(AdEvent{
		Type:       EventClick,
		UserID:     "user_123",
		CampaignID: "camp_summer",
		AdID:       "ad_456",
		DeviceType: "mobile",
	})
	store.Update(AdEvent{
		Type:       EventPurchase,
		UserID:     "user_123",
		Value:      99.99,
		CampaignID: "camp_summer",
		AdID:       "ad_456",
	})
	uf := store.GetUserFeatures("user_123")
	if uf != nil {
		fmt.Printf("User features: clicks=%d, conversions=%d, spend=%.2f\n",
			uf.Clicks24h, uf.Conversions24h, uf.Spend24h)
	}

	// 3. 归因计算
	path := &ConversionPath{
		ConversionID: "conv_001",
		UserID:       "user_123",
		Events: []AdEvent{
			{ID: "e1", Type: EventImpression, AdID: "ad_a", Timestamp: time.Now().Add(-7 * 24 * time.Hour)},
			{ID: "e2", Type: EventClick, AdID: "ad_a", Timestamp: time.Now().Add(-6 * 24 * time.Hour)},
			{ID: "e3", Type: EventImpression, AdID: "ad_b", Timestamp: time.Now().Add(-4 * 24 * time.Hour)},
			{ID: "e4", Type: EventClick, AdID: "ad_b", Timestamp: time.Now().Add(-3 * 24 * time.Hour)},
			{ID: "e5", Type: EventImpression, AdID: "ad_c", Timestamp: time.Now().Add(-1 * 24 * time.Hour)},
			{ID: "e6", Type: EventClick, AdID: "ad_c", Timestamp: time.Now().Add(-2 * time.Hour)},
			{ID: "e7", Type: EventPurchase, AdID: "ad_c", Value: 150.0, Timestamp: time.Now()},
		},
		Value: 150.0,
	}

	// Last Click
	lastClick := NewIncrementalAttribution(LastClick, 0)
	credits := lastClick.Attribute(path)
	fmt.Printf("Last Click: %v\n", credits)

	// Linear
	linear := NewIncrementalAttribution(Linear, 0)
	credits = linear.Attribute(path)
	fmt.Printf("Linear: %v\n", credits)

	// Position Based
	posBased := NewIncrementalAttribution(PositionBased, 0)
	credits = posBased.Attribute(path)
	fmt.Printf("Position Based: %v\n", credits)
}
