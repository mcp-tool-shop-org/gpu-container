"""Tests for the rig-safety watchdog — pure verdict logic, multi-GPU folding, the PeakTracker
envelope, and the supervise loop (mocked: no GPU, no real process)."""
import argparse
import json
import os
import subprocess

from gpu_container import watchdog
from gpu_container.watchdog import (
    PeakTracker, Sample, Thresholds, WatchdogReport, _append_log, _host_source, _terminate_job,
    _thresholds_from_args, evaluate, execute_action, main, sample_host, sample_nvidia_smi, supervise,
)


# --- pure evaluate() verdict logic --------------------------------------------------------------

def test_all_calm_is_ok():
    s = Sample(gpu_power_pct=50, gpu_temp_c=60, gpu_vram_pct=55, host_mem_pct=40, host_avail_mib=20000)
    r = evaluate(s, Thresholds())
    assert r.verdict == "ok"
    assert not r.breaches


def test_power_over_limit_aborts():
    r = evaluate(Sample(gpu_power_pct=96), Thresholds())
    assert r.verdict == "abort"
    assert any(b.metric == "gpu_power_pct" and b.level == "abort" for b in r.breaches)


def test_host_memory_high_aborts():
    r = evaluate(Sample(host_mem_pct=92), Thresholds())          # THE incident metric
    assert r.verdict == "abort"
    assert any(b.metric == "host_mem_pct" for b in r.breaches)


def test_host_available_low_aborts():
    r = evaluate(Sample(host_avail_mib=1500), Thresholds())
    assert r.verdict == "abort"
    assert any(b.metric == "host_avail_mib" and b.level == "abort" for b in r.breaches)


def test_approaching_limit_warns_not_aborts():
    r = evaluate(Sample(gpu_power_pct=88), Thresholds())         # 88 in [0.9*95=85.5, 95)
    assert r.verdict == "warn"
    assert r.breaches and r.breaches[0].level == "warn"


def test_none_metrics_are_skipped():
    r = evaluate(Sample(gpu_power_pct=99), Thresholds())         # only power set; rest None -> skipped
    assert r.verdict == "abort"
    assert len(r.breaches) == 1


def test_config_override_tightens():
    r = evaluate(Sample(gpu_power_pct=60), Thresholds(power_pct_max=50))
    assert r.verdict == "abort"


# --- on-breach actions --------------------------------------------------------------------------

def test_default_action_is_alert_only_and_runs_nothing():
    called = []
    msg = execute_action("alert", WatchdogReport(verdict="abort"), run=lambda *a, **k: called.append(a))
    assert "alert" in msg.lower()
    assert not called                                            # 'alert' must never execute a kill


def test_wsl_shutdown_action_invokes_the_runner():
    calls = []
    msg = execute_action("wsl-shutdown", WatchdogReport(verdict="abort"),
                         run=lambda *a, **k: calls.append(a[0]))
    assert calls == [["wsl", "--shutdown"]]
    assert "wsl --shutdown" in msg


def test_report_serializes_to_json():
    d = evaluate(Sample(gpu_power_pct=50, host_mem_pct=40), Thresholds()).to_dict()
    assert d["verdict"] == "ok"
    assert "sample" in d and "breaches" in d


# --- multi-GPU worst-case folding (A3) ----------------------------------------------------------

def _run_returning(stdout, rc=0):
    class _Out:
        def __init__(self):
            self.stdout, self.returncode = stdout, rc
    return lambda *a, **k: _Out()


def test_single_gpu_parses():
    s = sample_nvidia_smi(run=_run_returning("14.16, 575.0, 28, 2123, 32607, 1"))
    assert s.gpu_count == 1
    assert s.gpu_power_pct == 2.5
    assert s.gpu_vram_pct == 6.5
    assert not any("worst-case" in n for n in s.notes)


def test_multi_gpu_takes_worst_case():
    out = "100.0, 575.0, 60, 5000, 32607, 50\n450.0, 575.0, 80, 30000, 32607, 99"
    s = sample_nvidia_smi(run=_run_returning(out))
    assert s.gpu_count == 2
    assert s.gpu_power_pct == 78.3 and s.gpu_power_w == 450.0      # GPU1 drew more
    assert s.gpu_vram_pct == 92.0 and s.gpu_vram_used_mib == 30000  # GPU1 fuller
    assert s.gpu_temp_c == 80 and s.gpu_util_pct == 99
    assert any("worst-case across 2 GPUs" in n for n in s.notes)


