// This file is Copyright (c) 2015 Florent Kermarrec <florent@enjoy-digital.fr>
// License: BSD
#include "Vdut.h"
#include "verilated.h"
#include "verilated_vcd_c.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <fcntl.h>
#include <sys/socket.h>
#include <sys/ioctl.h>
#include <termios.h>
#include <sys/poll.h>

#include <linux/if.h>
#include <linux/if_tun.h>

/* ios */

#ifdef SERIAL_SOURCE_STB
#define WITH_SERIAL
#endif

#ifdef ETH_SOURCE_STB
#define WITH_ETH
#endif

#define MAX(a,b) (((a)>(b))?(a):(b))
#define MIN(a,b) (((a)<(b))?(a):(b))

int trace = 0;

vluint64_t main_time = 0;
double sc_time_stamp()
{
	return main_time;
}

/* Sim struct */
struct sim {
	bool run;

	unsigned int tick;
	clock_t start;
	clock_t end;
	float speed;

#ifndef WITH_SERIAL_PTY
	char rx_serial_stb;
	char rx_serial_data;
	char rx_serial_presented;
#else
	char serial_dev[64];
	int serial_fd;
	unsigned char serial_rx_data;
	unsigned char serial_tx_data;
#endif
#ifdef WITH_ETH
	const char *eth_dev;
	const char *eth_tap;
	int eth_fd;
	unsigned char eth_txbuffer[2048];
	unsigned char eth_rxbuffer[2048];
	int eth_txbuffer_len;
	int eth_rxbuffer_len;
	int eth_rxbuffer_pos;
	int eth_last_source_stb;
#endif
};

/* Serial functions */
#ifndef WITH_SERIAL_PTY
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
#endif

/* Ethernet functions */
/* create tap:
     openvpn --mktun --dev tap0
     ifconfig tap0 192.168.0.14 up
     mknod /dev/net/tap0 c 10 200
   delete tap:
     openvpn --rmtun --dev tap0 */
#ifdef WITH_ETH
void eth_init(struct sim *s, const char *dev, const char*tap)
{
	s->eth_txbuffer_len = 0;
	s->eth_rxbuffer_len = 0;
	s->eth_rxbuffer_pos = 0;
	s->eth_last_source_stb = 0;
	s->eth_dev = dev;
	s->eth_tap = tap;
}

void eth_open(struct sim *s)
{

	struct ifreq ifr;
	s->eth_fd = open (s->eth_dev, O_RDWR);
	if(s->eth_fd < 0) {
		fprintf (stderr, " Could not open dev %s\n", s->eth_dev);
		return;
	}

	memset (&ifr, 0, sizeof(ifr));
	ifr.ifr_flags = IFF_TAP | IFF_NO_PI;
	strncpy (ifr.ifr_name, s->eth_tap, IFNAMSIZ);

	if (ioctl (s->eth_fd, TUNSETIFF, (void *) &ifr) < 0) {
		fprintf (stderr, " Could not set %s\n", s->eth_tap);
		close(s->eth_fd);
	}
	return;
}

int eth_close(struct sim *s)
{
	if (s->eth_fd < 0)
		close(s->eth_fd);
}

void eth_write(struct sim *s, unsigned char *buf, int len)
{
	write(s->eth_fd, buf, len);
}

int eth_read(struct sim *s, unsigned char *buf)
{

	struct pollfd fds[1];
	int n;
	int len;

	fds[0].fd = s->eth_fd;
	fds[0].events = POLLIN;

	n = poll(fds, 1, 0);
	if ((n > 0) && ((fds[0].revents & POLLIN) == POLLIN)) {
		len = read(s->eth_fd, buf, 1532);
	} else {
		len = 0;
	}
	return len;
}
#endif

Vdut* dut;
VerilatedVcdC* tfp;

#ifndef WITH_SERIAL_PTY
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
#else
void console_init(struct sim *s)
{
	FILE *f;
	f = fopen("/tmp/simserial","r");
	fscanf(f, "%[^\n]", s->serial_dev);
	fclose(f);
	return;
}

