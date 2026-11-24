
def generate_default_apparmor_profile(profile_name: str = "termbox-default") -> str:
    """Generate minimal AppArmor profile definition restricting raw sockets and cap sys_admin."""
    return f"profile {profile_name} flags=(attach_disconnected,mediate_deleted) {{\n  deny capability sys_admin,\n  deny raw,\n}}"

def get_default_seccomp_profile() -> dict:
    """Return default seccomp profile dictionary denying ptrace and personality."""
    return {"defaultAction": "SCMP_ACT_ALLOW", "syscalls": [{"names": ["ptrace", "personality", "sys_chroot"], "action": "SCMP_ACT_ERRNO"}]}
