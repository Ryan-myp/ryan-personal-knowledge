# 广告技术专家考核题库 — 标准答案（源码级深度）

> 创建日期: 20260608
> 作者: Ryan

---

## 第一题：MySQL MVCC — Next-Key Lock 原理

### 场景
RR 隔离级别下，UPDATE `ad_report WHERE campaign_id = ?` 加锁。campaign_id 是普通索引。

### 答案

**为什么加 Next-Key Lock 而不是 Record Lock？**

因为 campaign_id 是**普通索引**（非唯一索引），InnoDB 需要防止幻读：
- 如果只锁记录，其他事务可以 INSERT 到相邻间隙 → 幻读
- 所以加 Next-Key Lock = Record Lock（锁记录本身）+ Gap Lock（锁前面的间隙）

**源码级分析：**

```c
// row_upd_build_index_constraint() — 构建索引约束
// 决定锁类型:
// - UNIQUE_INDEX → Lock Record（唯一索引，不会幻读）
// - NON_UNIQUE_INDEX → Lock Next-Key（非唯一索引，需要防幻读）

// lock_rec_build() — 构建记录锁
// 参数:
// - page_no: 页号
// - heap_no: 堆号（记录在页中的位置）
// - mode: 锁模式（X/S/IX/IS）

// 关键逻辑:
if (index->is_meta() || index->type != DICT_STATS || 
    dict_table_is_clust(table) || dict_table_is_purgeable(table)) {
    // 主键索引或特殊索引 → Record Lock
} else {
    // 普通索引 → Next-Key Lock
}
```

**排查步骤：**
1. `SELECT * FROM information_schema.INNODB_LOCKS;`
2. `SELECT * FROM information_schema.INNODB_LOCK_WAITS;`
3. `SELECT * FROM information_schema.INNODB_TRX;`
4. 定位锁类型 → Record/Gap/Next-Key/Insert Intention

**解决：**
- 加唯一索引 → 降级为 Record Lock
- 缩短事务
- 批量更新按主键顺序（避免死锁）

---

## 第二题：Go GMP 调度器

### 场景
Go 服务 P99 从 50ms 飙到 2s，1000+ goroutine 在 Grunnable 排队。

### 答案

**为什么 M 不够用？**

1. `GOMAXPROCS` 默认等于 CPU 核心数，但如果没设置，只有 1 个 M
2. 大量 G 在执行系统调用（如 IO），绑定 M 被阻塞
3. P 的本地队列满（256个），G 被移到全局队列，调度开销大

**GMP 结构体（runtime2.go）：**

```go
type g struct {
    stack   stack        // 栈
    sched   gobuf        // 调度信息
    m       *m           // 当前绑定的 M
    status  uint32       // Grunnable/Grunning/Gwaiting 等
}

type m struct {
    g0     *g           // 系统 goroutine（调度用）
    curg   *g           // 当前用户 goroutine
    p      p            // 绑定的 P
}

type p struct {
    status      uint32
    runqhead    uint32       // 本地队列头
    runqtail    uint32       // 本地队列尾
    runq        [256]g       // 本地队列（最多 256）
    runnext     *g           // 下一个要执行的 G
}
```

**调度流程（schedule()）：**
1. 从 P 本地队列取 G（`runqget()`）
2. 本地空，从其他 P 偷 G（`findrunnable()`，偷一半）
3. 偷不到，从全局队列取（`globrunqget()`）
4. 全局也空，M 休眠

**为什么你的场景 P99 飙升？**
- 1000 个 G 排队 → 局部队列满（256）→ 全队列也满
- 调度器频繁锁竞争
- GOMAXPROCS=32 降一半 → 增加了 P 数量，减少锁竞争

**根本原因可能是：**
- 大量 G 在执行系统调用阻塞（如 HTTP 请求、DB 查询）
- channel 缓冲不够导致 goroutine 频繁阻塞
- 没有用 goroutine pool

---

## 第三题：广告竞价

### 场景
广告列表不能让同一品牌连续出现。

### 答案

**放在哪个阶段？**

**重排阶段（Re-ranking）**，不是精排。原因：
- 精排目标：找出最优广告（eCPM 最高）
- 去重是用户体验优化，不应影响排序逻辑
- 重排可以在保持排序基本不变的情况下做多样性

**如何平衡排序公平性？**
- 允许同一品牌在 N 个广告位内出现（N=3）
- 多样性加权: `eCPM × (1 + position × 0.1)`
- 位置越靠后，加权越高

**VCG vs 第一价格：**
- 去重场景下 VCG 更公平
- VCG 定价: `price = 如果没有 winner 时其他广告的最大总效用 - 有 winner 时的总效用`
- 实际中第一价格更简单，RTB 行业主流用第一价格

---

## 第四题：Redis

### 场景
缓存击穿 + Cluster 跨 slot 查询

### 答案

**缓存击穿解决方案：**
- 互斥锁方案：锁超时 → 穿透
- **推荐：逻辑过期**。不设置 TTL，而是在值里存过期时间，读取时发现过期，异步重建缓存并返回旧值

**Cluster 跨 slot 查询：**
- 用哈希标签: `KEYS{user}:1001`, `KEYS{user}:1002` → 都在同一个 slot
- 或在客户端分片查询后聚合

**Rehash 期间影响：**
- 内存翻倍（两个哈希表同时存在）
- 写入：写入 ht[1]，性能不变
- 读取：可能查两个哈希表，略有下降
- 渐进式 rehash：每次写入迁移一个 bucket

