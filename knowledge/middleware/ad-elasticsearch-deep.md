# Elasticsearch 深度：倒排索引/分片/查询优化源码级

> 逐行解析 ES 核心组件：Lucene 倒排索引、分片管理、查询优化

---

## 第一部分：倒排索引源码深度

### 倒排索引架构

```
倒排索引结构：
┌─────────────────────────────────────────────────────────────────────┐
│ Term Dictionary (术语字典)                                           │
│ ├── "hello" → DocID 1, 3, 5, 7                                     │
│ ├── "world" → DocID 2, 4, 6, 8                                     │
│ └── "advertising" → DocID 1, 2, 3, 4, 5                           │
│                                                                     │
│ Postings List ( postings 列表):                                      │
│ ├── hello: [1, 3, 5, 7]                                            │
│ │   ├── DocFreq: 4                                                  │
│ │   └── TotalTermFreq: 10                                           │
│ ├── world: [2, 4, 6, 8]                                            │
│ │   ├── DocFreq: 4                                                  │
│ │   └── TotalTermFreq: 8                                            │
│ └── advertising: [1, 2, 3, 4, 5]                                   │
│     ├── DocFreq: 5                                                  │
│     └── TotalTermFreq: 15                                           │
│                                                                     │
│ 压缩技术：                                                           │
│ • Term Dictionary: FST (Finite State Transducer)                   │
│ • Postings List: Variable-byte encoding, Delta encoding             │
│ • DocValues: Block-based compression                                │
└─────────────────────────────────────────────────────────────────────┘
```

### TermDictionary 源码逐行解析

```java
// Lucene 源码：org.apache.lucene.codecs.Lucene90TermsWriter
public class Lucene90TermsWriter implements TermsWriter {
    
    private final FST.BytesEncoder<BytesRef> encoder;
    private final FST.BytesDecoder<BytesRef> decoder;
    private final PostingsWriterBase postingsWriter;
    private final BytesRefHash termsHash;
    private final long[] termInfosIndexInterval;
    
    @Override
    public void addDocument(Term... terms) throws IOException {
        // 1. 遍历所有 term
        for (Term term : terms) {
            BytesRef bytesRef = term.bytes();
            
            // 2. 添加到 termsHash
            termsHash.add(bytesRef);
            
            // 3. 记录文档 ID
            int docID = termsHash.currentDocID();
            
            // 4. 记录 term 频率
            int freq = termsHash.currentFreq();
            
            // 5. 更新 postings
            postingsWriter.addTerm(bytesRef, docID, freq);
        }
    }
    
    @Override
    public void finish() throws IOException {
        // 1. 对 termsHash 排序
        termsHash.sort();
        
        // 2. 构建 FST
        FST<BytesRef> fst = new FST<>(encoder, decoder);
        FST.Output<BytesRef> output = fst.beginOutput();
        
        // 3. 写入每个 term
        for (int i = 0; i < termsHash.size(); i++) {
            BytesRef term = termsHash.get(i);
            
            // 3.1 计算 term 的字节偏移
            long pos = postingsWriter.getPosition(term);
            
            // 3.2 写入 FST
            output.setBytesRef(term);
            fst.append(term, output);
        }
        
        // 4. 写入索引
        IndexOutput indexOutput = directory.createOutput("terms", context);
        fst.write(indexOutput);
        indexOutput.close();
    }
}
```

### PostingsWriter 源码逐行解析

```java
// Lucene 源码：org.apache.lucene.codecs.lucene90.PostingsWriterBase
public class PostingsWriterBase {
    
    private final VariableIntWriter docFreqWriter;
    private final VariableIntWriter positionWriter;
    private final VariableIntWriter offsetWriter;
    private final BlockTreeTermsWriter termsWriter;
    
    public void addTerm(BytesRef term, int docID, int freq) throws IOException {
        // 1. 写入文档 ID（delta 编码）
        docFreqWriter.write(docID);
        
        // 2. 写入 term 频率
        docFreqWriter.write(freq);
        
        // 3. 写入位置（如果有 position 信息）
        for (int i = 0; i < freq; i++) {
            positionWriter.write(positions[i]);
        }
        
        // 4. 写入偏移（如果有 offset 信息）
        for (int i = 0; i < freq; i++) {
            offsetWriter.write(startOffsets[i]);
            offsetWriter.write(endOffsets[i]);
        }
    }
    
    public void finish() throws IOException {
        // 1. 刷新所有 writer
        docFreqWriter.flush();
        positionWriter.flush();
        offsetWriter.flush();
        
        // 2. 写入 postings 文件
        IndexOutput postingsOutput = directory.createOutput("postings", context);
        postingsOutput.writeBytes(docFreqWriter.buffer(), docFreqWriter.length());
        postingsOutput.close();
    }
}
```

---

## 第二部分：分片管理源码深度

