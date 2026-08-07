智能网联平台运维工具
====================

项目周期: 2022年7月 – 2022年10月

## 项目概述

围绕 Linux 服务器运维、监控告警、CICD 流水线与容器平台管理展开的实践项目。

## 项目结构

```
.
├── monitoring_tool/           # 监控工具
│   ├── service_checker.py     # 服务状态检查与日志检索脚本
│   └── deploy_monitoring.sh   # Prometheus + Grafana 部署脚本
│
├── cicd_pipeline/             # CI/CD 流水线
│   ├── cicd_manager.py        # 流水线管理脚本
│   └── Jenkinsfile            # Jenkins 流水线配置
│
└── container_manager/        # 容器管理
    └── docker_manager.sh      # Docker 容器管理脚本
```

## 主要功能

### 1. 监控告警 (Prometheus + Grafana)

- **部署脚本**: `deploy_monitoring.sh`
  - 一键部署 Prometheus 和 Grafana
  - 自动配置节点监控
  - 预设 CPU、内存、磁盘告警规则

- **服务检查**: `service_checker.py`
  - TCP 端口健康检查
  - 响应时间监控
  - 邮件告警通知
  - Prometheus 指标导出

**告警规则**:
| 指标 | 警告阈值 | 危急阈值 |
|------|---------|---------|
| CPU | 80% | 90% |
| 内存 | 85% | 95% |
| 磁盘 | 85% | 90% |

### 2. 自动化巡检

**Python 脚本功能**:
```python
# 每日自动巡检
python service_checker.py

# 导出 Prometheus 指标
# 发送告警邮件
# 生成日报
```

**日志检索**:
```bash
# 搜索错误日志
python service_checker.py --search "ERROR" --service prometheus

# 错误汇总统计
python service_checker.py --error-summary
```

### 3. CI/CD 流水线 (GitLab + Jenkins + Docker)

**流水线阶段**:
```
代码检出 → 依赖安装 → 代码检查 → 单元测试 
       → 构建镜像 → 集成测试 → 镜像扫描 
       → 测试部署 → 生产部署
```

**Jenkins 特性**:
- 参数化构建
- 蓝绿部署
- 自动回滚
- 钉钉/邮件通知
- 镜像安全扫描

**使用示例**:
```bash
# 部署应用
python cicd_manager.py deploy -p project/app -b main

# 回滚版本
python cicd_manager.py rollback -p project/app -t v1.2.3

# 跳过测试快速构建
python cicd_manager.py deploy -p project/app -b develop --skip-test
```

### 4. 容器管理

**管理脚本**: `docker_manager.sh`

```bash
# 容器管理
./docker_manager.sh status        # 查看状态
./docker_manager.sh stats         # 资源使用
./docker_manager.sh logs app       # 查看日志

# 服务管理
./docker_manager.sh start          # 启动服务
./docker_manager.sh stop           # 停止服务
./docker_manager.sh restart        # 重启服务

# 运维操作
./docker_manager.sh health         # 健康检查
./docker_manager.sh backup         # 备份数据
./docker_manager.sh alert           # 告警检查
```

## 技术栈

| 类别 | 技术 |
|------|------|
| 监控 | Prometheus, Grafana, Node Exporter, cAdvisor |
| 告警 | Alertmanager, Email, 钉钉机器人 |
| CI/CD | GitLab CI, Jenkins, Docker Registry |
| 容器 | Docker, Docker Compose, Portainer |
| 编程 | Python 3, Bash, Groovy (Jenkinsfile) |

## 部署架构

```
┌─────────────────────────────────────────────────────┐
│                    GitLab                           │
│         (代码仓库 + 镜像仓库)                        │
└─────────────────────┬───────────────────────────────┘
                      │ Webhook
                      ▼
┌─────────────────────────────────────────────────────┐
│                    Jenkins                          │
│         (流水线编排 + 自动化构建)                    │
└──────────┬──────────────────────────────────────────┘
           │ SSH
           ▼
┌─────────────────────────────────────────────────────┐
│                   Docker Host                        │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐            │
│  │prometheus│ │ grafana  │ │  app     │            │
│  │  :9090   │ │  :3000   │ │  :8080   │            │
│  └──────────┘ └──────────┘ └──────────┘            │
└─────────────────────────────────────────────────────┘
```

## 快速开始

### 1. 部署监控平台

```bash
chmod +x deploy_monitoring.sh
sudo ./deploy_monitoring.sh
```

### 2. 配置每日巡检

```bash
# 添加定时任务
crontab -e

# 每天早上9点执行巡检
0 9 * * * /usr/bin/python3 /opt/monitor/service_checker.py >> /var/log/monitor/cron.log 2>&1
```

### 3. 启动容器平台

```bash
chmod +x docker_manager.sh
./docker_manager.sh start
```

## 成果

- ✅ 实现服务器状态可视化，告警响应时间缩短 70%
- ✅ 自动化巡检替代人工操作，每天节省 30 分钟
- ✅ CI/CD 流水线将发布频率从每周 1 次提升到每天 3 次
- ✅ 蓝绿部署实现零停机发布
