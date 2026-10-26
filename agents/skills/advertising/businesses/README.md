# 业务 Skills

`app/`、`ecommerce/`、`social/` 提供按业务目标组织的 advisory 指导；
`channels/` 提供渠道专业知识。二者都不注册 Tool 或持有 Provider 凭证。
工具与参数能力由当前 Registry、Tool schema、蓝图和账户资格决定。

`business` frontmatter 可选：`name`、`version`、`description`、
`business_rules.focus_metrics` 只描述业务背景。只有确实存在可审计的
合同/合规限制时，才声明 `allowed_channels`、`disallowed_channels`、
`allowed_campaign_types` 或 `min_budget` / `max_budget`。这些字段由
`BusinessSkillPolicy` **强制执行**，不是软性建议；一旦声明，就必须说明
来源、适用租户/币种、变更与撤销方式，并有专门测试。

不把各平台 Campaign 类型拼成统一静态枚举，例如 `MAX` 不能代替
Google Ads 的 `PERFORMANCE_MAX`；也不把不同货币的数字直接比较。
Skill 不应承诺一键批量操作、品牌效果或跨渠道预算迁移已可执行。
新增业务时沿用标准 `SKILL.md` 格式，写目标、输入、步骤、证据边界和
失败/恢复条件；仅在有真实业务授权时才配置策略门禁。
