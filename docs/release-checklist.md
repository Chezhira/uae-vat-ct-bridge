# Release Checklist

Do not tag `v0.1.0` until all of the following are true:

- CI is green.
- Engine coverage is at least 80 percent.
- `python -m engine.demo_run` passes.
- The golden-file test passes.
- README screenshots render cleanly on GitHub.
- Excel export works from the Streamlit UI.
- PDF export works from the Streamlit UI.
- The Streamlit app runs locally.
- The deployed app uses synthetic demo data.
- Disclaimers and independence wording are visible.
- No uploaded data is written to disk except active-session export generation.

Suggested pre-tag commands:

```powershell
python -m ruff check --no-cache .
python -m ruff format --check --no-cache .
python -m pytest
python -m pytest --cov=engine --cov-report=term-missing
python -m engine.demo_run
```
