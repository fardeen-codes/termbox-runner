"""Tests for security isolation and capability restriction schemas."""

from termbox_runner.models import ResourceLimits, SecurityOptions, TaskSubmission


def test_security_options_defaults():
    sec = SecurityOptions()
    assert sec.drop_capabilities == ["ALL"]
    assert sec.add_capabilities == []
    assert sec.no_new_privileges is True
    assert sec.read_only_rootfs is False
    assert sec.seccomp_profile is None


def test_task_submission_custom_security():
    task = TaskSubmission(
        main_cmd="echo secure",
        limits=ResourceLimits(
            security=SecurityOptions(
                read_only_rootfs=True,
                drop_capabilities=["ALL", "NET_ADMIN"],
                add_capabilities=["CHOWN"],
                no_new_privileges=True,
            )
        ),
    )
    assert task.limits.security.read_only_rootfs is True
    assert "CHOWN" in task.limits.security.add_capabilities
    assert "NET_ADMIN" in task.limits.security.drop_capabilities
