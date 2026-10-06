#!/usr/bin/env python3
"""
Veikk S640 Zero-Smoothing Firmware Generator
Target MCU: GigaDevice GD32F150C6T6 (ARM Cortex-M3 / Thumb-2)

This script patches official stock firmware (S640-251022) to completely remove:
1. The 8-sample and 4-sample coordinate boxcar moving average filter (up to 32ms latency).
2. The inline 2-sample coordinate moving average filter ((previous + current) / 2).
3. The micro-jitter / slow-movement smoothing filter.

Both patched binary and Intel HEX are emitted.
"""

import sys
import hashlib

BASE_ADDR = 0x08000000

def patch_firmware(stock_bin_path, out_bin_path, out_hex_path):
    with open(stock_bin_path, "rb") as f:
        stock_data = bytearray(f.read())

    patched_data = bytearray(stock_data)

    # Patch 1: Bypass Function 0x08000310 (8-sample & 4-sample boxcar moving average filter)
    # Original: 0xf0, 0xb5 ("push {r4, r5, r6, r7, lr}")
    # Patched:  0x70, 0x47 ("bx lr")
    p1_offset = 0x08000310 - BASE_ADDR
    assert stock_data[p1_offset:p1_offset+2] == b"\xf0\xb5", f"Patch 1 mismatch: {stock_data[p1_offset:p1_offset+2].hex()}"
    patched_data[p1_offset:p1_offset+2] = b"\x70\x47"

    # Patch 2: Bypass 2-sample moving average filter in coordinate update (0x08002eaa)
    # Original: 0x05, 0xd1 ("bne #0x8002eb8" -> branches to (prev+curr)/2)
    # Patched:  0x00, 0xbf ("nop" -> falls through to store raw sl, sb directly)
    p2_offset = 0x08002eaa - BASE_ADDR
    assert stock_data[p2_offset:p2_offset+2] == b"\x05\xd1", f"Patch 2 mismatch: {stock_data[p2_offset:p2_offset+2].hex()}"
    patched_data[p2_offset:p2_offset+2] = b"\x00\xbf"

    # Patch 3: Bypass slow-movement micro-jitter smoothing filter (0x08002f18)
    # Original: 0x04, 0xd1 ("bne #0x8002f24" -> branches to slow movement filter)
    # Patched:  0x00, 0xbf ("nop" -> falls through to store raw r3, r2 directly)
    p3_offset = 0x08002f18 - BASE_ADDR
    assert stock_data[p3_offset:p3_offset+2] == b"\x04\xd1", f"Patch 3 mismatch: {stock_data[p3_offset:p3_offset+2].hex()}"
    patched_data[p3_offset:p3_offset+2] = b"\x00\xbf"

    # Write binary
    with open(out_bin_path, "wb") as f:
        f.write(patched_data)

    # Write Intel HEX
    with open(out_hex_path, "w") as f:
        for i in range(0, len(patched_data), 16):
            addr = BASE_ADDR + i
            chunk = patched_data[i:i+16]
            if i % 65536 == 0:
                upper = (addr >> 16) & 0xffff
                f.write(f":02000004{upper:04X}{((0x100 - (2 + 4 + (upper >> 8) + (upper & 0xff))) & 0xff):02X}\n")
            record_addr = addr & 0xffff
            length = len(chunk)
            record = bytearray([length, (record_addr >> 8) & 0xff, record_addr & 0xff, 0x00]) + chunk
            checksum = (0x100 - (sum(record) & 0xff)) & 0xff
            f.write(f":{length:02X}{record_addr:04X}00{chunk.hex().upper()}{checksum:02X}\n")
        f.write(":00000001FF\n")

    print(f"Patched binary saved to: {out_bin_path} ({len(patched_data)} bytes)")
    print(f"Patched Intel HEX saved to: {out_hex_path}")
    print(f"Stock SHA256:   {hashlib.sha256(stock_data).hexdigest()}")
    print(f"Patched SHA256: {hashlib.sha256(patched_data).hexdigest()}")

if __name__ == "__main__":
    stock_bin = "/home/afterlight/veikk-s640-zero-smoothing/s640_firmware_stock_251022.bin"
    out_bin = "/home/afterlight/veikk-s640-zero-smoothing/s640_firmware_zero_smoothing.bin"
    out_hex = "/home/afterlight/veikk-s640-zero-smoothing/s640_firmware_zero_smoothing.hex"
    patch_firmware(stock_bin, out_bin, out_hex)
