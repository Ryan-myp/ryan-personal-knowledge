# Kubernetes HPA/VPA自动扩缩容 - 资深专家深度实现

## 一、HPA架构设计

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      HPA控制器架构                                        │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   ┌──────────────┐    ┌──────────────┐    ┌──────────────┐            │
│   │  Metrics     │    │  HPA         │    │  Deployment  │            │
│   │  Server      │───▶│  Controller  │───▶│  / ReplicaSet│            │
│   │              │    │              │    │              │            │
│   │ • CPU/Memory │    │ • 计算目标   │    │ • 更新副本数  │            │
│   │ • 自定义指标 │    │ • 保护机制   │    │ • 滚动更新   │            │
│   │ • Pod指标    │    │ • 状态同步   │    │              │            │
│   └──────────────┘    └──────────────┘    └──────────────┘            │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

## 二、HPA实现

### 2.1 HPA Spec定义

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: api-server
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: api-server
  minReplicas: 3
  maxReplicas: 20
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
  - type: Pods
    pods:
      metric:
        name: network_packets_per_second
      target:
        type: AverageValue
        averageValue: '5000'
  behavior:
    scaleUp:
      stabilizationWindowSeconds: 60
      policies:
      - type: Percent
        value: 100
        periodSeconds: 15
    scaleDown:
      stabilizationWindowSeconds: 300
      policies:
      - type: Percent
        value: 10
        periodSeconds: 60
```

### 2.2 HPA控制器逻辑

```go
package hpa

import (
    "context"
    "fmt"
    "time"
    
    autoscalingv2 "k8s.io/api/autoscaling/v2"
    "k8s.io/apimachinery/pkg/api/resource"
    metricsv1 "k8s.io/metrics/pkg/apis/metrics/v1beta1"
)

type HPACoordinator struct {
    metricsClient MetricsClient
    deployClient  DeployClient
}

// Reconcile  reconcile HPA状态
func (c *HPACoordinator) Reconcile(ctx context.Context, hpa *autoscalingv2.HorizontalPodAutoscaler) error {
    // 1. 获取当前metrics
    currentMetrics, err := c.getCurrentMetrics(ctx, hpa)
    if err != nil {
        return err
    }
    
    // 2. 计算目标副本数
    desiredReplicas, err := c.calculateDesiredReplicas(ctx, hpa, currentMetrics)
    if err != nil {
        return err
    }
    
    // 3. 应用保护策略
    desiredReplicas = c.applyBehaviorPolicy(hpa, desiredReplicas)
    
    // 4. 更新Deployment副本数
    return c.updateDeployment(ctx, hpa, desiredReplicas)
}

func (c *HPACoordinator) calculateDesiredReplicas(
    ctx context.Context, 
    hpa *autoscalingv2.HorizontalPodAutoscaler,
    metrics []*MetricValue,
) (int32, error) {
    
    var maxDesired int32
    
    for _, m := range metrics {
        var current, target float64
        
        switch m.Target.Type {
        case autoscalingv2.UtilizationMetricTarget:
            current = float64(m.Current.Value().String()) / float64(m.ResourceLimit.MilliValue())
            target = float64(m.Target.AverageUtilization)
        case autoscalingv2.ValueMetricTarget:
            current = float64(m.Current.Value().MilliValue())
            target = float64(m.Target.AverageValue.MilliValue())
        }
        
        // 计算需要多少副本
        if target > 0 && current > 0 {
            needed := int32(float64(hpa.Spec.MinReplicas) * current / target)
            if needed > maxDesired {
                maxDesired = needed
            }
        }
    }
    
    // 限制在min/max范围内
    if maxDesired < hpa.Spec.MinReplicas {
        maxDesired = hpa.Spec.MinReplicas
    }
    if maxDesired > hpa.Spec.MaxReplicas {
        maxDesired = hpa.Spec.MaxReplicas
    }
    
    return maxDesired, nil
}

func (c *HPACoordinator) applyBehaviorPolicy(
    hpa *autoscalingv2.HorizontalPodAutoscaler,
    desired int32,
) int32 {
    
    if hpa.Spec.Behavior == nil {
        return desired
    }
    
    currentReplicas := hpa.Status.CurrentReplicas
    
    if desired > currentReplicas {
        // Scale up
        return c.applyScaleUpPolicy(hpa, currentReplicas, desired)
    } else if desired < currentReplicas {
        // Scale down
        return c.applyScaleDownPolicy(hpa, currentReplicas, desired)
    }
    
    return desired
}
```

## 三、VPA实现

```go
package vpa

type VPACoordinator struct {
    metricsClient MetricsClient
}

// RecomputeRecommendation 重新计算推荐配置
func (c *VPACoordinator) RecomputeRecommendation(vpa *autoscalingv1.VerticalPodAutoscaler) error {
    // 1. 收集历史资源使用数据
    history := c.collectResourceHistory(vpa)
    
    // 2. 计算推荐值
    recommendation := vpa.Recommendation
    
    for _, resource := range history.Resources {
        // P99计算
        p99 := computePercentile(resource.Usage, 0.99)
        ceiling := p99 * 1.1  // 10% buffer
        
        recommendation.Target[resource.Name] = *resource.NewMilliQuantity(ceiling, resource.DecimalSI)
    }
    
    return nil
}

func computePercentile(values []float64, percentile float64) float64 {
    if len(values) == 0 {
        return 0
    }
    sorted := make([]float64, len(values))
    copy(sorted, values)
    sort.Float64s(sorted)
    
    index := int(float64(len(sorted)) * percentile)
    if index >= len(sorted) {
        index = len(sorted) - 1
    }
    return sorted[index]
}
```

## 四、面试高频题

### Q1: HPA和VPA有什么区别？

```
A:
• HPA: 水平扩缩，调整副本数
• VPA: 垂直扩缩，调整单个Pod的资源限制
• 两者可以结合使用
```

### Q2: HPA的计算周期是多少？

```
A: 
• 默认30秒检查一次
• 可通过controller-manager的--horizontal-pod-autoscaler-sync-period调整
```

## 五、自测题

1. HPA如何处理scale up和scale down的保护？
2. 如何实现自定义指标的HPA？
3. VPA的recommender如何工作？

---

## 参考文档

- [K8s HPA文档](https://kubernetes.io/docs/tasks/run-application/horizontal-pod-autoscale/)
- [K8s VPA文档](https://kubernetes.io/docs/tasks/run-application/vertical-pod-autoscaler/)
