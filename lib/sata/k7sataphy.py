class K7SATAPHY(Module):
	def __init__(self):
	self.specials += [
		Instance("GTXE2_CHANNEL",
			# Simulation-Only Attributes
				p_SIM_RECEIVER_DETECT_PASS=,
				p_SIM_TX_EIDLE_DRIVE_LEVEL=,
				p_SIM_RESET_SPEEDUP=,
				p_SIM_RESET_SPEEDUP=,
				p_SIM_CPLLREFCLK_SEL=,
				p_SIM_VERSION=,

			# RX Byte and Word Alignment Attributes
				p_ALIGN_COMMA_DOUBLE=,
				p_ALIGN_COMMA_ENABLE=,
				p_ALIGN_COMMA_WORD=,
				p_ALIGN_MCOMMA_DET=,
				p_ALIGN_MCOMMA_VALUE=,
				p_ALIGN_PCOMMA_DET=,
				p_ALIGN_PCOMMA_VALUE=,
				p_SHOW_REALIGN_COMMA=,
				p_RXSLIDE_AUTO_WAIT=,
				p_RXSLIDE_MODE=,
				p_RX_SIG_VALID_DLY=,

			# RX 8B/10B Decoder Attributes
				p_RX_DISPERR_SEQ_MATCH=,
				p_DEC_MCOMMA_DETECT=,
				p_DEC_PCOMMA_DETECT=,
				p_DEC_VALID_COMMA_ONLY=,

			# RX Clock Correction Attributes
				p_CBCC_DATA_SOURCE_SEL=,
				p_CLK_COR_SEQ_2_USE=,
				p_CLK_COR_SEQ_2_USE=,
				p_CLK_COR_KEEP_IDLE=,
				p_CLK_COR_MAX_LAT=,
				p_CLK_COR_MIN_LAT=,
				p_CLK_COR_PRECEDENCE=,
				p_CLK_COR_REPEAT_WAIT=,
				p_CLK_COR_SEQ_LEN=,
				p_CLK_COR_SEQ_1_ENABLE=,
				p_CLK_COR_SEQ_1_ENABLE=,
				p_CLK_COR_SEQ_1_1=,
				p_CLK_COR_SEQ_1_1=,
				p_CLK_COR_SEQ_1_2=,
				p_CLK_COR_SEQ_1_3=,
				p_CLK_COR_SEQ_1_4=,
				p_CLK_CORRECT_USE=,
				p_CLK_CORRECT_USE=,
				p_CLK_COR_SEQ_2_ENABLE=,
				p_CLK_COR_SEQ_2_ENABLE=,
				p_CLK_COR_SEQ_2_1=,
				p_CLK_COR_SEQ_2_1=,
				p_CLK_COR_SEQ_2_2=,
				p_CLK_COR_SEQ_2_3=,
				p_CLK_COR_SEQ_2_4=,

			# RX Channel Bonding Attributes
				p_CHAN_BOND_KEEP_ALIGN=,
				p_CHAN_BOND_MAX_SKEW=,
				p_CHAN_BOND_SEQ_LEN=,
				p_CHAN_BOND_SEQ_1_1=,
				p_CHAN_BOND_SEQ_1_1=,
				p_CHAN_BOND_SEQ_1_2=,
				p_CHAN_BOND_SEQ_1_3=,
				p_CHAN_BOND_SEQ_1_4=,
				p_CHAN_BOND_SEQ_1_ENABLE=,
				p_CHAN_BOND_SEQ_1_ENABLE=,
				p_CHAN_BOND_SEQ_2_1=,
				p_CHAN_BOND_SEQ_2_2=,
				p_CHAN_BOND_SEQ_2_3=,
				p_CHAN_BOND_SEQ_2_4=,
				p_CHAN_BOND_SEQ_2_ENABLE=,
				p_CHAN_BOND_SEQ_2_ENABLE=,
				p_CHAN_BOND_SEQ_2_USE=,
				p_FTS_DESKEW_SEQ_ENABLE=,
				p_FTS_LANE_DESKEW_CFG=,
				p_FTS_LANE_DESKEW_EN=,

			# RX Margin Analysis Attributes
				p_ES_CONTROL=,
				p_ES_ERRDET_EN=,
				p_ES_EYE_SCAN_EN=,
				p_ES_HORZ_OFFSET=,
				p_ES_PMA_CFG=,
				p_ES_PRESCALE=,
				p_ES_QUALIFIER=,
				p_ES_QUAL_MASK=,
				p_ES_SDATA_MASK=,
				p_ES_VERT_OFFSET=,

			# FPGA RX Interface Attributes
				p_RX_DATA_WIDTH=,

			# PMA Attributes
				p_OUTREFCLK_SEL_INV=,
				p_PMA_RSV=,
				p_PMA_RSV2=,
				p_PMA_RSV3=,
				p_PMA_RSV4=,
				p_RX_BIAS_CFG=,
				p_DMONITOR_CFG=,
				p_RX_CM_SEL=,
				p_RX_CM_TRIM=,
				p_RX_DEBUG_CFG=,
				p_RX_OS_CFG=,
				p_TERM_RCAL_CFG=,
				p_TERM_RCAL_OVRD=,
				p_TST_RSV=,
				p_RX_CLK25_DIV=,
				p_TX_CLK25_DIV=,
				p_UCODEER_CLR=,

			# PCI Express Attributes
				p_PCS_PCIE_EN=,

			# PCS Attributes
				p_PCS_RSVD_ATTR=,

			# RX Buffer Attributes
				p_RXBUF_ADDR_MODE=,
				p_RXBUF_ADDR_MODE=,
				p_RXBUF_EIDLE_HI_CNT=,
				p_RXBUF_EIDLE_LO_CNT=,
				p_RXBUF_EN=,
				p_RX_BUFFER_CFG=,
				p_RXBUF_RESET_ON_CB_CHANGE=,
				p_RXBUF_RESET_ON_COMMAALIGN=,
				p_RXBUF_RESET_ON_EIDLE=,
				p_RXBUF_RESET_ON_RATE_CHANGE=,
				p_RXBUFRESET_TIME=,
				p_RXBUF_THRESH_OVFLW=,
				p_RXBUF_THRESH_OVRD=,
				p_RXBUF_THRESH_UNDFLW=,
				p_RXDLY_CFG=,
				p_RXDLY_LCFG=,
				p_RXDLY_TAP_CFG=,
				p_RXPH_CFG=,
				p_RXPHDLY_CFG=,
				p_RXPH_MONITOR_SEL=,
				p_RX_XCLK_SEL=,
				p_RX_DDI_SEL=,
				p_RX_DEFER_RESET_BUF_EN=,

			#CDR Attributes
			#Gen 3, 6 Gb/s		1	72'h03_8000_8BFF_1020_0010
			#Gen 2, 3 Gb/s		2	72'h03_8800_8BFF_4020_0008
			#Gen 1, 1.5 Gb/s	4 	72'h03_8000_8BFF_4010_0008
				p_RXCDR_CFG=,
				p_RXCDR_FR_RESET_ON_EIDLE=,
				p_RXCDR_HOLD_DURING_EIDLE=,
				p_RXCDR_PH_RESET_ON_EIDLE=,
				p_RXCDR_LOCK_CFG=,

			# RX Initialization and Reset Attributes
				p_RXCDRFREQRESET_TIME=,
				p_RXCDRPHRESET_TIME=,
				p_RXISCANRESET_TIME=,
				p_RXPCSRESET_TIME=,
				p_RXPMARESET_TIME=,

			# RX OOB Signaling Attributes
				p_RXOOB_CFG=,

			# RX Gearbox Attributes
				p_RXGEARBOX_EN=,
				p_GEARBOX_MODE=,

			# PRBS Detection Attribute
				p_RXPRBS_ERR_LOOPBACk=,

			# Power-Down Attributes
				p_PD_TRANS_TIME_FROM_P2=,
				p_PD_TRANS_TIME_NONE_P2=,
				p_PD_TRANS_TIME_TO_P2=,

			# RX OOB Signaling Attributes
				p_SAS_MAX_COM=,
				p_SAS_MIN_COM=,
				p_SATA_BURST_SEQ_LEN=,
				p_SATA_BURST_SEQ_LEN=,
				p_SATA_BURST_VAL=,
				p_SATA_EIDLE_VAL=,
				p_SATA_MAX_BURST=,
				p_SATA_MAX_INIT=,
				p_SATA_MAX_WAKE=,
				p_SATA_MIN_BURST=,
				p_SATA_MIN_INIT=,
				p_SATA_MIN_WAKE=,

			# RX Fabric Clock Output Control Attributes
				p_TRANS_TIME_RATE=,

			# TX Buffer Attributes
				p_TXBUF_EN=,
				p_TXBUF_EN=,
				p_TXBUF_RESET_ON_RATE_CHANGE=,
				p_TXDLY_CFG=,
				p_TXDLY_LCFG=,
				p_TXDLY_TAP_CFG=,
				p_TXPH_CFG=,
				p_TXPHDLY_CFG=,
				p_TXPH_MONITOR_SEL=,
				p_TX_XCLK_SEL=,
				p_TX_XCLK_SEL=,

			# FPGA TX Interface Attributes
				p_TX_DATA_WIDTH=,
			# TX Configurable Driver Attributes
				p_TX_DEEMPH0=,
				p_TX_DEEMPH1=,
				p_TX_EIDLE_ASSERT_DELAY=,
				p_TX_EIDLE_DEASSERT_DELAY=,
				p_TX_LOOPBACK_DRIVE_HIZ=,
				p_TX_MAINCURSOR_SEL=,
				p_TX_DRIVE_MODE=,
				p_TX_MARGIN_FULL_0=,
				p_TX_MARGIN_FULL_1=,
				p_TX_MARGIN_FULL_2=,
				p_TX_MARGIN_FULL_3=,
				p_TX_MARGIN_FULL_4=,
				p_TX_MARGIN_LOW_0=,
				p_TX_MARGIN_LOW_1=,
				p_TX_MARGIN_LOW_2=,
				p_TX_MARGIN_LOW_3=,
				p_TX_MARGIN_LOW_4=,

			# TX Gearbox Attributes
				p_TXGEARBOX_EN=,
			# TX Initialization and Reset Attributes
				p_TXPCSRESET_TIME=,
				p_TXPMARESET_TIME=,

			# TX Receiver Detection Attributes
				p_TX_RXDETECT_CFG=,
				p_TX_RXDETECT_REF=,

			# CPLL Attributes
				p_CPLL_CFG=,
				p_CPLL_FBDIV=,
				p_CPLL_FBDIV_45=,
				p_CPLL_INIT_CFG=,
				p_CPLL_LOCK_CFG=,
				p_CPLL_REFCLK_DIV=,
				p_RXOUT_DIV=,
				p_TXOUT_DIV=,
				p_RXOUT_DIV=,
				p_TXOUT_DIV=,
				p_SATA_CPLL_CFG=,

			# RX Initialization and Reset Attributes
				p_RXDFELPMRESET_TIME=,

			# RX Equalizer Attributes
				p_RXLPM_HF_CFG=,
				p_RXLPM_LF_CFG=,
				p_RX_DFE_GAIN_CFG=,
				p_RX_DFE_H2_CFG=,
				p_RX_DFE_H3_CFG=,
				p_RX_DFE_H4_CFG=,
				p_RX_DFE_H5_CFG=,
				p_RX_DFE_KL_CFG=,
				p_RX_DFE_LPM_CFG=,
				p_RX_DFE_LPM_HOLD_DURING_EIDLE=,
				p_RX_DFE_UT_CFG=,
				p_RX_DFE_VP_CFG=,

			# Power-Down Attributes
				p_RX_CLKMUX_PD=,
				p_TX_CLKMUX_PD=,

			# FPGA RX Interface Attribute
				p_RX_INT_DATAWIDTH=,

			# FPGA TX Interface Attribute
				p_TX_INT_DATAWIDTH=,

			# TX Configurable Driver Attributes
				p_TX_QPI_STATUS_EN=,

			# RX Equalizer Attributes
				p_RX_DFE_KL_CFG2=,
				p_RX_DFE_XYD_CFG=,

			# TX Configurable Driver Attributes
				p_TX_PREDRIVER_MODE=,

			# CPLL Ports
				o_CPLLFBCLKLOST=,
				o_CPLLLOCK=,
				i_CPLLLOCKDETCLK=,
				i_CPLLLOCKDETCLK=,
				i_CPLLLOCKEN=,
				i_CPLLPD=,
				o_CPLLREFCLKLOST=,
				i_CPLLREFCLKSEL=,
				i_CPLLRESET=,
				i_GTRSVD=,
				i_PCSRSVDIN=,
				i_PCSRSVDIN2=,
				i_PMARSVDIN=,
				i_PMARSVDIN2=,
				i_TSTIN=,
				o_TSTOUT=,

			# Channel
				i_CLKRSVD=,

			# Channel - Clocking Ports
				i_GTGREFCLK=,
				i_GTNORTHREFCLK0=,
				i_GTNORTHREFCLK1=,
				i_GTREFCLK0=,
				i_GTREFCLK1=,
				i_GTSOUTHREFCLK0=,
				i_GTSOUTHREFCLK1=,

			# Channel - DRP Ports
				i_DRPADDR=,
				i_DRPCLK=,
				i_DRPDI=,
				i_DRPDO=,
				i_DRPEN=,
				o_DRPRDY=,
				i_DRPWE=,

			# Clocking Ports
				o_GTREFCLKMONITOR=,
				i_QPLLCLK=,
				i_QPLLCLK=,
				i_QPLLREFCLK=,
				i_QPLLREFCLK=,
				i_RXSYSCLKSEL=,
				i_TXSYSCLKSEL=,

			# Digital Monitor Ports
				o_DMONITOROUT=,

			# FPGA TX Interface Datapath Configuration
				i_TX8B10BEN=,

			# Loopback Ports
				i_LOOPBACK=,

			# PCI Express Ports
				o_PHYSTATUS=,
				i_RXRATE=,
				o_RXVALID=,

			# Power-Down Ports
				i_RXPD=,
				i_TXPD=,

			# RX 8B/10B Decoder Ports
				i_SETERRSTATUS=,

			# RX Initialization and Reset Ports
				i_EYESCANRESET=,
				i_RXUSERRDY=,

			# RX Margin Analysis Ports
				o_EYESCANDATAERROR=,
				i_EYESCANMODE=,
				i_EYESCANTRIGGER=,

			# Receive Ports - CDR Ports
				i_RXCDRFREQRESET=,
				i_RXCDRHOLD=,
				o_RXCDRLOCK=,
				o_RXCDRLOCK=,
				i_RXCDROVRDEN=,
				i_RXCDRRESET=,
				i_RXCDRRESETRSV=,

			# Receive Ports - Clock Correction Ports
				o_RXCLKCORCNT=,

			# Receive Ports - FPGA RX Interface Datapath Configuration
				i_RX8B10BEN=,

			# Receive Ports - FPGA RX Interface Ports
				i_RXUSRCLK=,
				i_RXUSRCLK2=,

			# Receive Ports - FPGA RX interface Ports
				i_RXDATA=,

			# Receive Ports - Pattern Checker Ports
				o_RXPRBSERR=,
				i_RXPRBSSEL=,

			# Receive Ports - Pattern Checker ports
				i_RXPRBSCNTRESET=,

			# Receive Ports - RX  Equalizer Ports
				i_RXDFEXYDEN=,
				i_RXDFEXYDHOLD=,
				i_RXDFEXYDOVRDEN=,

			# Receive Ports - RX 8B/10B Decoder Ports
				i_RXDISPERR=,
				o_RXNOTINTABLE=,

			# Receive Ports - RX AFE
				i_GTXRXP=,

			# Receive Ports - RX AFE Ports
				i_GTXRXN=,

			# Receive Ports - RX Buffer Bypass Ports
				i_RXBUFRESET=,
				o_RXBUFSTATUS=,
				i_RXDDIEN=,
				i_RXDLYBYPASS=,
				i_RXDLYEN=,
				i_RXDLYOVRDEN=,
				i_RXDLYSRESET=,
				o_RXDLYSRESETDONE=,
				i_RXPHALIGN=,
				o_RXPHALIGNDONE=,
				i_RXPHALIGNEN=,
				i_RXPHDLYPD=,
				i_RXPHDLYRESET=,
				o_RXPHMONITOR=,
				i_RXPHOVRDEN=,
				o_RXPHSLIPMONITOR=,
				o_RXSTATUS=,

			# Receive Ports - RX Byte and Word Alignment Ports
				o_RXBYTEISALIGNED=,
				o_RXBYTEREALIGN=,
				o_RXCOMMADET=,
				i_RXCOMMADETEN=,
				i_RXMCOMMAALIGNEN=,
				i_RXMCOMMAALIGNEN=,
				i_RXPCOMMAALIGNEN=,
				i_RXPCOMMAALIGNEN=,

			# Receive Ports - RX Channel Bonding Ports
				o_RXCHANBONDSEQ=,
				i_RXCHBONDEN=,
				i_RXCHBONDLEVEL=,
				i_RXCHBONDMASTER=,
				o_RXCHBONDO=,
				i_RXCHBONDSLAVE=,

			# Receive Ports - RX Channel Bonding Ports
				o_RXCHANISALIGNED=,
				o_RXCHANREALIGN=,

			# Receive Ports - RX Equalizer Ports
				i_RXDFEAGCHOLD=,
				i_RXDFEAGCOVRDEN=,
				i_RXDFECM1EN=,
				i_RXDFELFHOLD=,
				i_RXDFELFOVRDEN=,
				i_RXDFELPMRESET=,
				i_RXDFETAP2HOLD=,
				i_RXDFETAP2OVRDEN=,
				i_RXDFETAP3HOLD=,
				i_RXDFETAP3OVRDEN=,
				i_RXDFETAP4HOLD=,
				i_RXDFETAP4OVRDEN=,
				i_RXDFETAP5HOLD=,
				i_RXDFETAP5OVRDEN=,
				i_RXDFEUTHOLD=,
				i_RXDFEUTOVRDEN=,
				i_RXDFEVPHOLD=,
				i_RXDFEVPOVRDEN=,
				i_RXDFEVSEN=,
				i_RXLPMLFKLOVRDEN=,
				o_RXMONITOROUT=,
				i_RXMONITORSEL=,
				i_RXOSHOLD=,
				i_RXOSOVRDEN=,

			# Receive Ports - RX Equilizer Ports
				i_RXLPMHFHOLD=,
				i_RXLPMHFOVRDEN=,
				i_RXLPMLFHOLD=,

			# Receive Ports - RX Fabric ClocK Output Control Ports
				o_RXRATEDONE=,

			# Receive Ports - RX Fabric Output Control Ports
				o_RXOUTCLK=,
				o_RXOUTCLKFABRIC=,
				o_RXOUTCLKPCS=,
				i_RXOUTCLKSEL=,

			# Receive Ports - RX Gearbox Ports
				o_RXDATAVALID=,
				o_RXHEADER=,
				o_RXHEADERVALID=,
				o_RXSTARTOFSEQ=,

			# Receive Ports - RX Gearbox Ports
				i_RXGEARBOXSLIP=,

			# Receive Ports - RX Initialization and Reset Ports
				i_GTRXRESET=,
				i_RXOOBRESET=,
				i_RXPCSRESET=,
				i_RXPMARESET=,

			# Receive Ports - RX Margin Analysis ports
				i_RXLPMEN=,

			# Receive Ports - RX OOB Signaling ports
				o_RXCOMSASDET=,
				o_RXCOMWAKEDET=,

			# Receive Ports - RX OOB Signaling ports
				o_RXCOMINITDET=,

			# Receive Ports - RX OOB signalling Ports
				o_RXELECIDLE=,
				i_RXELECIDLEMODE=,

			# Receive Ports - RX Polarity Control Ports
				i_RXPOLARITY=,

			# Receive Ports - RX gearbox ports
				i_RXSLIDE=,
				i_RXSLIDE=,

			# Receive Ports - RX8B/10B Decoder Ports
				o_RXCHARISCOMMA=,
				o_RXCHARISK=,

			# Receive Ports - Rx Channel Bonding Ports
				i_RXCHBONDI=,

			# Receive Ports -RX Initialization and Reset Ports
				o_RXRESETDONE=,

			# Rx AFE Ports
				i_RXQPIEN=,
				o_RXQPISENN=,
				o_RXQPISENP=,

			# TX Buffer Bypass Ports
				i_TXPHDLYTSTCL=,

			# TX Configurable Driver Ports
				i_TXPOSTCURSOR=,
				i_TXPOSTCURSORINV=,
				i_TXPRECURSOR=,
				i_TXPRECURSOR=,
				i_TXPRECURSORINV=,
				i_TXQPIBIASEN=,
				i_TXQPISTRONGPDOWN=,
				i_TXQPIWEAKPUP=,

			# TX Initialization and Reset Ports
				i_CFGRESET=,
				i_GTTXRESET=,
				o_PCSRSVDOUT=,
				i_TXUSERRDY=,

			# Transceiver Reset Mode Operation
				i_GTRESETSEL=,
				i_RESETOVRD=,

			# Transmit Ports - 8b10b Encoder Control Ports
				i_TXCHARDISPMODE=,
				i_TXCHARDISPVAL=,

			# Transmit Ports - FPGA TX Interface Ports
				i_TXUSRCLK=,
				i_TXUSRCLK2=,

			# Transmit Ports - PCI Express Ports
				i_TXELECIDLE=,
				i_TXMARGIN=,
				i_TXRATE=,
				i_TXSWING=,

			# Transmit Ports - Pattern Generator Ports
				i_TXPRBSFORCEERR=,

			# Transmit Ports - TX Buffer Bypass Ports
				i_TXDLYBYPASS=,
				i_TXDLYEN=,
				i_TXDLYHOLD=,
				i_TXDLYOVRDEN=,
				i_TXDLYSRESET=,
				o_TXDLYSRESETDONE=,
				i_TXDLYUPDOWN=,
				i_TXPHALIGN=,
				o_TXPHALIGNDONE=,
				i_TXPHALIGNEN=,
				i_TXPHDLYPD=,
				i_TXPHDLYRESET=,
				i_TXPHINIT=,
				o_TXPHINITDONE=,
				i_TXPHOVRDEN=,

			# Transmit Ports - TX Buffer Ports
				o_TXBUFSTATUS=,

			# Transmit Ports - TX Configurable Driver Ports
				i_TXBUFDIFFCTRL=,
				i_TXDEEMPH=,
				i_TXDIFFCTRL=,
				i_TXDIFFPD=,
				i_TXINHIBIT=,
				i_TXMAINCURSOR=,
				i_TXPISOPD=,

			# Transmit Ports - TX Data Path interface
				i_TXDATA=,

			# Transmit Ports - TX Driver and OOB signaling
				o_GTXTXN=,
				o_GTXTXP=,

			# Transmit Ports - TX Fabric Clock Output Control Ports
				o_TXOUTCLK=,
				o_TXOUTCLKFABRIC=,
				o_TXOUTCLKPCS=,
				i_TXOUTCLKSEL=,
				o_TXRATEDONE=,
			# Transmit Ports - TX Gearbox Ports
				i_TXCHARISK=,
				o_TXGEARBOXREADY=,
				i_TXHEADER=,
				i_TXSEQUENCE=,
				i_TXSTARTSEQ=,

			# Transmit Ports - TX Initialization and Reset Ports
				i_TXPCSRESET=,
				i_TXPMARESET=,
				o_TXRESETDONE=,

			# Transmit Ports - TX OOB signalling Ports
				o_TXCOMFINISH=,
				i_TXCOMINIT=,
				i_TXCOMSAS=,
				i_TXCOMWAKE=,
				i_TXPDELECIDLEMODE=,

			# Transmit Ports - TX Polarity Control Ports
				i_TXPOLARITY=,

			# Transmit Ports - TX Receiver Detection Ports
				i_TXDETECTRX=,

			# Transmit Ports - TX8b/10b Encoder Ports
				i_TX8B10BBYPASS=

			# Transmit Ports - pattern Generator Ports
				i_TXPRBSSEL=,

			# Tx Configurable Driver  Ports
				o_TXQPISENN=,
				o_TXQPISENP=
		)
