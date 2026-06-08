#!/usr/bin/env bash
# Bootstrap the rig-safe training env for the Token Budget Analyst specialist.
# Isolated venv (~/bp-env) on ext4; cu130 torch (matches the working vllm-env Blackwell build);
# guards against the documented unsloth/CPU-torch clobber by re-verifying CUDA after each phase.
set -uo pipefail
log(){ echo "[setup] $*"; }
export HF_HOME=/mnt/e/AI-Models/hf-cache
VENV="$HOME/bp-env"
CU_STABLE="https://download.pytorch.org/whl/cu130"
CU_NIGHTLY="https://download.pytorch.org/whl/nightly/cu130"

ensure_torch_cuda(){
  local ok
  ok=$(python -c 'import torch;print(int(torch.cuda.is_available()))' 2>/dev/null || echo 0)
  if [ "$ok" != "1" ]; then
    log "torch CUDA missing/clobbered -> reinstalling cu130 torch"
    uv pip install "torch==2.11.0" --index-url "$CU_STABLE" --reinstall-package torch \
      || uv pip install "torch==2.11.0" --index-url "$CU_NIGHTLY" --reinstall-package torch
  fi
}

log "uv venv $VENV (python 3.12)"
uv venv "$VENV" --python 3.12 || { log "venv FAILED"; exit 1; }
# shellcheck disable=SC1091
source "$VENV/bin/activate"

log "installing torch==2.11.0 (cu130)"
uv pip install "torch==2.11.0" --index-url "$CU_STABLE" \
  || uv pip install "torch==2.11.0" --index-url "$CU_NIGHTLY" \
  || { log "torch install FAILED"; exit 2; }

python -c "import torch;print('[verify] torch',torch.__version__,'cuda',torch.version.cuda,'avail',torch.cuda.is_available());print('[verify]',torch.cuda.get_device_name(0))" \
  || { log "torch CUDA verify FAILED"; exit 3; }

log "installing training stack (bitsandbytes peft trl transformers accelerate datasets)"
uv pip install bitsandbytes peft trl transformers accelerate datasets
ensure_torch_cuda

log "verify bitsandbytes import (cu130/sm_120 is bleeding-edge — capture any failure)"
python -c "import bitsandbytes as bnb; print('[verify] bnb', bnb.__version__)" 2>&1 | head -25 || log "bnb import had issues (see above)"

log "installing backpropagate (editable, local v1.5.0)"
uv pip install -e /mnt/e/AI/backpropagate 2>&1 | tail -6
ensure_torch_cuda

log "FINAL verify"
python -c "import torch;print('[final] torch',torch.__version__,'cuda-avail',torch.cuda.is_available())"
( backprop --version 2>&1 | head -2 ) || log "backprop --version unavailable"
log "--- backprop train flags (reasoning/rslora) ---"
( backprop train --help 2>&1 | grep -iE "reasoning|rslora|rank|method|mode|seq|seed|epoch" | head -20 ) || log "could not read backprop train --help"
log "DONE_SETUP"
