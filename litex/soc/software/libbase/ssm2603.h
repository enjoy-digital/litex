// SPDX-License-Identifier: BSD-2-Clause

#ifndef __SSM2603_H
#define __SSM2603_H

#ifdef __cplusplus
extern "C" {
#endif

#include <stdbool.h>

/* SSM2603 Registers */
#define SSM2603_LEFT_ADC_VOLUME_REG  0x0 /* Left-Channel ADC Input Volume  */
#define SSM2603_RIGHT_ADC_VOLUME_REG 0x1 /* Right-Channel ADC Input Volume */
#define SSM2603_LEFT_DAC_VOLUME_REG  0x2 /* Left-Channel DAC Volume        */
#define SSM2603_RIGHT_DAC_VOLUME_REG 0x3 /* Right-Channel DAC Volume       */
#define SSM2603_ANALOG_PATH_REG      0x4 /* Analog Audio Path              */
#define SSM2603_DIGITAL_PATH_REG     0x5 /* Digital Audio Path             */
#define SSM2603_POWER_REG            0x6 /* Power Management               */
#define SSM2603_INTERFACE_REG        0x7 /* Digital Audio I/F              */
#define SSM2603_SAMPLING_REG         0x8 /* Sampling Rate                  */
#define SSM2603_ACTIVE_REG           0x9 /* Active                         */

/* DAC Volume Register Fields/Values */
#define SSM2603_DAC_VOLUME_BOTH      0x100 /* Apply the gain to both channels */
#define SSM2603_DAC_VOLUME_0DB       0x79  /* 0 dB, 1 dB steps                */
#define SSM2603_DAC_VOLUME_MIN_DB    -73
#define SSM2603_DAC_VOLUME_MAX_DB    6

/* Digital Audio Path Register Fields */
#define SSM2603_DIGITAL_PATH_DACMU   0x008 /* DAC soft mute */

bool ssm2603_init(void);
bool ssm2603_restart(void);
bool ssm2603_set_volume(int db);
bool ssm2603_set_mute(bool mute);

#ifdef __cplusplus
}
#endif

#endif /* __SSM2603_H */
