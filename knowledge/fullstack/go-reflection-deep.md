# Go 反射与元编程深度解析

> 深入 Go 反射机制：reflect包源码、类型系统、动态调用。
> 源码级分析，包含实战案例。
> 适用对象：Go工程师、框架开发者

---

## 1. reflect 包核心

### 1.1 Type 和 Value

```go
// reflect_intro.go

package main

import (
    "fmt"
    "reflect"
)

func main() {
    var x float64 = 3.14
    
    // 获取 Type
    t := reflect.TypeOf(x)
    fmt.Println("Type:", t.Name(), t.Kind())
    
    // 获取 Value
    v := reflect.ValueOf(x)
    fmt.Println("Value:", v.Float())
    
    // 修改值（需要可设置的 Value）
    p := reflect.ValueOf(&x)
    p.Elem().SetFloat(2.71)
    fmt.Println("Modified:", x)
}
```

### 1.2 Kind 和 Type

```go
// kind_type.go

package reflect

// Kind 表示类型的底层类别
type Kind uint

const (
    Invalid Kind = iota
    Bool
    Int
    Int8
    Int16
    Int32
    Int64
    Uint
    Uint8
    Uint16
    Uint32
    Uint64
    Uintptr
    Float32
    Float64
    Complex64
    Complex128
    Array
    Chan
    Func
    Interface
    Map
    Ptr
    Slice
    String
    Struct
    UnsafePointer
)

// Type 表示一个Go类型
type Type interface {
    Align() int
    FieldAlign() int
    Method(int) Method
    MethodByName(string) (Method, bool)
    NumMethod() int
    Name() string
    PkgPath() string
    Size() uintptr
    String() string
    Kind() Kind
    Implements(Type) bool
    AssignableTo(Type) bool
    ConvertibleTo(Type) bool
    Comparable() bool
}
```

---

## 2. 动态调用

### 2.1 函数反射

```go
// reflect_func.go

package reflect

import (
    "reflect"
)

// Call 动态调用函数
func Call(fn interface{}, args ...interface{}) []reflect.Value {
    v := reflect.ValueOf(fn)
    if v.Kind() != reflect.Func {
        panic("not a function")
    }
    
    // 检查参数
    if v.Type().NumIn() != len(args) {
        panic("argument count mismatch")
    }
    
    // 转换参数
    in := make([]reflect.Value, len(args))
    for i, arg := range args {
        in[i] = reflect.ValueOf(arg)
    }
    
    return v.Call(in)
}

// MethodCall 动态调用方法
func MethodCall(obj interface{}, methodName string, args ...interface{}) []reflect.Value {
    v := reflect.ValueOf(obj)
    m := v.MethodByName(methodName)
    if !m.IsValid() {
        panic("method not found")
    }
    
    in := make([]reflect.Value, len(args))
    for i, arg := range args {
        in[i] = reflect.ValueOf(arg)
    }
    
    return m.Call(in)
}
```

### 2.2 实战案例：ORM

```go
// orm.go

package orm

import (
    "database/sql"
    "reflect"
)

type Model struct {
    Table string
}

func Query(db *sql.DB, model interface{}) error {
    v := reflect.ValueOf(model).Elem()
    t := v.Type()
    
    // 获取表名
    tableName := t.Field(0).Tag.Get("table")
    
    // 执行查询
    rows, err := db.Query("SELECT * FROM " + tableName)
    if err != nil {
        return err
    }
    defer rows.Close()
    
    // 扫描结果
    for rows.Next() {
        // 创建新实例
        instance := reflect.New(t).Elem()
        
        // 扫描列
        values := make([]interface{}, t.NumField())
        for i := 0; i < t.NumField(); i++ {
            values[i] = instance.Field(i).Addr().Interface()
        }
        
        err := rows.Scan(values...)
        if err != nil {
            return err
        }
        
        // 追加到结果
        v.Set(reflect.Append(v, instance))
    }
    
    return rows.Err()
}
```

---

## 3. 元编程

### 3.1 结构体标签解析

```go
// struct_tags.go

package reflection

import (
    "reflect"
    "strings"
)

type FieldInfo struct {
    Name     string
    JSONName string
    Type     reflect.Type
    Tag      reflect.StructTag
}

func ParseStructInfo(t reflect.Type) []FieldInfo {
    var fields []FieldInfo
    
    for i := 0; i < t.NumField(); i++ {
        field := t.Field(i)
        
        info := FieldInfo{
            Name:   field.Name,
            Type:   field.Type,
            Tag:    field.Tag,
        }
        
        // 解析 JSON 标签
        jsonTag := field.Tag.Get("json")
        if jsonTag != "" {
            parts := strings.Split(jsonTag, ",")
            info.JSONName = parts[0]
        }
        
        fields = append(fields, info)
    }
    
    return fields
}
```

### 3.2 动态对象映射

```go
// mapper.go

package reflection

import (
    "reflect"
)

type Mapper struct{}

func (m *Mapper) Map(src, dst interface{}) error {
    srcVal := reflect.ValueOf(src).Elem()
    dstVal := reflect.ValueOf(dst).Elem()
    
    srcType := srcVal.Type()
    dstType := dstVal.Type()
    
    for i := 0; i < srcType.NumField(); i++ {
        srcField := srcType.Field(i)
        dstField, ok := dstType.FieldByName(srcField.Name)
        if !ok {
            continue
        }
        
        if srcField.Type == dstField.Type {
            dstVal.Field(i).Set(srcVal.Field(i))
        }
    }
    
    return nil
}
```

---

## 4. 性能考虑

### 4.1 反射性能

```
反射性能对比：

普通调用：1ns
反射调用：100-1000ns

原因：
1. 类型检查开销
2. 动态分发开销
3. 内存分配开销
```

### 4.2 优化建议

```go
// optimize.go

package reflection

// 1. 缓存反射结果
type CachedReflection struct {
    cache map[reflect.Type][]FieldInfo
}

func (c *CachedReflection) GetInfo(t reflect.Type) []FieldInfo {
    if info, ok := c.cache[t]; ok {
        return info
    }
    
    info := parseFields(t)
    c.cache[t] = info
    return info
}

// 2. 使用接口而非反射
type Mappable interface {
    MapTo(interface{}) error
}

// 3. 代码生成替代反射
// 使用 go:generate 生成映射代码
```

---

## 5. 实战案例

### 5.1 动态 API 路由

```go
// router.go

package handler

import (
    "net/http"
    "reflect"
)

type Router struct {
    handlers map[string]reflect.Value
}

func (r *Router) Register(method string, handler interface{}) {
    r.handlers[method] = reflect.ValueOf(handler)
}

func (r *Router) Handle(w http.ResponseWriter, r *http.Request) {
    handler := r.handlers[r.Method]
    if handler.IsValid() {
        handler.Call([]reflect.Value{
            reflect.ValueOf(w),
            reflect.ValueOf(r),
        })
    }
}
```

---

## 6. 总结

### 6.1 核心原理

| 概念 | 说明 |
|------|------|
| Type | 运行时类型信息 |
| Value | 运行时值 |
| Kind | 类型类别 |
| reflect.TypeOf | 获取Type |
| reflect.ValueOf | 获取Value |

### 6.2 最佳实践

- [ ] 优先使用接口而非反射
- [ ] 缓存反射结果
- [ ] 注意性能影响
- [ ] 使用代码生成替代

---

*最后更新：2026-08-11*
*作者：Ryan*
