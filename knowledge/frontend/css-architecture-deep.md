# CSS 架构设计深度实现

> **文档级别**: Level 5 - 专家级  
> **创建日期**: 2026-08-13  
> **状态**: ✅ 已补齐

---

## 一、BEM 命名规范

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        BEM 命名规范                                         │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Block (块)                                                                   │
│  └─ .button {}                                                              │
│                                                                             │
│  Element (元素)                                                               │
│  └─ .button__icon {}                                                        │
│                                                                             │
│  Modifier (修饰符)                                                           │
│  └─ .button--primary {}                                                     │
│  └─ .button__icon--disabled {}                                              │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 二、CSS Modules 实战

```css
/* 文件: frontend/css/Card.module.css */
.card {
  padding: 16px;
  border-radius: 8px;
  background: var(--color-surface);
}

.card__header {
  font-size: 18px;
  font-weight: 600;
  margin-bottom: 8px;
}

.card__body {
  color: var(--color-text-secondary);
}

.card--featured {
  border: 2px solid var(--color-primary);
}
```

```jsx
// 文件: frontend/css/Card.jsx
import styles from './Card.module.css';

function Card({ featured, children }) {
  return (
    <div className={`${styles.card} ${featured ? styles['card--featured'] : ''}`}>
      <div className={styles.card__header}>Title</div>
      <div className={styles.card__body}>{children}</div>
    </div>
  );
}
```

---

## 三、参考资料

```
核心规范:
├── BEM: https://getbem.com/
├── CSS Modules: https://github.com/css-modules/css-modules
└── Tailwind CSS: https://tailwindcss.com/
```

---

*文档版本: v1.0*  
*最后更新: 2026-08-13*  
*作者: Ryan*
