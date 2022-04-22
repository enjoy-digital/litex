#ifndef __SYSTEM_H
#define __SYSTEM_H

#ifdef __cplusplus
extern "C" {
#endif

#define UART_POLLING

typedef struct
{
  volatile uint32_t ISER[1];                 /*!< Offset: 0x000 (R/W)  Interrupt Set Enable Register           */
       uint32_t RESERVED0[31];
  volatile uint32_t ICER[1];                 /*!< Offset: 0x080 (R/W)  Interrupt Clear Enable Register          */
       uint32_t RSERVED1[31];
  volatile uint32_t ISPR[1];                 /*!< Offset: 0x100 (R/W)  Interrupt Set Pending Register           */
       uint32_t RESERVED2[31];
  volatile uint32_t ICPR[1];                 /*!< Offset: 0x180 (R/W)  Interrupt Clear Pending Register         */
       uint32_t RESERVED3[31];
       uint32_t RESERVED4[64];
  volatile uint32_t IP[8];                   /*!< Offset: 0x300 (R/W)  Interrupt Priority Register              */
} NVIC_Type;

#define SCS_BASE (0xE000E000UL)
#define NVIC_BASE (SCS_BASE + 0x0100UL)
#define NVIC ((NVIC_Type *) NVIC_BASE)

__attribute__((unused)) static void flush_cpu_icache(void){}; /* No instruction cache */
__attribute__((unused)) static void flush_cpu_dcache(void){}; /* No instruction cache */
void flush_l2_cache(void);

void busy_wait(unsigned int ms);
void busy_wait_us(unsigned int us);

#ifdef __cplusplus
}
#endif

#endif /* __SYSTEM_H */
