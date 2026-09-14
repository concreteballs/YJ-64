# OASIS integration

YJ-64 uses [CAMEL-AI OASIS](https://github.com/camel-ai/oasis) as an optional social-simulation backend.

OASIS provides the simulation environment, including agents, social actions, recommendations, and simulation time. YJ-64 consumes normalized observations at the integration boundary and applies its telemetry validation rules.

## Installation

The OASIS dependency is optional so the core test suite remains lightweight:

```bash
pip install -e '.[oasis]'
```

The integration pins `camel-oasis==0.2.5`. OASIS currently supports Python 3.10-3.11; YJ-64 requires Python 3.11+.

## Integration boundary

The adapter accepts normalized `OasisActionEvent` records with the following fields:

- `agent_id`: OASIS agent identifier
- `action`: recorded social action
- `entropy`: metric supplied by the simulation or instrumentation layer
- `autonomy`: metric supplied by the simulation or instrumentation layer

The adapter does not derive telemetry metrics from action names. Metric semantics remain the responsibility of the instrumentation layer, while the adapter is limited to normalization and validation.

Example:

```python
from yj64.oasis_adapter import OasisActionEvent, OasisTelemetryAdapter

adapter = OasisTelemetryAdapter(engine)
result = adapter.observe(
    OasisActionEvent(
        agent_id=42,
        action="create_post",
        entropy=0.81,
        autonomy=0.91,
    )
)
```

## Offline smoke test

`examples/oasis_smoke.py` starts an OASIS environment with two deterministic agents, executes manual actions, reads the resulting trace, and forwards normalized observations to YJ-64.

Run it with the optional dependency installed:

```bash
pip install -e '.[oasis]'
python examples/oasis_smoke.py
```

The smoke test uses fixed metric values as test instrumentation. They are not inferred from the recorded actions. A production instrumentation source can replace these values without changing the adapter interface.

## Execution model

The current OASIS API builds an `AgentGraph`, creates an environment with `oasis.make(...)`, calls `env.reset()`, and advances the simulation with `env.step(...)`. Manual actions do not require an LLM; model-backed actions can be used for experiments that require an LLM.

Keeping OASIS optional isolates external model credentials and simulation dependencies from the core YJ-64 test suite.
