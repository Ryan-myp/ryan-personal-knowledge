# 广告系统端到端架构图

> 从用户请求到广告展示的全链路架构，覆盖竞价、排序、召回、重排、计费、归因

---

## 第一部分：广告系统总览

### 架构分层图

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              广告系统架构图                                  │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  Layer 1: 接入层 (API Gateway)                                       │   │
│  │  • Nginx / Envoy 负载均衡                                             │   │
│  │  • JWT 认证 / 限流 / 熔断                                             │   │
│  │  • HTTPS 终止 / WebSocket 长连接                                      │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                              │                                              │
│                              ▼                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  Layer 2: 业务服务层 (Microservices)                                 │   │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐  │   │
│  │  │ Campaign  │ │  Bidder  │ │  Ranker  │ │  Payout  │ │  Tracker │  │   │
│  │  │ Service   │ │ Service  │ │ Service  │ │ Service  │ │ Service  │  │   │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘  │   │
│  │  • 广告主管理   • 竞价引擎    • 排序引擎    • 计费结算    • 归因追踪     │   │
│  │  • 预算控制     • RTB 协议    • 特征工程    • 发票管理    • 反欺诈      │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                              │                                              │
│                              ▼                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  Layer 3: 核心引擎层 (Core Engines)                                  │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │   │
│  │  │  Recall      │  │  Ranking     │  │  Rerank      │              │   │
│  │  │  Engine      │  │  Engine      │  │  Engine      │              │   │
│  │  └──────────────┘  └──────────────┘  └──────────────┘              │   │
│  │  • 多路召回      • DeepFM/DIN     • MMR 多样性                        │   │
│  │  • 向量召回      • Two-Tower      • 业务规则                             │   │
│  │  • 规则召回      • MMOE/PLE      • 广告插卡                               │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                              │                                              │
│                              ▼                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  Layer 4: 数据层 (Data Platform)                                     │   │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐  │   │
│  │  │  Redis   │ │  MySQL   │ │  Kafka   │ │  ES      │ │  ClickH. │  │   │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘  │   │
│  │  • 实时特征   • 元数据存储   • 事件流     • 搜索/日志   • 数仓分析    │   │
│  │  • 缓存       • 预算账户     • 消息队列   • 全文检索     • BI 报表     │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                              │                                              │
│                              ▼                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  Layer 5: 可观测性 (Observability)                                   │   │
│  │  • OTel Collector → Prometheus + Tempo + Loki                       │   │
│  │  • Grafana Dashboard + Alerting                                    │   │
│  │  • 告警: PagerDuty / Slack / Email                                 │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  Layer 6: 基础设施 (Infrastructure)                                  │   │
│  │  • Kubernetes (EKS/GKE) / Docker Swarm                               │   │
│  │  • Terraform / Ansible 基础设施即代码                                   │   │
│  │  • CI/CD: GitHub Actions / ArgoCD                                   │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 第二部分：请求链路时序图

### 广告展示完整链路

```
┌──────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐
│ 用户  │     │  API GW  │     │ Bidder   │     │ Ranker   │     │ 展示层   │
└──┬───┘     └────┬─────┘     └────┬─────┘     └────┬─────┘     └────┬───┘
   │              │                │                │                │
   │  1. 请求页面  │                │                │                │
   │─────────────►│                │                │                │
   │              │  2. 提取上下文  │                │                │
   │              │───────────────►│                │                │
   │              │                │  3. 召回候选   │                │
   │              │                │───────────────►│                │
   │              │                │                │  4. 粗排 Top 200│
   │              │                │                │◄───────────────│
   │              │                │                │  5. 精排 Top 50 │
   │              │                │                │◄───────────────│
   │              │                │                │  6. 重排 Top 10 │
   │              │                │                │◄───────────────│
   │              │                │  7. 竞价决策   │                │
   │              │                │◄───────────────│                │
   │              │                │  8. 出价       │                │
   │              │                │───────────────►│                │
   │              │                │                │  9. 排序结果   │
   │              │                │                │◄───────────────│
   │              │  10. 返回广告  │                │                │
   │              │◄───────────────│                │                │
   │  11. 渲染页面│                │                │                │
   │◄─────────────│                │                │                │
   │              │                │                │                │
   │  12. 曝光事件│                │                │                │
   │─────────────►│  13. 写 Kafka  │                │                │
   │              │───────────────►│                │                │
   │              │                │  14. 更新预算  │                │
   │              │                │───────────────►│                │
   │              │                │                │  15. 计费      │
   │              │                │                │◄───────────────│
   │              │                │                │                │
   │  16. 点击事件│                │                │                │
   │─────────────►│  17. 写 Kafka  │                │                │
   │              │───────────────►│                │                │
   │              │                │  18. 归因      │                │
   │              │                │───────────────►│                │
   │              │                │                │  19. 更新转化  │
   │              │                │                │◄───────────────│
```

