#ifndef __HW_UART_H
#define __HW_UART_H

#include <hw/common.h>
#include <csrbase.h>

#define UART_CSR(x)		MMPTR(UART_BASE+(x))

#define CSR_UART_RXTX		UART_CSR(0x00)
#define CSR_UART_DIVISORH	UART_CSR(0x04)
#define CSR_UART_DIVISORL	UART_CSR(0x08)

#define CSR_UART_EV_STAT	UART_CSR(0x0c)
#define CSR_UART_EV_PENDING	UART_CSR(0x10)
#define CSR_UART_EV_ENABLE	UART_CSR(0x14)

#define UART_EV_TX		0x1
#define UART_EV_RX		0x2

#endif /* __HW_UART_H */
