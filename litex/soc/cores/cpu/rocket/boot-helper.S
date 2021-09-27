.section    .text, "ax", @progbits
.global boot_helper
.global smp_ap_args
.global smp_ap_target
.global smp_ap_ready

boot_helper:
  // boot core saves args and jump target for ap cores:
  sd a0, smp_ap_args, t1
  sd a1, smp_ap_args+8, t1
  sd a2, smp_ap_args+16, t1
  sd a3, smp_ap_target, t1
  fence w, w
  // notify application cores to proceed with boot:
  li t0, 1
  sd t0, smp_ap_ready, t1
  // boot core now also ready to boot:
  jr a3
