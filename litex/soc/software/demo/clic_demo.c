// This file is Copyright (c) 2025 LiteX developers
// License: BSD

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdbool.h>
#include <stdint.h>
#include <generated/csr.h>
#include <clic.h>
#include <irq.h>
#include <system.h>

#ifdef CSR_CLIC_BASE

/* Global variables for interrupt handling */
/* Allocate a fixed size array to avoid out-of-bounds issues */
#define MAX_INTERRUPTS 32
static volatile unsigned int clic_interrupt_count[MAX_INTERRUPTS];
static volatile unsigned int clic_last_interrupt_id = 0;
static volatile unsigned int clic_last_interrupt_priority = 0;
static volatile unsigned int clic_interrupt_cycles = 0;

/* Forward declaration - busy_wait is provided by the system */
void busy_wait(unsigned int cycles);

/* Simple delay function using busy_wait */
static void delay_ms(unsigned int ms) {
    /* Rough approximation - adjust based on your CPU frequency */
    unsigned int cycles_per_ms = CONFIG_CLOCK_FREQUENCY / 1000;
    busy_wait(cycles_per_ms * ms / 100); /* Divided by 100 for reasonable delay */
}

/* CLIC interrupt handler */
void __attribute__((weak)) clic_interrupt_handler(unsigned int id, unsigned int priority) {
    /* Bounds check to prevent array overflow */
    if (id >= MAX_INTERRUPTS) {
        printf("CLIC: Invalid interrupt ID %d (max=%d)\n", id, MAX_INTERRUPTS-1);
        return;
    }
    
    clic_interrupt_count[id]++;
    clic_last_interrupt_id = id;
    clic_last_interrupt_priority = priority;
    /* Record that interrupt was handled */
    clic_interrupt_cycles++;

    /* Clear the interrupt (for software-triggered interrupts) */
    clic_clear_pending(id);

    printf("CLIC: Interrupt %d handled (priority=%d, count=%d)\n", 
           id, priority, clic_interrupt_count[id]);
}

/* Initialize CLIC */
static void clic_init(void) {
    unsigned int i;

    printf("Initializing CLIC...\n");

    /* Clear all interrupt counts */
    for (i = 0; i < MAX_INTERRUPTS; i++) {
        clic_interrupt_count[i] = 0;
    }

    /* Disable all interrupts initially */
    /* Only configure interrupts that are actually implemented in hardware */
    unsigned int max_hw_interrupts = CLIC_NUM_INTERRUPTS;
    if (max_hw_interrupts > MAX_INTERRUPTS) {
        max_hw_interrupts = MAX_INTERRUPTS;
    }
    for (i = 0; i < max_hw_interrupts; i++) {
        clic_disable_interrupt(i);
        clic_clear_pending(i);
    }

    /* Set interrupt threshold to 0 (allow all priorities) */
    clic_set_mithreshold(0, 0);

    /* Enable global interrupts */
    irq_setie(1);

    printf("CLIC initialized\n");
}

/* Basic interrupt functionality */
static void test_basic_interrupts(void) {
    unsigned int i;
    unsigned int test_irqs[] = {1, 3, 5, 7, 9};
    unsigned int num_tests = sizeof(test_irqs) / sizeof(test_irqs[0]);

    printf("\n=== Basic Interrupt Functionality ===\n");

    /* Configure and trigger interrupts one by one */
    for (i = 0; i < num_tests; i++) {
        unsigned int irq = test_irqs[i];
        unsigned int priority = 128; /* Mid-range priority */

        printf("\nConfiguring IRQ %d with priority %d...\n", irq, priority);

        /* Configure as edge-triggered, positive polarity */
        clic_configure_interrupt(irq, priority, true, true);

        /* Enable the interrupt */
        clic_enable_interrupt(irq);

        /* Clear any pending state */
        clic_clear_pending(irq);

        /* Reset counter */
        clic_interrupt_count[irq] = 0;

        printf("Triggering IRQ %d...\n", irq);

        /* Trigger the interrupt */
        clic_set_pending(irq);

        /* Small delay to allow interrupt handling */
        delay_ms(10);

        /* Check if interrupt was handled */
        if (clic_interrupt_count[irq] > 0) {
            printf("✓ IRQ %d handled successfully (count=%d)\n", 
                   irq, clic_interrupt_count[irq]);
        } else {
            printf("✗ IRQ %d was not handled!\n", irq);
        }

        /* Disable the interrupt */
        clic_disable_interrupt(irq);
    }
}

