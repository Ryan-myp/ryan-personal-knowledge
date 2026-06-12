# 系统设计实战：广告/搜索/推荐/即时通讯

> 从需求到架构：广告竞价系统 / 推荐引擎 / 搜索系统 / IM 系统

---

## 第一部分：入门引导（5 分钟速览）

### 什么是系统设计？

系统设计是将业务需求转化为技术架构的过程。核心要素：
1. **需求分析**：功能需求、性能需求、容量估算
2. **高层架构**：服务划分、数据流、部署拓扑
3. **详细设计**：API 设计、数据库 schema、缓存策略
4. **性能评估**：瓶颈分析、优化方案

### 广告平台系统规模

| 指标 | 量级 | 说明 |
|------|------|------|
| QPS | 100 万+ | 实时竞价 |
| 日活用户 | 1 亿+ | 广告平台用户 |
| 日曝光 | 100 亿+ | 广告曝光日志 |
| 数据量 | PB 级 | 历史数据 |
| 延迟 | < 100ms | 竞价 RTT |

---

## 第二部分：广告竞价系统设计

### 2.1 需求分析

```
功能需求：
- 广告主创建广告计划
- 广告位申请曝光
- 竞价引擎计算出价
- 广告主扣减预算
- 曝光日志上报

性能需求：
- 竞价 RTT < 100ms（P99）
- 可用性 99.99%
- 预算扣减强一致
```

### 2.2 架构设计

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   Ad Server  │────▶│  Bid Engine  │────▶│  Budget Svc  │
│  (API Gateway)│    │  (竞价引擎)    │    │  (预算扣减)    │
└──────────────┘     └──────────────┘     └──────────────┘
                           │                       │
                           ▼                       ▼
                    ┌──────────────┐     ┌──────────────┐
                    │   Redis      │     │    MySQL     │
                    │  (实时数据)    │     │  (预算数据)    │
                    └──────────────┘     └──────────────┘
                           │
                           ▼
                    ┌──────────────┐
                    │   Kafka      │
                    │  (日志上报)    │
                    └──────────────┘
```

### 2.3 Go 竞价引擎核心代码

```go
package bidengine

type BidEngine struct {
    rcmd  *RCache        // 召回缓存
    rank  *Ranker        // 排序模型
    budget *BudgetChecker // 预算检查
}

func (be *BidEngine) HandleBid(ctx context.Context, req *BidRequest) (*BidResponse, error) {
    // 1. 召回
    candidates := be.rcmd.Retrieve(ctx, req.UserProfile)
    
    // 2. 过滤
    candidates = be.budget.Filter(ctx, candidates)
    
    // 3. 排序
    results := be.rank.Score(ctx, candidates)
    
    // 4. 竞价
    winner := results[0]
    bidPrice := be.calculateSecondPrice(results)
    
    // 5. 扣减预算
    be.budget.Deduct(ctx, winner.AdID, bidPrice)
    
    return &BidResponse{
        AdID:    winner.AdID,
        Price:   bidPrice,
        Latency: time.Since(startTime).Milliseconds(),
    }, nil
}
```

---

## 第三部分：推荐系统设计

### 3.1 推荐系统架构

```
召回层（Recall） → 粗排 → 精排 → 重排 → 曝光

召回（1000+ 候选）：
- 基于用户行为的协同过滤
- 基于内容的推荐
- 基于热门趋势的推荐

粗排（100 候选）：
- 轻量级模型，快速筛选

精排（10 候选）：
- 复杂模型，精确打分

重排（5 候选）：
- 去重、多样性、业务规则
```

### 3.2 Go 实现召回层

```go
type RecallEngine struct {
    userCF  *UserCFRecall
    content *ContentRecall
    hot     *HotRecall
}