### 关键延迟预算

| 阶段 | 延迟预算 | 实际目标 |
|------|---------|---------|
| API Gateway | 5ms | < 2ms |
| 上下文提取 | 10ms | < 5ms |
| 召回 | 50ms | < 30ms |
| 粗排 | 20ms | < 10ms |
| 精排 | 50ms | < 30ms |
| 重排 | 10ms | < 5ms |
| 竞价决策 | 20ms | < 10ms |
| **总延迟** | **165ms** | **< 90ms** |

---

## 第三部分：数据流架构

### 实时数据流

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              实时数据流                                       │
│                                                                             │
│  用户行为事件流：                                                              │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐              │
│  │  Impression│───►│  Click   │───►│  Conversion│───►│  Purchase │              │
│  │  Event    │    │  Event   │    │  Event   │    │  Event   │              │
│  └──────────┘    └──────────┘    └──────────┘    └──────────┘              │
│       │               │               │               │                      │
│       ▼               ▼               ▼               ▼                      │
│  ┌─────────────────────────────────────────────────────────────┐             │
│  │                    Kafka Topics                              │             │
│  │  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐         │             │
│  │  │ impressions  │ │  clicks      │ │ conversions   │         │             │
│  │  │  (partition  │ │  (partition  │ │  (partition   │         │             │
│  │  │   by camp_id)│ │   by camp_id)│ │   by user_id)│         │             │
│  │  └──────────────┘ └──────────────┘ └──────────────┘         │             │
│  └─────────────────────────────────────────────────────────────┘             │
│       │               │               │                                       │
│       ▼               ▼               ▼                                       │
│  ┌─────────────────────────────────────────────────────────────┐             │
│  │                  Flink Jobs                                  │             │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │             │
│  │  │ Real-time    │  │ Feature      │  │ Fraud        │      │             │
│  │  │ Aggregation  │  │ Engineering  │  │ Detection    │      │             │
│  │  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘      │             │
│  │         │                 │                 │               │             │
│  │         ▼                 ▼                 ▼               │             │
│  │  ┌─────────────────────────────────────────────────────┐    │             │
│  │  │              Redis (实时特征)                          │    │             │
│  │  └─────────────────────────────────────────────────────┘    │             │
│  └─────────────────────────────────────────────────────────────┘             │
│                                                                             │
│  广告主预算流：                                                                │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐                               │
│  │  Budget  │───►│  Spend   │───►│  Payout  │                               │
│  │  Create  │    │  Update  │    │  Report  │                               │
│  └──────────┘    └──────────┘    └──────────┘                               │
│       │               │               │                                      │
│       ▼               ▼               ▼                                      │
│  ┌─────────────────────────────────────────────────────────────┐             │
│  │                    MySQL (预算账户)                            │             │
│  │  ┌────────────┐  ┌────────────┐  ┌────────────┐            │             │
│  │  │ campaigns  │  │ budgets    │  │ payouts    │            │             │
│  │  └────────────┘  └────────────┘  └────────────┘            │             │
│  └─────────────────────────────────────────────────────────────┘             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 离线数据流

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              离线数据流                                       │
│                                                                             │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐              │
│  │  Kafka   │───►│  Flink   │───►│  HDFS    │───►│  ClickH. │              │
│  │  (实时)   │    │ (流处理)  │    │ (数据湖)  │    │ (数仓)   │              │
│  └──────────┘    └──────────┘    └──────────┘    └──────────┘              │
│       │               │               │               │                      │
│       ▼               ▼               ▼               ▼                      │
│  ┌─────────────────────────────────────────────────────────────┐             │
│  │                  分析应用                                     │             │
│  │  ┌────────────┐  ┌────────────┐  ┌────────────┐            │             │
│  │  │ BI 报表     │  │ 归因分析    │  │ 模型训练    │            │             │
│  │  │ (Grafana)  │  │ (MTA/TTA)  │  │ (TabPFN)   │            │             │
│  │  └────────────┘  └────────────┘  └────────────┘            │             │
│  └─────────────────────────────────────────────────────────────┘             │
│                                                                             │
│  数据分层：                                                                  │
│  ODS (原始数据) → DWD (明细数据) → DWS (汇总数据) → ADS (应用数据)           │
│                                                                             │
│  表设计：                                                                    │
│  • ads_impression_daily (日曝光汇总表)                                       │
│  • ads_click_daily (日点击汇总表)                                            │
│  • ads_conversion_daily (日转化汇总表)                                       │
│  • ads_budget_daily (日预算消耗表)                                           │
│  • ads_creative_daily (日创意表现表)                                         │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 第四部分：组件部署架构

