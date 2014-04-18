import binascii

def CRC32(buf):
	return binascii.crc32(buf).to_bytes(4, byteorder='big')

def LENGTH(buf):
	return len(buf).to_bytes(4, byteorder='big')

def insert_crc(i_filename, o_filename=None):
	f = open(i_filename, 'rb+')
	fdata = f.read()
	fcrc = CRC32(fdata)
	flength = LENGTH(fdata)
	f.close()

	# Write the CRC32 in big endian at the end of the file
	if o_filename is None:
		f = open(i_filename, 'wb')
		f.write(fdata)
		f.write(fcrc)
		f.close()

	# Write a new file prepended with the size and CRC
	else:
		f = open(o_filename, 'wb')
		f.write(flength)
		f.write(fcrc)
		f.write(fdata)
		f.close()
