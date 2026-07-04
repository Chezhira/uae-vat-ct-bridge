from __future__ import annotations

from decimal import Decimal

from engine.constants import DEFAULT_FIXED_MATERIALITY_AED, DEFAULT_PERCENT_MATERIALITY
from engine.models import BridgeInputs, BridgeTableRow


def calculate_vat_declared_supplies(inputs: BridgeInputs) -> Decimal:
    return sum(
        (period.std_rated_supplies + period.zero_rated_supplies + period.exempt_supplies + period.adjustments)
        for period in inputs.vat_returns
    )


def calculate_reverse_charge_context(inputs: BridgeInputs) -> Decimal:
    return sum(period.reverse_charge_supplies for period in inputs.vat_returns)


def calculate_materiality(accounting_revenue: Decimal, override: Decimal | None = None) -> Decimal:
    if override is not None:
        return override
    return max(DEFAULT_FIXED_MATERIALITY_AED, accounting_revenue * DEFAULT_PERCENT_MATERIALITY)


def build_bridge_table(inputs: BridgeInputs) -> list[BridgeTableRow]:
    vat_declared = calculate_vat_declared_supplies(inputs)
    rows = [BridgeTableRow(label="VAT-declared supplies", amount=vat_declared)]
    for item in inputs.reconciling_items:
        rows.append(BridgeTableRow(label=f"Reconciling item: {item.description}", amount=item.amount))
    bridge_target = vat_declared + sum(item.amount for item in inputs.reconciling_items)
    residual = inputs.ct_computation.accounting_revenue - bridge_target
    rows.extend(
        [
            BridgeTableRow(label="Bridge target", amount=bridge_target),
            BridgeTableRow(
                label="Accounting revenue per CT computation",
                amount=inputs.ct_computation.accounting_revenue,
            ),
            BridgeTableRow(label="Residual unexplained difference", amount=residual),
        ]
    )
    return rows


def calculate_bridge_values(inputs: BridgeInputs) -> dict[str, Decimal]:
    vat_declared = calculate_vat_declared_supplies(inputs)
    total_reconciling = sum(item.amount for item in inputs.reconciling_items)
    bridge_target = vat_declared + total_reconciling
    accounting_revenue = inputs.ct_computation.accounting_revenue
    residual = accounting_revenue - bridge_target
    materiality = calculate_materiality(accounting_revenue, inputs.materiality_override)
    return {
        "vat_declared_supplies": vat_declared,
        "reverse_charge_context": calculate_reverse_charge_context(inputs),
        "total_reconciling_items": total_reconciling,
        "bridge_target": bridge_target,
        "accounting_revenue": accounting_revenue,
        "residual": residual,
        "materiality": materiality,
    }
