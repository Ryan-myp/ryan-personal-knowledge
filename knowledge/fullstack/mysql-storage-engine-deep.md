# MySQL 存储引擎深度解析

> 深入 MySQL 存储引擎：InnoDB、MyISAM、Memory 对比。
> 源码级分析，包含引擎选择建议。
> 适用对象：DBA、后端工程师、系统工程师

---

## 1. InnoDB 引擎

### 1.1 核心特性

```
┌─────────────────────────────────────────────────────────────┐
│                  InnoDB 核心特性                             │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  事务支持                                                    │
│  ├── ACID 事务                                              │
│  ├── MVCC 多版本并发控制                                    │
│  ├── 行级锁                                                │
│  └── 支持回滚                                              │
│                                                             │
│  存储结构                                                    │
│  ├── 聚簇索引（主键索引）                                    │
│  ├── 二级索引                                              │
│  ├──  redo log（事务日志）                                  │
│  └──  undo log（回滚日志）                                  │
│                                                             │
│  性能优化                                                    │
│  ├── Buffer Pool 缓存                                      │
│  ├── Change Buffer 变更缓冲                                │
│  ├── Read View 读视图                                      │
│  └── Doublewrite Buffer 双写缓冲                            │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 1.2 InnoDB 架构

```
┌─────────────────────────────────────────────────────────────┐
│                    InnoDB 架构                               │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │                 Buffer Pool                         │   │
│  │  ├── 数据页缓存                                      │   │
│  │  ├── 索引页缓存                                      │   │
│  │  └── 自适应哈希索引                                  │   │
│  └─────────────────────────────────────────────────────┘   │
│                         │                                   │
│          ┌──────────────┼──────────────┐                   │
│          ▼              ▼              ▼                    │
│  ┌───────────┐  ┌───────────┐  ┌───────────┐              │
│  │ redo log  │  │ undo log  │  │ Change    │              │
│  │ (重做日志) │  │ (回滚日志) │  │  Buffer   │              │
│  └───────────┘  └───────────┘  └───────────┘              │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. MyISAM 引擎

### 2.1 核心特性

```
MyISAM 特性：

├── 不支持事务
├── 表级锁
├── 不支持外键
├── 支持全文索引
└── 适合读多写少场景
```

### 2.2 MyISAM vs InnoDB

```
┌─────────────────────────────────────────────────────────────┐
│                  MyISAM vs InnoDB 对比                      │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  特性              │ MyISAM        │ InnoDB                │
│  ├─────────────────┼───────────────┼───────────────────────┤
│  │ 事务支持         │ ❌             │ ✅                    │
│  │ 行级锁          │ ❌             │ ✅                    │
│  │ 外键支持        │ ❌             │ ✅                    │
│  │ 全文索引        │ ✅             │ ✅（5.6+）            │
│  │ 崩溃恢复        │ ❌             │ ✅                    │
│  │ 存储空间        │ 较小           │ 较大                  │
│  └─────────────────┴───────────────┴───────────────────────┘
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. Memory 引擎

### 3.1 核心特性

```
Memory 引擎特性：

├── 数据存储在内存中
├── 访问速度快
├── 重启后数据丢失
├── 支持哈希索引
└── 适合临时表、缓存表
```

---

## 4. 引擎选择指南

### 4.1 选择决策树

```
需要事务支持？
├── 是 → InnoDB
└── 否
    ├── 读多写少？
    │   ├── 是 → MyISAM
    │   └── 否 → InnoDB
    └── 临时数据？
        ├── 是 → Memory
        └── 否 → InnoDB
```

### 4.2 Go 实现引擎选择

```go
// engine_selector.go

package db

import "strings"

type EngineSelector struct{}

func (s *EngineSelector) SelectEngine(
    requiresTransaction bool,
    readWriteRatio float64,
    isTempTable bool,
) string {
    if requiresTransaction {
        return "InnoDB"
    }
    
    if isTempTable {
        return "Memory"
    }
    
    if readWriteRatio > 10.0 {
        return "MyISAM"
    }
    
    return "InnoDB"
}

func (s *EngineSelector) CheckEngineCompatibility(
    engine string,
    features []string,
) ([]string, error) {
    var issues []string
    
    switch engine {
    case "MyISAM":
        for _, feature := range features {
            if feature == "transaction" || feature == "foreign_key" {
                issues = append(issues, "MyISAM does not support "+feature)
            }
        }
    }
    
    return issues, nil
}
```

---

## 5. 性能优化

### 5.1 InnoDB 优化

```sql
-- 调整 Buffer Pool 大小
SET GLOBAL innodb_buffer_pool_size = 2147483648;  -- 2GB

-- 调整日志文件大小
SET GLOBAL innodb_log_file_size = 536870912;  -- 512MB

-- 调整刷盘策略
SET GLOBAL innodb_flush_log_at_trx_commit = 2;
```

### 5.2 性能监控

```sql
-- 查看 InnoDB 状态
SHOW ENGINE INNODB STATUS;

-- 查看 Buffer Pool 状态
SHOW STATUS LIKE 'Innodb_buffer_pool%';

-- 查看锁状态
SELECT * FROM information_schema.innodb_locks;
```

---

## 6. 故障排查

### 6.1 常见问题

| 问题 | 症状 | 排查命令 | 解决方案 |
|------|------|----------|----------|
| 锁等待超时 | 事务阻塞 | `SHOW ENGINE INNODB STATUS` | 优化查询/增加超时 |
| 缓冲池不足 | 性能下降 | `SHOW STATUS LIKE 'Innodb_buffer_pool%'` | 增加 buffer pool |
| 日志文件损坏 | 启动失败 | 检查错误日志 | 重建日志文件 |
| 死锁频繁 | 事务回滚 | `SHOW ENGINE INNODB STATUS` | 优化事务顺序 |

---

## 7. 总结

### 7.1 核心原理回顾

| 引擎 | 核心特性 | 适用场景 |
|------|----------|----------|
| InnoDB | 事务/行锁/MVCC | 通用场景 |
| MyISAM | 表锁/全文索引 | 读多写少 |
| Memory | 内存存储 | 临时数据 |

### 7.2 最佳实践

- [ ] 默认使用 InnoDB
- [ ] 合理配置 Buffer Pool
- [ ] 监控锁等待
- [ ] 定期清理日志

---

*最后更新：2026-08-11*
*作者：Ryan*
