"""Behavioral checks for the configured-log error summary."""

from datetime import datetime, timedelta
import gzip
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from demo.local_demo import load_legacy_module


class ErrorSummaryTests(unittest.TestCase):
    def test_summary_scans_plain_and_gzip_logs_with_requested_time_window(self):
        legacy = load_legacy_module()
        recent = datetime.now() - timedelta(hours=2)
        old = datetime.now() - timedelta(hours=48)

        with TemporaryDirectory(prefix="error_summary_test_") as temp_dir:
            temp = Path(temp_dir)
            plain_log = temp / "app.log"
            plain_log.write_text(
                f"{recent:%Y-%m-%d %H:%M:%S} ERROR request TIMEOUT\n"
                f"{old:%Y-%m-%d %H:%M:%S} CRITICAL historical failure\n",
                encoding="utf-8",
            )
            compressed_log = temp / "worker.log.gz"
            with gzip.open(compressed_log, "wt", encoding="utf-8") as stream:
                stream.write(f"{recent:%Y-%m-%d %H:%M:%S} WARNING retry\n")

            config = legacy.ConfigManager(config_path=str(temp / "missing.json"))
            config._config["log_paths"] = {
                "app": str(plain_log),
                "worker": str(compressed_log),
            }
            searcher = legacy.LogSearcher(config)

            last_day = searcher.get_error_summary(hours=24)
            self.assertEqual(
                {kind: item["count"] for kind, item in last_day.items()},
                {"ERROR": 1, "WARNING": 1, "CRITICAL": 0, "FAILED": 0, "TIMEOUT": 1},
            )
            self.assertIn("app", last_day["ERROR"]["details"])
            self.assertIn("worker", last_day["WARNING"]["details"])
            self.assertEqual(
                {kind: item["count"] for kind, item in searcher.get_error_summary(hours=1).items()},
                {"ERROR": 0, "WARNING": 0, "CRITICAL": 0, "FAILED": 0, "TIMEOUT": 0},
            )


if __name__ == "__main__":
    unittest.main()
