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

## OASIS execution model

The current OASIS examples create a `Platform`, generate an `AgentGraph`, and repeatedly call `perform_action_by_llm()` for active agents. That gives us a clean future hook: normalize each completed action into an `OasisActionEvent`, then pass it to YJ-64 without changing the protected YJ-64 core modules.

The first integration milestone is therefore an **offline/simulation-only telemetry bridge**. It does not connect to real social networks or automate interaction with real users.
