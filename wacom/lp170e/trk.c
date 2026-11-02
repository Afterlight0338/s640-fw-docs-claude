/* Position-only tracker for a Wacom LP-170E on the Veikk S640, linked into free flash at 0x0800C464
 * and hooked into the stock 251022 firmware (build.py):
 *   trk_init  replaces the last start-up call (bl 0x08003A38 at 0x08006678) and calls it first
 *   trk_step  replaces the pen-mode dispatch of the main loop (0x08006794), once per pass
 * Search: power burst + full self-excited scan. Track: excite the peak coil, read the peak plus the
 * two nearest live coils on each side, parabola through peak and nearest neighbours.
 * Output: the vendor report 09 41 (status, X24, Y24, pressure 0, tilt 0) written to the firmware's
 * buffer 0x200001B5 (flag byte + 13 bytes); the main loop queues it (0x08001CD4) and USB sends it.
 * RAM above the stock stack top 0x200018F0 is unused by the stock firmware:
 *   0x20001A00 carrier burst (copied from vb[]), 0x20001E00 scratch, 0x20001EF0 SWD snapshot,
 *   0x20001F28 snapshot request, 0x20001F30 state, 0x20001F80 burst params. */
#include <stdint.h>
#include "vb.h"   /* vb[], VB_SLED_END: vburst.bin linked at 0x20001A00 */

/* Flash runs through a small cache: a miss costs ~2090 cycles (29 us; cold flash read 2091 vs 4 warm, measured
 * 2026-10-29). Run from flash, the tracker + stock main loop + stock measure path thrashed it: ~1.2 ms of misses
 * per pass. So only start-up code (BOOT) stays in flash; everything else is linked to run from the SRAM hole
 * 0x20000900..0x20000FFF (between the stock RW/ZI regions, nothing references it) and copied there by trk_init. */
#define BOOT __attribute__((section(".boot"), noinline))
extern uint8_t __ram_load[], __ram_start[], __ram_end[], __dbg_load[], __dbg_start[], __dbg_end[];
#define DBG __attribute__((section(".dbg"), noinline))   /* debug-build report code: SRAM 0x20001B90.. */
#define SPILL DBG                                   /* the 1792 B hole is full: these helpers live in .dbg too */

typedef uint32_t (*meas_t)(uint32_t, uint32_t, uint32_t, uint32_t);
#define XW ((meas_t)0x08002765)                     /* X wrapper: excite X coil r0, read r2 */
#define YW ((meas_t)0x080027C9)                     /* Y wrapper: excite Y coil r1, read r2 */
#define SCAN_BEGIN ((void (*)(void))0x08000BD1)     /* masks USB/SysTick/TIMER5 IRQs */
#define SCAN_END ((void (*)(void))0x08000C6D)
#define STOCK_INIT ((void (*)(void))0x08003A39)
#define R8(a) (*(volatile uint8_t *)(a))
#define R32(a) (*(volatile uint32_t *)(a))
#define VB_ADDR 0x20001A00u
#define CH ((0x20001F90u - 0x08006B9Cu) / 4)        /* burst table index that lands on 0x20001F90 */
#define DEAD_X ((1u << 10) | (1u << 16) | (1u << 21)) /* this unit's dead X coils */
#define DEAD_Y 0u
#ifndef WAIT_B
#define WAIT_B 60                                   /* B wait (us) before the ADC sample, per measurement */
#endif
enum { NX = 26, NY = 18, THR = 160, LOST = 20, PUMP = 1000 };  /* THR in 12-bit counts (= 40 in the stock 10-bit) */

#ifdef DEBUG_TIMING2
#define DEBUG_TIMING
#endif
struct st { uint32_t seq, search, xp, yp, rr, lost, inrange, ox, oy, mism, t_pass, t_start, n_search, msum, gbetw, t_q, mn, tlast, via, age; };  /* ends 0x20001F80 */
#define CYC R32(0xE0001004)
#define S ((volatile struct st *)0x20001F30)
#define XS ((volatile uint16_t *)0x20001E00)
#define YS ((volatile uint16_t *)0x20001E40)
typedef union { uint32_t w[13]; uint16_t h[26]; uint8_t b[52]; } frame_t;
#define FR ((volatile frame_t *)0x20001E80)        /* frame being built */
#define SNAP ((volatile uint32_t *)0x20001EF0)      /* whole frame for SWD, on request */
#define REQ R32(0x20001F28)

