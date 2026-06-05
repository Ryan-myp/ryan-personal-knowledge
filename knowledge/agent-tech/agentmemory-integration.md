# agentmemory 集成记录

**日期**: 2025-06-05
**分类**: agent-tech
**标签**: #agent-技术 #工具集成

## 集成方案：C — 混合模式

### 架构
```
Hermes 内置记忆 (SQLite + FTS5) — 保留，继续工作
    +
agentmemory MCP (语义搜索 + 跨会话记忆) — 增强层
```

### 安装步骤

#### 1. 安装 iii-engine
```bash
# 下载
curl -fsSL https://github.com/iii-hq/iii/releases/download/iii/v0.11.2/iii-aarch64-apple-darwin.tar.gz -o /tmp/iii-engine.tar.gz
# 解压
tar -xzf /tmp/iii-engine.tar.gz -C /tmp/
# 安装
cp /tmp/iii ~/.local/bin/iii && chmod +x ~/.local/bin/iii
# 验证
~/.local/bin/iii --version  # 输出: 0.11.2
```

#### 2. 安装 agentmemory
```bash
npm install -g @agentmemory/agentmemory  # 239 packages, 3 minutes
```

#### 3. 首次启动
```bash
agentmemory
```
- 交互式选择接入的 Agent（选了 Claude Code + Hermes）
- 嵌入 provider 选择本地（免费）

#### 4. 创建 .env
```bash
mkdir -p ~/.agentmemory && cp $(npm root -g)/@agentmemory/agentmemory/.env.example ~/.agentmemory/.env
```

#### 5. 配置 Hermes MCP
在 `~/.hermes/config.yaml` 末尾追加：
```yaml
mcp_servers:
  agentmemory:
    command: npx
    args: ["-y", "@agentmemory/mcp"]
    env:
      AGENTMEMORY_URL: "http://localhost:3111"
```

#### 6. 验证
```bash
# 健康检查
curl http://localhost:3111/agentmemory/health  # status: healthy

# 搜索测试
curl -X POST http://localhost:3111/agentmemory/smart-search \
  -H "Content-Type: application/json" \
  -d '{"query": "test"}'  # 返回空结果（无记忆数据）
```

### 服务端口
| 服务 | 端口 |
|------|------|
| REST API | 3111 |
| Viewer | 3113 |
| Streams | 3112 |
| Engine | 49134 |

### 注意事项
1. **agentmemory 服务器必须保持运行**（前台进程）
2. **iii console 安装失败** — GitHub API 限速，不影响核心功能，可跳过
3. **Heap tight 警告** (91%) — Node.js 正常现象，内存实际很小 (21MB)
4. **LLM compression 未配置** — 因为没设 API key，LLM 压缩和总结功能被禁用，这是安全默认行为

### 对比方案

| | 方案 A: 纯 MCP | 方案 B: 深度替换 | **方案 C: 混合** |
|---|---|---|---|
| Hermes 内置记忆 | ✅ | ❌ | ✅ |
| agentmemory MCP | ✅ | ✅ | ✅ |
| 风险 | 低 | 高 | 低 |
| 可逆性 | 容易 | 难 | 容易 |

选择 C 的理由：不破坏现有工作流，渐进式增强，随时可以退回到纯内置。

### 后续优化
- 配置 LLM embedding provider (Gemini/Vertex AI 免费)
- 设置自动压缩和总结
- 定期回顾 agentmemory 的召回质量
- 观察 Token 节省效果
