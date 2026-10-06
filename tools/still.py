# Still-pen test: python3 still.py [seconds]. Pen must not move. Prints rate and per-field noise.
import os, sys, time, statistics as st
dur = float(sys.argv[1]) if len(sys.argv) > 1 else 5
import glob
node = next("/dev/" + p.split("/")[4] for p in glob.glob("/sys/class/hidraw/*/device/uevent") if "00002FEB" in open(p).read() and "input2" in open(p).read())
fd = os.open(node, os.O_RDONLY)
ts, rs = [], []
end = time.monotonic() + dur
while time.monotonic() < end:
    rs.append(os.read(fd, 64)); ts.append(time.monotonic())
dt = sorted(b - a for a, b in zip(ts, ts[1:]))
f = lambda o: [r[o] | r[o + 1] << 8 for r in rs if len(r) > o + 1]
hist = {}
for d in dt: k = round(d * 1000); hist[k] = hist.get(k, 0) + 1
print(f"reports {len(rs)}  rate {len(rs)/dur:.0f} Hz  median {1000*dt[len(dt)//2]:.2f} ms  intervals(ms):{dict(sorted(hist.items())[:6])}")
for name, o in (("x@3", 3), ("y@6", 6), ("raw@9", 9)):
    v = f(o); print(f"  {name}: mean {st.mean(v):.1f}  std {st.pstdev(v):.2f}  range {max(v)-min(v)}")
print("  status bytes:", sorted({r[1] for r in rs}))
