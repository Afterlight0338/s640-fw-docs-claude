# Veikk S640: SWD unbrick, firmware internals, and the zero-smoothing patch

Everything learned while bringing a bricked Veikk S640 drawing tablet back to life over SWD
with a Raspberry Pi Pico, then reading its firmware to find out where the report rate and
the cursor smoothing come from. Every number here was measured or read from the chip or the
firmware image. Things that were not verified say so.

Written 2026-10-06. Firmware analysed: Veikk's official update `S640-251022` (50,276 bytes,
SHA-256 `150fbc8b…287b45`).

> **Do not run anything here on a working tablet without reading section 3 first.** Getting
> SWD access requires removing the chip's read protection, and that **erases the whole flash**,
> including per-unit data that this document cannot give back to you (section 3.6).

## 0. How to flash

The short path. Section 3 explains every step, and [`docs/short.md`](docs/short.md) has the
same steps with the do's and don'ts.

**You need:** a Raspberry Pi Pico running Raspberry Pi's `debugprobe` firmware, 4 jumper
wires, a multimeter with a beep mode, OpenOCD 0.12, Python 3, and the tablet opened up.

**1. The stock firmware.** If you're reading this repo, you probably already know where to
obtain the firmware. You need `S640-251022.bin`. Check it first:

```
sha256sum S640-251022.bin
# 150fbc8b9cf356224245865c76ebab194083d72d32225921e6af55e83a287b45
```

If you have the `.hex`, convert it with the gaps filled as `0xFF` (the default fill of `0x00`
gives a different file):

```
objcopy -I ihex -O binary --gap-fill 0xff S640-251022.hex S640-251022.bin
```

**2. The patch.** That part is ours: [`patches/nosmooth.py`](patches/nosmooth.py) builds it
from the stock file. Run it in a folder that contains `S640-251022.bin`:

```
python3 nosmooth.py s640_nosmooth_nohold.bin --nohold
sha256sum s640_nosmooth_nohold.bin
# 371a4f7bc4ab181a1a41d58867bf31e7bc56dcaec656c0fe614f68995551877e
```

The script checks the original bytes before it changes anything and stops on a mismatch.
Without `--nohold` you get `nosmooth` (average removed, motion hold kept, 7.3).

**3. Wire the Pico to J1** (2.4): pad 2 (SWCLK) to GP2, pad 3 (SWDIO) to GP3, pad 5 (GND) to
GND. Pad 4 (NRST) to GP1 is optional: this unit had it wired, but the commands below use
`reset_config none`, so OpenOCD never drives it. Leave pad 1 (3V3) unconnected. Beep-test
every wire from the Pico pin to the chip pin.

**4. Connect and check read protection.**

```
openocd -f interface/cmsis-dap.cfg -c 'transport select swd; set CPUTAPID 0' -f target/stm32f1x.cfg -c 'adapter speed 1000; reset_config none; init; halt; mdw 0x4002201C; shutdown'
```

You want `SWD DPIDR 0x1ba01477`. If the value printed for `0x4002201C` ends in `2`, read
protection is on and has to be removed first. **That erases the whole chip**, including
Veikk's USB updater and the per-unit settings (3.5, 3.6):

```
openocd -f interface/cmsis-dap.cfg -c 'transport select swd; set CPUTAPID 0' -f target/stm32f1x.cfg -c 'adapter speed 1000; reset_config none; init; halt; stm32f1x unlock 0; shutdown'
```

Then unplug the tablet and plug it back in.

**5. Flash the patch and the factory tags.**

```
openocd -f interface/cmsis-dap.cfg -c 'transport select swd; set CPUTAPID 0' -f target/stm32f1x.cfg -c 'adapter speed 1000; reset_config none; init; halt; program s640_nosmooth_nohold.bin 0x08000000 verify; program factory_tags_fc60.bin 0x0800FC60 verify; reset run; shutdown'
```

