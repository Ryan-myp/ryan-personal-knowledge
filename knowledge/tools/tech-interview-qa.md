# 广告技术专家考核题库 — 标准答案（源码级深度）

> 创建日期: 20260608
> 作者: Ryan

---

## 第一题：MySQL MVCC

### 题目：RR 隔离级别下，UPDATE 加锁为什么是 Next-Key Lock？

### 核心答案

```
InnoDB 的锁不是只加在"记录"上，而是加在"记录+间隙"上的。

为什么？

在 RR 隔离级别下，InnoDB 需要防止"幻读"。如果只锁记录，
其他事务可以在相邻的间隙插入新记录，导致两次查询结果不同。

所以 InnoDB 在索引查找时，不仅锁命中的记录，还锁住"相邻间隙"。
```

### 源码级分析

```c
// 1. 锁类型判断（row_upd_index() 函数）
// 根据事务隔离级别和查询方式决定锁类型

lock_t *lock_rec_build(
    ulint         mode,           // 锁模式（X/S/IX/IS）
    ulint         mode_if_not_found,  // 记录未找到时的锁
    const rec_t * rec,             // 记录
    const ulint * offsets,         // 页信息
    bool        match_mode)        // 是否匹配模式

// 2. 判断是否为 Next-Key Lock（row_sel_build_locks()）
// 
// 关键逻辑:
// 
// 情况1: SELECT ... FOR UPDATE（当前读）
// → 加 X Record Lock（锁记录本身）
//
// 情况2: SELECT ... FOR UPDATE + 范围查询（WHERE id > 5）
// → 加 X Next-Key Lock（锁记录 + 记录前面的间隙）
//
// 情况3: UPDATE ... WHERE id = ?
// → 如果 id 有唯一索引（PRIMARY KEY）: 加 X Record Lock
// → 如果 id 有普通索引: 加 X Next-Key Lock
// → 如果没有索引: 全表扫描，加 X Record Lock 到每行
//
// 情况4: UPDATE ... WHERE name = ?（name 是二级索引）
// → 加 X Next-Key Lock 在二级索引上
// → 同时加 X Record Lock 在主键上（因为要更新数据行）
// → 这就是"间隙锁"的由来

// 3. 为什么你的 UPDATE 加了 Next-Key Lock？

// 假设表结构:
CREATE TABLE ad_report (
    id INT PRIMARY KEY,
    campaign_id INT,  -- 普通索引
    status INT
);

// 执行: UPDATE ad_report SET status = 1 WHERE campaign_id = 100

// InnoDB 的处理流程:
// 1. 在 campaign_id 索引上查找
// 2. 找到 campaign_id = 100 的记录
// 3. 因为 campaign_id 是**普通索引**（不是唯一索引），所以加 Next-Key Lock
// 4. Next-Key Lock = Record Lock（锁定这条记录）+ Gap Lock（锁定前面的间隙）
//
// 这意味着:
// - 其他事务不能 INSERT campaign_id = 100 的记录（Gap Lock 阻止）
// - 其他事务不能 UPDATE campaign_id = 100 的记录（Record Lock 阻止）
// - 其他事务可以 INSERT campaign_id = 50 或 150 的记录（不在间隙内）

// 4. 如果 campaign_id 是唯一索引:
// UPDATE ad_report SET status = 1 WHERE campaign_id = 100
// → 加 X Record Lock（只锁记录，不锁间隙）
// → 因为唯一索引不会有幻读问题
```

### 关键源码函数

```c
// row_upd_build_sort_vec() — 构建排序向量
// 用于确定锁的范围

// lock_rec_add_to_queue() — 添加记录锁到锁队列
// 参数:
// - mode: 锁模式
// - page_id: 页 ID
// - page_no: 页号
// - offset: 记录偏移
// - flag: 锁标志
// - index: 索引
// - heap_no: 堆号

// lock_wait_timeout — 锁超时设置（默认 50s）
// innodb_lock_wait_timeout = 50
```

### 排查建议

