// SPDX-License-Identifier: BSD-2-Clause

#ifndef __SDCARD_DMA_H
#define __SDCARD_DMA_H

#include <generated/csr.h>
#include <generated/mem.h>
#include <generated/soc.h>

/* Diagnostic workaround for litesdcard#59: keep receive DMA away from BIOS
 * SRAM on VexiiRiscv with coherent DMA. The BIOS loader reserves this scratch
 * area until handoff; no reservation is needed by the booted application.
 * Define SDCARD_DMA_BOUNCE=0 to compare against the original path. */
#ifndef SDCARD_DMA_BOUNCE
#if defined(CSR_SDCARD_BLOCK2MEM_DMA_BASE_ADDR) && \
    defined(CONFIG_CPU_TYPE_VEXIIRISCV) && defined(CONFIG_CPU_HAS_DMA_BUS) && \
    defined(MAIN_RAM_BASE) && defined(MAIN_RAM_SIZE)
#define SDCARD_DMA_BOUNCE 1
#else
#define SDCARD_DMA_BOUNCE 0
#endif
#endif

#if SDCARD_DMA_BOUNCE
#define SDCARD_DMA_BUFFER_SIZE 512
#define SDCARD_DMA_BUFFER_OFFSET ((MAIN_RAM_SIZE - SDCARD_DMA_BUFFER_SIZE) & ~63UL)
#define SDCARD_DMA_BUFFER_BASE (MAIN_RAM_BASE + SDCARD_DMA_BUFFER_OFFSET)
#ifdef MAIN_RAM_BASE_VA
#define SDCARD_DMA_BUFFER_BASE_VA (MAIN_RAM_BASE_VA + SDCARD_DMA_BUFFER_OFFSET)
#else
#define SDCARD_DMA_BUFFER_BASE_VA SDCARD_DMA_BUFFER_BASE
#endif
#endif

#endif /* __SDCARD_DMA_H */
