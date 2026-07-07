# 微信读书精华：技术基础与实战 蒸馏笔记

> 来源：《趣学数据结构》《大话数据结构》《ClickHouse入门、实战与进阶》《Elasticsearch数据搜索与分析实战》《Excel+Python：飞速搞定数据分析与处理》《Google API大全》《Python王者归来》
> 状态：未读完（基于目录和简介蒸馏）
> 蒸馏日期：2026-07-07
> 蒸馏方式：基于书名、作者、简介 + 知识库现有内容补充

---

## 第一部分：数据结构基础

### 1.1 数据结构知识体系

```
数据结构全景图：

线性结构                          非线性结构
├─ 数组（Array）                  ├─ 树（Tree）
├─ 链表（Linked List）            │  ├─ 二叉树 / 平衡二叉树
├─ 栈（Stack）                   │  ├─ B/B+ 树（数据库索引）
├─ 队列（Queue）                 │  ├─ Trie / Radix Tree
├─ 双端队列（Deque）             │  ├─ RB-Tree / AVL
└─ 哈希表（Hash Table）          │  └─ B+ Tree / LSM-Tree
                                 ├─ 图（Graph）
                                 │  ├─ 有向图 / 无向图
                                 │  ├─ 最短路径（Dijkstra/BFS）
                                 │  └─ 最小生成树（Prim/Kruskal）
                                 └─ 堆（Heap）
                                    ├─ 最大堆 / 最小堆
                                    └─ 二项堆 / Fibonacci 堆
```

### 1.2 核心数据结构深度解析

**数组 vs 链表 vs 哈希表（Go 视角）：**

```go
// 数组：连续内存，O(1) 随机访问
type ArraySlice struct {
    data []int  // Go slice 底层是连续内存数组
}

func (a *ArraySlice) Get(i int) int {
    return a.data[i]  // O(1) - 直接内存偏移
}

func (a *ArraySlice) Insert(i, v int) {
    a.data = append(a.data[:i+1], a.data[i:]...)
    a.data[i] = v  // O(n) - 需要移动元素
}

// 链表：离散内存，O(1) 插入删除（已知位置）
type ListNode struct {
    Val  int
    Next *ListNode
}

// 哈希表：Go map 底层是 hash array map
// O(1) 平均查找，O(n) 最坏（hash 冲突）
```

**B+ Tree 与 LSM-Tree 对比（数据库索引核心）：**

```
┌──────────────────┬──────────────────┬──────────────────┐
│     特性         │  B+ Tree         │  LSM-Tree        │
├──────────────────┼──────────────────┼──────────────────┤
│ 写入性能         │  中等（随机 IO）  │  极高（顺序写）   │
│ 读取性能         │  高（有序遍历）   │  中等（需合并）   │
│ 空间利用率       │  高              │  中（compaction） │
│ 适用场景         │  OLTP 数据库      │  宽表/日志系统    │
│ 代表系统         │  MySQL/PostgreSQL │  Cassandra/RocksDB│
│ 磁盘 IO 模式     │  随机读为主       │  顺序写为主       │
└──────────────────┴──────────────────┴──────────────────┘
```

### 1.3 算法复杂度速查

```
常见操作的时间复杂度：

操作          │ 数组  │ 链表  │ 哈希表 │ 二叉搜索树 │ B+树
──────────────┼───────┼───────┼────────┼────────────┼─────
查找          │ O(1)  │ O(n)  │ O(1)*  │ O(log n)   │ O(log n)
插入          │ O(n)  │ O(1)  │ O(1)*  │ O(log n)   │ O(log n)
删除          │ O(n)  │ O(1)  │ O(1)*  │ O(log n)   │ O(log n)
范围查询      │ O(n)  │ O(n)  │ N/A    │ O(log n+k) │ O(log n+k)

* 平均情况，最坏 O(n)（hash 冲突）
* k 为返回结果数量
```

---

## 第二部分：ClickHouse 实战

### 2.1 ClickHouse 架构核心

**参考：《ClickHouse入门、实战与进阶》+ 知识库 `ad-clickhouse-merge-tree-deep.md`**

