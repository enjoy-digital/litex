from miscope.host.uart2wishbone import Uart2Wishbone

csr_csv_file = "./csr.csv"
busword = 32
debug_wb = False

com = 2
baud = 921600
wb = Uart2Wishbone(com, baud, csr_csv_file, busword, debug_wb)