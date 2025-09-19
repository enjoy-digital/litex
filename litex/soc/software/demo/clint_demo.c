// This file is Copyright (c) 2025 LiteX Contributors
// License: BSD
// CLINT Software Interrupt Demo
//
// This demo shows how to use the CLINT (Core Local Interruptor) for
// software interrupts in LiteX. It demonstrates:
// 1. Setting up a software interrupt handler
// 2. Triggering software interrupts via MSIP register
// 3. Inter-processor communication (IPI) patterns

#include <stdio.h>
#include <stdint.h>
#include <stdbool.h>
#include <generated/csr.h>
#include <generated/mem.h>
#include <generated/soc.h>
#include <system.h>
#include <irq.h>

#ifdef CSR_CLINT_BASE
#include <clint.h>

// RISC-V CSR definitions if not already defined
#ifndef CSR_MSTATUS_MIE
#define CSR_MSTATUS_MIE 0x8
#endif

// CSR addresses for direct access (from Minerva's csr-defs.h)
#ifndef CSR_MIE
#define CSR_MIE 0x304
#endif
#ifndef CSR_MIP
#define CSR_MIP 0x344
#endif

// Machine interrupt enable bits (CSR_MIE_MSIE might be defined in CPU-specific headers)
#ifndef CSR_MIE_MSIE
#define CSR_MIE_MSIE (1 << 3) // Machine Software Interrupt Enable
#endif
#ifndef CSR_MIE_MTIE
#define CSR_MIE_MTIE (1 << 7) // Machine Timer Interrupt Enable
#endif
#ifndef CSR_MIE_MEIE
#define CSR_MIE_MEIE (1 << 11) // Machine External Interrupt Enable
#endif

// Define MIE_MTIE if not already defined (for clearing timer interrupts)
#ifndef MIE_MTIE
#define MIE_MTIE (1 << 7) // Machine Timer Interrupt Enable
#endif

// Machine interrupt pending bits
#ifndef CSR_MIP_MSIP
#define CSR_MIP_MSIP (1 << 3) // Machine Software Interrupt Pending
#endif

// Use CPU-specific names if available, otherwise use our defines
#ifdef CSR_MIE_MSIE
#define MIE_MSIE CSR_MIE_MSIE
#else
#define MIE_MSIE (1 << 3)
#endif

#ifdef CSR_MIP_MSIP
#define MIP_MSIP CSR_MIP_MSIP
#else
#define MIP_MSIP (1 << 3)
#endif

// Global variables for demo
static volatile int sw_interrupt_count = 0;
static volatile bool sw_interrupt_handled = false;

// Software interrupt handler - NOT static so it's globally visible
void software_interrupt_handler(void)
{
    sw_interrupt_count++;
    sw_interrupt_handled = true;

    // Clear the software interrupt by writing 0 to MSIP
    clint_set_msip(0, 0);

    printf("Software interrupt handled! Count: %d\n", sw_interrupt_count);
}

// Note: The main interrupt handler isr() is defined in libbase/isr.c
// For CLINT, the ISR directly calls our software_interrupt_handler function

// Initialize CLINT for software interrupts
static void clint_init(void)
{
    unsigned int test_mstatus = irq_getie() ? 1 : 0;
    // Clear any pending software interrupts
    clint_set_msip(0, 0);

    // Enable software interrupt using direct CSR access that matches Minerva's implementation
    asm volatile("csrrs x0, %0, %1" ::"i"(CSR_MIE), "r"(CSR_MIE_MSIE));
    // Enable global interrupts
    irq_setie(1);

    printf("CLINT initialized for software interrupts\n");
}

