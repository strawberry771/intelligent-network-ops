#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
智能网联平台运维工具 - 服务状态检查与日志检索脚本
项目: 2022年7月-10月 智能网联平台运维工具开发
"""

import os
import sys
import json
import time
import socket
import smtplib
import logging
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
from enum import Enum

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/var/log/monitor/service_check.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class ServiceStatus(Enum):
    """服务状态枚举"""
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


@dataclass
class ServiceCheckResult:
    """服务检查结果数据类"""
    service_name: str
    status: str
    message: str
    response_time: float
    timestamp: str
    details: Optional[Dict] = None

    def to_dict(self) -> Dict:
        return asdict(self)

    def to_prometheus_format(self) -> str:
        """转换为 Prometheus 指标格式"""
        status_value = 1 if self.status == "healthy" else 0
        return f'service_status{{service="{self.service_name}"}} {status_value}\n'


class ConfigManager:
    """配置管理器"""
    
    def __init__(self, config_path: str = "/etc/monitor/config.json"):
        self.config_path = config_path
        self._config = self._load_config()
    
    def _load_config(self) -> Dict:
        """加载配置文件"""
        default_config = {
            "smtp": {
                "host": "smtp.example.com",
                "port": 587,
                "username": "monitor@example.com",
                "password": "your_password",
                "from_addr": "monitor@example.com",
                "to_addrs": ["admin@example.com"]
            },
            "services": {
                "prometheus": {"host": "localhost", "port": 9090, "timeout": 5},
                "grafana": {"host": "localhost", "port": 3000, "timeout": 5},
                "jenkins": {"host": "localhost", "port": 8080, "timeout": 5},
                "gitlab": {"host": "localhost", "port": 80, "timeout": 5},
                "docker": {"host": "localhost", "port": 2375, "timeout": 3}
            },
            "log_paths": {
                "prometheus": "/var/log/prometheus/prometheus.log",
                "jenkins": "/var/log/jenkins/jenkins.log",
                "gitlab": "/var/log/gitlab/gitlab-rails/production.log",
                "nginx": "/var/log/nginx/access.log",
                "docker": "/var/log/docker.log"
            },
            "alert_rules": {
                "cpu_threshold": 80,
                "memory_threshold": 85,
                "disk_threshold": 90,
                "response_time_threshold": 3.0
            }
        }
        
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"加载配置文件失败，使用默认配置: {e}")
        
        return default_config
    
    @property
    def services(self) -> Dict:
        return self._config.get("services", {})
    
    @property
    def alert_rules(self) -> Dict:
        return self._config.get("alert_rules", {})


class ServiceChecker:
    """服务状态检查器"""
    
    def __init__(self, config: ConfigManager):
        self.config = config
    
    def check_tcp_port(self, host: str, port: int, timeout: int = 5) -> tuple:
        """检查 TCP 端口连通性"""
        start_time = time.time()
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            result = sock.connect_ex((host, port))
            sock.close()
            response_time = time.time() - start_time
            return result == 0, response_time
        except socket.timeout:
            return False, timeout
        except Exception as e:
            logger.error(f"端口检查失败 {host}:{port}: {e}")
            return False, timeout
    
    def check_service(self, service_name: str, host: str, port: int, timeout: int) -> ServiceCheckResult:
        """检查单个服务状态"""
        logger.info(f"检查服务: {service_name} ({host}:{port})")
        
        is_healthy, response_time = self.check_tcp_port(host, port, timeout)
        
        if is_healthy:
            status = ServiceStatus.HEALTHY.value
            message = f"服务正常，响应时间: {response_time:.3f}s"
        else:
            status = ServiceStatus.CRITICAL.value
            message = f"服务不可达，响应时间: {response_time:.3f}s"
        
        return ServiceCheckResult(
            service_name=service_name,
            status=status,
            message=message,
            response_time=response_time,
            timestamp=datetime.now().isoformat(),
            details={"host": host, "port": port}
        )
    
    def check_all_services(self) -> List[ServiceCheckResult]:
        """检查所有配置的服务"""
        results = []
        services = self.config.services
        
        for service_name, params in services.items():
            result = self.check_service(
                service_name,
                params.get("host", "localhost"),
                params.get("port", 80),
                params.get("timeout", 5)
            )
            results.append(result)
        
        return results


class LogSearcher:
    """日志检索器"""
    
    def __init__(self, config: ConfigManager):
        self.config = config
    
    def search_in_file(self, filepath: str, pattern: str, 
                       max_lines: int = 100, since_hours: int = 24) -> List[Dict]:
        """
        在日志文件中搜索匹配的行
        
        Args:
            filepath: 日志文件路径
            pattern: 搜索模式 (支持正则)
            max_lines: 最大返回行数
            since_hours: 搜索最近几小时内的日志
        """
        import re
        import gzip
        
        if not os.path.exists(filepath):
            logger.warning(f"日志文件不存在: {filepath}")
            return []
        
        # 计算时间过滤
        cutoff_time = datetime.now().timestamp() - (since_hours * 3600)
        results = []
        
        try:
            # 处理 gzip 压缩日志
            if filepath.endswith('.gz'):
                opener = gzip.open
                mode = 'rt'
            else:
                opener = open
                mode = 'r'
            
            with opener(filepath, mode, encoding='utf-8', errors='ignore') as f:
                for line in f:
                    try:
                        # 解析日志时间戳 (常见格式: 2022-08-01 10:30:45)
                        if len(line) > 19:
                            log_time_str = line[:19]
                            try:
                                log_time = datetime.strptime(log_time_str, '%Y-%m-%d %H:%M:%S').timestamp()
                                if log_time < cutoff_time:
                                    continue
                            except ValueError:
                                pass  # 无法解析时间，使用行
                        
                        # 匹配模式
                        if re.search(pattern, line):
                            results.append({
                                "line": line.strip(),
                                "file": filepath,
                                "timestamp": log_time_str if 'log_time_str' in locals() else None
                            })
                            
                            if len(results) >= max_lines:
                                break
                    except Exception as e:
                        logger.debug(f"解析日志行失败: {e}")
                        continue
                        
        except Exception as e:
            logger.error(f"读取日志文件失败 {filepath}: {e}")
        
        return results
    
    def search_all_logs(self, pattern: str, service: str = None) -> Dict[str, List]:
        """在所有日志中搜索"""
        log_paths = self.config._config.get("log_paths", {})
        all_results = {}
        
        for log_name, log_path in log_paths.items():
            if service and service != log_name:
                continue
            
            logger.info(f"搜索日志: {log_name} -> {log_path}")
            results = self.search_in_file(log_path, pattern)
            if results:
                all_results[log_name] = results
        
        return all_results
    
    def get_error_summary(self, hours: int = 24) -> Dict:
        """获取错误汇总统计"""
        error_patterns = {
            "ERROR": r'\bERROR\b',
            "WARNING": r'\bWARNING\b',
            "CRITICAL": r'\bCRITICAL\b|Exception|Traceback',
            "FAILED": r'\bFAILED\b',
            "TIMEOUT": r'\bTIMEOUT\b'
        }
        
        summary = {}
        for error_type, pattern in error_patterns.items():
            results = self.search_all_logs(pattern, since_hours=hours)
            count = sum(len(v) for v in results.values())
            summary[error_type] = {
                "count": count,
                "details": results
            }
        
        return summary


class AlertManager:
    """告警管理器"""
    
    def __init__(self, config: ConfigManager):
        self.config = config
    
    def send_email_alert(self, subject: str, body: str) -> bool:
        """发送邮件告警"""
        smtp_config = self.config._config.get("smtp", {})
        
        try:
            msg = MIMEMultipart()
            msg['From'] = smtp_config.get('from_addr')
            msg['To'] = ', '.join(smtp_config.get('to_addrs', []))
            msg['Subject'] = subject
            
            msg.attach(MIMEText(body, 'html', 'utf-8'))
            
            server = smtplib.SMTP(smtp_config['host'], smtp_config['port'])
            server.starttls()
            server.login(smtp_config['username'], smtp_config['password'])
            server.send_message(msg)
            server.quit()
            
            logger.info(f"告警邮件发送成功: {subject}")
            return True
            
        except Exception as e:
            logger.error(f"发送告警邮件失败: {e}")
            return False
    
    def check_and_alert(self, results: List[ServiceCheckResult]) -> None:
        """检查结果并发送告警"""
        threshold = self.config.alert_rules.get("response_time_threshold", 3.0)
        
        critical_services = [
            r for r in results 
            if r.status == ServiceStatus.CRITICAL.value
        ]
        
        slow_services = [
            r for r in results 
            if r.response_time > threshold
        ]
        
        if critical_services:
            body = "<h2>🚨 服务不可达告警</h2><table border='1'>"
            body += "<tr><th>服务</th><th>状态</th><th>消息</th></tr>"
            for service in critical_services:
                body += f"<tr><td>{service.service_name}</td>"
                body += f"<td style='color:red'>{service.status}</td>"
                body += f"<td>{service.message}</td></tr>"
            body += "</table>"
            self.send_email_alert("【告警】服务不可达", body)
        
        if slow_services:
            body = "<h2>⚠️ 服务响应缓慢告警</h2><table border='1'>"
            body += "<tr><th>服务</th><th>响应时间</th><th>阈值</th></tr>"
            for service in slow_services:
                body += f"<tr><td>{service.service_name}</td>"
                body += f"<td>{service.response_time:.3f}s</td>"
                body += f"<td>{threshold}s</td></tr>"
            body += "</table>"
            self.send_email_alert("【警告】服务响应缓慢", body)


class MonitorReporter:
    """监控报告生成器"""
    
    def __init__(self, config: ConfigManager):
        self.config = config
    
    def generate_report(self, results: List[ServiceCheckResult]) -> str:
        """生成监控报告"""
        report = []
        report.append("=" * 60)
        report.append(f"智能网联平台运维监控报告")
        report.append(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append("=" * 60)
        report.append("")
        
        # 统计信息
        total = len(results)
        healthy = sum(1 for r in results if r.status == "healthy")
        critical = sum(1 for r in results if r.status == "critical")
        
        report.append(f"📊 服务状态统计:")
        report.append(f"   总计: {total} | 正常: {healthy} | 异常: {critical}")
        report.append("")
        
        # 详细状态
        report.append(f"📋 详细状态:")
        report.append("-" * 60)
        for result in results:
            status_icon = "✅" if result.status == "healthy" else "❌"
            report.append(f"{status_icon} {result.service_name:15} | "
                         f"{result.status:10} | {result.message}")
        
        report.append("")
        report.append("=" * 60)
        
        return "\n".join(report)
    
    def export_prometheus_metrics(self, results: List[ServiceCheckResult]) -> str:
        """导出 Prometheus 指标格式"""
        metrics = ["# HELP service_status Service health status (1=healthy, 0=unhealthy)",
                   "# TYPE service_status gauge"]
        
        for result in results:
            metrics.append(result.to_prometheus_format())
        
        return "\n".join(metrics)


def main():
    """主函数 - 每日巡检"""
    logger.info("=" * 50)
    logger.info("开始每日服务巡检")
    logger.info("=" * 50)
    
    # 初始化
    config = ConfigManager()
    checker = ServiceChecker(config)
    alert_manager = AlertManager(config)
    reporter = MonitorReporter(config)
    
    # 检查所有服务
    results = checker.check_all_services()
    
    # 生成报告
    report = reporter.generate_report(results)
    print(report)
    
    # 保存报告
    report_path = f"/var/log/monitor/daily_report_{datetime.now().strftime('%Y%m%d')}.txt"
    os.makedirs(os.path.dirname(report_path), exist_ok=True)
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(report)
    logger.info(f"报告已保存: {report_path}")
    
    # 检查并发送告警
    alert_manager.check_and_alert(results)
    
    # 导出 Prometheus 指标
    metrics = reporter.export_prometheus_metrics(results)
    metrics_path = "/var/lib/node_exporter/textfile_collector/service_status.prom"
    os.makedirs(os.path.dirname(metrics_path), exist_ok=True)
    with open(metrics_path, 'w', encoding='utf-8') as f:
        f.write(metrics)
    
    logger.info("每日巡检完成")
    return 0 if all(r.status == "healthy" for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
