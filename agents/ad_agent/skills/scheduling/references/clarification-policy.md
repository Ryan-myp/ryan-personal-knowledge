# 定时任务澄清字段

## 最小可执行合同

```text
ScheduleDraft
  ├── instruction       到期后交给 Agent 的自然语言指令
  ├── cadence            合法 cron 或已解析的周期
  ├── timezone           IANA 时区
  ├── providers          当前 Registry 中能匹配 Tool 的渠道
  ├── account_scope      账户/租户范围，来自可信 principal 或用户明确选择
  ├── capability_check   matched tools、读写效果、缺口和警告
  └── confirmation       awaiting_input / awaiting_confirmation / confirmed
```

## 能力预检规则

1. 先把定时任务的 instruction 当作一次普通 Agent 请求解析。
2. 使用当前 Tool Registry 和 IntentRouter 匹配能力，不执行 Tool。
3. 没有渠道、没有普通业务意图或没有匹配 Tool 时，返回澄清/不支持原因。
4. 写操作只能报告 dry-run 和后续确认要求，不能授予 live 权限。
5. 只有草稿字段完整、能力匹配成功并收到用户确认，才能创建 active schedule。

## Schema 级补充检查

匹配到 Tool 后还要读取它自己的 `input_schema`：

- `required` 和 `provider_required` 中未提供的字段必须进入缺口列表；
- `provider_any_of` / `provider_exactly_one_of` 未满足时，必须说明可选字段组；
- 账户字段只能从可信 principal 的范围和用户明确选择的账户合并得出；不同渠道的
  账户不能因为都叫 `account` 就自动复用；
- 动态资源 ID 缺失时只能继续澄清或调用已注册的只读 lookup，不能由名称或模型猜 ID；
- schema 检查只读本地 metadata，`provider_calls=0`、`network_called=false`，不验证
  凭证是否能真实访问平台。

建议将预检报告保存成以下结构，供确认摘要、运行记录和前端展示复用：

```json
{
  "status": "ready | needs_input | unsupported",
  "intent_type": "download_report",
  "tool_names": ["provider_owned_tool"],
  "missing_parameters": {},
  "account_id": "redacted-or-scoped-id",
  "effects": ["read"],
  "execution_mode": "dry_run",
  "provider_calls": 0,
  "network_called": false
}
```
