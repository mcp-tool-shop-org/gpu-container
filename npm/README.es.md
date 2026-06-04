<p align="center">
  <a href="README.ja.md">日本語</a> | <a href="README.zh.md">中文</a> | <a href="README.md">English</a> | <a href="README.fr.md">Français</a> | <a href="README.hi.md">हिन्दी</a> | <a href="README.it.md">Italiano</a> | <a href="README.pt-BR.md">Português (BR)</a>
</p>

<div align="center">

<img src="https://raw.githubusercontent.com/mcp-tool-shop-org/gpu-container/main/assets/logo.png" width="400" alt="gpu-container" />

[![CI](https://github.com/mcp-tool-shop-org/gpu-container/actions/workflows/ci.yml/badge.svg)](https://github.com/mcp-tool-shop-org/gpu-container/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/gpu-container)](https://pypi.org/project/gpu-container/)
[![npm](https://img.shields.io/npm/v/gpu-container)](https://www.npmjs.com/package/gpu-container)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://github.com/mcp-tool-shop-org/gpu-container/blob/main/LICENSE)
[![Handbook](https://img.shields.io/badge/handbook-docs-blue)](https://mcp-tool-shop-org.github.io/gpu-container/)

**Un contenedor habilitado para GPU expone el dispositivo. Un entorno de ejecución consciente del modelo decide qué se almacena en la VRAM, la RAM asignada y la NVMe.**

</div

Ejecute el modelo local más grande y útil que su máquina pueda soportar de manera realista, con planes de ubicación explícitos, resultados de pruebas comparativas y rechazo cuando el plan cause problemas. Este paquete npm es un **programa de inicio sin requisitos previos**: `npx gpu-container` descarga el binario de la plataforma desde [GitHub Release](https://github.com/mcp-tool-shop-org/gpu-container/releases), verifica su SHA256 con las sumas de comprobación publicadas, lo almacena en caché y lo ejecuta. **No se requiere Python.**

```bash
npx gpu-container --help
npx gpu-container plan --profile profile.json --model-config qwen3.json --quant gguf-q4_k_m
```

> ¿Prefiere Python? `pip install "gpu-container[host]"` instala directamente los cinco comandos `gpu-container-*`.

## Por qué existe

En Windows/WSL2, la sobreasignación de memoria unificada de CUDA **no está disponible** (confirmado por NVIDIA) y no es la herramienta adecuada para la decodificación, incluso en Linux. Por lo tanto, `gpu-container` no depende de la magia del entorno de ejecución; en su lugar, hace que la **ubicación explícita y declarada** sea el producto. Esa es la ventaja competitiva.

## Qué hace

`gpu-container <command>` es un conjunto de cinco herramientas en un solo binario:

| Comando | Hace |
|---|---|
| `profile` | Mide el hardware (VRAM, PCIe, NVMe, RAM asignable, ancho de banda de la CPU) + el modelo |
| `plan` | Calcula la ubicación explícita en VRAM/RAM/NVMe + una previsión de rendimiento calibrada; **acepta o rechaza** |
| `receipt` | Verifica un plan con una ejecución real de `llama-bench`; escribe un punto de calibración |
| `concentration` | Reduce el riesgo de la caché por experto: mide la concentración del enrutamiento antes de construir para ello |
| `watchdog` | Supervisa un trabajo de GPU; interrumpe si se supera el límite de memoria del host/potencia/VRAM |

- **Niveles de expertos MoE** (principal) — capas compartidas/de atención en VRAM, expertos en la RAM de la CPU a través de llama.cpp `--n-cpu-moe`. Probado en vivo en Qwen3-30B-A3B.
- **Resultados medidos** — una ejecución real verifica la previsión con un *límite máximo* y una *banda* calibrada; el resultado mejora el siguiente plan.
- **Rechazo honesto** — si ningún plan supera los >1 tok/s, lo rechaza y explica por qué.
- **Supervisión de seguridad del hardware** — nació de un incidente real; supervisa cualquier trabajo de GPU para que un plan incorrecto no pueda inutilizar la máquina.

## Ejecute un trabajo de GPU de forma segura

```bash
gpu-container watchdog run --on-breach kill-job --peaks-out peaks.json -- \
  docker run --rm --gpus all -v "E:/AI-Models:/models" ghcr.io/ggml-org/llama.cpp:full-cuda \
    llama-bench -m /models/model.gguf --n-cpu-moe 0 -o json > bench.json
```

## Documentación

- **Guía de inicio rápido + manual:** https://mcp-tool-shop-org.github.io/gpu-container/handbook/
- **Código fuente + documentación completa:** https://github.com/mcp-tool-shop-org/gpu-container
- **Privacidad y seguridad:** local, sin conexión, sin telemetría, sin salida de red. [SECURITY.md](https://github.com/mcp-tool-shop-org/gpu-container/blob/main/SECURITY.md)

<div align="center">

Creado por <a href="https://mcp-tool-shop.github.io/">MCP Tool Shop</a> · Licencia MIT

</div
