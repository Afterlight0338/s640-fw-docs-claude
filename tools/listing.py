#!/usr/bin/env python3
"""Annotated Thumb disassembly of a flash image.

usage: python3 listing.py IMAGE.bin START END [START END ...]
  START/END are absolute addresses (0x08xxxxxx). Every `ldr rX, [pc, #imm]`
  is annotated with the literal it loads, and words used as literals inside
  the range are printed as `.word` instead of being disassembled as code.
Needs capstone (nix-shell -p 'python3.withPackages(p:[p.capstone])').
"""
import struct, sys
import capstone

BASE = 0x08000000
img = open(sys.argv[1], "rb").read()
md = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_THUMB | capstone.CS_MODE_MCLASS)
md.detail = False


def lit_target(addr, insn):
    """Address loaded by a PC-relative ldr (16-bit T1 or 32-bit T2), else None."""
    if insn.mnemonic.startswith("ldr") and "[pc, #" in insn.op_str:
        imm = int(insn.op_str.split("[pc, #")[1].rstrip("]"), 0)
        return ((addr + 4) & ~3) + imm
    return None


def word(a):
    return struct.unpack_from("<I", img, a - BASE)[0]


def listing(start, end):
    # pass 1: collect literal addresses referenced from the range
    lits = set()
    a = start
    while a < end:
        insns = list(md.disasm(img[a - BASE:a - BASE + 4], a, 1))
        if not insns:
            a += 2
            continue
        t = lit_target(a, insns[0])
        if t is not None:
            lits.add(t)
        a += insns[0].size
    # pass 2: print
    out = []
    a = start
    while a < end:
        if a in lits:
            w = word(a)
            out.append(f"{a:08x}:  {img[a-BASE:a-BASE+4].hex(' '):<12}  .word    0x{w:08x}")
            a += 4
            continue
        insns = list(md.disasm(img[a - BASE:a - BASE + 4], a, 1))
        if not insns:
            out.append(f"{a:08x}:  {img[a-BASE:a-BASE+2].hex(' '):<12}  .short   0x{struct.unpack_from('<H', img, a-BASE)[0]:04x}")
            a += 2
            continue
        i = insns[0]
        line = f"{a:08x}:  {i.bytes.hex(' '):<12}  {i.mnemonic:<8} {i.op_str}"
        t = lit_target(a, i)
        if t is not None and BASE <= t < BASE + len(img) - 3:
            line += f"    ; =0x{word(t):08x}"
        out.append(line)
        a += i.size
    return "\n".join(out)


args = [int(x, 0) for x in sys.argv[2:]]
for s, e in zip(args[::2], args[1::2]):
    print(f"; ---- 0x{s:08x} .. 0x{e:08x}")
    print(listing(s, e))
