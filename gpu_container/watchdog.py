"""gpu-container-watchdog — a rig-safety control plane for GPU workloads.

Two ways to use it:

  1. **Monitor** (one-shot or `--watch`) — poll GPU + host metrics, compare against thresholds, emit
     an ok/warn/ABORT verdict (exit 0/5/7) that an AI agent or a `--watch` loop reads to halt a job.

  2. **Supervisor** (`run -- <command...>`) — launch a GPU job AS A CHILD, poll metrics in parallel
     while it runs, and on a hard breach act: `kill-job` terminates just the child (a soft abort);
     `wsl-shutdown` nukes the whole VM (the catastrophic case). This makes "run a GPU job safely" one
     command, and records the run's PEAK envelope for the receipt (proof it stayed inside the limits).

Born from the 2026-06-04 incident: a too-large MoE drove host memory to 92-98% and throttled the
machine for over a minute. The lesson, institutionalized — size + WATCH every GPU run, and abort the
instant a hard threshold is crossed. On a WSL2 rig the abort of record is `wsl --shutdown` (instant;
frees all VM RAM in ~5s). The monitor's DEFAULT action is `alert` (surface, never auto-kill); the
supervisor's default is `kill-job` (stop just the job it launched).

Metrics (None when unavailable — never guessed):
  - GPU via `nvidia-smi`: power draw vs board limit (%), temperature, VRAM used/total (%), utilization.
    Multi-GPU rigs are folded WORST-CASE (the hottest/fullest/most-drawing GPU drives the verdict).
  - Host via `psutil` (optional dep): memory % used, available MiB — THE incident metric. `mem_source`
    tags whether psutil is reading the WINDOWS HOST (run the watchdog on Windows — the incident metric
    is the host) or a WSL2 VM / Linux container (run in-container — host coverage is then partial).

VRAM source note: the watchdog reads VRAM via `nvidia-smi memory.used`, which INCLUDES driver-reserved
memory; the profiler (`gpu_container.profiler.hardware`) prefers pynvml v2, which separates `reserved`
from `used`. They agree on `total`; the watchdog's `used` runs a touch higher. That is deliberate — a
safety monitor should read conservative (over-, not under-count), and `nvidia-smi` is always present
on the host where pynvml may not be installed.

Exit code (ANDON, scriptable): 0 = ok, 5 = warn (approaching a limit), 7 = ABORT (a hard limit crossed).
For `run`: 7 = a breach aborted the job; 0 = the job finished with no breach; otherwise the job's own
non-zero exit code (a job that failed on its own, no watchdog involvement).
"""
from __future__ import annotations

import argparse
import json
import platform
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field
from typing import List, Optional

from .errors import GpuContainerError, guard


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
    gpu_count: Optional[int] = None      # GPUs seen; metrics above are the WORST-CASE across them
    host_mem_pct: Optional[float] = None
    host_avail_mib: Optional[float] = None
    mem_source: Optional[str] = None     # "windows-host" | "wsl2-vm" | "linux" — what psutil read
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


def _max(a: Optional[float], b: Optional[float]) -> Optional[float]:
    """None-safe max: a missing reading never lowers (or raises) a peak."""
    if b is None:
        return a
    if a is None:
        return b
    return max(a, b)


def _min(a: Optional[float], b: Optional[float]) -> Optional[float]:
    if b is None:
        return a
    if a is None:
        return b
    return min(a, b)


