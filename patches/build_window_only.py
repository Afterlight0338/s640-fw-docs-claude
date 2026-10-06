# Exact code used on 2026-10-06 to build test_v3_windowonly.bin (nosmooth-nohold + smaller tracking window).
# Run next to test_nosmooth_v2.bin (output of: python3 nosmooth.py test_nosmooth_v2.bin --nohold).
# RESULT: tracks the pen, but never re-acquires it after the pen leaves range. Do not use.
b = bytearray(open('test_nosmooth_v2.bin','rb').read())
for off, old, new in ((0x3CD0,3,2),(0x3DA0,6,4),(0x3DDE,5,3),(0x3E0A,5,3),(0x3F04,5,3),(0x3F38,5,3)):
    assert b[off] == old; b[off] = new
open('test_v3_windowonly.bin','wb').write(b)
