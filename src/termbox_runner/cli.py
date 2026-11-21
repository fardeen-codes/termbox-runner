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
