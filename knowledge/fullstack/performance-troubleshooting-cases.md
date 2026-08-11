# 性能排查实战案例库

> 本文档收录真实系统性能排查案例，涵盖 CPU、内存、网络、数据库、GC 等方面。
> 每个案例包含：问题现象、排查过程、根因分析、解决方案、效果对比。
> 适用对象：后端工程师、SRE、性能优化工程师

---

## 案例 1：Go 服务 CPU 100% 排查

### 1.1 问题现象

```
2024-03-15 14:30:00  告警：某竞价服务 CPU 使用率持续 100%
                    影响：P99 延迟从 50ms 升至 800ms
                    请求成功率：从 99.9% 降至 85%
```

### 1.2 排查过程

**Step 1: 定位热点 goroutine**

```bash
# 获取 pprof CPU profile
curl http://localhost:6060/debug/pprof/profile?seconds=30 > cpu.prof

# 分析
go tool pprof cpu.prof
```

```
(pprof) top 10
flameGraph showing:
  45%  runtime.gcScavenge
  25%  runtime.mallocgc
  15%  encoding/json.Unmarshal
  10%  main.processBid
   5%  other
```

**Step 2: 分析 GC 压力**

```bash
(pprof) list runtime.gcScavenge
Total: 120.5s

ROUTINE ======================== runtime.gcScavenge in /usr/local/go/src/runtime/mcgroup.go
    45.2s      45.2s  (flame graph shows this is the hot spot)
```

**Step 3: 检查分配率**

```go
// 添加监控
import "runtime"

func printGCStats() {
    var stats runtime.MemStats
    runtime.ReadMemStats(&stats)
    log.Printf("alloc=%dB total_alloc=%dB gc_cycles=%d",
        stats.Alloc,
        stats.TotalAlloc,
        stats.NumGC,
    )
}
```

输出：
```
alloc=512MB total_alloc=25GB gc_cycles=150/min
```

### 1.3 根因分析

**主要问题**：
1. 高频分配小对象（每秒 50 万分配）
2. GC 频繁触发（150 次/分钟）
3. GC 扫垃圾时间占比 45%

**代码问题**：
```go
// ❌ 问题代码
func processBid(req *BidRequest) *BidResponse {
    // 每次调用都分配新字符串
    logMsg := fmt.Sprintf("bid %s from user %d", req.ID, req.UserID)
    
    // 频繁的 map 操作
    result := make(map[string]interface{})
    result["price"] = req.Price
    result["rank"] = req.Rank
    
    return &BidResponse{...}
}
```

### 1.4 解决方案

**优化 1: 减少字符串分配**

```go
// ✅ 优化后
var logBuf sync.Pool

func processBid(req *BidRequest) *BidResponse {
    buf := logBuf.Get().(*bytes.Buffer)
    defer logBuf.Put(buf)
    
    buf.Reset()
    buf.WriteString("bid ")
    buf.WriteString(req.ID)
    buf.WriteString(" from user ")
    buf.WriteString(strconv.Itoa(req.UserID))
    log.Printf("%s", buf.String())
    
    // 使用结构体替代 map
    return &BidResponse{...}
}
```

**优化 2: 对象池复用**

```go
var responsePool = sync.Pool{
    New: func() interface{} {
        return &BidResponse{}
    },
}

func getResponse() *BidResponse {
    return responsePool.Get().(*BidResponse)
}

func putResponse(r *BidResponse) {
    r.Reset()
    responsePool.Put(r)
}
```

### 1.5 效果对比

| 指标 | 优化前 | 优化后 | 提升 |
|------|--------|--------|------|
| CPU 使用率 | 100% | 35% | -65% |
| P99 延迟 | 800ms | 45ms | 17.8x |
| GC 频率 | 150次/分 | 20次/分 | -87% |
| 内存分配 | 25GB/h | 3GB/h | -88% |

---

## 案例 2：MySQL 慢查询优化

### 2.1 问题现象

```
某竞价查询执行时间 2.1s，QPS 5000
```

### 2.2 排查过程

```sql
-- 慢查询日志
SELECT * FROM bid_record 
WHERE user_id = 12345 
  AND campaign_id IN (SELECT id FROM campaign WHERE status = 1)
  AND create_time > '2024-01-01'
ORDER BY create_time DESC
LIMIT 20;
```

**EXPLAIN 分析**：
| id | select_type | table | type | key | rows | Extra |
|----|-------------|-------|------|-----|------|-------|
| 1 | PRIMARY | bid_record | ALL | NULL | 5000000 | Using where; Using filesort |
| 2 | SUBQUERY | campaign | ALL | NULL | 10000 | Using where |

