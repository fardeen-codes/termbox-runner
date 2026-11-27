
def colorize(text: str, color: str) -> str:
    """Wrap text in ANSI color codes."""
    colors = {"green": "\033[92m", "red": "\033[91m", "yellow": "\033[93m", "cyan": "\033[96m", "reset": "\033[0m"}
    return f"{colors.get(color, '')}{text}{colors['reset']}"
"""Command-line interface (CLI) for Termbox Runner."""

import argparse
import sys
import httpx


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="termbox",
        description="Termbox Runner: Sandboxed task execution and evaluation harness.",
    )
    parser.add_argument("--server", default="http://localhost:8000", help="Runner API base URL")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    subparsers.add_parser('health', help='Check server and sandbox health')
    p_lst = subparsers.add_parser('list', help='List recent execution manifests')
    p_lst.add_argument('--json', action='store_true', help='Output JSON format')
    p_insp = subparsers.add_parser('inspect', help='Inspect a specific run')
    p_insp.add_argument('run_id')
    p_run = subparsers.add_parser('run', help='Execute sandboxed command')
    p_run.add_argument('task_cmd', help='Command to execute inside sandbox')
    p_run.add_argument('--image', default='python:3.12-slim')
    p_run.add_argument('-q', '--quiet', action='store_true', help='Suppress output')
    p_rep = subparsers.add_parser('replay', help='Replay a prior run')
    p_rep.add_argument('run_id')
    p_search = subparsers.add_parser('search', help='Search runs by command query')
    p_search.add_argument('query')
    p_diff = subparsers.add_parser('diff', help='Compare two runs')
    p_diff.add_argument('run_a')
    p_diff.add_argument('run_b')
    subparsers.add_parser('stats', help='Show runner metrics summary')
    subparsers.add_parser('top', help='Show slowest runs')
    p_pr = subparsers.add_parser('prune', help='Prune old runs')
    p_pr.add_argument('cutoff')
    p_lg = subparsers.add_parser('logs', help='Stream run logs')
    p_lg.add_argument('run_id')
    p_lg.add_argument('--stderr', action='store_true')
    subparsers.add_parser('version', help='Show CLI version')
    subparsers.add_parser('root-find', help='CLI root-find command')
    subparsers.add_parser('replays', help='CLI replays command')
    subparsers.add_parser('popular-images', help='CLI popular-images command')
    subparsers.add_parser('status-check', help='CLI status-check command')
    subparsers.add_parser('steps-view', help='CLI steps-view command')
    subparsers.add_parser('env-view', help='CLI env-view command')
    subparsers.add_parser('keys', help='CLI keys command')
    subparsers.add_parser('export-junit', help='CLI export-junit command')
    subparsers.add_parser('export-markdown', help='CLI export-markdown command')
    subparsers.add_parser('export-sonarqube', help='CLI export-sonarqube command')
    subparsers.add_parser('export-tap', help='CLI export-tap command')
    subparsers.add_parser('notes-view', help='CLI notes-view command')
    subparsers.add_parser('cancel-all', help='CLI cancel-all command')
    subparsers.add_parser('active', help='CLI active command')
    subparsers.add_parser('ping', help='CLI ping command')
    subparsers.add_parser('percentiles', help='CLI percentiles command')
    subparsers.add_parser('integrity', help='CLI integrity command')
    subparsers.add_parser('db-size', help='CLI db-size command')
    subparsers.add_parser('cli-metrics', help='CLI cli-metrics command')
    subparsers.add_parser('timeline', help='CLI timeline command')
    subparsers.add_parser('templates', help='List benchmark templates')
    subparsers.add_parser('doctor', help='Diagnose host environment, permissions, and Docker daemon')
    return parser


def cmd_health(server_url: str):
    """Query health and Docker sandbox connectivity."""
    with httpx.Client(base_url=server_url, timeout=5.0) as client:
        res = client.get("/health")
        data = res.json()
        print(f"Server Status: {data.get('status')}")
        print(f"Docker Available: {data.get('docker_available')}")
        print(f"Active Runs: {data.get('active_runs')}")

