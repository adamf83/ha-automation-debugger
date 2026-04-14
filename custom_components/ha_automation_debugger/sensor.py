"""Sensor platform for HA Automation Debugger."""
from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback

from .const import DOMAIN
from .coordinator import AutomationDebuggerCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities,
) -> None:
    """Set up the Automation Debugger sensor from a config entry (UI setup)."""
    coordinator: AutomationDebuggerCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([AutomationDebuggerSensor(coordinator)])


async def async_setup_platform(
    hass: HomeAssistant,
    config: dict,
    async_add_entities,
    discovery_info=None,
) -> None:
    """Set up the Automation Debugger sensor from a platform discovery (YAML setup)."""
    coordinator: AutomationDebuggerCoordinator = hass.data[DOMAIN]["yaml"]
    async_add_entities([AutomationDebuggerSensor(coordinator)])


class AutomationDebuggerSensor(SensorEntity):
    """Sensor that surfaces automation failures count and details.

    State: integer count of currently buffered failures.
    Attributes:
        failures: list of failure dicts (most recent last), each containing:
            automation, timestamp, status, reason, trigger.
    """

    _attr_name = "Automation Debugger Failures"
    _attr_unique_id = f"{DOMAIN}_failures"
    _attr_icon = "mdi:bug"
    _attr_native_unit_of_measurement = "failures"

    def __init__(self, coordinator: AutomationDebuggerCoordinator) -> None:
        self._coordinator = coordinator
        self._remove_listener: callable | None = None

    async def async_added_to_hass(self) -> None:
        """Subscribe to coordinator updates when added to HA."""
        self._remove_listener = self._coordinator.async_add_listener(
            self.async_write_ha_state
        )

    async def async_will_remove_from_hass(self) -> None:
        """Unsubscribe when removed from HA."""
        if self._remove_listener is not None:
            self._remove_listener()

    @property
    def native_value(self) -> int:
        """Return the number of buffered failures."""
        return len(self._coordinator.failures)

    @property
    def extra_state_attributes(self) -> dict:
        """Expose the full failure list as attributes."""
        return {"failures": list(self._coordinator.failures)}
