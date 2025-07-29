#!/bin/bash

# RMMT 安全部署脚本

set -e

echo "🔒 开始部署RMMT安全配置..."

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 检查kubectl
if ! command -v kubectl &> /dev/null; then
    echo -e "${RED}❌ kubectl未安装，请先安装kubectl${NC}"
    exit 1
fi

# 检查集群连接
if ! kubectl cluster-info &> /dev/null; then
    echo -e "${RED}❌ 无法连接到Kubernetes集群${NC}"
    exit 1
fi

echo -e "${GREEN}✅ 集群连接正常${NC}"

# 部署步骤
echo -e "${BLUE}📋 部署步骤：${NC}"

# 1. 创建命名空间
echo -e "${YELLOW}1️⃣ 创建命名空间...${NC}"
kubectl apply -f k8s/namespace.yaml

# 2. 创建基础配置
echo -e "${YELLOW}2️⃣ 创建基础配置...${NC}"
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/secret.yaml

# 3. 创建安全配置
echo -e "${YELLOW}3️⃣ 创建安全配置...${NC}"
kubectl apply -f k8s/network-policy.yaml
kubectl apply -f k8s/pod-security-policy.yaml
kubectl apply -f k8s/waf-configmap.yaml
kubectl apply -f k8s/security-monitoring.yaml

# 4. 部署应用
echo -e "${YELLOW}4️⃣ 部署应用...${NC}"
kubectl apply -f k8s/rmmt-db-deployment.yaml
kubectl apply -f k8s/rmmt-api-deployment.yaml
kubectl apply -f k8s/rmmt-api-service.yaml
kubectl apply -f k8s/rmmt-student-deployment.yaml
kubectl apply -f k8s/rmmt-student-service.yaml
kubectl apply -f k8s/rmmt-admin-deployment.yaml
kubectl apply -f k8s/rmmt-admin-service.yaml

# 5. 部署安全Ingress
echo -e "${YELLOW}5️⃣ 部署安全Ingress...${NC}"
kubectl apply -f k8s/ingress-secure.yaml

# 等待部署完成
echo -e "${YELLOW}⏳ 等待部署完成...${NC}"
kubectl wait --for=condition=available --timeout=300s deployment/rmmt-db -n rmmt
kubectl wait --for=condition=available --timeout=300s deployment/rmmt-api -n rmmt
kubectl wait --for=condition=available --timeout=300s deployment/rmmt-student -n rmmt
kubectl wait --for=condition=available --timeout=300s deployment/rmmt-admin -n rmt

# 检查部署状态
echo -e "${GREEN}✅ 部署完成！检查状态：${NC}"
echo ""
echo "📊 Pod状态："
kubectl get pods -n rmmt

echo ""
echo "🌐 服务状态："
kubectl get svc -n rmmt

echo ""
echo "🚪 Ingress状态："
kubectl get ingress -n rmmt

echo ""
echo "🔒 安全策略状态："
kubectl get networkpolicy -n rmmt
kubectl get psp rmmt-psp

echo ""
echo -e "${GREEN}🎉 安全部署完成！${NC}"
echo ""
echo -e "${BLUE}📋 安全特性已启用：${NC}"
echo "✅ 网络策略 - 限制Pod间通信"
echo "✅ Pod安全策略 - 限制Pod权限"
echo "✅ WAF配置 - Web应用防火墙"
echo "✅ 速率限制 - 防止DDoS攻击"
echo "✅ 恶意请求过滤 - 阻止SQL注入、XSS等"
echo "✅ 安全监控 - 实时告警"
echo "✅ SSL/TLS - 强制HTTPS"
echo "✅ 安全响应头 - 防止点击劫持等"

echo ""
echo -e "${YELLOW}⚠️  注意事项：${NC}"
echo "1. 请更新域名配置（ingress-secure.yaml）"
echo "2. 配置SSL证书（cert-manager）"
echo "3. 设置监控告警（Prometheus + AlertManager）"
echo "4. 定期更新安全规则"
echo "5. 监控安全日志"

echo ""
echo -e "${BLUE}🔍 查看日志：${NC}"
echo "kubectl logs -f deployment/rmmt-api -n rmmt"
echo "kubectl logs -f deployment/rmmt-student -n rmmt"
echo "kubectl logs -f deployment/rmmt-admin -n rmmt"