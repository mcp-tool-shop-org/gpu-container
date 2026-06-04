# CLI reference

`gpu-container` is five small commands that compose into one pipeline:

```
profile ─▶ plan ─▶ (launch under) watchdog ─▶ receipt
                         │                        ▲
   concentration ───────┘ (de-risk the per-expert lane, before you build for it)
```

Each command does one thing, reads/writes JSON, and returns a **verdict-coded exit status** (an ANDON contract — a non-zero exit means "stop and look"). The commands are dependency-light: the core runs on the standard library; richer GPU/host introspection and the `--imatrix` path pull optional extras (noted per command).

## Exit codes at a glance

| Command | `0` | Other |
|---|---|---|
| `gpu-container-profile` | profiled | `2` emit-baseline failed |
| `gpu-container-plan` | **ship** | `3` **refuse** (no plan clears the floor) |
| `gpu-container-receipt` | cleared the floor, at/below ceiling | `3` below the >1 tok/s floor · `4` **exceeded** the ceiling (bandwidth model is wrong) · `2` bad input |
| `gpu-container-concentration` | cache **NOT** justified (the common "hold") | `5` cache **could** help · `2` bad input |
| `gpu-container-watchdog` (monitor) | ok | `5` warn · `7` **abort** |
| `gpu-container-watchdog run` (supervisor) | job finished, no breach | `7` a breach aborted the job · `2` no command · *else* the job's own exit code |

> The two "info" codes (`5` for both `concentration` and the watchdog) are deliberate: they say *look closer*, not *fail*. Script them — e.g. `if concentration exits 5, weigh the per-expert cache`.

---

## `gpu-container-profile`

Profile the rig (and, optionally, a model) into the `profile.json` the planner reads.

```
gpu-container-profile [--model-config CONFIG] [--quant TAG] [--no-bench]
                      [--bench-dir DIR] [-o profile.json]
```

