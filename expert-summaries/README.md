# Ryan 个人知识库 — 全面优化版 v3.0

> 目标：打造广告业务 + Agent 技术的资深专家级知识库
> 知识库规模：1205+ 文档，17MB，覆盖广告/Agent/全栈/成长四大领域

## 🎯 核心定位

**广告业务 + Agent 技术双精通的资深专家知识库**

| 维度 | 目标水平 | 当前进度 |
|------|---------|---------|
| 广告竞价系统 | 资深专家 | ⭐⭐⭐⭐⭐ |
| 广告平台 API | 资深专家 | ⭐⭐⭐⭐⭐ |
| Agent 架构设计 | 资深专家 | ⭐⭐⭐⭐ |
| Go 语言深入 | 资深专家 | ⭐⭐⭐⭐ |
| 全栈工程能力 | 高级专家 | ⭐⭐⭐⭐ |
| 技术领导力 | 高级专家 | ⭐⭐⭐ |

## 📦 Expert Skills 体系

### 广告专家技能 (7 个)
- `ad-bidding-expert` — 竞价引擎设计、RTB/RTA、出价策略
- `ad-platform-api-expert` — Google/Meta/TikTok/DV360 API 深度
- `ad-attribution-expert` — 归因模型、增量测量、LTV/CAC
- `ad-dsp-architecture-expert` — DSP 高并发架构、性能优化
- `ad-ssp-architecture-expert` — SSP 库存管理、收益最大化
- `ad-fraud-detection-expert` — 反作弊系统、GNN 检测
- `ad-creative-agent-expert` — AI 创意生成、NL2Ad

### Agent 专家技能 (5 个)
- `agent-architecture-expert` — ReAct/Planner/Multi-Agent
- `agent-rag-expert` — RAG 系统、向量数据库、检索优化
- `agent-memory-expert` — 持久化记忆、agentmemory
- `agent-skill-engineer` — Skill 编写规范、经验蒸馏
- `agent-observability-expert` — Agent 可观测性、调试

### 全栈专家技能 (4 个)
- `go-deep-expert` — GMP/GC/网络/内存源码级
- `mysql-expert` — InnoDB 内核、事务、锁、调优
- `redis-expert` — 数据结构、持久化、集群
- `elasticsearch-expert` — 倒排索引、查询优化

### 成长专家技能 (3 个)
- `tech-leadership-expert` — 技术决策、架构治理
- `ad-business-strategy-expert` — 广告业务战略、ROI
- `team-management-expert` — 团队管理、人才培养

## 📊 知识库结构

```
ryan-personal-knowledge/
├── skills/                          ← Expert Skills 体系
│   ├── README.md
│   ├── ad-bidding-expert/
│   ├── ad-platform-api-expert/
│   ├── ad-attribution-expert/
│   ├── ad-dsp-architecture-expert/
│   ├── agent-architecture-expert/
│   ├── go-deep-expert/
│   └── tech-leadership-expert/
├── knowledge/                       ← 原始知识库 (1205 文件)
│   ├── advertising/                 ← 广告业务 (236 文件)
│   │   ├── day-by-day/              ← 每日学习笔记
│   │   ├── google-ads/              ← Google Ads 深度
│   │   ├── meta-ads/                ← Meta Ads 深度
│   │   ├── tiktok-ads/              ← TikTok Ads 深度
│   │   └── dv360/                   ← DV360 深度
│   ├── agent-ai/                    ← Agent 技术 (46 文件)
│   │   ├── day-by-day/              ← 每日学习笔记
│   │   └── archive/                 ← 归档内容
│   ├── fullstack/                   ← 全栈开发 (202 文件)
│   │   ├── backend/
│   │   ├── frontend/
│   │   ├── devops/
│   │   └── tdd/
│   ├── growth-plan/                 ← 成长计划 (17 文件)
│   └── 前沿/                        ← 前沿追踪
├── templates/                       ← 模板库
├── tasks/                           ← 碎片任务管理
├── progress/                        ← 学习进度追踪
├── books/                           ← 阅读管理
├── knowledge-search/                ← 知识库搜索引擎
└── references/                      ← 参考文档
```

## 🔍 知识搜索

```bash
# 进入 knowledge-search 目录
cd knowledge-search

# 基础搜索
python3 query_knowledge.py "Redis 相关的书"

# 提问意图
python3 query_knowledge.py "怎么集成 agentmemory"

# 对比意图
python3 query_knowledge.py "对比 agentmemory 的三种方案"

# 重建索引
python3 query_knowledge.py "关键词" --rebuild
```

## 📈 学习路线

### 第一阶段：基础夯实 (已完成)
- [x] Hermes 配置与扩展
- [x] 广告系统架构理解
- [x] Go 语言深入
- [x] MySQL/Redis 源码级理解

### 第二阶段：专业深化 (进行中)
- [x] Agent 架构设计
- [x] RAG 系统设计
- [x] 竞价引擎设计
- [ ] Multi-Agent 编排
- [ ] DSP 高并发优化

### 第三阶段：专家突破 (计划中)
- [ ] 多工具链对比实践
- [ ] 构建个人 Agent 生态
- [ ] 技术影响力建设
- [ ] 团队技术体系搭建

## 🎯 当前重点

1. **广告业务深度** — 补齐 SSP、反作弊、创意 AI 方向
2. **Agent 实战** — delegate_task 实践、多 Agent 协作
3. **Skill 蒸馏** — 将经验提炼为可复用 skill
4. **前沿追踪** — 持续更新 agent/memory/RAG 方向

## 📝 更新日志

- **2026-08-12**: v3.0 全面优化，创建 Expert Skills 体系，新增 7 个广告 skill + 5 个 Agent skill + 4 个全栈 skill + 3 个成长 skill
- **2026-06-08**: v2.0 知识库骨架搭建，1200+ 文件大规模升级
