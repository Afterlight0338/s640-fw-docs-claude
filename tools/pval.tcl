init
halt
set vals {}
for {set i 0} {$i < 12} {incr i} {
  bp 0x08001f98 2 hw; resume; wait_halt 3000; rbp 0x08001f98
  lappend vals [format %d [lindex [reg r0] 2]]
}
resume
echo "pressure fn returns: $vals"
shutdown
