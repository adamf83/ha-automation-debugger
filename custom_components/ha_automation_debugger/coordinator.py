"""Coordinator for HA Automation Debugger.

Listens for automation_triggered events, waits for the trace to finalise,
then inspects the trace for failures and keeps a bounded in-memory buffer.
"""
from __future__ import annotations

import logging
from collections import deque
from datetime import datetime
from typing import Callable

from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.event import async_call_later
from homeassistant.util import dt as dt_util

from .const import (
    EVENT_AUTOMATION_TRIGGERED,
    MAX_FAILURES,
    TRACE_FETCH_DELAY,
)
from .trace_analyzer import async_fetch_latest_failure

_LOGGER = logging.getLogger(__name__)


class AutomationDebuggerCoordinator:
    """Manages the in-memory failure buffer and the automation event listener."""

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass
        self.failures: deque[dict] = deque(maxlen=MAX_FAILURES)
        self._event_unsub: Callable | None = None
        self._update_callbacks: set[Callable] = set()
        # Tracks run IDs we have already recorded so duplicate events are ignored
        self._seen_run_ids: set[str] = set()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def async_setup(self) -> None:
        """Register the automation_triggered event listener."""
        self._event_unsub = self.hass.bus.async_listen(
            EVENT_AUTOMATION_TRIGGERED,
            self._handle_automation_triggered,
        )
        _LOGGER.debug("Automation Debugger coordinator set up")

    def async_teardown(self) -> None:
        """Unregister the event listener."""
        if self._event_unsub is not None:
            self._event_unsub()
            self._event_unsub = None

    # ------------------------------------------------------------------
    # Listener registration
    # ------------------------------------------------------------------

    @callback
    def async_add_listener(self, update_callback: Callable) -> Callable:
        """Register *update_callback* to be called on every new failure.

        Returns a callable that removes the listener when invoked.
        """
        self._update_callbacks.add(update_callback)

        @callback
        def remove_listener() -> None:
            self._update_callbacks.discard(update_callback)

        return remove_listener

    # ------------------------------------------------------------------
    # Internal event handling
    # ------------------------------------------------------------------

    @callback
    def _handle_automation_triggered(self, event: Event) -> None:
        """Respond to an automation_triggered bus event.

        Schedules a delayed task that fetches the trace once the automation
        run has had time to finalise.
        """
        entity_id: str | None = event.data.get(ATTR_ENTITY_ID)
        if not entity_id or not entity_id.startswith("automation."):
            return

        trigger_time = dt_util.utcnow()
        _LOGGER.debug("automation_triggered received: %s at %s", entity_id, trigger_time)

        async_call_later(
            self.hass,
            TRACE_FETCH_DELAY,
            lambda _now: self.hass.async_create_task(
                self._check_for_failure(entity_id, trigger_time)
            ),
        )

    async def _check_for_failure(
        self, entity_id: str, trigger_time: datetime
    ) -> None:
        """Fetch the trace and record a failure entry when applicable."""
        failure = await async_fetch_latest_failure(self.hass, entity_id, trigger_time)
        if failure is None:
            return

        run_id: str = failure.pop("run_id", "")
        if run_id and run_id in self._seen_run_ids:
            _LOGGER.debug("Skipping already-seen run_id %s for %s", run_id, entity_id)
            return

        if run_id:
            self._seen_run_ids.add(run_id)
            # Bound the set so it does not grow without limit
            if len(self._seen_run_ids) > 500:
                self._seen_run_ids.pop()

        self.failures.append(failure)
        _LOGGER.info(
            "Recorded automation failure: %s — %s",
            failure.get("automation"),
            failure.get("reason"),
        )
        self._notify_listeners()

    def _notify_listeners(self) -> None:
        """Invoke all registered update callbacks."""
        for cb in self._update_callbacks:
            cb()