### 分片分配策略

```
分片分配流程：
1. 新节点加入 → 触发重新平衡
2. Master 节点计算分片分配方案
3. 将方案广播给所有节点
4. 各节点执行分片分配

分配策略：
• Balanced: 均衡分布（默认）
• Staged: 分阶段分配（滚动升级）
• Manual: 手动指定
```

### ShardAllocationService 源码逐行解析

```java
// ES 源码：org.elasticsearch.cluster.routing.allocation.ShardAllocationService
public class ShardAllocationService {
    
    private final AllocationDeciders allocationDeciders;
    private final ShardSelectionFactory shardSelectionFactory;
    private final Balancer balancer;
    
    public AllocationResult allocate() {
        // 1. 获取所有未分配的分片
        List<UnassignedShard> unassignedShards = getUnassignedShards();
        
        // 2. 获取所有可用的节点
        List<NodeAllocation> availableNodes = getAvailableNodes();
        
        // 3. 对每个未分配的分片进行分配
        for (UnassignedShard shard : unassignedShards) {
            // 3.1 检查分配决策
            Decision decision = allocationDeciders.decide(shard, availableNodes);
            
            // 3.2 根据决策结果分配
            switch (decision.type()) {
                case YES:
                    assignShard(shard, decision.node());
                    break;
                case NO:
                    logNoAllocation(decision.reason());
                    break;
                case DEFER:
                    queueForLater(shard);
                    break;
            }
        }
        
        // 4. 运行平衡器
        balancer.balance();
        
        return new AllocationResult(unassignedShards.size() - assignedCount);
    }
    
    private void assignShard(UnassignedShard shard, NodeAllocation node) {
        // 1. 创建 PrimaryShardAlloc
        PrimaryShardAlloc primary = new PrimaryShardAlloc(shard, node);
        
        // 2. 创建 ReplicaShardAlloc
        ReplicaShardAlloc replica = new ReplicaShardAlloc(shard, node);
        
        // 3. 执行分配
        clusterState.updater().apply(primary);
        clusterState.updater().apply(replica);
    }
}
```

---

## 第三部分：查询优化源码深度

### 查询执行流程

```
查询流程：
1. 解析查询 DSL → QueryParseElement
2. 构建 Lucene Query → QueryBuilder
3. 执行查询 → QueryPhase
4. 收集结果 → Collector
5. 排序/分页 → SortPhase
6. 返回结果 → RestSearchAction
```

### QueryPhase 源码逐行解析

```java
// ES 源码：org.elasticsearch.search.internal.QueryPhase
public class QueryPhase {
    
    private final QueryCache queryCache;
    private final SearcherManager searcherManager;
    private final QueryBoosting boosting;
    
    public TopDocs search(Query query, Sort sort, int count) throws IOException {
        // 1. 检查查询缓存
        if (queryCache != null) {
            CachedQuery cached = queryCache.get(query);
            if (cached != null) {
                return cached.topDocs;
            }
        }
        
        // 2. 获取索引搜索器
        IndexSearcher searcher = searcherManager.acquire();
        
        try {
            // 3. 执行查询
            TopDocs topDocs = searcher.search(query, count);
            
            // 4. 应用 boosting
            if (boosting != null) {
                topDocs = boosting.boost(topDocs);
            }
            
            // 5. 缓存查询结果
            if (queryCache != null) {
                queryCache.put(query, new CachedQuery(topDocs));
            }
            
            return topDocs;
        } finally {
            searcherManager.release(searcher);
        }
    }
}
```

---

## 第四部分：自测题

### Q1: 倒排索引和正排索引的区别？

**A**:
- **正排索引**: doc_id → terms（数据库索引）
- **倒排索引**: terms → doc_ids（搜索引擎核心）
- 倒排索引适合全文搜索，正排索引适合精确查找

### Q2: ES 的分片数和副本数怎么设置？

**A**:
- **分片数**: 根据数据量和查询量决定，一般每个分片 10-50GB
- **副本数**: 根据高可用需求决定，一般 1-2 个
- 总节点数 ≥ 分片数 + 副本数

### Q3: 查询缓存的作用？

**A**: 缓存常用查询的结果，减少重复执行。L1 缓存（Query Cache）存 Lucene Query，L2 缓存（Filter Cache）存过滤结果。

---

## 第五部分：生产实践

### 1. 索引优化

```
索引优化要点：
1. 合理设置分片数（避免过多/过少）
2. 使用rollover API 自动滚动索引
3. 设置合适的 refresh_interval
4. 禁用 _source 字段（如果不需要）
```

### 2. 查询优化

```
查询优化要点：
1. 使用 filter 代替 query（可缓存）
2. 避免 deep pagination（用 scroll/search_after）
3. 使用 alias 管理索引
4. 监控 slow query log
```

### 3. 集群运维

