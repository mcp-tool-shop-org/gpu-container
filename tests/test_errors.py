"""Tests for the structured-error contract (shipcheck B1) + the CLI guard (B3)."""
import pytest

from gpu_container.errors import GpuContainerError, guard


def test_error_renders_code_message_hint_cause_retryable():
    e = GpuContainerError("INPUT_BAD", "bad thing", hint="do better", cause="boom", retryable=True)
    r = e.render()
    assert "ERROR [INPUT_BAD]: bad thing" in r
    assert "hint: do better" in r
    assert "cause: boom" in r
    assert "retryable: yes" in r


def test_error_to_dict_shape():
    d = GpuContainerError("IO_X", "nope").to_dict()
    assert set(d) == {"code", "message", "hint", "cause", "retryable"}
    assert d["code"] == "IO_X" and d["retryable"] is False


def test_guard_passes_through_verdict_codes():
    assert guard(lambda argv: 0, []) == 0
    assert guard(lambda argv: 7, []) == 7          # watchdog abort code passes straight through


def test_guard_renders_structured_error_and_returns_exit_code(capsys):
    def boom(argv):
        raise GpuContainerError("IO_X", "nope", hint="try Y")
    rc = guard(boom, [])
    assert rc == 2                                  # default error exit code
    err = capsys.readouterr().err
    assert "ERROR [IO_X]: nope" in err and "hint: try Y" in err
    assert "Traceback" not in err


def test_guard_honours_custom_exit_code():
    def boom(argv):
        raise GpuContainerError("RUNTIME_X", "y", exit_code=4)
    assert guard(boom, []) == 4


def test_guard_swallows_unexpected_without_debug(capsys):
    def boom(argv):
        raise RuntimeError("kaboom")
    rc = guard(boom, [])                            # no --debug
    assert rc == 2
    err = capsys.readouterr().err
    assert "RUNTIME_UNEXPECTED" in err and "kaboom" in err
    assert "Traceback" not in err                   # gate B3: no raw stack without --debug


def test_guard_reraises_unexpected_with_debug():
    def boom(argv):
        raise RuntimeError("kaboom")
    with pytest.raises(RuntimeError):
        guard(boom, ["--debug"])                    # --debug surfaces the real traceback