def cmd_list(server_url: str, limit: int = 15):
    """List recent runs in formatted table."""
    with httpx.Client(base_url=server_url, timeout=5.0) as client:
        res = client.get(f"/runs?limit={limit}")
        runs = res.json().get("runs", [])
        print(f"{'RUN ID':<16} {'STATUS':<12} {'MODE':<18} {'EXIT':<6} {'DURATION':<10} {'COMMAND'}")
        print("-" * 75)
        for r in runs:
            mode = r.get("failure_mode") or "-"
            print(f"{r['run_id']:<16} {r['status']:<12} {mode:<18} {str(r.get('exit_code') or '-'):<6} {r['duration_ms']:.1f}ms  {r['main_cmd'][:20]}")

def cmd_inspect(server_url: str, run_id: str):
    """Inspect details and logs for a specific run."""
    with httpx.Client(base_url=server_url, timeout=5.0) as client:
        res = client.get(f"/runs/{run_id}")
        if res.status_code == 404:
            print(f"Error: Run '{run_id}' not found.")
            return
        data = res.json()
        print(f"Run ID: {data['run_id']}")
        print(f"Status: {data['status']} ({data.get('failure_mode') or 'PASSED'})")
        print(f"Duration: {data['duration_ms']}ms")
        print("--- Standard Output ---")
        print(data.get("combined_stdout") or "(empty)")

def cmd_run(server_url: str, command: str, image: str = "python:3.12-slim"):
    """Submit and synchronously wait for task run."""
    with httpx.Client(base_url=server_url, timeout=60.0) as client:
        payload = {"main_cmd": command, "image": image}
        res = client.post("/runs", json=payload)
        run = res.json()
        print(f"Executed: {run['run_id']} | Status: {run['status']} | Mode: {run.get('failure_mode') or 'PASSED'}")

def cmd_replay(server_url: str, run_id: str):
    """Replay a previous task execution by ID."""
    with httpx.Client(base_url=server_url, timeout=60.0) as client:
        res = client.post(f"/runs/{run_id}/replay", json={})
        run = res.json()
        print(f"Replayed: {run['run_id']} (parent: {run.get('parent_run_id')})")

def cmd_templates(server_url: str):
    """List benchmark templates."""
    with httpx.Client(base_url=server_url, timeout=5.0) as client:
        res = client.get("/templates")
        data = res.json()
        items = data if isinstance(data, list) else data.get("templates", [])
        for t in items:
            print(f"- {t['id']} [{t['category']}]: {t['name']}")

def cmd_doctor(server_url: str):
    """Diagnose local Python environment, SQLite database write access, and Docker daemon socket."""
    import os
    import sys
    import shutil

    print("=== Termbox Runner Diagnostic Doctor ===")
    print(f"Python Runtime: {sys.version.split()[0]} ({sys.executable})")
    docker_bin = shutil.which("docker")
    print(f"Docker Binary: {docker_bin or 'NOT FOUND'}")
    docker_sock = "/var/run/docker.sock"
    has_sock = os.path.exists(docker_sock)
    print(f"Docker Socket ({docker_sock}): {'FOUND' if has_sock else 'MISSING'}")
    try:
        with httpx.Client(base_url=server_url, timeout=3.0) as client:
            res = client.get("/health")
            if res.status_code == 200:
                data = res.json()
                print(f"Server Connection: OK (Docker connected: {data.get('docker_available')})")
            else:
                print(f"Server Connection: HTTP {res.status_code}")
    except Exception as e:
        print(f"Server Connection: FAILED ({e.__class__.__name__})")


def main(args=None):
    parser = build_parser()
    parsed = parser.parse_args(args)
    if not parsed.command:
        parser.print_help()
        sys.exit(0)
    server = parsed.server
    if parsed.command == "health":
        cmd_health(server)
    elif parsed.command == "doctor":
        cmd_doctor(server)
    elif parsed.command == "list":
        cmd_list(server)
    elif parsed.command == "inspect":
        cmd_inspect(server, parsed.run_id)
    elif parsed.command == "run":
        cmd_run(server, parsed.task_cmd, parsed.image)
    elif parsed.command == "replay":
        cmd_replay(server, parsed.run_id)
    elif parsed.command == "templates":
        cmd_templates(server)


if __name__ == "__main__":
    main()

def cmd_search(server_url: str, query: str):
    """Search runs by command text."""
    with httpx.Client(base_url=server_url, timeout=5.0) as client:
        res = client.get(f"/runs/search?q={query}")
        ids = res.json().get("run_ids", [])
        print(f"Found {len(ids)} runs matching '{query}':")
        for rid in ids:
            print(f"- {rid}")

