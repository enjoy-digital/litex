// This file is Copyright (c) 2013-2014 Sebastien Bourdeauducq <sb@m-labs.hk>
// This file is Copyright (c) 2014-2019 Florent Kermarrec <florent@enjoy-digital.fr>
// This file is Copyright (c) 2015 Yann Sionneau <ys@m-labs.hk>
// This file is Copyright (c) 2015 whitequark <whitequark@whitequark.org>
// This file is Copyright (c) 2019 Ambroz Bizjak <ambrop7@gmail.com>
// This file is Copyright (c) 2019 Caleb Jamison <cbjamo@gmail.com>
// This file is Copyright (c) 2018 Dolu1990 <charles.papon.90@gmail.com>
// This file is Copyright (c) 2018 Felix Held <felix-github@felixheld.de>
// This file is Copyright (c) 2019 Gabriel L. Somlo <gsomlo@gmail.com>
// This file is Copyright (c) 2018 Jean-François Nguyen <jf@lambdaconcept.fr>
// This file is Copyright (c) 2018 Sergiusz Bazanski <q3k@q3k.org>
// This file is Copyright (c) 2016 Tim 'mithro' Ansell <mithro@mithis.com>
// This file is Copyright (c) 2020 Franck Jullien <franck.jullien@gmail.com>
// This file is Copyright (c) 2020 Antmicro <www.antmicro.com>

// License: BSD

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <system.h>
#include <irq.h>

#include "boot.h"
#include "readline.h"
#include "helpers.h"
#include "command.h"

#include <generated/csr.h>
#include <generated/soc.h>
#include <generated/mem.h>
#include <generated/git.h>

#include <libbase/console.h>
#include <libbase/crc.h>
#include <libbase/memtest.h>

#include <libbase/spiflash.h>
#include <libbase/uart.h>
#include <libbase/i2c.h>

#include <liblitedram/sdram.h>
#include <liblitedram/utils.h>

#include <libliteeth/udp.h>
#include <libliteeth/mdio.h>

#include <liblitespi/spiflash.h>

#include <liblitesdcard/sdcard.h>
#include <liblitesata/sata.h>

#ifndef CONFIG_BIOS_NO_BOOT
static void boot_sequence(void)
{
#ifdef CSR_UART_BASE
	if (serialboot() == 0)
		return;
#endif
	if (target_boot)
		target_boot();
#ifdef FLASH_BOOT_ADDRESS
	flashboot();
#endif
#ifdef ROM_BOOT_ADDRESS
	romboot();
#endif
#if defined(CSR_SPISDCARD_BASE) || defined(CSR_SDCARD_CORE_BASE)
	sdcardboot();
#endif
#if defined(CSR_SATA_SECTOR2MEM_BASE)
	sataboot();
#endif
#ifdef CSR_ETHMAC_BASE
#ifdef CSR_ETHPHY_MODE_DETECTION_MODE_ADDR
	eth_mode();
#endif
	netboot(0, NULL);
#endif
	printf("No boot medium found\n");
}
#endif

__attribute__((__used__)) int main(int i, char **c)
{
#ifndef BIOS_CONSOLE_DISABLE
	char buffer[CMD_LINE_BUFFER_SIZE];
	char *params[MAX_PARAM];
	char *command;
	struct command_struct *cmd;
	int nb_params;
#endif
	int sdr_ok;

#ifdef CONFIG_CPU_HAS_INTERRUPT
	irq_setmask(0);
	irq_setie(1);
#endif
#ifdef CSR_UART_BASE
	uart_init();
#endif

#ifdef CONFIG_HAS_I2C
	i2c_send_init_cmds();
#endif

#ifndef CONFIG_BIOS_NO_PROMPT
	printf("\n");
	printf("\e[1m        __   _ __      _  __\e[0m\n");
	printf("\e[1m       / /  (_) /____ | |/_/\e[0m\n");
	printf("\e[1m      / /__/ / __/ -_)>  <\e[0m\n");
	printf("\e[1m     /____/_/\\__/\\__/_/|_|\e[0m\n");
	printf("\e[1m   Build your hardware, easily!\e[0m\n");
	printf("\n");
	printf(" (c) Copyright 2012-2024 Enjoy-Digital\n");
	printf(" (c) Copyright 2007-2015 M-Labs\n");
	printf("\n");
#ifndef CONFIG_BIOS_NO_BUILD_TIME
	printf(" BIOS built on "__DATE__" "__TIME__"\n");
#endif
#ifndef CONFIG_BIOS_NO_CRC
	crcbios();
#endif
	printf("\n");
	printf(" LiteX git sha1: "LITEX_GIT_SHA1"\n");
	printf("\n");
	printf("--=============== \e[1mSoC\e[0m ==================--\n");
	printf("\e[1mCPU\e[0m:\t\t%s @ %dMHz\n",
		CONFIG_CPU_HUMAN_NAME,
#ifdef CONFIG_CPU_CLK_FREQ
		CONFIG_CPU_CLK_FREQ/1000000);
#else
		CONFIG_CLOCK_FREQUENCY/1000000);
