#ifndef __FB_H
#define __FB_H

enum {
    FB_MODE_640_480,
    FB_MODE_800_600,
    FB_MODE_1024_768,
    FB_MODE_1920_1080
};

extern int fb_hres, fb_vres;

void fb_set_mode(int mode);
void fb_enable(int en);

#endif /* __FB_H */
