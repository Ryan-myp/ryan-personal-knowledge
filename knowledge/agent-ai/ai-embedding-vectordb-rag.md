# AI 实战：Embedding 模型/向量检索/微调

> Embedding 原理/HNSW 索引/Milvus/Pinecone/Fine-tuning 实战

---

## 第一部分：入门引导（5 分钟速览）

### Embedding 是什么？

```
文本 → 高维向量 → 语义相似度计算

"手机" → [0.12, -0.34, 0.56, ...]
"智能手机" → [0.11, -0.33, 0.55, ...]
余弦相似度 ≈ 0.99 → 语义相似
```

---

## 第二部分：Embedding 模型

### 2.1 Embedding 原理

```
输入文本 → Tokenizer → Embedding Layer → Transformer → 输出向量
```

### 2.2 Go 实现 Embedding

```go
package embedding

import (
    "math"
    "vector"
)

type EmbeddingModel interface {
    Encode(text string) ([]float64, error)
    Dim() int
}

type TextEmbedding struct {
    model     *Model
    dim       int
    tokenizer *Tokenizer
}

func (te *TextEmbedding) Encode(text string) ([]float64, error) {
    // 1. 分词
    tokens := te.tokenizer.Encode(text)
    
    // 2. Token Embedding + Position Embedding
    tokenVecs := te.model.TokenEmbed(tokens)
    posVecs := te.model.PositionEmbed(len(tokens))
    
    // 3. 平均池化
    result := make([]float64, te.dim)
    for _, tv := range tokenVecs {
        for i, v := range tv {
            result[i] += v
        }
    }
    for i := range result {
        result[i] /= float64(len(tokenVecs))
    }
    
    // 4. L2 归一化
    norm := math.Sqrt(te.dot(result, result))
    if norm > 0 {
        for i := range result {
            result[i] /= norm
        }
    }
    
    return result, nil
}

func (te *TextEmbedding) dot(a, b []float64) float64 {
    sum := 0.0
    for i := range a {
        sum += a[i] * b[i]
    }
    return sum
}

// Cosine Similarity 余弦相似度
func CosineSimilarity(a, b []float64) float64 {
    dot := 0.0
    normA := 0.0
    normB := 0.0
    
    for i := range a {
        dot += a[i] * b[i]
        normA += a[i] * a[i]
        normB += b[i] * b[i]
    }
    
    if normA == 0 || normB == 0 {
        return 0
    }
    
    return dot / (math.Sqrt(normA) * math.Sqrt(normB))
}
```

---

## 第三部分：向量数据库

### 3.1 HNSW 索引

```go
type HNSW struct {
    layers   [][]*Node
    M        int       // 每层最大连接数
    ef       int       // 搜索范围
    entryPoint *Node
}

type Node struct {
    id        int
    embedding []float64
    neighbors map[int][]int // layer → neighbor IDs
}

func (hnsw *HNSW) Search(query []float64, k int) []int {
    // 从顶层开始搜索
    entryPoint := hnsw.layers[len(hnsw.layers)-1][0]
    
    // 逐层向下搜索入口点
    for layer := len(hnsw.layers) - 2; layer >= 0; layer-- {
        best := hnsw.findEntryPoint(entryPoint.id, query, layer)
        entryPoint = hnsw.layers[layer][best]
    }
    
    // 在最底层搜索最近邻
    return hnsw.knnSearch(entryPoint.id, query, k)
}

func (hnsw *HNSW) knnSearch(nodeID int, query []float64, k int) []int {
    candidates := make(PriorityQueue, 0)
    visited := make(map[int]bool)
    
    candidates.Push(&Item{
        ID:       nodeID,
        Distance: hnsw.distance(hnsw.layers[0][nodeID].embedding, query),
        Priority: 0,
    })
    
    for candidates.Len() > 0 && len(visited) < hnsw.ef {
        item := candidates.Pop().(*Item)
        if visited[item.ID] {
            continue
        }
        visited[item.ID] = true
        
        // 添加邻居
        for _, neighborID := range hnsw.layers[0][item.ID].neighbors[0] {
            if !visited[neighborID] {
                dist := hnsw.distance(hnsw.layers[0][neighborID].embedding, query)
                candidates.Push(&Item{
                    ID:       neighborID,
                    Distance: dist,
                    Priority: -dist,
                })
            }
        }
    }
    
    // 返回 top-k
    result := make([]int, 0, k)
    for candidates.Len() > 0 && len(result) < k {
        item := candidates.Pop().(*Item)
        result = append(result, item.ID)
    }
    
    return result
}
```

### 3.2 Milvus 客户端

