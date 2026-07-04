from decimal import Decimal

from engine.bridge import calculate_bridge_values, calculate_materiality
from engine.checks import check_residual_bridge


def test_bridge_residual_calculates_correctly(demo_inputs):
    values = calculate_bridge_values(demo_inputs)
    assert values["vat_declared_supplies"] == Decimal("18200000")
    assert values["bridge_target"] == Decimal("17550000")
    assert values["residual"] == Decimal("90000")


def test_materiality_default_calculates_correctly():
    assert calculate_materiality(Decimal("17640000")) == Decimal("88200.000")
    assert calculate_materiality(Decimal("1000000")) == Decimal("10000")


def test_material_residual_returns_fail(demo_inputs):
    values = calculate_bridge_values(demo_inputs)
    result = check_residual_bridge(values)
    assert result.status == "FAIL"
    assert result.amount == Decimal("90000")


def test_residual_below_materiality_returns_pass(demo_inputs):
    demo_inputs.ct_computation.accounting_revenue = Decimal("17600000")
    values = calculate_bridge_values(demo_inputs)
    result = check_residual_bridge(values)
    assert result.status == "PASS"
