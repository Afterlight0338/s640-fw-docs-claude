proc rd {a} { return [lindex [read_memory $a 32 1] 0] }
init
halt
mww 0xE000EDFC 0x01000000
mww 0xE0001000 [expr {[rd 0xE0001000] | 1}]
proc at {a} { bp $a 2 hw; resume; wait_halt 3000; rbp $a; return [rd 0xE0001004] }
set out {}
for {set i 0} {$i < 6} {incr i} {
  set c0 [at 0x08001f94]; set c1 [at 0x08001f98]; set c2 [at 0x08001f94]
  lappend out "pressure [expr {($c1-$c0)&0xffffffff}] cyc, report period [expr {($c2-$c0)&0xffffffff}] cyc"
}
resume
foreach l $out { echo $l }
shutdown
