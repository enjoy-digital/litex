/*
 * fastftdi.c - A minimal FTDI FT2232H interface for which supports bit-bang
 *              mode, but focuses on very high-performance support for
 *              synchronous FIFO mode. Requires libusb-1.0
 *
 * Copyright (C) 2009 Micah Elizabeth Scott
 * Copyright (C) 2015 Florent Kermarrec
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

#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <stdbool.h>
#include "fastftdi.h"

#if defined _WIN32 || defined _WIN64
  #include <time.h>
  #include <sys/timeb.h>
  int gettimeofday (struct timeval *tp, void *tz)
  {
    struct _timeb timebuffer;
    _ftime (&timebuffer);
    tp->tv_sec = timebuffer.time;
    tp->tv_usec = timebuffer.millitm * 1000;
    return 0;
  }
#endif

typedef struct {
   FTDIStreamCallback *callback;
   void *userdata;
   int result;
   FTDIProgressInfo progress;
} FTDIStreamState;

static int
DeviceInit(FTDIDevice *dev, FTDIInterface interface)
{
  int err;

  if (libusb_kernel_driver_active(dev->handle, (interface-1)) == 1) {
    if ((err = libusb_detach_kernel_driver(dev->handle, (interface-1)))) {
      perror("Error detaching kernel driver");
      return err;
    }
  }

  if ((err = libusb_set_configuration(dev->handle, 1))) {
    perror("Error setting configuration");
    return err;
  }

  if ((err = libusb_claim_interface(dev->handle, (interface-1)))) {
    perror("Error claiming interface");
    return err;
  }

  return 0;
}


int
FTDIDevice_Open(FTDIDevice *dev, FTDIInterface interface)
{
  int err;

  memset(dev, 0, sizeof *dev);

  if ((err = libusb_init(&dev->libusb))) {
    return err;
  }

  libusb_set_debug(dev->libusb, 0);


  if (!dev->handle) {
    dev->handle = libusb_open_device_with_vid_pid(dev->libusb,
						  FTDI_VENDOR,
						  FTDI_PRODUCT_FT2232H);
  }

  if (!dev->handle) {
    return LIBUSB_ERROR_NO_DEVICE;
  }

  return DeviceInit(dev, interface);
}


void
FTDIDevice_Close(FTDIDevice *dev)
{
  libusb_close(dev->handle);
  libusb_exit(dev->libusb);
}


int
FTDIDevice_Reset(FTDIDevice *dev, FTDIInterface interface)
{
  int err;

  err = libusb_reset_device(dev->handle);
  if (err)
    return err;

  return DeviceInit(dev, interface);
}


int
FTDIDevice_SetMode(FTDIDevice *dev, FTDIInterface interface,
                   FTDIBitmode mode, uint8_t pinDirections,
                   int baudRate)
{
  int err;

  err = libusb_control_transfer(dev->handle,
                                LIBUSB_REQUEST_TYPE_VENDOR
                                | LIBUSB_RECIPIENT_DEVICE
                                | LIBUSB_ENDPOINT_OUT,
                                FTDI_SET_BITMODE_REQUEST,
                                pinDirections | (mode << 8),
                                interface,
                                NULL, 0,
                                FTDI_COMMAND_TIMEOUT);
  if (err)
    return err;

  if (baudRate) {
    int divisor;

    if (mode == FTDI_BITMODE_BITBANG)
      baudRate <<= 2;

    divisor = 240000000 / baudRate;
    if (divisor < 1 || divisor > 0xFFFF) {
      return LIBUSB_ERROR_INVALID_PARAM;
    }

    err = libusb_control_transfer(dev->handle,
                                  LIBUSB_REQUEST_TYPE_VENDOR
                                  | LIBUSB_RECIPIENT_DEVICE
                                  | LIBUSB_ENDPOINT_OUT,
                                  FTDI_SET_BAUD_REQUEST,
                                  divisor,
                                  interface,
                                  NULL, 0,
                                  FTDI_COMMAND_TIMEOUT);
    if (err)
      return err;
  }

  return err;
}


/*
 * Internal callback for cleaning up async writes.
 */

static void
WriteAsyncCallback(struct libusb_transfer *transfer)
{
   free(transfer->buffer);
   libusb_free_transfer(transfer);
}


/*
 * Write to an FTDI interface, either synchronously or asynchronously.
 * Async writes have no completion callback, they finish 'eventually'.
 */

