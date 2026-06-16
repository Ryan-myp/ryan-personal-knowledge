# 广告位管理深度：SSP 侧实现/填充率/底价策略

> 广告位管理 + 填充率优化 + 底价策略 + 程序化直采

---

## 第一部分：广告位管理的核心挑战

### SSP 侧 vs DSP 侧

```
DSP（需求方）：
→ 我要买广告位
→ 出价策略
→ 人群定向

SSP（供给方）：
→ 我有广告位
→ 要卖个好价钱
→ 填充率要尽量高

广告位管理 = SSP 侧的核心功能
```

### 核心指标

```
1. 填充率（Fill Rate）：
   → 有广告展示的请求 / 总请求
   → 目标：> 95%

2. eCPM：
   → 每千次展示收入
   → 目标：最大化

3. 底价（Floor Price）：
   → 最低 Acceptable eCPM
   → 太高：填充率低
   → 太低：收入低
```

### 数据量

```
1000 万 DAU × 每个用户每天 10 次请求
= 1 亿次广告请求/天
= 每秒 1157 次请求

每个广告位：
→ Banner：300×250, 728×90
→ 信息流：原生样式
→ 开屏：全屏
→ 插屏：全屏/半屏
```

---

## 第二部分：广告位管理系统

### 2.1 核心表结构

```sql
-- 广告位表
CREATE TABLE inventory_slot (
    id              BIGINT PRIMARY KEY AUTO_INCREMENT,
    app_id          BIGINT NOT NULL,           -- 应用 ID
    slot_type       TINYINT NOT NULL,          -- 类型（1=Banner, 2=信息流, 3=开屏, 4=插屏）
    slot_code       VARCHAR(128) NOT NULL,     -- 广告位 code
    width           INT,                       -- 宽度
    height          INT,                       -- 高度
    format          VARCHAR(32),               -- 格式
    status          TINYINT DEFAULT 1,         -- 状态（1=启用, 0=禁用）
    floor_price     DECIMAL(10,4),            -- 底价（eCPM）
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_app_slot (app_id, slot_code),
    INDEX idx_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 广告位配置表
CREATE TABLE inventory_slot_config (
    id              BIGINT PRIMARY KEY AUTO_INCREMENT,
    slot_id         BIGINT NOT NULL,
    max_ads         INT DEFAULT 1,             -- 最大广告数
    ad_rotation     TINYINT DEFAULT 0,         -- 广告轮换（0=不轮换, 1=轮换）
    priority        INT DEFAULT 0,             -- 优先级
    custom_params   JSON,                      -- 自定义参数
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_slot_id (slot_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

### 2.2 广告位管理

```go
package inventory

import (
    "context"
    "fmt"
)

// SlotManager 广告位管理器
type SlotManager struct {
    db     *Database
    cache  *RedisClient
}

// Slot 广告位
type Slot struct {
    ID        int64
    AppID     int64
    SlotType  int    // 1=Banner, 2=信息流, 3=开屏, 4=插屏
    SlotCode  string
    Width     int
    Height    int
    Format    string
    Status    int    // 1=启用, 0=禁用
    FloorPrice float64 // 底价
}

// GetSlot 获取广告位
func (sm *SlotManager) GetSlot(ctx context.Context, appID int64, slotCode string) (*Slot, error) {
    // 1. 查缓存
    key := fmt.Sprintf("slot:%d:%s", appID, slotCode)
    cached, err := sm.cache.Get(ctx, key)
    if err == nil && cached != "" {
        return parseSlot(cached), nil
    }
    
    // 2. 查数据库
    slot, err := sm.db.GetSlot(appID, slotCode)
    if err != nil {
        return nil, err
    }
    
    // 3. 写缓存
    sm.cache.Set(ctx, key, marshalSlot(slot), 3600)
    
    return slot, nil
}

// UpdateFloorPrice 更新底价
func (sm *SlotManager) UpdateFloorPrice(ctx context.Context, slotID int64, floorPrice float64) error {
    return sm.db.UpdateFloorPrice(slotID, floorPrice)
}
```

---

## 第三部分：填充率优化

### 3.1 填充率低的原因

```
1. 没有匹配的 advertiser：
   → 定向太严格
   → 预算不足

2. 出价太低：
   → 底价太高
   → 竞价失败

3. 创意不足：
   → 广告主创意审核不通过
   → 创意过期
```

### 3.2 填充率优化策略

```
策略 1：动态底价
→ 填充率低时降低底价
→ 填充率高时提高底价
→ 自动调节

策略 2： waterfall（瀑布流）
→ 先请求高价网络
→ 填充率低时请求低价网络
→ 逐步降低

策略 3：合并请求
→ 多个广告位合并请求
→ 提高填充率
```

### 3.3 代码实现

```go
// FillRateOptimizer 填充率优化器
type FillRateOptimizer struct {
    slotManager *SlotManager
    minFillRate float64 // 最低填充率阈值
    maxFillRate float64 // 最高填充率阈值
}

// OptimizeFloorPrice 优化底价
func (fro *FillRateOptimizer) OptimizeFloorPrice(slotID int64, currentFillRate float64, currentFloorPrice float64) (float64, error) {
    if currentFillRate < fro.minFillRate {
        // 填充率低，降低底价
        newFloorPrice := currentFloorPrice * 0.9
        fro.slotManager.UpdateFloorPrice(slotID, newFloorPrice)
        return newFloorPrice, nil
    } else if currentFillRate > fro.maxFillRate {
        // 填充率高，提高底价
        newFloorPrice := currentFloorPrice * 1.1
        fro.slotManager.UpdateFloorPrice(slotID, newFloorPrice)
        return newFloorPrice, nil
    }
    
    return currentFloorPrice, nil
}
```

---

## 第四部分：底价策略

### 4.1 底价类型

```
1. 固定底价：
   → 所有广告都一样
   → 简单，但不灵活

2. 动态底价：
   → 根据历史 eCPM 调整
   → 更合理

3. 个性化底价：
   → 根据广告主出价能力调整
   → 最灵活
```

### 4.2 代码实现

```go
// FloorPriceStrategy 底价策略
type FloorPriceStrategy struct {
    staticPrice float64     // 固定底价
    dynamicPrice float64    // 动态底价
    personalizedPrice float64 // 个性化底价
}

// Calculate 计算底价
func (fps *FloorPriceStrategy) Calculate(slotID, advertiserID int64) float64 {
    // 获取广告位基础底价
    baseFloor, _ := fps.slotManager.GetFloorPrice(slotID)
    
    // 根据广告主调整
    if advertiserID > 0 {
        advertiserFloor := fps.getAdvertiserFloor(advertiserID)
        if advertiserFloor > baseFloor {
            return advertiserFloor
        }
    }
    
    return baseFloor
}
```

---

## 第五部分：自测题

### 问题 1
填充率优化的策略有哪些？

<details>
<summary>查看答案</summary>

1. **动态底价**：填充率低时降低，高时提高
2. **Waterfall**：先高价后低价
3. **合并请求**：多个广告位合并
4. **自动调节**：根据填充率自动调整
5. **目标**：填充率 > 95%
</details>

### 问题 2
底价策略有哪些类型？

<details>
<summary>查看答案</summary>

1. **固定底价**：所有广告一样
2. **动态底价**：根据历史 eCPM 调整
3. **个性化底价**：根据广告主出价能力调整
4. **目标**：平衡填充率和收入
5. **实现**：根据广告位 + 广告主动态计算
</details>

---

*本文档基于广告位管理生产实战整理。*