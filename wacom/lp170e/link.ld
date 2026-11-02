MEMORY
{
  FLASH (rx)  : ORIGIN = 0x0800C464, LENGTH = 0x0800D000 - 0x0800C464
  RAM   (rwx) : ORIGIN = 0x20000900, LENGTH = 0x20001000 - 0x20000900   /* hole between the stock RW/ZI regions */
  RAM2  (rwx) : ORIGIN = 0x20001B90, LENGTH = 0x20001E00 - 0x20001B90   /* after the burst code: spill + debug code */
}
SECTIONS
{
  .boot ORIGIN(FLASH) : { *(.boot*) *(.rodata*) . = ALIGN(4); } > FLASH   /* exactly at 0xC464: build.py appends the blob there */
  .text : { *(.text*) . = ALIGN(4); } > RAM AT > FLASH
  .dbg : { *(.dbg*) . = ALIGN(4); } > RAM2 AT > FLASH
  __ram_load = LOADADDR(.text);
  __ram_start = ADDR(.text);
  __ram_end = ADDR(.text) + SIZEOF(.text);
  __dbg_load = LOADADDR(.dbg);
  __dbg_start = ADDR(.dbg);
  __dbg_end = ADDR(.dbg) + SIZEOF(.dbg);
  /DISCARD/ : { *(.comment) *(.ARM.*) *(.note*) }
}
