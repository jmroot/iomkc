#!/bin/sh

# Turn blktrace output into buildChain.py (Markov chain builder) input
# usage: ./prep.sh dev outfile
# e.g. ./prep.sh sdc trace.txt

blkparse -q -f "%a %d %N %S %T.%t\n" $1 | grep "^Q" > $2

# in R/W field: B = barrier, S = sync, A= readahead, M = metadata
# (can ignore all but barrier, I think)
