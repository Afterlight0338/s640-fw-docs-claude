proc rd {a} { return [lindex [read_memory $a 32 1] 0] }
init
echo [format "TIMER5 CTL0=%08x PSC=%d CAR=%d" [rd 0x40001000] [rd 0x40001028] [rd 0x4000102C]]
echo [format "TIMER2 PSC=%d CAR=%d" [rd 0x40000428] [rd 0x4000042C]]
echo [format "RCU CTL=%08x CFG0=%08x CFG1=%08x" [rd 0x40021000] [rd 0x40021004] [rd 0x4002102C]]
mww 0xE000EDFC 0x01000000
mww 0xE0001000 [expr {[rd 0xE0001000] | 1}]
set c0 [rd 0xE0001004]; set t0 [clock microseconds]
after 1000
set c1 [rd 0xE0001004]; set t1 [clock microseconds]
echo [format "sysclk ~ %.2f MHz" [expr {(($c1 - $c0) & 0xffffffff) / double($t1 - $t0)}]]
shutdown
