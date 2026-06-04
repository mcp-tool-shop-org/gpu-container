<p align="center">
  <a href="README.ja.md">日本語</a> | <a href="README.zh.md">中文</a> | <a href="README.es.md">Español</a> | <a href="README.md">English</a> | <a href="README.hi.md">हिन्दी</a> | <a href="README.it.md">Italiano</a> | <a href="README.pt-BR.md">Português (BR)</a>
</p>

<div align="center">

<img src="https://raw.githubusercontent.com/mcp-tool-shop-org/gpu-container/main/assets/logo.png" width="400" alt="gpu-container" />

[![CI](https://github.com/mcp-tool-shop-org/gpu-container/actions/workflows/ci.yml/badge.svg)](https://github.com/mcp-tool-shop-org/gpu-container/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/gpu-container)](https://pypi.org/project/gpu-container/)
[![npm](https://img.shields.io/npm/v/gpu-container)](https://www.npmjs.com/package/gpu-container)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Handbook](https://img.shields.io/badge/handbook-docs-blue)](https://mcp-tool-shop-org.github.io/gpu-container/)

**Un conteneur compatible GPU expose le périphérique. Un environnement d’exécution prenant en compte le modèle détermine ce qui est stocké dans la VRAM, la RAM et le NVMe.**

</div>

Exécutez le modèle local utile le plus volumineux que votre machine puisse réellement prendre en charge, avec des plans de placement explicites, des rapports de référence et un refus si le plan risque de provoquer des problèmes.

## Architecture

```
Windows / WSL2 / Linux host
  └─ GPU-enabled Docker container
      └─ Inference runtime
          ├─ VRAM: hot weights, active layers, activations, KV working set
          ├─ pinned RAM: CPU-offloaded weights, MoE experts, KV spill/reuse
          └─ NVMe: mmap shards, disk offload, cold experts, cold KV
```

## Périmètre du produit

```
Docker         = packaging + GPU exposure
CUDA/runtime   = compute backend
Planner        = memory law
Inference engine = execution
```

## Fonctionnalités principales

1. **Analyseur de matériel** — Détecte la VRAM, la RAM, le type de GPU, WSL/Linux natif, la vitesse du NVMe, la disponibilité de CUDA
2. **Analyseur de modèle** — Détecte les modèles denses par rapport aux modèles MoE, la couche la plus grande, le nombre total de paramètres, la quantification, l’augmentation de la taille de la clé en fonction de la longueur du contexte
3. **Planificateur d’exécution** — Génère des plans de lancement pour llama.cpp, vLLM, Accelerate, TensorRT-LLM ou un déchargement de type DeepSpeed
4. **Rapport de placement** — Indique ce qui se trouve dans la VRAM, ce qui se trouve dans la RAM, ce qui se trouve sur le disque, le goulot d’étranglement attendu, le nombre de jetons/seconde mesuré
5. **Chemin spécialisé pour MoE** — Maintient les couches toujours actives sur le GPU, redirige les experts vers le CPU/RAM, NVMe pour une solution de repli
6. **Atténuation des risques liés au routage** — Mesure si le routage MoE d’un modèle est suffisamment biaisé pour qu’un cache par expert soit utile, avant de construire le système en conséquence (`gpu-container-concentration`)
7. **Surveillance de la sécurité du système** — Surveille la puissance/température/VRAM du GPU + la mémoire hôte par rapport aux seuils configurables ; un agent d’IA ou une boucle autonome interrompt une exécution avant qu’elle ne mette en danger la machine (`gpu-container-watchdog`)

## Contrainte principale

Sous Windows/WSL, la surallocation de la mémoire unifiée CUDA n’est **pas la solution**. CUDA traite Windows/WSL comme un support limité de la mémoire unifiée : pas de migration fine des pages GPU, pas de surallocation de la mémoire GPU au-delà de la VRAM physique. Ce produit est un **placement explicite de la mémoire d’inférence**, et non un « débordement de la VRAM Docker ».

## État

Développé et fonctionnel aujourd’hui : `gpu-container-profile`, `gpu-container-plan`, `gpu-container-receipt` (avec la boucle de recalibrage), `gpu-container-concentration` (atténuation des risques liés au routage) et `gpu-container-watchdog` (surveillance sécurisée d’un travail GPU). llama.cpp est le backend intégré ; les calculs de placement sont indépendants du backend. Commencez par le [guide de démarrage rapide](docs/quickstart.md).

## Confidentialité et sécurité

`gpu-container` est un **outil local et hors ligne** : il n’effectue aucune requête réseau et ne collecte **aucune télémétrie**, par défaut ou autre. Il lit les métriques du GPU (`nvidia-smi` / NVML) et la mémoire hôte (`psutil`), le fichier `config.json` du modèle que vous fournissez et les fichiers JSON que vous lui indiquez ; il n’écrit que dans les chemins de sortie que vous spécifiez. Il ne lit ni ne transmet pas les paramètres du modèle, les informations d’identification ou les jetons. Les actions au niveau de l’hôte (`wsl --shutdown`, `docker stop`, `kill`) ne sont exécutées que lorsque vous y consentez explicitement via l’option `--on-breach` du système de surveillance ; par défaut, il ne touche jamais votre machine au-delà du travail qu’il supervise. Politique complète : [SECURITY.md](SECURITY.md).

## Documentation

- [`docs/quickstart.md`](docs/quickstart.md) — guide complet : profilage → planification → lancement sous la surveillance → rapport → recalibrage
- [`docs/cli.md`](docs/cli.md) — les cinq commandes : synopsis, options, codes de sortie, exemples
- [`docs/architecture.md`](docs/architecture.md) — modèle à plusieurs niveaux de mémoire, flux de données, routage des experts MoE, boucle de recalibrage
- [`docs/features.md`](docs/features.md) — les sept fonctionnalités principales en détail
- [`docs/moe-lane-architecture.md`](docs/moe-lane-architecture.md) — la principale architecture de voie MoE en détail
- [`docs/derisk-concentration.md`](docs/derisk-concentration.md) — la porte d’atténuation des risques du cache par expert (concentration du routage)
- [`docs/decisions/0001-per-expert-cache-build-vs-upstream.md`](docs/decisions/0001-per-expert-cache-build-vs-upstream.md) — ADR-0001 : utiliser le mécanisme de cache, contribuer à la politique
- [`docs/constraints.md`](docs/constraints.md) — objectifs non pris en compte + correction de la mémoire unifiée CUDA sous Windows/WSL
- [`docs/prior-art.md`](docs/prior-art.md) — environnements d’exécution que nous orchestrons et le rôle que ce produit remplit
- [`docs/feasibility.md`](docs/feasibility.md) — évaluation de la faisabilité, fondement de la recherche et ce qui a été confirmé en direct

---

<div align="center">

Créé par <a href="https://mcp-tool-shop.github.io/">MCP Tool Shop</a> · Licence MIT

</div>
