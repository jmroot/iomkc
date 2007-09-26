#!/usr/bin/env python

"""
Generate Markov chain based on blkparse output

Usage: buildChain.py -i infile -o outfile [options]

Copyright 2007 The University of New South Wales
Author: Joshua Root <jmr@gelato.unsw.edu.au>
"""

import re
import sys
from getopt import gnu_getopt
from zipUtils import zipSave
from IOChain import IOChain, szkey, skkey, dlkey, strw, stsz, stsk, stdl

# An op is (r/w,seek,size,delay)
# size is bytes but seek is sectors, thanks to blkparse
# A state is a tuple of bucket numbers
# A state's step fn is [p1->s1,(p1+p2)->s2,(p1+p2+p3)->s3,...]
# I guess we assume 512-byte sectors. Maybe it should be an option.
sectorSize = 512
nsz = 10 #number of size buckets
nsk = 7 #seek
ndl = 10 #delay
infilename = None
outfilename = None

def parseArgs():
      global nsz, nsk, ndl, infilename, outfilename
      optlist, args = gnu_getopt(sys.argv[1:], "d:i:k:o:s:")
      for opt,val in optlist:
            if opt == "-i":
                  infilename = val
            elif opt == "-o":
                  outfilename = val
            elif opt == "-s":
                  nsz = int(val)
            elif opt == "-k":
                  nsk = int(val)
            elif opt == "-d":
                  ndl = int(val)
            else:
                  print "Unknown option: "+opt
                  sys.exit(2)
      
      if infilename is None or outfilename is None:
            print "Usage: buildChain.py -i infile -o outfile [options]"
            sys.exit(2)

def classify(op, key):
	rw = op[strw]
	size = op[stsz]
	seek = op[stsk]
	delay = op[stdl]
	sizeKey = key[szkey]
	seekKey = key[skkey]
	delayKey = key[dlkey]
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
	
	transitionCounts = {} # state -> (state -> int)
	key = [[], [], []] # list of bucket boundaries
	
	# defaults (can be overridden with command line options):
	# buckets: r/w=2, seek=7 (farback,medback,nearback,0,nearfwd,
        #                         medfwd,farfwd),
	# size=10, delay=10
	# state space size = 1400, (possible) graph edges = 1.96M
	
	totalOps = 0
	lastTime = 0.0
	lastSector = 0
	maxSeek = -sys.maxint-1
	minSeek = sys.maxint
	seekSum = 0
	maxSize = 0
	sizeSum = 0
	maxDelay = 0.0
	delaySum = 0.0
	regex = re.compile(r"Q (..?) (\d+) (\d+) (\d+(\.\d*)?|\.\d+)")
	
	parseArgs()
	
	print "First pass"
	infile = open(infilename)
	for line in infile:
		match = regex.match(line)
		if match is not None:
			groups = match.groups()
			
			totalOps += 1
                        
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
	sizeGranule = maxSize / nsz
	seekGranule = (maxSeek - minSeek) / (nsk-1) #special-case 0 (sequential)
	delayGranule = maxDelay / ndl

	key[szkey].append(0) #simplifies building ops
	for i in range(1,nsz):
		key[szkey].append(i*sizeGranule)
	key[szkey].append(maxSize + 1) # so all ops will match a bucket

      # XXX need to fix this to work properly with variable nsk
	key[skkey].append(minSeek) #need to know it when generating ops later
	key[skkey].append(minSeek + seekGranule)
	key[skkey].append(minSeek + 2*seekGranule)
	key[skkey].append(0)
	key[skkey].append(1) #special case sequential access
	key[skkey].append(maxSeek - 2*seekGranule)
	key[skkey].append(maxSeek - seekGranule)
	key[skkey].append(maxSeek + 1)

	key[dlkey].append(0.0)
	for i in range(1,ndl):
		key[dlkey].append(i*delayGranule)
	key[dlkey].append(maxDelay + 1)
	
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
	zipSave(outfilename, chain)