/* One measurement with all IRQs masked: an interrupt inside the burst or the wait windows inflates the
 * reading (v1 without this: ~10% of reports jumped 4-17 mm). PRIMASK is restored, not cleared, so a
 * caller can keep a whole frame masked (v3: tracking frames, for an even burst cadence). */
static uint32_t irq_off(void) { uint32_t m; __asm volatile("mrs %0, primask\n cpsid i" : "=r"(m) :: "memory"); return m; }
static void irq_restore(uint32_t m) { __asm volatile("msr primask, %0" :: "r"(m) : "memory"); }
/* The stock measure routine returns ADC >> 2; the full 12-bit conversion is still in ADC_RDATA when it
 * returns (v4 still-pen readings sat at +-1 count = the 10-bit quantization floor). Readings are 12-bit
 * from here on; if RDATA ever disagrees with the returned value, fall back to it and count (S->mism). */
#define ADC_RDATA R32(0x4001244C)
static uint32_t full(uint32_t v)
{
    uint32_t a = ADC_RDATA & 0xfff;
    if ((a >> 2) != v) { S->mism++; a = v << 2; }
    return a;
}
#ifdef DEBUG_TIMING2   /* per frame: cycles inside the masked measurements (msum), between one measurement call's
                          exit and the next one's entry (gbetw) */
static void mt(uint32_t c) { S->msum += c; S->mn++; }
#define MT_ENTRY uint32_t _e = CYC; if (S->tlast) S->gbetw += _e - S->tlast;
#define MT_BEGIN uint32_t _c = CYC;
#define MT_END mt(CYC - _c); uint32_t _u = CYC;
#define MT_EXIT { (void)_u; S->tlast = CYC; }
#else
#define MT_ENTRY
#define MT_BEGIN
#define MT_END
#define MT_EXIT
#endif
static uint32_t meas(meas_t w, uint32_t xc, uint32_t yc, uint32_t rd)
{
    MT_ENTRY
    uint32_t m = irq_off();
    MT_BEGIN
    uint32_t v = full(w(xc, yc, rd, CH) & 0xffff);
    MT_END
    irq_restore(m);
    MT_EXIT
    return v;
}
#define xm(ex, rd) meas(XW, (ex), 0xff, (rd))
#define ym(ex, rd) meas(YW, 0xff, (ex), (rd))

/* idx[2] = p, idx[1] / idx[3] = nearest live coil below / above, 0xFF = none. idx[0] and idx[4] (the
 * second neighbours) are only filled with WIN5: the fit uses the peak and its nearest neighbours, and the
 * peak can't move 2 coils in one ~1 ms frame, so v5 measures 3 coils per axis instead of 5. */
SPILL static void win(uint32_t p, uint32_t n, uint32_t dead, volatile uint8_t *idx)
{
    uint32_t c = p;
    idx[2] = p;
    for (int k = 1; k >= 0; k--) { do c--; while (c < n && (dead >> c & 1)); idx[k] = c < n ? c : 0xff; }
    c = p;
    for (int k = 3; k < 5; k++) { do c++; while (c < n && (dead >> c & 1)); idx[k] = c < n ? c : 0xff; }
#ifndef WIN5
    idx[0] = idx[4] = 0xff;
#endif
}

/* Window slot of the peak coil to keep: the current one (slot 2) unless another coil beats it by 1/8.
 * Without this a pen near a coil midpoint flips the peak (and the excited coil) every frame, and the
 * position hops between a few levels (v3: Y in 4 levels 12 units apart). */
SPILL static int keep(volatile uint8_t *idx, volatile uint16_t *w)
{
    int km = 2;
    for (int k = 0; k < 5; k++)
        if (idx[k] != 0xff && w[k] != 0xffff && w[k] > w[km]) km = k;
#ifdef HYST
    return w[km] > w[2] + w[2] / 8 ? km : 2;
#else
    return km;                                      /* v4 hysteresis made X worse (sd 2.8 -> 12.2 units) */
#endif
}

