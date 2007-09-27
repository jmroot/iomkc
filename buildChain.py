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

sizeGranule = 4096
seekGranule = 131072
delayGranule = 0.01

infilename = None
outfilename = None

def parseArgs():
      global sizeGranule, seekGranule, delayGranule, infilename, outfilename
      optlist, args = gnu_getopt(sys.argv[1:], "d:i:k:o:s:")
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
            else:
                  print "Unknown option: "+opt
                  sys.exit(2)
      
      if infilename is None or outfilename is None:
            print "Usage: buildChain.py -i infile -o outfile [options]"
            sys.exit(2)

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
      regex = re.compile(r"Q (..?) (\d+) (\d+) (\d+(\.\d*)?|\.\d+)")

      parseArgs()

      print "First pass"
      infile = open(infilename)
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
      nsz = maxSize / sizeGranule
      key[szkey].append(0) #simplifies building ops
      for i in range(1,nsz):
            key[szkey].append(i*sizeGranule)
      key[szkey].append(maxSize + 1) # so all ops will match a bucket

      nsk = (maxSeek - minSeek) / seekGranule
      for i in range(nsk-1):
            val = minSeek + i*seekGranule
            if (val >= 0 and val-seekGranule < 0):
                  # special-case sequential access
                  # might be duplicates sometimes, but hey
                  skzero = i+1
                  key[skkey].append(0)
                  key[skkey].append(1)
                  #print "skzero is "+str(skzero)+", points to "+str(key[skkey][skzero])
            key[skkey].append(val)
      key[skkey].append(maxSeek + 1)

      ndl = int(maxDelay / delayGranule)
      key[dlkey].append(0.0)
      for i in range(1,ndl):
            key[dlkey].append(i*delayGranule)
      key[dlkey].append(maxDelay + 1)
      
      print "nsz,nsk,ndl = "+str(nsz)+","+str(nsk)+","+str(ndl)
      #print str(key)

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
