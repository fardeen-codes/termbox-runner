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
    return parser


def main(args=None):
    parser = build_parser()
    parsed = parser.parse_args(args)
    if not parsed.command:
        parser.print_help()
        sys.exit(0)


if __name__ == "__main__":
    main()
