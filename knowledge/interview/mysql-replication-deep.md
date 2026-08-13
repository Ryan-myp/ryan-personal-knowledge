# MySQL复制架构 - 资深专家深度实现

## 一、复制拓扑

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    MySQL 复制拓扑                                          │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   主从复制              主主复制              半同步复制                  │
│   ┌─────┐             ┌─────┐              ┌─────┐                      │
│   │ Master│───►│       │◄───│ Master │     │ Master│───►│              │
│   └─────┘             └─────┘              └─────┘    │                │
│        │                                         └─────┘                │
│        ▼                                                       │        │
│   ┌─────┐                                                     │        │
│   │ Slave │ ←── 异步，可能有延迟                            │  强一致│
│   └─────┘                                                     └────────┘
│                                                                         →
└─────────────────────────────────────────────────────────────────────────┘
```

## 二、半同步复制实现

```go
package replication

import (
    "context"
)

// SemiSyncConfig 半同步复制配置
type SemiSyncConfig struct {
    RplSemiSyncMaster     bool
    RplSemiSyncSlave      bool
    RplSemisyncTimeout    int
    RplSemisyncMasterRetry int
}

// ReplicationManager 复制管理器
type ReplicationManager struct {
    primary   *MySQLInstance
    slaves    []*MySQLInstance
}

// EnableSemiSync 启用半同步复制
func (m *ReplicationManager) EnableSemiSync(ctx context.Context) error {
    // 主库配置
    m.primary.Execute(ctx, "SET GLOBAL rpl_semi_sync_master_enabled=ON")
    m.primary.Execute(ctx, "SET GLOBAL rpl_semi_sync_master_timeout=1000")
    
    // 从库配置
    for _, slave := range m.slaves {
        slave.Execute(ctx, "SET GLOBAL rpl_semi_sync_slave_enabled=ON")
        slave.Execute(ctx, "START SLAVE")
    }
    
    return nil
}

// CheckStatus 检查复制状态
func (m *ReplicationManager) CheckStatus(ctx context.Context) (*Status, error) {
    result := m.primary.Query(ctx, "SHOW MASTER STATUS")
    slaveStatus := m.primary.Query(ctx, "SHOW SLAVE STATUS")
    
    return &Status{
        MasterLogPos: result.ExecutedGtidSet,
        SlaveIORunning: slaveStatus.IORunning,
        SlaveSQLRunning: slaveStatus.SQLRunning,
        SecondsBehindMaster: slaveStatus.SecondsBehindMaster,
    }, nil
}
```

## 三、面试高频题

### Q1: 半同步复制的优势？

```
A:
1. 数据强一致
2. 防止主库丢失
3. 性能损失小
```

### Q2: 如何解决复制延迟？

```
A:
1. 并行复制
2. 大事务拆分
3. 读取从库优化
```

## 四、自测题

1. 解释复制拓扑
2. 如何实现半同步？
3. 如何解决延迟？

---

## 参考文档

- [MySQL Replication](https://dev.mysql.com/doc/refman/8.0/en/replication.html)
- [Semi-Sync Replication](https://dev.mysql.com/doc/refman/8.0/en/replication-semisync.html)
