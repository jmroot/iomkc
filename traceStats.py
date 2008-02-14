#! /usr/bin/env python

# Copyright 2007 The University of New South Wales
# Author: Joshua Root <jmr@gelato.unsw.edu.au>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the Australian Public Licence B. See the file
# OZPLB.txt for the licence terms.

"""
Calculate statistics for a trace
"""

# use psyco JIT if available (only on IA-32...)
try:
      import psyco
      psyco.full()
except ImportError:
      pass

from getopt import gnu_getopt
import scipy.stats.distributions
import math
import re
import sys

sectorSize = 512
bigmem = False #setting True keeps trace data in memory rather than two-pass streaming
do_fio = False # output an fio job file that approximates the commands' access patterns

def parseArgs():
      """Handle command-line options."""
      global infilename, bigmem, do_fio
      optlist, args = gnu_getopt(sys.argv[1:], "i:mf")
      for opt,val in optlist:
            if opt == "-i":
                  infilename = val
            elif opt == "-m":
                  bigmem = True
            elif opt == "-f":
                  do_fio = True
            else:
                  print "Unknown option: "+opt
                  sys.exit(2)

      if infilename is None:
            print "Usage: traceStats.py -i infile [-m]"
            sys.exit(2)

class TSVals(object):
      """Values for a particular process"""
      def __init__(self):
            if bigmem:
                  self.ops = []
            self.totalOps = 0
            self.lastTime = 0.0
            self.lastCompletion = 0.0
            self.lastSector = 0
            self.depth = 0
            self.maxDepth = 0
      
            self.reads = 0
            self.writes = 0
            self.lastWasRead = True
            self.dirSwaps = 0
            self.dirSwapTime = 0.0
            self.lastDirSwap = 0.0
            self.sync = 0
            self.async = 0

            self.maxRead = -sys.maxint-1
            self.maxWrite = -sys.maxint-1
            self.minRead = sys.maxint
            self.minWrite = sys.maxint

            self.maxSeek = -sys.maxint-1
            self.minSeek = sys.maxint
            self.seekSum = 0
            self.sequentialCount = 0

            self.minSize = sys.maxint
            self.maxSize = 0
            self.sizeSum = 0

            self.minDelay = float(sys.maxint)
            self.maxDelay = 0.0
            self.delaySum = 0.0
            self.meanThink = 0.0

            self.szVar = 0
            self.skVar = 0
            self.dlVar = 0

            self.nbins = 1000 # yeah, that's "lots", right?

      def initBins(self):
            self.szBins = {}
            self.szBinWidth = float(self.maxSize-self.minSize)/(self.nbins-1)
            if self.szBinWidth == 0.0:
                  self.szBinWidth = float(self.maxSize)
            
            self.skBins = {}
            self.skBinWidth = float(self.maxSeek-self.minSeek)/(self.nbins-1)
            if self.skBinWidth == 0.0:
                  self.skBinWidth = float(self.maxSeek)
            
            self.dlBins = {}
            self.dlBinWidth = (self.maxDelay-self.minDelay)/(self.nbins-1)
            if self.dlBinWidth == 0.0:
                  self.dlBinWidth = float(self.maxDelay)
            
            for bin in range(self.nbins):
                  self.szBins[bin] = 0
                  self.skBins[bin] = 0
                  self.dlBins[bin] = 0

      def calcChi2(self):
            szdist = {}
            szdist["norm"] = lambda x:scipy.stats.distributions.norm.cdf( \
                  x,loc=self.meanSize,scale=self.szDev)

            if self.szVar == 0.0:
                  self.szVar = 0.001 #HACK
            sztheta = self.szVar / self.meanSize
            szk = self.meanSize / sztheta
            szdist["gamma"] = lambda x:scipy.stats.distributions.gamma.cdf( \
                  x, szk, scale=sztheta)
            szdist["poisson"] = lambda x:scipy.stats.distributions.poisson.cdf( \
                  int(round(x)), self.meanSize)
            szdist["uniform"] = lambda x:scipy.stats.distributions.uniform.cdf( \
                  x, loc=self.minSize, scale=(self.maxSize-self.minSize))

            skdist = {}
            skdist["norm"] = lambda x:scipy.stats.distributions.norm.cdf( \
                  x,loc=self.meanSeek,scale=self.skDev)

            if self.skVar == 0.0:
                  self.skVar = 0.001 #HACK
            sktheta = self.skVar / self.meanSeek
            skk = self.meanSeek / sktheta
            skdist["gamma"] = lambda x:scipy.stats.distributions.gamma.cdf( \
                  x, skk, scale=sktheta)
            skdist["poisson"] = lambda x:scipy.stats.distributions.poisson.cdf( \
                  int(round(x)), self.meanSeek)
            skdist["uniform"] = lambda x:scipy.stats.distributions.uniform.cdf( \
                  x, loc=self.minSeek, scale=(self.maxSeek-self.minSeek))

            dldist = {}
            dldist["norm"] = lambda x:scipy.stats.distributions.norm.cdf( \
                  x,loc=self.meanDelay,scale=self.dlDev)

            if self.dlVar == 0.0:
                  self.dlVar = 0.001 #HACK
            dltheta = self.dlVar / self.meanDelay
            dlk = self.meanDelay / dltheta
            dldist["gamma"] = lambda x:scipy.stats.distributions.gamma.cdf( \
                  x, dlk, scale=dltheta)
            dldist["poisson"] = lambda x:scipy.stats.distributions.poisson.cdf( \
                  int(round(x)), self.meanDelay)
            dldist["uniform"] = lambda x:scipy.stats.distributions.uniform.cdf( \
                  x, loc=self.minDelay, scale=(self.maxDelay-self.minDelay))

            szchi2 = {}
            skchi2 = {}
            dlchi2 = {}
            for dist in ["norm","gamma","poisson","uniform"]:
                  szchi2[dist] = 0.0
                  skchi2[dist] = 0.0
                  dlchi2[dist] = 0.0

                  for bin in range(self.nbins):
                        # e = expected
                        esize = float(szdist[dist]((bin*self.szBinWidth + self.minSize)+ \
                                      (self.szBinWidth/2))) - float(szdist[dist](( \
                                      bin*self.szBinWidth + self.minSize)-(self.szBinWidth/2)))
                        if esize > 0.0:
                              szchi2[dist] += (self.szBins[bin] - esize)**2 / esize
            
                        eseek = float(skdist[dist]((bin*self.skBinWidth + self.minSeek)+
                                (self.skBinWidth/2))) - float(skdist[dist]((bin*self.skBinWidth \
                                + self.minSeek)-(self.skBinWidth/2)))
            
                        if eseek > 0.0:
                              skchi2[dist] += (self.skBins[bin] - eseek)**2 / eseek

                        edelay = float(dldist[dist]((bin*self.dlBinWidth + self.minDelay)+ \
                                 (self.dlBinWidth/2))) - float(dldist[dist]((bin*self.dlBinWidth \
                                 + self.minDelay)-(self.dlBinWidth/2)))
                        if edelay > 0.0:
                              dlchi2[dist] += (self.dlBins[bin] - edelay)**2 / edelay

                  print "size chi2("+dist+") = "+str(szchi2[dist])
                  print "seek chi2("+dist+") = "+str(skchi2[dist])
                  print "delay chi2("+dist+") = "+str(dlchi2[dist])

