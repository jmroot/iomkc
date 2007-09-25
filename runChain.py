#!/usr/bin/env python

"""
Run I/O ops from a Markov chain built from blkparse output

Usage: runChain.py -i chainfile -d device [options]

Copyright 2007 The University of New South Wales
Author: Joshua Root <jmr@gelato.unsw.edu.au>
"""

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

infilename = None
devicename = None
maxOps = None
maxTime = None

def parseArgs():
      global infilename, devicename, maxOps, maxTime
      optlist, args = gnu_getopt(sys.argv[1:], "d:i:n:t:")
      for opt,val in optlist:
            if opt == "-d":
                  devicename = val
            elif opt == "-i":
                  infilename = val
            elif opt == "-n":
                  maxOps = int(val)
            elif opt == "-t":
                  maxTime = float(val) #in seconds
            else:
                  print "Unknown option: "+opt
                  sys.exit(2)
      
      if infilename is None or devicename is None:
            print "Usage: runChain.py -i chainfile -d device [options]"
            sys.exit(2)

def do_io(write, size):
	if write:
		directrw.write(dev, data[:size], size)
	else:
		newdata = directrw.read(dev, size)

if __name__ == "__main__":
	
	parseArgs()
	chain = zipLoad(infilename)
	
	flags = os.O_RDWR
	if hasattr(os, "O_LARGEFILE"):
		flags |= os.O_LARGEFILE
		print "using O_LARGEFILE"
	if hasattr(os, "O_DIRECT"):
		flags |= os.O_DIRECT
		print "using O_DIRECT"
	dev = os.open(devicename, flags)
	
	devsize = os.lseek(dev,0,2)
	print "device size: "+str(devsize)
	
	offset = 0
	os.lseek(dev, offset, 0)

	data.zfill(chain.stateKey[szkey][-1]) #zero filled array to write from

      opsDone = 0
      startTime = datetime.utcnow()
      lastTime = startTime
	while True:
            if maxOps is not None and opsDone >= maxOps:
                  break
            if maxTime is not None:
                  totaltime = datetime.utcnow() - startTime
                  totalsecs = totaltime.seconds + (totaltime.microseconds/1000000.0)
                  if totalsecs >= maxTime:
                        break

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
            opsDone += 1
