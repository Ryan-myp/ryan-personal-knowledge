# 分布式数据库深度：TiDB 架构（TiDB/TiKV/PD 三组件）

> 从架构到源码逐行解析 TiDB 三组件架构，理解分布式 SQL 引擎如何协同工作

---

## 第一部分：TiDB 架构总览

### 为什么广告平台需要 TiDB？

```
MySQL 在广告平台的瓶颈：
1. 单表 10 亿+ 行 → 索引膨胀，查询慢
2. 写入 QPS 10 万+ → 单点写入瓶颈
3. 热点行 → 单 partition 被打满
4. 跨机房部署 → 主从延迟大

TiDB 解决方案：
1. 自动分片（16384 Region，自动 Split/Merge）
2. 并行查询（PD 调度，TiKV 分布式）
3. 强一致性（Raft 保证）
4. 多机房部署（PD 多副本）
```

### TiDB 三组件架构

```
                    用户请求
                       │
              ┌────────┴────────┐
              │   TiDB Server    │
              │  (SQL 引擎)      │
              │  Go 实现         │
              │  无状态          │
              └───────┬─────────┘
                      │ gRPC
         ┌────────────┼────────────┐
         │            │            │
┌────────┴──────┐ ┌───┴────────┐ ┌──┴──────────┐
│   TiKV Node 1  │ │ TiKV Node 2│ │ TiKV Node 3  │
│  (存储引擎)    │ │ (存储引擎)  │ │ (存储引擎)   │
│  Raft 状态机   │ │ Raft 状态机 │ │ Raft 状态机  │
│  RocksDB       │ │ RocksDB     │ │ RocksDB      │
│  Region 0-5460 │ │ Region 5461│ │ Region 10921 │
│  Region 10921- │ │ Region 0-5 │ │ Region 6-5460│
│  16383         │ │ 16383      │ │ 10921-16383  │
└────────────────┘ └────────────┘ └──────────────┘
         ▲              ▲              ▲
         │              │              │
┌────────┴──────────────┴──────────────┴────────┐
│                   PD Server                    │
│  (Placement Driver)                           │
│  - 分配全局唯一 ID                            │
│  - 调度 Region（Split/Merge/Migrate）          │
│  - 管理集群拓扑                               │
│  - 存储元数据（etcd）                         │
└────────────────────────────────────────────────┘
```

---

## 第二部分：TiDB Server 源码深度

### TiDB Server 的职责

```
TiDB Server（无状态 SQL 执行器）：
├── SQL 解析：ANTLR 解析 SQL 语句
├── 逻辑计划：构建优化后的执行计划
├── 物理计划：选择最优执行策略
├── 执行引擎：并行执行查询（Coprocessor）
└── 事务控制：管理 2PC 事务

特点：
- 无状态：可以水平扩展
- 多租户：支持 Schema/DB/Table
- 协议兼容：MySQL 5.7 协议
```

### 源码逐行解析：executeStmt

