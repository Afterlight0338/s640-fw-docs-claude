#!/usr/bin/env python3
"""Dump the data tables of S640-251022.bin that the docs refer to. usage: datatables.py IMAGE.bin"""
import struct, sys
img = open(sys.argv[1], "rb").read()
B = 0x08000000
u32 = lambda a: struct.unpack_from("<I", img, a - B)[0]
u16 = lambda a: struct.unpack_from("<H", img, a - B)[0]

print("== Vector table (0x08000000)")
core = ["initial SP", "Reset", "NMI", "HardFault", "MemManage", "BusFault", "UsageFault", "-", "-", "-", "-",
        "SVCall", "DebugMon", "-", "PendSV", "SysTick"]
for i in range(64):
    w = u32(B + 4 * i)
    name = core[i] if i < 16 else f"IRQ{i-16}"
    print(f"  [{i:2d}] 0x{B+4*i:08x}  0x{w:08x}  {name}")

print("\n== Carrier frequency table 0x080072b0 (16 x u32, Hz) and burst routines 0x08006b9c")
for i in range(16):
    f = u32(0x080072b0 + 4 * i)
    print(f"  ch{i:2d}  {f:6d} Hz  = 72 MHz / {72_000_000 / f:.1f}   routine 0x{u32(0x08006b9c + 4*i) & ~1:08x}")

print("\n== Coil/mux select routine table 0x08006a0c (100 x u32 function pointers, Thumb bit set)")
for i in range(0, 100, 4):
    print("  " + "  ".join(f"[{j:2d}] 0x{u32(0x08006a0c + 4*j):08x}" for j in range(i, i + 4)))

print("\n== Tables used by the position routine (0x080070d8 u16 x 101, 0x080071a2 u8 x 90, 0x080071fc u8 x 90)")
print("  0x080070d8: " + " ".join(str(u16(0x080070d8 + 2 * i)) for i in range(101)))
print("  0x080071a2: " + " ".join(str(img[0x71a2 + i]) for i in range(90)))
print("  0x080071fc: " + " ".join(str(img[0x71fc + i]) for i in range(90)))

print("\n== USB configuration descriptor at 0x0800a55e (91 bytes)")
d = img[0xa55e:0xa55e + 91]
i = 0
names = {2: "CONFIGURATION", 4: "INTERFACE", 5: "ENDPOINT", 0x21: "HID"}
while i < len(d):
    ln, ty = d[i], d[i + 1]
    print(f"  +0x{i:02x} ({0x0800a55e+i:#010x}) {names.get(ty, hex(ty)):<13} {d[i:i+ln].hex(' ')}")
    if ty == 5:
        print(f"         bEndpointAddress 0x{d[i+2]:02x}  bmAttributes {d[i+3]}  wMaxPacketSize {d[i+4] | d[i+5] << 8}  bInterval {d[i+6]}")
    i += ln

dev = img.find(bytes([0x12, 0x01]))
while dev != -1 and img[dev + 8:dev + 10] != b"\xeb\x2f":
    dev = img.find(bytes([0x12, 0x01]), dev + 1)
if dev != -1:
    print(f"\n== USB device descriptor at 0x{B+dev:08x}: {img[dev:dev+18].hex(' ')}")

print("\n== Factory tag constants compared by the firmware (expected at 0x0800fc60..0x0800fc7f)")
for a in (0x08002438, 0x0800243c, 0x080030c4, 0x080030c8, 0x080065d0, 0x080065d4, 0x080022d4, 0x080022d8):
    print(f"  literal 0x{a:08x} = 0x{u32(a):08x}")
