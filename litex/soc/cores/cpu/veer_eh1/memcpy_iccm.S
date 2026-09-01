# ================================================================
# memcpy_iccm.S - SIMPLE ICCM-SAFE memcpy
# NO complex masks, uses shifts only
# ================================================================

#undef _MACHINE_RISCV_MEMCPY_ASM_

.global memcpy
.type memcpy, @function
memcpy:
  mv    t3, a0            # Save original dest pointer
  mv    t0, a0            # Destination pointer (advances)
  mv    t1, a1            # Source pointer
  mv    t2, a2            # Size in bytes

  # Copy full words (4 bytes at a time)
  srli  t4, t2, 2
  beqz  t4, check_tail

loop_word:
  lw    t5, 0(t1)
  sw    t5, 0(t0)
  addi  t1, t1, 4
  addi  t0, t0, 4
  addi  t4, t4, -1
  bnez  t4, loop_word

check_tail:
  andi  t4, t2, 3
  beqz  t4, done_fence

  # Read existing word from destination
  lw    t6, 0(t0)
  lw    t5, 0(t1)
  
  # Handle 3 bytes remaining
  li    t1, 3
  beq   t4, t1, tail_3
  li    t1, 2
  beq   t4, t1, tail_2

tail_1:
  # Keep bytes 1-3 from destination, get byte 0 from source
  andi  t5, t5, 0xFF        # Source byte 0 only
  li    t1, 0xFFFFFF00
  and   t6, t6, t1          # Keep destination bytes 1-3
  or    t6, t6, t5
  j     write_tail

tail_2:
  # Keep bytes 2-3 from destination, get bytes 0-1 from source
  li    t1, 0xFFFF
  and   t5, t5, t1          # Source bytes 0-1 only
  li    t1, 0xFFFF0000
  and   t6, t6, t1          # Keep destination bytes 2-3
  or    t6, t6, t5
  j     write_tail

tail_3:
  # Keep byte 3 from destination, get bytes 0-2 from source
  li    t1, 0xFFFFFF
  and   t5, t5, t1          # Source bytes 0-2 only
  li    t1, 0xFF000000
  and   t6, t6, t1          # Keep destination byte 3
  or    t6, t6, t5

write_tail:
  sw    t6, 0(t0)

done_fence:
  fence
  fence.i

done:
  mv    a0, t3
  ret

.size memcpy, .-memcpy