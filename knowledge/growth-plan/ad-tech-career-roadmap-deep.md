# 广告技术人成长路线：从入门到架构师

> 基于广告技术栈的完整学习路径，覆盖竞价/排序/Agent/架构

---

## 第一部分：广告技术能力矩阵

```
广告技术人才四维度：
┌─────────────────────────────────────────────────────────────────────┐
│ 1. 技术深度（Technical Depth）                                       │
│    • Go/Python 语言级                                                │
│    • MySQL/Redis/ClickHouse 源码级                                   │
│    • Linux 内核级                                                    │
│    • 高并发/分布式系统设计                                            │
│                                                                     │
│ 2. 广告领域（Advertising Domain）                                    │
│    • RTB/竞价/排序/归因                                             │
│    • 多平台 API（Meta/Google/TikTok/DV360）                          │
│    • 广告协议（OpenRTB/TCF/Privacy Sandbox）                         │
│    • 反欺诈/合规                                                     │
│                                                                     │
│ 3. AI/Agent（AI & Agent）                                          │
│    • 推荐系统（召回/排序/重排）                                      │
│    • 深度学习（DeepFM/DIN/MMOE）                                     │
│    • Agent 编排（MCP/技能系统/图编排）                               │
│    • NL2AD/对话式广告                                               │
│                                                                     │
│ 4. 架构与领导力（Architecture & Leadership）                        │
│    • 系统架构设计                                                    │
│    • 高可用/高并发/容灾                                              │
│    • 团队管理/技术影响力                                             │
│    • 商业思维                                                        │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 第二部分：学习路线图

### Phase 1: 基础夯实（0-6 个月）

```
目标：掌握广告系统核心技术栈

技术栈：
• Go 语言：并发编程/网络编程
• MySQL：索引优化/事务/锁
• Redis：数据结构/持久化/集群
• Linux：系统调用/性能调优
• HTTP/HTTPS：协议基础

广告基础：
• 广告术语：CPM/CPC/CPA/CTR/CVR/ROAS
• 广告流程：展示→点击→转化→归因
• 广告平台：Meta Ads/Google Ads/TikTok Ads

学习资源：
• 《Go 语言圣经》
• 《MySQL 技术内幕》
• Redis 官方文档
• 广告平台官方文档
```

### Phase 2: 进阶提升（6-18 个月）

```
目标：深入广告核心技术

技术栈：
• Kafka：消息队列/事件流
• ClickHouse：列式数据库/数仓
• Elasticsearch：搜索引擎
• Docker/K8s：容器化/编排

广告进阶：
• RTB 竞价流程
• 多路召回/排序模型
• A/B 测试/实验设计
• 广告归因模型

学习资源：
• 《Kafka 权威指南》
• ClickHouse 官方文档
• 《推荐系统实战》
• 广告平台 API 文档
```

### Phase 3: 专家突破（18-36 个月）

```
目标：成为广告技术专家

技术栈：
• 分布式系统：一致性/分片/容错
• 深度学习：PyTorch/TensorFlow
• 大数据：Spark/Flink
• 可观测性：OTel/Prometheus/Grafana

广告专家：
• 竞价策略优化（RL/Bandit）
• 排序模型（DeepFM/DIN/MMOE）
• 多平台 API 集成
• 反欺诈/GNN

学习资源：
• 《Designing Data-Intensive Applications》
• 《Deep Learning》(Goodfellow)
• Spark 官方文档
• 论文阅读（SIGIR/KDD/WWW）
```

### Phase 4: 架构师（3-5 年）

```
目标：系统架构师/技术负责人

技术栈：
• 云原生：Service Mesh/Istio
• 多活容灾：跨区域部署
• 成本优化：Spot 实例/Reserved
• 安全合规：GDPR/CCPA

架构能力：
• 系统架构设计
• 团队管理
• 技术选型
• 跨部门协作

领导力：
• 技术影响力（演讲/开源/专利）
• 商业思维（ROI/成本/收益）
• 人才培养（mentorship）
```

---

## 第三部分：技能评估

### 自评量表

```
技能等级：
1. 了解（Awareness）：知道是什么，能解释基本概念
2. 会用（Proficient）：能在项目中实际应用
3. 精通（Expert）：能解决复杂问题，优化性能
4. 专家（Authority）：能设计架构，指导他人

示例：Go 网络编程
• Level 1：知道 net/http 的基本用法
• Level 2：能用 net/http 构建 REST API
• Level 3：理解 Netpoller 源码，能优化高并发
• Level 4：能设计新的网络框架
```

### 面试准备

```
高频面试题：
1. Go 相关：
   • GMP 调度器工作原理
   • Netpoller 实现细节
   • GC 机制和调优
   • 内存分配器设计

2. 数据库：
   • MySQL InnoDB 事务隔离级别
   • Redis 持久化机制
   • ClickHouse 查询优化

3. 广告系统：
   • RTB 竞价流程
   • 排序模型选型
   • 高并发设计

4. 系统设计：
   • 设计一个广告系统
   • 如何保证数据一致性
   • 如何做容灾设计
```

---

## 第四部分：自测题

### Q1: 广告技术人应该优先学习什么？

**A**: 先打好 Go/MySQL/Redis 基础，再深入广告领域知识（竞价/排序/归因），最后学习 AI/Agent 和架构设计。

### Q2: 如何衡量学习效果？

**A**: 
1. 能独立完成广告系统模块开发
2. 能通过面试
3. 能在生产中解决复杂问题
4. 能指导他人

### Q3: 广告技术人的核心竞争力是什么？

**A**: 技术深度 + 广告领域知识 + AI/Agent 能力 + 架构设计能力的组合。单纯的技术或单纯的广告知识都不够，需要跨界整合。

---

## 第五部分：生产实践

### 1. 学习计划

```
每周学习建议：
• 20% 时间：阅读源码/论文
• 30% 时间：动手实践（写代码/搭环境）
• 30% 时间：输出（写文档/博客）
• 20% 时间：交流（讨论/分享）
```

### 2. 资源推荐

```
书籍：
• 《Go 语言设计与实现》
• 《MySQL 技术内幕》
• 《Redis 设计与实现》
• 《Designing Data-Intensive Applications》
• 《推荐系统实战》

课程：
• Coursera: Machine Learning (Andrew Ng)
• Udemy: Go 语言实战
• B 站: 广告技术系列

论文：
• DeepFM (SIGIR 2017)
• DIN (KDD 2018)
• MMOE (KDD 2018)
• PLE (KDD 2020)
```

### 3. 成长里程碑

```
里程碑检查：
□ 能独立开发广告系统模块
□ 能优化数据库查询性能
□ 能设计高并发系统
□ 能使用 ClickHouse 做数据分析
□ 能部署和维护 K8s 集群
□ 能设计广告排序模型
□ 能实现 NL2AD 功能
□ 能设计多活容灾架构
□ 能指导团队成员成长
□ 能在技术会议上分享
```