def test_nvidia_smi_unavailable_is_all_none_with_note():
    def _raise(*a, **k):
        raise OSError("no nvidia-smi")
    s = sample_nvidia_smi(run=_raise)
    assert s.gpu_power_pct is None and s.gpu_count is None
    assert any("unavailable" in n for n in s.notes)


def test_nvidia_smi_nonzero_exit_is_none_with_note():
    s = sample_nvidia_smi(run=_run_returning("", rc=9))
    assert s.gpu_power_pct is None
    assert any("exit 9" in n for n in s.notes)


def test_na_field_stays_none_not_zero():
    s = sample_nvidia_smi(run=_run_returning("[N/A], 575.0, 28, 2123, 32607, 1"))
    assert s.gpu_power_pct is None          # power.draw N/A -> unknown, never 0
    assert s.gpu_vram_pct == 6.5            # the readable metrics still come through


# --- host-source tagging (A3) -------------------------------------------------------------------

def test_host_source_windows(monkeypatch):
    monkeypatch.setattr(watchdog.platform, "system", lambda: "Windows")
    assert _host_source() == "windows-host"


def test_host_source_is_a_known_tag():
    assert _host_source() in {"windows-host", "wsl2-vm", "linux"}


def test_sample_host_tags_mem_source():
    s = sample_host(Sample())
    assert s.mem_source in {"windows-host", "wsl2-vm", "linux"}


# --- PeakTracker envelope (A2) ------------------------------------------------------------------

def test_peak_tracker_tracks_worst_case_none_safe():
    pt = PeakTracker()
    pt.update(Sample(gpu_power_pct=10, host_mem_pct=20, host_avail_mib=50000))
    pt.update(Sample(gpu_power_pct=40, host_mem_pct=None, host_avail_mib=30000))  # None must not move a peak
    pt.update(Sample(gpu_power_pct=25, host_mem_pct=35, host_avail_mib=None))
    assert pt.samples == 3
    assert pt.peak_gpu_power_pct == 40
    assert pt.peak_host_mem_pct == 35
    assert pt.min_host_avail_mib == 30000      # min over the non-None readings


def test_peak_tracker_all_none_stays_none():
    pt = PeakTracker()
    pt.update(Sample())
    assert pt.samples == 1
    assert pt.peak_host_mem_pct is None and pt.min_host_avail_mib is None


# --- supervise loop + kill-job (A1) -------------------------------------------------------------

class FakeProc:
    """A stand-in subprocess: poll()/terminate()/kill()/wait() with no real process."""
    def __init__(self, rc=0, finish_after=None, ignore_terminate=False):
        self._rc = rc
        self.finish_after = finish_after        # poll() returns rc once polled > finish_after times
        self.ignore_terminate = ignore_terminate  # terminate() does nothing -> forces the kill() path
        self.poll_calls = 0
        self.terminated = self.killed = False
        self._done = False

    def poll(self):
        self.poll_calls += 1
        if self._done:
            return self._rc
        if self.finish_after is not None and self.poll_calls > self.finish_after:
            self._done = True
            return self._rc
        return None

    def terminate(self):
        self.terminated = True
        if not self.ignore_terminate:
            self._done = True

    def kill(self):
        self.killed = True
        self._done = True

    def wait(self, timeout=None):
        if self.ignore_terminate and not self.killed:
            raise subprocess.TimeoutExpired(cmd="fake", timeout=timeout)
        self._done = True
        return self._rc


_NOSLEEP = lambda *a, **k: None


def test_supervise_kill_job_on_breach_terminates_child():
    proc = FakeProc()
    res = supervise(["job"], Thresholds(), on_breach="kill-job",
                    popen=lambda c: proc, sampler=lambda: Sample(host_mem_pct=99),  # instant abort
                    sleep=_NOSLEEP)
    assert res.breached and res.verdict == "abort"
    assert proc.terminated                          # the JOB was killed, not the VM
    assert res.peaks.samples == 1
    assert "terminated" in res.breach.action_taken


