# Introduction to Wishbone Bus in LiteX SoCs

One of the key components of a LiteX SoC is the bus system, which is used to connect the various components of the SoC and one of the default and probably most popular bus systems used in LiteX SoCs is the... Wishbone bus :).

## Overview of Wishbone Bus

The Wishbone bus is a standardized, open-source bus system that is widely used in FPGA-based SoCs. It was originally developed as part of the OpenCores project and has since become a standard for inter-component communication in FPGA-based systems.

The Wishbone bus provides a simple, flexible, and scalable bus architecture that makes it easy to connect and communicate between different components in an SoC. The Wishbone bus specification defines a standard interface for communication between components, allowing components from different vendors to be easily combined in a single SoC.

The Wishbone bus API in LiteX provides a convenient and straightforward way to work with the Wishbone bus in a LiteX SoC.

## How Wishbone Bus Works in LiteX SoCs

In a LiteX SoC, the Wishbone bus provides a communication channel between the different components of the SoC. Each component that wants to participate in the bus must implement a Wishbone slave interface, which provides access to the component's registers and memory. The Wishbone bus masters, such as a processor, can then read from or write to the slave components using the Wishbone slave interface.

Wishbone transactions are initiated by the bus master and consist of a request for data (read) or a request to write data (write). The transaction includes the address of the target component's slave interface and the data to be read or written. The slave component responds with the requested data in the case of a read transaction, or acknowledges the write transaction.

## Wishbone Bus Example in LiteX SoCs

Here is a concrete example of how the Wishbone bus can be used in a LiteX SoC. Suppose we want to design an SoC that contains a processor and a memory module, and we want to use the Wishbone bus to connect the two components.

`TODO`
