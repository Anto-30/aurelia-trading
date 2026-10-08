from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from runtime.core.trade_counter import read_journal, trade_count


def main() -> int:
    parser = argparse.ArgumentParser(description="Report accepted AURELIA broker trade count.")
    parser.add_argument(
        "--journal",
        default=os.getenv("AURELIA_JOURNAL_PATH", "/tmp/aurelia/journal.ndjson"),
    )
    args = parser.parse_args()

    summary = trade_count(read_journal(Path(args.journal)))
    report = {
        "schema": "aurelia.trade_count.v1",
        "journal_path": str(Path(args.journal)),
        "accepted_trades": summary.accepted_trades,
        "unique_intents": summary.unique_intents,
        "last_trade_at_utc": summary.last_trade_at_utc,
        "capital_authority_granted": False,
        "execution_enablement": False,
    }
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