/* Reports go straight into the stock EP3 queue (8 x 16 B at 0x20000374, [0] = length 13; write index
 * 0x20001036, read index 0x20001037; the SysTick ISR sends one per ms), newest wins: if our previous in-range
 * report is still unsent, it is overwritten instead of queued behind. The stock path (flag buffer 0x200001B5,
 * copied by 0x08001CD4 each pass with no full check) had 28% of reports waiting behind an older one and 2% behind
 * two (dbgq, 2026-10-29); a tracker faster than 1 kHz would grow that backlog to 7 ms. Call with IRQs masked. */
#define TX ((volatile uint8_t *)0x20001FA0)         /* report being built, 13 bytes */
#define QC ((volatile uint8_t *)0x20000374)
/* Direct EP3 loading (v9+). Through the stock sender (SysTick 0x08005860, or the catch-up in SCAN_END) 32% of our
 * reports reached the endpoint one frame (~1 ms) stale and 4.4% never (dbgsend, 2026-10-29). So the newest report
 * goes straight into the EP3 packet memory when the endpoint is free. A packet still VALID (not polled yet) is
 * never touched: replacing it under NAK (v9-v13) collided with the host's poll, because a second load inside one
 * poll interval always lands just before the next poll. B=55 debug: every one of 71 host gaps per 10 s followed
 * such a replace, and a replace after the IN token has started can send a torn half-old half-new packet. Stock GD32 USBD: EPxCS 0x40005C00 + 4n, STAT_TX
 * bits 5:4 toggle on writing 1 (11 VALID, 10 NAK), CTR bits 15/7 clear on writing 0; packet memory 0x40006000 with
 * one 16-bit halfword per 32-bit word; BTABLE entry n = ADDR_TX, COUNT_TX, ... (as in usbd_ep_send 0x08006314).
 * Only after DIRECT_AFTER passes since boot (~10 s): if this ever breaks USB, a replug gives a window with the
 * stock path in which send_dfu_reset still works. */
#define EP3CS R32(0x40005C0C)
#define EP3LEN R32(0x20000124)                      /* stock EP3 IN transfer: bytes left, 0 = done */
#define STUCK R8(0x20001FB0)
#define PEND R8(0x20001FB1)                         /* TX holds a report that must still go out (pen left, 0xC0) */
#define DIRECT_AFTER 10000u
static void ep3_stat(uint32_t st)                  /* st = target STAT_TX bits (0x20 NAK, 0x30 VALID) */
{
    EP3CS = ((EP3CS & 0x8FBF) ^ st) | 0x8080;
}
static void ep3_load(void)                         /* call only when EP3 isn't VALID */
{
    volatile uint32_t *ent = (volatile uint32_t *)(0x40006000u + ((R32(0x40005C50) & 0xfff8) + 3 * 8) * 2);
    volatile uint16_t *d = (volatile uint16_t *)(0x40006000u + (ent[0] & 0xfffe) * 2);
    for (int k = 0; k < 7; k++) d[2 * k] = TX[2 * k] | (k < 6 ? TX[2 * k + 1] << 8 : 0);
    ent[1] = 13;                                    /* COUNT_TX */
    /* The stock USB IRQ treats every EP3 IN completion as progress of its own last transfer (struct at
     * 0x200000BC + 0x1C + 3 * 24: buf, len, count; written by usbd_ep_send 0x08006314). Without this it saw
     * our completions, decremented len below 0 and sent the following RAM as packets until the source passed
     * 0x20002000: bus fault in its PMA copy -> reset (v9 first try, caught with vector_catch). */
    R32(0x20000120) = (uint32_t)TX; R32(0x20000124) = 13; R32(0x20000128) = 0;
    ep3_stat(0x30);
    R8(0x2000101B) = 1;                             /* stock "EP3 busy": its sender won't load over us */
}
static void qput(void)
{
    if (S->seq > DIRECT_AFTER && R8(0x20001036) == R8(0x20001037)) {     /* stock queue empty */
#ifdef DEBUG_TIMING2    /* EP3 state at load (STAT_TX 2 bit, CTR_TX pending bit 2) and time since the previous load */
        { uint32_t e = EP3CS, t = CYC; S->via = (e >> 4 & 3) | (e >> 5 & 4); S->age = t - S->t_q; S->t_q = t; }
#endif
        /* Free = the stock IRQ has counted our previous packet's completion (its len back to 0) and EP3 isn't
         * VALID. STAT_TX alone isn't enough: while the host is reading the packet it can already show NAK with
         * CTR_TX not yet set; loading then rewrote the in-flight packet and the completion got counted against
         * the new one: len below 0 -> the stock IRQ sent the following RAM as packets until it bus-faulted
         * (dbgskip60, 2026-10-29). If CTR_TX is pending (IRQs masked: we're inside a report), let it run now. */
        uint32_t e = EP3CS;
        if (EP3LEN && (e & 0x80)) { __asm volatile("cpsie i\n nop\n nop\n cpsid i" ::: "memory"); e = EP3CS; }
        if (EP3LEN && !(e & 0x80) && (e & 0x30) != 0x30) {
            if (++STUCK > 2) EP3LEN = 0;            /* 3 frames with nothing in flight (USB reset?): give up on it */
        } else STUCK = 0;
        PEND = 0;
        if (!EP3LEN && (e & 0x30) != 0x30 && R8(0x200000BF) == 3) ep3_load();   /* configured (as usbd send checks) */
        else if (TX[2] != 0xA0) PEND = 1;           /* busy: an in-range frame is just dropped (the next one goes),
                                                       anything else is retried every pass (trk_step) */
        return;
    }
    uint32_t w = R8(0x20001036);
    volatile uint8_t *e = QC + 16 * ((w - 1) & 7);
    if (w == R8(0x20001037) || e[1] != 0x09 || e[2] != 0x41 || e[3] != 0xA0 || TX[2] != 0xA0) {
        e = QC + 16 * w;                            /* empty, or the pending entry isn't an in-range pen report */
        R8(0x20001036) = (w + 1) & 7;
#ifdef DEBUG_TIMING2
        S->t_q = CYC;                               /* sender age stamps (systick(), SCAN_END below) */
#endif
    }
    e[0] = 13;
    for (int i = 0; i < 13; i++) e[1 + i] = TX[i];
}