```
当遇到锁等待问题时:

1. 查锁表:
   SELECT * FROM information_schema.INNODB_LOCKS;
   SELECT * FROM information_schema.INNODB_LOCK_WAITS;

2. 查事务:
   SELECT * FROM information_schema.INNODB_TRX;

3. 定位锁类型:
   - Record Lock: 锁住具体记录
   - Gap Lock: 锁住间隙
   - Next-Key Lock: Record Lock + Gap Lock
   - Insert Intention Lock: 插入意向锁

4. 解决:
   - 加唯一索引 → 从 Next-Key Lock 降级为 Record Lock
   - 缩短事务持续时间
   - 降低隔离级别到 RC（不推荐）
   - 批量更新时按主键顺序（避免死锁）
```

---

## 第二题：Go GMP 调度器

### 题目：Goroutine 在 Runnable 队列排成长队，M 不够用？

### 核心答案

```
这是 Go 调度器中最经典的问题之一。

根本原因：不是 M（OS 线程）不够，而是 G（goroutine）太多，
但全局运行队列和局部运行队列的设计导致 M 无法及时"偷"到 G 来执行。
```

### 源码级分析

```c
// 1. GMP 结构体（runtime/runtime2.go）

// G — goroutine
type g struct {
    stack       stack       // 栈
    sched       gobuf       // 调度信息
    m           *m          // 当前绑定的 M
    status      uint32      // G 状态（Grunwaiting/Grunnable/Grunning 等）
    ...
}

// M — OS 线程
type m struct {
    g0      *g         // 系统 goroutine，用于调度
    curg    *g         // 当前用户 goroutine
    p       p          // 绑定的 P（Processor）
    ...
}

// P — 处理器
type p struct {
    status      uint32      // 状态（Prunning/Pidle 等）
    m           m           // 绑定的 M（0 = 无绑定）
    goidelta    uint32      // 下一个可用的 goroutine ID
    runqhead    uint32      // 本地运行队列头
    runqtail    uint32      // 本地运行队列尾
    runq      [256]g          // 本地运行队列（大小 256）
    runnext    *g              // 下一个要执行的 G
    ...
}

// 2. 全局运行队列

// 全局运行队列（sched.runq 和 sched.runqsize）
// 所有 P 共享的全局 runnable G 队列

// 3. G 的执行流程

// Step 1: 创建 G
// 调用 runtime.newproc()
//   → 创建 G 结构体
//   → 放到 P 的本地运行队列 runq

// Step 2: G 入队
// gexec() 被调用
//   → G 开始运行

// Step 3: G 被抢占（preempt）
// 如果 G 运行时间过长，被系统抢占
//   → G 状态变为 Grunnable
//   → 放入 P 的 runnext 或 runq

// Step 4: M 偷 G
// 如果 P 的本地队列满了（256个）
//   → 把一半的 G 移到全局运行队列
// 如果 P 的本地队列为空
//   → M 尝试从其他 P 的本地队列"偷"一半 G
//   → 如果还是没有，从全局运行队列取 G
//   → 如果全局也空，M 休眠

// 4. 为什么 M 不够用？

// 场景分析:
// 1000 个 G 在 runnable 状态排队

// 原因 A: 没有设置 GOMAXPROCS
// 默认 GOMAXPROCS = 1（Go 1.5+ 默认等于 CPU 核心数）
// 如果你的服务器有 16 核，但 GOMAXPROCS = 1
// → 只有 1 个 M 在调度 1000 个 G
// → 调度开销过大

// 原因 B: 大量 G 在系统调用阻塞
// 如果大量 G 在执行系统调用（如 IO、网络）
// → 它们绑定的 M 也被阻塞
// → 其他 G 无法使用这些 M
// → 剩下的 M 不够用

// 原因 C: G 的数量超过 P 的容量
// 每个 P 最多持有 256 个 G 在本地队列
// 如果只有 4 个 P，最多容纳 1024 个 G
// 如果有 1000 个 G 都在 runnable 状态
// → 调度器需要频繁从全局队列"偷" G
// → 锁竞争严重

// 5. 解决方案

// 方案 A: 设置 GOMAXPROCS
// export GOMAXPROCS=32
// → 增加 P 的数量，每个 P 有自己的 M
// → 减少锁竞争

// 方案 B: 优化 G 的创建和销毁
// 使用 goroutine 池（如 workerpool）
// → 避免频繁创建/销毁 G
// → 减少调度开销

// 方案 C: 使用 channel 替代 mutex
// channel 内部使用 gopark/gorunqueue 机制
// → 更高效的任务调度

// 方案 D: 避免系统调用阻塞
// 如果 G 在执行系统调用，绑定的 M 也会被阻塞
// → 使用 netpoller 处理网络 IO
// → 避免 M 被长时间阻塞
```

