#ifndef __PROCESSOR_H
#define __PROCESSOR_H

#define PROCESSOR_MODE_COUNT 4
#define PROCESSOR_MODE_DESCLEN 32

void processor_list_modes(char *mode_descriptors);
void processor_start(int mode);
void processor_service(void);

#endif /* __VIDEOMODE_H */
