# YJ-64

Modular telemetry ingestion and diagnostic verification engine.

## Structure

- `src/yj64/models.py` — typed telemetry and diagnostic data models.
- `src/yj64/config.py` — validated JSON configuration loader.
- `src/yj64/telemetry.py` — telemetry ingestion and threshold evaluation.
- `src/yj64/state.py` — explicit engine lifecycle state machine.
- `src/yj64/diagnostics.py` — configurable diagnostic query generation.
- `src/yj64/agent_core.py` — asynchronous orchestration layer.
- `src/yj64/oasis_adapter.py` — OASIS integration boundary.
- `config/telemetry.json` — thresholds and execution parameters.
- `tests/` — automated tests.
- `.github/workflows/ci.yml` — continuous integration verification.

## Development

Install the project and test dependencies:

```bash
python -m pip install pytest
python -m pip install .
```

Run the test suite and local verification cycle:

```bash
python -m pytest -q
python main.py
```

The ingestion boundary rejects malformed telemetry without terminating the validation cycle. Configuration is externalized and validated before engine initialization.

## Optional OASIS integration

Install the optional integration dependency with:

```bash
python -m pip install -e '.[oasis]'
```

The OASIS adapter consumes normalized simulation events and forwards telemetry metrics to the validation engine. Metric values are supplied by the instrumentation layer and are not inferred from action names.
