#include <startup.h>
#include <irq.h>

typedef void (*init_func)(void);

extern init_func const __preinit_array_start[];
extern init_func const __preinit_array_end[];
extern init_func const __init_array_start[];
extern init_func const __init_array_end[];

static void call_init_array(init_func const *start, init_func const *end)
{
	for (init_func const *func = start; func != end; func++)
		(*func)();
}

void litex_startup_init(void)
{
	irq_init();

	call_init_array(__preinit_array_start, __preinit_array_end);
	call_init_array(__init_array_start, __init_array_end);
}
