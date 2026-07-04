from datetime import date
from decimal import Decimal

RULES_VERSION = "2026-07"
RULES_VERIFIED_ON = date(2026, 7, 4)

# UAE VAT standard rate is 5 percent under UAE VAT legislation.
UAE_VAT_STANDARD_RATE = Decimal("0.05")
DEFAULT_FIXED_MATERIALITY_AED = Decimal("10000")
DEFAULT_PERCENT_MATERIALITY = Decimal("0.005")

# UAE Corporate Tax returns are generally due within 9 months after tax period end.
CT_FILING_DEADLINE_MONTHS_AFTER_PERIOD_END = 9

EXPORT_DISCLAIMER = (
    "This tool provides an arithmetic self-check for internal preparation purposes only. "
    "It is not tax advice, does not constitute a tax filing, and is not affiliated with "
    "or endorsed by the UAE Federal Tax Authority. Consult a registered UAE tax agent "
    "or qualified adviser before taking any tax position."
)

SAFE_POSITIONING = (
    "This tool performs an arithmetic pre-filing self-check between VAT return totals "
    "and accounting revenue used for Corporate Tax preparation. It helps finance teams "
    "identify and document unexplained differences before filing. It is not tax advice "
    "and does not constitute a filing or official FTA review."
)
