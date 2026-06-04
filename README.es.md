<p align="center">
  <a href="README.ja.md">日本語</a> | <a href="README.zh.md">中文</a> | <a href="README.md">English</a> | <a href="README.fr.md">Français</a> | <a href="README.hi.md">हिन्दी</a> | <a href="README.it.md">Italiano</a> | <a href="README.pt-BR.md">Português (BR)</a>
</p>

<div align="center">

<img src="https://raw.githubusercontent.com/mcp-tool-shop-org/gpu-container/main/assets/logo.png" width="400" alt="gpu-container" />

[![CI](https://github.com/mcp-tool-shop-org/gpu-container/actions/workflows/ci.yml/badge.svg)](https://github.com/mcp-tool-shop-org/gpu-container/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/gpu-container)](https://pypi.org/project/gpu-container/)
[![npm](https://img.shields.io/npm/v/gpu-container)](https://www.npmjs.com/package/gpu-container)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Handbook](https://img.shields.io/badge/handbook-docs-blue)](https://mcp-tool-shop-org.github.io/gpu-container/)

**Un contenedor habilitado para GPU expone el dispositivo. Un entorno de ejecución consciente del modelo decide qué se almacena en la VRAM, la RAM asignada y la NVMe.**

</div>

Ejecute el modelo local más grande y útil que su máquina pueda soportar de manera realista, con planes de ubicación explícitos, informes de pruebas de rendimiento y rechazo cuando el plan cause problemas.

## Arquitectura

```
Windows / WSL2 / Linux host
  └─ GPU-enabled Docker container
      └─ Inference runtime
          ├─ VRAM: hot weights, active layers, activations, KV working set
          ├─ pinned RAM: CPU-offloaded weights, MoE experts, KV spill/reuse
          └─ NVMe: mmap shards, disk offload, cold experts, cold KV
```

## Límite del producto

```
Docker         = packaging + GPU exposure
CUDA/runtime   = compute backend
Planner        = memory law
Inference engine = execution
```

## Características principales

1. **Perfilador de hardware:** Detecta la VRAM, la RAM, el tipo de GPU, WSL/Linux nativo, la velocidad de NVMe y la disponibilidad de CUDA.
2. **Perfilador de modelo:** Detecta si es denso o MoE, la capa más grande, el número total de parámetros, la cuantificación y el crecimiento de KV según la longitud del contexto.
3. **Planificador de entorno de ejecución:** Genera planes de inicio para llama.cpp, vLLM, Accelerate, TensorRT-LLM o la descarga al estilo DeepSpeed.
4. **Informe de ubicación:** Muestra qué hay en la VRAM, qué hay en la RAM, qué hay en el disco, el cuello de botella esperado y los tokens/segundo medidos.
5. **Ruta especializada para MoE:** Mantiene las capas siempre activas en la GPU, dirige los expertos a la CPU/RAM y a la NVMe para la recuperación en caso de inactividad.
6. **Reducción de riesgos en el enrutamiento:** Mide si el enrutamiento MoE de un modelo está lo suficientemente sesgado como para que una caché por experto sea útil, antes de construirlo (`gpu-container-concentration`).
7. **Vigilante de seguridad del sistema:** Supervisa la potencia/temperatura/VRAM de la GPU y la memoria del host en comparación con los umbrales configurables; un agente de IA o un bucle autónomo aborta una ejecución antes de que ponga en peligro la máquina (`gpu-container-watchdog`).

## Restricción clave

En Windows/WSL, la sobreasignación de memoria unificada de CUDA **no es la solución**. CUDA trata Windows/WSL como un soporte limitado para la memoria unificada: no hay migración de páginas de GPU de grano fino, ni sobreasignación de memoria de GPU más allá de la VRAM física. Este producto es la **ubicación explícita de la memoria de inferencia**, no el "desbordamiento de VRAM de Docker".

## Estado

Construido y funcionando hoy: `gpu-container-profile`, `gpu-container-plan`, `gpu-container-receipt` (con el bucle de recalibración), `gpu-container-concentration` (reducción de riesgos en el enrutamiento) y `gpu-container-watchdog` (supervisión segura de un trabajo de GPU). llama.cpp es el backend integrado; las matemáticas de ubicación son independientes del backend. Comience con el [inicio rápido](docs/quickstart.md).

## Privacidad y seguridad

`gpu-container` es una **herramienta local y sin conexión**: no realiza llamadas de red y no recopila **ninguna telemetría**, ni por defecto ni de otra manera. Lee las métricas de la GPU (`nvidia-smi` / NVML) y la memoria del host (`psutil`), el archivo `config.json` del modelo que proporciona y los archivos JSON a los que lo apunta; solo escribe en las rutas de salida que especifica. **No** lee ni transmite los parámetros del modelo, las credenciales ni los tokens. Las acciones a nivel de host (`wsl --shutdown`, `docker stop`, `kill`) solo se ejecutan cuando usted acepta explícitamente a través del parámetro `--on-breach` del vigilante; los valores predeterminados nunca tocan su máquina más allá del trabajo que supervisan. Política completa: [SECURITY.md](SECURITY.md).

## Documentación

- [`docs/quickstart.md`](docs/quickstart.md): recorrido completo: perfil → plan → inicio bajo el vigilante → informe → recalibración
- [`docs/cli.md`](docs/cli.md): los cinco comandos: resumen, opciones, códigos de salida, ejemplos prácticos
- [`docs/architecture.md`](docs/architecture.md): modelo de niveles de memoria, flujo de datos, enrutamiento de expertos MoE, el bucle de recalibración
- [`docs/features.md`](docs/features.md): las siete características principales en detalle
- [`docs/moe-lane-architecture.md`](docs/moe-lane-architecture.md): la ruta MoE insignia en detalle
- [`docs/derisk-concentration.md`](docs/derisk-concentration.md): la puerta de reducción de riesgos de la caché por experto (concentración del enrutamiento)
- [`docs/decisions/0001-per-expert-cache-build-vs-upstream.md`](docs/decisions/0001-per-expert-cache-build-vs-upstream.md): ADR-0001: consumir el mecanismo de caché, contribuir a la política
- [`docs/constraints.md`](docs/constraints.md): objetivos no cumplidos + la corrección de la memoria unificada de CUDA en Windows/WSL
- [`docs/prior-art.md`](docs/prior-art.md): entornos de ejecución que orquestamos y la brecha que llena este producto
- [`docs/feasibility.md`](docs/feasibility.md): evaluación de viabilidad, base de investigación y lo que se ha confirmado que funciona

---

<div align="center">

Creado por <a href="https://mcp-tool-shop.github.io/">MCP Tool Shop</a> · Licencia MIT

</div>
