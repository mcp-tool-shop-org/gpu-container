#!/usr/bin/env bash
# ~4-min sampler spanning the 14B config-test (load ~3min + steps): peak VRAM (MiB) + util stats.
mv=0; umx=0; usum=0; un=0
for i in $(seq 1 120); do
  v=$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits 2>/dev/null | head -1)
  u=$(nvidia-smi --query-gpu=utilization.gpu --format=csv,noheader,nounits 2>/dev/null | head -1)
  if [ -n "$v" ] && [ "$v" -gt "$mv" ]; then mv=$v; fi
  if [ -n "$u" ]; then
    if [ "$u" -gt "$umx" ]; then umx=$u; fi
    usum=$((usum + u)); un=$((un + 1))
  fi
  sleep 2
done
[ "$un" -gt 0 ] && echo "PEAK_VRAM_MIB=$mv util_max=$umx util_avg=$((usum / un))"
