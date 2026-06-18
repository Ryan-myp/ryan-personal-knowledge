# 广告技术面试题库深度：Go/MySQL/Redis/广告系统

> 从基础到源码级，覆盖广告技术面试高频问题

---

## 第一部分：Go 语言面试题

### GMP 调度

```
Q: Go 的 GMP 调度器工作原理？
A: 
G (Goroutine): 协程，包含栈、状态、调度信息
M (Machine): 操作系统线程，执行 G
P (Processor): 处理器，管理本地 runq

调度流程：
1. 新建 G → 放入 P 的本地 runq
2. P 从 runq 取出 G 执行
3. G 阻塞时，P 创建新 M
4. P 本地队列满（256）时，一半放入全局队列
5. P 本地队列为空时，从全局队列或其他 P 偷取（work stealing）

关键优化：
• 本地队列减少锁竞争
• Work stealing 负载均衡
• Sysmon 监控长时间运行的 G
```

### 内存管理

```
Q: Go 的内存分配策略？
A:
小对象 (< 32KB):
  MCache → MSpan → MHeap → OS
  每个 P 有独立 MCache，避免锁竞争

大对象 (>= 32KB):
  MHeap → OS mmap
  直接映射到虚拟内存

零值对象:
  直接指向 zerobase

关键数据结构：
• mcache: 每 P 的本地缓存
• mspan: 连续内存块
• mheap: 全局内存堆
```

### Channel 底层

```
Q: Channel 的实现原理？
A:
结构体：
  type hchan struct {
      qcount   uint           // 队列元素个数
      dataqsiz uint           // 环形队列大小
      buf      unsafe.Pointer // 环形队列缓冲区
      elemsize uint16         // 元素大小
      closed   uint32         // 是否关闭
      elemtype *_type         // 元素类型
      sendx    uint           // 发送索引
      recvx    uint           // 接收索引
      recvq    waitq          // 等待接收的 G 队列
      sendq    waitq          // 等待发送的 G 队列
      lock     mutex          // 互斥锁
  }

操作流程：
1. 发送：锁 → 检查缓冲区 → 有空间则拷贝 → 解锁
2. 接收：锁 → 检查缓冲区 → 有数据则拷贝 → 解锁
3. 缓冲区满/空：G 进入等待队列，调度器切换
```

---

## 第二部分：MySQL 面试题

### 索引原理

```
Q: MySQL 索引为什么用 B+ 树？
A:
B+ 树优势：
1. 多叉树，高度低（3 层可存千万级数据）
2. 叶子节点链表，范围查询高效
3. 非叶子节点只存索引，内存可存更多
4. 顺序访问，磁盘 IO 友好

对比：
• B 树：非叶子节点也存数据，高度略高
• Hash：只支持等值查询
• 跳表：内存数据结构，不适合磁盘
```

### 事务隔离

```
Q: MySQL 的 MVCC 如何实现？
A:
实现机制：
1. 隐藏列：DB_TRX_ID（事务 ID）、DB_ROLL_PTR（回滚指针）
2. Undo Log：保存历史版本
3. Read View：事务快照

RR 隔离级别下的 Read View：
• 第一次 SELECT 时创建
• 可见性规则：
  - trx_id < min_trx_id → 可见
  - trx_id >= max_trx_id → 可见
  - trx_id 在活跃列表中 → 不可见
  - 否则 → 可见

RC 隔离级别：
• 每次 SELECT 都创建新的 Read View
• 所以能看到其他事务已提交的修改
```

### 锁机制

```
Q: MySQL 的锁类型？
A:
1. 全局锁：FLUSH TABLES WITH READ LOCK
2. 表级锁：LOCK TABLES
3. 行级锁：
   - 记录锁（Record Lock）：锁定索引记录
   - 间隙锁（Gap Lock）：锁定索引间隙
   - 临键锁（Next-Key Lock）：记录锁 + 间隙锁

死锁处理：
• InnoDB 自动检测死锁
• 选择回滚代价小的事务
```

---

## 第三部分：Redis 面试题

### 持久化

```
Q: RDB 和 AOF 的区别？
A:
RDB:
• 快照形式，周期性保存
• 恢复快，体积小
• 可能丢失最后一次快照后的数据

AOF:
• 命令日志，每次写都记录
• 数据更安全
• 文件大，恢复慢

生产推荐：
• 同时开启 RDB + AOF
• AOF 优先恢复
• appendfsync everysec
```

### 内存淘汰

