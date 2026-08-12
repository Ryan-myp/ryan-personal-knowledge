---
name: ad-dsp-architecture-expert
description: "DSP 架构专家技能 — 高并发竞价引擎、低延迟优化、预算追踪、容灾降级"
version: 1.0.0
author: ryan
tags: [advertising, dsp, architecture, high-concurrency, expert]
---

# DSP 架构专家技能

> 从竞价引擎到全链路架构，掌握生产级 DSP 系统设计

## 核心能力

### 1. 竞价引擎
- **实时竞价流程**：请求接收 → 用户画像 → 出价决策 → 响应返回
- **延迟控制**：P99 < 100ms，端到端 < 200ms
- **并发模型**：goroutine 池、无锁数据结构、本地缓存
- **降级策略**：超时保护、默认出价、 fallback 策略

### 2. 用户画像
- **实时特征**：上下文信息、当前会话
- **离线特征**：历史行为、用户标签
- **特征存储**：Redis / HBase / ClickHouse
- **特征同步**：DMP 数据回流、实时更新

### 3. 预算追踪
- **日预算**：全局预算 + 分时段预算
- **频次控制**：滑动窗口、bloom filter
- **频控策略**：用户级 / 广告主级 / 创意级
- **预算超投防护**：预扣机制、异步对账

### 4. 容灾与监控
- **多级降级**：画像降级 → 规则出价 → 默认出价
- **熔断机制**：依赖服务熔断、超时熔断
- **监控指标**：QPS、延迟、中标率、ROI
- **告警体系**：P0/P1/P2 分级告警

## 知识库引用

| 主题 | 文档 |
|------|------|
| DSP 架构 | `knowledge/advertising/ad-dsp-architecture-deep.md` |
| 系统设计 | `knowledge/fullstack/weread-system-design-deep.md` |
| DSP 核心引擎 | `knowledge/advertising/ad-dsp-core-engine-deep.md` |
| 高并发设计 | `knowledge/advertising/dsp-high-concurrency-design-deep.md` |
| DSP 系统深度 | `knowledge/advertising/dsp-system-deep-v3.md` |
| 并发限制 | `knowledge/advertising/ad-dsp-concurrency-limit.md` |
| 限流策略 | `knowledge/advertising/ad-dsp-throttling-strategy.md` |
| 并行查询 | `knowledge/advertising/dsp-parallel-query-deep.md` |
| 内存查询 | `knowledge/advertising/dsp-memory-query-deep.md` |

## 使用场景

### 场景 1: 设计 DSP 竞价引擎
1. 参考 `knowledge/advertising/dsp-high-concurrency-design-deep.md`
2. 设计请求处理 pipeline
3. 实现预算追踪和频控
4. 设计降级策略

### 场景 2: 排查竞价延迟问题
1. 查看 `knowledge/advertising/ad-dsp-high-concurrency-case-deep.md`
2. 分析链路追踪数据
3. 定位瓶颈环节（画像 / 模型 / 决策）
4. 应用优化策略

### 场景 3: 预算超投排查
1. 查看 `knowledge/advertising/ad-budget-overrun-warning-v2.md`
2. 检查预算追踪逻辑
3. 验证异步对账机制
4. 加强预扣机制

## 关键架构决策

```
请求入口 → API Gateway → Bid Handler
                              ├── 用户画像查询 (Redis/HBase)
                              ├── 规则引擎 (频控/预算)
                              ├── 模型推理 (pCTR/pCVR)
                              ├── 出价决策
                              └── 响应返回

关键约束：
- 总延迟预算: 100ms (P99)
- 画像查询: < 5ms
- 模型推理: < 20ms
- 决策逻辑: < 5ms
```

## 自测题

<details>
<summary>Q1: DSP 如何处理高并发下的预算追踪？</summary>

**答案**：
1. **本地缓存 + 异步同步**：每个实例维护本地预算计数器，定期同步到 Redis
2. **预扣机制**：出价前预扣预算，中标后确认，未中标退款
3. **分段预算**：按小时/分钟分段，降低精度需求
4. **分布式锁**：关键操作使用 Redis SETNX 或 etcd 锁
5. **最终一致性**：接受短时超投，通过事后对账修正

</details>

<details>
<summary>Q2: DSP 降级策略的优先级是怎样的？</summary>

**答案**：
1. **第一级**：画像查询失败 → 使用默认画像（最近一次 + 静态标签）
2. **第二级**：模型推理失败 → 使用规则出价（固定出价策略）
3. **第三级**：规则引擎失败 → 使用基础出价（最低价 + 质量分调整）
4. **第四级**：全部失败 → 拒绝请求或返回默认响应

</details>

<details>
<summary>Q3: 如何设计一个抗雪崩的 DSP 系统？</summary>

**答案**：
1. **限流**：API Gateway 层限流 + 业务层令牌桶
2. **熔断**：依赖服务熔断（hystrix/resilience4j 模式）
3. **降级**：核心功能降级（画像→规则→默认）
4. **隔离**：线程池隔离、信号量隔离
5. **压测**：常态化压测 + 混沌工程

</details>
