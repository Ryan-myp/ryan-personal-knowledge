# 个人 Skill 蒸馏原则

**日期**: 2025-06-05
**上下文**: 从会话中蒸馏可复用 skill 时的决策框架

## 核心原则

**绝不修改用户现有的 skills**（包括 ad-ai-coding 下的 111+ skills）。用户明确偏好：
- 个人知识积累走 `ryan-personal-knowledge` 体系（笔记 + 碎片任务）
- 经验蒸馏成可复用 skill 时，新建独立 skill 文件，不触碰已有 skill
- 现有 skills 处于迭代优化中，由用户或 CI 流程管理

## 蒸馏决策流程

```
用户分享经验/排障/集成
    ↓
值得复用？(5+ tool calls / 复杂流程 / 用户说"记住这个")
    ↓
是 → 新建独立 skill（ryan-xxx- 前缀）
    ↓
不是 → 只记入 knowledge/ 笔记
```

## 什么时候蒸馏成 Skill

- 排障流程有固定 checklist（如 seaTalk bridge）
- 工具配置有多步骤、容易遗忘
- 用户明确说"写成 skill 吧"
- 同一个模式在 future session 会被重复调用

## 什么时候只记笔记

- 一次性任务
- 纯知识性内容（API 文档、概念理解）
- 实验性/探索性内容
- 用户说"先记笔记，后面再说"
