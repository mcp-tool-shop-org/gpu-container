import type { SiteConfig } from '@mcptoolshop/site-theme';

export const config: SiteConfig = {
  title: 'gpu-container',
  description:
    'Model-aware inference memory-placement planner for single-GPU rigs — profile the rig + model, plan explicit VRAM/RAM/NVMe placement, and prove it with a measured receipt.',
  logoBadge: 'GC',
  brandName: 'gpu-container',
  repoUrl: 'https://github.com/mcp-tool-shop-org/gpu-container',
  npmUrl: 'https://www.npmjs.com/package/gpu-container',
  footerText:
    'MIT Licensed — built by <a href="https://github.com/mcp-tool-shop-org" style="color:var(--color-muted);text-decoration:underline">mcp-tool-shop-org</a>',

  hero: {
    badge: 'Memory-placement planner · beta',
    headline: 'Run the largest useful model',
    headlineAccent: 'your GPU can honestly support.',
    description:
      "A GPU-enabled container exposes the device; gpu-container decides what lives in VRAM, pinned RAM, and NVMe. It profiles the rig + model, emits an explicit placement plan, proves it with a measured receipt — and refuses when the plan would thrash. Not 'Docker VRAM overflow': explicit, declared placement is the moat.",
    primaryCta: { href: '#usage', label: 'Get started' },
    secondaryCta: { href: 'handbook/', label: 'Read the Handbook' },
    previews: [
      { label: 'Install (PyPI)', code: 'pip install "gpu-container[host]"' },
      { label: 'Install (npx)', code: 'npx gpu-container --help' },
      { label: 'Plan', code: 'gpu-container-plan --profile profile.json --model-config qwen3.json' },
    ],
  },

  sections: [
    {
      kind: 'features',
      id: 'features',
      title: 'Explicit placement, measured proof, honest refusal',
      subtitle: 'Why a gpu-container plan is trustworthy on a single personal rig.',
      features: [
        {
          title: 'Explicit placement',
          desc: 'Every byte has a declared home — VRAM, pinned RAM, or NVMe. CUDA Unified-Memory oversubscription is unavailable on Windows/WSL2 (NVIDIA-confirmed); declared placement is the path.',
        },
        {
          title: 'MoE expert tiering',
          desc: 'The flagship lane: shared/attention layers in VRAM, experts routed to CPU RAM via llama.cpp --n-cpu-moe. Proven live on Qwen3-30B-A3B.',
        },
        {
          title: 'Measured receipts',
          desc: 'A real llama-bench run verifies the plan against a roofline ceiling + calibrated band — and writes a calibration point back so the next plan is sharper.',
        },
        {
          title: 'Honest refusal',
          desc: 'No plan clears >1 tok/s? It refuses and explains why. NVMe is the cold-expert lane, not a dense-weight-streaming lane — sub-1 tok/s there is physics.',
        },
        {
          title: 'Routing de-risk gate',
          desc: 'Before building per-expert caching, measure whether a model\'s routing is even skewed enough to cache. Qwen3 routes near-uniform — so the cache is on hold, with evidence.',
        },
        {
          title: 'Rig-safety watchdog',
          desc: 'Supervise a GPU job: poll GPU power/temp/VRAM + host memory, and abort on a hard breach (kill the job, or the whole VM). Born from a real incident.',
        },
      ],
    },
    {
      kind: 'code-cards',
      id: 'usage',
      title: 'Usage',
      cards: [
        {
          title: 'Install',
          code: 'pip install "gpu-container[host]"\n# or, zero Python:\nnpx gpu-container --help',
        },
        {
          title: 'Profile → plan',
          code: '# in the target container (honest, measured inputs):\ngpu-container-profile --bench-dir /bench -o profile.json\ngpu-container-plan --profile profile.json --model-config qwen3.json --quant gguf-q4_k_m',
        },
        {
          title: 'Launch under the watchdog',
          code: 'gpu-container-watchdog run --on-breach kill-job --peaks-out peaks.json -- \\\n  docker run --rm --gpus all -v "E:/AI-Models:/models" llama.cpp:full-cuda \\\n    llama-bench -m /models/model.gguf --n-cpu-moe 0 -o json > bench.json',
        },
        {
          title: 'Prove it with a receipt',
          code: 'gpu-container-receipt --plan plan.json --bench bench.json --peaks peaks.json \\\n  --model-name Qwen3-30B-A3B --calibration-dir ./calib -o receipt.json',
        },
      ],
    },
  ],
};