```go
// TiDB 源码：executor/ddl.go - executeStmt
// 执行一条 SQL 语句

func (s *server) executeStmt(ctx context.Context, stmtNode ast.Node) (
    []sqlexec.RecordSet, error) {
    
    // 1. 从 Session 获取 Connection ID
    connID := ctx.GetSessionVars().ConnectionID
    
    // 2. 记录执行开始时间
    startTime := time.Now()
    stmtText := ast.NodeText(ctx, stmtNode)
    
    // 3. 检查是否允许执行
    if !ctx.Auth() {
        return nil, ErrAccessDenied
    }
    
    // 4. 构建逻辑执行计划
    planBuilder := planner.NewBuilder(ctx)
    logicalPlan := planBuilder.Build(stmtNode)
    if logicalPlan == nil {
        return nil, errors.New("plan building failed")
    }
    
    // 5. 优化执行计划
    logicalPlan = planner.Optimize(ctx, logicalPlan, s.domain.InfoSchema())
    
    // 6. 编译为物理执行计划
    physicalPlan, err := logicalPlan.OptimizePrepared()
    if err != nil {
        return nil, err
    }
    
    // 7. 构建 Exec 执行器
    exec, err := builder.Build(physicalPlan)
    if err != nil {
        return nil, err
    }
    
    // 8. 执行计划
    var recordSets []sqlexec.RecordSet
    
    // 8.1 查询类：构建 Coprocessor 请求
    switch x := exec.(type) {
    case *executor.TableReaderExecutor:
        // 构建 CopRequest 发送给 TiKV
        copReq := &coprocessor.Request{
            Tp: int32(kvrpcpb.CmdType_SelectFromTiKV),
            Data: x.GetCopRequest(),
        }
        // 并行执行 Coprocessor
        result := copIterator(copReq, ctx)
        recordSets = append(recordSets, result)
        
    case *executor.InsertExecutor:
        // INSERT：写入 TiKV（2PC）
        result := x.Exec()
        recordSets = append(recordSets, result)
        
    case *executor.UpdateExecutor:
        // UPDATE：读取 + 修改 TiKV（2PC）
        result := x.Exec()
        recordSets = append(recordSets, result)
    }
    
    // 9. 执行统计
    ctx.GetSessionVars().StmtCtx.DurationParse = time.Since(startTime)
    
    return recordSets, nil
}
```

**关键点**：
- **无状态**：TiDB Server 不存储数据，所有数据操作通过 Coprocessor 下发到 TiKV
- **Coprocessor**：将计算推送到存储层，减少网络传输
- **2PC**：写操作（INSERT/UPDATE/DELETE）使用两阶段提交

### Coprocessor 机制

```
Coprocessor 流程：
┌──────────┐    CopRequest     ┌──────────┐
│ TiDB     │ ──────────────► │ TiKV     │
│ Server   │                   │ Node     │
│          │ ◄────────────── │          │
│          │  CopResponse      │          │
└──────────┘    (Partial)      └──────────┘

CopRequest 内容：
- Table ID, Index ID
- Key range（起始 Key ~ 结束 Key）
- 过滤条件（Where/Order By/Limit）
- 聚合函数（SUM/COUNT/MAX/MIN）

CopResponse 内容：
- 部分聚合结果（Partial）
- TiDB 合并多个 TiKV 的 Partial 结果
```

---

## 第三部分：TiKV 源码深度

### TiKV 存储架构

```
TiKV 存储引擎：
┌─────────────────────────────────────────────────┐
│              TiKV Server                         │
│                                                  │
│  ┌────────────────────────────────────────────┐  │
│  │               Raft Store                   │  │
│  │  Raft Group: Region 0 ~ Region 16383        │  │
│  │  Raft State Machine                        │  │
│  │  - Ready → Apply → Commit                  │  │
│  │                                            │  │
│  │  Region 边界：                             │  │
│  │  Region 1: [nil, "abc")                    │  │
│  │  Region 2: ["abc", "xyz")                  │  │
│  │  Region 3: ["xyz", nil)                    │  │
│  └────────────────────────────────────────────┘  │
│                                                  │
│  ┌────────────────────────────────────────────┐  │
│  │               RocksDB                      │  │
│  │  Default CF: 业务数据 + 索引                │  │
│  │  Write CF:    WAL + MVCC 版本               │  │
│  │  Lock CF:     分布式锁                      │  │
│  │  Range CF:    Tombstone                    │  │
│  └────────────────────────────────────────────┘  │
│                                                  │
│  数据分布：                                      │
│  - 每个 Region 约 96MB                           │
│  - 自动 Split：Region 过大时自动分裂              │
│  - 自动 Merge：Region 过小时合并                 │
└─────────────────────────────────────────────────┘
```

### 源码逐行解析：KVStore.get

