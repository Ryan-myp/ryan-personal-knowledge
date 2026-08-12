---
name: ad-fraud-detection-expert
description: "广告反作弊专家技能 — GNN  fraud 检测、实时风控、设备指纹、归因欺诈"
version: 1.0.0
author: ryan
tags: [advertising, fraud, security, gnn, real-time, expert]
---

# 广告反作弊专家技能

> 从设备指纹到 GNN 图神经网络，掌握生产级反作弊系统

## 核心能力

### 1. 欺诈类型识别
- **点击欺诈**：虚假点击骗取广告费
- **展示欺诈**：机器人流量、不可见曝光
- **归因欺诈**：劫持转化、Last Click 作弊
- **安装欺诈**：虚假安装、诱导安装
- **刷量作弊**：水军、自动化脚本

### 2. 风控系统架构
- **规则引擎**：预设规则匹配
- **设备指纹**：设备唯一标识
- **行为分析**：用户行为模式识别
- **实时决策**：毫秒级风险判定

### 3. GNN  fraud 检测
- **图构建**：用户-设备-IP-广告关系图
- **节点特征**：行为特征、设备特征
- **图算法**：PageRank、Node2Vec、GAT
- **异常检测**：Isolation Forest、AutoEncoder

### 4. 实时风控
- **流式处理**：Kafka + Flink 实时计算
- **特征工程**：实时特征聚合
- **模型推理**：在线模型服务
- **决策输出**：通过/拒绝/人工审核

## 知识库引用

| 主题 | 文档 |
|------|------|
| 反作弊系统 | `knowledge/advertising/ad-fraud-detection-deep.md` |
| 反作弊升级 | `knowledge/advertising/ad-fraud-detection-deep-v2.md` |
| GNN 实时检测 | `knowledge/advertising/ad-fraud-gnn-realtime-deep.md` |
| 误判处理 | `knowledge/advertising/ad-fraud-misjudge-fix.md` |
| 真实案例 | `knowledge/advertising/ad-fraud-detection-false-positive.md` |
| 防范策略 | `knowledge/advertising/ad-fraud-prevention-deep.md` |

## 使用场景

### 场景 1: 设计反作弊系统
1. 参考 `knowledge/advertising/ad-fraud-detection-deep.md`
2. 确定欺诈类型和检测策略
3. 设计规则引擎 + 模型 pipeline
4. 实现实时风控决策

### 场景 2: GNN fraud 检测
1. 构建关系图（用户-设备-IP-广告）
2. 提取节点和边特征
3. 训练图神经网络模型
4. 部署在线推理服务

### 场景 3: 排查误判问题
1. 查看 `knowledge/advertising/ad-fraud-misjudge-fix.md`
2. 分析误判案例特征
3. 调整模型阈值或规则
4. 建立人工审核流程

## 关键公式

```
Risk Score = w1 × RuleScore + w2 × ModelScore + w3 × BehaviorScore
Decision:
  Risk Score < 0.3  → 通过
  0.3 ≤ Risk Score < 0.7 → 人工审核
  Risk Score ≥ 0.7  → 拒绝
```

## 自测题

<details>
<summary>Q1: GNN 在反作弊中的应用原理是什么？</summary>

**答案**：
1. **图构建**：将用户、设备、IP、广告构成异构图
2. **特征学习**：Node2Vec/GAT 学习节点嵌入
3. **异常检测**：异常节点的嵌入向量与正常节点差异大
4. **传播效应**：通过图传播识别关联欺诈（同一设备关联多个账号）
5. **优势**：能捕捉复杂关联关系，比单点检测更准确

</details>

<details>
<summary>Q2: 设备指纹如何防止被绕过？</summary>

**答案**：
1. **多维度采集**：Canvas、WebGL、Font、Audio、屏幕分辨率
2. **熵值优化**：选择区分度高的特征组合
3. **容错机制**：允许部分特征变化，降低误判
4. **加密存储**：指纹数据加密，防止篡改
5. **动态更新**：定期更新指纹算法，应对新绕过技术

</details>

<details>
<summary>Q3: 如何平衡反作弊严格度和用户体验？</summary>

**答案**：
1. **分层决策**：高风险直接拒绝，中风险人工审核，低风险放行
2. **渐进式验证**：首次异常要求验证，后续降低验证频率
3. **白名单机制**：可信用户/设备加入白名单
4. **申诉通道**：提供便捷的申诉和复审流程
5. **持续优化**：基于反馈数据调整阈值和策略

</details>
