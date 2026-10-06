init
for {set i 0} {$i < 5} {incr i} {
  halt
  set hx [read_memory 0x20000482 16 8]; set hy [read_memory 0x2000139a 16 8]
  set o [read_memory 0x20001040 16 2]
  echo "histX $hx | outX [lindex $o 0]   histY7 [lindex $hy 7] outY [lindex $o 1]"
  resume; after 300
}
shutdown
