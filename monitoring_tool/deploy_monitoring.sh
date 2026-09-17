#!/bin/bash
# Prometheus 与 Grafana 部署脚本
# 项目: 智能网联平台运维工具开发
# 环境: CentOS 7/8

set -e

# 配置变量
PROMETHEUS_VERSION="2.40.0"
GRAFANA_VERSION="9.2.0"
INSTALL_DIR="/opt/monitoring"
DATA_DIR="/var/lib/monitoring"

echo "=========================================="
echo "智能网联平台监控部署脚本"
echo "=========================================="

# 创建目录
mkdir -p ${INSTALL_DIR}/{prometheus,grafana}
mkdir -p ${DATA_DIR}/{prometheus,grafana}

# 安装 Prometheus
install_prometheus() {
    echo "[1/4] 安装 Prometheus ${PROMETHEUS_VERSION}..."
    
    # 下载
    curl -fsSL "https://github.com/prometheus/prometheus/releases/download/v${PROMETHEUS_VERSION}/prometheus-${PROMETHEUS_VERSION}.linux-amd64.tar.gz" \
        -o /tmp/prometheus.tar.gz
    
    # 解压
    tar -xzf /tmp/prometheus.tar.gz -C /tmp/
    
    # 复制二进制文件
    cp /tmp/prometheus-${PROMETHEUS_VERSION}.linux-amd64/prometheus ${INSTALL_DIR}/prometheus/
    cp /tmp/prometheus-${PROMETHEUS_VERSION}.linux-amd64/promtool ${INSTALL_DIR}/prometheus/
    
    # 复制配置文件
    cp -r /tmp/prometheus-${PROMETHEUS_VERSION}.linux-amd64/consoles ${INSTALL_DIR}/prometheus/
    cp -r /tmp/prometheus-${PROMETHEUS_VERSION}.linux-amd64/console_libraries ${INSTALL_DIR}/prometheus/
    
    # 创建 prometheus 用户
    useradd --no-create-home --shell /bin/false prometheus 2>/dev/null || true
    chown -R prometheus:prometheus ${INSTALL_DIR}/prometheus
    chown -R prometheus:prometheus ${DATA_DIR}/prometheus
    
    # 清理
    rm -rf /tmp/prometheus*
    
    echo "✓ Prometheus 安装完成"
}

# 安装 Grafana
install_grafana() {
    echo "[2/4] 安装 Grafana ${GRAFANA_VERSION}..."
    
    # 添加 Grafana YUM 源 (CentOS)
    cat > /etc/yum.repos.d/grafana.repo << EOF
[grafana]
name=grafana
baseurl=https://packages.grafana.com/oss/rpm
repo_gpgcheck=1
enabled=1
gpgcheck=1
gpgkey=https://packages.grafana.com/gpg.key
sslverify=1
sslcacert=/etc/pki/tls/certs/ca-bundle.crt
EOF
    
    # 安装
    yum install -y grafana-${GRAFANA_VERSION}
    
    # 配置数据目录
    sed -i 's|;data = /var/lib/grafana|data = '${DATA_DIR}'/grafana|g' /etc/grafana/grafana.ini
    sed -i 's|;logs = /var/log/grafana|logs = /var/log/grafana|g' /etc/grafana/grafana.ini
    
    # 创建数据目录
    mkdir -p ${DATA_DIR}/grafana
    chown -R grafana:grafana ${DATA_DIR}/grafana
    
    # 启动服务
    systemctl daemon-reload
    systemctl enable grafana-server
    systemctl start grafana-server
    
    echo "✓ Grafana 安装完成"
}

