# K8s Operator 模式 - 资深专家深度实现

## 一、Operator架构

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    K8s Operator 架构                                       │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   ┌─────────────┐     ┌─────────────┐     ┌─────────────┐             │
│   │  CRD        │     │  Controller │     │  Custom     │             │
│   │  (资源定义)  │────►│  (控制器)    │────►│  Resource   │             │
│   └─────────────┘     └─────────────┘     └─────────────┘             │
│                              │                                          │
│                     ┌────────┴────────┐                                │
│                     ▼                 ▼                                │
│               ┌──────────┐      ┌──────────┐                           │
│               │ Watch    │      │ Reconcile│                           │
│               │  API     │      │  Loop    │                           │
│               └──────────┘      └──────────┘                           │
│                                                                         →
└─────────────────────────────────────────────────────────────────────────┘
```

## 二、Operator实现

```go
package controllers

import (
    "context"
    "fmt"
    "k8s.io/apimachinery/pkg/runtime"
    ctrl "sigs.k8s.io/controller-runtime"
    "sigs.k8s.io/controller-runtime/pkg/client"
)

// MyOperator Controller
type MyOperator struct {
    client client.Client
    scheme *runtime.Scheme
}

// Reconcile  reconciler
func (r *MyOperator) Reconcile(ctx context.Context, req ctrl.Request) (ctrl.Result, error) {
    // 1. 获取资源
    myResource := &v1alpha1.MyResource{}
    if err := r.client.Get(ctx, req.NamespacedName, myResource); err != nil {
        return ctrl.Result{}, client.IgnoreNotFound(err)
    }
    
    // 2. 业务逻辑
    err := r.reconcileMyResource(ctx, myResource)
    if err != nil {
        return ctrl.Result{}, err
    }
    
    // 3. 返回结果
    return ctrl.Result{RequeueAfter: time.Minute}, nil
}

func (r *MyOperator) reconcileMyResource(ctx context.Context, resource *v1alpha1.MyResource) error {
    // 创建或更新下游资源
    dep := &appsv1.Deployment{
        ObjectMeta: metav1.ObjectMeta{
            Name:      resource.Name,
            Namespace: resource.Namespace,
        },
    }
    
    // 确保Deployment存在
    found := &appsv1.Deployment{}
    err := r.client.Get(ctx, types.NamespacedName{Name: dep.Name, Namespace: dep.Namespace}, found)
    if err != nil {
        if errors.IsNotFound(err) {
            // 创建
            if err := r.client.Create(ctx, dep); err != nil {
                return err
            }
        } else {
            return err
        }
    }
    
    // 状态同步
    resource.Status.Ready = true
    return r.client.Status().Update(ctx, resource)
}

// SetupWithManager 注册到manager
func (r *MyOperator) SetupWithManager(mgr ctrl.Manager) error {
    return ctrl.NewControllerManagedBy(mgr).
        For(&v1alpha1.MyResource{}).
        Complete(r)
}
```

## 三、面试高频题

### Q1: Operator模式和传统管理方式有什么区别？

```
A:
1. 自动化程度: Operator自动修复
2. 声明式: 通过CRD描述期望状态
3. 扩展性: 可复用模式
```

### Q2: 如何实现Controller？

```
A:
1. 定义CRD
2. 实现Reconcile循环
3. 监听资源变化
```

## 四、自测题

1. 解释Operator架构
2. 如何实现Reconcile？
3. 如何处理资源删除？

---

## 参考文档

- [K8s Operator Pattern](https://kubernetes.io/docs/concepts/extend-kubernetes/operator/)
- [Controller Runtime](https://book.kubebuilder.io/)