def sample_nvidia_smi(run=subprocess.run) -> Sample:
    """GPU metrics via nvidia-smi, folded WORST-CASE across all GPUs (the safety-relevant view).

    Each reported percentage keeps its own GPU's absolute pair (power_w/limit, vram_used/total) so the
    numbers stay coherent. Returns an all-None Sample (+ a note) if nvidia-smi is unavailable.
    """
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

    gpus = []
    for line in rows:
        p = [x.strip() for x in line.split(",")]
        if len(p) < 6:
            continue
        pw, lim, temp, used, total, util = (_num(p[0]), _num(p[1]), _num(p[2]),
                                            _num(p[3]), _num(p[4]), _num(p[5]))
        gpus.append({
            "power_w": pw, "limit_w": lim, "temp_c": temp,
            "vram_used": used, "vram_total": total, "util": util,
            "power_pct": round(100.0 * pw / lim, 1) if (pw and lim) else None,
            "vram_pct": round(100.0 * used / total, 1) if (used and total) else None,
        })
    if not gpus:
        s.notes.append("nvidia-smi rows had too few fields — GPU metrics unknown")
        return s

    s.gpu_count = len(gpus)
    # power: the GPU drawing the highest % of its limit (carry its absolute w + limit for a coherent pair)
    pw_gpus = [g for g in gpus if g["power_pct"] is not None]
    if pw_gpus:
        g = max(pw_gpus, key=lambda g: g["power_pct"])
        s.gpu_power_w, s.gpu_power_limit_w, s.gpu_power_pct = g["power_w"], g["limit_w"], g["power_pct"]
    # vram: the fullest GPU (carry its used + total)
    vr_gpus = [g for g in gpus if g["vram_pct"] is not None]
    if vr_gpus:
        g = max(vr_gpus, key=lambda g: g["vram_pct"])
        s.gpu_vram_used_mib, s.gpu_vram_total_mib, s.gpu_vram_pct = g["vram_used"], g["vram_total"], g["vram_pct"]
    temps = [g["temp_c"] for g in gpus if g["temp_c"] is not None]
    utils = [g["util"] for g in gpus if g["util"] is not None]
    s.gpu_temp_c = max(temps) if temps else None
    s.gpu_util_pct = max(utils) if utils else None
    if s.gpu_count > 1:
        s.notes.append(f"worst-case across {s.gpu_count} GPUs")
    return s


def _host_source() -> str:
    """Tag what psutil is actually reading. The 2026-06-04 incident metric is WINDOWS HOST memory;
    run the watchdog on the Windows host for true coverage. In a WSL2/Linux container psutil only
    sees the VM, which can sit calm while the host is starved."""
    if platform.system() == "Windows":
        return "windows-host"
    for path in ("/proc/version", "/proc/sys/kernel/osrelease"):
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                if "microsoft" in f.read().lower():
                    return "wsl2-vm"
        except OSError:
            continue
    return "linux"


def sample_host(into: Sample) -> Sample:
    """Host memory via psutil (optional dep). Leaves host metrics None (+ a note) if psutil is absent,
    and tags `mem_source` so the reading's vantage (host vs VM) is never ambiguous."""
    into.mem_source = _host_source()
    try:
        import psutil
    except ImportError:
        into.notes.append("psutil not installed — host memory unknown (pip install psutil); the "
                          "incident metric IS host memory, so install it for full coverage")
        return into
    vm = psutil.virtual_memory()
    into.host_mem_pct = round(vm.percent, 1)
    into.host_avail_mib = round(vm.available / (1024 * 1024), 1)
    if into.mem_source != "windows-host":
        into.notes.append(f"psutil is reading the {into.mem_source}, NOT the Windows host — the "
                          "2026-06-04 incident metric is HOST memory; run the watchdog on Windows "
                          "for true host coverage")
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


