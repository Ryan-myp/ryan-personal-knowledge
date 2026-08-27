# Skills 实现指南

> 状态说明：本文保留为设计参考。当前唯一的 Skill contract/loader 位于 `runtime/skill.py`；可执行实现以 `capabilities/`、`core/` 和 `runtime/` 源码为准。`SKILL.md` 中的工具说明不等于已注册的可执行工具。当前四个平台 Capability 共 72 个工具，跨渠道编排由 Runtime + `core/cross_channel.py` 提供。

## 架构分层

```
skills/
├── SKILL.md              # 工具定义（配置层）- 已完成 ✅
├── loader.py             # Skill 加载器 - 已完成 ✅
├── registry.py           # 工具注册器 - 已完成 ✅
├── meta/
│   ├── SKILL.md          # Meta 工具定义（专家说明）
│   ├── tools/            # Meta 工具实现 ⏳
│   │   ├── campaign.py   # meta_create_campaign 等
│   │   ├── adset.py      # meta_create_adset 等
│   │   └── report.py     # meta_get_campaign_report 等
│   └── expert/           # Meta 专家知识
├── tiktok/
│   ├── SKILL.md          # TikTok 工具定义（专家说明）
│   ├── tools/            # TikTok 工具实现 ⏳
│   └── expert/
├── google-ads/
│   ├── SKILL.md          # Google Ads 工具定义（专家说明）
│   ├── tools/            # Google Ads 工具实现 ⏳
│   └── expert/
├── dv360/
│   ├── SKILL.md          # DV360 工具定义（专家说明）
│   ├── tools/            # DV360 工具实现 ⏳
│   └── expert/
└── cross-channel/
    ├── SKILL.md          # 跨渠道设计契约（未注册为独立工具）
    ├── tools/            # 跨渠道工具实现 ⏳
    └── expert/
```

## 当前状态

| 层级 | 状态 | 说明 |
|------|------|------|
| SKILL.md (定义层) | ✅ | 专家知识和设计契约；不作为 Runtime 工具注册源 |
| loader.py (加载层) | ✅ 完成 | 自动解析 SKILL.md |
| registry.py (注册层) | ✅ 完成 | 自动注册到 ToolRegistry |
| tool_selector.py (选择层) | ✅ 完成 | 动态选择相关工具 |
| context_optimizer.py (优化层) | ✅ 完成 | 构建精简 LLM 上下文 |
| capabilities/ (实现层) | ✅ | 当前 Runtime 的实际 Handler/API Client 入口 |

## 如何补充实现

### 示例：实现 meta_create_campaign

创建 `skills/meta/tools/campaign.py`：

```python
"""
skills/meta/tools/campaign.py - Meta Campaign 工具实现
"""

import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)


class MetaCampaignTools:
    """Meta Campaign 相关工具实现"""
    
    def __init__(self, api_client):
        self.client = api_client
    
    def create_campaign(self, account_id: str, campaign: Dict[str, Any]) -> str:
        """
        创建 Meta Campaign
        
        Args:
            account_id: 广告账户 ID
            campaign: campaign 参数
            
        Returns:
            campaign_id: 创建的广告系列 ID
        """
        # 调用已有的 Meta API 客户端
        campaign_id = self.client.create_campaign(account_id, campaign)
        logger.info(f"Created Meta campaign: {campaign_id}")
        return campaign_id
    
    def update_campaign(self, account_id: str, campaign_id: str, updates: Dict[str, Any]) -> bool:
        """更新 Meta Campaign"""
        # 实现...
        pass
    
    def pause_campaign(self, account_id: str, campaign_id: str) -> bool:
        """暂停 Meta Campaign"""
        # 实现...
        pass
```

### 注册工具

在 `skills/meta/SKILL.md` 中已经定义了工具，只需：
1. 实现工具逻辑
2. 在 `capabilities/meta_capability.py` 中调用

## 动态工具选择原理

### 工作流程

```
用户输入: "查询 Google Campaign 报表"
    │
    ▼
IntentParser 解析
    │
    ├─ intent_type: "get_report"
    ├─ platforms: ["google"]
    └─ objective: None
    │
    ▼
DynamicToolSelector 筛选
    │
    ├─ 获取 Google 平台所有工具 (20 个)
    ├─ 根据 intent_type="get_report" 筛选
    │   ├─ 关键词: ["report", "get_", "list_", "query"]
    │   └─ 匹配工具:
    │       ├─ google_get_campaign_report ✅
    │       ├─ google_get_keyword_report ✅
    │       └─ ... (共 7 个)
    │
    ├─ 获取专家知识
    │   └─ bidding_strategies.md, report_metrics.md
    │
    ▼
ContextOptimizer 构建 Prompt
    │
    ├─ system prompt 只包含 7 个工具
    ├─ 注入专家知识摘要
    └─ 控制总长度 < 2000 tokens
    │
    ▼
LLM 收到精简上下文
    │
    └─ 调用相关工具执行
```

### 效果对比

| 方案 | 工具数 | Token 消耗 | 响应速度 |
|------|--------|-----------|----------|
| 原始方案（全部工具） | 87 | ~8000 tokens | 慢 |
| 优化方案（动态选择） | 5-12 | ~1000 tokens | 快 5x |

## 扩展新渠道（3 步）

### 步骤 1：创建 SKILL.md

```yaml
# skills/new-platform/SKILL.md
---
skill:
  name: new-platform-api
  version: "1.0"
  description: "新平台 API 专家 Skill"
  platform: new-platform
---

# 新平台 API 专家 Skill

## 工具列表

#### new_platform_create_campaign
- **描述**: 创建广告系列
- **参数**: campaign_name, budget

#### new_platform_get_report
- **描述**: 获取报表
- **参数**: campaign_id, date_range
```

### 步骤 2：实现工具代码

```python
# skills/new-platform/tools/campaign.py
class NewPlatformCampaignTools:
    def create_campaign(self, ...):
        # 调用新平台 API
        pass
```

### 步骤 3：自动生效

```bash
# 无需修改其他代码，自动加载
python agents/ad_agent/api_server.py
```

## 当前推荐的可执行扩展契约

对于不需要修改内置 Capability 的新增功能，使用以下目录结构：

```text
skills/channels/<skill-name>/
├── SKILL.md
└── tools.py                 # 或 tools/__init__.py
```

`tools.py` 导出 `create_skill(api_client=None)`，返回实现 Core `Skill` 接口的对象：

```python
class MySkill(Skill):
    name = "my-skill"
    platform = "meta"  # 也可以是新的、受控配置的平台名
    intent_to_tools = {"my_intent": {"meta": ["my_tool"]}}

    def get_tools(self):
        return [my_tool_definition]

    def get_tool_handler(self, tool_name):
        return my_handler if tool_name == "my_tool" else None

def create_skill(api_client=None):
    return MySkill()
```

Runtime 自动加载 plugin 后，工具仍由统一 Registry 执行；不能因为在 `SKILL.md`
中列出工具，就绕过 Handler、schema、白名单或 dry-run/live 安全门禁。

服务启动时会自动：
1. 扫描 `skills/` 目录下所有 SKILL.md
2. 解析工具定义
3. 注册到 ToolRegistry
4. 参与动态工具选择
