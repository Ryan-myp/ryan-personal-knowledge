# 面试题库完整知识体系规划

## 一、Go语言 (目标30篇)

### 核心主题
1. Goroutine调度器(GMP模型)
2. Channel实现原理
3. Map并发安全
4. GC垃圾回收
5. 内存分配(Arena/Tcmalloc)
6. 栈内存管理
7. Interface底层实现
8. 反射机制
9. sync包深度解析
10. context机制
11. error handling
12. unsafe包使用
13. race detector
14. pprof性能分析
15. trace分析
16. net/http源码
17. io包设计
18. encoding/json
19. time包定时器
20. math/rand vs crypto/rand
21. 错误恢复机制
22. defer执行顺序
23. slice底层实现
24. string不可变性
25. map哈希冲突
26. mutex vs RWMutex
27. WaitGroup原理
28. Once单例模式
29. Cond条件变量
30. pool对象池

### 已覆盖
- ✅ 大部分在wiki/concepts/中
- ❌ 需要整理到interview/目录

---

## 二、系统设计 (目标25篇)

### 核心主题
1. 短链接系统
2. 分布式ID生成器
3. 消息队列设计
4. 分布式锁
5. 缓存系统设计
6. 搜索系统设计
7. 推荐系统设计
8. 实时竞价系统
9. 新闻Feed系统
10. 视频点播系统
11. 社交网络设计
12. 电商系统设计
13. 支付系统设计
14. 限流系统设计
15. 秒杀系统设计
16. 分布式事务
17. 一致性哈希
18. CAP定理权衡
19. 最终一致性
20. 分布式追踪
21. 服务发现
22. API网关设计
23. 微服务拆分
24. 数据分片策略
25. CDN设计

### 已覆盖
- ✅ interview-qa-expert-deep.md (新建)
- ❌ 大部分缺失

---

## 三、数据库 (目标20篇)

### 核心主题
1. MySQL索引优化
2. MySQL执行计划
3. MySQL事务隔离
4. MySQL锁机制
5. MySQL MVCC
6. MySQL复制延迟
7. MySQL分库分表
8. MySQL读写分离
9. MySQL性能调优
10. Redis数据结构
11. Redis持久化
12. Redis集群
13. Redis哨兵
14. Redis缓存策略
15. Redis热点Key
16. Redis大Key问题
17. Elasticsearch原理
18. Elasticsearch查询优化
19. ClickHouse列式存储
20. TiDB分布式架构

### 已覆盖
- ✅ 大部分在wiki/concepts/中
- ❌ 需要整理到interview/目录

---

## 四、分布式系统 (目标15篇)

### 核心主题
1. Raft共识算法
2. Paxos算法
3. ZAB协议
4. 分布式事务(TwoPC/ThreePC)
5. TCC事务
6. Saga模式
7. 分布式锁实现
8. 分布式缓存一致性
9. 分布式追踪
10. 服务网格
11. 服务熔断降级
12. 限流算法
13. 幂等性设计
14. 异步消息保证
15. 分布式配置中心

### 已覆盖
- ❌ 大部分缺失

---

## 五、广告系统 (目标20篇)

### 核心主题
1. 广告竞价原理
2. RTB实时竞价
3. RTA实时适配
4. 出价策略(OCPM/OCPC)
5. 频控策略
6. 归因模型
7. 创意审核
8. 广告排序
9. eCPM计算
10. 质量度计算
11. 预算控制
12. 反作弊系统
13. 广告位管理
14. 投放定向
15. 创意优化
16. 人群包管理
17. 动态创意
18. 素材管理
19. 效果评估
20. A/B测试

### 已覆盖
- ✅ bidding-system-expert-deep.md
- ✅ rta-implementation-deep.md
- ✅ ssp-implementation-deep.md
- ✅ dsp-timeout-control-deep.md
- ❌ 大部分缺失

---

## 六、Agent/AI (目标20篇)

### 核心主题
1. LLM基本原理
2. Transformer架构
3. 提示工程
4. RAG系统
5. 向量数据库
6. Embedding模型
7. 微调方法(LoRA/QLoRA)
8. Agent框架对比
9. 工具调用设计
10. 记忆系统
11. 多Agent协作
12. 评估方法
13. 幻觉问题
14. 安全护栏
15. 多模态理解
16. 推理优化
17. 模型量化
18. 边缘AI部署
19. MCP协议
20. Agent测试

### 已覆盖
- ✅ 部分在agent-ai/目录
- ❌ 需要整理到interview/目录

---

## 七、前端开发 (目标15篇)

### 核心主题
1. React hooks原理
2. Virtual DOM
3. Fiber架构
4. 状态管理(Zustand/Redux)
5. 性能优化
6. SSR/SSG
7. TypeScript高级类型
8. 微前端架构
9. Webpack/Vite配置
10. Bundles优化
11. Code Splitting
12. 懒加载
13. PWA
14. Web Worker
15. 跨域解决方案

### 已覆盖
- ✅ 部分在fullstack/目录
- ❌ 需要整理到interview/目录

---

## 八、架构设计 (目标15篇)

### 核心主题
1. 微服务架构
2. 事件驱动架构
3. DDD领域驱动设计
4. CQRS模式
5. 服务网格
6. API Gateway
7. 消息队列选型
8. 缓存架构
9. 数据库选型
10. 高可用设计
11. 高并发设计
12. 可扩展性设计
13. 容错设计
14. 安全架构
15. 可观测性架构

### 已覆盖
- ❌ 大部分缺失

---

## 九、DevOps (目标10篇)

### 核心主题
1. CI/CD流程
2. Kubernetes
3. Docker
4. Terraform
5. Prometheus
6. ELK
7. 混沌工程
8. GitOps
9. 基础设施即代码
10. 成本优化

### 已覆盖
- ✅ devops-cicd-expert-deep.md (新建)
- ✅ monitoring-alerting-expert-deep.md (新建)
- ❌ 大部分缺失

---

## 十、综合实战 (目标10篇)

### 核心主题
1. 设计一个完整的广告系统
2. 设计一个推荐系统
3. 设计一个即时通讯系统
4. 设计一个电商系统
5. 设计一个社交媒体
6. 设计一个视频平台
7. 设计一个游戏后端
8. 设计一个物联网平台
9. 设计一个金融系统
10. 设计一个机器学习平台

### 已覆盖
- ❌ 缺失

---

## 合计目标: 180篇
## 当前覆盖: ~8篇
## 需要新增: 172篇