// Debug function to directly check interrupt wiring
static void check_clint_cpu_connection(void)
{
    // Check if CLINT is properly connected by toggling MSIP and watching signals
    printf("\n=== Testing CLINT->CPU connection ===\n");

    // Clear MSIP first
    clint_set_msip(0, 0);
    busy_wait(10);

    // Read initial MIP
    unsigned int mip1;
    asm volatile("csrr %0, %1" : "=r"(mip1) : "i"(CSR_MIP));

    // Set MSIP
    clint_set_msip(0, 1);
    busy_wait(10);

    // Read MIP again
    unsigned int mip2;
    asm volatile("csrr %0, %1" : "=r"(mip2) : "i"(CSR_MIP));

    // Check if MIP changed
    if ((mip2 & CSR_MIP_MSIP) && !(mip1 & CSR_MIP_MSIP))
    {
        printf("Test PASSED: MIP.MSIP responds to CLINT MSIP\n");
    }
    else
    {
        printf("Test FAILED: MIP.MSIP does not respond to CLINT MSIP\n");
        printf("This indicates CLINT is not properly connected to CPU\n");
    }

    // Clear MSIP
    clint_set_msip(0, 0);
}

// CSR Manipulation test
static void csr_manupulation_test(void)
{
    printf("\n=== CSR Manipulation Test ===\n");

    // Direct CSR manipulation
    unsigned int mip_orig, mip_forced, mip_cleared;

    // Read original MIP
    asm volatile("csrr %0, %1" : "=r"(mip_orig) : "i"(CSR_MIP));

    // Try to force MSIP bit in MIP (this should fail as MIP.MSIP is read-only)
    asm volatile("csrrs x0, %0, %1" ::"i"(CSR_MIP), "r"(CSR_MIP_MSIP));
    asm volatile("csrr %0, %1" : "=r"(mip_forced) : "i"(CSR_MIP));

    // Clear attempt
    asm volatile("csrrc x0, %0, %1" ::"i"(CSR_MIP), "r"(CSR_MIP_MSIP));
    asm volatile("csrr %0, %1" : "=r"(mip_cleared) : "i"(CSR_MIP));

    // Compare values to determine test result
    if (mip_orig == mip_forced && mip_orig == mip_cleared)
    {
        printf("Test PASSED: MIP.MSIP is read-only as expected\n");
    }
    else
    {
        printf("Test FAILED: MIP.MSIP is not behaving as read-only\n");
    }
}

static void memory_barrier_test(void)
{

    // Test 2: Memory barrier test
    printf("\n=== Memory barrier Test ===\n");

    // Clear MSIP with memory barrier
    clint_set_msip(0, 0);
    asm volatile("fence" ::: "memory");
    busy_wait(10);

    unsigned int mip1;
    asm volatile("csrr %0, %1" : "=r"(mip1) : "i"(CSR_MIP));
 
    // Set MSIP with memory barrier
    clint_set_msip(0, 1);
    asm volatile("fence" ::: "memory");
    busy_wait(10);

    unsigned int mip2;
    asm volatile("csrr %0, %1" : "=r"(mip2) : "i"(CSR_MIP));
 
    // Compare mip1 and mip2 to determine test result
    if ((mip2 & CSR_MIP_MSIP) && !(mip1 & CSR_MIP_MSIP))
    {
        printf("Test PASSED: MIP.MSIP responds correctly to MSIP changes\n");
    }
    else
    {
        printf("Test FAILED: MIP.MSIP does not respond correctly to MSIP changes\n");
    }

    // Clean up
    clint_set_msip(0, 0);
}

static void configure_interrupt_registers(void)
{
    // Read and print interrupt registers
    // Set MSIP bit to trigger software interrupt
    clint_set_msip(0, 1);
    // Check if MSIP is actually set
    uint32_t msip_value = clint_get_msip(0);
    if (!(msip_value))
    {
        printf("ERROR: MSIP failed to set! (value: 0x%08x)\n", msip_value);
        volatile uint32_t *msip_addr = (volatile uint32_t *)(CSR_CLINT_BASE + CLINT_MSIP_OFFSET);
        printf("Direct read of MSIP: 0x%08x\n", *msip_addr);
        // Try writing again directly
        *msip_addr = 1;
        printf("After direct write, MSIP: 0x%08x\n", *msip_addr);
    }

    // Check MIE register
    unsigned int mie_val;
    asm volatile("csrr %0, %1" : "=r"(mie_val) : "i"(CSR_MIE));

    // If MSIE is disabled, try to re-enable it
    if (!(mie_val & MIE_MSIE))
    {
        printf("WARNING: MSIE was cleared! Re-enabling...\n");
        asm volatile("csrrs x0, %0, %1" ::"i"(CSR_MIE), "r"(MIE_MSIE));
        asm volatile("csrr %0, %1" : "=r"(mie_val) : "i"(CSR_MIE));
        printf("MIE after re-enable: 0x%08x\n", mie_val);
    }
}

