from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from pathlib import Path

import pandas as pd
import streamlit as st

from engine.checks import run_checks
from engine.constants import EXPORT_DISCLAIMER, RULES_VERIFIED_ON, SAFE_POSITIONING
from engine.ingest import parse_pl_summary, parse_reconciling_items, parse_vat_returns
from engine.models import BridgeInputs, CTComputation, ReconcilingItem
from engine.report_excel import build_excel_working_paper
from engine.report_pdf import build_pdf_report

ROOT = Path(__file__).parent
DEMO_DIR = ROOT / "data" / "demo_dataset"
TEMPLATE_DIR = ROOT / "data" / "templates"
RECONCILING_CATEGORIES = [
    "reverse_charge_not_revenue",
    "asset_disposal_outside_revenue",
    "other_income_outside_vat",
    "timing_difference",
    "credit_note_or_bad_debt_timing",
    "intercompany_or_branch_difference",
    "out_of_scope_income",
    "manual_adjustment_other",
]


def money(value: Decimal) -> str:
    return f"AED {value:,.2f}"


def load_demo_inputs() -> BridgeInputs:
    ct = CTComputation.model_validate(json.loads((DEMO_DIR / "ct_computation_demo.json").read_text()))
    return BridgeInputs(
        company_name="Falcon Trading DMCC, demo only",
        vat_returns=parse_vat_returns(DEMO_DIR / "vat_returns_demo.csv"),
        pl_summary=parse_pl_summary(DEMO_DIR / "pl_summary_demo.csv"),
        ct_computation=ct,
        reconciling_items=parse_reconciling_items(DEMO_DIR / "reconciling_items_demo.csv"),
    )


def parse_uploaded(upload, parser):
    if upload is None:
        return None
    if upload.name.lower().endswith(".xlsm"):
        st.error("Something went wrong. No data was retained.")
        return None
    if upload.size > 10 * 1024 * 1024:
        st.error("File exceeds the 10 MB upload limit.")
        return None
    return parser(upload, upload.name)


def reconciling_items_frame(items: list[ReconcilingItem]) -> pd.DataFrame:
    if not items:
        return pd.DataFrame(
            [
                {
                    "category": "manual_adjustment_other",
                    "description": "",
                    "amount": 0.0,
                    "evidence_ref": "",
                }
            ]
        )
    return pd.DataFrame([item.model_dump(mode="json") for item in items])


def build_reconciling_items(records: pd.DataFrame) -> list[ReconcilingItem]:
    items: list[ReconcilingItem] = []
    for record in records.fillna("").to_dict(orient="records"):
        description = str(record.get("description", "")).strip()
        amount = Decimal(str(record.get("amount") or "0"))
        if not description and amount == 0:
            continue
        items.append(
            ReconcilingItem(
                category=record.get("category") or "manual_adjustment_other",
                description=description or "Manual reconciling item",
                amount=amount,
                evidence_ref=str(record.get("evidence_ref", "")).strip(),
            )
        )
    return items


def render_metric_grid(findings) -> None:
    first_row = st.columns(3)
    first_row[0].metric("VAT-declared supplies", money(findings.vat_declared_supplies))
    first_row[1].metric("Accounting revenue", money(findings.accounting_revenue))
    first_row[2].metric("Residual unexplained difference", money(findings.residual))

    second_row = st.columns(3)
    second_row[0].metric("Bridge status", findings.bridge_status)
    second_row[1].metric("Materiality", money(findings.materiality))
    second_row[2].metric("Total reconciling items", money(findings.total_reconciling_items))

    third_row = st.columns(2)
    third_row[0].metric("RCM context", money(findings.reverse_charge_context))
    third_row[1].metric("Pre-filing exception score", f"{findings.score.score} - {findings.score.label}")


def table_from_models(models: list) -> pd.DataFrame:
    return pd.DataFrame([model.model_dump(mode="json") for model in models])


