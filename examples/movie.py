"""Runs a Movie experiment"""

import os
from dimstim.Constants import dc # dimstim config
from dimstim.Core import StaticParams, DynamicParams, Variable, Variables, Runs, BlankSweeps
from dimstim.Movie import Movie

s = StaticParams()
d = DynamicParams()

"""Static parameters always remain constant during the entire experiment"""

# movie file name with path
s.fname = os.path.join(dc.get('Path', 'movies'), 'mseq', 'MSEQ32')
# pre-experiment duration to display blank screen (sec)
s.preexpSec = 0
# post-experiment duration to display blank screen (sec)
s.postexpSec = 1
# movie orientation offset (deg)
s.orioff = 0 #dc.get('Manbar0', 'orioff')
# movie width (deg)
s.widthDeg = 15 #dc.get('Manbar0', 'widthDeg')
# movie height (deg)
s.heightDeg = 15 #dc.get('Manbar0', 'heightDeg')
# mask, one of:  None, 'gaussian', or 'circle'
s.mask = None
# mask diameter (deg), ignored if mask is None
s.diameterDeg = 10
# screen gamma: None, or single value, or 3-tuple
s.gamma = None

"""Dynamic parameters can potentially vary from one sweep to the next. If a dynamic parameter
is assigned multiple values in a sequence, it's treated as a Variable, and has to be added to
this Experiment's Variables object"""

# movie frame indices
d.framei = range(2**16 - 1) # mseq has 65535 frames, ie 0 to 65534
# movie orientation relative to orioff (deg)
d.ori = 0
# movie x position relative to origin (deg)
d.xposDeg = 0
# movie y position relative to origin (deg)
d.yposDeg = 0
# invert movie polarity?
d.invert = False
# background brightness (0-1)
d.bgbrightness = 0.5
# sweep duration (sec)
d.sweepSec = 0.010
# post-sweep duration to display blank screen (sec)
d.postsweepSec = 0

vs = Variables()
vs.framei = Variable(vals=d.framei, dim=0, shuffle=False) # kwargs: vals, dim, shuffle, random

runs = Runs(n=1, reshuffle=False)

#bs = BlankSweeps(T=7, sec=2, shuffle=False) # blank sweep every T sweeps for sec seconds

e = Movie(script=__file__,
          static=s, dynamic=d, variables=vs,
          runs=runs, blanksweeps=None) # create a Movie experiment
e.run() # run it
