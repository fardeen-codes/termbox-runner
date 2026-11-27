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

def test_security_part3_features():
    from termbox_runner.security import get_strict_network_seccomp_profile, validate_dropped_capabilities
    from termbox_runner.runner import calculate_memory_reservation
    prof = get_strict_network_seccomp_profile()
    assert "socket" in prof["syscalls"][0]["names"]
    assert validate_dropped_capabilities(["ALL"]) is True
    assert validate_dropped_capabilities(["CHOWN"]) is False
    res = calculate_memory_reservation(100 * 1024 * 1024, 0.5)
    assert res == 50 * 1024 * 1024

def test_cgroups_and_security_extensions():
    from termbox_runner.runner import (
        calculate_cgroup_memory_high,
        calculate_cgroup_cpu_weight,
        calculate_cgroup_io_weight,
        get_low_tier_preset,
        build_tmpfs_mount_spec,
    )
    from termbox_runner.security import (
        get_extended_masked_paths,
        get_seccomp_architectures,
        has_dropped_all_capabilities,
    )
    assert calculate_cgroup_memory_high(1000) == 850
    assert calculate_cgroup_cpu_weight(1.0) == 100
    assert calculate_cgroup_io_weight(0) == 100
    assert get_low_tier_preset()["mem_limit"] == "128m"
    assert "nosuid" in build_tmpfs_mount_spec()["/tmp"]
    assert "/proc/acpi" in get_extended_masked_paths()
    assert "SCMP_ARCH_X86_64" in get_seccomp_architectures()
    assert has_dropped_all_capabilities(["ALL"]) is True

def test_security_part4_network_and_sysctls():
    from termbox_runner.runner import is_valid_network_mode, parse_cpuset_to_list, validate_volume_mount_mode
    from termbox_runner.security import is_safe_container_sysctl, override_seccomp_syscall_action
    assert is_valid_network_mode("none") is True
    assert is_valid_network_mode("bridge") is True
    assert parse_cpuset_to_list("0,2-4") == [0, 2, 3, 4]
    assert validate_volume_mount_mode("ro") is True
    assert is_safe_container_sysctl("net.ipv4.ip_forward") is True
    assert is_safe_container_sysctl("kernel.core_pattern") is False

def test_security_part5_device_and_oom():
    from termbox_runner.runner import compute_oom_score_adj, clamp_cpu_shares, parse_rate_limit_bytes
    from termbox_runner.security import get_restricted_devices_list, is_safe_device_rule
    assert compute_oom_score_adj(5) == 250
    assert clamp_cpu_shares(1) == 2
    assert parse_rate_limit_bytes("10m") == 10 * 1024 * 1024
    assert "/dev/mem" in get_restricted_devices_list()
    assert is_safe_device_rule("c 1:3 r") is True
    assert is_safe_device_rule("b *:* rwm") is False
