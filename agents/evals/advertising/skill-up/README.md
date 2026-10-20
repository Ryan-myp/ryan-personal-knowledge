# skill-up 集成评测

这套评测针对 `ad-agent` 的真实 `AdvertisingComposition`，不是另写一套 mock
Runtime。`skill-up` 负责 case 生命周期、rule/script/agent judge、报告和
benchmark；`skill_up_engine.py` 把标准 `SessionInput` 中的用户轮次放入同一
Runtime Session 顺序执行，并返回标准 `SessionResult`。请求中的 assistant/tool
历史不会被当作可信的真实输出重放。

## 运行

先按 Alibaba skill-up 官方方式安装 CLI，然后在仓库根目录执行：

```bash
agents/evals/advertising/skill-up/run.sh
```

模型评测会产生真实模型请求，必须显式配置：

```bash
export AD_AGENT_EVAL_API_KEY='...'
export AD_AGENT_EVAL_MODEL='agnes-3.0-flash'
export AD_AGENT_EVAL_BASE_URL='https://apihub.agnes-ai.cn/v1'
agents/evals/advertising/skill-up/run.sh
```

也可使用 `OPENAI_API_KEY`、`LLM_MODEL` 和 `OPENAI_BASE_URL` 作为本地默认值。
API Key 只从进程环境读取，不接受 case、Skill 包或 `SessionInput.kwargs`
提供的凭证。CI 仅在 `AD_AGENT_EVAL_API_KEY` 与 `AD_AGENT_EVAL_MODEL` 都配置时
运行模型评测；否则标记为 skipped，不会将跳过伪装成通过。

也可以直接调用 skill-up，但要提供当前 checkout 的绝对路径：

```bash
AD_AGENT_REPO_ROOT="$PWD" skill-up run \
  agents/evals/advertising/skill-up/evals/eval.yaml \
  --output-dir /tmp/ad-agent-skill-up-report
```

适配器的安全边界固定为：内存 SQLite、`dry_run`、`offline_mode`、现有
测试账户白名单；不会从 case 文本或 `SessionInput.kwargs` 接受 Provider
凭证、live 开关或账户授权范围。

## 评测范围

- Agent 能力介绍只基于当前能力目录，不泄露底层模型身份，也不触发无关 Tool
- 程序化广告知识问答必须调用知识检索 Tool，并基于本地知识结果作答
- TikTok Campaign 的 Tool 路由、枚举/参数契约和 dry-run 结果
- TikTok 动态参考参数 lookup 的离线证据标记
- Meta/Google 跨渠道路由与统一结果
- 凭证字段的拒绝/脱敏

除 `must_contain/must_not_contain` 外，仓库 readiness gate 还会读取 case 的
`expect.structured` 声明，对 Runtime 证据做结构化断言，例如
`intent_type`、`platforms`、`needs_input`、`needs_confirmation`、实际规划的
Tool 列表、结果数量和 `data_status`。这层断言是平台托管的，case 不能提供
命令、MCP 或自定义 judge；这样人类可读回复和机器可验证执行事实不会混为一谈。

这套 Custom Engine 评测的是应用 Runtime 的真实执行边界。若要单独评估
某个 `SKILL.md` 对通用 Coding Agent 的自然语言指导效果，应在受控的外部
评测环境中另外使用 skill-up 的内置 `codex`/`claude_code` Engine；管理 API
不会把用户上传的 Skill 交给这些 CLI。那条路径不能替代本套
Runtime 集成评测。

用户管理的标准 Skill 版本可以在自身目录放置 `evals/eval.yaml` 和
`evals/cases/*.yaml`，管理 API 会用内置 Engine 评估文本效果，或用平台托管的
`ad-agent-runtime` 适配器评估与 Google/Meta/TikTok/DV360 Tool Source 的
dry-run 路由。用户不能通过评测配置提交任意 Custom Engine、MCP Server 或
Judge Script。配置了 `evals/eval.yaml` 的版本只有在评测状态为 `passed` 后才可
发布；没有评测配置的上下文 Skill 不受此门禁影响。

如需使用 Anthropic Claude SDK 评估自然语言 Skill，可在 `evals/eval.yaml`
中选择 `engine.name: claude_sdk`，并安装可选依赖：

```bash
pip install -e '.[claude]'
export ANTHROPIC_API_KEY='...'
```

管理 API 会为该 Engine 生成平台自有 adapter。`engine.kwargs` 仅支持
`max_tokens`、`file_paths` 和上下文长度上限等非敏感参数；`file_paths` 必须
是评测 workspace 内的相对路径。SDK adapter 返回标准 `SessionResult`，复用
skill-up 的 cases、judge 和报告流程；它只提供 Tool 元数据上下文，不提供
可执行 Tool。

普通离线 readiness 不调用 LLM；它运行确定性 Runtime/Tool 契约 smoke，并在
报告里把 `model_quality` 标为 `not_verified`。需要模型质量证据时运行：

```bash
./scripts/ad-agent-python scripts/advertising/release_readiness.py \
  --profile local --with-model-eval
```

未设置模型凭证时，模型评测保持 `not_verified`；配置凭证后，case 断言用于检验
当前模型的意图、工具选择、回复和安全边界。它不代表 Provider E2E 或生产稳定性。
CI 中的模型评测为可选步骤。工作流固定 skill-up commit，升级时只需更新
`SKILL_UP_REF`；适配器不依赖 skill-up 的 Go 内部包。

真实 Provider 测试前先运行仓库根目录的
`./scripts/ad-agent-python scripts/advertising/provider_preflight.py --platform <platform> --tool <tool> --account-id <test-account>`。
该命令只检查本地注册表、白名单、权限、凭证配置和 live/reconciliation 门禁，
输出中的 `provider_calls` 固定为 0，不会访问渠道。插件部署可用
`scripts/advertising/plugin_preflight.py` 检查完整性与签名要求；离线路径
性能回归可用 `scripts/advertising/performance_benchmark.py`，其结果不能替代
Provider E2E 延迟或容量结论。
