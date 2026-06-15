# DevOps 深度：Terraform/Helm

> Infrastructure as Code/K8s 包管理/多环境管理

---

## 第一部分：入门引导（5 分钟速览）

### 为什么需要 IaC？

```
手动部署 → 不可复现、易出错
IaC (Terraform) → 可版本控制、可回滚、可审计
```

| 工具 | 作用 |
|------|------|
| Terraform | 基础设施编排（云资源） |
| Helm | K8s 包管理（应用部署） |
| Ansible | 配置管理 |
| Packer | 镜像构建 |

---

## 第二部分：Terraform 深度

### 2.1 核心概念

```
Terraform 工作流：
terraform plan → terraform apply → terraform destroy
```

### 2.2 Terraform 配置

```hcl
# main.tf
terraform {
  required_version = ">= 1.5.0"
  
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.20"
    }
  }
  
  backend "s3" {
    bucket         = "terraform-state-ad-platform"
    key            = "production/terraform.tfstate"
    region         = "us-east-1"
    dynamodb_table = "terraform-locks"
    encrypt        = true
  }
}

provider "aws" {
  region = var.region
}

# VPC
resource "aws_vpc" "main" {
  cidr_block           = "10.0.0.0/16"
  enable_dns_support   = true
  enable_dns_hostnames = true
  
  tags = {
    Name        = "ad-platform-vpc"
    Environment = var.environment
  }
}

# Subnets
resource "aws_subnet" "public" {
  count             = length(var.availability_zones)
  vpc_id            = aws_vpc.main.id
  cidr_block        = cidrsubnet(aws_vpc.main.cidr_block, 8, count.index)
  availability_zone = var.availability_zones[count.index]
  
  tags = {
    Name = "ad-platform-public-${count.index}"
  }
}

# EC2 实例
resource "aws_instance" "bidding" {
  count         = var.bidding_count
  ami           = var.ami_id
  instance_type = var.instance_type
  subnet_id     = aws_subnet.public[count.index % length(aws_subnet.public)].id
  
  tags = {
    Name = "bidding-${count.index}"
  }
}

# RDS
resource "aws_db_instance" "mysql" {
  identifier     = "ad-platform-mysql"
  engine         = "mysql"
  engine_version = "8.0"
  instance_class = var.db_instance_class
  
  allocated_storage = 100
  storage_type      = "gp3"
  
  db_name  = "ad_platform"
  username = var.db_username
  password = var.db_password
  
  vpc_security_group_ids = [aws_security_group.mysql.id]
  db_subnet_group_name   = aws_db_subnet_group.main.name
  
  backup_retention_period = 7
  multi_az                = true
  
  tags = {
    Name = "ad-platform-mysql"
  }
}

# ElastiCache Redis
resource "aws_elasticache_cluster" "redis" {
  cluster_id           = "ad-platform-redis"
  engine               = "redis"
  node_type            = "cache.r6g.large"
  num_cache_nodes      = 3
  port                 = 6379
  
  subnet_group_name   = aws_elasticache_subnet_group.main.name
  security_group_ids  = [aws_security_group.redis.id]
  
  tags = {
    Name = "ad-platform-redis"
  }
}
```

### 2.3 多环境管理

```hcl
# environments/production/main.tf
module "vpc" {
  source = "../../modules/vpc"
  
  environment = "production"
  cidr_block  = "10.0.0.0/16"
  
  tags = {
    Owner       = "ad-platform-team"
    Project     = "ad-platform"
  }
}

module "bidding" {
  source = "../../modules/bidding"
  
  environment  = "production"
  instance_count = 10
  instance_type  = "c5.2xlarge"
  
  vpc_id     = module.vpc.vpc_id
  subnet_ids = module.vpc.public_subnet_ids
  
  redis_endpoint = module.redis.endpoint
  mysql_endpoint = module.mysql.endpoint
}

module "redis" {
  source = "../../modules/redis"
  
  environment = "production"
  instance_count = 3
  instance_type = "cache.r6g.large"
  
  vpc_id     = module.vpc.vpc_id
  subnet_ids = module.vpc.private_subnet_ids
}

module "mysql" {
  source = "../../modules/mysql"
  
  environment    = "production"
  instance_class = "r5.2xlarge"
  storage        = 500
  
  vpc_id         = module.vpc.vpc_id
  subnet_ids     = module.vpc.private_subnet_ids
}
```

### 2.4 Terraform 最佳实践

```hcl
# 使用 locals 管理变量
locals {
  common_tags = {
    Owner       = var.owner
    Project     = var.project
    Environment = var.environment
    ManagedBy   = "terraform"
  }
}

# 使用 data 数据源
data "aws_ami" "ubuntu" {
  most_recent = true
  owners      = ["099720109477"] # Canonical
  
  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*"]
  }
}

# 使用 provisioners 谨慎
resource "aws_instance" "app" {
  # ...
  
  provisioner "remote-exec" {
    connection {
      type        = "ssh"
      user        = "ubuntu"
      private_key = file("~/.ssh/ad-platform.pem")
      host        = self.public_ip
    }
    
    inline = [
      "sudo apt-get update",
      "sudo apt-get install -y docker.io",
    ]
  }
}

# 使用 lifecycle 避免意外删除
resource "aws_db_instance" "mysql" {
  # ...
  
  lifecycle {
    prevent_destroy = true
  }
}

# 使用 depends_on 明确依赖
resource "aws_route53_record" "bidding" {
  zone_id = data.aws_route53_zone.main.zone_id
  name    = "bidding.ad-platform.com"
  type    = "A"
  
  alias {
    name                   = aws_lb.bidding.dns_name
    zone_id                = aws_lb.bidding.zone_id
    evaluate_target_health = true
  }
  
  depends_on = [aws_lb.bidding]
}
```

