# Go反射机制深度实现 - 资深专家

## 一、反射基础

### 1.1 反射三定律

```go
// 反射第一定律: 反射可以从interface变量读取值
func reflectFromInterface(i interface{}) {
    // 获取interface的值
    v := reflect.ValueOf(i)
    
    // 获取类型信息
    t := reflect.TypeOf(i)
    
    fmt.Printf("Type: %v, Kind: %v\n", t, v.Kind())
}

// 反射第二定律: 反射可以写回interface变量
func reflectWriteToInterface(i interface{}) {
    v := reflect.ValueOf(i)
    
    // 必须是指针才能修改
    if v.Kind() != reflect.Ptr {
        panic("must be a pointer")
    }
    
    // 解引用并修改
    elem := v.Elem()
    if elem.Kind() == reflect.Int {
        elem.SetInt(100)
    }
}

// 反射第三定律: 反射无法修改未导出字段
type Person struct {
    Name string
    age  int // 小写，无法通过反射修改
}
```

### 1.2 类型与值

```go
func analyzeTypeValue(i interface{}) {
    t := reflect.TypeOf(i)
    v := reflect.ValueOf(i)
    
    fmt.Printf("Type: %v\n", t)
    fmt.Printf("Kind: %v\n", v.Kind())
    fmt.Printf("CanAddr: %v\n", v.CanAddr())
    fmt.Printf("CanSet: %v\n", v.CanSet())
    
    // 获取字段
    if t.Kind() == reflect.Struct {
        for i := 0; i < t.NumField(); i++ {
            field := t.Field(i)
            value := v.Field(i)
            fmt.Printf("Field: %s, Type: %v, Value: %v\n", 
                field.Name, field.Type, value)
        }
    }
}
```

## 二、反射进阶

### 2.1 动态调用方法

```go
// 通过反射调用方法
func callMethod(obj interface{}, methodName string, args ...interface{}) {
    v := reflect.ValueOf(obj)
    method := v.MethodByName(methodName)
    
    if !method.IsValid() {
        panic(fmt.Sprintf("method %s not found", methodName))
    }
    
    // 准备参数
    in := make([]reflect.Value, len(args))
    for i, arg := range args {
        in[i] = reflect.ValueOf(arg)
    }
    
    // 调用方法
    results := method.Call(in)
    
    // 处理返回值
    for _, result := range results {
        fmt.Printf("Result: %v\n", result)
    }
}

// 泛型反射调用
func genericCall[T any](obj T, methodName string, args ...interface{}) []reflect.Value {
    v := reflect.ValueOf(obj)
    method := v.MethodByName(methodName)
    
    if !method.IsValid() {
        panic("method not found")
    }
    
    in := make([]reflect.Value, len(args))
    for i, arg := range args {
        in[i] = reflect.ValueOf(arg)
    }
    
    return method.Call(in)
}
```

### 2.2 动态创建对象

```go
// 动态创建结构体
func createStruct(typ reflect.Type, values map[string]interface{}) (interface{}, error) {
    // 创建指针
    ptr := reflect.New(typ)
    elem := ptr.Elem()
    
    // 设置字段
    for name, value := range values {
        field := elem.FieldByName(name)
        if !field.IsValid() {
            continue
        }
        
        v := reflect.ValueOf(value)
        if v.Type().AssignableTo(field.Type()) {
            field.Set(v)
        }
    }
    
    return ptr.Interface(), nil
}

// 动态解析JSON
func parseJSON(typ reflect.Type, data []byte) (interface{}, error) {
    var raw map[string]interface{}
    if err := json.Unmarshal(data, &raw); err != nil {
        return nil, err
    }
    
    return createStruct(typ, raw)
}
```

## 三、生产实践

### 3.1 ORM框架实现

```go
// 简易ORM
typeORM struct {
    db *sql.DB
}

// 结构体映射
type Mapper struct {
    tableName string
    fields    map[string]FieldMapper
}

type FieldMapper struct {
    columnName string
    fieldType  reflect.Type
}

// 查询构建
func (m *Mapper) BuildSelect(table string, conditions map[string]interface{}) string {
    columns := make([]string, 0, len(m.fields))
    for _, field := range m.fields {
        columns = append(columns, field.columnName)
    }
    
    sql := fmt.Sprintf("SELECT %s FROM %s", 
        strings.Join(columns, ", "), table)
    
    if len(conditions) > 0 {
        sql += " WHERE " + buildConditions(conditions)
    }
    
    return sql
}

// 结果映射
func (m *Mapper) ScanRows(rows *sql.Rows, dest interface{}) error {
    v := reflect.ValueOf(dest).Elem()
    t := v.Type()
    
    columns, _ := rows.Columns()
    values := make([]interface{}, len(columns))
    valuePtrs := make([]interface{}, len(columns))
    
    for i := range values {
        valuePtrs[i] = &values[i]
    }
    
    if err := rows.Scan(valuePtrs...); err != nil {
        return err
    }
    
    // 映射到结构体
    for i, col := range columns {
        if field, ok := m.fields[col]; ok {
            fieldValue := v.FieldByName(field.structFieldName)
            fieldValue.Set(reflect.ValueOf(values[i]))
        }
    }
    
    return nil
}
```