#endif
	printf("\e[1mBUS\e[0m:\t\t%s %d-bit @ %dGiB\n",
		CONFIG_BUS_STANDARD,
		CONFIG_BUS_DATA_WIDTH,
		(1 << (CONFIG_BUS_ADDRESS_WIDTH - 30)));
	printf("\e[1mCSR\e[0m:\t\t%d-bit data\n",
		CONFIG_CSR_DATA_WIDTH);
	printf("\e[1mROM\e[0m:\t\t");
	print_size(ROM_SIZE);
	printf("\n");
	printf("\e[1mSRAM\e[0m:\t\t");
	print_size(SRAM_SIZE);
	printf("\n");
#ifdef CONFIG_L2_SIZE
	printf("\e[1mL2\e[0m:\t\t");
	print_size(CONFIG_L2_SIZE);
	printf("\n");
#endif
#ifdef CSR_SPIFLASH_CORE_BASE
	printf("\e[1mFLASH\e[0m:\t\t");
	print_size(SPIFLASH_MODULE_TOTAL_SIZE);
	printf("\n");
#endif
#ifdef MAIN_RAM_SIZE
#ifdef CSR_SDRAM_BASE
	uint64_t supported_memory = sdram_get_supported_memory();
	printf("\e[1mSDRAM\e[0m:\t\t");
	print_size(supported_memory);
	printf(" %d-bit @ %dMT/s ",
		sdram_get_databits(),
		sdram_get_freq()/1000000);
	printf("(CL-%d",
		sdram_get_cl());
	if (sdram_get_cwl() != -1)
		printf(" CWL-%d", sdram_get_cwl());
	printf(")\n");
#endif
	printf("\e[1mMAIN-RAM\e[0m:\t");
	print_size(MAIN_RAM_SIZE);
	printf("\n");
#endif
	printf("\n");
#endif

        sdr_ok = 1;

#ifdef CSR_HYPERRAM_BASE /* FIXME: Move to libbase/hyperram.h/c? */
    /* Helper Functions */

    printf("HyperRAM init...\n");
    void hyperram_write_reg(uint16_t reg_addr, uint16_t data) {
        /* Write data to the register */
        hyperram_reg_wdata_write(data);
        hyperram_reg_control_write(
            1        << CSR_HYPERRAM_REG_CONTROL_WRITE_OFFSET |
            0        << CSR_HYPERRAM_REG_CONTROL_READ_OFFSET  |
            reg_addr << CSR_HYPERRAM_REG_CONTROL_ADDR_OFFSET
        );
        /* Wait for write to complete */
        while ((hyperram_reg_status_read() & (1 << CSR_HYPERRAM_REG_STATUS_WRITE_DONE_OFFSET)) == 0);
    }

    uint16_t hyperram_read_reg(uint16_t reg_addr) {
        /* Read data from the register */
        hyperram_reg_control_write(
            0        << CSR_HYPERRAM_REG_CONTROL_WRITE_OFFSET |
            1        << CSR_HYPERRAM_REG_CONTROL_READ_OFFSET  |
            reg_addr << CSR_HYPERRAM_REG_CONTROL_ADDR_OFFSET
        );
        /* Wait for read to complete */
        while ((hyperram_reg_status_read() & (1 << CSR_HYPERRAM_REG_STATUS_READ_DONE_OFFSET)) == 0);
        return hyperram_reg_rdata_read();
    }

    /* Configuration and Utility Functions */

    uint16_t hyperram_get_core_latency_setting(uint32_t clk_freq) {
        /* Raw clock latency settings for the HyperRAM core */
        if (clk_freq <=  85000000) return 3; /* 3 Clock Latency */
        if (clk_freq <= 104000000) return 4; /* 4 Clock Latency */
        if (clk_freq <= 133000000) return 5; /* 5 Clock Latency */
        if (clk_freq <= 166000000) return 6; /* 6 Clock Latency */
        if (clk_freq <= 250000000) return 7; /* 7 Clock Latency */
        return 7; /* Default to highest latency for safety */
    }

    uint16_t hyperram_get_chip_latency_setting(uint32_t clk_freq) {
        /* LUT/Translated settings for the HyperRAM chip */
        if (clk_freq <=  85000000) return 0b1110; /* 3 Clock Latency */
        if (clk_freq <= 104000000) return 0b1111; /* 4 Clock Latency */
        if (clk_freq <= 133000000) return 0b0000; /* 5 Clock Latency */
        if (clk_freq <= 166000000) return 0b0001; /* 6 Clock Latency */
        if (clk_freq <= 250000000) return 0b0010; /* 7 Clock Latency */
        return 0b0010; /* Default to highest latency for safety */
    }

    void hyperram_configure_latency(void) {
        uint16_t config_reg_0 = 0x8f2f;
        uint16_t core_latency_setting;
        uint16_t chip_latency_setting;

        /* Compute Latency settings */
        core_latency_setting = hyperram_get_core_latency_setting(CONFIG_CLOCK_FREQUENCY/4);
        chip_latency_setting = hyperram_get_chip_latency_setting(CONFIG_CLOCK_FREQUENCY/4);

        /* Write Latency to HyperRAM Core */
        printf("HyperRAM Core Latency: %d CK (X1).\n", core_latency_setting);
        hyperram_config_write(core_latency_setting << CSR_HYPERRAM_CONFIG_LATENCY_OFFSET);

        /* Enable Variable Latency on HyperRAM Chip */
        if (hyperram_status_read() & 0x1)
            config_reg_0 &= ~(0b1 << 3); /* Enable Variable Latency */

        /* Update Latency on HyperRAM Chip */
        config_reg_0 &= ~(0b1111 << 4);
        config_reg_0 |= chip_latency_setting << 4;

        /* Write Configuration Register 0 to HyperRAM Chip */
        hyperram_write_reg(2, config_reg_0);

        /* Read current configuration */
        config_reg_0 = hyperram_read_reg(2);
        printf("HyperRAM Configuration Register 0: %08x\n", config_reg_0);
    }
    hyperram_configure_latency();
    printf("\n");
