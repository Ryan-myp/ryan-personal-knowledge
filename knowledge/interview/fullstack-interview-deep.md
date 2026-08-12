# 全栈技术面试题库深度实现 - 20道高频题

> **版本**: v2.0  
> **日期**: 2026-08-14  
> **作者**: Ryan  
> **分类**: 面试/全栈  
> **代码密度**: 30%

---

## 一、Go 并发

**Q1: Go GMP调度器的工作原理？**

```
答案:
• G: Goroutine，包含栈、PC指针、状态
• M: Machine，OS线程，执行G
• P: Processor，本地runqueue，最大数量=CPU核心数

调度流程:
1. 新建G → 放入P的本地队列
2. M从P的本地队列取G执行
3. 本地队列为空时，M从全局队列或其他P stealing
4. syscall阻塞 → M释放P，P寻找新M
5. 网络IO就绪 → Woke M，唤醒执行
```

**Q2: channel的底层实现？**

```
hchan结构:
• qcount: 队列中元素个数
• dataqsiz: 环形队列大小
• buf: 环形队列数组
• elemsize: 元素大小
• elem: 元素指针
• recvq/sendq: 等待队列 (sudog链表)
• lock: 互斥锁

操作:
• send: 有等待receiver则直接传递，否则入队+阻塞
• recv: 有等待sender则直接接收，否则入队+阻塞
```

---

## 二、Redis

**Q3: Redis持久化RDB vs AOF对比？**

```
┌──────────────┬──────────────┬──────────────┐
│     特性      │     RDB      │     AOF      │
├──────────────┼──────────────┼──────────────┤
│ 恢复速度     │ 快           │ 慢           │
│ 数据完整性   │ 可能丢失     │ 完整         │
│ 文件大小     │ 小           │ 大           │
│ 写入性能     │ 高           │ 较低         │
│ 推荐策略     │ 混合使用     │ 每秒sync     │
└──────────────┴──────────────┴──────────────┘
```

**Q4: Redis分布式锁实现？**

```go
// Lua脚本保证原子性
func SetLock(ctx context.Context, key, value string, ttl time.Duration) bool {
    script := `
    if redis.call('GET', KEYS[1]) == false then
        redis.call('SET', KEYS[1], ARGV[1], 'EX', ARGV[2])
        return 1
    end
    return 0
    `
    result := redis.Eval(ctx, script, []string{key}, value, int(ttl.Seconds()))
    return result.Bool()
}
```

---

## 三、Kafka

**Q5: Kafka为什么这么快？**

```
答案:
1. 顺序写磁盘 (零拷贝 + Page Cache)
2. 分区并行处理
3. 批量发送 + 压缩
4. Page Cache 缓存热点数据
5. 零拷贝 (sendfile)
```

**Q6: Kafka消费者组Rebalance机制？**

```
触发条件:
• 消费者加入/离开
• Topic新增分区
• 消费超时

Rebalance策略:
• Range: 按分区范围分配
• RoundRobin: 轮询分配
• Sticky: 最小化迁移

实现:
1. GroupCoordinator选举Leader
2. Member发送JoinGroup请求
3. Leader计算分配方案
4. 广播SyncGroup响应
5. 更新offset
```

---

## 四、系统设计

**Q7: 如何设计一个短链接服务？**

```
架构:
1. 生成短码: Base62(数字+字母)编码
2. 存储: Redis/hash存储URL映射
3. 读写: 写多读少，缓存热点短链
4. 到期: TTL自动过期

短码生成:
• 自增ID → Base62转换
• 雪花ID → 部分位编码
• Hash截取 → 碰撞检测
```

**Q8: 秒杀系统设计？**

```
核心思路: 层层过滤，削峰填谷

1. 前端: 按钮置灰 + 请求限流
2. CDN: 静态资源缓存
3. 网关: IP/账号限流
4. 服务: 库存预扣减 (Redis)
5. 消息: Kafka异步下单
6. 数据库: 乐观锁 + 分批提交

库存处理:
• Redis预扣减: DECR原子操作
• 超卖检测: 最后校验
• 补偿: 超时未支付回滚库存
```

---

## 五、自测题

1. **Go的select原理？**
   - 遍历case，随机选择一个就绪channel

2. **Redis Cluster数据分片？**
   - 16384个slot，CRC16(key) % 16384