```
ClickHouse 架构：

┌─────────────────────────────────────────────────────────────┐
│ 查询层                                                      │
│ ├─ HTTP/TCP 接口                                            │
│ ├─ 分片路由（Shard Routing）                                 │
│ └─ 查询优化器                                               │
├─────────────────────────────────────────────────────────────┤
│ 存储层                                                      │
│ ├─ MergeTree 引擎族                                         │
│ │  ├─ MergeTree（基础）                                     │
│ │  ├─ ReplicatedMergeTree（副本）                           │
│ │  ├─ AggregatingMergeTree（预聚合）                        │
│ │  └─ SummingMergeTree（求和）                              │
│ ├─ 列式存储（Columnar Storage）                              │
│ ├─ 向量化执行（Vectorized Execution）                        │
│ └─ 数据压缩（Codec）                                        │
├─────────────────────────────────────────────────────────────┤
│ 分布式层                                                    │
│ ├─ Distributed 表引擎                                       │
│ ├─ 分片键（Sharding Key）                                    │
│ └─ 副本策略（Replication）                                   │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 MergeTree 核心原理

```
MergeTree 数据组织：

数据分区（Partition）
  └─ 数据块（Granule，8192 rows）
       └─ 列文件（.mrk2 + .bin）
            ├─ primary.cmr  （主键索引）
            ├─ timestamp.bin（时间戳列）
            ├─ user_id.bin  （用户ID列）
            └─ ...

Merge 策略：
├─ 常规合并：后台线程定期合并数据块
├─ OPTIMIZE TABLE：手动触发合并
├─ 合并规则：
│  ├─ 相同分区内的数据块合并
│  ├─ 合并后的数据块按主键排序
│  └─ 标记删除（Tombstone）用于逻辑删除
└─ 合并的影响：
   ├─ 写入后数据立即可查（不等合并）
   ├─ 合并期间不影响查询
   └─ 过多小数据块会影响查询性能
```

### 2.3 ClickHouse 查询优化实战

```
ClickHouse 查询优化 checklist：

1. 分区键选择
   ├─ 按时间分区（天/月）
   ├─ 避免过多分区（< 1000）
   └─ 避免过少分区（每个分区 < 10GB）

2. 排序键设计
   ├─ 主键 = 排序键 + 稀疏索引
   ├─ 常用查询条件放前面
   └─  cardinality 高的字段放后面

3. 数据类型选择
   ├─ 用 LowCardinality 减少重复字符串
   ├─ 用 DateTime64 替代 String
   └─ 避免 Nullable（性能差）

4. 查询写法优化
   ├─ 尽量使用 WHERE 过滤（partition pruning）
   ├─ 避免 SELECT *（只查需要的列）
   ├─ 使用 PREWHERE 替代 WHERE（列式优化）
   └─ 合理使用 JOIN（SELECT 优先）

5. 物化视图
   ├─ 预聚合常用查询
   ├─ 实时更新 vs 批量更新
   └─ 注意写入放大
```

---

## 第三部分：Elasticsearch 搜索实战

### 3.1 ES 核心架构

**参考：《Elasticsearch数据搜索与分析实战》+ 知识库 `ad-elasticsearch-inverted-index-deep.md`**

```
ES 集群架构：

Node 类型：
├─ Master Node：集群管理（选举/分片分配）
├─ Data Node：数据存储 + 查询执行
├─ Coordinator Node：请求路由 + 结果聚合
└─ Ingest Node：文档预处理

索引结构：
├─ Index → Shard（主分片） → Replica Shard（副本分片）
├─ 每个 Shard = 独立的 Lucene 实例
└─ 分片策略：按 ID Hash 分布

倒排索引（Inverted Index）：
┌──────────────┬──────────────────────────────┐
│   Term       │   Document IDs               │
├──────────────┼──────────────────────────────┤
│   广告       │   [doc1, doc3, doc7]         │
│   投放       │   [doc1, doc5]               │
│   转化       │   [doc3, doc7, doc9]         │
│   点击       │   [doc1, doc3, doc5, doc9]   │
└──────────────┴──────────────────────────────┘

搜索流程：
1. Query 到达 Coordinator Node
2. Coordinator 将查询路由到所有相关 Shard
3. 每个 Shard 执行搜索（倒排索引 + BM25 打分）
4. Shard 返回 Top-K 结果给 Coordinator
5. Coordinator 合并排序，返回最终结果
```

### 3.2 ES 搜索优化策略

```
ES 搜索优化维度：

