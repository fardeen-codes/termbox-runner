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
