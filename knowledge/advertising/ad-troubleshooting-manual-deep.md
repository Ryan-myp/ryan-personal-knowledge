# 广告系统排查手册：常见问题快速定位与解决

> 生产环境常见问题 + 排查步骤 + 解决方案 + 预防建议

---

## 第一部分：排查方法论

### 1.1 排查思路

```
问题 → 收集信息 → 假设 → 验证 → 定位 → 解决 → 复盘

1. 收集信息：
   → 问题发生的时间
   → 影响的范围（单个广告/所有广告/单个用户/所有用户）
   → 最近的变更（代码/配置/数据）

2. 假设：
   → 根据经验列出可能的原因
   → 按可能性排序

3. 验证：
   → 逐一验证假设
   → 用日志/监控/诊断工具确认

4. 解决：
   → 临时解决：快速恢复业务
   → 根本解决：修复根因

5. 复盘：
   → 为什么会发生？
   → 如何预防再次发生？
   → 更新排查手册
```

### 1.2 排查工具箱

```
1. 诊断引擎：一键诊断（ad-diagnosis-engine-deep.md）
2. 日志查询：ELK 搜索（ad-observability-deep.md）
3. 监控面板：Grafana 实时查看
4. 数据库：直接查询 MySQL/ClickHouse
5. 缓存：Redis CLI 查看
6. 链路追踪：Jaeger 查看 Trace
```

---

## 第二部分：常见问题排查

### 2.1 问题：广告 0 展示

```
症状：
→ 广告组状态：运行中
→ 预算充足
→ 审核通过
→ 但 0 展示

排查步骤：
1. 查竞价日志：
   SELECT * FROM bid_logs 
   WHERE ad_id = 'xxx' AND date = '2024-01-01'
   ORDER BY timestamp DESC LIMIT 100;
   
   → 如果有请求但没有 win：说明竞价失败
   → 如果没有请求：说明没有流量

2. 查出价竞争力：
   SELECT AVG(bid_price) FROM bid_logs 
   WHERE slot_id = 'xxx' AND date = '2024-01-01';
   
   → 如果我们的出价 < 行业均价：提高出价

3. 查 CTR 预测：
   SELECT predicted_ctr FROM ad_predictions 
   WHERE ad_id = 'xxx';
   
   → 如果 CTR < 0.001：优化创意

4. 查定向条件：
   SELECT targeting FROM campaigns WHERE id = 'xxx';
   
   → 如果地域/年龄/兴趣限制太窄：放宽定向

5. 查广告位流量：
   SELECT request_count FROM slot_metrics 
   WHERE slot_id = 'xxx' AND date = '2024-01-01';
   
   → 如果 request_count = 0：广告位无流量
```

### 2.2 问题：eCPM 突然下降

```
症状：
→ 昨天 eCPM ¥50，今天 ¥30

排查步骤：
1. 拆分解 eCPM：
   eCPM = CTR × CVR × targetCPA × 1000
   
   → CTR 下降？→ 创意疲劳
   → CVR 下降？→ 落地页问题
   → targetCPA 下降？→ 出价策略变更

2. 查 CTR 趋势：
   SELECT DATE(timestamp), AVG(ctr) 
   FROM ad_metrics 
   WHERE ad_id = 'xxx' 
   GROUP BY DATE(timestamp) 
   ORDER BY DATE(timestamp) DESC 
   LIMIT 7;
   
   → 如果 CTR 持续下降：创意疲劳，需要新素材

3. 查流量质量：
   SELECT DATE(timestamp), AVG(user_quality_score) 
   FROM user_metrics 
   WHERE slot_id = 'xxx' 
   GROUP BY DATE(timestamp);
   
   → 如果新用户占比上升：流量质量下降

4. 查竞争环境：
   SELECT DATE(timestamp), AVG(industry_ecpm) 
   FROM market_metrics 
   GROUP BY DATE(timestamp);
   
   → 如果行业 eCPM 下降：竞争加剧

5. 查近期变更：
   → 最近是否调整了出价策略？
   → 最近是否更换了创意？
   → 最近是否扩大了定向范围？
```

### 2.3 问题：用户投诉看不到广告

```
症状：
→ 用户反馈 App 里没有广告

排查步骤：
1. 查用户画像：
   SELECT age, gender, interests FROM user_profiles 
   WHERE user_id = 'xxx';
   
   → 如果用户画像不完整：补充画像

2. 查频次限制：
   SELECT freq_count FROM user_frequency 
   WHERE user_id = 'xxx' AND date = CURDATE();
   
   → 如果 freq_count >= max_freq：用户被频次限制

3. 查反作弊：
   SELECT fraud_score FROM user_fraud 
   WHERE user_id = 'xxx';
   
   → 如果 fraud_score > 0.8：用户被标记为可疑

4. 查广告位填充率：
   SELECT fill_rate FROM slot_metrics 
   WHERE slot_id = 'xxx' AND date = CURDATE();
   
   → 如果 fill_rate < 50%：填充率低

5. 查地域限制：
   → 用户所在城市是否在投放地域内？
```

### 2.4 问题：预算扣减异常

```
症状：
→ 广告主说预算被超额扣减

排查步骤：
1. 查扣费日志：
   SELECT * FROM billing_logs 
   WHERE account_id = 'xxx' AND date = '2024-01-01'
   ORDER BY timestamp;
   
   → 检查是否有重复扣费

2. 查预算状态：
   SELECT budget, spent, remaining FROM campaigns 
   WHERE id = 'xxx';
   
   → 检查 spent 是否 > budget

3. 查并发扣费：
   → 同一广告同时有多个请求时，是否并发扣费？
   → 检查 Redis 的 DECR 操作是否有竞态条件

4. 查对账差异：
   → MySQL 预算记录 vs Redis 预算记录是否一致？
   → 如果不一致，以哪个为准？
```

---

## 第三部分：预防建议

### 3.1 预防措施

```
1. 监控告警：
   → eCPM 下降 > 20%：告警
   → 填充率 < 90%：告警
   → 错误率 > 5%：告警

2. 定期巡检：
   → 每周检查广告主账户状态
   → 每月检查预算扣费准确性
   → 每季度检查创意质量

3. 容量规划：
   → 提前扩容（QPS 增长 50% 时）
   → 提前储备（大促前）

4. 灰度发布：
   → 新出价策略先灰度 1%
   → 新创意模板先灰度 5%
```

### 3.2 应急方案

```
1. 广告投不出去：
   → 临时：降低底价，放宽定向
   → 根本：优化竞价策略

2. eCPM 下降：
   → 临时：提高出价
   → 根本：优化创意

3. 预算扣费异常：
   → 临时：暂停广告组
   → 根本：修复扣费逻辑

4. 系统宕机：
   → 临时：降级到缓存
   → 根本：修复系统
```

---

## 第四部分：自测题

### 问题 1
广告 0 展示的排查步骤？

<details>
<summary>查看答案</summary>

1. 查竞价日志：是否有 win
2. 查出价竞争力：是否 < 行业均价
3. 查 CTR 预测：是否过低
4. 查定向条件：是否太窄
5. 查广告位流量：是否有请求
</details>

### 问题 2
eCPM 下降如何排查？

<details>
<summary>查看答案</summary>

1. 拆解 eCPM = CTR × CVR × targetCPA
2. 查 CTR 趋势：创意疲劳？
3. 查流量质量：新用户占比？
4. 查竞争环境：行业 eCPM？
5. 查近期变更：出价/创意/定向？
</details>

---

*本文档基于广告系统排查生产实战整理。*