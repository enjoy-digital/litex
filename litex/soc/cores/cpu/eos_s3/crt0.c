#include <stdint.h>

extern uint32_t _fdata_rom, _fdata, _edata, _fbss, _ebss;

void SystemInit(void);
void Reset_Handler(void);
void _start(void);

void _start(void) {
  Reset_Handler();
}

void Reset_Handler(void) {
  uint32_t *y = &_fdata_rom;
  for (uint32_t *x = &_fdata; x < &_edata; x ++)
    *x = *y ++;

  for (uint32_t *x = &_fbss; x < &_ebss; x ++)
    *x = 0;

#ifndef __NO_SYSTEM_INIT
  SystemInit();
#endif

  // just in case - for now EOS CPU support relies on QORC SDK
  // and main() is launched inside SystemInit() as FreeRTOS task
  // so this call is not reached
  __asm__("bl main");
}

__attribute__((weak)) uint32_t __semihost_call(uint32_t r0, uint32_t r1);

__attribute__((weak)) uint32_t __semihost_call(uint32_t r0, uint32_t r1) {
  return 0;
}
