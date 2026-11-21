"""Unit tests for configuration settings."""

from termbox_runner.config import Settings, get_settings


def test_settings_defaults():
    s = Settings()
    assert s.app_name == "termbox-runner"
    assert s.default_timeout_seconds == 30.0
    assert s.container_hostname == "sandbox"
    assert s.stop_grace_period_seconds == 2
    assert s.tmpfs_size_mb == 64


def test_settings_sanitized_dict():
    s = Settings()
    d = s.sanitized_dict()
    assert "docker_base_url" not in d
    assert d["app_name"] == "termbox-runner"
    assert d["container_hostname"] == "sandbox"


def test_get_settings_caching():
    s1 = get_settings()
    s2 = get_settings()
    assert s1 is s2
