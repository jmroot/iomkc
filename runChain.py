#!/usr/bin/env python

# Copyright 2007 The University of New South Wales
# Author: Joshua Root <jmr@gelato.unsw.edu.au>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the Australian Public Licence B. See the file
# OZPLB.txt for the licence terms.

"""
Run I/O ops from a Markov chain built from blkparse output

Usage: runChain.py -i chainfile -d device [options]
"""

# todo:
# option to use async I/O (needs C module)
# a way to limit the number of in-flight I/Os
# option to "go fast", i.e. ignore delays and do each I/O immediately
# ability to specify a random seed, for reproducibility

# use psyco JIT if available (only on IA-32...)
try:
      import psyco
      psyco.full()
except ImportError:
      pass

from datetime import datetime
from getopt import gnu_getopt
import os
import sys
import threading
import time
from zipUtils import zipLoad
from IOChain import IOChain, szkey

sectorSize = 512
sectorMask = ~511

data = ""

pipe = None # is the pipe's name if we send our op data to btreplay
infilename = None
devicename = None
devicepath = None
maxOps = None
maxTime = None
verbose = False
randseed = None

def parseArgs():
      global infilename, devicepath, devicename, maxOps, maxTime,\
             pipe, verbose, randseed
      optlist, args = gnu_getopt(sys.argv[1:], "d:i:n:r:t:p:v")
      for opt,val in optlist:
            if opt == "-d":
                  # this should be the full path e.g. /dev/sdb
                  devicepath = val
            elif opt == "-i":
                  infilename = val
            elif opt == "-n":
                  maxOps = int(val)
            elif opt == "-t":
                  maxTime = float(val) #in seconds
            elif opt == "-p":
                  pipe = val
            elif opt == "-r":
                  randseed = int(val)
            elif opt == "-v":
                  verbose = True
            else:
                  print "Unknown option: "+opt
                  sys.exit(2)
      
      if infilename is None or devicepath is None:
            print "Usage: runChain.py -i chainfile -d device [options]"
            sys.exit(2)

      if pipe:
            devicename = devicepath.split('/')[-1]

def do_io(write, size):
      if write:
            directrw.write(dev, data[:size], size)
      else:
            newdata = directrw.read(dev, size)

if __name__ == "__main__":

      parseArgs()
      
      if pipe:
            import btrecord
      else:
            import directrw
      
      chain = zipLoad(infilename)

      chain.randSeed(randseed)
      
      offset = 0
      flags = os.O_RDWR
      if hasattr(os, "O_LARGEFILE"):
            flags |= os.O_LARGEFILE
            if verbose:
                  print "using O_LARGEFILE"
      if hasattr(os, "O_DIRECT"):
            flags |= os.O_DIRECT
            if verbose:
                  print "using O_DIRECT"
      dev = os.open(devicepath, flags)
      devsize = os.lseek(dev,0,2)
      if verbose:
            print "device size: "+str(devsize)

      if not pipe:
            os.lseek(dev, offset, 0)

            data.zfill(chain.stateKey[szkey][-1]) #zero filled array to write from
            startnthreads = threading.activeCount()
            startTime = datetime.utcnow()
      else:
            os.close(dev)
            btrecord.setOutFile(pipe, devicename)
            startTime = 0

      opsDone = 0
      lastTime = startTime
      while True:
            if maxOps and opsDone >= maxOps:
                  break
            if maxTime:
                  totaltime = lastTime - startTime
                  if not pipe:
                        totalsecs = totaltime.seconds + (totaltime.microseconds/1000000.0)
                  else:
                        # blktrace timestamp
                        totalsecs = float(totaltime) / 1000000000
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
            
            if verbose:
		  if write:
		        rw = 'w' 
		  else:
		        rw = 'r'
                  print rw+","+str(size)+","+str(offset)+"("+str(seek)+")"+","+str(delay)

            if not pipe:
                  thisTime = datetime.utcnow()
                  delta = (thisTime - lastTime)
                  secs = delta.seconds + (delta.microseconds/1000000.0)
                  if (secs < delay):
                        time.sleep(delay-secs)
		
                  offset = os.lseek(dev, offset, 0)
                  newthread = threading.Thread(target=do_io, args=(write,size))
                  newthread.start()
                  lastTime = datetime.utcnow()
            else:
                  lastTime += int(delay*1000000000)
                  btrecord.addOp(write, size, offset/sectorSize, lastTime)
            
            offset += size
            chain.step()
            opsDone += 1

      if pipe:
            btrecord.done()
      else:
            while threading.activeCount() > startnthreads:
                  time.sleep(0.001)
            os.close(dev)
