# Expert Skills 目录

> 从知识库中蒸馏出的可复用 expert skills
> 每个 skill 对应一个专业领域，可直接被 agent 加载使用

## Skill 体系

### 🎯 广告专家技能 (Advertising Expert Skills)

| Skill | 描述 | 状态 |
|-------|------|------|
| `ad-bidding-expert` | 竞价引擎设计、RTB/RTA、出价策略、质量分计算 | ✅ |
| `ad-platform-api-expert` | Google/Meta/TikTok/DV360 Marketing API 专家 | ✅ |
| `ad-attribution-expert` | 归因模型、增量测量、LTV/CAC、ROI 优化 | ✅ |
| `ad-dsp-architecture-expert` | DSP 系统设计、高并发架构、性能调优 | ✅ |
| `ad-ssp-architecture-expert` | SSP 系统设计、库存管理、收益最大化 | ✅ |
| `ad-fraud-detection-expert` | 反作弊系统、GNN 检测、实时风控 | ✅ |
| `ad-creative-agent-expert` | AI 创意生成、NL2Ad、对话式投放 | ✅ |

### 🤖 Agent 专家技能 (Agent Expert Skills)

| Skill | 描述 | 状态 |
|-------|------|------|
| `agent-architecture-expert` | Agent 架构设计、ReAct、Planner、多 Agent 编排 | ✅ |
| `agent-rag-expert` | RAG 系统设计、向量数据库、检索优化 | ✅ |
| `agent-memory-expert` | 持久化记忆、agentmemory 集成、记忆架构 | ✅ |
| `agent-skill-engineer` | Skill 编写规范、经验蒸馏、测试方法 | ✅ |
| `agent-observability-expert` | Agent 可观测性、调试、性能监控 | ✅ |

### 🔧 全栈专家技能 (Fullstack Expert Skills)

| Skill | 描述 | 状态 |
|-------|------|------|
| `go-deep-expert` | Go 源码级深入：GMP/GC/网络/内存 | ✅ |
| `mysql-expert` | MySQL InnoDB 内核：事务/锁/索引/调优 | ✅ |
| `redis-expert` | Redis 源码级：数据结构/持久化/集群 | ✅ |
| `elasticsearch-expert` | ES 底层：倒排索引/Routing/查询优化 | ✅ |

### 📈 成长专家技能 (Growth Expert Skills)

| Skill | 描述 | 状态 |
|-------|------|------|
| `tech-leadership-expert` | 技术领导力：决策/架构/影响力 | ✅ |
| `ad-business-strategy-expert` | 广告业务战略：ROI/LTV/增长模型 | ✅ |
| `team-management-expert` | 团队管理：招聘/绩效/协作 | ✅ |

## 使用方法

```bash
# 加载单个 skill
cd skills/ad-bidding-expert
cat SKILL.md

# 批量加载
find skills -name "SKILL.md" | xargs cat
```

## 创建新 Skill

1. 在对应目录下创建 `SKILL.md`
2. 引用 `knowledge/` 中的相关文档
3. 添加使用示例和最佳实践
4. 更新本 README 的表格
