# DV360 广告类型专家知识

## 1. 程序化保证 (Programmatic Guaranteed - PG)

### 适用场景
- 品牌保量采购
- 优质媒体资源锁定
- 高价展示位购买

### 核心配置
```yaml
line_item_type: GUARANTEED
flight_type: FIXED_PRICE
impressions_guaranteed: 1000000
```

### 专家提示
- 适合知名品牌的大规模投放
- 可与 Direct Buys 结合
- 确保媒体质量和流量来源

---

## 2. 程序化私有市场 (PMP - Private Marketplace)

### 适用场景
- 精选媒体采购
- 品牌安全要求高
- 溢价媒体获取

### 核心配置
```yaml
line_item_type: REMARKETING
marketplace_id: "pmp_id"
bid_shading: true
```

### PMP 等级
| 等级 | 说明 | 价格 |
|------|------|------|
| Invited | 邀请制 | 市场价 |
| Preferred | 优先权 | 市场价 |
| Private Auction | 私有竞价 | 高于 Open |

---

## 3. Open Auction（公开竞价）

### 适用场景
- 大规模流量获取
- 性价比优先
- 动态扩量

### 核心配置
```yaml
line_item_type: NON_GUARANTEED
bidding_strategy: COMPETITIVE
bid_cap: 5.0  # CPM 上限
```

### 专家提示
- 设置合理的 Bid Cap 控制成本
- 配合 Frequency Capping 避免疲劳
- 实时监控 ROI 调整出价

---

## 4. Standard Flight（标准航班）

### 适用场景
- 常规品牌广告投放
- 固定时段投放
- 稳定预算分配

### 专家提示
- 适合长期品牌建设
- 可与 Video 广告组合
- 考虑时段优化
