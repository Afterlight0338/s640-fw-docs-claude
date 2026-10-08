
---

## 6. Report rate: why 1000 Hz is not possible here

### 6.1 Measured rate

All measurements: pen reports read straight from the interface 2 hidraw node while
OpenTabletDriver 0.6.7 was running (it puts the tablet into the vendor report mode).

| Condition | Firmware | Result | Source |
| :--- | :--- | :--- | :--- |
| hovering and moving, 15 s | stock | 2460 reports, median interval 3.99 ms (250 Hz), mean while moving 243 Hz, shortest 0.20 ms | `data/rate_stock.txt` |
| pen lying flat, 6 s | stock | 209 Hz and 207 Hz (two runs), intervals: mostly 4 ms, some 3 and 5 ms | `data/still_stock*.txt` |
| earlier notes, with the tablet's previous firmware | old | 248.8 Hz, 99.5 % of intervals at 4 ms | `history/` |

The pen endpoint already has `bInterval 1`, so the host asks for a report every 1 ms. A
report that is ready after 3.4 ms waits for the next poll and shows up at 4 ms. Measured
intervals are therefore whole milliseconds, and the possible steady rates are
1000, 500, 333 and 250 Hz. To reach 333 Hz the scan must finish in under 3 ms, and 500 Hz
needs under 2 ms.

### 6.2 Why the scan takes about 3.9 ms

Section 5.9. About 15 coil measurements at 179 µs each, plus a 0.32 ms frequency
measurement, plus about 0.9 ms of other work. The coil measurements are mostly physics:
a 28-cycle burst at about 500 kHz (56 µs) and about 100 µs of waiting and integrating per coil.
The non-waiting work alone is over 1 ms, so even a firmware with no waits at all (which
would not see the pen) could not reach 1000 Hz. A realistic ceiling with careful tuning is
around 300 to 330 Hz.

### 6.3 How the Wacom "1000 Hz" firmwares do it

Sources: `https://files.shav.it/osu/tablet/` ("tabletvit") and `https://xstarry.dev/firmware`,
both looked at on 2026-10-06. Snapshots in `wacom/`.

What their pages say (verbatim, `wacom/tabletvit_page_strings_2026-10-06.txt`):

* "pro pen 3 guarantees 1000 hz; other pens will do 400 hz or higher."
* "custom firmware enables a 1000 hz scan rate and disables firmware filtering. requires pro pen 3."
* "flashed firmware only reaches around 500 hz"
* motion sync: "aligns tablet scan timing with usb reports."
* the page script accepts report rates from 133 to 1000

xstarry's catalog (`wacom/xstarry_firmware_catalog_snapshot_2026-10-06.json`, download
counts as of that day):

| Firmware | Downloads |
| :--- | :--- |
| CTL-472 / CTL-672 700hz Firmware (Position Only, No tip) | 22706 |
| CTL-472 / CTL-672 600hz Firmware (Tip) | 17943 |
| CTL-472 / CTL-672 200hz Firmware V2 | 11587 |
| CTL-472 / CTL-672 Original Firmware | 7660 |
| CTL/CTH 480/680 600hz Firmware (Tip) | 7605 |
| CTL-4100/4100WL Original Firmware (1.11) | 6574 |
| CTL/CTH 480/680 700hz Firmware (Position Only, No tip) | 5959 |
| CTL/CTH 480/680 200hz Firmware V2 | 5167 |
| PTK-470 Original Firmware (1.06) | 4197 |
| CTC-4110 500hz Firmware (1.07) | 3941 |
| CTC-4110 Original Firmware (1.07) | 3793 |
| CTL-4100/4100WL 500HZ Firmware V1 | 2259 |
| CTL-6100/6100WL 500HZ Firmware V1 | 175 |
| CTL-6100/6100WL Original Firmware (1.11) | 93 |

Note the "Tip" (600 Hz) and "Position Only, No tip" (700 Hz) pairs: dropping the pressure
measurement buys about 100 Hz. Those Wacom models report at 133 Hz with stock firmware, so
there was far more slack to remove than on the S640.

**CTC-4110 (ARM, readable):** the 1.07 "official" and "459hz" files are Wacom `.wac` files
(a `WACOM2…` header line plus Motorola S-records). They hold the firmware twice (banks at
`0x08018000` and `0x08052000`); both copies get the same patch, and each bank's checksum word
changes. 30 bytes differ in total (`wacom/ctc4110_459hz_vs_official_1.07_diff.txt`):

| Address (bank 1 / bank 2) | Stock | 459 Hz | What it is |
| :--- | :--- | :--- | :--- |
| `0x08018570` / `0x08052570` | `31 f4 80 71` `bics r1,r1,#0x100` | `41 f4 80 71` `orr r1,r1,#0x100` | sets a configuration bit instead of clearing it |
| `0x08018590` / `0x08052590` | `31 f0 80 61` `bics r1,r1,#0x4000000` | `41 f0 80 61` `orr r1,r1,#0x4000000` | same, another bit |
| `0x0803AC0A` / `0x08074C0A` | `38 b5 05 00` `push {r3,r4,r5,lr}; movs r5,r0` | `00 20 70 47` `movs r0,#0; bx lr` | a function stubbed to return 0 |
| `0x08041643` / `0x0807B643` | `05` | `02` | a count in a table, 5 to 2 |
| `0x08041651` / `0x0807B651` | `03` | `02` | a count in a table, 3 to 2 |
| `0x0804185C` / `0x0807B85C` | `5f 06` (1631) | `e5 05` (1509) | a timing value, about 7.5 % shorter |
| `0x08042666` / `0x0807C666` | `11` (17) | `08` | a count, 17 to 8 |
| `0x08045F00` / `0x0807FF00` | `ea 40 2f 6e` / `28 1b f2 c2` | `b7 cc 78 9c` / `75 97 a5 30` | bank checksums |

