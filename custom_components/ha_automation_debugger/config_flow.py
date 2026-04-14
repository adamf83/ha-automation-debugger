"""Config flow for HA Automation Debugger — enables UI setup."""
from __future__ import annotations

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult

from .const import DOMAIN


class HaAutomationDebuggerConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for HA Automation Debugger."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step triggered from the UI."""
        if self._async_current_entries():
            return self.async_abort(reason="already_configured")

        if user_input is not None:
            return self.async_create_entry(title="HA Automation Debugger", data={})

        return self.async_show_form(step_id="user", data_schema=vol.Schema({}))
