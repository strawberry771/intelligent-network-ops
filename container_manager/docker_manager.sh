#!/bin/bash
# Docker 容器管理脚本
# 项目: 智能网联平台运维工具开发

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 日志函数
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 配置变量
COMPOSE_FILE="docker-compose.yml"
REGISTRY="registry.example.com"
NETWORK_NAME="intranet"

# 检查依赖
check_dependencies() {
    log_info "检查依赖..."
    
    if ! command -v docker &> /dev/null; then
        log_error "Docker 未安装"
        exit 1
    fi
    
    if ! command -v docker-compose &> /dev/null; then
        log_error "Docker Compose 未安装"
        exit 1
    fi
    
    docker version > /dev/null 2>&1 || {
        log_error "Docker 服务未运行"
        exit 1
    }
    
    log_info "依赖检查通过"
}

# 查看容器状态
status() {
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}  容器状态  ${NC}"
    echo -e "${BLUE}========================================${NC}"
    
    docker ps -a --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}\t{{.Image}}"
}

# 查看资源使用
stats() {
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}  资源使用  ${NC}"
    echo -e "${BLUE}========================================${NC}"
    
    docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}"
}

# 查看日志
logs() {
    local container=$1
    local lines=${2:-100}
    
    if [ -z "$container" ]; then
        log_error "请指定容器名称"
        echo "用法: $0 logs <容器名> [行数]"
        exit 1
    fi
    
    log_info "查看容器 $container 的日志 (最近 $lines 行)"
    docker logs --tail $lines -f $container
}

# 启动服务
start() {
    log_info "启动服务..."
    
    # 创建网络
    docker network create $NETWORK_NAME 2>/dev/null || true
    
    # 启动容器
    docker-compose -f $COMPOSE_FILE up -d
    
    # 等待服务启动
    sleep 5
    
    # 健康检查
    health_check
    
    log_info "服务启动完成"
}

# 停止服务
stop() {
    log_info "停止服务..."
    docker-compose -f $COMPOSE_FILE down
    log_info "服务已停止"
}

# 重启服务
restart() {
    log_info "重启服务..."
    stop
    sleep 2
    start
}

# 清理资源
clean() {
    log_warn "清理未使用的 Docker 资源..."
    
    # 停止并删除容器
    docker-compose -f $COMPOSE_FILE down -v
    
    # 清理未使用的镜像
    docker image prune -f
    
    # 清理未使用的网络
    docker network prune -f
    
    # 清理构建缓存
    docker builder prune -f
    
    log_info "清理完成"
}

# 健康检查
health_check() {
    log_info "执行健康检查..."
    
    local services=("prometheus:9090" "grafana:3000" "jenkins:8080")
    local all_healthy=true
    
    for service in "${services[@]}"; do
        local name=$(echo $service | cut -d':' -f1)
        local port=$(echo $service | cut -d':' -f2)
        
        if docker exec $name wget -q -O /dev/null -T 3 http://localhost:$port 2>/dev/null || \
           docker exec $name curl -sf http://localhost:$port >/dev/null 2>&1; then
            echo -e "  ${GREEN}✓${NC} $name 健康"
        else
            echo -e "  ${RED}✗${NC} $name 异常"
            all_healthy=false
        fi
    done
    
    if [ "$all_healthy" = false ]; then
        log_warn "部分服务不健康，请检查"
    fi
}

# 备份数据
backup() {
    local backup_dir="/var/backups/docker"
    local timestamp=$(date +%Y%m%d_%H%M%S)
    local backup_file="$backup_dir/backup_$timestamp.tar.gz"
    
    mkdir -p $backup_dir
    
    log_info "备份数据到 $backup_file..."
    
    # 备份 volumes
    docker run --rm \
        -v prometheus_data:/data:ro \
        -v grafana_data:/data:ro \
        -v jenkins_home:/data:ro \
        -v $backup_dir:/backup \
        alpine \
        tar czf /backup/backup_$timestamp.tar.gz /data
    
    # 备份配置文件
    tar czf $backup_dir/config_$timestamp.tar.gz \
        ./prometheus ./grafana ./jenkins 2>/dev/null || true
    
    log_info "备份完成: $backup_file"
}