@dataclass
class PeakTracker:
    """Running worst-case envelope over a supervised run — the proof a job stayed inside the limits.
    Fed to the Receipt (A2) so a receipt can say 'decode 302 tok/s; peak host-mem 31%, peak power 41%
    — within envelope.' None-safe: a missing reading never moves a peak."""
    samples: int = 0
    peak_gpu_power_pct: Optional[float] = None
    peak_gpu_power_w: Optional[float] = None
    peak_gpu_temp_c: Optional[float] = None
    peak_gpu_vram_used_mib: Optional[float] = None
    peak_gpu_vram_pct: Optional[float] = None
    peak_gpu_util_pct: Optional[float] = None
    peak_host_mem_pct: Optional[float] = None
    min_host_avail_mib: Optional[float] = None

    def update(self, s: Sample) -> "PeakTracker":
        self.samples += 1
        self.peak_gpu_power_pct = _max(self.peak_gpu_power_pct, s.gpu_power_pct)
        self.peak_gpu_power_w = _max(self.peak_gpu_power_w, s.gpu_power_w)
        self.peak_gpu_temp_c = _max(self.peak_gpu_temp_c, s.gpu_temp_c)
        self.peak_gpu_vram_used_mib = _max(self.peak_gpu_vram_used_mib, s.gpu_vram_used_mib)
        self.peak_gpu_vram_pct = _max(self.peak_gpu_vram_pct, s.gpu_vram_pct)
        self.peak_gpu_util_pct = _max(self.peak_gpu_util_pct, s.gpu_util_pct)
        self.peak_host_mem_pct = _max(self.peak_host_mem_pct, s.host_mem_pct)
        self.min_host_avail_mib = _min(self.min_host_avail_mib, s.host_avail_mib)
        return self

    def to_dict(self) -> dict:
        return asdict(self)


def execute_action(action: str, report: WatchdogReport, run=subprocess.run) -> str:
    """Perform a configured on-breach action that does NOT need the supervised process handle.
    (`kill-job` is handled by the supervisor, which owns the child.) Default 'alert' never kills."""
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
    return (f"unknown action '{action}' — did nothing "
            "(use alert | kill-job | wsl-shutdown | docker-stop:NAME | kill:PID | command:CMD)")


def _terminate_job(proc, grace: float = 5.0) -> str:
    """Stop a supervised child: terminate() (polite), then kill() if it ignores the grace window.

    On Windows both map to TerminateProcess; this stops the direct child. For a containerized job
    (e.g. `docker run ...`) the child is the docker client — prefer `--on-breach docker-stop:NAME`
    or `wsl-shutdown` when you need the whole container/VM gone, not just the launcher.
    """
    if proc.poll() is not None:
        return f"job already exited (rc={proc.poll()})"
    try:
        proc.terminate()
    except OSError as e:
        return f"terminate failed: {e} — INTERVENE MANUALLY"
    try:
        proc.wait(timeout=grace)
        return f"terminated the job (rc={proc.poll()})"
    except subprocess.TimeoutExpired:
        try:
            proc.kill()
            proc.wait(timeout=grace)
            return f"job ignored terminate; killed it (rc={proc.poll()})"
        except (OSError, subprocess.SubprocessError) as e:
            return f"kill failed: {e} — INTERVENE MANUALLY"


@dataclass
class SuperviseResult:
    job_rc: Optional[int]
    verdict: str                 # "ok" | "abort"
    peaks: PeakTracker
    breached: bool = False
    breach: Optional[WatchdogReport] = None


def supervise(command: List[str], t: Thresholds, *, interval: float = 5.0,
              on_breach: str = "kill-job", popen=subprocess.Popen, sampler=sample,
              run=subprocess.run, sleep=time.sleep, emit=None,
              max_polls: Optional[int] = None) -> SuperviseResult:
    """Launch `command`, poll metrics every `interval`s WHILE IT RUNS, and on a hard breach act:
    'kill-job' terminates the child (soft abort); anything else goes through execute_action
    (wsl-shutdown / docker-stop / ...) AND still stops the child. Tracks the run's peak envelope.

    Every external dependency (popen, sampler, run, sleep) is injectable, so the whole loop is
    unit-testable with a fake process and no real GPU.
    """
    proc = popen(command)
    peaks = PeakTracker()
    breach_report: Optional[WatchdogReport] = None
    while True:
        if proc.poll() is not None:
            break                                       # job finished on its own
        rep = evaluate(sampler(), t)
        peaks.update(rep.sample)
        if emit:
            emit(rep)
        if rep.verdict == "abort":
            breach_report = rep
            if on_breach == "kill-job":
                rep.action_taken = _terminate_job(proc)
            else:
                rep.action_taken = execute_action(on_breach, rep, run=run)
                _terminate_job(proc)                    # aborting => always stop the job too
            break
        if max_polls and peaks.samples >= max_polls:
            break
        sleep(max(0.5, interval))
    _terminate_job(proc)                                # never leave the child running
    return SuperviseResult(
        job_rc=proc.poll(), verdict=("abort" if breach_report else "ok"),
        peaks=peaks, breached=breach_report is not None, breach=breach_report,
    )


