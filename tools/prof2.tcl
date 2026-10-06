init
set f [open pcs.txt w]
for {set i 0} {$i < 8000} {incr i} { puts $f [lindex [read_memory 0xE000101C 32 1] 0] }
close $f
shutdown