#endif

#if defined(CSR_ETHMAC_BASE) || defined(MAIN_RAM_BASE) || defined(CSR_SPIFLASH_CORE_BASE)
    printf("--========== \e[1mInitialization\e[0m ============--\n");
#ifdef CSR_ETHMAC_BASE
	eth_init();
#endif

	/* Initialize and test DRAM */
#ifdef CSR_SDRAM_BASE
	sdr_ok = sdram_init();
#else
	/* Test Main RAM when present and not pre-initialized */
#ifdef MAIN_RAM_BASE
#ifndef CONFIG_MAIN_RAM_INIT
	sdr_ok = memtest((unsigned int *) MAIN_RAM_BASE, min(MAIN_RAM_SIZE, MEMTEST_DATA_SIZE));
	memspeed((unsigned int *) MAIN_RAM_BASE, min(MAIN_RAM_SIZE, MEMTEST_DATA_SIZE), false, 0);
#endif
#endif
#endif
	if (sdr_ok != 1)
		printf("Memory initialization failed\n");
#endif

	/* Initialize and test SPIFLASH */
#ifdef CSR_SPIFLASH_CORE_BASE
	spiflash_init();
#endif
	printf("\n");


	/* Initialize Video Framebuffer FIXME: Move */
#ifdef CSR_VIDEO_FRAMEBUFFER_BASE
	video_framebuffer_vtg_enable_write(0);
	video_framebuffer_dma_enable_write(0);
	video_framebuffer_vtg_enable_write(1);
	video_framebuffer_dma_enable_write(1);
#endif

	/* Execute  initialization functions */
	init_dispatcher();

	/* Execute any target specific initialisation (if linked) */
	if (target_init)
		target_init();

	/* Execute Boot sequence */
#ifndef CONFIG_BIOS_NO_BOOT
	if(sdr_ok) {
		printf("--============== \e[1mBoot\e[0m ==================--\n");
		boot_sequence();
		printf("\n");
	}
#endif

	/* Console */
#ifdef BIOS_CONSOLE_DISABLE
	printf("--======= \e[1mDone (No Console) \e[0m ==========--\n");
#else
	printf("--============= \e[1mConsole\e[0m ================--\n");
#if !defined(BIOS_CONSOLE_LITE) && !defined(BIOS_CONSOLE_NO_HISTORY)
	hist_init();
#endif
	printf("\n%s", PROMPT);
	while(1) {
		readline(buffer, CMD_LINE_BUFFER_SIZE);
		if (buffer[0] != 0) {
			printf("\n");
			nb_params = get_param(buffer, &command, params);
			cmd = command_dispatcher(command, nb_params, params);
			if (!cmd)
				printf("Command not found");
		}
		printf("\n%s", PROMPT);
	}
#endif
	return 0;
}
