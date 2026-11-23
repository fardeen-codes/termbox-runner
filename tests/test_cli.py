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


def test_cli_additional_subcommands():
    from termbox_runner.cli import build_parser, render_box_separator, format_network_error

    parser = build_parser()
    args_stats = parser.parse_args(["stats"])
    assert args_stats.command == "stats"

    args_top = parser.parse_args(["top"])
    assert args_top.command == "top"

    args_ver = parser.parse_args(["version"])
    assert args_ver.command == "version"

    assert "───" in render_box_separator(10)
    assert "Connection Error" in format_network_error(Exception(), "http://localhost:8000")


def test_cli_helpers_and_formatting():
    from termbox_runner.cli import pad_cell, terminal_bold, terminal_dim, safe_json_loads

    assert pad_cell("test", 10) == "test      "
    assert "\033[1m" in terminal_bold("bold")
    assert "\033[2m" in terminal_dim("dim")
    assert safe_json_loads('{"a": 1}')["a"] == 1
    assert safe_json_loads("invalid") == {}
