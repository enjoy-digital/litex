/*
 * show_progress.c - simple progress bar functions
 *
 * Copyright (c) 2010 Sascha Hauer <s.hauer@pengutronix.de>, Pengutronix
 *
 * See file CREDITS for list of people who contributed to this
 * project.
 *
 * This program is free software; you can redistribute it and/or modify
 * it under the terms of the GNU General Public License version 2
 * as published by the Free Software Foundation.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 */

#include <console.h>
#include <stdio.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

#include <div64.h>
#include <progress.h>

#include <generated/csr.h>
#include <generated/soc.h>

#define FILESIZE_MAX    100000000
#define HASHES_PER_LINE	40
#define BLOCK_PATTERN_LEN (8 * 4)

static int printed;
static int progress_max;
static int spin;

#ifdef CSR_VIDEO_FRAMEBUFFER_BASE
static void show_progress_fb(int index) {
    int i = 0;
    unsigned char *fb_ptr = (unsigned char *)VIDEO_FRAMEBUFFER_BASE;
    unsigned int fb_offset = 0;
    unsigned int pos_offset = 0;
    unsigned char block_pattern[BLOCK_PATTERN_LEN];

    memset(block_pattern, 0x00, BLOCK_PATTERN_LEN);
    for(i = 0; i < (BLOCK_PATTERN_LEN / 2); i = i + 4) {
        block_pattern[i + 0] = 0x00;
        block_pattern[i + 1] = 0xFF;  // Green
        block_pattern[i + 2] = 0x00;
        block_pattern[i + 3] = 0x00;
    }

    fb_offset = VIDEO_FRAMEBUFFER_HRES * ((VIDEO_FRAMEBUFFER_VRES / 2) - 8) * 4;
    pos_offset = (10 * 4) + index * BLOCK_PATTERN_LEN;
    fb_ptr = fb_ptr + fb_offset + pos_offset;
    for(i = 0; i < 16; i++){
        memcpy(fb_ptr, block_pattern, BLOCK_PATTERN_LEN);
        fb_ptr += (VIDEO_FRAMEBUFFER_HRES * 4);
    }
}
#endif

void show_progress(int now)
{
	char spinchr[] = "\\|/-";

	if (now < 0) {
		printf("%c\b", spinchr[spin++ % (sizeof(spinchr) - 1)]);
		return;
	}

	if (progress_max && progress_max != FILESIZE_MAX) {
		uint64_t tmp = (int64_t)now * HASHES_PER_LINE;
		do_div(tmp, progress_max);
		now = tmp;
	}

	while (printed < now) {
		if (!(printed % HASHES_PER_LINE) && printed)
			printf("\n");
		printf("#");

#ifdef CSR_VIDEO_FRAMEBUFFER_BASE
        show_progress_fb(printed);
#endif

		printed++;
	}
}

void init_progression_bar(int max)
{
	printed = 0;
	progress_max = max;
	spin = 0;
	if (progress_max && progress_max != FILESIZE_MAX)
		printf("[%*s]\r[", HASHES_PER_LINE, "");

#ifdef CSR_VIDEO_FRAMEBUFFER_BASE
	unsigned char *fb_ptr = NULL;
	unsigned int fb_len = 0;
	fb_ptr = (unsigned char *)VIDEO_FRAMEBUFFER_BASE;
	fb_len = VIDEO_FRAMEBUFFER_HRES * VIDEO_FRAMEBUFFER_VRES * 4;
	memset(fb_ptr, 0x00, fb_len);
#endif

}
