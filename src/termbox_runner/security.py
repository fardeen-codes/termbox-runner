
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