int
FTDIDevice_Write(FTDIDevice *dev, FTDIInterface interface,
                 uint8_t *data, size_t length, bool async)
{
   int err;

   if (async) {
      struct libusb_transfer *transfer = libusb_alloc_transfer(0);

      if (!transfer) {
         return LIBUSB_ERROR_NO_MEM;
      }

      libusb_fill_bulk_transfer(transfer, dev->handle, FTDI_EP_OUT(interface),
                                malloc(length), length, (libusb_transfer_cb_fn) WriteAsyncCallback, 0, 0);

      if (!transfer->buffer) {
         libusb_free_transfer(transfer);
         return LIBUSB_ERROR_NO_MEM;
      }

      memcpy(transfer->buffer, data, length);
      err = libusb_submit_transfer(transfer);

   } else {
      int transferred;
      err = libusb_bulk_transfer(dev->handle, FTDI_EP_OUT(interface),
                                 data, length, &transferred,
                                 FTDI_COMMAND_TIMEOUT);
   }

   if (err < 0)
      return err;
   else
      return 0;
}


int
FTDIDevice_WriteByteSync(FTDIDevice *dev, FTDIInterface interface, uint8_t byte)
{
   return FTDIDevice_Write(dev, interface, &byte, sizeof byte, false);
}


int
FTDIDevice_ReadByteSync(FTDIDevice *dev, FTDIInterface interface, uint8_t *byte)
{
  /*
   * This is a simplified synchronous read, intended for bit-banging mode.
   * Ignores the modem/buffer status bytes, returns just the data.
   *
   */

  uint8_t packet[3];
  int transferred, err;

  err = libusb_bulk_transfer(dev->handle, FTDI_EP_IN(interface),
                             packet, sizeof packet, &transferred,
                             FTDI_COMMAND_TIMEOUT);
  if (err < 0) {
    return err;
  }
  if (transferred != sizeof packet) {
    return -1;
  }

  if (byte) {
     *byte = packet[sizeof packet - 1];
  }

  return 0;
}


/*
 * Internal callback for one transfer's worth of stream data.
 * Split it into packets and invoke the callbacks.
 */

static void
ReadStreamCallback(struct libusb_transfer *transfer)
{
   FTDIStreamState *state = transfer->user_data;

   if (state->result == 0) {
      if (transfer->status == LIBUSB_TRANSFER_COMPLETED) {

         int i;
         uint8_t *ptr = transfer->buffer;
         int length = transfer->actual_length;
         int numPackets = (length + FTDI_PACKET_SIZE - 1) >> FTDI_LOG_PACKET_SIZE;

         for (i = 0; i < numPackets; i++) {
            int payloadLen;
            int packetLen = length;

            if (packetLen > FTDI_PACKET_SIZE)
               packetLen = FTDI_PACKET_SIZE;

            payloadLen = packetLen - FTDI_HEADER_SIZE;
            state->progress.current.totalBytes += payloadLen;

            state->result = state->callback(ptr + FTDI_HEADER_SIZE, payloadLen,
                                            NULL, state->userdata);
            if (state->result)
               break;

            ptr += packetLen;
            length -= packetLen;
         }

      } else {
         state->result = LIBUSB_ERROR_IO;
      }
   }

   if (state->result == 0) {
      transfer->status = -1;
      state->result = libusb_submit_transfer(transfer);
   }
}


static double
TimevalDiff(const struct timeval *a, const struct timeval *b)
{
   return (a->tv_sec - b->tv_sec) + 1e-6 * (a->tv_usec - b->tv_usec);
}


/*
 * Use asynchronous transfers in libusb-1.0 for high-performance
 * streaming of data from a device interface back to the PC. This
 * function continuously transfers data until either an error occurs
 * or the callback returns a nonzero value. This function returns
 * a libusb error code or the callback's return value.
 *
 * For every contiguous block of received data, the callback will
 * be invoked.
 */

