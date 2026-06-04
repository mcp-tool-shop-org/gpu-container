# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| 0.1.x (pre-release) | Yes — current development line |

Once 1.0.0 ships, the latest minor release is supported.

## Reporting a Vulnerability

Email: **64996768+mcp-tool-shop@users.noreply.github.com**

Include:
- Description of the vulnerability
- Steps to reproduce
- Version affected
- Potential impact

### Response timeline

| Action | Target |
|--------|--------|
| Acknowledge report | 48 hours |
| Assess severity | 7 days |
| Release fix | 30 days |

These are best-effort targets for a small studio project, not a contractual SLA.

## Scope / threat model

`gpu-container` is a **local, offline planning tool**. It profiles your rig, plans memory placement, and verifies it with a measured receipt.

- **Data touched:** local JSON files you point it at (`profile.json` / `plan.json` / `bench.json` / `receipt.json` / a calibration directory), GPU metrics read via `nvidia-smi` / pynvml, host memory read via `psutil`, and a model's HuggingFace `config.json` you supply. It writes only to the output paths you specify.
- **Data NOT touched:** no model weights are read or transmitted; no credentials, tokens, or API keys are read, stored, or sent.
- **No network egress.** The package makes no outbound network calls. The only subprocesses it invokes are local rig tools — `nvidia-smi`, `fio`, `llama-bench`/`llama-imatrix`, and (only when you opt in) `wsl`/`docker`.
- **No telemetry** of any kind is collected or sent — by default or otherwise.
- **Dangerous actions are opt-in.** The watchdog's default action is `alert` (monitor) / `kill-job` (supervisor — terminates only the child process it launched). Host-level kills (`wsl --shutdown`, `docker stop`, `kill <pid>`) run **only** when you explicitly pass `--on-breach <action>`.
- **Optional dependencies:** the `[gpu]` (pynvml), `[host]` (psutil + numpy), and `gguf` (the `--imatrix` path) extras are read-only introspection libraries.
