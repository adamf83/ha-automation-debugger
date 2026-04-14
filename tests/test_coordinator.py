"""Unit tests for coordinator.py."""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.ha_automation_debugger.coordinator import (
    AutomationDebuggerCoordinator,
)
from custom_components.ha_automation_debugger.const import (
    EVENT_AUTOMATION_TRIGGERED,
    MAX_FAILURES,
)

TRIGGER_TIME = datetime(2026, 4, 14, 18, 41, 59, tzinfo=timezone.utc)
ENTITY_ID = "automation.evening_lights"

_FAILURE = {
    "run_id": "run-abc",
    "automation": ENTITY_ID,
    "timestamp": "2026-04-14T18:42:00+00:00",
    "status": "failed",
    "reason": "Sun condition not met",
    "trigger": "time (18:42)",
}


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_async_setup_registers_event_listener(mock_hass):
    coordinator = AutomationDebuggerCoordinator(mock_hass)
    await coordinator.async_setup()

    mock_hass.bus.async_listen.assert_called_once_with(
        EVENT_AUTOMATION_TRIGGERED,
        coordinator._handle_automation_triggered,
    )


@pytest.mark.asyncio
async def test_async_teardown_calls_unsub(mock_hass):
    unsub = MagicMock()
    mock_hass.bus.async_listen.return_value = unsub

    coordinator = AutomationDebuggerCoordinator(mock_hass)
    await coordinator.async_setup()
    coordinator.async_teardown()

    unsub.assert_called_once()
    assert coordinator._event_unsub is None


@pytest.mark.asyncio
async def test_teardown_is_idempotent(mock_hass):
    """Calling teardown twice does not raise."""
    coordinator = AutomationDebuggerCoordinator(mock_hass)
    await coordinator.async_setup()
    coordinator.async_teardown()
    coordinator.async_teardown()  # should not raise


# ---------------------------------------------------------------------------
# Listener management
# ---------------------------------------------------------------------------


def test_add_listener_returns_remover(mock_hass):
    coordinator = AutomationDebuggerCoordinator(mock_hass)
    cb = MagicMock()

    remove = coordinator.async_add_listener(cb)
    assert cb in coordinator._update_callbacks

    remove()
    assert cb not in coordinator._update_callbacks


def test_notify_listeners_calls_all_callbacks(mock_hass):
    coordinator = AutomationDebuggerCoordinator(mock_hass)
    cb1, cb2 = MagicMock(), MagicMock()
    coordinator.async_add_listener(cb1)
    coordinator.async_add_listener(cb2)

    coordinator._notify_listeners()

    cb1.assert_called_once()
    cb2.assert_called_once()


# ---------------------------------------------------------------------------
# Failure buffer
# ---------------------------------------------------------------------------


def test_failures_deque_respects_max_size(mock_hass):
    coordinator = AutomationDebuggerCoordinator(mock_hass)

    for i in range(MAX_FAILURES + 5):
        coordinator.failures.append({"automation": f"automation.test_{i}"})

    assert len(coordinator.failures) == MAX_FAILURES
    assert coordinator.failures[-1]["automation"] == f"automation.test_{MAX_FAILURES + 4}"


@pytest.mark.asyncio
async def test_successful_run_not_recorded(mock_hass):
    """None from the analyser → nothing added to failures."""
    coordinator = AutomationDebuggerCoordinator(mock_hass)

    with patch(
        "custom_components.ha_automation_debugger.coordinator.async_fetch_latest_failure",
        new=AsyncMock(return_value=None),
    ):
        await coordinator._check_for_failure(ENTITY_ID, TRIGGER_TIME)

    assert len(coordinator.failures) == 0


@pytest.mark.asyncio
async def test_failure_is_recorded_and_listeners_notified(mock_hass):
    coordinator = AutomationDebuggerCoordinator(mock_hass)
    cb = MagicMock()
    coordinator.async_add_listener(cb)

    with patch(
        "custom_components.ha_automation_debugger.coordinator.async_fetch_latest_failure",
        new=AsyncMock(return_value=dict(_FAILURE)),
    ):
        await coordinator._check_for_failure(ENTITY_ID, TRIGGER_TIME)

    assert len(coordinator.failures) == 1
    assert coordinator.failures[0]["reason"] == "Sun condition not met"
    cb.assert_called_once()


@pytest.mark.asyncio
async def test_run_id_stripped_from_stored_failure(mock_hass):
    """run_id is used for deduplication but not stored in the public failure dict."""
    coordinator = AutomationDebuggerCoordinator(mock_hass)

    with patch(
        "custom_components.ha_automation_debugger.coordinator.async_fetch_latest_failure",
        new=AsyncMock(return_value=dict(_FAILURE)),
    ):
        await coordinator._check_for_failure(ENTITY_ID, TRIGGER_TIME)

    assert "run_id" not in coordinator.failures[0]


@pytest.mark.asyncio
async def test_duplicate_run_ids_not_recorded(mock_hass):
    coordinator = AutomationDebuggerCoordinator(mock_hass)

    with patch(
        "custom_components.ha_automation_debugger.coordinator.async_fetch_latest_failure",
        new=AsyncMock(side_effect=lambda *a, **kw: dict(_FAILURE)),
    ):
        await coordinator._check_for_failure(ENTITY_ID, TRIGGER_TIME)
        await coordinator._check_for_failure(ENTITY_ID, TRIGGER_TIME)

    assert len(coordinator.failures) == 1


@pytest.mark.asyncio
async def test_empty_run_id_allows_multiple_failures(mock_hass):
    """When the trace has no run_id, every failure is recorded (no dedup)."""
    failure_no_id = dict(_FAILURE)
    failure_no_id["run_id"] = ""

    coordinator = AutomationDebuggerCoordinator(mock_hass)

    with patch(
        "custom_components.ha_automation_debugger.coordinator.async_fetch_latest_failure",
        new=AsyncMock(return_value=failure_no_id),
    ):
        await coordinator._check_for_failure(ENTITY_ID, TRIGGER_TIME)
        await coordinator._check_for_failure(ENTITY_ID, TRIGGER_TIME)

    assert len(coordinator.failures) == 2