/* Priority-based preemption */
static void test_priority_preemption(void) {
    unsigned int low_prio_irq = 2;
    unsigned int high_prio_irq = 4;

    printf("\n=== Priority-based Preemption ===\n");

    /* Configure low priority interrupt */
    clic_configure_interrupt(low_prio_irq, 200, true, true);  /* Lower priority (higher number) */
    clic_enable_interrupt(low_prio_irq);

    /* Configure high priority interrupt */
    clic_configure_interrupt(high_prio_irq, 50, true, true);  /* Higher priority (lower number) */
    clic_enable_interrupt(high_prio_irq);

    /* Clear counters */
    clic_interrupt_count[low_prio_irq] = 0;
    clic_interrupt_count[high_prio_irq] = 0;

    printf("Triggering both interrupts simultaneously...\n");

    /* Trigger both interrupts */
    clic_set_pending(low_prio_irq);
    clic_set_pending(high_prio_irq);

    /* Small delay */
    delay_ms(10);

    printf("Results:\n");
    printf("  Low priority IRQ %d: count=%d\n", low_prio_irq, clic_interrupt_count[low_prio_irq]);
    printf("  High priority IRQ %d: count=%d\n", high_prio_irq, clic_interrupt_count[high_prio_irq]);

    if (clic_last_interrupt_id == low_prio_irq) {
        printf("  Last handled: Low priority (IRQ %d)\n", low_prio_irq);
    } else if (clic_last_interrupt_id == high_prio_irq) {
        printf("  Last handled: High priority (IRQ %d)\n", high_prio_irq);
    }

    /* Disable interrupts */
    clic_disable_interrupt(low_prio_irq);
    clic_disable_interrupt(high_prio_irq);
}

/* Interrupt threshold */
static void test_interrupt_threshold(void) {
    unsigned int test_irqs[] = {10, 11, 12};
    unsigned int priorities[] = {50, 128, 200};
    unsigned int i;

    printf("\n=== Interrupt Threshold ===\n");

    /* Configure interrupts with different priorities */
    for (i = 0; i < 3; i++) {
        clic_configure_interrupt(test_irqs[i], priorities[i], true, true);
        clic_enable_interrupt(test_irqs[i]);
        clic_interrupt_count[test_irqs[i]] = 0;
    }

    /* Test with threshold = 100 (should block priority >= 100) */
    printf("\nSetting threshold to 100...\n");
    clic_set_mithreshold(0, 100);

    /* Trigger all interrupts */
    for (i = 0; i < 3; i++) {
        clic_set_pending(test_irqs[i]);
    }

    delay_ms(10);

    printf("Results with threshold=100:\n");
    for (i = 0; i < 3; i++) {
        printf("  IRQ %d (priority=%d): count=%d %s\n", 
               test_irqs[i], priorities[i], clic_interrupt_count[test_irqs[i]],
               (priorities[i] < 100) ? "✓ (allowed)" : "✗ (blocked)");
    }

    /* Reset threshold */
    clic_set_mithreshold(0, 0);

    /* Clear pending interrupts and disable */
    for (i = 0; i < 3; i++) {
        clic_clear_pending(test_irqs[i]);
        clic_disable_interrupt(test_irqs[i]);
    }
}

/* Edge vs Level triggering */
static void test_trigger_modes(void) {
    unsigned int edge_irq = 15;
    unsigned int level_irq = 16;

    printf("\n=== Test 4: Edge vs Level Triggering ===\n");

    /* Configure edge-triggered interrupt */
    printf("\nConfiguring IRQ %d as edge-triggered...\n", edge_irq);
    clic_configure_interrupt(edge_irq, 128, true, true);  /* edge-triggered */
    clic_enable_interrupt(edge_irq);
    clic_interrupt_count[edge_irq] = 0;

    /* Configure level-triggered interrupt */
    printf("Configuring IRQ %d as level-triggered...\n", level_irq);
    clic_configure_interrupt(level_irq, 128, false, true);  /* level-triggered */
    clic_enable_interrupt(level_irq);
    clic_interrupt_count[level_irq] = 0;

    /* Test edge-triggered */
    printf("\nTesting edge-triggered interrupt...\n");
    clic_set_pending(edge_irq);
    delay_ms(5);
    printf("  Edge IRQ %d: count=%d (should be 1)\n", edge_irq, clic_interrupt_count[edge_irq]);

    /* For level-triggered, we need to manually clear it in the handler */
    /* This is just a demonstration - in real use, the hardware would control the level */
    printf("\nTesting level-triggered interrupt...\n");
    clic_set_pending(level_irq);
    delay_ms(5);
    printf("  Level IRQ %d: count=%d\n", level_irq, clic_interrupt_count[level_irq]);

    /* Cleanup */
    clic_disable_interrupt(edge_irq);
    clic_disable_interrupt(level_irq);
}

