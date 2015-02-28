/*
 * fastftdi.h - A minimal FTDI FT232H interface for Linux which supports
 *              bit-bang mode, but focuses on very high-performance support
 *              for synchronous FIFO mode.
 *
 * Copyright (C) 2009 Micah Elizabeth Scott
 *
 * Permission is hereby granted, free of charge, to any person obtaining a copy
 * of this software and associated documentation files (the "Software"), to deal
 * in the Software without restriction, including without limitation the rights
 * to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
 * copies of the Software, and to permit persons to whom the Software is
 * furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in
 * all copies or substantial portions of the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
 * IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
 * FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
 * LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
 * OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
 * THE SOFTWARE.
 */

#ifndef __FASTFTDI_H
#define __FASTFTDI_H

#include <libusb.h>
#include <stdint.h>
#include <stdbool.h>

typedef enum {
  FTDI_BITMODE_RESET        = 0,
  FTDI_BITMODE_BITBANG      = 1 << 0,
  FTDI_BITMODE_MPSSE        = 1 << 1,
  FTDI_BITMODE_SYNC_BITBANG = 1 << 2,
  FTDI_BITMODE_MCU          = 1 << 3,
  FTDI_BITMODE_OPTO         = 1 << 4,
  FTDI_BITMODE_CBUS         = 1 << 5,
  FTDI_BITMODE_SYNC_FIFO    = 1 << 6,
} FTDIBitmode;

typedef enum {
  FTDI_MPSSE_SETLOW  = 0x80,
  FTDI_MPSSE_SETHIGH = 0x82,
  FTDI_MPSSE_GETLOW  = 0x81,
  FTDI_MPSSE_GETHIGH = 0x83,
  FTDI_MPSSE_SETDIVISOR = 0x86,
} FTDIMPSSEOpcode;

typedef enum {
  FTDI_INTERFACE_A = 1,
  FTDI_INTERFACE_B = 2,
} FTDIInterface;

typedef struct {
  libusb_context *libusb;
  libusb_device_handle *handle;
} FTDIDevice;

typedef struct {
   struct {
      uint64_t       totalBytes;
      struct timeval time;
   } first, prev, current;

   double totalTime;
   double totalRate;
   double currentRate;
} FTDIProgressInfo;


/*
 * USB Constants
 */

#define FTDI_VENDOR               0x0403
#define FTDI_PRODUCT_FT2232H      0x6010

#define LITEUSB_VENDOR              0x1d50
#define LITEUSB_PRODUCT             0x607c

#define FTDI_COMMAND_TIMEOUT      1000

#define FTDI_SET_BAUD_REQUEST     0x03
#define FTDI_SET_BITMODE_REQUEST  0x0B

#define FTDI_EP_IN(i)             (0x81 + (i-1)*2)
#define FTDI_EP_OUT(i)            (0x02 + (i-1)*2)

#define FTDI_PACKET_SIZE          512   // Specific to FT2232H
#define FTDI_LOG_PACKET_SIZE      9     // 512 == 1 << 9
#define FTDI_HEADER_SIZE          2

typedef int (FTDIStreamCallback)(uint8_t *buffer, int length,
                                 FTDIProgressInfo *progress, void *userdata);


/*
 * Public Functions
 */

int FTDIDevice_Open(FTDIDevice *dev);
void FTDIDevice_Close(FTDIDevice *dev);
int FTDIDevice_Reset(FTDIDevice *dev);

int FTDIDevice_SetMode(FTDIDevice *dev, FTDIInterface interface,
                       FTDIBitmode mode, uint8_t pinDirections,
                       int baudRate);

int FTDIDevice_Write(FTDIDevice *dev, FTDIInterface interface,
                     uint8_t *data, size_t length, bool async);

int FTDIDevice_WriteByteSync(FTDIDevice *dev, FTDIInterface interface, uint8_t byte);
int FTDIDevice_ReadByteSync(FTDIDevice *dev, FTDIInterface interface, uint8_t *byte);

int FTDIDevice_ReadStream(FTDIDevice *dev, FTDIInterface interface,
                          FTDIStreamCallback *callback, void *userdata,
                          int packetsPerTransfer, int numTransfers);

int FTDIDevice_MPSSE_Enable(FTDIDevice *dev, FTDIInterface interface);
int FTDIDevice_MPSSE_SetDivisor(FTDIDevice *dev, FTDIInterface interface,
                                uint8_t ValueL, uint8_t ValueH);

int FTDIDevice_MPSSE_SetLowByte(FTDIDevice *dev, FTDIInterface interface,
                                uint8_t data, uint8_t dir);
int FTDIDevice_MPSSE_SetHighByte(FTDIDevice *dev, FTDIInterface interface,
                                 uint8_t data, uint8_t dir);

int FTDIDevice_MPSSE_GetLowByte(FTDIDevice *dev, FTDIInterface interface, uint8_t *byte);
int FTDIDevice_MPSSE_GetHighByte(FTDIDevice *dev, FTDIInterface interface, uint8_t *byte);

#endif /* __FASTFTDI_H */
