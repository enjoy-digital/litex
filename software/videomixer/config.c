#include <stdio.h>
#include <string.h>
#include <generated/mem.h>

#include "config.h"

#define FLASH_BLOCK_SIZE	(128*1024)
#define FLASH_OFFSET_CONFIG (FLASH_BOOT_ADDRESS + FLASH_BLOCK_SIZE)

static volatile unsigned short *flash_config = (unsigned short *)(0x80000000 | FLASH_OFFSET_CONFIG);

static void wait_program(void)
{
	while(!(*flash_config & 0x0080)); /* Read status register */
	*flash_config = 0x0050; /* Clear status register */
	*flash_config = 0x00ff; /* Go to Read Array mode */
}

static void config_erase_block(void)
{
	*flash_config = 0x0020; /* Setup Erase */
	*flash_config = 0x00d0; /* Confirm Erase */
	wait_program();
}

static void config_write(int offset, unsigned short data)
{
	flash_config[offset] = 0x0040; /* Word Program */
	flash_config[offset] = data;
	wait_program();
}

static const unsigned char config_defaults[CONFIG_KEY_COUNT] = CONFIG_DEFAULTS;
static int config_record_count;
static unsigned char config_values[CONFIG_KEY_COUNT];

static int config_process_record(unsigned char key, unsigned char value)
{
	if(key >= CONFIG_KEY_COUNT)
		return 0;
	config_record_count++;
	config_values[key] = value;
	return 1;
}

void config_init(void)
{
	volatile unsigned int *flash_config32 = (unsigned int *)flash_config;
	int i;
	unsigned int flash_word;

	memcpy(config_values, config_defaults, CONFIG_KEY_COUNT);

	for(i=0;i<FLASH_BLOCK_SIZE/4;i++) {
		flash_word = flash_config32[i];
		if(!config_process_record((flash_word >> 24) & 0xff, (flash_word >> 16) & 0xff))
			break;
		if(!config_process_record((flash_word >> 8) & 0xff, flash_word & 0xff))
			break;
	}
}

void config_write_all(void)
{
	int i;

	config_erase_block();
	config_record_count = 0;
	for(i=0;i<CONFIG_KEY_COUNT;i++) {
		if(config_values[i] != config_defaults[i]) {
			config_write(config_record_count, (i << 8) | config_values[i]);
			config_record_count++;
		}
	}
}

unsigned char config_get(unsigned char key)
{
	return config_values[key];
}

void config_set(unsigned char key, unsigned char value)
{
	if(config_values[key] == value)
		return;
	config_values[key] = value;
	if(config_record_count < FLASH_BLOCK_SIZE/2)
		config_write(config_record_count++, (key << 8) | value);
	else
		config_write_all();
}
