---
name: ad-creative-agent-expert
description: "广告创意 Agent 专家技能 — AI 创意生成、NL2Ad、对话式投放、创意优化"
version: 1.0.0
author: ryan
tags: [advertising, creative, ai, nl2ad, agent, expert]
---

# 广告创意 Agent 专家技能

> 从 AI 创意生成到对话式投放，掌握广告创意智能化

## 核心能力

### 1. NL2Ad (自然语言到广告)
- **意图理解**：理解用户投放需求
- **素材生成**：文案、图片、视频的自动生成
- **A/B Test**：多创意自动生成和测试
- **优化迭代**：基于效果数据的创意优化

### 2. AI 创意生成
- **文案生成**：GPT/Claude 生成广告文案
- **图片生成**：DALL-E/Stable Diffusion 生成素材
- **视频生成**：AI 视频剪辑和生成
- **多模态融合**：文本+图片+视频组合

### 3. 对话式投放
- **意图识别**：理解用户投放意图
- **问答交互**：对话式需求澄清
- **方案推荐**：基于历史的创意推荐
- **效果反馈**：投放效果实时反馈

### 4. 创意评估
- **自动评分**：基于规则的创意质量评分
- **预测点击率**：pCTR 预估创意效果
- **品牌安全**：创意内容品牌适配检查
- **合规检查**：广告法规合规性检查

## 知识库引用

| 主题 | 文档 |
|------|------|
| AI 创意生成 | `knowledge/agent-ai/ad-ai-creative-generation-deep.md` |
| 创意优化 | `knowledge/advertising/ad-creative-optimization-deep.md` |
| 创意生成案例 | `knowledge/advertising/ad-creative-generation-optimization-case-deep.md` |
| NL2Agent | `knowledge/advertising/ad-nl2agent-deep.md` |
| 对话平台 | `knowledge/advertising/ad-conversational-platform-deep.md` |
| 创意自动化 | `knowledge/advertising/ad-creative-automation-deep.md` |
| 创意分享 | `knowledge/advertising/a-creative-sharing-deep.md` |

## 使用场景

### 场景 1: 设计 NL2Ad 系统
1. 参考 `knowledge/agent-ai/ad-agent-nl2ad-deep.md`
2. 设计意图理解模块
3. 集成 AI 生成能力
4. 实现效果反馈闭环

### 场景 2: 创意 A/B Test 自动化
1. 自动生成多版本文案/图片
2. 快速投放测试
3. 自动选择优胜创意
4. 迭代优化

### 场景 3: 创意质量评估
1. 实现自动评分规则
2. 集成 pCTR 预估
3. 品牌安全检测
4. 合规性检查

## 关键流程

```
用户需求 → 意图理解 → 创意生成 → 质量评估 → 投放测试 → 效果反馈 → 优化迭代
    ↑                                                                  ↓
    └──────────────────── 用户确认 ←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←┘
```

## 自测题

<details>
<summary>Q1: NL2Ad 系统的关键技术挑战是什么？</summary>

**答案**：
1. **意图理解**：用户描述模糊，需要多轮澄清
2. **创意质量**：生成的创意需要符合品牌调性
3. **个性化**：不同受众需要不同创意
4. **合规性**：广告内容需要符合法规
5. **效果可预测**：生成前预估效果困难

</details>

<details>
<summary>Q2: 如何用 AI 实现创意 A/B Test 自动化？</summary>

**答案**：
1. **批量生成**：基于模板生成 N 个变体
2. **快速投放**：小预算快速测试
3. **数据收集**：实时收集点击/转化数据
4. **统计显著**：确保样本量足够
5. **自动优选**：统计方法选择优胜创意
6. **迭代优化**：基于优胜创意继续迭代

</details>

<details>
<summary>Q3: 创意质量评估的自动化方案？</summary>

**答案**：
1. **规则评分**：关键词、长度、标点等规则
2. **ML 评分**：基于历史数据的创意质量预测
3. **pCTR 预估**：预测创意的点击率
4. **品牌适配**：创意与品牌调性一致性
5. **合规检查**：敏感词、商标、法规检查
6. **综合评分**：加权融合各维度分数

</details>
