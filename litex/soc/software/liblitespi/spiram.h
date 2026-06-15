#ifndef __LITESPI_SPIRAM_H
#define __LITESPI_SPIRAM_H

#ifdef __cplusplus
extern "C" {
#endif

int spiram_freq_init(void);
void spiram_dummy_bits_setup(unsigned int dummy_bits);
void spiram_memspeed(void);
void spiram_init(void);

#ifdef __cplusplus
}
#endif

#endif /* __LITESPI_SPIRAM_H */