The meanings in the last column are a reading of the values, not traced through that
firmware. They match the general idea: fewer repetitions per measurement and shorter scan
timing.

**CTL-472, CTL-480 (LC87 8-bit core):** the custom builds differ from stock in thousands of
bytes (5,140; 14,715; 12,713 of 49,152), i.e. rebuilt or heavily rewritten code
(`wacom/lc87_pairs_diff_sizes.txt`). Not analysed further.

None of their firmware files are in this repository; their SHA-256 values are in
`wacom/hashes_of_files_analysed.txt`.

### 6.4 Experiment: shorter integration window (T = 80)

`patches/scanpatch.py 80 70 test_t80.bin` changes the tuner so A + B = 80 instead of 100
and A tops out at 70 instead of 80 (4 bytes, `asm/patched_t80_tuner.lst`):

| Offset | Stock | T = 80 | Instruction |
| :--- | :--- | :--- | :--- |
| `0x3AEA` | `50` | `46` | `cmp r1,#0x50` → `#0x46` (X, A limit) |
| `0x3B08` | `64` | `50` | `rsb.w r0,r1,#0x64` → `#0x50` (X, B = T - A) |
| `0x3B48` | `50` | `46` | same as `0x3AEA`, Y |
| `0x3B66` | `64` | `50` | same as `0x3B08`, Y |

| Measurement | Stock | T = 80 |
| :--- | :--- | :--- |
| hovering and moving: mean report rate while moving | 243 Hz | **268 Hz** (3634 reports, median 3.90 ms) |
| pen lying flat: average rate | 209 / 207 Hz | 199 / 198 Hz |
| pen lying flat: most common interval | 4 ms | **3 ms** (349 of 1193), but more 5 ms gaps |
| pen lying flat, untouched: X position | 4596, then 4593 after going back to stock | **5246** |

X moved by 650 units (**3.25 mm**) while nobody touched the pen, and came back when stock was
flashed again. Y readings moved by up to 180 units between all runs, stock included, so Y is
inconclusive. A shorter integration window changes the coil amplitudes the position
interpolation sees, which shifts the computed position. **About 10 % more reports for a
3 mm offset is not worth it.** Stock was flashed back.

### 6.5 Experiment: "position only" and a smaller window (both failed)

Built with `patches/nosmooth.py v3.bin --nohold --fast` and
`patches/build_window_only.py` (31 and 27 bytes different from stock):

| Change | Bytes | Result |
| :--- | :--- | :--- |
| replace the frequency/pressure call at `0x08001F94` (`00 f0 ca fb`, `bl 0x0800272C`) with `40 f6 69 20` (`movw r0,#0xa69`, 2665 = the hover value measured with `tools/pval.tcl`) | 4 | **pen never detected**. The frequency measurement is also what picks the carrier channel and decides that a pen is present (5.7), so a fixed value cannot stand in for it |
| tracking window extents: `0x3CD0` 3→2, `0x3DA0` 6→4, `0x3DDE` 5→3, `0x3E0A` 5→3, `0x3F04` 5→3, `0x3F38` 5→3 | 6 | tracks the pen, but **never finds it again after it is lifted away**. Which of the six values breaks re-acquisition was not bisected |

Both were reverted to nosmooth-nohold. Expected gain had they worked: about 0.32 ms + 0.6 ms, from
3.93 ms to about 3.0 ms (about 330 Hz).

### 6.6 What is left to try

* Bisect the six window constants and keep only the ones that do not break re-acquisition
  (maybe 10 to 15 % more reports).
* Shorten the frequency measurement's gate (36 x 5 µs) instead of skipping it. It only needs
  two TIMER2 captures (maybe 5 %).
* Re-tune the position interpolation together with a shorter integration window, the way the
  Wacom mods appear to. Large effort, uncertain result.
* Read several coils after one burst. Limited by how fast the pen's ring-down fades (6.7).

Always test lifting the pen away and bringing it back, and measure accuracy, not just Hz.

### 6.7 Measured by another user: the pen signal on the neighbouring coils

Another user measured this on their own tablet over SWD (2026-10-08). The numbers below are
theirs, quoted from their write-up, not repeated here. Setup: the coil measurement of 5.4,
burst on Y coil `y` at carrier channel 9 (507 kHz), but read on coil `y + d` (the third
selection) for d = -2 to +2. Wait A = 0, 5, 10 and 20, wait B = 60 throughout (units of about
1 µs, 5.3). Values are the routine's return value, `ADC >> 2`, so 0 to 1023.

Pen over the tablet, A = 5 (average of two tries), and what is left at A = 20:

| Coil | A = 5 | vs. coil `y` | A = 20, as % of A = 5 |
| :--- | :--- | :--- | :--- |
| y - 2 | 125 | 15 % | 38 % |
| y - 1 | 749 | 90 % | 57 % |
| y (burst) | 835 | 100 % | 80 % |
| y + 1 | 806 | 97 % | 72 % |
| y + 2 | 385 | 46 % | 52 % |

What it shows:

* **Pen away**: about 145 at A = 0 on every coil, two coils away too, and exactly 0 from
  A = 5 up. The 145 is a transient from the end of the burst, not the pen. It is gone by
  A = 5 (1 to 4 were not tried), which fits the tuner's lower limit of 5 (5.5). Exactly 0,
  instead of noise around a baseline, also means the front end clamps at the bottom, so "no
  crosstalk without the pen" holds only down to that floor (see below).
* **The neighbours pick up most of the signal.** The pen keeps ringing after the burst, and
  the coils next to the excited one see almost as much of it. The stock firmware already
  relies on this: while the pen moves slowly, it excites the peak coil and reads the others
  (5.6).
* **The readings are lopsided** (y + 1 > y - 1, y + 2 > y - 2): the pen sits a little towards
  +y. That asymmetry is what the position math works from.
* **The centre clips** at about 841 to 844 (about 2.7 V, if the ADC reference is 3.3 V). The
  test held A at 5. In normal use the tuner (5.5) raises A until the peak coil reads 320 to
  640, which is how stock firmware avoids clipping.
* **One decay time, not five.** Their write-up reads the five percentages as decay times of
  15 to 70 µs. One pen rings down with one time constant, so the spread must come from the
  front end. One time constant τ, a floor c (the front end outputs nothing below it) and the
  clipping explain all five. With reading = signal - c and the signal falling as e^(-A/τ),
  reading(20) = r x reading(5) - c x (1 - r), with r = e^(-15/τ): a straight line. Through
  y - 2, y - 1 and y + 2, the coils that do not clip, r = 0.61, so **τ ≈ 30 µs** and the floor
  is about 80 counts, with all three within 3 counts of the line. y and y + 1 sit above it, as
  they should if their A = 5 readings are clipped. The line puts their unclipped values at about
  1150 and 1000. The 60 µs window does not bend this: for an exponential, the ratio of two
  equally long windows is exactly e^(-ΔA/τ). The estimate is rough because it rests on three
  points, two unknowns and rounded percentages, not because of the window.

**Same test on the tablet these notes come from, pen away** (2026-10-08,
`tools/sweep.tcl`, `data/sweep_penaway_2026-10-08.txt`; burst and read on Y coil 8 ± 2,
channel 9, B = 60): the transient is about 41 to 51 at A = 0 (not 145), 18 to 40 at A = 1,
and **exactly 0 from A = 2 up**. Going from about 25 to exactly 0 in 1 µs suggests the floor
subtracts, rather than the transient simply fading. A sweep of B at A = 0 on the burst coil
gave 73, 89, 87, 81, 75, 61, 41 for B = 0, 2, 5, 10, 20, 40, 60: **the reading falls as B
grows**. A plain integrator would hold or grow, so the stage that PB1 releases leaks, and
"integration window" (5.4) is a loose name for B. That does not change the τ estimate above,
because the stage still scales with its input. How B behaves with the pen over the tablet is
not measured yet.

**What it means for reading several coils after one burst.** Each measurement today has its
own burst: 28 carrier cycles, about 55 µs of the 179 µs (5.4). One burst for several coils
would save most of that, but:

* All coils share one receive path. The measurement selects one receive coil, gates one stage
  with PB1 and starts one ADC conversion (5.4). Reads after one burst would come one after
  the other, not at the same time.
* With τ ≈ 30 µs, a second read whose window starts 65 µs after the first one's (A + B)
  sees about 12 % of the signal, and most of that is under the floor. With stock windows, one
  burst serves one read.
* Shorter windows could fit 2 or 3 reads into one ring-down. But each read gets less signal,
  each slot needs its own gain correction, and the edge coils that carry the position
  information (y ± 2 here) are the first to drop under the floor. A window only 20 % shorter
  already moved the position by 3 mm (6.4), so the position math would need redoing too.

Not tried. The first test worth doing: how much of y ± 2 is left with a 10 to 15 µs window.

---

## 7. Zero smoothing

### 7.1 What the earlier patch claimed, and what is true

`history/scripts/create_zero_smoothing_fw.py` patched three places:

| Site | Bytes | Claimed | Verified 2026-10-06 |
| :--- | :--- | :--- | :--- |
| `0x08000310` | `f0 b5` → `70 47` (`bx lr`) | removes the 8/4-sample boxcar | it is the boxcar, but it is also **the only routine that writes the output coordinates and sets "report pending"** (`0x20001031`). With `bx lr` the main loop would never call the report builder in tracking mode: no pen reports at all (from the code; this build was never flashed over SWD) |
| `0x08002EAA` | `05 d1` → `00 bf` | removes a 2-sample average | that code is path A (5.8), **never executed** in normal use (hardware breakpoints) |
| `0x08002F18` | `04 d1` → `00 bf` | removes "micro-movement jitter damping" | that code is path B (5.8), **not executed** while the pen moved. The real jitter hold is the motion state machine at `0x080017CA` |

### 7.2 How the active path was found: hardware breakpoints

`tools/paths.tcl` sets one FPB hardware breakpoint at a time on the running tablet, resumes,
and waits 2.5 s for a hit, while the pen is being moved:

| Address | Code | Hit |
| :--- | :--- | :--- |
| `0x080068F0` (sanity: delay loop) | | **yes** |
| `0x08002464` (sanity: coil measurement) | | **yes** |
| `0x08000330` | boxcar, 8-sample path | **yes** |
| `0x08000356` | boxcar, 4-sample path | no |
| `0x08002E98`, `0x08002ECA`, `0x08002EB8`, `0x08002EAC` | path A | no |
| `0x08002F24`, `0x08002F1A` | path B | no |