# 配置 Prometheus
configure_prometheus() {
    echo "[3/4] 配置 Prometheus..."
    
    # Prometheus 主配置
    cat > ${INSTALL_DIR}/prometheus/prometheus.yml << 'EOF'
global:
  scrape_interval: 15s
  evaluation_interval: 15s
  external_labels:
    cluster: 'intelligent-network'
    env: 'production'

alerting:
  alertmanagers:
    - static_configs:
        - targets: []

rule_files:
  - "rules/*.yml"

scrape_configs:
  # Prometheus 自身监控
  - job_name: 'prometheus'
    static_configs:
      - targets: ['localhost:9090']
        labels:
          service: 'prometheus'

  # Node Exporter - 节点资源监控
  # 注：以下为示例占位地址，部署前请替换为实际节点 IP
  - job_name: 'node'
    static_configs:
      - targets:
        - 'YOUR_NODE_IP_1:9100'
        - 'YOUR_NODE_IP_2:9100'
        - 'YOUR_NODE_IP_3:9100'
        labels:
          service: 'node-exporter'

  # Docker 监控
  - job_name: 'cadvisor'
    static_configs:
      - targets: ['YOUR_NODE_IP_1:8080']

  # 应用服务监控
  - job_name: 'application'
    static_configs:
      - targets: ['YOUR_NODE_IP_1:9113']
        labels:
          service: 'web-api'
      - targets: ['YOUR_NODE_IP_2:9114']
        labels:
          service: 'jenkins'
EOF

    # 创建告警规则
    mkdir -p ${INSTALL_DIR}/prometheus/rules
    
    # CPU 告警规则
    cat > ${INSTALL_DIR}/prometheus/rules/cpu_alerts.yml << 'EOF'
groups:
- name: cpu_alerts
  rules:
  - alert: HighCPUUsage
    expr: 100 - (avg by(instance) (irate(node_cpu_seconds_total{mode="idle"}[5m])) * 100) > 80
    for: 5m
    labels:
      severity: warning
    annotations:
      summary: "实例 {{ $labels.instance }} CPU 使用率过高"
      description: "CPU 使用率已超过 80%，当前值: {{ $value }}%"

  - alert: CriticalCPUUsage
    expr: 100 - (avg by(instance) (irate(node_cpu_seconds_total{mode="idle"}[5m])) * 100) > 90
    for: 3m
    labels:
      severity: critical
    annotations:
      summary: "实例 {{ $labels.instance }} CPU 使用率危急"
      description: "CPU 使用率已超过 90%，当前值: {{ $value }}%，请立即处理！"
EOF

    # 内存告警规则
    cat > ${INSTALL_DIR}/prometheus/rules/memory_alerts.yml << 'EOF'
groups:
- name: memory_alerts
  rules:
  - alert: HighMemoryUsage
    expr: (node_memory_MemTotal_bytes - node_memory_MemAvailable_bytes) / node_memory_MemTotal_bytes * 100 > 85
    for: 10m
    labels:
      severity: warning
    annotations:
      summary: "实例 {{ $labels.instance }} 内存使用率过高"
      description: "内存使用率已超过 85%，当前值: {{ $value | printf \"%.2f\" }}%"

  - alert: CriticalMemoryUsage
    expr: (node_memory_MemTotal_bytes - node_memory_MemAvailable_bytes) / node_memory_MemTotal_bytes * 100 > 95
    for: 5m
    labels:
      severity: critical
    annotations:
      summary: "实例 {{ $labels.instance }} 内存即将耗尽"
      description: "内存使用率已超过 95%，当前值: {{ $value | printf \"%.2f\" }}%"
EOF

    # 磁盘告警规则
    cat > ${INSTALL_DIR}/prometheus/rules/disk_alerts.yml << 'EOF'
groups:
- name: disk_alerts
  rules:
  - alert: HighDiskUsage
    expr: (node_filesystem_size_bytes{mountpoint!="/boot"} - node_filesystem_avail_bytes{mountpoint!="/boot"}) / node_filesystem_size_bytes{mountpoint!="/boot"} * 100 > 85
    for: 10m
    labels:
      severity: warning
    annotations:
      summary: "实例 {{ $labels.instance }} 磁盘使用率过高"
      description: "磁盘 {{ $labels.mountpoint }} 使用率已超过 85%，当前值: {{ $value | printf \"%.2f\" }}%"

  - alert: DiskSpaceLow
    expr: (node_filesystem_size_bytes{mountpoint!="/boot"} - node_filesystem_avail_bytes{mountpoint!="/boot"}) / node_filesystem_size_bytes{mountpoint!="/boot"} * 100 > 90
    for: 5m
    labels:
      severity: critical
    annotations:
      summary: "实例 {{ $labels.instance }} 磁盘空间不足"
      description: "磁盘 {{ $labels.mountpoint }} 使用率已超过 90%，请立即清理或扩容！"

  - alert: HighDiskIO
    expr: rate(node_disk_io_time_seconds_total[5m]) * 100 > 80
    for: 10m
    labels:
      severity: warning
    annotations:
      summary: "实例 {{ $labels.instance }} 磁盘 IO 繁忙"
      description: "磁盘 IO 使用率已超过 80%"
EOF

    # 服务告警规则
    cat > ${INSTALL_DIR}/prometheus/rules/service_alerts.yml << 'EOF'
groups:
- name: service_alerts
  rules:
  - alert: ServiceDown
    expr: up == 0
    for: 1m
    labels:
      severity: critical
    annotations:
      summary: "服务 {{ $labels.job }} 不可用"
      description: "服务 {{ $labels.job }} ({{ $labels.instance }}) 已离线超过 1 分钟"

  - alert: HighResponseTime
    expr: prometheus_target_interval_length_seconds{quantile="0.99"} > 3
    for: 5m
    labels:
      severity: warning
    annotations:
      summary: "Prometheus 采集响应时间过长"
      description: "99分位响应时间: {{ $value }}s"
EOF

    # 创建 systemd 服务文件
    cat > /etc/systemd/system/prometheus.service << 'EOF'
[Unit]
Description=Prometheus Monitoring System
Documentation=https://prometheus.io/docs/
After=network.target

[Service]
Type=simple
User=prometheus
Group=prometheus
ExecStart=/opt/monitoring/prometheus/prometheus \
    --config.file=/opt/monitoring/prometheus/prometheus.yml \
    --storage.tsdb.path=/var/lib/monitoring/prometheus \
    --storage.tsdb.retention.time=15d \
    --web.console.libraries=/opt/monitoring/prometheus/console_libraries \
    --web.console.templates=/opt/monitoring/prometheus/consoles \
    --web.enable-lifecycle
Restart=on-failure
RestartSec=10s

[Install]
WantedBy=multi-user.target
EOF

    # 启动 Prometheus
    systemctl daemon-reload
    systemctl enable prometheus
    systemctl start prometheus
    
    echo "✓ Prometheus 配置完成"
}

