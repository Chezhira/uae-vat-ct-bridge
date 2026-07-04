from __future__ import annotations

import json
from pathlib import Path

import pytest

from engine.ingest import parse_pl_summary, parse_reconciling_items, parse_vat_returns
from engine.models import BridgeInputs, CTComputation

ROOT = Path(__file__).resolve().parents[1]
DEMO_DIR = ROOT / "data" / "demo_dataset"


@pytest.fixture
def demo_inputs() -> BridgeInputs:
    ct = CTComputation.model_validate(json.loads((DEMO_DIR / "ct_computation_demo.json").read_text()))
    return BridgeInputs(
        company_name="Falcon Trading DMCC, demo only",
        vat_returns=parse_vat_returns(DEMO_DIR / "vat_returns_demo.csv"),
        pl_summary=parse_pl_summary(DEMO_DIR / "pl_summary_demo.csv"),
        ct_computation=ct,
        reconciling_items=parse_reconciling_items(DEMO_DIR / "reconciling_items_demo.csv"),
    )
