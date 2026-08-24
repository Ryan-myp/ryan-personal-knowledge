# DV360 定向专家知识

## 1. 受众定向

### 第一方数据
```yaml
audience_targeting:
  - source: CRM_DATABASE
    match_rate: 70%
  - source: WEBSITE_VISITORS
    duration: 30d
```

### 第二方数据
```yaml
audience_targeting:
  - source: PUBLISHER_DATA
    publisher: "example.com"
```

### 第三方数据
```yaml
audience_targeting:
  - source: THIRD_PARTY
    provider: "Eyeota"
    segments: ["Luxury Shoppers"]
```

---

## 2. 上下文定向

### 关键词定向
```yaml
contextual_targeting:
  keywords:
    - "luxury travel"
    - "premium hotels"
  negative_keywords:
    - "cheap"
    - "budget"
```

### 内容分类
```yaml
content_categories:
  - "Automotive"
  - "Luxury Goods"
  - "Finance"
```

---

## 3. 位置定向

### 地理位置
```yaml
location_targeting:
  - type: GEO
    locations:
      - name: "New York"
        radius: 50mi
  - type: PLACE
    places:
      - name: "Manhattan"
```

### 位置细分
```yaml
location_segments:
  - high_income_neighborhoods
  - urban_core
  - suburban_affluent
```
