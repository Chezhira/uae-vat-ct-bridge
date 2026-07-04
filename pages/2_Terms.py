import streamlit as st

from engine.constants import EXPORT_DISCLAIMER

st.title("Terms")
st.write(
    "This public portfolio tool is provided for demonstration and internal working-paper preparation only. "
    "It does not prepare, submit, validate, or approve VAT or Corporate Tax filings."
)
st.info(EXPORT_DISCLAIMER)
