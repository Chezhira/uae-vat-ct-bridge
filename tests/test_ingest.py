from io import StringIO

import pytest

from engine.ingest import parse_pl_summary, parse_vat_returns


def test_valid_vat_template_parses_correctly():
    csv = StringIO(
        "period_start,period_end,std_rated_supplies,zero_rated_supplies,exempt_supplies,reverse_charge_supplies,"
        "goods_imported,adjustments,recoverable_input_vat_base,output_vat,input_vat\n"
        "2025-01-01,2025-03-31,100,0,0,0,0,0,50,5,2.5\n"
    )
    periods = parse_vat_returns(csv, "vat.csv")
    assert len(periods) == 1
    assert periods[0].std_rated_supplies == 100


def test_invalid_date_fails_clearly():
    csv = StringIO(
        "period_start,period_end,std_rated_supplies,zero_rated_supplies,exempt_supplies,reverse_charge_supplies,"
        "goods_imported,adjustments,recoverable_input_vat_base,output_vat,input_vat\n"
        "not-a-date,2025-03-31,100,0,0,0,0,0,50,5,2.5\n"
    )
    with pytest.raises(Exception, match="period_start|date"):
        parse_vat_returns(csv, "vat.csv")


def test_pl_summary_requires_one_row():
    csv = StringIO(
        "accounting_revenue,other_income,gains_on_disposal,total_expenses,accounting_profit\n100,0,0,80,20\n"
    )
    summary = parse_pl_summary(csv, "pl.csv")
    assert summary.accounting_revenue == 100
