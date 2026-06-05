# agentmemory 与 Hermes Agent 集成指南

**日期**: 2025-06-05
**方案**: 混合模式 (C) — 保留 Hermes 内置记忆 + agentmemory 增强层

## 简介

agentmemory (https://github.com/rohitg00/agentmemory, 21.3k ⭐) 是一个为 AI 编码代理提供持久化记忆的记忆引擎。

核心能力：
- 自动捕获每次工具调用 (通过 hooks)
- BM25 + 向量 + 知识图谱混合搜索 (R@5: 95.2%)
- 4 层记忆整合 (工作/情景/语义/程序)
- Token 节省 ~92%

## 安装步骤

### 1. 安装 iii-engine

```bash
# macOS arm64
mkdir -p ~/.local/bin
curl -fsSL https://github.com/iii-hq/iii/releases/download/iii/v0.11.2/iii-aarch64-apple-darwin.tar.gz -o /tmp/iii-engine.tar.gz
tar -xzf /tmp/iii-engine.tar.gz -C /tmp/
# 注意：包内文件名为 'iii'，不是 'iii-aarch64-apple-darwin'
cp /tmp/iii ~/.local/bin/iii
chmod +x ~/.local/bin/iii
~/.local/bin/iii --version  # 应输出 0.11.2
```

**注意**:
- 用 `tar -tzf file.tar.gz` 先看包内结构
- 大型二进制 tar 文件解压可能触发系统超时阻断，备选用 Python `tarfile` 模块

### 2. 安装 agentmemory

```bash
npm install -g @agentmemory/agentmemory
agentmemory  # 首次启动，交互式选择接入的 Agent
```

首次启动会：
1. 选择接入哪些 Agent (可选 Hermes)
2. 配置 LLM provider (可选，不配也能用)
3. 启动记忆服务器 (:3111) + 查看器 (:3113)

### 3. 验证安装

```bash
# 健康检查
curl http://localhost:3111/agentmemory/health

# 搜索测试 (注意加 Content-Type header)
curl -X POST http://localhost:3111/agentmemory/smart-search \
  -H "Content-Type: application/json" \
  -d '{"query": "test"}'
```

## Hermes 配置

在 `~/.hermes/config.yaml` 添加：

```yaml
mcp_servers:
  agentmemory:
    command: npx
    args: ["-y", "@agentmemory/mcp"]
    env:
      AGENTMEMORY_URL: "http://localhost:3111"
```

启动 agentmemory 服务器后，Hermes 可以通过 MCP 访问 53 个 memory tools。

## 端口说明

| 端口 | 服务 | 说明 |
|------|------|------|
| 3111 | REST API | 记忆搜索/保存 API |
| 3112 | WebSocket Streams | 实时事件流 |
| 3113 | Viewer | 记忆浏览器 UI |
| 49134 | Engine | iii-engine WebSocket |

## 注意事项

- agentmemory 需要在前台保持运行 (另一个终端窗口)
- 无 LLM key 也能运行，但压缩/摘要功能会禁用
- 内存占用约 20-25MB RSS
- iii console 可能因 GitHub API 限时而安装失败，不影响核心功能
