from datetime import date

from engine.checks import run_checks


def test_score_uses_prefiling_exception_label(demo_inputs):
    findings = run_checks(demo_inputs, today=date(2026, 7, 4))
    assert findings.score.label == "Medium exception load"
    assert "not a prediction of FTA action" in findings.score.narrative
