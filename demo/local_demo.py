#!/usr/bin/env python3
"""Exercise the existing inspection code with loopback sockets and sample logs.

This is a 2026 presentation/verification aid, not a production run or an
original 2022 project component. It does not contact external services,
send email, or write to the legacy script's Linux paths.
"""

from __future__ import annotations

from datetime import datetime, timedelta
import gzip
import importlib.util
import logging
from pathlib import Path
import socket
import sys
from tempfile import TemporaryDirectory
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
LEGACY_SCRIPT = ROOT / "monitoring_tool" / "service_checker.py"
SAMPLE_LOGS = Path(__file__).with_name("sample_logs.txt")


def load_legacy_module():
    """Import the unchanged Linux script without opening /var/log on this host."""
    spec = importlib.util.spec_from_file_location("local_demo_service_checker", LEGACY_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    with patch.object(logging, "FileHandler", return_value=logging.NullHandler()):
        spec.loader.exec_module(module)
    module.logger.setLevel(logging.ERROR)
    return module


def run_demo():
    legacy = load_legacy_module()
    with TemporaryDirectory(prefix="network_ops_demo_") as temp_dir:
        temp = Path(temp_dir)
        config = legacy.ConfigManager(config_path=str(temp / "missing_config.json"))

        # A listening socket is the only live service. The second socket keeps
        # its port reserved but never listens, producing a controlled failure.
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as live_socket:
            live_socket.bind(("127.0.0.1", 0))
            live_socket.listen(1)
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as closed_socket:
                closed_socket.bind(("127.0.0.1", 0))
                config._config["services"] = {
                    "demo_service": {
                        "host": "127.0.0.1",
                        "port": live_socket.getsockname()[1],
                        "timeout": 1,
                    },
                    "unused_local_port": {
                        "host": "127.0.0.1",
                        "port": closed_socket.getsockname()[1],
                        "timeout": 1,
                    },
                }
                results = legacy.ServiceChecker(config).check_all_services()

        statuses = {result.service_name: result.status for result in results}
        if statuses != {"demo_service": "healthy", "unused_local_port": "critical"}:
            raise RuntimeError(f"Unexpected local TCP inspection: {statuses}")

        reporter = legacy.MonitorReporter(config)
        report = reporter.generate_report(results)
        metrics = reporter.export_prometheus_metrics(results)
        if "demo_service" not in report or "unused_local_port" not in report:
            raise RuntimeError("Inspection report omitted a sample service")
        for expected in (
            'service_status{service="demo_service"} 1',
            'service_status{service="unused_local_port"} 0',
        ):
            if expected not in metrics:
                raise RuntimeError(f"Missing sample metric: {expected}")

        now = datetime.now()
        old = now - timedelta(hours=48)
        plain_text = SAMPLE_LOGS.read_text(encoding="utf-8")
        plain_text = plain_text.replace("{NOW}", now.strftime("%Y-%m-%d %H:%M:%S"))
        plain_text = plain_text.replace("{OLD}", old.strftime("%Y-%m-%d %H:%M:%S"))
        plain_log = temp / "sample.log"
        plain_log.write_text(plain_text, encoding="utf-8")
        compressed_log = temp / "sample.log.gz"
        with gzip.open(compressed_log, "wt", encoding="utf-8") as stream:
            stream.write(f"{now:%Y-%m-%d %H:%M:%S} WARNING compressed sample retry\n")

        searcher = legacy.LogSearcher(config)
        plain_matches = searcher.search_in_file(
            str(plain_log), r"ERROR|CRITICAL", since_hours=24
        )
        gzip_matches = searcher.search_in_file(
            str(compressed_log), r"WARNING", since_hours=24
        )
        old_matches = searcher.search_in_file(
            str(plain_log), r"CRITICAL", since_hours=24
        )
        if len(plain_matches) != 1 or len(gzip_matches) != 1 or old_matches:
            raise RuntimeError("Sample log search did not match the expected time window")

    print("[LOCAL DEMO: loopback service + synthetic sample logs]")
    print(f"demo_service={statuses['demo_service']}")
    print(f"unused_local_port={statuses['unused_local_port']}")
    print("prometheus_healthy=1")
    print("prometheus_unreachable=0")
    print(f"plain_match_count={len(plain_matches)}")
    print(f"plain_match={plain_matches[0]['line'].split(' ', 2)[2]}")
    print(f"gzip_match_count={len(gzip_matches)}")
    print(f"gzip_match={gzip_matches[0]['line'].split(' ', 2)[2]}")
    print(f"old_entry_filtered={str(not old_matches).lower()}")
    print("data_scope=local_sample_only")


if __name__ == "__main__":
    run_demo()
