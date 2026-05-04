#include "wishbone_burst_benchmark.h"

#include <stdio.h>

#include <generated/csr.h>

#include <libbase/memtest.h>

#include "sim_debug.h"

#define wb_burst_monitor_clear(prefix) prefix##_control_write(1)
#define wb_burst_monitor_freeze(prefix) prefix##_control_write(2)
#define wb_burst_monitor_unfreeze(prefix) prefix##_control_write(0)

#define wb_burst_monitor_dump(name, prefix) do { \
	printf("wishbone_burst_monitor %s", name); \
	printf(" cycles=%lu",              (unsigned long)prefix##_cycles_read()); \
	printf(" beats=%lu",               (unsigned long)prefix##_beats_read()); \
	printf(" read_beats=%lu",          (unsigned long)prefix##_read_beats_read()); \
	printf(" write_beats=%lu",         (unsigned long)prefix##_write_beats_read()); \
	printf(" cti_none=%lu",            (unsigned long)prefix##_cti_none_beats_read()); \
	printf(" cti_constant=%lu",        (unsigned long)prefix##_cti_constant_beats_read()); \
	printf(" cti_increment=%lu",       (unsigned long)prefix##_cti_increment_beats_read()); \
	printf(" cti_end=%lu",             (unsigned long)prefix##_cti_end_beats_read()); \
	printf(" burst_count=%lu",         (unsigned long)prefix##_burst_count_read()); \
	printf(" burst_beats=%lu",         (unsigned long)prefix##_burst_beats_read()); \
	printf(" max_burst_beats=%lu",     (unsigned long)prefix##_max_burst_beats_read()); \
	printf(" orphan_end=%lu",          (unsigned long)prefix##_orphan_end_count_read()); \
	printf(" unsupported_bte=%lu\n",   (unsigned long)prefix##_unsupported_bte_read()); \
} while (0)

static void wishbone_burst_monitors_clear(void)
{
#ifdef CSR_WISHBONE_BURST_MONITOR_IBUS_BASE
	wb_burst_monitor_clear(wishbone_burst_monitor_ibus);
#endif
#ifdef CSR_WISHBONE_BURST_MONITOR_DBUS_BASE
	wb_burst_monitor_clear(wishbone_burst_monitor_dbus);
#endif
#ifdef CSR_WISHBONE_BURST_MONITOR_IDBUS_BASE
	wb_burst_monitor_clear(wishbone_burst_monitor_idbus);
#endif
#ifdef CSR_WISHBONE_BURST_MONITOR_PBUS_BASE
	wb_burst_monitor_clear(wishbone_burst_monitor_pbus);
#endif
#ifdef CSR_WISHBONE_BURST_MONITOR_MAIN_RAM_BASE
	wb_burst_monitor_clear(wishbone_burst_monitor_main_ram);
#endif
#ifdef CSR_WISHBONE_BURST_MONITOR_L2_SLAVE_BASE
	wb_burst_monitor_clear(wishbone_burst_monitor_l2_slave);
#endif
}

static void wishbone_burst_monitors_freeze(void)
{
#ifdef CSR_WISHBONE_BURST_MONITOR_IBUS_BASE
	wb_burst_monitor_freeze(wishbone_burst_monitor_ibus);
#endif
#ifdef CSR_WISHBONE_BURST_MONITOR_DBUS_BASE
	wb_burst_monitor_freeze(wishbone_burst_monitor_dbus);
#endif
#ifdef CSR_WISHBONE_BURST_MONITOR_IDBUS_BASE
	wb_burst_monitor_freeze(wishbone_burst_monitor_idbus);
#endif
#ifdef CSR_WISHBONE_BURST_MONITOR_PBUS_BASE
	wb_burst_monitor_freeze(wishbone_burst_monitor_pbus);
#endif
#ifdef CSR_WISHBONE_BURST_MONITOR_MAIN_RAM_BASE
	wb_burst_monitor_freeze(wishbone_burst_monitor_main_ram);
#endif
#ifdef CSR_WISHBONE_BURST_MONITOR_L2_SLAVE_BASE
	wb_burst_monitor_freeze(wishbone_burst_monitor_l2_slave);
#endif
}

static void wishbone_burst_monitors_unfreeze(void)
{
#ifdef CSR_WISHBONE_BURST_MONITOR_IBUS_BASE
	wb_burst_monitor_unfreeze(wishbone_burst_monitor_ibus);
#endif
#ifdef CSR_WISHBONE_BURST_MONITOR_DBUS_BASE
	wb_burst_monitor_unfreeze(wishbone_burst_monitor_dbus);
#endif
#ifdef CSR_WISHBONE_BURST_MONITOR_IDBUS_BASE
	wb_burst_monitor_unfreeze(wishbone_burst_monitor_idbus);
#endif
#ifdef CSR_WISHBONE_BURST_MONITOR_PBUS_BASE
	wb_burst_monitor_unfreeze(wishbone_burst_monitor_pbus);
#endif
#ifdef CSR_WISHBONE_BURST_MONITOR_MAIN_RAM_BASE
	wb_burst_monitor_unfreeze(wishbone_burst_monitor_main_ram);
#endif
#ifdef CSR_WISHBONE_BURST_MONITOR_L2_SLAVE_BASE
	wb_burst_monitor_unfreeze(wishbone_burst_monitor_l2_slave);
#endif
}

static void wishbone_burst_monitors_dump(void)
{
#ifdef CSR_WISHBONE_BURST_MONITOR_IBUS_BASE
	wb_burst_monitor_dump("ibus", wishbone_burst_monitor_ibus);
#endif
#ifdef CSR_WISHBONE_BURST_MONITOR_DBUS_BASE
	wb_burst_monitor_dump("dbus", wishbone_burst_monitor_dbus);
#endif
#ifdef CSR_WISHBONE_BURST_MONITOR_IDBUS_BASE
	wb_burst_monitor_dump("idbus", wishbone_burst_monitor_idbus);
#endif
#ifdef CSR_WISHBONE_BURST_MONITOR_PBUS_BASE
	wb_burst_monitor_dump("pbus", wishbone_burst_monitor_pbus);
#endif
#ifdef CSR_WISHBONE_BURST_MONITOR_MAIN_RAM_BASE
	wb_burst_monitor_dump("main_ram", wishbone_burst_monitor_main_ram);
#endif
#ifdef CSR_WISHBONE_BURST_MONITOR_L2_SLAVE_BASE
	wb_burst_monitor_dump("l2_slave", wishbone_burst_monitor_l2_slave);
#endif
#if !defined(CSR_WISHBONE_BURST_MONITOR_IBUS_BASE) && \
	!defined(CSR_WISHBONE_BURST_MONITOR_DBUS_BASE) && \
	!defined(CSR_WISHBONE_BURST_MONITOR_IDBUS_BASE) && \
	!defined(CSR_WISHBONE_BURST_MONITOR_PBUS_BASE) && \
	!defined(CSR_WISHBONE_BURST_MONITOR_MAIN_RAM_BASE) && \
	!defined(CSR_WISHBONE_BURST_MONITOR_L2_SLAVE_BASE)
	printf("wishbone_burst_monitor none\n");
#endif
}

void wishbone_burst_benchmark(unsigned int *addr, unsigned long size, bool read_only, bool random, bool finish)
{
	printf("--====== Wishbone Burst Benchmark ======--\n");
	printf("Benchmark address: %p\n", addr);
	printf("Benchmark size: %lu bytes\n", size);
	printf("Benchmark read_only: %u\n", read_only ? 1 : 0);
	printf("Benchmark random: %u\n", random ? 1 : 0);

	wishbone_burst_monitors_clear();
	memspeed(addr, size, read_only, random);
	wishbone_burst_monitors_freeze();
	wishbone_burst_monitors_dump();
	wishbone_burst_monitors_unfreeze();

	if (finish)
		sim_finish();
}