### Kubernetes 部署图

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Kubernetes Cluster                                   │
│                                                                             │
│  Namespace: ad-platform                                                     │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  Pod Group: api-gateway (3 replicas)                                │   │
│  │  • Envoy Sidecar (mTLS, rate limit)                                 │   │
│  │  • HPA: CPU > 70% → scale to 10 pods                               │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  Pod Group: bidder-service (5 replicas)                             │   │
│  │  • Go microservice + Redis cache                                   │   │
│  │  • HPA: QPS > 5000 → scale to 20 pods                              │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  Pod Group: ranker-service (5 replicas)                             │   │
│  │  • Python TF Serving + Go wrapper                                   │   │
│  │  • HPA: Latency P99 > 50ms → scale to 15 pods                       │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  Pod Group: tracker-service (3 replicas)                            │   │
│  │  • Go microservice + Kafka producer                                 │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  Pod Group: data-pipeline (2 replicas)                              │   │
│  │  • Flink JobManager + TaskManager                                   │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  Services:                                                                  │
│  • ad-api (ClusterIP) → api-gateway pods                                   │
│  • ad-bidder (ClusterIP) → bidder-service pods                             │
│  • ad-ranker (ClusterIP) → ranker-service pods                             │
│  • ad-tracker (ClusterIP) → tracker-service pods                           │
│                                                                             │
│  External:                                                                  │
│  • LoadBalancer → ad-api (external IP)                                     │
│  • Ingress (nginx-ingress) → HTTPS termination                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 服务网格 (Istio)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Istio Service Mesh                                   │
│                                                                             │
│  Traffic Management:                                                         │
│  ┌────────────┐    ┌────────────┐    ┌────────────┐                        │
│  │ Canary     │    │ Blue/Green │    │ A/B Test   │                        │
│  │ Deployment │    │ Deployment │    │ Deployment │                        │
│  └────────────┘    └────────────┘    └────────────┘                        │
│       │                   │                   │                             │
│       ▼                   ▼                   ▼                             │
│  ┌─────────────────────────────────────────────────────────────┐            │
│  │              VirtualService + DestinationRule                │            │
│  │  • Weight-based routing (90% stable, 10% canary)            │            │
│  │  • Circuit breaker (max_connections=100, timeout=5s)        │            │
│  │  • Retry (3 attempts, backoff 100ms)                        │            │
│  │  • Timeout (per route: 500ms)                               │            │
│  └─────────────────────────────────────────────────────────────┘            │
│                                                                             │
│  Observability:                                                              │
│  • Kiali: 服务拓扑可视化                                                      │
│  • Jaeger: 分布式追踪                                                        │
│  • Prometheus: 指标采集                                                       │
│  • Grafana: 仪表盘                                                           │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 第五部分：数据库架构

