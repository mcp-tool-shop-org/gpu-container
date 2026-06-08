#!/usr/bin/env bash
# Rebuild ~/bp-env pinned to backpropagate v1.5.0's verified-on-5090 stack (Mike-approved, option A).
# Whole stack is cu128 so bitsandbytes 0.49.2's CUDA binary matches the torch toolkit (no cu130 skew).
# Stays entirely on WSL — the rig-safety kill switch (wsl --shutdown) only reaches WSL.
set -uo pipefail
log(){ echo "[setup2] $*"; }
export HF_HOME=/mnt/e/AI-Models/hf-cache
VENV="$HOME/bp-env"
CU128="https://download.pytorch.org/whl/cu128"
CONSTRAINTS=/mnt/e/AI/gpu-container/specialist-training/constraints.txt

ensure_torch_cuda(){
  local ok; ok=$(python -c 'import torch;print(int(torch.cuda.is_available()))' 2>/dev/null || echo 0)
  [ "$ok" = "1" ] || { log "torch CUDA clobbered -> reinstall cu128 torch"; uv pip install "torch==2.10.0" --index-url "$CU128" --reinstall-package torch; }
}

log "removing old (cu130) venv + recreating fresh (python 3.12)"
rm -rf "$VENV"
uv venv "$VENV" --python 3.12 || { log "venv FAILED"; exit 1; }
# shellcheck disable=SC1091
source "$VENV/bin/activate"

log "torch==2.10.0 (cu128 — matches the verified env)"
uv pip install "torch==2.10.0" --index-url "$CU128" || { log "torch FAILED"; exit 2; }
python -c "import torch;print('[v] torch',torch.__version__,'cuda',torch.version.cuda,'avail',torch.cuda.is_available());print('[v]',torch.cuda.get_device_name(0))" || { log "cuda verify FAILED"; exit 3; }

log "pinned training libs (the verified combo)"
uv pip install \
  "transformers==5.5.0" "trl==0.24.0" "peft==0.19.1" \
  "bitsandbytes==0.49.2" "accelerate==1.13.0" "datasets==4.3.0" || { log "libs FAILED"; exit 4; }
ensure_torch_cuda

log "backpropagate editable (local v1.5.0), constrained so it cannot bump the pins"
uv pip install -e /mnt/e/AI/backpropagate --constraint "$CONSTRAINTS" 2>&1 | tail -6
ensure_torch_cuda

log "final version report"
python - <<'PY'
import torch, transformers, trl, peft, bitsandbytes, accelerate, datasets
print("torch", torch.__version__, "| cuda-avail", torch.cuda.is_available())
print("transformers", transformers.__version__, "| trl", trl.__version__, "| peft", peft.__version__)
print("bitsandbytes", bitsandbytes.__version__, "| accelerate", accelerate.__version__, "| datasets", datasets.__version__)
PY
( backprop --version 2>&1 | head -1 ) || log "backprop --version unavailable"
log "DONE_SETUP2"
