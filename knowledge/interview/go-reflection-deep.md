# Go反射机制 - 资深专家深度实现

## 一、Type和Value

```go
package main

import (
    "fmt"
    "reflect"
)

func reflectDemo(i interface{}) {
    t := reflect.TypeOf(i)
    v := reflect.ValueOf(i)
    
    fmt.Printf("Type: %v, Kind: %v\n", t, t.Kind())
    fmt.Printf("Value: %v\n", v)
}

// 反射修改值
func reflectModify(i interface{}) {
    v := reflect.ValueOf(i).Elem()
    v.SetInt(100)
}

func main() {
    x := 42
    reflectDemo(x)
    
    reflectModify(&x)
    fmt.Println(x) // 100
}
```

## 二、结构体反射

```go
type User struct {
    Name string `json:"name"`
    Age  int    `json:"age"`
}

func reflectStruct(u User) {
    t := reflect.TypeOf(u)
    v := reflect.ValueOf(u)
    
    for i := 0; i < t.NumField(); i++ {
        field := t.Field(i)
        value := v.Field(i)
        
        fmt.Printf("Field: %s, Type: %v, Value: %v\n", 
            field.Name, field.Type, value)
        
        // 获取tag
        tag := field.Tag.Get("json")
        fmt.Printf("Tag: %s\n", tag)
    }
}
```

## 三、面试高频题

### Q1: 反射的性能开销？

```
A:
1. 运行时类型检查
2. 无法内联优化
3. 建议使用interface传递
```

### Q2: 如何避免反射？

```
A:
1. 使用泛型
2. 使用interface
3. 编译期生成代码
```

## 四、自测题

1. 解释Type和Value关系
2. 如何实现Set?
3. 反射的性能影响？

---

## 参考文档

- [Go反射源码](https://github.com/golang/go/blob/master/src/reflect/type.go)
- [Go博客: 反射](https://go.dev/blog/laws-of-reflection)