def _human(r: WatchdogReport) -> str:
    s = r.sample
    bits = []
    if s.gpu_power_pct is not None: bits.append(f"power {s.gpu_power_pct:.0f}%")
    if s.gpu_temp_c is not None: bits.append(f"{s.gpu_temp_c:.0f}C")
    if s.gpu_vram_pct is not None: bits.append(f"vram {s.gpu_vram_pct:.0f}%")
    if s.host_mem_pct is not None: bits.append(f"host-mem {s.host_mem_pct:.0f}%")
    if s.host_avail_mib is not None: bits.append(f"host-free {s.host_avail_mib / 1024:.1f}GiB")
    tag = f" [{s.mem_source}]" if s.mem_source else ""
    if s.gpu_count and s.gpu_count > 1:
        tag += f" [{s.gpu_count}GPU worst-case]"
    br = "; ".join(f"{b.metric}={b.value} vs {b.threshold} ({b.level})" for b in r.breaches)
    return f"[{r.verdict.upper()}]{tag} {', '.join(bits) or 'no metrics'}" + (f" — {br}" if br else "")


def _append_log(path: str, rep: WatchdogReport, elapsed_s: float) -> None:
    """Append one poll to a JSONL trajectory log — so an AI reads the TREND, not just the instant."""
    entry = {
        "elapsed_s": elapsed_s, "t": time.time(), "verdict": rep.verdict,
        "sample": rep.sample.to_dict(),
        "breaches": [asdict(b) for b in rep.breaches],
    }
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _add_threshold_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--config", help="JSON file of threshold overrides (see watchdog.example.json)")
    p.add_argument("--power-max", type=float, help="abort over this %% of the GPU power limit (default 95)")
    p.add_argument("--temp-max", type=float, help="abort over this GPU temperature in C (default 87)")
    p.add_argument("--vram-max", type=float, help="abort over this %% VRAM (default 98)")
    p.add_argument("--host-mem-max", type=float, help="abort over this %% host memory (default 90)")
    p.add_argument("--host-avail-min", type=float, help="abort under this host free MiB (default 2000)")
    p.add_argument("--warn-fraction", type=float, help="warn at this fraction of a limit (default 0.9)")


def _thresholds_from_args(args: argparse.Namespace) -> Thresholds:
    t = Thresholds()
    if getattr(args, "config", None):
        with open(args.config, "r", encoding="utf-8") as f:
            for k, v in json.load(f).items():
                if hasattr(t, k):
                    setattr(t, k, float(v))   # unknown keys (e.g. "_comment") are ignored
    for attr, val in [("power_pct_max", args.power_max), ("gpu_temp_c_max", args.temp_max),
                      ("vram_pct_max", args.vram_max), ("host_mem_pct_max", args.host_mem_max),
                      ("host_avail_mib_min", args.host_avail_min), ("warn_fraction", args.warn_fraction)]:
        if val is not None:
            setattr(t, attr, val)
    return t