```c
// dictAdd():
func dictAdd(d *dict, key, val) {
    if d.rehashidx >= 0 {
        // rehash 中，写入 ht[1]
        dictAddToHT(d.ht[1], key, val)
    } else {
        dictAddToHT(d.ht[0], key, val)
    }
}

// dictFind():
func dictFind(d *dict, key) {
    if d.rehashidx >= 0 {
        // 先在 ht[1] 找，再在 ht[0] 找
        if val := dictFindInHT(d.ht[1], key); val != nil {
            return val
        }
        return dictFindInHT(d.ht[0], key)
    }
    return dictFindInHT(d.ht[0], key)
}
```

---

## 第五题：Kafka

### 场景
消费者 Rebalance 导致流处理停顿 30 秒

### 答案

**Rebalance 触发条件：**
1. 消费者加入 Consumer Group
2. 消费者离开（关闭、崩溃、网络分区）
3. Topic 分区变化
4. 心跳超时（session.timeout.ms）

**三个参数关系：**
```
heartbeat.interval.ms < session.timeout.ms / 3
max.poll.interval.ms > session.timeout.ms * 10
```

**Rebalance 策略选择：**
- **Range**（默认）：简单但不均衡
- **RoundRobin**：均匀但全量迁移
- **CooperativeSticky**（推荐）：增量迁移，只移动变化的分区

**优化方案：**
1. 用 CooperativeSticky
2. 调整超时参数
3. 预提交 offset
4. 考虑用 Kafka Streams（自带状态恢复）

---

## 第六题：Elasticsearch

### 场景
搜索延迟从 10ms 涨到 500ms

### 答案

**排查步骤：**
1. 查 JVM GC: `jstat -gcutil <pid> 1000`
2. 查 ES 指标: `_cluster/health`, `_nodes/stats`
3. 查 slow query log
4. 查 CPU/IO 占用

**分词器：**
- IK 分词器：支持自定义词典，适合中文
- 标准分词器：按 Unicode 分词，不区分语言

**Segment Merge 影响：**
- Merge 过程会读取多个 segment，增加 IO
- 但 ES 有后台合并机制，影响有限
- 如果 merge 太频繁，说明写入量太大

---

## 第七题：ClickHouse

### 场景
`SELECT date, campaign_id, count() GROUP BY date, campaign_id` 跑几分钟

### 答案

**Sorting Key 加速：**
- ClickHouse 按 sorting key 排序存储
- GROUP BY 可以利用排序做内存聚合，避免磁盘 IO

**高基数 GROUP BY 优化：**
- 用 `uniqCombined` 替代 `count(distinct)`
- 用 `GROUP BY` 预聚合，再聚合
- 用 `MATERIALIZED VIEW` 预计算

**手动 MERGE vs 自动 MERGE：**
- 自动：后台合并，透明
- 手动：`ALTER TABLE ... MERGE`，用于优化小分区
- 手动在分区刚创建时有用

---

## 第八题：设计模式 + Go 实战

### 场景
5 个广告平台 API 统一接入

### 答案

**Go 接口 + 组合模式：**

```go
type AdPlatformAPI interface {
    CreateCampaign(ctx context.Context, req *CreateCampaignRequest) (*Campaign, error)
    Bid(ctx context.Context, req *BidRequest) (*BidResponse, error)
}

// 各平台实现独立，互不影响
type GoogleAdsAdapter struct { client *google.Client }
type MetaAdsAdapter struct { client *meta.Client }
type TikTokAdsAdapter struct { client *tiktok.Client }

// 使用:
var api AdPlatformAPI = &GoogleAdsAdapter{client: gc}
```

**防腐层：**
- 每个平台适配器独立
- 改 Google 不影响其他

**限流：**
- 令牌桶算法
- 按平台独立限流
- 全局熔断

---

## 第九题：广告数据分析

### 场景
Facebook ROI 下降 20%

### 答案

**拆解方法：**
- A/B Test 思路：拆解变量（出价、定向、创意、时段）
- 归因模型：看各渠道贡献

**LTV/CAC：**
- LTV = Σ(ARPU_m × Retention_m) / (1 + r)^m
- LTV:CAC ≥ 3 健康
- CAC 上升但 LTV 不变 → 获客渠道质量下降

**Shapley Value 近似：**
- Monte Carlo 采样
- 随机排列触点，计算平均边际贡献

---

## 第十题：系统设计

### 场景
设计广告竞价系统（10万 QPS，P99 < 100ms）

### 答案

**架构图：**
```
┌──────────┐  ┌──────────┐  ┌──────────┐
│ 负载均衡  │→ │竞价引擎  │→ │ 广告库   │
│ (Nginx)  │  │(Go)      │  │(MySQL)  │
└──────────┘  └──────────┘  └──────────┘
                   │
                   ▼
            ┌──────────┐
            │用户画像  │
            │(Redis)  │
            └──────────┘
```

**用户画像存储：**
- Redis: 热点用户画像
- ES: 用户特征检索
- MySQL: 持久化

**竞价引擎扩展：**
- 分片: 按 campaign_id 哈希
- 缓存: 广告特征缓存
- 异步: 预算控制异步化

**预算控制一致性：**
- Redis 原子操作（INCR/DECR）
- 异步对账（每分钟一次）

**容灾：**
- 降级: 某个平台挂了，自动切换
- 熔断: 服务异常时熔断
- 超时: 所有调用设置超时