### 2.3 根因分析

1. `bid_record` 表无 `user_id` 索引
2. `campaign_id` IN 子查询导致 nested loop
3. `create_time` 范围查询后还要 filesort

### 2.4 解决方案

```sql
-- 添加复合索引
ALTER TABLE bid_record 
ADD INDEX idx_user_time (user_id, create_time);

-- 改写 SQL 使用 JOIN
SELECT b.* FROM bid_record b
INNER JOIN campaign c ON b.campaign_id = c.id
WHERE b.user_id = 12345
  AND c.status = 1
  AND b.create_time > '2024-01-01'
ORDER BY b.create_time DESC
LIMIT 20;
```

### 2.5 效果对比

| 指标 | 优化前 | 优化后 |
|------|--------|--------|
| 执行时间 | 2100ms | 45ms |
| 扫描行数 | 5,000,000 | 20 |
| QPS 承载 | 5000 | 50000 |

---

## 案例 3：Redis 缓存穿透

### 3.1 问题现象

```
Redis 缓存命中率从 95% 降至 15%
MySQL QPS 从 1000 飙升至 50000
```

### 3.2 排查过程

**分析 Redis 监控**：
```
key_space_hits: 150000
key_space_misses: 850000
miss_rate: 85%
```

**分析命中请求**：
```bash
# 提取 miss 的 key
redis-cli --scan | xargs redis-cli exists | grep ":0" | head -20
```

发现大量不存在的 user_id：
```
user:-1
user:0
user:99999999
```

### 3.3 根因分析

恶意请求持续查询不存在的用户，导致缓存失效，所有请求打到 MySQL。

### 3.4 解决方案

**方案 1: 布隆过滤器**

```go
type BloomFilter struct {
    bf *bloom.BloomFilter
}

func (b *BloomFilter) IsExist(userID int64) bool {
    return b.bf.Test([]byte(strconv.FormatInt(userID, 10)))
}
```

**方案 2: 空值缓存**

```go
func GetUser(userID int64) (*User, error) {
    cacheKey := fmt.Sprintf("user:%d", userID)
    
    data, err := redis.Get(ctx, cacheKey).Bytes()
    if err == nil {
        return deserialize(data), nil
    }
    
    // 检查是否是空值标记
    if redis.Exists(ctx, cacheKey).Val() {
        return nil, ErrUserNotFound
    }
    
    user, err := db.GetUser(ctx, userID)
    if err != nil {
        redis.Set(ctx, cacheKey, "", 5*time.Minute)  // 缓存空值
        return nil, err
    }
    
    redis.Set(ctx, cacheKey, user, 30*time.Minute)
    return user, nil
}
```

### 3.5 效果对比

| 指标 | 优化前 | 优化后 |
|------|--------|--------|
| 缓存命中率 | 15% | 98% |
| MySQL QPS | 50000 | 5000 |
| 响应时间 | 500ms | 5ms |

---

## 案例 4：Goroutine 泄漏

### 4.1 问题现象

```
服务启动后 goroutine 数持续增长
10 小时后从 1000 增长到 50000
```

### 4.2 排查过程

```bash
# 获取 goroutine profile
curl http://localhost:6060/debug/pprof/goroutine?debug=2 > goroutine.prof

# 分析
go tool pprof goroutine.prof
```

```
(pprof) top 10
  15000  runtime.gopark
  10000  syscall.Syscall
   8000  net.accept
   5000  bufio.Reader.Read
   2000  other
```

```
(pprof) list main.processBid
Total: 50000

ROUTINE ======================== main.processBid in /app/main.go
   8000      8000  /app/main.go:45  // goroutine 泄漏点
```

### 4.3 根因分析

```go
// ❌ 问题代码
func processBid(ch chan *BidRequest) {
    for req := range ch {
        go func() {
            // 某些条件下不退出
            if !shouldProcess(req) {
                return  // 但这个 return 不会关闭 goroutine
            }
            handle(req)
        }()
    }
}
```

**原因**：goroutine 在特定条件下无法退出，持续累积。

### 4.4 解决方案

```go
// ✅ 修复后
func processBid(ctx context.Context, ch chan *BidRequest) {
    var wg sync.WaitGroup
    
    for {
        select {
        case req, ok := <-ch:
            if !ok {
                return  // channel 关闭
            }
            wg.Add(1)
            go func() {
                defer wg.Done()
                handle(ctx, req)
            }()
        case <-ctx.Done():
            return  // context 取消
        }
    }
}
```

