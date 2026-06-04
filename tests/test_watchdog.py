"""Tests for the rig-safety watchdog — the pure evaluate() verdict logic (no GPU needed)."""
from gpu_container.watchdog import Sample, Thresholds, WatchdogReport, evaluate, execute_action


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
