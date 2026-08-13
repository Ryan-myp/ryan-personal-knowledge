# Istio进阶 - 资深专家深度实现

## 一、高级特性

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    Istio 高级特性                                          │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   特性                | 功能                                    │
│   ────────────────────┼──────────────────────────────────────────────│
│   mTLS               | 双向TLS加密通信                            │
│   Rate Limiting      | 请求速率限制                              │
│   Fault Injection    | 故障注入测试                              │
│   Traffic Mirroring  | 流量镜像                                  │
│   Request Routing    | 高级路由策略                              │
│                                                                         →
└─────────────────────────────────────────────────────────────────────────┘
```

## 二、mTLS实现

```go
package istio

import (
    "context"
)

// MTLSConfig mTLS配置
type MTLSConfig struct {
    Mode       PeerAuthentication_MutualTLS_Mode
    Namespace  string
    Service    string
}

// MTLSManager mTLS管理器
type MTLSManager struct {
    client *IstioClient
}

// EnableMTLS 启用mTLS
func (m *MTLSManager) EnableMTLS(ctx context.Context, config MTLSConfig) error {
    pa := &istiosecurityv1beta1.PeerAuthentication{
        ObjectMeta: metav1.ObjectMeta{
            Name:      config.Service,
            Namespace: config.Namespace,
        },
        Spec: istiosecurityv1beta1.PeerAuthentication{
            Mtls: &istiosecurityv1beta1_MUTUAL_TLS,
        },
    }
    
    return m.client.Create(ctx, pa)
}

// DisableMTLS 禁用mTLS
func (m *MTLSManager) DisableMTLS(ctx context.Context, namespace string) error {
    pa := &istiosecurityv1beta1.PeerAuthentication{
        ObjectMeta: metav1.ObjectMeta{
            Name:      "default",
            Namespace: namespace,
        },
        Spec: istiosecurityv1beta1.PeerAuthentication{
            Mtls: &istiosecurityv1beta1_PERMISSIVE,
        },
    }
    
    return m.client.Update(ctx, pa)
}
```

## 三、流量镜像实现

```go
package istio

// TrafficMirror 流量镜像
type TrafficMirror struct {
    Source      string
    Destination string
    Percentage  float32
}

func (m *MTLSManager) MirrorTraffic(ctx context.Context, mirror *TrafficMirror) error {
    vs := &istionetworkingv1beta1.VirtualService{
        ObjectMeta: metav1.ObjectMeta{
            Name:      mirror.Source + "-mirror",
            Namespace: "default",
        },
        Spec: istionetworkingv1beta1.VirtualService{
            Hosts: []string{mirror.Source},
            Http: []istionetworkingv1beta1.HTTPRoute{
                {
                    Route: []istionetworkingv1beta1.HTTPDestination{
                        {Destination: istionetworkingv1beta1.HTTPRouteDestination{
                            Host: mirror.Source,
                        }},
                    },
                    Mirrors: []istionetworkingv1beta1.HTTPMirrorPolicy{
                        {Destination: istionetworkingv1beta1.HTTPRouteDestination{
                            Host: mirror.Destination,
                        }},
                        Percentage: mirror.Percentage,
                    },
                },
            },
        },
    }
    
    return m.client.Create(ctx, vs)
}
```

## 四、面试高频题

### Q1: mTLS如何工作？

```
A:
1. 证书自动分发
2. 双向身份验证
3. 加密传输
```

### Q2: 如何实现流量镜像？

```
A:
1. VirtualService配置
2. Mirrors规则
3. 百分比控制
```

## 五、自测题

1. 解释mTLS原理
2. 如何配置流量镜像？
3. 如何实现熔断器？

---

## 参考文档

- [Istio Security](https://istio.io/latest/docs/concepts/security/)
- [Istio Routing](https://istio.io/latest/docs/reference/config/networking/)
