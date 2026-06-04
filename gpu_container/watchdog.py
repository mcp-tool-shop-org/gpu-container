"""gpu-container-watchdog — a rig-safety control plane for GPU workloads.

Poll GPU + host metrics, compare against configurable thresholds, and emit an ok/warn/ABORT verdict
that an AI agent (one-shot) or an autonomous `--watch` loop uses to halt a workload before it
endangers the rig.

Born from the 2026-06-04 incident: a too-large MoE drove host memory to 92-98% and throttled the
machine for over a minute. The lesson, institutionalized — size + WATCH every GPU run, and abort the
instant a hard threshold is crossed. On a WSL2 rig the abort of record is `wsl --shutdown` (instant;
frees all VM RAM in ~5s). But the DEFAULT action here is `alert` — surface the breach loudly and let
a human/AI pull the trigger; an auto-kill is strictly opt-in (`--on-breach wsl-shutdown`).

Metrics (None when unavailable — never guessed):
  - GPU via `nvidia-smi`: power draw vs board limit (%), temperature, VRAM used/total (%), utilization.
  - Host via `psutil` (optional dep): memory % used, available MiB — THE incident metric.

Exit code (ANDON, scriptable): 0 = ok, 5 = warn (approaching a limit), 7 = ABORT (a hard limit crossed).
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field
from typing import List, Optional


@dataclass
class Thresholds:
    """Hard limits; a breach => abort. Within `warn_fraction` of a max (or its reciprocal for a min)
    => warn. Defaults tuned for the Robot rig (RTX 5090 / 64 GB / WSL2 28 GB cap) and the incident."""
    power_pct_max: float = 95.0          # GPU power draw as % of the board power limit
    gpu_temp_c_max: float = 87.0
    vram_pct_max: float = 98.0
    host_mem_pct_max: float = 90.0       # the incident hit 92-98%; abort with margin
    host_avail_mib_min: float = 2000.0   # abort if free host/VM RAM drops below this
    warn_fraction: float = 0.9

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Sample:
    gpu_power_w: Optional[float] = None
    gpu_power_limit_w: Optional[float] = None
    gpu_power_pct: Optional[float] = None
    gpu_temp_c: Optional[float] = None
    gpu_vram_used_mib: Optional[float] = None
    gpu_vram_total_mib: Optional[float] = None
    gpu_vram_pct: Optional[float] = None
    gpu_util_pct: Optional[float] = None
    host_mem_pct: Optional[float] = None
    host_avail_mib: Optional[float] = None
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Breach:
    metric: str
    value: float
    threshold: float
    level: str   # "warn" | "abort"


@dataclass
class WatchdogReport:
    verdict: str                 # "ok" | "warn" | "abort"
    breaches: List[Breach] = field(default_factory=list)
    sample: Optional[Sample] = None
    action_taken: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)


def _num(s: str) -> Optional[float]:
    try:
        return float((s or "").strip())
    except ValueError:
        return None   # "[N/A]" and friends -> unknown, never 0


def sample_nvidia_smi(run=subprocess.run) -> Sample:
    """GPU metrics via nvidia-smi. Returns an all-None Sample (+ a note) if nvidia-smi is unavailable."""
    s = Sample()
    q = "power.draw,power.limit,temperature.gpu,memory.used,memory.total,utilization.gpu"
    try:
        out = run(["nvidia-smi", f"--query-gpu={q}", "--format=csv,noheader,nounits"],
                  capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        s.notes.append("nvidia-smi unavailable — GPU metrics unknown")
        return s
    if out.returncode != 0:
        s.notes.append(f"nvidia-smi exit {out.returncode} — GPU metrics unknown")
        return s
    rows = (out.stdout or "").strip().splitlines()
    if not rows:
        s.notes.append("nvidia-smi returned no rows")
        return s
    p = [x.strip() for x in rows[0].split(",")]
    if len(p) >= 6:
        (s.gpu_power_w, s.gpu_power_limit_w, s.gpu_temp_c,
         s.gpu_vram_used_mib, s.gpu_vram_total_mib, s.gpu_util_pct) = (
            _num(p[0]), _num(p[1]), _num(p[2]), _num(p[3]), _num(p[4]), _num(p[5]))
        if s.gpu_power_w and s.gpu_power_limit_w:
            s.gpu_power_pct = round(100.0 * s.gpu_power_w / s.gpu_power_limit_w, 1)
        if s.gpu_vram_used_mib and s.gpu_vram_total_mib:
            s.gpu_vram_pct = round(100.0 * s.gpu_vram_used_mib / s.gpu_vram_total_mib, 1)
    return s


def sample_host(into: Sample) -> Sample:
    """Host memory via psutil (optional dep). Leaves host metrics None (+ a note) if psutil is absent."""
    try:
        import psutil
    except ImportError:
        into.notes.append("psutil not installed — host memory unknown (pip install psutil); the "
                          "incident metric IS host memory, so install it for full coverage")
        return into
    vm = psutil.virtual_memory()
    into.host_mem_pct = round(vm.percent, 1)
    into.host_avail_mib = round(vm.available / (1024 * 1024), 1)
    return into


def sample() -> Sample:
    """One full reading: GPU (nvidia-smi) + host (psutil)."""
    return sample_host(sample_nvidia_smi())


def evaluate(s: Sample, t: Thresholds) -> WatchdogReport:
    """Pure: a Sample + Thresholds -> ok/warn/abort + the breach list. None metrics are skipped."""
    breaches: List[Breach] = []

    def check_max(value, limit, name):
        if value is None:
            return
        if value >= limit:
            breaches.append(Breach(name, value, limit, "abort"))
        elif value >= t.warn_fraction * limit:
            breaches.append(Breach(name, value, round(t.warn_fraction * limit, 1), "warn"))

    def check_min(value, limit, name):
        if value is None:
            return
        if value <= limit:
            breaches.append(Breach(name, value, limit, "abort"))
        elif t.warn_fraction and value <= limit / t.warn_fraction:
            breaches.append(Breach(name, value, round(limit / t.warn_fraction, 1), "warn"))

    check_max(s.gpu_power_pct, t.power_pct_max, "gpu_power_pct")
    check_max(s.gpu_temp_c, t.gpu_temp_c_max, "gpu_temp_c")
    check_max(s.gpu_vram_pct, t.vram_pct_max, "gpu_vram_pct")
    check_max(s.host_mem_pct, t.host_mem_pct_max, "host_mem_pct")
    check_min(s.host_avail_mib, t.host_avail_mib_min, "host_avail_mib")

    if any(b.level == "abort" for b in breaches):
        verdict = "abort"
    elif any(b.level == "warn" for b in breaches):
        verdict = "warn"
    else:
        verdict = "ok"
    return WatchdogReport(verdict=verdict, breaches=breaches, sample=s)


_EXIT = {"ok": 0, "warn": 5, "abort": 7}


def execute_action(action: str, report: WatchdogReport, run=subprocess.run) -> str:
    """Perform the configured on-breach action. Default 'alert' never kills — it only surfaces."""
    if not action or action == "alert":
        return "alert only (no kill) — abort surfaced; a human/AI decides the next move"
    try:
        if action == "wsl-shutdown":
            run(["wsl", "--shutdown"], timeout=30)
            return "ran `wsl --shutdown` (instant VM kill — frees all WSL2 RAM in ~5s)"
        if action.startswith("docker-stop:"):
            name = action.split(":", 1)[1]
            run(["docker", "stop", name], timeout=60)
            return f"ran `docker stop {name}`"
        if action.startswith("kill:"):
            pid = action.split(":", 1)[1]
            run(["kill", "-9", pid], timeout=10)
            return f"killed pid {pid}"
        if action.startswith("command:"):
            cmd = action.split(":", 1)[1]
            run(cmd, shell=True, timeout=60)
            return f"ran `{cmd}`"
    except (OSError, subprocess.SubprocessError) as e:
        return f"action '{action}' FAILED: {e} — INTERVENE MANUALLY"
    return f"unknown action '{action}' — did nothing (use alert | wsl-shutdown | docker-stop:NAME | kill:PID | command:CMD)"


def _human(r: WatchdogReport) -> str:
    s = r.sample
    bits = []
    if s.gpu_power_pct is not None: bits.append(f"power {s.gpu_power_pct:.0f}%")
    if s.gpu_temp_c is not None: bits.append(f"{s.gpu_temp_c:.0f}C")
    if s.gpu_vram_pct is not None: bits.append(f"vram {s.gpu_vram_pct:.0f}%")
    if s.host_mem_pct is not None: bits.append(f"host-mem {s.host_mem_pct:.0f}%")
    if s.host_avail_mib is not None: bits.append(f"host-free {s.host_avail_mib / 1024:.1f}GiB")
    br = "; ".join(f"{b.metric}={b.value} vs {b.threshold} ({b.level})" for b in r.breaches)
    return f"[{r.verdict.upper()}] {', '.join(bits) or 'no metrics'}" + (f" — {br}" if br else "")


def main(argv: Optional[List[str]] = None) -> int:
    for _stream in (sys.stdout, sys.stderr):
        try:
            _stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass

    ap = argparse.ArgumentParser(
        prog="gpu-container-watchdog",
        description="Rig-safety control plane: watch GPU+host metrics, abort on a hard-threshold breach.",
    )
    ap.add_argument("--config", help="JSON file of threshold overrides")
    ap.add_argument("--power-max", type=float, help="abort over this %% of the GPU power limit (default 95)")
    ap.add_argument("--temp-max", type=float, help="abort over this GPU temperature in C (default 87)")
    ap.add_argument("--vram-max", type=float, help="abort over this %% VRAM (default 98)")
    ap.add_argument("--host-mem-max", type=float, help="abort over this %% host memory (default 90)")
    ap.add_argument("--host-avail-min", type=float, help="abort under this host free MiB (default 2000)")
    ap.add_argument("--warn-fraction", type=float, help="warn at this fraction of a limit (default 0.9)")
    ap.add_argument("--watch", action="store_true", help="loop until a breach (else a single one-shot reading)")
    ap.add_argument("--interval", type=float, default=5.0, help="--watch poll seconds (default 5)")
    ap.add_argument("--max-polls", type=int, help="--watch: stop after N polls (default: until breach/interrupt)")
    ap.add_argument("--on-breach", default="alert",
                    help="alert | wsl-shutdown | docker-stop:NAME | kill:PID | command:CMD (default alert — no kill)")
    ap.add_argument("--json", action="store_true", help="emit the JSON report per poll (else a human line)")
    args = ap.parse_args(argv)

    t = Thresholds()
    if args.config:
        with open(args.config, "r", encoding="utf-8") as f:
            for k, v in json.load(f).items():
                if hasattr(t, k):
                    setattr(t, k, float(v))
    for attr, val in [("power_pct_max", args.power_max), ("gpu_temp_c_max", args.temp_max),
                      ("vram_pct_max", args.vram_max), ("host_mem_pct_max", args.host_mem_max),
                      ("host_avail_mib_min", args.host_avail_min), ("warn_fraction", args.warn_fraction)]:
        if val is not None:
            setattr(t, attr, val)

    def one() -> WatchdogReport:
        rep = evaluate(sample(), t)
        print(rep.to_json() if args.json else _human(rep), file=sys.stderr if not args.json else sys.stdout)
        for n in rep.sample.notes:
            print(f"  note: {n}", file=sys.stderr)
        return rep

    if not args.watch:
        return _EXIT[one().verdict]

    polls = 0
    while True:
        rep = one()
        if rep.verdict == "abort":
            rep.action_taken = execute_action(args.on_breach, rep)
            print(f"ABORT: {rep.action_taken}", file=sys.stderr)
            return _EXIT["abort"]
        polls += 1
        if args.max_polls and polls >= args.max_polls:
            return _EXIT[rep.verdict]
        time.sleep(max(0.5, args.interval))


if __name__ == "__main__":
    raise SystemExit(main())
