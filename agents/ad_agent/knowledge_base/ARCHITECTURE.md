# LLM Wiki 通用知识库系统架构

## 概述

LLM Wiki 是一个**通用型广告平台知识库系统**，支持多层级知识管理：
- **平台层**：层级结构、约束规则、工作流
- **业务层**：业务策略、出价策略、定向策略、素材指南
- **经验层**：最佳实践、案例研究、错误模式、实用技巧
- **动态层**：API 变更日志、性能数据

解决广告创建中「上层参数约束下层选项」的问题，同时支持业务策略推荐和错误预防。

## 架构设计

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      LLM Wiki 通用知识库系统                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                        知识类型体系 (KnowledgeType)                   │    │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ │    │
│  │  │ HIERARCHY│ │CONSTRAINT│ │ PARAMETER│ │ WORKFLOW │ │ STRATEGY │ │    │
│  │  │  层级结构 │ │  约束规则 │ │  参数定义 │ │  工作流  │ │ 业务策略 │ │    │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘ │    │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ │    │
│  │  │BIDDING_  │ │TARGETING_│ │CREATIVE_ │ │BEST_     │ │CASE_     │ │    │
│  │  │STRATEGY  │ │STRATEGY  │ │GUIDE     │ │PRACTICE  │ │STUDY     │ │    │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘ │    │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐              │    │
│  │  │ERROR_    │ │ TIP      │ │API_      │ │PERF_     │              │    │
│  │  │PATTERN   │ │          │ │CHANGE    │ │DATA      │              │    │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘              │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                        知识库存储结构                                 │    │
│  │                                                                      │    │
│  │  knowledge_base/                                                     │    │
│  │  ├── meta/                 # Meta 平台知识                           │    │
│  │  │   ├── hierarchy.json     # Campaign/AdSet/Ad 层级参数              │    │
│  │  │   ├── constraints.json  # 层级间约束规则                         │    │
│  │  │   └── workflows.json    # API 工作流                             │    │
│  │  ├── tiktok/               # TikTok 平台知识                         │    │
│  │  │   ├── hierarchy.json     # 3 entries                              │    │
│  │  │   ├── constraints.json  # 1 entry                                │    │
│  │  │   └── workflows.json    # 1 entry                                │    │
│  │  ├── google/               # Google Ads 平台知识                     │    │
│  │  ├── dv360/                # DV360 平台知识                          │    │
│  │  ├── business/             # 业务层知识                              │    │
│  │  │   ├── strategy.json      # 业务策略（电商/游戏/App）              │    │
│  │  │   ├── bidding.json       # 出价策略                               │    │
│  │  │   ├── targeting.json     # 定向策略                               │    │
│  │  │   └── creative.json      # 素材指南                               │    │
│  │  ├── expertise/            # 经验层知识                              │    │
│  │  │   ├── best_practices.json # 最佳实践（3 entries）                 │    │
│  │  │   ├── case_studies.json  # 案例研究                               │    │
│  │  │   ├── error_patterns.json # 错误模式（3 entries）                 │    │
│  │  │   └── tips.json          # 实用技巧（3 entries）                  │    │
│  │  └── dynamic/              # 动态知识                                │    │
│  │      ├── api_changes.json   # API 变更日志                          │    │
│  │      └── performance.json   # 性能数据                               │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                        核心类层次结构                                 │    │
│  │                                                                      │    │
│  │  BaseKnowledgeBase (ABC)                                            │    │
│  │  ├── PlatformHierarchyKB    # 平台层级结构                           │    │
│  │  ├── PlatformConstraintKB   # 平台约束规则                           │    │
│  │  ├── PlatformWorkflowKB     # 平台工作流                             │    │
│  │  ├── BusinessStrategyKB     # 业务策略                               │    │
│  │  ├── BiddingStrategyKB      # 出价策略                               │    │
│  │  ├── TargetingStrategyKB    # 定向策略                               │    │
│  │  ├── CreativeGuideKB        # 素材指南                               │    │
│  │  ├── BestPracticeKB         # 最佳实践                               │    │
│  │  ├── CaseStudyKB            # 案例研究                               │    │
│  │  ├── ErrorPatternKB         # 错误模式                               │    │
│  │  ├── TipKB                  # 实用技巧                               │    │
│  │  ├── APIChangeKB            # API 变更                               │    │
│  │  └── PerformanceDataKB      # 性能数据                               │    │
│  │                                                                      │    │
│  │  LLMWikiKnowledgeBase (主控制器)                                      │    │
│  │  ├── search()            # 跨知识库搜索                              │    │
│  │  ├── get_parameter_suggestions() # 参数建议                          │    │
│  │  ├── validate_creation_flow()    # 流程验证                          │    │
│  │  └── get_api_workflow()    # 获取工作流                              │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

