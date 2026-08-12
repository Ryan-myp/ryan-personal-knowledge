---
name: agent-skill-engineer
description: "Agent Skill 工程专家技能 — Skill 编写规范、经验蒸馏、测试方法、版本管理"
version: 1.0.0
author: ryan
tags: [agent, skill, engineering, distillation, testing, expert]
---

# Agent Skill 工程专家技能

> 从经验蒸馏到 Skill 发布，掌握生产级 Agent Skill 工程

## 核心能力

### 1. Skill 编写规范
- **Frontmatter**：元数据定义（name、description、version、tags）
- **结构规范**：核心能力、知识库引用、使用场景、自测题
- **内容标准**：源码级深度、ASCII 架构图、对比表格
- **版本管理**：语义化版本、CHANGELOG、向后兼容

### 2. 经验蒸馏
- **识别可蒸馏经验**：从实践中提取通用模式
- **抽象概括**：从具体案例到通用方法论
- **结构化表达**：模板化、标准化
- **验证测试**：用实际案例验证 Skill 有效性

### 3. 测试方法
- **单元测试**：Skill 核心逻辑测试
- **集成测试**：Skill 与系统交互测试
- **端到端测试**：完整场景验证
- **回归测试**：更新后验证不破坏已有功能

### 4. 版本管理
- **语义化版本**：MAJOR.MINOR.PATCH
- **变更日志**：记录每个版本变更
- **兼容性**：向后兼容原则
- **发布流程**：开发 → 测试 → 发布

## 知识库引用

| 主题 | 文档 |
|------|------|
| 经验蒸馏 | `references/distilling-principles.md` |
| 质量标准 | `references/quality-standards.md` |
| Skill 编写 | `knowledge/agent-ai/agent-skills-best-practices.md` |
| 开发实践 | `knowledge/agent-ai/agent-development-practice.md` |

## 使用场景

### 场景 1: 编写新 Skill
1. 确定 Skill 定位和目标用户
2. 参考现有 Skill 模板
3. 填充核心能力和知识库引用
4. 添加使用场景和自测题
5. 测试验证

### 场景 2: 蒸馏经验
1. 回顾近期项目中的最佳实践
2. 识别可复用的模式和解决方案
3. 抽象为通用的 Skill
4. 更新到 references/ 或 skills/

### 场景 3: 更新 Skill
1. 收集用户反馈和使用数据
2. 识别改进点
3. 制定变更计划
4. 执行更新并测试
5. 发布新版本

## Skill 模板

```markdown
---
name: {skill-name}
description: "{skill-description}"
version: {major}.{minor}.{patch}
author: {author}
tags: [{tag1}, {tag2}]
---

# {Skill Name}

> 一句话描述 Skill 的价值

## 核心能力

### 1. {能力 1}
- 要点 1
- 要点 2

### 2. {能力 2}
- 要点 1
- 要点 2

## 知识库引用

| 主题 | 文档 |
|------|------|
| ... | ... |

## 使用场景

### 场景 1: ...
1. ...
2. ...

### 场景 2: ...
1. ...
2. ...

## 关键代码/公式

```{code}
// ...
```

## 自测题

<details>
<summary>Q1: ...</summary>

**答案**：
...
</details>
```

## 自测题

<details>
<summary>Q1: Skill 和 reference 有什么区别？</summary>

**答案**：
- **Skill**：独立的、可复用的能力单元，有完整的 frontmatter 和结构
- **Reference**：辅助文档，记录特定问题的解决方案或架构决策
- **关系**：Skill 可以引用多个 Reference，Reference 可以作为 Skill 的知识来源

</details>

<details>
<summary>Q2: 如何判断一个经验是否值得蒸馏成 Skill？</summary>

**答案**：
1. **复用性**：是否能在多个场景中使用
2. **通用性**：是否抽象掉了具体细节
3. **价值**：是否能显著提升效率或质量
4. **成熟度**：是否经过实践验证
5. **可维护性**：是否易于理解和更新

</details>

<details>
<summary>Q3: Semantic Versioning 在 Skill 中如何应用？</summary>

**答案**：
- **MAJOR**：不兼容的 API/结构变更
- **MINOR**：向后兼容的功能新增
- **PATCH**：向后兼容的问题修复
- **示例**：1.0.0 → 1.1.0（新增能力）→ 1.1.1（修复 bug）→ 2.0.0（重构）

</details>
