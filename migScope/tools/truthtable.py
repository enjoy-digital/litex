import os
import re 
import sys

def remove_duplicates(seq):
    seen = set()
    seen_add = seen.add
    return [ x for x in seq if x not in seen and not seen_add(x)]

def get_operands(s):
	operands = remove_duplicates(sorted(re.findall("[A-z0-9_]+", s)))
	return operands

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
		truth_table.append(eval(s) != 0)
	return truth_table

def main():
	print(gen_truth_table("(A&B&C)|D"))

if __name__ == '__main__':
  main()
