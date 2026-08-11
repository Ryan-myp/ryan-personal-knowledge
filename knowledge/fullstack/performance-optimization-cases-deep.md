# 真实案例：广告竞价系统性能优化

> 基于真实生产环境的性能优化案例。
> 包含问题发现、分析、解决方案和效果验证。
> 适用对象：后端工程师、性能优化工程师

---

## 案例一：竞价延迟优化

### 1.1 问题发现

```
现象：
- 竞价 P99 延迟从 30ms 增长到 150ms
- 部分请求超时失败
- 系统 CPU 使用率正常，但响应变慢

影响：
- 收益下降 15%
- 用户投诉增加
- 合作伙伴满意度下降
```

### 1.2 问题定位

```
排查步骤：
1. 查看监控指标
   - CPU: 45% (正常)
   - 内存: 60% (正常)
   - 网络: 正常
   - 数据库: 正常

2. 分析请求链路
   - API Gateway: 5ms (正常)
   - Bidding Service: 120ms (异常)
   - Audience Service: 80ms (异常)
   - Pricing Service: 40ms (正常)

3. 深入分析 Bidding Service
   - 热点代码：受众匹配逻辑
   - 问题：每次都查询 Redis
   - 原因：热点用户未缓存
```

### 1.3 解决方案

```go
// 优化前：每次都查询 Redis
func (s *BiddingService) MatchAudience(userID string) ([]string, error) {
    // 直接查询 Redis
    result, err := s.redis.HGetAll(ctx, "audience:"+userID)
    if err != nil {
        return nil, err
    }
    return result, nil
}

// 优化后：本地缓存 + Redis 双重缓存
func (s *BiddingService) MatchAudience(userID string) ([]string, error) {
    // 1. 先查本地缓存
    if result, ok := s.localCache.Get("audience:" + userID); ok {
        return result.([]string), nil
    }
    
    // 2. 再查 Redis
    result, err := s.redis.HGetAll(ctx, "audience:"+userID)
    if err != nil {
        return nil, err
    }
    
    // 3. 写入本地缓存（TTL 5分钟）
    s.localCache.Set("audience:"+userID, result, 5*time.Minute)
    
    return result, nil
}
```

### 1.4 效果验证

```
优化前后对比：

指标          优化前    优化后    改善
─────────────────────────────────────
P50 延迟      15ms      3ms       -80%
P99 延迟      150ms     25ms      -83%
错误率        2.1%      0.1%      -95%
收益          基准      +15%      +15%
```

---

## 案例二：内存泄漏排查

### 2.1 问题发现

```
现象：
- 服务启动后内存持续增长
- 24小时后 OOM 重启
- 重启后内存恢复正常，几天后再次增长

影响：
- 每天需要重启服务
- 影响服务稳定性
- 增加运维成本
```

### 2.2 问题定位

```
排查步骤：
1. 使用 pprof 分析堆内存
   go tool pprof http://localhost:6060/debug/pprof/heap

2. 发现问题：map 无限增长
   - 某个缓存 map 只增不减
   - 缺少过期机制

3. 定位代码
   - 文件：bidding/service.go
   - 行号：156
   - 问题：cache map 未设置 TTL
```

### 2.3 代码分析

```go
// 问题代码
type BiddingService struct {
    // ... 其他字段
    cache map[string]*BidResult  // ❌ 无限增长
}

func (s *BiddingService) Process(req *BidRequest) *BidResult {
    // 查询缓存
    if result, ok := s.cache[req.ID]; ok {
        return result
    }
    
    // 计算结果
    result := s.calculate(req)
    
    // 写入缓存
    s.cache[req.ID] = result  // ❌ 只增不减
    
    return result
}

// 解决方案：使用带 TTL 的缓存
type TTLCache struct {
    data sync.Map
    ttl  time.Duration
}

func (c *TTLCache) Set(key string, value interface{}) {
    c.data.Store(key, &item{
        value:  value,
        expiry: time.Now().Add(c.ttl),
    })
}

func (c *TTLCache) Get(key string) (interface{}, bool) {
    v, ok := c.data.Load(key)
    if !ok {
        return nil, false
    }
    item := v.(*item)
    if time.Now().After(item.expiry) {
        c.data.Delete(key)
        return nil, false
    }
    return item.value, true
}
```

### 2.4 效果验证

```
优化前后对比：

指标          优化前    优化后    改善
─────────────────────────────────────
内存使用      8GB→OOM   稳定2GB   -75%
重启次数      1次/天    0次/月    -100%
稳定性        差        好        ✅
```

