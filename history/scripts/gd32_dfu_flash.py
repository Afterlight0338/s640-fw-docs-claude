#!/usr/bin/env python3
import sys, time, struct
import usb.core, usb.util

VID           = 0x28e9
PID           = 0x0189
BASE_ADDR     = 0x08000000
TRANSFER_SIZE = 2048

DFU_DETACH    = 0
DFU_DNLOAD    = 1
DFU_GETSTATUS = 3
DFU_CLRSTATUS = 4
DFU_ABORT     = 6

DFU_IDLE      = 2
DFU_DNLOAD_IDLE = 5
DFU_ERROR     = 10

STATE_NAMES = {
    2: "DFU_IDLE", 3: "DNLOAD_SYNC", 4: "DNBUSY",
    5: "DNLOAD_IDLE", 6: "MANIFEST_SYNC", 7: "MANIFEST",
    8: "MANIFEST_WAIT_RESET", 9: "UPLOAD_IDLE", 10: "ERROR",
}

def getstatus(dev):
    d = dev.ctrl_transfer(bmRequestType=0xa1, bRequest=DFU_GETSTATUS,
                          wValue=0, wIndex=0, data_or_wLength=6)
    return d[0], d[1] | (d[2] << 8) | (d[3] << 16), d[4]

def clrstatus(dev):
    dev.ctrl_transfer(bmRequestType=0x21, bRequest=DFU_CLRSTATUS,
                      wValue=0, wIndex=0, data_or_wLength=0)

def abort(dev):
    dev.ctrl_transfer(bmRequestType=0x21, bRequest=DFU_ABORT,
                      wValue=0, wIndex=0, data_or_wLength=0)

def wait(dev, target, timeout=5.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        status, poll_ms, state = getstatus(dev)
        if status != 0:
            clrstatus(dev)
            print(f"  error: status=0x{status:02x} state={STATE_NAMES.get(state, state)}")
            return False
        if state == target:
            return True
        time.sleep(max(poll_ms / 1000.0, 0.01))
    print(f"  timeout waiting for {STATE_NAMES.get(target, target)}")
    return False

def ctrl_out(dev, request, value, data=None):
    dev.ctrl_transfer(bmRequestType=0x21, bRequest=request,
                      wValue=value, wIndex=0,
                      data_or_wLength=data if data is not None else 0)

def main():
    bin_path  = sys.argv[1] if len(sys.argv) > 1 else "/home/afterlight/veikk-s640-zero-smoothing/s640_firmware_zero_smoothing.bin"
    base_addr = int(sys.argv[2], 0) if len(sys.argv) > 2 else BASE_ADDR

    firmware = open(bin_path, "rb").read()
    print(f"Firmware:  {bin_path}  ({len(firmware)} bytes)")
    print(f"Target:    {VID:04x}:{PID:04x}  base=0x{base_addr:08x}")

    dev = usb.core.find(idVendor=VID, idProduct=PID)
    if dev is None:
        print("error: device not found")
        sys.exit(1)

    if dev.is_kernel_driver_active(0):
        dev.detach_kernel_driver(0)

    try:
        usb.util.claim_interface(dev, 0)
    except usb.core.USBError as e:
        print(f"error: claim_interface: {e}")
        sys.exit(1)

    status, _, state = getstatus(dev)
    print(f"State:     {STATE_NAMES.get(state, state)}")

    if state == DFU_ERROR:
        clrstatus(dev)
        _, _, state = getstatus(dev)

    if state != DFU_IDLE:
        abort(dev)
        time.sleep(0.1)

    ctrl_out(dev, DFU_DNLOAD, 0, struct.pack("<BI", 0x21, base_addr))
    if not wait(dev, DFU_DNLOAD_IDLE, timeout=10):
        print("error: set address pointer failed")
        sys.exit(1)

    abort(dev)
    time.sleep(0.1)

    total = (len(firmware) + TRANSFER_SIZE - 1) // TRANSFER_SIZE
    print(f"Flashing   {total} blocks...")

    for i in range(total):
        chunk = firmware[i * TRANSFER_SIZE:(i + 1) * TRANSFER_SIZE]
        block = i + 2
        addr  = base_addr + i * TRANSFER_SIZE
        print(f"  [{(i+1)/total*100:5.1f}%]  block {block}  0x{addr:08x}  {len(chunk)}B", end="\r", flush=True)
        try:
            ctrl_out(dev, DFU_DNLOAD, block, bytes(chunk))
        except usb.core.USBError as e:
            print(f"\nerror: block {block}: {e}")
            sys.exit(1)
        if not wait(dev, DFU_DNLOAD_IDLE, timeout=10):
            print(f"\nerror: timeout at block {block}")
            sys.exit(1)

    print()
    ctrl_out(dev, DFU_DNLOAD, total + 2)

    time.sleep(0.5)
    try:
        _, _, state = getstatus(dev)
        print(f"Post-flash state: {STATE_NAMES.get(state, state)}")
    except usb.core.USBError:
        pass

    try:
        ctrl_out(dev, DFU_DETACH, 1000)
    except usb.core.USBError:
        pass

    time.sleep(2)
    try:
        dev.reset()
    except usb.core.USBError:
        pass

    print("Done.")

if __name__ == "__main__":
    main()
