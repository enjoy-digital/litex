from migen.genlib.record import *

def rec_dat(width):
	layout = [
			("stb", 1, DIR_M_TO_S),
			("ack", 1, DIR_S_TO_M),
			("dat", width, DIR_M_TO_S)
		]
	return Record(layout)

def rec_hit():
	layout = [
			("stb", 1, DIR_M_TO_S),
			("ack", 1, DIR_S_TO_M),
			("hit", 1, DIR_M_TO_S)
		]
	return Record(layout)

def rec_dat_hit(width):
	layout = [
			("stb", 1, DIR_M_TO_S),
			("ack", 1, DIR_S_TO_M),
			("hit", 1, DIR_M_TO_S),
			("dat", width, DIR_M_TO_S)
		]
	return Record(layout)