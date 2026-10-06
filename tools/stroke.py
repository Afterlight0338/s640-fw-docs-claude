# Stroke sharpness: python3 stroke.py [seconds]. Scribble fast. Smoothing lowers mean|d2x|/mean|dx|.
import os, sys, time, glob
dur = float(sys.argv[1]) if len(sys.argv) > 1 else 10
node = next("/dev/" + p.split("/")[4] for p in glob.glob("/sys/class/hidraw/*/device/uevent") if "00002FEB" in open(p).read() and "input2" in open(p).read())
fd = os.open(node, os.O_RDONLY); s = []
end = time.monotonic() + dur
while time.monotonic() < end:
    r = os.read(fd, 64); s.append((time.monotonic(), r[3] | r[4] << 8, r[6] | r[7] << 8))
d1 = d2 = n = 0
for (t0, x0, y0), (t1, x1, y1), (t2, x2, y2) in zip(s, s[1:], s[2:]):
    if t2 - t0 > 0.012 or abs(x1 - x0) + abs(y1 - y0) < 20: continue  # skip gaps and near-still samples
    d1 += abs(x1 - x0) + abs(y1 - y0); d2 += abs(x2 - 2 * x1 + x0) + abs(y2 - 2 * y1 + y0); n += 1
print(f"reports {len(s)}  moving triples {n}  mean|dx| {d1/max(n,1):.1f}  mean|d2x| {d2/max(n,1):.1f}  sharpness {d2/max(d1,1):.3f}")