def _run_supervise(args: argparse.Namespace) -> int:
    command = list(args.command or [])
    if command and command[0] == "--":     # tolerate the `--` separator argparse may keep
        command = command[1:]
    if not command:
        raise GpuContainerError("INPUT_NO_COMMAND", "no command to supervise",
                                hint="usage: gpu-container-watchdog run [opts] -- <command...>")
    t = _thresholds_from_args(args)
    t0 = time.monotonic()

    def emit(rep: WatchdogReport) -> None:
        if args.json:
            print(rep.to_json())
        else:
            print(_human(rep), file=sys.stderr)
        for n in rep.sample.notes:
            print(f"  note: {n}", file=sys.stderr)
        if args.log:
            _append_log(args.log, rep, round(time.monotonic() - t0, 2))

    print(f"supervising (on-breach={args.on_breach}): {' '.join(command)}", file=sys.stderr)
    res = supervise(command, t, interval=args.interval, on_breach=args.on_breach, emit=emit)

    if args.peaks_out:
        payload = res.peaks.to_dict()
        payload.update({"breached": res.breached, "stayed_within_envelope": not res.breached,
                        "on_breach": args.on_breach, "thresholds": t.to_dict()})
        with open(args.peaks_out, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        print(f"wrote peaks -> {args.peaks_out} "
              f"(feed it to `gpu-container-receipt --peaks {args.peaks_out}`)", file=sys.stderr)

    if res.breached:
        print(f"ABORT: {res.breach.action_taken}", file=sys.stderr)
        return _EXIT["abort"]                         # 7 — the safety verdict dominates
    if res.job_rc:                                    # job's own non-zero exit (no watchdog breach)
        print(f"job exited {res.job_rc} (no watchdog breach)", file=sys.stderr)
        return res.job_rc
    return 0


def _main(argv: Optional[List[str]] = None) -> int:
    for _stream in (sys.stdout, sys.stderr):
        try:
            _stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass

    ap = argparse.ArgumentParser(
        prog="gpu-container-watchdog",
        description="Rig-safety control plane: watch GPU+host metrics, abort on a hard-threshold breach.",
    )
    _add_threshold_args(ap)
    ap.add_argument("--debug", action="store_true", help="show the full traceback on an unexpected error")
    ap.add_argument("--watch", action="store_true", help="loop until a breach (else a single one-shot reading)")
    ap.add_argument("--interval", type=float, default=5.0, help="--watch poll seconds (default 5)")
    ap.add_argument("--max-polls", type=int, help="--watch: stop after N polls (default: until breach/interrupt)")
    ap.add_argument("--on-breach", default="alert",
                    help="alert | wsl-shutdown | docker-stop:NAME | kill:PID | command:CMD (default alert — no kill)")
    ap.add_argument("--json", action="store_true", help="emit the JSON report per poll (else a human line)")
    ap.add_argument("--log", help="append each poll as a JSONL line here (the rolling trajectory)")

    sub = ap.add_subparsers(dest="mode")
    rp = sub.add_parser("run", help="supervise a command: launch it, poll metrics in parallel, act on a breach")
    _add_threshold_args(rp)
    rp.add_argument("--interval", type=float, default=5.0, help="poll seconds while the job runs (default 5)")
    rp.add_argument("--on-breach", default="kill-job",
                    help="kill-job (terminate the child — default) | wsl-shutdown | docker-stop:NAME | alert | command:CMD")
    rp.add_argument("--json", action="store_true", help="emit the JSON report per poll")
    rp.add_argument("--log", help="append each poll as a JSONL line here (the rolling trajectory)")
    rp.add_argument("--peaks-out", help="write the run's peak-metrics JSON here (feed to gpu-container-receipt --peaks)")
    rp.add_argument("--debug", action="store_true", help="show the full traceback on an unexpected error")
    rp.add_argument("command", nargs=argparse.REMAINDER, help="the command to supervise, after `--`")

    args = ap.parse_args(argv)
    if getattr(args, "mode", None) == "run":
        return _run_supervise(args)

    # --- legacy monitor: one-shot or --watch ---------------------------------
    t = _thresholds_from_args(args)
    t0 = time.monotonic()

    def one() -> WatchdogReport:
        rep = evaluate(sample(), t)
        print(rep.to_json() if args.json else _human(rep), file=sys.stdout if args.json else sys.stderr)
        for n in rep.sample.notes:
            print(f"  note: {n}", file=sys.stderr)
        if args.log:
            _append_log(args.log, rep, round(time.monotonic() - t0, 2))
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


def main(argv: Optional[List[str]] = None) -> int:
    return guard(_main, argv)


if __name__ == "__main__":
    raise SystemExit(main())
