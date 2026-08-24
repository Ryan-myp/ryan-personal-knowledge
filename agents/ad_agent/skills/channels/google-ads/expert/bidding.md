# Google Ads 出价策略专家知识

## 1. 手动出价 (Manual CPC)

### 适用场景
- 新 Campaign 冷启动
- 需要精细控制的预算

### 专家提示
- 设置合理的 Max CPC 上限
- 根据关键词表现调整出价
- 配合位置调整优化排名

---

## 2. Target CPA

```yaml
bidding_strategy: TARGET_CPA
target_cpa: 50
```

**适用场景：**
- 已有 50+ 转化数据的 Campaign
- 追求稳定转化成本

---

## 3. Target ROAS

```yaml
bidding_strategy: TARGET_ROAS
target_roas: 300
```

**适用场景：**
- 高客单价产品
- 有清晰的收入数据

---

## 4. Maximize Conversions

```yaml
bidding_strategy: MAXIMIZE_CONVERSIONS
```

**适用场景：**
- 追求转化量最大化
- 新 Campaign 冷启动

---

## 5. 出价策略决策树

```
开始
  │
  ├─ 转化数据 < 50/周？→ Manual CPC
  │
  ├─ 追求稳定 CPA？→ Target CPA
  │
  ├─ 高客单价？→ Target ROAS
  │
  └─ 否则 → Maximize Conversions
```
