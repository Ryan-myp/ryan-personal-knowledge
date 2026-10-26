---
name: creative-production
description: "广告文案、图片和视频制作与素材视觉评审；生成媒体使用已注册的创意 Tool，上传素材仅在用户明确要求后执行。"
version: 1.1.0
namespace: advertising
triggers:
  - [广告创意制作, 创意生产, 生成广告素材, 图片生成, 生成图片, 帮我画, 广告图片, 视频生成, 生成视频, 广告视频, 广告文案, creative production, generate ad creative, make an ad]
  - [广告素材设计, 素材视觉评审, 广告创意视觉方向, ad creative review]
  - [品牌素材来源, 品牌 logo, 素材权属, 商标授权]
---

# 广告创意生产

- 把创意策略、文案撰写、媒体生成和平台上传区分为不同动作。
- 生成图片或视频必须调用已注册的创意 Tool；不得声称未调用 Tool 的素材已生成。
- 只依据用户、知识库或只读查询提供的产品事实；不编造功效、价格、证言、数据或品牌资产。
- 设计从本次目标、受众和已核验的品牌/产品素材出发。探索性 brief 可提出有实质差异的视觉方向；单张制作、局部修改或用户已选定方向时直接执行，不设置固定的三版审批门。
- 交付前检查主张与视觉是否一致、主体和 CTA 是否清晰、文字在目标版位是否可读，以及商标、人物、字体和素材的来源与使用授权。未实际查看生成结果时，不能声称已经通过视觉审核。
- 视频任务是异步的：提交一次、保存素材 ID、使用状态查询 Tool 轮询，不重复提交。
- 只有用户明确要求上传时，才使用现有广告上传 Tool；遵守账户、权限、live、确认和审计门禁。
- 生成、上传、绑定广告和启用投放必须分别表述，不得混为一谈。
- 请求缺少会改变结果的关键信息时先追问；探索性请求可以使用明确标注的假设。

制作 brief、提示词或渠道适配时按需参考 [production-workflow.md](references/production-workflow.md)；探索视觉方向或做成品评审时参考 [visual-quality-review.md](references/visual-quality-review.md)；品牌素材来源、权属和授权核对见 [brand-asset-check.md](references/brand-asset-check.md)。这些参考只提供方法，不执行脚本或注册 Tool。
