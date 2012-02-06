/*
 * Milkymist SoC (Software)
 * Copyright (C) 2007, 2008, 2009, 2012 Sebastien Bourdeauducq
 *
 * This program is free software: you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation, version 3 of the License.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program.  If not, see <http://www.gnu.org/licenses/>.
 */

#include <irq.h>
#include <uart.h>
#include <hw/sysctl.h>

#include <system.h>

void flush_cpu_icache(void)
{
	asm volatile(
		"wcsr ICC, r0\n"
		"nop\n"
		"nop\n"
		"nop\n"
		"nop\n"
	);
}

void flush_cpu_dcache(void)
{
	asm volatile(
		"wcsr DCC, r0\n"
		"nop\n"
	);
}

__attribute__((noreturn)) void reboot(void)
{
	uart_sync();
	irq_setmask(0);
	irq_setie(0);
	CSR_SYSTEM_ID = 1; /* Writing to CSR_SYSTEM_ID causes a system reset */
	while(1);
}

static void icap_write(int val, unsigned int w)
{
	while(!(CSR_ICAP & ICAP_READY));
	if(!val)
		w |= ICAP_CE|ICAP_WRITE;
	CSR_ICAP = w;
}

__attribute__((noreturn)) void reconf(void)
{
	uart_sync();
	irq_setmask(0);
	irq_setie(0);
	icap_write(0, 0xffff); /* dummy word */
	icap_write(0, 0xffff); /* dummy word */
	icap_write(0, 0xffff); /* dummy word */
	icap_write(0, 0xffff); /* dummy word */
	icap_write(1, 0xaa99); /* sync word part 1 */
	icap_write(1, 0x5566); /* sync word part 2 */
	icap_write(1, 0x30a1); /* write to command register */
	icap_write(1, 0x0000); /* null command */
	icap_write(1, 0x30a1); /* write to command register */
	icap_write(1, 0x000e); /* reboot command */
	icap_write(1, 0x2000); /* NOP */
	icap_write(1, 0x2000); /* NOP */
	icap_write(1, 0x2000); /* NOP */
	icap_write(1, 0x2000); /* NOP */
	icap_write(0, 0x1111); /* NULL */
	icap_write(0, 0xffff); /* dummy word */
	while(1);
}