### 3.2 API序列化

```go
// 自定义JSON序列化
func CustomMarshal(i interface{}) ([]byte, error) {
    v := reflect.ValueOf(i)
    t := reflect.TypeOf(i)
    
    result := make(map[string]interface{})
    
    // 遍历所有字段
    for i := 0; i < v.NumField(); i++ {
        field := t.Field(i)
        value := v.Field(i)
        
        // 获取tag
        tag := field.Tag.Get("json")
        if tag == "-" {
            continue
        }
        
        // 解析tag
        parts := strings.Split(tag, ",")
        fieldName := parts[0]
        if fieldName == "" {
            fieldName = field.Name
        }
        
        // 处理omitempty
        if len(parts) > 1 && parts[1] == "omitempty" {
            if isZeroValue(value) {
                continue
            }
        }
        
        result[fieldName] = value.Interface()
    }
    
    return json.Marshal(result)
}

func isZeroValue(v reflect.Value) bool {
    switch v.Kind() {
    case reflect.String:
        return v.String() == ""
    case reflect.Int, reflect.Int8, reflect.Int16, reflect.Int32, reflect.Int64:
        return v.Int() == 0
    case reflect.Uint, reflect.Uint8, reflect.Uint16, reflect.Uint32, reflect.Uint64:
        return v.Uint() == 0
    case reflect.Float32, reflect.Float64:
        return v.Float() == 0
    case reflect.Bool:
        return !v.Bool()
    case reflect.Interface, reflect.Ptr:
        return v.IsNil()
    }
    return false
}
```

## 四、性能优化

### 4.1 缓存反射结果

```go
type ReflectionCache struct {
    mu      sync.RWMutex
    cache   map[string]*ReflectionInfo
}

type ReflectionInfo struct {
    fields    map[string]reflect.StructField
    methods   map[string]reflect.Method
    typeNum   int
}

// 获取结构体字段信息
func (rc *ReflectionCache) GetStructFields(t reflect.Type) map[string]reflect.StructField {
    key := t.String()
    
    rc.mu.RLock()
    info, ok := rc.cache[key]
    rc.mu.RUnlock()
    
    if ok {
        return info.fields
    }
    
    // 计算并缓存
    fields := make(map[string]reflect.StructField)
    for i := 0; i < t.NumField(); i++ {
        field := t.Field(i)
        fields[field.Name] = field
    }
    
    info = &ReflectionInfo{
        fields: fields,
        typeNum: t.NumField(),
    }
    
    rc.mu.Lock()
    rc.cache[key] = info
    rc.mu.Unlock()
    
    return fields
}
```

### 4.2 避免反射

```go
// 使用interface避免反射
type Serializable interface {
    Marshal() ([]byte, error)
    Unmarshal([]byte) error
}

// 编译期类型检查
func Serialize(s Serializable) ([]byte, error) {
    return s.Marshal()
}

// 反射作为fallback
func ReflectiveSerialize(i interface{}) ([]byte, error) {
    if s, ok := i.(Serializable); ok {
        return s.Marshal()
    }
    
    // 使用反射作为fallback
    return CustomMarshal(i)
}
```

## 五、面试高频题

### Q1: 反射有哪些应用场景？

```
A:
1. ORM框架实现
2. JSON/XML序列化
3. 依赖注入
4. 测试框架
5. 模板引擎
```

### Q2: 反射的性能开销如何？

```
A:
1. 类型检查: O(1)
2. 字段访问: O(n)
3. 方法调用: O(1)
4. 建议: 热路径避免反射
```

### Q3: 如何优化反射性能？

```
A:
1. 缓存反射结果
2. 使用interface避免反射
3. 批量处理减少重复调用
4. 编译期代码生成替代
```

## 六、自测题

1. 解释反射三定律
2. 如何通过反射调用方法？
3. 如何实现动态ORM？

---

## 参考文档

- [Go Channel深入](./go-channel-impl-deep.md)
- [Go调度器深入](./go-scheduler-deep.md)
- [Go内存管理深入](./go-memory-management-deep.md)
