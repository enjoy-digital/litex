#ifndef __IRQ_H
#define __IRQ_H

#ifdef __cplusplus
extern "C" {
#endif

#include <system.h>
#include <generated/csr.h>
#include <generated/soc.h>

// PicoRV32 has a very limited interrupt support, implemented via custom
// instructions. It also doesn't have a global interrupt enable/disable, so
// we have to emulate it via saving and restoring a mask and using 0/~1 as a
// hardware mask.
// Due to all this somewhat low-level mess, all of the glue is implemented in
// the RiscV crt0, and this header is kept as a thin wrapper. Since interrupts
// managed by this layer, do not call interrupt instructions directly, as the
// state will go out of sync with the hardware.

// Read only.
extern unsigned int _irq_pending;
// Read only.
extern unsigned int _irq_mask;
// Read only.
extern unsigned int _irq_enabled;
extern void _irq_enable(void);
extern void _irq_disable(void);
extern void _irq_setmask(unsigned int);

static inline unsigned int irq_getie(void)
{
	return _irq_enabled != 0;
}

static inline void irq_setie(unsigned int ie)
{
    if (ie & 0x1)
        _irq_enable();
    else
        _irq_disable();
}

static inline unsigned int irq_getmask(void)
{
    // PicoRV32 interrupt mask bits are high-disabled. This is the inverse of how
    // LiteX sees things.
    return ~_irq_mask;
}

static inline void irq_setmask(unsigned int mask)
{
    // PicoRV32 interrupt mask bits are high-disabled. This is the inverse of how
    // LiteX sees things.
    _irq_setmask(~mask);
}

static inline unsigned int irq_pending(void)
{
	return _irq_pending;
}

#ifdef __cplusplus
}
#endif

#endif /* __IRQ_H */
