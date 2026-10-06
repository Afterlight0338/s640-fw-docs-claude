#!/usr/bin/env python3
import os, sys, time, struct, glob
import usb.core, usb.util

GD32_VID   = 0x28e9
GD32_PID   = 0x0189
BASE_ADDR  = 0x08000000
WRITE_START= 0x08003000  # Start of writable region (116*001Kg)
PAGE_SIZE  = 1024        # 1 KB per page on GD32F150

DFU_DETACH    = 0
DFU_DNLOAD    = 1
DFU_UPLOAD    = 2
DFU_GETSTATUS = 3
DFU_CLRSTATUS = 4
DFU_ABORT     = 6

DFU_IDLE        = 2
DFU_DNLOAD_IDLE = 5
DFU_ERROR       = 10

DFU_TRIGGER = bytes([0x00, 0x09, 0x04, 0x2f, 0xeb, 0x00, 0x00, 0x00, 0x00, 0xc0])

def find_hidraw():
    for uevent in glob.glob("/sys/class/hidraw/hidraw*/device/uevent"):
        try:
            data = open(uevent).read()
            if "2FEB" in data and "input2" in data:
                node = uevent.split("/")[4]
                return f"/dev/{node}"
        except Exception:
            pass
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
    except Exception:
        pass

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

def ctrl_out(dev, req, value, data=None):
    dev.ctrl_transfer(bmRequestType=0x21, bRequest=req,
                      wValue=value, wIndex=0,
                      data_or_wLength=data if data is not None else 0)

def wait_state(dev, target, timeout=10.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        status, poll_ms, state = getstatus(dev)
        if status != 0:
            clrstatus(dev)
            return False
        if state == target:
            return True
        time.sleep(max(poll_ms / 1000.0, 0.01))
    return False

def erase_page(dev, page_addr):
    payload = struct.pack("<BI", 0x41, page_addr)
    ctrl_out(dev, DFU_DNLOAD, 0, payload)
    return wait_state(dev, DFU_DNLOAD_IDLE, timeout=15.0)

def set_address(dev, addr):
    payload = struct.pack("<BI", 0x21, addr)
    ctrl_out(dev, DFU_DNLOAD, 0, payload)
    return wait_state(dev, DFU_DNLOAD_IDLE, timeout=10.0)

def read_memory(dev, addr, length):
    if not set_address(dev, addr):
        return None
    abort(dev)
    time.sleep(0.02)
    data = dev.ctrl_transfer(bmRequestType=0xa1, bRequest=DFU_UPLOAD,
                             wValue=2, wIndex=0, data_or_wLength=length)
    abort(dev)
    time.sleep(0.02)
    return bytes(data)

def main():
    bin_path = sys.argv[1] if len(sys.argv) > 1 else "/home/afterlight/veikk-s640-zero-smoothing/s640_firmware_500hz.bin"
    firmware = open(bin_path, "rb").read()
    total_len = len(firmware)
    print(f"Firmware: {bin_path} ({total_len} bytes)")

    # Verify 500Hz bInterval=2 in the file
    off_desc = 0x0800a55e - 0x08000000
    ep83_interval = firmware[off_desc + 0x4d + 6]
    print(f"Target Endpoint 0x83 bInterval in file: {ep83_interval} ({1000//ep83_interval} Hz)")

    # Find and trigger device
    dev = usb.core.find(idVendor=GD32_VID, idProduct=GD32_PID)
    if dev is None:
        hidraw = find_hidraw()
        if hidraw is None:
            print("Error: S640 tablet not detected.")
            sys.exit(1)
        print(f"Found tablet on {hidraw}. Triggering DFU...")
        trigger_dfu(hidraw)
        dev = wait_for_dfu()
        if dev is None:
            print("Error: DFU bootloader did not appear.")
            sys.exit(1)

    print(f"Found DFU Device: {GD32_VID:04x}:{GD32_PID:04x}")
    unlock_node(dev)

    if dev.is_kernel_driver_active(0):
        dev.detach_kernel_driver(0)
    usb.util.claim_interface(dev, 0)

    status, _, state = getstatus(dev)
    if state == DFU_ERROR:
        clrstatus(dev)
    if state != DFU_IDLE:
        abort(dev)
        time.sleep(0.05)

    # 1. Erase writable sectors (0x08003000 to end of firmware)
    start_offset = WRITE_START - BASE_ADDR
    num_pages = (total_len - start_offset + PAGE_SIZE - 1) // PAGE_SIZE
    print(f"Erasing {num_pages} sectors from 0x{WRITE_START:08x}...")
    for i in range(num_pages):
        page_addr = WRITE_START + i * PAGE_SIZE
        print(f"  Erasing sector {12 + i}/127: 0x{page_addr:08x}...", end="\r", flush=True)
        if not erase_page(dev, page_addr):
            print(f"\nWarning: Erase returned error on 0x{page_addr:08x}")
    print(f"\nErase phase complete.")

    # 2. Program writable sectors
    print(f"Programming {num_pages} sectors from 0x{WRITE_START:08x}...")
    for i in range(num_pages):
        page_addr = WRITE_START + i * PAGE_SIZE
        page_off  = start_offset + i * PAGE_SIZE
        chunk     = firmware[page_off:page_off + PAGE_SIZE]
        print(f"  [{((i+1)/num_pages)*100:5.1f}%] Writing sector at 0x{page_addr:08x}...", end="\r", flush=True)
        
        # Set address pointer to this page
        if not set_address(dev, page_addr):
            print(f"\nError: Failed to set address 0x{page_addr:08x}")
            sys.exit(1)
        
        # In DfuSe, write page data starting at block 2
        # Transmit in 1024-byte chunk
        ctrl_out(dev, DFU_DNLOAD, 2, bytes(chunk))
        if not wait_state(dev, DFU_DNLOAD_IDLE, timeout=10.0):
            print(f"\nError: Failed writing block to 0x{page_addr:08x}")
            sys.exit(1)

    print("\nProgramming complete.")

    # 3. Readback Verification of USB Descriptor
    print("Verifying USB descriptor at 0x0800a55e...")
    readback = read_memory(dev, 0x0800a55e, 91)
    if readback:
        actual_interval = readback[0x4d + 6]
        print(f"Verification: Endpoint 0x83 bInterval on flash = {actual_interval}")
        if actual_interval == ep83_interval:
            print(">>> SUCCESS: Flash verification confirmed! 500 Hz descriptor written! <<<")
        else:
            print(f"Warning: bInterval mismatch (expected {ep83_interval}, got {actual_interval})")
    else:
        print("Note: Readback blocked by bootloader read protection (normal under RDP1).")

    # 4. Detach and reboot tablet
    print("Rebooting tablet into normal mode...")
    try:
        ctrl_out(dev, DFU_DETACH, 1000)
    except usb.core.USBError:
        pass
    time.sleep(1.5)
    try:
        dev.reset()
    except usb.core.USBError:
        pass

    print("Done! Check lsusb -v -d 2feb:0001 for bInterval = 2.")

if __name__ == "__main__":
    main()
