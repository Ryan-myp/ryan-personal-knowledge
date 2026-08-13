# 故障排查案例库 - 资深专家深度实现

## 一、典型故障案例

### 1.1 案例一: Go Goroutine泄漏

```go
// 问题代码
func ProcessOrders(ch <-chan Order) {
    for order := range ch {
        go func() {
            // 业务处理
            process(order)
        }()
    }
}

// 修复方案
func ProcessOrders(ch <-chan Order, workerCount int) {
    var wg sync.WaitGroup
    for i := 0; i < workerCount; i++ {
        wg.Add(1)
        go func() {
            defer wg.Done()
            for order := range ch {
                process(order)
            }
        }()
    }
    wg.Wait()
}
```

### 1.2 案例二: MySQL连接池耗尽

```go
// 问题: 连接未正确释放
db, _ := sql.Open("mysql", dsn)
db.SetMaxOpenConns(100)
db.SetMaxIdleConns(10)

// 正确配置
db.SetConnMaxLifetime(5 * time.Minute)
db.SetConnMaxIdleTime(2 * time.Minute)
```

### 1.3 案例三: Redis缓存击穿

```go
func GetWithMutex(key string) (string, error) {
    val, err := redis.Get(key).Result()
    if err == redis.Nil {
        mu.Lock()
        defer mu.Unlock()
        
        val, err = redis.Get(key).Result()
        if err == redis.Nil {
            val = queryDB(key)
            redis.Set(key, val, time.Hour)
        }
    }
    return val, err
}
```

## 二、监控告警

```yaml
# Prometheus告警规则
groups:
- name: services
  rules:
  - alert: HighErrorRate
    expr: rate(http_requests_total{status=~"5.."}[5m]) > 0.05
    for: 5m
    labels:
      severity: critical
    annotations:
      summary: "高错误率告警"
```

## 三、应急预案

```
1. 快速定位: 查看Prometheus/Grafana
2. 止血操作: 重启/降级/限流
3. 根因分析: 日志/trace分析
4. 复盘改进: 编写案例文档
```

## 四、面试高频题

### Q1: 如何排查线上问题？

```
A:
1. 监控告警
2. 日志分析
3. 链路追踪
4. 代码审查
```

### Q2: 常见性能问题有哪些？

```
A:
1. 数据库慢查询
2. 内存泄漏
3. 连接池耗尽
4. 锁竞争
```

## 五、自测题

1. 描述一次完整的故障排查过程
2. 如何设计告警策略？

---

## 参考文档

- [故障排查方法论](https://thenewstack.io/)
