#ifndef __TIMER_H
#define __TIMER_H

unsigned int get_system_frequency(void);
void timer_enable(int en);
unsigned int timer_get(void);
void timer_set_counter(unsigned int value);
void timer_set_reload(unsigned int value);
void busy_wait(unsigned int ms);

#endif /* __TIMER_H */
