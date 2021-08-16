#ifndef __SIM_DEBUG_H
#define __SIM_DEBUG_H

#ifdef __cplusplus
extern "C" {
#endif

// add next marker with given comment
void sim_mark(const char *comment);
#define sim_mark_func() sim_mark(__func__)
// print the summary of markers mapping (number -> comment)
void sim_markers_summary(void);
// enable simulation trace dump
void sim_trace(int on);
// check if trace is on
int sim_trace_on(void);
// finish simulation
void sim_finish(void);

#ifdef __cplusplus
}
#endif

#endif

