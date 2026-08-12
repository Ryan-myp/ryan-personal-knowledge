# TypeScript 高级类型系统深度实现

> **版本**: v1.0  
> **日期**: 2026-08-13  
> **作者**: Ryan  
> **分类**: 全栈/前端  
> **难度**: 高级

---

## 一、条件类型

### 1.1 基础语法

```typescript
// 条件类型基础
type IsString<T> = T extends string ? true : false;

type A = IsString<string>;   // true
type B = IsString<number>;   // false

// 嵌套条件
type DeepNullable<T> = T extends object
  ? { [K in keyof T]: DeepNullable<T[K]> | null }
  : T | null;
```

### 1.2 分布式条件类型

```typescript
// 分布式条件类型 - 自动展开联合类型
type ToArray<T> = T extends any ? T[] : never;

type Result = ToArray<string | number>;
// 等价于: string[] | number[]

// 实际应用
type ExtractString<T> = T extends string ? T : never;
type OnlyStrings = ExtractString<string | number | boolean>; // string
```

---

## 二、映射类型

### 2.1 基础映射

```typescript
// 将所有属性变为可选
type Partial<T> = {
  [P in keyof T]?: T[P];
};

// 将所有属性变为只读
type Readonly<T> = {
  readonly [P in keyof T]: T[P];
};

// 移除指定属性
type Without<T, K extends keyof T> = {
  [P in Exclude<keyof T, K>]: T[P];
};

type User = { id: number; name: string; age: number };
type UserWithoutAge = Without<User, 'age'>;
```

### 2.2 条件映射

```typescript
// 只保留字符串属性
type StringOnly<T> = {
  [P in keyof T as T[P] extends string ? P : never]: T[P];
};

type Filtered = StringOnly<{ a: string; b: number; c: string }>;
// { a: string; c: string }

// 添加前缀
type Prefixed<T, P extends string> = {
  [K in keyof T as `${P}_${Extract<K, string>}`]: T[K];
};

type Person = { name: string; age: number };
type PrefixedPerson = Prefixed<Person, 'user'>;
// { user_name: string; user_age: number }
```

---

## 三、泛型约束与推断

### 3.1 泛型约束

```typescript
// 基础约束
function getProperty<T, K extends keyof T>(obj: T, key: K): T[K] {
  return obj[key];
}

// 多重约束
interface HasLength {
  length: number;
}

function logLength<T extends HasLength>(obj: T): void {
  console.log(obj.length);
}

logLength("hello");      // ✅ string 有 length
logLength([1, 2, 3]);    // ✅ array 有 length
logLength(42);           // ❌ number 没有 length
```

### 3.2 泛型推断

```typescript
// 自动推断
type ElementType<T> = T extends (infer E)[] ? E : T;

type Num = ElementType<number[]>;    // number
type Str = ElementType<string>;      // string

// 条件推断
type FirstArg<T> = T extends (arg: infer A, ...args: any[]) => any
  ? A
  : never;

type Fn = (x: number, y: string) => boolean;
type Arg1 = FirstArg<Fn>;  // number

// 递归推断
type Flatten<T> = T extends (infer U)[] ? Flatten<U> : T;
type Flat = Flatten<number[][][]>;  // number
```

---

## 四、模板字面量类型

### 4.1 基础用法

```typescript
// 拼接字符串
type World = "world";
type Greeting = `hello ${World}`;  // "hello world"

// 联合类型扩展
type Verbs = "run" | "jump" | "walk";
type Actions = `don't ${Verbs}`;
// "don't run" | "don't jump" | "don't walk"
```

### 4.2 实用场景

```typescript
// API 端点生成
type ApiPath<T extends string> = `/api/${T}`;
type UsersEndpoint = ApiPath<"users">;  // "/api/users"

// 事件名称
type EventName<T extends string> = `on${Capitalize<T>}`;
type ClickEvent = EventName<"click">;  // "onClick"

// CSS 属性
type CSSProperty = `--${string}`;
type CustomProp = CSSProperty;  // `--${string}`
```

---

## 五、高级工具类型

### 5.1 ReturnType 实现

```typescript
// 手动实现 ReturnType
type MyReturnType<T extends (...args: any[]) => any> = 
  T extends (...args: any[]) => infer R ? R : never;

