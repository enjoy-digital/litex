from migen.fhdl.std import *
from migen.genlib.cdc import *
from migen.actorlib.fifo import AsyncFIFO
from migen.actorlib.structuring import Converter
from migen.flow.actor import Sink, Source

from lib.sata.k7sataphy.std import *

class _PulseSynchronizer(PulseSynchronizer):
	def __init__(self, i, idomain, o, odomain):
		PulseSynchronizer.__init__(self, idomain, odomain)
		self.comb += [
			self.i.eq(i),
			o.eq(self.o)
		]

class K7SATAPHYGTX(Module):
	def __init__(self, pads, default_speed):
	# Interface
		self.drp = DRPBus()

		# Channel - Ref Clock Ports
		self.gtrefclk0 = Signal()

		# Channel PLL
		self.cplllock = Signal()
		self.cpllreset = Signal()

		# Receive Ports
		self.rxuserrdy = Signal()
		self.rxalign = Signal()

		# Receive Ports - 8b10b Decoder
		self.rxcharisk = Signal(2)
		self.rxdisperr = Signal(2)

		# Receive Ports - RX Data Path interface
		self.gtrxreset = Signal()
		self.rxdata = Signal(16)
		self.rxoutclk = Signal()
		self.rxusrclk = Signal()
		self.rxusrclk2 = Signal()

		# Receive Ports - RX Driver,OOB signalling,Coupling and Eq.,CDR
		self.rxelecidle = Signal()

		# Receive Ports - RX Elastic Buffer and Phase Alignment Ports
		self.rxdlyen = Signal()
		self.rxdlysreset = Signal()
		self.rxdlysresetdone = Signal()
		self.rxphalign = Signal()
		self.rxphaligndone = Signal()
		self.rxphalignen = Signal()
		self.rxphdlyreset = Signal()

		# Receive Ports - RX PLL Ports
		self.rxresetdone = Signal()

		# Receive Ports - RX Ports for SATA
		self.rxcominitdet = Signal()
		self.rxcomwakedet = Signal()

		# Transmit Ports
		self.txuserrdy = Signal()

		# Transmit Ports - 8b10b Encoder Control Ports
		self.txcharisk = Signal(2)

		# Transmit Ports - TX Buffer and Phase Alignment Ports
		self.txdlyen = Signal()
		self.txdlysreset = Signal()
		self.txdlysresetdone = Signal()
		self.txphalign = Signal()
		self.txphaligndone = Signal()
		self.txphalignen = Signal()
		self.txphdlyreset = Signal()
		self.txphinit = Signal()
		self.txphinitdone = Signal()

		# Transmit Ports - TX Data Path interface
		self.gttxreset = Signal()
		self.txdata = Signal(16)
		self.txoutclk = Signal()
		self.txusrclk = Signal()
		self.txusrclk2 = Signal()

		# Transmit Ports - TX PLL Ports
		self.txresetdone = Signal()

		# Transmit Ports - TX Ports for PCI Express
		self.txelecidle = Signal(reset=1)

		# Transmit Ports - TX Ports for SATA
		self.txcomfinish = Signal()
		self.txcominit = Signal()
		self.txcomwake = Signal()
		self.rxrate = Signal(3)
		self.rxratedone = Signal()
		self.txrate = Signal(3)
		self.txratedone = Signal()

	# Config at startup
		div_config = {
			"SATA1" : 	4,
			"SATA2" :	2,
			"SATA3" : 	1
			}
		rxout_div = div_config[default_speed]
		txout_div = div_config[default_speed]

		cdr_config = {
			"SATA1" :	0x0380008BFF40100008,
			"SATA2" :	0x0380008BFF40200008,
			"SATA3" :	0X0380008BFF20200010
		}
		rxcdr_cfg = cdr_config[default_speed]

	# Internals and clock domain crossing
		# sys_clk --> sata_tx clk
		txuserrdy = Signal()
		txdlyen = Signal()
		txdlysreset = Signal()
		txphalign = Signal()
		txphalignen = Signal()
		txphdlyreset = Signal()
		txphinit = Signal()
		txelecidle = Signal(reset=1)
		txcominit = Signal()
		txcomwake = Signal()
		txrate = Signal(3)

		self.specials += [
			MultiReg(self.txuserrdy, txuserrdy, "sata_tx"),
			MultiReg(self.txdlyen, txdlyen, "sata_tx"),
			MultiReg(self.txdlysreset, txdlysreset, "sata_tx"),
			MultiReg(self.txphalign, txphalign, "sata_tx"),
			MultiReg(self.txphalignen, txphalignen, "sata_tx"),
			MultiReg(self.txphdlyreset, txphdlyreset, "sata_tx"),
			MultiReg(self.txelecidle, txelecidle, "sata_tx"),
			MultiReg(self.txrate, txrate, "sata_tx")
		]
		self.submodules += [
			_PulseSynchronizer(self.txcominit, "sys", txcominit, "sata_tx"),
			_PulseSynchronizer(self.txcomwake, "sys", txcomwake, "sata_tx"),
		]

		# sata_tx clk --> sys clk
		txdlysresetdone = Signal()
		txphaligndone = Signal()
		txphinitdone = Signal()
		txresetdone = Signal()
		txratedone = Signal()
		txcomfinish = Signal()

		self.specials += [
			MultiReg(txdlysresetdone, self.txdlysresetdone, "sys"),
			MultiReg(txphaligndone, self.txphaligndone, "sys"),
			MultiReg(txphinitdone, self.txphinitdone, "sys"),
			MultiReg(txresetdone, self.txresetdone, "sys"),
			MultiReg(txratedone, self.txratedone, "sys"),
		]

		self.submodules += [
			_PulseSynchronizer(txcomfinish, "sata_tx", self.txcomfinish, "sys"),
		]	

		# sys clk --> sata_rx clk
		rxuserrdy = Signal()
		rxelecidle = Signal()
		rxdlyen = Signal()
		rxdlysreset = Signal()
		rxphalign = Signal()
		rxphalignen = Signal()
		rxphdlyreset = Signal()
		rxrate = Signal(3)
		rxalign = Signal()

		self.specials += [
			MultiReg(self.rxuserrdy, rxuserrdy, "sata_rx"),
			MultiReg(self.rxelecidle, rxelecidle, "sata_rx"),
			MultiReg(self.rxdlyen, rxdlyen, "sata_rx"),
			MultiReg(self.rxdlysreset, rxdlysreset, "sata_rx"),
			MultiReg(self.rxphalign, rxphalign, "sata_rx"),
			MultiReg(self.rxphalignen, rxphalignen, "sata_rx"),
			MultiReg(self.rxphdlyreset, rxphdlyreset, "sata_rx"),
			MultiReg(self.rxrate, rxrate, "sata_rx"),
			MultiReg(self.rxalign, rxalign, "sata_rx"),
		]


		# sata_rx clk --> sys clk
		rxdlysresetdone = Signal()
		rxphaligndone = Signal()
		rxresetdone = Signal()
		rxcominitdet = Signal()
		rxcomwakedet = Signal()
		rxratedone = Signal()

		self.specials += [
			MultiReg(rxdlysresetdone, self.rxdlysresetdone, "sys"),
			MultiReg(rxphaligndone, self.rxphaligndone, "sys"),
			MultiReg(rxresetdone, self.rxresetdone, "sys"),
			MultiReg(rxratedone, self.rxratedone, "sys")
		]

		self.submodules += [
			_PulseSynchronizer(rxcominitdet, "sata_rx", self.rxcominitdet, "sys"),
			_PulseSynchronizer(rxcomwakedet, "sata_rx", self.rxcomwakedet, "sys"),
		]	


		self.rxbyteisaligned = Signal()
		self.rxbyterealign = Signal()
		self.rxcommadet = Signal()

	# Instance
		gtxe2_channel_parameters = {
				# Simulation-Only Attributes
					"p_SIM_RECEIVER_DETECT_PASS":"TRUE",
					"p_SIM_TX_EIDLE_DRIVE_LEVEL":"X",
					"p_SIM_RESET_SPEEDUP":"TRUE",
					"p_SIM_CPLLREFCLK_SEL":0b001,
					"p_SIM_VERSION":"4.0",

				# RX Byte and Word Alignment Attributes
					"p_ALIGN_COMMA_DOUBLE":"FALSE",
					"p_ALIGN_COMMA_ENABLE":ones(10),
					"p_ALIGN_COMMA_WORD":2,
					"p_ALIGN_MCOMMA_DET":"TRUE",
					"p_ALIGN_MCOMMA_VALUE":0b1010000011,
					"p_ALIGN_PCOMMA_DET":"TRUE",
					"p_ALIGN_PCOMMA_VALUE":0b0101111100,
					"p_SHOW_REALIGN_COMMA":"FALSE",
					"p_RXSLIDE_AUTO_WAIT":7,
					"p_RXSLIDE_MODE":"OFF",
					"p_RX_SIG_VALID_DLY":10,

				# RX 8B/10B Decoder Attributes
					"p_RX_DISPERR_SEQ_MATCH":"TRUE",
					"p_DEC_MCOMMA_DETECT":"TRUE",
					"p_DEC_PCOMMA_DETECT":"TRUE",
					"p_DEC_VALID_COMMA_ONLY":"TRUE",

				# RX Clock Correction Attributes
					"p_CBCC_DATA_SOURCE_SEL":"DECODED",
					"p_CLK_COR_SEQ_2_USE":"FALSE",
					"p_CLK_COR_KEEP_IDLE":"FALSE",
					"p_CLK_COR_MAX_LAT":9,
					"p_CLK_COR_MIN_LAT":7,
					"p_CLK_COR_PRECEDENCE":"TRUE",
					"p_CLK_COR_REPEAT_WAIT":0,
					"p_CLK_COR_SEQ_LEN":1,
					"p_CLK_COR_SEQ_1_ENABLE":ones(4),
					"p_CLK_COR_SEQ_1_ENABLE":0,
					"p_CLK_COR_SEQ_1_1":0,
					"p_CLK_COR_SEQ_1_1":0,
					"p_CLK_COR_SEQ_1_2":0,
					"p_CLK_COR_SEQ_1_3":0,
					"p_CLK_COR_SEQ_1_4":0,
					"p_CLK_CORRECT_USE":"FALSE",
					"p_CLK_COR_SEQ_2_ENABLE":ones(4),
					"p_CLK_COR_SEQ_2_1":0,
					"p_CLK_COR_SEQ_2_2":0,
					"p_CLK_COR_SEQ_2_3":0,
					"p_CLK_COR_SEQ_2_4":0,

				# RX Channel Bonding Attributes
					"p_CHAN_BOND_KEEP_ALIGN":"FALSE",
					"p_CHAN_BOND_MAX_SKEW":1,
					"p_CHAN_BOND_SEQ_LEN":1,
					"p_CHAN_BOND_SEQ_1_1":0,
					"p_CHAN_BOND_SEQ_1_1":0,
					"p_CHAN_BOND_SEQ_1_2":0,
					"p_CHAN_BOND_SEQ_1_3":0,
					"p_CHAN_BOND_SEQ_1_4":0,
					"p_CHAN_BOND_SEQ_1_ENABLE":ones(4),
					"p_CHAN_BOND_SEQ_2_1":0,
					"p_CHAN_BOND_SEQ_2_2":0,
					"p_CHAN_BOND_SEQ_2_3":0,
					"p_CHAN_BOND_SEQ_2_4":0,
					"p_CHAN_BOND_SEQ_2_ENABLE":ones(4),
					"p_CHAN_BOND_SEQ_2_USE":"FALSE",
					"p_FTS_DESKEW_SEQ_ENABLE":ones(4),
					"p_FTS_LANE_DESKEW_CFG":ones(4),
					"p_FTS_LANE_DESKEW_EN":"FALSE",

				# RX Margin Analysis Attributes
					"p_ES_CONTROL":0,
					"p_ES_ERRDET_EN":"FALSE",
					"p_ES_EYE_SCAN_EN":"TRUE",
					"p_ES_HORZ_OFFSET":0,
					"p_ES_PMA_CFG":0,
					"p_ES_PRESCALE":0,
					"p_ES_QUALIFIER":0,
					"p_ES_QUAL_MASK":0,
					"p_ES_SDATA_MASK":0,
					"p_ES_VERT_OFFSET":0,

				# FPGA RX Interface Attributes
					"p_RX_DATA_WIDTH":20,

				# PMA Attributes
					"p_OUTREFCLK_SEL_INV":0b11,
					"p_PMA_RSV":0x00018480,
					"p_PMA_RSV2":0x2050,
					"p_PMA_RSV3":0,
					"p_PMA_RSV4":0,
					"p_RX_BIAS_CFG":0b100,
					"p_DMONITOR_CFG":0xA00,
					"p_RX_CM_SEL":0b11,
					"p_RX_CM_TRIM":0b010,
					"p_RX_DEBUG_CFG":0,
					"p_RX_OS_CFG":0b10000000,
					"p_TERM_RCAL_CFG":0,
					"p_TERM_RCAL_OVRD":0,
					"p_TST_RSV":0,
					"p_RX_CLK25_DIV":6,
					"p_TX_CLK25_DIV":6,
					"p_UCODEER_CLR":0,

				# PCI Express Attributes
					"p_PCS_PCIE_EN":"FALSE",

				# PCS Attributes
					"p_PCS_RSVD_ATTR":0x100,

				# RX Buffer Attributes
					"p_RXBUF_ADDR_MODE":"FAST",
					"p_RXBUF_EIDLE_HI_CNT":0b1000,
					"p_RXBUF_EIDLE_LO_CNT":0,
					"p_RXBUF_EN":"FALSE",
					"p_RX_BUFFER_CFG":0,
					"p_RXBUF_RESET_ON_CB_CHANGE":"TRUE",
					"p_RXBUF_RESET_ON_COMMAALIGN":"FALSE",
					"p_RXBUF_RESET_ON_EIDLE":"FALSE",
					"p_RXBUF_RESET_ON_RATE_CHANGE":"TRUE",
					"p_RXBUFRESET_TIME":1,
					"p_RXBUF_THRESH_OVFLW":61,
					"p_RXBUF_THRESH_OVRD":"FALSE",
					"p_RXBUF_THRESH_UNDFLW":4,
					"p_RXDLY_CFG":0x1f,
					"p_RXDLY_LCFG":0x30,
					"p_RXDLY_TAP_CFG":0,
					"p_RXPH_CFG":0,
					"p_RXPHDLY_CFG":0x084820,
					"p_RXPH_MONITOR_SEL":0,
					"p_RX_XCLK_SEL":"RXUSR",
					"p_RX_DDI_SEL":0,
					"p_RX_DEFER_RESET_BUF_EN":"TRUE",

				#CDR Attributes
					"p_RXCDR_CFG":rxcdr_cfg,
					"p_RXCDR_FR_RESET_ON_EIDLE":0,
					"p_RXCDR_HOLD_DURING_EIDLE":0,
					"p_RXCDR_PH_RESET_ON_EIDLE":0,
					"p_RXCDR_LOCK_CFG":0b010101,

				# RX Initialization and Reset Attributes
					"p_RXCDRFREQRESET_TIME":1,
					"p_RXCDRPHRESET_TIME":1,
					"p_RXISCANRESET_TIME":1,
					"p_RXPCSRESET_TIME":1,
					"p_RXPMARESET_TIME":3,

				# RX OOB Signaling Attributes
					"p_RXOOB_CFG":0b0000110,

				# RX Gearbox Attributes
					"p_RXGEARBOX_EN":"FALSE",
					"p_GEARBOX_MODE":0,

				# PRBS Detection Attribute
					"p_RXPRBS_ERR_LOOPBACK":0,

				# Power-Down Attributes
					"p_PD_TRANS_TIME_FROM_P2":0x03c,
					"p_PD_TRANS_TIME_NONE_P2":0x3c,
					"p_PD_TRANS_TIME_TO_P2":0x64,

				# RX OOB Signaling Attributes
					"p_SAS_MAX_COM":64,
					"p_SAS_MIN_COM":36,
					"p_SATA_BURST_SEQ_LEN":0b0101,
					"p_SATA_BURST_VAL":0b100,
					"p_SATA_EIDLE_VAL":0b100,
					"p_SATA_MAX_BURST":8,
					"p_SATA_MAX_INIT":21,
					"p_SATA_MAX_WAKE":7,
					"p_SATA_MIN_BURST":4,
					"p_SATA_MIN_INIT":12,
					"p_SATA_MIN_WAKE":4,

				# RX Fabric Clock Output Control Attributes
					"p_TRANS_TIME_RATE":0x0e,

				# TX Buffer Attributes
					"p_TXBUF_EN":"FALSE",
					"p_TXBUF_RESET_ON_RATE_CHANGE":"FALSE",
					"p_TXDLY_CFG":0x1f,
					"p_TXDLY_LCFG":0x030,
					"p_TXDLY_TAP_CFG":0,
					"p_TXPH_CFG":0x0780,
					"p_TXPHDLY_CFG":0x084020,
					"p_TXPH_MONITOR_SEL":0,
					"p_TX_XCLK_SEL":"TXUSR",

				# FPGA TX Interface Attributes
					"p_TX_DATA_WIDTH":20,

				# TX Configurable Driver Attributes
					"p_TX_DEEMPH0":0,
					"p_TX_DEEMPH1":0,
					"p_TX_EIDLE_ASSERT_DELAY":0b110,
					"p_TX_EIDLE_DEASSERT_DELAY":0b100,
					"p_TX_LOOPBACK_DRIVE_HIZ":"FALSE",
					"p_TX_MAINCURSOR_SEL":0,
					"p_TX_DRIVE_MODE":"DIRECT",
					"p_TX_MARGIN_FULL_0":0b1001110,
					"p_TX_MARGIN_FULL_1":0b1001001,
					"p_TX_MARGIN_FULL_2":0b1000101,
					"p_TX_MARGIN_FULL_3":0b1000010,
					"p_TX_MARGIN_FULL_4":0b1000000,
					"p_TX_MARGIN_LOW_0":0b1000110,
					"p_TX_MARGIN_LOW_1":0b1000100,
					"p_TX_MARGIN_LOW_2":0b1000010,
					"p_TX_MARGIN_LOW_3":0b1000000,
					"p_TX_MARGIN_LOW_4":0b1000000,

				# TX Gearbox Attributes
					"p_TXGEARBOX_EN":"FALSE",

				# TX Initialization and Reset Attributes
					"p_TXPCSRESET_TIME":1,
					"p_TXPMARESET_TIME":1,

				# TX Receiver Detection Attributes
					"p_TX_RXDETECT_CFG":0x1832,
					"p_TX_RXDETECT_REF":0b100,

				# CPLL Attributes
					"p_CPLL_CFG":0xBC07DC,
					"p_CPLL_FBDIV":4,
					"p_CPLL_FBDIV_45":5,
					"p_CPLL_INIT_CFG":0x00001e,
					"p_CPLL_LOCK_CFG":0x01e8,
					"p_CPLL_REFCLK_DIV":1,
					"p_RXOUT_DIV":rxout_div,
					"p_TXOUT_DIV":txout_div,
					"p_SATA_CPLL_CFG":"VCO_3000MHZ",

				# RX Initialization and Reset Attributes
					"p_RXDFELPMRESET_TIME":0b0001111,

				# RX Equalizer Attributes
					"p_RXLPM_HF_CFG":0b00000011110000,
					"p_RXLPM_LF_CFG":0b00000011110000,
					"p_RX_DFE_GAIN_CFG":0x020fea,
					"p_RX_DFE_H2_CFG":0b000000000000,
					"p_RX_DFE_H3_CFG":0b000001000000,
					"p_RX_DFE_H4_CFG":0b00011110000,
					"p_RX_DFE_H5_CFG":0b00011100000,
					"p_RX_DFE_KL_CFG":0b0000011111110,
					"p_RX_DFE_LPM_CFG":0x0954,
					"p_RX_DFE_LPM_HOLD_DURING_EIDLE":1,
					"p_RX_DFE_UT_CFG":0b10001111000000000,
					"p_RX_DFE_VP_CFG":0b00011111100000011,

				# Power-Down Attributes
					"p_RX_CLKMUX_PD":1,
					"p_TX_CLKMUX_PD":1,

				# FPGA RX Interface Attribute
					"p_RX_INT_DATAWIDTH":0,

				# FPGA TX Interface Attribute
					"p_TX_INT_DATAWIDTH":0,

				# TX Configurable Driver Attributes
					"p_TX_QPI_STATUS_EN":0,

				# RX Equalizer Attributes
					"p_RX_DFE_KL_CFG2":0b00110011000100000001100000001100,
					"p_RX_DFE_XYD_CFG":0b0000000000000,

				# TX Configurable Driver Attributes
					"p_TX_PREDRIVER_MODE":0,
			}

		self.specials += \
			Instance("GTXE2_CHANNEL",
				# CPLL Ports
					#o_CPLLFBCLKLOST=,
					o_CPLLLOCK=self.cplllock,
					i_CPLLLOCKDETCLK=0,
					i_CPLLLOCKEN=1,
					i_CPLLPD=0,
					#o_CPLLREFCLKLOST=0,
					i_CPLLREFCLKSEL=0b001,
					i_CPLLRESET=self.cpllreset,
					i_GTRSVD=0,
					i_PCSRSVDIN=0,
					i_PCSRSVDIN2=0,
					i_PMARSVDIN=0,
					i_PMARSVDIN2=0,
					i_TSTIN=ones(20),
					#o_TSTOUT=,

				# Channel
					i_CLKRSVD=0,

				# Channel - Clocking Ports
					i_GTGREFCLK=0,
					i_GTNORTHREFCLK0=0,
					i_GTNORTHREFCLK1=0,
					i_GTREFCLK0=self.gtrefclk0,
					i_GTREFCLK1=0,
					i_GTSOUTHREFCLK0=0,
					i_GTSOUTHREFCLK1=0,

				# Channel - DRP Ports
					i_DRPADDR=self.drp.addr,
					i_DRPCLK=self.drp.clk,
					i_DRPDI=self.drp.di,
					o_DRPDO=self.drp.do,
					i_DRPEN=self.drp.en,
					o_DRPRDY=self.drp.rdy,
					i_DRPWE=self.drp.we,

				# Clocking Ports
					#o_GTREFCLKMONITOR=,
					i_QPLLCLK=0,
					i_QPLLREFCLK=0,
					i_RXSYSCLKSEL=0b00,
					i_TXSYSCLKSEL=0b00,

				# Digital Monitor Ports
					#o_DMONITOROUT=,

				# FPGA TX Interface Datapath Configuration
					i_TX8B10BEN=1,

				# Loopback Ports
					i_LOOPBACK=0,

				# PCI Express Ports
					#o_PHYSTATUS=,
					i_RXRATE=rxrate,
					#o_RXVALID=,

				# Power-Down Ports
					i_RXPD=0b00,
					i_TXPD=0b00,

				# RX 8B/10B Decoder Ports
					i_SETERRSTATUS=0,

				# RX Initialization and Reset Ports
					i_EYESCANRESET=0,
					i_RXUSERRDY=rxuserrdy,

				# RX Margin Analysis Ports
					#o_EYESCANDATAERROR=,
					i_EYESCANMODE=0,
					i_EYESCANTRIGGER=0,

				# Receive Ports - CDR Ports
					i_RXCDRFREQRESET=0,
					i_RXCDRHOLD=0,
					#o_RXCDRLOCK=,
					i_RXCDROVRDEN=0,
					i_RXCDRRESET=0,
					i_RXCDRRESETRSV=0,

				# Receive Ports - Clock Correction Ports
					#o_RXCLKCORCNT=,

				# Receive Ports - FPGA RX Interface Datapath Configuration
					i_RX8B10BEN=1,

				# Receive Ports - FPGA RX Interface Ports
					i_RXUSRCLK=self.rxusrclk,
					i_RXUSRCLK2=self.rxusrclk2,

				# Receive Ports - FPGA RX interface Ports
					o_RXDATA=self.rxdata,

				# Receive Ports - Pattern Checker Ports
					#o_RXPRBSERR=,
					i_RXPRBSSEL=0,

				# Receive Ports - Pattern Checker ports
					i_RXPRBSCNTRESET=0,

				# Receive Ports - RX  Equalizer Ports
					i_RXDFEXYDEN=0,
					i_RXDFEXYDHOLD=0,
					i_RXDFEXYDOVRDEN=0,

				# Receive Ports - RX 8B/10B Decoder Ports
					#o_RXDISPERR=,
					#o_RXNOTINTABLE=,

				# Receive Ports - RX AFE
					i_GTXRXP=pads.rxp,
					i_GTXRXN=pads.rxn,

				# Receive Ports - RX Buffer Bypass Ports
					i_RXBUFRESET=0,
					#o_RXBUFSTATUS=,
					i_RXDDIEN=1,
					i_RXDLYBYPASS=0,
					i_RXDLYEN=rxdlyen,
					i_RXDLYOVRDEN=0,
					i_RXDLYSRESET=rxdlysreset,
					o_RXDLYSRESETDONE=rxdlysresetdone,
					i_RXPHALIGN=rxphalign,
					o_RXPHALIGNDONE=rxphaligndone,
					i_RXPHALIGNEN=rxphalignen,
					i_RXPHDLYPD=0,
					i_RXPHDLYRESET=rxphdlyreset,
					#o_RXPHMONITOR=,
					i_RXPHOVRDEN=0,
					#o_RXPHSLIPMONITOR=,
					#o_RXSTATUS=,

				# Receive Ports - RX Byte and Word Alignment Ports
					o_RXBYTEISALIGNED=self.rxbyteisaligned,
					o_RXBYTEREALIGN=self.rxbyterealign,
					o_RXCOMMADET=self.rxcommadet,
					i_RXCOMMADETEN=1,
					i_RXMCOMMAALIGNEN=rxalign,
					i_RXPCOMMAALIGNEN=rxalign,

				# Receive Ports - RX Channel Bonding Ports
					#o_RXCHANBONDSEQ=,
					i_RXCHBONDEN=0,
					i_RXCHBONDLEVEL=0,
					i_RXCHBONDMASTER=0,
					#o_RXCHBONDO=,
					i_RXCHBONDSLAVE=0,

				# Receive Ports - RX Channel Bonding Ports
					#o_RXCHANISALIGNED=,
					#o_RXCHANREALIGN=,

				# Receive Ports - RX Equalizer Ports
					i_RXDFEAGCHOLD=0,
					i_RXDFEAGCOVRDEN=0,
					i_RXDFECM1EN=0,
					i_RXDFELFHOLD=0,
					i_RXDFELFOVRDEN=1,
					i_RXDFELPMRESET=0,
					i_RXDFETAP2HOLD=0,
					i_RXDFETAP2OVRDEN=0,
					i_RXDFETAP3HOLD=0,
					i_RXDFETAP3OVRDEN=0,
					i_RXDFETAP4HOLD=0,
					i_RXDFETAP4OVRDEN=0,
					i_RXDFETAP5HOLD=0,
					i_RXDFETAP5OVRDEN=0,
					i_RXDFEUTHOLD=0,
					i_RXDFEUTOVRDEN=0,
					i_RXDFEVPHOLD=0,
					i_RXDFEVPOVRDEN=0,
					i_RXDFEVSEN=0,
					i_RXLPMLFKLOVRDEN=0,
					#o_RXMONITOROUT=,
					i_RXMONITORSEL=0b00,
					i_RXOSHOLD=0,
					i_RXOSOVRDEN=0,

				# Receive Ports - RX Equilizer Ports
					i_RXLPMHFHOLD=0,
					i_RXLPMHFOVRDEN=0,
					i_RXLPMLFHOLD=0,

				# Receive Ports - RX Fabric ClocK Output Control Ports
					o_RXRATEDONE=rxratedone,

				# Receive Ports - RX Fabric Output Control Ports
					o_RXOUTCLK=self.rxoutclk,
					#o_RXOUTCLKFABRIC=,
					#o_RXOUTCLKPCS=,
					i_RXOUTCLKSEL=0b010,

				# Receive Ports - RX Gearbox Ports
					#o_RXDATAVALID=,
					#o_RXHEADER=,
					#o_RXHEADERVALID=,
					#o_RXSTARTOFSEQ=,

				# Receive Ports - RX Gearbox Ports
					i_RXGEARBOXSLIP=0,

				# Receive Ports - RX Initialization and Reset Ports
					i_GTRXRESET=self.gtrxreset,
					i_RXOOBRESET=0,
					i_RXPCSRESET=0,
					i_RXPMARESET=0,

				# Receive Ports - RX Margin Analysis ports
					i_RXLPMEN=0,

				# Receive Ports - RX OOB Signaling ports
					#o_RXCOMSASDET=,
					o_RXCOMWAKEDET=rxcomwakedet,

				# Receive Ports - RX OOB Signaling ports
					o_RXCOMINITDET=rxcominitdet,

				# Receive Ports - RX OOB signalling Ports
					o_RXELECIDLE=rxelecidle,
					i_RXELECIDLEMODE=0b00,

				# Receive Ports - RX Polarity Control Ports
					i_RXPOLARITY=0,

				# Receive Ports - RX gearbox ports
					i_RXSLIDE=0,

				# Receive Ports - RX8B/10B Decoder Ports
					#o_RXCHARISCOMMA=,
					o_RXCHARISK=self.rxcharisk,

				# Receive Ports - Rx Channel Bonding Ports
					i_RXCHBONDI=0,

				# Receive Ports -RX Initialization and Reset Ports
					o_RXRESETDONE=rxresetdone,

				# Rx AFE Ports
					i_RXQPIEN=0,
					#o_RXQPISENN=,
					#o_RXQPISENP=,

				# TX Buffer Bypass Ports
					i_TXPHDLYTSTCLK=0,

				# TX Configurable Driver Ports
					i_TXPOSTCURSOR=0,
					i_TXPOSTCURSORINV=0,
					i_TXPRECURSOR=0,
					i_TXPRECURSORINV=0,
					i_TXQPIBIASEN=0,
					i_TXQPISTRONGPDOWN=0,
					i_TXQPIWEAKPUP=0,

				# TX Initialization and Reset Ports
					i_CFGRESET=0,
					i_GTTXRESET=self.gttxreset,
					#o_PCSRSVDOUT=,
					i_TXUSERRDY=txuserrdy,

				# Transceiver Reset Mode Operation
					i_GTRESETSEL=0,
					i_RESETOVRD=0,

				# Transmit Ports - 8b10b Encoder Control Ports
					i_TXCHARDISPMODE=0,
					i_TXCHARDISPVAL=0,

				# Transmit Ports - FPGA TX Interface Ports
					i_TXUSRCLK=self.txusrclk,
					i_TXUSRCLK2=self.txusrclk2,

				# Transmit Ports - PCI Express Ports
					i_TXELECIDLE=txelecidle,
					i_TXMARGIN=0,
					i_TXRATE=txrate,
					i_TXSWING=0,

				# Transmit Ports - Pattern Generator Ports
					i_TXPRBSFORCEERR=0,

				# Transmit Ports - TX Buffer Bypass Ports
					i_TXDLYBYPASS=0,
					i_TXDLYEN=txdlyen,
					i_TXDLYHOLD=0,
					i_TXDLYOVRDEN=0,
					i_TXDLYSRESET=txdlysreset,
					o_TXDLYSRESETDONE=txdlysresetdone,
					i_TXDLYUPDOWN=0,
					i_TXPHALIGN=txphalign,
					o_TXPHALIGNDONE=txphaligndone,
					i_TXPHALIGNEN=txphalignen,
					i_TXPHDLYPD=0,
					i_TXPHDLYRESET=txphdlyreset,
					i_TXPHINIT=txphinit,
					o_TXPHINITDONE=txphinitdone,
					i_TXPHOVRDEN=0,

				# Transmit Ports - TX Buffer Ports
					#o_TXBUFSTATUS=,

				# Transmit Ports - TX Configurable Driver Ports
					i_TXBUFDIFFCTRL=0b100,
					i_TXDEEMPH=0,
					i_TXDIFFCTRL=0b1000,
					i_TXDIFFPD=0,
					i_TXINHIBIT=0,
					i_TXMAINCURSOR=0,
					i_TXPISOPD=0,

				# Transmit Ports - TX Data Path interface
					i_TXDATA=self.txdata,

				# Transmit Ports - TX Driver and OOB signaling
					o_GTXTXP=pads.txp,
					o_GTXTXN=pads.txn,

				# Transmit Ports - TX Fabric Clock Output Control Ports
					o_TXOUTCLK=self.txoutclk,
					#o_TXOUTCLKFABRIC=,
					#o_TXOUTCLKPCS=,
					i_TXOUTCLKSEL=0b11,
					o_TXRATEDONE=txratedone,
				# Transmit Ports - TX Gearbox Ports
					i_TXCHARISK=self.txcharisk,
					#o_TXGEARBOXREADY=,
					i_TXHEADER=0,
					i_TXSEQUENCE=0,
					i_TXSTARTSEQ=0,

				# Transmit Ports - TX Initialization and Reset Ports
					i_TXPCSRESET=0,
					i_TXPMARESET=0,
					o_TXRESETDONE=txresetdone,

				# Transmit Ports - TX OOB signalling Ports
					o_TXCOMFINISH=txcomfinish,
					i_TXCOMINIT=txcominit,
					i_TXCOMSAS=0,
					i_TXCOMWAKE=txcomwake,
					i_TXPDELECIDLEMODE=0,

				# Transmit Ports - TX Polarity Control Ports
					i_TXPOLARITY=0,

				# Transmit Ports - TX Receiver Detection Ports
					i_TXDETECTRX=0,

				# Transmit Ports - TX8b/10b Encoder Ports
					i_TX8B10BBYPASS=0,

				# Transmit Ports - pattern Generator Ports
					i_TXPRBSSEL=0,

				# Tx Configurable Driver  Ports
					#o_TXQPISENN=,
					#o_TXQPISENP=,

					**gtxe2_channel_parameters
			)