**Run it INSIDE the target container.** The PCIe / NVMe / pinnable-RAM benchmarks need the CUDA runtime, `fio`, and an ext4 bench volume the container provides; an honest hardware vantage is the whole point (a measurement you didn't take is `None`, never a spec-sheet guess).

| Flag | Meaning |
|---|---|
| `--model-config CONFIG` | a HuggingFace `config.json` to profile the model side (dense/MoE, experts, KV growth) |
| `--model-name NAME` / `--quant TAG` | override the model name; tag the quant (e.g. `gguf-q4_k_m`) |
| `--no-bench` | identity detection only — skip the PCIe/NVMe/pinnable benchmarks |
| `--bench-dir DIR` | directory for the `fio` NVMe test (an ext4-backed mounted volume; default `$GPU_CONTAINER_BENCH_DIR` or `/bench`) |
| `--from-profile X.json` `--emit-baseline` | record a profile's measured readouts into the docker-knowledge KB (host-side) |
| `-o, --out FILE` | write the JSON here (default: stdout) |

**Exit:** `0` profiled · `2` `--emit-baseline` failed.

```bash
# inside the container, with the bench volume mounted at /bench:
gpu-container-profile --bench-dir /bench -o profile.json
```

Optional extras: `pip install gpu-container[gpu]` (pynvml v2 — separates driver-reserved VRAM from used) and `[host]` (psutil + numpy — system RAM and the CPU-bandwidth probe). Without them the profiler falls back to `nvidia-smi` and `/proc/meminfo`, recording the lower-fidelity source in the profile.

---

## `gpu-container-plan`

Turn a profile (+ model) into a llama.cpp `--n-cpu-moe` placement plan with a calibrated throughput forecast and an honest ship/refuse verdict.

```
gpu-container-plan --profile profile.json [--model-config CONFIG] [--quant TAG]
                   [--ctx N] [--hf REF] [--floor TOK_S] [-o plan.json]
```

| Flag | Meaning |
|---|---|
| `--profile FILE` | **required** — `profile.json` from `gpu-container-profile` |
| `--model-config CONFIG` | HF `config.json` to (re)profile the model side into the plan |
| `--model-name` / `--quant TAG` | name override; quant tag (drives bytes/weight + footprint) |
| `--ctx N` | context length for the KV-cache budget (default `4096`) |
| `--batch N` | batch size (default `1`) |
| `--cpu-bw GBPS` | override measured CPU RAM bandwidth (the offload-throughput input) |
| `--non-expert-bpw F` | bytes/weight for always-resident weights (auto: f16 for mxfp4, else the quant bpw) |
| `--floor TOK_S` | refuse below this decode tok/s (default `1.0`) |
| `--hf REF` | model ref baked into the launch command, e.g. `unsloth/Qwen3-30B-A3B-GGUF:Q4_K_M` |
| `--calibration-dir DIR` | extra calibration receipts to fold in (atop the bundled seed) |
| `--no-calibration` | forecast the raw roofline ceiling only (skip the calibrated band) |
| `-o, --out FILE` | write the plan JSON here (default: stdout) |

**Exit:** `0` **ship** · `3` **refuse**. The plan carries the exact `llama_flags` string, the predicted memory map, a **roofline ceiling** *and* a calibrated forecast band, and a contrastive message on a refusal.

> The ceiling is an **upper bound**, not a point prediction — real decode runs at a fraction of it (see [architecture.md](architecture.md#throughput-calibration--the-recalibration-loop)). Refusal fires only when even the optimistic ceiling can't clear the floor, so a usable model is never refused.

```bash
gpu-container-plan --profile profile.json --model-config qwen3.json \
    --quant gguf-q4_k_m --ctx 4096 --hf unsloth/Qwen3-30B-A3B-GGUF:Q4_K_M -o plan.json
```

---

## `gpu-container-receipt`

The measured proof. Pair a real `llama-bench` run with the plan's forecast, record realized efficiency + whether the floor cleared, and (optionally) write a calibration point back so the next plan for this shape is calibrated. The verifier is a real GPU run — a *different mechanism* than the planner's closed form (EXTERNAL_VERIFIER).

```
gpu-container-receipt --plan plan.json
                      [--bench bench.json | --decode-tok-s N]
                      [--trace trace.json] [--peaks peaks.json]
                      [--calibration-dir DIR --model-name NAME] [-o receipt.json]
```

| Flag | Meaning |
|---|---|
| `--plan FILE` | **required** — the `plan.json` being verified |
| `--bench FILE` | `llama-bench -o json` output (file or `-` for stdin) |
| `--decode-tok-s N` / `--prefill-tok-s N` | measured rates directly, instead of `--bench` |
| `--vram-used-mib N` | measured VRAM use (optional, for the predicted-vs-actual note) |
| `--trace FILE` | an `ActivationTrace` JSON — fold the per-expert routing **de-risk** verdict into the receipt |
| `--coverage F` / `--threshold F` | routing-coverage target / `cache_helps` threshold for `--trace` (defaults `0.90` / `0.50`) |
| `--peaks FILE` | peak-metrics JSON from `watchdog run --peaks-out` — fold the run's **safety envelope** (peak power/host-mem/VRAM) into the receipt |
| `--calibration-dir DIR` + `--model-name NAME` | append a `CalibrationPoint` here — the recalibration write-back |
| `--quant` / `--created` / `--rig` / `--source` | calibration-point provenance |
| `-o, --out FILE` | write the receipt JSON here (default: stdout) |

**Exit:** `0` cleared the floor and sat at/below the ceiling · `3` fell below the >1 tok/s floor (the ship was optimistic) · `4` **exceeded** the ceiling (the bandwidth model itself is wrong — halt and fix assumptions, don't just recalibrate) · `2` bad input.

```bash
# verify a plan, fold in both the routing de-risk and the supervised run's safety envelope,
# and write a calibration point back so the next plan for this shape is calibrated:
gpu-container-receipt --plan plan.json --bench bench.json \
    --trace trace.json --peaks peaks.json \
    --model-name Qwen3-30B-A3B --quant gguf-q4_k_m --calibration-dir ./calib -o receipt.json
```

---

## `gpu-container-concentration`

The per-expert-cache **de-risk gate**, as a command. Given an activation trace (which experts fired, per layer), score routing concentration and answer the prior question for the per-expert lane: would a hot-expert VRAM cache (the llama.cpp [#20757](https://github.com/ggml-org/llama.cpp/issues/20757) mechanism) actually help, or is routing too uniform to bother? Full method: [derisk-concentration.md](derisk-concentration.md).

```
gpu-container-concentration (--trace trace.json | --imatrix imatrix.gguf)
                            [--model-name NAME] [--coverage F] [--threshold F] [-o report.json]
```

| Flag | Meaning |
|---|---|
| `--trace FILE` | an `ActivationTrace` JSON (the L×E per-expert count matrix) — dependency-free |
| `--imatrix FILE` | a `llama-imatrix` `imatrix.gguf`; extracts the per-expert `.counts` directly (needs the optional `gguf` package) |
| `--model-name NAME` | model name (for the `--imatrix` path / the report) |
| `--topk N` | experts/token, for the `--imatrix` token-count estimate (default `8`) |
| `--coverage F` | routing-mass coverage target (default `0.90`) |
| `--threshold F` | `cache_helps` if fewer than this fraction of experts cover the target (default `0.50`) |
| `-o, --out FILE` | write the report JSON here (default: stdout) |

**Exit:** `0` analyzed, a per-expert cache is **NOT** justified (routing too uniform — the common "hold") · `5` analyzed, routing concentrates enough that a cache **could** help · `2` usage/input error.

```bash
# capture once (in the llama.cpp container), then gate:
llama-imatrix -m model.gguf -f corpus.txt -ngl 99 --no-ppl -o imatrix.gguf
gpu-container-concentration --imatrix imatrix.gguf --model-name Qwen3-30B-A3B
```

---

## `gpu-container-watchdog`

The rig-safety control plane. It has two modes.

### Monitor — poll, get a verdict

```
gpu-container-watchdog [--json] [--watch] [--interval N] [--on-breach ACTION]
                       [--config watchdog.json] [--log trail.jsonl] [THRESHOLD OVERRIDES]
```

One-shot (default) prints a single ok/warn/abort verdict and exits; `--watch` loops until a breach. Reads GPU power/temp/VRAM (`nvidia-smi`, worst-case across all GPUs) + host memory (`psutil` — the 2026-06-04 incident metric). The default action is **`alert`** — it surfaces a breach, it never auto-kills.

**Exit:** `0` ok · `5` warn (approaching a limit) · `7` **abort** (a hard limit crossed).

```bash
gpu-container-watchdog --json                     # one-shot, machine-readable
gpu-container-watchdog --watch --on-breach wsl-shutdown   # autonomous abort (opt-in)
```

### Supervisor — run a job *under* the watchdog

```
gpu-container-watchdog run [--on-breach kill-job] [--interval N]
                          [--peaks-out peaks.json] [--log trail.jsonl] [THRESHOLD OVERRIDES]
                          -- <command...>
```

Launches `<command>` as a child, polls metrics **in parallel** while it runs, and on a hard breach takes the action. This makes "run a GPU job safely" one self-monitoring command — **the recommended way to run any GPU job.** The default action is **`kill-job`** (terminate just the child — a soft abort); `wsl-shutdown` stays for the catastrophic case.

**Exit:** `7` a breach aborted the job · `0` the job finished with no breach · *otherwise* the job's own non-zero exit code · `2` no command given.

```bash
gpu-container-watchdog run --on-breach kill-job --peaks-out peaks.json \
    -- docker run --rm --gpus all -v "E:/AI-Models/m:/models" llama.cpp:full-cuda \
       llama-bench -m /models/model.gguf --n-cpu-moe 0 -p 512 -n 128 -o json > bench.json
```

`--peaks-out` writes the run's peak envelope (peak power/host-mem/VRAM, `stayed_within_envelope`) — feed it to `gpu-container-receipt --peaks` so the receipt proves the run stayed inside the rig's limits.

### Thresholds (both modes)

| Flag | Default | Aborts when |
|---|---|---|
| `--power-max PCT` | `95` | GPU power draw ≥ this % of the board limit |
| `--temp-max C` | `87` | GPU temperature ≥ this °C |
| `--vram-max PCT` | `98` | VRAM ≥ this % |
| `--host-mem-max PCT` | `90` | host memory ≥ this % (**the incident metric**) |
| `--host-avail-min MIB` | `2000` | free host/VM RAM drops below this |
| `--warn-fraction F` | `0.9` | within this fraction of a limit ⇒ `warn` |
| `--config FILE` | — | JSON threshold overrides (see [`watchdog.example.json`](../watchdog.example.json)) |

`--on-breach` actions: `alert` (monitor default, no kill) · `kill-job` (supervisor default, terminate the child) · `wsl-shutdown` (instant VM kill — frees all WSL2 RAM in ~5s) · `docker-stop:NAME` · `kill:PID` · `command:CMD`.

> **Run the watchdog on the Windows host.** `psutil` reads whatever it runs on; the incident metric is *host* memory. Run in a WSL2/Linux container and `psutil` only sees the VM — which can sit calm while the host is starved. The sample's `mem_source` field tags which vantage you got.
