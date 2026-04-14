"""HA Automation Debugger — surfaces failed automation runs as a sensor.

Preferred setup: add via the Home Assistant UI (Settings → Integrations).

Legacy YAML setup is also supported:

    ha_automation_debugger:

No further configuration is required in either case.
"""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import discovery
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN
from .coordinator import AutomationDebuggerCoordinator
from . import websocket_api as ws_api

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR]

_WS_API_REGISTERED_KEY = f"{DOMAIN}_ws_api_registered"


def _register_websocket_api_once(hass: HomeAssistant) -> None:
    """Register WebSocket commands exactly once, regardless of setup path."""
    if not hass.data.get(_WS_API_REGISTERED_KEY):
        ws_api.async_setup(hass)
        hass.data[_WS_API_REGISTERED_KEY] = True


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the integration from configuration.yaml (legacy YAML path)."""
    coordinator = AutomationDebuggerCoordinator(hass)
    await coordinator.async_setup()
    hass.data.setdefault(DOMAIN, {})["yaml"] = coordinator

    # Load the sensor platform via HA's discovery mechanism
    hass.async_create_task(
        discovery.async_load_platform(hass, Platform.SENSOR, DOMAIN, {}, config)
    )

    async def _handle_reload(call: ServiceCall) -> None:
        """Tear down and restart the coordinator (useful after config changes)."""
        coordinator.async_teardown()
        new_coordinator = AutomationDebuggerCoordinator(hass)
        await new_coordinator.async_setup()
        hass.data[DOMAIN]["yaml"] = new_coordinator
        _LOGGER.info("HA Automation Debugger reloaded")

    hass.services.async_register(DOMAIN, "reload", _handle_reload)
    _register_websocket_api_once(hass)
    _LOGGER.info("HA Automation Debugger set up successfully (YAML)")
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up HA Automation Debugger from a config entry (UI setup)."""
    coordinator = AutomationDebuggerCoordinator(hass)
    await coordinator.async_setup()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    _register_websocket_api_once(hass)
    _LOGGER.info("HA Automation Debugger set up successfully (UI)")
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        coordinator: AutomationDebuggerCoordinator = hass.data[DOMAIN].pop(
            entry.entry_id
        )
        coordinator.async_teardown()
    return unload_ok