Look for `** Verified OK **` twice. The tags ([`patches/factory_tags_fc60.bin`](patches/factory_tags_fc60.bin))
are required after an unlock: without them the pen is never detected (3.7, seen on two
tablets). Writing them again on a tablet that has them does no harm.

**Back to stock:** the same command with `S640-251022.bin`.
**Not over USB:** Veikk's USB updater skips the first 12 KB, which is where the patch is (3.1).

## Contents

1. [Quick facts](#1-quick-facts)
2. [Hardware](#2-hardware)
3. [How it was bricked, and how it was recovered](#3-how-it-was-bricked-and-how-it-was-recovered)
4. [The firmware image](#4-the-firmware-image)
5. [How the firmware works](#5-how-the-firmware-works)
6. [Report rate: why 1000 Hz is not possible here](#6-report-rate-why-1000-hz-is-not-possible-here)
7. [Zero smoothing](#7-zero-smoothing)
8. [Corrections to the earlier notes](#8-corrections-to-the-earlier-notes)
9. [Tools, scripts and data in this repository](#9-tools-scripts-and-data-in-this-repository)
10. [Checksums](#10-checksums)
11. [Open questions](#11-open-questions)
12. [Annotated listings](#12-annotated-listings)

---

## 1. Quick facts

| Thing | Value | How it was found |
| :--- | :--- | :--- |
| Unit used | one Veikk S640. It shipped with V1-format firmware and now runs `S640-251022`, which is V2 format. V1 and V2 are report formats, not hardware (2.6) | earlier notes' logs, `hidraw` |
| Tablet | Veikk S640, USB `2feb:0001`, manufacturer string `VEIKK.INC`, product `S640` | `lsusb`, kernel log |
| MCU marking | `VEIKK VK1801` (relabelled), LQFP64, 16 pins per side | photos |
| Core | ARM Cortex-M3 r2p1, CPUID `0x412FC231` | SWD read of `0xE000ED00` |
| SWD DPIDR | `0x1BA01477` | OpenOCD |
| Device ID (OpenOCD `stm32f1x` driver) | `0x13030410` | OpenOCD |
| Flash / SRAM | 64 KB / 8 KB (`0x1FFFF7E0` reads `0x00080040`) | SWD |
| Peripheral map | GigaDevice GD32F1x0 style: GPIO on AHB at `0x48000000`, USBD `0x40005C00`, FMC `0x40022000`, ADC `0x40012400` | firmware + SWD |
| System clock | 72.00 MHz (12 MHz crystal x 6 PLL, inferred from `RCU_CFG0 = 0x0011800A`) | DWT cycle counter over 1 s |
| Debug header | J1, 5 through-holes: 3V3, SWCLK, SWDIO, NRST, GND | multimeter |
| BOOT0 | pin 60, tied straight to GND (0 Ω) | multimeter |
| Read protection | was ON (`FMC_OBSTAT = 0xFFFFFF02`, option byte SPC = `0x00`) | SWD |
| Pen report rate | 250 Hz (4.0 ms), limited by the antenna scan, not USB | measured |
| USB polling | `bInterval 1` on all IN endpoints in `S640-251022` | descriptor + `lsusb -v` |
| Pen coordinates | 0.005 mm per unit (5080 LPI), X 0 to 30480, Y 0 to 20320 | report builder + measurements |
| Firmware smoothing | 8-sample boxcar on X/Y + a motion "hold" (deadzone), both removed by the nosmooth-nohold patch | breakpoints + RAM reads |

---

## 2. Hardware

### 2.1 The unit these notes come from

| | |
| :--- | :--- |
| Model | Veikk S640 (6 x 4 inch). The earlier notes called it a "V1"; that name only describes the firmware it shipped with (2.6) |
| PCB revision | no version or date marking on the parts of the board in the photos (front side around the MCU and the antenna front end) |
| USB | `2feb:0001`, `bcdDevice 0x0000`, strings `VEIKK.INC` / `S640` |
| MCU | marked `VEIKK VK1801`, LQFP64, device ID `0x13030410` |
| Firmware it came with | unknown version, never read out (lost in the unlock, 3.6). It sent 9-byte V1-format pen reports (logged 2026-09-15, for example `09 41 a0 74 15 30 29 00 00`), and the earlier notes measured `bInterval 3` on it |
| Firmware now | `S640-251022` with the nosmooth-nohold patch (7.4) |
| Pen | the pen that came with it; model not recorded. The hover frequency measurement returns a period of 2621 to 2687 TIMER2 ticks (5.7) |

If your tablet's MCU marking, USB ID, J1 layout or the bytes the patch scripts check differ
from this table, **stop**: you have different hardware or firmware, and nothing below is
known to apply.

### 2.2 Board

![Board with the J1 SWD wiring](images/s640_board_j1_swd_wiring.jpg)

Photo orientation used throughout this document: chip text `VK1801` upright, J1 is the
vertical column of 5 gold through-holes to the left of the chip, **pad 1 is the bottom hole**.
The USB cable is soldered to pads at the top (red = 5 V, black = GND, green and white = data).

Parts seen on the board (from the photos in `images/raw/`):

| Ref | Part | Notes |
| :--- | :--- | :--- |
| U1 | `VEIKK VK1801`, LQFP64 | the MCU, a relabelled GigaDevice GD32F1x0 class part (Cortex-M3 core with STM32F0 style peripherals) |
| OSC1 | crystal | below the chip in the photo above, wired to pins 5 and 6 (PF0/PF1). 12 MHz inferred from the PLL setting |
| U7, U8, U18, U19, U21, U22 | `HC4051` 8-channel analog multiplexers | select the antenna coils |
| U10, U11, U14 | `UTC MC4580` dual op-amps | receive amplifier and integrator chain |
| U4 | small IC left of J1 | probably the 3.3 V regulator (not traced); the rail measures 3.30 to 3.33 V |
| D1 | probably the status LED | top left in the rotated photo |
| R3, R13, R15 | resistors next to pins 44 and 45 | in the USB D+/D- path (PA11/PA12) |
| J2 | USB cable pads | |

`images/raw/IMG20260929140039.jpg` shows the antenna front end (the HC4051 and MC4580 parts).

### 2.3 MCU pins that matter

![Chip and J1, rotated view](images/s640_mcu_pinout_top_view.jpg)

The second photo is the board rotated 90 degrees clockwise (pin-1 dot at the top left, J1 as
a row above the chip). In it J1 pad 1 is the **left** hole, which is the same hole as
"bottom" in the first photo.

Standard LQFP64 numbering for this family (pin 1 at the dot, counting counter-clockwise).
Pins 7, 46, 49, 60, 63 and 64 were checked with a meter; the rest follow from the package
pinout and from what the firmware drives.

| Pin | Name | Use on this board |
| :--- | :--- | :--- |
| 5, 6 | PF0, PF1 | crystal |
| 7 | NRST | reset, also on J1 pad 4 |
| 22, 23 | PA6, PA7 | mux address lines (driven by the coil select routines) |
| 24 | PC4 | mux address line |
| 27 | PB1 | switched around every coil measurement (integrator or sample control, see 5.3) |
| 28 | PB2 | set or cleared per axis before each measurement (front-end path select) |
| 30 | PB11 | mux control (enable) |
| 37 to 40 | PC6, PC7, PC8, PC9 | excitation drive, toggled together (mask `0x3C0`) to generate the carrier |
| 41 | PA8 | mux control (enable) |
| 44, 45 | PA11, PA12 | USB D-, D+ |
| 46 | PA13 | SWDIO, also on J1 pad 3 |
| 49 | PA14 | SWCLK, also on J1 pad 2 |
| 60 | BOOT0 | tied to GND on the board |
| 63, 64 | VSS, VDD | |

### 2.4 J1 debug header

| J1 pad | Signal | Connects to | Volts, tablet powered | Diode reading to GND, unpowered |
| :--- | :--- | :--- | :--- | :--- |
| 1 (bottom) | 3V3 | VDD | 3.33 V | 761 (pin 64 reads about 760) |
| 2 | SWCLK | pin 49 (beep) | 0 V (PA14 has an internal pull-down) | open |
| 3 | SWDIO | pin 46 (beep) | 3.30 V (PA13 has an internal pull-up) | open |
| 4 | NRST | pin 7 (same voltage and diode reading) | 3.19 V | 1312 (pin 7 reads 1200 to 1300) |
| 5 (top) | GND | GND (beep) | 0 V | 002, beeps |

Wiring used for the recovery (Raspberry Pi Pico running `debugprobe_on_pico`):

| Pico pin (physical) | Pico GPIO | J1 pad |
| :--- | :--- | :--- |
| 4 | GP2 | 2, SWCLK |
| 5 | GP3 | 3, SWDIO |
| 3 | GND | 5, GND |
| 2 | GP1 | 4, NRST (optional, see 3.4) |
| none | none | 1, 3V3: leave unconnected, the tablet powers itself from USB |

Physical pin numbers count from the USB end of the Pico, on the row that starts with GP0.

### 2.5 BOOT0 cannot be used

BOOT0 (pin 60) measures **0 Ω to GND**. It is tied to ground on the board, so the chip
can never be strapped into its ROM bootloader from BOOT0. Bridging pin 64 (3.3 V) to pin 60,
which was tried on 2026-09-29, shorts the 3.3 V rail to GND. **Do not do it.** The tablet's
"enter DFU" USB command (section 3.1) jumps to Veikk's own bootloader in flash, which needs
working firmware to receive the command. With broken firmware, SWD is the only way in.

---

### 2.6 "V1" and "V2" are firmware, not hardware

OpenTabletDriver has two S640 configurations. Both use USB ID `2feb:0001`, the same size and
the same pressure range. The only difference is the pen report:

| OpenTabletDriver name | Report | Parser | X / Y |
| :--- | :--- | :--- | :--- |
| `VEIKK S640` ("V1") | 9 bytes | `VeikkV1ReportParser` | 16 bit |
| `VEIKK S640 V2` | 13 bytes | `VeikkReportParser` | 24 bit (bytes 3 to 5 and 6 to 8), pressure 16 bit at byte 9 |

The V2 configuration was added on 2021-06-15 (OpenTabletDriver commit `9771bfb1`, PR #1186).
In July 2021 people were already reporting "S640 v2" tablets that the older hawku
TabletDriver could not read (hawku/TabletDriver#1162). So from about mid-2021, S640s shipped
with firmware that sends the newer report.

What that means here:

* This unit sent 9-byte V1 reports before anything was flashed (2.1). On `S640-251022` it
  sends 13-byte reports (5.8). Same board, so **`S640-251022` is V2-format firmware**, and it
  runs fine on a tablet that shipped with V1-format firmware.
* **Any S640 running `S640-251022` shows up as "S640 V2"**, whatever it shipped with.
  Seeing "V2" after flashing it says nothing about the hardware.
* Another user's tablet, flashed with `S640-251022` after a mass erase, has the same board:
  marked `HK1102 VER02b` and `20180113`, with the same `VK1801`, J1, six HC4051 and MC4580
  layout, and the same 8 KB of SRAM.
* Whether Veikk ever made an S640 with different hardware is not known. Nothing found so far
  points to one.

## 3. How it was bricked, and how it was recovered

### 3.1 Before 2026-10-06 (from the earlier notes, written with another AI assistant)

These facts come from `history/VEIKK_S640_REVERSE_ENGINEERING_original.md` and the
scripts in `history/`. They were not re-tested on 2026-10-06 unless stated.

* The tablet exposes three HID interfaces: 0 = pen (boot mouse protocol), 1 = keys,
  2 = vendor channel with an OUT endpoint.
* OpenTabletDriver sends `09 01 04 00 00 00 00 00 00` on interface 2 to switch the tablet
  into its vendor reporting mode (the tablet answers `09 81 04 …`).
* Writing `00 09 04 2f eb 00 00 00 00 c0` (report ID 0 plus 9 bytes) to the interface 2
  hidraw node makes the tablet re-enumerate as `28e9:0189` (GigaDevice's USB ID) with the DFU
  alt-setting name `@Internal Flash  /0x08000000/12*001Ka,116*001Kg`.
* The earlier notes assumed that was the chip's ROM bootloader. **The firmware shows it is
  not** (verified 2026-10-06 in `asm/32_hardfault_reset_and_vendor_cmds.lst` and
  `asm/33_main_loop.lst`): the command is checked at `0x08001922` (`cmp r1,#0x2f`,
  `cmp r3,#0xeb`, `cmp r8,#0xc0`), which sets the byte at `0x20001030` and answers `0x84`.
  The main loop then sees that byte (`0x0800671A`), calls `0x08000BB8` and `0x08009A4E`
  (probably USB shutdown, not traced), waits for a 100-tick countdown at `0x2000100D`,
  disables TIMER5, and if the word at **`0x0800D800`** looks like a stack pointer (`word & 0x2FFE0000 == 0x20000000`)
  it loads it into MSP (`0x08000182`, `msr msp, r0`) and jumps to the address stored at
  **`0x0800D804`**. So the DFU bootloader is Veikk code at `0x0800D800` in the main flash,
  outside the firmware image.
* `dfu-util` failed on that bootloader with `LIBUSB_ERROR_OTHER` on SET_INTERFACE, so a
  custom pyusb flasher (`gd32_dfu_flash.py`) was used. The bootloader's descriptor marks the
  first 12 KB (`12*001Ka`) as read-only, and writes there were silently ignored. Read-back was
  refused.
* `S640-251022.bin` was flashed through that DFU; only the part from `0x08003000` up
  actually landed. The earlier notes record the tablet at 248.8 Hz before and 247.8 Hz after.
* `flash_500hz.py` then erased the pages from `0x08003000` to the end of the image
  (`0x08003000` to about `0x0800C7FF`) and started programming page by page. Per the owner,
  the script died partway through programming. Nothing in the script restores the erased pages
  if a step fails, so the flash was left with an intact first 12 KB (old code) and a partly
  erased rest. Its payload, `s640_firmware_500hz.bin`, only changed the three `bInterval`
  bytes of the USB configuration descriptor from 1 to 2 (`0x0800A57F`, `0x0800A598`,
  `0x0800A5B1`). That would have **halved** the USB polling rate, so the "500 Hz" patch could
  never have worked.
* Result: no LED, nothing on USB. The HardFault handler of this firmware (`0x08001588`) is
  `msr faultmask` followed by a system reset through AIRCR (`0x05FA0004` into `0xE000ED0C`),
  so a crash just restarts the chip forever without ever enumerating.
* 2026-09-29: BOOT0 attempts (no effect, BOOT0 is grounded). 2026-10-03: first SWD attempt
  with a Pico failed with `cannot read IDR` (wiring was unverified at the time). A MicroPython
  pad scanner (`tools/padscan.sh`) was written to find the J1 pinout with the Pico's ADC; it
  never logged a reading (`data/padscan.log` only has serial-port errors).

### 3.2 Finding the debug pins with a multimeter

Done in three rounds. All values are in `data/session_outputs_2026-10-06.txt`.

1. **Tablet powered, DC volts, black probe on the black USB wire.** Pin 64 read 3.3 V, so the
   chip has power; pin 7 (NRST) read a steady 3.19 V, so the chip is not held in reset; pin 60
   read 0 V. J1 pads bottom to top: 3.33, 0, 3.30, 3.19, 0 V.
2. **Unpowered, diode/continuity mode against GND.** J1 pads: 761, open, open, 1312, beep.
   Pin 64 about 760, pin 7 1200 to 1300, pins 49 and 46 open. Matching readings identify pad 1
   as VDD and pad 4 as NRST; the beep makes pad 5 GND.
3. **Unpowered, ohms.** BOOT0 to GND: 0. Continuity pad 2 to pin 49 and pad 3 to pin 46: both beep.

The SWCLK/SWDIO split also matches the reset state of the pins: PA14 (SWCLK) has an internal
pull-down (0 V on pad 2), PA13 (SWDIO) a pull-up (3.30 V on pad 3).

### 3.3 Turning a Pico into an SWD probe

1. Hold BOOTSEL and plug the Pico in. It appears as `2e8a:0003 RP2 Boot` with a drive called `RPI-RP2`.
2. Copy `debugprobe_on_pico.uf2` onto it (SHA-256 in section 10). It re-enumerates as
   `2e8a:000c Raspberry Pi Debugprobe on Pico (CMSIS-DAP)`, firmware version 2.0.0.
3. Wire it as in 2.4. Then plug in the tablet first and the Pico second.

A charge-only USB cable is a common reason for the Pico not appearing at all.

### 3.4 Connecting, and what went wrong first

OpenOCD 0.12.0 (`nix-shell -p openocd`). The command that works on this tablet:

```
openocd -f interface/cmsis-dap.cfg -c 'transport select swd; set CPUTAPID 0' \
        -f target/stm32f1x.cfg -c 'adapter speed 1000; reset_config none' -c 'init; halt'
```

* `set CPUTAPID 0` stops the `stm32f1x` config from rejecting a non-ST ID.
* `adapter speed` must come **after** `target/stm32f1x.cfg`, which sets 1000 kHz itself.
* `reset_config none` connects to the running chip. Connect-under-reset
  (`srst_only srst_nogate connect_assert_srst`) **did not work** on this board: DPIDR read
  back as `0xFFFFFFFF` and halt timed out after "external reset detected".

`Error connecting DP: cannot read IDR` appeared at every speed (1 MHz, 100 kHz, 50 kHz,
10 kHz) until the wiring was fixed. Two wiring faults caused it, found with the meter by
beeping from the **Pico pin to the chip pin** (not just to the J1 pad):

1. On the first try there were no wires between the Pico and the tablet at all.
2. On the second, the SWDIO wire touched both pad 2 and pad 3 (GP3 beeped to pins 46 and 49)
   and the SWCLK wire touched nothing.

Once the wiring was right:

```
Info : SWD DPIDR 0x1ba01477
Info : [stm32f1x.cpu] Cortex-M3 r2p1 processor detected
Info : [stm32f1x.cpu] target has 6 breakpoints, 4 watchpoints
Error: [stm32f1x.cpu] clearing lockup after double fault
Error: Failed to read memory at 0x08000004
```

The core was in **lockup** (a fault while handling a fault), PC `0x08001210`. Flash reads
failed because of read protection:

| Address | Value | Meaning |
| :--- | :--- | :--- |
| `0x4002201C` FMC_OBSTAT | `0xFFFFFF02` | bit 1 set: flash read protection active |
| `0x40022010` FMC_CTL | `0x00000080` | LK set (flash controller locked) |
| `0x1FFFF800` option bytes | `00ffff00 00ff00ff 00ff00ff 00ff00ff` | SPC = `0x00`, nSPC = `0xFF` (anything other than `0xA5` = protected) |
| `0x1FFFF7E0` | `0x00080040` | 64 KB flash, 8 KB SRAM |
| `0xE000ED00` CPUID | `0x412FC231` | Cortex-M3 r2p1 |
| `0xE000EDF0` DHCSR | `0x00030003` | halted under debug |
| `0x20000000` | `d5dffd01 02c9b8b6 0bd8be20 1add3856` | SRAM content at that moment |

Read protection explains why SWD could not read flash. Why the DFU bootloader refused the
first 12 KB is not proven: its own descriptor declares those 12 pages read-only (`a`), and
read protection on GigaDevice and ST parts also write-protects the first pages, so either
could be the reason.

### 3.5 Removing read protection (mass erase)

```
openocd … -c 'init; halt; stm32f1x unlock 0; shutdown'
```

OpenOCD printed `device id = 0x13030410` and `flash size = 64 KiB`. The option bytes then
read `00ff5aa5 …` (SPC = `0xA5`, unprotected) but `FMC_OBSTAT` still showed protection until
the tablet was **unplugged and plugged back in** (option bytes are loaded at power-on). After
that `FMC_OBSTAT = 0xFFFFFF00` and the whole flash read `0xFFFFFFFF`.

### 3.6 What the mass erase destroys

| Region | Content | Can it be restored? |
| :--- | :--- | :--- |
| `0x08000000` to `0x0800C463` | firmware | yes, `S640-251022.bin` is a complete image from `0x08000000` (vector table at 0) |
| `0x0800D000`, `0x0800D400` | settings pages the firmware loads at start and rewrites (section 4.4) | **no**, per-unit content. The tablet tracks the pen without them |
| `0x0800D800` up to `0x0800FC5F` | **Veikk's DFU bootloader** (3.1) | **no**. It is not in any public file we have. Consequence: the "enter DFU" command and Veikk's USB updater no longer work on this tablet; the firmware checks for a valid vector table at `0x0800D800` first, so the command just does nothing now. Update over SWD instead |
| `0x0800FC60` to `0x0800FC7F` | factory tags checked by the firmware | **yes**, the four expected values are constants in the firmware (4.3) |
| anything else outside the image | unknown | unknown |

The tablet's original firmware version (whatever was on it before the DFU flash in 3.1) is
also gone; it was never read out. If you own a working S640, a dump of `0x0800D000` to
`0x0800FFFF` (bootloader, settings and tags) would fill the gaps in this document.

If you have a working tablet and want to keep its original flash, look at the published
GD32F1x0 read-protection bypass by Positive Technologies ("GigaVulnerability") before
unlocking. It was **not tried here**.

### 3.7 Flashing the firmware back

```
openocd -f interface/cmsis-dap.cfg -c 'transport select swd; set CPUTAPID 0' \
        -f target/stm32f1x.cfg -c 'adapter speed 1000; reset_config none; init; halt;
          program S640-251022.bin 0x08000000 verify;
          program patches/factory_tags_fc60.bin 0x0800FC60 verify;
          reset run; shutdown'
```

Both writes printed `** Verified OK **`, and the tablet came up as `2feb:0001` with the pen
working. The factory tags only need writing once; later firmware flashes do not erase that
page (they only erase the pages the image covers).

`patches/factory_tags_fc60.bin` (32 bytes, unused bytes `0xFF`):

```
0x0800FC60: 55 47 45 45 ff ff ff ff   "UGEE"
0x0800FC68: 33 37 32 31 ff ff ff ff   "3721"
0x0800FC70: 30 32 32 36 ff ff ff ff   "0226"
0x0800FC78: 8c 42 09 d2 ff ff ff ff   0xD209428C
```

Without the `"3721"` tag the tracking scan returns immediately (4.3) and the pen is never
detected. That is the first thing to check if a re-flashed tablet sees no pen.

**Seen on a second tablet (2026-10-07):** another user mass-erased their S640 and flashed
`S640-251022`. The tablet showed up on USB but never detected the pen. Writing
`factory_tags_fc60.bin` brought the pen back. With the stock firmware they then saw the
cursor lag and creep into place whenever the pen slowed down or stopped, which is the stock
motion hold and 8-sample average (5.8), the two things `nosmooth-nohold` removes.

### 3.8 Flashing any image later

With the Pico still wired:

```
cd veikk-s640-zero-smoothing
nix-shell -p openocd --run "openocd -f interface/cmsis-dap.cfg -c 'transport select swd; set CPUTAPID 0' -f target/stm32f1x.cfg -c 'adapter speed 1000; reset_config none; init; halt; program s640_nosmooth_nohold.bin 0x08000000 verify; reset run; shutdown'"
```

Look for `** Verified OK **`. The tablet restarts by itself. **Never flash images from this
project through Veikk's USB DFU:** it silently skips the first 12 KB, which is exactly where
the zero-smoothing patches are, and an interrupted DFU flash is how this tablet was bricked.
