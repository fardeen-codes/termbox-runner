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

def test_security_profiles_and_helpers():
    from termbox_runner.security import (
        generate_default_apparmor_profile,
        get_default_seccomp_profile,
        get_security_opts,
        get_whitelisted_capabilities,
        validate_read_only_rootfs,
        get_masked_paths,
        get_readonly_paths,
        emit_security_audit_event,
    )
    assert "termbox-default" in generate_default_apparmor_profile()
    assert "ptrace" in get_default_seccomp_profile()["syscalls"][0]["names"]
    assert "no-new-privileges:true" in get_security_opts()
    assert "CHOWN" in get_whitelisted_capabilities()
    assert validate_read_only_rootfs(True, True) is True
    assert validate_read_only_rootfs(True, False) is False
    assert "/proc/kcore" in get_masked_paths()
    assert "/proc/sys" in get_readonly_paths()
    audit = emit_security_audit_event("priv_esc_attempt", {"pid": 42})
    assert audit["event_type"] == "priv_esc_attempt"
