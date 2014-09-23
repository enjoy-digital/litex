class K7SATAPHY(Module):
	def __init__(self):

	_K28_5 = 0b1010000011

	def _ones(width):
		return 2**width-1

	self.specials += \
		Instance("GTXE2_CHANNEL",
			# Simulation-Only Attributes
				p_SIM_RECEIVER_DETECT_PASS="TRUE",
				p_SIM_TX_EIDLE_DRIVE_LEVEL="X",
				p_SIM_RESET_SPEEDUP=,
				p_SIM_CPLLREFCLK_SEL=,
				p_SIM_VERSION=,

			# RX Byte and Word Alignment Attributes
				p_ALIGN_COMMA_DOUBLE="FALSE",
				p_ALIGN_COMMA_ENABLE=_ones(10),
				p_ALIGN_COMMA_WORD=2,
				p_ALIGN_MCOMMA_DET="TRUE",
				p_ALIGN_MCOMMA_VALUE=_K28_5,
				p_ALIGN_PCOMMA_DET="TRUE",
				p_ALIGN_PCOMMA_VALUE=~_K28_5,
				p_SHOW_REALIGN_COMMA="FALSE",
				p_RXSLIDE_AUTO_WAIT=7,
				p_RXSLIDE_MODE="OFF",
				p_RX_SIG_VALID_DLY=10,

			# RX 8B/10B Decoder Attributes
				p_RX_DISPERR_SEQ_MATCH="TRUE",
				p_DEC_MCOMMA_DETECT="TRUE",
				p_DEC_PCOMMA_DETECT="TRUE",
				p_DEC_VALID_COMMA_ONLY="FALSE",

			# RX Clock Correction Attributes
				p_CBCC_DATA_SOURCE_SEL="DECODED",
				p_CLK_COR_SEQ_2_USE="FALSE",
				p_CLK_COR_KEEP_IDLE="FALSE",
				p_CLK_COR_MAX_LAT=9,
				p_CLK_COR_MIN_LAT=7,
				p_CLK_COR_PRECEDENCE="TRUE",
				p_CLK_COR_REPEAT_WAIT=0,
				p_CLK_COR_SEQ_LEN=1,
				p_CLK_COR_SEQ_1_ENABLE=_ones(4),
				p_CLK_COR_SEQ_1_ENABLE=0,
				p_CLK_COR_SEQ_1_1=0,
				p_CLK_COR_SEQ_1_1=0,
				p_CLK_COR_SEQ_1_2=0,
				p_CLK_COR_SEQ_1_3=,
				p_CLK_COR_SEQ_1_4=0,
				p_CLK_CORRECT_USE="FALSE",
				p_CLK_COR_SEQ_2_ENABLE=_ones(4),
				p_CLK_COR_SEQ_2_1=0,
				p_CLK_COR_SEQ_2_2=0,
				p_CLK_COR_SEQ_2_3=0,
				p_CLK_COR_SEQ_2_4=0,

			# RX Channel Bonding Attributes
				p_CHAN_BOND_KEEP_ALIGN="FALSE",
				p_CHAN_BOND_MAX_SKEW=1,
				p_CHAN_BOND_SEQ_LEN=1,
				p_CHAN_BOND_SEQ_1_1=0,
				p_CHAN_BOND_SEQ_1_1=0,
				p_CHAN_BOND_SEQ_1_2=0,
				p_CHAN_BOND_SEQ_1_3=0,
				p_CHAN_BOND_SEQ_1_4=0,
				p_CHAN_BOND_SEQ_1_ENABLE=_ones(4),
				p_CHAN_BOND_SEQ_2_1=0,
				p_CHAN_BOND_SEQ_2_2=0,
				p_CHAN_BOND_SEQ_2_3=0,
				p_CHAN_BOND_SEQ_2_4=0,
				p_CHAN_BOND_SEQ_2_ENABLE=_ones(4),
				p_CHAN_BOND_SEQ_2_USE="FALSE",
				p_FTS_DESKEW_SEQ_ENABLE=_ones(4),
				p_FTS_LANE_DESKEW_CFG=_ones(4),
				p_FTS_LANE_DESKEW_EN="FALSE",

			# RX Margin Analysis Attributes
				p_ES_CONTROL=0,
				p_ES_ERRDET_EN="FALSE",
				p_ES_EYE_SCAN_EN="TRUE",
				p_ES_HORZ_OFFSET=0,
				p_ES_PMA_CFG=0,
				p_ES_PRESCALE=0,
				p_ES_QUALIFIER=0,
				p_ES_QUAL_MASK=0,
				p_ES_SDATA_MASK=0,
				p_ES_VERT_OFFSET=0,

			# FPGA RX Interface Attributes
				p_RX_DATA_WIDTH=20,

			# PMA Attributes
				p_OUTREFCLK_SEL_INV=0b11,
				p_PMA_RSV=,
				p_PMA_RSV2=0x2050,
				p_PMA_RSV3=0,
				p_PMA_RSV4=0,
				p_RX_BIAS_CFG=0b100,
				p_DMONITOR_CFG=0xA00,
				p_RX_CM_SEL=0b11,
				p_RX_CM_TRIM=0b010,
				p_RX_DEBUG_CFG=0,
				p_RX_OS_CFG=0b10000000,
				p_TERM_RCAL_CFG=0,
				p_TERM_RCAL_OVRD=0,
				p_TST_RSV=0,
				p_RX_CLK25_DIV=6,
				p_TX_CLK25_DIV=6,
				p_UCODEER_CLR=0,

			# PCI Express Attributes
				p_PCS_PCIE_EN="FALSE",

			# PCS Attributes
				p_PCS_RSVD_ATTR=,

			# RX Buffer Attributes
				p_RXBUF_ADDR_MODE="FAST",
				p_RXBUF_EIDLE_HI_CNT=0b1000,
				p_RXBUF_EIDLE_LO_CNT=0,
				p_RXBUF_EN="FALSE",
				p_RX_BUFFER_CFG=0,
				p_RXBUF_RESET_ON_CB_CHANGE="TRUE",
				p_RXBUF_RESET_ON_COMMAALIGN="FALSE",
				p_RXBUF_RESET_ON_EIDLE="FALSE",
				p_RXBUF_RESET_ON_RATE_CHANGE="TRUE",
				p_RXBUFRESET_TIME=1,
				p_RXBUF_THRESH_OVFLW=61,
				p_RXBUF_THRESH_OVRD="FALSE",
				p_RXBUF_THRESH_UNDFLW=4,
				p_RXDLY_CFG=0x1f,
				p_RXDLY_LCFG=0x30,
				p_RXDLY_TAP_CFG=0,
				p_RXPH_CFG=0,
				p_RXPHDLY_CFG=0x084820,
				p_RXPH_MONITOR_SEL=0,
				p_RX_XCLK_SEL="RXUSR",
				p_RX_DDI_SEL=0,
				p_RX_DEFER_RESET_BUF_EN="TRUE",

			#CDR Attributes
			#Gen 3, 6 Gb/s		1	72'h03_8000_8BFF_1020_0010
			#Gen 2, 3 Gb/s		2	72'h03_8800_8BFF_4020_0008
			#Gen 1, 1.5 Gb/s	4 	72'h03_8000_8BFF_4010_0008
				p_RXCDR_CFG=,
				p_RXCDR_FR_RESET_ON_EIDLE=0,
				p_RXCDR_HOLD_DURING_EIDLE=0,
				p_RXCDR_PH_RESET_ON_EIDLE=0,
				p_RXCDR_LOCK_CFG=0b010101,

			# RX Initialization and Reset Attributes
				p_RXCDRFREQRESET_TIME=1,
				p_RXCDRPHRESET_TIME=1,
				p_RXISCANRESET_TIME=1,
				p_RXPCSRESET_TIME=1,
				p_RXPMARESET_TIME=3,

			# RX OOB Signaling Attributes
				p_RXOOB_CFG=0b0000110,

			# RX Gearbox Attributes
				p_RXGEARBOX_EN="FALSE",
				p_GEARBOX_MODE=0,

			# PRBS Detection Attribute
				p_RXPRBS_ERR_LOOPBACK=0,

			# Power-Down Attributes
				p_PD_TRANS_TIME_FROM_P2=0x03c,
				p_PD_TRANS_TIME_NONE_P2=0x3c,
				p_PD_TRANS_TIME_TO_P2=0x64,

			# RX OOB Signaling Attributes
				p_SAS_MAX_COM=64,
				p_SAS_MIN_COM=36,
				p_SATA_BURST_SEQ_LEN=0b0101,
				p_SATA_BURST_VAL=0b100,
				p_SATA_EIDLE_VAL=0b100,
				p_SATA_MAX_BURST=8,
				p_SATA_MAX_INIT=21,
				p_SATA_MAX_WAKE=7,
				p_SATA_MIN_BURST=4,
				p_SATA_MIN_INIT=12,
				p_SATA_MIN_WAKE=4,

			# RX Fabric Clock Output Control Attributes
				p_TRANS_TIME_RATE=0x0e,

			# TX Buffer Attributes
				p_TXBUF_EN="FALSE",
				p_TXBUF_RESET_ON_RATE_CHANGE="FALSE",
				p_TXDLY_CFG=0x1f,
				p_TXDLY_LCFG=0x030,
				p_TXDLY_TAP_CFG=0,
				p_TXPH_CFG=0x0780,
				p_TXPHDLY_CFG=0x084020,
				p_TXPH_MONITOR_SEL=0,
				p_TX_XCLK_SEL="TXUSR",

			# FPGA TX Interface Attributes
				p_TX_DATA_WIDTH=20,

			# TX Configurable Driver Attributes
				p_TX_DEEMPH0=0,
				p_TX_DEEMPH1=0,
				p_TX_EIDLE_ASSERT_DELAY=0b110,
				p_TX_EIDLE_DEASSERT_DELAY=0b100,
				p_TX_LOOPBACK_DRIVE_HIZ="FALSE",
				p_TX_MAINCURSOR_SEL=0,
				p_TX_DRIVE_MODE="DIRECT",
				p_TX_MARGIN_FULL_0=0b1001110,
				p_TX_MARGIN_FULL_1=0b1001001,
				p_TX_MARGIN_FULL_2=0b1000101,
				p_TX_MARGIN_FULL_3=0b1000010,
				p_TX_MARGIN_FULL_4=0b1000000,
				p_TX_MARGIN_LOW_0=0b1000110,
				p_TX_MARGIN_LOW_1=0b1000100,
				p_TX_MARGIN_LOW_2=0b1000010,
				p_TX_MARGIN_LOW_3=0b1000000,
				p_TX_MARGIN_LOW_4=0b1000000,

			# TX Gearbox Attributes
				p_TXGEARBOX_EN="FALSE",

			# TX Initialization and Reset Attributes
				p_TXPCSRESET_TIME=1,
				p_TXPMARESET_TIME=1,

			# TX Receiver Detection Attributes
				p_TX_RXDETECT_CFG=0x1832,
				p_TX_RXDETECT_REF=0b100,

			# CPLL Attributes
				p_CPLL_CFG=0xBC07DC,
				p_CPLL_FBDIV=4,
				p_CPLL_FBDIV_45=5,
				p_CPLL_INIT_CFG=0x00001E
				p_CPLL_LOCK_CFG=0x01e8,
				p_CPLL_REFCLK_DIV=1,
				p_RXOUT_DIV=,
				p_TXOUT_DIV=,
				p_SATA_CPLL_CFG="VCO_3000MHZ",

			# RX Initialization and Reset Attributes
				p_RXDFELPMRESET_TIME=0b0001111,

			# RX Equalizer Attributes
				p_RXLPM_HF_CFG=0b00000011110000,
				p_RXLPM_LF_CFG=0b00000011110000,
				p_RX_DFE_GAIN_CFG=0b020FEA,
				p_RX_DFE_H2_CFG=0b000000000000,
				p_RX_DFE_H3_CFG=0b000001000000,
				p_RX_DFE_H4_CFG=0b00011110000,
				p_RX_DFE_H5_CFG=0b00011100000,
				p_RX_DFE_KL_CFG=0b0000011111110,
				p_RX_DFE_LPM_CFG=0x0954,
				p_RX_DFE_LPM_HOLD_DURING_EIDLE=1,
				p_RX_DFE_UT_CFG=0b10001111000000000,
				p_RX_DFE_VP_CFG=0b00011111100000011,

			# Power-Down Attributes
				p_RX_CLKMUX_PD=1,
				p_TX_CLKMUX_PD=1,

			# FPGA RX Interface Attribute
				p_RX_INT_DATAWIDTH=0,

			# FPGA TX Interface Attribute
				p_TX_INT_DATAWIDTH=0,

			# TX Configurable Driver Attributes
				p_TX_QPI_STATUS_EN=0,

			# RX Equalizer Attributes
				p_RX_DFE_KL_CFG2=0b00110011000100000001100000001100
				p_RX_DFE_XYD_CFG=0bb0000000000000,

			# TX Configurable Driver Attributes
				p_TX_PREDRIVER_MODE=0,

			# CPLL Ports
				o_CPLLFBCLKLOST=,
				o_CPLLLOCK=,
				i_CPLLLOCKDETCLK=,
				i_CPLLLOCKEN=1,
				i_CPLLPD=0,
				o_CPLLREFCLKLOST=,
				i_CPLLREFCLKSEL=0b001,
				i_CPLLRESET=,
				i_GTRSVD=,
				i_PCSRSVDIN=0,
				i_PCSRSVDIN2=0,
				i_PMARSVDIN=0,
				i_PMARSVDIN2=0,
				i_TSTIN=_ones(20),
				#o_TSTOUT=,

			# Channel
				i_CLKRSVD=,

			# Channel - Clocking Ports
				i_GTGREFCLK=0,
				i_GTNORTHREFCLK0=0,
				i_GTNORTHREFCLK1=0,
				i_GTREFCLK0=,
				i_GTREFCLK1=0,
				i_GTSOUTHREFCLK0=0,
				i_GTSOUTHREFCLK1=0,

			# Channel - DRP Ports
				i_DRPADDR=,
				i_DRPCLK=,
				i_DRPDI=,
				i_DRPDO=,
				i_DRPEN=,
				o_DRPRDY=,
				i_DRPWE=,

			# Clocking Ports
				#o_GTREFCLKMONITOR=,
				i_QPLLCLK=,
				i_QPLLCLK=,
				i_QPLLREFCLK=,
				i_QPLLREFCLK=,
				i_RXSYSCLKSEL=0b00,
				i_TXSYSCLKSEL=0b00,

			# Digital Monitor Ports
				o_DMONITOROUT=,

			# FPGA TX Interface Datapath Configuration
				i_TX8B10BEN=1,

			# Loopback Ports
				i_LOOPBACK=0,

			# PCI Express Ports
				#o_PHYSTATUS=,
				i_RXRATE=,
				#o_RXVALID=,

			# Power-Down Ports
				i_RXPD=0b00,
				i_TXPD=0b00,

			# RX 8B/10B Decoder Ports
				i_SETERRSTATUS=0,

			# RX Initialization and Reset Ports
				i_EYESCANRESET=0,
				i_RXUSERRDY=,

			# RX Margin Analysis Ports
				o_EYESCANDATAERROR=,
				i_EYESCANMODE=0,
				i_EYESCANTRIGGER=0,

			# Receive Ports - CDR Ports
				i_RXCDRFREQRESET=,
				i_RXCDRHOLD=0,
				o_RXCDRLOCK=,
				i_RXCDROVRDEN=0,
				i_RXCDRRESET=0,
				i_RXCDRRESETRSV=0,

			# Receive Ports - Clock Correction Ports
				#o_RXCLKCORCNT=,

			# Receive Ports - FPGA RX Interface Datapath Configuration
				i_RX8B10BEN=1,

			# Receive Ports - FPGA RX Interface Ports
				i_RXUSRCLK=,
				i_RXUSRCLK2=,

			# Receive Ports - FPGA RX interface Ports
				i_RXDATA=,

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
				i_RXDISPERR=,
				o_RXNOTINTABLE=,

			# Receive Ports - RX AFE
				i_GTXRXP=,

			# Receive Ports - RX AFE Ports
				i_GTXRXN=,

			# Receive Ports - RX Buffer Bypass Ports
				i_RXBUFRESET=0,
				#o_RXBUFSTATUS=,
				i_RXDDIEN=1,
				i_RXDLYBYPASS=0,
				i_RXDLYEN=,
				i_RXDLYOVRDEN=0,
				i_RXDLYSRESET=,
				o_RXDLYSRESETDONE=,
				i_RXPHALIGN=,
				o_RXPHALIGNDONE=,
				i_RXPHALIGNEN=,
				i_RXPHDLYPD=0,
				i_RXPHDLYRESET=,
				o_RXPHMONITOR=,
				i_RXPHOVRDEN=0,
				o_RXPHSLIPMONITOR=,
				o_RXSTATUS=,

			# Receive Ports - RX Byte and Word Alignment Ports
				#o_RXBYTEISALIGNED=,
				#o_RXBYTEREALIGN=,
				#o_RXCOMMADET=,
				i_RXCOMMADETEN=1,
				i_RXMCOMMAALIGNEN=,
				i_RXPCOMMAALIGNEN=,

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
				o_RXRATEDONE=,

			# Receive Ports - RX Fabric Output Control Ports
				o_RXOUTCLK=,
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
				i_GTRXRESET=,
				i_RXOOBRESET=0,
				i_RXPCSRESET=0,
				i_RXPMARESET=0,

			# Receive Ports - RX Margin Analysis ports
				i_RXLPMEN=,

			# Receive Ports - RX OOB Signaling ports
				#o_RXCOMSASDET=,
				o_RXCOMWAKEDET=,

			# Receive Ports - RX OOB Signaling ports
				o_RXCOMINITDET=,

			# Receive Ports - RX OOB signalling Ports
				o_RXELECIDLE=,
				i_RXELECIDLEMODE=,

			# Receive Ports - RX Polarity Control Ports
				i_RXPOLARITY=0,

			# Receive Ports - RX gearbox ports
				i_RXSLIDE=0,

			# Receive Ports - RX8B/10B Decoder Ports
				#o_RXCHARISCOMMA=,
				o_RXCHARISK=,

			# Receive Ports - Rx Channel Bonding Ports
				i_RXCHBONDI=0,

			# Receive Ports -RX Initialization and Reset Ports
				o_RXRESETDONE=,

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
				i_CFGRESET=,
				i_GTTXRESET=,
				#o_PCSRSVDOUT=,
				i_TXUSERRDY=,

			# Transceiver Reset Mode Operation
				i_GTRESETSEL=,
				i_RESETOVRD=,

			# Transmit Ports - 8b10b Encoder Control Ports
				i_TXCHARDISPMODE=0,
				i_TXCHARDISPVAL=0,

			# Transmit Ports - FPGA TX Interface Ports
				i_TXUSRCLK=,
				i_TXUSRCLK2=,

			# Transmit Ports - PCI Express Ports
				i_TXELECIDLE=,
				i_TXMARGIN=0,
				i_TXRATE=,
				i_TXSWING=0,

			# Transmit Ports - Pattern Generator Ports
				i_TXPRBSFORCEERR=0,

			# Transmit Ports - TX Buffer Bypass Ports
				i_TXDLYBYPASS=0,
				i_TXDLYEN=,
				i_TXDLYHOLD=0,
				i_TXDLYOVRDEN=0,
				i_TXDLYSRESET=,
				o_TXDLYSRESETDONE=,
				i_TXDLYUPDOWN=0,
				i_TXPHALIGN=,
				o_TXPHALIGNDONE=,
				i_TXPHALIGNEN=,
				i_TXPHDLYPD=0,
				i_TXPHDLYRESET=,
				i_TXPHINIT=,
				o_TXPHINITDONE=,
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
				i_TXDATA=,

			# Transmit Ports - TX Driver and OOB signaling
				o_GTXTXN=,
				o_GTXTXP=,

			# Transmit Ports - TX Fabric Clock Output Control Ports
				o_TXOUTCLK=,
				o_TXOUTCLKFABRIC=,
				o_TXOUTCLKPCS=,
				i_TXOUTCLKSEL=0b11,
				o_TXRATEDONE=,
			# Transmit Ports - TX Gearbox Ports
				i_TXCHARISK=,
				#o_TXGEARBOXREADY=,
				i_TXHEADER=0,
				i_TXSEQUENCE=0,
				i_TXSTARTSEQ=0,

			# Transmit Ports - TX Initialization and Reset Ports
				i_TXPCSRESET=0,
				i_TXPMARESET=0,
				o_TXRESETDONE=,

			# Transmit Ports - TX OOB signalling Ports
				o_TXCOMFINISH=,
				i_TXCOMINIT=,
				i_TXCOMSAS=0,
				i_TXCOMWAKE=,
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
				#o_TXQPISENP=
		)

	self.specials += \
		Instance("GTXE2_COMMON",
			# Simulation attributes
				p_SIM_RESET_SPEEDUP=,
				p_SIM_QPLLREFCLK_SEL=,
				p_SIM_VERSION=,

			# Common block attributes
				p_BIAS_CFG=,
				p_COMMON_CFG=,
				p_QPLL_CFG=,
				p_QPLL_CLKOUT_CFG=,
				p_QPLL_COARSE_FREQ_OVRD=,
				p_QPLL_COARSE_FREQ_OVRD_EN=,
				p_QPLL_CP=,
				p_QPLL_CP_MONITOR_EN=,
				p_QPLL_DMONITOR_SEL=,
				p_QPLL_FBDIV=,
				p_QPLL_FBDIV_MONITOR_EN=,
				p_QPLL_FBDIV_RATIO=,
				p_QPLL_INIT_CFG=,
				p_QPLL_LOCK_CFG=,
				p_QPLL_LPF=,
				p_QPLL_REFCLK_DIV=,

			# Common block - Dynamic Reconfiguration Port (DRP)
				i_DRPADDR=,
				i_DRPCLK=,
				i_DRPDI=,
				o_DRPDO=,
				i_DRPEN=,
				o_DRPRDY=,
				i_DRPWE=,

			# Common block  - Ref Clock Ports
				i_GTGREFCLK=,
				i_GTNORTHREFCLK0=,
				i_GTNORTHREFCLK1=,
				i_GTREFCLK0=,
				i_GTREFCLK1=,
				i_GTSOUTHREFCLK0=,
				i_GTSOUTHREFCLK1=,

			# Common block - QPLL Ports
				o_QPLLDMONITOR=,
				o_QPLLFBCLKLOST=,
				o_QPLLLOCK=,
				i_QPLLLOCKDETCLK=,
				i_QPLLLOCKEN=,
				o_QPLLOUTCLK=,
				o_QPLLOUTREFCLK=,
				i_QPLLOUTRESET=,
				i_QPLLPD=,
				o_QPLLREFCLKLOST=,
				i_QPLLREFCLKSEL=,
				i_QPLLRESET=,
				i_QPLLRSVD1=,
				i_QPLLRSVD2=,
				o_REFCLKOUTMONITOR=,

			# Common block Ports
				i_BGBYPASSB=,
				i_BGMONITORENB=,
				i_BGPDB=,
				i_BGRCALOVRD=,
				i_PMARSVD=,
				i_RCALENB=
		)
