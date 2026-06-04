<p align="center">
  <a href="README.md">English</a> | <a href="README.zh.md">中文</a> | <a href="README.es.md">Español</a> | <a href="README.fr.md">Français</a> | <a href="README.hi.md">हिन्दी</a> | <a href="README.it.md">Italiano</a> | <a href="README.pt-BR.md">Português (BR)</a>
</p>

<div align="center">

<img src="https://raw.githubusercontent.com/mcp-tool-shop-org/gpu-container/main/assets/logo.png" width="400" alt="gpu-container" />

[![CI](https://github.com/mcp-tool-shop-org/gpu-container/actions/workflows/ci.yml/badge.svg)](https://github.com/mcp-tool-shop-org/gpu-container/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/gpu-container)](https://pypi.org/project/gpu-container/)
[![npm](https://img.shields.io/npm/v/gpu-container)](https://www.npmjs.com/package/gpu-container)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://github.com/mcp-tool-shop-org/gpu-container/blob/main/LICENSE)
[![Handbook](https://img.shields.io/badge/handbook-docs-blue)](https://mcp-tool-shop-org.github.io/gpu-container/)

**GPU を搭載したコンテナは、デバイスを公開します。モデルを認識するランタイムは、VRAM、固定 RAM、および NVMe に何を配置するかを決定します。**

</div

マシンが実際にサポートできる最大の有用なローカルモデルを、明示的な配置計画、ベンチマークの結果、および計画が過剰な負荷をかける場合に拒否する機能とともに実行します。この npm パッケージは、**前提条件がゼロのランチャー**です。`npx gpu-container` は、[GitHub リリース](https://github.com/mcp-tool-shop-org/gpu-container/releases) からプラットフォームバイナリをダウンロードし、公開されているチェックサムに対して SHA256 を検証し、キャッシュし、実行します。**Python は不要です。**

```bash
npx gpu-container --help
npx gpu-container plan --profile profile.json --model-config qwen3.json --quant gguf-q4_k_m
```

> Python を使用したいですか？ `pip install "gpu-container[host]"` を使用すると、5 つの `gpu-container-*` コマンドが直接インストールされます。

## このツールの存在意義

Windows/WSL2 では、CUDA Unified-Memory の過剰な割り当ては**利用できません**（NVIDIA が確認済み）であり、Linux でもデコードには適切なツールではありません。したがって、`gpu-container` はランタイムの動的なオーバーフローに依存するのではなく、**明示的で宣言的な配置**を製品の核とします。それがこのツールの強みです。

## このツールの機能

`gpu-container <command>` は、1 つのバイナリに 5 つのツールをまとめたものです。

| コマンド | 実行内容 |
|---|---|
| `profile` | マシン（VRAM、PCIe、NVMe、固定 RAM、CPU 帯域幅）とモデルを測定します。 |
| `plan` | 明示的な VRAM/RAM/NVMe 配置と、キャリブレーションされたスループット予測を計算します。**配置を承認または拒否**します。 |
| `receipt` | 実際の `llama-bench` 実行に対して計画を検証し、キャリブレーションポイントを記録します。 |
| `concentration` | 各専門家キャッシュのリスクを軽減します。それに向けてビルドする前に、ルーティングの集中度を測定します。 |
| `watchdog` | GPU ジョブを監視し、ホストメモリ、電力、または VRAM の制限を超えた場合にジョブを中止します。 |

- **MoE 専門家階層化**（主要機能）—共有/アテンション層を VRAM に、専門家を CPU RAM に配置します（llama.cpp の `--n-cpu-moe` オプションを使用）。Qwen3-30B-A3B で実証済み。
- **測定された結果**—実際の実行で、予測を屋根の線（*ceiling*）とキャリブレーションされた帯域（*band*）に対して検証します。結果は、次の計画を改善するために使用されます。
- **正直な拒否**—1 秒あたり 1 トークン以上の処理ができない計画の場合、拒否し、その理由を説明します。
- **マシン保護ウォッチドッグ**—実際のインシデントから生まれました。すべての GPU ジョブを監視し、不適切な計画によってマシンが停止しないようにします。

## GPU ジョブを安全に実行します

```bash
gpu-container watchdog run --on-breach kill-job --peaks-out peaks.json -- \
  docker run --rm --gpus all -v "E:/AI-Models:/models" ghcr.io/ggml-org/llama.cpp:full-cuda \
    llama-bench -m /models/model.gguf --n-cpu-moe 0 -o json > bench.json
```

## ドキュメント

- **クイックスタート + ハンドブック:** https://mcp-tool-shop-org.github.io/gpu-container/handbook/
- **ソースコード + 完全なドキュメント:** https://github.com/mcp-tool-shop-org/gpu-container
- **プライバシーと安全性:** ローカル、オフライン、テレメトリなし、ネットワークへのデータ送信なし。[SECURITY.md](https://github.com/mcp-tool-shop-org/gpu-container/blob/main/SECURITY.md)

<div align="center">

<a href="https://mcp-tool-shop.github.io/">MCP Tool Shop</a> によって作成されました。MIT ライセンス。

</div