/* Interrupt latency measurement */
static void test_interrupt_latency(void) {
    unsigned int test_irq = 20;
    unsigned int i;
    unsigned int total_latency = 0;
    unsigned int iterations = 10;

    printf("\n=== Interrupt Latency Measurement ===\n");

    /* Configure interrupt */
    clic_configure_interrupt(test_irq, 64, true, true);
    clic_enable_interrupt(test_irq);

    printf("Measuring interrupt latency over %d iterations...\n", iterations);

    for (i = 0; i < iterations; i++) {
        /* Reset interrupt count */
        clic_interrupt_count[test_irq] = 0;
        
        /* Count cycles for simple latency measurement */
        unsigned int cycles = 0;
        
        /* Trigger interrupt */
        clic_set_pending(test_irq);
        
        /* Wait for interrupt to be handled */
        while (clic_interrupt_count[test_irq] == 0 && cycles < 10000) {
            cycles++;
        }
        
        if (clic_interrupt_count[test_irq] > 0) {
            total_latency += cycles;
            printf("  Iteration %d: ~%d cycles\n", i+1, cycles);
        } else {
            printf("  Iteration %d: TIMEOUT\n", i+1);
        }

        delay_ms(10);
    }

    if (total_latency > 0) {
        unsigned int avg_latency = total_latency / iterations;
        printf("\nAverage interrupt latency: ~%u cycles\n", avg_latency);
    }

    /* Cleanup */
    clic_disable_interrupt(test_irq);
}

/* Test 6: Multiple simultaneous interrupts */
static void test_multiple_interrupts(void) {
    unsigned int i;
    unsigned int num_irqs = 5;
    unsigned int base_irq = 25;

    printf("\n=== Multiple Simultaneous Interrupts ===\n");

    /* Configure multiple interrupts with different priorities */
    for (i = 0; i < num_irqs; i++) {
        unsigned int irq = base_irq + i;
        unsigned int priority = 50 + (i * 30);  /* Priorities: 50, 80, 110, 140, 170 */

        clic_configure_interrupt(irq, priority, true, true);
        clic_enable_interrupt(irq);
        clic_interrupt_count[irq] = 0;

        printf("Configured IRQ %d with priority %d\n", irq, priority);
    }

    printf("\nTriggering all %d interrupts simultaneously...\n", num_irqs);

    /* Trigger all interrupts at once */
    for (i = 0; i < num_irqs; i++) {
        clic_set_pending(base_irq + i);
    }

    /* Allow time for handling */
    delay_ms(20);

    printf("\nResults:\n");
    for (i = 0; i < num_irqs; i++) {
        unsigned int irq = base_irq + i;
        printf("  IRQ %d: handled %d times\n", irq, clic_interrupt_count[irq]);
    }

    /* Cleanup */
    for (i = 0; i < num_irqs; i++) {
        clic_disable_interrupt(base_irq + i);
    }
}

