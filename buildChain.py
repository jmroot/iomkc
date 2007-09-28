#!/usr/bin/env python

"""
Generate Markov chain based on blkparse output

Usage: buildChain.py -i infile -o outfile [options]

Copyright 2007 The University of New South Wales
Author: Joshua Root <jmr@gelato.unsw.edu.au>
"""

# speed things up with psyco if available (it isn't on 64-bit platforms...)
try:
      import psyco
      psyco.full()
except ImportError:
      pass

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

sizeGranule = 4096
seekGranule = 131072
delayGranule = 0.001

infilename = None
outfilename = None

bigmem = False #setting True keeps trace data in memory rather than two-pass streaming

def parseArgs():
      global sizeGranule, seekGranule, delayGranule, infilename, outfilename
      optlist, args = gnu_getopt(sys.argv[1:], "d:i:k:mo:s:")
      for opt,val in optlist:
            if opt == "-i":
                  infilename = val
            elif opt == "-o":
                  outfilename = val
            elif opt == "-s":
                  sizeGranule = int(val)
            elif opt == "-k":
                  seekGranule = int(val)
            elif opt == "-d":
                  delayGranule = float(val)
            elif opt == "-m":
                  bigmem = True
            else:
                  print "Unknown option: "+opt
                  sys.exit(2)
      
      if infilename is None or outfilename is None:
            print "Usage: buildChain.py -i infile -o outfile [options]"
            sys.exit(2)

def parseLine(line):
      words = line.split()
      rw = words[1][0] == 'W'
      size = int(words[2])
      sector = int(words[3])
      secs = float(words[4])
      
      return (rw,size,sector,secs)

def classify(op, key):
      #print "size,seek,delay = "+str((size,seek,delay))
      sz = op[stsz] / sizeGranule
      seek = op[stsk]
      if seek > 0:
            sk = ((seek-minSeek) / seekGranule) + 2 # 0,1 inserted specially
      elif seek < 0:
            sk = (seek-minSeek) / seekGranule
      else:
            sk = skzero
      dl = int(op[stdl] / delayGranule)

      return (op[strw], sz, sk, dl)


if __name__ == "__main__":

      transitionCounts = {} # state -> (state -> int)
      key = [[], [], []] # list of bucket boundaries

      # defaults (can be overridden with command line options):
      # buckets: r/w=2, seek=7 (farback,medback,nearback,0,nearfwd,
      #                         medfwd,farfwd),
      # size=10, delay=10
      # state space size = 1400, (possible) graph edges = 1.96M

      lastTime = 0.0
      lastSector = 0
      maxSeek = -sys.maxint-1
      minSeek = sys.maxint
      seekSum = 0
      maxSize = 0
      sizeSum = 0
      maxDelay = 0.0
      delaySum = 0.0

      parseArgs()
      
      if bigmem:
            ops = []

      print "First pass"
      infile = open(infilename)
      for line in infile:
            rw,size,sector,thisTime = parseLine(line)
            
            if maxSize < size:
                  maxSize = size

            seek = sector - lastSector
            if maxSeek < seek:
                  maxSeek = seek
            if minSeek > seek:
                  minSeek = seek
            lastSector = sector + (size/sectorSize)

            delay = thisTime - lastTime
            if maxDelay < delay:
                  maxDelay = delay
            lastTime = thisTime
            
            if bigmem:
                  ops.append((rw,size,seek,delay))
      
      if bigmem:
            infile.close()

      print "Creating buckets"
      # key defines the buckets into which to divide ops
      nsz = maxSize / sizeGranule
      for i in range(nsz+1):
            key[szkey].append(i*sizeGranule)
      key[szkey].append(maxSize+1)

      nsk = (maxSeek - minSeek) / seekGranule
      for i in range(nsk+1):
            val = minSeek + i*seekGranule
            if (val >= 0 and val-seekGranule < 0):
                  # special-case sequential access
                  # might be duplicates sometimes, but hey
                  skzero = i
                  key[skkey].append(0)
                  key[skkey].append(1)
                  #print "skzero is "+str(skzero)+", points to "+str(key[skkey][skzero])
            key[skkey].append(val)
      key[skkey].append(maxSeek+1)

      ndl = int(maxDelay / delayGranule)
      for i in range(ndl+1):
            key[dlkey].append(i*delayGranule)
      key[dlkey].append(maxDelay) #twice on the end, to limit it
      
      print "nsz,nsk,ndl = "+str(nsz)+","+str(nsk)+","+str(ndl)
      #print str(key)

      print "Second pass"
      
      if bigmem:
            initialState = classify(ops[0], key)
            lastState = initialState
            for op in ops[1:]:
                  state = classify(op, key)
                  if lastState in transitionCounts:
                        if state in transitionCounts[lastState]:
                              transitionCounts[lastState][state] += 1
                        else:
                              transitionCounts[lastState][state] = 1
                  else:
                        transitionCounts[lastState] = {}
                        transitionCounts[lastState][state] = 1
                  lastState = state
      else:
            infile.seek(0)
            # special-case first op since it doesn't come from any other one -- sigh
            line = infile.readline()
            rw,size,sector,thisTime = parseLine(line)
            lastSector = sector + (size/sectorSize)
            lastTime = thisTime
            op = (rw, size, 0, 0.0) #arbitrarily call it sequential
            initialState = classify(op, key)
            lastState = initialState
      
            for line in infile:
                  rw,size,sector,thisTime = parseLine(line)
                  seek = sector - lastSector
                  lastSector = sector + (size/sectorSize)
                  delay = thisTime - lastTime
                  lastTime = thisTime

                  state = classify((rw, size, seek, delay), key)
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
