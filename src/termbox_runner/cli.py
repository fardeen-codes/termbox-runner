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
    p_run.add_argument('command')
    p_run.add_argument('--image', default='python:3.12-slim')
    p_rep = subparsers.add_parser('replay', help='Replay a prior run')
    p_rep.add_argument('run_id')
    subparsers.add_parser('templates', help='List benchmark templates')
    return parser


def main(args=None):
    parser = build_parser()
    parsed = parser.parse_args(args)
    if not parsed.command:
        parser.print_help()
        sys.exit(0)


if __name__ == "__main__":
    main()

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
        items = res.json().get("templates", [])
        for t in items:
            print(f"- {t['id']} [{t['category']}]: {t['name']}")
