    .syntax unified
    .cpu cortex-m3
    .thumb

    .equ ST,   0x20001F00   @ state, above the initial SP (0x200018F0)
    .equ OUT,  0x20001040
    .global hook
    .thumb_func
hook:
    push {r4, r5, r6, r7, lr}
    ldr  r4, =ST
    ldr  r6, =OUT
    ldrh r0, [r6]
    movw r1, #0xFFFF
    cmp  r0, r1
    bne  1f
    movs r0, #0
    strb r0, [r4]           @ pen was lost: forget the history
1:  bl   pos_fn                @ stock: history, hold, 8-sample average, sets pending
    ldr  r0, =0x20001031
    ldrb r0, [r0]
    cbz  r0, done           @ no report this pass: a PC filter would see nothing
    ldr  r0, =0x2000107E
    ldrb r0, [r0]
    cbnz r0, done
    ldrb r0, [r4]
    cmp  r0, #0xA5
    bne  seed
    ldrb r5, [r4, #1]
    movs r0, #0
    bl   axis
    movs r0, #2
    bl   axis
    adds r5, #1
    and  r5, r5, #7
    strb r5, [r4, #1]
    b    done
seed:
    ldrh r0, [r6]
    ldrh r1, [r6, #2]
    strh r0, [r4, #2]
    strh r1, [r4, #4]
    movs r2, #0
2:  add  r3, r4, r2, lsl #1
    strh r0, [r3, #8]
    strh r1, [r3, #0x18]
    adds r2, #1
    cmp  r2, #8
    blo  2b
    movs r0, #0
    strb r0, [r4, #1]
    movs r0, #0xA5
    strb r0, [r4]
done:
    pop  {r4, r5, r6, r7, pc}

@ r0 = 0 (X) or 2 (Y); r4 = ST, r5 = idx, r6 = OUT
@ rec = rec[n-8] + 8 * (out[n] - out[n-1]), the exact inverse of floor(sum of 8 / 8) minus rounding
    .thumb_func
axis:
    ldrh r1, [r6, r0]       @ smoothed output
    add  r2, r4, r0
    ldrh r3, [r2, #2]       @ previous smoothed output
    strh r1, [r2, #2]
    subs r3, r1, r3
    add  r7, r4, r0, lsl #3
    add  r7, r7, r5, lsl #1 @ rec[n-8] at [r7, #8]
    ldrh r2, [r7, #8]
    add  r3, r2, r3, lsl #3
    subs r2, r3, r1         @ guard: more than 2000 units (10 mm) off the average -> use the average
    it   mi
    rsbmi r2, r2, #0
    cmp  r2, #2000
    it   hi
    movhi r3, r1
    cmp  r3, #0
    it   lt
    movlt r3, #0
    movw r2, #0xFFFE
    cmp  r3, r2
    it   gt
    movgt r3, r2
    strh r3, [r7, #8]
    strh r3, [r6, r0]
    bx   lr
    .ltorg
