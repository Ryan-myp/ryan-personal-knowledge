# 同一 Run 内动态发现与加载工具

## 问题与原因

用户查询 Campaign 及其下层级详情，父级结果已经返回 Ad Set / Ad ID，
Agent 却因为当前模型请求仅附带 Campaign 工具而提前结束。
原有选择器每一步主要根据用户输入选择工具；没有可执行的运行期发现入口。
提示词只能禁止虚构工具，不能让模型主动获得缺失的 schema。

## 实现

- 新增通用本地工具 `agent_discover_tools`，通过现有 Tool Source / Plugin 生命周期注册。
- 初始选择仍按原有规则进行；发现入口作为控制能力提供，不参与业务意图竞争。
- 模型根据下一步动作、namespace、资源类型检索注册目录。匹配工具的 schema 在下一次
  模型请求中加载，继续使用已经获得的真实资源 ID。发现本身不执行业务操作。
- 如果模型先调用未附带的工具，LLM adapter 有一次受约束的恢复机会，指向注册的发现入口；
  不执行或转发未校验的工具名和参数。
- 每次最多返回 4 个工具，每个 Run 最多执行 6 次搜索、同时加载最多 8 个工具，仍受
  `max_tools`、工具调用次数、模型上下文和超时上限限制。注册目录复用，不初始化第二套 Agent。
- 后续加固将加载集合改为滚动窗口：新能力替换较早加载的 schema，需要时可以重新发现；
  发现动作不复用查询缓存，避免返回“已加载”但实际 schema 已被替换的旧结果。
- 加载状态在 Run 的 ContextVar 中隔离，由受信任 executor 更新；请求 context、历史对话和
  模型 context_updates 不能注入加载权限。Run 结束即清理，迟到的调用不能重新打开状态。

## 安全、失败与恢复

搜索默认只读；查找写工具需要显式 `effect=write`。发现结果受 Tool allowlist、可信 principal
权限、业务 namespace 策略和 live 写工具开放范围约束。已加载工具执行时仍经过现有
schema、账户范围、确认、幂等、审计等门禁，发现不会授予执行权限。

发现结果分别返回 `loaded`、`no_matching_tool`、`capacity_limit`、`discovery_limit`。
没有匹配不等于外部接口没有权限；可以在预算内调整检索表达，最终说明具体阻塞。
新发现的工具不能在获得 schema 之前与发现调用一起执行。源卸载或契约变化后，不复用旧 schema。

## 回归与验证边界

新增回归涵盖父子资源查询、非广告 invoice line 场景、初始工具选择为空、显式 allowlist、
权限不足、业务策略限制、写工具发现边界、并发会话隔离、跨 Run 清理、schema 与搜索预算、
同批越界调用，以及模型错误工具名的受控恢复。

使用真实模型和本地固定渠道返回数据回放原请求，验证模型自主发现后继续查询 Campaign、
Ad Set、Ad；未发起真实广告渠道 API 请求。该证据只证明编排与加载链路，不替代渠道在线验收。

主要回归文件：

- `agents/tests/harness/test_runtime_tool_discovery.py`
- `agents/tests/harness/test_discovery_bounds.py`
- `agents/tests/harness/test_llm_tool_calling.py`
- `agents/tests/advertising/test_runtime_discovery_integration.py`

最终验证：`make ad-agent-check` 通过（3356 项 Python 测试、编译、能力/契约及知识审计）；
213 项前端测试和 `git diff --check` 通过。新增发现模块覆盖率 97%。真实模型两次隔离回放
均主动发现并查完三个层级。278 个工具目录的本地搜索实测冷启动约 2.6ms，后续中位数约 0.6ms。

全仓 QGuard 仍未通过：771 个文件、4998 项问题、评分 0；未调整门槛。
本次新增的两个发现模块单独检查为 0 项问题。不能将单模块检查表述为全仓质量门禁通过。
可追溯结果位于 `agents/evals/advertising/evidence/runtime-tool-discovery-20261029.json`。

## 部署与回滚

无需迁移数据库，不改模型凭证、用户模板或聊天记录。重启原来的 `0.0.0.0:8766`
服务即可加载。回滚本次发现工具、Harness 接入和对应契约快照后重启即可，不需要恢复数据库。
已重启并验证 `*:8766` 监听、`/readyz` 返回 200、发现工具已注册，原有 14 份用户模板的 ID
和原对话记录均保留。
发现调用已复用普通 Tool 的执行轨迹和审计链路，后续指标系统可以直接统计发现次数、
命中率和查找后实际执行比例，无需另建生命周期。
