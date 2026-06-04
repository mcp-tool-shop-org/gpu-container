"""Tests for the unified `gpu-container <command>` dispatcher (the binary/launcher entry)."""
from gpu_container import __version__
from gpu_container.__main__ import main as gpc


def test_version_help_and_bare_exit_zero(capsys):
    assert gpc(["--version"]) == 0
    assert gpc(["--help"]) == 0
    assert gpc([]) == 0
    out = capsys.readouterr().out
    assert __version__ in out          # --version printed the static package version


def test_unknown_command_exits_2():
    assert gpc(["bogus"]) == 2


def test_routes_to_subcommand():
    # 'concentration' with a missing trace dispatches into that CLI -> its guarded IO error (exit 2).
    assert gpc(["concentration", "--trace", "does-not-exist-xyz.json"]) == 2
