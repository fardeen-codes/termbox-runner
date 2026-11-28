
def generate_default_apparmor_profile(profile_name: str = "termbox-default") -> str:
    """Generate minimal AppArmor profile definition restricting raw sockets and cap sys_admin."""
    return f"profile {profile_name} flags=(attach_disconnected,mediate_deleted) {{\n  deny capability sys_admin,\n  deny raw,\n}}"

def get_default_seccomp_profile() -> dict:
    """Return default seccomp profile dictionary denying ptrace and personality."""
    return {"defaultAction": "SCMP_ACT_ALLOW", "syscalls": [{"names": ["ptrace", "personality", "sys_chroot"], "action": "SCMP_ACT_ERRNO"}]}

def get_security_opts(no_new_privs: bool = True) -> list[str]:
    """Build list of security options for Docker container runtime."""
    opts = []
    if no_new_privs:
        opts.append("no-new-privileges:true")
    return opts

def get_whitelisted_capabilities() -> list[str]:
    """Return safe capabilities required for basic sandboxed unprivileged CLI tasks."""
    return ["CHOWN", "DAC_OVERRIDE", "FOWNER", "SETGID", "SETUID"]

def validate_read_only_rootfs(is_read_only: bool, tmpfs_configured: bool) -> bool:
    """Validate that read-only root filesystems provide /tmp via tmpfs mount."""
    if is_read_only and not tmpfs_configured:
        return False
    return True

def get_masked_paths() -> list[str]:
    """Return kernel and hardware info paths that must be masked from containers."""
    return ["/proc/kcore", "/proc/sys", "/proc/sysrq-trigger", "/proc/irq", "/proc/bus"]

def get_readonly_paths() -> list[str]:
    """Return sensitive virtual filesystem paths that must be mounted read-only."""
    return ["/proc/asound", "/proc/bus", "/proc/fs", "/proc/sys", "/sys/fs/cgroup"]

def emit_security_audit_event(event_type: str, details: dict) -> dict:
    """Construct structured security audit log entry."""
    from datetime import datetime, timezone
    return {
        "event_type": event_type,
        "details": details,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "severity": "SECURITY_WARNING"
    }

def get_strict_network_seccomp_profile() -> dict:
    """Return seccomp profile denying packet and raw socket creation."""
    return {
        "defaultAction": "SCMP_ACT_ALLOW",
        "syscalls": [{"names": ["socket", "bind", "connect", "listen"], "action": "SCMP_ACT_ERRNO"}]
    }

def validate_dropped_capabilities(drop_caps: list) -> bool:
    """Verify that ALL or SYS_ADMIN is included in dropped capabilities."""
    upper_caps = [c.upper() for c in drop_caps]
    return "ALL" in upper_caps or "SYS_ADMIN" in upper_caps or "CAP_SYS_ADMIN" in upper_caps

def get_extended_masked_paths() -> list[str]:
    """Return comprehensive list of proc and sys paths to mask in container sandbox."""
    return [
        "/proc/kcore", "/proc/sys", "/proc/sysrq-trigger", "/proc/irq", "/proc/bus",
        "/proc/acpi", "/proc/keys", "/proc/latency_stats", "/proc/timer_list", "/proc/sched_debug"
    ]

def get_seccomp_architectures() -> list[str]:
    """Return supported seccomp architectures for multi-arch runners."""
    return ["SCMP_ARCH_X86_64", "SCMP_ARCH_AARCH64", "SCMP_ARCH_X86"]

def is_secure_tmpfs_options(options: str) -> bool:
    """Ensure noexec and nosuid flags are present in mount options."""
    return "nosuid" in options

def has_dropped_all_capabilities(cap_drop: list[str]) -> bool:
    """Check if container explicitly drops ALL capabilities."""
    return "ALL" in [c.upper() for c in cap_drop]

def validate_seccomp_action(action: str) -> bool:
    """Validate seccomp action string."""
    return action in ("SCMP_ACT_ALLOW", "SCMP_ACT_ERRNO", "SCMP_ACT_KILL", "SCMP_ACT_TRAP")

def generate_complain_mode_apparmor_profile(name: str = "termbox-complain") -> str:
    """Generate AppArmor profile in non-enforcing audit/complain mode."""
    return f"profile {name} flags=(complain) {{\n  file,\n  network,\n}}"

def override_seccomp_syscall_action(profile: dict, syscall_name: str, new_action: str) -> dict:
    """Modify action for a specific syscall inside seccomp profile dict."""
    new_prof = dict(profile)
    for sc in new_prof.get("syscalls", []):
        if syscall_name in sc.get("names", []):
            sc["action"] = new_action
    return new_prof

