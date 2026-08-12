# E2E 测试深度实现

> **文档级别**: Level 5 - 专家级  
> **创建日期**: 2026-08-13  
> **状态**: ✅ 已补齐

---

## 一、Playwright 实战

```typescript
// 文件: testing/e2e/login.spec.ts

import { test, expect } from '@playwright/test';

test.describe('用户登录流程', () => {
  test('正常登录', async ({ page }) => {
    await page.goto('http://localhost:3000/login');
    await page.fill('[name="email"]', 'test@example.com');
    await page.fill('[name="password"]', 'password123');
    await page.click('button[type="submit"]');
    
    await expect(page).toHaveURL('/dashboard');
    await expect(page.locator('.user-avatar')).toBeVisible();
  });
  
  test('错误密码提示', async ({ page }) => {
    await page.goto('http://localhost:3000/login');
    await page.fill('[name="email"]', 'test@example.com');
    await page.fill('[name="password"]', 'wrongpassword');
    await page.click('button[type="submit"]');
    
    await expect(page.locator('.error-message')).toContainText(
      '密码错误'
    );
  });
});
```

---

## 二、Cypress 集成测试

```javascript
// 文件: testing/e2e/ad-dashboard.cy.js

describe('广告竞价系统', () => {
  beforeEach(() => {
    cy.loginAsAdmin();
  });
  
  it('应该显示实时竞价数据', () => {
    cy.visit('/ads/bidding');
    cy.get('.bidding-metrics').should('be.visible');
    cy.get('.request-count').should('have.text');
  });
  
  it('应该能够创建广告计划', () => {
    cy.visit('/ads/create');
    cy.get('#campaign-name').type('Test Campaign');
    cy.get('#budget').type('1000');
    cy.get('#platform-checkbox').check('Google');
    cy.get('#submit-btn').click();
    
    cy.url().should('include', '/ads/success');
    cy.get('.success-message').should('contain', '创建成功');
  });
});
```

---

## 三、参考资料

```
核心工具:
├── Playwright: https://playwright.dev/
├── Cypress: https://www.cypress.io/
└── Selenium: https://www.selenium.dev/
```

---

*文档版本: v1.0*  
*最后更新: 2026-08-13*  
*作者: Ryan*
