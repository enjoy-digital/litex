#include <stdio.h>

#include <hw/csr.h>
#include <hw/flags.h>

#include "fb.h"

int fb_hres = 640;
int fb_vres = 480;

static void fb_clkgen_write(int cmd, int data)
{
	int word;

	word = (data << 2) | cmd;
	crg_cmd_data_write(word);
	crg_send_cmd_data_write(1);
	while(crg_status_read() & CLKGEN_STATUS_BUSY);
}

void fb_set_mode(int mode)
{
	int clock_m, clock_d;

	switch(mode) {
		default:
		case FB_MODE_640_480: // Pixel clock: 25MHz
			fb_hres = 640;
			fb_vres = 480;
			clock_m = 2;
			clock_d = 4;
			fb_fi_hres_write(640);
			fb_fi_hsync_start_write(656);
			fb_fi_hsync_end_write(752);
			fb_fi_hscan_write(800);
			fb_fi_vres_write(480);
			fb_fi_vsync_start_write(492);
			fb_fi_vsync_end_write(494);
			fb_fi_vscan_write(525);
			break;
		case FB_MODE_800_600: // Pixel clock: 50MHz
			fb_hres = 800;
			fb_vres = 600;
			clock_m = 2;
			clock_d = 2;
			fb_fi_hres_write(800);
			fb_fi_hsync_start_write(848);
			fb_fi_hsync_end_write(976);
			fb_fi_hscan_write(1040);
			fb_fi_vres_write(600);
			fb_fi_vsync_start_write(636);
			fb_fi_vsync_end_write(642);
			fb_fi_vscan_write(665);
			break;
		case FB_MODE_1024_768: // Pixel clock: 65MHz
			fb_hres = 1024;
			fb_vres = 768;
			clock_m = 13;
			clock_d = 10;
			fb_fi_hres_write(1024);
			fb_fi_hsync_start_write(1048);
			fb_fi_hsync_end_write(1184);
			fb_fi_hscan_write(1344);
			fb_fi_vres_write(768);
			fb_fi_vsync_start_write(772);
			fb_fi_vsync_end_write(778);
			fb_fi_vscan_write(807);
			break;
		case FB_MODE_1920_1080: // Pixel clock: 148MHz
			fb_hres = 1920;
			fb_vres = 1080;
			clock_m = 74;
			clock_d = 25;
			fb_fi_hres_write(1920);
			fb_fi_hsync_start_write(2008);
			fb_fi_hsync_end_write(2052);
			fb_fi_hscan_write(2200);
			fb_fi_vres_write(1080);
			fb_fi_vsync_start_write(1084);
			fb_fi_vsync_end_write(1089);
			fb_fi_vscan_write(1125);
			break;
	}
	fb_dma0_length_write(fb_hres*fb_vres*4);
	fb_dma1_length_write(fb_hres*fb_vres*4);

	fb_clkgen_write(0x1, clock_d-1);
	fb_clkgen_write(0x3, clock_m-1);
	crg_send_go_write(1);
	printf("waiting for PROGDONE...");
	while(!(crg_status_read() & CLKGEN_STATUS_PROGDONE));
	printf("ok\n");
	printf("waiting for LOCKED...");
	while(!(crg_status_read() & CLKGEN_STATUS_LOCKED));
	printf("ok\n");

	printf("VGA: mode set to %dx%d\n", fb_hres, fb_vres);
}

void fb_enable(int en)
{
	fb_enable_write(!!en);
}
