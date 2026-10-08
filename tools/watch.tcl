# Sample state from the running tablet without halting it (AHB-AP reads), every 100 ms.
# Columns: ms flagX flagY peakX peakY outX outY histX7 histY7 counter107F
proc u8 {a} { return [lindex [read_memory $a 8 1] 0] }
proc u16 {a} { return [lindex [read_memory $a 16 1] 0] }
init
set end [expr {[clock milliseconds] + 300000}]
while {[clock milliseconds] < $end} {
  if {[catch {
    echo [format "%d %d %d %d %d %d %d %d %d %d" [clock milliseconds] [u8 0x20001026] [u8 0x20001027] \
      [u8 0x2000101D] [u8 0x2000101E] [u16 0x20001040] [u16 0x20001042] \
      [u16 0x20000490] [u16 0x200013A8] [u8 0x2000107F]]
  } e]} { echo "ERR $e" }
  sleep 100
}
shutdown
