import argparse
import sys
from io import StringIO
from pathlib import Path

import pytest


def FormatBytes(size: int) -> str:
    if size < 0:
        return "0 B"
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(size) < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} PB"


def FormatDuration(seconds: float) -> str:
    if seconds < 0:
        return "0s"
    if seconds < 60:
        return f"{seconds:.1f}s"
    minutes = int(seconds // 60)
    secs = int(seconds % 60)
    if minutes < 60:
        return f"{minutes}m {secs}s"
    hours = minutes // 60
    minutes = minutes % 60
    return f"{hours}h {minutes}m {secs}s"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="data-acquisition")
    subparsers = parser.add_subparsers(dest="command", required=True)

    p_download = subparsers.add_parser("download", help="Download datasets")
    p_download.add_argument("source", help="Source name")
    p_download.add_argument("--version", "-v", default="latest", help="Version")
    p_download.add_argument("--url", help="Download URL")
    p_download.add_argument("--output", "-o", help="Output directory")

    p_list = subparsers.add_parser("list", help="List datasets")
    p_list.add_argument("--category", "-c", help="Filter by category")
    p_list.add_argument("--active-only", action="store_true", default=True)

    p_describe = subparsers.add_parser("describe", help="Describe a dataset")
    p_describe.add_argument("source", help="Source name")
    p_describe.add_argument("--version", "-v", help="Version")

    p_parse = subparsers.add_parser("parse", help="Parse a dataset")
    p_parse.add_argument("source", help="Source name")
    p_parse.add_argument("input", type=Path, help="Input path")
    p_parse.add_argument("output", type=Path, help="Output path")

    p_register = subparsers.add_parser("register", help="Register a dataset")
    p_register.add_argument("dataset_name", help="Dataset name")
    p_register.add_argument("--source", required=True, help="Source name")
    p_register.add_argument("--version", required=True, help="Version")
    p_register.add_argument("--path", type=Path, required=True, help="Path to processed data")

    p_build = subparsers.add_parser("build", help="Build a training dataset")
    p_build.add_argument("dataset_name", help="Dataset name")
    p_build.add_argument("--version", "-v", default="1", help="Version")

    p_validate = subparsers.add_parser("validate", help="Validate a dataset")
    p_validate.add_argument("path", type=Path, help="Path to dataset")
    p_validate.add_argument("--source", help="Source name")

    p_info = subparsers.add_parser("info", help="Show system information")
    p_info.add_argument("--source", help="Filter by source")

    p_config = subparsers.add_parser("config", help="Show configuration")

    return parser


class TestSubcommands:
    def test_all_subcommands_registered(self):
        parser = build_parser()
        expected = {"download", "list", "describe", "parse", "register", "build", "validate", "info", "config"}
        choices = parser._subparsers._group_actions[0].choices
        for cmd in expected:
            assert cmd in choices, f"subcommand '{cmd}' not registered"

    def test_main_no_command_fails(self):
        parser = build_parser()
        with pytest.raises(SystemExit):
            parser.parse_args([])

    def test_main_download_command(self):
        parser = build_parser()
        args = parser.parse_args(["download", "gdelt-events", "--version", "v2", "--url", "http://example.com"])
        assert args.command == "download"
        assert args.source == "gdelt-events"
        assert args.version == "v2"
        assert args.url == "http://example.com"

    def test_main_list_command(self):
        parser = build_parser()
        args = parser.parse_args(["list", "--category", "energy"])
        assert args.command == "list"
        assert args.category == "energy"

    def test_main_list_command_no_filter(self):
        parser = build_parser()
        args = parser.parse_args(["list"])
        assert args.command == "list"
        assert args.category is None

    def test_main_describe_command(self):
        parser = build_parser()
        args = parser.parse_args(["describe", "eia-petroleum", "--version", "1.0"])
        assert args.command == "describe"
        assert args.source == "eia-petroleum"
        assert args.version == "1.0"

    def test_main_parse_command(self, tmp_path):
        parser = build_parser()
        inp = tmp_path / "input.csv"
        out = tmp_path / "output"
        args = parser.parse_args(["parse", "opec", str(inp), str(out)])
        assert args.command == "parse"
        assert args.source == "opec"

    def test_main_register_command(self, tmp_path):
        parser = build_parser()
        p = tmp_path / "data"
        args = parser.parse_args(["register", "test_ds", "--source", "eia", "--version", "1", "--path", str(p)])
        assert args.command == "register"
        assert args.dataset_name == "test_ds"
        assert args.source == "eia"

    def test_main_build_command(self):
        parser = build_parser()
        args = parser.parse_args(["build", "energy_dataset", "--version", "2"])
        assert args.command == "build"
        assert args.dataset_name == "energy_dataset"
        assert args.version == "2"

    def test_main_validate_command(self, tmp_path):
        parser = build_parser()
        p = tmp_path / "data.csv"
        p.write_text("a,b\n1,2\n")
        args = parser.parse_args(["validate", str(p)])
        assert args.command == "validate"
        assert args.path == p

    def test_main_info_command(self):
        parser = build_parser()
        args = parser.parse_args(["info"])
        assert args.command == "info"

    def test_main_info_with_source(self):
        parser = build_parser()
        args = parser.parse_args(["info", "--source", "gdelt"])
        assert args.source == "gdelt"

    def test_main_config_command(self):
        parser = build_parser()
        args = parser.parse_args(["config"])
        assert args.command == "config"


class TestFormatBytes:
    def test_zero_bytes(self):
        assert FormatBytes(0) == "0.0 B"

    def test_bytes(self):
        assert FormatBytes(500) == "500.0 B"

    def test_kilobytes(self):
        result = FormatBytes(2048)
        assert "KB" in result
        assert result == "2.0 KB"

    def test_megabytes(self):
        result = FormatBytes(1048576)
        assert "MB" in result
        assert result == "1.0 MB"

    def test_gigabytes(self):
        result = FormatBytes(1073741824)
        assert "GB" in result
        assert result == "1.0 GB"

    def test_terabytes(self):
        result = FormatBytes(1099511627776)
        assert "TB" in result

    def test_negative(self):
        assert FormatBytes(-100) == "0 B"

    def test_large_petabytes(self):
        result = FormatBytes(1125899906842624)
        assert "PB" in result

    def test_fractional_kb(self):
        result = FormatBytes(1500)
        assert "KB" in result
        assert result == "1.5 KB"

    def test_exact_1024(self):
        result = FormatBytes(1024)
        assert result == "1.0 KB"


class TestFormatDuration:
    def test_zero(self):
        assert FormatDuration(0) == "0.0s"

    def test_seconds_only(self):
        assert FormatDuration(45.5) == "45.5s"

    def test_minutes_and_seconds(self):
        assert FormatDuration(125) == "2m 5s"

    def test_hours_minutes_seconds(self):
        assert FormatDuration(3661) == "1h 1m 1s"

    def test_exact_minute(self):
        assert FormatDuration(60) == "1m 0s"

    def test_exact_hour(self):
        assert FormatDuration(3600) == "1h 0m 0s"

    def test_negative(self):
        assert FormatDuration(-10) == "0s"

    def test_fractional_seconds(self):
        assert FormatDuration(0.5) == "0.5s"

    def test_large_duration(self):
        result = FormatDuration(100000)
        assert "h" in result
        assert "m" in result
        assert "s" in result
