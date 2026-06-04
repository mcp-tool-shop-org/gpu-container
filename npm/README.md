# gpu-container (npm launcher)

Zero-prerequisite launcher for **gpu-container** — a model-aware inference memory-placement planner for single-GPU rigs.

```bash
npx gpu-container --help
npx gpu-container plan --profile profile.json --model-config qwen3.json
```

This npm package is a thin launcher: on first run it downloads the platform binary from the [gpu-container GitHub Release](https://github.com/mcp-tool-shop-org/gpu-container/releases), verifies its SHA256 against the published `checksums-<version>.txt`, caches it, and runs it with full argument passthrough. No Python required.

Prefer Python? `pip install "gpu-container[host]"` installs the five `gpu-container-*` commands directly.

- **Source + docs:** https://github.com/mcp-tool-shop-org/gpu-container
- **Handbook:** https://mcp-tool-shop-org.github.io/gpu-container/handbook/
- **License:** MIT
