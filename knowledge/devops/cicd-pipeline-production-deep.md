---
title: CI/CD生产流水线深度实现
date: 2026-08-25
status: deep
tags: [CI/CD, GitLab, Jenkins, ArgoCD]
domain: DevOps
level: 专家级
---

# CI/CD生产流水线深度实现

## 一、GitLab CI配置

```yaml
stages:
  - build
  - test
  - security
  - deploy

variables:
  DOCKER_REGISTRY: registry.example.com
  APP_VERSION: ${CI_COMMIT_SHORT_SHA}

build:
  stage: build
  script:
    - docker build -t $DOCKER_REGISTRY/$CI_PROJECT_NAME:$APP_VERSION .
    - docker push $DOCKER_REGISTRY/$CI_PROJECT_NAME:$APP_VERSION
  only:
    - main

test:
  stage: test
  script:
    - go test ./... -coverprofile=coverage.out
    - go vet ./...
  coverage: '/coverage: \d+\.\d+%/'
