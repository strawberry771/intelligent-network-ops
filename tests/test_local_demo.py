"""Black-box checks for the isolated, loopback-only project demonstration."""

from pathlib import Path
import subprocess
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "demo" / "local_demo.py"


class LocalDemoTests(unittest.TestCase):
    def run_demo(self):
        return subprocess.run(
            [sys.executable, str(DEMO)],
            cwd=ROOT,
            text=True,
            capture_output=True,
            timeout=15,
            check=False,
        )

    def test_loopback_service_inspection_reports_live_and_closed_ports(self):
        result = self.run_demo()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("demo_service=healthy", result.stdout)
        self.assertIn("unused_local_port=critical", result.stdout)
        self.assertIn("prometheus_healthy=1", result.stdout)
        self.assertIn("prometheus_unreachable=0", result.stdout)
        self.assertEqual(result.stderr, "", "The copyable demo output should not include variable local ports")

    def test_sample_log_search_covers_plain_gzip_and_time_filter(self):
        result = self.run_demo()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("plain_match_count=1", result.stdout)
        self.assertIn("plain_match=ERROR sample request timed out", result.stdout)
        self.assertIn("gzip_match_count=1", result.stdout)
        self.assertIn("gzip_match=WARNING compressed sample retry", result.stdout)
        self.assertIn("old_entry_filtered=true", result.stdout)
        self.assertIn("data_scope=local_sample_only", result.stdout)

    def test_triage_view_reports_error_summary_without_claiming_causality(self):
        result = self.run_demo()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("summary_24h=ERROR:1 WARNING:1 CRITICAL:0 FAILED:0 TIMEOUT:0", result.stdout)
        self.assertIn("triage_view=critical TCP status + recent ERROR log", result.stdout)
        self.assertIn("evidence_relation=independent_local_examples", result.stdout)

    def test_metric_values_come_from_the_generated_metrics_text(self):
        from demo import local_demo

        parser = getattr(local_demo, "parse_metric_values", None)
        self.assertIsNotNone(parser)
        sample = (
            '# HELP service_status Demo\n'
            'service_status{service="demo_service"} 0\n'
            'service_status{service="unused_local_port"} 1\n'
        )
        self.assertEqual(
            parser(sample),
            {"demo_service": 0, "unused_local_port": 1},
        )


if __name__ == "__main__":
    unittest.main()
