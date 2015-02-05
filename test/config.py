from litescope.host.driver import LiteScopeUART2WBDriver

csr_csv_file = "./csr.csv"
busword = 32
debug_wb = False

com = 2
baud = 921600
wb = LiteScopeUART2WBDriver(com, baud, csr_csv_file, busword, debug_wb)