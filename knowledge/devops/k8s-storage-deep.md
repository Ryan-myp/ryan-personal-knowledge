# K8s存储体系 - 资深专家深度实现

## 一、存储架构

```
┌─────────────────────────────────────────────────────────────────────────┐
│                   Kubernetes 存储架构                                      │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   PV (PersistentVolume)                                                │
│        │                                                               │
│        ▼                                                               │
│   PVC (PersistentVolumeClaim) ← 用户申请                                │
│        │                                                               │
│        ▼                                                               │
│   Volume Plugin (存储插件)                                             │
│        │                                                               │
│   ┌────┴────┬────────┬────────┬────────┬────────┐                    │
│   ▼         ▼        ▼        ▼        ▼        ▼                     │
│  NFS    CSI Driver  Local   HostPath  iSCSI  CephFS                   │
│                                                                         →
└─────────────────────────────────────────────────────────────────────────┘
```

## 二、实现代码

```go
package k8s_storage

import (
    "context"
    corev1 "k8s.io/api/core/v1"
)

// StorageManager 存储管理器
type StorageManager struct {
    client *K8sClient
}

// CreatePV 创建PV
func (m *StorageManager) CreatePV(ctx context.Context, config PVConfig) (*corev1.PersistentVolume, error) {
    pv := &corev1.PersistentVolume{
        ObjectMeta: metav1.ObjectMeta{
            Name: config.Name,
        },
        Spec: corev1.PersistentVolumeSpec{
            Capacity: corev1.ResourceList{
                corev1.ResourceStorage: resource.MustParse(config.Size),
            },
            AccessModes: []corev1.PersistentVolumeAccessMode{
                corev1.ReadWriteOnce,
            },
            PersistentVolumeSource: corev1.PersistentVolumeSource{
                CSI: &corev1.CSIPersistentVolumeSource{
                    Driver:       config.Driver,
                    VolumeHandle: config.VolumeHandle,
                },
            },
        },
    }
    
    return m.client.CreatePV(ctx, pv)
}

// CreatePVC 创建PVC
func (m *StorageManager) CreatePVC(ctx context.Context, config PVCConfig) (*corev1.PersistentVolumeClaim, error) {
    pvc := &corev1.PersistentVolumeClaim{
        ObjectMeta: metav1.ObjectMeta{
            Name:      config.Name,
            Namespace: config.Namespace,
        },
        Spec: corev1.PersistentVolumeClaimSpec{
            AccessModes: []corev1.PersistentVolumeAccessMode{
                corev1.ReadWriteOnce,
            },
            Resources: corev1.VolumeResourceRequirements{
                Requests: corev1.ResourceList{
                    corev1.ResourceStorage: resource.MustParse(config.Size),
                },
            },
            StorageClassName: &config.StorageClass,
        },
    }
    
    return m.client.CreatePVC(ctx, pvc)
}
```

## 三、面试高频题

### Q1: PV和PVC的区别？

```
A:
1. PV是集群资源
2. PVC是用户请求
3. PV绑定PVC
```

### Q2: 如何实现动态 provisioning？

```
A:
1. StorageClass
2. Provisioner
3. 自动创建PV
```

## 四、自测题

1. 解释存储架构
2. 如何实现PV/PVC？
3. 如何动态创建？

---

## 参考文档

- [K8s Storage](https://kubernetes.io/docs/concepts/storage/)
- [CSI Spec](https://github.com/container-storage-interface/spec)
