# bios: Fix bugs/robustness issues and improve usability (review fixes)

This PR is the result of a systematic review of the LiteX BIOS (`litex/soc/software/bios/` and the libbase/libliteeth/liblitesdcard/liblitesata/liblitespi code on its boot path) for bugs, robustness issues and usability problems. 31 commits, one fix per commit.

## Memory safety / correctness

- **readline**: fix a 1-byte stack overflow in the escape-sequence parser, reachable from ordinary keystrokes (Ctrl+Delete/Shift+Delete), and stop unrecognized keys (F1-F12, Ctrl+arrows) from acting as backspace (`read_key()`'s -1 truncated to DEL through an `unsigned char`).
- **complete**: fix the common-prefix computation when one command name is a strict prefix of another, and the completion column layout.
- **boot**: accept load regions ending exactly at the top of the address space (`base + size` wrapping to 0 rejected the whole region, e.g. `MAIN_RAM_BASE=0xC0000000` + 1GB).
- Build fixes: `sataboot_from_bin()` missing its `MAIN_RAM_BASE` guard, `sim_finish()` using `n_markers` without `CSR_SIM_MARKER_BASE`.

## Boot reliability

- **serialboot**: reload the SFL frame timeout on every received byte (a whole frame had to fit in 0.25s, breaking serialboot at low baudrates).
- **netboot/TFTP**: fix transfers > 64MB (16-bit block-number wrap), parse the OACK blksize instead of assuming the request was granted (a server without option support silently returned a 512-byte truncated image as *success*), and print TFTP server error messages.
- **boot.json**: abort instead of half-booting when an entry cannot be parsed (e.g. jumping to a kernel with its device tree silently skipped); raise the name/token limits and report "too many entries" explicitly.
- **flashboot**: single CRC pass instead of two over (slow, often XIP) flash; image size cap tied to `MAIN_RAM_SIZE` instead of a hardcoded 16MiB; fix `uint32_t` printed with `%lx`/`%ld` (garbage on 64-bit CPUs).
- Report `f_mount` failures everywhere instead of failing silently.

## Hang elimination & storage correctness

- **litesdcard**: bound the six infinite command-retry loops and the DMA-done waits (a removed/failing card hard-hung the BIOS); propagate read/write errors through `sd_disk_read` to FatFs instead of handing it stale buffers; support standard-capacity ver2 cards (CCS bit was never checked, so SDSC cards were byte- vs block-address mis-addressed); fix an unmasked SPI status wait that hangs with `aligned`-mode SPIMaster.
- **litesata**: move the bounded retry/timeout logic (previously private to `sata_rwtest`) into `sata_read()`/`sata_write()` so no SATA command can hang the console; propagate errors to FatFs and the commands.
- **liteeth/udp**: fix `ip_checksum()` dropping the last byte of odd-length buffers (bad ICMP checksums).
- **libbase/memtest**: `memtest_addr` never ran with default build options (silently passing) and wrote out of bounds when enabled; `mem_test` without a size defaulted to write-testing ~4GiB over the BIOS stack.
- **libbase/uart**: service the UART manually when interrupts are disabled (panic `printf` output was silently truncated, reads returned NUL).
- **libbase/i2c + soc/cores/bitbang**: support I2C clock stretching - adds an SCL readback field to the I2CMaster status CSR (backward-compatible layout) and a bounded SCL-high wait in the bit-banged driver.

## Usability

- 128-char command line; tab-completion over all registered commands (was capped at 10 of ~70); optional boot.json filename for `sdcardboot`/`sataboot`; netboot progress marks; console polish (whitespace-only lines, Ctrl-L clear screen, warning when arguments beyond `MAX_PARAM` are dropped, escape filtering in the lite console); `sdcard_read [count]`; clarified help strings (`mem_copy`/`mem_cmp` word units, `sata_rwtest` memory/disk footprint); error checking on flash writes with a hint at `flash_erase_range`.

## Verification

- BIOS builds verified with `litex_sim` (featured config with ethernet+sdcard+spiflash, and `--cpu-type=serv` for the minimal/no-IRQ configuration).
- Python unit tests pass (`test_bitbang.py`, `test_export.py`, `test_i2c.py` for the gateware/export change).
- End-to-end Verilator run: BIOS boots to the `litex>` prompt; `ident`, `mem_read`, `mem_test` default size and whitespace-line handling exercised live at the console.

**Note**: the SD/SATA hardware paths compile and are logic-reviewed, but were only exercised as far as simulation allows - a quick smoke test on real hardware with a card/disk is recommended before merging.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
