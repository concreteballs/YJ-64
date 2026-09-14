# OASIS integration

YJ-64 uses [CAMEL-AI OASIS](https://github.com/camel-ai/oasis) as the first social-simulation host candidate.

OASIS provides the social environment: agents, posts, comments, follows, reposts, recommendations, and simulation time. YJ-64 remains an observation and diagnostic layer.

## Installation

The simulator is optional so the core YJ-64 test suite stays lightweight:

```bash
pip install -e '.[oasis]'
```

The optional dependency is pinned to `camel-oasis==0.2.5` and requires Python 3.10-3.11 in the current OASIS package. YJ-64 itself requires Python 3.11+.

## Integration boundary

OASIS emits social actions. The adapter accepts normalized `OasisActionEvent` records:

- `agent_id`: OASIS agent identifier
- `action`: social action such as `create_post`, `like_post`, or `follow`
- `entropy`: metric supplied by the simulation/instrumentation layer
- `autonomy`: metric supplied by the simulation/instrumentation layer

The adapter intentionally does **not** infer psychological or behavioral metrics from an action name. This keeps the diagnostic layer measurable and prevents the bridge from silently changing the meaning of YJ-64 thresholds.

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

## Offline OASIS smoke runner

`examples/oasis_smoke.py` runs an actual OASIS environment with two deterministic agents using `ManualAction`. After the simulation closes, it reads OASIS's `trace` table, converts the recorded actions into YJ-64 observations, and runs the diagnostic engine.

Run it with the optional dependency installed:

```bash
pip install -e '.[oasis]'
python examples/oasis_smoke.py
```

The smoke runner uses explicit fixed metric observations for the two agents. Those values are test instrumentation, not metrics inferred from `create_post`. A later instrumentation layer can replace them with measured simulation data without changing the adapter boundary.

## OASIS execution model

OASIS's current API creates an `AgentGraph`, constructs an environment with `oasis.make(...)`, calls `env.reset()`, and advances the simulation with `env.step(...)`. Manual actions can be used without an LLM, while `LLMAction` can be used when a model-backed experiment is desired.

The current integration therefore has a real offline execution path while keeping LLM credentials and external social networks out of the base YJ-64 test suite. The next step is to replace the fixed smoke-test metrics with a dedicated instrumentation source.