# 配置 Grafana 数据源和仪表盘
configure_grafana() {
    echo "[4/4] 配置 Grafana 仪表盘..."
    
    # 等待 Grafana 启动
    sleep 5
    
    # 添加 Prometheus 数据源
    curl -X POST \
        -H "Content-Type: application/json" \
        -H "Accept: application/json" \
        -d '{
            "name": "Prometheus",
            "type": "prometheus",
            "url": "http://localhost:9090",
            "access": "proxy",
            "isDefault": true
        }' \
        "http://admin:admin@localhost:3000/api/datasources" 2>/dev/null || true
    
    # 创建节点监控仪表盘
    create_node_dashboard
    
    echo "✓ Grafana 配置完成"
}

create_node_dashboard() {
    # 创建 Node Exporter 概览仪表盘
    cat > /tmp/node_dashboard.json << 'EOFDASH'
{
  "dashboard": {
    "title": "Node Exporter 概览",
    "tags": ["node", "系统监控"],
    "timezone": "browser",
    "panels": [
      {
        "title": "CPU 使用率",
        "type": "graph",
        "gridPos": {"x": 0, "y": 0, "w": 12, "h": 8},
        "targets": [{
          "expr": "100 - (avg by(instance) (irate(node_cpu_seconds_total{mode=\"idle\"}[5m])) * 100)",
          "legendFormat": "{{instance}}"
        }]
      },
      {
        "title": "内存使用率",
        "type": "graph", 
        "gridPos": {"x": 12, "y": 0, "w": 12, "h": 8},
        "targets": [{
          "expr": "(node_memory_MemTotal_bytes - node_memory_MemAvailable_bytes) / node_memory_MemTotal_bytes * 100",
          "legendFormat": "{{instance}}"
        }]
      },
      {
        "title": "磁盘使用率",
        "type": "gauge",
        "gridPos": {"x": 0, "y": 8, "w": 8, "h": 8},
        "targets": [{
          "expr": "(node_filesystem_size_bytes - node_filesystem_avail_bytes) / node_filesystem_size_bytes * 100",
          "legendFormat": "{{mountpoint}}"
        }]
      },
      {
        "title": "网络流量",
        "type": "graph",
        "gridPos": {"x": 8, "y": 8, "w": 16, "h": 8},
        "targets": [
          {"expr": "rate(node_network_receive_bytes_total[5m])", "legendFormat": "接收 {{instance}}"},
          {"expr": "rate(node_network_transmit_bytes_total[5m])", "legendFormat": "发送 {{instance}}"}
        ]
      }
    ]
  }
}
EOFDASH

    curl -X POST \
        -H "Content-Type: application/json" \
        -H "Accept: application/json" \
        -d @/tmp/node_dashboard.json \
        "http://admin:admin@localhost:3000/api/dashboards/db" 2>/dev/null || true
    
    rm -f /tmp/node_dashboard.json
}

# 主函数
main() {
    install_prometheus
    install_grafana
    configure_prometheus
    configure_grafana
    
    echo ""
    echo "=========================================="
    echo "✅ 监控平台部署完成！"
    echo "=========================================="
    echo ""
    echo "访问地址:"
    echo "  - Prometheus: http://localhost:9090"
    echo "  - Grafana:    http://localhost:3000 (admin/admin)"
    echo ""
    echo "常用命令:"
    echo "  systemctl status prometheus"
    echo "  systemctl status grafana-server"
    echo ""
}

main "$@"
