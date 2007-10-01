#! /usr/bin/env python

"""
Calculate statistics for a trace
"""

import scipy.stats.distributions
import math
import re
import sys

sectorSize = 512

if __name__ == "__main__":

    totalOps = 0
    
    lastTime = 0.0
    lastSector = 0

    reads = 0
    writes = 0
    
    maxSeek = -sys.maxint-1
    minSeek = sys.maxint
    seekSum = 0

    minSize = sys.maxint
    maxSize = 0
    sizeSum = 0

    minDelay = float(sys.maxint)
    maxDelay = 0.0
    delaySum = 0.0
    
    regex = re.compile(r"Q (..?) (\d+) (\d+) (\d+(\.\d*)?|\.\d+)")

    infile = open(sys.argv[1])
    for line in infile:
        match = regex.match(line)
        if match is not None:
            groups = match.groups()
            
            totalOps += 1

            if groups[0][0] == 'W':
                writes += 1
            else:
                reads += 1
            
            size = int(groups[1])
            if maxSize < size:
                maxSize = size
            if minSize > size:
                minSize = size
            sizeSum += size
			
            seek = int(groups[2]) - lastSector
            if maxSeek < seek:
                maxSeek = seek
            if minSeek > seek:
                minSeek = seek
            lastSector = int(groups[2]) + (size/sectorSize)
            seekSum += seek
			
            delay = float(groups[3]) - lastTime
            if maxDelay < delay:
                maxDelay = delay
            if minDelay > delay:
                minDelay = delay
            lastTime = float(groups[3])
            delaySum += delay

    pw = float(writes) / totalOps
    pr = float(reads) / totalOps
    print str(reads)+" reads, "+str(writes)+" writes"
    print "r/w ratio: "+str(pr)+"/"+str(pw)

    meanSize = float(sizeSum) / totalOps
    print "size min/mean/max (B) = "+str(minSize)+"/"+str(meanSize)+"/"+str(maxSize)

    meanSeek = float(seekSum*sectorSize) / totalOps
    print "seek min/mean/max (B) = "+str(minSeek)+"/"+str(meanSeek)+"/"+str(maxSeek)

    meanDelay = delaySum / totalOps
    print "delay min/mean/max (sec) = "+str(minDelay)+"/"+str(meanDelay)+"/"+str(maxDelay)

    szVar = 0
    skVar = 0
    dlVar = 0

    nbins = 100000 # yeah, that's "lots", right?
    szBins = {}
    szBinWidth = float(maxSize-minSize)/(nbins-1)
    skBins = {}
    skBinWidth = float(maxSeek-minSeek)/(nbins-1)
    dlBins = {}
    dlBinWidth = (maxDelay-minDelay)/(nbins-1)
    for bin in range(nbins):
        szBins[bin] = 0
        skBins[bin] = 0
        dlBins[bin] = 0

    #print "bin widths "+str(szBinWidth)+","+str(skBinWidth)+","+str(dlBinWidth)

    lastTime = 0.0
    lastSector = 0
    infile.seek(0)
    for line in infile:
        match = regex.match(line)
        if match is not None:
            groups = match.groups()
            
            size = int(groups[1])
            szVar += (size - meanSize)**2
            szBins[int((size-minSize)/szBinWidth)] += 1

            seek = int(groups[2]) - lastSector
            lastSector = int(groups[2]) + (size/sectorSize)
            skVar += (seek - meanSeek)**2
            skBins[int((seek-minSeek)/skBinWidth)] += 1

            delay = float(groups[3]) - lastTime
            #print "delay = "+str(delay)
            lastTime = float(groups[3])
            dlVar += (delay - meanDelay)**2
            dlBins[int((delay-minDelay)/dlBinWidth)] += 1

    szVar /= totalOps
    skVar /= totalOps
    dlVar /= totalOps

    szDev = math.sqrt(szVar)
    skDev = math.sqrt(skVar)
    dlDev = math.sqrt(dlVar)

    print "size stddev = "+str(szDev)
    print "seek stddev = "+str(skDev)
    print "delay stddev = "+str(dlDev)

    szdist = {}
    szdist["norm"] = lambda x:scipy.stats.distributions.norm.cdf(x,loc=meanSize,scale=szDev)
    sztheta = szVar / meanSize
    szk = meanSize / sztheta
    szdist["gamma"] = lambda x:scipy.stats.distributions.gamma.cdf(x, szk, scale=sztheta)
    szdist["poisson"] = lambda x:scipy.stats.distributions.poisson.cdf(int(round(x)), meanSize)
    szdist["uniform"] = lambda x:scipy.stats.distributions.uniform.cdf(x, loc=minSize, scale=(maxSize-minSize))

    skdist = {}
    skdist["norm"] = lambda x:scipy.stats.distributions.norm.cdf(x,loc=meanSeek,scale=skDev)
    sktheta = skVar / meanSeek
    skk = meanSeek / sktheta
    skdist["gamma"] = lambda x:scipy.stats.distributions.gamma.cdf(x, skk, scale=sktheta)
    skdist["poisson"] = lambda x:scipy.stats.distributions.poisson.cdf(int(round(x)), meanSeek)
    skdist["uniform"] = lambda x:scipy.stats.distributions.uniform.cdf(x, loc=minSeek, scale=(maxSeek-minSeek))

    dldist = {}
    dldist["norm"] = lambda x:scipy.stats.distributions.norm.cdf(x,loc=meanDelay,scale=dlDev)
    dltheta = dlVar / meanDelay
    dlk = meanDelay / dltheta
    dldist["gamma"] = lambda x:scipy.stats.distributions.gamma.cdf(x, dlk, scale=dltheta)
    dldist["poisson"] = lambda x:scipy.stats.distributions.poisson.cdf(int(round(x)), meanDelay)
    dldist["uniform"] = lambda x:scipy.stats.distributions.uniform.cdf(x, loc=minDelay, scale=(maxDelay-minDelay))

    szchi2 = {}
    skchi2 = {}
    dlchi2 = {}
    for dist in ["norm","gamma","poisson","uniform"]:
        szchi2[dist] = 0.0
        skchi2[dist] = 0.0
        dlchi2[dist] = 0.0

        for bin in range(nbins):
            # e = expected
            esize = float(szdist[dist]((bin*szBinWidth + minSize)+(szBinWidth/2))) - \
                    float(szdist[dist]((bin*szBinWidth + minSize)-(szBinWidth/2)))
            if esize > 0.0:
                szchi2[dist] += (szBins[bin] - esize)**2 / esize
            
            eseek = float(skdist[dist]((bin*skBinWidth + minSeek)+(skBinWidth/2))) - \
                    float(skdist[dist]((bin*skBinWidth + minSeek)-(skBinWidth/2)))
            
            if eseek > 0.0:
                skchi2[dist] += (skBins[bin] - eseek)**2 / eseek

            edelay = float(dldist[dist]((bin*dlBinWidth + minDelay)+(dlBinWidth/2))) - \
                     float(dldist[dist]((bin*dlBinWidth + minDelay)-(dlBinWidth/2)))
            if edelay > 0.0:
                dlchi2[dist] += (dlBins[bin] - edelay)**2 / edelay

        print "size chi2("+dist+") = "+str(szchi2[dist])
        print "seek chi2("+dist+") = "+str(skchi2[dist])
        print "delay chi2("+dist+") = "+str(skchi2[dist])