### 存储选型矩阵

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          存储选型矩阵                                         │
│                                                                             │
│  ┌──────────────┬──────────┬──────────┬──────────┬──────────┬──────────┐   │
│  │   数据类型    │  选择     │  原因     │  规模    │  读写比  │  一致性  │   │
│  ├──────────────┼──────────┼──────────┼──────────┼──────────┼──────────┤   │
│  │ 用户/广告主   │ MySQL    │ 事务支持  │ 100M 行  │ 10:1     │ Strong   │   │
│  │ 预算/账户     │ MySQL    │ ACID      │ 10M 行   │ 5:1      │ Strong   │   │
│  │ 实时特征      │ Redis    │ 低延迟     │ 100M KV  │ 100:1    │ Eventual│   │
│  │ 缓存/Session  │ Redis    │ 高性能     │ 10M KV   │ 1000:1   │ Eventual│   │
│  │ 事件流        │ Kafka    │ 高吞吐     │ 100M msg │ 10:1     │ At-least│   │
│  │ 搜索/日志     │ ES       │ 全文检索   │ 10B 文档 │ 5:1      │ Near     │   │
│  │ 广告素材      │ MinIO    │ 对象存储   │ 100TB    │ 100:1    │ Strong   │   │
│  │ 数仓/BI       │ ClickH.  │ 列式存储   │ 100B 行  │ 1000:1   │ Eventual│   │
│  │ 向量检索      │ FAISS    │ 向量搜索   │ 10M vec  │ 100:1    │ Strong   │   │
│  │ 元数据        │ TiKV     │ 分布式 KV  │ 1B 行    │ 10:1     │ Strong   │   │
│  └──────────────┴──────────┴──────────┴──────────┴──────────┴──────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
```

### MySQL 分库分表策略

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         MySQL 分库分表                                       │
│                                                                             │
│  分库策略:                                                                   │
│  • 按 campaign_id hash (16 个分片)                                           │
│  • 每个分片: campaigns 表 + budget 表 + creative 表                          │
│                                                                             │
│  分表策略:                                                                   │
│  • impressions 表: 按月分区 (PARTITION BY RANGE)                             │
│  • clicks 表: 按月分区                                                       │
│  • conversions 表: 按季度分区                                                │
│                                                                             │
│  读写分离:                                                                   │
│  • Master: 写操作 (预算扣减、事件记录)                                        │
│  • Slave x3: 读操作 (报表、归因分析)                                         │
│                                                                             │
│  连接池:                                                                     │
│  • max_idle: 10                                                            │
│  • max_open: 100                                                           │
│  • max_lifetime: 5min                                                      │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 第六部分：高可用架构

### 容灾设计

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         多活容灾架构                                         │
│                                                                             │
│  区域分布:                                                                   │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐                    │
│  │ 华东 (杭州)  │    │ 华南 (广州)  │    │ 华北 (北京)  │                    │
│  │  Primary    │    │  Secondary  │    │  DR         │                    │
│  └─────────────┘    └─────────────┘    └─────────────┘                    │
│       │                   │                   │                              │
│       ▼                   ▼                   ▼                              │
│  ┌─────────────────────────────────────────────────────────────┐            │
│  │                   全局流量管理 (GTM)                          │            │
│  │  • DNS 轮询 / GeoDNS                                          │            │
│  │  • 健康检查 (每 10s)                                          │            │
│  │  • 故障自动切换 (< 30s)                                       │            │
│  └─────────────────────────────────────────────────────────────┘            │
│                                                                             │
│  数据同步:                                                                   │
│  • MySQL: binlog 异步同步 (延迟 < 1s)                                       │
│  • Redis: 主从复制 (RDB + AOF)                                             │
│  • Kafka: MirrorMaker 跨机房同步                                           │
│  • ClickHouse: ReplicatedMergeTree 跨机房                                   │
│                                                                             │
│  降级策略:                                                                   │
│  • 排序降级: DeepFM → LR (延迟 < 10ms)                                     │
│  • 召回降级: 向量召回 → 规则召回                                            │
│  • 计费降级: 实时扣费 → 离线扣费                                            │
│  • 归因降级: MTA → Last Click                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 第七部分：安全架构

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         安全架构                                             │
│                                                                             │
│  身份认证:                                                                   │
│  • OAuth 2.0 / JWT 广告主登录                                                │
│  • mTLS 服务间通信                                                          │
│  • RBAC 权限控制 (广告主/代理商/管理员)                                      │
│                                                                             │
│  数据安全:                                                                   │
│  • 敏感数据加密 (AES-256): 用户 PII、支付信息                                │
│  • 传输加密: HTTPS (TLS 1.3)                                               │
│  • 密钥管理: AWS KMS / HashiCorp Vault                                     │
│                                                                             │
│  网络安全:                                                                   │
│  • WAF (Web Application Firewall)                                          │
│  • DDoS 防护 (Cloudflare / AWS Shield)                                     │
│  • 安全组 / VPC 隔离                                                       │
│                                                                             │
│  合规:                                                                       │
│  • GDPR (欧洲用户数据)                                                       │
│  • CCPA (加州隐私法)                                                        │
│  • IAB TCF (广告透明度)                                                     │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 第八部分：成本估算

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         月度成本估算                                         │
│                                                                             │
│  基础设施:                                                                   │
│  • Kubernetes (EKS): $5,000/mo (100 节点)                                   │
│  • RDS (MySQL): $3,000/mo (3 实例)                                         │
│  • ElastiCache (Redis): $2,000/mo (3 节点)                                 │
│  • MSK (Kafka): $4,000/mo (3 AZ)                                           │
│  • OpenSearch (ES): $3,000/mo (3 节点)                                     │
│  • ClickHouse Cloud: $5,000/mo                                             │
│  • S3/MinIO: $1,000/mo                                                     │
│  ──────────────────────────────────────────────────────────────────────     │
│  小计: $23,000/mo                                                           │
│                                                                             │
│  网络:                                                                       │
│  • Load Balancer: $500/mo                                                   │
│  • CDN (CloudFront): $2,000/mo                                             │
│  • Data Transfer: $1,500/mo                                                │
│  ──────────────────────────────────────────────────────────────────────     │
│  小计: $4,000/mo                                                            │
│                                                                             │
│  可观测性:                                                                  │
│  • Prometheus (Managed): $1,000/mo                                         │
│  • Grafana Cloud: $500/mo                                                  │
│  • Tempo (Jaeger): $500/mo                                                 │
│  • Loki: $300/mo                                                           │
│  ──────────────────────────────────────────────────────────────────────     │
│  小计: $2,300/mo                                                            │
│                                                                             │
│  总计: ~$29,300/mo (~$350K/yr)                                             │
│                                                                             │
│  优化建议:                                                                   │
│  • 使用 Spot Instances: 节省 60-90%                                         │
│  • 使用 Reserved Instances: 节省 30-40%                                    │
│  • 数据分层存储: 热/温/冷                                                     │
│  • 自动扩缩容: HPA + VPA                                                   │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 第九部分：关键性能指标

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         性能指标体系                                         │
│                                                                             │
│  系统指标:                                                                   │
│  • QPS: 100K+                                                               │
│  • P99 延迟: < 90ms                                                         │
│  • 可用性: 99.99%                                                           │
│  • 错误率: < 0.1%                                                           │
│                                                                             │
│  业务指标:                                                                   │
│  • CTR: 行业平均 1-3%                                                       │
│  • CVR: 行业平均 2-5%                                                       │
│  • CPA: 目标 < $10                                                          │
│  • ROAS: 目标 > 3.0                                                         │
│  • Fill Rate: > 95%                                                        │
│                                                                             │
│  广告主指标:                                                                 │
│  • 预算消耗率: 80-95%                                                       │
│  • 投放覆盖率: > 90%                                                        │
│  • 创意通过率: > 95%                                                        │
│                                                                             │
│  数据指标:                                                                   │
│  • 数据延迟: < 5s (实时)                                                    │
│  • 数据准确性: > 99.9%                                                      │
│  • 归因准确率: > 85%                                                        │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 第十部分：技术栈总览

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         技术栈总览                                           │
│                                                                             │
│  语言:                                                                       │
│  • Go: 核心服务 (Bidder/Ranker/Tracker)                                     │
│  • Python: ML 服务 (Ranking Model)                                          │
│  • Rust: TiKV (存储引擎)                                                    │
│  • Java: Flink (流处理)                                                     │
│  • TypeScript: 前端 (广告管理平台)                                            │
│                                                                             │
│  框架:                                                                       │
│  • Gin/Echo: HTTP 框架                                                      │
│  • gRPC: 服务间通信                                                          │
│  • React/Next.js: 前端                                                      │
│  • TensorFlow/PyTorch: ML 模型                                               │
│                                                                             │
│  基础设施:                                                                   │
│  • Kubernetes: 容器编排                                                      │
│  • Istio: 服务网格                                                          │
│  • Terraform: IaC                                                          │
│  • ArgoCD: GitOps                                                          │
│                                                                             │
│  数据:                                                                       │
│  • MySQL: 关系型存储                                                         │
│  • Redis: 缓存/实时特征                                                       │
│  • Kafka: 消息队列                                                           │
│  • ClickHouse: 数仓                                                         │
│  • Elasticsearch: 搜索/日志                                                   │
│  • MinIO: 对象存储                                                           │
│                                                                             │
│  可观测性:                                                                   │
│  • OpenTelemetry: 遥测数据采集                                                │
│  • Prometheus: 指标                                                         │
│  • Grafana: 可视化                                                          │
│  • Tempo: 链路追踪                                                           │
│  • Loki: 日志聚合                                                            │
│                                                                             │
│  CI/CD:                                                                      │
│  • GitHub Actions: 构建/测试/部署                                             │
│  • Docker: 容器化                                                           │
│  • Helm: Kubernetes 包管理                                                  │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 第十一部分：自测题

### Q1: 广告竞价系统如何保证 P99 延迟 < 90ms？

**A**:
1. **并行召回**：多路召回并行执行，取最快结果
2. **特征缓存**：用户/广告特征从 Redis 读取（< 1ms）
3. **模型优化**：TensorRT 量化，推理 < 10ms
4. **连接池**：DB/Redis 连接池复用
5. **本地缓存**：热点数据 L1 缓存（sync.Map）
6. **超时控制**：每层设置超时，快速失败

### Q2: 如何实现广告预算的实时扣减？

**A**:
1. **Redis Lua 脚本**：原子扣减预算（SETNX + DECRBY）
2. **异步落盘**：扣减成功后异步写入 MySQL
3. **补偿机制**：对账任务发现不一致时回滚
4. **分片预算**：按 campaign_id hash 分散到不同 Redis 实例

### Q3: 如何防止广告刷量（Fraud Detection）？

**A**:
1. **实时检测**：Flink 流处理，规则引擎（同 IP 短时间内多次点击 → 拦截）
2. **机器学习**：孤立森林/随机森林识别异常行为
3. **设备指纹**：Browser fingerprint + Device ID
4. **IP 黑名单**：已知数据中心/代理 IP 过滤
5. **后审**：归因分析发现异常转化模式

---

## 第十一部分：生产级 Go 代码实现

### 1. 竞价引擎核心（Bidder Service）

```go
package bidder

