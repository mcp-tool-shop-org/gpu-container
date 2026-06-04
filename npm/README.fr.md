<p align="center">
  <a href="README.ja.md">日本語</a> | <a href="README.zh.md">中文</a> | <a href="README.es.md">Español</a> | <a href="README.md">English</a> | <a href="README.hi.md">हिन्दी</a> | <a href="README.it.md">Italiano</a> | <a href="README.pt-BR.md">Português (BR)</a>
</p>

<div align="center">

<img src="https://raw.githubusercontent.com/mcp-tool-shop-org/gpu-container/main/assets/logo.png" width="400" alt="gpu-container" />

[![CI](https://github.com/mcp-tool-shop-org/gpu-container/actions/workflows/ci.yml/badge.svg)](https://github.com/mcp-tool-shop-org/gpu-container/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/gpu-container)](https://pypi.org/project/gpu-container/)
[![npm](https://img.shields.io/npm/v/gpu-container)](https://www.npmjs.com/package/gpu-container)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://github.com/mcp-tool-shop-org/gpu-container/blob/main/LICENSE)
[![Handbook](https://img.shields.io/badge/handbook-docs-blue)](https://mcp-tool-shop-org.github.io/gpu-container/)

**Un conteneur compatible GPU expose le périphérique. Un environnement d’exécution prenant en compte le modèle détermine ce qui doit être placé dans la VRAM, la RAM allouée et le NVMe.**

</div

Exécutez le modèle local le plus volumineux et le plus utile que votre machine puisse réellement prendre en charge, avec des plans de placement explicites, des résultats de tests de performance et un refus si le plan risque de provoquer des problèmes. Ce paquet npm est un **lanceur sans prérequis** : `npx gpu-container` télécharge le binaire de la plateforme à partir de [GitHub Release](https://github.com/mcp-tool-shop-org/gpu-container/releases), vérifie son SHA256 par rapport aux sommes de contrôle publiées, le met en cache et l’exécute. **Aucun Python requis.**

```bash
npx gpu-container --help
npx gpu-container plan --profile profile.json --model-config qwen3.json --quant gguf-q4_k_m
```

> Vous préférez Python ? `pip install "gpu-container[host]"` installe directement les cinq commandes `gpu-container-*`.

## Pourquoi il existe

Sur Windows/WSL2, la surallocation de mémoire unifiée CUDA est **indisponible** (confirmé par NVIDIA) et n’est pas l’outil approprié pour le décodage, même sous Linux. Ainsi, `gpu-container` ne repose pas sur une magie d’exécution, mais rend le **placement explicite et déclaré** le produit. C’est sa force.

## Ce qu’il fait

`gpu-container <commande>` est un ensemble de cinq outils dans un seul binaire :

| Commande | Fait |
|---|---|
| `profile` | Mesure la configuration (VRAM, PCIe, NVMe, RAM allouée, bande passante du CPU) + le modèle |
| `plan` | Calcule le placement explicite dans la VRAM/RAM/NVMe + une prévision de débit calibrée ; **accepte ou refuse** |
| `receipt` | Vérifie un plan par rapport à une exécution réelle de `llama-bench` ; enregistre un point de calibration |
| `concentration` | Réduit les risques liés au cache par expert : mesure la concentration du routage avant de construire pour cela |
| `watchdog` | Supervise un travail GPU ; interrompt en cas de dépassement de la mémoire hôte/de la puissance/de la VRAM |

- **Hiérarchisation des experts MoE** (principal) : couches partagées/d’attention dans la VRAM, experts dans la RAM du CPU via llama.cpp `--n-cpu-moe`. Déjà testé en direct sur Qwen3-30B-A3B.
- **Résultats mesurés** : une exécution réelle vérifie la prévision par rapport à une limite *théorique* et une bande passante *calibrée* ; les résultats affinent le plan suivant.
- **Refus honnête** : si aucun plan ne permet d’atteindre > 1 tok/s, il refuse et explique pourquoi.
- **Surveillance de la sécurité de la configuration** : né d’un incident réel ; supervise tout travail GPU afin qu’un mauvais plan ne puisse pas entraîner l’arrêt de la machine.

## Exécutez un travail GPU en toute sécurité

```bash
gpu-container watchdog run --on-breach kill-job --peaks-out peaks.json -- \
  docker run --rm --gpus all -v "E:/AI-Models:/models" ghcr.io/ggml-org/llama.cpp:full-cuda \
    llama-bench -m /models/model.gguf --n-cpu-moe 0 -o json > bench.json
```

## Documentation

- **Guide de démarrage rapide + manuel :** https://mcp-tool-shop-org.github.io/gpu-container/handbook/
- **Code source + documentation complète :** https://github.com/mcp-tool-shop-org/gpu-container
- **Confidentialité et sécurité :** local, hors ligne, pas de télémétrie, pas de transfert de données sur le réseau. [SECURITY.md](https://github.com/mcp-tool-shop-org/gpu-container/blob/main/SECURITY.md)

<div align="center">

Créé par <a href="https://mcp-tool-shop.github.io/">MCP Tool Shop</a> · Licence MIT

</div
