@ RDP page-lock test, linked at 0x0800C4A8 (after the nosmooth-hook routine).
@ Reset handler literal 0x080001AC points here instead of SystemInit.
@ For each page: program 0x0000 into the first padding slot still reading 0xFFFF,
@ log {addr, FMC_STAT, readback} at 0x20001F88 + 12*i. 0x20001F80 = magic, +4 = OBSTAT.
        .syntax unified
        .thumb
        .global test
test:
        push    {r4-r7, lr}
        ldr     r7, =0x20001F80
        ldr     r0, =0x4002201C
        ldr     r0, [r0]
        str     r0, [r7, #4]
        ldr     r6, =0x40022000         @ FMC: KEY +4, STAT +0xC, CTL +0x10
        ldr     r0, =0x45670123
        str     r0, [r6, #4]
        ldr     r0, =0xCDEF89AB
        str     r0, [r6, #4]
        adr     r4, table
        adds    r7, #8
        movw    r3, #0xFFFF
loop:
        ldr     r5, [r4]
        cbz     r5, done
        ldrh    r0, [r5]
        cmp     r0, r3
        beq     go
        ldr     r5, [r4, #4]
        ldrh    r0, [r5]
        cmp     r0, r3
        beq     go
        ldr     r0, =0xEEEEEEEE         @ no blank slot left
        b       rec
go:
        movs    r0, #0x34
        str     r0, [r6, #0xC]          @ clear PGERR WPERR ENDF
        movs    r0, #1
        str     r0, [r6, #0x10]         @ PG
        movs    r0, #0
        strh    r0, [r5]
wait:
        ldr     r0, [r6, #0xC]
        lsls    r1, r0, #31
        bne     wait
        movs    r1, #0
        str     r1, [r6, #0x10]
rec:
        str     r5, [r7]
        str     r0, [r7, #4]
        ldrh    r0, [r5]
        str     r0, [r7, #8]
        adds    r7, #12
        adds    r4, #8
        b       loop
done:
        movs    r0, #0x80
        str     r0, [r6, #0x10]         @ LOCK
        ldr     r7, =0x20001F80
        ldr     r0, =0x5AFE0001
        str     r0, [r7]
        ldr     r0, =0x080040F9         @ SystemInit
        blx     r0
        pop     {r4-r7, pc}
        .align  2
table:
        .word   0x08000212, 0x08000266  @ page 0
        .word   0x08000B1A, 0x08000B6E  @ page 2
        .word   0x08000C0E, 0x08000C6A  @ page 3
        .word   0x0800132E, 0x0800132E  @ page 4 (one slot)
        .word   0x0800141A, 0x08001516  @ page 5
        .word   0x080023B2, 0x080023BA  @ page 8
        .word   0x0800CC00, 0x0800CC02  @ page 51, blank control
        .word   0
        .ltorg
