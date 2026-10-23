import csv
import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "reconcile_mt5_api_candles.py"
START = 1729382400  # 2024-10-20 00:00:00 UTC
END = START + 3 * 60

def write_csv(path: Path, header, rows):
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f); writer.writerow(header); writer.writerows(rows)

def run(api, mt5, out, *args):
    return subprocess.run([sys.executable, str(SCRIPT), "--api", str(api), "--mt5", str(mt5),
        "--api-symbol", "R_100", "--mt5-symbol", "Volatility 100 Index",
        "--start-epoch", str(START), "--end-epoch-exclusive", str(END),
        "--output", str(out), *args], capture_output=True, text=True, check=False)

def build_files(tmp_path, mt5_rows=None, api_rows=None):
    epochs = [START, START + 60, START + 120]
    rows = [[e, "100.00", "100.50", "99.50", "100.20"] for e in epochs]
    api, mt5 = tmp_path / "api.csv", tmp_path / "mt5.csv"
    header = ["epoch", "open", "high", "low", "close"]
    write_csv(api, header, rows if api_rows is None else api_rows)
    write_csv(mt5, header, rows if mt5_rows is None else mt5_rows)
    return api, mt5

def test_exact_ohlc_match_passes_and_emits_hashes(tmp_path):
    api, mt5 = build_files(tmp_path); out = tmp_path / "report.json"
    result = run(api, mt5, out)
    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads(out.read_text(encoding="utf-8"))
    assert report["status"] == "PASS_EXACT_OHLC_EQUIVALENCE" and report["matched_rows"] == 3
    assert len(report["api_sha256"]) == 64 and len(report["mt5_sha256"]) == 64

def test_one_ohlc_price_deviation_fails_closed(tmp_path):
    rows = [[START, "100.00", "100.50", "99.50", "100.20"], [START+60, "100.00", "100.50", "99.50", "100.20"], [START+120, "100.00", "100.51", "99.50", "100.20"]]
    api, mt5 = build_files(tmp_path, mt5_rows=rows); out=tmp_path/"report.json"; result=run(api,mt5,out)
    assert result.returncode != 0 and "OHLC_MISMATCH" in result.stdout
    assert json.loads(out.read_text())["status"] == "BLOCKED_OHLC_MISMATCH"

def test_missing_minute_fails_without_interpolating(tmp_path):
    rows = [[START, "100.00", "100.50", "99.50", "100.20"], [START+120, "100.00", "100.50", "99.50", "100.20"]]
    api, mt5 = build_files(tmp_path, mt5_rows=rows); result=run(api,mt5,tmp_path/"report.json")
    assert result.returncode != 0 and "EPOCH_SET_MISMATCH" in result.stdout

def test_duplicate_epoch_fails_without_deduplicating(tmp_path):
    rows = [[START, "100.00", "100.50", "99.50", "100.20"], [START+60, "100.00", "100.50", "99.50", "100.20"], [START+60, "100.00", "100.50", "99.50", "100.20"], [START+120, "100.00", "100.50", "99.50", "100.20"]]
    api, mt5 = build_files(tmp_path, mt5_rows=rows); result=run(api,mt5,tmp_path/"report.json")
    assert result.returncode != 0 and "DUPLICATE_EPOCH" in result.stdout

def test_untagged_mt5_datetime_requires_timezone(tmp_path):
    api, mt5 = tmp_path/"api.csv", tmp_path/"mt5.csv"
    write_csv(api, ["epoch","open","high","low","close"], [[START+i*60,"100.00","100.50","99.50","100.20"] for i in range(3)])
    write_csv(mt5, ["Date","Time","Open","High","Low","Close"], [["2024.10.20",f"00:0{i}:00","100.00","100.50","99.50","100.20"] for i in range(3)])
    result=run(api,mt5,tmp_path/"report.json")
    assert result.returncode != 0 and "TIMEZONE_REQUIRED" in result.stdout

def test_mt5_datetime_matches_with_explicit_timezone(tmp_path):
    api, mt5 = tmp_path/"api.csv", tmp_path/"mt5.csv"
    write_csv(api, ["epoch","open","high","low","close"], [[START+i*60,"100.00","100.50","99.50","100.20"] for i in range(3)])
    write_csv(mt5, ["Date","Time","Open","High","Low","Close"], [["2024.10.20",f"00:0{i}:00","100.00","100.50","99.50","100.20"] for i in range(3)])
    result=run(api,mt5,tmp_path/"report.json","--mt5-timezone","UTC")
    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads((tmp_path/"report.json").read_text())["status"] == "PASS_EXACT_OHLC_EQUIVALENCE"

def test_reversed_rows_fail_without_sorting(tmp_path):
    rows = [[START+120,"100.00","100.50","99.50","100.20"],[START+60,"100.00","100.50","99.50","100.20"],[START,"100.00","100.50","99.50","100.20"]]
    api, mt5 = build_files(tmp_path, mt5_rows=rows); result=run(api,mt5,tmp_path/"report.json")
    assert result.returncode != 0 and "NON_MONOTONIC_EPOCHS" in result.stdout
