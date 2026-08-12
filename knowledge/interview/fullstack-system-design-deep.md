# 全栈系统设计面试深度实现 - 15道高频题

> **版本**: v2.0  
> **日期**: 2026-08-14  
> **作者**: Ryan  
> **分类**: 面试/系统设计  
> **代码密度**: 30%

---

## 一、分布式系统

**Q1: 如何设计一个分布式ID生成器？**

```
方案: 雪花算法 (Snowflake)
• 64位: sign(1) + timestamp(41) + worker(10) + sequence(12)
• 时间戳: 毫秒级，可用69年
• Worker: 1024个节点
• 序列: 每节点每毫秒4096个ID

Go实现:
type Snowflake struct {
    workerID     int64
    sequence     int64
    lastTimestamp int64
}

func (s *Snowflake) Next() int64 {
    ts := time.Now().UnixMilli()
    if ts == s.lastTimestamp {
        s.sequence++
    } else {
        s.sequence = 0
        s.lastTimestamp = ts
    }
    return (ts << 22) | (s.workerID << 12) | s.sequence
}
```

**Q2: 如何设计一个短链接服务？**

```
核心: Base62编码 + Redis缓存 + 异步降级

1. 生成短码:
   • 自增ID → Base62转换
   • 或雪花ID截取高位
   
2. 存储映射:
   • Redis hash: short_code → long_url
   • TTL: 永久或自定义
   
3. 读取流程:
   • 查询Redis → 302重定向
   • 缓存未命中 → 查DB → 回填缓存
   
4. 监控:
   • QPS统计
   • 热点短链
   • 失效统计
```

---

## 二、高并发

**Q3: 秒杀系统设计？**

```
架构分层:
1. CDN: 静态资源缓存
2. 网关: 限流 + IP黑名单
3. 服务: Redis预扣库存
4. 消息: Kafka削峰
5. 数据库: 乐观锁 + 分批提交

关键:
• 库存预扣减 (Redis DECR)
• 超卖检测 (DB最终校验)
• 异步下单 (Kafka队列)
• 超时释放 (TTL + 定时任务)
```

**Q4: 如何实现分布式锁？**

```go
// Redis分布式锁
func AcquireLock(redis *redis.Client, key, value string, ttl time.Duration) bool {
    script := `
    if redis.call('SET', KEYS[1], ARGV[1], 'NX', 'EX', ARGV[2]) then
        return 1
    end
    return 0
    `
    ok, _ := redis.Eval(script, []string{key}, value, int(ttl.Seconds())).Bool()
    return ok
}

// 释放锁 (Lua保证原子性)
func ReleaseLock(redis *redis.Client, key, value string) bool {
    script := `
    if redis.call('GET', KEYS[1]) == ARGV[1] then
        return redis.call('DEL', KEYS[1])
    end
    return 0
    `
    ok, _ := redis.Eval(script, []string{key}, value).Bool()
    return ok
}
```

---

## 三、自测题

1. **雪花算法的时钟回拨问题？**
   - 等待 / 跳过 / 报错处理

2. **秒杀超卖的原因？**
   - 并发扣库存 + DB最终校验

