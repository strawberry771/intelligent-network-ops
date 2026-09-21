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


if __name__ == "__main__":
    unittest.main()
