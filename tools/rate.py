# Report-rate meter: python3 rate.py [seconds]. Reads all S640 hidraw nodes; move the pen while it runs.
import os, select, sys, time, glob, collections
dur = float(sys.argv[1]) if len(sys.argv) > 1 else 10
nodes = [ "/dev/" + p.split("/")[4] for p in glob.glob("/sys/class/hidraw/*/device/uevent") if "00002FEB" in open(p).read()]
fds = {os.open(n, os.O_RDONLY | os.O_NONBLOCK): n for n in nodes}
ts = collections.defaultdict(list); first = {}
end = time.monotonic() + dur
while (now := time.monotonic()) < end:
    for fd in select.select(list(fds), [], [], 0.2)[0]:
        try: d = os.read(fd, 64)
        except BlockingIOError: continue
        ts[fd].append(time.monotonic()); first.setdefault(fd, d.hex(" "))
for fd, n in fds.items():
    t = ts[fd]
    if len(t) < 3: print(n, "reports:", len(t)); continue
    dt = sorted(b - a for a, b in zip(t, t[1:]))
    active = [x for x in dt if x < 0.05]  # ignore pauses when the pen lifts
    print(f"{n}: {len(t)} reports, median {1000*dt[len(dt)//2]:.2f} ms -> {1/dt[len(dt)//2]:.0f} Hz, "
          f"active mean {len(active)/max(sum(active),1e-9):.0f} Hz, min {1000*dt[0]:.2f} ms  sample: {first[fd][:47]}")
