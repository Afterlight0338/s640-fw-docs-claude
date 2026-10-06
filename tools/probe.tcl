proc r {a {n 1}} { if {[catch {set v [read_memory $a 32 $n]} e]} { echo [format "%08x: ERR %s" $a $e] } else { echo [format "%08x: %s" $a [lmap x $v {format %08x $x}]] } }
init
catch {halt 500}
echo "state: [stm32f1x.cpu curstate]"
r 0xE000ED00
r 0xE000EDF0
r 0x40022000 8
r 0x1FFFF7E0
r 0x1FFFF800 4
r 0x20000000 4
r 0x08000000 2
r 0x0800D000 2
catch {echo [reg pc]}
shutdown
