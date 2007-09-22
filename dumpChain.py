#!/usr/bin/env python

import sys
from zipUtils import zipLoad, zipSave
from IOChain import IOChain

if __name__ == "__main__":
	if len(sys.argv) < 2:
		print "Usage: dumpChain.py chainfile"
		sys.exit(2)
	
	chain = zipLoad(sys.argv[1])
	print str(chain)
