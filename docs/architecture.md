# 架构说明

本项目的三条核心链路：**监控**、**自动化巡检**、**发布**。每条链路均对应仓库内真实存在的脚本 / 配置文件。

## 1. 监控链路

```mermaid
flowchart LR
    N1[Linux Server<br/>Node Exporter :9100] --> P[Prometheus :9090]
    N2[应用服务<br/>:9113 / :9114] --> P
    D[cAdvisor :8080<br/>Docker 指标] --> P
    P --> G[Grafana :3000<br/>数据源 + 仪表盘]
    P --> R[告警规则<br/>CPU / 内存 / 磁盘 / 服务]
```

**对应文件**：`monitoring_tool/deploy_monitoring.sh`

- 部署 Prometheus + Grafana，生成 `prometheus.yml`（抓取 Node Exporter / cAdvisor / 应用服务）
- 内嵌 CPU / 内存 / 磁盘 / 服务可用性告警规则
- 自动创建 Grafana Prometheus 数据源与 Node Exporter 概览仪表盘

## 2. 自动化巡检链路

```mermaid
flowchart TB
    PY[service_checker.py] --> SC[ServiceChecker<br/>TCP 端口探测]
    PY --> LS[LogSearcher<br/>正则检索 / gzip / 时间过滤]
    SC --> RPT[MonitorReporter<br/>巡检报告]
    SC --> AM[AlertManager<br/>SMTP 邮件告警]
    SC --> MET[Prometheus textfile 指标导出]
```

**对应文件**：`monitoring_tool/service_checker.py`

## 3. 发布链路

```mermaid
flowchart LR
    GL[GitLab<br/>代码仓库] --> JK[Jenkins<br/>Jenkinsfile 流水线]
    JK --> B[Docker Build<br/>镜像构建]
    B --> PG[镜像推送<br/>registry.example.com]
    PG --> DP[容器部署<br/>测试 / 生产 蓝绿切换]
```

**对应文件**：`cicd_pipeline/Jenkinsfile`、`cicd_pipeline/cicd_manager.py`、`container_manager/docker_manager.sh`

## 文件 ↔ 功能映射

| 文件 | 链路 | 功能 |
|------|------|------|
| `monitoring_tool/deploy_monitoring.sh` | 监控 | 部署 Prometheus + Grafana，配置抓取目标与告警规则 |
| `monitoring_tool/service_checker.py` | 巡检 | 服务状态检查、日志检索、邮件告警、指标导出 |
| `cicd_pipeline/Jenkinsfile` | 发布 | Jenkins 声明式流水线（构建/测试/部署） |
| `cicd_pipeline/cicd_manager.py` | 发布 | GitLab API + Docker 镜像构建推送部署回滚 |
| `container_manager/docker_manager.sh` | 运维 | 容器启停、日志、健康检查、备份恢复 |