### 关键源码函数

```c
// runtime/sched.go

// schedule() — 调度函数
// 这是 Go 调度器的核心
// 每次 G 切换时都会调用这个函数

func schedule() {
    _g_ := getg()
    
    // 1. 检查当前 P 的本地队列
    if gp := runqget(_g_.m.p.ptr()); gp != nil {
        // 从本地队列取 G
        goready(gp, 0)
    }
    
    // 2. 本地队列为空，尝试从其他 P "偷" G
    if gp := findrunnable(); gp != nil {
        goready(gp, 0)
    }
    
    // 3. 还是没有，从全局队列取
    if gp := globrunqget(_g_.m.p.ptr()); gp != nil {
        goready(gp, 0)
    }
}

// findrunnable() — 找 runnable G
// 核心逻辑: 从其他 P 的本地队列偷 G

func findrunnable() (gp *g, inheritTime bool) {
    // 尝试从其他 P 的本地队列偷 G
    for i := 0; i < 4; i++ {
        _p_ = allp[FastRand()%uint32(len(allp))]
        if _p_ == nil || _p_.m != 0 {
            continue
        }
        if gp := runqgrab(_p_, &sched, 0) {
            return gp, false
        }
    }
    
    // 还是找不到，从全局队列取
    gp := globrunqget(_g_.m.p.ptr())
    if gp != nil {
        return gp, false
    }
    
    return nil, false
}
```

---

## 第三题：广告竞价

### 题目：广告去重混排 + 定价策略

### 核心答案

```
1. 去重+混排应该放在"重排"阶段，不是精排。
2. VCG 定价在去重场景下更公平，但计算复杂度更高。
```

### 源码级分析

```c
// 1. 竞价流程架构

// 标准竞价流程:
// ① 预筛选 → ② 粗排 → ③ 精排 → ④ 竞价 → ⑤ 重排 → 输出

// 去重+混排应该放在哪个阶段？

// 答案: 重排阶段（Re-ranking）

// 原因:
// - 预筛选、粗排、精排的目标是"找出最优广告"
// - 去重+混排是"优化用户体验"
// - 放在重排阶段，不影响前面的排序逻辑
// - 可以在保持 eCPM 排序大致不变的情况下，插入其他品牌的广告

// 2. 重排算法

// 重排流程:
// 输入: 精排后的广告列表（按 eCPM 排序）
// 输出: 最终展示的广告列表（去重+混排）

// 算法:
func reRank(ads []Ad, slots int) []Ad {
    result := []Ad{}
    seen := make(map[string]bool) // 已展示的 brand
    
    for _, ad := range ads {
        if len(result) >= slots {
            break
        }
        
        // 去重: 同一品牌连续出现不超过 N 次
        if seen[ad.BrandID] {
            continue
        }
        
        result = append(result, ad)
        seen[ad.BrandID] = true
    }
    
    // 插入其他内容（自然内容）
    // 每 3 条广告插入 1 条自然内容
    // ...
    
    return result
}

// 3. 排序公平性

// 问题: 去重会影响 eCPM 排序的公平性吗？

// 答案: 会。去重后，原本排在前面的广告可能被后置，
// 导致实际展示的广告不是 eCPM 最高的。

// 解决方案:
// - 允许同一品牌在 N 个广告位内出现（如 N=3）
// - 使用"多样性加权": 去重后的广告 eCPM * diversityWeight
//   diversityWeight = 1.0 + (position - 1) * 0.1
//   → 位置越靠后，加权越高，越可能被选中

// 4. 定价策略

// 第一价格拍卖 vs 第二价格拍卖 vs VCG

// 第一价格: price = bid_winner
// - 优点: 简单
// - 缺点: 投标人要策略性出价（低于真实估值）
// - 适用: 实时竞价（RTB）

// 第二价格: price = bid_second_highest
// - 优点: 投标人可以诚实出价
// - 缺点: 投标人可能"低价中标"
// - 适用: 传统拍卖

// VCG（Vickrey-Clarke-Groves）:
// - 优点: 最公平，投标人可以诚实出价
// - 缺点: 计算复杂
// - 适用: 复杂场景（如去重+混排）

// VCG 定价公式:
// price_i = Σ_{j ≠ i} max_{k} v_j(x_{-i} ∪ {k}) - Σ_{j ≠ i} max_{k} v_j(x_{-i})
// 即: winner 支付"社会成本" = 如果没有 winner 时其他广告的最大总效用
// 减去 有 winner 时其他广告的最大总效用

// 去重场景下的 VCG:
// 如果去重后，广告 A 被选中（因为品牌多样性），
// 但广告 B（第二高 eCPM）被后置了，
// 那么广告 A 的 VCG 价格 = 广告 B 的 eCPM * 多样性权重
// → 更公平
```

