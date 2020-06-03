// SPDX-License-Identifier: BSD-Source-Code

#include <stdio.h>
#include <stdlib.h>

#include <generated/csr.h>

#include "../command.h"
#include "../helpers.h"
#include "../boot.h"

/**
 * Command "flashboot"
 *
 * Boot software from flash
 *
 */
#ifdef FLASH_BOOT_ADDRESS
define_command(flashboot, flashboot, "Boot from Flash", BOOT_CMDS);
#endif

/**
 * Command "romboot"
 *
 * Boot software from embedded rom
 *
 */
#ifdef ROM_BOOT_ADDRESS
define_command(romboot, romboot, "Boot from ROM", BOOT_CMDS);
#endif

/**
 * Command "serialboot"
 *
 * Boot software from serial interface
 *
 */
define_command(serialboot, serialboot, "Boot from Serial (SFL)", BOOT_CMDS);

/**
 * Command "netboot"
 *
 * Boot software from TFTP server
 *
 */
#ifdef CSR_ETHMAC_BASE
define_command(netboot, netboot, "Boot via Ethernet (TFTP)", BOOT_CMDS);
#endif

/**
 * Command "spisdcardboot"
 *
 * Boot software from SDcard
 *
 */
#if defined(CSR_SPISDCARD_BASE) || defined(CSR_SDCORE_BASE)
define_command(sdcardboot, sdcardboot, "Boot from SDCard", BOOT_CMDS);
#endif