### 4.5 效果对比

| 指标 | 优化前 | 优化后 |
|------|--------|--------|
| Goroutine 数 | 50000 | 1000 |
| 内存使用 | 8GB | 1GB |
| 服务稳定性 | 不稳定 | 稳定 |

---

## 案例 5：Kafka 消息堆积

### 5.1 问题现象

```
Kafka 消息堆积 500 万条
消费者 lag 持续增长
```

### 5.2 排查过程

```bash
# 查看 consumer lag
kafka-consumer-groups.sh --bootstrap-server broker:9092 --describe --group bid-consumer

TOPIC           PARTITION  CURRENT-OFFSET  LOG-END-OFFSET  LAG
bid-events      0          5000000         10000000        5000000
bid-events      1          4800000         9800000         5000000
```

**原因分析**：
1. 消费者处理速度慢
2. 批量处理效率低
3. 下游 MySQL 写入瓶颈

### 5.3 解决方案

**优化 1: 增加消费者并行度**

```go
// 启动多个 consumer
func StartConsumers(topics []string, batchSize int) {
    for i := 0; i < 10; i++ {
        go func(instanceID int) {
            consumer, _ := kafka.NewConsumer(...)
            consumer.Subscribe(topics...)
            
            for msg := range consumer.Messages() {
                processBatch(msg, batchSize)
            }
        }(i)
    }
}
```

**优化 2: 批量写入**

```go
func processBatch(messages []*kafka.Message) {
    tx, _ := db.Begin()
    for _, msg := range messages {
        insertIntoDB(tx, msg)
    }
    tx.Commit()
}
```

### 5.4 效果对比

| 指标 | 优化前 | 优化后 |
|------|--------|--------|
| 堆积量 | 500万 | 0（2小时消费完） |
| 消费速率 | 1000 msg/s | 50000 msg/s |
| MySQL QPS | 5000 | 20000 |

---

## 案例 6：MySQL 连接池泄漏

### 6.1 问题现象

```
MySQL 连接数达到上限（500）
新请求无法获取连接
```

### 6.2 排查过程

```sql
-- 查看连接状态
SHOW PROCESSLIST;

-- 发现大量 sleep 连接
| Id | User | Host | db | Command | Time | State | Info |
|----|------|------|----|---------|------|-------|------|
| 1  | app  | ...  | bid| Sleep   | 300  |       | NULL |
| 2  | app  | ...  | bid| Sleep   | 280  |       | NULL |
...
```

```go
// ❌ 问题代码
func Query(db *sql.DB, query string) ([]byte, error) {
    conn, _ := db.Conn(ctx)
    defer conn.Close()  // 但有时忘记调用
    return conn.QueryContext(ctx, query)
}
```

### 6.3 解决方案

```go
func initDB() *sql.DB {
    db, _ := sql.Open("mysql", dsn)
    
    // 正确配置连接池
    db.SetMaxOpenConns(50)       // 最大连接数
    db.SetMaxIdleConns(20)       // 最大空闲连接
    db.SetConnMaxLifetime(5 * time.Minute)  // 连接最大生命周期
    db.SetConnMaxIdleTime(2 * time.Minute)  // 空闲连接回收时间
    
    return db
}
```

### 6.4 效果对比

| 指标 | 优化前 | 优化后 |
|------|--------|--------|
| 连接数 | 500（满） | 50（正常） |
| 响应时间 | 5s（超时） | 50ms |
| 错误率 | 30% | 0.1% |

---

## 总结

### 排查方法论

```
1. 监控告警 → 2. 定位问题 → 3. 收集数据 → 4. 分析根因 → 5. 制定方案 → 6. 验证效果
```

### 常用工具

| 工具 | 用途 | 命令 |
|------|------|------|
| pprof | CPU/内存分析 | `go tool pprof` |
| mysqldumpslow | 慢查询分析 | `mysqldumpslow` |
| kafka-consumer-groups | 消息堆积 | `--describe` |
| Prometheus | 指标监控 | Grafana |
| Jaeger | 链路追踪 | UI |

### Checklist

- [ ] 定期检查 pprof
- [ ] 设置合理的连接池参数
- [ ] 监控 goroutine 数量
- [ ] 设置 Kafka lag 告警
- [ ] 定期 review 慢查询

---

*最后更新：2026-08-11*
*作者：Ryan*
