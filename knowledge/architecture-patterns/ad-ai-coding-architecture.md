# ad-ai-coding Skills 架构分析与通用化方案

**日期**: 2025-06-05
**标签**: #agent-架构 #skill工程

## 现状分析

### 现有 Skills 关系图

```text
                    ┌──────────────────┐
                    │  ad-knowledge-   │
                    │     query        │
                    │  (证据查询引擎)   │
                    └────────┬─────────┘
                             │ 被所有 Skill 消费
        ┌────────────────────┼────────────────────┐
        │                    │                    │
┌───────▼───────┐  ┌────────▼────────┐  ┌────────▼──────────┐
│  prd-review   │  │    ad-dev       │  │  ad-test-case     │
│  (PRD评审)    │  │  (TD+开发计划)   │  │  (测试用例)        │
└───────┬───────┘  └────────┬────────┘  └────────┬──────────┘
        │                   │                    │
        └───────────────────┼────────────────────┘
                            │
                    ┌───────▼───────┐
                    │ ad-test-auto  │
                    │  (自动化计划)  │
                    └───────────────┘
```

### 核心发现

**1. 广告领域特有内容（必须抽象掉的）**
- `docs/01-business-dap/scenario_cards.json` — 广告场景卡索引
- DAP/ADP/SC/MMP 等业务缩写
- Provider/API 映射（Google Ads, Meta, TikTok 等）
- Confluence PRD 拉取
- Confluence Token 认证
- 广告对象关系（Campaign → Ad Group → Ad）

**2. 通用流程模式（应该保留的）**
- PRD 评审流程：确认有效性 → 抽取变更集 → 证据查询 → 评审 → 输出报告
- 开发交付流程：PRD → TD → 开发计划 → Codex handoff
- 测试设计流程：PRD/review → 覆盖矩阵 → 场景生命周期矩阵 → case
- 质量闭环：查询失败 → 记录学习事件 → 补 benchmark case

**3. 通用基础设施（应该抽象的）**
- 证据查询 → `query_evidence.py`（已存在于 business-delivery）
- 场景卡系统 → `discover_scenarios.py`
- Profile 扩展机制 → `init_profile.py`
- 学习事件记录 → `record_learning_event.py`
- Benchmark 回归 → `run_query_benchmark.py`

## 通用化方案设计

### 三层架构

```text
┌─────────────────────────────────────────────────┐
│              Layer 1: 核心引擎                    │
│           (完全通用，不依赖任何业务)               │
│                                                 │
│  • evidence_query.py   — 通用证据查询           │
│  • review_engine.py    — PRD评审引擎            │
│  • td_engine.py        — TD生成引擎             │
│  • test_engine.py      — 测试用例引擎           │
│  • profile_registry.py — 业务Profile管理        │
│  • benchmark.py        — 回归测试               │
└─────────────────────────────────────────────────┘
                      ▲
                      │ Profile 配置
┌─────────────────────────────────────────────────┐
│              Layer 2: 业务 Profile               │
│         (定义业务域，不涉及实现细节)              │
│                                                 │
│  profile.json:                                  │
│  {                                             │
│    "business_domain": "my-service",           │
│    "repositories": [...],                      │
│    "domain_terms": [...],                      │
│    "evidence_sources": ["code", "schema"],     │
│    "review_rules": [...],                      │
│    "scenario_cards": "path/to/scenarios.json"  │
│  }                                             │
└─────────────────────────────────────────────────┘
                      ▲
                      │ 实现特定
┌─────────────────────────────────────────────────┐
│              Layer 3: 业务扩展点                 │
│         (Hook 函数，实现业务差异)               │
│                                                 │
│  hooks/:                                        │
│    • fetch_prd.py      — 如何获取 PRD           │
│    • map_terms.py      — 业务术语映射           │
│    • validate.py       — 业务校验规则           │
│    • generate_graph.py — 业务专属图谱生成        │
└─────────────────────────────────────────────────┘
```

### 扩展点设计（Hook 系统）

```python
# hooks/fetch_prd.py — 如何获取 PRD（Confluence/Wiki/本地文件/URL）
# hooks/map_terms.py — 业务术语 → 代码关键词映射
# hooks/validate.py — 业务专属校验规则
# hooks/post_review.py — 评审后处理
# hooks/generate_graph.py — 业务专属知识图谱构建
# hooks/test_dimensions.py — 业务专属测试维度
```

## 新 Skill 名称建议

### 选项 A: `generic-delivery`
- 通用交付链
- 强调端到端交付

### 选项 B: `ad-kit-core`
- 广告知识库核心
- 表明从 ad-ai-coding 衍生

### 选项 C: `biz-delivery`
- 业务交付框架
- 简洁，暗示业务可配置

### 推荐: `biz-delivery`

## 迁移策略

### Phase 1: 提取核心
1. 从 business-delivery 提取通用引擎
2. 把广告特有内容移到 profile + hooks
3. 保留 ad-knowledge-query 作为证据查询后端

### Phase 2: 新业务接入测试
1. 用 biz-delivery + profile 接入一个新业务域
2. 验证流程是否通顺
3. 补充 hooks 实现

### Phase 3: 清理 ad-ai-coding
1. 新业务直接使用 biz-delivery
2. 保留 ad-ai-coding 作为广告专用版本
3. 后续逐步迁移广告业务到 biz-delivery

## 仓库结构设计

```
biz-delivery/                    # 新仓库
├── SKILL.md                     # 入口
├── scripts/
│   ├── query_evidence.py        # 通用证据查询
│   ├── review_engine.py         # PRD评审引擎
│   ├── td_engine.py            # TD生成引擎
│   ├── test_engine.py          # 测试用例引擎
│   ├── profile_registry.py     # 业务Profile管理
│   └── benchmark.py            # 回归测试
├── profiles/
│   ├── default.json            # 默认配置
│   └── index.json              # 业务注册表
├── hooks/
│   ├── fetch_prd.py            # 扩展点：获取PRD
│   ├── map_terms.py            # 扩展点：术语映射
│   ├── validate.py             # 扩展点：校验规则
│   └── test_dimensions.py      # 扩展点：测试维度
├── references/
│   ├── profile_schema.json     # Profile schema
│   ├── extension_guide.md      # 扩展指南
│   ├── input_contract.md       # 输入契约
│   └── output_contract.md      # 输出契约
└── templates/
    ├── review_report.md.j2     # 评审报告模板
    ├── td.md.j2               # TD模板
    └── test_cases.md.j2       # 测试用例模板
```

## 新业务接入流程

```bash
# 1. 初始化业务 Profile
python3 scripts/init_profile.py \
  --business-domain "my-service" \
  --repository "/path/to/repo" \
  --output profiles/my-service.json

# 2. 实现业务 Hook（按需）
# 只需要实现 fetch_prd.py 和 validate.py 即可开始

# 3. 开始使用
python3 scripts/run_pipeline.py \
  --profile "profiles/my-service.json" \
  --text "<PRD内容>" \
  --output-dir delivery/my-feature
```
