# 系统设计面试题库

> **文档级别**: Level 4  
> **创建日期**: 2026-08-13  
> **状态**: ✅ 已创建

---

## 一、基础设计题

### Q1: 如何设计一个短链接服务？

```
设计方案:
├── 存储选型
│   ├── Redis: 热点数据 (TTL)
│   ├── MySQL: 持久化存储
│   └── KV Store: 分布式存储
│
├── ID 生成
│   ├── 自增 ID + Base62 编码
│   ├── 雪花算法
│   └── 分布式 ID 服务
│
└── 重定向
    ├── 301 永久重定向
    ├── 302 临时重定向
    └── JS 跳转 (兼容旧浏览器)
```

### Q2: 如何设计一个秒杀系统？

```
架构设计:
├── 流量控制
│   ├── Nginx 限流
│   ├── Redis 预减库存
│   └── 消息队列削峰
│
├── 库存扣减
│   ├── Lua 脚本原子操作
│   ├── 分布式锁
│   └── 最终一致性
│
└── 订单处理
    ├── 异步下单
    ├── 支付回调
    └── 超时取消
```

---

## 二、参考资料

```
核心资源:
├── System Design Primer: https://github.com/donnemartin/system-design-primer
├── Grokking System Design: https://www.educative.io/courses/grokking-system-design
└── High Scalability: http://highscalability.com/
```

---

*文档版本: v1.0*  
*最后更新: 2026-08-13*  
*作者: Ryan*
