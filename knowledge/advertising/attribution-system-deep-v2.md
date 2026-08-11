# 广告归因系统深度解析

> 深入广告归因：归因模型、多触点归因、归因数据管道。
> 包含真实生产环境归因系统架构。
> 适用对象：广告算法工程师、数据分析师、架构师

---

## 1. 归因模型

### 1.1 常见归因模型

```
┌────────────────┬─────────────────────────────────────┬──────────────┐
│ 归因模型       │ 说明                                │ 适用场景     │
├────────────────┼─────────────────────────────────────┼──────────────┤
│ 最后点击       │ 100%归因给最后一次点击              │ 简单场景     │
│ 首次点击       │ 100%归因给第一次点击                │ 获客分析     │
│ 线性归因       │ 所有触点平分归因                    │ 平衡视角     │
│ 时间衰减       │ 越接近转化归因权重越高              │ 转化周期长   │
│ 位置归因       │ 首尾触点权重高                      │ 强调触点     │
│ 数据驱动       │ 基于历史数据计算归因                │ 数据充足     │
└────────────────┴─────────────────────────────────────┴──────────────┘
```

### 1.2 Go 实现归因模型

```go
// attribution.go

package ad

import "sync"

type AttributionModel int

const (
    LastClick AttributionModel = iota
    FirstClick
    Linear
    TimeDecay
    Position
    DataDriven
)

type TouchPoint struct {
    ID        string
    Channel   string
    Timestamp int64
    Value     float64
}

type AttributionResult struct {
    TouchPoints []TouchPoint
    Model       AttributionModel
    Weights     map[string]float64
}

type AttributionEngine struct {
    models map[AttributionModel]func([]TouchPoint) map[string]float64
    mu     sync.RWMutex
}

func NewAttributionEngine() *AttributionEngine {
    ae := &AttributionEngine{
        models: make(map[AttributionModel]func([]TouchPoint) map[string]float64),
    }
    ae.registerModels()
    return ae
}

func (ae *AttributionEngine) registerModels() {
    ae.models[LastClick] = ae.lastClickModel
    ae.models[FirstClick] = ae.firstClickModel
    ae.models[Linear] = ae.linearModel
    ae.models[TimeDecay] = ae.timeDecayModel
    ae.models[Position] = ae.positionModel
}

func (ae *AttributionEngine) Attribute(touchPoints []TouchPoint, model AttributionModel) map[string]float64 {
    fn, ok := ae.models[model]
    if !ok {
        return ae.models[LastClick](touchPoints)
    }
    return fn(touchPoints)
}

func (ae *AttributionEngine) lastClickModel(touchPoints []TouchPoint) map[string]float64 {
    result := make(map[string]float64)
    if len(touchPoints) == 0 {
        return result
    }
    last := touchPoints[len(touchPoints)-1]
    result[last.Channel] = 1.0
    return result
}

func (ae *AttributionEngine) firstClickModel(touchPoints []TouchPoint) map[string]float64 {
    result := make(map[string]float64)
    if len(touchPoints) == 0 {
        return result
    }
    first := touchPoints[0]
    result[first.Channel] = 1.0
    return result
}

func (ae *AttributionEngine) linearModel(touchPoints []TouchPoint) map[string]float64 {
    result := make(map[string]float64)
    if len(touchPoints) == 0 {
        return result
    }
    weight := 1.0 / float64(len(touchPoints))
    for _, tp := range touchPoints {
        result[tp.Channel] += weight
    }
    return result
}
```

---

## 2. 多触点归因

### 2.1 归因路径

```
多触点归因路径示例：

用户路径：
  展示广告(百度) → 点击广告(Google) → 搜索品牌词 → 点击广告(Facebook) → 转化

归因分析：
├── 百度展示：辅助转化
├── Google点击：首次点击贡献
├── 品牌搜索：中间触点
└── Facebook点击：最后点击贡献
```

### 2.2 Go 实现多触点归因