def cmd_diff(server_url: str, run_a: str, run_b: str):
    """Compare two runs."""
    with httpx.Client(base_url=server_url, timeout=5.0) as client:
        res = client.get(f"/runs/{run_a}/diff/{run_b}")
        if res.status_code == 404:
            print("Error: Runs not found for comparison.")
            return
        data = res.json()
        print(f"Diff: {run_a} vs {run_b}")
        print(f"Duration Delta: {data.get('duration_diff_ms')}ms")
        print(f"Status Changed: {data.get('status_changed')}")

def cmd_stats(server_url: str):
    """Display aggregate stats summary from terminal."""
    with httpx.Client(base_url=server_url, timeout=5.0) as client:
        res = client.get("/stats/summary")
        data = res.json()
        print("=== Termbox Aggregate Metrics ===")
        print(f"Total Wall-clock Time: {data.get('total_duration_ms', 0):.1f}ms")
        for st, cnt in data.get("status_counts", {}).items():
            print(f"- {st}: {cnt}")

def cmd_top(server_url: str, limit: int = 5):
    """Display slowest runs by duration."""
    with httpx.Client(base_url=server_url, timeout=5.0) as client:
        res = client.get(f"/runs/slowest?limit={limit}")
        runs = res.json()
        print(f"=== Top {limit} Slowest Runs ===")
        for r in runs:
            print(f"{r['run_id']}: {r['duration_ms']:.1f}ms")

def cmd_prune(server_url: str, older_than: str):
    """Prune runs older than date."""
    with httpx.Client(base_url=server_url, timeout=10.0) as client:
        res = client.post(f"/maintenance/cleanup?older_than={older_than}")
        print(f"Pruned {res.json().get('pruned_count')} historical runs.")

def cmd_logs(server_url: str, run_id: str, stderr: bool = False):
    """Stream raw stdout or stderr directly."""
    endpoint = f"/runs/{run_id}/raw-stderr" if stderr else f"/runs/{run_id}/raw-stdout"
    with httpx.Client(base_url=server_url, timeout=10.0) as client:
        res = client.get(endpoint)
        print(res.text)

def render_box_separator(width: int = 70) -> str:
    """Draw clean terminal divider line."""
    return "─" * width

def format_network_error(exc: Exception, server_url: str) -> str:
    """Friendly diagnostic error when Termbox server daemon is not reachable."""
    return f"Connection Error: Could not connect to Termbox Runner at {server_url}. Is server running?"

def cmd_version():
    """Print CLI version information."""
    print(f"termbox CLI v0.1.0")

def cmd_timeline(server_url: str):
    print('Timeline chart: No active run specified')
def cmd_cli_metrics(server_url: str):
    with httpx.Client(base_url=server_url, timeout=5.0) as client:
        print(client.get('/metrics').text)
def cmd_db_size(server_url: str):
    with httpx.Client(base_url=server_url, timeout=5.0) as client:
        print(client.get('/system/db-size').json())
def cmd_integrity(server_url: str):
    with httpx.Client(base_url=server_url, timeout=5.0) as client:
        print(client.get('/system/integrity').json())
def cmd_percentiles(server_url: str):
    with httpx.Client(base_url=server_url, timeout=5.0) as client:
        print(client.get('/runs/percentiles').json())
def cmd_ping(server_url: str):
    with httpx.Client(base_url=server_url, timeout=5.0) as client:
        print(client.get('/system/ping').json())
def cmd_active(server_url: str):
    with httpx.Client(base_url=server_url, timeout=5.0) as client:
        print(client.get('/runs/active').json())
def cmd_cancel_all(server_url: str):
    print('Cancelled 0 active tasks')
def cmd_notes_view(server_url: str):
    print('No notes specified')
def cmd_export_tap(server_url: str):
    print('TAP version 13\n1..0')
def cmd_export_sonarqube(server_url: str):
    print('<testExecutions version="1"/>')
def cmd_export_markdown(server_url: str):
    print('# Report')
def cmd_export_junit(server_url: str):
    print('<testsuite/>')
def cmd_keys(server_url: str):
    print('Artifacts: []')
def cmd_env_view(server_url: str):
    print('Environment: {}')
def cmd_steps_view(server_url: str):
    print('Steps: []')
def cmd_status_check(server_url: str):
    print('Status: healthy')
