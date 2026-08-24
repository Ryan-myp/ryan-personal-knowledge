# Meta 定向策略详解

## 1. 基础定向 (Core Targeting)

### 人口统计
| 维度 | 可选值 | 建议 |
|------|--------|------|
| 年龄 | 13-65+ | 根据产品定位选择 |
| 性别 | 所有/女性/男性 | 男性产品测试男性受众 |
| 语言 | 多语言支持 | 按地区语言定向 |
| 教育 | 高等教育/职业培训 | 教育类产品定向 |
| 就业 | 职位/行业 | B2B 产品定向 |
| 关系状态 | 单身/恋爱/已婚 | 婚恋产品定向 |

### 地理位置
```yaml
locations:
  - type: PLACES
    places:
      - name: "北京"
        placement: CITY
        distance: 50km
  - type: DROPSHIP
    places:
      - name: "上海市静安区"
        radius: 5km
```

---

## 2. 自定义受众 (Custom Audiences)

### 来源类型
| 类型 | 说明 | 推荐指数 |
|------|------|----------|
| 网站流量 | Pixel 追踪用户 | ⭐⭐⭐⭐⭐ |
| App 活动 | App Events 用户 | ⭐⭐⭐⭐⭐ |
| 客户列表 | 手机号/邮箱上传 | ⭐⭐⭐⭐ |
| 页面互动 | Instagram/Facebook 互动 | ⭐⭐⭐ |
| 视频观看 | 视频播放时长 | ⭐⭐⭐ |

### 专家提示
- 网站访客 30 天数据量最大，转化效果稳定
- 高价值用户（Purchase 90 天）用于 Lookalike 种子
- 视频观看 25%+ 用户用于再营销

---

## 3. 相似受众 (Lookalike Audiences)

### 创建方法
```yaml
lookalike:
  source: custom_audience_id  # 种子受众 ID
  percentage: 1  # 1% = 最相似，10% = 覆盖最广
  location: "CN"  # 国家代码
```

### 专家建议
| 种子质量 | 相似比例 | 适用场景 |
|----------|----------|----------|
| 高价值用户 | 1-2% | 转化目标，追求质量 |
| 中等价值 | 3-5% | 平衡量级和质量 |
| 广泛种子 | 5-10% | 品牌曝光，追求量级 |

---

## 4. 兴趣定向 (Interest Targeting)

### 热门兴趣分类
```yaml
interests:
  # 电商相关
  - E-commerce
  - Online shopping
  - Amazon
  - Taobao
  
  # 生活方式
  - Fashion
  - Luxury goods
  - Beauty products
  
  # 技术相关
  - Technology
  - Mobile apps
  - Gaming
```

### 专家提示
- 兴趣定向配合行为定向效果更好
- 避免兴趣重叠度过高（系统自动去重）
- 定期清理无效兴趣，保持受众新鲜度

---

## 5. 排除定向 (Exclusions)

### 常用排除策略
```yaml
exclusions:
  - type: CUSTOM_AUDIENCE
    source: purchasers_30d  # 排除 30 天内购买用户
  - type: ENGAGEMENT
    source: instagram_90d   # 排除 90 天 Instagram 互动用户
```

### 专家建议
- 已转化用户一定要排除，避免浪费预算
- 高频互动用户可降低出价权重
- 负面反馈用户加入黑名单

---

## 6. 频次控制 (Frequency Capping)

### 配置示例
```yaml
frequency_cap:
  time_window: 7  # 7 天内
  max_impressions: 3  # 最多展示 3 次
```

### 专家建议
- 品牌广告：7 天 3-5 次
- 效果广告：7 天 1-2 次
- 避免频次过高导致用户疲劳