## 知识类型详解

### 平台层知识（Platform Layer）

| 类型 | 描述 | 示例 |
|------|------|------|
| HIERARCHY | 层级结构定义 | Campaign/AdGroup/Ad 的参数列表 |
| CONSTRAINT | 参数约束规则 | Campaign objective 限制 AdGroup promotion_type |
| PARAMETER | 参数定义 | 参数名、类型、是否必需、合法值 |
| WORKFLOW | 操作工作流 | 创建 Campaign → AdGroup → Ad 的完整流程 |

### 业务层知识（Business Layer）

| 类型 | 描述 | 示例 |
|------|------|------|
| BUSINESS_STRATEGY | 业务策略 | 电商/游戏/App 的通用投放策略 |
| BIDDING_STRATEGY | 出价策略 | 目标 ROAS、成本上限、最低成本 |
| TARGETING_STRATEGY | 定向策略 | 兴趣定向、相似受众、再营销 |
| CREATIVE_GUIDE | 素材指南 | 视频规格、图片规格、创作技巧 |

### 经验层知识（Expertise Layer）

| 类型 | 描述 | 示例 |
|------|------|------|
| BEST_PRACTICE | 最佳实践 | 账户结构、预算分配、素材测试 |
| CASE_STUDY | 案例研究 | 成功/失败案例分析 |
| ERROR_PATTERN | 错误模式 | API 错误码及解决方案 |
| TIP | 实用技巧 | 命名规范、学习期优化、受众重叠检查 |

### 动态知识（Dynamic Layer）

| 类型 | 描述 | 示例 |
|------|------|------|
| API_CHANGE | API 变更日志 | 新版本 API 字段变更 |
| PERFORMANCE_DATA | 性能数据 | 各平台 CTR/CVR 基准数据 |

## 核心类设计

### KnowledgeEntry（知识条目）

```python
@dataclass
class KnowledgeEntry:
    entry_id: str                          # 唯一标识
    knowledge_type: KnowledgeType          # 知识类型
    platform: str                          # 平台 (tiktok/meta/google/dv360/all)
    content: Dict[str, Any]                # 内容
    source: KnowledgeSource                # 来源
    source_ref: str                        # 来源引用
    created_at: str                        # 创建时间
    updated_at: str                        # 更新时间
    tags: List[str]                        # 标签
    metadata: Dict[str, Any]              # 元数据
    confidence: float = 1.0               # 置信度 0-1
    usage_count: int = 0                  # 使用次数
```

### ParameterDefinition（参数定义）

```python
@dataclass
class ParameterDefinition:
    name: str                              # 参数名
    type: str                              # 类型
    required: bool                         # 是否必需
    description: str                       # 描述
    valid_values: List[str]               # 合法值
    constraints: List[Dict]               # 约束规则
    depends_on: Dict[str, str]            # 依赖关系
```

## 使用方式

### 1. 查询层级结构

```bash
python3 tools/wiki_query.py \
  --platform tiktok \
  --action hierarchy \
  --level campaign
```

### 2. 查询约束规则

```bash
python3 tools/wiki_query.py \
  --platform tiktok \
  --action constraints \
  --source-level campaign \
  --target-level ad_group
```

### 3. 获取参数建议

```bash
python3 tools/wiki_query.py \
  --platform tiktok \
  --action suggest \
  --level campaign \
  --params '{"objective_type": "TRAFFIC"}'
```

### 4. 获取业务策略

```bash
python3 tools/wiki_query.py \
  --action strategy \
  --business-type ecommerce
```

### 5. 获取最佳实践