def handleCompletion(vals, name, thisTime):
	if name not in vals:
		vals[name] = TSVals()
	val = vals[name]
	overall = vals["__overall"]
      
	for v in [val, overall]:
		v.lastCompletion = thisTime
		if v.depth > 0:
			v.depth -= 1

def updateRun1(vals, rw, sync, size, sector, thisTime, name):
      if name not in vals:
            vals[name] = TSVals()
      val = vals[name]
      overall = vals["__overall"]

      for v in [val, overall]:
            v.totalOps += 1
            v.depth += 1
            if v.depth > v.maxDepth:
            	v.maxDepth = v.depth
            
            v.meanThink += thisTime - v.lastCompletion

            if rw:
                  v.writes += 1
                  if v.maxWrite < size:
                        v.maxWrite = size
                  if v.minWrite > size:
                        v.minWrite = size
                  if v.lastWasRead:
                  	v.dirSwaps += 1
                  	v.lastWasRead = False
                  	v.dirSwapTime += thisTime - v.lastDirSwap
                  	v.lastDirSwap = thisTime
            else:
                  v.reads += 1
                  if v.maxRead < size:
                        v.maxRead = size
                  if v.minRead > size:
                        v.minRead = size
                  if not v.lastWasRead:
                  	v.dirSwaps += 1
                  	v.lastWasRead = True
                  	v.dirSwapTime += thisTime - v.lastDirSwap
                  	v.lastDirSwap = thisTime

            if sync:
                  v.sync += 1
            else:
                  v.async += 1

            if v.maxSize < size:
                  v.maxSize = size
            if v.minSize > size:
                  v.minSize = size
            v.sizeSum += size

            seek = sector - v.lastSector
            if v.maxSeek < seek:
                  v.maxSeek = seek
            if v.minSeek > seek:
                  v.minSeek = seek
            v.lastSector = sector + (size/sectorSize)
            v.seekSum += seek
            if seek == 0:
            	v.sequentialCount += 1

            delay = thisTime - v.lastTime
            if v.maxDelay < delay:
                  v.maxDelay = delay
            if v.minDelay > delay:
                  v.minDelay = delay
            v.lastTime = thisTime
            v.delaySum += delay

            if bigmem:
                  v.ops.append((rw,size,seek,delay))

