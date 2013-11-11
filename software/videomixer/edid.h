#ifndef __EDID_H
#define __EDID_H

#define MAX_MONITOR_NAME_LEN 13

struct video_timing {
	unsigned int pixel_clock; /* in tens of kHz */

	unsigned int h_active;
	unsigned int h_blanking;
	unsigned int h_sync_offset;
	unsigned int h_sync_width;

	unsigned int v_active;
	unsigned int v_blanking;
	unsigned int v_sync_offset;
	unsigned int v_sync_width;

	unsigned int established_timing;
};

int validate_edid(const void *buf);
void get_monitor_name(const void *buf, char *name);
void generate_edid(void *out,
	const char mfg_name[3], const char product_code[2], int year,
	const char *name,
	const struct video_timing *timing);

#endif
