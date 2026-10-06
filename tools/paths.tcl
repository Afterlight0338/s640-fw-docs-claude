init
foreach {a name} {0x080068f0 SANITY_delay 0x08002464 SANITY_coil 0x08000330 boxcar8 0x08000356 boxcar4 0x08002e98 bigmove 0x08002eca deadzone_or_done 0x08002eb8 halfavg 0x08002eac rawstore 0x08002f24 site3_filter 0x08002f1a site3_raw} {
  bp $a 2 hw
  catch {resume}
  set hit [expr {[catch {wait_halt 2500}] ? "no" : "HIT"}]
  catch {halt 200}
  rbp $a
  catch {resume}
  echo "$name ($a): $hit"
}
shutdown
