proc r {a {n 1}} { if {[catch {set v [read_memory $a 32 $n]} e]} { echo [format "%08x: ERR" $a] } else { echo [format "%08x: %s" $a [lmap x $v {format %08x $x}]] } }
init
catch {halt 500}
r 0x4002201C
r 0x1FFFF800 4
r 0x08000000 4
r 0x0800FC60 8
shutdown
