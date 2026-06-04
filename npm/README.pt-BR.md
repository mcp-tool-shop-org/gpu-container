<p align="center">
  <a href="README.ja.md">日本語</a> | <a href="README.zh.md">中文</a> | <a href="README.es.md">Español</a> | <a href="README.fr.md">Français</a> | <a href="README.hi.md">हिन्दी</a> | <a href="README.it.md">Italiano</a> | <a href="README.md">English</a>
</p>

<div align="center">

<img src="https://raw.githubusercontent.com/mcp-tool-shop-org/gpu-container/main/assets/logo.png" width="400" alt="gpu-container" />

[![CI](https://github.com/mcp-tool-shop-org/gpu-container/actions/workflows/ci.yml/badge.svg)](https://github.com/mcp-tool-shop-org/gpu-container/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/gpu-container)](https://pypi.org/project/gpu-container/)
[![npm](https://img.shields.io/npm/v/gpu-container)](https://www.npmjs.com/package/gpu-container)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://github.com/mcp-tool-shop-org/gpu-container/blob/main/LICENSE)
[![Handbook](https://img.shields.io/badge/handbook-docs-blue)](https://mcp-tool-shop-org.github.io/gpu-container/)

**Um contêiner habilitado para GPU expõe o dispositivo. Um ambiente de execução consciente do modelo decide o que será armazenado na VRAM, na RAM alocada e na NVMe.**

</div>

Execute o maior modelo local útil que sua máquina possa suportar — com planos de alocação explícitos, resultados de testes de desempenho e recusa quando o plano causar problemas. Este pacote npm é um **inicializador sem pré-requisitos**: `npx gpu-container` baixa o binário da plataforma do [GitHub Release](https://github.com/mcp-tool-shop-org/gpu-container/releases), verifica seu SHA256 em relação aos hashes publicados, armazena em cache e o executa. **Não é necessário Python.**

```bash
npx gpu-container --help
npx gpu-container plan --profile profile.json --model-config qwen3.json --quant gguf-q4_k_m
```

> Prefere Python? `pip install "gpu-container[host]"` instala diretamente os cinco comandos `gpu-container-*`.

## Por que ele existe

No Windows/WSL2, o uso excessivo de memória unificada da CUDA é **indisponível** (confirmado pela NVIDIA) e não é a ferramenta certa para decodificação, mesmo no Linux. Portanto, `gpu-container` não depende de truques de alocação em tempo de execução — ele torna a **alocação explícita e declarada** o produto. Essa é a vantagem.

## O que ele faz

`gpu-container <command>` é cinco ferramentas em um único binário:

| Comando | Faz |
|---|---|
| `profile` | Mede o hardware (VRAM, PCIe, NVMe, RAM alocada, largura de banda da CPU) + o modelo |
| `plan` | Calcula a alocação explícita de VRAM/RAM/NVMe + uma previsão de desempenho calibrada; **executa ou recusa** |
| `receipt` | Verifica um plano em relação a uma execução real do `llama-bench`; grava um ponto de calibração |
| `concentration` | Reduz o risco do cache por especialista — mede a concentração de roteamento antes de construir para ele |
| `watchdog` | Supervisiona um trabalho da GPU; aborta em caso de violação da memória do host/energia/VRAM |

- **Níveis de especialistas MoE** (principal) — camadas compartilhadas/de atenção na VRAM, especialistas na RAM da CPU via llama.cpp `--n-cpu-moe`. Comprovado em funcionamento no Qwen3-30B-A3B.
- **Resultados medidos** — uma execução real verifica a previsão em relação a um *limite máximo* e uma *faixa* calibrada; o resultado refina o próximo plano.
- **Recusa honesta** — nenhum plano atinge >1 token/s? Ele recusa e explica o motivo.
- **Monitor de segurança do hardware** — nascido de um incidente real; supervisiona qualquer trabalho da GPU para que um plano ruim não cause a falha da máquina.

## Execute um trabalho da GPU com segurança

```bash
gpu-container watchdog run --on-breach kill-job --peaks-out peaks.json -- \
  docker run --rm --gpus all -v "E:/AI-Models:/models" ghcr.io/ggml-org/llama.cpp:full-cuda \
    llama-bench -m /models/model.gguf --n-cpu-moe 0 -o json > bench.json
```

## Documentação

- **Guia rápido + manual:** https://mcp-tool-shop-org.github.io/gpu-container/handbook/
- **Código-fonte + documentação completa:** https://github.com/mcp-tool-shop-org/gpu-container
- **Privacidade e segurança:** local, offline, sem telemetria, sem envio de dados para a rede. [SECURITY.md](https://github.com/mcp-tool-shop-org/gpu-container/blob/main/SECURITY.md)

<div align="center">

Criado por <a href="https://mcp-tool-shop.github.io/">MCP Tool Shop</a> · Licenciado sob MIT

</div>
