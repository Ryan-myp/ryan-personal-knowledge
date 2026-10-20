---
name: creative-production
description: "广告创意策略、文案、图片和视频制作；生成图片/视频时使用已注册的创意 Tool，上传素材仅在用户明确要求后执行。"
version: 1.0.0
namespace: advertising
triggers:
  - [广告创意制作, 创意生产, 生成广告素材, 图片生成, 生成图片, 帮我画, 广告图片, 视频生成, 生成视频, 广告视频, 广告文案, creative production, generate ad creative, make an ad]
---

# 广告创意生产

- 把创意策略、文案撰写、媒体生成和平台上传区分为不同动作。
- 生成图片或视频必须调用已注册的创意 Tool；不得声称未调用 Tool 的素材已生成。
- 只依据用户、知识库或只读查询提供的产品事实；不编造功效、价格、证言、数据或品牌资产。
- 视频任务是异步的：提交一次、保存素材 ID、使用状态查询 Tool 轮询，不重复提交。
- 只有用户明确要求上传时，才使用现有广告上传 Tool；遵守账户、权限、live、确认和审计门禁。
- 生成、上传、绑定广告和启用投放必须分别表述，不得混为一谈。
- 请求缺少会改变结果的关键信息时先追问；探索性请求可以使用明确标注的假设。

需要制作 brief、提示词、审核清单或渠道限制时，按需参考 [production-workflow.md](references/production-workflow.md)。