st.set_page_config(
    page_title="UAE VAT-to-CT Bridge",
    layout="wide",
    initial_sidebar_state="collapsed",
)
st.markdown(
    """
    <style>
    .block-container { padding-top: 1.2rem; max-width: 1080px; }
    header[data-testid="stHeader"] { display: none; }
    #MainMenu { visibility: hidden; }
    footer { visibility: hidden; }
    section[data-testid="stSidebar"] { display: none; }
    button[data-testid="stBaseButton-headerNoPadding"] { display: none; }
    div[data-testid="stMetric"] {
        background: #ffffff;
        border: 1px solid #e3e7ec;
        border-radius: 8px;
        padding: 0.8rem 0.9rem;
    }
    div[data-testid="stMetricValue"] { font-size: 1.35rem; }
    .cs-small { color: #5d6978; font-size: 0.9rem; }
    .hero-copy {
        color: #3b4654;
        font-size: 1rem;
        line-height: 1.55;
        max-width: 980px;
    }
    .disclaimer-copy {
        color: #667085;
        font-size: 0.86rem;
        line-height: 1.45;
        max-width: 980px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("UAE VAT-to-CT Bridge")
st.caption("Arithmetic self-check for VAT-declared supplies and CT preparation revenue")
st.markdown(f'<div class="hero-copy">{SAFE_POSITIONING}</div>', unsafe_allow_html=True)
st.markdown(f'<div class="disclaimer-copy">{EXPORT_DISCLAIMER}</div>', unsafe_allow_html=True)

if (date.today() - RULES_VERIFIED_ON).days > 90:
    st.warning("Rules may be outdated. Please verify current UAE tax rules before relying on this self-check.")

if "inputs" not in st.session_state:
    st.session_state.inputs = None
if "working_inputs" not in st.session_state:
    st.session_state.working_inputs = None

demo_col, template_col = st.columns([1, 3])
with demo_col:
    if st.button("Load demo company", type="primary", use_container_width=True):
        st.session_state.inputs = load_demo_inputs()
        st.session_state.working_inputs = st.session_state.inputs
with template_col:
    with st.expander("Download input templates", expanded=False):
        template_cols = st.columns(3)
        for idx, template in enumerate(sorted(TEMPLATE_DIR.glob("*.csv"))):
            template_cols[idx % 3].download_button(
                label=template.name.replace("_", " "),
                data=template.read_bytes(),
                file_name=template.name,
                mime="text/csv",
                use_container_width=True,
            )

source_inputs = st.session_state.working_inputs or st.session_state.inputs
default_ct = source_inputs.ct_computation if source_inputs else None
default_recon = source_inputs.reconciling_items if source_inputs else []

input_tab, dashboard_tab, exports_tab = st.tabs(["Inputs", "Dashboard", "Exports"])

with input_tab:
    upload_col, ct_col = st.columns([1, 1])
    with upload_col:
        st.subheader("Upload files")
        vat_upload = st.file_uploader("VAT returns", type=["csv", "xlsx"], key="vat_upload")
        pl_upload = st.file_uploader("P&L summary", type=["csv", "xlsx"], key="pl_upload")
        recon_upload = st.file_uploader("Reconciling items", type=["csv", "xlsx"], key="recon_upload")
        company_name = st.text_input(
            "Company name",
            value=source_inputs.company_name if source_inputs else "Uploaded company",
        )
    with ct_col:
        st.subheader("CT computation")
        tax_start = st.date_input(
            "Tax period start",
            value=default_ct.tax_period_start if default_ct else date(2025, 1, 1),
        )
        tax_end = st.date_input(
            "Tax period end",
            value=default_ct.tax_period_end if default_ct else date(2025, 12, 31),
        )
        ct_revenue = st.number_input(
            "Accounting revenue used for CT",
            min_value=0.0,
            value=float(default_ct.accounting_revenue) if default_ct else 0.0,
            step=10000.0,
        )
        accounting_profit = st.number_input(
            "Accounting profit",
            value=float(default_ct.accounting_profit) if default_ct else 0.0,
            step=10000.0,
        )
        taxable_income = st.number_input(
            "Taxable income",
            value=float(default_ct.taxable_income) if default_ct else 0.0,
            step=10000.0,
        )
        entity_index = ["unknown", "mainland", "free_zone"].index(default_ct.entity_type) if default_ct else 0
        entity_type = st.selectbox("Entity type", ["unknown", "mainland", "free_zone"], index=entity_index)
        materiality_override = st.number_input("Materiality override, optional", min_value=0.0, value=0.0, step=1000.0)

    st.subheader("Reconciling items")
    recon_frame = reconciling_items_frame(default_recon)
    edited_recon = st.data_editor(
        recon_frame,
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "category": st.column_config.SelectboxColumn("category", options=RECONCILING_CATEGORIES, required=True),
            "description": st.column_config.TextColumn("description", width="large"),
            "amount": st.column_config.NumberColumn("amount", step=1000.0, format="%.2f"),
            "evidence_ref": st.column_config.TextColumn("evidence_ref", width="medium"),
        },
        key="recon_editor",
    )

    if st.button("Run bridge", type="primary", use_container_width=True):
        try:
            parsed_vat = parse_uploaded(vat_upload, parse_vat_returns)
            parsed_pl = parse_uploaded(pl_upload, parse_pl_summary)
            uploaded_recon = parse_uploaded(recon_upload, parse_reconciling_items)
            if parsed_vat is None and source_inputs:
                parsed_vat = source_inputs.vat_returns
            if parsed_pl is None and source_inputs:
                parsed_pl = source_inputs.pl_summary
            if parsed_vat is None or parsed_pl is None:
                st.warning("Load the demo company or upload VAT returns and a P&L summary to run the bridge.")
            else:
                reconciling_items = (
                    uploaded_recon if uploaded_recon is not None else build_reconciling_items(edited_recon)
                )
                st.session_state.inputs = BridgeInputs(
                    company_name=company_name,
                    vat_returns=parsed_vat,
                    pl_summary=parsed_pl,
                    ct_computation=CTComputation(
                        tax_period_start=tax_start,
                        tax_period_end=tax_end,
                        accounting_revenue=Decimal(str(ct_revenue)),
                        accounting_profit=Decimal(str(accounting_profit)),
                        taxable_income=Decimal(str(taxable_income)),
                        entity_type=entity_type,
                    ),
                    reconciling_items=reconciling_items,
                    materiality_override=Decimal(str(materiality_override)) if materiality_override else None,
                )
                st.session_state.working_inputs = st.session_state.inputs
                st.success("Bridge completed.")
        except Exception:
            st.error("Something went wrong. No data was retained.")

inputs = st.session_state.inputs
findings = run_checks(inputs) if inputs else None

with dashboard_tab:
    if not inputs or not findings:
        st.warning("Load the demo company or upload VAT returns and a P&L summary to run the bridge.")
    else:
        st.subheader("Results dashboard")
        render_metric_grid(findings)
        st.caption(findings.score.narrative)

        st.write("Top exception drivers")
        st.dataframe(table_from_models(findings.top_exception_drivers), use_container_width=True, hide_index=True)
        st.write("Checks")
        st.dataframe(table_from_models(findings.checks), use_container_width=True, hide_index=True)

        st.write("Bridge table")
        st.dataframe(table_from_models(findings.bridge_table), use_container_width=True, hide_index=True)
        st.write("Reconciling items")
        st.dataframe(table_from_models(inputs.reconciling_items), use_container_width=True, hide_index=True)

with exports_tab:
    if not inputs or not findings:
        st.warning("Load the demo company or upload VAT returns and a P&L summary to run the bridge.")
    else:
        excel_bytes = build_excel_working_paper(inputs, findings)
        pdf_bytes = build_pdf_report(inputs, findings)
        st.download_button(
            "Download Excel working paper",
            data=excel_bytes,
            file_name="uae_vat_ct_bridge_working_paper.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )
        st.download_button(
            "Download PDF bridge report",
            data=pdf_bytes,
            file_name="uae_vat_ct_bridge_report.pdf",
            mime="application/pdf",
            use_container_width=True,
        )

        st.write("PDF report preview")
        st.markdown(
            f"""
            **{findings.company_name}**

            Residual unexplained difference: **{money(findings.residual)}**

            Materiality: **{money(findings.materiality)}**

            Bridge status: **{findings.bridge_status_label}**

            Pre-filing exception score: **{findings.score.score} - {findings.score.label}**
            """
        )
        st.caption(findings.rules_stamp)
        st.caption(EXPORT_DISCLAIMER)
        st.write("Excel export preview")
        st.dataframe(
            pd.DataFrame(findings.report_data["summary"].items(), columns=["metric", "value"]),
            use_container_width=True,
            hide_index=True,
        )
        st.caption(
            "Workbook sheets: Summary, VAT Returns, P&L Summary, CT Computation, Reconciling Items, Checks, Methodology"
        )
