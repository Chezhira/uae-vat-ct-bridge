from __future__ import annotations

from datetime import date
from decimal import Decimal

from engine.models import BridgeInputs, CheckResult, ExceptionDriver, ScoreResult

SCORE_NARRATIVE = (
    "This score is an internal prioritisation indicator based only on the uploaded data "
    "and the checks in this tool. It is not a prediction of FTA action."
)


def score_band(score: int) -> str:
    if score <= 25:
        return "Low exception load"
    if score <= 60:
        return "Medium exception load"
    return "High exception load"


def calculate_exception_score(
    inputs: BridgeInputs,
    checks: list[CheckResult],
    residual: Decimal,
    materiality: Decimal,
    filing_deadline: date,
    today: date | None = None,
) -> ScoreResult:
    today = today or date.today()
    score = 0

    if materiality > 0:
        residual_ratio = abs(residual) / materiality
        score += min(45, int(residual_ratio * 45))

    undocumented_material = [
        item for item in inputs.reconciling_items if abs(item.amount) > materiality and not item.evidence_ref.strip()
    ]
    if undocumented_material:
        score += 20

    warn_count = sum(1 for check in checks if check.status == "WARN")
    fail_count = sum(1 for check in checks if check.status == "FAIL")
    score += min(25, warn_count * 5 + fail_count * 10)

    days_remaining = (filing_deadline - today).days
    if days_remaining < 0:
        score += 10
    elif days_remaining <= 30:
        score += 8
    elif days_remaining <= 90:
        score += 5

    score = max(0, min(100, score))
    return ScoreResult(score=score, label=score_band(score), narrative=SCORE_NARRATIVE)


def build_exception_drivers(
    inputs: BridgeInputs,
    checks: list[CheckResult],
    residual: Decimal,
    materiality: Decimal,
    filing_deadline: date,
    today: date | None = None,
) -> list[ExceptionDriver]:
    today = today or date.today()
    drivers: list[ExceptionDriver] = []
    if abs(residual) > materiality:
        drivers.append(
            ExceptionDriver(
                driver="Residual unexplained difference vs materiality",
                weight=45,
                detail=f"Residual AED {residual:,.2f} exceeds materiality AED {materiality:,.2f}.",
            )
        )
    if any(abs(item.amount) > materiality and not item.evidence_ref.strip() for item in inputs.reconciling_items):
        drivers.append(
            ExceptionDriver(
                driver="Undocumented material reconciling items",
                weight=20,
                detail="At least one material reconciling item has no evidence reference.",
            )
        )
    warning_or_failure = [check for check in checks if check.status in {"WARN", "FAIL"}]
    if warning_or_failure:
        drivers.append(
            ExceptionDriver(
                driver="Validation check failures or warnings",
                weight=25,
                detail=", ".join(check.title for check in warning_or_failure[:3]),
            )
        )
    days_remaining = (filing_deadline - today).days
    if days_remaining <= 90:
        drivers.append(
            ExceptionDriver(
                driver="Days to filing deadline",
                weight=10,
                detail=f"{days_remaining} days remaining based on runtime date {today.isoformat()}.",
            )
        )
    return sorted(drivers, key=lambda driver: driver.weight, reverse=True)