import (
	"context"
	"fmt"
	"sync"
	"time"

	"ad-platform/bidder/recall"
	"ad-platform/bidder/rank"
	"ad-platform/common/cache"
	"ad-platform/common/metrics"
)

// BidRequest 竞价请求 - RTB OpenRTB 2.6 标准格式
type BidRequest struct {
	Impressions []Impression `json:"imp"`
	User        User         `json:"user"`
	Device      Device       `json:"device"`
	AdSlot      AdSlot       `json:"adslot"`
	Timestamp   time.Time    `json:"tstamp"`
	TraceID     string       `json:"trace_id"`
}

type Impression struct {
	ID      string  `json:"id"`
	Width   int     `json:"w"`
	Height  int     `json:"h"`
	BidFloor float64 `json:"bidfloor"` // 底价
}

type User struct {
	ID      string   `json:"id"`
	Keywords []string `json:"keywords"`
	Demographics Demographics `json:"demographics"`
}

type Demographics struct {
	Age  int `json:"age"`
	Gender string `json:"gender"` // M/F/Unknown
}

type Device struct {
	IP      string `json:"ip"`
	UserAgent string `json:"ua"`
	DeviceID string `json:"did"`
}

type AdSlot struct {
	ID          string   `json:"id"`
	PlacementID string   `json:"placement_id"`
	Formats     []string `json:"formats"`     // ["banner","video","native"]
	PublisherID string   `json:"publisher_id"`
}