性能优化：
├─ 索引阶段：批量写入 > 单条写入
│  ├─ 使用 _bulk API
│  ├─ 调整 index.buffer.size
│  └─ 关闭刷新（refresh_interval=30s）
├─ 查询阶段：缓存命中 > 全量扫描
│  ├─ 使用 filter context（不走评分）
│  ├─ 合理设置 query_cache / request_cache
│  └─ 避免深分页（use_scroll / search_after）
└─ 集群层面：分片均衡 > 热点集中
   ├─ 监控 shard 分配
   ├─ 调整 routing shard count
   └─ 冷热数据分离

数据模型优化：
├─ 嵌套类型（nested）vs 父子文档（parent-child）
├─ 关键字（keyword）vs 文本（text）
├─ 动态映射（dynamic mapping）vs 显式 mapping
└─ 字段弃用（field dropping）减少存储
```

---

## 第四部分：Python 数据分析实战

### 4.1 Excel + Python 数据清洗流程

**参考：《Excel+Python：飞速搞定数据分析与处理》**

```
Excel 数据清洗 Python 流程：

Step 1: 读取 Excel（处理合并单元格和元数据）
├─ 跳过合并单元格导致的 NaN
├─ 识别并跳过元数据行（表头前的说明行）
├─ 处理多 sheet 合并
└─ 处理混合数据类型（数字/文本/日期）

Step 2: 数据清洗
├─ 缺失值处理：填充/删除/插值
├─ 重复值处理：drop_duplicates
├─ 异常值处理：IQR/Z-Score 检测
├─ 格式统一：日期/货币/百分比
└─ 列名标准化：去除空格/特殊字符

Step 3: 数据分析
├─ 描述性统计：mean/median/std/min/max
├─ 分组聚合：groupby + agg
├─ 透视表：pivot_table
├─ 时间序列：resample + rolling
└─ 相关性分析：corr + heatmap

Step 4: 数据可视化
├─ Matplotlib：基础绘图
├─ Seaborn：统计图表
├─ Plotly：交互式图表
└─ Pandas Profiling：自动 EDA 报告
```

### 4.2 Python 数据分析核心技能树

```
Python 数据分析技能树：

基础层：
├─ pandas：DataFrame 操作 / groupby / merge
├─ numpy：数组运算 / 广播机制 / ufunc
└─ matplotlib/seaborn：静态图表

进阶层：
├─ scipy/stats：统计检验 / 分布拟合
├─ statsmodels：回归分析 / 时间序列
└─ plotly/bokeh：交互式可视化

进阶层：
├─ scikit-learn：机器学习基础
├─ feature-engine：特征工程
└─ yellowbrick：模型可视化

专业层：
├─ PySpark：大规模数据处理
├─ Dask：并行计算
└─ Polars：高性能 DataFrame
```

---

## 第五部分：Google API 与 Python 进阶

### 5.1 Google API 生态

**参考：《Google API大全》**

```
Google API 核心服务：

认证授权：
├─ OAuth 2.0：用户授权访问
├─ Service Account：服务间授权
└─ API Key：简单访问（限流）

核心 API：
├─ Cloud APIs
│  ├─ Compute Engine：虚拟机管理
│  ├─ Cloud Storage：对象存储
│  ├─ Cloud Functions：Serverless
│  └─ Kubernetes Engine：容器编排
├─ Productivity APIs
│  ├─ Gmail API：邮件收发
│  ├─ Drive API：文件管理
│  ├─ Calendar API：日程管理
│  └─ Sheets API：电子表格
├─ Developer APIs
│  ├─ BigQuery：数据仓库
│  ├─ TensorFlow Hub：模型仓库
│  ├─ Vertex AI：AI 平台
│  └─ Cloud ML：机器学习
└─ Advertising APIs
   ├─ Google Ads API：广告投放
   ├─ Search Ads 360：搜索广告
   ├─ Display & Video 360：展示广告
   └─ Campaign Manager：广告追踪
```

### 5.2 Python 进阶核心概念

**参考：《Python王者归来》**

```
Python 进阶核心：

