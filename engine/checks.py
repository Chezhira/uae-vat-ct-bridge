from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from dateutil.relativedelta import relativedelta

from engine.bridge import build_bridge_table, calculate_bridge_values
from engine.constants import (
    CT_FILING_DEADLINE_MONTHS_AFTER_PERIOD_END,
    RULES_VERIFIED_ON,
    RULES_VERSION,
    UAE_VAT_STANDARD_RATE,
)
from engine.models import BridgeFindings, BridgeInputs, CheckResult
from engine.score import build_exception_drivers, calculate_exception_score


def filing_deadline(tax_period_end: date) -> date:
    return tax_period_end + relativedelta(months=CT_FILING_DEADLINE_MONTHS_AFTER_PERIOD_END)


def check_vat_period_continuity(inputs: BridgeInputs) -> CheckResult:
    periods = sorted(inputs.vat_returns, key=lambda period: period.period_start)
    if not periods:
        return CheckResult(
            check_id="VAT_PERIOD_CONTINUITY",
            title="VAT period continuity",
            status="FAIL",
            message="No VAT periods were provided.",
            detail="The bridge cannot be computed without VAT return periods.",
        )

    previous_end = None
    for period in periods:
        if previous_end and period.period_start <= previous_end:
            return CheckResult(
                check_id="VAT_PERIOD_CONTINUITY",
                title="VAT period continuity",
                status="FAIL",
                message="VAT periods overlap.",
                detail="Review the period start and end dates before relying on the bridge.",
            )
        if previous_end and period.period_start != previous_end + timedelta(days=1):
            return CheckResult(
                check_id="VAT_PERIOD_CONTINUITY",
                title="VAT period continuity",
                status="WARN",
                message="VAT periods are not contiguous.",
                detail="There is a date gap between VAT periods. The bridge is usable but coverage is limited.",
            )
        previous_end = period.period_end

    ct = inputs.ct_computation
    if periods[0].period_start != ct.tax_period_start or periods[-1].period_end != ct.tax_period_end:
        return CheckResult(
            check_id="VAT_PERIOD_CONTINUITY",
            title="VAT period continuity",
            status="WARN",
            message="VAT period coverage does not exactly match the CT tax period.",
            detail="The result may be limited by partial coverage.",
        )

    return CheckResult(
        check_id="VAT_PERIOD_CONTINUITY",
        title="VAT period continuity",
        status="PASS",
        message="VAT periods are contiguous and match the CT tax period.",
        detail="Coverage matches the provided CT computation dates.",
    )


def check_vat_output_arithmetic(inputs: BridgeInputs) -> CheckResult:
    exceptions = []
    for period in inputs.vat_returns:
        expected = period.std_rated_supplies * UAE_VAT_STANDARD_RATE
        tolerance = max(Decimal("10"), period.std_rated_supplies * Decimal("0.001"))
        difference = period.output_vat - expected
        if abs(difference) > tolerance:
            exceptions.append((period.period_start, difference))

    if exceptions:
        total_difference = sum(diff for _, diff in exceptions)
        return CheckResult(
            check_id="VAT_OUTPUT_ARITHMETIC",
            title="VAT output arithmetic",
            status="WARN",
            amount=total_difference,
            message="Output VAT differs from a simple 5 percent sense check for one or more periods.",
            detail="Rounding, adjustments, emirate reporting, or special cases may explain the difference.",
        )
    return CheckResult(
        check_id="VAT_OUTPUT_ARITHMETIC",
        title="VAT output arithmetic",
        status="PASS",
        message="Output VAT is within the simple 5 percent sense-check tolerance.",
        detail="This is an arithmetic check only, not a VAT treatment conclusion.",
    )


def check_residual_bridge(values: dict[str, Decimal]) -> CheckResult:
    residual = values["residual"]
    materiality = values["materiality"]
    if abs(residual) <= materiality:
        return CheckResult(
            check_id="RESIDUAL_BRIDGE_DIFFERENCE",
            title="Residual bridge difference",
            status="PASS",
            amount=residual,
            message="No material unexplained difference based on provided data.",
            detail=f"Residual is within materiality of AED {materiality:,.2f}.",
        )
    return CheckResult(
        check_id="RESIDUAL_BRIDGE_DIFFERENCE",
        title="Residual bridge difference",
        status="FAIL",
        amount=residual,
        message="Material unexplained difference based on provided data.",
        detail=f"Residual exceeds materiality of AED {materiality:,.2f}.",
    )


