# Google Ads 广告类型专家知识

## 1. 搜索广告 (Search Ads)

### 适用场景
- 高意向关键词捕获
- 品牌词保护
- 竞品词投放

### 核心配置
```yaml
advertising_channel_type: SEARCH
bidding_strategy: TARGET_CPA
campaign_type: MANUAL_CPC
```

### 专家提示
- 广泛匹配 + 智能出价 = 最佳组合
- 短语匹配适合平衡流量和质量
- 精确匹配适合品牌词和竞品词

---

## 2. 购物广告 (Shopping Ads)

### 适用场景
- 电商商品推广
- 价格比较展示
- 商品发现

### 核心配置
```yaml
advertising_channel_type: SHOPPING
campaign_type: SHOPPING
product_feed: product_feed_id
```

### 专家提示
- Product Feed 质量决定投放效果
- 优先优化标题和品类属性
- 分产品组设置不同出价

---

## 3. 视频广告 (Video Ads)

### 广告格式
| 格式 | 说明 | 适用场景 |
|------|------|----------|
| In-Stream | 视频前/中/后插播 | 品牌曝光 |
| Out-Stream | 信息流展示 | 移动端覆盖 |
| Discovery | 搜索发现 | 主动兴趣用户 |
| Bumper | 6 秒不可跳过 | 高频曝光 |

### 专家提示
- In-Stream 适合 15-30 秒故事
- Bumper 适合品牌口号记忆
- 前置 5 秒抓住注意力

---

## 4. Performance Max (PMax)

### 适用场景
- 全渠道智能投放
- 自动化优化
- 跨渠道转化

### 核心配置
```yaml
advertising_channel_type: MAX
asset_group:
  - name: 夏季促销
    headlines: ["夏季新品", "限时优惠"]
audience_signals:
  - type: CUSTOM_SEGMENT
    name: 高价值用户
```

### 专家提示
- Asset Group 至少准备 5 个创意组合
- Audience Signals 提供初始学习信号
- 配合 Customer Match 数据训练模型

---

## 5. 展示广告 (Display Ads)

### 适用场景
- 品牌再营销
- 受众拓展
- 视觉冲击

### 专家提示
- 响应式展示广告优先使用
- 准备多种尺寸素材
- 再营销列表至少 1000 用户

---

## 6. 应用广告 (App Ads)

### 适用场景
- App 安装
- App 激活
- App 内行为

### 专家提示
- 使用 Install & Activate 优化
- 准备多种 App 截图和演示视频
- 配合 Value Optimization 优化高价值用户
