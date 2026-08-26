# LLM Wiki 知识库升级总结

## 升级内容

### v1.0 → v1.1 (2026-08-24)

#### 新增功能

| 类别 | 新增内容 | 数量 |
|------|----------|------|
| **平台层** | TikTok/Meta 约束规则 | +6 |
| **平台层** | TikTok/Meta 工作流 | +2 |
| **业务层** | 保持原有 12 条 | - |
| **经验层** | 案例研究（电商/游戏/B2B） | +3 |
| **经验层** | 错误模式扩展 | +5 |
| **动态层** | 性能基准数据 | +3 |
| **文档** | 使用指南 | +1 |

#### 最终统计

```
总计: 51 条知识

├── 平台层 (19 条)
│   ├── TikTok: 9 条
│   │   ├── hierarchy: 3 (Campaign/AdGroup/Ad)
│   │   ├── constraints: 4 (目标限制/预算限制/API限制)
│   │   └── workflows: 2 (Campaign创建/AdGroup创建)
│   ├── Meta: 8 条
│   │   ├── hierarchy: 3 (Campaign/AdSet/Ad)
│   │   ├── constraints: 3 (目标限制/素材限制/特殊广告类别)
│   │   └── workflows: 2 (Campaign创建/Ad创建)
│   ├── Google: 1 条
│   └── DV360: 1 条
│
├── 业务层 (12 条)
│   ├── strategy: 3 (电商/游戏/App)
│   ├── bidding: 3 (成本效率/目标ROAS/成本上限)
│   ├── targeting: 3 (兴趣/相似受众/再营销)
│   └── creative: 3 (视频/图片/最佳实践)
│
├── 经验层 (17 条)
│   ├── best_practices: 3 (结构/预算/素材)
│   ├── case_studies: 3 (电商ROAS/游戏安装/B2B线索)
│   ├── error_patterns: 8 (含解决方案)
│   └── tips: 3 (命名/学习期/受众重叠)
│
└── 动态层 (3 条)
    └── performance: 3 (TikTok/Meta/Google 基准)
```

## 关键成果

### 1. 完整的层级约束体系

**TikTok:**
- Campaign objective → AdGroup promotion_type 映射
- Campaign budget_mode → AdGroup budget 约束
- API v1.3 限制（UPGRADED_SMART_PLUS 不支持）

**Meta:**
- Campaign objective → AdSet optimization_goal 映射
- Special Ad Categories 定向限制
- Ad 素材类型约束

### 2. 实战案例库

| 案例 | 平台 | 业务类型 | 关键结果 |
|------|------|----------|----------|
| 电商 ROAS 优化 | Meta | ecommerce | ROAS 2.5 → 4.8 (+92%) |
| 游戏 App 安装规模化 | TikTok | gaming | CPI 降低 40% |
| B2B 线索收集 | Google | b2b | CPL $50 → $32.5 (-35%) |

### 3. 错误预防系统

8 个已知错误模式及解决方案：
- INVALID_PARAMETER（Meta）
- BUDGET_TOO_LOW（TikTok）
- API_NOT_SUPPORTED（TikTok v1.3）
- INVALID_TARGETING（Meta）
- INSUFFICIENT_BALANCE（全平台）
- PIXEL_NOT_FOUND（Meta）
- CREATIVE_REJECTED（全平台）
- NOT_FOUND（Google）

### 4. 性能基准数据

各平台 CTR/CPC/CPM/CVR 基准范围，用于：
- 效果评估
- 预算规划
- 目标设定

## 使用方式

### CLI 查询

```bash
# 统计
python3 tools/wiki_query.py --action stats

# 层级查询
python3 tools/wiki_query.py --platform tiktok --action hierarchy --level campaign

# 业务策略
python3 tools/wiki_query.py --action strategy --business-type ecommerce

# 错误解决
python3 tools/wiki_query.py --action errors --query "BUDGET_TOO_LOW"

# 案例研究
python3 tools/wiki_query.py --action cases --business-type ecommerce
```

### Python API

```python
from knowledge_base import get_wiki_kb

kb = get_wiki_kb('knowledge_base')

# 搜索
results = kb.search("campaign objective")

# 参数建议
suggestions = kb.get_parameter_suggestions("tiktok", "campaign", {})

# 流程验证
validation = kb.validate_creation_flow("tiktok", {"campaign": {...}})

# 获取工作流
workflow = kb.get_api_workflow("tiktok")
```

## 文件结构

```
agents/ad_agent/knowledge_base/
├── __init__.py                    # 核心类（1100+ 行）
├── ARCHITECTURE.md                # 架构文档
├── USAGE_GUIDE.md                 # 使用指南
├── init_*.py                      # 初始化脚本
├── extend_*.py                    # 扩展脚本
├── add_*.py                       # 添加脚本
│
├── tiktok/                        # TikTok 知识 (9 条)
│   ├── hierarchy.json
│   ├── constraints.json
│   └── workflows.json
│
├── meta/                          # Meta 知识 (8 条)
│   ├── hierarchy.json
│   ├── constraints.json
│   └── workflows.json
│
├── google/                        # Google 知识 (1 条)
│   └── hierarchy.json
│
├── dv360/                         # DV360 知识 (1 条)
│   └── hierarchy.json
│
├── business/                      # 业务知识 (12 条)
│   ├── strategy.json
│   ├── bidding.json
│   ├── targeting.json
│   └── creative.json
│
├── expertise/                     # 经验知识 (17 条)
│   ├── best_practices.json
│   ├── case_studies.json
│   ├── error_patterns.json
│   └── tips.json
│
└── dynamic/                       # 动态知识 (3 条)
    └── performance.json
```

## 后续计划

- [ ] 填充 Google Ads 完整知识库
- [ ] 填充 DV360 完整知识库
- [ ] 添加更多业务策略（教育/金融/旅游等）
- [ ] 实现自动学习机制（从实际使用收集数据）
- [ ] 添加 API 变更日志追踪
- [ ] 实现知识版本管理

## 技术栈

- Python 3.9+
- JSON 存储
- 类型注解
- 抽象基类
- 数据类
