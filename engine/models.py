from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

ReconcilingCategory = Literal[
    "reverse_charge_not_revenue",
    "asset_disposal_outside_revenue",
    "other_income_outside_vat",
    "timing_difference",
    "credit_note_or_bad_debt_timing",
    "intercompany_or_branch_difference",
    "out_of_scope_income",
    "manual_adjustment_other",
]

CheckStatus = Literal["PASS", "WARN", "FAIL"]
BridgeStatus = Literal["PASS", "WARN", "FAIL"]


class MoneyModel(BaseModel):
    model_config = ConfigDict(validate_assignment=True)

    @field_validator("*", mode="before")
    @classmethod
    def blank_to_zero(cls, value):
        if value is None:
            return Decimal("0")
        return value


class VATReturnPeriod(MoneyModel):
    period_start: date
    period_end: date
    std_rated_supplies: Decimal
    zero_rated_supplies: Decimal
    exempt_supplies: Decimal
    reverse_charge_supplies: Decimal
    goods_imported: Decimal
    adjustments: Decimal
    recoverable_input_vat_base: Decimal
    output_vat: Decimal
    input_vat: Decimal

    @field_validator(
        "std_rated_supplies",
        "zero_rated_supplies",
        "exempt_supplies",
        "reverse_charge_supplies",
        "goods_imported",
        "recoverable_input_vat_base",
        "output_vat",
        "input_vat",
    )
    @classmethod
    def non_negative(cls, value: Decimal) -> Decimal:
        if value < 0:
            raise ValueError("Amount must not be negative")
        return value

    @model_validator(mode="after")
    def period_order(self) -> VATReturnPeriod:
        if self.period_end < self.period_start:
            raise ValueError("period_end must be on or after period_start")
        return self


class PLSummary(MoneyModel):
    accounting_revenue: Decimal
    other_income: Decimal
    gains_on_disposal: Decimal
    total_expenses: Decimal
    accounting_profit: Decimal


class CTComputation(MoneyModel):
    tax_period_start: date
    tax_period_end: date
    accounting_revenue: Decimal
    accounting_profit: Decimal
    taxable_income: Decimal
    entity_type: Literal["mainland", "free_zone", "unknown"] = "unknown"

    @model_validator(mode="after")
    def period_order(self) -> CTComputation:
        if self.tax_period_end < self.tax_period_start:
            raise ValueError("tax_period_end must be on or after tax_period_start")
        return self


class ReconcilingItem(MoneyModel):
    category: ReconcilingCategory
    description: str
    amount: Decimal
    evidence_ref: str = ""


class BridgeInputs(BaseModel):
    vat_returns: list[VATReturnPeriod] = Field(default_factory=list)
    pl_summary: PLSummary | None = None
    ct_computation: CTComputation
    reconciling_items: list[ReconcilingItem] = Field(default_factory=list)
    materiality_override: Decimal | None = None
    company_name: str = "User company"


class BridgeTableRow(BaseModel):
    label: str
    amount: Decimal


class CheckResult(BaseModel):
    check_id: str
    title: str
    status: CheckStatus
    amount: Decimal | None = None
    message: str
    detail: str


class ScoreResult(BaseModel):
    score: int
    label: str
    narrative: str


class ExceptionDriver(BaseModel):
    driver: str
    weight: int
    detail: str


class BridgeFindings(BaseModel):
    company_name: str
    vat_declared_supplies: Decimal
    reverse_charge_context: Decimal
    total_reconciling_items: Decimal
    bridge_target: Decimal
    accounting_revenue: Decimal
    residual: Decimal
    materiality: Decimal
    bridge_status: BridgeStatus
    bridge_status_label: str
    bridge_table: list[BridgeTableRow]
    checks: list[CheckResult]
    score: ScoreResult
    top_exception_drivers: list[ExceptionDriver]
    report_data: dict[str, Any]
    filing_deadline: date
    rules_stamp: str
