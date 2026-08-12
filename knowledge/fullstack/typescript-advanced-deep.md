# TypeScript 高级类型系统深度实现

> **文档级别**: Level 5 - 专家级  
> **创建日期**: 2026-08-13  
> **状态**: ✅ 已补齐

---

## 一、条件类型与模板字面量

```typescript
// 文件: types/conditional.ts

// ─── 条件类型基础 ───
type IsString<T> = T extends string ? true : false;
type IsNumber<T> = T extends number ? true : false;

type Test1 = IsString<string>;    // true
type Test2 = IsString<number>;    // false
type Test3 = IsString<string | number>; // true (分布到联合类型)

// ─── 模板字面量类型 ───
type EventName<T extends string> = `on${Capitalize<T>}`;
type ClickEvent = EventName<"click">;  // "onClick"

type ApiMethod = "get" | "post" | "put" | "delete";
type HttpMethod = `HTTP_${Uppercase<ApiMethod>}`;
// "HTTP_GET" | "HTTP_POST" | "HTTP_PUT" | "HTTP_DELETE"

// ─── 实际应用: API 响应类型 ───
type ApiResponse<T> = {
  data: T;
  status: number;
  message: string;
};

type UserResponse = ApiResponse<{
  id: string;
  name: string;
  email: string;
}>;
```

---

## 二、映射类型与工具类型

```typescript
// 文件: types/mapped.ts

// ─── 自定义 Readonly ───
type MyReadonly<T> = {
  readonly [K in keyof T]: T[K];
};

// ─── Partial (可选属性) ───
type MyPartial<T> = {
  [K in keyof T]?: T[K];
};

// ─── Pick (选择属性) ───
type MyPick<T, K extends keyof T> = {
  [P in K]: T[P];
};

// ─── 实际应用: 广告配置类型 ───
interface AdConfig {
  budget: number;
  targetCPM: number;
  bidStrategy: string;
  audience: AudienceTargeting;
  schedule: ScheduleConfig;
}

type ConfigInput = Partial<AdConfig>;  // 所有字段可选
type BudgetConfig = Pick<AdConfig, 'budget' | 'targetCPM'>;  // 仅预算相关
```

---

## 三、泛型约束与推断

```typescript
// 文件: types/generics.ts

// ─── 泛型约束 ───
interface HasID {
  id: string;
}

function getID<T extends HasID>(item: T): string {
  return item.id;
}

// ─── 泛型推断 (Infer) ───
type ReturnType<T> = T extends (...args: any[]) => infer R ? R : never;

type Fn = (x: string, y: number) => boolean;
type Result = ReturnType<Fn>;  // boolean

// ─── 条件推断: 解包 Promise ───
type UnwrapPromise<T> = T extends Promise<infer U> ? U : T;
type Unwrapped = UnwrapPromise<Promise<string>>;  // string

// ─── 实际应用: 类型安全的 API Client ───
type Endpoint<T extends (...args: any[]) => any> = {
  fn: T;
  path: string;
  method: 'GET' | 'POST' | 'PUT' | 'DELETE';
};

type UserAPI = {
  getUser: Endpoint<(id: string) => Promise<User>>;
  createUser: Endpoint<(data: CreateUserInput) => Promise<User>>;
};
```

---

## 四、模板类型实战

```typescript
// 文件: types/template-literals.ts

// ─── REST API 路径类型 ───
type RouteParam<T extends string> = `:${T}`;
type RoutePath<Paths extends string> = Paths extends `${string}/${string}`
  ? `/api/${Paths}`
  : `/api/${Paths}`;

type UserRoute = RoutePath<'users/:id'>;  // "/api/users/:id"

// ─── 事件类型推导 ───
type EventType = "click" | "submit" | "change";
type EventHandler<T extends EventType> = (event: `on${Capitalize<T>}`) => void;

// ─── 表单字段类型 ───
type FormField<T extends string, V> = {
  name: T;
  value: V;
  error?: string;
  required?: boolean;
};

type UserForm = FormField<"email", string> & 
                FormField<"password", string> &
                FormField<"name", string>;
```

---

## 五、参考资料

```
核心特性:
├── TypeScript Handbook
├── Total TypeScript (Matt Pocock)
└── TypeScript Deep Dive

工具库:
├── type-fest
├── ts-toolbelt
└── z-schema
```

---

*文档版本: v1.0*  
*最后更新: 2026-08-13*  
*作者: Ryan*
