# 数据湖深度：Iceberg/Hudi/Delta Lake

> 逐行源码解析 + 生产排障案例 + 对比分析 + 动手验证

---

## 第一部分：入门引导（5 分钟速览）

### 类比理解数据湖

```
数据湖 = 大仓库

原始数据湖（Raw Lake）：
→ 所有数据直接存放
→ Schema on Read（读时模式）
→ 灵活但乱

数据湖表（Lake Table）：
→ 结构化查询
→ Schema on Write（写时模式）
→ ACID 事务
```

### 数据湖核心挑战

```
1. 数据更新：传统 HDFS 不支持更新/删除
2. 数据质量：垃圾进垃圾出
3. 小文件问题：大量小文件影响性能
4.  Schema 演化：表结构变更
```

---

## 第二部分：Apache Iceberg 深度

### 2.1 Iceberg 架构

```
Iceberg 表结构：
Snapshot：表的快照
Manifest：指向数据文件的清单
Metadata：元数据文件

优势：
1. 隐藏分区：不需要知道分区列
2. Schema 演化：支持字段添加/删除/重命名
3. 时间旅行：查询历史版本
4. 合并小文件：Compaction
```

### 2.2 Go 实现简化 Iceberg

```go
package iceberg

import (
    "time"
)

// Table 表结构
type Table struct {
    Name        string
    Location    string
    Snapshots   []Snapshot
    Current     *Snapshot
    Schema      *Schema
}

// Snapshot 快照
type Snapshot struct {
    ID        int64
    Timestamp time.Time
    Manifests []Manifest
    Parent    *int64
}

// Manifest 清单
type Manifest struct {
    Path    string
    DataFiles []string
    Added   bool
}

// Schema 模式
type Schema struct {
    Fields []Field
}

type Field struct {
    ID    int
    Name  string
    Type  string
    Required bool
}

// 时间旅行查询
func (t *Table) QueryAt(version int64) (*Snapshot, error) {
    for i := len(t.Snapshots) - 1; i >= 0; i-- {
        if t.Snapshots[i].ID == version {
            return &t.Snapshots[i], nil
        }
    }
    return nil, fmt.Errorf("version not found")
}

// 添加新数据
func (t *Table) AddData(files []string) error {
    newManifest := Manifest{
        Path:    fmt.Sprintf("manifest-%d.avro", len(t.Snapshots)),
        DataFiles: files,
        Added:   true,
    }
    
    newSnapshot := Snapshot{
        ID:        time.Now().UnixNano(),
        Timestamp: time.Now(),
        Manifests: []Manifest{newManifest},
        Parent:    &t.Current.ID,
    }
    
    t.Snapshots = append(t.Snapshots, newSnapshot)
    t.Current = &newSnapshot
    
    return nil
}
```

---

## 第三部分：Delta Lake 深度

### 3.1 Delta Lake 架构

```
Delta Lake = Parquet + 事务日志

事务日志（_delta_log）：
→ JSON 格式
→ 记录每次提交
→ 保证 ACID 事务

优势：
1. ACID 事务：并发控制
2. 时间旅行：历史查询
3. Schema 演化：结构变更
4. Upsert：MERGE INTO
```

### 3.2 Go 实现简化 Delta Lake

