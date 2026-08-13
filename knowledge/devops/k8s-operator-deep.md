# K8s Operator模式 - 资深专家深度实现

## 一、架构概览

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      K8s Operator模式                                    │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   CRD (Custom Resource Definition)                                       │
│   ├── apiVersion: apps.example.com/v1                                   │
│   ├── kind: MyApp                                                      │
│   └── spec: {...}                                                       │
│                                                                         │
│   Controller                                                             │
│   ├── Watch CRD                                                         │
│   ├── Reconcile Loop                                                     │
│   ├── Create/Update Resources                                           │
│   └── Handle Errors                                                     │
│                                                                         │
│   工作流程:                                                                │
│   1. 用户创建CR                                                            │
│   2. API Server存储                                                       │
│   3. Controller监听到变化                                                  │
│   4. Reconcile循环                                                        │
│   5. 创建/更新实际资源                                                      │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

## 二、Operator实现

```go
// controllers/myapp_controller.go
type MyAppReconciler struct {
    client.Client
    Scheme   *runtime.Scheme
}

func (r *MyAppReconciler) Reconcile(ctx context.Context, req ctrl.Request) (ctrl.Result, error) {
    // 1. 获取自定义资源
    myApp := &examplev1.MyApp{}
    if err := r.Get(ctx, req.NamespacedName, myApp); err != nil {
        return ctrl.Result{}, client.IgnoreNotFound(err)
    }
    
    // 2. 确保Deployment存在
    deployment := &appsv1.Deployment{}
    if err := r.Get(ctx, types.NamespacedName{Name: myApp.Name, Namespace: myApp.Namespace}, deployment); err != nil {
        if err := r.createDeployment(ctx, myApp); err != nil {
            return ctrl.Result{}, err
        }
    }
    
    // 3. 状态同步
    if !r.isReady(deployment) {
        return ctrl.Result{RequeueAfter: time.Second * 10}, nil
    }
    
    // 4. 更新状态
    myApp.Status.Ready = true
    return ctrl.Result{}, r.Status().Update(ctx, myApp)
}
```

## 三、面试高频题

### Q1: Operator vs Deployment区别？

```
A:
1. Operator封装运维知识
2. 自动化复杂操作
3. 状态自愈合
```

### Q2: 如何实现Reconcile？

```
A:
1. 获取CR
2. 检查期望状态
3. 调整实际状态
4. 处理错误
```

## 四、自测题

1. 解释Operator模式
2. 如何实现Watch机制？
3. 如何处理冲突？

---

## 参考文档

- [K8s Operator文档](https://kubernetes.io/docs/concepts/extend-kubernetes/operator/)
- [Operator Framework](https://operatorframework.io/)
