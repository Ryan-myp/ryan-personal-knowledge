# 批处理与流处理架构对比

> 深入批处理和流处理：架构模式、技术选型、性能优化。

---

## 1. 架构对比

| 特性 | 批处理 | 流处理 |
|------|--------|--------|
| 延迟 | 分钟 ~ 小时 | 毫秒 ~ 秒 |
| 吞吐量 | 高 | 中 |
| 数据模型 | 有限数据集 | 无限数据流 |
| 典型场景 | ETL、报表 | 实时监控 |
| 代表技术 | Spark, Hadoop | Flink, Kafka Streams |

---

## 2. Lambda 架构

```
         Data In (Kafka)
               │
    ┌──────────┼──────────┐
    ▼          ▼          ▼
Speed Layer  Batch Layer  Serving Layer
 (Flink)    (Spark)     (ClickHouse)
```

---

## 3. 技术选型

| 场景 | 推荐方案 |
|------|----------|
| 离线数仓 | Spark + Hive |
| 实时数仓 | Flink + ClickHouse |
| 日志处理 | Kafka + Logstash |
| 流式分析 | Flink |

---

## 4. 实践 Checklist
- [ ] 明确延迟要求
- [ ] 选择合适的计算引擎
- [ ] 配置合理的并发度
- [ ] 实现数据质量监控

**参考**: Data Engineering 书籍、Apache 官方文档