// Trigger a software interrupt
static void trigger_software_interrupt(void)
{
    printf("Triggering software interrupt...\n");
    sw_interrupt_handled = false;

    configure_interrupt_registers();

    // Small delay to ensure interrupt propagates
    for (volatile int delay = 0; delay < 100; delay++)
        ;

    // Wait for interrupt to be handled
    // Add some nops to keep pipeline active while waiting
    int timeout = 1000000;
    while (!sw_interrupt_handled && timeout > 0)
    {
        timeout--;
        // Add memory barrier to ensure sw_interrupt_handled is re-read
        __asm__ __volatile__("" : : : "memory");
        // Keep pipeline active with nops
        __asm__ __volatile__("nop");
        __asm__ __volatile__("nop");
        __asm__ __volatile__("nop");
        __asm__ __volatile__("nop");
    }

    if (timeout == 0)
    {
        printf("Warning: Software interrupt was not handled!\n");
        // Debug: Final check of interrupt state
        unsigned int final_mip;
        asm volatile("csrr %0, %1" : "=r"(final_mip) : "i"(CSR_MIP));
        printf("  Final MIP: 0x%08x\n", final_mip);
    }
}

// Basic software interrupt test
static void test_basic_interrupt(void)
{
    printf("\n=== Basic Software Interrupt test ===\n");

    for (int i = 0; i < 5; i++)
    {
        trigger_software_interrupt();
        busy_wait(100);
    }

    printf("Total interrupts handled: %d\n", sw_interrupt_count);
}

// Interrupt enable/disable test
static void test_interrupt_control(void)
{
    printf("\n=== Interrupt Enable/Disable test ===\n");

    // Save current interrupt count
    int initial_count = sw_interrupt_count;

    // Disable software interrupts
    asm volatile("csrrc x0, %0, %1" ::"i"(CSR_MIE), "r"(MIE_MSIE));

    // Try to trigger interrupt (should not be handled)
    clint_set_msip(0, 1);
    busy_wait(100);

    if (sw_interrupt_count == initial_count)
    {
        printf("Good: Interrupt was not handled while disabled\n");
    }
    else
    {
        printf("Error: Interrupt was handled while disabled!\n");
    }

    // Clear pending interrupt
    clint_set_msip(0, 0);

    // Re-enable software interrupts
    asm volatile("csrrs x0, %0, %1" ::"i"(CSR_MIE), "r"(MIE_MSIE));

    // Trigger interrupt (should be handled now)
    trigger_software_interrupt();

    if (sw_interrupt_count > initial_count)
    {
        printf("Good: Interrupt was handled after re-enabling\n");
    }
    else
    {
        printf("Error: Interrupt was not handled after re-enabling!\n");
    }
}

// Main CLINT demo function
void clint_demo(void)
{
    printf("CLINT base address: 0x%08x\n", CSR_CLINT_BASE);
    busy_wait(10); // Small delay

    // Check if we have interrupt support
#ifndef CONFIG_CPU_HAS_INTERRUPT
    printf("Error: CPU does not have interrupt support!\n");
    printf("Please rebuild with CONFIG_CPU_HAS_INTERRUPT enabled.\n");
    return;
#endif
    // Initialize CLINT
    clint_init();

    // Run tests
    check_clint_cpu_connection();
    csr_manupulation_test();
    memory_barrier_test();
    test_basic_interrupt();
    test_interrupt_control();

    printf("\n==== CLINT Demo Complete ====\n");
}

#else /* !CSR_CLINT_BASE */

void clint_demo(void)
{
    printf("CLINT not supported on this build.\n");
}

#endif /* CSR_CLINT_BASE */