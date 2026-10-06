#!/usr/bin/env python3
import sys
import capstone

def main():
    bin_path = sys.argv[1] if len(sys.argv) > 1 else "/home/afterlight/veikk-s640-zero-smoothing/s640_firmware_stock_251022.bin"
    out_path = sys.argv[2] if len(sys.argv) > 2 else "/home/afterlight/veikk-s640-zero-smoothing/s640_firmware_stock_251022.asm"
    base_addr = 0x08000000

    try:
        with open(bin_path, "rb") as f:
            data = f.read()
    except Exception as e:
        print(f"Error opening {bin_path}: {e}", file=sys.stderr)
        sys.exit(1)

    total_bytes = len(data)
    print(f"Disassembling {bin_path} ({total_bytes} bytes, base 0x{base_addr:08x}) -> {out_path}...")

    md = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_THUMB)

    lines_written = 0
    offset = 0

    with open(out_path, "w") as out:
        while offset < total_bytes:
            curr_addr = base_addr + offset
            chunk = data[offset:min(offset + 16, total_bytes)]

            # Try to decode one instruction at current offset
            insns = list(md.disasm(chunk, curr_addr, count=1))

            if insns:
                insn = insns[0]
                raw_hex = insn.bytes.hex()
                # Format: 0x08000000:  f0 18 00 20    movs r0, #0
                formatted_hex = " ".join(f"{b:02x}" for b in insn.bytes)
                line = f"0x{insn.address:08x}:  {formatted_hex:<12}  {insn.mnemonic:<8} {insn.op_str}\n"
                out.write(line)
                offset += insn.size
            else:
                # 2-byte unaligned / undecodable halfword (literal pool data, alignment, or vector entry)
                if offset + 2 <= total_bytes:
                    raw = data[offset:offset+2]
                    formatted_hex = f"{raw[0]:02x} {raw[1]:02x}"
                    val = raw[0] | (raw[1] << 8)
                    line = f"0x{curr_addr:08x}:  {formatted_hex:<12}  .short   0x{val:04x}\n"
                    offset += 2
                else:
                    raw = data[offset:offset+1]
                    formatted_hex = f"{raw[0]:02x}"
                    line = f"0x{curr_addr:08x}:  {formatted_hex:<12}  .byte    0x{raw[0]:02x}\n"
                    offset += 1
                out.write(line)

            lines_written += 1
            if lines_written % 5000 == 0:
                print(f"  Processed {offset}/{total_bytes} bytes ({(offset/total_bytes)*100:4.1f}%)...", end="\r", flush=True)

    print(f"\nFinished! Wrote {lines_written} lines to {out_path}")

if __name__ == "__main__":
    main()
