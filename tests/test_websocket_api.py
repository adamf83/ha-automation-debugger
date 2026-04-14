"""Tests for the WebSocket API command."""
from __future__ import annotations

from collections import deque
from unittest.mock import MagicMock

import pytest

from custom_components.ha_automation_debugger.websocket_api import ws_get_failures
from custom_components.ha_automation_debugger.coordinator import (
    AutomationDebuggerCoordinator,
)
from custom_components.ha_automation_debugger.const import DOMAIN

_FAILURE = {
    "automation": "automation.evening_lights",
    "timestamp": "2026-04-14T18:42:00+00:00",
    "status": "failed",
    "reason": "Sun condition not met",
    "trigger": "time (18:42)",
}


@pytest.fixture
def mock_connection():
    return MagicMock()


def test_ws_get_failures_empty(mock_hass, mock_connection):
    """Returns count=0 and empty list when no coordinators have failures."""
    mock_hass.data = {DOMAIN: {}}
    msg = {"id": 1}

    ws_get_failures(mock_hass, mock_connection, msg)

    mock_connection.send_result.assert_called_once_with(1, {"count": 0, "failures": []})


def test_ws_get_failures_with_data(mock_hass, mock_connection):
    """Returns all failures from an active coordinator."""
    coordinator = AutomationDebuggerCoordinator(mock_hass)
    coordinator.failures.append(dict(_FAILURE))
    mock_hass.data = {DOMAIN: {"entry-1": coordinator}}
    msg = {"id": 2}

    ws_get_failures(mock_hass, mock_connection, msg)

    mock_connection.send_result.assert_called_once()
    _call_args = mock_connection.send_result.call_args[0]
    assert _call_args[0] == 2
    assert _call_args[1]["count"] == 1
    assert _call_args[1]["failures"][0]["automation"] == "automation.evening_lights"


def test_ws_get_failures_ignores_non_coordinator_values(mock_hass, mock_connection):
    """Non-coordinator values in hass.data[DOMAIN] are skipped gracefully."""
    coordinator = AutomationDebuggerCoordinator(mock_hass)
    coordinator.failures.append(dict(_FAILURE))
    mock_hass.data = {DOMAIN: {"entry-1": coordinator, "ws_registered": True}}
    msg = {"id": 3}

    ws_get_failures(mock_hass, mock_connection, msg)

    _call_args = mock_connection.send_result.call_args[0]
    assert _call_args[1]["count"] == 1


def test_ws_get_failures_aggregates_multiple_coordinators(mock_hass, mock_connection):
    """Failures from multiple coordinators are combined in the response."""
    c1 = AutomationDebuggerCoordinator(mock_hass)
    c1.failures.append(dict(_FAILURE))
    c2 = AutomationDebuggerCoordinator(mock_hass)
    c2.failures.append(dict(_FAILURE, automation="automation.other"))
    mock_hass.data = {DOMAIN: {"entry-1": c1, "entry-2": c2}}
    msg = {"id": 4}

    ws_get_failures(mock_hass, mock_connection, msg)

    _call_args = mock_connection.send_result.call_args[0]
    assert _call_args[1]["count"] == 2
