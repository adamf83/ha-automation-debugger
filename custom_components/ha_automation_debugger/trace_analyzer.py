"""Fetch and analyze Home Assistant automation traces for failure details."""
from __future__ import annotations

import logging
from datetime import datetime

from homeassistant.core import HomeAssistant

from .const import CONDITION_REASON_MAP

_LOGGER = logging.getLogger(__name__)

# DATA_TRACE is the hass.data key used by HA's trace component.
# Import it from HA if available; fall back to the well-known literal so the
# module can still be imported in unit-test environments without a full HA stack.
try:
    from homeassistant.components.trace import DATA_TRACE  # type: ignore[import]
except ImportError:  # pragma: no cover
    DATA_TRACE = "trace"


async def async_fetch_latest_failure(
    hass: HomeAssistant,
    entity_id: str,
    since: datetime,
) -> dict | None:
    """Return a failure dict for the most recent trace of *entity_id*, or None.

    Args:
        hass: The Home Assistant instance.
        entity_id: Automation entity ID (e.g. ``automation.evening_lights``).
        since: Only consider traces whose start timestamp is at or after this
            time (with a small tolerance to account for sub-second skew).

    Returns:
        A dict matching the failure data model, or ``None`` when the
        automation succeeded or no actionable trace was found.
    """
    try:
        return _analyze_trace(hass, entity_id, since)
    except Exception:
        _LOGGER.exception("Unexpected error analysing trace for %s", entity_id)
        return None


def _analyze_trace(
    hass: HomeAssistant,
    entity_id: str,
    since: datetime,
) -> dict | None:
    """Synchronous core of the trace analysis — easy to unit-test directly."""
    store = hass.data.get(DATA_TRACE)
    if store is None:
        _LOGGER.debug(
            "Trace store not available (is the 'trace' component loaded?)"
        )
        return None

    automation_store = store.get("automation") if hasattr(store, "get") else None
    if not automation_store:
        return None

    # Traces are keyed by the automation's object_id (no "automation." prefix)
    item_id = entity_id.removeprefix("automation.")
    trace_collection = automation_store.get(item_id)
    if not trace_collection:
        return None

    # Collection may be a dict (run_id → trace) or a sequence; normalise to list
    traces = (
        list(trace_collection.values())
        if hasattr(trace_collection, "values")
        else list(trace_collection)
    )
    if not traces:
        return None

    # Most-recent trace is last in insertion order
    trace_obj = traces[-1]
    trace_data = trace_obj.as_dict()

    if not _trace_is_recent(trace_data, since):
        return None

    state = trace_data.get("state")

    if state == "finished":
        return None  # automation completed successfully
    if state not in ("stopped", "error"):
        return None  # still running or unknown state

    trigger_desc = _extract_trigger_description(trace_data)
    run_id = trace_data.get("run_id", "")

    if state == "error":
        status = "aborted"
        reason = trace_data.get("error") or "Automation raised an error"
    else:
        # state == "stopped": a condition blocked execution
        status = "failed"
        reason = _extract_condition_reason(trace_data)

    return {
        "run_id": run_id,
        "automation": entity_id,
        "timestamp": since.isoformat(),
        "status": status,
        "reason": reason,
        "trigger": trigger_desc,
    }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _trace_is_recent(trace_data: dict, since: datetime) -> bool:
    """Return True if the trace started at or after *since* (ignoring microseconds)."""
    start_str: str | None = trace_data.get("timestamp", {}).get("start")
    if not start_str:
        return True  # no timestamp → assume valid

    try:
        from homeassistant.util import dt as dt_util  # type: ignore[import]

        start_time = dt_util.parse_datetime(start_str)
    except ImportError:
        # Fallback for test environments without homeassistant.util
        from datetime import datetime as _dt, timezone as _tz

        start_time = _dt.fromisoformat(start_str)
        if start_time.tzinfo is None:
            start_time = start_time.replace(tzinfo=_tz.utc)

    if start_time is None:
        return True

    # Truncate microseconds to allow for sub-second timing skew
    return start_time >= since.replace(microsecond=0)


def _extract_trigger_description(trace_data: dict) -> str:
    """Return a human-readable description of what triggered the automation."""
    trace_nodes: dict = trace_data.get("trace", {})

    for key in sorted(trace_nodes.keys()):
        if key.startswith("trigger:"):
            nodes = trace_nodes[key]
            if nodes:
                result: dict = nodes[0].get("result", {})
                desc = result.get("description") or result.get("source")
                if desc:
                    return str(desc)

    # Fall back to the top-level "trigger" field (a plain string in many traces)
    top = trace_data.get("trigger")
    return str(top) if top else "Unknown trigger"


def _extract_condition_reason(trace_data: dict) -> str:
    """Find the first failed condition node and return a human-readable reason."""
    trace_nodes: dict = trace_data.get("trace", {})
    conditions_config: list = trace_data.get("config", {}).get("condition", [])

    # Sort so we process conditions in their execution order
    condition_keys = sorted(
        (k for k in trace_nodes if "condition" in k),
        key=lambda k: (k.count("/"), k),
    )

    for key in condition_keys:
        nodes = trace_nodes[key]
        if not nodes:
            continue
        node: dict = nodes[0]
        result: dict = node.get("result", {})

        if result.get("result") is not False:
            continue  # this condition passed

        # Prefer a ready-made description from HA's own trace output
        description: str | None = result.get("description")
        if description:
            return str(description)

        # Fall back to mapping from the automation config
        condition_type = _get_condition_type(key, conditions_config)
        base = CONDITION_REASON_MAP.get(condition_type, "Condition not met")

        entities: list = result.get("entities") or []
        if entities:
            return f"{base}: {', '.join(str(e) for e in entities)}"

        return base

    return "Condition not met (no details available)"


def _get_condition_type(trace_key: str, conditions_config: list) -> str:
    """Try to derive the condition type from its trace key and automation config."""
    # Simple case: "condition:0" → index 0 in conditions_config
    parts = trace_key.split(":")
    if len(parts) == 2:
        try:
            idx = int(parts[1])
            if idx < len(conditions_config):
                return conditions_config[idx].get("condition", "unknown")
        except (ValueError, IndexError):
            pass
    return "unknown"