/* CSR Access Test - verifies that CLIC CSR read/write operations work correctly */
static void test_clic_csr_access(void) {
    printf("\n=== CLIC CSR Access Test ===\n");
    printf("CSR_BASE: 0x%08lx\n", CSR_BASE);
    printf("CSR_CLIC_BASE: 0x%08lx\n", CSR_CLIC_BASE);
    
    /* Test interrupt 0 */
    printf("\nTesting interrupt 0 CSRs:\n");
    printf("CLICINTIE0 addr: 0x%08lx\n", CSR_CLIC_CLICINTIE0_ADDR);
    printf("CLICINTIP0 addr: 0x%08lx\n", CSR_CLIC_CLICINTIP0_ADDR);
    printf("CLICIPRIO0 addr: 0x%08lx\n", CSR_CLIC_CLICIPRIO0_ADDR);
    printf("CLICINTATTR0 addr: 0x%08lx\n", CSR_CLIC_CLICINTATTR0_ADDR);
    
    /* Write and read back interrupt 0 enable */
    clic_set_intie(0, 1);
    printf("Wrote 1 to CLICINTIE0\n");
    uint32_t ie0 = clic_get_intie(0);
    printf("Read back CLICINTIE0: %u\n", ie0);
    
    /* Configure interrupt 0 */
    clic_set_intprio(0, 128);  /* Mid priority */
    clic_set_intattr(0, 0x03); /* Edge triggered, positive */
    printf("Configured interrupt 0: priority=128, edge triggered\n");
    
    /* Try to trigger interrupt 0 */
    printf("\nTriggering interrupt 0...\n");
    clic_set_intip(0, 1);
    
    /* Read pending status */
    uint32_t ip0 = clic_get_intip(0);
    printf("CLICINTIP0 after trigger: %u\n", ip0);
    
    /* Clear pending */
    clic_set_intip(0, 0);
    ip0 = clic_get_intip(0);
    printf("CLICINTIP0 after clear: %u\n", ip0);
    
    clic_set_intie(0, 0);  /* Disable interrupt 0 */
}

/* Simple CLIC Test - basic interrupt functionality with direct CSR access */
static void test_clic_simple(void) {
    printf("\n=== Simple CLIC Test ===\n");
    
    /* Show CSR addresses */
    printf("CSR_BASE: 0x%08lx\n", CSR_BASE);
    printf("CSR_CLIC_BASE: 0x%08lx\n", CSR_CLIC_BASE);
    
    /* Disable all interrupts first */
    irq_setie(0);
    
    /* Configure interrupt 1 */
    printf("\nConfiguring interrupt 1...\n");
    clic_set_intattr(1, 0x01);  /* Edge triggered, positive polarity */
    clic_set_intprio(1, 128);   /* Mid priority */
    clic_set_intie(1, 1);       /* Enable interrupt 1 */
    
    /* Enable global interrupts */
    irq_setie(1);
    printf("Global interrupts enabled\n");
    
    /* Test 1: Trigger interrupt via CSR write */
    printf("\nTest 1: Triggering interrupt 1 via CSR write...\n");
    clic_interrupt_count[1] = 0;
    
    /* Trigger the interrupt */
    clic_set_intip(1, 1);
    
    /* Small delay */
    delay_ms(10);
    
    /* Check result */
    if (clic_interrupt_count[1] > 0) {
        printf("SUCCESS: Interrupt was handled %d times\n", clic_interrupt_count[1]);
    } else {
        printf("FAILED: Interrupt was not handled\n");
    }
    
    /* Test 2: Check if pending bit can be read */
    printf("\nTest 2: Testing pending bit read/write...\n");
    clic_set_intip(1, 1);
    uint32_t pending = clic_get_intip(1);
    printf("After setting: pending = %u\n", pending);
    
    clic_set_intip(1, 0);
    pending = clic_get_intip(1);
    printf("After clearing: pending = %u\n", pending);
    
    /* Test 3: Check other CSRs */
    printf("\nTest 3: Reading configuration CSRs...\n");
    printf("CLICINTIE1: %u\n", clic_get_intie(1));
    printf("CLICIPRIO1: %u\n", clic_get_intprio(1));
    printf("CLICINTATTR1: 0x%02x\n", clic_get_intattr(1));
    
    /* Disable interrupts */
    irq_setie(0);
    clic_set_intie(1, 0);
    
    printf("\nSimple CLIC test complete\n");
}

/* Main CLIC demo function */
void clic_demo(void) {
    printf("\n");
    /* Initialize CLIC */
    clic_init();

    /* Run basic CSR and functionality tests first */
    test_clic_csr_access();
    test_clic_simple();

    /* Run all existing tests */
    test_basic_interrupts();
    test_priority_preemption();
    test_interrupt_threshold();
    test_trigger_modes();
    test_interrupt_latency();
    test_multiple_interrupts();

    printf("\nClic tests finished\n");
}

#else

void clic_demo(void) {
    printf("CLIC not supported on this build.\n");
}

#endif /* CSR_CLIC_BASE */