---

## 第四题：Redis

### 题目：缓存击穿 + Cluster 跨 slot 查询

### 核心答案

```
1. 缓存击穿用互斥锁解决，但锁超时后还是穿透。
   解决: 用"逻辑过期"替代"物理过期"。
   
2. Cluster 跨 slot 查询用"哈希槽映射表"解决。
   
3. rehash 期间的写入影响: 
   渐进式 rehash 保证写入不会阻塞，但会增加内存使用。
```

### 源码级分析

```c
// 1. 缓存击穿解决方案

// 方案 A: 互斥锁（当前方案）
// 问题: 锁超时 → 穿透

// 方案 B: 逻辑过期（推荐）
// 原理: 不设置 TTL，而是在值里存"过期时间"
// 读取时，如果发现值已过期，异步重建缓存，返回旧值
// 这样不会穿透

func GetOrCreateCache(key string) (*CacheItem, error) {
    // 1. 读缓存
    data, err := redis.Get(key)
    if err == nil && !IsExpired(data) {
        return data, nil
    }
    
    // 2. 缓存过期，尝试加锁重建
    if !TryLock("cache_rebuild:" + key) {
        // 锁被占用，返回旧值（如果存在）
        return data, nil
    }
    defer Unlock("cache_rebuild:" + key)
    
    // 3. 双重检查
    data, err = redis.Get(key)
    if err == nil && !IsExpired(data) {
        return data, nil
    }
    
    // 4. 重建缓存
    data = rebuildCache(key)
    redis.SetEx(key, data, 3600) // 设置 TTL
    
    return data, nil
}

// 5. 使用布隆过滤器防止缓存穿透
// 在缓存前加一层布隆过滤器，检查 key 是否存在

// 2. Cluster 跨 slot 查询

// Redis Cluster 将 16384 个 slot 分配到不同节点
// 如果查询需要跨 slot 聚合数据:

// 方案 A: 使用哈希标签（hash tags）
// 将相关数据分配到同一个 slot
// KEYS{user}:1001, KEYS{user}:1002 → 都在同一个 slot

// 方案 B: 客户端分片查询
// 分别查询每个 slot 的数据，然后在客户端聚合

func GetMultiUserProfiles(userIDs []string) ([]UserProfile, error) {
    results := make([]UserProfile, 0, len(userIDs))
    
    for _, userID := range userIDs {
        key := fmt.Sprintf("user:%s:profile", userID)
        data, err := redisCluster.Get(key)
        if err == nil {
            profile := parseProfile(data)
            results = append(results, profile)
        }
    }
    
    return results, nil
}

// 3. Rehash 期间写入

// 渐进式 rehash 实现:
// ht[0] → 旧哈希表
// ht[1] → 新哈希表
// rehashidx → 当前 rehash 进度（-1 表示不在 rehash）

// 写入流程:
// 1. 如果 ht[1] 存在，写入 ht[1]
// 2. 如果 ht[1] 不存在，写入 ht[0]

func dictAdd(d *dict, key, val interface{}) {
    if d.rehashidx >= 0 {
        // 正在 rehash，写入 ht[1]
        dictAddToHT(d, d.ht[1], key, val)
    } else {
        // 不 in rehash，写入 ht[0]
        dictAddToHT(d, d.ht[0], key, val)
    }
}

// 读取流程:
// 1. 先在 ht[1] 查找
// 2. 如果没找到，再在 ht[0] 查找

func dictFind(d *dict, key interface{}) interface{} {
    if d.rehashidx >= 0 {
        if val := dictFindInHT(d, d.ht[1], key); val != nil {
            return val
        }
        return dictFindInHT(d, d.ht[0], key)
    } else {
        return dictFindInHT(d, d.ht[0], key)
    }
}

// 性能影响:
// - 内存: 两个哈希表同时存在，内存翻倍
// - 写入: 写入 ht[1]，性能不变
// - 读取: 可能查两个哈希表，性能略有下降
// - 逐步迁移: 每次写入时迁移一个 bucket，逐步完成 rehash
```

