#!/usr/bin/env python

"""
Generate Markov chain based on blkparse output

Usage: buildChain.py infile outfile

Copyright 2007 The University of New South Wales
Author: Joshua Root <jmr@gelato.unsw.edu.au>
"""

import re
import sys
from zipUtils import zipSave
from IOChain import IOChain

# An op is (r/w,seek,size,delay)
# size is bytes but seek is sectors, thanks to blkparse
# A state is a tuple of bucket numbers
# A state's step fn is [p1->s1,(p1+p2)->s2,(p1+p2+p3)->s3,...]
# I guess we assume 512-byte sectors
sectorSize = 512

def classify(op, key):
	rw = op[0]
	size = op[1]
	seek = op[2]
	delay = op[3]
	sizeKey = key[0]
	seekKey = key[1]
	delayKey = key[2]
	for i in range(len(sizeKey)):
		if size < sizeKey[i]:
			sz = i
			break
	for i in range(len(seekKey)):
		if seek < seekKey[i]:
			sk = i
			break
	for i in range(len(delayKey)):
		if delay < delayKey[i]:
			dl = i
			break
	
	return (rw, sz, sk, dl)


if __name__ == "__main__":
	
	if len(sys.argv) < 3:
		print "Usage: buildChain.py infile outfile"
		sys.exit(2)
	
	transitionCounts = {} # state -> (state -> int)
	key = [[], [], []] # list of bucket boundaries
	
	# buckets: r/w=2, seek=7 (farback,medback,nearback,0,nearfwd,medfwd,farfwd),
	# size=10, delay=10 -- change these if necessary
	# state space size = 1400, graph edges = 1.96M
	
	totalOps = 0
	lastTime = 0.0
	lastSector = 0
	maxSeek = -sys.maxint-1
	minSeek = sys.maxint
	maxSize = 0
	maxDelay = 0.0
	regex = re.compile(r"Q (..?) (\d+) (\d+) (\d+(\.\d*)?|\.\d+)([eE][-+]?\d+)?")
	
	print "First pass"
	infile = open(sys.argv[1])
	for line in infile:
		match = regex.match(line)
		if match is not None:
			groups = match.groups()
			
			size = int(groups[1])
			if maxSize < size:
				maxSize = size
			
			seek = int(groups[2]) - lastSector
			if maxSeek < seek:
				maxSeek = seek
			if minSeek > seek:
				minSeek = seek
			lastSector = int(groups[2]) + (size/sectorSize)
			
			delay = float(groups[3]) - lastTime
			if maxDelay < delay:
				maxDelay = delay
			lastTime = float(groups[3])
	
	print "Creating buckets"
	# key defines the buckets into which to divide ops
	sizeGranule = maxSize / 10
	seekGranule = (maxSeek - minSeek) / 6
	delayGranule = maxDelay / 10

	key[0].append(0) #simplifies building ops
	for i in range(1,10):
		key[0].append(i*sizeGranule)
	key[0].append(maxSize + 1) # so all ops will match a bucket

	key[1].append(minSeek) #need to know it when generating ops later
	key[1].append(minSeek + seekGranule)
	key[1].append(minSeek + 2*seekGranule)
	key[1].append(0)
	key[1].append(1) #special case sequential access
	key[1].append(maxSeek - 2*seekGranule)
	key[1].append(maxSeek - seekGranule)
	key[1].append(maxSeek + 1)

	key[2].append(0.0)
	for i in range(1,10):
		key[2].append(i*delayGranule)
	key[2].append (maxDelay + 1)
	
	print "Second pass"
	infile.seek(0)
	# special-case first op since it doesn't come from
	# any other one -- sigh
	line = infile.readline()
	match = regex.match(line)
	if match is not None:
		groups = match.groups()
		rw = groups[0][0] == 'W'
		size = int(groups[1])
		lastSector = int(groups[2]) + (size/sectorSize)
		lastTime = float(groups[3])
	else:
		raise ValueError("First input line couldn't be parsed")
	op = (rw, size, 0, 0.0) #arbitrarily call it sequential
	initialState = classify(op, key)
	lastState = initialState
	
	for line in infile:
		match = regex.match(line)
		if match is not None:
			groups = match.groups()
			rw = groups[0][0] == 'W'
			size = int(groups[1])
			seek = int(groups[2]) - lastSector
			lastSector = int(groups[2]) + (size/sectorSize)
			delay = float(groups[3]) - lastTime
			lastTime = float(groups[3])
		
			op = (rw, size, seek, delay)
			state = classify(op, key)
			# increment lastState->state transition count
			if lastState in transitionCounts:
				if state in transitionCounts[lastState]:
					transitionCounts[lastState][state] += 1
				else:
					transitionCounts[lastState][state] = 1
			else:
				transitionCounts[lastState] = {}
				transitionCounts[lastState][state] = 1
			lastState = state
	
	infile.close()
	
	print "Building chain"
	chain = IOChain(initialState, key, transitionCounts)
	print "Saving"
	zipSave(sys.argv[2], chain)
