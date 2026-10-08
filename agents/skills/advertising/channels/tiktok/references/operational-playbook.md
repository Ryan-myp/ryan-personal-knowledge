# TikTok Ads 操作清单

## 创建前 Preflight

```text
advertiser scope
  -> objective / campaign type
  -> ad group budget / schedule / optimization / bid
  -> targeting lookup
  -> asset / identity / pixel / catalog dependencies
  -> format schema + policy
  -> dry-run / confirmation / idempotency
```

动态字段必须记录 lookup 来源和账户范围；素材、identity、Pixel、catalog、product set 的
ID 要区分所有权与生命周期。

## Spark 检查

- creator/item/post 是否已授权给目标 advertiser；
- Spark 引用与普通上传视频字段不能混用；
- 原生互动、评论、授权有效期和 tracking 要在结果中单独说明；
- 未授权不能自动切换格式绕过阻塞。

## 报表与事件检查

- 报表先锁定 level、日期、时区、币种、维度和归因窗口；
- 视频观看、安装、转化和购买价值按 objective/归因口径解释；
- Pixel/CAPI 保持 event_id、事件命名、时间单位和 action source 一致；
- 事件接收、匹配、去重、归因和可见性是不同状态。

## 失败恢复

超时或未知状态先 readback；批量结果逐项保存。对限流做有界退避，对参数/权限/资产问题
停止重试并返回可操作的缺口。