#ifdef DEBUG_RAW
/* Debug build only (OTD must be stopped: these bytes land in the pressure field). Report payload
 * (hidraw bytes 3..12, 80 bits LSB first): 5 window values x 12 bit (0xFFF = no coil), centre coil 5 bit,
 * axis 1 bit (0 X, 1 Y), seq 8 bit, ADC mismatch count 6 bit. Axes alternate per frame. */
DBG static void dbg_report(uint32_t axis, uint32_t centre, volatile uint16_t *w, uint32_t seq, uint32_t mism)
{
    volatile uint8_t *r = TX - 1;
    uint32_t bit = 0, m = irq_off();
    for (int i = 4; i < 14; i++) r[i] = 0;
#define PUT(x, n) do { for (uint32_t _b = 0; _b < (n); _b++, bit++) if (((x) >> _b) & 1) r[4 + (bit >> 3)] |= 1 << (bit & 7); } while (0)
    for (int k = 0; k < 5; k++) PUT(w[k] == 0xffff ? 0xfffu : w[k] & 0xfffu, 12);
    PUT(centre, 5); PUT(axis, 1); PUT(seq, 8); PUT(mism > 63 ? 63 : mism, 6);
#undef PUT
    r[1] = 0x09; r[2] = 0x41; r[3] = 0xA0;
    qput();
    irq_restore(m);
}
#endif

/* Peak position in firmware units (960 per coil, coil i centred at 960*(i+1)): parabola through the
 * kept peak (slot k0) and its nearest neighbours, which may be 2 coils away across a dead coil. */
SPILL static uint32_t pos(volatile uint8_t *idx, volatile uint16_t *w, int k0)
{
    int c0 = idx[k0], kl = k0 - 1, kr = k0 + 1;
    int32_t off = 0;
    if (kl >= 0 && kr < 5 && idx[kl] != 0xff && idx[kr] != 0xff) {
        int32_t a = c0 - idx[kl], b = idx[kr] - c0, L = (int32_t)w[kl] - w[k0], R = (int32_t)w[kr] - w[k0];
        int32_t num = b * b * L - a * a * R, den = 2 * (b * L + a * R);
        if (den) off = 960 * num / den;
        if (off < -960 * a) off = -960 * a;
        if (off > 960 * b) off = 960 * b;
    }
    return (uint32_t)(960 * (c0 + 1) + off);
}