```go
package vectordb

import (
    "context"
    "github.com/milvus-io/milvus-sdk-go/v2/client"
    "github.com/milvus-io/milvus-sdk-go/v2/entity"
)

type VectorDB struct {
    client   client.Client
    collection *entity.Collection
}

func NewVectorDB(addr string) (*VectorDB, error) {
    ctx := context.Background()
    c, err := client.NewClient(ctx, client.Config{
        Address: addr,
    })
    if err != nil {
        return nil, err
    }
    
    return &VectorDB{client: c}, nil
}

func (vd *VectorDB) CreateCollection(name string, dim int) error {
    schema := &entity.Schema{
        CollectionName: name,
        Fields: []*entity.Field{
            {
                Name:       "id",
                DataType:   entity.FieldTypeInt64,
                PrimaryKey: true,
            },
            {
                Name:     "embedding",
                DataType: entity.FieldTypeFloatVector,
                TypeParams: map[string]string{
                    entity.TypeParamDimension: fmt.Sprintf("%d", dim),
                },
            },
            {
                Name:     "text",
                DataType: entity.FieldTypeVarChar,
                TypeParams: map[string]string{
                    entity.TypeParamMaxLength: "500",
                },
            },
        },
    }
    
    return vd.client.CreateCollection(context.Background(), schema, 1)
}

func (vd *VectorDB) Insert(collectionName string, ids []int64, embeddings [][]float64, texts []string) error {
    idField := entity.NewColumnInt64("id", ids)
    embField := entity.NewColumnFloatVector("embedding", len(embeddings[0]), embeddings)
    textField := entity.NewColumnVarChar("text", texts)
    
    return vd.client.Insert(context.Background(), collectionName, "", idField, embField, textField)
}

func (vd *VectorDB) Search(collectionName string, query []float64, topK int, filter string) ([]entity.Row, error) {
    results, err := vd.client.Search(
        context.Background(),
        collectionName,
        []string{},
        filter,
        []string{"embedding"},
        entity.NewColumnFloatVector("embedding", len(query), [][]float64{query}),
        topK,
        entity.L2,
        map[string]string{},
    )
    
    if err != nil {
        return nil, err
    }
    
    var rows []entity.Row
    for _, res := range results {
        for i := range res.IDs.GetRow(0) {
            rows = append(rows, res.GetResult(i))
        }
    }
    
    return rows, nil
}
```

---

## 第四部分：Fine-tuning

### 4.1 Fine-tuning 流程

```go
package finetune

import (
    "context"
    "github.com/huggingface/transformers-go"
)

type FineTuner struct {
    baseModel string
    dataset   Dataset
    args      TrainingArgs
}

type TrainingArgs struct {
    Epochs       int
    BatchSize    int
    LearningRate float64
}

func (ft *FineTuner) Train(ctx context.Context) error {
    // 1. 加载基础模型
    model, err := transformers.LoadModel(ft.baseModel)
    if err != nil {
        return err
    }
    
    // 2. 准备数据
    trainDataset, valDataset := ft.prepareData()
    
    // 3. 训练
    trainingArgs := transformers.TrainingArguments{
        OutputDir:      "./output",
        NumTrainEpochs: float32(ft.args.Epochs),
        PerDeviceTrainBatchSize: int32(ft.args.BatchSize),
        LearningRate:  ft.args.LearningRate,
    }
    
    trainer := transformers.NewTrainer(
        model,
        trainDataset,
        valDataset,
        trainingArgs,
    )
    
    _, err = trainer.Train()
    if err != nil {
        return err
    }
    
    return trainer.SaveModel("./fine-tuned-model")
}
```

### 4.2 RAG 增强检索

```go
package rag

import (
    "context"
)

type RAGEngine struct {
    vectorDB   *VectorDB
    embedder   *embedding.TextEmbedding
    llm        *LLMClient
    topK       int
}

func (rag *RAGEngine) Answer(ctx context.Context, query string) (*RAGResponse, error) {
    // 1. 检索相关文档
    queryEmbedding, err := rag.embedder.Encode(query)
    if err != nil {
        return nil, err
    }
    
    results, err := rag.vectorDB.Search("knowledge", queryEmbedding, rag.topK, "")
    if err != nil {
        return nil, err
    }
    
    // 2. 构建 prompt
    context := rag.buildContext(results)
    prompt := rag.buildPrompt(query, context)
    
    // 3. LLM 生成回答
    answer, err := rag.llm.Generate(ctx, prompt)
    if err != nil {
        return nil, err
    }
    
    return &RAGResponse{
        Answer:  answer,
        Sources: rag.extractSources(results),
    }, nil
}
```

---

## 第五部分：自测题

### 问题 1
为什么需要 Embedding？

<details>
<summary>查看答案</summary>

1. **语义理解**：捕捉词义而非字面
2. **同义词**："手机"和"智能手机"语义相似
3. **高维空间**：余弦相似度衡量语义距离
4. **广告场景**：用户意图识别必须用语义
5. **Go 实现**：TextEmbedding

</details>

### 问题 2
HNSW 为什么比暴力搜索快？

<details>
<summary>查看答案</summary>

1. **多层结构**：类似 SkipList
2. **近似最近邻**：O(log n) 复杂度
3. **ef 参数**：控制精度和速度权衡
4. **M 参数**：控制每层连接数
5. **Go 实现**：HNSW.Search()

</details>

### 问题 3
RAG 相比直接生成有什么优势？

<details>
<summary>查看答案</summary>

1. **事实性**：基于真实数据
2. **可追溯**：有信息来源
3. **时效性**：知识库可实时更新
4. **可控性**：可以限制回答范围
5. **Go 实现**：RAGEngine

</details>

---

*本文档基于 AI 实战原理整理。*