def test_supervise_clean_completion_is_ok():
    proc = FakeProc(rc=0, finish_after=2)            # job exits on its own after 2 polls
    res = supervise(["job"], Thresholds(), popen=lambda c: proc,
                    sampler=lambda: Sample(host_mem_pct=10, gpu_power_pct=5), sleep=_NOSLEEP)
    assert not res.breached and res.verdict == "ok"
    assert res.job_rc == 0
    assert res.peaks.samples == 2
    assert not proc.terminated                        # finished naturally — nothing to kill


def test_supervise_propagates_job_failure_without_breach():
    proc = FakeProc(rc=3, finish_after=1)
    res = supervise(["job"], Thresholds(), popen=lambda c: proc,
                    sampler=lambda: Sample(host_mem_pct=10), sleep=_NOSLEEP)
    assert not res.breached
    assert res.job_rc == 3                             # the job's own failure is preserved


def test_supervise_max_polls_stops_and_kills():
    proc = FakeProc()                                 # never finishes on its own
    res = supervise(["job"], Thresholds(), popen=lambda c: proc,
                    sampler=lambda: Sample(host_mem_pct=10), sleep=_NOSLEEP, max_polls=3)
    assert not res.breached
    assert res.peaks.samples == 3
    assert proc.terminated                            # supervise never leaves the child running


def test_supervise_nonkill_action_runs_and_also_kills_job():
    proc = FakeProc()
    calls = []
    res = supervise(["job"], Thresholds(), on_breach="wsl-shutdown", popen=lambda c: proc,
                    sampler=lambda: Sample(host_mem_pct=99),
                    run=lambda *a, **k: calls.append(a[0]), sleep=_NOSLEEP)
    assert res.breached
    assert ["wsl", "--shutdown"] in calls             # catastrophic action fired
    assert proc.terminated                            # AND the job was stopped


# --- _terminate_job mechanics -------------------------------------------------------------------

def test_terminate_job_already_exited():
    proc = FakeProc(rc=0, finish_after=0)             # first poll() reports it already gone
    msg = _terminate_job(proc)
    assert "already exited" in msg
    assert not proc.terminated


def test_terminate_job_kills_when_terminate_ignored():
    proc = FakeProc(ignore_terminate=True)
    msg = _terminate_job(proc, grace=0.01)
    assert proc.terminated and proc.killed
    assert "killed" in msg


# --- config + rolling log (A3) ------------------------------------------------------------------

def _args(**kw):
    base = dict(config=None, power_max=None, temp_max=None, vram_max=None,
                host_mem_max=None, host_avail_min=None, warn_fraction=None)
    base.update(kw)
    return argparse.Namespace(**base)


def test_shipped_example_config_loads_and_ignores_comment():
    path = os.path.join(os.path.dirname(__file__), "..", "watchdog.example.json")
    t = _thresholds_from_args(_args(config=path))      # the _comment key must be ignored, not crash
    assert t.host_mem_pct_max == 90.0
    assert t.power_pct_max == 95.0


def test_cli_flags_override_thresholds():
    t = _thresholds_from_args(_args(host_mem_max=80.0, power_max=70.0))
    assert t.host_mem_pct_max == 80.0 and t.power_pct_max == 70.0


def test_append_log_writes_parseable_jsonl(tmp_path):
    p = tmp_path / "trail.jsonl"
    rep = evaluate(Sample(gpu_power_pct=50, host_mem_pct=40), Thresholds())
    _append_log(str(p), rep, elapsed_s=1.5)
    _append_log(str(p), rep, elapsed_s=2.5)
    lines = p.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2                             # appends, one JSON object per poll
    entry = json.loads(lines[0])
    assert entry["verdict"] == "ok" and entry["elapsed_s"] == 1.5
    assert "sample" in entry and "breaches" in entry


# --- CLI guardrail ------------------------------------------------------------------------------

def test_run_subcommand_without_command_errors():
    assert main(["run"]) == 2                          # no command after `run` -> exit 2, no subprocess