/* vendor report, same scaling and clamps as the stock builder 0x08008780 */
static void report(uint32_t st, uint32_t ox, uint32_t oy)
{
    if (ox < 1560) ox = 1560;
    if (ox > 24130) ox = 24130;
    if (oy < 1760) oy = 1760;
    if (oy > 16580) oy = 16580;
    uint32_t X = (ox - 1560) * 30480 / 22570, Y = 20320 - (oy - 1760) * 20320 / 14820;
    volatile uint8_t *r = TX - 1;
    uint32_t m = irq_off();                         /* the SysTick sender reads the queue: no torn reports */
    r[1] = 0x09; r[2] = 0x41; r[3] = st;
    r[4] = X; r[5] = X >> 8; r[6] = X >> 16;
    r[7] = Y; r[8] = Y >> 8; r[9] = Y >> 16;
    r[10] = r[11] = r[12] = r[13] = 0;
    qput();
    irq_restore(m);
}

void trk_step(void) __attribute__((long_call));
BOOT void trk_step_flash(void) { trk_step(); }     /* main-loop hook target (flash); trk_step itself is in SRAM */

/* (2026-10-29 dbgsend measured the stock sender with a SysTick-vector wrapper in SRAM; removed: SysTick can fire
 * before trk_init has copied the SRAM code, which ran stale bytes from the previous image and wedged the next build.) */

BOOT void trk_init(void)
{
    STOCK_INIT();
    for (uint8_t *s = __ram_load, *d = __ram_start; d < __ram_end; ) *d++ = *s++;
    for (uint8_t *s = __dbg_load, *d = __dbg_start; d < __dbg_end; ) *d++ = *s++;
    volatile uint8_t *d = (volatile uint8_t *)VB_ADDR;
    for (uint32_t i = 0; i < sizeof vb; i++) d[i] = vb[i];
    R32(0x20001F80) = (VB_SLED_END - 2 * 19) | 1;   /* 672.9 kHz carrier, measured over SWD */
    R32(0x20001F84) = (VB_SLED_END - 2 * 20) | 1;
    R32(0x20001F90) = VB_ADDR | 1;
    R32(0x20001F98) = 0;
    R32(0xE000EDFC) |= 1u << 24;                    /* DWT CYCCNT, stamped by the burst */
    R32(0xE0001000) |= 1;
    PEND = 0; STUCK = 0;
    S->seq = 0; S->mism = 0; S->search = 1; S->xp = 13; S->yp = 9; S->rr = 0; S->lost = 0; S->inrange = 0;
    REQ = 0;
}

#ifdef DEBUG_TIMING
/* Debug build only (OTD must be stopped). Payload (hidraw bytes 3..12, LSB first): main-loop pass us 16 bit
 * (start of this trk_step to the start of the previous one), this frame's us 16 bit, search frames since the
 * last report 8 bit, lost 5 bit, ADC mismatches 6 bit, xmax>>7 5 bit, ymax>>7 5 bit, seq 8 bit. */
#define t_pass S->t_pass
#define t_start S->t_start
#define n_search S->n_search
__attribute__((unused)) DBG static void dbg_timing(uint32_t seq, uint32_t xmax, uint32_t ymax)
{
    volatile uint8_t *r = TX - 1;
    uint32_t bit = 0, fr_us = (R32(0xE0001004) - t_start) / 72, m = irq_off();
    for (int i = 4; i < 14; i++) r[i] = 0;
#define PUT(x, n) do { uint32_t _x = (x); for (uint32_t _b = 0; _b < (n); _b++, bit++) if ((_x >> _b) & 1) r[4 + (bit >> 3)] |= 1 << (bit & 7); } while (0)
    PUT(t_pass > 65535 ? 65535 : t_pass, 16); PUT(fr_us > 65535 ? 65535 : fr_us, 16);
    PUT(n_search > 255 ? 255 : n_search, 8); PUT(S->lost > 31 ? 31 : S->lost, 5); PUT(S->mism > 63 ? 63 : S->mism, 6);
    PUT(xmax >> 7 > 31 ? 31 : xmax >> 7, 5); PUT(ymax >> 7 > 31 ? 31 : ymax >> 7, 5); PUT(seq, 8);
#undef PUT
    r[1] = 0x09; r[2] = 0x41; r[3] = 0xA0;
    qput();
    irq_restore(m);
    n_search = 0;
}
#endif