func (re *RecallEngine) Recall(ctx context.Context, userID string) []*Candidate {
    var candidates []*Candidate
    
    // 用户协同过滤
    if cands := re.userCF.Recall(ctx, userID); len(cands) > 0 {
        candidates = append(candidates, cands...)
    }
    
    // 内容推荐
    if cands := re.content.Recall(ctx, userID); len(cands) > 0 {
        candidates = append(candidates, cands...)
    }
    
    // 热门推荐
    if cands := re.hot.Recall(ctx, userID); len(cands) > 0 {
        candidates = append(candidates, cands...)
    }
    
    // 去重
    return dedup(candidates)
}
```

---

## 第四部分：搜索系统设计

### 4.1 搜索引擎架构

```
用户搜索 → 查询解析 → 倒排索引查找 → 排序 → 返回结果

查询解析：
- 分词（分词器）
- 同义词扩展
- 拼写纠错

倒排索引：
- 词 → 文档列表
- 支持 AND/OR/NOT 查询

排序：
- BM25 相关性
- 广告竞价加权
- 个性化排序
```

### 4.2 Go 实现简单搜索引擎

```go
type SearchEngine struct {
    index *InvertedIndex
}

type InvertedIndex struct {
    terms map[string]*TermDocList
}

type TermDocList struct {
    docs map[string]*DocInfo
}

func (se *SearchEngine) Search(query string) ([]*Document, error) {
    // 1. 分词
    terms := segment(query)
    
    // 2. 倒排索引查询
    var candidates []*Document
    for _, term := range terms {
        docList, ok := se.index.Get(term)
        if ok {
            candidates = append(candidates, docList.Docs()...)
        }
    }
    
    // 3. 排序
    sortByRelevance(candidates)
    
    return candidates, nil
}
```

---

## 第五部分：即时通讯系统设计

### 5.1 IM 系统架构

```
用户 → TCP/WS 长连接 → 消息网关 → 消息路由 → 存储 → 下发

核心挑战：
- 百万级长连接
- 消息不丢不重
- 低延迟推送
- 离线消息
```

### 5.2 Go 实现长连接网关

```go
type Gateway struct {
    connections map[string]*Client
    mu          sync.RWMutex
}

func (gw *Gateway) OnConnect(ws *websocket.Conn) {
    client := &Client{
        WS:      ws,
        OutChan: make(chan []byte, 1000),
    }
    
    gw.mu.Lock()
    gw.connections[client.ID] = client
    gw.mu.Unlock()
    
    // 处理消息
    for {
        msg, err := ws.ReadMessage()
        if err != nil {
            gw.removeClient(client.ID)
            return
        }
        gw.handleMessage(client.ID, msg)
    }
}
```

---

## 第六部分：自测题

### 问题 1
如何设计一个支持百万 QPS 的广告竞价系统？

<details>
<summary>查看答案</summary>

1. **服务分层**：召回 → 过滤 → 排序 → 竞价
2. **缓存层**：Redis 存储用户画像、预算数据
3. **异步处理**：日志通过 Kafka 异步上报
4. **水平扩展**：无状态服务 + 负载均衡
5. **Go 优化**：gRPC 通信、连接池、对象池
6. **容灾**：多活部署、故障自动转移

</details>

### 问题 2
推荐系统如何冷启动？

<details>
<summary>查看答案</summary>

1. **热门推荐**：新用户/新内容 → 热门列表
2. **基于内容**：新用户偏好 → 内容属性匹配
3. **社交推荐**：好友偏好
4. **探索与利用**：ε-greedy、Bandit 算法
5. **Go 实现**：多路召回融合权重

</details>

### 问题 3
IM 系统如何保证消息不丢不重？

<details>
<summary>查看答案</summary>

1. **消息 ID**：全局唯一 ID（Snowflake）
2. **ACK 机制**：客户端收到后返回 ACK
3. **持久化**：消息写入 MySQL + Redis 缓存
4. **去重**：客户端记录已读消息 ID 列表
5. **离线消息**：客户端上线后拉取未读消息
6. **Go 实现**：channel + goroutine 异步处理

</details>

---

*本文档基于系统设计最佳实践整理，结合广告平台实战场景。*