```bash
python3 tools/wiki_query.py \
  --action best_practices \
  --limit 5
```

### 6. 获取错误解决方案

```bash
python3 tools/wiki_query.py \
  --action errors \
  --query "BUDGET_TOO_LOW"
```

### 7. Python API

```python
from knowledge_base import get_wiki_kb

kb = get_wiki_kb()

# 搜索知识
results = kb.search("campaign objective")

# 获取参数建议
suggestions = kb.get_parameter_suggestions(
    "tiktok", "campaign",
    {"objective_type": "TRAFFIC"}
)

# 验证创建流程
validation = kb.validate_creation_flow(
    "tiktok",
    {
        "campaign": {...},
        "ad_group": {...},
        "ad": {...}
    }
)

# 获取业务策略
strategies = kb.business_kbs['strategy']
ecommerce = strategies.get_by_business_type('ecommerce')

# 获取错误解决方案
solutions = kb.get_error_solutions("BUDGET_TOO_LOW", "tiktok")
```

## 与 Agent 集成

### 1. 创建前验证

```python
async def validate_and_create(platform: str, flow: Dict):
    tool = WikiQueryTool()
    
    # 1. 验证流程
    validation = tool.validate_creation_flow(platform, flow)
    if not validation['valid']:
        return ToolResult(
            success=False,
            error="流程验证失败",
            suggestions=validation['suggestions']
        )
    
    # 2. 执行创建
    result = await create_with_platform(platform, flow)
    return result
```

### 2. 智能参数建议

```python
async def get_smart_suggestions(platform: str, level: str, existing_params: Dict):
    tool = WikiQueryTool()
    
    # 从知识库获取建议
    suggestions = tool.get_parameter_suggestions(platform, level, existing_params)
    
    # 结合业务策略优化
    business_type = existing_params.get('business_type', 'general')
    strategy = tool.get_business_strategy(business_type, platform)
    
    # 合并建议
    suggestions['strategy'] = strategy
    
    return suggestions
```

### 3. 错误预防

```python
async def prevent_errors(platform: str, params: Dict):
    tool = WikiQueryTool()
    
    # 检查已知错误模式
    errors = kb.expertise_kbs['error_patterns']
    for entry in errors.entries.values():
        if entry.platform == platform or entry.platform == 'all':
            # 检查是否可能触发该错误
            if check_error_risk(entry.content, params):
                return {
                    'warning': entry.content['error_message'],
                    'solution': entry.content['solutions']
                }
    
    return None
```

## 知识库统计

| 类别 | 条目数 | 说明 |
|------|--------|------|
| TikTok 平台层 | 5 | hierarchy(3) + constraints(1) + workflows(1) |
| Meta 平台层 | 5 | hierarchy(3) + constraints(1) + workflows(1) |
| Google 平台层 | 1 | hierarchy(1) - 简化版 |
| DV360 平台层 | 0 | 待填充 |
| 业务策略 | 3 | ecommerce/gaming/app |
| 出价策略 | 3 | cost_efficiency/target_roas/cost_cap |
| 定向策略 | 3 | interest/lookalike/retargeting |
| 素材指南 | 3 | video/image/best_practices |
| 最佳实践 | 3 | structure/budget/creative |
| 错误模式 | 3 | invalid_objective/budget_too_low/api_limitation |
| 实用技巧 | 3 | naming/learning-phase/audience-overlap |
| **总计** | **32** | 持续增长中 |

## 扩展指南

### 添加新平台知识

1. 创建初始化脚本: `init_{platform}_kb.py`
2. 填充层级、约束、工作流数据
3. 运行脚本生成 JSON 文件

### 添加业务知识

1. 编辑 `init_business_kb.py`
2. 添加新的业务策略/出价策略/定向策略
3. 运行脚本更新知识库

### 添加经验知识

1. 编辑 `init_expertise_kb.py`
2. 添加最佳实践/错误模式/技巧
3. 运行脚本更新知识库

## 版本历史

- v1.0.0 (2026-08-24): 初始版本
  - 支持 4 平台（TikTok/Meta/Google/DV360）
  - 13 种知识类型
  - 32 条初始知识条目
  - CLI 查询工具
  - Python API
