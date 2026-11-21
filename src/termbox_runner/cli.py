
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
    subparsers.add_parser('list', help='List recent execution manifests')
    p_insp = subparsers.add_parser('inspect', help='Inspect a specific run')
    p_insp.add_argument('run_id')
    p_run = subparsers.add_parser('run', help='Execute sandboxed command')
    p_run.add_argument('task_cmd', help='Command to execute inside sandbox')
    p_run.add_argument('--image', default='python:3.12-slim')
    p_rep = subparsers.add_parser('replay', help='Replay a prior run')
    p_rep.add_argument('run_id')
    p_search = subparsers.add_parser('search', help='Search runs by command query')
    p_search.add_argument('query')
    p_diff = subparsers.add_parser('diff', help='Compare two runs')
    p_diff.add_argument('run_a')
    p_diff.add_argument('run_b')
    subparsers.add_parser('templates', help='List benchmark templates')
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

def main(args=None):
    parser = build_parser()
    parsed = parser.parse_args(args)
    if not parsed.command:
        parser.print_help()
        sys.exit(0)
    server = parsed.server
    if parsed.command == "health":
        cmd_health(server)
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
