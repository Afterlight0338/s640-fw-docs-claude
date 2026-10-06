# Build the nosmooth-hook image (UNTESTED, README 0.2 and 7.9):
#   python3 hook.py out.bin
# Same effect as nosmooth-nohold, but no byte below 0x08003000 changes, so the result could
# in principle be written by Veikk's USB updater. It has only been assembled and checked
# against the disassembly, never run on a tablet.
#
# The main loop calls the position routine 0x08002834 at 0x08006822 and 0x0800685E. Both calls
# go to a new routine appended after the image (0x0800C464, free flash):
#
#   push {r4, r5, r6, lr}
#   ldr  r4, =0x2000107F    ; 19-entry history counter, changes on every valid sample
#   ldrb r5, [r4]
#   bl   0x08002834         ; the original routine: history, motion hold, 8-sample average
#   ldrb r0, [r4]
#   cmp  r0, r5
#   beq  done               ; no new sample this pass
#   ldr  r0, =0x2000107E    ; "path A" mode flag; the stock output routine skips when set
#   ldrb r0, [r0]
#   cbnz r0, done
#   ldr  r1, =0x20000482    ; histX
#   ldrh r0, [r1, #14]      ; histX[7], newest
#   ldr  r2, =0x20001040
#   strh r0, [r2]           ; outX
#   ldr  r1, =0x2000139A    ; histY
#   ldrh r0, [r1, #14]
#   strh r0, [r2, #2]       ; outY (0x20001042)
#   ldr  r1, =0x20001031
#   movs r0, #1
#   strb r0, [r1]           ; report pending
# done:
#   pop  {r4, r5, r6, pc}
import hashlib, sys

STOCK_SHA = "150fbc8b9cf356224245865c76ebab194083d72d32225921e6af55e83a287b45"
HOOK_AT = 0xC464  # offset of 0x0800C464, the end of the stock image
HOOK = bytes.fromhex(
    "70b50a4c2578f6f7e3f92078a8420cd00748007848b90749c889074a10800749"
    "c889508006490120087070bd7f1000207e10002082040020401000209a130020"
    "31100020")
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
