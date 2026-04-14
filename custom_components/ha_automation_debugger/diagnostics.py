"""Diagnostics support for HA Automation Debugger.

Provides the data shown when the user clicks "Download Diagnostics" on the
integration card in Settings → Devices & Services.
"""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import AutomationDebuggerCoordinator


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict:
    """Return a snapshot of all buffered failures for this config entry."""
    coordinator: AutomationDebuggerCoordinator = hass.data[DOMAIN][entry.entry_id]
    return {
        "failures_count": len(coordinator.failures),
        "failures": list(coordinator.failures),
    }
