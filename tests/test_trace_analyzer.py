"""Unit tests for trace_analyzer.py."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from tests.conftest import build_trace_store

# Import the module under test *after* conftest has stubbed HA modules
from custom_components.ha_automation_debugger.trace_analyzer import (
    _analyze_trace,
    _extract_condition_reason,
    _extract_trigger_description,
    _get_condition_type,
    _trace_is_recent,
)

SINCE = datetime(2026, 4, 14, 18, 41, 59, tzinfo=timezone.utc)
ENTITY_ID = "automation.evening_lights"


# ---------------------------------------------------------------------------
# _analyze_trace — end-to-end
# ---------------------------------------------------------------------------


def test_stopped_trace_sun_condition_returns_failure(
    mock_hass, sample_trace_stopped
):
    """Stopped trace with a sun condition → failure with mapped reason."""
    mock_hass.data["trace"] = build_trace_store(ENTITY_ID, sample_trace_stopped)
    result = _analyze_trace(mock_hass, ENTITY_ID, SINCE)

    assert result is not None
    assert result["status"] == "failed"
    assert result["automation"] == ENTITY_ID
    assert result["reason"] == "Sun condition not met"
    assert result["trigger"] == "time (18:42)"


def test_stopped_trace_with_description_uses_it(
    mock_hass, sample_trace_stopped_with_description
):
    """When the failed condition supplies its own description, use it verbatim."""
    mock_hass.data["trace"] = build_trace_store(
        ENTITY_ID, sample_trace_stopped_with_description
    )
    result = _analyze_trace(mock_hass, ENTITY_ID, SINCE)

    assert result is not None
    assert result["reason"] == "State of cover.garage is open, expected closed"


def test_error_trace_returns_aborted_with_error_message(
    mock_hass, sample_trace_error
):
    """Error trace → aborted status and the error string as the reason."""
    mock_hass.data["trace"] = build_trace_store(ENTITY_ID, sample_trace_error)
    result = _analyze_trace(mock_hass, ENTITY_ID, SINCE)

    assert result is not None
    assert result["status"] == "aborted"
    assert "Service not found" in result["reason"]
    assert result["trigger"] == "state change (sensor.motion)"


def test_finished_trace_returns_none(mock_hass, sample_trace_finished):
    """Successful (finished) trace → None."""
    mock_hass.data["trace"] = build_trace_store(ENTITY_ID, sample_trace_finished)
    result = _analyze_trace(mock_hass, ENTITY_ID, SINCE)

    assert result is None


def test_trace_older_than_since_returns_none(mock_hass, sample_trace_stopped):
    """Trace that started before *since* is ignored."""
    mock_hass.data["trace"] = build_trace_store(ENTITY_ID, sample_trace_stopped)
    # Move since to well after the trace start time
    late_since = datetime(2026, 4, 14, 19, 0, 0, tzinfo=timezone.utc)
    result = _analyze_trace(mock_hass, ENTITY_ID, late_since)

    assert result is None


def test_missing_trace_store_returns_none(mock_hass):
    """Absent trace store → None (graceful degradation)."""
    mock_hass.data = {}
    result = _analyze_trace(mock_hass, ENTITY_ID, SINCE)
    assert result is None


def test_missing_automation_in_store_returns_none(mock_hass):
    """Known trace store but unknown automation → None."""
    mock_hass.data["trace"] = {"automation": {}}
    result = _analyze_trace(mock_hass, ENTITY_ID, SINCE)
    assert result is None


def test_run_id_included_in_result(mock_hass, sample_trace_stopped):
    """run_id from the trace is propagated so the coordinator can deduplicate."""
    mock_hass.data["trace"] = build_trace_store(ENTITY_ID, sample_trace_stopped)
    result = _analyze_trace(mock_hass, ENTITY_ID, SINCE)
    assert result["run_id"] == "abc-123"


# ---------------------------------------------------------------------------
# _trace_is_recent
# ---------------------------------------------------------------------------


def test_trace_is_recent_same_second():
    trace_data = {"timestamp": {"start": "2026-04-14T18:42:00+00:00"}}
    since = datetime(2026, 4, 14, 18, 42, 0, tzinfo=timezone.utc)
    assert _trace_is_recent(trace_data, since) is True


def test_trace_is_recent_future_start():
    trace_data = {"timestamp": {"start": "2026-04-14T18:42:05+00:00"}}
    since = datetime(2026, 4, 14, 18, 42, 0, tzinfo=timezone.utc)
    assert _trace_is_recent(trace_data, since) is True


def test_trace_is_recent_old_start():
    trace_data = {"timestamp": {"start": "2026-04-14T18:40:00+00:00"}}
    since = datetime(2026, 4, 14, 18, 42, 0, tzinfo=timezone.utc)
    assert _trace_is_recent(trace_data, since) is False


def test_trace_is_recent_no_timestamp():
    """Missing timestamp is treated as valid (can't tell → assume recent)."""
    assert _trace_is_recent({}, datetime(2026, 4, 14, 18, 42, 0, tzinfo=timezone.utc)) is True


# ---------------------------------------------------------------------------
# _extract_trigger_description
# ---------------------------------------------------------------------------


def test_extract_trigger_description_from_trace_node():
    trace_data = {
        "trace": {
            "trigger:0": [{"result": {"description": "motion detected (living_room)"}}]
        }
    }
    assert _extract_trigger_description(trace_data) == "motion detected (living_room)"


def test_extract_trigger_description_fallback_to_top_level():
    trace_data = {"trace": {}, "trigger": "time"}
    assert _extract_trigger_description(trace_data) == "time"


def test_extract_trigger_description_unknown_when_nothing():
    assert _extract_trigger_description({"trace": {}}) == "Unknown trigger"


# ---------------------------------------------------------------------------
# _extract_condition_reason
# ---------------------------------------------------------------------------


def test_extract_condition_reason_uses_result_description():
    trace_data = {
        "config": {},
        "trace": {
            "condition:0": [
                {"result": {"result": False, "description": "Sun elevation is 45°, expected below 0°"}}
            ]
        },
    }
    assert _extract_condition_reason(trace_data) == "Sun elevation is 45°, expected below 0°"


def test_extract_condition_reason_maps_from_config():
    trace_data = {
        "config": {"condition": [{"condition": "time"}]},
        "trace": {
            "condition:0": [{"result": {"result": False}}]
        },
    }
    assert _extract_condition_reason(trace_data) == "Time condition not met"


def test_extract_condition_reason_skips_passing_conditions():
    trace_data = {
        "config": {"condition": [{"condition": "state"}, {"condition": "sun"}]},
        "trace": {
            "condition:0": [{"result": {"result": True}}],
            "condition:1": [{"result": {"result": False}}],
        },
    }
    assert _extract_condition_reason(trace_data) == "Sun condition not met"


def test_extract_condition_reason_fallback_when_no_condition_nodes():
    trace_data = {"config": {}, "trace": {}}
    assert "Condition not met" in _extract_condition_reason(trace_data)


# ---------------------------------------------------------------------------
# _get_condition_type
# ---------------------------------------------------------------------------


def test_get_condition_type_simple_index():
    config = [{"condition": "sun"}, {"condition": "state"}]
    assert _get_condition_type("condition:1", config) == "state"


def test_get_condition_type_out_of_range():
    assert _get_condition_type("condition:99", []) == "unknown"


def test_get_condition_type_non_numeric():
    assert _get_condition_type("condition/0/condition/0", []) == "unknown"
