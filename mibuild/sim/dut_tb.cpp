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

#define MAX(a,b) (((a)>(b))?(a):(b))
#define MIN(a,b) (((a)<(b))?(a):(b))

int trace = 0;

vluint64_t main_time = 0;
double sc_time_stamp()
{
	return main_time;
}

/* ios */

/* Terminal functions */
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

/* Ethernet functions */
/* create tap:
     openvpn --mktun --dev tap0
     ifconfig tap0 192.168.0.14 up
     mknod /dev/net/tap0 c 10 200
   delete tap:
     openvpn --rmtun --dev tap0 */
#ifdef ETH_SOURCE_STB
unsigned char eth_txbuffer[1532];
unsigned char eth_rxbuffer[1532];
int eth_txbuffer_len = 0;
int eth_rxbuffer_len = 0;
int eth_rxbuffer_pos = 0;

struct eth_device
{
	char *dev;
	char *tap;
	int fd;
};

void eth_open(struct eth_device *eth)
{

	struct ifreq ifr;
	eth->fd = open (eth->dev, O_RDWR);
	if(eth->fd < 0) {
		fprintf (stderr, " Could not open dev %s\n", eth->dev);
		return;
	}

	memset (&ifr, 0, sizeof(ifr));
	ifr.ifr_flags = IFF_TAP | IFF_NO_PI;
	strncpy (ifr.ifr_name, eth->tap, IFNAMSIZ);

	if (ioctl (eth->fd, TUNSETIFF, (void *) &ifr) < 0) {
		fprintf (stderr, " Could not set %s\n", eth->tap);
		close(eth->fd);
	}
	return;
}

int eth_close(struct eth_device *eth)
{
	if (eth->fd < 0)
		close(eth->fd);
}

void eth_write_tap(
	struct eth_device *eth,
	unsigned char *buf,
	unsigned long int length)
{
	write (eth->fd, buf, length);
}

int eth_read_tap (
	struct eth_device *eth,
	unsigned char *buf)
{

	struct pollfd fds[1];
	int n;
	int length;

	fds[0].fd = eth->fd;
	fds[0].events = POLLIN;

	n = poll(fds, 1, 0);
	if ((n > 0) && ((fds[0].revents & POLLIN) == POLLIN)) {
		length = read(eth->fd, buf, 1532);
	} else {
		length = 0;
	}
	return length;
}
#endif

Vdut* dut;
VerilatedVcdC* tfp;

#define MAX_LEN 2048

struct sim {
	bool run;

	unsigned int tick;
	clock_t start;
	clock_t end;
	float speed;

	char txbuffer[MAX_LEN];
	char rxbuffer[MAX_LEN];

	char rx_serial_stb;
	char rx_serial_data;
	char rx_serial_presented;
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

#ifdef ETH_SOURCE_STB
int eth_last_source_stb = 0;

int ethernet_service(struct eth_device *eth) {
	/* fpga --> tap */
	ETH_SOURCE_ACK = 1;
	if(ETH_SOURCE_STB == 1) {
		eth_txbuffer[eth_txbuffer_len] = ETH_SOURCE_DATA;
		eth_txbuffer_len++;
	} else {
		if (eth_last_source_stb) {
			eth_write_tap(eth, eth_txbuffer, eth_txbuffer_len-1); // XXX FIXME software or gateware?
			eth_txbuffer_len = 0;
		}
	}
	eth_last_source_stb = ETH_SOURCE_STB;

	/* tap --> fpga */
	if (eth_rxbuffer_len == 0) {
		ETH_SINK_STB = 0;
		eth_rxbuffer_pos = 0;
		eth_rxbuffer_len = eth_read_tap(eth, eth_rxbuffer);
	} else {
		if (eth_rxbuffer_pos < MAX(eth_rxbuffer_len, 60)) {
			ETH_SINK_STB = 1;
			ETH_SINK_DATA = eth_rxbuffer[eth_rxbuffer_pos];
			eth_rxbuffer_pos++;
		} else {
			ETH_SINK_STB = 0;
			eth_rxbuffer_len = 0;
			memset(eth_rxbuffer, 0, 1532);
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

	set_conio_terminal_mode();

	Verilated::commandArgs(argc, argv);
	dut = new Vdut;

	Verilated::traceEverOn(true);
	tfp = new VerilatedVcdC;
	dut->trace(tfp, 99);
	tfp->open("dut.vcd");

	struct sim s;
	sim_init(&s);

#ifdef ETH_SOURCE_STB
	struct eth_device eth;
	char dev[] = "/dev/net/tap0";
	char tap[] = "tap0";
	eth.dev = dev;
	eth.tap = tap;
	eth_open(&eth);
#endif

	s.run = true;
	while(s.run) {
		sim_tick(&s);
		if (SYS_CLK) {
			if (console_service(&s) != 0)
				s.run = false;
#ifdef ETH_SOURCE_STB
			ethernet_service(&eth);
#endif
		}
	}
	s.end = clock();

	speed = (s.tick/2)/((s.end-s.start)/CLOCKS_PER_SEC);

	printf("average speed: %3.3f MHz\n\r", speed/1000000);


	tfp->close();

	exit(0);
}
