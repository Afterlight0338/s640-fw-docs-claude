# Call the Y measure wrapper 0x080027C8(0xFF, burst coil, read coil, channel) from SWD.
# Returns at a hw breakpoint on erased flash (0x0800C500); interrupts masked meanwhile.
proc rb {a} { return [lindex [read_memory $a 8 1] 0] }
proc meas {burst rd ch A B} {
  write_memory 0x20001094 8 $A
  write_memory 0x20000045 8 $B
  reg r0 0xff; reg r1 $burst; reg r2 $rd; reg r3 $ch
  reg pc 0x080027C8; reg xPSR 0x01000000
  reg lr 0x0800C501
  resume
  wait_halt 500
  return [expr {[lindex [regsub -all {.*: } [reg r0] ""] 0] & 0xffff}]
}
init
halt
reg primask 1
reg msp 0x200018F0
bp 0x0800C500 2 hw
echo "PB2 flag 0x2000105B = [rb 0x2000105B]"
set y 8
foreach B {60} {
 foreach A {0 1 2 3 4 5 6 8 10 20} {
  set row "A=$A B=$B:"
  foreach d {-2 -1 0 1 2} {
    set v {}
    for {set t 0} {$t < 3} {incr t} { lappend v [meas $y [expr {$y+$d}] 9 $A $B] }
    append row "  d=$d [join $v /]"
  }
  echo $row
 }
}
# B sweep at A=0 on the burst coil: transient integral vs window
foreach B {0 2 5 10 20 40 60} { echo "A=0 B=$B d=0: [meas $y $y 9 0 $B] [meas $y $y 9 0 $B]" }
rbp 0x0800C500
reset run
shutdown
