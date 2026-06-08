#!/usr/bin/env bash
# Sample GPU temp (C) every 15s for ~10min — verify the sustained-training thermal plateau stays
# under the watchdog's 87C abort. Reports peak; if it's creeping toward 87 I power-limit proactively.
mt=0; last=0
for i in $(seq 1 40); do
  t=$(nvidia-smi --query-gpu=temperature.gpu --format=csv,noheader,nounits 2>/dev/null | head -1)
  if [ -n "$t" ]; then
    if [ "$t" -gt "$mt" ]; then mt=$t; fi
    last=$t
  fi
  sleep 15
done
echo "PEAK_TEMP_C=$mt LAST_TEMP_C=$last"
