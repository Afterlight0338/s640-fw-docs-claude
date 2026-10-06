# history

The notes, scripts and pictures from before 2026-10-06, unchanged. They were written with
another AI assistant and contain mistakes; section 8 of the main README lists them.

* `VEIKK_S640_REVERSE_ENGINEERING_original.md`, `README_original.md`: the original notes.
* `scripts/`: the original tools. **Do not run `flash_500hz.py`**: it erases half the
  firmware over USB DFU and bricked this tablet when it stopped partway. `create_zero_smoothing_fw.py`
  builds an image whose first patch (`bx lr` at `0x08000310`) would stop all pen reports.
* `s640_pin_numbered_WRONG.jpg`, `s640_pin44_guide_WRONG.jpg`: pin labels for a 48-pin chip.
  The real chip is LQFP64 and BOOT0 is pin 60. Kept only to show what went wrong.