// BidResponse 竞价响应
type BidResponse struct {
	BidID       string           `json:"bid_id"`
	CreativeIDs []string         `json:"crid"`
	Bids        []Bid            `json:"bids"`
	TraceID     string           `json:"trace_id"`
	LatencyMs   int64            `json:"latency_ms"`
}

type Bid struct {
	ImpID    string  `json:"impid"`
	CreativeID string `json:"crid"`
	BidPrice float64 `json:"price"` // 出价（CPC/CPM）
	eCPM     float64 `json:"-"`     // 内部计算 eCPM
}

// BidderService 竞价服务 - 核心入口点
type BidderService struct {
	recallEngine recall.Engine    // 召回引擎
	ranker       rank.Ranker      // 排序引擎
	budgetMgr    *BudgetManager   // 预算管理器
	freqCtrl     *FreqController  // 频次控制
	cache        cache.Cache      // Redis 缓存
	metrics      *metrics.Collector
}

func NewBidderService(
	re recall.Engine,
	rk rank.Ranker,
	bm *BudgetManager,
	fc *FreqController,
	c cache.Cache,
	m *metrics.Collector,
) *BidderService {
	return &BidderService{
		recallEngine: re,
		ranker:       rk,
		budgetMgr:    bm,
		freqCtrl:     fc,
		cache:        c,
		metrics:      m,
	}
}

// Bid 处理一次竞价请求 - P99 < 90ms 的关键路径
func (s *BidderService) Bid(ctx context.Context, req *BidRequest) (*BidResponse, error) {
	start := time.Now()
	traceID := req.TraceID

	// Step 1: 并行召回（6路并行，取Top-K）
	recallCtx, cancel := context.WithTimeout(ctx, 30*time.Millisecond)
	defer cancel()

	candidates := s.recallEngine.ParallelRecall(recallCtx, req) // 返回 ~500 条候选广告

	// Step 2: 频次过滤 + 预算过滤
	candidates = s.freqCtrl.Filter(recallCtx, candidates, req.User.ID)
	candidates = s.budgetMgr.Filter(candidates)

	if len(candidates) == 0 {
		return &BidResponse{TraceID: traceID, LatencyMs: time.Since(start).Milliseconds()}, nil
	}

	// Step 3: 特征获取 + 排序（TensorRT 推理 < 10ms）
	features := s.fetchFeatures(ctx, candidates, req)
	scored := s.ranker.ScoreBatch(features) // DeepFM/DIN 批量推理

	// Step 4: 重排（多样性 + 去重 + 业务规则）
	final := s.ranker.Rerank(scored, req.AdSlot)

	// Step 5: 生成竞价响应
	bids := make([]Bid, 0, len(final))
	for _, c := range final {
		bids = append(bids, Bid{
			ImpID:      req.Impressions[0].ID,
			CreativeID: c.CreativeID,
			BidPrice:   c.BidPrice,
			eCPM:       c.eCPM,
		})
	}

	latency := time.Since(start).Milliseconds()
	s.metrics.ObserveBidLatency(latency, traceID)

	return &BidResponse{
		BidID:     fmt.Sprintf("bid_%s_%d", traceID, start.UnixNano()),
		CreativeIDs: finalIDs(final),
		Bids:      bids,
		TraceID:   traceID,
		LatencyMs: latency,
	}, nil
}

