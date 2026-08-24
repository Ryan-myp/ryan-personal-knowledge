# Meta 出价策略详解

## 1. 自动竞价 (Automatic Bidding)

### LOWEST_COST
- 系统自动优化，追求最大转化量
- 适合：新 Campaign、预算充足、追求量级

```yaml
bidding_strategy: LOWEST_COST
```

### COST_CAP
- 设置成本上限，不超出指定金额
- 适合：有明确 CPA 目标

```yaml
bidding_strategy: COST_CAP
cost_cap: 50  # 目标 CPA
```

---

## 2. 手动竞价 (Manual Bidding)

### ENHANCED_CPC
- 在手动 CPC 基础上智能调整
- 适合：需要控制单次点击成本

```yaml
bidding_strategy: ENHANCED_CPC
bid_limit: 5.0  # 最高 CPC
```

### MANUAL_CPC
- 完全手动控制出价
- 适合：精细化运营、测试阶段

```yaml
bidding_strategy: MANUAL_CPC
bid_amount: 3.0
```

---

## 3. 目标出价 (Target Bidding)

### TARGET_COST
- 控制平均转化成本
- 适合：稳定投放期

```yaml
bidding_strategy: TARGET_COST
target_cost: 50  # 目标 CPA
```

### START_BID
- 设置初始出价，系统逐步优化
- 适合：冷启动阶段

```yaml
bidding_strategy: START_BID
start_bid: 2.0
```

---

## 4. 出价策略决策树

```
开始
  │
  ├─ Campaign 冷启动？→ LOWEST_COST
  │
  ├─ 有明确 CPA 目标？
  │     ├─ 是 → TARGET_COST
  │     └─ 否 → 下一步
  │
  ├─ 需要控制点击成本？→ ENHANCED_CPC
  │
  └─ 否则 → LOWEST_COST
```

---

## 5. 专家提示

| 阶段 | 推荐策略 | 预算建议 |
|------|----------|----------|
| 冷启动 (0-50 转化) | LOWEST_COST | 10x 目标 CPA |
| 成长期 (50-200 转化) | TARGET_COST | 逐步优化 |
| 成熟期 (200+ 转化) | TARGET_COST | 稳定投放 |

### 注意事项
- 预算至少应为目标 CPA 的 10 倍
- 新 Campaign 前 3 天不要调整出价
- 每次调整幅度不超过 20%
