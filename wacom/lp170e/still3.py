# still3.py SECONDS OUT.txt: log every report (t, status, X, Y, b11, b12) and summarise still-pen behaviour.
import os, sys, time, glob, statistics as st, collections
dur = float(sys.argv[1]); out = sys.argv[2]
node = next("/dev/" + p.split("/")[4] for p in glob.glob("/sys/class/hidraw/*/device/uevent") if "00002FEB" in open(p).read() and "input2" in open(p).read())
fd = os.open(node, os.O_RDONLY); R = []
end = time.monotonic() + dur
while time.monotonic() < end:
    r = os.read(fd, 64); t = time.monotonic()
    if len(r) >= 13 and r[1] == 0x41: R.append((t, r[2], r[3] | r[4] << 8 | r[5] << 16, r[6] | r[7] << 8 | r[8] << 16, r[11], r[12]))
with open(out, "w") as f:
    for x in R: f.write(" ".join(map(str, x)) + "\n")
I = [x for x in R if x[1] == 0xa0]
dt = [b[0] - a[0] for a, b in zip(I, I[1:])]
hist = collections.Counter(min(round(d * 1000), 20) for d in dt)
print(f"{len(I)} in-range reports in {dur:.0f} s = {len(I)/dur:.0f} Hz; interval ms histogram {dict(sorted(hist.items()))}")
for n, k in (("X", 2), ("Y", 3)):
    v = [x[k] for x in I]; m = st.median(v); s = sorted(abs(b - a) for a, b in zip(v, v[1:]))
    c = collections.Counter(int((x - m) // 4) * 4 for x in v)
    print(f"{n}: median {m} sd {st.pstdev(v):.1f} units ({st.pstdev(v)*5:.0f} um), p1-p99 {sorted(v)[len(v)//100]-m}..{sorted(v)[99*len(v)//100]-m}, "
          f"step median/p95/max {s[len(s)//2]}/{s[95*len(s)//100]}/{s[-1]}")
    print("   histogram (4-unit bins, offset from median):", " ".join(f"{k:+d}:{c[k]}" for k in sorted(c) if c[k] > len(v) // 300))
if any(x[4] or x[5] for x in I):
    pairs = collections.Counter((x[4], x[5]) for x in I)
    print("debug bytes (b11,b12) counts:", pairs.most_common(8))
    for key, cnt in pairs.most_common(4):
        sub = [x for x in I if (x[4], x[5]) == key]
        print(f"   {key}: n {cnt}  X median {st.median(x[2] for x in sub)}  Y median {st.median(x[3] for x in sub)}")
    flips = sum(1 for a, b in zip(I, I[1:]) if (a[4], a[5]) != (b[4], b[5]))
    print(f"   debug-byte changes between consecutive reports: {flips}")
