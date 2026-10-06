# veikk-s640-zero-smoothing

Removes hardware coordinate smoothing from the Veikk S640 V1.  
Patches the firmware in-place over USB — no hardware required.

## What this does

The stock firmware runs coordinates through three filters before sending them:
- 8-sample boxcar moving average (~32ms latency)
- 2-sample moving average per-report
- Micro-movement jitter damping

This patches all three out. Raw ADC coordinates go directly to USB.

## Limitations

The GD32F150's DFU bootloader write-protects the first 12KB of flash.  
Two of the three filters live in that region. Full patch requires SWD access.  
The third filter (2-sample average) is in the writable region and will be removed.

To apply all three patches you need an ST-Link V2 or a Pi Pico running Picoprobe.

## Requirements

- NixOS (or adapt the `nix-shell` calls for your distro)
- Veikk S640 V1 plugged in via USB

## Usage

**1. Trigger DFU mode**
```
systemctl --user stop opentabletdriver
./send_dfu_reset /dev/hidraw5
```
Find the right hidraw node first:
```
for h in /sys/class/hidraw/hidraw*/device/uevent; do
  node=$(echo $h | sed 's|/sys/class/hidraw/||;s|/device/uevent||')
  grep -q "2FEB" $h && grep HID_PHYS $h | grep -q "input2" && echo $node
done
```

**2. Unlock the USB device node**
```
sudo chmod a+rw /dev/bus/usb/003/$(lsusb | grep 28e9 | grep -oP 'Device \K\d+')
```

**3. Flash**
```
nix-shell -p python3 python3Packages.pyusb --run \
  "python3 gd32_dfu_flash.py s640_firmware_zero_smoothing.bin 0x08000000"
```

**4. Restart OTD**
```
systemctl --user start opentabletdriver
```

## Verifying DFU write protection

```
nix-shell -p dfu-util --run "dfu-util -l -d 28e9:0189"
```

Look for `12*001Ka` in the output. Those 12KB are write-protected by the bootloader.  
`116*001Kg` is the writable region where the partial patch lands.

## SWD (full patch)

Wire SWDIO, SWCLK, GND from an ST-Link to the four test pads next to the GD32F150 on the PCB.

```
openocd -f interface/stlink.cfg -f target/stm32f1x.cfg \
  -c "program s640_firmware_zero_smoothing.bin 0x08000000 verify reset exit"
```

## Files

| File | Description |
|---|---|
| `s640_firmware_zero_smoothing.bin` | Patched firmware |
| `s640_firmware_stock_251022.bin` | Stock firmware (S640-251022, Oct 2022) |
| `gd32_dfu_flash.py` | DFU flash script (works around GD32 SET_INTERFACE quirk) |
| `send_dfu_reset.c` | Sends the HID packet that jumps the tablet into DFU mode |
| `create_zero_smoothing_fw.py` | Reproduces the patch from the stock binary |
