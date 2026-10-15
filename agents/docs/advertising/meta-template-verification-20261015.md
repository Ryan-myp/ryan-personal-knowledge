# Meta 内置模板核验

日期：2026-10-15。

## 范围

只使用已确认的 Meta 测试账号 `2806375919473667`。
覆盖流量链接、商品目录销售、网站转化和 App Promotion 四个内置模板。
创建通过运行中的 HTTP Agent、注册 Tool、签名确认、白名单、幂等和审计执行，
没有直接调用 Provider client 绕过执行门禁。

模板仅要求用户填写广告系列名称、开始时间、结束时间和日预算。
Page、素材、定向、应用、Pixel、商品目录和商品集仍需在使用时重新查询校验，
预置 ID 本身不构成写入授权。

## 实测发现与修复

1. 模板仍将已预填的素材、定向和资源列为必填；App 的对象级字段又与已预填子字段重复。
   补齐 `required_input_fields`，保持四项输入，并保存一致的 App 推广对象。
2. 选择蓝图时只暴露创建 Tool，实际无法调用资源查询；原提示词还禁止这些查询。
   live 模式只增加当前 Tool schema 或蓝图声明的同渠道只读 lookup Tool，
   不扩展其他写操作，也不使用父级列表查询替代本次创建返回的 ID。
3. 纯对话查询产生的资源校验证据无法传给后续创建。
   在应用参数选择服务中保留有界、仅内存的签名证明，仍校验用户、租户、会话、
   当前账号、目标 Tool、字段、具体值和有效期；原前端显式 token 路径保持相同校验。
   模型无需接触或复制 token，离线/模拟结果不能生成证明。
4. Catalog 归属检查扫描前 1000 项，把列表外的有效模板目录误判为越权。
   增加精确目录 ID 查询，读取其 Business 归属并与凭证绑定的 Business 比较，
   不将 Business 凭证标识返回模型或写入模板。
5. Campaign 的目录引用错误地发送为顶层 `catalog_id`，没有建立真正的目录推广对象。
   适配为 Graph API 的 `promoted_object.product_catalog_id`。
6. 新加坡定向的真实创建缺少地区声明和身份参数。
   从当前测试账号已有 Ad Set 读取既有声明及受益人、付款人身份，
   在 Provider schema、序列化和三个新加坡模板中补齐。
   不生成新身份，也不将声明等同于 Meta 审核通过或业务合规认证。
7. 目录 Creative 没有传顶层 Product Set，导致轮播被解释为缺少图片。
   保留 Creative 的 `product_set_id`，不放入 `template_data`。
8. 转化模板缺少明确的 `targeting_automation.advantage_audience`；
   对照现有广告组补齐显式选择，不由模型猜测。
9. App 模板沿用了历史 HTTP 商店地址，与当前 App Creative 的 HTTPS 契约冲突。
   统一预置 Google Play URL 为 HTTPS，不改变应用 ID。
10. 页面选择模板后把首次初始化当作推广目标编辑，触发级联清空预置优化目标和计费事件。
    初始化改为无变更路径的评估；真实用户修改仍保留级联重置，并有前端回归测试。

## 证据

证据目录：`outputs/meta-template-e2e-20261015/`。

- `meta-traffic-native-final.json`：真实模型按模板完成签名确认及 Campaign、Ad Set、Ad 创建。
- `meta-traffic-native-readback.json`：真实 API 回查三个投放层级均为 PAUSED，Creative 存在。
- `meta-catalog-source-regional.json`、`meta-app-source-regional.json`：
  当前测试账号已有地区声明的来源。
- `meta-catalog-prefill-check.json`：精确 Catalog 及 Product Set 查询通过。
- `check_template_form.py`：复现页面的资源 picker 校验与正常聊天提交，
  所有写入仍经过平台确认；续建时明确指定已创建父级，限制可用写 Tool。

失败阶段、模型限流及参数错误均保留在同一目录，不计作成功。
早期失败留下的暂停父资源没有被自动删除、激活或冒充完整创建成功。
最终结果以创建记录和后续实际回查为准。

### 完整层级回查

以下均为真实 API 回查，不是将 Tool 的成功标记当作回查证据。
每条记录的 Campaign、Ad Set、Ad 均为 PAUSED，父子 ID 关联一致，Creative 存在。

| 模板 | Campaign | Ad Set | Ad | Creative |
| --- | --- | --- | --- | --- |
| 流量 | 120251900775700251 | 120251900776940251 | 120251900777680251 | 1824855241868636 |
| 目录销售 | 120251900772720251 | 120251900813550251 | 120251900832310251 | 1656661742492518 |
| 网站转化 | 120251900781220251 | 120251900831800251 | 120251900832340251 | 1061561130211320 |
| App 推广 | 120251900582820251 | 120251900814210251 | 120251900832380251 | 1395069802781116 |

对应 `meta-traffic-native-readback.json` 及三个 `meta-*-complete-readback.json`。
目录 Creative 的商品集、转化的 Pixel、App 的应用与商店 URL 均与模板相符。
四个内置模板的验证标记依据上述记录更新，不代表每种媒体变体或其他账号已验证。

### 对话与上游限制

流量的全新纯对话已完成创建及最终回复。其余类型也已通过页面同等的资源校验、
正常聊天提交、平台确认、续建及真实回查，不能把它们仅归类为 dry-run 验证。

另外保留了纯对话并发复测的失败：Catalog、Conversion 在确认后遭遇模型
`RateLimitError`；App 曾在 Campaign 创建后遇到相同限流。串行重试 Catalog 时，
三层创建 Tool 都成功，但最终模型回复仍被限流，因此 Run 的 `failed` 状态没有伪改为成功。
这些记录不能宣称为完整对话 Run 通过。外部资源可能已经创建，必须先回查，不能直接重试整条创建。

浏览器页面复测确认模板管理已显示四类 Meta 模板；重新加载流量模板后，
`LANDING_PAGE_VIEWS` 和 `IMPRESSIONS` 不再被初始化级联清空。
截图为 `meta-template-page.png`；只验证加载和参数，没有在页面点击真实创建确认。

## 边界与恢复

Campaign、Ad Set、Ad 的创建状态必须为 PAUSED；Creative 没有独立投放开关。
Meta 查询预算保留 Provider 的最小货币单位，API 值 `3000` 对应本次输入的 `30`，
不能将原始数值当作已换算的账户币种金额。

没有修改通用 Harness、另建 Runtime、增加 SQL 表或迁移历史会话。
新增 Provider 字段由闭合 schema 约束，签名证明不持久化，服务重启或证明过期后需重新查询。
全链路的权限、确认、幂等和审计保持原执行底座。

部署需重启以加载模板、schema 和上下文规则；回退需恢复这些代码与契约快照再重启。
回退不会删除已有外部资源，也不声称回滚 Provider 已成功执行的步骤。
沿用现有 Run 事件和 Provider HTTP 证据，不新建观察性链路。

最终 `make ad-agent-check` 完成编译、能力审计、310 个 Tool 契约快照校验，
1870 项 Agent 测试通过，保留 1 项依赖弃用警告；`git diff --check` 通过。
资源选择证明模块的专项行覆盖率为 86%，前端回归 37 项通过。
全仓 qguard 仍未通过，不能据此宣称整体质量门禁达标。
