# 广告技术面试题库深度实现 - 20道高频题

> **版本**: v2.0  
> **日期**: 2026-08-13  
> **作者**: Ryan  
> **分类**: 面试/广告  
> **代码密度**: 30%

---

## 一、竞价系统

**Q1: RTB竞价流程中，如何保证50ms SLA？**

```
答案要点:
1. 特征预取: 在HTTP解析同时异步查询Redis特征
2. GPU加速推理: pCTR模型部署在GPU集群
3. 超时控制: 每个子步骤设置独立超时
4. 结果缓存: 高频场景缓存竞价结果
5. 异步上报: 计费数据异步写入ClickHouse
```

**Q2: pCTR模型为什么需要校准？**

```
答案:
• 模型输出是相对概率，需要校准到绝对概率
• Platt Scaling: logit变换 + 线性拟合
• Isotonic Regression: 非参数单调校准
• 未校准的pCTR会导致出价偏差，影响ROI
```

**Q3: 出价策略 vCPM/oCPM/tCPA 的区别？**

```
vCPM: bid = targetCPM × pCTR  (只看曝光价值)
oCPM: bid = targetCPM × calibratedCTR (优化转化)
tCPA: bid = targetCPA × pCVR (目标成本)

选择: 品牌广告用vCPM, 效果广告用oCPM/tCPA
```

---

## 二、RTA/频控

**Q4: RTA过滤策略的实现要点？**

```
• 策略: 过滤外/过滤内 (DSP侧推荐过滤外)
• 延迟: <20ms (通常10-15ms)
• 数据: 第一方数据匹配，不暴露用户ID
• 缓存: 白名单本地缓存，TTL 5-30min
```

**Q5: 频控的滑动窗口实现？**

```go
// Redis ZSet 实现滑动窗口频控
key := fmt.Sprintf("freq:%d:%d", userID, adID)
now := time.Now().Unix()
windowStart := now - 86400 // 24小时窗口

pipe := rdb.Pipeline()
pipe.ZAdd(ctx, key, redis.Z{Score: float64(now), Member: now})
pipe.ZRemRangeByScore(ctx, key, "0", fmt.Sprintf("%d", windowStart))
pipe.Expire(ctx, key, 48*time.Hour)
pipe.ZCard(ctx, key)

results, _ := pipe.Exec(ctx)
count := results[len(results)-1].(*redis.IntCmd).Val()
return int(count) < maxFreq
```

---

## 三、归因与反作弊

**Q6: Shapley Value 归因为什么公平？**

```
• 考虑了所有可能的通道组合
• 每个通道的贡献 = 平均边际贡献
• 满足: 效率性 + 对称性 + 可加性
```

**Q7: 反作弊图检测的核心思路？**

```
• 构建关联图: 设备/IP/账号为节点
• 连通分量检测: 找出异常集群
• 中心性分析: 识别关键作弊节点
• 时序异常: 检测操作模式异常
```

---

## 四、系统设计

**Q8: 如何设计一个日均10亿次请求的广告竞价系统？**

```
架构要点:
1. 接入层: K8s + GIN，单Pod QPS 5000
2. 特征层: Redis Cluster，特征预取<5ms
3. 模型层: GPU集群，pCTR推理<10ms
4. 出价层: 内存计算，Budget Pacing
5. 上报层: Kafka → Flink → ClickHouse
6. 容灾: 多可用区 + 异地备份
```

**Q9: Budget Pacing的S-curve原理？**

```
早期慢投: 避免预算过早耗尽
中期加速: 抓住流量高峰
后期收敛: 平滑收尾

公式: factor = remaining / (total × (1 - exp(-3×progress)))
限制范围: [0.5, 2.0]
```

---

## 五、高级问题

**Q10: 如何处理广告归因中的自竞争(自引流)问题？**

```
• 识别: 同一域名/品牌多次转化
• 屏蔽: 排除自有流量归因
• 修正: 使用增量测试校准
• 报告: 单独展示自竞争数据
```

**Q11: DSP端如何防止Bid Shading被攻击？**

```
• 噪声注入: 对出价添加少量随机噪声
• 动态阈值: 根据竞争环境动态调整
• 行为检测: 检测异常的bid波动
• 限速: 限制单广告主出价频率
```

**Q12: 如何实现跨平台广告归因？**

```
• Device Graph: 关联不同平台的设备ID
•概率匹配: 基于WiFi/地理位置/时间窗口
• 可信执行环境(TEE): 隐私保护下的数据匹配
• 联邦学习: 跨平台联合建模不共享原始数据
```

---

## 六、实战题

**Q13-20: 编码题**

```
Q13: 实现一个简单的Token Bucket限流器
Q14: 实现Redis ZSet滑动窗口频控
Q15: 实现pCTR模型的Platt Scaling校准
Q16: 实现S-curve Budget Pacing算法
Q17: 实现简单的决策树CTR模型
Q18: 实现Kafka生产者异步批处理
Q19: 实现gRPC流式响应
Q20: 实现简单的Circuit Breaker熔断器
```

---

## 七、自测题

1. **50ms SLA的分配原则？**
   - 特征5ms + 推理15ms + 出价5ms + 序列化5ms + 余量20ms

2. **Shapley Value的时间复杂度？**
   - O(2^n)，n为通道数，实际用Monte Carlo近似