int
FTDIDevice_ReadStream(FTDIDevice *dev, FTDIInterface interface,
                      FTDIStreamCallback *callback, void *userdata,
                      int packetsPerTransfer, int numTransfers)
{
   struct libusb_transfer **transfers;
   FTDIStreamState state = { callback, userdata };
   int bufferSize = packetsPerTransfer * FTDI_PACKET_SIZE;
   int xferIndex;
   int err = 0;

   /*
    * Set up all transfers
    */

   transfers = calloc(numTransfers, sizeof *transfers);
   if (!transfers) {
      err = LIBUSB_ERROR_NO_MEM;
      goto cleanup;
   }

   for (xferIndex = 0; xferIndex < numTransfers; xferIndex++) {
      struct libusb_transfer *transfer;

      transfer = libusb_alloc_transfer(0);
      transfers[xferIndex] = transfer;
      if (!transfer) {
         err = LIBUSB_ERROR_NO_MEM;
         goto cleanup;
      }

      libusb_fill_bulk_transfer(transfer, dev->handle, FTDI_EP_IN(interface),
                                malloc(bufferSize), bufferSize, (libusb_transfer_cb_fn) ReadStreamCallback,
                                &state, 0);

      if (!transfer->buffer) {
         err = LIBUSB_ERROR_NO_MEM;
         goto cleanup;
      }

      transfer->status = -1;
      err = libusb_submit_transfer(transfer);
      if (err)
         goto cleanup;
   }

   /*
    * Run the transfers, and periodically assess progress.
    */

   gettimeofday(&state.progress.first.time, NULL);

   do {
      FTDIProgressInfo  *progress = &state.progress;
      const double progressInterval = 0.1;
      struct timeval timeout = { 0, 10000 };
      struct timeval now;

      int err = libusb_handle_events_timeout(dev->libusb, &timeout);
      if (!state.result) {
         state.result = err;
      }

      // If enough time has elapsed, update the progress
      gettimeofday(&now, NULL);
      if (TimevalDiff(&now, &progress->current.time) >= progressInterval) {

         progress->current.time = now;

         if (progress->prev.totalBytes) {
            // We have enough information to calculate rates

            double currentTime;

            progress->totalTime = TimevalDiff(&progress->current.time,
                                              &progress->first.time);
            currentTime = TimevalDiff(&progress->current.time,
                                      &progress->prev.time);

            progress->totalRate = progress->current.totalBytes / progress->totalTime;
            progress->currentRate = (progress->current.totalBytes -
                                     progress->prev.totalBytes) / currentTime;
         }

         state.result = state.callback(NULL, 0, progress, state.userdata);
         progress->prev = progress->current;
      }
   } while (!state.result);

   /*
    * Cancel any outstanding transfers, and free memory.
    */

 cleanup:
   if (transfers) {
      bool done_cleanup = false;
      while (!done_cleanup)
      {
          done_cleanup = true;

          for (xferIndex = 0; xferIndex < numTransfers; xferIndex++) {
             struct libusb_transfer *transfer = transfers[xferIndex];

             if (transfer) {
                // If a transfer is in progress, cancel it
                if (transfer->status == -1) {
                   libusb_cancel_transfer(transfer);

                   // And we need to wait until we get a clean sweep
                   done_cleanup = false;

                // If a transfer is complete or cancelled, nuke it
                } else if (transfer->status == 0 ||
                        transfer->status == LIBUSB_TRANSFER_CANCELLED) {
                    free(transfer->buffer);
                    libusb_free_transfer(transfer);
                    transfers[xferIndex] = NULL;
                }
             }
          }

          // pump events
          struct timeval timeout = { 0, 10000 };
          libusb_handle_events_timeout(dev->libusb, &timeout);
      }
      free(transfers);
   }

   if (err)
      return err;
   else
      return state.result;
}

/* MPSSE mode support -- see
 * http://www.ftdichip.com/Support/Documents/AppNotes/AN_108_Command_Processor_for_MPSSE_and_MCU_Host_Bus_Emulation_Modes.pdf
 */

int
FTDIDevice_MPSSE_Enable(FTDIDevice *dev, FTDIInterface interface)
{
  int err;

 /* Reset interface */

  err = FTDIDevice_SetMode(dev, interface, FTDI_BITMODE_RESET, 0, 0);
  if (err)
    return err;

 /* Enable MPSSE mode */

  err = FTDIDevice_SetMode(dev, interface, FTDI_BITMODE_MPSSE,
    FTDI_SET_BITMODE_REQUEST, 0);

  return err;
}

int
FTDIDevice_MPSSE_SetDivisor(FTDIDevice *dev, FTDIInterface interface,
                   uint8_t ValueL, uint8_t ValueH)
{
  uint8_t buf[3] = {FTDI_MPSSE_SETDIVISOR, 0, 0};

  buf[1] = ValueL;
  buf[2] = ValueH;

  return FTDIDevice_Write(dev, interface, buf, 3, false);
}

int
FTDIDevice_MPSSE_SetLowByte(FTDIDevice *dev, FTDIInterface interface, uint8_t data, uint8_t dir)
{
  uint8_t buf[3] = {FTDI_MPSSE_SETLOW, 0, 0};

  buf[1] = data;
  buf[2] = dir;

  return FTDIDevice_Write(dev, interface, buf, 3, false);
}

int
FTDIDevice_MPSSE_SetHighByte(FTDIDevice *dev, FTDIInterface interface, uint8_t data, uint8_t dir)
{
  uint8_t buf[3] = {FTDI_MPSSE_SETHIGH, 0, 0};

  buf[1] = data;
  buf[2] = dir;

  return FTDIDevice_Write(dev, interface, buf, 3, false);
}

int
FTDIDevice_MPSSE_GetLowByte(FTDIDevice *dev, FTDIInterface interface, uint8_t *byte)
{
  int err;

  err = FTDIDevice_WriteByteSync(dev, interface, FTDI_MPSSE_GETLOW);
  if (err)
    return err;

  return FTDIDevice_ReadByteSync(dev, interface, byte);
}

int
FTDIDevice_MPSSE_GetHighByte(FTDIDevice *dev, FTDIInterface interface, uint8_t *byte)
{
  int err;

  err = FTDIDevice_WriteByteSync(dev, interface, FTDI_MPSSE_GETHIGH);
  if (err)
    return err;

  return FTDIDevice_ReadByteSync(dev, interface, byte);
}
