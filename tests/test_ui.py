"""Tests for dashboard UI rendering and endpoints."""

from termbox_runner.ui import DASHBOARD_HTML


def test_dashboard_contains_critical_ui_elements():
    assert "Termbox Runner" in DASHBOARD_HTML
    assert "Export CSV" in DASHBOARD_HTML
    assert "submitPreset" in DASHBOARD_HTML
    assert "openNewRunModal" in DASHBOARD_HTML


def test_ui_additional_controls():
    assert "copyCommand" in DASHBOARD_HTML
    assert "toggleAutoRefresh" in DASHBOARD_HTML
    assert "getExitCodeBadge" in DASHBOARD_HTML


def test_ui_part3_features():
    assert "renderGanttTimeline" in DASHBOARD_HTML
    assert "bindEscapeShortcut" in DASHBOARD_HTML
    assert "toggleTheme" in DASHBOARD_HTML