# 恢复数据
restore() {
    local backup_file=$1
    
    if [ -z "$backup_file" ]; then
        log_error "请指定备份文件"
        echo "用法: $0 restore <备份文件>"
        exit 1
    fi
    
    if [ ! -f "$backup_file" ]; then
        log_error "备份文件不存在: $backup_file"
        exit 1
    fi
    
    log_info "恢复数据从 $backup_file..."
    
    # 停止服务
    stop
    
    # 恢复 volumes
    docker run --rm \
        -v prometheus_data:/data \
        -v grafana_data:/data \
        -v jenkins_home:/data \
        -v $(dirname $backup_file):/backup \
        alpine \
        tar xzf /backup/$(basename $backup_file) -C /
    
    # 重启服务
    start
    
    log_info "恢复完成"
}

# 扩缩容
scale() {
    local service=$1
    local replicas=${2:-1}
    
    if [ -z "$service" ]; then
        log_error "请指定服务名称和副本数"
        echo "用法: $0 scale <服务名> <副本数>"
        exit 1
    fi
    
    log_info "扩展 $service 到 $replicas 个副本..."
    docker-compose -f $COMPOSE_FILE up -d --scale $service=$replicas
}

# 监控面板
monitor() {
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}  服务监控面板  ${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo ""
    echo "  Prometheus:  http://localhost:9090"
    echo "  Grafana:     http://localhost:3000"
    echo "  Jenkins:     http://localhost:8080"
    echo "  GitLab:       http://localhost:80"
    echo ""
    echo "  容器管理:"
    echo "    - 状态: $0 status"
    echo "    - 资源: $0 stats"
    echo "    - 日志: $0 logs <容器名>"
    echo ""
}

# 告警检查
alert_check() {
    log_info "执行告警检查..."
    
    # 检查 CPU 使用率
    local cpu_usage=$(docker stats --no-stream --format "{{.CPUPerc}}" | grep -oP '\d+' | sort -rn | head -1)
    if [ "$cpu_usage" -gt 80 ]; then
        log_warn "CPU 使用率过高: ${cpu_usage}%"
    fi
    
    # 检查内存使用率
    local mem_usage=$(docker stats --no-stream --format "{{.MemPerc}}" | grep -oP '\d+' | sort -rn | head -1)
    if [ "$mem_usage" -gt 85 ]; then
        log_warn "内存使用率过高: ${mem_usage}%"
    fi
    
    # 检查磁盘空间
    local disk_usage=$(df / | tail -1 | awk '{print $5}' | tr -d '%')
    if [ "$disk_usage" -gt 90 ]; then
        log_error "磁盘空间不足: ${disk_usage}%"
    fi
    
    # 检查停止的容器
    local stopped=$(docker ps -a --filter status=exited --format "{{.Names}}" | wc -l)
    if [ "$stopped" -gt 0 ]; then
        log_warn "存在 $stopped 个已停止的容器"
    fi
}

# 帮助信息
help() {
    echo -e "${BLUE}智能网联平台 Docker 管理脚本${NC}"
    echo ""
    echo "用法: $0 <命令>"
    echo ""
    echo "命令:"
    echo "  status       查看容器状态"
    echo "  stats        查看资源使用"
    echo "  logs         查看容器日志"
    echo "  start        启动服务"
    echo "  stop         停止服务"
    echo "  restart      重启服务"
    echo "  clean        清理资源"
    echo "  health       健康检查"
    echo "  backup       备份数据"
    echo "  restore      恢复数据"
    echo "  scale        扩缩容"
    echo "  monitor      显示监控面板"
    echo "  alert        告警检查"
    echo "  help         显示帮助"
    echo ""
}

# 主函数
main() {
    check_dependencies
    
    case "${1:-help}" in
        status)
            status
            ;;
        stats)
            stats
            ;;
        logs)
            logs "$2" "$3"
            ;;
        start)
            start
            ;;
        stop)
            stop
            ;;
        restart)
            restart
            ;;
        clean)
            clean
            ;;
        health)
            health_check
            ;;
        backup)
            backup
            ;;
        restore)
            restore "$2"
            ;;
        scale)
            scale "$2" "$3"
            ;;
        monitor)
            monitor
            ;;
        alert)
            alert_check
            ;;
        help|--help|-h)
            help
            ;;
        *)
            log_error "未知命令: $1"
            help
            exit 1
            ;;
    esac
}

main "$@"
