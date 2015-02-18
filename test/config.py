from litescope.host.driver.uart import LiteScopeUARTDriver

csr_csv_file = "./csr.csv"
busword = 32
debug_wb = False

com = 3
baud = 115200
wb = LiteScopeUARTDriver(com, baud, csr_csv_file, busword, debug_wb)