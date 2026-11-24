
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
