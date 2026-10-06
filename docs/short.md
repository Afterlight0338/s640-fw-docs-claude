## What this is

A Veikk S640 bricked by a bad USB flash, revived over SWD with a Raspberry Pi Pico, then
patched so the firmware stops smoothing the cursor. This is the short version: what you need,
what to run, what not to do. The long version has the why, the proof and every byte.

## Is this your tablet?

Only go on if all of these match. If anything differs, stop.

| Check | Must be |
| :--- | :--- |
| Tablet | Veikk S640 (this one is the "V1"; an S640 V2 was never tested) |
| USB ID when working | `2feb:0001`, product `S640` |
| Chip marking | `VEIKK VK1801`, 64 pins (16 per side) |
| Debug header | J1, five gold through-holes in a row next to the chip |

## What you need

* Raspberry Pi Pico (RP2040) and a USB cable that carries **data**
* `debugprobe_on_pico.uf2` (Raspberry Pi's official debugprobe firmware)
* 4 female-to-male jumper wires
* a multimeter with a beep/continuity mode
* OpenOCD 0.12 (`nix-shell -p openocd` on NixOS)
* `S640-251022.bin` (Veikk's firmware update, SHA-256 starts with `150fbc8b`)
* from the GitHub repo: [`patches/nosmooth.py`](patches/nosmooth.py) and [`patches/factory_tags_fc60.bin`](patches/factory_tags_fc60.bin)

## Wiring

Hold the board so the chip text `VK1801` reads upright. J1 is the column of 5 holes left of
the chip. **Pad 1 is the bottom one.**

| J1 pad | Signal | Pico pin (count from the USB end, GP0 row) |
| :--- | :--- | :--- |
| 1 | 3V3 | **nothing, leave it alone** |
| 2 | SWCLK | pin 4 (GP2) |
| 3 | SWDIO | pin 5 (GP3) |
| 4 | NRST | pin 2 (GP1), optional |
| 5 | GND | pin 3 (GND) |

![J1 wiring](images/s640_board_j1_swd_wiring.jpg)

Then **beep-test every wire from the Pico pin to the chip pin**: GP2 to chip pin 49, GP3 to
chip pin 46, GND to pad 5. GP2 and GP3 must **not** beep to each other. Most "it doesn't
connect" problems are a wire that isn't touching or one that touches two holes.

## Steps

**1. Pico.** Hold BOOTSEL, plug it in, copy `debugprobe_on_pico.uf2` onto the `RPI-RP2` drive.

**2. Plug in the tablet first**, then the Pico.

**3. Connect.**

```
openocd -f interface/cmsis-dap.cfg -c 'transport select swd; set CPUTAPID 0' -f target/stm32f1x.cfg -c 'adapter speed 1000; reset_config none; init; halt; mdw 0x4002201C; shutdown'
```

You want `SWD DPIDR 0x1ba01477` and `Cortex-M3 r2p1`. `cannot read IDR` = wiring, go back
and beep-test.

**4. Only if flash is read-protected** (the value at `0x4002201C` ends in `2`, or flash reads
fail). Unlocking **erases everything** on the chip, including Veikk's USB updater and per-unit
settings that you cannot get back. Only do this on a tablet that is already dead.

```
openocd -f interface/cmsis-dap.cfg -c 'transport select swd; set CPUTAPID 0' -f target/stm32f1x.cfg -c 'adapter speed 1000; reset_config none; init; halt; stm32f1x unlock 0; shutdown'
```

Then **unplug the tablet and plug it back in.**

**5. Build the patched firmware** (in a folder with `S640-251022.bin` in it):

```
python3 nosmooth.py s640_firmware_nosmooth_v2.bin --nodeadzone
sha256sum s640_firmware_nosmooth_v2.bin
# 371a4f7bc4ab181a1a41d58867bf31e7bc56dcaec656c0fe614f68995551877e
```

**6. Flash it, plus the factory tags** (the tags only matter after an unlock, but writing them
again does no harm):

```
openocd -f interface/cmsis-dap.cfg -c 'transport select swd; set CPUTAPID 0' -f target/stm32f1x.cfg -c 'adapter speed 1000; reset_config none; init; halt; program s640_firmware_nosmooth_v2.bin 0x08000000 verify; program factory_tags_fc60.bin 0x0800FC60 verify; reset run; shutdown'
```

Look for `** Verified OK **` twice. The tablet restarts on its own.

To go back to stock, flash `S640-251022.bin` the same way.

## Do

* Beep-test Pico pin to **chip pin**, not just to the J1 hole.
* Put `adapter speed` **after** `target/stm32f1x.cfg` (the target file overrides it otherwise).
* Use `reset_config none`. Connect-under-reset does not work on this board.
* Write the factory tags after any unlock. Without them the pen is never detected.
* Lift the pen away and bring it back after flashing anything, to check it is picked up again.

## Don't

* **Don't bridge BOOT0 (pin 60) to 3.3 V.** BOOT0 is wired straight to ground; that is a short.
* **Don't connect J1 pad 1** (3V3) to the Pico. The tablet powers itself from USB.
* **Don't flash anything from this project through Veikk's USB updater / DFU.** It skips the
  first 12 KB (where the patch is) and an interrupted DFU flash is how this tablet died.
* **Don't use the old scripts in [`history/`](history/)**: `flash_500hz.py` bricked it, and the old
  "zero smoothing" image (`bx lr` at `0x08000310`) would stop all pen reports.
* **Don't expect 1000 Hz.** The antenna scan takes about 3.9 ms, so 250 Hz is it. The USB side
  is already 1 ms.
* **Don't try the speed hacks**: skipping the pressure measurement kills pen detection, and
  shrinking the coil window loses the pen for good once you lift it.

## What you get

| | Stock | Patched (v2) |
| :--- | :--- | :--- |
| Position smoothing | 8-sample average (about 14 ms of lag) | none, every report is the newest sample |
| Motion "deadzone" | holds the cursor on small moves | gone |
| Reports, pen held still | about 208 per second | about 267 per second |
| Report rate, pen moving | 250 Hz | 250 Hz |
| Still-pen jitter | 0 (hidden by the deadzone) | about 0.03 mm (filter it in OpenTabletDriver if it bugs you) |
| Pressure | 8-sample average, 4-report tip debounce | unchanged |

## If something goes wrong

| Symptom | Likely cause |
| :--- | :--- |
| `cannot read IDR` | wiring. Beep-test again |
| `Failed to read memory at 0x08000004` | flash is read-protected, see step 4 |
| tablet shows up on USB but the pen is never detected | factory tags missing, write `factory_tags_fc60.bin` |
| pen works, then never comes back after lifting it | you flashed a build with the window hack, flash v2 again |
| nothing on USB at all, no LED | firmware broken. SWD in, flash `S640-251022.bin` + tags |
