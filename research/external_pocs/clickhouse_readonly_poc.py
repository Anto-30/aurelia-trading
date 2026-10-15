"""Ephemeral ClickHouse read-only analytics proof of concept; uses synthetic events only."""
from __future__ import annotations

import json
import os
import sys
import time

import clickhouse_connect

HOST = os.getenv("CLICKHOUSE_HOST", "127.0.0.1")
PORT = int(os.getenv("CLICKHOUSE_PORT", "8123"))
ADMIN_USER = os.getenv("CLICKHOUSE_ADMIN_USER", "default")
ADMIN_PASSWORD = os.getenv("CLICKHOUSE_ADMIN_PASSWORD", "ci-test-password")
REPORT_USER = "aurelia_reporting_poc"
REPORT_PASSWORD = "ci-reporting-password"


def main() -> int:
    admin = clickhouse_connect.get_client(
        host=HOST, port=PORT, username=ADMIN_USER, password=ADMIN_PASSWORD,
        connect_timeout=5, send_receive_timeout=10,
    )
    try:
        admin.command("CREATE DATABASE IF NOT EXISTS external_poc")
        admin.command(
            """
            CREATE TABLE IF NOT EXISTS external_poc.events (
                event_id String,
                event_version UInt64,
                event_time DateTime64(3, 'UTC'),
                strategy_id LowCardinality(String),
                pnl Float64
            ) ENGINE = ReplacingMergeTree(event_version)
            ORDER BY event_id
            """
        )
        admin.command(f"DROP USER IF EXISTS {REPORT_USER}")
        admin.command(
            f"CREATE USER {REPORT_USER} IDENTIFIED WITH plaintext_password "
            f"BY '{REPORT_PASSWORD}' SETTINGS readonly = 1"
        )
        admin.command(f"GRANT SELECT ON external_poc.events TO {REPORT_USER}")
        admin.command("TRUNCATE TABLE external_poc.events")
        admin.insert(
            "external_poc.events",
            [
                ("evt-1", 1, "2026-01-01 00:00:00.000", "synthetic-fixture", 1.0),
                ("evt-1", 2, "2026-01-01 00:00:00.000", "synthetic-fixture", 1.5),
                ("evt-2", 1, "2026-01-01 00:00:01.000", "synthetic-fixture", -0.2),
            ],
            column_names=["event_id", "event_version", "event_time", "strategy_id", "pnl"],
        )
        expected = admin.query("SELECT count() FROM external_poc.events FINAL").result_rows[0][0]
        if expected != 2:
            raise AssertionError(f"REPLACING_MERGETREE_DEDUPLICATION_FAILED:{expected}")

        reporter = clickhouse_connect.get_client(
            host=HOST, port=PORT, username=REPORT_USER, password=REPORT_PASSWORD,
            connect_timeout=5, send_receive_timeout=10,
        )
        try:
            visible = reporter.query("SELECT count() FROM external_poc.events FINAL").result_rows[0][0]
            if visible != 2:
                raise AssertionError(f"READ_ONLY_SELECT_FAILED:{visible}")
            for operation, sql in (
                ("INSERT", "INSERT INTO external_poc.events VALUES ('blocked', 1, '2026-01-01 00:00:02.000', 'fixture', 0)"),
                ("ALTER", "ALTER TABLE external_poc.events ADD COLUMN forbidden UInt8"),
            ):
                try:
                    reporter.command(sql)
                except Exception:
                    continue
                raise AssertionError(f"READ_ONLY_{operation}_WAS_ALLOWED")
        finally:
            reporter.close()

        print(json.dumps({
            "status": "PASS",
            "synthetic_event_rows_after_final_dedup": visible,
            "reporting_user_select": "ALLOWED",
            "reporting_user_insert": "DENIED",
            "reporting_user_alter": "DENIED",
            "authority": "READ_ONLY_ANALYTICS_NO_EXECUTION_OR_LEDGER_AUTHORITY",
        }, sort_keys=True))
        return 0
    finally:
        try:
            admin.command(f"DROP USER IF EXISTS {REPORT_USER}")
        except Exception:
            pass
        admin.close()


if __name__ == "__main__":
    sys.exit(main())
