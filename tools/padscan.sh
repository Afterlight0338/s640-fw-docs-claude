#!/usr/bin/env nix-shell
#! nix-shell -i bash -p mpremote
# Probe J1 pads with the Pico (MicroPython on GP26). Run: ./padscan.sh
# Per pad it measures GP26 with pull-up and with pull-down and logs to padscan.log.
#   GND: up~0 down~0 | 3V3: up~3.3 down~3.3 | floating/no contact: up~3.3 down~0
#   MCU pin with pull-down (SWCLK?): up mid, down~0 | with pull-up (SWDIO/RST?): up~3.3, down mid
PORT=${PORT:-/dev/ttyACM0}
LOG="$(dirname "$0")/padscan.log"
PY='
from machine import ADC, mem32
import time
a = ADC(26)
reg = 0x4001C000 + 4 + 26 * 4
def meas(bit):
    mem32[reg] = (mem32[reg] & ~0xC) | bit
    time.sleep_ms(50)
    v = sorted(a.read_u16() * 3.3 / 65535 for _ in range(15) if not time.sleep_ms(100))
    return v[7], v[-1] - v[0]
up, su = meas(0x8)
dn, sd = meas(0x4)
mem32[reg] = mem32[reg] & ~0xC
print("%.2f %.2f %.2f %.2f" % (up, dn, su, sd))
'
echo "Pico GND must be on a black USB pad. Never touch the red (5V) pad." | tee -a "$LOG"
echo "Press Enter to measure, hold the probe still for ~3 s. Type q to quit."
for pad in 1 2 3 4 5; do
  while true; do
    read -rp "Probe on J1 pad $pad (1=bottom..5=top), press Enter: " k
    [ "$k" = q ] && exit 0
    out=$(mpremote connect "$PORT" exec "$PY" 2>&1 | tail -1)
    read -r up dn su sd <<<"$out"
    if ! [[ "$sd" =~ ^[0-9.]+$ ]]; then
      echo "  error: $out"
      [ -w "$PORT" ] || echo "  fix: sudo chmod 666 $PORT (the Pico re-enumerated, permissions reset)"
      continue
    fi
    unstable=$(awk -v a="$su" -v b="$sd" 'BEGIN{print (a>0.3||b>0.3)?"UNSTABLE":"ok"}')
    line="pad $pad: pullup=${up}V pulldown=${dn}V spread=${su}/${sd} $unstable"
    echo "  $line"; echo "$(date +%T) $line" >> "$LOG"
    [ "$unstable" = ok ] && break
    echo "  contact moved, redo"
  done
done
echo done
