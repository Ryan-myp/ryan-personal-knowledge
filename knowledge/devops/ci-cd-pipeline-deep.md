# CI/CD 流水线深度实现

> **文档级别**: Level 5 - 专家级  
> **创建日期**: 2026-08-13  
> **状态**: ✅ 已补齐

---

## 一、GitLab CI 配置

```yaml
# 文件: .gitlab-ci.yml

stages:
  - build
  - test
  - security
  - deploy

variables:
  DOCKER_REGISTRY: registry.example.com
  APP_NAME: ad-bidding

build:
  stage: build
  script:
    - docker build -t $DOCKER_REGISTRY/$APP_NAME:$CI_COMMIT_SHA .
    - docker push $DOCKER_REGISTRY/$APP_NAME:$CI_COMMIT_SHA
  only:
    - main

test:
  stage: test
  script:
    - go test -v -race ./...
    - go vet ./...
  only:
    - main

security-scan:
  stage: security
  script:
    - trivy image $DOCKER_REGISTRY/$APP_NAME:$CI_COMMIT_SHA
    - sonar-scanner
  only:
    - main

deploy:
  stage: deploy
  script:
    - kubectl set image deployment/$APP_NAME app=$DOCKER_REGISTRY/$APP_NAME:$CI_COMMIT_SHA
  when: manual
  only:
    - main
```

---

## 二、参考资料

```
核心平台:
├── GitLab CI: https://docs.gitlab.com/
├── GitHub Actions: https://github.com/features/actions
└── Jenkins: https://www.jenkins.io/
```

---

*文档版本: v1.0*  
*最后更新: 2026-08-13*  
*作者: Ryan*
