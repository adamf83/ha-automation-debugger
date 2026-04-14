"""Tests for the diagnostics platform."""
from __future__ import annotations

from collections import deque
from unittest.mock import MagicMock

import pytest

from custom_components.ha_automation_debugger.diagnostics import (
    async_get_config_entry_diagnostics,
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
def mock_entry():
    entry = MagicMock()
    entry.entry_id = "test-entry-id"
    return entry


@pytest.mark.asyncio
async def test_diagnostics_empty(mock_hass, mock_entry):
    """Diagnostics returns zero count and empty list when no failures recorded."""
    coordinator = MagicMock()
    coordinator.failures = deque(maxlen=20)
    mock_hass.data = {DOMAIN: {mock_entry.entry_id: coordinator}}

    result = await async_get_config_entry_diagnostics(mock_hass, mock_entry)

    assert result["failures_count"] == 0
    assert result["failures"] == []


@pytest.mark.asyncio
async def test_diagnostics_with_failures(mock_hass, mock_entry):
    """Diagnostics includes all buffered failures."""
    coordinator = MagicMock()
    coordinator.failures = deque([dict(_FAILURE), dict(_FAILURE, automation="automation.other")], maxlen=20)
    mock_hass.data = {DOMAIN: {mock_entry.entry_id: coordinator}}

    result = await async_get_config_entry_diagnostics(mock_hass, mock_entry)

    assert result["failures_count"] == 2
    assert result["failures"][0]["automation"] == "automation.evening_lights"
    assert result["failures"][1]["automation"] == "automation.other"


@pytest.mark.asyncio
async def test_diagnostics_returns_list_not_deque(mock_hass, mock_entry):
    """The failures value must be a plain list (JSON-serialisable)."""
    coordinator = MagicMock()
    coordinator.failures = deque([dict(_FAILURE)], maxlen=20)
    mock_hass.data = {DOMAIN: {mock_entry.entry_id: coordinator}}

    result = await async_get_config_entry_diagnostics(mock_hass, mock_entry)

    assert isinstance(result["failures"], list)
