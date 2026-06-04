<p align="center">
  <a href="README.ja.md">日本語</a> | <a href="README.zh.md">中文</a> | <a href="README.es.md">Español</a> | <a href="README.fr.md">Français</a> | <a href="README.hi.md">हिन्दी</a> | <a href="README.md">English</a> | <a href="README.pt-BR.md">Português (BR)</a>
</p>

<div align="center">

<img src="https://raw.githubusercontent.com/mcp-tool-shop-org/gpu-container/main/assets/logo.png" width="400" alt="gpu-container" />

[![CI](https://github.com/mcp-tool-shop-org/gpu-container/actions/workflows/ci.yml/badge.svg)](https://github.com/mcp-tool-shop-org/gpu-container/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/gpu-container)](https://pypi.org/project/gpu-container/)
[![npm](https://img.shields.io/npm/v/gpu-container)](https://www.npmjs.com/package/gpu-container)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://github.com/mcp-tool-shop-org/gpu-container/blob/main/LICENSE)
[![Handbook](https://img.shields.io/badge/handbook-docs-blue)](https://mcp-tool-shop-org.github.io/gpu-container/)

**Un container abilitato per GPU espone il dispositivo. Un runtime consapevole del modello decide cosa deve essere allocato nella VRAM, nella RAM allocata e nella NVMe.**

</div>

Esegui il modello locale più grande e utile che la tua macchina può effettivamente supportare, con piani di allocazione espliciti, risultati dei benchmark e rifiuto nel caso in cui il piano causerebbe problemi. Questo pacchetto npm è un **launcher senza prerequisiti**: `npx gpu-container` scarica il binario della piattaforma da [GitHub Release](https://github.com/mcp-tool-shop-org/gpu-container/releases), verifica il suo SHA256 rispetto alle checksum pubblicate, lo memorizza nella cache e lo esegue. **Non è necessario Python.**

```bash
npx gpu-container --help
npx gpu-container plan --profile profile.json --model-config qwen3.json --quant gguf-q4_k_m
```

> Preferisci Python? `pip install "gpu-container[host]"` installa direttamente i cinque comandi `gpu-container-*`.

## Perché esiste

Su Windows/WSL2, l'oversubscription di CUDA Unified-Memory **non è disponibile** (confermato da NVIDIA) e non è lo strumento giusto per la decodifica, nemmeno su Linux. Quindi, `gpu-container` non si basa su una "magia" di overflow in fase di esecuzione, ma rende **esplicita e dichiarata l'allocazione** come elemento centrale. Questo è il vantaggio competitivo.

## Cosa fa

`gpu-container <command>` è costituito da cinque strumenti in un unico binario:

| Comando | Fa |
|---|---|
| `profile` | Misura le risorse (VRAM, PCIe, NVMe, RAM allocabile, larghezza di banda della CPU) + il modello |
| `plan` | Calcola l'allocazione esplicita in VRAM/RAM/NVMe + una previsione di throughput calibrata; **accetta o rifiuta** |
| `receipt` | Verifica un piano rispetto a un'esecuzione reale di `llama-bench`; scrive un punto di calibrazione |
| `concentration` | Riduce il rischio della cache per ogni esperto: misura la concentrazione del routing prima di procedere alla sua creazione |
| `watchdog` | Supervisiona un lavoro della GPU; interrompe in caso di superamento dei limiti di memoria host, potenza o VRAM |

- **Tiering degli esperti MoE** (funzionalità principale): livelli condivisi/di attenzione in VRAM, esperti nella RAM della CPU tramite llama.cpp `--n-cpu-moe`. Testato in diretta su Qwen3-30B-A3B.
- **Risultati misurati**: un'esecuzione reale verifica la previsione rispetto a un limite massimo e a una banda calibrata; i risultati affinano il piano successivo.
- **Rifiuto onesto**: se nessun piano supera 1 tok/s, viene rifiutato e viene spiegato il motivo.
- **Watchdog per la sicurezza del sistema**: nato da un incidente reale; supervisiona qualsiasi lavoro della GPU in modo che un piano errato non possa compromettere il sistema.

## Esegui un lavoro della GPU in modo sicuro

```bash
gpu-container watchdog run --on-breach kill-job --peaks-out peaks.json -- \
  docker run --rm --gpus all -v "E:/AI-Models:/models" ghcr.io/ggml-org/llama.cpp:full-cuda \
    llama-bench -m /models/model.gguf --n-cpu-moe 0 -o json > bench.json
```

## Documentazione

- **Guida rapida + manuale**: https://mcp-tool-shop-org.github.io/gpu-container/handbook/
- **Codice sorgente + documentazione completa**: https://github.com/mcp-tool-shop-org/gpu-container
- **Privacy e sicurezza**: locale, offline, senza telemetria, nessun trasferimento di dati in rete. [SECURITY.md](https://github.com/mcp-tool-shop-org/gpu-container/blob/main/SECURITY.md)

<div align="center">

Creato da <a href="https://mcp-tool-shop.github.io/">MCP Tool Shop</a> · Licenza MIT

</div>
