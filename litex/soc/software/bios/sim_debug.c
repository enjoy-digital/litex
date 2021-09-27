#include "sim_debug.h"

#include <stdio.h>
#include <generated/csr.h>

// 0 is used as no marker
#define MAX_N_MARKERS (255 - 1)

#ifdef CSR_SIM_MARKER_BASE
static int n_markers = 0;
static const char *markers[MAX_N_MARKERS] = {0};
#endif

void sim_mark(const char *text) {
#ifdef CSR_SIM_MARKER_BASE
  if (text == NULL) {
    text = "NO COMMENT";
  }
  // 0 is not used
  int marker_num = n_markers + 1;
  markers[n_markers++] = text;
  sim_marker_marker_write(marker_num);
  if (n_markers >= MAX_N_MARKERS) {
    printf("Max number of markers reached\n");
    n_markers = 0;
  }
#else
  printf("No sim_marker CSR\n");
#endif
}

void sim_markers_summary(void) {
#ifdef CSR_SIM_MARKER_BASE
    printf("\nMarkers:\n");
    for (int i = 0; i < n_markers; ++i) {
        printf(" %3d: %s\n", i + 1, markers[i]);
    }
    printf("\n");
#else
  printf("No sim_marker CSR\n");
#endif
}

void sim_trace(int on) {
#ifdef CSR_SIM_TRACE_BASE
  sim_trace_enable_write(on);
#else
  printf("No sim_trace CSR\n");
#endif
}

int sim_trace_on(void) {
#ifdef CSR_SIM_TRACE_BASE
  return sim_trace_enable_read();
#else
  printf("No sim_trace CSR\n");
  return 0;
#endif
}

void sim_finish(void) {
#ifdef CSR_SIM_FINISH_BASE
  sim_trace(0);
  if (n_markers > 0) {
    sim_markers_summary();
  }
  sim_finish_finish_write(1);
#else
  printf("No sim_finish CSR\n");
#endif
}
