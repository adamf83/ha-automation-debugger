"""Constants for the HA Automation Debugger integration."""

DOMAIN = "ha_automation_debugger"
MAX_FAILURES = 20
TRACE_FETCH_DELAY = 2.0  # seconds to wait after trigger before fetching the trace

EVENT_AUTOMATION_TRIGGERED = "automation_triggered"

# Human-readable reason templates keyed by HA condition type
CONDITION_REASON_MAP: dict[str, str] = {
    "sun": "Sun condition not met",
    "state": "State condition not met",
    "template": "Template condition evaluated to false",
    "numeric_state": "Numeric state condition not met",
    "time": "Time condition not met",
    "zone": "Zone condition not met",
    "device": "Device condition not met",
    "and": "Combined (AND) condition not met",
    "or": "Combined (OR) condition not met",
    "not": "Negated condition not met",
}