void console_open(struct sim *s)
{
	s->serial_fd = open(s->serial_dev, O_RDWR);
	if(s->serial_fd < 0) {
		fprintf(stderr, " Could not open dev %s\n", s->serial_dev);
		return;
	}
	return;
}

int console_close(struct sim *s)
{
	if (s->serial_fd < 0)
		close(s->serial_fd);
}

void console_write(struct sim *s, unsigned char *buf, int len)
{
	write(s->serial_fd, buf, len);
}

int console_read(struct sim *s, unsigned char *buf)
{
	struct pollfd fds[1];
	int n;
	int len;

	fds[0].fd = s->serial_fd;
	fds[0].events = POLLIN;

	n = poll(fds, 1, 0);
	if ((n > 0) && ((fds[0].revents & POLLIN) == POLLIN)) {
		len = read(s->serial_fd, buf, 1);
	} else {
		len = 0;
	}
	return len;
}

int console_service(struct sim *s)
{
	/* fpga --> console */
	SERIAL_SOURCE_ACK = 1;
	if(SERIAL_SOURCE_STB == 1) {
		s->serial_tx_data = SERIAL_SOURCE_DATA;
		console_write(s, &(s->serial_tx_data), 1);
	}

	/* console --> fpga */
	SERIAL_SINK_STB = 0;
	if (console_read(s, &(s->serial_rx_data)))
	{
		SERIAL_SINK_STB = 1;
		SERIAL_SINK_DATA = s->serial_rx_data;
	}
	return 0;
}
#endif

#ifdef WITH_ETH
int ethernet_service(struct sim *s) {
	/* fpga --> tap */
	ETH_SOURCE_ACK = 1;
	if(ETH_SOURCE_STB == 1) {
		s->eth_txbuffer[s->eth_txbuffer_len] = ETH_SOURCE_DATA;
		s->eth_txbuffer_len++;
	} else {
		if (s->eth_last_source_stb) {
			eth_write(s, s->eth_txbuffer, s->eth_txbuffer_len);
			s->eth_txbuffer_len = 0;
		}
	}
	s->eth_last_source_stb = ETH_SOURCE_STB;

	/* tap --> fpga */
	if (s->eth_rxbuffer_len == 0) {
		ETH_SINK_STB = 0;
		s->eth_rxbuffer_pos = 0;
		s->eth_rxbuffer_len = eth_read(s, s->eth_rxbuffer);
	} else {
		if (s->eth_rxbuffer_pos < MAX(s->eth_rxbuffer_len, 60)) {
			ETH_SINK_STB = 1;
			ETH_SINK_DATA = s->eth_rxbuffer[s->eth_rxbuffer_pos];
			s->eth_rxbuffer_pos++;
		} else {
			ETH_SINK_STB = 0;
			s->eth_rxbuffer_len = 0;
			memset(s->eth_rxbuffer, 0, 1532);
		}
	}
}
#endif

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

#ifndef WITH_SERIAL_PTY
	set_conio_terminal_mode();
#endif

	Verilated::commandArgs(argc, argv);
	dut = new Vdut;

	Verilated::traceEverOn(true);
	tfp = new VerilatedVcdC;
	dut->trace(tfp, 99);
	tfp->open("dut.vcd");

	struct sim s;
	sim_init(&s);

#ifdef WITH_SERIAL_PTY
	console_init(&s);
	console_open(&s);
#endif

#ifdef WITH_ETH
	eth_init(&s, "/dev/net/tap0", "tap0"); // XXX get this from /tmp/simethernet
	eth_open(&s);
#endif

	s.run = true;
	while(s.run) {
		sim_tick(&s);
		if (SYS_CLK) {
#ifdef WITH_SERIAL
			if (console_service(&s) != 0)
				s.run = false;
#endif
#ifdef WITH_ETH
			ethernet_service(&s);
#endif
		}
	}
	s.end = clock();

	speed = (s.tick/2)/((s.end-s.start)/CLOCKS_PER_SEC);

	printf("average speed: %3.3f MHz\n\r", speed/1000000);

	tfp->close();


#ifdef WITH_SERIAL_PTY
	console_close(&s);
#endif
#ifdef WITH_ETH
	eth_close(&s);
#endif

	exit(0);
}
