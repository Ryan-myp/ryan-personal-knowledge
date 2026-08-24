# LLM Wiki 知识库使用指南

## 快速开始

### 1. 命令行查询

```bash
# 查看知识库统计
python3 tools/wiki_query.py --action stats

# 查询 TikTok Campaign 层级结构
python3 tools/wiki_query.py --platform tiktok --action hierarchy --level campaign

# 查询业务策略
python3 tools/wiki_query.py --action strategy --business-type ecommerce

# 获取最佳实践
python3 tools/wiki_query.py --action best_practices --limit 5

# 获取错误解决方案
python3 tools/wiki_query.py --action errors --query "BUDGET_TOO_LOW"

# 搜索知识
python3 tools/wiki_query.py --action search --query "campaign objective"
```

### 2. Python API

```python
from knowledge_base import get_wiki_kb

kb = get_wiki_kb('knowledge_base')

# 搜索知识
results = kb.search("campaign")
for r in results:
    print(f"{r.entry_id}: {r.content.get('description')}")

# 获取参数建议
suggestions = kb.get_parameter_suggestions(
    "tiktok", "campaign",
    {"objective_type": "TRAFFIC"}
)
print(f"必需参数: {[p['name'] for p in suggestions['required_params']]}")

# 验证创建流程
validation = kb.validate_creation_flow(
    "tiktok",
    {
        "campaign": {"objective_type": "TRAFFIC"},
        "ad_group": {"promotion_type": "WEBSITE"}
    }
)
if not validation['valid']:
    print(f"验证失败: {validation['errors']}")

# 获取 API 工作流
workflow = kb.get_api_workflow("tiktok")
for wf in workflow.get('workflows', []):
    print(f"{wf['type']}: {len(wf['steps'])} 步")
```

### 3. Agent 集成示例

```python
async def create_campaign_with_knowledge(platform: str, params: Dict):
    """使用知识库辅助创建广告"""
    kb = get_wiki_kb()
    
    # 1. 验证参数
    validation = kb.validate_creation_flow(platform, {"campaign": params})
    if not validation['valid']:
        return {
            'success': False,
            'errors': validation['errors'],
            'suggestions': validation.get('suggestions', [])
        }
    
    # 2. 获取业务策略建议
    strategy = kb.get_best_practices(platform, params.get('business_type'))
    
    # 3. 检查已知错误
    error_solution = kb.get_error_solutions(params.get('error_code'), platform)
    
    # 4. 执行创建
    result = await api_client.create_campaign(platform, params)
    
    return {
        'success': True,
        'result': result,
        'strategy_tips': strategy,
        'error_prevention': error_solution
    }
```

## 知识库结构

```
knowledge_base/
├── tiktok/           # TikTok 平台知识 (9 条)
│   ├── hierarchy.json    # 3 条: Campaign/AdGroup/Ad 层级
│   ├── constraints.json  # 4 条: 层级间约束规则
│   └── workflows.json    # 2 条: 创建流程
│
├── meta/             # Meta 平台知识 (8 条)
│   ├── hierarchy.json    # 3 条: Campaign/AdSet/Ad 层级
│   ├── constraints.json  # 3 条: 特殊广告类别约束等
│   └── workflows.json    # 2 条: 创建流程
│
├── google/           # Google Ads 简化版 (1 条)
├── dv360/            # DV360 简化版 (1 条)
│
├── business/         # 业务层知识 (12 条)
│   ├── strategy.json     # 3 条: 电商/游戏/App 策略
│   ├── bidding.json      # 3 条: 出价策略
│   ├── targeting.json    # 3 条: 定向策略
│   └── creative.json     # 3 条: 素材指南
│
├── expertise/        # 经验层知识 (17 条)
│   ├── best_practices.json  # 3 条: 最佳实践
│   ├── case_studies.json    # 3 条: 案例研究
│   ├── error_patterns.json  # 8 条: 错误模式
│   └── tips.json          # 3 条: 实用技巧
│
└── dynamic/          # 动态知识 (3 条)
    └── performance.json    # 3 条: 性能基准
```

## 使用场景

### 场景 1: 创建广告前的参数验证

```python
# 用户输入
params = {
    "platform": "tiktok",
    "campaign": {
        "objective_type": "APP_PROMOTION",
        "budget_mode": "BUDGET_MODE_INFINITE"
    },
    "ad_group": {
        "promotion_type": "APP_ANDROID"
    }
}

# 知识库验证
kb = get_wiki_kb()
validation = kb.validate_creation_flow("tiktok", params)

if not validation['valid']:
    print(f"❌ 验证失败: {validation['errors']}")
    print(f"💡 建议: {validation['suggestions']}")
else:
    print("✅ 参数验证通过")
```

### 场景 2: 获取业务策略建议

```python
# 用户询问电商投放策略
kb = get_wiki_kb()
strategies = kb.get_best_practices(platform="tiktok", business_type="ecommerce")

for s in strategies:
    print(f"【{s.get('title')}】")
    print(f"推荐: {s.get('recommendations')}")
    print()
```

### 场景 3: 错误预防

```python
# 创建前检查可能的错误
kb = get_wiki_kb()
errors = kb.expertise_kbs['error_patterns']

for entry in errors.entries.values():
    if entry.platform == platform or entry.platform == 'all':
        # 检查是否可能触发该错误
        if check_error_risk(entry.content, params):
            print(f"⚠️ 可能触发错误: {entry.content['error_message']}")
            print(f"💡 解决方案: {entry.content['solutions']}")
```

### 场景 4: 性能基准参考

```python
# 获取 TikTok 性能基准
perf_kb = kb.dynamic_kbs['performance']
for entry in perf_kb.entries.values():
    if entry.platform == "tiktok":
        benchmarks = entry.content['benchmarks']
        print(f"TikTok CTR 基准: {benchmarks['ctr']['video_ads']['avg']}%")
        print(f"TikTok CPC 范围: ${benchmarks['cpc']['app_installs']['min']}-${benchmarks['cpc']['app_installs']['max']}")
```

## 扩展知识库

### 添加新平台知识

1. 创建初始化脚本 `init_{platform}_kb.py`
2. 定义层级、约束、工作流知识条目
3. 运行脚本生成 JSON 文件

### 添加业务知识

编辑 `init_business_kb.py`，添加新的业务策略、出价策略、定向策略或素材指南。

### 添加经验知识

编辑 `init_expertise_kb.py`，添加最佳实践、案例研究、错误模式或实用技巧。

## 知识来源说明

| 来源 | 标识 | 说明 |
|------|------|------|
| 官方文档 | `official_docs` | 来自各平台官方 API 文档 |
| API 实测 | `api_test` | 通过实际 API 调用验证 |
| 专家经验 | `manual_expert` | 基于 Ryan 专家经验整理 |
| 历史数据 | `historical_data` | 基于历史投放数据分析 |

## 版本历史

- v1.0.0 (2026-08-24): 初始版本，33 条知识
- v1.1.0 (2026-08-24): 扩展至 51 条知识
  - 新增 TikTok/Meta 约束规则
  - 新增案例研究 3 条
  - 新增错误模式 5 条
  - 新增性能基准 3 条
