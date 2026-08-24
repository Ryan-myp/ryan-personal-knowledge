# Meta 广告类型专家知识

## 1. 销售转化广告 (Sales/Conversions)

### 适用场景
- 电商网站转化
- App 安装和激活
- 线索收集表单

### 核心配置
```yaml
objective: OUTCOME_SALES
optimization_goal: CONVERSIONS
bidding_strategy: TARGET_COST
target_cost: 50  # 目标 CPA
```

### 专家提示
- 新 Campaign 建议先用 LOWEST_COST 积累 50+ 转化
- 数据充足后切换到 TARGET_COST 控制成本
- 转化事件优先选择高质量转化（Purchase > AddToCart）

---

## 2. 流量广告 (Traffic)

### 适用场景
- 网站访问量提升
- Landing Page 转化
- 内容传播

### 核心配置
```yaml
objective: OUTCOME_TRAFFIC
optimization_goal: LINK_CLICKS
bidding_strategy: LOWEST_COST
```

### 专家提示
- 流量广告成本最低，但质量参差不齐
- 建议配合 Pixel 追踪筛选高质量用户
- 适合品牌曝光+引流组合投放

---

## 3. 互动广告 (Engagement)

### 适用场景
- 帖子互动提升
- 视频观看
- Messenger 消息
- 活动参与

### 核心配置
```yaml
objective: OUTCOME_ENGAGEMENT
optimization_goal: POST_ENGAGEMENT
```

### 专家提示
- 适合品牌建设和社区运营
- 视频观看率是核心指标
- 可搭配 Lookalike 受众扩量

---

## 4. 品牌认知广告 (Brand Awareness)

### 适用场景
- 新品发布
- 品牌曝光
- 市场教育

### 核心配置
```yaml
objective: OUTCOME_BRAND_AWARENESS
optimization_goal: REACH
```

### 专家提示
- 优先使用 Video Reach 广告
- 控制频次（Frequency Capping）避免疲劳
- 配合 Brand Lift 研究评估效果

---

## 5. 应用安装广告 (App Installs)

### 适用场景
- App 下载量提升
- 应用激活
- 应用内行为优化

### 核心配置
```yaml
objective: OUTCOME_APP_INSTALLS
optimization_goal: INSTANTS
```

### 专家提示
- 使用 Install & Activate 优化目标
- 结合 Value Optimization 优化高价值用户
- A/B 测试不同创意素材效果

---

## 6. 本地广告 (Local Awareness)

### 适用场景
- 线下门店引流
- 本地服务推广
- 商圈覆盖

### 核心配置
```yaml
objective: OUTCOME_STORE_TRAFFIC
targeting:
  location_type: DROPSHIP
  radius: 10km
```

### 专家提示
- 设置合适的门店覆盖半径（1-10km）
- 结合 Store Visits 转化事件
- 移动端定向效果更佳
