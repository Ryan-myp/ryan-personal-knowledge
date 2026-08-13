# 分布式ID生成 - 资深专家深度实现

## 一、Snowflake算法

```go
package snowflake

import (
    "sync"
    "time"
)

type Snowflake struct {
    mu          sync.Mutex
    lastTs      int64
    sequence    int64
    workerId    int64
    datacenterId int64
}

const (
    workerIdBits    = 5
    datacenterIdBits = 5
    maxWorkerId     = -1 ^ (-1 << workerIdBits)
    maxDatacenterId = -1 ^ (-1 << datacenterIdBits)
    sequenceBits    = 12
    workerIdShift   = sequenceBits
    datacenterIdShift = sequenceBits + workerIdBits
    timestampLeftShift = sequenceBits + workerIdBits + datacenterIdBits
    sequenceMask      = -1 ^ (-1 << sequenceBits)
)

func (s *Snowflake) NextID() int64 {
    s.mu.Lock()
    defer s.mu.Unlock()
    
    ts := time.Now().UnixMilli()
    if ts < s.lastTs {
        return -1 // 时钟回拨
    }
    
    if ts == s.lastTs {
        s.sequence = (s.sequence + 1) & sequenceMask
        if s.sequence == 0 {
            ts = s.waitNextMillis(ts)
        }
    } else {
        s.sequence = 0
    }
    
    s.lastTs = ts
    return ((ts << timestampLeftShift) |
        (s.datacenterId << datacenterIdShift) |
        (s.workerId << workerIdShift) |
        s.sequence)
}
```

## 二、 UUID v7

```
UUID v7 时间戳顺序:
┌─────────────────────────────────────────────────────────────┐
│  Timestamp (48 bits) | CRC (4 bits) | Version (4 bits)      │
│                       │ Counter (12 bits)                   │
└─────────────────────────────────────────────────────────────┘

格式: XXXXXXXX-XXXX-7XXX-[89ab]XXX-XXXXXXXXXXXX
```

## 三、数据库方案

```sql
-- 自增ID
CREATE TABLE orders (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id BIGINT NOT NULL,
    amount DECIMAL(10,2)
);

-- 分库分表ID生成
CREATE TABLE sequence (
    name VARCHAR(32) NOT NULL,
    current_value BIGINT NOT NULL,
    increment INT NOT NULL DEFAULT 1,
    PRIMARY KEY (name)
);

-- 获取ID
SELECT GET_SEQ_ID('order_id') as id;
```

## 四、面试高频题

### Q1: Snowflake有什么缺点？

```
A:
1. 依赖时钟，时钟回拨会失败
2. 单机生成，有上限
3. 需要分配worker_id
```

### Q2: 如何保证唯一性？

```
A:
1. 时间戳 + 机器ID + 序列号
2. 本地缓存预分配
3. 数据库号段模式
```

## 五、自测题

1. 解释Snowflake算法
2. 如何实现时钟回拨处理？
3. 分布式ID方案有哪些？

---

## 参考文档

- [Snowflake源码](https://github.com/bwmarrin/snowflake)
- [UUID v7 RFC](https://datatracker.ietf.org/doc/html/draft-ietf-uuidrev-rfc4122-bis)
