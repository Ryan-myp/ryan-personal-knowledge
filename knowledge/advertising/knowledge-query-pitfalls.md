# ad-knowledge-query 已知坑与规避策略

**日期**: 2025-06-05
**分类**: advertising
**标签**: #排障经验 #ad-knowledge-query #ad-api

## 背景

ad-knowledge-query 是广告平台代码库知识检索的核心工具，但有两个已知的坑会导致返回错误结果。

## 坑 1: scenario_card 的 min_confidence_score 导致走 SQLite 子图

### 症状
查询返回不相关的结果，source_mode 为 `sqlite_candidate_subgraph`

### 原因
当 scenario_card 中设置了 `min_confidence_score=999` 时，会跳过 knowledge_card 快捷路径，转而走 SQLite 子图查询，返回的内容与预期无关。

### 规避策略
- 不要给 scenario_card 设置过高的 min_confidence_score
- 如果返回了 sqlite_candidate_subgraph，检查 confidence_score 设置
- 需要确认查询是否走了预期的知识卡片路径

## 坑 2: api_docs 优先级覆盖正确结果

### 症状
正确的 code 查询结果被 api_docs 的误匹配覆盖

### 原因
`render_answer_context` 函数中，api_docs 的优先级高于 code。当 api_docs 存在误匹配时，会覆盖更准确的 code 结果。

### 规避策略
- 用 `--scope code` 限定只查代码，绕过 api_docs 干扰
- 确认查询结果中的 source_mode 和匹配源
- 优先使用 scope 参数缩小搜索范围

## 诊断 checklist

查询返回异常时按以下步骤排查：

1. 检查返回的 `source_mode` 是否为 `sqlite_candidate_subgraph` → 坑 1
2. 检查返回结果是否被 `api_docs` 覆盖 → 坑 2
3. 尝试用 `--scope code` 限定查询范围
4. 检查 scenario_card 的 min_confidence_score 设置

## 相关资源
- ad-ai-coding 仓库: git.garena.com/marketing/ad_ai_coding
- query_knowledge.py 路径: ~/ad_ai_coding/tools/knowledge_query/
