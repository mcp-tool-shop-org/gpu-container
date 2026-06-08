#!/usr/bin/env bash
# Sample GPU utilization (%) every 1s for ~25s — characterize how hard training is pushing the 5090.
mn=100; mx=0; sum=0; n=0
for i in $(seq 1 25); do
  u=$(nvidia-smi --query-gpu=utilization.gpu --format=csv,noheader,nounits 2>/dev/null | head -1)
  if [ -n "$u" ]; then
    if [ "$u" -lt "$mn" ]; then mn=$u; fi
    if [ "$u" -gt "$mx" ]; then mx=$u; fi
    sum=$((sum + u)); n=$((n + 1))
  fi
  sleep 1
done
[ "$n" -gt 0 ] && echo "util n=$n min=$mn max=$mx avg=$((sum / n))"