def updateRun2(name, vals, size, sector, thisTime):
      val = vals[name]
      overall = vals["__overall"]

      for v in [val, overall]:
            if v.totalOps < 1:
                  continue
            v.szVar += (size - v.meanSize)**2
            #print name
            v.szBins[int((size-v.minSize)/v.szBinWidth)] += 1
            
            seek = sector - v.lastSector
            v.lastSector = sector + (size/sectorSize)
            v.skVar += (seek - v.meanSeek)**2
            v.skBins[int((seek-v.minSeek)/v.skBinWidth)] += 1
            
            delay = thisTime - v.lastTime
            
            v.lastTime = thisTime
            v.dlVar += (delay - v.meanDelay)**2
            v.dlBins[int((delay-v.minDelay)/v.dlBinWidth)] += 1

def calcMeans(vals):
      for name in vals:
            v = vals[name]
            
            if v.totalOps != 0:
                  pw = float(v.writes) / v.totalOps
                  pr = float(v.reads) / v.totalOps

                  v.meanSize = float(v.sizeSum) / v.totalOps
                  v.meanSeek = float(v.seekSum*sectorSize) / v.totalOps
                  v.meanDelay = v.delaySum / v.totalOps
                  v.meanThink /= v.totalOps

            if not do_fio:
                  print name+":"
                  print str(v.reads)+" reads, "+str(v.writes)+" writes"
                  print "r/w ratio: "+str(pr)+"/"+str(pw)
                  print "size min/mean/max (B) = "+str(v.minSize)+"/"+str(v.meanSize) \
                        +"/"+str(v.maxSize)
                  print "seek min/mean/max (B) = "+str(v.minSeek)+"/"+str(v.meanSeek) \
                        +"/"+str(v.maxSeek)
                  print "delay min/mean/max (sec) = "+str(v.minDelay)+"/"+str(v.meanDelay) \
                        +"/"+str(v.maxDelay)
                  print ""
            
            if v.dirSwaps != 0:
                  v.dirSwapTime /= v.dirSwaps
      print "\n"