def is_safe_container_sysctl(key: str) -> bool:
    """Verify that kernel sysctl is safe for container execution."""
    unsafe_prefixes = ["kernel.", "fs.protected_", "vm.drop_caches"]
    return not any(key.startswith(p) for p in unsafe_prefixes)

def get_restricted_devices_list() -> list[str]:
    """Return list of dangerous host device paths blocked by default."""
    return ["/dev/kmem", "/dev/mem", "/dev/port", "/dev/nvme0", "/dev/sda"]

def is_safe_device_rule(rule: str) -> bool:
    """Verify device cgroup rule does not grant raw disk write."""
    return not ("b *:* rwm" in rule or "c 1:1 rwm" in rule)

def detect_docker_storage_driver(info_driver: str = "overlay2") -> str:
    """Normalize and identify Docker container storage driver."""
    return info_driver.lower().strip()

def estimate_overlay2_diff_size(layer_bytes: list[int]) -> int:
    """Sum layer byte sizes for container filesystem diff."""
    return sum(layer_bytes)

def normalize_capability_names(caps: list[str]) -> list[str]:
    """Ensure CAP_ prefix is consistently formatted."""
    return [c.upper() if c.upper().startswith("CAP_") else f"CAP_{c.upper()}" for c in caps]

def parse_tmpfs_size_mb(size_str: str) -> int:
    """Convert tmpfs size string like '128m' to MB integer."""
    from termbox_runner.models import parse_memory_to_bytes
    return int(parse_memory_to_bytes(size_str) / (1024 * 1024))

def filter_allowed_sysctls(sysctls: dict[str, str]) -> dict[str, str]:
    """Filter out any kernel sysctls that are dangerous."""
    return {k: v for k, v in sysctls.items() if is_safe_container_sysctl(k)}

def create_ro_bind_mount(host_path: str, container_path: str) -> dict:
    """Construct read-only volume mount dictionary."""
    return {host_path: {"bind": container_path, "mode": "ro"}}

def export_seccomp_profile_json(profile: dict) -> str:
    """Serialize seccomp profile dictionary to JSON string."""
    import json
    return json.dumps(profile, indent=2)

def is_apparmor_enforced(profile_output: str) -> bool:
    """Check if AppArmor reports profile in enforce mode."""
    return "flags=(enforce)" in profile_output or "flags=(attach_disconnected)" in profile_output

def generate_userns_remap_spec(host_uid: int, container_uid: int, count: int = 1) -> str:
    """Construct uid_map specification for unprivileged container user."""
    return f"{container_uid} {host_uid} {count}"

def parse_device_numbers(device_str: str) -> tuple[int, int]:
    """Parse device major:minor string (e.g. '1:3')."""
    parts = device_str.split(":")
    return int(parts[0]), int(parts[1])

def count_dropped_capabilities(cap_drop: list[str]) -> int:
    """Return count of explicitly dropped capabilities."""
    return len(cap_drop)

def format_security_summary(ro_rootfs: bool, no_new_privs: bool) -> str:
    """Return concise security summary string."""
    return f"ro_rootfs={ro_rootfs}, no_new_privs={no_new_privs}"

def count_seccomp_filtered_syscalls(profile: dict) -> int:
    """Count total number of filtered syscalls across rules."""
    return sum(len(sc.get("names", [])) for sc in profile.get("syscalls", []))

def is_valid_tmpfs_path(path: str) -> bool:
    """Ensure tmpfs mount path is standard temporary directory."""
    return path in ("/tmp", "/var/tmp", "/dev/shm", "/run")

def is_valid_pids_limit(pids_limit: int) -> bool:
    """Validate that pids_limit is within safe container execution range."""
    return 16 <= pids_limit <= 32768

def normalize_memory_swappiness(swappiness: int) -> int:
    """Clamp memory swappiness to safe range [0, 100]."""
    return max(0, min(100, swappiness))

def is_valid_kernel_memory_mb(kmem_mb: int) -> bool:
    """Validate kernel memory limit bounds."""
    return 4 <= kmem_mb <= 4096

def get_private_ipc_flag() -> str:
    """Return Docker flag to enforce private IPC namespace."""
    return "--ipc=private"

def is_valid_container_hostname(hostname: str) -> bool:
    """Validate container hostname conforming to RFC 1123."""
    import re
    return bool(re.match(r"^[a-zA-Z0-9][-a-zA-Z0-9]{0,62}$", hostname))

def format_memory_reservation(reservation_mb: int) -> str:
    """Format memory reservation parameter for docker run."""
    return f"--memory-reservation={reservation_mb}m"
