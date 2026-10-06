# Build a scan-timing test image: python3 scanpatch.py TOTAL CAP out.bin
# TOTAL = per-coil wait A+B (stock 100), CAP = max wait A (stock 80).
import sys
t, cap, out = int(sys.argv[1]), int(sys.argv[2]), sys.argv[3]
b = bytearray(open("S640-251022.bin", "rb").read())
for off, old, new in ((0x3B08, 0x64, t), (0x3B66, 0x64, t), (0x3AEA, 0x50, cap), (0x3B48, 0x50, cap)):
    assert b[off] == old, hex(off)
    b[off] = new
assert cap < t <= 255
open(out, "wb").write(b)
