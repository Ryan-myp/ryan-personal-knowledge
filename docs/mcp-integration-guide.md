# MCP Server 集成指南

> **版本**: v1.0.0
> **更新时间**: 2026-08-14
> **作者**: Ryan

---

## 📌 概述

本文档介绍如何将广告平台工具集成到 pi Agent 中，使其能够直接调用 API。

---

## 🎯 目标

当你说：
> "帮我查询一下 TikTok 渠道下 xxx 账户下的 campaign"

pi Agent 应该能够：
1. 理解你的意图
2. 自动调用 `tiktok_list_campaigns` 工具
3. 返回查询结果

---

## 🔧 当前架构

```
┌─────────────────────────────────────────────────────────────┐
│  pi Agent                                                    │
│  ├── 理解用户意图                                            │
│  └── 调用工具（通过 MCP）                                    │
└────────────────────────┬────────────────────────────────────┘
                         │ MCP Protocol
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  MCP Server                                                  │
│  (mcp_servers/ad_platform_server.py)                        │
│  ├── 接收工具调用请求                                         │
│  ├── 验证参数                                                │
│  └── 路由到具体实现                                           │
└────────────────────────┬────────────────────────────────────┘
                         │ API Calls
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  广告平台 API                                                │
│  ├── TikTok Ads API v2.0                                   │
│  ├── Meta Marketing API v18.0                               │
│  ├── Google Ads API v18.0                                   │
│  └── DV360 API v1                                           │
└─────────────────────────────────────────────────────────────┘
```

---

## 📂 文件结构

```
ryan-personal-knowledge/
├── mcp_servers/
│   └── ad_platform_server.py      # MCP Server 实现
├── .pi/
│   └── mcp/
│       └── ad-platform.json        # MCP 配置文件
├── knowledge/skills/
│   ├── tiktok-ads-expert/SKILL.md
│   ├── meta-marketing-api-expert/SKILL.md
│   ├── google-ads-api-expert/SKILL.md
│   ├── dv360-expert/SKILL.md
│   └── ad-platform-tools/SKILL.md
└── config/
    └── ad_platform_credentials_template.json
```

---

## 🚀 快速开始

### 1. 安装 MCP SDK

```bash
pip3 install mcp
```

### 2. 配置 MCP Server

编辑 `.pi/mcp/ad-platform.json`：

```json
{
  "mcpServers": {
    "ad-platform-tools": {
      "command": "python3",
      "args": [
        "/path/to/ryan-personal-knowledge/mcp_servers/ad_platform_server.py"
      ],
      "env": {
        "TIKTOK_APP_KEY": "your_app_key",
        "TIKTOK_APP_SECRET": "your_app_secret",
        "META_APP_ID": "your_app_id",
        "META_APP_SECRET": "your_app_secret",
        "GOOGLE_DEVELOPER_TOKEN": "your_token",
        "GOOGLE_CLIENT_ID": "your_client_id",
        "GOOGLE_CLIENT_SECRET": "your_client_secret",
        "GOOGLE_REFRESH_TOKEN": "your_refresh_token"
      }
    }
  }
}
```

### 3. 配置凭证

```bash
cp config/ad_platform_credentials_template.json config/ad_platform_credentials.json
nano config/ad_platform_credentials.json
```

### 4. 重启 pi

```bash
# 重启 pi Agent
# MCP Server 会自动加载
```

---

## 📝 使用示例

### 示例 1：查询 TikTok Campaign

**用户说：**
> "帮我查询一下 TikTok 渠道下 act_123456 账户下的 campaign"

**pi 执行：**
```python
# 内部调用
result = tiktok_list_campaigns(
    account_id="act_123456",
    fields=["id", "name", "status", "daily_budget"]
)
```

**返回结果：**
```json
{
  "data": [
    {
      "id": "campaign_001",
      "name": "Summer Sale 2026",
      "status": "ENABLED",
      "daily_budget": 100000
    }
  ]
}
```

### 示例 2：创建 Meta 广告系列

**用户说：**
> "帮我创建一个 Meta 广告系列，名称是 'Black Friday Sale'"

**pi 执行：**
```python
# 内部调用
result = meta_create_campaign(
    account_id="act_654321",
    name="Black Friday Sale",
    objective="SALES",
    status="PAUSED"
)
```

---

## 🔐 安全配置

### 环境变量方式（推荐）

```bash
# ~/.zshrc 或 ~/.bashrc
export TIKTOK_APP_KEY="your_key"
export TIKTOK_APP_SECRET="your_secret"
export META_APP_ID="your_app_id"
export GOOGLE_DEVELOPER_TOKEN="your_token"
```

### 凭证文件方式

```bash
# 编辑凭证文件（不提交到 git）
nano config/ad_platform_credentials.json
```

---

## ⚠️ 注意事项

### 1. MCP Server 状态

当前 MCP Server 是**框架版本**，需要补充具体实现：

```python
def _handle_tiktok(self, tool_name: str, args: Dict) -> Dict:
    """处理 TikTok 工具调用"""
    # TODO: 实现实际的 TikTok API 调用
    return {"status": "not_implemented"}
```

### 2. 需要实现的功能

| 平台 | 待实现功能 |
|------|-----------|
| TikTok | OAuth 认证、API 调用、错误处理 |
| Meta | OAuth 认证、Graph API 调用 |
| Google | OAuth 认证、Ads API 调用 |
| DV360 | 服务账号认证、REST API 调用 |

### 3. 速率限制

各平台都有 API 调用限制：
- TikTok: 10,000 次/小时
- Meta: 200,000 次/天
- Google: 100,000 Get / 10,000 Mutate 次/天
- DV360: 根据账户等级

---

## 🔄 更新流程

### 1. 更新 MCP Server

```bash
# 编辑实现
nano mcp_servers/ad_platform_server.py

# 测试
python3 mcp_servers/ad_platform_server.py --mode list

# 提交
git add mcp_servers/
git commit -m "feat: 更新 MCP Server 实现"
```

### 2. 更新 Skill 定义

```bash
# 编辑 SKILL.md
nano knowledge/skills/tiktok-ads-expert/SKILL.md

# 更新 version
# version: 2.0.0 → 2.1.0

# 提交
git add knowledge/skills/
git commit -m "docs: 更新 TikTok Ads Skill 至 2.1.0"
```

---

## 📚 参考文档

- **MCP 协议**: https://modelcontextprotocol.io/
- **TikTok Ads API**: https://business-api.tiktok.com/portal/docs
- **Meta Marketing API**: https://developers.facebook.com/docs/marketing-api
- **Google Ads API**: https://developers.google.com/google-ads/api
- **DV360 API**: https://developers.google.com/display-video/api

---

*本集成方案使 pi Agent 能够直接调用广告平台 API，实现智能化的广告投放管理。*
