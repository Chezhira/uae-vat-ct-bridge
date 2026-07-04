from datetime import date
from decimal import Decimal

from engine.checks import (
    check_reconciling_evidence,
    check_vat_output_arithmetic,
    check_vat_period_continuity,
    run_checks,
)
from engine.models import ReconcilingItem


def test_non_contiguous_vat_periods_warn(demo_inputs):
    demo_inputs.vat_returns[1].period_start = date(2025, 4, 2)
    result = check_vat_period_continuity(demo_inputs)
    assert result.status == "WARN"


def test_vat_output_arithmetic_warning_triggers(demo_inputs):
    demo_inputs.vat_returns[0].output_vat = Decimal("1")
    result = check_vat_output_arithmetic(demo_inputs)
    assert result.status == "WARN"


def test_missing_evidence_on_material_reconciling_item_warns(demo_inputs):
    demo_inputs.reconciling_items.append(
        ReconcilingItem(
            category="manual_adjustment_other",
            description="Large unexplained manual item",
            amount=Decimal("1000000"),
            evidence_ref="",
        )
    )
    result = check_reconciling_evidence(demo_inputs, Decimal("10000"))
    assert result.status == "WARN"


def test_deliberate_100k_gap_returns_fail(demo_inputs):
    demo_inputs.ct_computation.accounting_revenue = Decimal("17650000")
    findings = run_checks(demo_inputs, today=date(2026, 7, 4))
    assert findings.bridge_status == "FAIL"
    assert findings.residual == Decimal("100000")
