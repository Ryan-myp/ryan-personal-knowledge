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

这套 Custom Engine 评测的是应用 Runtime 的真实执行边界。若要单独评估
某个 `SKILL.md` 对通用 Coding Agent 的自然语言指导效果，应另外使用
skill-up 的内置 `codex`/`claude_code` Engine；那条路径不能替代本套
Runtime 集成评测。

CI 在 `.github/workflows/ad-agent-harness.yml` 中固定了 skill-up commit，
升级时只需更新 `SKILL_UP_REF`，再执行本套 `validate` 和 `run`；适配器不
依赖 skill-up 的 Go 内部包，因此不会被内部重构绑定。
