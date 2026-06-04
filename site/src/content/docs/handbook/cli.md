---
title: CLI Reference
description: All five gpu-container commands — flags, exit codes, examples.
sidebar:
  order: 2
---

Five small commands that compose into one pipeline. Each returns a **verdict-coded exit status** (an ANDON contract — a non-zero exit means "stop and look").

## Exit codes at a glance

| Command | `0` | Other |
|---|---|---|
| `gpu-container-profile` | profiled | `2` emit-baseline failed |
| `gpu-container-plan` | **ship** | `3` **refuse** (no plan clears the floor) |
| `gpu-container-receipt` | cleared floor, at/below ceiling | `3` below the >1 tok/s floor · `4` **exceeded** the ceiling (bandwidth model wrong) · `2` bad input |
| `gpu-container-concentration` | cache **NOT** justified (the common "hold") | `5` cache **could** help · `2` bad input |
| `gpu-container-watchdog` (monitor) | ok | `5` warn · `7` **abort** |
| `gpu-container-watchdog run` (supervisor) | job finished, no breach | `7` a breach aborted the job · `2` no command · *else* the job's own exit code |

Every command also accepts `--debug` (show the full traceback on an unexpected error) and renders structured errors as `ERROR [CODE]: message` + a hint — never a raw stack.

## gpu-container-profile

Profile the rig (and a model) into the `profile.json` the planner reads. **Run it inside the target container** for an honest hardware vantage.

```bash
gpu-container-profile [--model-config CONFIG] [--quant TAG] [--no-bench] [--bench-dir DIR] [-o profile.json]
```

Key flags: `--model-config` (HF `config.json`), `--no-bench` (identity only), `--bench-dir` (ext4 volume for the fio NVMe test), `--from-profile X.json --emit-baseline` (record readouts to the KB).

## gpu-container-plan

Turn a profile + model into a llama.cpp `--n-cpu-moe` placement plan with a calibrated forecast and a ship/refuse verdict.

```bash
gpu-container-plan --profile profile.json [--model-config CONFIG] [--quant TAG] [--ctx N] [--hf REF] [--floor TOK_S] [-o plan.json]
```

Key flags: `--ctx` (KV budget, default 4096), `--floor` (refuse below this tok/s, default 1.0), `--cpu-bw` (override measured CPU bandwidth), `--no-calibration` (raw ceiling only).

## gpu-container-receipt

Pair a real `llama-bench` run with the plan's forecast; record realized efficiency + whether the floor cleared; optionally write a calibration point back.

```bash
gpu-container-receipt --plan plan.json [--bench bench.json | --decode-tok-s N] [--trace trace.json] [--peaks peaks.json] [--calibration-dir DIR --model-name NAME] [-o receipt.json]
```

`--trace` folds the per-expert routing de-risk verdict in; `--peaks` folds the supervised run's safety envelope in; `--calibration-dir` + `--model-name` is the recalibration write-back.

## gpu-container-concentration

The per-expert-cache de-risk gate. See [Routing De-risk](./derisk/).

```bash
gpu-container-concentration (--trace trace.json | --imatrix imatrix.gguf) [--model-name NAME] [--coverage F] [--threshold F]
```

Exit `0` = a cache is NOT justified (routing too uniform); `5` = it could help.

## gpu-container-watchdog

The rig-safety control plane — two modes. See [Rig Safety](./safety/).

**Monitor:**
```bash
gpu-container-watchdog [--json] [--watch] [--on-breach ACTION] [--config watchdog.json]
```

**Supervisor** (run a job *under* the watchdog — recommended for any GPU job):
```bash
gpu-container-watchdog run [--on-breach kill-job] [--peaks-out peaks.json] -- <command...>
```

Thresholds (both modes): `--power-max` (95%), `--temp-max` (87°C), `--vram-max` (98%), `--host-mem-max` (90%), `--host-avail-min` (2000 MiB). `--on-breach`: `alert` (monitor default) · `kill-job` (supervisor default) · `wsl-shutdown` · `docker-stop:NAME` · `kill:PID` · `command:CMD`.
