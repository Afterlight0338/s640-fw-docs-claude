# Build no-boxcar image: python3 nosmooth.py out.bin
# 0x08000310 averages histX/histY (8 or 4 samples) into outX/outY. Replace both
# averaging paths with: outX = histX[7]; outY = histY[7] (newest sample); pop.
import sys
b = bytearray(open("S640-251022.bin", "rb").read())
new = bytes.fromhex("c889 2080 d089 2880 f0bd")  # ldrh r0,[r1,#14]; strh r0,[r4]; ldrh r0,[r2,#14]; strh r0,[r5]; pop {r4-r7,pc}
for off, old in ((0x330, "0b8816885ff00100"), (0x356, "0b891689052031f8")):
    assert b[off:off + 8].hex() == old, (hex(off), b[off:off + 8].hex())
    b[off:off + len(new)] = new
open(sys.argv[1], "wb").write(b)
# v2 (pass --nodeadzone): 0x080017CA picks whether to refresh outX/outY based on a motion
# state; small movements skip the refresh (hold). Branch straight to "movs r0,#2; bl 0x08000310".
if "--nodeadzone" in sys.argv:
    assert b[0x17CA:0x17CE].hex() == "9af80000" and b[0x17F4:0x17FA].hex() == "0220fef78bfd"
    b[0x17CA:0x17CC] = bytes.fromhex("13e0")  # b 0x080017F4
    open(sys.argv[1], "wb").write(b)
# v3 (pass --fast): position only. Replace the pressure/frequency measurement call at
# 0x08001F94 (bl 0x0800272C) with movw r0,#2665 (measured hover value, no pressure).
# Shrink the coil tracking window extents in 0x08003CD0-0x08003F3E: 6->4, 5->3, 3->2 (2 stays).
if "--fast" in sys.argv:
    assert b[0x1F94:0x1F98].hex() == "00f0cafb"
    b[0x1F94:0x1F98] = bytes.fromhex("40f66920")  # movw r0, #0xa69
    for off, old, new in ((0x3CD0, 3, 2), (0x3DA0, 6, 4), (0x3DDE, 5, 3), (0x3E0A, 5, 3), (0x3F04, 5, 3), (0x3F38, 5, 3)):
        assert b[off] == old and b[off + 1] in (0x22, 0x24, 0x27), hex(off)
        b[off] = new
    open(sys.argv[1], "wb").write(b)
