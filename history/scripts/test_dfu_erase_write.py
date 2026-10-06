#!/usr/bin/env python3
import os, sys, time, struct, glob
import usb.core, usb.util

GD32_VID = 0x28e9
GD32_PID = 0x0189

DFU_DETACH    = 0
DFU_DNLOAD    = 1
DFU_UPLOAD    = 2
DFU_GETSTATUS = 3
DFU_CLRSTATUS = 4
DFU_ABORT     = 6

DFU_IDLE        = 2
DFU_DNBUSY      = 4
DFU_DNLOAD_IDLE = 5
DFU_ERROR       = 10

STATE_NAMES = {
    2: "DFU_IDLE", 3: "DNLOAD_SYNC", 4: "DNBUSY",
    5: "DNLOAD_IDLE", 6: "MANIFEST_SYNC", 7: "MANIFEST",
    8: "MANIFEST_WAIT_RESET", 9: "UPLOAD_IDLE", 10: "ERROR",
}

STATUS_NAMES = {
    0x00: "OK", 0x01: "errTARGET", 0x02: "errFILE", 0x03: "errWRITE",
    0x04: "errERASE", 0x05: "errCHECK_ERASED", 0x06: "errPROG",
    0x07: "errVERIFY", 0x08: "errADDRESS", 0x09: "errNOTDONE",
    0x0a: "errFIRMWARE", 0x0b: "errVENDOR", 0x0c: "errUSBR",
    0x0d: "errPOR", 0x0e: "errUNKNOWN", 0x0f: "errSTALLEDPKT",
}

def getstatus(dev):
    d = dev.ctrl_transfer(bmRequestType=0xa1, bRequest=DFU_GETSTATUS,
                          wValue=0, wIndex=0, data_or_wLength=6)
    status = d[0]
    poll_ms = d[1] | (d[2] << 8) | (d[3] << 16)
    state = d[4]
    return status, poll_ms, state

def clrstatus(dev):
    dev.ctrl_transfer(bmRequestType=0x21, bRequest=DFU_CLRSTATUS,
                      wValue=0, wIndex=0, data_or_wLength=0)

def abort(dev):
    dev.ctrl_transfer(bmRequestType=0x21, bRequest=DFU_ABORT,
                      wValue=0, wIndex=0, data_or_wLength=0)

def wait_state(dev, target, timeout=10.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        status, poll_ms, state = getstatus(dev)
        if status != 0:
            err_str = STATUS_NAMES.get(status, f"0x{status:02x}")
            state_str = STATE_NAMES.get(state, f"{state}")
            print(f"  DFU Error: status={err_str} in state={state_str}")
            clrstatus(dev)
            return False
        if state == target:
            return True
        time.sleep(max(poll_ms / 1000.0, 0.01))
    print(f"  Timeout waiting for state {STATE_NAMES.get(target, target)}")
    return False

def set_address(dev, addr):
    payload = struct.pack("<BI", 0x21, addr)
    dev.ctrl_transfer(bmRequestType=0x21, bRequest=DFU_DNLOAD,
                      wValue=0, wIndex=0, data_or_wLength=payload)
    return wait_state(dev, DFU_DNLOAD_IDLE)

def erase_page(dev, page_addr):
    payload = struct.pack("<BI", 0x41, page_addr)
    dev.ctrl_transfer(bmRequestType=0x21, bRequest=DFU_DNLOAD,
                      wValue=0, wIndex=0, data_or_wLength=payload)
    return wait_state(dev, DFU_DNLOAD_IDLE, timeout=15.0)

def read_flash(dev, addr, length):
    # DfuSe read sequence: Set address, Abort to IDLE, then UPLOAD
    if not set_address(dev, addr):
        return None
    abort(dev)
    time.sleep(0.05)
    # DFU_UPLOAD block 2 reads from current address pointer
    data = dev.ctrl_transfer(bmRequestType=0xa1, bRequest=DFU_UPLOAD,
                             wValue=2, wIndex=0, data_or_wLength=length)
    abort(dev)
    time.sleep(0.05)
    return bytes(data)

def main():
    dev = usb.core.find(idVendor=GD32_VID, idProduct=GD32_PID)
    if dev is None:
        print("GD32 DFU device not found.")
        sys.exit(1)

    if dev.is_kernel_driver_active(0):
        dev.detach_kernel_driver(0)
    usb.util.claim_interface(dev, 0)

    status, _, state = getstatus(dev)
    print(f"Initial state: {STATE_NAMES.get(state, state)}, status={STATUS_NAMES.get(status, hex(status))}")
    if state == DFU_ERROR:
        clrstatus(dev)
    if state != DFU_IDLE:
        abort(dev)
        time.sleep(0.1)

    print("\n--- Test 1: Reading from Sector 41 (0x0800a400 - USB Descriptor area) ---")
    data = read_flash(dev, 0x0800a55e, 32)
    if data:
        print(f"Read {len(data)} bytes from 0x0800a55e:")
        print(" ".join(f"{b:02x}" for b in data))
    else:
        print("Read failed.")

    print("\n--- Test 2: Testing Erase Command on 0x0800a400 ---")
    ok = erase_page(dev, 0x0800a400)
    print(f"Erase result: {ok}")

if __name__ == "__main__":
    main()
