# agentmemory 集成分析

**日期**: 2025-06-05
**标签**: #前沿-agent #工具对比

## 项目概况

**agentmemory** (21.3k ⭐) — 为 AI 编码代理提供持久化记忆引擎
- 安装: `npm install -g @agentmemory/agentmemory`
- 启动后: 记忆服务器 (:3111) + 实时查看器 (:3113)
- 支持: Claude Code, Codex, Cursor, **Hermes**, Gemini CLI 等 30+ 代理

## 核心能力

### 1. 记忆流水线
```
PostToolUse hook → SHA-256去重 → 隐私过滤 → 存储观测
→ LLM压缩 → 结构化事实 + 概念 + 叙事
→ 向量嵌入 → BM25 + 向量索引
```

### 2. 4层记忆整合
| 层级 | 内容 | 类比 |
|------|------|------|
| Working | 原始观测 | 短期记忆 |
| Episodic | 会话摘要 | 「发生了什么」 |
| Semantic | 提取的事实 | 「我知道什么」 |
| Procedural | 工作流与决策 | 「怎么做」 |

### 3. 检索能力
- BM25 (关键词) + Vector (语义) + Graph (知识图谱)
- RRF 融合 (Reciprocal Rank Fusion)
- R@5 检索准确率: 95.2%
- Token 节省 ~92%

### 4. Hermes 集成方式 (关键!)
在 `~/.hermes/config.yaml` 添加:
```yaml
mcp_servers:
  agentmemory:
    command: npx
    args: ["-y", "@agentmemory/mcp"]

memory:
  provider: agentmemory
```

或更深的插件集成:
```bash
# 复制 integrations/hermes 到 ~/.hermes/plugins/agentmemory
```
这会提供 6-hook 记忆提供者集成:
- 预 LLM 上下文注入
- 轮次捕获
- MEMORY.md 镜像
- System prompt 块

## 与 Hermes 内置记忆的对比

| 维度 | Hermes 内置记忆 | agentmemory |
|------|----------------|-------------|
| 检索方式 | SQLite + FTS5 | BM25 + Vector + Graph |
| Token 效率 | 全量加载 | 只加载 top-K (~1900 tokens) |
| 跨代理 | 每代理独立文件 | MCP 统一记忆 |
| 记忆生命周期 | 静态 | 自动衰减 + 遗忘 |
| 实时查看 | 无 | 端口 3113 |

## 集成建议

### 方案 A: 轻量 MCP 集成 (推荐先试)
- 只加 MCP server，不动 Hermes memory 配置
- 获得 53 个 memory tools 可用
- 不破坏现有记忆体系

### 方案 B: 深度集成
- 设置 `memory.provider: agentmemory`
- 替换 Hermes 内置记忆
- 获得 hook 级自动捕获

### 方案 C: 混合模式
- 保留 Hermes 内置记忆作为基础
- agentmemory 作为增强层 (语义搜索 + 跨会话记忆)
- 通过 `/recall` 和 `/remember` 斜杠命令手动调用

## 依赖
- Node.js (npm)
- iii-engine (v0.11.2 固定版本)
- 可选: 本地嵌入 (npm install @xenova/transformers)

## 优点
1. 成熟度高 (21.3k ⭐, 124 PR, 成熟生态)
2. Hermes 官方支持 (有专门的 integration guide)
3. 多代理统一记忆
4. Token 节省显著
5. 有实时查看器

## 缺点
1. 依赖 iii-engine (需要单独安装原生二进制)
2. 增加一个后台进程
3. 嵌入模型需要额外配置才能达到最佳效果
4. 学习成本不低

## 下一步行动
1. 评估 iii-engine 安装难度 (macOS arm64 有预构建二进制)
2. 决定集成方案 (A/B/C)
3. 先试 MCP 方案，不满意再考虑深度集成
