#!/usr/bin/env python

# Copyright 2007 The University of New South Wales
# Author: Joshua Root <jmr@gelato.unsw.edu.au>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the Australian Public Licence B. See the file
# OZPLB.txt for the licence terms.

import sys
from zipUtils import zipLoad
from IOChain import IOChain

if __name__ == "__main__":
	if len(sys.argv) < 2:
		print "Usage: dumpChain.py chainfile"
		sys.exit(2)
	
	chain = zipLoad(sys.argv[1])
	print str(chain)
