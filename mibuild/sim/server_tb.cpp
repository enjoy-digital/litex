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
#include <sys/types.h>
#include <sys/select.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <sys/un.h>
#include <netdb.h>
#include <pthread.h>

int trace = 0;

vluint64_t main_time = 0;
double sc_time_stamp()
{
	return main_time;
}

Vdut* dut;
VerilatedVcdC* tfp;

/* ios */

#define MAX_LEN 2048

enum {
	MESSAGE_EXIT = 0,
	MESSAGE_ACK,
	MESSAGE_ERROR,
	MESSAGE_UART
};

struct sim {
	int socket;
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

int sim_connect(struct sim *s, const char *sockaddr)
{
	struct sockaddr_un addr;

	s->socket = socket(AF_UNIX, SOCK_SEQPACKET, 0);
	if(s->socket < 0) {
		return -1;
	}

	addr.sun_family = AF_UNIX;
	strcpy(addr.sun_path, sockaddr);
	if(connect(s->socket, (struct sockaddr *)&addr, sizeof(addr)) != 0) {
		close(s->socket);
		return -1;
	}

	return 0;
}

int sim_send(struct sim *s, char *buffer, int len)
{
	send(s->socket, s->txbuffer, len, 0);
	return 0;
}

void sim_receive_process(struct sim *s, char * buffer, int len) {
	int i;
	switch(buffer[0]) {
		case MESSAGE_EXIT:
			s->run = false;
			break;
		case MESSAGE_UART:
			i = 0;
			for(i=0; i<len-1; i++) {
				s->rx_serial_stb = 1;
				s->rx_serial_data = buffer[i+1];
				while (s->rx_serial_presented == 0);
				s->rx_serial_presented = 0;
			}
			s->rx_serial_stb = 0;
			break;
		default:
			break;
	}
}

void *sim_receive(void *s_void)
{
	struct sim *s = (sim *) s_void;
	int rxlen;
	while(1)
	{
		rxlen = recv(s->socket, s->rxbuffer, MAX_LEN, 0);
		if (rxlen > 0)
			sim_receive_process(s, s->rxbuffer, rxlen);
		s->txbuffer[0] = MESSAGE_ACK;
		sim_send(s, s->txbuffer, 1);
	}
}

void sim_destroy(struct sim *s)
{
	close(s->socket);
	free(s);
}

int console_service(struct sim *s)
{
	/* fpga --> console */
	SERIAL_SOURCE_ACK = 1;
	if(SERIAL_SOURCE_STB == 1) {
		s->txbuffer[0] = MESSAGE_UART;
		s->txbuffer[1] = SERIAL_SOURCE_DATA;
		sim_send(s, s->txbuffer, 2);
	}

	/* console --> fpga */
	SERIAL_SINK_STB = s->rx_serial_stb;
	SERIAL_SINK_DATA = s->rx_serial_data;
	if (s->rx_serial_stb)
		s->rx_serial_presented = 1;

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
	Verilated::commandArgs(argc, argv);
	dut = new Vdut;

	Verilated::traceEverOn(true);
	tfp = new VerilatedVcdC;
	dut->trace(tfp, 99);
	tfp->open("dut.vcd");

	struct sim s;
	sim_init(&s);
	sim_connect(&s, "/tmp/simsocket");

	pthread_t sim_receive_thread;

	pthread_create(&sim_receive_thread, NULL, sim_receive, &s);

	s.run = true;
	while(s.run) {
		sim_tick(&s);
		if (SYS_CLK) {
			if (console_service(&s) != 0)
				s.run = false;
		}
	}
	s.end = clock();

	tfp->close();
	pthread_cancel(sim_receive_thread);
	sim_destroy(&s);

	exit(0);
}
