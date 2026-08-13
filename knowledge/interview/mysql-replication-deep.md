# MySQL主从复制架构 --- 资深专家深度实现

## 概述

MySQL主从复制是实现高可用和读写分离的核心技术。本文深入剖析复制原理、延迟问题和故障切换方案。

## 一、复制原理

### 1.1 复制架构

```
┌─────────────────────────────────────────────────────────┐
│                    主从复制架构                          │
├─────────────────────────────────────────────────────────┤
│                                                          │
│   Master (主库)                                          │
│   ┌─────────────┐                                        │
│   │  Binlog     │───→ Network ───→ Slave               │
│   │  (二进制日志) │      (IO Thread)                      │
│   └─────────────┘                                        │
│        ↑                                                 │
│   SQL Thread ←── Relay Log (中继日志)                   │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

### 1.2 复制线程

```sql
-- 查看复制状态
SHOW SLAVE STATUS\G

-- 关键线程
-- 1. Slave I/O Thread: 连接Master，拉取Binlog
-- 2. Slave SQL Thread: 执行Relay Log中的SQL
-- 3. Master Dump Thread: 为Slave提供Binlog

-- 线程状态
-- Slave_IO_Running: Yes
-- Slave_SQL_Running: Yes
-- Seconds_Behind_Master: 0
```

### 1.3 复制模式

```sql
-- 1. 异步复制 (Asynchronous)
-- Master不等待Slave确认，性能最好，可能有数据丢失

-- 2. 半同步复制 (Semi-Synchronous)
-- Master至少等待一个Slave确认，数据安全性更高

-- 3. 全同步复制 (Fully Synchronous)
-- 所有Slave都确认后才返回，性能最差

-- 启用半同步复制
INSTALL PLUGIN rpl_semi_sync_master SONAME 'semisync_master.so';
SET GLOBAL rpl_semi_sync_master_enabled = ON;
```

## 二、延迟问题

### 2.1 延迟原因

```
┌─────────────────────────────────────────────────────────┐
│                    延迟产生原因                          │
├─────────────────────────────────────────────────────────┤
│  1. 网络延迟: Binlog传输耗时                           │
│  2. SQL线程单线程: 只能串行执行                         │
│  3. 大事务: 长事务阻塞后续执行                          │
│  4. 锁竞争: DDL操作阻塞                                │
│  5. 资源争抢: CPU/IO瓶颈                               │
└─────────────────────────────────────────────────────────┘
```

### 2.2 监控延迟

```sql
-- 实时监控延迟
SHOW SLAVE STATUS\G
-- Seconds_Behind_Master > 0 表示有延迟

-- 查询延迟趋势
SELECT 
    UNIX_TIMESTAMP() - MAX(creation_time) as max_delay
FROM mysql.slave_master_status;

-- 使用pt-heartbeat监控
pt-heartbeat -D mysql -t heartbeat --update --daemonize
```

### 2.3 减少延迟

```sql
-- 1. 并行复制 (MySQL 5.7+)
SET GLOBAL slave_parallel_type = 'LOGICAL_CLOCK';
SET GLOBAL slave_parallel_workers = 4;

-- 2. 优化Binlog格式
SET GLOBAL binlog_format = 'ROW';  -- 比STATEMENT更快

-- 3. 优化事务大小
-- 避免大事务，分批提交

-- 4. 使用GTID简化故障切换
SET GLOBAL enforce_gtid_consistency = ON;
SET GLOBAL gtid_mode = ON;
```

## 三、故障切换

### 3.1 MHA架构

```
┌─────────────────────────────────────────────────────────┐
│                    MHA故障切换架构                       │
├─────────────────────────────────────────────────────────┤
│                                                          │
│   Master                    Manager                     │
│   ┌─────────┐              ┌─────────┐                  │
│   │  DB1    │◄─────────────│  MHA    │                  │
│   └────┬────┘   VIP管理    └────┬────┘                  │
│        │                        │                       │
│   ┌────▼────┐              ┌────▼────┐                  │
│   │  DB2    │◄─────────────│  Monitor│                  │
│   └────┬────┘   主从监控   └─────────┘                  │
│        │                                                 │
│   ┌────▼────┐                                            │
│   │  DB3    │ (从库)                                     │
│   └─────────┘                                            │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

### 3.2 Orchestrator

```bash
# 使用Orchestrator进行拓扑发现和管理
./orchestrator -command discover -i db-master:3306

# 查看拓扑
./orchestrator -command topology -i db-master:3306

# 故障切换
./orchestrator -command failover -i db-master:3306
```

### 3.3 ProxySQL主从切换

```sql
-- ProxySQL管理主从配置
INSERT INTO mysql_servers(hostgroup_id,hostname,port) 
VALUES (10,'master',3306);

INSERT INTO mysql_servers(hostgroup_id,hostname,port) 
VALUES (20,'slave1',3306), (20,'slave2',3306);

-- 设置读取权重
UPDATE mysql_servers SET weight=10 WHERE hostgroup_id=20 AND hostname='slave1';
```

## 四、面试高频题

### 4.1 高频问题

**Q1: 主从复制的原理是什么？**

A: Master将数据变更写入Binlog，Slave通过IO线程拉取并写入Relay Log，SQL线程执行Relay Log中的SQL。

**Q2: 如何解决主从延迟？**

A:
- 开启并行复制
- 减小事务大小
- 优化网络带宽
- 使用半同步复制

**Q3: 什么是GTID？**

A: Global Transaction Identifier，全局唯一事务ID，简化故障切换和复制管理。

### 4.2 自测题

1. 画出主从复制架构图
2. 解释Binlog的三种格式
3. 分析主从延迟的原因
4. 设计一个高可用主从方案
5. 解释半同步复制的工作原理

---

**创建时间**: 2026-10-17
**作者**: Ryan
**领域**: Interview / 数据库
**关键词**: mysql, replication, master-slave, latency, failover
