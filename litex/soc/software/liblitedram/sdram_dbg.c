#include <liblitedram/sdram_dbg.h>

#include <string.h>
#include <stdio.h>

#ifdef SDRAM_DEBUG

void error_stats_init(struct error_stats *stats) {
	memset(stats, 0, sizeof(struct error_stats));
}

// TODO: Make the computations more generic
#if SDRAM_PHY_DATABITS * SDRAM_PHY_XDR > 32
#error "At most 32 databits SDR or 16 databits DDR supported"
#endif
void error_stats_update(struct error_stats *stats, struct memory_error err) {
	unsigned int phase = (err.addr % (SDRAM_PHY_PHASES*4)) / 4;
	unsigned int errors = err.data ^ err.ref;
	for (int edge = 0; edge < SDRAM_PHY_XDR; ++edge) {
		for (int bit = 0; bit < SDRAM_PHY_DATABITS; ++bit) {
			unsigned int bitval = 1 << (SDRAM_PHY_DATABITS*edge + bit);
			if ((errors & bitval) != 0) {
				stats->phase[phase].edge[edge].dq[bit]++;
			}
		}
	}
}

void error_stats_print(struct error_stats *stats) {
	printf("        DQ:");
	for (int bit = 0; bit < 16; ++bit) {
		printf(" %5d", bit);
	}
	printf("\n");
	for (int phase = 0; phase < 8; ++phase) {
		for (int edge = 0; edge < 2; ++edge) {
			unsigned int beat = 2*phase + edge;
			printf("  beat[%2d]:", beat);
			for (int bit = 0; bit < 16; ++bit) {
				unsigned int dq_errors = stats->phase[phase].edge[edge].dq[bit];
				printf(" %5d", dq_errors);
			}
			printf("\n");
		}
	}
}

void readback_init(struct readback *readback) {
	readback->len = 0;
}

int readback_find(struct readback *readback, unsigned int addr) {
	int left = 0;
	int right = readback->len - 1;
	while (left <= right) {
		int mid = (left + right) / 2;
		if (readback->errors[mid].addr == addr) {
			return mid;
		} else if (readback->errors[mid].addr < addr) {
			left = mid + 1;
		} else {
			right = mid - 1;
		}
	}
	return -1;
}

int readback_add(struct readback *readback, unsigned int max_len, struct memory_error error) {
	if (readback->len >= max_len)
		return 0;
	readback->errors[readback->len++] = error;
	return 1;
}

int readback_compare(struct readback *readback, struct readback *other, int verbose) {
	int missing = 0;
	for (unsigned int i = 0; i < readback->len ; ++i) {
		struct memory_error *err = &readback->errors[i];
		int at = readback_find(other, err->addr);
		if (at < 0) {
			if (verbose) {
				printf("  Missing @0x%08x: 0x%08x vs 0x%08x\n",
					err->addr, err->data, err->ref);
			}
			missing++;
		}
	}
	return missing;
}

#endif