```
Q: Redis 内存淘汰策略？
A:
1. noeviction: 不淘汰，返回错误（默认）
2. allkeys-lru: 所有 key 中淘汰 LRU
3. allkeys-lfu: 所有 key 中淘汰 LFU
4. volatile-lru: 有过期时间的 key 中淘汰 LRU
5. volatile-lfu: 有过期时间的 key 中淘汰 LFU
6. volatile-ttl: 有过期时间的 key 中淘汰 TTL 最短的

广告场景推荐：
• allkeys-lru: 缓存场景
• volatile-ttl: 精确控制
```

---

## 第四部分：广告系统面试题

### 竞价系统

```
Q: RTB 竞价流程？
A:
1. 用户访问页面
2. SSP 发起竞价请求（BidRequest）
3. DSP 获取请求，构建特征
4. 预测 CTR/CVR
5. 计算出价 = CTR × CVR × target_CPA
6. 发送竞价响应（BidResponse）
7. 竞价 winner 返回广告创意
8. 展示广告，记录曝光/点击

优化要点：
• 延迟 < 100ms
• 特征缓存（Redis）
• 模型量化（TensorRT）
• 本地缓存（sync.Map）
```

### 排序模型

```
Q: DeepFM 和 DIN 的区别？
A:
DeepFM:
• 低阶 + 高阶特征自动交互
• 静态特征，不考虑用户兴趣变化
• 适合特征工程复杂的场景

DIN:
• 注意力机制捕捉用户兴趣
• 动态特征，考虑用户历史行为
• 适合有用户行为序列的场景

广告场景：
• DeepFM: 特征少、实时性要求高
• DIN: 有用户行为序列、需要个性化
```

### 实验平台

```
Q: A/B 测试怎么设计？
A:
1. 确定目标指标（CTR/CVR/GMV）
2. 计算样本量（power analysis）
3. 随机分桶（保证均匀）
4. 运行实验（至少 1-2 周）
5. 统计分析（p-value < 0.05）
6. 决策（推广/回滚/继续）

注意事项：
• 辛普森悖论
• 新奇效应（Novelty Effect）
• 季节效应
• 网络效应（社交类产品）
```

---

## 第五部分：系统设计题

```
Q: 设计一个广告竞价系统？
A:
架构设计：
┌──────────────────────────────────────────────────────┐
│ API Gateway                                          │
│ ├── 请求路由                                           │
│ ├── 限流                                              │
│ └── 认证                                              │
│                                                      │
│ Bid Engine (竞价引擎)                                  │
│ ├── 特征获取 (Redis)                                   │
│ ├── CTR/CVR 预测 (TensorRT)                           │
│ ├── 出价策略 (RL/规则)                                 │
│ └── 预算控制                                           │
│                                                      │
│ Data Pipeline                                        │
│ ├── 实时事件 (Kafka)                                  │
│ ├── 特征计算 (Flink)                                  │
│ └── 模型训练 (Spark)                                  │
│                                                      │
│ Monitoring                                           │
│ ├── Prometheus + Grafana                              │
│ └── ELK 日志                                         │
│                                                      │
│ 关键指标：                                              │
│ • P99 延迟 < 100ms                                    │
│ • 可用性 > 99.99%                                     │
│ • 竞价成功率 > 99%                                    │
└──────────────────────────────────────────────────────┘
```

---

## 第六部分：自测题

### Q1: Go 的 GC 为什么这么快？

**A**: 三色标记 + 写屏障，并发标记清扫，STW 时间极短。

### Q2: Redis 为什么单线程还这么快？

**A**: 内存操作，epoll 事件驱动，避免锁竞争和上下文切换。

### Q3: 广告竞价延迟怎么优化？

**A**: 特征缓存 + 模型量化 + 并行推理 + 本地缓存。

---

## 第七部分：生产排障题

```
Q: 线上发现 CTR 突然下降，怎么排查？
A:
1. 确认影响范围：所有广告还是部分？
2. 检查数据管道：特征是否正常更新？
3. 检查模型：是否更新了模型？
4. 检查竞价策略：出价是否变化？
5. 检查外部环境：节假日/竞品活动？
6. 检查 A/B 实验：是否有实验干扰？
7. 回滚最近的变更
8. 逐步恢复并监控
```

---

## 第八部分：成长建议

```
面试准备建议：
1. 基础扎实：Go/MySQL/Redis 源码级理解
2. 广告知识：竞价/排序/召回/实验
3. 系统设计：能画架构图，能说清权衡
4. 实战经验：有生产排障案例
5. 表达能力：逻辑清晰，有条理
```