---

## 第三部分：Helm 深度

### 3.1 Helm Chart 结构

```
charts/bidding-service/
├── Chart.yaml
├── values.yaml
├── values-prod.yaml
├── templates/
│   ├── deployment.yaml
│   ├── service.yaml
│   ├── hpa.yaml
│   ├── ingress.yaml
│   └── configmap.yaml
└── charts/
    └── mysql/
```

### 3.2 Chart.yaml

```yaml
apiVersion: v2
name: bidding-service
description: 广告竞价服务
type: application
version: 1.2.0
appVersion: "1.2.0"

dependencies:
  - name: mysql
    version: "8.0.0"
    repository: "https://charts.bitnami.com/bitnami"
    condition: mysql.enabled
  - name: redis
    version: "17.0.0"
    repository: "https://charts.bitnami.com/bitnami"
    condition: redis.enabled
```

### 3.3 values.yaml

```yaml
replicaCount: 3

image:
  repository: registry.ad-platform.com/bidding-service
  tag: "1.2.0"
  pullPolicy: IfNotPresent

service:
  type: ClusterIP
  port: 80
  targetPort: 8080

ingress:
  enabled: true
  className: nginx
  hosts:
    - host: bidding.ad-platform.com
      paths:
        - path: /
          pathType: Prefix

resources:
  requests:
    cpu: 500m
    memory: 512Mi
  limits:
    cpu: 1000m
    memory: 1Gi

autoscaling:
  enabled: true
  minReplicas: 3
  maxReplicas: 20
  targetCPUUtilizationPercentage: 70

env:
  REDIS_ENDPOINT: "redis-master:6379"
  MYSQL_ENDPOINT: "mysql:3306"
  LOG_LEVEL: "info"
  ENABLE_PROFILING: "true"

mysql:
  enabled: true
  auth:
    rootPassword: "changeme"
    database: "ad_platform"
    username: "ad_user"
    password: "ad_password"

redis:
  enabled: true
  auth:
    password: "redis_password"
```

### 3.4 deployment.yaml

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {{ include "bidding-service.fullname" . }}
  labels:
    {{- include "bidding-service.labels" . | nindent 4 }}
spec:
  {{- if not .Values.autoscaling.enabled }}
  replicas: {{ .Values.replicaCount }}
  {{- end }}
  selector:
    matchLabels:
      {{- include "bidding-service.selectorLabels" . | nindent 6 }}
  template:
    metadata:
      labels:
        {{- include "bidding-service.selectorLabels" . | nindent 8 }}
    spec:
      containers:
        - name: {{ .Chart.Name }}
          image: "{{ .Values.image.repository }}:{{ .Values.image.tag }}"
          imagePullPolicy: {{ .Values.image.pullPolicy }}
          ports:
            - name: http
              containerPort: 8080
              protocol: TCP
          env:
            {{- range $key, $value := .Values.env }}
            - name: {{ $key }}
              value: {{ $value | quote }}
            {{- end }}
          livenessProbe:
            httpGet:
              path: /health
              port: http
            initialDelaySeconds: 30
            periodSeconds: 10
          readinessProbe:
            httpGet:
              path: /ready
              port: http
            initialDelaySeconds: 5
            periodSeconds: 5
          resources:
            {{- toYaml .Values.resources | nindent 12 }}
      {{- with .Values.nodeSelector }}
      nodeSelector:
        {{- toYaml . | nindent 8 }}
      {{- end }}
```

---

## 第四部分：自测题

### 问题 1
Terraform 相比手动部署有什么优势？

<details>
<summary>查看答案</summary>

1. **版本控制**：基础设施即代码
2. **可复现**：terraform apply 每次结果一致
3. **回滚**：terraform plan 预览变更
4. **多环境**：同一配置部署多环境
5. **审计**：terraform state 追踪变更

</details>

### 问题 2
Helm Chart 相比裸 K8s YAML 有什么优势？

<details>
<summary>查看答案</summary>

1. **模板化**：values.yaml 参数化配置
2. **依赖管理**：Chart.yaml 声明依赖
3. **版本控制**：Chart version + app version
4. **发布管理**：helm upgrade/rollback
5. **多环境**：values-prod.yaml 区分环境

</details>

### 问题 3
Terraform state 管理需要注意什么？

<details>
<summary>查看答案</summary>

1. **远程存储**：S3 + DynamoDB
2. **加密**：S3 服务端加密
3. **锁定**：DynamoDB 防止并发
4. **敏感数据**：terraform.tfvars 不入库
5. **备份**：定期备份 state 文件

</details>

---

*本文档基于 DevOps 原理整理。*