proc rd {a} { return [lindex [read_memory $a 32 1] 0] }
init
halt
mww 0xE000EDFC 0x01000000
mww 0xE0001000 [expr {[rd 0xE0001000] | 1}]
bp 0x08001f94 2 hw
resume; wait_halt 3000
for {set r 0} {$r < 2} {incr r} {
  bp 0x08002464 2 hw
  set n 0; set sum 0; set callers {}
  set c0 [rd 0xE0001004]
  while 1 {
    resume; wait_halt 3000
    set pc [lindex [reg pc] 2]
    if {$pc == 0x08001f94} break
    incr n
    set lr [format %08x [expr {[lindex [reg lr] 2] & ~1}]]
    if {[dict exists $callers $lr]} {dict incr callers $lr} {dict set callers $lr 1}
  }
  set c1 [rd 0xE0001004]
  rbp 0x08002464
  echo "report $r: coil measurements $n, period [expr {($c1-$c0)&0xffffffff}] cyc, callers $callers"
}
rbp 0x08001f94
# time one measurement
bp 0x08002464 2 hw; resume; wait_halt 3000; rbp 0x08002464
set ret [expr {[lindex [reg lr] 2] & ~1}]
set c0 [rd 0xE0001004]; bp $ret 2 hw; resume; wait_halt 3000; rbp $ret
echo "one coil measurement: [expr {([rd 0xE0001004]-$c0)&0xffffffff}] cyc"
resume
shutdown
