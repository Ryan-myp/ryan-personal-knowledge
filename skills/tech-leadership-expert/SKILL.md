---
name: tech-leadership-expert
description: "技术领导力专家技能 — 技术决策、架构治理、技术影响力、团队技术建设"
version: 1.0.0
author: ryan
tags: [leadership, architecture, influence, career, expert]
---

# 技术领导力专家技能

> 从工程师到技术 Leader，掌握技术决策与团队影响力

## 核心能力

### 1. 技术决策
- **架构选型**：技术栈选择、框架评估、Vendor 评估
- **技术债管理**：识别、评估、偿还优先级
- **风险权衡**：技术风险 vs 业务风险
- **决策框架**：ADR (Architecture Decision Records)

### 2. 架构治理
- **设计规范**：API 设计规范、代码规范、数据库规范
- **评审机制**：Code Review、架构评审、技术方案评审
- **技术栈演进**：渐进式迁移、兼容性保障
- **质量门禁**：自动化测试、CI/CD、监控告警

### 3. 技术影响力
- **技术分享**：内部分享、行业会议、技术博客
- **开源贡献**：参与开源项目、建立个人品牌
- **知识沉淀**：文档体系、Wiki、培训材料
- **导师机制**：培养新人、建立技术梯队

### 4. 团队技术建设
- **技术规划**：年度/季度技术路线图
- **能力建设**：技术培训、技术雷达、实践社区
- **技术文化**：技术创新氛围、试错文化
- **招聘面试**：技术面试标准、人才评估

## 知识库引用

| 主题 | 文档 |
|------|------|
| 技术领导力 | `knowledge/growth-plan/tech-leadership.md` |
| 技术影响力 | `knowledge/growth-plan/tech-influence.md` |
| 成长路线图 | `knowledge/growth-plan/growth-roadmap.md` |
| 技术面试 | `knowledge/growth-plan/ad-tech-interview-qa-deep.md` |
| 职业道路 | `knowledge/growth-plan/ad-tech-career-roadmap-deep.md` |
| 行业影响 | `knowledge/growth-plan/industry-influence-deep.md` |

## 使用场景

### 场景 1: 技术选型决策
1. 明确业务需求和约束
2. 列出候选方案
3. 评估各方案优劣（技术/成本/风险）
4. 编写 ADR 记录决策过程
5. 参考 `knowledge/growth-plan/tech-leadership.md`

### 场景 2: 技术债治理
1. 识别技术债（代码/架构/流程）
2. 评估影响范围和优先级
3. 制定偿还计划
4. 建立技术债追踪机制

### 场景 3: 技术影响力建设
1. 确定个人技术品牌定位
2. 建立内容输出节奏（博客/分享）
3. 参与行业社区和开源项目
4. 参考 `knowledge/growth-plan/tech-influence.md`

## 技术决策框架

### 决策矩阵
| 维度 | 权重 | 评分 (1-5) |
|------|------|-----------|
| 技术成熟度 | 25% | |
| 团队熟悉度 | 20% | |
| 生态活跃度 | 20% | |
| 长期维护成本 | 15% | |
| 业务适配度 | 20% | |

### ADR 模板
```markdown
## 标题
状态： Proposed / Accepted / Deprecated / Superseded
日期： YYYY-MM-DD

## 上下文
## 决策
## 后果
```

## 自测题

<details>
<summary>Q1: 如何处理技术债与业务需求的冲突？</summary>

**答案**：
1. **量化技术债影响**：计算技术债导致的研发效率损失、线上故障成本
2. **建立技术债看板**：可视化技术债，定期 review
3. **20% 时间原则**：每个 sprint 预留 20% 时间处理技术债
4. **业务价值对齐**：将技术债偿还与业务价值挂钩
5. **渐进式偿还**：不要一次性大规模重构，采用绞杀者模式

</details>

<details>
<summary>Q2: 如何建立有效的 Code Review 文化？</summary>

**答案**：
1. **明确标准**：制定 CR checklist，统一评审标准
2. **及时响应**：设定 SLA（如 24h 内完成 CR）
3. **建设性反馈**：对事不对人，提供改进建议
4. **自动化先行**：先通过 Linter/格式化工具解决形式问题
5. **持续改进**：定期 review CR 质量，收集反馈

</details>

<details>
<summary>Q3: 技术 Leader 的技术深度和广度如何平衡？</summary>

**答案**：
1. **T 型发展**：一专多能，在核心领域保持深度
2. **有所取舍**：不需要在所有技术领域都深入
3. **保持手感**：每周至少写一些代码，保持技术敏感
4. **深度优先**：优先保证核心业务领域的技术深度
5. **广度辅助**：广度用于技术选型和架构设计

</details>
