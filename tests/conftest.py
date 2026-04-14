"""Shared pytest fixtures for HA Automation Debugger tests."""
from __future__ import annotations

import sys
from unittest.mock import MagicMock

import pytest

# ---------------------------------------------------------------------------
# Minimal stubs for the HA modules we depend on, so unit tests run without a
# real Home Assistant installation.
# ---------------------------------------------------------------------------

def _stub_ha_modules() -> None:
    """Insert lightweight stub modules into sys.modules."""
    stubs = {
        "homeassistant": MagicMock(),
        "homeassistant.core": MagicMock(),
        "homeassistant.const": MagicMock(ATTR_ENTITY_ID="entity_id"),
        "homeassistant.components": MagicMock(),
        "homeassistant.components.sensor": MagicMock(),
        "homeassistant.components.trace": MagicMock(DATA_TRACE="trace"),
        "homeassistant.helpers": MagicMock(),
        "homeassistant.helpers.event": MagicMock(),
        "homeassistant.util": MagicMock(),
        "homeassistant.util.dt": MagicMock(),
    }
    for name, stub in stubs.items():
        sys.modules.setdefault(name, stub)


_stub_ha_modules()


@pytest.fixture
def mock_hass():
    """Return a minimal mock HomeAssistant instance."""
    hass = MagicMock()
    hass.data = {}
    hass.bus = MagicMock()
    hass.bus.async_listen = MagicMock(return_value=MagicMock())
    hass.async_create_task = MagicMock()
    return hass


# ---------------------------------------------------------------------------
# Reusable trace-data fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_trace_stopped():
    """Trace where a sun condition blocked execution."""
    return {
        "run_id": "abc-123",
        "state": "stopped",
        "timestamp": {
            "start": "2026-04-14T18:42:00+00:00",
            "finish": "2026-04-14T18:42:00.050000+00:00",
        },
        "trigger": "time",
        "config": {
            "condition": [{"condition": "sun", "after": "sunset"}]
        },
        "trace": {
            "trigger:0": [
                {"result": {"description": "time (18:42)"}}
            ],
            "condition:0": [
                {"result": {"result": False}}
            ],
        },
        "error": None,
    }


@pytest.fixture
def sample_trace_stopped_with_description():
    """Trace where the failed condition includes its own description."""
    return {
        "run_id": "abc-456",
        "state": "stopped",
        "timestamp": {
            "start": "2026-04-14T18:42:00+00:00",
            "finish": "2026-04-14T18:42:00.050000+00:00",
        },
        "trigger": "state",
        "config": {"condition": [{"condition": "state"}]},
        "trace": {
            "trigger:0": [
                {"result": {"description": "state change (cover.garage)"}}
            ],
            "condition:0": [
                {
                    "result": {
                        "result": False,
                        "description": "State of cover.garage is open, expected closed",
                    }
                }
            ],
        },
        "error": None,
    }


@pytest.fixture
def sample_trace_error():
    """Trace that ended with an unhandled exception."""
    return {
        "run_id": "def-456",
        "state": "error",
        "timestamp": {
            "start": "2026-04-14T18:42:00+00:00",
            "finish": "2026-04-14T18:42:00.100000+00:00",
        },
        "trigger": "state",
        "config": {},
        "trace": {
            "trigger:0": [
                {"result": {"description": "state change (sensor.motion)"}}
            ],
        },
        "error": "Service not found: light.turn_on",
    }


@pytest.fixture
def sample_trace_finished():
    """Trace that completed successfully."""
    return {
        "run_id": "ghi-789",
        "state": "finished",
        "timestamp": {
            "start": "2026-04-14T18:42:00+00:00",
            "finish": "2026-04-14T18:42:01+00:00",
        },
        "trigger": "state",
        "config": {},
        "trace": {
            "trigger:0": [
                {"result": {"description": "state change (binary_sensor.motion)"}}
            ],
        },
        "error": None,
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_trace_obj(data: dict) -> MagicMock:
    """Return a mock trace object whose ``as_dict()`` returns *data*."""
    obj = MagicMock()
    obj.as_dict.return_value = data
    obj.run_id = data.get("run_id", "")
    return obj


def build_trace_store(entity_id: str, trace_data: dict) -> dict:
    """Build a ``hass.data["trace"]``-shaped dict with a single trace entry."""
    item_id = entity_id.removeprefix("automation.")
    trace_obj = make_trace_obj(trace_data)
    return {"automation": {item_id: {trace_data["run_id"]: trace_obj}}}
