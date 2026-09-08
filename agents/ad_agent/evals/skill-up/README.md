# skill-up 集成评测

这套评测针对 `ad-agent` 的真实 `AgentRuntime`，不是另写一套 mock
Runtime。`skill-up` 负责 case 生命周期、rule/script/agent judge、报告和
benchmark；`skill_up_engine.py` 负责把标准 `SessionInput` 转成一次
`AgentRuntime.run()`，再返回标准 `SessionResult`。

## 运行

先按 Alibaba skill-up 官方方式安装 CLI，然后在仓库根目录执行：

```bash
agents/ad_agent/evals/skill-up/run.sh
```

也可以直接调用 skill-up，但要提供当前 checkout 的绝对路径：

```bash
AD_AGENT_REPO_ROOT="$PWD" skill-up run \
  agents/ad_agent/evals/skill-up/evals/eval.yaml \
  --output-dir /tmp/ad-agent-skill-up-report
```

适配器的安全边界固定为：内存 SQLite、`dry_run`、`offline_mode`、现有
测试账户白名单；不会从 case 文本或 `SessionInput.kwargs` 接受 Provider
凭证、live 开关或账户授权范围。

## 评测范围

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
`ad-agent-runtime` 适配器评估与 Google/Meta/TikTok/DV360 Capability 的
dry-run 路由。用户不能通过评测配置提交任意 Custom Engine、MCP Server 或
Judge Script。配置了 `evals/eval.yaml` 的版本只有在评测状态为 `passed` 后才可
发布；没有评测配置的上下文 Skill 不受此门禁影响。

如需使用 Anthropic Claude SDK 评估自然语言 Skill，可在 `evals/eval.yaml`
中选择 `engine.name: claude_sdk`，并安装可选依赖：

```bash
pip install -e 'agents/ad_agent[claude]'
export ANTHROPIC_API_KEY='...'
```

管理 API 会为该 Engine 生成平台自有 adapter。`engine.kwargs` 仅支持
`max_tokens`、`file_paths` 和上下文长度上限等非敏感参数；`file_paths` 必须
是评测 workspace 内的相对路径。SDK adapter 返回标准 `SessionResult`，复用
skill-up 的 cases、judge 和报告流程；它只提供 Tool 元数据上下文，不提供
可执行 Tool。

CI 在 `.github/workflows/ad-agent-harness.yml` 中固定了 skill-up commit，
升级时只需更新 `SKILL_UP_REF`，再执行本套 `validate` 和 `run`；适配器不
依赖 skill-up 的 Go 内部包，因此不会被内部重构绑定。

真实 Provider 测试前先运行仓库根目录的
`./scripts/ad-agent-python agents/ad_agent/scripts/provider_preflight.py --platform <platform> --tool <tool> --account-id <test-account>`。
该命令只检查本地注册表、白名单、权限、凭证配置和 live/reconciliation 门禁，
输出中的 `provider_calls` 固定为 0，不会访问渠道。插件部署可用
`agents/ad_agent/scripts/plugin_preflight.py` 检查完整性与签名要求；离线路径
性能回归可用 `agents/ad_agent/scripts/performance_benchmark.py`，其结果不能替代
Provider E2E 延迟或容量结论。
