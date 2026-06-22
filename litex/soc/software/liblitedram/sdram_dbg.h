#ifndef __SDRAM_DBG_H
#define __SDRAM_DBG_H

#ifdef __cplusplus
extern "C" {
#endif

#include <generated/csr.h>

#ifdef CSR_SDRAM_BASE

#include <generated/sdram_phy.h>

struct memory_error {
	unsigned int addr;
	unsigned int data;
	unsigned int ref;
};

/* Provides error statictics per phase/edge/dq */
struct error_stats {
	struct {
		struct {
			unsigned int dq[SDRAM_PHY_DATABITS];
		} edge[SDRAM_PHY_XDR];
	} phase[SDRAM_PHY_PHASES];
};

void error_stats_init(struct error_stats *stats);
void error_stats_update(struct error_stats *stats, struct memory_error error);
void error_stats_print(struct error_stats *stats);

/* Allows to store memory error information to compare several readbacks from memory.
 *
 * To achieve sensible results we need to store a lot of data, and we cannot use DRAM
 * for that purpose (because we are debugging DRAM issues). This structure should be
 * mapped to some memory region available in the SoC, ideally the SoC has some other
 * memory that can be used, e.g. HyperRAM.
 *
 * This structure uses flexible array, so user must ensure number of errors fits into
 * memory and must pass maximum size to readback_add when adding new entry.
 */
struct readback {
	unsigned int len;
	struct memory_error errors[];
};

#define READBACK_SIZE(n) (sizeof(struct readback) + (n) * sizeof(struct memory_error))

void readback_init(struct readback *readback);
// Uses binary search to find given address and return its index or -1 if not found.
// The addresses int the whole readback array must be non-decreasing.
int readback_find(struct readback *readback, unsigned int addr);
// Add new entry if there is space (depending on max_len). Returns 1 if added new entry.
int readback_add(struct readback *readback, unsigned int max_len, struct memory_error error);
// Print errors that occured in `readback` that didn't occure in `other`. Returns number of errors.
int readback_compare(struct readback *readback, struct readback *other, int verbose);

#endif /* CSR_SDRAM_BASE */

#ifdef __cplusplus
}
#endif

#endif /* __SDRAM_DBG_H */
