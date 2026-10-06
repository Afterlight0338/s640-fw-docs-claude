#!/usr/bin/env bash
# Regenerate asm/*.lst from the stock image. usage: tools/gen_listings.sh path/to/S640-251022.bin
set -euo pipefail
img=${1:?stock image}
cd "$(dirname "$0")/.."
echo "150fbc8b9cf356224245865c76ebab194083d72d32225921e6af55e83a287b45  $img" | sha256sum -c -
gen() { # name start end [start end ...]
  local name=$1; shift
  nix-shell -p 'python3.withPackages(p:[p.capstone])' --run "python3 -I tools/listing.py '$img' $*" > "asm/$name.lst"
}
gen 01_reset_adc_helpers        0x08000190 0x08000310
gen 02_boxcar_filter            0x08000310 0x08000390
gen 03_scan_helpers_defaults    0x08000bc8 0x08000dc0
gen 04_pen_search               0x080010f8 0x08001290
gen 05_gpio_helpers             0x08001290 0x08001330
gen 06_motion_state_machine     0x08001650 0x08001834
gen 07_main_pen_routine         0x08001ee4 0x080023bc
gen 08_full_coil_scan           0x080023bc 0x08002464
gen 09_coil_measure             0x08002464 0x0800257c
gen 10_frequency_measure        0x0800257c 0x0800272c
gen 11_measure_wrappers         0x0800272c 0x08002834
gen 12_position_and_history     0x08002834 0x08002fc4
gen 13_tracking_scan            0x08002fc4 0x080030f8
gen 14_timing_tuner             0x08003abc 0x08003bb4
gen 15_tracking_window          0x08003cc8 0x08004006
gen 16_clock_init               0x08004068 0x08004182
gen 17_timer_irq_handlers       0x080041b8 0x08004224
gen 18_timer_helpers            0x08004224 0x080044b0
gen 19_tag_0226_function        0x08006554 0x08006640
gen 20_delay_sleds              0x080068f0 0x08006a0c
gen 21_settings_pages           0x08008240 0x0800855c
gen 22_report_builder           0x08008780 0x08008c04
gen 23_nvic_helper              0x08009198 0x0800925c
gen 24_rcu_helpers              0x0800937c 0x0800941c
gen 25_timer_init               0x080095d4 0x080096e8
gen 26_mux_idle                 0x08000a8c 0x08000bc8
gen 27_coil_select_routines     0x080030f8 0x08003abc
gen 28_carrier_burst_channels   0x080045c0 0x08005860
gen 29_x_position_from_coils    0x08001330 0x0800142c
gen 30_y_position_from_coils    0x0800142c 0x08001650
gen 31_misc_0x0800941c          0x0800941c 0x080095d4
# data tables last
nix-shell -p python3 --run "python3 -I tools/datatables.py '$img'" > asm/00_data_tables.txt
gen 32_hardfault_reset_and_vendor_cmds 0x08001588 0x08001990
gen 33_main_loop                0x0800663c 0x080068f0
# patched images, rebuilt from the stock image with the scripts in patches/
tmp=$(mktemp -d); ln -s "$(realpath "$img")" "$tmp/S640-251022.bin"
( cd "$tmp" && nix-shell -p python3 --run "python3 -I '$OLDPWD/patches/nosmooth.py' nosmooth.bin && python3 -I '$OLDPWD/patches/nosmooth.py' nosmooth-nohold.bin --nohold && python3 -I '$OLDPWD/patches/scanpatch.py' 80 70 t80.bin" )
L() { nix-shell -p 'python3.withPackages(p:[p.capstone])' --run "python3 -I tools/listing.py $*"; }
L "$tmp/nosmooth.bin" 0x08000310 0x08000390 > asm/patched_nosmooth_output_routine.lst
L "$tmp/nosmooth-nohold.bin" 0x080017c6 0x0800180a > asm/patched_nohold_state_machine_tail.lst
L "$tmp/t80.bin" 0x08003ae2 0x08003b0e 0x08003b40 0x08003b6c > asm/patched_t80_tuner.lst
sha256sum "$tmp"/*.bin | sed "s|$tmp/||" > asm/patched_images.sha256
rm -rf "$tmp"
