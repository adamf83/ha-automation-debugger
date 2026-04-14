"""WebSocket API for HA Automation Debugger.

Registers the ``ha_automation_debugger/get_failures`` command so callers can
retrieve the buffered failure list without a Lovelace card.

Usage from the HA Developer Tools → Template console (or any WS client):

    {
      "type": "ha_automation_debugger/get_failures"
    }

Response:

    {
      "count": 3,
      "failures": [
        {
          "automation": "automation.my_light",
          "timestamp": "2026-04-14T18:00:00+00:00",
          "status": "failed",
          "reason": "State condition not met",
          "trigger": "State changed"
        },
        ...
      ]
    }
"""
from __future__ import annotations

import voluptuous as vol
from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback

from .const import DOMAIN
from .coordinator import AutomationDebuggerCoordinator


def async_setup(hass: HomeAssistant) -> None:
    """Register WebSocket API commands with HA."""
    websocket_api.async_register_command(hass, ws_get_failures)


@websocket_api.websocket_command(
    {vol.Required("type"): "ha_automation_debugger/get_failures"}
)
@callback
def ws_get_failures(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict,
) -> None:
    """Return all buffered automation failures across active coordinators."""
    all_failures: list[dict] = []
    for value in hass.data.get(DOMAIN, {}).values():
        if isinstance(value, AutomationDebuggerCoordinator):
            all_failures.extend(value.failures)

    connection.send_result(
        msg["id"],
        {
            "count": len(all_failures),
            "failures": all_failures,
        },
    )
