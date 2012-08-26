import os
import re 
import sys

def get_operands(s):
	return sorted(re.findall("[A-z0-9_]+",s))

def gen_truth_table(s):
	operands = get_operands(s)
	width = len(operands)
	stim = []
	for i in range(width):
		stim_op = []
		for j in range(2**width):
			stim_op.append((int(j/(2**i)))%2)
		stim.append(stim_op)
	
	truth_table = []
	for i in range(2**width):
		for j in range(width):
			exec("%s = stim[j][i]" %operands[j])
		truth_table.append(eval(s))
	return truth_table

def main():
	print(gen_truth_table("(A&B&C)|D"))

if __name__ == '__main__':
  main()
