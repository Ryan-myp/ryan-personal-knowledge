# 系统设计面试题库深度实现

> **版本**: v1.0  
> **日期**: 2026-08-13  
> **作者**: Ryan  
> **分类**: 面试/系统设计  
> **题目数**: 15 道高频题

---

## 一、核心系统设计题

### Q1: 设计一个短链接服务

```go
// 核心数据结构
type ShortLink struct {
    ID        uint64    `json:"id"`
    Original  string    `json:"original"`
    ShortCode string    `json:"short_code"`
    CreatedAt time.Time `json:"created_at"`
    ExpiresAt time.Time `json:"expires_at"`
}

// 编码方案: Base62
func encodeID(id uint64) string {
    const chars = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
    var result strings.Builder
    for id > 0 {
        result.WriteByte(chars[id%62])
        id /= 62
    }
    // 反转
    s := result.String()
    runes := []rune(s)
    for i, j := 0, len(runes)-1; i < j; i, j = i+1, j-1 {
        runes[i], runes[j] = runes[j], runes[i]
    }
    return string(runes)
}

// 数据库设计
CREATE TABLE short_links (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    short_code VARCHAR(10) UNIQUE NOT NULL,
    original_url TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    expires_at TIMESTAMP,
    click_count INT DEFAULT 0
);

CREATE INDEX idx_short_code ON short_links(short_code);
```

---

### Q2: 设计分布式 ID 生成器

```go
// Snowflake 算法
type Snowflake struct {
    mu         sync.Mutex
    lastTime   int64
    workerID   int64
    sequence   int64
}

const (
    workerBits  = 5
    sequenceBits = 12
    workerMax    = -1 ^ (-1 << workerBits)
    sequenceMask = -1 ^ (-1 << sequenceBits)
)

func (s *Snowflake) NextID() int64 {
    s.mu.Lock()
    defer s.mu.Unlock()
    
    now := time.Now().UnixMilli()
    if now < s.lastTime {
        return s.NextID() // 时钟回拨
    }
    
    if now == s.lastTime {
        s.sequence = (s.sequence + 1) & sequenceMask
        if s.sequence == 0 {
            now = s.waitNextMillis(now)
        }
    } else {
        s.sequence = 0
    }
    
    s.lastTime = now
    return ((now - epoch) << 22) | (s.workerID << 12) | s.sequence
}
```

---

## 二、架构设计题

### Q3: 设计一个高并发秒杀系统

```
秒杀流程:
用户请求 → API 网关 → 限流 → 库存预扣 → 排队 → 异步下单 → 结果返回

核心组件:
├── 限流: Token Bucket / Leaky Bucket
├── 库存: Redis 预扣 + MySQL 异步落库
├── 排队: Redis List / Kafka
└── 异步: Worker Pool 处理订单
```

```go
// 库存预扣
func (s *SeckillService) PreDeductStock(itemID, userID string) error {
    key := fmt.Sprintf("stock:%s", itemID)
    
    // Redis 原子扣减
    remaining, err := s.rdb.Decr(context.Background(), key).Result()
    if err != nil {
        return err
    }
    
    if remaining < 0 {
        // 库存不足，回滚
        s.rdb.Incr(context.Background(), key)
        return ErrOutOfStock
    }
    
    // 加入排队
    s.rdb.LPush(context.Background(), "queue:"+itemID, userID)
    return nil
}
```

---

### Q4: 设计实时推荐系统

```
实时推荐架构:
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   用户行为   │───▶│  实时特征    │───▶│  模型推理    │
│   采集       │    │  引擎        │    │  (TensorRT) │
└─────────────┘    └─────────────┘    └──────┬──────┘
                                             │
                              ┌──────────────┼──────────────┐
                              ▼              ▼              ▼
                        ┌─────────┐   ┌─────────┐   ┌─────────┐
                        │ 冷启动   │   │ 协同过滤 │   │ 深度学习 │
                        │ 策略     │   │ (Redis)  │   │ (GPU)   │
                        └─────────┘   └─────────┘   └─────────┘
```

---

## 三、15道高频题汇总

| # | 题目 | 难度 | 核心考点 |
|---|------|------|---------|
| 1 | 短链接服务 | ⭐⭐⭐ | 编码设计 |
| 2 | 分布式 ID | ⭐⭐⭐ | Snowflake |
| 3 | 秒杀系统 | ⭐⭐⭐⭐ | 高并发 |
| 4 | 实时推荐 | ⭐⭐⭐⭐ | 流处理 |
| 5 | 消息队列 | ⭐⭐⭐⭐ | Kafka |
| 6 | 缓存架构 | ⭐⭐⭐ | Redis |
| 7 | 搜索引擎 | ⭐⭐⭐⭐ | ES |
| 8 | 分布式事务 | ⭐⭐⭐⭐ | TCC/Saga |
| 9 | API 网关 | ⭐⭐⭐ | 路由/限流 |
| 10 | 日志系统 | ⭐⭐⭐ | ELK |
| 11 | 配置中心 | ⭐⭐ | 一致性 |
| 12 | 服务发现 | ⭐⭐⭐ | Consul |
| 13 | 链路追踪 | ⭐⭐⭐ | Jaeger |
| 14 | 数据库分片 | ⭐⭐⭐⭐ | Sharding |
| 15 | CDN 架构 | ⭐⭐⭐ | 边缘计算 |

---

## 四、自测题

1. **Snowflake 如何解决时钟回拨问题？**
   - 等待时钟追上或分配新 workerID

2. **秒杀系统如何防止超卖？**
   - Redis 原子扣减 + MySQL 最终一致

3. **分布式事务的 CAP 权衡？**
   - 强一致 (CP) vs 高可用 (AP)

