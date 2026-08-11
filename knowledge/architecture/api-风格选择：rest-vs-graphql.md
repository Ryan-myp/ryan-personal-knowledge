# API 风格选择：REST vs GraphQL

**状态**: proposed
**日期**: 2026-08-11

## 上下文

- 需要为业务系统提供数据访问接口

- 团队熟悉 REST 风格，学习成本低

- GraphQL 适合复杂查询场景，但增加运维复杂度

## 决策

采用 RESTful API 作为主要接口风格，GraphQL 作为补充。

## 影响

- ✅ REST 接口简单，易于理解和调试
- ✅ GraphQL 查询灵活，减少接口变更
- ✅ REST 缓存友好，性能可控
- ⚠️ GraphQL 学习曲线陡峭
- ✅ REST 版本管理简单

## 参考

- REST API Design Guide
- GraphQL Best Practices
