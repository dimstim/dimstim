"""dimstim install script, builds the C extension for interfacing with Data Translations Open
Layers

to create source distribution and force tar.gz file:
>>> python setup.py sdist --formats=gztar
to create binary distribution:
>>> python setup.py bdist_wininst
"""

from distutils.core import setup, Extension
import os

# absolute path to the Data Translations SDK directory
DTPATH = os.environ['DA_SDK'] # this environ var likely exists after install of DT SDK
#DTPATH = os.path.join(os.sep, 'bin', 'DT', 'Win32', 'SDK') # if not, modify and use this path

DTmodule = Extension('dimstim.DT',
                     #define_macros=[('MAJOR_VERSION', '1'),
                     #               ('MINOR_VERSION', '0')],
                     include_dirs=[os.path.join(DTPATH, 'Include')],
                     library_dirs=[os.path.join(DTPATH, 'Lib')],
                     libraries=['oldaapi32'],
                     sources=['dimstim/DT.c'])

setup(name='dimstim',
      version='0.19',
      license='BSD',
      description='Multidimensional stimulus system for vision science',
      author='Martin Spacek, Keith Godfrey',
      author_email='git mspacek mm st',
      url='http://dimstim.github.io',
      #long_description='',
      packages=['dimstim',
                'dimstim.examples'],
      package_data={'dimstim': ['dimstim.cfg']},
      data_files=[('', ['LICENSE', 'TODO', 'README.md'])],
      ext_modules=[DTmodule]
      )
