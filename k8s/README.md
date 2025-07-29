# RMMT Kubernetes 部署指南

## 概述

这个目录包含了RMMT（Roommate Matcher）系统在Kubernetes集群上的完整部署配置。

## 架构说明

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   RMMT-Student  │    │   RMMT-Admin    │    │   RMMT-API      │
│   (Frontend)    │    │   (Frontend)    │    │   (Backend)     │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         └───────────────────────┼───────────────────────┘
                                 │
                    ┌─────────────────┐
                    │   Ingress       │
                    │   Controller    │
                    └─────────────────┘
                                 │
                    ┌─────────────────┐
                    │   External      │
                    │   Traffic       │
                    └─────────────────┘
```

## 文件结构

```
k8s/
├── namespace.yaml              # 命名空间定义
├── configmap.yaml             # 配置映射
├── secret.yaml                # 密钥配置
├── rmmt-api-deployment.yaml   # API服务部署
├── rmmt-api-service.yaml      # API服务定义
├── rmmt-student-deployment.yaml # 学生前端部署
├── rmmt-student-service.yaml  # 学生前端服务
├── rmmt-admin-deployment.yaml # 管理前端部署
├── rmmt-admin-service.yaml    # 管理前端服务
├── ingress.yaml               # 入口配置
├── kustomization.yaml         # Kustomize配置
└── README.md                  # 本文件
```

## 前置要求

1. **Kubernetes集群** (v1.19+)
2. **kubectl** 命令行工具
3. **Docker镜像** 已构建并推送到镜像仓库
4. **Ingress Controller** (如nginx-ingress)
5. **cert-manager** (用于SSL证书)

## 部署步骤

### 1. 构建Docker镜像

```bash
# 构建API镜像
cd RMMT-API
docker build -t rmmt-api:latest .

# 构建Student前端镜像
cd RMMT-Student
docker build -t rmmt-student:latest .

# 构建Admin前端镜像
cd RMMT-Admin
docker build -t rmmt-admin:latest .

# 推送到镜像仓库（可选）
docker tag rmmt-api:latest your-registry/rmmt-api:latest
docker tag rmmt-student:latest your-registry/rmmt-student:latest
docker tag rmmt-admin:latest your-registry/rmmt-admin:latest
docker push your-registry/rmmt-api:latest
docker push your-registry/rmmt-student:latest
docker push your-registry/rmmt-admin:latest
```

### 2. 更新配置

在部署前，请更新以下配置：

1. **镜像名称**: 在deployment文件中更新镜像名称
2. **域名**: 在ingress.yaml中更新域名
3. **密钥**: 在secret.yaml中更新敏感信息
4. **配置**: 在configmap.yaml中更新应用配置

### 3. 部署到Kubernetes

```bash
# 使用kubectl直接部署
kubectl apply -f k8s/

# 或使用kustomize
kubectl apply -k k8s/

# 检查部署状态
kubectl get all -n rmmt
kubectl get ingress -n rmmt
```

### 4. 验证部署

```bash
# 检查Pod状态
kubectl get pods -n rmmt

# 检查服务状态
kubectl get svc -n rmmt

# 检查Ingress状态
kubectl get ingress -n rmmt

# 查看日志
kubectl logs -f deployment/rmmt-api -n rmmt
kubectl logs -f deployment/rmmt-student -n rmmt
kubectl logs -f deployment/rmmt-admin -n rmmt
```

## 访问地址

部署成功后，可以通过以下地址访问：

- **学生前端**: https://student.rmmt.example.com
- **管理前端**: https://admin.rmmt.example.com
- **API服务**: https://api.rmmt.example.com

## 配置说明

### 环境变量

- `NUXT_API_URL`: 前端访问API的地址
- `DB_HOST`: 数据库主机地址
- `DB_PASSWORD`: 数据库密码
- `JWT_SECRET`: JWT签名密钥

### 资源限制

- **API服务**: 256Mi-512Mi内存，250m-500m CPU
- **前端服务**: 128Mi-256Mi内存，100m-200m CPU

### 健康检查

所有服务都配置了liveness和readiness探针，确保服务健康状态。

## 扩展和缩放

```bash
# 扩展API服务副本数
kubectl scale deployment rmmt-api --replicas=3 -n rmmt

# 扩展前端服务副本数
kubectl scale deployment rmmt-student --replicas=3 -n rmmt
kubectl scale deployment rmmt-admin --replicas=3 -n rmmt
```

## 故障排除

1. **Pod启动失败**: 检查镜像是否存在，配置是否正确
2. **服务无法访问**: 检查Service和Ingress配置
3. **API连接失败**: 检查网络策略和防火墙设置
4. **证书问题**: 检查cert-manager配置

## 备份和恢复

```bash
# 备份配置
kubectl get all -n rmmt -o yaml > rmmt-backup.yaml

# 恢复配置
kubectl apply -f rmmt-backup.yaml
```

## 监控和日志

建议配置以下监控：

1. **Prometheus + Grafana**: 监控应用指标
2. **ELK Stack**: 集中日志管理
3. **AlertManager**: 告警通知

## 安全建议

1. 使用RBAC控制访问权限
2. 定期更新密钥和证书
3. 启用网络策略
4. 配置资源限制
5. 使用安全上下文