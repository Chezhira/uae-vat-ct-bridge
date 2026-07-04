import json
from datetime import date
from pathlib import Path

from engine.checks import run_checks

ROOT = Path(__file__).resolve().parents[1]


def test_demo_dataset_matches_expected_golden_json(demo_inputs):
    expected = json.loads((ROOT / "tests" / "golden" / "uae_demo_expected.json").read_text())
    findings = run_checks(demo_inputs, today=date(2026, 7, 4))
    actual = {
        "company_name": findings.company_name,
        "vat_declared_supplies": str(findings.vat_declared_supplies),
        "reverse_charge_context": str(findings.reverse_charge_context),
        "total_reconciling_items": str(findings.total_reconciling_items),
        "bridge_target": str(findings.bridge_target),
        "accounting_revenue": str(findings.accounting_revenue),
        "residual": str(findings.residual),
        "materiality": str(findings.materiality),
        "bridge_status": findings.bridge_status,
        "score_label": findings.score.label,
        "filing_deadline": findings.filing_deadline.isoformat(),
        "top_exception_drivers": [driver.driver for driver in findings.top_exception_drivers],
    }
    assert actual == expected
