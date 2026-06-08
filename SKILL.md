---
name: ryan-personal-knowledge
description: "Ryan 的个人学习仪表盘 + 知识库：追踪学习进度、沉淀广告业务/Agent技术知识、记录前沿洞察、管理碎片时间任务。"
version: 1.1.0
author: ryan
platforms: [linux, macos]
metadata:
  hermes:
    tags: [personal, learning, knowledge, progress, blogwatcher, notes]
---

# Ryan 个人学习仪表盘 + 知识库

## 概述

这是 Ryan 的个人学习与知识管理体系。包含：
1. **成长计划** — 从 TL 到高级/资深专家的学习路线、目标、监督机制
2. **知识库** — 广告业务、Agent技术、全栈开发、前沿追踪的知识笔记
3. **碎片任务管理** — 适合 15-30min 碎片时间完成的学习/沉淀任务
4. **前沿监控** — 通过 blogwatcher 自动推送

## 目录结构

```
ryan-personal-knowledge/
├── SKILL.md                              ← 主文件，定义使用规则
├── references/
│   └── distilling-principles.md          ← 从经验蒸馏 skill 的决策框架
├── templates/
│   ├── learning-note.md                  ← 知识笔记模板
│   ├── progress-log.md                   ← 学习进度日志模板
│   └── 前沿-insight.md                   ← 前沿洞察模板
├── progress/
│   └── roadmap.md                        ← 学习路线总览
├── knowledge/
│   ├── advertising/                      ← 广告业务知识
│   │   ├── google/                       ← Google Ads, PMax, GMX
│   │   ├── meta/                         ← FB Ads, IG, Advantage+
│   │   ├── tiktok/                       ← TikTok Ads, Pangle
│   │   ├── snapchat/                     ← Snapchat Ads
│   │   ├── amazon/                       ← Amazon DSP
│   │   ├── microsoft/                    ← Microsoft Advertising
│   │   ├── x/                            ← X/Twitter Ads
│   ├── agent-tech/                       ← Agent 技术知识
│   ├── fullstack/                        ← 全栈开发知识
│   ├── 前沿/                             ← 前沿追踪
│   └── growth-plan/                      ← 成长计划（新增）
│       └── growth-roadmap.md             ← 从TL到高级专家路线图
├── books/
│   ├── reading-list.md                   ← 待读书单
│   ├── reading-progress.md               ← 阅读进度跟踪
│   └── notes/                            ← 读书笔记
│       └── {book-name}.md               ← 每本书的笔记
└── tasks/
    └── 碎片任务.md                       ← 碎片任务看板
```
    └──碎片任务.md                     # 碎片任务看板
```

## 一、学习路线总览

当前四条学习线：

### 1. Agent 技术 (核心重点)
- **目标**: 深入理解 Agent 架构、编排、Skill 工程、多 Agent 协作
- **进度**: 查看 `progress/roadmap.md`
- **里程碑**:
  - [ ] 掌握 Hermes 配置与扩展
  - [ ] 理解并实践多 Agent 并行调度
  - [ ] 能够编写高质量 Skill
  - [ ] 对比 Claude Code / Codex / OpenCode
  - [ ] 构建个人 Skill 生态

### 2. 全栈开发
- **目标**: 提升工程能力，覆盖前后端 + DevOps
- **进度**: 查看 `progress/roadmap.md`
- **里程碑**:
  - [ ] 掌握 TDD 工作流
  - [ ] 系统化调试能力
  - [ ] 熟练 Git worktree + PR 流程

### 3. 广告业务深度
- **目标**: 深入理解广告平台架构、API、数据流
- **进度**: 查看 `progress/roadmap.md`
- **里程碑**:
  - [ ] 熟练 ad-knowledge-query 定位实现
  - [ ] 能够沉淀业务文档
  - [ ] 掌握测试设计流程

### 4. 前沿追踪
- **目标**: 持续跟踪 LLM / Agent / MLOps 前沿
- **进度**: 通过 blogwatcher 自动推送，笔记存于 `knowledge/前沿/`
- **工具**: blogwatcher + arxiv + llm-wiki

## 二、知识库使用

### 添加知识笔记

当学习/工作中获得新认知时，使用 `templates/learning-note.md` 模板：

```bash
# 1. 复制模板
cp templates/learning-note.md knowledge/agent-tech/某个主题.md

