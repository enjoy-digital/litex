#!/usr/bin/env python3

# Copyright (c) 2014 Guy Hutchison

# Redistribution and use in source and binary forms, with or without modification,
# are permitted provided that the following conditions are met:

# 1. Redistributions of source code must retain the above copyright notice, this
#    list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.

# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR
# ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
# (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON
# ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

import migen
import operator
from migen.fhdl.std import *
from migen.fhdl.verilog import convert


# Join two lists a and b, such that redundant terms are removed
def join_lists(a, b):
	z = []
	for x in a+b:
		if x not in z:
			z.append(x)
		else:
			z.remove(x)
	return z


def join_operator(list, op):
	if len(list) == 0:
		return []
	elif len(list) == 1:
		return list[0]
	elif len(list) == 2:
		return op(list[0], list[1])
	else:
		return op(list[0], join_operator(list[1:], op))


def calc_code_bits(data_bits):
	m = 1
	c = 0

	while c < data_bits:
		m += 1
		c = 2**m - m - 1
	return m


# build_seq() is used to create the selection of bits which need
# to be checked for a particular data parity bit.
def build_seq(bnum, out_width):
	tmp = []

	ptr = 0
	cur = 0
	skip = 2**bnum-1
	if skip == 0:
		check = 2**bnum
	else:
		check = 0
	while cur < out_width:
		if check > 0:
			if (cur != 2**bnum-1):
				tmp.append(cur)
				ptr += 1
			check -= 1
			if check == 0:
				skip = 2**bnum
		else:
			skip -= 1
			if skip == 0:
				check = 2**bnum
		cur += 1

	return tmp


# build_bits() is used for the generator portion, it combines the
# bit sequences for all input and parity bits which are used and
# removes redundant terms.
def build_bits(in_width, gen_parity=True):
	pnum = 1
	innum = 0
	blist = []
	num_code_bits = calc_code_bits(in_width)
	out_width = in_width + num_code_bits
	v = [list()] * out_width
	code_bit_list = []

	for b in range(out_width):
		if (b+1) == pnum:
			pnum = 2*pnum
		else:
			v[b] = [innum]
			innum += 1

	for b in range(num_code_bits):
		vindex = 2**b-1
		blist = build_seq(b, out_width)
		for bli in blist:
			v[vindex] = join_lists(v[vindex], v[bli])
		code_bit_list.append(v[vindex])

	# Calculate parity bit
	if gen_parity:
		pbit = []
		for b in v:
			pbit = join_lists(pbit, b)
		code_bit_list.append(pbit)
	return code_bit_list


# xor_tree() takes a signal and a list of bits to be applied from
# the signal and generates a balanced xor tree as output.
def xor_tree(in_signal, in_bits):
	if len(in_bits) == 0:
		print ("ERROR: in_bits must be > 0")
	elif len(in_bits) == 1:
		return in_signal[in_bits[0]]
	elif len(in_bits) == 2:
		return in_signal[in_bits[0]] ^ in_signal[in_bits[1]]
	elif len(in_bits) == 3:
		return in_signal[in_bits[0]] ^ in_signal[in_bits[1]] ^ in_signal[in_bits[2]]
	else:
		split = int(len(in_bits)/2)
		return xor_tree(in_signal, in_bits[0:split]) ^ xor_tree(in_signal, in_bits[split:])


# Base class for Hamming code generator/checker.


# Hamming code generator class

# The class constructor takes a single required input, which is the number of
# bits of the input data.  The module creates a single output, which is a set
# of code check bits and a parity bit.

# This generator and its corresponding checker will only generate a single-
# error correct, double-error detect code.  If double-error detection is
# not desired, the most-significant code_out bit can be left unconnected.

# If generated as a top-level module, contains its suggested module name
# in self.name and list of ports in self.ports
class HammingGenerator(Module):
	def __init__(self, input_size):
		self.input_size = input_size
		self.data_in = Signal(input_size)
		self.code_out = Signal(calc_code_bits(input_size)+1)

		xor_bits = build_bits(self.input_size)
		for b in range(len(xor_bits)):
			self.comb += self.code_out[b].eq(xor_tree(self.data_in, xor_bits[b]))


# Hamming code checker class

# Constructor takes two parameters:
#  input_size (bits of data bus, not counting check bits)
#  correct (boolean, True if output data should be corrected)

# If used as a check/correct module, the module creates an
# enable input which can dynamically turn off error correction
# for debug.

# If double-bit detection is not desired, the most-significant
# code_in bit can be tied to 0, and the dberr output port left
# unconnected.

# If generated as a top-level module, contains its suggested module name
# in self.name and list of ports in self.ports
class HammingChecker(Module):
	def __init__(self, input_size, correct=True, gen_parity=True):
		self.input_size = input_size
		self.correct = correct
		self.data_in = Signal(input_size)
		self.code_bits = calc_code_bits(input_size)
		self.code_in = Signal(self.code_bits+1)
		self.code_out = Signal(self.code_bits)
		self.sberr = Signal()
		if gen_parity:
			self.dberr = Signal()

		# vector of which interleaved bit position represents a particular
		# data bit, used for error correction
		dbits = []

		# Create interleaved vector of code bits and data bits with code bits
		# in power-of-two positions
		pnum = 0
		dnum = 0
		self.par_vec = Signal(input_size+self.code_bits)
		for b in range(input_size+calc_code_bits(input_size)):
			if b+1 == 2**pnum:
				self.comb += self.par_vec[b].eq(self.code_in[pnum])
				pnum += 1
			else:
				self.comb += self.par_vec[b].eq(self.data_in[dnum])
				dbits.append(b)
				dnum += 1

		if correct:
			self.enable = Signal()
			self.correct_out = Signal(input_size)
			self.data_out = Signal(input_size, name='data_out')
			for b in range(input_size):
				self.comb += self.correct_out[b].eq((self.code_out == (dbits[b]+1)) ^ self.data_in[b])
			self.comb += If(self.enable, self.data_out.eq(self.correct_out)).Else(self.data_out.eq(self.data_in))

		self.comb += self.sberr.eq(self.code_out != 0)
		if gen_parity:
			parity = Signal()
			self.comb += parity.eq(xor_tree(self.data_in, range(input_size)) ^ xor_tree(self.code_in, range(self.code_bits+1)))
			self.comb += self.dberr.eq(~parity)

		for b in range(calc_code_bits(self.input_size)):
			bits = [2**b-1]
			bits += build_seq(b, self.input_size+calc_code_bits(self.input_size))
			self.comb += self.code_out[b].eq(xor_tree(self.par_vec, bits))
