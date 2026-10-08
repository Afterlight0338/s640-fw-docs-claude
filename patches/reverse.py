# Build the reverse-smoothing image (an experiment, README 7.10):
#   python3 reverse.py out.bin
# Same placement as nosmooth-hook (calls at 0x08006822/0x0800685E -> 0x0800C464, nothing below
# 0x08003000 changes), but the routine does what a PC-side filter would have to do: it only
# looks at each report's smoothed position and works the raw position back out,
#   rec[n] = rec[n-8] + 8 * (out[n] - out[n-1])
# assuming the 8-sample average. It never reads the raw history. State lives at 0x20001F00
# (above the stack). Source: reverse.s (arm-none-eabi-as, linked at 0x0800C464 with
# --defsym=pos_fn=0x08002835).
import hashlib, sys

STOCK_SHA = "150fbc8b9cf356224245865c76ebab194083d72d32225921e6af55e83a287b45"
HOOK_AT = 0xC464
HOOK = bytes.fromhex(
    "f0b5284c284e30884ff6ff71884201d100202070f6f7dcf92448007808b32448"
    "0078f0b92078a5280bd16578002000f019f8022000f016f8013505f007056570"
    "0fe0308871886080a180002204eb4203188119830132082af8d300206070a520"
    "2070f0bd315a04eb000253885180cb1a04ebc00707eb45073a8902ebc3035a1a"
    "48bf5242b2f5fa6f88bf0b46002bb8bf00234ff6fe729342c8bf13463b813352"
    "70470000001f002040100020311000207e100020")
CALLS = ((0x6822, "fcf707f8", "05f01ffe"),  # bl 0x08002834 -> bl 0x0800C464
         (0x685E, "fbf7e9ff", "05f001fe"))

b = bytearray(open("S640-251022.bin", "rb").read())
assert hashlib.sha256(b).hexdigest() == STOCK_SHA, "not the stock S640-251022.bin"
assert len(b) == HOOK_AT
for off, old, new in CALLS:
    assert b[off:off + 4].hex() == old, hex(off)
    b[off:off + 4] = bytes.fromhex(new)
b += HOOK
stock = open("S640-251022.bin", "rb").read()
assert b[:0x3000] == stock[:0x3000], "changed a byte below 0x08003000"
open(sys.argv[1], "wb").write(b)
print(sys.argv[1], len(b), "bytes, sha256", hashlib.sha256(b).hexdigest())
