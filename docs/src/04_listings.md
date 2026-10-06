
---

## 12. Annotated listings

Generated from `S640-251022.bin` by `tools/listing.py` (capstone, Thumb-2 with M-profile
system instructions). Each line is `address: bytes  mnemonic operands`; PC-relative loads
show the loaded value as `; =0x…`, and literal pools are printed as `.word`. Byte order is
as stored in flash.

| File | Range | Content (section) |
| :--- | :--- | :--- |
| `asm/00_data_tables.txt` | | vector table, carrier table, coil select table, position tables, USB descriptors, tag literals |
| `asm/01_reset_adc_helpers.lst` | `0x08000190` to `0x08000310` | reset handler, default handlers, ADC helpers (4.1, 5.4) |
| `asm/02_boxcar_filter.lst` | `0x08000310` to `0x08000390` | output routine, the 8-sample average (5.8) |
| `asm/03_scan_helpers_defaults.lst` | `0x08000BC8` to `0x08000DC0` | scan begin/end helpers, EXTI handlers, tuner call and A/B defaults (5.5) |
| `asm/04_pen_search.lst` | `0x080010F8` to `0x08001290` | no-pen search at channels 3, 6, 9, 10 (5.6) |
| `asm/05_gpio_helpers.lst` | `0x08001290` to `0x08001330` | GPIO init, BC and BOP writes (5.4) |
| `asm/06_motion_state_machine.lst` | `0x08001650` to `0x08001834` | motion hold (5.8) |
| `asm/07_main_pen_routine.lst` | `0x08001EE4` to `0x080023BC` | frequency, pen state, pressure (5.7) |
| `asm/08_full_coil_scan.lst` | `0x080023BC` to `0x08002464` | `"UGEE"` check, all-coil scan (4.3, 5.6) |
| `asm/09_coil_measure.lst` | `0x08002464` to `0x0800257C` | one coil measurement (5.4) |
| `asm/10_frequency_measure.lst` | `0x0800257C` to `0x0800272C` | the frequency measurement (5.7) |
| `asm/11_measure_wrappers.lst` | `0x0800272C` to `0x08002834` | per-axis wrappers (5.4) |
| `asm/12_position_and_history.lst` | `0x08002834` to `0x08002FC4` | position, histories, paths A and B (5.8) |
| `asm/13_tracking_scan.lst` | `0x08002FC4` to `0x080030F8` | `"3721"` check, windowed scan (5.6) |
| `asm/14_timing_tuner.lst` | `0x08003ABC` to `0x08003BB4` | wait A/B tuner (5.5) |
| `asm/15_tracking_window.lst` | `0x08003CC8` to `0x08004006` | window extents (5.6) |
| `asm/16_clock_init.lst` | `0x08004068` to `0x08004182` | clock setup, SystemInit (5.2) |
| `asm/17_timer_irq_handlers.lst` | `0x080041B8` to `0x08004224` | TIMER2 capture and TIMER5 interrupts (4.1) |
| `asm/18_timer_helpers.lst` | `0x08004224` to `0x080044B0` | timer library helpers |
| `asm/19_tag_0226_function.lst` | `0x08006554` to `0x08006640` | `"0226"` check, baseline subtraction (5.6) |
| `asm/20_delay_sleds.lst` | `0x080068F0` to `0x08006A0C` | NOP delays (5.3) |
| `asm/21_settings_pages.lst` | `0x08008240` to `0x0800855C` | settings page load and save (4.4) |
| `asm/22_report_builder.lst` | `0x08008780` to `0x08008C04` | reports (5.8) |
| `asm/23_nvic_helper.lst` | `0x08009198` to `0x0800925C` | NVIC setup, system reset helper |
| `asm/24_rcu_helpers.lst` | `0x0800937C` to `0x0800941C` | clock enable helpers |
| `asm/25_timer_init.lst` | `0x080095D4` to `0x080096E8` | TIMER2 and TIMER5 setup (5.2) |
| `asm/26_mux_idle.lst` | `0x08000A8C` to `0x08000BC8` | all mux lines idle (5.4) |
| `asm/27_coil_select_routines.lst` | `0x080030F8` to `0x08003ABC` | the routines behind the coil select table (5.4) |
| `asm/28_carrier_burst_channels.lst` | `0x080045C0` to `0x08005860` | the 16 carrier burst routines (5.3) |
| `asm/29_x_position_from_coils.lst` | `0x08001330` to `0x0800142C` | raw X from coil amplitudes (not analysed) |
| `asm/30_y_position_from_coils.lst` | `0x0800142C` to `0x08001650` | raw Y from coil amplitudes (not analysed) |
| `asm/31_misc_0x0800941c.lst` | `0x0800941C` to `0x080095D4` | start-up helpers (not analysed) |
| `asm/32_hardfault_reset_and_vendor_cmds.lst` | `0x08001588` to `0x08001990` | HardFault reset, vendor command handler incl. DFU request (3.1) |
| `asm/33_main_loop.lst` | `0x0800663C` to `0x080068F0` | main loop, modes, bootloader jump (5.1, 3.1) |
| `asm/patched_nosmooth_output_routine.lst` | | nosmooth output routine |
| `asm/patched_nohold_state_machine_tail.lst` | | nosmooth-nohold state machine tail |
| `asm/patched_t80_tuner.lst` | | T = 80 tuner |
| `asm/patched_hook.lst` | | nosmooth-hook: redirected calls and the hook (untested) |

The routines that matter most, in full:

<details>
<summary>Output routine (boxcar), 0x08000310</summary>

```
{{file asm/02_boxcar_filter.lst}}
```

</details>

<details>
<summary>Motion state machine, 0x08001650</summary>

```
{{file asm/06_motion_state_machine.lst}}
```

</details>

<details>
<summary>One coil measurement, 0x08002464</summary>

```
{{file asm/09_coil_measure.lst}}
```

</details>

<details>
<summary>Frequency measurement, 0x0800257C</summary>

```
{{file asm/10_frequency_measure.lst}}
```

</details>

<details>
<summary>Per-axis measurement wrappers, 0x0800272C</summary>

```
{{file asm/11_measure_wrappers.lst}}
```

</details>

<details>
<summary>Full coil scan ("UGEE"), 0x080023BC</summary>

```
{{file asm/08_full_coil_scan.lst}}
```

</details>

<details>
<summary>Tracking scan ("3721"), 0x08002FC4</summary>

```
{{file asm/13_tracking_scan.lst}}
```

</details>

<details>
<summary>Timing tuner, 0x08003ABC</summary>

```
{{file asm/14_timing_tuner.lst}}
```

</details>

<details>
<summary>Tracking window, 0x08003CC8</summary>

```
{{file asm/15_tracking_window.lst}}
```

</details>

<details>
<summary>Baseline subtraction ("0226"), 0x08006554</summary>

```
{{file asm/19_tag_0226_function.lst}}
```

</details>

<details>
<summary>Timer interrupts, 0x080041B8</summary>

```
{{file asm/17_timer_irq_handlers.lst}}
```

</details>

<details>
<summary>Main loop, 0x0800663C</summary>

```
{{file asm/33_main_loop.lst}}
```

</details>

<details>
<summary>HardFault handler and vendor commands, 0x08001588</summary>

```
{{file asm/32_hardfault_reset_and_vendor_cmds.lst}}
```

</details>

<details>
<summary>Data tables (vector table, carrier table, coil select table, USB descriptors)</summary>

```
{{file asm/00_data_tables.txt}}
```

</details>

---

*Measured, read and written on 2026-10-06. Corrections welcome as issues or pull requests.*
