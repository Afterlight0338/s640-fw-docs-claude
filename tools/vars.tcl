init
foreach a {0x20000043 0x20001095 0x20001094 0x20000045 0x2000105b 0x20001093 0x20000044} { echo [format "%s = %d" $a [lindex [read_memory $a 8 1] 0]] }
shutdown
