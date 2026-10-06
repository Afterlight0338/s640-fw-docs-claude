#!/bin/bash
set -e

echo "[1/4] Installing udev rule for GD32 DFU access..."
cp /home/afterlight/veikk-s640-zero-smoothing/99-veikk-gd32-dfu.rules /etc/udev/rules.d/99-veikk-gd32-dfu.rules
udevadm control --reload-rules
udevadm trigger
echo "     udev rule installed."

echo "[2/4] Stopping OpenTabletDriver..."
systemctl --user -M afterlight@ stop opentabletdriver 2>/dev/null || true

echo "[3/4] Sending DFU reset command to /dev/hidraw5..."
/home/afterlight/veikk-s640-zero-smoothing/send_dfu_reset /dev/hidraw5
sleep 3

echo "[4/4] Flashing zero-smoothing firmware..."
lsusb | grep 28e9
nix-shell -p dfu-util --run "dfu-util -d 28e9:0189 -a 0 -s 0x08000000:leave -D /home/afterlight/veikk-s640-zero-smoothing/s640_firmware_zero_smoothing.bin"
echo "Done!"
