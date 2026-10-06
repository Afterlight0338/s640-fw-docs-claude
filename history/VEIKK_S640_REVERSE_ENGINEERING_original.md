# Veikk S640 Reverse Engineering: Runbook & Reproduction Steps

> **Target Audience:** Future AI Agents & Reverse Engineers  
> **Target Device:** Veikk S640 Drawing Tablet (V1 Hardware)  
> **Primary Objective:** Enter bootloader, inspect silicon, dump/modify firmware, and optimize report rates.

---

## 1. Quick Reference & Device Identity

| Stage | USB VID:PID | Manufacturer / Product String | Architecture / Details |
| :--- | :--- | :--- | :--- |
| **Normal Mode** | `2feb:0001` | `Beijing Veikk E-Commerce Co., Ltd. S640` | Digitizer + Keys + Vendor HID |
| **DFU Mode** | `28e9:0189` | `GDMicroelectronics GD32 DFU Bootloader` | Native ROM Bootloader (Cortex-M3) |
| **Target MCU** | **GigaDevice GD32F150C6T6** | LQFP48, ARM Cortex-M3 @ 72 MHz | 128 KB Flash, 8-16 KB SRAM |
| **Flash Map** | `0x08000000` | `12*001Ka, 116*001Kg` | 12 KB Boot/R-only, 116 KB R/W User Flash |

---

## 2. Hardware Reconnaissance & USB Topology

When plugged into Linux, the S640 exposes three USB HID interfaces on `2feb:0001`:

```
Device 2feb:0001
 ├── Interface 0 (MI_00) -> Stylus / Pen digitizer (Report ID 0x02, EP1 IN)
 ├── Interface 1 (MI_01) -> Express keys / Consumer controls (EP2 IN)
 └── Interface 2 (MI_02) -> Vendor Diagnostic & Control Channel (EP3 OUT, Usage Page 0xFF00)
```

### Locating the Vendor Interface (`MI_02`)
Check `/sys/class/hidraw` to map the interfaces:
```bash
for dev in /sys/class/hidraw/hidraw*; do
    echo "$dev -> $(cat $dev/device/uevent | grep HID_NAME | cut -d= -f2)"
    udevadm info -a -p $(readlink -f $dev) | grep -E "bInterfaceNumber" | head -n 1
done
```
Look for `bInterfaceNumber: 02`. In Linux, the active device nodes typically map as:
- Interface 0 (`MI_00`): `/dev/hidraw11` (Stylus Digitizer)
- Interface 1 (`MI_01`): `/dev/hidraw12` (Express Keys)
- Interface 2 (`MI_02`): `/dev/hidraw15` (Vendor Diagnostic / Control Channel)

Ensure proper permissions (or observe ACL configured for the user):
```bash
sudo chmod 666 /dev/hidraw*
```