1. 装饰器（Decorator）
   ├── functools.wraps：保留元信息
   ├── 类装饰器：状态ful 装饰
   └─ 应用：日志/缓存/权限/重试

2. 生成器（Generator）
   ├── yield：惰性求值
   ├── 生成器表达式：内存友好
   └─ 应用：大数据流处理/协程

3. 元编程（Metaprogramming）
   ├── __metaclass__：自定义类创建
   ├── __getattr__/__setattr__：属性拦截
   └─ 应用：ORM/配置框架

4. 并发编程
   ├── threading：GIL 限制下的并发
   ├── multiprocessing：真正的并行
   ├── asyncio：异步 I/O
   └─ 应用：爬虫/爬虫/数据处理

5. 类型注解（Type Hints）
   ├── typing module：泛型/联合类型
   ├── mypy：静态类型检查
   └─ 应用：大型项目可维护性
```

---

## 第六部分：自测题

### Q1: ClickHouse 和 MySQL 在 OLAP 场景下的核心差异是什么？

**参考答案：**

| 维度 | ClickHouse | MySQL |
|------|-----------|-------|
| 存储格式 | 列式 | 行式 |
| 查询模式 | 全表扫描 + 向量化 | 索引扫描 |
| 写入吞吐 | 高（批量写入） | 中（单条/小批量） |
| 聚合速度 | 快 10-100x | 慢 |
| 实时性 | 近实时（秒级） | 实时 |
| 适用场景 | 分析型查询（OLAP） | 事务型查询（OLTP） |
| Join 支持 | 有限（ASOF/全局） | 完善 |
| 事务支持 | 无 | ACID |

**结论**：OLAP 场景用 ClickHouse，OLTP 场景用 MySQL，两者互补。

### Q2: ES 中 filter context 和 query context 的区别是什么？什么时候用哪个？

**参考答案：**

- **filter context**：只匹配不评分，结果可缓存，性能更好
  - 适用：精确匹配（term/range/exists）、布尔逻辑
  - 示例：`status: published`、`price: 100-200`

- **query context**：匹配并评分（BM25），结果不可缓存
  - 适用：全文搜索（match/multi_match）、相关性排序
  - 示例：`title: "广告优化"`

**最佳实践**：在 bool query 中，精确条件放 filter，文本搜索放 must。

### Q3: Python 中装饰器和元类的区别和使用场景？

**参考答案：**

| 特性 | 装饰器 | 元类 |
|------|-------|------|
| 作用对象 | 函数/方法/类 | 类的类 |
| 复杂度 | 低 | 高 |
| 可读性 | 好 | 差 |
| 适用场景 | 日志/缓存/权限/重试 | ORM/单例/注册表 |
| 执行时机 | 定义时 | 类创建时 |

**原则**：能用装饰器解决的不用元类，元类是最后手段。

---

## 第七部分：与知识库的对照

### 已有知识
- `knowledge/middleware/weread-tech-unread-deep.md` — 覆盖了 Redis/Go/Kafka/Elasticsearch/ClickHouse 等
- `knowledge/middleware/ad-clickhouse-merge-tree-deep.md` — ClickHouse MergeTree 源码级
- `knowledge/middleware/ad-elasticsearch-inverted-index-deep.md` — ES 倒排索引深度
- `knowledge/bigdata/ad-feature-store-consistency-deep.md` — 特征工程
- `knowledge/fullstack/weread-go-architect-deep.md` — Go 语言高级开发

### 本次蒸馏补充
- **数据结构基础**：线性/非线性结构全景、B+ Tree vs LSM-Tree、算法复杂度
- **ClickHouse 实战**：架构核心、MergeTree 数据组织、查询优化 checklist
- **Elasticsearch 搜索**：集群架构、倒排索引、搜索优化策略
- **Python 数据分析**：Excel 清洗流程、技能树、工具链
- **Google API 生态**：认证授权、核心服务分类
- **Python 进阶**：装饰器/生成器/元编程/并发/类型注解

### 缺失知识（建议后续补充）
- [ ] ClickHouse 分布式查询原理（Consistent Hashing）
- [ ] ES 分片分配策略与扩容方案
- [ ] Python 性能 profiling（cProfile/py-spy）
- [ ] 数据仓库建模（星型/雪花/数据湖）
- [ ] Google Cloud 广告 API 集成实战
