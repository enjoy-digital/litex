from migen.genlib.record import *

def dat_layout(dw):
	return [
		("stb", 1, DIR_M_TO_S),
		("dat", dw, DIR_M_TO_S)
	]

def hit_layout():
	return [
		("stb", 1, DIR_M_TO_S),
		("hit", 1, DIR_M_TO_S)
	]
