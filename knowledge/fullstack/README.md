# 全栈深入知识库

> Go/MySQL/Redis/ES/ClickHouse/大数据 — 源码级深度

## 文档索引

| 文档 | 深度 | 行数 | 说明 |
|------|------|------|------|
| [go-deep-dive.md](./go-deep-dive.md) | 源码级 | ~1050行 | GMP调度器/GC/网络轮询器/内存分配器 |
| [mysql-kernel.md](./mysql-kernel.md) | 源码级 | ~875行 | InnoDB内核/事务/锁/redo/undo |
| [redis-source.md](./redis-source.md) | 源码级 | ~684行 | Redis底层数据结构/持久化/集群 |
| [es-deep.md](./es-deep.md) | 源码级 | ~435行 | Elasticsearch底层原理/倒排索引/Routing |
| [clickhouse.md](./clickhouse.md) | 源码级 | ~331行 | ClickHouse存储引擎/列式计算/MergeTree |
| 大数据生态 | [big-data.md](./big-data.md) | Hadoop/Spark/Flink |

---

## 自测题

### 问题 1
Go 中如何实现一个高性能的 Buffer Pool？

<details>
<summary>查看答案</summary>

1. **sync.Pool**：Go 内置的对象池，减少 GC 压力
2. **预分配**：一次性分配大量对象，按需获取
3. **示例**：
```go
var bufferPool = sync.Pool{
    New: func() interface{} {
        buf := make([]byte, 32*1024)
        return &buf
    },
}

func processData() {
    buf := bufferPool.Get().(*[]byte)
    defer bufferPool.Put(buf)
    // 使用 buf...
}
```
4. **适用场景**：HTTP 请求体、日志 buffer、临时数据结构
5. **注意事项**：Pool 中的对象可能会被 GC 回收，不要依赖对象状态

</details>

### 问题 2
Redis 的 SDS 字符串和 Go 的 string 有什么区别？

<details>
<summary>查看答案</summary>

1. **Redis SDS**：二进制安全，可缓存长度，预分配空间
2. **Go string**：不可变，UTF-8 编码，GC 管理
3. **性能差异**：
   - SDS 的 len() 是 O(1)，Go string 也是 O(1)（通过 header 存储长度）
   - SDS 的拼接是 O(n)，Go string 的拼接也是 O(n)
4. **Go 优化**：strings.Builder 用于频繁字符串拼接

</details>

```
Go 语言深入 (GMP/GC/内存)
    ↓
MySQL 内核 (InnoDB/事务/锁)
    ↓
Redis 源码 (数据结构/持久化)
    ↓
Elasticsearch (倒排索引/Routing)
    ↓
ClickHouse (列式存储/MergeTree)
    ↓
大数据生态 (Hadoop/Spark/Flink)
```
