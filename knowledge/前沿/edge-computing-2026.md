# 边缘计算与 AI 融合趋势

> **文档级别**: Level 4  
> **创建日期**: 2026-08-13  
> **状态**: ✅ 已更新

---

## 一、边缘 AI 架构

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        Edge AI 架构                                         │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Cloud Layer                                                                │
│  ├── Model Training (GPU Cluster)                                          │
│  ├── Model Management                                                       │
│  └── Centralized Analytics                                                  │
│                      │                                                      │
│                      ▼                                                      │
│  Edge Layer                                                                 │
│  ├── Edge Inference (ONNX/TensorRT)                                        │
│  ├── Real-time Processing                                                   │
│  └── Local Data Filtering                                                   │
│                      │                                                      │
│                      ▼                                                      │
│  Device Layer                                                               │
│  ├── Mobile (CoreML/TF Lite)                                                │
│  ├── IoT (TinyML)                                                          │
│  └── Vehicle (Horizon)                                                      │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 二、关键技术栈

```
模型压缩:
├── 量化 (Quantization): INT8/FP16
├── 剪枝 (Pruning): 结构/非结构
├── 知识蒸馏 (Knowledge Distillation)
└── 低秩分解 (Low-rank Factorization)

推理框架:
├── ONNX Runtime
├── TensorRT
├── CoreML
└── TFLite

边缘平台:
├── AWS Greengrass
├── Azure IoT Edge
└── 阿里云 Link IoT Edge
```

---

## 三、广告场景应用

```
实时 bid 决策:
├── 特征预计算在边缘
├── 模型推理在 CDN 节点
└── 结果回传中心

用户体验优化:
├── 本地缓存热门素材
├── 预测性加载
└── 离线内容预渲染
```

---

## 四、参考资料

```
核心资源:
├── Edge AI Survey: https://arxiv.org/abs/2105.03285
├── ONNX: https://onnx.ai/
└── TensorFlow Lite: https://www.tensorflow.org/lite
```

---

*文档版本: v1.0*  
*最后更新: 2026-08-13*  
*作者: Ryan*