```go
// multi_touch.go

package ad

import (
    "sort"
    "time"
)

type AttributionPath struct {
    UserID      string
    TouchPoints []TouchPoint
    Conversion  ConversionEvent
}

type ConversionEvent struct {
    Value     float64
    Timestamp int64
}

type MultiTouchAttribution struct {
    paths     []AttributionPath
    channels  map[string]float64
    mu        sync.Mutex
}

func NewMultiTouchAttribution() *MultiTouchAttribution {
    return &MultiTouchAttribution{
        channels: make(map[string]float64),
    }
}

func (mta *MultiTouchAttribution) AddPath(path AttributionPath) {
    mta.paths = append(mta.paths, path)
    mta.calculateAttribution()
}

func (mta *MultiTouchAttribution) calculateAttribution() {
    mta.mu.Lock()
    defer mta.mu.Unlock()
    
    // 重置
    for k := range mta.channels {
        delete(mta.channels, k)
    }
    
    // 计算归因
    for _, path := range mta.paths {
        if len(path.TouchPoints) == 0 {
            continue
        }
        
        // 按时间排序
        sort.Slice(path.TouchPoints, func(i, j int) bool {
            return path.TouchPoints[i].Timestamp < path.TouchPoints[j].Timestamp
        })
        
        // 线性归因
        weight := 1.0 / float64(len(path.TouchPoints))
        for _, tp := range path.TouchPoints {
            mta.channels[tp.Channel] += weight * path.Conversion.Value
        }
    }
}

func (mta *MultiTouchAttribution) GetChannelValue() map[string]float64 {
    mta.mu.Lock()
    defer mta.mu.Unlock()
    
    result := make(map[string]float64)
    for k, v := range mta.channels {
        result[k] = v
    }
    return result
}
```

---

## 3. 归因数据管道

### 3.1 数据流

```
归因数据管道：

┌─────────────────────────────────────────────────────────────┐
│                    归因数据管道                              │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  数据采集层                                                  │
│  ├── 广告曝光日志                                            │
│  ├── 广告点击日志                                            │
│  ├── 网站访问日志                                            │
│  └── 转化事件日志                                            │
│                                                             │
│  数据处理层                                                  │
│  ├── 数据清洗                                                │
│  ├── 数据关联 (用户ID映射)                                    │
│  ├── 归因计算                                                │
│  └── 归因结果存储                                            │
│                                                             │
│  数据应用层                                                  │
│  ├── 归因报告                                                │
│  ├── 渠道效果分析                                            │
│  ├── 预算分配建议                                            │
│  └── 实时出价优化                                            │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 Go 实现数据管道

```go
// attribution_pipeline.go

package ad

import (
    "sync"
    "time"
)

type DataPipeline struct {
    exposure chan ExposureEvent
    click    chan ClickEvent
    conversion chan ConversionEvent
    result   chan AttributionResult
    mu       sync.Mutex
}

type ExposureEvent struct {
    ID          string
    AdID        string
    Channel     string
    UserID      string
    Timestamp   int64
}

type ClickEvent struct {
    ID          string
    AdID        string
    Channel     string
    UserID      string
    Timestamp   int64
}

type PipelineProcessor struct {
    paths      map[string][]TouchPoint
    mu         sync.Mutex
}

func NewPipelineProcessor() *PipelineProcessor {
    return &PipelineProcessor{
        paths: make(map[string][]TouchPoint),
    }
}

func (pp *PipelineProcessor) ProcessExposure(exp ExposureEvent) {
    pp.mu.Lock()
    defer pp.mu.Unlock()
    
    if _, ok := pp.paths[exp.UserID]; !ok {
        pp.paths[exp.UserID] = make([]TouchPoint, 0)
    }
    pp.paths[exp.UserID] = append(pp.paths[exp.UserID], TouchPoint{
        ID:        exp.ID,
        Channel:   exp.Channel,
        Timestamp: exp.Timestamp,
        Value:     0,
    })
}

func (pp *PipelineProcessor) ProcessClick(click ClickEvent) {
    pp.mu.Lock()
    defer pp.mu.Unlock()
    
    if _, ok := pp.paths[click.UserID]; !ok {
        pp.paths[click.UserID] = make([]TouchPoint, 0)
    }
    pp.paths[click.UserID] = append(pp.paths[click.UserID], TouchPoint{
        ID:        click.ID,
        Channel:   click.Channel,
        Timestamp: click.Timestamp,
        Value:     1,
    })
}

func (pp *PipelineProcessor) ProcessConversion(conv ConversionEvent, model AttributionModel) AttributionResult {
    pp.mu.Lock()
    defer pp.mu.Unlock()
    
    touchPoints := pp.paths[conv.UserID]
    result := AttributionResult{
        TouchPoints: touchPoints,
        Model:       model,
        Weights:     make(map[string]float64),
    }
    
    // 计算归因
    if len(touchPoints) > 0 {
        // 线性归因
        weight := 1.0 / float64(len(touchPoints))
        for _, tp := range touchPoints {
            result.Weights[tp.Channel] += weight
        }
    }
    
    return result
}
```

---

## 4. 总结

### 4.1 核心原理回顾

| 模块 | 核心机制 |
|------|----------|
| 归因模型 | 最后点击/首次点击/线性/时间衰减 |
| 多触点归因 | 归因路径分析 |
| 数据管道 | 采集→处理→应用 |

### 4.2 最佳实践

- [ ] 选择合适的归因模型
- [ ] 建立完整的数据管道
- [ ] 定期校准归因结果
- [ ] 结合业务场景分析

---

*最后更新：2026-08-11*
*作者：Ryan*