```go
package deltalake

import (
    "encoding/json"
    "os"
    "time"
)

// DeltaTable Delta 表
type DeltaTable struct {
    path      string
    logs      []TransactionLog
    current   *TransactionLog
}

// TransactionLog 事务日志
type TransactionLog struct {
    Version    int64       `json:"version"`
    Timestamp  time.Time   `json:"timestamp"`
    AddFiles   []FileOp    `json:"add"`
    RemoveFiles []FileOp   `json:"remove"`
}

type FileOp struct {
    Path     string `json:"path"`
    Size     int64  `json:"size"`
    IsRemove bool   `json:"isRemove"`
}

// Commit 提交事务
func (dt *DeltaTable) Commit(addFiles, removeFiles []string) error {
    log := TransactionLog{
        Version:   int64(len(dt.logs)),
        Timestamp: time.Now(),
    }
    
    for _, f := range addFiles {
        size, _ := getFileSize(f)
        log.AddFiles = append(log.AddFiles, FileOp{
            Path: f,
            Size: size,
        })
    }
    
    for _, f := range removeFiles {
        log.RemoveFiles = append(log.RemoveFiles, FileOp{
            Path:     f,
            IsRemove: true,
        })
    }
    
    // 写入日志
    logPath := fmt.Sprintf("%s/_delta_log/%d.json", dt.path, log.Version)
    data, _ := json.Marshal(log)
    os.WriteFile(logPath, data, 0644)
    
    dt.logs = append(dt.logs, log)
    dt.current = &log
    
    return nil
}

// ReadAt 读取历史版本
func (dt *DeltaTable) ReadAt(version int64) ([]string, error) {
    if version >= int64(len(dt.logs)) {
        return nil, fmt.Errorf("version not found")
    }
    
    var files []string
    for _, log := range dt.logs[:version+1] {
        for _, f := range log.AddFiles {
            files = append(files, f.Path)
        }
        for _, f := range log.RemoveFiles {
            // 移除文件
            // ...
        }
    }
    
    return files, nil
}
```

---

## 第四部分：数据湖对比

### 4.1 Iceberg vs Delta Lake vs Hudi

| 特性 | Iceberg | Delta Lake | Hudi |
|------|---------|------------|------|
| **开发方** | Netflix | Databricks | Uber |
| **事务日志** | JSON | JSON | JSON |
| **时间旅行** | ✅ | ✅ | ✅ |
| **Upsert** | ✅ | ✅ | ✅ |
| **Schema 演化** | ✅ | ✅ | ✅ |
| **隐藏分区** | ✅ | ❌ | ❌ |
| **Spark 原生** | ✅ | ✅ | ✅ |
| **Flink 支持** | ✅ | ❌ | ✅ |
| **Hive 兼容** | ✅ | ✅ | ❌ |

### 4.2 选型建议

```
选 Iceberg：
→ 多计算引擎（Spark/Flink/Presto）
→ 需要隐藏分区
→ 社区活跃

选 Delta Lake：
→ Databricks 生态
→ 需要强 ACID
→ Spark 为主

选 Hudi：
→ 实时流处理
→ Flink 生态
→ UPSERT 场景
```

---

## 第五部分：生产排障案例

### 5.1 小文件问题

```
现象：数据湖文件数爆炸

排查：
1. 检查写入频率
2. 检查每个文件的大小
3. 检查分区策略

根因：高频小批量写入

解决方案：
1. 合并小文件
2. 批量写入
3. 调整分区策略
```

### 5.2 时间旅行查询慢

```
现象：历史版本查询超时

排查：
1. 检查 Snapshot 数量
2. 检查 Manifest 文件
3. 检查数据量

根因：Snapshots 过多

解决方案：
1. 定期删除过期快照
2. 优化 Manifest 读取
3. 使用缓存
```

---

## 第六部分：自测题

### 问题 1
Iceberg 相比传统 Hive 表有什么优势？

<details>
<summary>查看答案</summary>

1. **隐藏分区**：不需要知道分区列
2. **Schema 演化**：支持结构变更
3. **时间旅行**：历史查询
4. **合并小文件**：Compaction
5. **Go 实现**：Iceberg Table

</details>

### 问题 2
Delta Lake 的事务日志是什么格式？

<details>
<summary>查看答案</summary>

1. **JSON 格式**
2. **版本化**：每个版本一个文件
3. **原子性**：保证事务一致性
4. **追加写入**：不修改已有日志
5. **Go 实现**：TransactionLog

</details>

### 问题 3
什么时候应该用数据湖而不是数仓？

<details>
<summary>查看答案</summary>

1. **数据多样性**：结构化/半结构化/非结构化
2. **灵活性**：Schema on Read
3. **成本**：对象存储便宜
4. **实时性**：支持流式写入
5. **Go 实现**：Iceberg/Delta Lake

</details>

---

*本文档基于数据湖架构原理整理。*