```rust
// TiKV 源码：src/storage/txn/mod.rs
// KVStore.get — 读操作

pub async fn get(&self, key: Key, start_ts: Timestamp) -> Result<Value> {
    // 1. 查找 key 所在的 Region
    let region = self.region_cache.get_region_by_key(&key)?;
    
    // 2. 构建 Get 请求
    let req = GetRequest {
        key: key.into_raw(),
        timestamp: start_ts.into_inner(),
        not_found_error: true,
    };
    
    // 3. 发送给 Region Leader
    let resp = self.client.get(&region, &req).await?;
    
    // 4. 检查锁
    if resp.has_lock() {
        let lock = resp.lock.unwrap();
        // 4.1 如果是当前事务的锁，跳过
        if lock.txn_id == self.start_ts {
            // 读取旧版本
            return self.get_history(key, lock.start_ts).await;
        }
        // 4.2 等待锁释放
        self.wait_lock(&lock).await?;
    }
    
    // 5. 从 RocksDB 读取数据
    let value = self.blocking_get_from_rocksdb(key).await?;
    
    // 6. MVCC 读取：找到 start_ts 之前的最新提交
    let mut current_ts = start_ts;
    loop {
        let commit = self.get_commit_info(key, current_ts).await;
        if let Some(commit_ts) = commit {
            if commit_ts <= start_ts {
                // 找到了 start_ts 之前最新提交
                return self.get_value_at(key, commit_ts).await;
            }
            current_ts = commit_ts;
        } else {
            break;
        }
    }
    
    Err(Error::KeyNotFound(key))
}
```

**关键点**：
- **Region 路由**：通过 Region Cache 找到 key 对应的 Region Leader
- **锁检测**：读取时检查是否有未释放的锁
- **MVCC 链**：从 start_ts 向前遍历，找到最新提交版本

### 写操作源码：KVStore.prewrite

```rust
// TiKV 源码：src/storage/txn/actions/prewrite.rs
// prewrite — 2PC 第一阶段：预写

pub async fn prewrite(&self, key: Key, value: Option<Value>, 
                      primary: Key, start_ts: Timestamp) -> Result<()> {
    // 1. 检查主 Key 是否存在
    let primary_lock = self.get_lock(primary).await?;
    if let Some(lock) = primary_lock {
        // 检查锁是否过期
        if self.is_lock_expired(&lock).await {
            self.cleanup_lock(primary).await?;
        } else {
            return Err(Error::Deadlock(lock.txn_id));
        }
    }
    
    // 2. 写入锁（Lock CF）
    let lock = Lock {
        op: Op::Put,
        start_ts: start_ts,
        ttl: self.lock_ttl(),
        primary: primary.clone(),
        value: value.clone(),
    };
    
    // 3. 写入 RocksDB Lock CF
    self.put_lock(primary, &lock).await?;
    
    // 4. 写入数据（Write CF）
    let write = Write {
        op: Op::Put,
        start_ts: start_ts,
        commit_ts: None,  // 2PC 第一阶段不写 commit_ts
        short_value: value,
    };
    
    // 5. 写入 RocksDB Write CF
    self.put_write(key, &write).await?;
    
    // 6. 通知 PD 更新 region 缓存
    self.region_cache.refresh().await?;
    
    Ok(())
}
```

---

## 第四部分：PD 源码深度

### PD 的职责

```
PD（Placement Driver）职责：
├── 全局唯一 ID 分配（TSO：Timestamp Oracle）
│   └── 物理位 + 逻辑位（64 bit）
├── Region 调度
│   ├── Split：Region 过大时分裂
│   ├── Merge：Region 过小时合并
│   └── Replica：增减副本数
├── 集群拓扑管理
│   ├── 节点上下线
│   └── Region 迁移（Leader/Syncer）
├── 元数据存储
│   └── etcd（Raft 一致性）
└── 配置管理
    └── 全局配置下发
```

### TSO（时间戳 oracle）源码

