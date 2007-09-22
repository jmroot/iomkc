"""
Markov chain of I/O operations.

State tuple is (r/w,size,seek,delay)

Copyright 2007 The University of New South Wales
Author: Joshua Root <jmr@gelato.unsw.edu.au>
"""

from random import random

class IOChain:
	"""
	Markov chain of I/O ops.
	"""
	def __init__(self, initialState, stateKey, transitionCounts):
		self.stateKey = stateKey # bucket boundaries
		self.state = initialState
		self.matrix = self._buildMatrix(transitionCounts)

	def step(self):
                X = random()
                probs = self.matrix[self.state]
                for (p,s) in probs:
                        if X < p:
                                self.state = s
                                return s
		print "oops, random variable matched no probabilities"
		return None

	def genOp(self, st):
		rnd = random()
		sz = int(rnd*(self.stateKey[0][st[1]] - self.stateKey[0][st[1]-1]) + self.stateKey[0][st[1]-1])
		rnd = random()
		sk = int(rnd*(self.stateKey[1][st[2]] - self.stateKey[1][st[2]-1]) + self.stateKey[1][st[2]-1])
		rnd = random()
		dl = rnd*(self.stateKey[2][st[3]] - self.stateKey[2][st[3]-1]) + self.stateKey[2][st[3]-1]
		return (st[0],sz,sk,dl)
	
	def _buildMatrix(self, transitionCounts):
		matrix = {}
		for s1 in transitionCounts.keys():
			s1counts = transitionCounts[s1]
			total = float(sum(s1counts.values()))
			probs = []
			for s2 in s1counts.keys():
				probs.append([s1counts[s2]/total, s2])
			probs.sort(key=lambda p:p[0], reverse=True)
			for i in range(1,len(probs)):
				probs[i][0] += probs[i-1][0]
			probs[-1][0] = 1.0 # just to make sure :-)
			matrix[s1] = probs
		return matrix

	def __str__(self):
		return str(self.stateKey)+"\n"+str(self.state)+"\n"+str(self.matrix)