---

## 第五题：Kafka

### 题目：消费者 Rebalance 导致流处理停顿

### 核心答案

```
1. Rebalance 触发条件: 消费者加入/离开、Topic 分区变化、session timeout
2. session.timeout.ms < heartbeat.interval.ms * 3
3. CooperativeSticky 是最优选择
```

### 源码级分析

```c
// 1. Rebalance 触发条件

// 条件 A: 消费者加入 Consumer Group
// 条件 B: 消费者离开 Consumer Group
//   - 正常关闭
//   - 崩溃
//   - 网络分区
// 条件 C: Topic 分区变化
//   - 分区增加
//   - 分区减少
// 条件 D: 消费者心跳超时
//   - session.timeout.ms 内未收到心跳

// 2. 三个关键参数关系

// session.timeout.ms = 10000 (10秒)
// heartbeat.interval.ms = 3000 (3秒)
// max.poll.interval.ms = 300000 (5分钟)

// 关系:
// heartbeat.interval.ms < session.timeout.ms / 3
// max.poll.interval.ms > session.timeout.ms * 10

// 为什么:
// - 每 3 秒发一次心跳
// - 如果 10 秒没收到心跳，认为消费者已死
// - 处理一批消息最多 5 分钟，超过则认为消费者卡死

// 3. Rebalance 策略

// Range 策略（默认）:
// 优点: 简单
// 缺点: 可能导致负载不均衡

// RoundRobin 策略:
// 优点: 均匀分配
// 缺点: Rebalance 时移动所有分区

// CooperativeSticky 策略（推荐）:
// 优点: 增量 Rebalance，只移动变化的分区
// 缺点: 实现复杂

// 4. 优化 Rebalance

// 方案 A: 使用 CooperativeSticky
// consumer.config.group.rebalance.strategy = CooperativeSticky

// 方案 B: 调整参数
// session.timeout.ms = 30000
// heartbeat.interval.ms = 10000
// max.poll.interval.ms = 600000

// 方案 C: 预提交 offset
// 在 close 之前提交 offset，避免重复消费

// 方案 D: 使用 Kafka Streams
// Kafka Streams 自带状态管理，Rebalance 时自动恢复
```

---

*由于篇幅限制，后续题目（ES、ClickHouse、设计模式、广告数据分析、系统设计）的答案继续写在下面...*

## 第六题：Elasticsearch

### 核心答案

```
1. 排查 ES 延迟: 监控 JVM GC、CPU、IO、索引合并
2. IK 分词器支持自定义词典，标准分词器按 Unicode 分词
3. Segment merge 会影响查询性能，因为要读取多个 segment
```

## 第七题：ClickHouse

### 核心答案

```
1. MergeTree 利用 sorting key 做索引跳跃
2. 高基数列 GROUP BY 用 DISTINCT 或 COUNT(DISTINCT)
3. 手动 MERGE 用于优化小分区
```

## 第八题：设计模式 + Go 实战

### 核心答案

```
1. 接口 + 组合: AdPlatformAPI 接口，各平台实现
2. 防腐层: 每个平台的适配器独立，改一个不影响其他
3. 限流: 令牌桶算法，按平台独立限流
```

## 第九题：广告数据分析

### 核心答案

```
1. A/B Test: 拆解变量，控制单一变量
2. LTV/CAC: LTV > 3 * CAC 健康
3. Shapley Value 近似: Monte Carlo 采样
```

## 第十题：系统设计

### 核心答案

```
1. 架构图: 负载均衡 → 竞价引擎 → 广告库 → 用户画像
2. 用户画像: Redis（热点）+ ES（检索）
3. 竞价引擎: 分片 + 缓存 + 异步计算
4. 预算控制: Redis 原子操作 + 异步对账
5. 容灾: 降级 + 熔断 + 超时
```

---

*本文件持续更新，每次添加新题目的标准答案*