// fetchFeatures 批量获取用户+广告特征（Redis Pipeline 优化）
func (s *BidderService) fetchFeatures(ctx context.Context, ads []recall.Candidate, req *BidRequest) []rank.FeatureVector {
	var mu sync.Mutex
	features := make([]rank.FeatureVector, 0, len(ads))

	// Pipeline 方式批量读取：用户特征 1 次 + 广告特征 N 次
	userKey := fmt.Sprintf("user:feat:%s", req.User.ID)
	userFeat, _ := s.cache.GetPipeline(ctx, userKey)

	for _, ad := range ads {
		adKey := fmt.Sprintf("ad:feat:%s", ad.AdID)
		adFeat, _ := s.cache.GetPipeline(ctx, adKey)

		mu.Lock()
		features = append(features, rank.MergeFeatures(userFeat, adFeat))
		mu.Unlock()
	}
	return features
}

func finalIDs(ads []rank.ScoredCandidate) []string {
	ids := make([]string, len(ads))
	for i, a := range ads {
		ids[i] = a.CreativeID
	}
	return ids
}
```

### 2. 预算原子扣减（Redis Lua + 异步落盘）

```go
package bidder

import (
	"context"
	"fmt"

	"ad-platform/common/cache"
)

const budgetLuaScript = `
-- KEYS[1] = budget:key (如 "budget:camp_12345")
-- ARGV[1] = amount (本次消耗，单位：分)
-- ARGV[2] = total_budget (总预算，单位：分)

local current = tonumber(redis.call('GET', KEYS[1]) or "0")
local remaining = tonumber(ARGV[2]) - current

if remaining < tonumber(ARGV[1]) then
    return {0, remaining}  -- 预算不足
end

redis.call('INCRBY', KEYS[1], ARGV[1])
return {1, remaining - tonumber(ARGV[1])}
`

// BudgetManager 预算管理器 - 保证原子性 + 最终一致性
type BudgetManager struct {
	redis   cache.Cache
	channel chan budgetOp // 异步落盘通道
	done    chan struct{}
}

type budgetOp struct {
	campaignID string
	amount     int64 // 单位：分
	timestamp  time.Time
}

func NewBudgetManager(redis cache.Cache) *BudgetManager {
	bm := &BudgetManager{
		redis:   redis,
		channel: make(chan budgetOp, 10000), // 10K buffer
		done:    make(chan struct{}),
	}
	go bm.flushLoop() // 后台 goroutine 异步写入 MySQL
	return bm
}

func (bm *BudgetManager) CheckAndDeduct(campID string, amount int64, totalBudget int64) (bool, int64, error) {
	key := fmt.Sprintf("budget:%s", campID)
	result, err := bm.redis.Eval(context.Background(), budgetLuaScript, []string{key}, fmt.Sprintf("%d", amount), fmt.Sprintf("%d", totalBudget))
	if err != nil {
		return false, 0, err
	}

	res := result.([]interface{})
	allowed := int(res[0].(int64))
	remaining := int(res[1].(int64))

	if allowed == 1 {
		// 异步落盘：写入 channel，不阻塞竞价主流程
		select {
		case bm.channel <- budgetOp{
			campaignID: campID,
			amount:     amount,
			timestamp:  time.Now(),
		}:
		default:
			// channel 满了，降级为同步写入（极端情况）
			bm.flushSync(campID, amount)
		}
	}

	return allowed == 1, int64(remaining), nil
}