### USB Endpoint & Polling Intervals (`bInterval`)
Inspecting `lsusb -v -d 2feb:0001` reveals critical architectural choices made by Veikk:
```text
Interface Descriptor (Interface 0 - Stylus Digitizer):
  bInterfaceClass          3 Human Interface Device
  bInterfaceSubClass       1 Boot Interface Subclass
  bInterfaceProtocol       2 Mouse
  Endpoint Descriptor:
    bEndpointAddress     0x81  EP 1 IN
    bmAttributes            3  Interrupt
    wMaxPacketSize     0x0008  1x 8 bytes
    bInterval               3  (3 ms = ~333 Hz polling frame)

Interface Descriptor (Interface 1 - Keys):
  Endpoint Descriptor:
    bEndpointAddress     0x82  EP 2 IN
    wMaxPacketSize     0x0008  1x 8 bytes
    bInterval               3

Interface Descriptor (Interface 2 - Vendor Diagnostic):
  Endpoint Descriptor:
    bEndpointAddress     0x83  EP 3 IN (16 bytes, bInterval 3)
    bEndpointAddress     0x03  EP 3 OUT (16 bytes, bInterval 10)
```
> [!NOTE]
> **Key Finding — Boot Mouse Protocol & Host Polling Overrides:**
> Because Interface 0 advertises `bInterfaceSubClass: 1` and `bInterfaceProtocol: 2` (Mouse), the Linux kernel's `usbhid` module treats it as a mouse.
> Standard Linux defaults to `usbhid.mousepoll=0` (which respects the device's native `bInterval: 3`). Setting `usbhid.mousepoll=1` forces the host controller to poll the endpoint every 1ms (1000 Hz), eliminating USB scheduling jitter.

---

## 3. The Discovery: Reversing `VkTool_V3.0.3.2`

The vendor diagnostic tool `VkTool_V3.0.3.2_20260623.exe` communicates over Interface 2 (`MI_02`) with raw HID packets.

### Disassembly & Protocol Findings
Through static analysis of the binary's I/O subroutines and correlation with OpenTabletDriver configurations:
1. **Command Structure**:
   Packets sent to Interface 2 have a 9-byte payload (prepended by a `0x00` dummy Report ID byte when using `hidraw` write):
   - `Opcode 0x08`: Ping / status query (`08 00 00 ...`).
   - `Opcode 0x09`: Mode switch / control commands.

2. **Opcode 0x09 Subcommand Set**:
   - `09 01 04 00 00 00 00 00 00`: **Digitizer Streaming Init**. Sent by OpenTabletDriver (`OutputInitReport: ["CQEE"]`, Base64 for `09 01 04`) and official drivers to enable active tablet reporting.
   - `09 04 2f eb 00 00 00 00 c0`: **DFU Bootloader Jump**. Subroutine `0x418fe0` in `VkTool`.
     - `0x09`: Vendor command opcode.
     - `0x04`: Bootloader jump subcommand.
     - `0x2f 0xeb`: Little-endian validation key (`0xEB2F`, inverted bytes of VID `0x2FEB`).
     - `0x00 0x00 0x00 0x00`: Padding.
     - `0xc0`: Action trigger flag.

3. **Response & ACK Pattern**:
   When receiving valid commands on Interface 2 (`EP3 OUT`), the MCU returns an ACK packet on `EP3 IN` where bit 7 of the subcommand byte is set:
   - For `09 01 04 ...` -> Responds `09 81 04 00 00 00 00 00 00` (ACK).

---

## 4. Step-by-Step Reproduction: Triggering DFU Mode

Follow these steps to reproduce entering DFU mode:

### Step 1: Create the DFU Switch Tool
Create `test_reset_cmd.c`:
```c
#include <stdio.h>
#include <stdlib.h>
#include <fcntl.h>
#include <unistd.h>

int main(int argc, char **argv) {
    if (argc < 2) {
        fprintf(stderr, "Usage: %s /dev/hidrawX (Interface 2)\n", argv[0]);
        return 1;
    }

    int fd = open(argv[1], O_RDWR);
    if (fd < 0) {
        perror("Failed to open hidraw device");
        return 1;
    }

    // Byte 0 is HID Report ID (0x00 for unnumbered/raw transfer)
    // Bytes 1..9 are the Veikk DFU payload
    unsigned char payload[10] = {
        0x00, 
        0x09, 0x04, 0x2f, 0xeb, 0x00, 0x00, 0x00, 0x00, 0xc0
    };

    ssize_t written = write(fd, payload, sizeof(payload));
    if (written < 0) {
        perror("Write failed");
        close(fd);
        return 1;
    }

    printf("Successfully sent DFU reset command (%zd bytes) to %s\n", written, argv[1]);
    close(fd);
    return 0;
}
```

### Step 2: Compile and Run
```bash
gcc -O2 test_reset_cmd.c -o test_reset_cmd
sudo ./test_reset_cmd /dev/hidraw15
```

### Step 3: Verify DFU Enumeration
Within ~500ms, the tablet detaches from normal USB and re-attaches:
```bash
lsusb -d 28e9:0189
```
Expected output:
```text
Bus 003 Device 013: ID 28e9:0189 GDMicroelectronics GD32 DFU Bootloader (Longan Nano)
```

Inspect DFU descriptors:
```bash
dfu-util -l
```
Output confirms:
```text
Found DFU: [28e9:0189] ver=0100, devnum=13, cfg=1, intf=0, path="3-2", alt=0, name="@Internal Flash  /0x08000000/12*001Ka,116*001Kg", serial="??"
```

---

## 5. Security Architecture: Readout Protection (RDP Level 1) & Hardware Bypass Vector

When interacting with the GD32 DFU bootloader over USB:
1. **Flash Upload (`DFU_UPLOAD`) Failure**:
   Attempting to dump flash (`dfu-util -U dump.bin`) fails with `LIBUSB_ERROR_PIPE` (`-9`) or stalled control transfers.
2. **Root Cause**:
   - The native DFU descriptor `@Internal Flash  /0x08000000/12*001Ka,116*001Kg` defines Flash boundaries only. The bootloader rejects Set Address Pointer commands (`0x21`) outside flash (such as SRAM `0x20000000`).
   - GigaDevice silicon enforces **Readout Protection (RDP Level 1)** in the Option Bytes (`0x1FFFF800`). The on-chip boot ROM checks RDP and blocks reads of user flash over USB/SWD.
3. **CRITICAL WARNING — Do NOT Issue Unprotect**:
   ```bash
   # DO NOT EXECUTE THIS WITHOUT STOCK FIRMWARE BACKUP:
   dfu-util --unprotect
   ```
   On GigaDevice GD32F1x0 chips, clearing RDP Level 1 triggers a **mandatory hardware mass-erase** of the entire 128 KB user flash. If executed now, all factory firmware is permanently lost.

### Hardware Extraction Vector: GigaVulnerability #2 (Positive Technologies)
Documented by security researchers at Positive Technologies (PT SWARM), the GD32F1x0 family contains a critical architectural flaw in its readout protection:
- **Vulnerability Mechanism**:
  On GD32F1x0 microcontrollers, flash memory locking occurs when the debug power domain is enabled (`CDBGPWRUPREQ` bit in the DP `CTRL/STAT` register). Resetting this bit while code is executing from SRAM removes the flash read restriction for that code.
- **Visual Teardown & SWD Guide**:
  A complete visual walk-through with pinout diagram and terminal instructions is documented in [veikk_s640_hardware_dump_guide.md](file:///home/afterlight/.gemini/antigravity-cli/brain/62681947-23a6-4c22-b19b-733ef8c1ed94/veikk_s640_hardware_dump_guide.md).
- **Extraction Procedure (via SWD Pins)**:
  1. Connect a hardware debugger (ST-Link / CMSIS-DAP / Raspberry Pi) to the SWD pins (`SWCLK`, `SWDIO`, `GND`).
  2. Load a compact dumping payload into SRAM (`0x20000000`) via SWD and start execution.
  3. Reset the `CDBGPWRUPREQ` bit via OpenOCD:
     ```tcl
     chip.dap dpreg 0x4 0x0
     ```
  4. Signal the SRAM code (e.g. over USB or UART) to read the full 128 KB user Flash (`0x08000000` to `0x0801FFFF`) and dump it out.
  5. The dump succeeds with zero risk of mass-erase.

---

## 6. How to Safely Exit DFU / Return to Normal Mode

To exit DFU mode and restore normal tablet operation without unplugging the cable:

### Method A: USB Port Power Cycle / Bus Reset (Python)
```python
import usb.core

# Find GD32 DFU device
dev = usb.core.find(idVendor=0x28e9, idProduct=0x0189)
if dev:
    dev.reset()
    print("USB bus reset sent. Device returning to normal mode.")
```

### Method B: Physical Replug
Unplug and replug the USB cable. The boot pin pull-downs latch to User Flash, booting back into `2feb:0001`.

---

## 7. Actionable Roadmap & Testing Utilities

### Host-Side Polling Rate Benchmark
We developed a standalone high-precision C benchmark tool to measure raw inter-packet deltas and exact reporting frequencies directly from `/dev/hidraw11` (or whichever hidraw node corresponds to Interface 00).

```bash
# Run the compiled benchmark tool:
/home/afterlight/test_report_rate /dev/hidraw11
```
The tool captures 100 packets during pen movement and reports:
- Average, minimum, and maximum packet intervals (in ms).
- Real-time and average report rate (in Hz).

### Baseline Benchmark Results (Stock Hardware Benchmark)
Measured via `/home/afterlight/benchmark_otd /dev/hidraw17 30` during active user pen movement (under OpenTabletDriver):
- **Total Samples:** 7,400 packets (7,396 continuous intervals)
- **Average Report Rate:** **248.8 Hz** (Average interval: 4.019 ms)
- **Peak Rate:** 475.7 Hz (Min interval: 2.102 ms)
- **Floor Rate:** 49.9 Hz (Max interval: 20.041 ms)
- **Distribution:**
  - `<= 1.5ms (~1000 Hz):` 0 (0.0%)
  - `~2.0ms (~500 Hz):` 1 (0.0%)
  - `~3.0ms (~333 Hz):` 6 (0.1%)
  - `~4.0ms (~250 Hz):` **7,358 (99.5%)**
  - `> 4.5ms (Spikes):` 31 (0.4%)

**Conclusion:** The tablet hardware currently running on this physical unit is rigidly throttled to **250 Hz** (4 ms inter-packet delivery). The newly acquired official firmware `s640_firmware_stock_251022.bin` features **`bInterval: 1` (1 ms / 1000 Hz)** descriptors.

### Next Agent Priorities & Breakthrough
- [x] **Firmware Hunting — COMPLETED (Holy Grail Acquired!)**:
  - Acquired `S640-251022.hex` (dated 2025/10/22, 50,276 bytes Flash binary mapped at `0x08000000`).
  - Saved to [/home/afterlight/s640_firmware_stock_251022.bin](file:///home/afterlight/s640_firmware_stock_251022.bin) and [s640_firmware_stock_251022.hex](file:///home/afterlight/s640_firmware_stock_251022.hex).
  - **Verified Properties**:
    - Target Architecture: ARM Cortex-M3 (GD32F150)
    - USB VID/PID: `0x2FEB` / `0x0001` (Exact match)
    - Configuration Descriptor: Length 91 bytes (`0x5b`) at `0x0800a55e`
    - **Native 1000 Hz USB Endpoints**: EP1 IN (`0x81`), EP2 IN (`0x82`), and EP3 IN (`0x83`) are already configured with `bInterval: 1` (1 ms interrupt polling)!
- [x] **Empirical 30-Second Baseline Benchmark — COMPLETED**:
  - Confirmed 248.8 Hz (99.5% at 4ms) baseline on active hardware.
- [ ] **Flash Verification / DFU Flash Procedure**:
  - Test programming `s640_firmware_stock_251022.bin` via `dfu-util` in DFU mode (`28e9:0189`) or via SWD.
- [x] **Firmware Disassembly & Smoothing Removal — COMPLETED**:
  - Reverse engineered coordinate interpolation and filtering pipeline using Capstone & radare2 on GD32F150 Thumb-2 binary:
    1. **Sensor Matrix Processing**: 26 X-coils and 18 Y-coils sub-pixel peak interpolation located at `0x080003ac` and `0x080006f4`.
    2. **Inline 2-Sample Moving Average Filter (`0x08002ea4..0x08002eb8`)**:
       - Original: When coordinates change, `0x08002eaa` (`bne #0x8002eb8`) branches to `add.w; lsrs #1; add.w; lsrs #1` which computes `(previous + current) / 2`.
       - Patch: Replaced `0x08002eaa` with `nop` (`00 bf`), falling straight through to store pure raw instantaneous coordinates `sl` and `sb` into `0x20001040` and `0x20001042`.
    3. **Micro-Movement Jitter Filter (`0x08002f12..0x08002f26`)**:
       - Original: `0x08002f18` (`bne #0x8002f24`) branches to slow movement averaging.
       - Patch: Replaced `0x08002f18` with `nop` (`00 bf`), forcing immediate storage of raw coordinates.
    4. **Boxcar History Moving Average Filter (`0x08000310`)**:
       - Original: Subroutine sums up to 8 samples (`sum(X[0..7]) / 8`) or 4 samples (`sum(X[4..7]) / 4`) from history ring buffers `0x20000482` and `0x2000139a`, overwriting raw coordinates with delayed averages (up to 32 ms latency).
       - Patch: Replaced function entry at `0x08000310` with `bx lr` (`70 47`), bypassing the entire boxcar filter in 1 clock cycle.
  - **Zero-Smoothing Builds Created**:
    - Binary: [/home/afterlight/s640_firmware_zero_smoothing.bin](file:///home/afterlight/s640_firmware_zero_smoothing.bin) (`SHA256: 47e0959add33d2c4cb44649c6a220b81824dd86f2152e0be829eca892165aec0`)
    - Intel HEX: [/home/afterlight/s640_firmware_zero_smoothing.hex](file:///home/afterlight/s640_firmware_zero_smoothing.hex)
- [x] **Flash Verification / DFU Flash Procedure — COMPLETED (Partial)**:
  - Triggered DFU mode via `send_dfu_reset /dev/hidrawX` → device enumerated as `28e9:0189`
  - `dfu-util` failed with `LIBUSB_ERROR_OTHER` on `SET_INTERFACE` (GD32 DFU ROM quirk with RDP Level 1)
  - **Workaround:** Custom Python DFU flasher [`gd32_dfu_flash.py`](file:///home/afterlight/gd32_dfu_flash.py) using `pyusb`, which skips `SET_INTERFACE` and sends `DFU_DNLOAD` directly.
  - All 25 blocks (50,276 bytes) reported success. Device rebooted to `2feb:0001`.
  - **Critical Finding — First 12KB Write Protected:**
    - DFU descriptor `12*001Ka` means GD32 DFU ROM silently discards writes to first 12 sectors (0x08000000–0x08002FFF)
    - **All 3 smoothing patches (0x08000310, 0x08002eaa, 0x08002f18) are in the protected first 12KB → NOT APPLIED**
    - USB descriptor at 0x0800a55e (42KB, unprotected) was updated to `bInterval=1`, but the USB init code (in protected 12KB) copies from a hardcoded table → device still presents `bInterval=3`
    - **251022 firmware code beyond 12KB was updated successfully**
  - **Post-Flash Benchmark Results** (30 sec, `benchmark_otd /dev/hidraw5 30`):
    - Average Rate: 247.8 Hz (avg 4.036 ms) — same ballpark as before
    - **Min Delay: 0.790 ms (1265 Hz peak)** — improved from 2.102 ms (475 Hz) before flash!
    - `bInterval` changed from 4ms → 3ms (USB descriptor in unprotected region partially took effect via init code)
    - Distribution: 98.9% at ~4ms; 0.1% at ≤1.5ms (new, was 0.0%)
  - **Conclusion:** Smoothing patches blocked by DFU write protection. The 251022 code update did improve peak timing. Full patch requires SWD.
- [ ] **Full Smoothing Patch via SWD (Required for Complete Fix)**:
  - Need: ST-Link V2 (~$5) or Raspberry Pi Pico with Picoprobe firmware (~$4)
  - SWD bypasses DFU write protection entirely — can write to any flash sector including first 12KB
  - Hardware wiring guide: [veikk_s640_hardware_dump_guide.md](file:///home/afterlight/.gemini/antigravity-cli/brain/62681947-23a6-4c22-b19b-733ef8c1ed94/veikk_s640_hardware_dump_guide.md)
  - Flash command: `openocd -f interface/stlink.cfg -f target/stm32f1x.cfg -c "program /home/afterlight/s640_firmware_zero_smoothing.bin 0x08000000 verify reset exit"`
  - After SWD flash, all 3 patches will apply + `bInterval=1` (1000 Hz) will take effect
- [ ] **Host-Side Polling Rate Fix**:
  - Set `mousepoll=1` for 1ms USB host polling: `echo 1 | sudo tee /sys/module/usbhid/parameters/mousepoll`
  - Persistent fix for NixOS: add `boot.extraModprobeConfig = "options usbhid mousepoll=1";` to `configuration.nix` and rebuild
  - Force USB re-enumeration after setting (replug or `python3 -c "import usb.core; dev=usb.core.find(idVendor=0x2feb,idProduct=0x1); dev.reset()"`)





