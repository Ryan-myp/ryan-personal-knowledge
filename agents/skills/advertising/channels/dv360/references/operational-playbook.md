# DV360 操作清单

## 媒体购买 Preflight

```text
partner / advertiser scope
  -> Campaign / IO / Line Item parent
  -> budget + flight + buying type
  -> targeting option lookup / assignment diff
  -> creative format + approval
  -> schema + permission + dry-run
  -> confirmation + idempotency + readback
```

对每次变更保存：advertiser、父级资源、目标层级、预算/币种、开始结束时间、采购类型、
定向变更、创意审批状态和当前 Tool contract version。

## Report 生命周期

```text
definition requested -> definition accepted -> report running -> result ready/failed
```

查询前确认 advertiser、日期/时区、维度、指标、过滤、币种和 freshness。把 definition、
异步运行、result 可读和数据最终结算分开报告；轮询必须有超时和取消/重试边界。

## 创意审批

- 校验 advertiser、格式、尺寸、时长、媒体引用和落地页；
- 分开记录 uploaded、associated、pending、approved、rejected；
- reject 只做修订/重新审核计划，不重复创建绕过政策；
- 未注册格式或模板明确标记为 unsupported。

## 失败恢复

未知写入状态先 readback；已存在资源则转为核对或更新。异步报告失败要保留 definition/result
关联和安全错误摘要，不能把超时描述为“没有数据”。
