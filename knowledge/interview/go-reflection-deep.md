# Go反射机制深入 - 资深专家深度实现

## 一、反射基础

```go
package main

import (
    "fmt"
    "reflect"
)

func reflectType(v interface{}) {
    t := reflect.TypeOf(v)
    fmt.Printf("Type: %v, Kind: %v\n", t.Name(), t.Kind())
}

func reflectValue(v interface{}) {
    val := reflect.ValueOf(v)
    fmt.Printf("Value: %v, CanSet: %v\n", val, val.CanSet())
}
```

## 二、反射原理

```go
// reflect.Type 实现
typertype struct {
    size       uintptr
    ptrdata    uintptr
    hash       uint32
    tflag      tflag
    align      uint8
    fieldalign uint8
    kind       uint8
    alg        *typeAlg
    gcdata    *byte
    str       nameOff
    ptrToThis typeOff
}

// reflect.Value 核心结构
type value struct {
    typ  unsafe.Pointer  // *rtype
    ptr  unsafe.Pointer  // 数据指针
    flag flag            // 访问权限
}

func (v value) Interface() interface{} {
    if !v.ok() {
        return nil
    }
    return unpackEface(v)
}
```

## 三、反射应用

```go
// 动态调用方法
func callMethod(obj interface{}, methodName string, args ...interface{}) interface{} {
    v := reflect.ValueOf(obj)
    m := v.MethodByName(methodName)
    if !m.IsValid() {
        panic(fmt.Sprintf("method %s not found", methodName))
    }
    
    in := make([]reflect.Value, len(args))
    for i, arg := range args {
        in[i] = reflect.ValueOf(arg)
    }
    
    results := m.Call(in)
    if len(results) > 0 {
        return results[0].Interface()
    }
    return nil
}

// 结构体序列化
func structToMap(s interface{}) map[string]interface{} {
    v := reflect.ValueOf(s)
    if v.Kind() == reflect.Ptr {
        v = v.Elem()
    }
    
    m := make(map[string]interface{})
    t := v.Type()
    
    for i := 0; i < v.NumField(); i++ {
        field := t.Field(i)
        value := v.Field(i)
        
        // 获取json标签
        tag := field.Tag.Get("json")
        key := strings.Split(tag, ",")[0]
        if key == "" {
            key = field.Name
        }
        
        m[key] = value.Interface()
    }
    
    return m
}
```

## 四、面试高频题

### Q1: 反射的性能开销是什么？

```
A:
1. 类型检查开销
2. 间接寻址开销
3. 无法内联优化
```

### Q2: 如何实现动态代理？

```
A:
1. 使用reflect包
2. 拦截方法调用
3. 转发到实际对象
```

## 五、自测题

1. 解释反射原理
2. 如何实现动态调用？
3. 如何处理反射性能？

---

## 参考文档

- [Go Reflect Package](https://pkg.go.dev/reflect)
- [Effective Go Reflection](https://go.dev/blog/effective-go)