type Fn = () => string;
type Result = MyReturnType<Fn>;  // string
```

### 5.2 自定义工具类型

```typescript
// 深只读
type DeepReadonly<T> = {
  readonly [K in keyof T]: T[K] extends object
    ? DeepReadonly<T[K]>
    : T[K];
};

interface Config {
  host: string;
  ports: number[];
  features: {
    logging: boolean;
    cache: {
      ttl: number;
    };
  };
}

type ReadonlyConfig = DeepReadonly<Config>;
// Config 及其嵌套对象都变为只读
```

### 5.3 递归类型

```typescript
// 树形结构
interface TreeNode<T> {
  value: T;
  children?: TreeNode<T>[];
}

// 获取所有值类型
type AllValues<T> = T extends TreeNode<infer V>
  ? V | AllValues<T['children'] extends TreeNode<infer V> ? T['children'] : never>
  : never;
```

---

## 六、实战应用

### 6.1 API 响应类型

```typescript
// API 响应包装
type ApiResponse<T> = {
  code: number;
  data: T;
  message: string;
};

// 使用
type UserResponse = ApiResponse<{ id: number; name: string }>;

// 自动推导
function request<T>(url: string): Promise<ApiResponse<T>> {
  return fetch(url).then(res => res.json());
}

const users = await request<User[]>('/api/users');
```

### 6.2 表单验证

```typescript
// 表单字段类型
type FormField<T> = {
  value: T;
  error?: string;
  touched?: boolean;
};

type LoginForm = {
  email: FormField<string>;
  password: FormField<string>;
};

// 获取所有字段值
type FormValues<T> = {
  [K in keyof T]: T[K] extends FormField<infer V> ? V : never;
};

type LoginValues = FormValues<LoginForm>;
// { email: string; password: string }
```

### 6.3 路由类型

```typescript
// 路由类型安全
type Routes = {
  '/users': { id: number };
  '/posts': { postId: string };
  '/settings': Record<string, never>;
};

type RouteParams<T extends keyof Routes> = Routes[T];

function navigate<T extends keyof Routes>(
  route: T, 
  params: RouteParams<T>
): void {
  // 类型安全的导航
}

navigate('/users', { id: 1 });        // ✅
navigate('/posts', { postId: 'abc' }); // ✅
navigate('/users', { postId: 'abc' }); // ❌ 类型错误
```

---

## 七、性能优化

### 7.1 避免递归过深

```typescript
// 浅层递归
type DeepPick<T, K extends keyof T> = {
  [P in K]: T[P] extends object ? DeepPick<T[P], keyof T[P]> : T[P];
};

// 限制深度
type DeepPickLimited<T, K extends keyof T, Depth extends number = 3> = 
  Depth extends 0 ? T[K] :
  T[K] extends object ? { [P in keyof T[K]]: DeepPickLimited<T[K], P, Decrement<Depth>> } :
  T[K];

type Decrement<N extends number> = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9] extends 
  [infer F, ...infer Rest] ? Rest extends [infer F2, ...infer R2] 
  ? F2 extends N ? F : never : never : never;
```

---

## 八、总结

| 类型系统特性 | 应用场景 |
|-------------|---------|
| 条件类型 | 类型选择、派生类型 |
| 映射类型 | 对象转换、属性过滤 |
| 泛型推断 | 自动类型推导 |
| 模板字面量 | 字符串模板、枚举扩展 |
| 递归类型 | 树形结构、深度操作 |

---

## 九、自测题

1. **条件类型的分布式特性是什么？**
   - 自动展开联合类型，对每个成员分别计算

2. **映射类型中的 `keyof` 有什么用？**
   - 遍历对象的所有键

3. **如何用模板字面量类型生成事件名？**
   - `` type Event<T> = `on${Capitalize<T>}` ``

4. **泛型推断的最佳实践？**
   - 使用 `infer` 关键字，合理设计约束

EOF
echo "✅ 已创建: fullstack/typescript-advanced-types-deep.md"