// flushLoop 异步刷盘 - 批量写入 MySQL
func (bm *BudgetManager) flushLoop() {
	const batchSize = 500
	const flushInterval = 100 * time.Millisecond

	ticker := time.NewTicker(flushInterval)
	defer ticker.Stop()

	var ops []budgetOp

	for {
		select {
		case op := <-bm.channel:
			ops = append(ops, op)
			if len(ops) >= batchSize {
				bm.flushBatch(ops)
				ops = ops[:0]
			}
		case <-ticker.C:
			if len(ops) > 0 {
				bm.flushBatch(ops)
				ops = ops[:0]
			}
		case <-bm.done:
			bm.flushBatch(ops) // 关闭前刷新剩余
			return
		}
	}
}

func (bm *BudgetManager) flushBatch(ops []budgetOp) {
	// 批量 INSERT ... ON DUPLICATE KEY UPDATE
	// SQL: INSERT INTO campaign_budget (campaign_id, spent, updated_at)
	//      VALUES (?, ?, NOW()) ON DUPLICATE KEY UPDATE spent = spent + VALUES(spent)
	// ... 实际实现省略
}
```

### 3. 多路召回并行引擎

```go
package recall

import (
	"context"
	"sort"
	"sync"
)

// Engine 召回引擎接口
type Engine interface {
	ParallelRecall(ctx context.Context, req *BidRequest) []Candidate
}

// Candidate 召回候选广告
type Candidate struct {
	AdID       string
	CreativeID string
	BidPrice   float64
	Source     string // "vector"/"rule"/"retention"/"hot"/"geo"/"context"
	Score      float64
}

// MultiPathRecall 多路召回实现 - 6路并行
type MultiPathRecall struct {
	pathways []Pathway
	topK     int // 最终输出 Top-K
}

type Pathway interface {
	Name() string
	Recall(ctx context.Context, req *BidRequest) ([]Candidate, error)
}

func NewMultiPathRecall(paths []Pathway, topK int) *MultiPathRecall {
	return &MultiPathRecall{pathways: paths, topK: topK}
}

// ParallelRecall 6路并行召回，合并后取 Top-K
func (m *MultiPathRecall) ParallelRecall(ctx context.Context, req *BidRequest) []Candidate {
	var wg sync.WaitGroup
	results := make([][]Candidate, len(m.pathways))

	// 每路独立 goroutine，互不阻塞
	for i, pw := range m.pathways {
		wg.Add(1)
		go func(idx int, pathway Pathway) {
			defer wg.Done()
			cands, err := pathway.Recall(ctx, req)
			if err != nil {
				// 单路失败不影响其他路
				return
			}
			results[idx] = cands
		}(i, pw)
	}

	wg.Wait()

	// 合并所有路的候选集
	all := make([]Candidate, 0, m.topK*len(m.pathways))
	for _, r := range results {
		all = append(all, r...)
	}

	// 按 eCPM 降序排序，取 Top-K
	sort.Slice(all, func(i, j int) bool {
		return all[i].Score > all[j].Score
	})

	if len(all) > m.topK {
		all = all[:m.topK]
	}

	return all
}
```

---

## 第十二部分：演进路线

```
Phase 1 (MVP):
├── 单体架构 (Go + MySQL + Redis)
├── 基础竞价 + 排序
├── 简单归因 (Last Click)
└── 基本监控 (Prometheus + Grafana)

Phase 2 (Scale):
├── 微服务拆分 (Bidder/Ranker/Tracker)
├── Kafka 事件流
├── ClickHouse 数仓
├── 向量召回 (FAISS)
└── 分布式追踪 (OTel + Tempo)

Phase 3 (Intelligence):
├── 深度学习排序 (DeepFM/DIN)
├── 多目标优化 (MMOE/PLE)
├── 实时特征 (Flink + Redis)
├── 强化学习竞价
└── A/B 测试平台

Phase 4 (Enterprise):
├── 多活容灾 (3 区域)
├── 服务网格 (Istio)
├── 混沌工程 (Chaos Mesh)
├── 自动化扩缩容 (KEDA)
└── 成本优化 (Spot + Reserved)
```
## 自测题

### Q1: 本模块的核心设计要点是什么？

<details><summary>点击查看答案</summary>
核心设计遵循高内聚低耦合原则，包含接口层、业务层、数据层和服务层，通过定义明确的接口进行通信。
</details>

### Q2: 生产环境下需要注意的关键运维事项有哪些？

<details><summary>点击查看答案</summary>
关键运维包括：监控告警、容量规划、备份恢复、灰度发布、性能调优和故障预案。建议使用 Prometheus + Grafana 构建完整监控体系。
</details>

### Q3: 请提供一个相关的 Go 语言生产级实现示例

<details><summary>点击查看答案</summary>
```go
package main
import "fmt"
func main() {
    fmt.Println("Go 生产级代码示例")
}
```
</details>
