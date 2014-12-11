fis_types = {
	"REG_H2D":          0x27,
	"REG_D2H":          0x34,
	"DMA_ACTIVATE_D2H": 0x39,
	"DMA_SETUP":        0x41,
	"DATA":             0x46,
	"PIO_SETUP_D2H":    0x5F
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

fis_dma_setup_cmd_len = 7
fis_dma_setup_layout = {
	"type":               FISField(0,  0, 8),
	"pm_port":            FISField(0,  8, 4),
	"d":                  FISField(0, 13, 1),
	"i":                  FISField(0, 14, 1),
	"a":                  FISField(0, 15, 1),

	"dma_buffer_id_low":  FISField(1, 0, 32),

	"dma_buffer_id_high": FISField(2, 0, 32),

	"dma_buffer_offset":  FISField(4, 0, 32),

	"dma_transfer_count": FISField(4, 0, 32)
}

fis_data_cmd_len = 1
fis_data_layout = {
	"type": FISField(0,  0, 8)
}

fis_pio_setup_d2h_len = 5
fis_pio_setup_d2h_layout = {
	"type":           FISField(0,  0, 8),
	"pm_port":        FISField(0,  8, 4),
	"d":              FISField(0, 13, 1),
	"i":              FISField(0, 14, 1),
	"status":         FISField(0, 16, 8),
	"error":          FISField(0, 24, 8),

	"lba_lsb":        FISField(1, 0, 24),
	"device":         FISField(1, 24, 8),

	"lba_msb":        FISField(2, 0, 24),

	"count":          FISField(3, 0, 16),
	"e_status":       FISField(3, 24, 8),

	"transfer_count": FISField(4, 0, 16)
}
