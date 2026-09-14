# YJ-64

Modular telemetry ingestion and diagnostic verification engine.

## Structure

- `src/yj64/models.py` — typed telemetry and diagnostic data models.
- `src/yj64/config.py` — validated JSON configuration loader.
- `src/yj64/telemetry.py` — resilient packet ingestion and threshold evaluation.
- `src/yj64/state.py` — explicit diagnostic state machine.
- `src/yj64/diagnostics.py` — configurable diagnostic query generation.
- `src/yj64/agent_core.py` — asynchronous orchestration layer.
- `config/telemetry.json` — thresholds, execution parameters, and diagnostic payloads.
- `tests/` — unit and integration-oriented tests.
- `.github/workflows/ci.yml` — isolated CI verification cycle.

## Local verification

```bash
python -m pip install pytest
python -m pip install .
python -m pytest -q
python main.py
```

Malformed packets are rejected at the ingestion boundary and do not terminate a validation cycle. Configuration is externalized and validated before the engine starts.

<!-- CI runner probe: force a push-triggered verification without changing runtime code. -->