A first run without the sanity addresses gave "no" everywhere, which is what led to checking
that breakpoints work at all.

The two patches below were called "v1" and "v2" until 2026-10-07. They were renamed because
"V2" is also the name of Veikk's newer report format (2.6), and `S640-251022` is already
that format. `nosmooth.py` still accepts the old flag `--nodeadzone`.

### 7.3 Patch nosmooth: output = newest sample

`patches/nosmooth.py OUT.bin` (19 bytes). Both averaging paths of `0x08000310` become
"copy `history[7]` to the output". The "report pending" flag is still set, so reports keep flowing.

| Offset | Stock | nosmooth |
| :--- | :--- | :--- |
| `0x330` | `0b 88 16 88 5f f0 01 00 31 f8` | `c8 89 20 80 d0 89 28 80 f0 bd` |
| `0x356` | `0b 89 16 89 05 20 31 f8 10 70` | `c8 89 20 80 d0 89 28 80 f0 bd` |

```
ldrh r0, [r1, #0xe]    ; histX[7]
strh r0, [r4]          ; outX
ldrh r0, [r2, #0xe]    ; histY[7]
strh r0, [r5]          ; outY
pop  {r4, r5, r6, r7, pc}
```

Patched routine (`asm/patched_nosmooth_output_routine.lst`):

```
{{file asm/patched_nosmooth_output_routine.lst}}
```

### 7.4 Patch nosmooth-nohold: no motion hold either

`patches/nosmooth.py OUT.bin --nohold` (21 bytes): nosmooth plus 2 bytes at `0x17CA`,
`9a f8` → `13 e0`, which turns the start of `ldrb.w r0,[sl]` into `b 0x080017F4`, so states
0 and 1 also call the output routine with `r0 = 2` (the old bytes `00 00` at `0x17CC` are
skipped).

```
{{file asm/patched_nohold_state_machine_tail.lst}}
```

**Side effect found while writing this document** (from the code; harmless on the tablet,
which works): the branch also skips `mov r5, sl` at `0x080017CE`. The tail at `0x080017FA`
then does `ldrb r1,[r5]` with r5 still holding the X reversal count (0 to 6), so it reads a
byte of the boot alias of the vector table (addresses 0 to 6) instead of the motion state.
The hold counter `0x2000003D` is then reset on almost every report (it only counts up when the
byte read is 1, i.e. when the X reversal count is exactly 5), so **path B can practically
never run on nosmooth-nohold**. A cleaner way to write the same patch would be `55 46 12 e0` at `0x17CA`
(`mov r5, sl; b 0x080017F4`); that keeps the counter working and with it path B. **Not
built or tested.**

### 7.5 Results

| Test | Stock | nosmooth | nosmooth-nohold |
| :--- | :--- | :--- | :--- |
| output = `history[7]` on the chip, pen moving (5 snapshots) | (average of 8) | **yes, 5 of 5** | |
| output = `history[7]`, pen lying still | | no (held, e.g. out `0x14C4` while history moves `0x14B0` to `0x14DF`) | **yes, 3 of 3** |
| stroke sharpness, fast scribbles (`tools/stroke.py`) | 0.130 | 0.320 | **0.394** |
| still pen, X noise (std / range, report units) | 3.38 / 14 | 0 / 0 | **5.81 / 45** |
| still pen, Y noise | 0.96 / 4 | 0 / 0 | **5.09 / 29** |
| still pen, reports per second | 207 to 209 | 210 | **267** |

Stroke sharpness is `mean |second difference| / mean |first difference|` over consecutive
reports while the pen moves (triples with a gap over 12 ms or a step under 20 units are
skipped). A moving average lowers it. Two nosmooth-nohold runs where the pen hardly moved
(1.620 and 1.603, mean step 25 instead of 141 to 183) are kept in `data/` but are not
comparable, because the measure is dominated by noise when the pen barely moves.

What the numbers mean:

* The 8-sample average is gone (sharpness x 2.5 with nosmooth, x 3 with nosmooth-nohold).
* The hold is gone in nosmooth-nohold: the raw noise of a still pen now shows, about 5.5 units standard
  deviation, i.e. **about 0.03 mm** (0.005 mm per unit). OpenTabletDriver can filter that on
  the PC if wanted.
* The firmware skips the USB report when the output did not change (5.1), so the hold also
  cost reports: 209 Hz to 267 Hz with the pen still.

### 7.6 Smoothing that is still there

* **Pressure**: 8-sample average and a 4-report tip-down debounce (5.7). Not patched.
* **Path B** (5.8): practically disabled on nosmooth-nohold by the side effect in 7.4.
* **Path A**: only with the `0x2000107E` mode flag set, never seen.
* Inside one scan: coil baseline subtraction and position interpolation. These are part of
  measuring the position, not smoothing over time.

### 7.7 Building and flashing

```
mkdir build && cd build
cp /path/to/S640-251022.bin .          # the script reads this exact name from the current directory
python3 ../patches/nosmooth.py s640_nosmooth_nohold.bin --nohold
sha256sum s640_nosmooth_nohold.bin  # 371a4f7bc4ab181a1a41d58867bf31e7bc56dcaec656c0fe614f68995551877e
```

Then flash it over SWD (3.8). Every patch script asserts the original bytes first and stops
on any mismatch. To go back to stock, flash `S640-251022.bin` the same way.

### 7.8 How to check it yourself

