#!/usr/bin/env python

# Copyright 2007 The University of New South Wales
# Author: Joshua Root <jmr@gelato.unsw.edu.au>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the Australian Public Licence B. See the file
# OZPLB.txt for the licence terms.

"""
Generate Markov chain based on blkparse output

Usage: buildChain.py -i infile -o outfile [options]
"""

# use psyco JIT if available (only on IA-32...)
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

# completely arbitrary "reasonable" default granularities
sizeGranule = 1024
seekGranule = 131072
delayGranule = 0.001

infilename = None
outfilename = None

bigmem = False #setting True keeps trace data in memory rather than two-pass streaming

def parseArgs():
      """Handle command-line options."""
      global sizeGranule, seekGranule, delayGranule, infilename, outfilename, bigmem
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
      if words[0] == 'C':
            return None
      rw = words[1][0] == 'W'
      size = int(words[2])
      sector = int(words[3])
      secs = float(words[4])
      name = ""
      if len(words) > 5: 
            name = words[5]
      
      return (rw,size,sector,secs,name)

def classify(op):
      """Determine which bucket number each quantity belongs in."""
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
      
def makeBuckets(maxSize, maxSeek, minSeek, maxDelay):
      """
      Define the ranges of the buckets for each quantity, based on the desired
      granularity and the quantities' ranges in the input.
      """
      global skzero
      key = [[], [], []]
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
      return key

def findMinMax(infile):
      """Determine the range that each quantity traverses in the input."""
      global ops
      maxSeek = -sys.maxint-1
      minSeek = sys.maxint
      maxSize = 0
      maxDelay = 0.0
      lastTime = 0.0
      lastSector = 0
      
      infile.seek(0)
      for line in infile:
            words = line.split()
            if words[0] == 'C':
                  continue
            size = int(words[2])
            sector = int(words[3])
            thisTime = float(words[4])
            name = ""
            if len(words) > 5: 
                  name = words[5]
            
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
                  rw = words[1][0] == 'W'
                  ops.append((rw,size,seek,delay))
      
      return (maxSize, maxSeek, minSeek, maxDelay)

def countTransitions(infile):
      """Count the transitions between pairs of states in the input."""
      transitionCounts = {} # state -> (state -> int)
      
      if bigmem:
            initialState = classify(ops[0])
            lastState = initialState
            for op in ops[1:]:
                  state = classify(op)
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
            line = infile.next()
            parsedLine = None
            while parsedLine is None:
                  parsedLine = parseLine(line)
            rw,size,sector,thisTime,name = parsedLine
            lastSector = sector + (size/sectorSize)
            lastTime = thisTime
            op = (rw, size, 0, 0.0) #arbitrarily call it sequential
            initialState = classify(op)
            lastState = initialState
      
            for line in infile:
                  words = line.split()
                  # preparing for proper thinktime calculation,
                  # i.e. C-Q rather than Q-Q
                  if words[0] == 'C':
                        continue
                  rw = words[1][0] == 'W'
                  sector = int(words[3])
                  thisTime = float(words[4])
                  name = ""
                  if len(words) > 5: 
                        name = words[5]
                  
                  seek = sector - lastSector
                  lastSector = sector + (size/sectorSize)
                  delay = thisTime - lastTime
                  lastTime = thisTime

                  state = classify((rw, int(words[2]), seek, delay))
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
      return transitionCounts, initialState

if __name__ == "__main__":

      parseArgs()
      
      if bigmem:
            ops = []

      infile = open(infilename)
      print "First pass"
      (maxSize, maxSeek, minSeek, maxDelay) = findMinMax(infile)
      if bigmem:
            infile.close()
      
      print "Defining buckets"
      key = makeBuckets(maxSize, maxSeek, minSeek, maxDelay)
      
      print "Second pass"
      (transitionCounts, initialState) = countTransitions(infile)
      if bigmem:
            ops = None #free up the memory used by the op list
      else:
            infile.close()

      print "Building chain"
      chain = IOChain(initialState, key, transitionCounts)
      print "Saving"
      zipSave(outfilename, chain)
