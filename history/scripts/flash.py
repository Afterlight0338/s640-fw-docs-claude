#!/usr/bin/env python3
import os, sys, time, struct, glob
import usb.core, usb.util

VEIKK_VID  = 0x2feb
VEIKK_PID  = 0x0001
GD32_VID   = 0x28e9
GD32_PID   = 0x0189
BASE_ADDR  = 0x08000000
BLOCK_SIZE = 2048

DFU_DETACH    = 0
DFU_DNLOAD    = 1
DFU_GETSTATUS = 3
DFU_CLRSTATUS = 4
DFU_ABORT     = 6
DFU_IDLE      = 2
DFU_DNLOAD_IDLE = 5
DFU_ERROR     = 10

DFU_TRIGGER = bytes([0x00, 0x09, 0x04, 0x2f, 0xeb, 0x00, 0x00, 0x00, 0x00, 0xc0])

def find_hidraw():
    for uevent in glob.glob("/sys/class/hidraw/hidraw*/device/uevent"):
        data = open(uevent).read()
        if "2FEB" in data and "input2" in data:
            node = uevent.split("/")[4]
            return f"/dev/{node}"
    return None

def trigger_dfu(hidraw):
    with open(hidraw, "wb") as f:
        f.write(DFU_TRIGGER)

def wait_for_dfu(timeout=10):
    deadline = time.time() + timeout
    while time.time() < deadline:
        dev = usb.core.find(idVendor=GD32_VID, idProduct=GD32_PID)
        if dev is not None:
            return dev
        time.sleep(0.2)
    return None

def unlock_node(dev):
    bus = dev.bus
    addr = dev.address
    path = f"/dev/bus/usb/{bus:03d}/{addr:03d}"
    try:
        os.chmod(path, 0o666)
    except PermissionError:
        print(f"error: cannot chmod {path}, run as sudo")
        sys.exit(1)

def getstatus(dev):
    d = dev.ctrl_transfer(bmRequestType=0xa1, bRequest=DFU_GETSTATUS,
                          wValue=0, wIndex=0, data_or_wLength=6)
    return d[0], d[1] | (d[2] << 8) | (d[3] << 16), d[4]

def ctrl_out(dev, req, value, data=None):
    dev.ctrl_transfer(bmRequestType=0x21, bRequest=req,
                      wValue=value, wIndex=0,
                      data_or_wLength=data if data is not None else 0)

def wait_state(dev, target, timeout=5.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        status, poll_ms, state = getstatus(dev)
        if status != 0:
            ctrl_out(dev, DFU_CLRSTATUS, 0)
            return False
        if state == target:
            return True
        time.sleep(max(poll_ms / 1000.0, 0.01))
    return False

def flash(dev, firmware, base_addr):
    if dev.is_kernel_driver_active(0):
        dev.detach_kernel_driver(0)
    usb.util.claim_interface(dev, 0)

    _, _, state = getstatus(dev)
    if state == DFU_ERROR:
        ctrl_out(dev, DFU_CLRSTATUS, 0)
    if state != DFU_IDLE:
        ctrl_out(dev, DFU_ABORT, 0)
        time.sleep(0.1)

    ctrl_out(dev, DFU_DNLOAD, 0, struct.pack("<BI", 0x21, base_addr))
    if not wait_state(dev, DFU_DNLOAD_IDLE, timeout=10):
        print("error: set address failed")
        sys.exit(1)

    ctrl_out(dev, DFU_ABORT, 0)
    time.sleep(0.1)

    total = (len(firmware) + BLOCK_SIZE - 1) // BLOCK_SIZE
    for i in range(total):
        chunk = firmware[i * BLOCK_SIZE:(i + 1) * BLOCK_SIZE]
        block = i + 2
        addr  = base_addr + i * BLOCK_SIZE
        print(f"  [{(i+1)/total*100:5.1f}%]  0x{addr:08x}  {len(chunk)}B", end="\r", flush=True)
        ctrl_out(dev, DFU_DNLOAD, block, bytes(chunk))
        if not wait_state(dev, DFU_DNLOAD_IDLE, timeout=10):
            print(f"\nerror: timeout at block {block}")
            sys.exit(1)

    print()
    ctrl_out(dev, DFU_DNLOAD, total + 2)
    time.sleep(0.5)

    try:
        ctrl_out(dev, DFU_DETACH, 1000)
    except usb.core.USBError:
        pass
    time.sleep(2)
    try:
        dev.reset()
    except usb.core.USBError:
        pass

def main():
    if len(sys.argv) < 2:
        print(f"usage: {sys.argv[0]} <firmware.bin>")
        sys.exit(1)
    bin_path  = sys.argv[1]
    base_addr = int(sys.argv[2], 0) if len(sys.argv) > 2 else BASE_ADDR

    firmware = open(bin_path, "rb").read()
    print(f"firmware:  {bin_path}  ({len(firmware)} bytes)")

    hidraw = find_hidraw()
    if hidraw is None:
        print("error: S640 not found (stop OTD or re-plug)")
        sys.exit(1)

    print(f"hidraw:    {hidraw}")
    print("triggering DFU...")
    trigger_dfu(hidraw)

    print("waiting for GD32 DFU bootloader...")
    dev = wait_for_dfu()
    if dev is None:
        print("error: DFU device did not appear")
        sys.exit(1)

    print(f"found:     {GD32_VID:04x}:{GD32_PID:04x}  bus={dev.bus} dev={dev.address}")
    unlock_node(dev)

    print(f"flashing   {(len(firmware) + BLOCK_SIZE - 1) // BLOCK_SIZE} blocks to 0x{base_addr:08x}...")
    flash(dev, firmware, base_addr)

    print("done.")

if __name__ == "__main__":
    main()
