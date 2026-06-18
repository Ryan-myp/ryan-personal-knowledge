# 广告系统 Fullstack 深度：Go 高并发/Redis 集群实战/K8s 生产

> 从广告系统视角，深度解析 Go 高并发编程、Redis 集群实战、K8s 生产实践

---

## 第一部分：广告系统 Go 高并发编程

### 并发模型设计

```
广告系统 Go 并发模型：
┌─────────────────────────────────────────────────────────────────────┐
│ Goroutine 池模式                                                    │
│                                                                     │
│ 主 goroutine（accept 连接）                                         │
│   │                                                                 │
│   ├── 工作池（Worker Pool）                                         │
│   │   ├── Worker 1 → 处理竞价请求                                    │
│   │   ├── Worker 2 → 处理竞价请求                                    │
│   │   └── Worker N → 处理竞价请求                                    │
│   │                                                                 │
│   ├── 定时任务（Ticker）                                            │
│   │   ├── 每 1s：更新统计指标                                       │
│   │   ├── 每 1min：清理过期数据                                     │
│   │   └── 每 1h：compact 缓存                                       │
│   │                                                                 │
│   └── 后台协程（Background）                                        │
│       ├── Kafka 生产者                                            │
│       ├── 指标上报                                                │
│       └── 健康检查                                                │
└─────────────────────────────────────────────────────────────────────┘
```

### Worker Pool 实现

```go
package pool

import (
    "context"
    "sync"
)

// Job 工作单元
type Job struct {
    ID       string
    Payload  []byte
    ResultCh chan<- Result
}

// Result 工作结果
type Result struct {
    JobID string
    Data  []byte
    Err   error
}

// WorkerPool 工作池
type WorkerPool struct {
    jobs    chan Job
    results chan Result
    workers int
    wg      sync.WaitGroup
}

// NewWorkerPool 创建工作池
func NewWorkerPool(jobs, results, workers int) *WorkerPool {
    wp := &WorkerPool{
        jobs:    make(chan Job, jobs),
        results: make(chan Result, results),
        workers: workers,
    }
    
    // 启动 worker
    for i := 0; i < workers; i++ {
        wp.wg.Add(1)
        go wp.worker(i)
    }
    
    return wp
}

func (wp *WorkerPool) worker(id int) {
    defer wp.wg.Done()
    for job := range wp.jobs {
        // 处理工作
        data, err := wp.process(job.Payload)
        result := Result{
            JobID:  job.ID,
            Data:   data,
            Err:    err,
        }
        select {
        case job.ResultCh <- result:
        case <-time.After(5 * time.Second):
            log.Warn("result channel timeout", "job_id", job.ID)
        }
    }
}

func (wp *WorkerPool) Submit(job Job) error {
    select {
    case wp.jobs <- job:
        return nil
    case <-time.After(1 * time.Second):
        return fmt.Errorf("job submission timeout")
    }
}

func (wp *WorkerPool) Shutdown() {
    close(wp.jobs)
    wp.wg.Wait()
    close(wp.results)
}
```

---

## 第二部分：Redis 集群实战

### Redis Cluster 在广告系统中的应用

```
Redis Cluster 配置：
• 节点：3 Master + 3 Replica = 6 节点
• 槽位：16384 slots 均匀分布
• 分区策略：按 campaign_id hash 分布

广告系统 Redis 使用：
1. 用户特征：HSET user:{id} feature1 value1
2. 广告统计：HINCRBY campaign:{id} impressions 1
3. 预算扣减：Lua 脚本原子操作
4. 排行榜：ZADD leaderboard {score} {member}
5. 限流：INCR counter + EXPIRE
```

### Lua 脚本（预算扣减 + 曝光计数）

```lua
-- deduct_and_track.lua
-- 参数：KEYS[1]=budget_key, KEYS[2]=counter_key, ARGV[1]=amount

local budget_key = KEYS[1]
local counter_key = KEYS[2]
local amount = tonumber(ARGV[1])

-- 1. 扣减预算
local spent = redis.call('GET', budget_key) or '0'
local limit_key = budget_key .. ':limit'
local limit = redis.call('GET', limit_key) or '0'

if tonumber(spent) + amount > tonumber(limit) then
    return -1  -- 预算不足
end

redis.call('INCRBY', budget_key, amount)

-- 2. 更新计数器
redis.call('INCRBY', counter_key, 1)
redis.call('EXPIRE', counter_key, 86400)  -- 24h 过期

return 1  -- 成功
```

---

## 第三部分：K8s 生产实践

### 广告系统 K8s 部署

```yaml
# deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: bidder-service
spec:
  replicas: 5
  selector:
    matchLabels:
      app: bidder
  template:
    metadata:
      labels:
        app: bidder
    spec:
      containers:
      - name: bidder
        image: ad-platform/bidder:v1.2.3
        ports:
        - containerPort: 8080
        resources:
          requests:
            cpu: "500m"
            memory: "512Mi"
          limits:
            cpu: "2"
            memory: "2Gi"
        env:
        - name: REDIS_CLUSTER
          value: "redis-cluster:6379"
        - name: KAFKA_BROKERS
          value: "kafka-0:9092,kafka-1:9092"
        livenessProbe:
          httpGet:
            path: /health
            port: 8080
          initialDelaySeconds: 10
          periodSeconds: 5
        readinessProbe:
          httpGet:
            path: /ready
            port: 8080
          initialDelaySeconds: 5
          periodSeconds: 3
---
# hpa.yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: bidder-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: bidder-service
  minReplicas: 5
  maxReplicas: 50
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
```

---

## 第四部分：自测题

### Q1: Go Worker Pool 和 goroutine 的区别？

**A**: Worker Pool 控制并发数量，避免过多 goroutine 导致资源耗尽；原生 goroutine 数量无上限。

### Q2: Redis Cluster 的分区策略？

**A**: CRC16(key) % 16384 确定槽位，16384 个槽位分布在多个 master 节点。

### Q3: K8s HPA 的触发条件？

**A**: CPU 使用率 > 70% 或内存使用率 > 80% 时自动扩容。

---

## 第五部分：生产实践

### 1. Go 并发最佳实践

```
Go 并发要点：
• 使用 context 控制超时和取消
• 使用 sync.WaitGroup 等待协程完成
• 使用 channel 传递数据（而不是共享内存）
• 使用 select 实现超时
• 使用 defer 清理资源
```

### 2. Redis 运维

```
Redis 运维要点：
• 监控：内存使用、连接数、命中率、延迟
• 持久化：RDB + AOF
• 集群：Redis Cluster 自动分片
• 淘汰策略：allkeys-lru
```

### 3. K8s 运维

```
K8s 运维要点：
• 监控：Pod CPU/内存、Node 资源、网络
• 日志：Fluentd → Elasticsearch
• 追踪：Jaeger/OTel
• 安全：NetworkPolicy + RBAC
```
