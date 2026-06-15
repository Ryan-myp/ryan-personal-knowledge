# AI 实战：Embedding/向量数据库/Fine-tuning

> Embedding 模型/向量数据库(Milvus/Pinecone)/Fine-tuning/RAG 增强检索

---

## 第一部分：入门引导（5 分钟速览）

### 为什么需要 Embedding？

广告平台需要理解语义：
- **用户意图识别**：搜索"便宜手机"→ 推荐性价比机型
- **广告创意匹配**：根据用户兴趣匹配创意
- **相似推荐**：相似商品/广告推荐
- **反作弊**：相似举报内容检测

### Embedding vs Traditional Search

```
传统搜索：关键词匹配
"手机" → 找包含"手机"的文档

语义搜索（Embedding）：
"手机" → [0.12, -0.34, 0.56, ...]
"智能手机" → [0.11, -0.33, 0.55, ...]
相似度 ≈ 0.99 → 匹配！
```

---

## 第二部分：Embedding 模型

### 2.1 Embedding 原理

```go
package embedding

import (
    "math"
    "vector"
)

// EmbeddingModel 嵌入模型接口
type EmbeddingModel interface {
    Encode(text string) ([]float64, error)
    Dim() int
}

// TextEmbedding 文本嵌入
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
```

### 2.2 相似度计算

```go
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

// HNSW 近似最近邻搜索
type HNSW struct {
    layers [][]*Node
    M      int       // 每层最大连接数
    ef     int       // 搜索范围
}

type Node struct {
    id       int
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
```

---

## 第三部分：向量数据库

### 3.1 Milvus 客户端

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

### 3.2 广告创意向量检索

```go
type CreativeSearch struct {
    vectorDB *VectorDB
    embedder *embedding.TextEmbedding
}

func (cs *CreativeSearch) SearchCreatives(query string, topK int) ([]*Creative, error) {
    // 1. 查询文本 embedding
    queryVec, err := cs.embedder.Encode(query)
    if err != nil {
        return nil, err
    }
    
    // 2. 向量搜索
    results, err := cs.vectorDB.Search("creatives", queryVec, topK, "")
    if err != nil {
        return nil, err
    }
    
    // 3. 构建创意列表
    var creatives []*Creative
    for _, row := range results {
        creatives = append(creatives, &Creative{
            ID:     row.Get("id").(int64),
            Text:   row.Get("text").(string),
            Score:  row.Distance,
        })
    }
    
    return creatives, nil
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
    LR scheduler.Cycle
}

func (ft *FineTuner) Train(ctx context.Context) error {
    // 1. 加载基础模型
    model, err := transformers.LoadModel(ft.baseModel)
    if err != nil {
        return err
    }
    
    // 2. 准备数据
    trainDataset, valDataset := ft.prepareData()
    
    // 3. 配置训练参数
    trainingArgs := transformers.TrainingArguments{
        OutputDir:      "./output",
        NumTrainEpochs: float32(ft.args.Epochs),
        PerDeviceTrainBatchSize: int32(ft.args.BatchSize),
        LearningRate:  ft.args.LearningRate,
        LRType:        ft.args.LR,
        LoggingSteps:  10,
        SaveSteps:     100,
        EvalSteps:     100,
    }
    
    // 4. 训练
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
    
    // 5. 保存模型
    return trainer.SaveModel("./fine-tuned-model")
}
```

### 4.2 广告场景 Fine-tuning

```go
// 场景1：广告分类 Fine-tuning
type AdClassifier struct {
    model *transformers.Model
}

func (ac *AdClassifier) Predict(adText string) (string, float64) {
    // 1. 编码输入
    encoded := ac.model.Encode(adText)
    
    // 2. 预测分类
    logits := ac.model.Forward(encoded)
    probs := softmax(logits)
    
    // 3. 返回最高概率类别
    classID := argmax(probs)
    return adCategories[classID], probs[classID]
}

// 场景2：搜索意图识别
type SearchIntentRecognizer struct {
    model *transformers.Model
}

func (sir *SearchIntentRecognizer) Recognize(query string) string {
    prompt := fmt.Sprintf("Query: %s\nIntent: ", query)
    
    result := sir.model.Generate(
        prompt,
        transformers.GenerationConfig{
            MaxLength:  50,
            Temperature: 0.7,
            TopK:       50,
        },
    )
    
    return result
}
```

---

## 第五部分：RAG 增强检索

### 5.1 RAG 架构

```
用户查询
    ↓
检索知识库（向量数据库）
    ↓
返回相关文档
    ↓
LLM 生成回答
    ↓
最终答案
```

### 5.2 Go 实现 RAG

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

type RAGRequest struct {
    Query string
    Contexts []Document
}

type RAGResponse struct {
    Answer string
    Sources []string
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
    
    // 4. 返回答案和来源
    sources := rag.extractSources(results)
    
    return &RAGResponse{
        Answer:  answer,
        Sources: sources,
    }, nil
}

func (rag *RAGEngine) buildContext(results []entity.Row) string {
    context := ""
    for _, row := range results {
        doc := row.Get("content").(string)
        score := row.Distance
        context += fmt.Sprintf("=== Document (score: %.3f) ===\n%s\n\n", 1-score, doc)
    }
    return context
}

func (rag *RAGEngine) buildPrompt(query, context string) string {
    return fmt.Sprintf(`基于以下知识库内容回答问题：

%s

问题: %s

请基于知识库内容回答，如果不能回答请说"不知道"。`, context, query)
}
```

---

## 第六部分：自测题

### 问题 1
为什么需要使用 Embedding 而不是关键词匹配？

<details>
<summary>查看答案</summary>

1. **语义理解**：捕捉词义而非字面
2. **同义词**："手机"和"智能手机"语义相似
3. **泛化能力**：训练后能处理未见过的词
4. **高维空间**：余弦相似度衡量语义距离
5. **广告场景**：用户意图识别必须用语义

</details>

### 问题 2
向量数据库相比传统数据库有什么优势？

<details>
<summary>查看答案</summary>

1. **相似性搜索**：向量距离计算
2. **HNSW 算法**：近似最近邻，O(log n)
3. **高维优化**：针对 768/1536 维向量优化
4. **分布式**：分片存储大规模向量
5. **Milvus/Pinecone**：专业向量数据库

</details>

### 问题 3
Fine-tuning 和 Prompt Engineering 怎么选？

<details>
<summary>查看答案</summary>

1. **Prompt Engineering**：零成本，快速迭代
2. **Fine-tuning**：需要标注数据，训练成本高
3. **选择标准**：
   - 简单分类/意图识别 → Fine-tuning
   - 复杂推理 → Prompt Engineering
   - 实时性要求高 → Fine-tuning
4. **混合方案**：Fine-tuning + RAG
5. **广告场景**：广告分类用 Fine-tuning，创意生成用 RAG

</details>

---

*本文档基于 AI 实战原理整理。*