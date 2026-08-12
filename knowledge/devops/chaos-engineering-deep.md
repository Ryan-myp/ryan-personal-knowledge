# 混沌工程深度实现

> **文档级别**: Level 5 - 专家级  
> **创建日期**: 2026-08-13  
> **状态**: ✅ 已补齐

---

## 一、混沌工程原则

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      混沌工程核心原则                                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  1. 建立稳态假设                                                              │
│     • 定义系统正常行为基线                                                    │
│     • 监控关键指标 (延迟、错误率、吞吐量)                                     │
│                                                                             │
│  2. 假设灾难发生                                                              │
│     • 任何时刻都可能有故障发生                                                │
│     • 验证系统能否从故障中恢复                                                │
│                                                                             │
│  3. 运行实验                                                                  │
│     • 在受控环境中引入故障                                                    │
│     • 逐步增加故障规模                                                        │
│                                                                             │
│  4. 自动化与持续                                                              │
│     • 将混沌实验集成到 CI/CD                                                  │
│     • 定期运行以发现新问题                                                    │
│                                                                             │
│  5. 最小化爆炸半径                                                            │
│     • 选择影响最小的实验范围                                                  │
│     • 准备快速回滚方案                                                        │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 二、Chaos Mesh 实战

```yaml
# 文件: chaos/mesh/pod-failure.yaml
apiVersion: chaos-mesh.org/v1alpha1
kind: PodChaos
metadata:
  name: ad-bidding-pod-failure
  namespace: advertising
spec:
  action: pod-failure
  mode: one
  selector:
    namespaces:
      - advertising
    labelSelectors:
      app: ad-bidding
  scheduler:
    cron: '0 2 * * *'  # 每天凌晨2点执行
    duration: '10m'    # 持续10分钟
  
  # 影响比例
  percent: 10        # 10% 的 Pod
  
  # 恢复时间
  gracePeriod: 5     # 等待5秒后开始
  
  # 实验配置
  value:
    delay: 30s       # 延迟30秒后执行
    force: false
```

---

## 三、故障注入场景

```python
# 文件: chaos/injector.py

import chaos_client
from datetime import datetime

class ChaosInjector:
    """混沌工程注入器"""
    
    def __init__(self, cluster_url: str):
        self.client = chaos_client.ClusterClient(cluster_url)
        
    def inject_network_partition(self, target_pods: list, duration: int = 60):
        """网络分区实验"""
        experiment = {
            "apiVersion": "chaos-mesh.org/v1alpha1",
            "kind": "NetworkChaos",
            "metadata": {
                "name": f"net-partition-{datetime.now().strftime('%Y%m%d%H%M%S')}",
                "namespace": "advertising"
            },
            "spec": {
                "action": "partition",
                "mode": "one",
                "selector": {
                    "namespaces": ["advertising"],
                    "labelSelectors": {"app": "ad-bidding"}
                },
                "delay": 1000,  # 延迟1秒
                "duration": f"{duration}s"
            }
        }
        return self.client.apply(experiment)
    
    def inject_latency(self, target_pods: list, latency_ms: int = 500):
        """网络延迟实验"""
        experiment = {
            "apiVersion": "chaos-mesh.org/v1alpha1",
            "kind": "NetworkChaos",
            "spec": {
                "action": "delay",
                "delay": {
                    "latency": f"{latency_ms}ms",
                    "correlation": "95%"
                },
                "selector": {
                    "namespaces": ["advertising"],
                    "labelSelectors": {"app": "ad-bidding"}
                }
            }
        }
        return self.client.apply(experiment)
    
    def inject_cpu_stress(self, target_pods: list, cpu_percent: int = 80):
        """CPU 压力实验"""
        experiment = {
            "apiVersion": "chaos-mesh.org/v1alpha1",
            "kind": "PodChaos",
            "spec": {
                "action": "cpu-stress",
                "stressy": {
                    "load": cpu_percent,
                    "workers": 4
                },
                "selector": {
                    "namespaces": ["advertising"],
                    "labelSelectors": {"app": "ad-bidding"}
                }
            }
        }
        return self.client.apply(experiment)
```

---

## 四、参考资料

```
核心工具:
├── Chaos Mesh: https://chaos-mesh.org/
├── LitmusChaos: https://litmuschaos.io/
└── Gremlin: https://www.gremlin.com/

最佳实践:
├── "Designing Resilient Systems" (Netflix)
└── AWS Chaos Engineering Guide
```

---

*文档版本: v1.0*  
*最后更新: 2026-08-13*  
*作者: Ryan*
