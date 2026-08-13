# Embedding模型对比 - 资深专家深度实现

## 一、模型对比

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    Embedding 模型对比                                      │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   模型                  | 维度   | 性能    | 速度     | 适用场景         │
│   ──────────────────────┼────────┼─────────┼──────────┼─────────────────│
│   text-embedding-3-small│ 1536   | 中等    | 快       | 通用搜索         │
│   text-embedding-3-large│ 3072   | 高      | 中       | 高精度搜索       │
│   BGE-Large             | 1024   | 高      | 快       | 中文搜索         │
│   E5-V2                 | 768    | 中      | 快       | 多语言           │
│   OpenAI Ada            | 1536   | 中      | 中       | 英文通用         │
│                                                                         →
└─────────────────────────────────────────────────────────────────────────┘
```

## 二、模型选择实现

```go
package embedding

import (
    "context"
)

// Model 接口
type Model interface {
    Encode(ctx context.Context, text string) ([]float32, error)
    Dim() int
    Name() string
}

// ModelSelector 模型选择器
type ModelSelector struct {
    models map[string]Model
}

func (s *ModelSelector) Select(config SelectConfig) Model {
    // 根据场景选择模型
    switch config.Language {
    case "zh":
        return s.models["bge-large"]
    case "en":
        return s.models["text-embedding-3-large"]
    default:
        return s.models["text-embedding-3-small"]
    }
}

// SelectConfig 选择配置
type SelectConfig struct {
    Language    string
    Accuracy    float32  // 精度要求
    Latency     time.Duration // 延迟要求
    Dimension   int      // 维度要求
}
```

## 三、面试高频题

### Q1: 如何选择合适的Embedding模型？

```
A:
1. 语言匹配
2. 精度需求
3. 延迟要求
```

### Q2: 模型维度如何选择？

```
A:
1. 高维精度高但慢
2. 低维速度快但精度低
3. 平衡选择
```

## 四、自测题

1. 如何对比模型？
2. 如何选择模型？
3. 维度如何选择？

---

## 参考文档

- [MTEB Benchmark](https://huggingface.co/spaces/mteb/)
- [BGE Models](https://huggingface.co/BAAI/bge-large-zh)
