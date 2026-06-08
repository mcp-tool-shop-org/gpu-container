#!/usr/bin/env bash
# Sample peak GPU VRAM (MiB) every 2s for ~120s — rig-safety check during the 14B config-test.
m=0
for i in $(seq 1 60); do
  v=$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits 2>/dev/null | head -1)
  if [ -n "$v" ] && [ "$v" -gt "$m" ]; then m=$v; fi
  sleep 2
done
echo "PEAK_VRAM_MIB=$m"
