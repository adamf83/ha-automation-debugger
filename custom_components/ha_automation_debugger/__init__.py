"""HA Automation Debugger — surfaces failed automation runs as a sensor.

Add to configuration.yaml:

    ha_automation_debugger:

No further configuration is required.
"""
from __future__ import annotations

import logging

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import discovery
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN
from .coordinator import AutomationDebuggerCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the integration from configuration.yaml."""
    coordinator = AutomationDebuggerCoordinator(hass)
    await coordinator.async_setup()
    hass.data[DOMAIN] = coordinator

    # Load the sensor platform via HA's discovery mechanism
    hass.async_create_task(
        discovery.async_load_platform(hass, Platform.SENSOR, DOMAIN, {}, config)
    )

    async def _handle_reload(call: ServiceCall) -> None:
        """Tear down and restart the coordinator (useful after config changes)."""
        coordinator.async_teardown()
        new_coordinator = AutomationDebuggerCoordinator(hass)
        await new_coordinator.async_setup()
        hass.data[DOMAIN] = new_coordinator
        _LOGGER.info("HA Automation Debugger reloaded")

    hass.services.async_register(DOMAIN, "reload", _handle_reload)
    _LOGGER.info("HA Automation Debugger set up successfully")
    return True
