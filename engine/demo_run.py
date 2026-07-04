from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from engine.checks import run_checks
from engine.ingest import parse_pl_summary, parse_reconciling_items, parse_vat_returns
from engine.models import BridgeInputs, CTComputation

ROOT = Path(__file__).resolve().parents[1]
DEMO_DIR = ROOT / "data" / "demo_dataset"


def load_demo_inputs() -> BridgeInputs:
    ct_computation = CTComputation.model_validate(json.loads((DEMO_DIR / "ct_computation_demo.json").read_text()))
    return BridgeInputs(
        company_name="Falcon Trading DMCC, demo only",
        vat_returns=parse_vat_returns(DEMO_DIR / "vat_returns_demo.csv"),
        pl_summary=parse_pl_summary(DEMO_DIR / "pl_summary_demo.csv"),
        ct_computation=ct_computation,
        reconciling_items=parse_reconciling_items(DEMO_DIR / "reconciling_items_demo.csv"),
    )


def main() -> int:
    findings = run_checks(load_demo_inputs(), today=date(2026, 7, 4))
    expected_residual = "90000"
    expected_status = "FAIL"
    if str(findings.residual) != expected_residual or findings.bridge_status != expected_status:
        print("Demo smoke test failed.")
        print(f"Residual: {findings.residual}; status: {findings.bridge_status}")
        return 1
    print(json.dumps(findings.report_data["summary"], indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
