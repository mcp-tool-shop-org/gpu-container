"""Tests for the `gpu-container-concentration` CLI (the de-risk gate as a command).

Exercises the --trace path + exit-code contract (0 = hold, 5 = cache could help, 2 = input error).
The --imatrix path needs the optional `gguf` package + a real .gguf, so it is validated by the live
imatrix capture run (ADR-0001), not here.
"""
import json

from gpu_container.planner.concentration_cli import main
from gpu_container.planner.activation import ActivationTrace, LayerActivation


def _write_trace(path, counts, n_layers=8, E=64):
    tr = ActivationTrace(model="t", num_experts=E, experts_per_token=8, n_tokens=1000,
                         layers=[LayerActivation(i, list(counts)) for i in range(n_layers)])
    path.write_text(tr.to_json(), encoding="utf-8")


def test_uniform_exits_0_and_writes_report(tmp_path):
    t = tmp_path / "u.json"
    _write_trace(t, [125] * 64)
    out = tmp_path / "rep.json"
    rc = main(["--trace", str(t), "-o", str(out)])
    assert rc == 0
    rep = json.loads(out.read_text(encoding="utf-8"))
    assert rep["cache_helps"] is False
    assert rep["num_experts"] == 64


def test_concentrated_exits_5(tmp_path):
    t = tmp_path / "c.json"
    _write_trace(t, [950] * 8 + [7] * 56)
    assert main(["--trace", str(t)]) == 5


def test_missing_trace_exits_2(tmp_path):
    assert main(["--trace", str(tmp_path / "nope.json")]) == 2


def test_threshold_flips_verdict(tmp_path):
    # a moderately-skewed layer: ~75% of experts cover 90% — passes a loose bar, fails a strict one
    t = tmp_path / "m.json"
    _write_trace(t, [300] * 16 + [40] * 48)
    assert main(["--trace", str(t), "--threshold", "0.9"]) == 5
    assert main(["--trace", str(t), "--threshold", "0.1"]) == 0