#ifdef DEBUG_TIMING2
/* Debug build only (OTD must be stopped). Splits the tracking frame; ts[] = CYCCNT at trk_step start, after
 * win(), after SCAN_BEGIN, after the X loop, after the Y loop, after SCAN_END. Payload (hidraw bytes 3..12, LSB
 * first): pass us 13, X loop us 12, Y loop us 12, masked measurements us 12, via 3 + age us 11 (stock-sender mode:
 * bit 0 sent by SysTick, bit 1 by SCAN_END, age when sent; direct mode: EP3 STAT_TX at the previous load + bit 2
 * CTR_TX pending, time between the last two loads), EP3 queue depth 8, tag 0, seq 8. */
DBG static uint32_t put(uint32_t bit, uint32_t x, uint32_t n)     /* saturating LSB-first bit packer */
{
    volatile uint8_t *r = TX + 3;
    if (x > (1u << n) - 1) x = (1u << n) - 1;
    for (uint32_t b = 0; b < n; b++, bit++) if (x >> b & 1) r[bit >> 3] |= 1 << (bit & 7);
    return bit;
}
DBG static void dbg_timing2(uint32_t seq, const uint32_t *ts)
{
    volatile uint8_t *r = TX - 1;
    uint32_t bit = 0, m = irq_off();
    for (int i = 4; i < 14; i++) r[i] = 0;
#define PUT(x, n) bit = put(bit, (x), (n))
    PUT(t_pass, 13); PUT((ts[3] - ts[2]) / 72, 12); PUT((ts[4] - ts[3]) / 72, 12); PUT(S->msum / 72, 12);
    PUT(S->via, 3); PUT(S->age / 72, 11); PUT((R8(0x20001036) - R8(0x20001037)) & 7, 8); PUT(0, 1);
    S->via = 0;
    PUT(seq & 0xff, 8);
#undef PUT
    r[1] = 0x09; r[2] = 0x41; r[3] = 0xA0;
    qput();
    irq_restore(m);
}
#define TS(i) ts[i] = CYC
#else
#define TS(i)
#endif