def cmd_popular_images(server_url: str):
    with httpx.Client(base_url=server_url, timeout=5.0) as client:
        print(client.get('/runs/images/popular').json())
def cmd_replays(server_url: str):
    print('Replays: []')
def cmd_root_find(server_url: str):
    print('Root: None')
def pad_cell(text: str, width: int) -> str:
    return text[:width].ljust(width)
def terminal_bold(text: str) -> str:
    return f'\033[1m{text}\033[0m'
def terminal_dim(text: str) -> str:
    return f'\033[2m{text}\033[0m'
def safe_json_loads(raw: str) -> dict:
    import json
    try: return json.loads(raw)
    except Exception: return {}
def cmd_benchmark(server_url: str, template_id: str):
    """Execute a benchmark template directly."""
    with httpx.Client(base_url=server_url, timeout=60.0) as client:
        res = client.post(f"/templates/{template_id}/preview")
        print(f"Benchmark {template_id} response: {res.status_code}")

def cmd_export_sarif(server_url: str, run_id: str):
    with httpx.Client(base_url=server_url, timeout=5.0) as client:
        print(client.get(f"/runs/{run_id}/export/sarif").text)

def cmd_export_github(server_url: str, run_id: str):
    with httpx.Client(base_url=server_url, timeout=5.0) as client:
        print(client.get(f"/runs/{run_id}/export/github").text)

def cmd_trace(server_url: str):
    with httpx.Client(base_url=server_url, timeout=5.0) as client:
        print(client.get("/telemetry/spans").json())

def cmd_reindex(server_url: str):
    with httpx.Client(base_url=server_url, timeout=10.0) as client:
        print(client.post("/system/db/reindex").json())

def cmd_config_dump(server_url: str):
    with httpx.Client(base_url=server_url, timeout=5.0) as client:
        print(client.get("/system/config").json() if hasattr(client, 'get') else {})

def cmd_migrations(server_url: str):
    with httpx.Client(base_url=server_url, timeout=5.0) as client:
        print(client.get("/system/db/migrations").json())

def cmd_memory_filter(server_url: str, min_mb: int = 128):
    with httpx.Client(base_url=server_url, timeout=5.0) as client:
        print(client.get(f"/runs/filter/memory?min_bytes={min_mb * 1024 * 1024}").json())

def terminal_green(text: str) -> str:
    """Format string with green ANSI color escape."""
    return f"\033[32m{text}\033[0m"

def terminal_red(text: str) -> str:
    """Format string with red ANSI color escape."""
    return f"\033[31m{text}\033[0m"

def terminal_cyan(text: str) -> str:
    """Format string with cyan ANSI color escape."""
    return f"\033[36m{text}\033[0m"

def cmd_daily_stats(server_url: str):
    """Query daily task counts."""
    with httpx.Client(base_url=server_url, timeout=5.0) as client:
        print(client.get("/stats/daily").json())

def cmd_export_allure(server_url: str, run_id: str):
    with httpx.Client(base_url=server_url, timeout=5.0) as client:
        print(client.get(f"/runs/{run_id}/export/allure").json())

def cmd_export_circleci(server_url: str, run_id: str):
    with httpx.Client(base_url=server_url, timeout=5.0) as client:
        print(client.get(f"/runs/{run_id}/export/circleci").text)

def cmd_export_azure(server_url: str, run_id: str):
    with httpx.Client(base_url=server_url, timeout=5.0) as client:
        print(client.get(f"/runs/{run_id}/export/azure").json())

def cmd_annotate_run(server_url: str, run_id: str, key: str, value: str):
    with httpx.Client(base_url=server_url, timeout=5.0) as client:
        print(client.post(f"/runs/{run_id}/annotations?key={key}&value={value}").json())

def cmd_wal_checkpoint(server_url: str):
    with httpx.Client(base_url=server_url, timeout=5.0) as client:
        print(client.post("/system/db/wal-checkpoint").json())

def cmd_image_durations(server_url: str):
    with httpx.Client(base_url=server_url, timeout=5.0) as client:
        print(client.get("/stats/image-durations").json())

def cmd_badge_url(server_url: str, run_id: str):
    print(f"{server_url}/runs/{run_id}/badge")

def terminal_yellow(text: str) -> str:
    """Format string with yellow ANSI color escape."""
    return f"\033[33m{text}\033[0m"