```go
// PD 源码：tso/tso.go - tsoAllocator
// 生成全局唯一时间戳

type TSO struct {
    physical int64
    logical  int64
}

func (a *tsoAllocator) GenerateTSO(count uint32) ([]TSO, error) {
    // 1. 从 etcd 获取当前物理时间
    physical, err := a.getPhysical()
    if err != nil {
        return nil, err
    }
    
    // 2. 获取当前逻辑时间
    logical, err := a.getLogical()
    if err != nil {
        return nil, err
    }
    
    // 3. 分配 TSO
    var result []TSO
    for i := uint32(0); i < count; i++ {
        tso := TSO{
            physical: physical,
            logical:  logical + int64(i),
        }
        result = append(result, tso)
    }
    
    // 4. 更新逻辑时间
    a.setLogical(logical + int64(count))
    
    return result, nil
}

func encodeTSO(tso TSO) uint64 {
    // 高 42 位：物理时间（毫秒）
    // 低 22 位：逻辑时间
    return uint64(tso.physical)<<22 | uint64(tso.logical)
}
```

**关键点**：
- **42 位 + 22 位**：物理时间支持约 139 年，逻辑时间支持约 400 万 TPS
- **Raft Leader**：只有 PD Leader 生成 TSO，避免冲突
- **时钟回拨保护**：检测时钟回拨，强制等待

---

## 第五部分：自测题

### Q1: TiDB 和 MySQL 的区别？

**A**:
| 维度 | MySQL | TiDB |
|------|-------|------|
| **架构** | 单机 | 计算存储分离 |
| **分片** | 手动分库分表 | 自动分片 |
| **扩展性** | 纵向扩展为主 | 横向扩展 |
| **事务** | InnoDB 本地事务 | 分布式 2PC |
| **兼容性** | MySQL 协议 | MySQL 5.7 协议 |

### Q2: TiDB 的 TSO 和 MySQL 的自增 ID 区别？

**A**:
- **MySQL 自增 ID**：单机递增，主从切换可能重复
- **TiDB TSO**：全局唯一，64 位 ID，自动分片安全
- TiDB 的 AUTO_INCREMENT 实际上是 TSO 的前缀

### Q3: Region Split 的阈值是多少？

**A**: 默认 96MB（可配置）。当 Region 大小超过 96MB 时，PD 触发 Split，将 Region 一分为二。Split 是异步的，不影响读写。

---

## 第六部分：生产实践

### 1. 热点 Key 问题

```
热点 Key 原因：
- 自增主键：所有写入集中在最后一个 Region
- 时间序列：最近的数据集中在一个 Region

解决方案：
1. 使用 UUID 作为主键（随机分布）
2. 使用影子列（Shadow Column）打散
3. 使用 Row ID 作为主键（TiDB 默认）

示例：
-- 不推荐：自增主键
CREATE TABLE orders (id INT AUTO_INCREMENT, ...);

-- 推荐：TiDB 自动 Row ID
CREATE TABLE orders (id BIGINT UNSIGNED, ...);

-- 手动打散
CREATE TABLE orders (
    id BIGINT,
    hash_id BIGINT AS (ABS(MOD(id, 10000))),
    PRIMARY KEY (hash_id, id)
);
```

### 2. 慢查询优化

```sql
-- 查看慢查询
SHOW PROCESSLIST;

-- 查看执行计划
EXPLAIN SELECT * FROM orders WHERE user_id = 123;

-- TiDB 特有优化：
-- 1. 使用覆盖索引
-- 2. 避免 SELECT *
-- 3. 使用索引覆盖
-- 4. 分批查询大结果集
```

### 3. 容量规划

```
Region 计算：
- 每个 Region ~ 96MB
- 总容量 = Region 数 × 96MB
- 推荐：16384 Region（默认）

存储计算：
- 单副本：100GB → 100GB
- 三副本：100GB → 300GB
- 写放大：~2x（WAL + MVCC）

推荐配置：
- 10TB 数据 → 3x3 节点
- 100TB 数据 → 10x3 节点
```
