<p align="center">
  <a href="README.md">English</a> | <a href="README.zh.md">中文</a> | <a href="README.es.md">Español</a> | <a href="README.fr.md">Français</a> | <a href="README.hi.md">हिन्दी</a> | <a href="README.it.md">Italiano</a> | <a href="README.pt-BR.md">Português (BR)</a>
</p>

<div align="center">

<img src="https://raw.githubusercontent.com/mcp-tool-shop-org/gpu-container/main/assets/logo.png" width="400" alt="gpu-container" />

[![CI](https://github.com/mcp-tool-shop-org/gpu-container/actions/workflows/ci.yml/badge.svg)](https://github.com/mcp-tool-shop-org/gpu-container/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/gpu-container)](https://pypi.org/project/gpu-container/)
[![npm](https://img.shields.io/npm/v/gpu-container)](https://www.npmjs.com/package/gpu-container)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Handbook](https://img.shields.io/badge/handbook-docs-blue)](https://mcp-tool-shop-org.github.io/gpu-container/)

**GPU を活用したコンテナは、デバイスを公開します。モデルを認識するランタイムは、VRAM、ピン留めされた RAM、および NVMe に配置するものを決定します。**

</div>

マシンが実際にサポートできる最大の有用なローカルモデルを、明示的な配置計画、ベンチマークの結果、および計画が過負荷になる場合に実行を拒否するように実行します。

## アーキテクチャ

```
Windows / WSL2 / Linux host
  └─ GPU-enabled Docker container
      └─ Inference runtime
          ├─ VRAM: hot weights, active layers, activations, KV working set
          ├─ pinned RAM: CPU-offloaded weights, MoE experts, KV spill/reuse
          └─ NVMe: mmap shards, disk offload, cold experts, cold KV
```

## 製品の範囲

```
Docker         = packaging + GPU exposure
CUDA/runtime   = compute backend
Planner        = memory law
Inference engine = execution
```

## 主な機能

1. **ハードウェアプロファイラー** — VRAM、RAM、GPU タイプ、WSL/ネイティブ Linux、NVMe 速度、CUDA の可用性を検出します。
2. **モデルプロファイラー** — 密なモデルと MoE、最大のレイヤー、合計の重み、量子化、コンテキスト長による KV の増加を検出します。
3. **ランタイムプランナー** — llama.cpp、vLLM、Accelerate、TensorRT-LLM、または DeepSpeed スタイルのオフロードの起動計画を生成します。
4. **配置結果** — VRAM に配置するもの、RAM に配置するもの、ディスクに配置するもの、予想されるボトルネック、測定されたトークン/秒を表示します。
5. **MoE 専用パス** — 常にアクティブなレイヤーを GPU に配置し、エキスパートを CPU/RAM にルーティングし、コールドフォールバック用に NVMe を使用します。
6. **ルーティングのリスク軽減** — モデルの MoE ルーティングが、エキスパートごとのキャッシュが役立つほど偏っているかどうかを測定してから、そのためにビルドします (`gpu-container-concentration`)。
7. **リグの安全監視** — GPU の電力/温度/VRAM + ホストメモリを、構成可能なしきい値と比較します。AI エージェントまたは自律ループが、マシンに危険が及ぶ前に実行を中止します (`gpu-container-watchdog`)。

## 主な制約

Windows/WSL では、CUDA Unified Memory の過剰割り当ては**適切な方法ではありません**。CUDA は、Windows/WSL を限られた統合メモリサポートとして扱います。つまり、きめ細かい GPU ページフォールトの移行や、物理 VRAM を超える GPU メモリの過剰割り当ては行いません。この製品は、**明示的な推論メモリ配置**であり、「Docker VRAM オーバーフロー」ではありません。

## ステータス

現在、`gpu-container-profile`、`gpu-container-plan`、`gpu-container-receipt`（再調整ループ付き）、`gpu-container-concentration`（ルーティングのリスク軽減）、および `gpu-container-watchdog`（GPU ジョブを安全に監視）がビルドされ、動作しています。llama.cpp が統合されたバックエンドです。配置の計算は、バックエンドに依存しません。 [クイックスタート](docs/quickstart.md) から始めましょう。

## プライバシーと安全性

`gpu-container` は、**ローカルのオフラインツール**です。デフォルトまたはその他の方法で、ネットワーク呼び出しを行ったり、テレメトリを収集したりすることはありません。GPU メトリック (`nvidia-smi` / NVML) とホストメモリ (`psutil`)、提供するモデルの `config.json`、および指定する JSON ファイルを読み取ります。出力パスにのみ書き込みます。モデルの重み、資格情報、またはトークンは読み取ったり、送信したりしません。ホストレベルのアクション (`wsl --shutdown`、`docker stop`、`kill`) は、監視対象のジョブを超えてマシンに影響を与えないように、監視の `--on-breach` を介して明示的にオプトインした場合にのみ実行されます。完全なポリシー: [SECURITY.md](SECURITY.md)。

## ドキュメント

- [`docs/quickstart.md`](docs/quickstart.md) — エンドツーエンドのウォークスルー: プロファイル作成 → 計画 → 監視下での起動 → 結果 → 再調整
- [`docs/cli.md`](docs/cli.md) — 5 つのコマンド: 概要、フラグ、終了コード、実例
- [`docs/architecture.md`](docs/architecture.md) — メモリ階層モデル、データフロー、MoE エキスパートルーティング、再調整ループ
- [`docs/features.md`](docs/features.md) — 7 つの主な機能の詳細
- [`docs/moe-lane-architecture.md`](docs/moe-lane-architecture.md) — 主要な MoE レーンの詳細
- [`docs/derisk-concentration.md`](docs/derisk-concentration.md) — エキスパートごとのキャッシュのリスク軽減ゲート (ルーティングの集中度)
- [`docs/decisions/0001-per-expert-cache-build-vs-upstream.md`](docs/decisions/0001-per-expert-cache-build-vs-upstream.md) — ADR-0001: キャッシュメカニズムを使用し、ポリシーに貢献します。
- [`docs/constraints.md`](docs/constraints.md) — 非目標 + Windows/WSL CUDA Unified-Memory の修正
- [`docs/prior-art.md`](docs/prior-art.md) — 調整するランタイムと、この製品が埋めるギャップ
- [`docs/feasibility.md`](docs/feasibility.md) — 実行可能性評価、調査の根拠、および実際に確認されたこと

---

<div align="center">

<a href="https://mcp-tool-shop.github.io/">MCP Tool Shop</a> によって構築 · MIT ライセンス

</div>
