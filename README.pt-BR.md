<p align="center">
  <a href="README.ja.md">日本語</a> | <a href="README.zh.md">中文</a> | <a href="README.es.md">Español</a> | <a href="README.fr.md">Français</a> | <a href="README.hi.md">हिन्दी</a> | <a href="README.it.md">Italiano</a> | <a href="README.md">English</a>
</p>

<div align="center">

<img src="https://raw.githubusercontent.com/mcp-tool-shop-org/gpu-container/main/assets/logo.png" width="400" alt="gpu-container" />

```
[![CI](https://github.com/mcp-tool-shop-org/gpu-container/actions/workflows/ci.yml/badge.svg)](https://github.com/mcp-tool-shop-org/gpu-container/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/gpu-container)](https://pypi.org/project/gpu-container/)
[![npm](https://img.shields.io/npm/v/gpu-container)](https://www.npmjs.com/package/gpu-container)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Handbook](https://img.shields.io/badge/handbook-docs-blue)](https://mcp-tool-shop-org.github.io/gpu-container/)

**Um contêiner habilitado para GPU expõe o dispositivo. Um ambiente de execução com conhecimento do modelo decide o que será armazenado na VRAM, na RAM alocada e na NVMe.**

</div>

Execute o maior modelo local útil que sua máquina possa suportar, com planos de alocação explícitos, resultados de testes de desempenho e recusa quando o plano causar problemas.

## Arquitetura

```
Windows / WSL2 / Linux host
  └─ GPU-enabled Docker container
      └─ Inference runtime
          ├─ VRAM: hot weights, active layers, activations, KV working set
          ├─ pinned RAM: CPU-offloaded weights, MoE experts, KV spill/reuse
          └─ NVMe: mmap shards, disk offload, cold experts, cold KV
```

## Escopo do produto

```
Docker         = packaging + GPU exposure
CUDA/runtime   = compute backend
Planner        = memory law
Inference engine = execution
```

## Recursos principais

1. **Analisador de hardware** — Detecta VRAM, RAM, tipo de GPU, WSL/Linux nativo, velocidade da NVMe, disponibilidade da CUDA
2. **Analisador de modelo** — Detecta modelos densos vs. MoE, maior camada, número total de parâmetros, quantização, crescimento de KV por comprimento do contexto
3. **Planejador de execução** — Gera planos de execução para llama.cpp, vLLM, Accelerate, TensorRT-LLM ou descarregamento no estilo DeepSpeed
4. **Relatório de alocação** — Mostra o que está na VRAM, o que está na RAM, o que está no disco, gargalo esperado, tokens/segundo medidos
5. **Caminho especializado para MoE** — Mantenha as camadas sempre ativas na GPU, direcione os especialistas para a CPU/RAM, NVMe para fallback em caso de inatividade
6. **Redução de riscos no roteamento** — Mede se o roteamento MoE de um modelo está tão distorcido que um cache por especialista ajudaria, antes de construir para isso (`gpu-container-concentration`)
7. **Monitor de segurança do sistema** — Verifica a potência/temperatura/VRAM da GPU + memória do host em relação a limites configuráveis; um agente de IA ou um loop autônomo interrompe uma execução antes que ela coloque em risco a máquina (`gpu-container-watchdog`)

## Restrição principal

No Windows/WSL, o uso excessivo da memória unificada da CUDA **não é o caminho a seguir**. A CUDA trata o Windows/WSL como tendo suporte limitado à memória unificada — sem migração de página da GPU granular, sem uso excessivo da memória da GPU além da VRAM física. Este produto é **alocação explícita de memória para inferência**, não "transbordamento da VRAM do Docker".

## Status

Construído e funcionando hoje: `gpu-container-profile`, `gpu-container-plan`, `gpu-container-receipt` (com o loop de recalibração), `gpu-container-concentration` (redução de riscos no roteamento) e `gpu-container-watchdog` (supervisiona um trabalho da GPU com segurança). O llama.cpp é o backend integrado; a matemática de alocação é independente do backend. Comece com o [guia rápido](docs/quickstart.md).

## Privacidade e segurança

`gpu-container` é uma **ferramenta local e offline** — não faz chamadas de rede e não coleta **nenhuma telemetria**, por padrão ou de outra forma. Ele lê as métricas da GPU (`nvidia-smi` / NVML) e a memória do host (`psutil`), o arquivo `config.json` do modelo que você fornece e os arquivos JSON que você aponta para ele; ele grava apenas nos caminhos de saída que você especifica. Ele **não** lê ou transmite parâmetros do modelo, credenciais ou tokens. As ações no nível do host (`wsl --shutdown`, `docker stop`, `kill`) são executadas apenas quando você opta explicitamente por meio do `--on-breach` do monitor; os padrões nunca tocam em sua máquina além do trabalho que eles supervisionam. Política completa: [SECURITY.md](SECURITY.md).

## Documentação

- [`docs/quickstart.md`](docs/quickstart.md) — guia passo a passo: perfil → plano → execução sob o monitor → relatório → recalibração
- [`docs/cli.md`](docs/cli.md) — os cinco comandos: sinopse, flags, códigos de saída, exemplos práticos
- [`docs/architecture.md`](docs/architecture.md) — modelo de camadas de memória, fluxo de dados, roteamento de especialistas MoE, o loop de recalibração
- [`docs/features.md`](docs/features.md) — os sete recursos principais em detalhes
- [`docs/moe-lane-architecture.md`](docs/moe-lane-architecture.md) — a principal arquitetura de "lane" MoE em detalhes
- [`docs/derisk-concentration.md`](docs/derisk-concentration.md) — o mecanismo de redução de riscos do cache por especialista (concentração de roteamento)
- [`docs/decisions/0001-per-expert-cache-build-vs-upstream.md`](docs/decisions/0001-per-expert-cache-build-vs-upstream.md) — ADR-0001: consumir o mecanismo de cache, contribuir com a política
- [`docs/constraints.md`](docs/constraints.md) — não objetivos + a correção da memória unificada da CUDA no Windows/WSL
- [`docs/prior-art.md`](docs/prior-art.md) — os ambientes de execução que orquestramos e a lacuna que este produto preenche
- [`docs/feasibility.md`](docs/feasibility.md) — avaliação de viabilidade, base de pesquisa e o que foi confirmado em funcionamento

---

<div align="center">

Criado por <a href="https://mcp-tool-shop.github.io/">MCP Tool Shop</a> · Licenciado sob MIT
```

</div>
