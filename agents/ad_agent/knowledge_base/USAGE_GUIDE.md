# LLM Wiki 使用指南

## 这套知识库解决什么问题

它为单 Agent 提供广告业务上下文：识别平台对象与层级，补齐创建前依赖，解释预算/出价/受众/素材选择，诊断报表异常，并把平台指标连接到真实业务结果。它不是 API 文档的替代品，也不是可执行工作流或凭证存储。

## 查询示例

### CLI

```bash
./scripts/ad-agent-python agents/ad_agent/tools/wiki_query.py --action stats
./scripts/ad-agent-python agents/ad_agent/tools/wiki_query.py --action search --query "Meta CAPI 去重"
./scripts/ad-agent-python agents/ad_agent/tools/wiki_query.py --action search --query "DV360 Line Item 预算"
./scripts/ad-agent-python agents/ad_agent/tools/wiki_query.py --action search --query "TikTok Spark 授权"
./scripts/ad-agent-python agents/ad_agent/tools/wiki_query.py --action search --query "Google PMax 商品分组"
```

### Python

```python
from agents.ad_agent.tools.wiki_query import get_wiki_loader

loader = get_wiki_loader()
results = loader.search(
    "电商 purchase 事件和 ROAS 优化",
    platforms=["meta"],
    limit=5,
)
for result in results:
    print(result.content["title"])
    print(result.content["raw_content"][:800])
```

Runtime 通过 `KnowledgeProvider` 读取同一批 Markdown。查询结果是有界 excerpt，并携带文档版本、更新时间、来源、章节和 citation；不会把整库无上限注入 Prompt。

## 推荐的回答顺序

1. 识别平台、业务目标、账户/advertiser/partner scope、市场、时区和预算周期。
2. 检索 `cross-platform-hierarchy` 与对应平台的 hierarchy/constraint 文档。
3. 对创建或修改，核对当前 Registry Tool schema、动态 lookup、权限、风险、dry-run/live 和幂等。
4. 对优化，检索行业打法、预算出价、受众、创意和诊断文档，先解释假设再给动作。
5. 对数据，注明 level、日期、时区、归因窗口、币种、数据延迟、平台口径与后端口径。
6. 输出主指标、保护指标、观察窗口、停止/回滚条件；不要承诺固定结果。

## 内容目录

| 目录 | 适合问题 |
|---|---|
| `platforms/google` | Search、Shopping/PMax、Video/App、GAQL、转化和 Google 诊断 |
| `platforms/meta` | ODAX、Ad Set、Catalog、特殊类别、Pixel/CAPI、Insights |
| `platforms/tiktok` | Smart+、Spark、Commerce、素材事件、定向和报表 |
| `platforms/dv360` | IO/Line Item、采购、定向 assignment、创意审批、异步报告 |
| `business` | 层级对照、行业打法、预算、受众、创意、归因增量 |
| `expertise` | 全链路诊断、实验设计、最佳实践和错误模式 |

## 新增或修改文档

新文档必须使用 [`SCHEMA.md`](SCHEMA.md) 中的 frontmatter，至少包含稳定 `id`、`title`、`layer`、`knowledge_type`、`platform`、`source_ref`、`version`、`confidence`、`updated_at` 和 `status`。平台事实应写来源和版本；运营经验应写适用条件、样本边界和失效条件。

发布前检查：

```bash
python3.13 -m compileall -q agents/ad_agent
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=. python3.13 -m pytest agents/ad_agent/tests/test_knowledge_memory.py -q
make ad-agent-audit
git diff --check
```

## 检索实现

Markdown 按标题章节切块，使用 SQLite FTS5 做召回并用 BM25 风格排序；标题、章节和标签有额外权重。SQLite 不带 FTS5 时自动回退到进程内词法排序，因此不需要单独部署向量数据库或 Embedding 服务。未来若更换检索实现，文档格式、发布门禁和单 Agent 安全边界保持不变。

## 禁止事项

- 不在 Wiki 中写 access token、secret、用户原始 PII 或内部权限材料。
- 不在 Skill/知识文档中注册 Tool、调用 Provider 或执行脚本。
- 不把知识文档中的字段/枚举当作当前 Tool 的事实来源。
- 不把 API 接收成功、对象创建成功、审核通过、开始投放和最终归因混成一个状态。
- 不把平台归因 ROAS、固定 benchmark 或短期前后对比直接解释为真实增量。
