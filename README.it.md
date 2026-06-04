<p align="center">
  <a href="README.ja.md">日本語</a> | <a href="README.zh.md">中文</a> | <a href="README.es.md">Español</a> | <a href="README.fr.md">Français</a> | <a href="README.hi.md">हिन्दी</a> | <a href="README.md">English</a> | <a href="README.pt-BR.md">Português (BR)</a>
</p>

<div align="center">

<img src="https://raw.githubusercontent.com/mcp-tool-shop-org/gpu-container/main/assets/logo.png" width="400" alt="gpu-container" />

```
[![CI](https://github.com/mcp-tool-shop-org/gpu-container/actions/workflows/ci.yml/badge.svg)](https://github.com/mcp-tool-shop-org/gpu-container/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/gpu-container)](https://pypi.org/project/gpu-container/)
[![npm](https://img.shields.io/npm/v/gpu-container)](https://www.npmjs.com/package/gpu-container)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Handbook](https://img.shields.io/badge/handbook-docs-blue)](https://mcp-tool-shop-org.github.io/gpu-container/)

**Un container abilitato per GPU espone il dispositivo. Un runtime consapevole del modello decide cosa risiede nella VRAM, nella RAM allocata e nella NVMe.**

</div>

Esegui il modello locale più grande e utile che la tua macchina può effettivamente supportare, con piani di allocazione espliciti, risultati dei benchmark e rifiuto nel caso in cui il piano causerebbe un sovraccarico.

## Architettura

```
Windows / WSL2 / Linux host
  └─ GPU-enabled Docker container
      └─ Inference runtime
          ├─ VRAM: hot weights, active layers, activations, KV working set
          ├─ pinned RAM: CPU-offloaded weights, MoE experts, KV spill/reuse
          └─ NVMe: mmap shards, disk offload, cold experts, cold KV
```

## Confini del prodotto

```
Docker         = packaging + GPU exposure
CUDA/runtime   = compute backend
Planner        = memory law
Inference engine = execution
```

## Funzionalità principali

1. **Profiler hardware:** rileva VRAM, RAM, tipo di GPU, WSL/Linux nativo, velocità NVMe, disponibilità di CUDA
2. **Profiler del modello:** rileva modelli densi rispetto a MoE, livello più grande, peso totale, quantizzazione, crescita KV in base alla lunghezza del contesto
3. **Pianificatore runtime:** genera piani di avvio per llama.cpp, vLLM, Accelerate, TensorRT-LLM o offload in stile DeepSpeed
4. **Rapporto di allocazione:** mostra cosa si trova nella VRAM, cosa si trova nella RAM, cosa si trova sul disco, il potenziale collo di bottiglia, i token/secondo misurati
5. **Percorso specializzato per MoE:** mantiene i livelli sempre attivi sulla GPU, indirizza gli esperti verso CPU/RAM, NVMe per il fallback in caso di inattività
6. **Riduzione del rischio di routing:** misura se il routing MoE di un modello è distorto al punto che una cache per esperto sarebbe utile, prima di procedere alla sua implementazione (`gpu-container-concentration`)
7. **Watchdog per la sicurezza del sistema:** monitora la potenza/temperatura/VRAM della GPU + la memoria host rispetto alle soglie configurabili; un agente AI o un ciclo autonomo interrompe un'esecuzione prima che metta a rischio la macchina (`gpu-container-watchdog`)

## Vincolo principale

Su Windows/WSL, l'oversubscription della memoria unificata CUDA **non è la soluzione**. CUDA tratta Windows/WSL come un supporto limitato per la memoria unificata: nessuna migrazione fine a livello di pagina della GPU, nessun oversubscription della memoria GPU oltre la VRAM fisica. Questo prodotto è l'**allocazione esplicita della memoria per l'inferenza**, non un "overflow della VRAM di Docker".

## Stato

Già costruito e funzionante: `gpu-container-profile`, `gpu-container-plan`, `gpu-container-receipt` (con il ciclo di ricalibrazione), `gpu-container-concentration` (riduzione del rischio di routing) e `gpu-container-watchdog` (supervisione sicura di un job GPU). llama.cpp è il backend integrato; la matematica di allocazione è indipendente dal backend. Inizia con la [guida rapida](docs/quickstart.md).

## Privacy e sicurezza

`gpu-container` è uno **strumento locale, offline**: non effettua chiamate di rete e non raccoglie **nessun dato di telemetria**, né per impostazione predefinita né in altro modo. Legge le metriche della GPU (`nvidia-smi` / NVML) e la memoria host (`psutil`), il file `config.json` del modello che fornisci e i file JSON a cui lo indirizzi; scrive solo nei percorsi di output che specifichi. **Non** legge né trasmette i pesi del modello, le credenziali o i token. Le azioni a livello di host (`wsl --shutdown`, `docker stop`, `kill`) vengono eseguite solo quando si sceglie esplicitamente di farlo tramite il watchdog `--on-breach`; le impostazioni predefinite non toccano mai la tua macchina oltre al job che supervisionano. Politica completa: [SECURITY.md](SECURITY.md).

## Documentazione

- [`docs/quickstart.md`](docs/quickstart.md) — guida passo passo: profilo → piano → avvio sotto il watchdog → rapporto → ricalibrazione
- [`docs/cli.md`](docs/cli.md) — i cinque comandi: sintesi, flag, codici di uscita, esempi pratici
- [`docs/architecture.md`](docs/architecture.md) — modello a livelli di memoria, flusso di dati, routing degli esperti MoE, ciclo di ricalibrazione
- [`docs/features.md`](docs/features.md) — le sette funzionalità principali in dettaglio
- [`docs/moe-lane-architecture.md`](docs/moe-lane-architecture.md) — la principale architettura MoE in dettaglio
- [`docs/derisk-concentration.md`](docs/derisk-concentration.md) — il meccanismo di riduzione del rischio della cache per esperto (concentrazione del routing)
- [`docs/decisions/0001-per-expert-cache-build-vs-upstream.md`](docs/decisions/0001-per-expert-cache-build-vs-upstream.md) — ADR-0001: utilizza il meccanismo della cache, contribuisci alla politica
- [`docs/constraints.md`](docs/constraints.md) — obiettivi non perseguiti + correzione della memoria unificata CUDA per Windows/WSL
- [`docs/prior-art.md`](docs/prior-art.md) — runtime che orchestrano e il divario che questo prodotto colma
- [`docs/feasibility.md`](docs/feasibility.md) — valutazione della fattibilità, base di ricerca e ciò che è stato confermato in fase di test

---

<div align="center">

Creato da <a href="https://mcp-tool-shop.github.io/">MCP Tool Shop</a> · Licenza MIT
```

</div>
