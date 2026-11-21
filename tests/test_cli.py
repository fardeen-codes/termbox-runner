"""Tests for Termbox Runner CLI argument parser and commands."""

from termbox_runner.cli import build_parser, colorize


def test_cli_parser_commands():
    parser = build_parser()
    args = parser.parse_args(["health"])
    assert args.command == "health"

    args_run = parser.parse_args(["run", "echo hello"])
    assert args_run.command == "run"
    assert args_run.task_cmd == "echo hello"


def test_cli_colorize():
    assert "\033[92m" in colorize("OK", "green")