def check_input_vat_sense(inputs: BridgeInputs) -> CheckResult:
    total_difference = Decimal("0")
    outside = False
    for period in inputs.vat_returns:
        expected = period.recoverable_input_vat_base * UAE_VAT_STANDARD_RATE
        tolerance = max(Decimal("1000"), expected * Decimal("0.10"))
        difference = period.input_vat - expected
        if abs(difference) > tolerance:
            outside = True
            total_difference += difference
    if outside:
        return CheckResult(
            check_id="INPUT_VAT_SENSE_CHECK",
            title="Input VAT sense check",
            status="WARN",
            amount=total_difference,
            message="Input VAT differs from a lightweight 5 percent expense-base sense check.",
            detail="This does not mean input VAT is wrong; it highlights a point to document.",
        )
    return CheckResult(
        check_id="INPUT_VAT_SENSE_CHECK",
        title="Input VAT sense check",
        status="PASS",
        message="Input VAT is within the lightweight sense-check tolerance.",
        detail="This is an arithmetic context check only.",
    )


def check_reconciling_evidence(inputs: BridgeInputs, materiality: Decimal) -> CheckResult:
    missing = [
        item.description
        for item in inputs.reconciling_items
        if abs(item.amount) > materiality and not item.evidence_ref.strip()
    ]
    if missing:
        return CheckResult(
            check_id="RECONCILING_EVIDENCE",
            title="Reconciling item evidence",
            status="WARN",
            message="One or more material reconciling items do not include an evidence reference.",
            detail="Add document references for: " + "; ".join(missing),
        )
    return CheckResult(
        check_id="RECONCILING_EVIDENCE",
        title="Reconciling item evidence",
        status="PASS",
        message="Material reconciling items include evidence references.",
        detail="Evidence references are user-provided and not independently verified.",
    )


def check_filing_deadline_context(inputs: BridgeInputs, today: date | None = None) -> CheckResult:
    today = today or date.today()
    deadline = filing_deadline(inputs.ct_computation.tax_period_end)
    days_remaining = (deadline - today).days
    return CheckResult(
        check_id="FILING_DEADLINE_CONTEXT",
        title="Filing deadline context",
        status="PASS" if days_remaining >= 0 else "WARN",
        amount=Decimal(days_remaining),
        message=f"Generic CT filing deadline context: {deadline.isoformat()}.",
        detail=(
            f"Days remaining based on runtime date {today.isoformat()}: {days_remaining}. "
            f"Rules verified as at {RULES_VERIFIED_ON.isoformat()}."
        ),
    )


def run_checks(inputs: BridgeInputs, today: date | None = None) -> BridgeFindings:
    values = calculate_bridge_values(inputs)
    deadline = filing_deadline(inputs.ct_computation.tax_period_end)
    checks = [
        check_vat_period_continuity(inputs),
        check_vat_output_arithmetic(inputs),
        check_residual_bridge(values),
        check_input_vat_sense(inputs),
        check_reconciling_evidence(inputs, values["materiality"]),
        check_filing_deadline_context(inputs, today),
    ]
    bridge_status = "PASS" if abs(values["residual"]) <= values["materiality"] else "FAIL"
    if any(check.status == "FAIL" for check in checks if check.check_id == "VAT_PERIOD_CONTINUITY"):
        bridge_status = "WARN"
    status_label = {
        "PASS": "No material unexplained difference based on provided data",
        "FAIL": "Material unexplained difference based on provided data",
        "WARN": "Result limited by incomplete or inconsistent inputs",
    }[bridge_status]
    score = calculate_exception_score(inputs, checks, values["residual"], values["materiality"], deadline, today)
    top_exception_drivers = build_exception_drivers(
        inputs,
        checks,
        values["residual"],
        values["materiality"],
        deadline,
        today,
    )
    rules_stamp = f"Rules version {RULES_VERSION}; verified as at {RULES_VERIFIED_ON.isoformat()}"
    report_data = {
        "summary": {
            "company_name": inputs.company_name,
            "vat_declared_supplies": values["vat_declared_supplies"],
            "total_reconciling_items": values["total_reconciling_items"],
            "accounting_revenue": values["accounting_revenue"],
            "residual": values["residual"],
            "materiality": values["materiality"],
            "bridge_status": bridge_status,
            "pre_filing_exception_score": score.score,
            "score_label": score.label,
            "rules_stamp": rules_stamp,
        },
        "bridge_table": [row.model_dump(mode="json") for row in build_bridge_table(inputs)],
        "checks": [check.model_dump(mode="json") for check in checks],
        "top_exception_drivers": [driver.model_dump(mode="json") for driver in top_exception_drivers],
    }
    return BridgeFindings(
        company_name=inputs.company_name,
        vat_declared_supplies=values["vat_declared_supplies"],
        reverse_charge_context=values["reverse_charge_context"],
        total_reconciling_items=values["total_reconciling_items"],
        bridge_target=values["bridge_target"],
        accounting_revenue=values["accounting_revenue"],
        residual=values["residual"],
        materiality=values["materiality"],
        bridge_status=bridge_status,
        bridge_status_label=status_label,
        bridge_table=build_bridge_table(inputs),
        checks=checks,
        score=score,
        top_exception_drivers=top_exception_drivers,
        report_data=report_data,
        filing_deadline=deadline,
        rules_stamp=rules_stamp,
    )