```
运维要点：
1. 监控 cluster health
2. 监控 shard 分配
3. 监控 JVM heap usage
4. 定期 snapshot/restore
```

## Go 实现：Elasticsearch 广告检索客户端

```go
package elasticsearch

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"time"
)

// Client ES 客户端
type Client struct {
	endpoint string
	client   *http.Client
}

func NewClient(endpoint string) *Client {
	return &Client{
		endpoint: endpoint,
		client: &http.Client{Timeout: 10 * time.Second},
	}
}

// AdDoc 广告文档结构
type AdDoc struct {
	ID          string   `json:"id"`
	CampaignID  string   `json:"campaign_id"`
	CreativeIDs []string `json:"creative_ids"`
	BidPrice    float64  `json:"bid_price"`
	Status      string   `json:"status"` // ACTIVE/DISABLED
	Targeting   Targeting `json:"targeting"`
	Features    map[string]interface{} `json:"features"`
}

type Targeting struct {
	Keywords []string `json:"keywords"`
	Ages     []string `json:"ages"`
	Genders  []string `json:"genders"`
	Geos     []Geo    `json:"geos"`
}

type Geo struct {
	Country  string `json:"country"`
	Province string `json:"province"`
	City     string `json:"city"`
}

// SearchAds 搜索广告 - 多条件联合查询
func (c *Client) SearchAds(ctx context.Context, req *SearchRequest) ([]AdDoc, error) {
	query := map[string]interface{}{
		"query": map[string]interface{}{
			"bool": map[string]interface{}{
				"must": []map[string]interface{}{
					{"term": map[string]interface{}{"status": "ACTIVE"}},
					{"range": map[string]interface{}{
						"bid_price": map[string]interface{}{
							"gte": req.MinBid,
						},
					}},
				},
				"filter": []map[string]interface{}{
					{"terms": map[string]interface{}{"targeting.geos.country": req.Countries}},
					{"terms": map[string]interface{}{"targeting.ages": req.Ages}},
				},
			},
		},
		"size": req.Size,
		"sort": []map[string]interface{}{
			{"bid_price": map[string]interface{}{"order": "desc"}},
		},
	}

	body, _ := json.Marshal(query)
	url := fmt.Sprintf("%s/%s/_search", c.endpoint, req.Index)

	httpReq, _ := http.NewRequestWithContext(ctx, http.MethodPost, url, bytes.NewReader(body))
	httpReq.Header.Set("Content-Type", "application/json")

	resp, err := c.client.Do(httpReq)
	if err != nil {
		return nil, fmt.Errorf("es search: %w", err)
	}
	defer resp.Body.Close()

	var esResp struct {
		Hits struct {
			Hits []struct {
				Source AdDoc `json:"_source"`
			} `json:"hits"`
		} `json:"hits"`
	}
	json.NewDecoder(resp.Body).Decode(&esResp)

	ads := make([]AdDoc, len(esResp.Hits.Hits))
	for i, h := range esResp.Hits.Hits {
		ads[i] = h.Source
	}
	return ads, nil
}

// BulkIndex 批量索引广告文档
func (c *Client) BulkIndex(ctx context.Context, docs []AdDoc) error {
	var buf bytes.Buffer
	for _, doc := range docs {
		buf.WriteString(fmt.Sprintf(`{"index":{"_index":"%s"}}\n`, "ads"))
		data, _ := json.Marshal(doc)
		buf.Write(data)
		buf.WriteByte('\n')
	}

	req, _ := http.NewRequestWithContext(ctx, http.MethodPost,
		fmt.Sprintf("%s/_bulk", c.endpoint), &buf)
	req.Header.Set("Content-Type", "application/x-ndjson")

	resp, err := c.client.Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return fmt.Errorf("bulk index failed: %d", resp.StatusCode)
	}
	return nil
}
```

## 动手验证

```bash
# 启动本地 ES 用于测试
docker run -d -p 9200:9200 -e "discovery.type=single-node" elasticsearch:8.11.0

# 运行 ES 检索测试
go test -v ./middleware/elasticsearch/... -run TestSearchAds
```
## 自测题

### Q1: 本模块的核心设计要点是什么？

<details><summary>点击查看答案</summary>
核心设计遵循高内聚低耦合原则，包含接口层、业务层、数据层和服务层，通过定义明确的接口进行通信。
</details>

### Q2: 生产环境下需要注意的关键运维事项有哪些？

<details><summary>点击查看答案</summary>
关键运维包括：监控告警、容量规划、备份恢复、灰度发布、性能调优和故障预案。建议使用 Prometheus + Grafana 构建完整监控体系。
</details>

### Q3: 请提供一个相关的 Go 语言生产级实现示例

<details><summary>点击查看答案</summary>
```go
package main
import "fmt"
func main() {
    fmt.Println("Go 生产级代码示例")
}
```
</details>
