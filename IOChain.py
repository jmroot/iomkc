# Copyright 2007 The University of New South Wales
# Author: Joshua Root <jmr@gelato.unsw.edu.au>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the Australian Public Licence B. See the file
# OZPLB.txt for the licence terms.

"""
Markov chain of I/O operations.

State tuple is (r/w,size,seek,delay)
"""

import random

szkey = 0 #indices into stateKey for the attributes
skkey = 1
dlkey = 2

strw = 0 #attributes' indices into the state tuple
stsz = 1
stsk = 2
stdl = 3

class IOChain(object):
	"""
	Markov chain of I/O ops.
	"""
	def __init__(self, initialState, stateKey, transitionCounts):
		self.stateKey = stateKey # bucket boundaries
		self.state = initialState
		self.matrix = self._buildMatrix(transitionCounts)

	def randSeed(self, seed):
		random.seed(seed)

	def step(self):
            X = random.random()
            probs = self.matrix[self.state]
            #print probs
            for (p,s) in probs:
                  if X < p:
                        self.state = s
                        return
            # XXX the last state in the source trace could quite
            # possibly not be a key in matrix
            print "oops, random variable matched no probabilities"

	def genOp(self, st):
		rnd = random.random()
		sz = int(rnd*(self.stateKey[szkey][st[stsz]+1] - \
			self.stateKey[szkey][st[stsz]]) + \
			self.stateKey[szkey][st[stsz]])
		rnd = random.random()
		sk = int(rnd*(self.stateKey[skkey][st[stsk]+1] - \
			self.stateKey[skkey][st[stsk]]) + \
			self.stateKey[skkey][st[stsk]])
		rnd = random.random()
		dl = rnd*(self.stateKey[dlkey][st[stdl]+1] - \
			self.stateKey[dlkey][st[stdl]]) + \
			self.stateKey[dlkey][st[stdl]]
		return (st[strw],sz,sk,dl)
	
	def _buildMatrix(self, transitionCounts):
		matrix = {}
		sortkey = lambda p:p[0]
		for s1 in transitionCounts.keys():
			s1counts = transitionCounts[s1]
			total = float(sum(s1counts.values()))
			probs = []
			for s2 in s1counts.keys():
				probs.append([s1counts[s2]/total, s2])
			probs.sort(key=sortkey, reverse=True)
			for i in range(1,len(probs)):
				probs[i][0] += probs[i-1][0]
			probs[-1][0] = 1.0 # just to make sure :-)
			matrix[s1] = probs
		return matrix

	def __str__(self):
		return str(self.stateKey)+"\n"+str(self.state)+"\n"+str(self.matrix)