def calcDevs(vals):
      for name in vals:
            v = vals[name]
            print name+":"
            
            v.szVar /= v.totalOps
            v.skVar /= v.totalOps
            v.dlVar /= v.totalOps

            v.szDev = math.sqrt(v.szVar)
            v.skDev = math.sqrt(v.skVar)
            v.dlDev = math.sqrt(v.dlVar)

            print "size stddev = "+str(v.szDev)
            print "seek stddev = "+str(v.skDev)
            print "delay stddev = "+str(v.dlDev)
            print ""
      print "\n"

def calcChi2s(vals):
      for name in vals:
            v = vals[name]
            print name+":"
            v.calcChi2()

def writeJobFile(vals):
      print "; job file based on "+infilename
      print "[global]"
      print "filename=FILENAME"
      print "direct=1"
      print "runtime=60" # 1 minute
      print "time_based"
      print "norandommap"
      print ""
      
      for name in vals:
            if name == "__overall":
                  continue
            v = vals[name]
            if v.totalOps < 1:
                  continue

            print "["+name+"]"
            
            print "prioclass=2" #best-effort
            print "prio=7" #lowest, 0 is highest

            if v.sync >= v.async:
                  print "ioengine=vsync"
            else:
                  print "ioengine=libaio"

            print "iodepth="+str(int(round(v.maxDepth)))
            
            bsrange = ""
            if v.reads >= 1:
                  bsrange += str(v.minRead)+"-"+str(v.maxRead)
                  if v.writes >= 1:
                        bsrange += ","
            if v.writes >= 1:
                  bsrange += str(v.minWrite)+"-"+str(v.maxWrite)
            print "bsrange="+bsrange

            micros = int(round(v.meanThink * 1000000))
            print "thinktime="+str(micros)

            meanSequential = int(round(float(v.totalOps) / (v.totalOps - v.sequentialCount)))
            if v.reads == 0:
                  print "rw=randwrite:"+str(meanSequential)
            elif v.writes == 0:
                  print "rw=randread:"+str(meanSequential)
            else:
                  print "rw=randrw:"+str(meanSequential)

            pctread = (float(v.reads) / v.totalOps) * 100
            print "rwmixread="+str(int(round(pctread)))

            print "rwmixcycle="+str(int(round(v.dirSwapTime)))

            print ""

if __name__ == "__main__":

      parseArgs()

      vals = {}
      vals["__overall"] = TSVals() # HACK: overall values (avoid processes named "__overall"...)

      infile = open(infilename)
      for line in infile:
            words = line.split()
            thisTime = float(words[4])
            name = words[5]
            if words[0] == 'C':
                  handleCompletion(vals, name, thisTime)
                  continue

            rw = words[1][0] == 'W'
            sync = words[1].find('S') != -1
            size = int(words[2])
            sector = int(words[3])

            updateRun1(vals, rw, sync, size, sector, thisTime, name)
      
      if bigmem or do_fio:
            infile.close()

      calcMeans(vals)

      if do_fio:
            writeJobFile(vals)
      else:
            for v in vals.values():
                  v.initBins()

            #print "bin widths "+str(szBinWidth)+","+str(skBinWidth)+","+str(dlBinWidth)

            if bigmem:
                  for v in vals.values():
                        if v.totalOps < 1:
                              continue
                        for (rw,size,seek,delay) in v.ops:
                              v.szVar += (size - v.meanSize)**2
                              v.szBins[int((size-v.minSize)/v.szBinWidth)] += 1

                              v.skVar += (seek - v.meanSeek)**2
                              v.skBins[int((seek-v.minSeek)/v.skBinWidth)] += 1

                              v.dlVar += (delay - v.meanDelay)**2
                              v.dlBins[int((delay-v.minDelay)/v.dlBinWidth)] += 1
                        v.ops = None
            else:
                  for v in vals.values():
                        v.lastTime = 0.0
                        v.lastSector = 0
                  infile.seek(0)
                  for line in infile:
                        words = line.split()
                        size = int(words[2])
                        sector = int(words[3])
                        thisTime = float(words[4])
                        name = words[5]

                        updateRun2(name, vals, size, sector, thisTime)
                  infile.close()
            calcDevs(vals)
            calcChi2s(vals)
