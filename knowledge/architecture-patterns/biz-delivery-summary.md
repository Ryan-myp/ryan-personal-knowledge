# biz-delivery 能力总结

## 一句话描述

**通用业务交付框架** — 从 PRD 到测试用例的全链路自动化，业务差异通过 Profile + Hooks 配置，不修改核心引擎。

## 仓库

`https://github.com/Ryan-myp/biz-delivery`

## 核心能力

### 1. 知识提取引擎

把代码/文档变成结构化知识，4 层抽象：

```
代码/文档
    │
    ▼
┌─ 结构化抽象 ──────────────────────────┐
│ • AST — 语法结构（函数/类/方法）       │
│ • CFG — 控制流图（分支/循环/异常）     │
│ • DFG — 数据流分析（变量传播）         │
│ • SIG — 接口契约（签名/类型/装饰器）   │
│ • Flow — 业务流（入口→调用拓扑→数据落点）│
│ • Semantics — 语义层（功能描述/业务概念）│
└────────────────────────────────────────┘
    │
    ▼
┌─ 混合索引 ────────────────────────────┐
│ • BM25 — 关键词匹配                  │
│ • 向量 — 语义相似度                   │
│ • 图谱 — 关系查询                    │
│ • 元数据 — 语言/路径/时间            │
│ • 缓存 — TTL 缓存热点查询             │
└────────────────────────────────────────┘
```

**亮点**：
- Python AST 提取器（零依赖，标准库 ast）
- 业务流发现（从入口点 BFS 构建调用拓扑）
- 语义层提取（docstring/业务概念/设计模式）

### 2. 意图识别 + 智能路由

18 种意图识别，自动选择最佳查询路径：

| 意图 | 触发词 | 优先 scope |
|------|--------|-----------|
| create | 创建/新建/新增 | code |
| update | 修改/更新/变更 | code |
| query | 查询/查看/获取 | api_docs |
| sync | 同步/回流 | schema |
| debug | 调试/排障/错误 | code |
| compare | 对比/比较 | api_docs |
| callchain | 谁调用了/调用链 | callgraph |
| dataflow | 从哪来/数据来源 | dataflow |
| impact | 改了影响什么 | impact |

**亮点**：
- 18 种意图模式（中 + 英）
- 意图 → scope 权重映射
- 缓存命中时直接返回，不重复计算

### 3. RRF 多路融合查询

多路径并行查询，RRF 融合结果：

```
用户查询
    │
    ▼
意图路由器 → 选出 top 3 scopes
    │
    ▼
多路并行查询（每个 scope 一路）
    │
    ▼
RRF 融合（k=60，按命中排名加权）
    │
    ▼
按置信度排序 → 输出 top K
```

**亮点**：
- 借鉴 agentmemory 的 RRF 融合方案
- 多路并行，各查各的，最后融合
- 避免单路查询的覆盖盲区

### 4. 查询缓存

轻量文件缓存，提升重复查询性能：

```python
cache = QueryCache("/tmp/biz-delivery-cache")
cache.get(query, scopes)  # 命中返回缓存
cache.set(query, scopes, data)  # 缓存结果，TTL=1h
```

**亮点**：
- MD5 键值，避免路径过长
- TTL 自动过期清理
- 支持按关键词清除

## 架构：4 层分离

```
┌─ Layer 1: 知识提取引擎 ─────────────┐
│ 把代码/文档变成结构化知识            │
│ AST │ CFG │ DFG │ SIG │ Flow       │
└─────────────────────────────────────┘
                  │
┌─ Layer 2: 核心引擎 ────────────────┐
│ PRD评审 → TD → 开发计划 → 测试用例   │
│ query_evidence │ review │ td │ test │
└─────────────────────────────────────┘
                  ▲
┌─ Layer 3: 业务 Profile ────────────┐
│ 定义业务域：仓库/术语/证据源/规则    │
└─────────────────────────────────────┘
                  ▲
┌─ Layer 4: 业务 Hook ──────────────┐
│ fetch_prd.py │ validate.py ...     │
│ （实现业务差异，不修改引擎）         │
└─────────────────────────────────────┘
```

## 与 ad-ai-coding 的关系

| | ad-ai-coding | biz-delivery |
|---|---|---|
| 定位 | 广告专用 | 通用框架 |
| 广告术语 | 硬编码在脚本里 | 放在 Profile + Hooks |
| Provider映射 | 内置 | hooks/map_terms.py |
| Confluence PRD | 内置 | hooks/fetch_prd.py |
| 新业务接入 | 修改脚本 | 新增 Profile + Hooks |
| 知识提取 | grep/ripgrep | AST + CFG + DFG |

## 新业务接入流程

```bash
# 1. 初始化业务 Profile
python3 scripts/init_profile.py \
  --business-domain "my-service" \
  --repository "/path/to/repo" \
  --output profiles/my-service.json

# 2. 按需实现 Hooks
# 最少实现：hooks/fetch_prd.py
# 按需实现：hooks/validate.py

# 3. 跑端到端流水线
python3 scripts/run_pipeline.py \
  --profile "profiles/my-service.json" \
  --text "<PRD内容>" \
  --output-dir "delivery/my-feature"
```

## 与现有能力的关系

| 能力 | 来源 | 用途 |
|------|------|------|
| PRD评审 | ad-ai-coding | 评审需求完整性 |
| TD生成 | ad-ai-coding | 技术方案生成 |
| 测试用例 | ad-ai-coding | QA case 设计 |
| **知识提取** | **biz-delivery** | **把代码变成知识** |
| **意图路由** | **biz-delivery** | **自动选最佳查询路径** |
| **RRF融合** | **biz-delivery** | **多路查询结果融合** |
| agentmemory | 外部集成 | 语义搜索 + 跨会话记忆 |

**互补关系**：
- ad-ai-coding = 业务逻辑（怎么审、怎么生成）
- biz-delivery = 基础设施（怎么查、怎么提取知识）
- agentmemory = 增强层（语义记忆 + 跨会话关联）
