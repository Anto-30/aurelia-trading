"""Repository-level AURELIA certification gate.

This gate checks repository/control/evidence readiness only. It never grants
live authority and never contacts a broker.
"""
from __future__ import annotations
import argparse,json
from pathlib import Path
from typing import Any
from .certification_evidence import runtime_source_status, validate_evidence_bundle
MANDATORY_DOCUMENTS=(
 "docs/AURELIA_PRODUCTION_STANDARD.yaml","docs/AURELIA_CONSTITUTION.md","docs/AURELIA_TEST_ORACLE_MATRIX.yaml","docs/AURELIA_ASSURANCE_PROGRAM.md","docs/AURELIA_SECURITY_THREAT_MODEL.md","docs/AURELIA_COUNTERFACTUAL_NEARMISS.md","docs/AURELIA_RESEARCH_GOVERNANCE.yaml","docs/AURELIA_RELEASE_MANIFEST.yaml","docs/AURELIA_STATUS_MODEL.yaml","docs/AURELIA_CONTROL_HARDENING_2026-10-03.yaml","docs/AURELIA_ADVERSARIAL_SOAK_PROTOCOL_2026-10-03.md","docs/AURELIA_STAKE_POLICY_2026-10-03.md","docs/AURELIA_RESEARCH_QUALITY_CONTROLS_2026-10-03.md","docs/AURELIA_RUNTIME_BASELINE_2026-10-03.md")
HARDENING_MARKERS=("assurance/aurelia_hardening.py","assurance/adversarial_matrix.py","assurance/evidence_writer.py","assurance/research_quality.py","assurance/soak_protocol.py","assurance/operational_hardening.py")

def exists(root,p): return (root/p).exists()
def evaluate_repository(root):
 results=[]
 missing=[p for p in MANDATORY_DOCUMENTS if not exists(root,p)]
 results.append({"name":"ASSURANCE_DOCUMENTS","status":"PASS" if not missing else "FAIL","detail":"All assurance documents present." if not missing else "Missing: "+", ".join(missing)})
 missing=[p for p in HARDENING_MARKERS if not exists(root,p)]
 results.append({"name":"HARDENING_CONTRACTS","status":"PASS" if not missing else "FAIL","detail":"All hardening contracts present." if not missing else "Missing: "+", ".join(missing)})
 source,source_missing=runtime_source_status(root)
 if source=="HISTORICAL": detail="Historical v1.27 runtime markers are present.";status="PASS"
 elif source=="NEW_BASELINE": detail="Explicit new AURELIA runtime baseline is present; historical v1.27 source is not inferred.";status="PASS"
 else: detail="Neither authoritative historical runtime nor complete new baseline is synced; missing baseline markers: "+", ".join(source_missing);status="BLOCKED"
 results.append({"name":"AURELIA_SOURCE_SYNC","status":status,"detail":detail})
 evs,detail=validate_evidence_bundle(root);results.append({"name":"PRODUCTION_EVIDENCE","status":evs,"detail":detail})
 results.append({"name":"LIVE_EXECUTION","status":"BLOCKED","detail":"Repository certification never grants live capital authority."})
 return results

def overall(results):
 blocking=[r for r in results if r["status"] in {"FAIL","BLOCKED"} and r["name"]!="LIVE_EXECUTION"]
 return "READY_FOR_CAPITAL_REVIEW" if not blocking else "NOT_READY"

def main():
 parser=argparse.ArgumentParser();parser.add_argument("--json-out",default=None);args=parser.parse_args();root=Path(__file__).resolve().parents[1];results=evaluate_repository(root);status=overall(results)
 for r in results: print(f"[{r['status']}] {r['name']}: {r['detail']}")
 print(f"CERTIFICATION_RESULT={status}");print("FINAL_EXECUTION_AUTHORIZATION=FALSE");print("LIVE_EXECUTION=BLOCKED")
 if args.json_out:
  out=root/args.json_out;out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps({"repository":"Anto-30/aurelia-trading","certification_result":status,"final_execution_authorization":False,"live_execution":"BLOCKED","results":results},indent=2,sort_keys=True)+"\n",encoding="utf-8");print(f"CERTIFICATION_REPORT={out}")
 return 0 if status=="READY_FOR_CAPITAL_REVIEW" else 1
if __name__=="__main__":raise SystemExit(main())