static void frame(void)
{
#ifdef DEBUG_TIMING
    { uint32_t now = R32(0xE0001004); t_pass = (now - t_start) / 72; t_start = now; if (S->search) n_search++; }
#endif
#ifdef DEBUG_TIMING2
    uint32_t ts[6];
    ts[0] = t_start; S->msum = S->mn = S->gbetw = S->tlast = 0;
#endif
    uint32_t xp = S->xp, yp = S->yp, nxp = xp, nyp = yp, xmax = 0, ymax = 0;
    volatile frame_t *f = FR;
    R8(0x20000043) = 4; R8(0x20001095) = WAIT_B;    /* X wait A/B (us) */
    R8(0x20001094) = 4; R8(0x20000045) = WAIT_B;    /* Y wait A/B */
    R8(0x20000005) = 1; R8(0x2000105B) = 1;         /* PB2 level per axis */
    if (S->search) {
        uint32_t rr = S->rr;
        SCAN_BEGIN();
        R32(0x20001F98) = PUMP;
        if (rr & 0x40) ym(rr & 0x3f, rr & 0x3f); else xm(rr, rr);
        R32(0x20001F98) = 0;
        for (uint32_t i = 0; i < NX; i++) { XS[i] = xm(i, i); if (XS[i] > xmax) { xmax = XS[i]; nxp = i; } }
        SCAN_END();
        SCAN_BEGIN();
        for (uint32_t i = 0; i < NY; i++) { YS[i] = ym(i, i); if (YS[i] > ymax) { ymax = YS[i]; nyp = i; } }
        SCAN_END();
        xp = nxp; yp = nyp;
        win(xp, NX, DEAD_X, f->b + 0x20); win(yp, NY, DEAD_Y, f->b + 0x25);
        for (uint32_t k = 0; k < 5; k++) {
            uint32_t cx = f->b[0x20 + k], cy = f->b[0x25 + k];
            f->h[4 + k] = cx < NX ? XS[cx] : 0xffff;
            f->h[9 + k] = cy < NY ? YS[cy] : 0xffff;
        }
        if (xmax >= THR && ymax >= THR) { S->search = 0; S->lost = 0; }
        if (ymax >= THR && ymax >= xmax) rr = 0x40 | yp;
        else if (xmax >= THR) rr = xp;
        else rr = (rr & 0x40) || rr + 1 >= NX ? 0 : rr + 1;
        S->rr = rr;
    } else {
        win(xp, NX, DEAD_X, f->b + 0x20); win(yp, NY, DEAD_Y, f->b + 0x25);
        TS(1);
        SCAN_BEGIN();                               /* IRQs masked per measurement only: masking whole frames
                                                       (v3) starved USB control transfers (5 s per step). Skipping
                                                       SCAN_BEGIN/END here (v11): worse, 58 vs ~10 2 ms gaps per 10 s */
        TS(2);
        for (uint32_t k = 0; k < 5; k++) {
            uint32_t c = f->b[0x20 + k], v = c < NX ? xm(xp, c) : 0xffff;
            f->h[4 + k] = v;
            if (v != 0xffff && v > xmax) { xmax = v; nxp = c; }
        }
        TS(3);
        for (uint32_t k = 0; k < 5; k++) {
            uint32_t c = f->b[0x25 + k], v = c < NY ? ym(yp, c) : 0xffff;
            f->h[9 + k] = v;
            if (v != 0xffff && v > ymax) { ymax = v; nyp = c; }
        }
        TS(4);
#ifdef DEBUG_TIMING2
        { uint32_t r0 = R8(0x20001037), t = CYC; SCAN_END(); if (R8(0x20001037) != r0) { S->via |= 2; S->age = t - S->t_q; } }
#else
        SCAN_END();
#endif
        TS(5);
#ifdef TEST_LEAVE  /* test build: act as if the pen were lost for 22 frames every 4096 (leave report + re-acquire) */
        if (xmax < THR || ymax < THR || (S->seq & 4095) < LOST + 2) {
#else
        if (xmax < THR || ymax < THR) {
#endif
            if (++S->lost > LOST) {
                S->search = 1;
                if (S->inrange) { report(0xC0, S->ox, S->oy); S->inrange = 0; }
            }
        } else {
            int kx = keep(f->b + 0x20, f->h + 4), ky = keep(f->b + 0x25, f->h + 9);
            S->lost = 0; xp = f->b[0x20 + kx]; yp = f->b[0x25 + ky];
#ifdef WIN5
            S->ox = pos(f->b + 0x20, f->h + 4, kx);
            S->oy = pos(f->b + 0x25, f->h + 9, ky);
#else       /* 3-coil window: fit around the measured centre; the peak moves on for the next frame */
            S->ox = pos(f->b + 0x20, f->h + 4, 2);
            S->oy = pos(f->b + 0x25, f->h + 9, 2);
#endif
#ifdef DEBUG_TIMING2
            dbg_timing2(S->seq, ts);
#elif defined(DEBUG_TIMING)
            dbg_timing(S->seq, xmax, ymax);
#elif defined(DEBUG_RAW)
            if (S->seq & 1) dbg_report(1, f->b[0x25 + 2], f->h + 9, S->seq, S->mism);
            else dbg_report(0, f->b[0x20 + 2], f->h + 4, S->seq, S->mism);
#else
            report(0xA0, S->ox, S->oy);
#endif
            S->inrange = 1;
        }
    }
    S->xp = xp; S->yp = yp;
    f->w[1] = S->search | xp << 8 | yp << 16;
    f->w[7] = R32(0xE0001004);
    f->w[0] = f->w[12] = ++S->seq;
    if (REQ) { for (int i = 0; i < 13; i++) SNAP[i] = f->w[i]; REQ = 0; }
}

/* Once per stock main-loop pass (~200 us outside our frame, ~800 us per frame). FRAMES > 1 runs more tracking
 * frames per pass so they finish faster than the 1 ms polls. Only useful with direct EP loading: with the stock
 * sender, 2 frames per pass gave 887 Hz (v8) vs 954 (v7). */
#ifndef FRAMES
#define FRAMES 1
#endif
void trk_step(void)
{
    if (PEND) { uint32_t m = irq_off(); qput(); irq_restore(m); }
    frame();
    for (int i = 1; i < FRAMES && !S->search; i++) frame();
}

