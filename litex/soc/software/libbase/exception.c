#include <generated/csr.h>
#include <stdio.h>
#include <stdarg.h>

void isr(void);

#ifdef __or1k__

#include <hw/flags.h>

#define EXTERNAL_IRQ 0x8

static void emerg_printf(const char *fmt, ...)
{
	char buf[512];
	va_list args;
	va_start(args, fmt);
	vsnprintf(buf, sizeof(buf), fmt, args);
	va_end(args);

	char *p = buf;
	while(*p) {
		while(uart_txfull_read());
		uart_rxtx_write(*p++);
	}
}

static char emerg_getc()
{
	while(uart_rxempty_read());
	char c = uart_rxtx_read();
	uart_ev_pending_write(UART_EV_RX);
	return c;
}

static const char hex[] = "0123456789abcdef";

static void gdb_send(const char *txbuf)
{
	unsigned char cksum = 0;
	const char *p = txbuf;
	while(*p) cksum += *p++;
	emerg_printf("+$%s#%c%c", txbuf, hex[cksum >> 4], hex[cksum & 0xf]);
}

static void gdb_recv(char *rxbuf, size_t size)
{
	size_t pos = (size_t)-1;
	for(;;) {
		char c = emerg_getc();
		if(c == '$')
			pos = 0;
		else if(c == '#')
			return;
		else if(pos < size - 1) {
			rxbuf[pos++] = c;
			rxbuf[pos] = 0;
		}
	}
}

static void gdb_stub(unsigned long pc, unsigned long sr,
                     unsigned long r1, unsigned long *regs)
{
	gdb_send("S05");

	char buf[385];
	for(;;) {
		gdb_recv(buf, sizeof(buf));

		switch(buf[0]) {
			case '?': {
				snprintf(buf, sizeof(buf), "S05");
				break;
			}

			case 'g': {
				snprintf(buf, sizeof(buf),
				         "%08x%08x%08x%08x%08x%08x%08x%08x%08x%08x%08x%08x%08x%08x%08x%08x"
				         "%08x%08x%08x%08x%08x%08x%08x%08x%08x%08x%08x%08x%08x%08x%08x%08x"
				         "%08x%08x%08x",
				         0,        r1,       regs[2],  regs[3],  regs[4],  regs[5],  regs[6],  regs[7],
				         regs[8],  regs[9],  regs[10], regs[11], regs[12], regs[13], regs[14], regs[15],
				         regs[16], regs[17], regs[18], regs[19], regs[20], regs[21], regs[22], regs[23],
				         regs[24], regs[25], regs[26], regs[27], regs[28], regs[29], regs[30], regs[31],
				         pc-4,     pc,       sr);
				break;
			}

			case 'm': {
				unsigned long addr, len;
				char *endptr = &buf[0];
				addr  = strtoul(endptr + 1, &endptr, 16);
				len   = strtoul(endptr + 1, &endptr, 16);
				unsigned char *ptr = (unsigned char *)addr;
				if(len > sizeof(buf) / 2) len = sizeof(buf) / 2;
				for(size_t i = 0; i < len; i++) {
					buf[i*2  ] = hex[ptr[i] >> 4];
					buf[i*2+1] = hex[ptr[i] & 15];
					buf[i*2+2] = 0;
				}
				break;
			}

			case 'p': {
				unsigned long reg, value;
				char *endptr = &buf[0];
				reg   = strtoul(endptr + 1, &endptr, 16);
				if(reg == 0)
					value = 0;
				else if(reg == 1)
					value = r1;
				else if(reg >= 2 && reg <= 31)
					value = regs[reg];
				else if(reg == 33)
					value = pc;
				else if(reg == 34)
					value = sr;
				else {
					snprintf(buf, sizeof(buf), "E01");
					break;
				}
				snprintf(buf, sizeof(buf), "%08x", value);
				break;
			}

			case 'P': {
				unsigned long reg, value;
				char *endptr = &buf[0];
				reg   = strtoul(endptr + 1, &endptr, 16);
				value = strtoul(endptr + 1, &endptr, 16);
				if(reg == 0)
					/* ignore */;
				else if(reg == 1)
					r1 = value;
				else if(reg >= 2 && reg <= 31)
					regs[reg] = value;
				else if(reg == 33)
					pc = value;
				else if(reg == 34)
					sr = value;
				else {
					snprintf(buf, sizeof(buf), "E01");
					break;
				}
				snprintf(buf, sizeof(buf), "OK");
				break;
			}

			case 'c': {
				if(buf[1] != '\0') {
					snprintf(buf, sizeof(buf), "E01");
					break;
				}
				return;
			}

			default:
				snprintf(buf, sizeof(buf), "");
				break;
		}

		do {
			gdb_send(buf);
		} while(emerg_getc() == '-');
	}
}

void exception_handler(unsigned long vect, unsigned long *regs,
                       unsigned long pc, unsigned long ea, unsigned long sr);
void exception_handler(unsigned long vect, unsigned long *regs,
                       unsigned long pc, unsigned long ea, unsigned long sr)
{
	if(vect == EXTERNAL_IRQ) {
		isr();
	} else {
		emerg_printf("\n *** Unhandled exception %d *** \n", vect);
		emerg_printf("   pc  %08x sr  %08x ea  %08x\n",
		             pc, sr, ea);
		unsigned long r1 = (unsigned long)regs + 4*32;
		regs -= 2;
		emerg_printf("   r0  %08x r1  %08x r2  %08x r3  %08x\n",
		             0, r1, regs[2], regs[3]);
		emerg_printf("   r4  %08x r5  %08x r6  %08x r7  %08x\n",
		             regs[4], regs[5], regs[6], regs[7]);
		emerg_printf("   r8  %08x r9  %08x r10 %08x r11 %08x\n",
		             regs[8], regs[9], regs[10], regs[11]);
		emerg_printf("   r12 %08x r13 %08x r14 %08x r15 %08x\n",
		             regs[12], regs[13], regs[14], regs[15]);
		emerg_printf("   r16 %08x r17 %08x r18 %08x r19 %08x\n",
		             regs[16], regs[17], regs[18], regs[19]);
		emerg_printf("   r20 %08x r21 %08x r22 %08x r23 %08x\n",
		             regs[20], regs[21], regs[22], regs[23]);
		emerg_printf("   r24 %08x r25 %08x r26 %08x r27 %08x\n",
		             regs[24], regs[25], regs[26], regs[27]);
		emerg_printf("   r28 %08x r29 %08x r30 %08x r31 %08x\n",
		             regs[28], regs[29], regs[30], regs[31]);
		emerg_printf(" stack:\n");
		unsigned long *sp = (unsigned long *)r1;
		for(unsigned long spoff = 0; spoff < 16; spoff += 4) {
			emerg_printf("   %08x:", &sp[spoff]);
			for(unsigned long spoff2 = 0; spoff2 < 4; spoff2++) {
				emerg_printf(" %08x", sp[spoff + spoff2]);
			}
			emerg_printf("\n");
		}
		emerg_printf(" waiting for gdb... ");
		gdb_stub(pc, sr, r1, regs);
	}
}
#endif
