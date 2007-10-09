from distutils.core import setup, Extension

directrwmodule = Extension('directrw',
                    sources = ['directrwmodule.c'])
btrecordmodule = Extension('btrecord',
                    sources = ['btrecordmodule.c', 'btrecord.c'])

setup (name = 'DirectRW',
       version = '0.1',
       description = 'Call read/write with correctly aligned buffers for O_DIRECT',
       author = 'Joshua Root',
       author_email = 'jmr@gelato.unsw.edu.au',
       ext_modules = [directrwmodule])

setup (name = 'btrecord',
       version = '0.1',
       description = 'Output I/O op data in btrecord format',
       author = 'Joshua Root',
       author_email = 'jmr@gelato.unsw.edu.au',
       ext_modules = [btrecordmodule])

# still to come: posix aio
