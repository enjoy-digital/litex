// This file is Copyright (c) 2015 Florent Kermarrec <florent@enjoy-digital.fr>
// License: BSD

#include <time.h>

#include "Vdut.h"
#include "verilated.h"
#include "verilated_vcd_c.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <sys/select.h>
#include <sys/socket.h>
#include <sys/ioctl.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <termios.h>

int trace = 0;

struct termios orig_termios;

void reset_terminal_mode(void)
{
	tcsetattr(0, TCSANOW, &orig_termios);
}

void set_conio_terminal_mode(void)
{
	struct termios new_termios;

	/* take two copies - one for now, one for later */
	tcgetattr(0, &orig_termios);
	memcpy(&new_termios, &orig_termios, sizeof(new_termios));

	/* register cleanup handler, and set the new terminal mode */
	atexit(reset_terminal_mode);
	cfmakeraw(&new_termios);
	tcsetattr(0, TCSANOW, &new_termios);
}

int kbhit(void)
{
	struct timeval tv = { 0L, 0L };
	fd_set fds;
	FD_ZERO(&fds);
	FD_SET(0, &fds);
	return select(1, &fds, NULL, NULL, &tv);
}

int getch(void)
{
	int r;
	unsigned char c;
	if ((r = read(0, &c, sizeof(c))) < 0) {
		return r;
	} else {
		return c;
	}
}

vluint64_t main_time = 0;
double sc_time_stamp()
{
	return main_time;
}

Vdut* dut;
VerilatedVcdC* tfp;

/* ios */

struct sim {
	bool run;

	unsigned int tick;
	clock_t start;
	clock_t end;
};

int console_service(struct sim *s)
{
	/* fpga --> console */
	SERIAL_SOURCE_ACK = 1;
	if(SERIAL_SOURCE_STB == 1) {
		if (SERIAL_SOURCE_DATA == '\n')
			putchar('\r');
		putchar(SERIAL_SOURCE_DATA);
		fflush(stdout);
	}

	/* console --> fpga */
	SERIAL_SINK_STB = 0;
	if (s->tick%(1000) == 0) {
		if(kbhit()) {
			char c = getch();
			if (c == 27 && !kbhit()) {
				printf("\r\n");
				return -1;
			} else {
				SERIAL_SINK_STB = 1;
				SERIAL_SINK_DATA = c;
			}
		}
	}
	return 0;
}

void sim_tick(struct sim *s)
{
	SYS_CLK = s->tick%2;
	dut->eval();
	if (trace)
		tfp->dump(s->tick);
	s->tick++;
}

void sim_init(struct sim *s)
{
	int i;
	s->tick = 0;
#ifdef SYS_RST
	SYS_RST = 1;
	SYS_CLK = 0;
	for (i=0; i<8; i++)
		sim_tick(s);
	SYS_RST = 0;
#endif
	s->start = clock();
}

int main(int argc, char **argv, char **env)
{
	float speed;

	set_conio_terminal_mode();

	Verilated::commandArgs(argc, argv);
	dut = new Vdut;

	Verilated::traceEverOn(true);
	tfp = new VerilatedVcdC;
	dut->trace(tfp, 99);
	tfp->open("dut.vcd");

	struct sim s;
	sim_init(&s);

	s.run = true;
	while(s.run) {
		sim_tick(&s);
		if (SYS_CLK) {
			if (console_service(&s) != 0)
				s.run = false;
		}
	}
	s.end = clock();

	speed = (s.tick/2)/((s.end-s.start)/CLOCKS_PER_SEC);

	printf("average speed: %3.3f MHz\n\r", speed/1000000);

	tfp->close();

	exit(0);
}
