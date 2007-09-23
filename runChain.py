#!/usr/bin/env python

"""
Run I/O ops from a Markov chain built from blkparse output

Usage: runChain.py chainfile device

Copyright 2007 The University of New South Wales
Author: Joshua Root <jmr@gelato.unsw.edu.au>
"""

# todo: option to run for a fixed time or number of I/Os

from datetime import datetime
import directrw
import os
import sys
import thread
import time
from zipUtils import zipLoad
from IOChain import IOChain, szkey

sectorSize = 512
sectorMask = ~511

data = ""

def do_io(write, size):
	if write:
		directrw.write(dev, data[:size], size)
	else:
		newdata = directrw.read(dev, size)

if __name__ == "__main__":
	
	if len(sys.argv) < 3:
		print "Usage: runChain.py chainfile device"
		sys.exit(2)
	
	chain = zipLoad(sys.argv[1])
	
	flags = os.O_RDWR
	if hasattr(os, "O_LARGEFILE"):
		flags |= os.O_LARGEFILE
		print "using O_LARGEFILE"
	if hasattr(os, "O_DIRECT"):
		flags |= os.O_DIRECT
		print "using O_DIRECT"
	dev = os.open(sys.argv[2], flags)
	
	devsize = os.lseek(dev,0,2)
	print "device size: "+str(devsize)
	
	offset = 0
	os.lseek(dev, offset, 0)

	data.zfill(chain.stateKey[szkey][-1]) #zero filled array to write from

	lastTime = datetime.utcnow()
	while True:
		(write,size,seek,delay) = chain.genOp(chain.state)
		if size < sectorSize:
			size = sectorSize
		size &= sectorMask #whole sectors only
		seek *= sectorSize
		offset += seek
		if offset < 0:
			offset += devsize
		if (offset+size) >= devsize:
			offset -= (devsize-size)
		thisTime = datetime.utcnow()
		delta = (thisTime - lastTime)
		secs = delta.seconds + (delta.microseconds/1000000.0)
		if (secs < delay):
			time.sleep(delay-secs)
		
		offset = os.lseek(dev, offset, 0)
		print str(write)+","+str(size)+","+str(offset)+"("+str(seek)+")"+","+str(delay)
		thread.start_new_thread(do_io, (write,size))
		lastTime = datetime.utcnow()
		offset += size
		chain.step()