1. Lay the pen flat and run `python3 tools/still.py 6`. With nosmooth-nohold the X/Y standard deviation is
   a few units; with stock or nosmooth it is 0 to 3.
2. Scribble fast and run `python3 tools/stroke.py 10`. nosmooth-nohold is around 0.4, stock around 0.13.
3. With the Pico attached, `tools/outcheck.tcl` prints the history buffer and the output
   coordinates five times. With nosmooth-nohold, `outX` equals the last `histX` value every time.


### 7.9 Patch nosmooth-hook (SWD-tested): the same result without touching the first 12 KB

`patches/hook.py OUT.bin`. Why it exists and how to try it: 0.2.

**Tested over SWD on 2026-10-08.** The owner played osu! on three images flashed in random
order without being told which was which (stock, `nosmooth-nohold`, `nosmooth-hook`), and
named all three correctly. During each round `tools/watch.tcl` read, every 100 ms and
without halting the chip, the output position `0x20001040/42` and the newest history
sample (`histX[7]` `0x20000490`, `histY[7]` `0x200013A8`):

| Image | Samples with the pen tracked | Output = newest sample | Within 50 units | More than 300 apart |
| :--- | :--- | :--- | :--- | :--- |
| stock | 534 | 0 % | 23 % | 180 |
| nosmooth-nohold | 543 | 23 % | 69 % | 4 |
| nosmooth-hook | 506 | 26 % | 70 % | 7 |

The two values are read a few ms apart while the pen moves, so even a perfect patch does
not reach 100 %; the point is that the hook and nosmooth-nohold are indistinguishable and
stock is not. Logs: `data/watch_blind_*_2026-10-08.txt`. Not yet run on the hook:
`still.py`, `stroke.py`, and a check of pressure and the pen buttons.

Changes (68 bytes appended at `0x0800C464`, 2 calls redirected; nothing below `0x08003000`):

| Offset | Stock | Hook |
| :--- | :--- | :--- |
| `0x6822` | `fc f7 07 f8` (`bl 0x08002834`) | `05 f0 1f fe` (`bl 0x0800C464`) |
| `0x685E` | `fb f7 e9 ff` (`bl 0x08002834`) | `05 f0 01 fe` (`bl 0x0800C464`) |
| `0xC464` | end of image (erased flash) | the routine below |

How each part was decided:

* **New sample or not.** The 19-entry raw history counter `0x2000107F` changes on every valid
  sample: it is incremented at `0x08002A52`, set to 1 when the pen is first found
  (`0x08002A90`, all histories filled), and wraps from 19 to 3. Passes with no valid sample
  leave `0x2834` before that: an invalid sample (`0xFFFF`) goes `0x080028DA` → `0x08002AFA` →
  `0x08002F6A` → exit, and a too-weak signal exits at `0x08002A16`/`0x08002A24`. The hook compares
  the counter before and after the call. (One corner: if the pen is found again while the
  counter is already 1, that one pass is missed.)
* **Mode A.** `0x2000107E` set means path A owns the output (`0x08002E62`), and the stock
  output routine `0x08000310` does nothing in that case. The hook does the same.
* **No added lag.** The report is built after `0x2834` returns: the main loop checks the
  pending flag `0x20001031` at `0x080068A4` and calls the report builder at `0x080068D6`.
* **Registers.** `0x2834` keeps r4 to r11 and returns nothing the main loop uses, and
  `0x08000390`, called next, loads its own inputs. The hook keeps r4 to r6 and the stack
  8-byte aligned.
* **Path B** (5.8) can still run inside `0x2834` on a still pen and move the output; the hook
  overwrites it right after, so it has no effect.

```
{{file asm/patched_hook.lst}}
```

### 7.10 Experiment: reversing the smoothing (worse than stock)

0.2.1 argues that undoing the average after the fact cannot work. To check it on a tablet,
`patches/reverse.py` (source `patches/reverse.s`) builds an image that does exactly what a
PC-side filter would have to do. It sits where the hook sits (same two redirected calls, the
routine at `0x0800C464`, nothing below `0x08003000` changed), but it never reads the raw
history. It only looks at the smoothed position of each report that is about to go out and
works backwards, assuming the 8-sample average:

```
rec[n] = rec[n-8] + 8 x (out[n] - out[n-1])
```

That is the exact inverse of `sum / 8`, apart from the rounding. It keeps its own last 8
results at `0x20001F00` (above the stack), starts from the smoothed value after the pen is
found, and falls back to the smoothed value if the result lands more than 2000 units (10 mm)
away from it.

**Result (2026-10-08):** in the blind osu! test (7.9) the owner recognised it within seconds
and stopped the test. `tools/watch.tcl` (`data/watch_reverse_2026-10-08.txt`), compared with
the newest raw sample as in 7.9:

| Image | Samples with the pen tracked | Within 50 units | More than 300 apart |
| :--- | :--- | :--- | :--- |
| reverse | 572 | 6 % | 378 |
| stock | 534 | 23 % | 180 |
| nosmooth-hook | 506 | 70 % | 7 |

Worse than leaving the smoothing in. Each step can be off by up to 7 units of rounding,
multiplied back by 8, and nothing pulls the error back, so the 8 interleaved chains drift
apart. Samples the hold never reported put the chains out of step for good. An OpenTabletDriver filter works on
the same reports, so it would do no better. The hook (7.9) is the way: the raw value is
still in RAM, so use it.

---

## 8. Corrections to the earlier notes

