# 广告账户读写权限

## 权限边界

- `allowed_accounts` 仍是测试账户写入白名单，不包含普通生产账户。
- `provider_read_namespaces` 是部署侧显式授予共享身份的只读范围。指定渠道中，
  可以查询当前渠道凭证有权访问的账户，但不代表上游已经授权或验证成功。
- 独立 API key 身份不自动继承共享身份的只读范围；其权限仍来自可信身份配置。
- 请求体、模型参数、历史对话和 Skill 不能授予或扩大这个范围。
- 查询使用用户指定的账户；失败时保留真实错误，不自动换成测试账户。

测试部署示例：

```yaml
provider_read_namespaces: ["google-ads", "meta", "tiktok"]
allowed_accounts:
  meta: ["test-account"]
```

这里的 `test-account` 是示例标识，不是可执行账户。实际测试账户继续沿用部署配置，
无需将需要分析的普通账户逐一加入写入白名单。

## 执行链路

身份契约新增 `provider_read_namespaces`，通过 `to_safe_dict()` /
`from_claims()` 保留在任务的可信身份快照中。旧快照没有此字段时仍默认拒绝额外范围，
不会因为升级自动提权。

原生 Tool 和 MCP 管理入口共用账户策略。查询账户列表时区分“没有授权账户”
和“按当前凭证查询”，避免把写入白名单当成完整账户目录。渠道本身的访问权限、
限流、账户状态和错误分类保持不变。

测试账户的真实写入还必须通过：`ads.write`、部署 live 开关、界面的 live 模式、
已批准且声明支持 live 的 Tool、确认、幂等、资源归属校验和审计。
测试部署放行的是已支持的 Campaign 及下层级创建、修改等操作，不因此开放
Audience、Pixel 等其他资源写入，也不把仅支持 dry-run 的接口变成 live。

## 失败恢复与回滚

本次不修改数据库结构，不迁移或清空聊天、模板、知识库等数据。当前运行中的任务
继续使用自己的身份快照；新配置需重启原服务生效。

需要恢复原来的严格查询范围时，删除或置空 `provider_read_namespaces` 后重启。
需要关闭真实写入时，关闭 `allow_live_writes` 或部署 live 开关。
新增账户授权上下文使用现有结构化审计字段，不要求额外观察性组件。

回归用例位于
`agents/tests/advertising/test_account_read_write_permissions.py`，
覆盖三渠道查询、报表、多轮账户延续、MCP、写入拒绝、身份隔离和非法配置。
验证使用假客户端与网络拦截，不消耗真实渠道 API 配额。