---

## 案例三：数据库慢查询优化

### 3.1 问题发现

```
现象：
- 用户画像查询响应慢（2s+）
- 数据库 CPU 使用率高
- 频繁触发慢查询日志

影响：
- 竞价请求超时
- 用户体验下降
- 数据库压力过大
```

### 3.2 问题定位

```
排查步骤：
1. 查看慢查询日志
   SHOW SLOW QUERY LOG;

2. 发现慢查询
   SELECT * FROM user_profiles 
   WHERE user_id IN (子查询)

3. 分析执行计划
   EXPLAIN SELECT ...
   
   问题：
   - 子查询返回大量数据
   - 缺少索引
   - 全表扫描
```

### 3.3 解决方案

```sql
-- 优化前：子查询
SELECT * FROM user_profiles 
WHERE user_id IN (
    SELECT user_id FROM audience_match 
    WHERE campaign_id = 12345
)

-- 优化方案1：添加索引
CREATE INDEX idx_audience_campaign ON audience_match(campaign_id, user_id);

-- 优化方案2：改为 JOIN
SELECT p.* FROM user_profiles p
INNER JOIN audience_match a ON p.user_id = a.user_id
WHERE a.campaign_id = 12345;

-- 优化方案3：物化视图
CREATE MATERIALIZED VIEW mv_audience_12345
AS SELECT user_id FROM audience_match WHERE campaign_id = 12345;

-- 优化方案4：缓存热点数据
-- Redis 缓存 user_profile
```

### 3.4 效果验证

```
优化前后对比：

指标          优化前    优化后    改善
─────────────────────────────────────
查询延迟      2.1s      50ms      -97%
CPU使用率     85%       35%       -59%
数据库压力    高        低        ✅
```

---

## 案例四：Redis 热点 Key

### 4.1 问题发现

```
现象：
- Redis CPU 使用率突然飙升
- 某些请求响应变慢
- 日志显示大量请求打到同一个 key

影响：
- 热点请求阻塞其他请求
- 系统整体性能下降
```

### 4.2 问题分析

```
热点 Key：
- user_profile:100001 (访问频率: 10000 QPS)
- campaign_config:5678 (访问频率: 8000 QPS)

原因：
- 头部用户/热门广告
- 热点数据集中
- 缺少本地缓存
```

### 4.3 解决方案

```go
// 方案1：本地缓存
type HotKeyCache struct {
    local  *LocalCache  // Caffeine/Guava
    remote *RedisClient
}

func (c *HotKeyCache) Get(key string) (interface{}, error) {
    // 先查本地缓存
    if val, ok := c.local.Get(key); ok {
        return val, nil
    }
    
    // 再查 Redis
    val, err := c.remote.Get(ctx, key)
    if err != nil {
        return nil, err
    }
    
    // 写入本地缓存
    c.local.Set(key, val, 30*time.Second)
    return val, nil
}

// 方案2：热点识别
func (c *HotKeyCache) IdentifyHotKeys() {
    // 实时监控访问频率
    // 识别热点 key
    // 自动加入本地缓存
}

// 方案3：请求合并
func (c *HotKeyCache) BatchGet(keys []string) map[string]interface{} {
    // 合并多个请求
    // 批量查询 Redis
    // 分别返回结果
}
```

### 4.4 效果验证

```
优化前后对比：

指标          优化前    优化后    改善
─────────────────────────────────────
Redis CPU     95%       45%       -53%
请求延迟      200ms     15ms      -92%
系统稳定性    差        好        ✅
```

---

## 案例总结

### 5.1 核心经验

```
1. 性能优化方法论：
   - 监控发现问题
   - 分析定位根因
   - 实施优化方案
   - 验证优化效果

2. 常见性能问题：
   - 缓存缺失/过期策略不当
   - 数据库查询优化
   - 热点 Key 处理
   - 内存泄漏
   - 并发控制

3. 优化工具：
   - pprof（Go）
   - EXPLAIN（MySQL）
   - Redis Monitor
   - APM 监控
```

### 5.2 最佳实践

```
性能优化 Checklist：
□ 监控告警完善
□ 缓存策略合理
□ 数据库索引优化
□ 热点数据处理
□ 内存泄漏排查
□ 并发控制合理
□ 异步处理耗时操作
□ 压力测试验证
```

---

*最后更新：2026-08-11*
*作者：Ryan*
