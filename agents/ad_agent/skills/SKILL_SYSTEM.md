# ad-agent Skills 系统架构

## 设计原则

1. **Skill 独立** - 每个渠道有独立的 SKILL.md 定义 tools
2. **Tool 注册** - 统一的 tool registry 支持跨渠道调度
3. **跨渠道编排** - 支持多平台 Campaign 统一管理
4. **专家级能力** - 每个 Skill 包含该渠道的专家知识

## Skill 目录结构

```
skills/
├── SKILL_SYSTEM.md        # 本文件：系统架构说明
├── meta/                  # Meta Marketing API Skill
│   ├── SKILL.md           # Skill 定义（tools + 专家知识）
│   ├── tools/             # Tool 实现
│   │   ├── campaign.py
│   │   ├── adset.py
│   │   ├── creative.py
│   │   └── report.py
│   └── expert/            # 专家知识
│       ├── bidding_strategies.md
│       └── targeting_guide.md
├── tiktok/                # TikTok Ads Skill
│   ├── SKILL.md
│   ├── tools/
│   └── expert/
├── google-ads/            # Google Ads Skill
│   ├── SKILL.md
│   ├── tools/
│   └── expert/
├── dv360/                 # DV360 Skill
│   ├── SKILL.md
│   ├── tools/
│   └── expert/
└── cross-channel/         # 跨渠道 Skill
    ├── SKILL.md
    └── tools/
        ├── campaign_manager.py
        └── budget_optimizer.py
```

## Skill 定义格式

每个 Skill 的 SKILL.md 包含：

```yaml
skill:
  name: meta-marketing-api
  version: "1.0"
  description: "Meta Marketing API 专家 Skill"
  platform: meta
  author: "Ryan"
  
tools:
  - name: meta_create_campaign
    description: "创建广告系列"
    params: [...]
    expert_tips: "..."
    
  - name: meta_optimize_bidding
    description: "智能出价优化"
    params: [...]
    expert_tips: "..."
    
skills:
  - name: meta_bidding_expert
    description: "出价策略专家"
    strategies: [...]
```

## 跨渠道 Campaign 管理

通过 `cross-channel` skill 提供：

1. **Campaign 总览** - 统一查看各平台 Campaign 状态
2. **预算分配** - 跨平台预算智能分配
3. **性能对比** - 对比各平台 ROI/CPA
4. **批量操作** - 一键启停多个平台 Campaign

## 扩展新渠道

只需三步：

1. 创建 `skills/channels/{channel}/SKILL.md`
2. 实现同目录下的 `tools.py`（导出 `create_skill(api_client=None)`）
3. 让 Runtime 自动发现；无需修改核心路由，工具仍需通过统一 Registry 和安全门禁
