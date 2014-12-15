from migen.fhdl.std import *
from migen.genlib.record import *
from migen.flow.actor import *

# PHY / Link Layers
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

def phy_description(dw):
	layout = [
		("data", dw),
		("charisk", dw//8),
	]
	return EndpointDescription(layout, packetized=False)

def link_description(dw):
	layout = [
		("d", dw),
		("error", 1)
	]
	return EndpointDescription(layout, packetized=True)

# Transport Layer
fis_types = {
	"REG_H2D":          0x27,
	"REG_D2H":          0x34,
	"DMA_ACTIVATE_D2H": 0x39,
	"DATA":             0x46
}

class FISField():
	def __init__(self, dword, offset, width):
		self.dword = dword
		self.offset = offset
		self.width = width

fis_reg_h2d_cmd_len = 5
fis_reg_h2d_layout = {
	"type":         FISField(0,  0, 8),
	"pm_port":      FISField(0,  8, 4),
	"c":            FISField(0, 15, 1),
	"command":      FISField(0, 16, 8),
	"features_lsb": FISField(0, 24, 8),

	"lba_lsb":      FISField(1, 0, 24),
	"device":       FISField(1, 24, 8),

	"lba_msb":      FISField(2, 0, 24),
	"features_msb": FISField(2, 24, 8),

	"count":        FISField(3, 0, 16),
	"icc":          FISField(3, 16, 8),
	"control":      FISField(3, 24, 8)
}

fis_reg_d2h_cmd_len = 5
fis_reg_d2h_layout = {
	"type":    FISField(0,  0, 8),
	"pm_port": FISField(0,  8, 4),
	"i":       FISField(0, 14, 1),
	"status":  FISField(0, 16, 8),
	"error":   FISField(0, 24, 8),

	"lba_lsb": FISField(1, 0, 24),
	"device":  FISField(1, 24, 8),

	"lba_msb": FISField(2, 0, 24),

	"count":   FISField(3, 0, 16)
}

fis_dma_activate_d2h_cmd_len = 1
fis_dma_activate_d2h_layout = {
	"type":    FISField(0,  0, 8),
	"pm_port": FISField(0,  8, 4)
}

fis_data_cmd_len = 1
fis_data_layout = {
	"type": FISField(0,  0, 8)
}

def transport_tx_description(dw):
	layout = [
		("type", 8),
		("pm_port", 4),
		("c", 1),
		("command", 8),
		("features", 16),
		("lba", 48),
		("device", 8),
		("count", 16),
		("icc", 8),
		("control", 8),
		("data", dw)
	]
	return EndpointDescription(layout, packetized=True)

def transport_rx_description(dw):
	layout = [
		("type", 8),
		("pm_port", 4),
		("i", 1),
		("status", 8),
		("error", 8),
		("lba", 48),
		("device", 8),
		("count", 16),
		("data", dw)
	]
	return EndpointDescription(layout, packetized=True)

# Command Layer
regs = {
	"WRITE_DMA_EXT"			: 0x35,
	"READ_DMA_EXT"			: 0x25,
	"IDENTIFY_DEVICE_DMA"	: 0xEE
}

def command_tx_description(dw):
	layout = [
		("write", 1),
		("read", 1),
		("identify", 1),
		("sector", 48),
		("count", 4),
		("data", dw)
	]
	return EndpointDescription(layout, packetized=True)

def command_rx_description(dw):
	layout = [
		("write", 1),
		("read", 1),
		("identify", 1),
		("success", 1),
		("failed", 1),
		("data", dw)
	]
	return EndpointDescription(layout, packetized=True)
