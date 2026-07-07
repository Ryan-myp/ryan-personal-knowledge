# 广告平台系统架构设计

## 一、系统概述

### 1.1 业务背景

中型电商广告平台，日 GMV 500 万，需要支持多平台广告投放（Google Ads、Meta、TikTok、DV360），实时竞价，智能优化。

**核心需求：**
- 多平台广告统一管理
- 实时竞价（<50ms）
- 智能出价优化
- 跨渠道归因分析
- 高并发（10 万 QPS 峰值）

### 1.2 技术栈

| 层级 | 技术选型 | 说明 |
|------|----------|------|
| API 网关 | Kong + Go | 统一入口，鉴权限流 |
| 微服务 | Go gRPC | 高性能服务通信 |
| 服务发现 | Consul | 服务注册发现 |
| 熔断器 | Go | 自定义实现 |
| 消息队列 | Kafka | 异步解耦 |
| 实时计算 | Flink | 实时竞价 |
| OLAP | ClickHouse | 广告分析 |
| 搜索引擎 | Elasticsearch | 商品搜索 |
| 缓存 | Redis | 用户画像缓存 |
| 容器化 | Docker + K8s | 部署编排 |

## 二、架构设计

### 2.1 系统架构图

```
┌─────────────────────────────────────────────────────────────┐
│                        Client (Web/Mobile)                   │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    API Gateway (Kong)                        │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌─────────────┐ │
│  │  鉴权     │  │  限流     │  │  路由     │  │  日志       │ │
│  │ (JWT)    │  │(令牌桶)   │  │(Consul)  │  │(OpenTelem.) │ │
│  └──────────┘  └──────────┘  └──────────┘  └─────────────┘ │
└─────────────────────────────────────────────────────────────┘
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
┌──────────────────┐ ┌──────────────────┐ ┌──────────────────┐
│  User Profile    │ │   Bidding        │ │   Creative       │
│   Service        │ │   Service        │ │   Service        │
│                  │ │                  │ │                  │
│ - Redis 缓存      │ │ - Flink 实时     │ │ - 向量检索        │
│ - 用户画像        │ │ - 竞价引擎       │ │ - AI 创意生成     │
└──────────────────┘ └──────────────────┘ └──────────────────┘
              │               │               │
              ▼               ▼               ▼
┌─────────────────────────────────────────────────────────────┐
│                    Ad Integration Layer                      │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌─────────────┐ │
│  │ Google   │  │ Meta     │  │ TikTok   │  │ DV360       │ │
│  │ Ads API  │  │ API      │  │ API      │  │ API         │ │
│  └──────────┘  └──────────┘  └──────────┘  └─────────────┘ │
└─────────────────────────────────────────────────────────────┘
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
┌──────────────────┐ ┌──────────────────┐ ┌──────────────────┐
│   Kafka          │ │   Flink          │ │   ClickHouse     │
│   (消息队列)      │ │   (实时计算)      │ │   (OLAP 分析)     │
└──────────────────┘ └──────────────────┘ └──────────────────┘
```

### 2.2 数据流

```
1. 广告请求流:
   Client → Gateway → User Profile → Bidding → Creative → Response
   (鉴权)   (缓存)     (竞价)        (匹配)    (<50ms)

2. 数据上报流:
   Ad Impression/Click → Kafka → Flink → ClickHouse
   (实时)    (缓冲)    (计算)    (分析)

3. 投放管理流:
   Campaign Config → Ad Integrations → Platform APIs
   (配置)    (Saga)      (Google/Meta/TikTok/DV360)
```

## 三、核心模块设计

### 3.1 API 网关

**职责：**
- 统一入口
- 鉴权 (JWT)
- 限流 (令牌桶)
- 路由转发
- 日志监控

**关键技术：**
- Go net/http 反向代理
- 令牌桶限流算法
- JWT 鉴权中间件
- OpenTelemetry 分布式追踪

### 3.2 用户画像服务

**职责：**
- 用户兴趣分析
- 用户行为追踪
- 个性化推荐

**关键技术：**
- Redis 缓存 (TTL 30min)
- ClickHouse 存储行为数据
- Elasticsearch 用户搜索

### 3.3 竞价服务

**职责：**
- 实时竞价计算
- CTR/CVR 预测
- 出价策略优化

**关键技术：**
- Flink 实时计算
- 机器学习模型 (CTR 预测)
- 智能出价 (Target CPA/ROAS)

### 3.4 创意服务

**职责：**
- 创意素材管理
- 创意匹配
- A/B 测试

**关键技术：**
- 向量检索 (Milvus)
- AI 创意生成
- 多臂老虎机算法

### 3.5 广告平台集成

**职责：**
- Google Ads API
- Meta Marketing API
- TikTok Marketing API
- DV360 API

**关键技术：**
- OAuth2 认证
- 批量操作
- 错误重试
- 速率限制

## 四、部署架构

### 4.1 容器编排

```yaml
# docker-compose.yml
version: '3.8'
services:
  gateway:
    build: ./gateway
    ports: ["8080:8080"]
    depends_on: [consul, redis]
    
  user-profile:
    build: ./services/user-profile
    depends_on: [redis, clickhouse]
    
  bidding:
    build: ./services/bidding
    depends_on: [kafka, flink]
    
  creative:
    build: ./services/creative
    depends_on: [milvus, elasticsearch]
    
  # 基础设施
  consul:
    image: consul:latest
    
  redis:
    image: redis:7-alpine
    
  kafka:
    image: confluentinc/cp-kafka:latest
    
  clickhouse:
    image: clickhouse/clickhouse-server:latest
```

### 4.2 扩缩容策略

| 服务 | 初始副本 | 最大副本 | 扩缩容条件 |
|------|----------|----------|-----------|
| Gateway | 2 | 10 | CPU > 70% |
| User Profile | 2 | 5 | 内存 > 80% |
| Bidding | 4 | 20 | QPS > 5000 |
| Creative | 2 | 8 | GPU 利用率 > 70% |

## 五、性能指标

### 5.1 SLA

| 指标 | 目标值 | 说明 |
|------|--------|------|
| API 延迟 | <50ms | P99 |
| 可用性 | 99.99% | 全年停机 <52min |
| 吞吐量 | 10万 QPS | 峰值 |
| 数据延迟 | <1s | 实时分析 |

### 5.2 容量规划

```
日广告请求: 10 万次/秒 × 86400 秒 = 86.4 亿次
日数据量: 86.4 亿 × 1KB = 8.6TB/天
月存储: 8.6TB × 30 = 258TB
```

## 六、自测题

1. 系统如何保证 <50ms 的竞价延迟？
2. 如何设计跨渠道归因分析？
3. 高峰期如何保证系统稳定性？

## 七、动手验证

```bash
# 1. 启动基础设施
docker-compose up -d consul redis kafka clickhouse

# 2. 启动服务
make build
make run

# 3. 压测
wrk -t12 -c400 -d30s http://localhost:8080/api/bid

# 4. 分析数据
clickhouse-client --query "SELECT ..."
```