The notes in `history/` were written with another AI assistant before this session. Wrong or
unverified claims, and what is actually true:

| Earlier claim | Actually |
| :--- | :--- |
| MCU is a GD32F150C6T6, LQFP48, 128 KB flash | relabelled `VK1801`, **LQFP64**, Cortex-M3, **64 KB flash and 8 KB SRAM** per the flash size register (the DFU descriptor's 128 KB layout does not match the chip) |
| pin pictures with "44 BOOT0", "37 PA14 (SWCLK)" (`history/*_WRONG.jpg`) | 48-pin numbering on a 64-pin chip. BOOT0 is pin 60, SWCLK pin 49, SWDIO pin 46 |
| SWD on "the four test pads next to the GD32F150" | J1 has **five** through-holes: 3V3, SWCLK, SWDIO, NRST, GND |
| `28e9:0189` is the native ROM bootloader | Veikk's own bootloader at `0x0800D800`, entered from the firmware (3.1). Erased by the unlock |
| the "GD32 DFU ROM silently discards writes" to the first 12 KB, and "251022 firmware code beyond 12KB was updated successfully" | the refusal is the updater's own address check, not the ROM or the chip (0.3.1). The rest most likely did not land either, because no erase commands were sent (3.1) |
| pen interface `bInterval 3`, fix it with `usbhid.mousepoll=1` | `S640-251022` declares `bInterval 1` on every IN endpoint; host polling is not the limit. (The 3 ms may have been true for the tablet's previous firmware) |
| the boxcar adds "up to 32 ms latency" | an 8-sample average spans 8 reports (about 32 ms), but its group delay is 3.5 reports, **about 14 ms** |
| patch `bx lr` at `0x08000310` removes the boxcar | it would stop all pen reports (7.1) |
| `0x08002EAA` removes a 2-sample average; `0x08002F18` removes jitter damping | both are on paths that do not run in normal use; the jitter hold is at `0x080017CA` |
| "after SWD flash, all 3 patches will apply + bInterval=1 (1000 Hz) will take effect" | the rate is limited by the scan (about 3.9 ms), not USB (section 6) |
| the "500 Hz" firmware | changed `bInterval` 1 → 2, which would have halved USB polling |
| "Sensor Matrix Processing: 26 X-coils and 18 Y-coils sub-pixel peak interpolation located at `0x080003ac` and `0x080006f4`" | 26 and 18 coils is right (window clamps, full scan loops). The raw X/Y come from `0x08001330` and `0x0800142C`; `0x08000390`/`0x080003AC` run after the position routine and were not analysed |
| clearing read protection erases "the entire 128 KB" | it erases the whole 64 KB flash, including the bootloader, settings pages and factory tags (3.6) |
| this unit is "V1 hardware" | V1 and V2 are report formats. This unit shipped with V1-format firmware and runs V2-format `S640-251022` on the same board (2.6) |
| Veikk quietly shipped "3 hardware revisions" of the S640, the V2 with a different MCU and crystal; around 2020 to 2021 an updater with no revision check flashed the wrong binary and bricked tablets, so Veikk pulled all firmware downloads in 2021 | **no source.** The earlier assistant's own web search found no record of it, and the details were made up. It started from one unsourced line in a Discord chat ("they took down all firmware downloads in 2021 because they bricked tablets"). `S640-251022` itself is dated 2025-10-22. What is documented is the 2021 switch to the 13-byte V2 report (2.6), which made new tablets unreadable by older drivers |

Corrections to things said during the 2026-10-06 session itself (before this write-up):

| Said during the session | Correct |
| :--- | :--- |
| excitation pins are PB6 to PB9 | **PC6 to PC9** (GPIOC `0x48000800`, mask `0x3C0`); GPIOB is PB1 (mask 2) and PB2 (mask 4) |
| the frequency gate is 45 delay calls | **42** (6 before the capture is enabled, 36 after) |
| `0x20000003` is a "phase" marker | it is the **burst length** in carrier cycles (28 / 45) |
| wait A = excitation, wait B = settle | the burst happens before both; A is most likely the delay before integration, B the integration window |
| the two wait sets are "search" and "tracking" | they are the **X and Y axes** |
| the scan code partly runs from the SVCall/PendSV handlers | both handlers are empty `bx lr` |
| nosmooth-nohold still-pen jitter is ±0.04 mm | standard deviation about **0.03 mm** (5.5 report units at 0.005 mm) |
| `28e9:0189` is the ROM DFU (project memory) | Veikk bootloader at `0x0800D800` |
| `0x0800D800` is a settings page | it is the bootloader; the settings pages are `0x0800D000` and `0x0800D400` |
| the J1 photo numbering 1 to 5 "left to right" differs from "bottom to top" | they are the same holes, the photos are just rotated 90 degrees |

Corrections to this document (2026-10-08):

| Said before | Correct |
| :--- | :--- |
| the mux control lines are PA8 and PB11 | there are six enable lines, PA8 and PB11 to PB15, one per HC4051 (2.3, 5.4). Pointed out by another user |
| read protection may be why Veikk's updater refuses the first 12 KB | it is the updater's own address check (0.3.1). Whether read protection also locks pages against the firmware is a separate, open question (0.3.2) |
| in September only the part from `0x3000` up landed, so an old first 12 KB runs with 251022's upper part | most likely nothing landed (3.1); no tablet is known to run that mix |

---

## 9. Tools, scripts and data in this repository

### 9.1 Layout

```
README.md                    this document (generated, see below)
docs/src/*.md                its source, with listing placeholders
asm/                         annotated disassembly, generated from S640-251022.bin
patches/                     patch builders and the factory tag file
tools/                       measurement scripts, OpenOCD TCL scripts, generators
data/                        every measurement from the session
images/                      annotated photos, raw photos in images/raw/
wacom/                       the Wacom firmware comparison (no firmware files)
history/                     the earlier notes, scripts and wrong pinout pictures, unchanged
```

Regenerate the listings and this README from the stock image:

```
tools/gen_listings.sh /path/to/S640-251022.bin   # checks the SHA-256 first
python3 tools/build_readme.py
```

### 9.2 Patch builders (`patches/`)

| File | Use |
| :--- | :--- |
| `nosmooth.py OUT.bin [--nohold] [--fast]` | reads `S640-251022.bin` from the current directory. No flag: nosmooth. `--nohold`: nosmooth-nohold. `--fast`: also the failed changes of 6.5 (do not use) |
| `scanpatch.py TOTAL CAP OUT.bin` | the tuner experiment of 6.4 (stock = 100 and 80) |
| `build_window_only.py` | the failed window-only build of 6.5, exactly as run (do not use) |
| `hook.py OUT.bin` | `nosmooth-hook` (7.9, tested over SWD): same effect as nosmooth-nohold, nothing below `0x08003000` changed |
| `reverse.py OUT.bin` | the reverse-smoothing experiment of 7.10 (worse than stock, do not use); source `reverse.s` |
| `factory_tags_fc60.bin` | the 32 tag bytes for `0x0800FC60` (4.3) |

### 9.3 Measurement scripts (`tools/`, Python 3, no dependencies)

| File | What it does |
| :--- | :--- |
| `rate.py [seconds]` | reads every S640 hidraw node at once, prints reports, median interval, mean rate while moving, shortest interval |
| `still.py [seconds]` | pen must not move. Interval histogram and mean/std/range of X (bytes 3-4), Y (6-7) and pressure (9-10). The "status bytes" line shows byte 1, which is always `0x41` |
| `stroke.py [seconds]` | scribble fast. Prints the stroke sharpness of 7.5 |

`data/still_stock.txt` and `data/still_t80.txt` were made by an earlier version of `still.py`
that read X from bytes 2-3 (status byte + low byte of X). Their X values are meaningless;
their Y and pressure values are fine.

### 9.4 OpenOCD scripts (`tools/*.tcl`)

All are run as
`openocd -f interface/cmsis-dap.cfg -c 'transport select swd; set CPUTAPID 0' -f target/stm32f1x.cfg -c 'adapter speed 1000; reset_config none' -f tools/NAME.tcl`
(`prof*.tcl` used `adapter speed 4000`).

| File | What it does |
| :--- | :--- |
| `probe.tcl` | halts and reads CPUID, DHCSR, the FMC registers, flash size, option bytes, start of SRAM and flash, PC |
| `state.tcl` | FMC_OBSTAT, option bytes, first words of flash and of `0x0800FC60` |
| `clk.tcl` | TIMER5 and TIMER2 setup, RCU registers, measures the core clock with DWT_CYCCNT over 1 s |
| `vars.tcl` | reads the wait-length bytes (5.4, 5.5) |
| `prof.tcl` | samples DWT_PCSR N times without halting, prints 64-byte buckets with at least 40 hits |
| `prof2.tcl` | samples DWT_PCSR 8000 times into `pcs.txt` |
| `paths.tcl` | one hardware breakpoint at a time, reports which addresses are hit within 2.5 s (7.2) |
| `outcheck.tcl` | 5 snapshots of the history buffers and output coordinates (7.5) |
| `cyc.tcl` | cycles inside the frequency call and per report, with DWT_CYCCNT and breakpoints (5.9) |
| `count.tcl` | counts coil measurements per report and times one (5.9) |
| `pval.tcl` | 12 return values of the frequency call (6.5) |
| `sweep.tcl` | runs the Y coil measurement directly (burst on one coil, read on another) for a grid of A and B (6.7); halts the tablet, resets it at the end |
| `watch.tcl` | every 100 ms for 5 minutes, without halting: scan flags, peak coils, output position, newest history sample, counter (7.9) |

Breakpoint-based scripts halt the tablet briefly; the pen drops out for a moment while they run.

### 9.5 Generators

| File | What it does |
| :--- | :--- |
| `listing.py IMAGE START END …` | annotated Thumb-2 / M-profile disassembly (capstone); resolves every PC-relative literal and prints literal pools as `.word` |
| `datatables.py IMAGE` | vector table, carrier table, coil select table, position tables, USB descriptors, factory tag literals |
| `gen_listings.sh IMAGE` | all of `asm/`, including listings of the rebuilt patched images |
| `build_readme.py` | joins `docs/src/` and replaces listing placeholders with exact excerpts |
| `padscan.sh` | the MicroPython J1 pad scanner from 2026-10-03 (never produced data; kept for completeness) |

### 9.6 Data (`data/`)

| File | Content |
| :--- | :--- |
| `session_outputs_2026-10-06.txt` | every output of the session that was not saved to its own file: meter readings, OpenOCD output, register reads, unlock, restore, breakpoints, RAM snapshots, cycle counts |
| `rate_stock.txt`, `rate_t80.txt` | `rate.py`, 15 s, pen moving |
| `still_stock.txt`, `still_t80.txt`, `still_stock2.txt`, `still_nosmooth.txt`, `still_nohold.txt` | `still.py`, pen lying flat |
| `stroke_stock.txt`, `stroke_nosmooth.txt`, `stroke_nohold_c.txt` | `stroke.py`, fast scribbles (valid runs) |
| `stroke_nohold.txt`, `stroke_nohold_b.txt` | `stroke.py` runs where the pen barely moved (not comparable) |
| `profile_buckets_pen_in_use_12000.txt` | `prof.tcl`, 12000 samples, pen moving, stock |
| `pcs_window_only_build_pen_lost.txt` | 8000 raw PCs on the failed window-only build after the pen was lost |
| `padscan.log` | the 2026-10-03 pad scan attempt (only port errors) |
| `sweep_penaway_2026-10-08.txt` | `sweep.tcl`, pen away (6.7) |
| `watch_blind_stock_2026-10-08.txt`, `watch_blind_nohold_2026-10-08.txt`, `watch_blind_hook_2026-10-08.txt` | `watch.tcl` during the blind osu! test (7.9) |
| `watch_reverse_2026-10-08.txt` | `watch.tcl`, the reverse-smoothing image (7.10) |
| `watch_hook_osu_2026-10-08.txt` | `watch.tcl`, nosmooth-hook, earlier osu! session (scan flags always 0, 5.6) |

---

## 10. Checksums

SHA-256:

| File | Hash |
| :--- | :--- |
| `S640-251022.bin` (stock, not included) | `150fbc8b9cf356224245865c76ebab194083d72d32225921e6af55e83a287b45` |
| `S640-251022.hex` (stock, not included) | `8bbc8c491ad2806b3fcd18cdf5520974226ac413863477690e3e9091d9297319` |
| nosmooth, `s640_nosmooth.bin` | `ab25928dd939246f03fffbb858bded70663db3a4dbc37b01fb24c26d5477b7e2` |
| nosmooth-nohold, `s640_nosmooth_nohold.bin` | `371a4f7bc4ab181a1a41d58867bf31e7bc56dcaec656c0fe614f68995551877e` |
| T = 80, `test_t80.bin` | `93ac3e22e1c5b2dcec173d932f73bb843625f46872f41e0a3a9edd3b510ccf51` |
| nosmooth-hook, `s640_nosmooth_hook.bin` | `4f41d2b5c537efae1bc964f4f2c1298932ff3afdaa22dba708defc47744da96c` |
| reverse experiment (7.10, do not use) | `c17f91a3185d89dc0ea4a761d1fafc18af450d3234c432da93cdf3c990ae74f3` |
| failed `--fast` build, `test_v3.bin` | `986577b753ea574ed1bcee845152d949c743dc47393e655a319b6ad15cdbb592` |
| failed window-only, `test_v3_windowonly.bin` | `85de141275ada1ff30e6e74b3032a52587ae8375333959f6f9827ac03396d6a6` |
| `patches/factory_tags_fc60.bin` | `09816b76a42cd4c5109f91dc5e880c012fb89f37b815a53e20eb592851b50247` |
| the old "500 Hz" image `s640_firmware_500hz.bin` | `1835c781c2d2c9a7963432dff2187e1862df050e88b383d329c8fae8c35d0401` |
| the old "zero smoothing" image `s640_firmware_zero_smoothing.bin` (`bx lr` at `0x310`, do not use) | `47e0959add33d2c4cb44649c6a220b81824dd86f2152e0be829eca892165aec0` |
| `debugprobe_on_pico.uf2` used for the Pico | `6649ebba11df46cfa6cfa1faec9706bd21303893cf3f1e40067284bd4e3792d4` |

`tools/gen_listings.sh` rebuilds nosmooth, nosmooth-nohold and T = 80 from the stock image and records their
hashes in `asm/patched_images.sha256`; they match the table.

---

## 11. Open questions

* What exactly the hold flag `0x2000107E` (path A) is for, and whether anything sets it.
* How the frequency measurement turns `72 MHz / period + band offset` into the pen's
  resonant frequency (what feeds TIMER2 channel 2).
* What the mode in `0x20001054` (saved to settings page B after about 500 reports) does.
* What the settings pages held on this unit, and whether pressure, pen buttons and the
  express keys behave the same with them blank.
* Which of the six window constants breaks re-acquisition (6.5).
* How the X/Y interpolation in `0x08001330` and `0x0800142C` works, and what `0x08000390`,
  `0x080003AC` and `0x08000B24` do.
* The meaning of report bytes 11 and 12 (most likely tilt).
* Whether the unused `mov r5, sl` variant of nosmooth-nohold (7.4) behaves any differently in practice.
* Whether `nosmooth-hook` (7.9, works over SWD) can be written safely through Veikk's USB
  updater on an untouched tablet (0.2).
* Pressure smoothing: the 8-sample pressure average and the 4-report tip debounce (5.7) are
  still in every patch here.
* Whether a tablet with a different board than `HK1102 VER02b` exists at all (2.6).
* Which HC4051 each enable line (PA8, PB11 to PB15) drives.
* What sets the receive floor (about 80 counts in 6.7), and whether the 30 µs ring-down
  changes with pressure or between pens.
* Whether read protection stops the firmware itself from writing the first pages (0.3.2).
  That decides whether the bootloader idea in 0.3 can work.
* The S640 bootloader at `0x0800D800`: it is not in Veikk's update file. It matches
  GigaDevice's DFU example (0.3.1); a flash dump from a working tablet would confirm that and
  answer the settings questions.
