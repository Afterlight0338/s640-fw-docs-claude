@ Variable-frequency carrier burst, runs from SRAM at 0x20001A00.
@ Called like the stock burst routines (table 0x08006B9C): [0x20000003] cycles on PC6-9.
@ Params at 0x20001F80: +0 high sled entry, +4 low sled entry (thumb addrs), +8/+12 CYCCNT start/end. +0x18 burst override.
    .syntax unified
    .thumb
    .global vburst
vburst:
    push {r4-r7, lr}
    ldr  r7, =0x20000003
    ldrb r4, [r7]
    ldr  r7, =0x20001F98   @ burst length override, 0 = use [0x20000003]
    ldr  r7, [r7]
    cbz  r7, 1f
    mov  r4, r7
1:
    ldr  r6, =0x48000800
    movw r5, #0x3c0
    ldr  r7, =0x20001F80
    ldr  r2, [r7]
    ldr  r3, [r7, #4]
    ldr  r1, =0xE0001004
    ldr  r0, [r1]
    str  r0, [r7, #8]
    cbz  r4, done
loop:
    str  r5, [r6, #0x18]
    blx  r2
    strh r5, [r6, #0x28]
    blx  r3
    subs r4, r4, #1
    bne  loop
done:
    ldr  r1, =0xE0001004
    ldr  r0, [r1]
    str  r0, [r7, #12]
    pop  {r4-r7, pc}
    .ltorg
    .balign 4
    .global sled
sled:
    .rept 160
    nop
    .endr
    .global sled_end
sled_end:
    bx lr
