
---

## 4. The firmware image

### 4.1 Files

| File | Size | SHA-256 | Notes |
| :--- | :--- | :--- | :--- |
| `S640-251022.hex` (as `s640_firmware_stock_251022.hex`) | 132,786 bytes | `8bbc8c49…297319` | Veikk's update file, Intel HEX. "251022" is in the name, probably 2025-10-22 |
| `S640-251022.bin` | 50,276 bytes (`0xC464`) | `150fbc8b…287b45` | same content as raw binary, linked at `0x08000000` |

**Neither file is in this repository** (it is Veikk's firmware). Every patch script checks the
input bytes before changing them, so they refuse anything that is not this exact image.

The image starts with its vector table at `0x08000000` and contains no bootloader. Full
vector table: `asm/00_data_tables.txt`. The entries that matter:

| Vector | Handler | What it does |
| :--- | :--- | :--- |
| initial SP | `0x200018F0` | top of the stack, 6.2 KB into the 8 KB SRAM |
| Reset | `0x08000190` | calls SystemInit `0x080040F8` (clocks), then the C runtime at `0x0800015A`, which ends in the main loop (`0x0800664C`) |
| NMI | `0x08001E24` | |
| HardFault | `0x08001588` | `msr faultmask`, then system reset (AIRCR = `0x05FA0004`). A crash restarts the chip |
| SVCall | `0x080023B8` | `bx lr` (empty) |
| PendSV | `0x08001EE0` | `bx lr` (empty) |
| SysTick | `0x080040F4` | branch veneers to `0x08005860` |
| IRQ0 | `0x0800662C` | `bx lr` (empty) |
| IRQ5, IRQ6, IRQ7 (EXTI) | `0x08000C40`, `0x08000C42`, `0x08000C44` | the first two are `bx lr` |
| IRQ16 (TIMER2) | `0x080041B8` | stores TIMER2 channel 2 captures into a 20-entry ring at `0x20001474` (count at `0x20000033`) |
| IRQ17 (TIMER5) | `0x080041FC` | 200 Hz housekeeping tick, continues at `0x08004544` |
| all others | `0x080001AA` | `b .` (hangs) |

### 4.2 Flash map (64 KB)

| Range | Content |
| :--- | :--- |
| `0x08000000` to `0x0800C463` | firmware image `S640-251022` |
| `0x0800C464` to `0x0800CFFF` | unused (erased) |
| `0x0800D000` to `0x0800D3FF` | settings page A (4.4) |
| `0x0800D400` to `0x0800D7FF` | settings page B (4.4) |
| `0x0800D800` to `0x0800FC5F` | Veikk DFU bootloader (3.1). Lost on this unit |
| `0x0800FC60` to `0x0800FC7F` | factory tags (4.3) |
| `0x0800FC80` to `0x0800FFFF` | unknown |

Pages are 1 KB. The firmware references `0x0800C464` (the end of its own image) and the
addresses above; nothing else past the image. The `0x0800C464` reference is a C startup
table entry at `0x08007320` that zeroes `0x77C` bytes of RAM at `0x20001174`; its handler
(`0x0800663E`) never reads the source address, so the flash after the image really is free.

### 4.3 Factory tags

Four 32-bit words at the end of flash. Each gates one function: if the word is wrong, that
function returns without doing anything.

| Address | Expected | Checked at | Gates | Effect when missing |
| :--- | :--- | :--- | :--- | :--- |
| `0x0800FC60` | `0x45454755` (`"UGEE"`) | `0x080023BE` | full scan of all 26 X and 18 Y coils (`0x080023BC`, 5.6) | pen never acquired |
| `0x0800FC68` | `0x31323733` (`"3721"`) | `0x08002FC8` | tracking scan (`0x08002FC4`, 5.6) | pen never tracked |
| `0x0800FC70` | `0x36323230` (`"0226"`) | `0x08006556` | baseline subtraction (`0x08006554`, 5.6) | coil amplitudes never updated |
| `0x0800FC78` | `0xD209428C` | `0x08001EF2` | frequency, button and pressure routine (`0x08001EE4`, 5.7) | no pen state, no reports |

UGEE is the Chinese tablet maker behind XP-Pen; the tag suggests this firmware comes from UGEE code (not verified). The values are fixed constants in the firmware, not derived from the chip ID, so the same 32 bytes work on any S640 with this firmware.

{{lst 08_full_coil_scan 0x080023bc 0x080023ca}}

### 4.4 Settings pages

| Routine | Does |
| :--- | :--- |
| `0x08008268` | copies page `0x0800D000` into RAM at `0x200004E5` (called once at start, `0x08006650`) |
| `0x080082A0` | loads fields from page `0x0800D400` into `0x2000108E`, `0x2000003E`, `0x20001090`, `0x20000040`, `0x20001092`, `0x200008E5` (block), `0x20001058`, `0x20001054` (called at start, `0x08006654`) |
| `0x080083A0` | erases and rewrites page `0x0800D000` from RAM (called from the vendor command handler, `0x0800198C`) |
| `0x08008408` | erases and rewrites page `0x0800D400` (called from `0x08001ABA`, `0x08001B2C`, and from the pen routine at `0x0800209C`/`0x080020C8`) |

Flash helpers used by those: `0x08008230` (unlock), `0x08008188` (page erase),
`0x080081FC` (program), `0x0800817C` (wait).

The pen routine calls the page B save when the byte at `0x20001054` changes to 1 or 2. That
happens after a counter at `0x20001048` reaches 500 (`0x1F4`) reports in a particular pen
frequency band, which looks like "hold a pen button for about 2 seconds to switch a mode".
`0x20001054` is also used by the report builder to pick a smaller Y range
(`0x2E8C` instead of `0x40C4`). What the mode is for was not worked out. With both pages
blank (`0xFF`) after the mass erase, position tracking works normally. Pressure, pen buttons
and express keys were **not tested** after the restore.

### 4.5 USB descriptors in the image

Device descriptor at `0x0800A3F0`: `12 01 10 01 00 00 00 40 eb 2f 01 00 00 00 01 02 03 01`
(USB 1.10, EP0 64 bytes, VID `0x2FEB`, PID `0x0001`, bcdDevice 0, string indexes 1/2/3,
1 configuration).

Configuration descriptor at `0x0800A55E` (91 bytes):

| Offset | Descriptor | Bytes | Meaning |
| :--- | :--- | :--- | :--- |
| +0x00 | configuration | `09 02 5b 00 03 01 00 80 32` | 91 bytes total, 3 interfaces, bus powered, 100 mA |
| +0x09 | interface 0 | `09 04 00 00 01 03 01 02 00` | HID, boot subclass, mouse protocol, 1 endpoint |
| +0x12 | HID | `09 21 00 01 00 01 22 89 00` | report descriptor 137 bytes |
| +0x1B | endpoint | `07 05 81 03 08 00 01` | EP1 IN, interrupt, 8 bytes, **bInterval 1** |
| +0x22 | interface 1 | `09 04 01 00 01 03 01 02 00` | HID, boot subclass, mouse protocol, 1 endpoint |
| +0x2B | HID | `09 21 00 01 00 01 22 9d 00` | report descriptor 157 bytes |
| +0x34 | endpoint | `07 05 82 03 0a 00 01` | EP2 IN, interrupt, 10 bytes, **bInterval 1** |
| +0x3B | interface 2 | `09 04 02 00 02 03 00 00 00` | HID, no subclass, 2 endpoints |
| +0x44 | HID | `09 21 00 01 00 01 22 24 00` | report descriptor 36 bytes |
| +0x4D | endpoint | `07 05 83 03 10 00 01` | EP3 IN, interrupt, 16 bytes, **bInterval 1** |
| +0x54 | endpoint | `07 05 03 03 10 00 0a` | EP3 OUT, interrupt, 16 bytes, bInterval 10 |

`lsusb -v` on the restored tablet shows the same values. The host already polls the pen
endpoints every 1 ms.

---

## 5. How the firmware works

### 5.1 Main loop and modes

Everything runs in one loop in `main` (`0x0800664C`, `asm/33_main_loop.lst`). Interrupts
only collect timer captures (TIMER2) and run a 200 Hz tick (TIMER5). The pen state machine
lives in the byte at `0x2000100B`:

| Mode | Per pass of the loop | Meaning |
| :--- | :--- | :--- |
| 0 | `0x0800925C` while the byte at `0x20001023` is clear; otherwise the search `0x080010F8` (and `0x080080F8` every 100 passes); a hit switches to mode 1 | no pen |
| 3 | search `0x080010F8`; a hit switches straight to mode 2 and copies the peak coils from `0x2000100E`/`0x2000100F` | re-acquiring |
| 1 | full scan `0x080023BC` (all coils), `0x080064DC`, `0x08000D0C` (tuner), position `0x08002834`, `0x08000390`, `0x08000AF4`, window `0x08003CC8` | pen just found |
| 2 | tracking scan `0x08002FC4`, baseline `0x08006554`, `0x08000D0C` (tuner), position `0x08002834`, `0x08000390`, `0x08000B24`, window `0x08003CC8`, pen routine `0x08001EE4`, `0x08000A3C`, then the report builder `0x08008780` **only if the byte at `0x20001031` is set** | tracking (normal use) |

The byte at `0x20001031` is set by the boxcar output routine (5.8). When the output is not
refreshed, no pen report is sent for that pass. That is why removing the motion hold raised
the report count with the pen lying still (7.4).

Start-up calls before the loop: `0x080015F4`, `0x08008268` and `0x080082A0` (settings),
`0x0800855C`, `0x080096E8`, `0x080080F8`, `0x08009554`, `0x080095D4` (TIMER2),
`0x08009674` (TIMER5), `0x08005DB4`, `0x08000C00`, `0x08003A38`.

### 5.2 Clock and timers

* SystemInit `0x080040F8`, clock setup `0x08004068`: HXTAL on, PLL from HXTAL,
  `RCU_CFG0 = 0x0011800A` (PLL multiplier code 4 = x6, system clock from PLL),
  `RCU_CTL = 0x03035F83`. Measured: 72.00 MHz. So the crystal is 12 MHz.
* **TIMER2** (`0x40000400`): prescaler 0, auto-reload `0xFFFF`, free running at 72 MHz,
  channel 2 capture with interrupt (IRQ16). Used to time the pen's returned signal (5.7).
* **TIMER5** (`0x40001000`): prescaler 999, auto-reload 359, so 72 MHz / 1000 / 360 =
  **200 Hz**, update interrupt (IRQ17). Housekeeping only. **It does not pace the pen
  reports.**
* The struct layouts passed to the timer init helper (`0x08004224`) match ST's SPL
  `TIM_TimeBaseInitTypeDef` (prescaler u16, counter mode u16, period u32, clock division
  u16, repetition u8).

{{lst 25_timer_init 0x08009674 0x080096e8}}

### 5.3 The excitation carrier is bit-banged

The pen is a passive LC resonator. The tablet energises it with bursts of a carrier around
450 to 554 kHz and listens for it ringing back. The carrier is generated **in software**: 16
routines, one per frequency channel, toggle PC6 to PC9 together with NOP-timed loops.

| Table | Content |
| :--- | :--- |
| `0x080072B0` | 16 x u32 frequencies in Hz |
| `0x08006B9C` | 16 x u32 pointers to the burst routines |
| `0x20000003` | burst length in carrier cycles: **28** (`0x1C`) for a coil measurement, **45** (`0x2D`) for the frequency measurement |
| `0x2000002E` | the channel in use (0 to 15) |

| Ch | Routine | NOPs high + low | Period (cycles) | Frequency |
| :--- | :--- | :--- | :--- | :--- |
| 0 | `0x080045C0` | 72 + 67 | 160 | 450,000 Hz |
| 1 | `0x08004708` | 71 + 66 | 158 | 455,696 Hz |
| 2 | `0x0800484C` | 70 + 65 | 156 | 461,538 Hz |
| 3 | `0x0800498C` | 69 + 64 | 154 | 467,532 Hz |
| 4 | `0x08004AC8` | 68 + 63 | 152 | 473,684 Hz |
| 5 | `0x08004C00` | 67 + 62 | 150 | 480,000 Hz |
| 6 | `0x08004D34` | 66 + 61 | 148 | 486,486 Hz |
| 7 | `0x08004E64` | 65 + 60 | 146 | 493,151 Hz |
| 8 | `0x08004F90` | 64 + 59 | 144 | 500,000 Hz |
| 9 | `0x080050B8` | 63 + 58 | 142 | 507,042 Hz |
| 10 | `0x080051DC` | 62 + 57 | 140 | 514,286 Hz |
| 11 | `0x080052FC` | 61 + 56 | 138 | 521,739 Hz |
| 12 | `0x08005418` | 60 + 55 | 136 | 529,412 Hz |
| 13 | `0x08005530` | 59 + 54 | 134 | 537,313 Hz |
| 14 | `0x08005644` | 58 + 53 | 132 | 545,455 Hz |
| 15 | `0x08005754` | 57 + 52 | 130 | 553,846 Hz |

For every channel, NOPs + 21 = the period in cycles, and 72 MHz / period = the table value
exactly. So each NOP costs one cycle and each loop pass has 21 cycles of overhead (two GPIO
helper calls, counter, branch). One burst routine, start and end (the full 16 are in
`asm/28_carrier_burst_channels.lst`):

{{lst 28_carrier_burst_channels 0x080045c0 0x080045da}}
{{lst 28_carrier_burst_channels 0x08004664 0x08004708}}

Delay helpers built the same way (`asm/20_delay_sleds.lst`):

| Routine | Body | Approximate length |
| :--- | :--- | :--- |
| `0x080068F0` | 60 NOPs, `bx lr` | about 1 µs with the calling loop (the "unit" used by waits A and B) |
| `0x08006984` | 66 NOPs, `bx lr` | about 1 µs |
| `0x0800696A` | `push {lr}`, 4 x `bl 0x08006984`, pop, then falls into `0x08006984` once more | about 5 µs |

### 5.4 One coil measurement (`0x08002464`)

Called with up to two mux selections, a third coil selection and the carrier channel. Steps,
in order (`asm/09_coil_measure.lst`):

1. `[0x20000003] = 28`: the burst will be 28 carrier cycles.
2. `0x08000A8C`: sets PC4, PA6, PA7 (mux address) and PA8, PB11, PB12, PB13, PB14, PB15
   (the six mux enables) high, so every mux is off.
3. Coil/mux select routines from the 100-entry table at `0x08006A0C` for the first two
   arguments (`0xFF` = skip). Each sets the address on PA6, PA7 and PC4, then pulls one
   enable low: PA8, PB11, PB12, PB13, PB14 or PB15, one per HC4051 (which line goes to which
   chip was not traced). Unused table slots point at `bx lr` stubs.
4. PB1 high (`0x0800132A`, BOP register).
5. PC6 to PC9: push-pull outputs, then driven low (`0x08001290` init, `0x08001326` BC register).
6. **Carrier burst**: the channel's routine from `0x08006B9C`, 28 cycles on PC6 to PC9.
7. PC6 to PC9 back to inputs (open drain setting, no pull), driven low again.
8. `0x08000A8C` again, then the third coil selection.
9. **Wait A**: `[0x20001093]` x `0x080068F0` (about 1 µs each).
10. PB1 low.
11. **Wait B**: `[0x20000044]` x `0x080068F0`.
12. ADC conversion (`0x080002D4` with 1), `0x0800696A` (about 5 µs), read the ADC data
    register `0x4001244C` (`0x08000218`).
13. PB1 high, `0x08000A8C`, return `ADC >> 2`.

The most consistent reading is that PB1 controls the receive integrator (or sample and hold):
wait A is the delay after the burst before integration starts, and wait B is the
integration window. That also explains the tuner below. The roles of PB1 and the PC pins come
from the code, not from tracing the board.

{{lst 09_coil_measure 0x08002464 0x08002560}}

Measured: **12,905 cycles (179 µs)** for one coil measurement, consistent with about 100 µs of
waits + a 28-cycle burst (about 4,000 to 4,500 cycles) + GPIO and mux overhead.

The wrappers set the per-axis wait lengths and PB2 before calling it (`asm/11_measure_wrappers.lst`):

| Wrapper | Axis | PB2 from | Wait A copied from | Wait B copied from | Adds `0x40` to (unless `0xFF`) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `0x08002764` | X (26 coils) | `0x20000005` | `0x20000043` | `0x20001095` | second argument |
| `0x080027C8` | Y (18 coils) | `0x2000105B` | `0x20001094` | `0x20000045` | second and third arguments |
| `0x0800272C` | frequency (5.7) | `0x20000005` | none | none | |

### 5.5 Timing tuner (`0x08003ABC`)

Called from `0x08000D4E` whenever both peak coils are valid; otherwise `0x08000D54` resets
both axes to the defaults (A = 5, B = 60). For each axis it measures the peak coil
(`0x2000101D` for X, `0x2000101E` for Y) again and again (up to 50 times for X, 49 for Y):

* amplitude above **640** (`0x280`): A += 2 (up to 80, `0x50`)
* amplitude below **320** (`0x140`): A -= 2 (down to 5)
* in between: stop
* after each change: **B = 100 - A**

So the firmware keeps the signal in the ADC's sweet spot by moving the integration window,
while **A + B stays 100 (about 100 µs)**. Values read from a running tablet: A = 5, B = 60
right after start (defaults, A + B = 65 until the tuner first runs); later X A = 35, B = 65 and
Y A = 49, B = 51.

{{lst 14_timing_tuner 0x08003abc 0x08003b2c}}

### 5.6 Scans

**Search** (`0x080010F8`, no pen): resets both axes to A = 5, B = 60, then four
measurements through the Y wrapper at carrier channels **3, 6, 9 and 10** (467.5, 480.0,
507.0 and 514.3 kHz) to see whether anything resonates.

**Full scan** (`0x080023BC`, pen just found, gated by `"UGEE"`): resets A/B to 5/60, sets
`0x20000005 = 1` and `0x2000105B = 1`, then measures **all 26 X coils** into `0x200001F8` and
**all 18 Y coils** into `0x20000250` at the current channel.

**Tracking scan** (`0x08002FC4`, normal use, gated by `"3721"`): measures only a window of
coils around the last peak on each axis, X into `0x200001F8`, Y into `0x20000250`. The
window bounds are bytes: X from `0x20001074` to `0x20000020`, Y from `0x20001075` to
`0x20000021` (the loops can also run downwards).

**Window** (`0x08003CC8`, `asm/15_tracking_window.lst`): from the movement of the peak since
the last report it sets how many coils to scan behind and ahead of the peak, then clamps to
the grid (X index 0 to 25, `0x19`; Y index 0 to 17, `0x11`). Extents written by the code:
3 behind / 6 ahead (`movs r2,#3` at `0x08003CD0`, `movs r7,#6` at `0x08003DA0`), the mirror
6 / 3, 5 / 5 (`movs r4,#5` at `0x08003DDE` and `0x08003E0A`), 5 at `0x08003F04` and
`0x08003F38`, 2 / 2 (`movs r4,#2` at `0x08003E58`, `movs r2,#2` at `0x08003F3E`). Measured:
14 to 16 coil measurements per report (11 X + 5 Y and 5 X + 9 Y in two consecutive reports).

**Baseline** (`0x08006554`, gated by `"0226"`): for each coil in the window,
`corrected = raw - baseline` (0 if negative), and when raw is not above the baseline the
baseline becomes raw. X: raw `0x200001F8`, baseline `0x20000404`, corrected `0x200001C4`.
Y: raw `0x20000250`, baseline `0x20000438`, corrected `0x2000022C`. The position math and the
tuner read the corrected arrays.

### 5.7 Pen frequency, buttons and pressure (`0x08001EE4`, gated by `0xD209428C`)

1. Picks a band from the current channel `[0x2000002E]`:
   channel 0 to 5: base `0x6B2F0` (439,024), `[0x20001059] = 0x28`, `[0x20000004] = 3`, `[0x2000105A] = 2`;
   6 to 8: base `0x70AE2` (461,538), `0x26`, 3, 2; 9 and up: base `0x75300` (480,000), `0x0E`, 9, 5.
2. Calls the frequency measurement through `0x0800272C` → `0x0800257C`: 45-cycle burst, then
   6 x `0x0800696A`, TIMER2 channel 2 capture on, **36 x `0x0800696A`** (about 180 µs gate),
   capture off. It returns `capture[2] - capture[1]` in 72 MHz ticks (0 if fewer than 2
   captures). Measured while hovering: 2621 to 2687. Measured cost: **about 23,300 cycles
   (0.32 ms)**.
3. `f = 72,000,000 / period + base` (`0x044AA200` = 72,000,000). 0 → no pen.
4. Finds the closest entry of the carrier table and stores that channel in `0x2000002E`. If
   the channel jumps by more than 2 from last time, it bails out (`0x08000CA4`).
5. Decodes the pen state from `f` (stored at `0x20000028`) with these thresholds:
   `0x7B188` 504,200, `0x7AF94` 503,700, `0x7C31C` 508,700, `0x7975C` 497,500,
   `0x75EB8` 483,000, `0x75CC4` 482,500, `0x7704C` 487,500, `0x74554` 476,500,
   `0x74748` 477,000, `0x71E44` 466,500, `0x6FD10` 458,000, `0x79950` 498,000,
   `0x7EB58` 519,000. The state goes to `0x20001028` (1, 2 or 3; probably which side
   button is held).
6. Pressure: `(f - f0) * 16383 / span`, capped at `0x3FFF` (16383, 14 bit):

   | State | f0 | span | full pressure at |
   | :--- | :--- | :--- | :--- |
   | 3 | 466,500 (`0x71E44`) plus an amplitude-dependent margin | 10,500 (`0x2904`) | 477,000 |
   | 2 | 487,500 (`0x7704C`) | 10,500 (`0x2904`) | 498,000 |
   | 1 | 508,700 (`0x7C31C`) | 10,300 (`0x283C`) | 519,000 |

7. **Tip-down debounce**: a counter at `0x2000102B` must reach 4 before a non-zero pressure is
   passed on (4 reports, about 16 ms).
8. **Pressure smoothing**: an 8-entry history at `0x200003F4`, output = average of the 8
   (`0x2000103C`). On a fresh touch with pressure of at least 24, the history is filled with
   the new value first. **This 8-sample pressure average is not patched by nosmooth or nosmooth-nohold.**
9. A margin added to f0 of states 3 and 2 depends on the amplitude at `0x2000107C` (set by
   `0x08000B24`) and on X wait A: if the amplitude is under 320, `(320 - amp) * 8`; if A is 15
   or less, plus `(15 - A) * 64`. With an amplitude under 8, no pressure is reported at all.

### 5.8 Position, history, smoothing and the report

`0x08002834` (`asm/12_position_and_history.lst`), every report:

1. Raw X = `0x08001330()`, raw Y = `0x0800142C()` from the corrected coil amplitudes
   (interpolation, not analysed; `asm/29_…` and `asm/30_…`). `0xFFFF` = invalid.
2. Two signed bytes (`0x20000022`, `0x20001077`) go through tables at `0x080070D8`,
   `0x080071A2` and `0x080071FC` into `0x200010A6` and `0x20000046`. These end up as the two
   last bytes of the report (tilt, most likely).
3. On the first valid sample after the pen appears: all histories are filled with it.
4. A 19-entry raw history (X at `0x2000045C`, Y at `0x20001374`, newest at index 18).
   Whenever its counter `0x2000107F` reaches 19 it is reset to 3 and a despiked average is
   computed (each inner sample that is a local peak or dip is replaced by its neighbours'
   mean, then entries 1 to 16 are averaged). That average is only used by path A below.
5. The 8-entry history used for the output: X at `0x20000482`, Y at `0x2000139A`, shifted
   down every report, **newest at index 7** (`strh r5,[r2,#0xe]` at `0x08002CCA`).
   Deltas (newest minus previous) go into 7-entry arrays at `0x20000492` (X) and
   `0x200013AA` (Y).
6. Every 8 reports (`0x200010AA` counter): 8-sample sums into 16-entry arrays
   (`0x200013B8`, `0x200013F8`), their differences into `0x20001438` and `0x200004A0`, and
   sign changes counted into `0x2000004A` and `0x200010AB`. These feed the motion state
   machine.
7. An "inside the active area" flag at `0x20000030` (cleared when X < 3560, X > 22130,
   Y < 3760 or Y > 14580).
8. If `0x2000107E` (a mode flag) is set: **path A** (`0x08002E62`, old "site 2"), which
   moves the output only on large jumps, toward the despiked average, half way at a time.
   **Never reached in normal use** (hardware breakpoints, 7.2).
9. Otherwise: the **motion state machine** `0x08001650` (below), then **path B**
   (`0x08002ED6`, old "site 3"): only when the 8-report counter just wrapped, the state
   machine has said "still" for 8 or more reports (`0x2000003D`), and `0x2000107E` is clear.
   It moves the output half way toward the 8-sample average when they differ by more than a
   margin (16 plus an amplitude-dependent term). Not hit during the breakpoint test (the pen
   was moving).

**Motion state machine** (`0x08001650`, `asm/06_motion_state_machine.lst`):

* Sums `|delta|` over the 7 X deltas and the 7 Y deltas, and counts direction reversals on
  each axis.
* Uses the larger sum (`r2`). If both axes reversed more than once (jitter), or the sum is
  small, it goes to the "hold" states.
* Thresholds on the sum: **448** (`0x1C0`) state 4, **112** (`0x70`) state 3, **28**
  (`0x1C`) state 2, **21** (`0x15`) borderline. State byte: `0x2000102E`.
* At `0x080017CA`: states 4, 3, 2 call the output routine `0x08000310` with `r0 = 2`
  (after writing 7, 6 or 4 to `0x20000031`; no other direct reference to that byte exists).
  States 0 and 1 skip it, so **the output and the report hold still**.
* `0x2000003D` counts consecutive "hold" passes (used by path B).

{{lst 06_motion_state_machine 0x080017c6 0x0800180a}}

**Output routine** (`0x08000310`, the "boxcar"): unless `0x2000107E` is set, sets
`0x20001031 = 1` (report pending) and writes the output coordinates `0x20001040` (X) and
`0x20001042` (Y):

* `r0 = 2` (the only value the firmware passes): **average of all 8 history entries**
  (`sum >> 3`)
* `r0 = 1`: average of entries 4 to 7 (`sum >> 2`), never used

An 8-sample moving average at about 250 reports per second delays the cursor by 3.5 samples
(group delay), **about 14 ms**, plus the time for the average to catch up after a stop.

{{lst 02_boxcar_filter 0x08000310 0x08000390}}

**Report builder** (`0x08008780`, `asm/22_report_builder.lst`) reads `0x20001040`/`0x20001042`
(`0xFFFF` = no pen), subtracts the border and clamps:

* X: `outX - 0x618` (1560), clamped to 0 to 22570 (`0x5E42 - 0x618 = 0x582A`)
* Y: `outY - 0x6E0` (1760), clamped to 0 to 14820 (`0x40C4 - 0x6E0`), or to 10156
  (`0x2E8C - 0x6E0`) in the mode from 4.4

then scales for the vendor report (verified against measured reports):

* `X = (outX - 1560) * 30480 / 22570`
* `Y = 20320 - (outY - 1760) * 20320 / 14820` (Y is flipped)

30480 x 20320 units over the 152.4 x 101.6 mm (6 x 4 inch) active area is **0.005 mm per unit
(5080 LPI)**.

Vendor pen report on interface 2 (13 bytes as read from hidraw; the firmware's buffer at
`0x200001B5` has one flag byte in front):

| Byte | Content |
| :--- | :--- |
| 0 | `0x09` report ID |
| 1 | `0x41` |
| 2 | status: `0xA0` in range, bit 0 tip, bits 1 and 2 buttons; `0xC0` out of range |
| 3 to 5 | X, 24 bit little endian |
| 6 to 8 | Y, 24 bit little endian |
| 9, 10 | pressure, 0 to 16383 |
| 11, 12 | two signed bytes from step 2 (tilt, most likely) |

Example, pen moving: `09 41 a0 78 53 00 b3 29 00 00 00 00 00` (X 21368, Y 10675, no tip).
Pen lying flat on the surface: `09 41 a1 f4 11 00 b0 15 00 a3 0b 00 00` (tip bit set,
pressure about 2,980).

### 5.9 Time per report (tracking mode, pen hovering)

| Part | Cycles | Time |
| :--- | :--- | :--- |
| whole report (pass to pass over `0x08001F94`) | 279,584 to 289,588 (one pass 253,791) | about 3.9 ms |
| one coil measurement | 12,905 | 179 µs |
| coil measurements per report | 14 to 16 | about 2.6 ms |
| frequency/pressure measurement | 23,256 to 23,428 | 0.32 ms |
| everything else (position math, USB, housekeeping) | about 65,000 | about 0.9 ms |

PC sampling (8000 samples of `DWT_PCSR`) found **72 %** of all samples on a `nop`: carrier
bursts plus integration waits. The rest of the work alone is more than 1 ms.

### 5.10 RAM map

| Address | Size | Meaning |
| :--- | :--- | :--- |
| `0x20000003` | u8 | carrier burst length in cycles (28 coil, 45 frequency) |
| `0x20000004` | u8 | band parameter (3 or 9), set by the pen routine |
| `0x20000005` | u8 | PB2 level for X and frequency measurements |
| `0x20000018` | u8 | `0xFF` = skip the pen routine |
| `0x20000020`, `0x20000021` | u8 | tracking window end, X and Y |
| `0x20000022` | s8 | input to the step 2 tables (tilt X?) |
| `0x20000028` | u32 | measured pen frequency in Hz |
| `0x2000002E` | u8 | carrier channel (0 to 15) |
| `0x20000030` | u8 | inside-active-area flag |
| `0x20000031` | u8 | 8/7/6/4 written by the state machine, no other direct reference |
| `0x20000033` | u8 | TIMER2 capture count (wraps at 20) |
| `0x2000003C` | u8 | dominant axis from the state machine |
| `0x2000003D` | u8 | consecutive hold passes |
| `0x20000043`, `0x20001095` | u8 | X wait A and wait B |
| `0x20001094`, `0x20000045` | u8 | Y wait A and wait B |
| `0x20001093`, `0x20000044` | u8 | wait A and wait B used by the current measurement |
| `0x20000046`, `0x200010A6` | s16 | step 2 outputs (report bytes 11 and 12) |
| `0x2000004A`, `0x200010AB` | u8 | slow sign-change counters (state machine input) |
| `0x200001B5` | 15 bytes | vendor report buffer (flag + 14 bytes) |
| `0x200001C4`, `0x2000022C` | 26 / 18 x u16 | corrected coil amplitudes, X / Y |
| `0x200001F8`, `0x20000250` | 26 / 18 x u16 | raw coil amplitudes, X / Y |
| `0x200003F4` | 8 x u16 | pressure history |
| `0x20000404`, `0x20000438` | u16 arrays | coil baselines, X / Y |
| `0x2000045C`, `0x20001374` | 19 x u16 | raw position history, X / Y |
| `0x20000482`, `0x2000139A` | 8 x u16 | output history, X / Y (newest at [7]) |
| `0x20000492`, `0x200013AA` | 7 x s16 | position deltas, X / Y |
| `0x200004A0`, `0x20001438`, `0x200013B8`, `0x200013F8` | 16 x u32 | 8-report sums and their differences |
| `0x200004E5` | 1 KB | RAM copy of settings page A |
| `0x20001000` | struct | main loop state; `+0x0B` mode, `+0x0D` countdown, `+0x30` DFU request, `+0x31` report pending |
| `0x2000101D`, `0x2000101E` | u8 | peak coil, X / Y (`0xFF` none) |
| `0x20001028` | u8 | pen state from the frequency (1/2/3) |
| `0x2000102B` | u8 | tip debounce counter |
| `0x2000102E` | u8 | motion state (0 to 4) |
| `0x20001030` | u8 | DFU request (set by the vendor command) |
| `0x20001031` | u8 | report pending |
| `0x2000103C` | u16 | pressure output |
| `0x20001040`, `0x20001042` | u16 | output X, Y (`0xFFFF` = none) |
| `0x20001048` | u16 | 500-report counter for the mode switch |
| `0x20001054` | u8 | mode saved to settings page B |
| `0x2000105B` | u8 | PB2 level for Y measurements |
| `0x20001074`, `0x20001075` | u8 | tracking window start, X and Y |
| `0x2000107C` | u16 | amplitude written by `0x08000B24`, read by the pen routine |
| `0x2000107E` | u8 | mode flag that enables path A and disables the output routine; only read in the image (no direct writer, maybe written through the `0x20001000` struct) |
| `0x2000107F` | u8 | 19-entry history counter |
| `0x200010AA` | u8 | 8-report counter |
| `0x20001474` | 20 x u16 | TIMER2 capture ring |
