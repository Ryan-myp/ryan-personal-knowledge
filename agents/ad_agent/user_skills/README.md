# User Skills

用户 Skill 只提供标准 `SKILL.md` 目录中的知识、SOP、参考资料和评测素材。
它们不会注册可执行的编排器，也不会绕过 `AgentRuntime`、`IntentRouter` 或
`ToolRegistry`。

跨渠道广告创建由 Runtime 根据各 Capability 发布的 Tool 元数据、Schema 和
资源依赖自动规划；新增业务流程应通过标准 Skill 描述流程，并复用已注册
Tools。需要接入新的外部动作时，应新增对应 Capability Tool，而不是在这里
增加第二套 workflow/orchestrator 执行入口。
