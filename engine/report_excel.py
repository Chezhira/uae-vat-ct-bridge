from __future__ import annotations

from io import BytesIO

import pandas as pd

from engine.constants import EXPORT_DISCLAIMER
from engine.models import BridgeFindings, BridgeInputs


def _records(models: list) -> list[dict]:
    return [model.model_dump(mode="json") for model in models]


def build_excel_working_paper(inputs: BridgeInputs, findings: BridgeFindings) -> bytes:
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        pd.DataFrame(
            [
                {"metric": "Company", "value": findings.company_name},
                {"metric": "VAT-declared supplies", "value": findings.vat_declared_supplies},
                {"metric": "Total reconciling items", "value": findings.total_reconciling_items},
                {"metric": "Accounting revenue", "value": findings.accounting_revenue},
                {"metric": "Residual unexplained difference", "value": findings.residual},
                {"metric": "Materiality", "value": findings.materiality},
                {"metric": "Bridge status", "value": findings.bridge_status_label},
                {"metric": "Pre-filing exception score", "value": findings.score.score},
                {"metric": "Score label", "value": findings.score.label},
                {
                    "metric": "Top exception drivers",
                    "value": "; ".join(d.driver for d in findings.top_exception_drivers),
                },
                {"metric": "Rules stamp", "value": findings.rules_stamp},
                {"metric": "Disclaimer", "value": EXPORT_DISCLAIMER},
            ]
        ).to_excel(writer, sheet_name="Summary", index=False)
        pd.DataFrame(_records(inputs.vat_returns)).to_excel(writer, sheet_name="VAT Returns", index=False)
        pd.DataFrame([inputs.pl_summary.model_dump(mode="json") if inputs.pl_summary else {}]).to_excel(
            writer, sheet_name="P&L Summary", index=False
        )
        pd.DataFrame([inputs.ct_computation.model_dump(mode="json")]).to_excel(
            writer, sheet_name="CT Computation", index=False
        )
        pd.DataFrame(_records(inputs.reconciling_items)).to_excel(writer, sheet_name="Reconciling Items", index=False)
        pd.DataFrame(_records(findings.checks)).to_excel(writer, sheet_name="Checks", index=False)
        pd.DataFrame(
            [
                {
                    "section": "Methodology",
                    "text": "VAT-declared supplies plus signed reconciling items equals bridge target.",
                },
                {"section": "Rules stamp", "text": findings.rules_stamp},
                {"section": "Disclaimer", "text": EXPORT_DISCLAIMER},
            ]
        ).to_excel(writer, sheet_name="Methodology", index=False)
        for worksheet in writer.sheets.values():
            worksheet.oddFooter.left.text = EXPORT_DISCLAIMER[:220]
            for column_cells in worksheet.columns:
                worksheet.column_dimensions[column_cells[0].column_letter].width = 24
    return output.getvalue()