# 2. 编辑内容
# 填写：日期、标签、核心概念、实践心得、相关 links
```

### 笔记标签体系

- `#agent-architecture` — Agent 架构相关
- `#skill-engineering` — Skill 编写经验
- `#ad-api` — 广告 API 知识
- `#ad-dataflow` — 数据流/调用链
- `#fullstack` — 全栈开发实践
- `#frontend` — 前端相关
- `#backend` — 后端相关
- `#devops` — 运维/部署
- `#前沿-llm` — LLM 前沿
- `#前沿-agent` — Agent 前沿
- `#前沿-mlops` — MLOps 前沿
- `#排障经验` — 排坑记录
- `#工具对比` — 工具选型对比

## 三、碎片任务管理

任务存储在 `tasks/碎片任务.md`，格式：

```markdown
## 待办
- [ ] #agent-技术 #15min 读一篇 blogwatcher 推送的文章
- [ ] #skill #20min 把 ad-knowledge-query 的坑蒸馏成 skill
- [ ] #广告 #30min 给某个模块写知识库

## 进行中
- [x] #agent #30min 写第一个个人 skill

## 已完成（归档到 history/）
```

### 碎片任务原则
- 每个任务标注预计时间 (#15min / #20min / #30min / #60min)
- 任务完成后更新状态，积累的经验蒸馏进知识库
- 每周回顾一次，更新 roadmap.md

## 四、进度日志

每次学习后记录进度到 `progress/progress-log-YYYY-MM.md`：

```markdown
## 2025-01-15
- 学习了什么
- 实践了什么
- 产出（笔记链接）
- 下一步
```

## 五、使用场景

### 场景 1: 收到新任务时
1. 检查 `knowledge/` 是否有相关笔记
2. 如果有，先复习再动手
3. 完成后更新/新增笔记

### 场景 2: 碎片时间学习时
1. 查看 `tasks/碎片任务.md`，选一个任务
2. 完成后更新进度 + 写笔记
3. 把经验蒸馏成 skill（如果需要）

### 场景 3: 积累到一定量时
1. 考虑是否值得把经验蒸馏成独立 skill
2. 更新 roadmap.md 的里程碑状态
3. 清理过时的碎片任务

### 场景 4: 前沿追踪
1. blogwatcher 自动推送（需配置）
2. 有价值的文章 → 写前沿洞察笔记
3. 定期汇总到 `knowledge/前沿/summary-YYYY-QN.md`

## 六、与 Hermes 现有体系的关系

- 本 skill 是个人知识管理，不影响现有 111 个 skills
- 经验蒸馏成可复用 skill 时，写到 `~/.hermes/skills/` 下
- 本 skill 的笔记供个人回顾，不自动加载到 agent prompt
- 用 `session_search` 也可以搜历史对话中的知识点

## 七、知识库搜索 — 如何快速查找知识

知识库内置了基于 biz-delivery 框架的轻量级搜索引擎 `knowledge-search/`，支持意图识别 + 多路融合查询。

### 快速使用

```bash
# 进入 knowledge-search 目录
cd knowledge-search

# 基础搜索 — 关键词匹配
python3 query_knowledge.py "Redis 相关的书"

# 查询意图 — 自动识别"查找/查看"类查询
python3 query_knowledge.py "我想看 Redis 相关的书"

# 提问意图 — 自动识别"怎么/如何"类问题
python3 query_knowledge.py "怎么集成 agentmemory"

# 对比意图 — 自动识别"对比/比较"类查询
python3 query_knowledge.py "对比 agentmemory 的三种方案"

# 排障意图 — 自动识别"排障/错误"类问题
python3 query_knowledge.py "seaTalk bridge 怎么排障"
```

### 搜索维度
搜索引擎从 4 个维度交叉匹配，RRF 融合排序：

1. **📄 文件内容** — 全文关键词匹配（权重最高）
2. **📁 目录路径** — 文件所在目录匹配（如 agent-tech, advertising）
3. **🏷️ 标签** — #tag 关键词匹配（如 #前沿, #agent-技术）
4. **📑 文件名/标题** — Markdown 文件名和 # 标题匹配

### 意图自动识别

搜索引擎会自动识别你的查询意图，选择最优搜索策略：

| 意图 | 触发词 | 权重倾向 |
|------|--------|---------|
| query (查询) | 查看/查找/获取 | 文件内容 0.8 |
| question (提问) | 怎么/如何/为什么 | 文件内容 0.8 |
| explain (解释) | 原理/机制/解释 | 文件内容 0.9 |
| compare (对比) | 对比/比较/区别 | 标签 0.8 |
| debug (排障) | 排障/错误/bug | 文件内容 0.9 |

### 高级选项

```bash
# 重建索引（当新增/修改文件后）
python3 query_knowledge.py "关键词" --rebuild

# 清除查询缓存
python3 query_knowledge.py "关键词" --clear-cache

# 查看详细信息
python3 query_knowledge.py "关键词" --verbose
```

### 工作原理

```text
用户查询
    │
    ▼
意图识别 → 选择各搜索维度的权重
    │
    ▼
多路并行查询（内容 / 文件名 / 标签 / 目录）
    │
    ▼
RRF 融合（按命中排名加权）
    │
    ▼
返回排序后的 Top-K 结果 + 摘要 + 标签
```

### 与 biz-delivery 的关系

`knowledge-search` 复用了 biz-delivery 框架的核心能力：
- 意图识别逻辑 → 来自 `biz-delivery/scripts/smart_routing.py`
- RRF 融合引擎 → 来自 `biz-delivery/scripts/rrf_fusion.py`
- 查询缓存机制 → 来自 `biz-delivery/scripts/query_cache.py`
- 配置化 Profile → 类似 biz-delivery 的 profile.json

---

## 八、已知问题与排障

- `blogwatcher` 的大多数主流 AI 博客 (Anthropic, OpenAI, Google AI, Meta AI) RSS feed 已失效，只有 Hugging Face 正常工作。详见 `knowledge/前沿/blogwatcher-setup.md` 和 `references/verified-feeds.md`。
- 大型二进制 tar 文件在 macOS 上用 `tar xzf` 可能触发系统超时阻断。备选方案：用 Python `tarfile` 模块解压。
- 确认包内结构：`tar -tzf file.tar.gz` 先看文件名再决定解压路径。

- Blogwatcher 配置见 `references/blogwatcher-setup.md`
- 验证可用的 RSS feed 见 `references/verified-feeds.md`

## 新增技能

### agentmemory 集成 (2025-06-05)
- agentmemory 是一个成熟的持久化记忆引擎（21.3k ⭐），可为 AI 编码代理提供自动记忆
- 与 Hermes 的集成方式见 `references/agentmemory-integration.md`
- 采用方案 C（混合模式）：保留 Hermes 内置记忆 + agentmemory 作为增强层
- 依赖：iii-engine (v0.11.2) + @agentmemory/agentmemory (npm)

## 七、GitHub 仓库

本 skill 的内容同步到 GitHub 用于版本管理和协作：
- 仓库: `https://github.com/Ryan-myp/ryan-personal-knowledge`
- 每次更新 commit + push 保持本地和远程一致

## 八、个人 Sub-skill 体系

> 从经验蒸馏出的可复用 skill 统一作为本 skill 的 references 子文件

当前 sub-skill（以 references/ 文件形式存在于本 skill 下）：
- `references/seatalk-bridge-troubleshooting.md` — SeaTalk bridge 排障指南
- `references/agentmemory-integration.md` — agentmemory 与 Hermes 集成指南
- `references/macos-tar-workaround.md` — macOS 大文件 tar 解压避坑

创建规则：
1. 不新建独立 skill 目录（避免碎片化）
2. 蒸馏结果作为 `references/` 文件加入本 umbrella
3. SKILL.md 头部维护一个引用列表
