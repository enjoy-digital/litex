from migen.fhdl.std import *
from migen.genlib.record import *
from migen.flow.actor import *

primitives = {
	"ALIGN"	:	0x7B4A4ABC,
	"CONT"	: 	0X9999AA7C,
	"SYNC"	:	0xB5B5957C,
	"R_RDY"	:	0x4A4A957C,
	"R_OK"	:	0x3535B57C,
	"R_ERR"	:	0x5656B57C,
	"R_IP"	:	0X5555B57C,
	"X_RDY"	:	0x5757B57C,
	"CONT"	:	0x9999AA7C,
	"WTRM"	:	0x5858B57C,
	"SOF"	:	0x3737B57C,
	"EOF"	:	0xD5D5B57C,
	"HOLD"	:	0xD5D5AA7C,
	"HOLDA"	: 	0X9595AA7C
}

def is_primitive(dword):
	for k, v in primitives.items():
		if dword == v:
			return True
	return False

def decode_primitive(dword):
	for k, v in primitives.items():
		if dword == v:
			return k
	return ""

def ones(width):
	return 2**width-1

def phy_layout(dw):
	layout = [
		("data", dw),
		("charisk", dw//8),
	]
	return EndpointDescription(layout, packetized=False)

def link_layout(dw):
	layout = [
		("d", dw),
		("error", 1)
	]
	return EndpointDescription(layout, packetized=True)

def transport_cmd_tx_layout():
	layout = [
		("type", 8),
		("pm_port", 4),
		("a", 1),
		("c", 1),
		("d", 1),
		("i", 1),
		("command", 8),
		("features", 16),
		("lba", 48),
		("device", 8),
		("count", 16),
		("icc", 8),
		("control", 8),
		("dma_buffer_id", 64),
		("dma_buffer_offset", 32),
		("dma_transfer_count", 32),
	]
	return EndpointDescription(layout, packetized=False)

def transport_cmd_rx_layout():
	layout = [
		("type", 8),
		("pm_port", 4),
		("a", 1),
		("d", 1),
		("i", 1),
		("status", 8),
		("error", 8),
		("lba", 48),
		("device", 8),
		("count", 16),
		("e_status", 8),
		("transfer_count", 16),
		("dma_buffer_id", 64),
		("dma_buffer_offset", 32),
		("dma_transfer_count", 32)
	]
	return EndpointDescription(layout, packetized=False)

def transport_data_layout(dw):
	layout = [
		("d", dw)
	]
	return EndpointDescription(layout, packetized=True)
