"""
Helpers for loading and saving gzipped pickled objects.
"""

import cPickle
from gzip import GzipFile

def zipLoad(fileName):
      theFile = GzipFile(fileName)
      obj = cPickle.load(theFile)
      theFile.close()
      return obj

def zipSave(outfile, obj):
      theFile = GzipFile(outfile, 'wb')
      cPickle.dump(obj, theFile, 2) #use pickle protocol v2 (latest as of Python 2.5)
      theFile.close()
