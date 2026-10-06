init
set n 12000; array set h {}
set vals [list]
for {set i 0} {$i < $n} {incr i} { lappend vals [lindex [read_memory 0xE000101C 32 1] 0] }
foreach v $vals { set k [format %08x [expr {$v & ~0x3f}]]; if {[info exists h($k)]} {incr h($k)} {set h($k) 1} }
foreach k [lsort [array names h]] { if {$h($k) >= 40} { echo "$k $h($k)" } }
shutdown
