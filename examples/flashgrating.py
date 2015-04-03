"""Runs a flashed Grating experiment"""

from dimstim.Constants import dc # dimstim config
from dimstim.Core import StaticParams, DynamicParams, Variable, Variables, Runs, BlankSweeps
from dimstim.Grating import Grating

s = StaticParams()
d = DynamicParams()

"""Static parameters always remain constant during the entire experiment"""

# pre-experiment duration to display blank screen (sec)
s.preexpSec = 1
# post-experiment duration to display blank screen (sec)
s.postexpSec = 1
# bar orientation offset (deg)
s.orioff = 0 #dc.get('Manbar0', 'orioff')
# grating width (deg)
s.widthDeg = 60 #dc.get('Manbar0', 'widthDeg')
# grating height (deg)
s.heightDeg = 60 #dc.get('Manbar0', 'heightDeg')
# mask, one of:  None, 'gaussian', or 'circle'
s.mask = None
# screen gamma: None, or single value, or 3-tuple
s.gamma = dc.get('Screen', 'gamma')

"""Dynamic parameters can potentially vary from one sweep to the next. If a dynamic parameter
is assigned multiple values in a sequence, it's treated as a Variable, and has to be added to
this Experiment's Variables object"""

# grating orientation relative to orioff (deg)
d.ori = range(0, 180, 10)
# grating x position relative to origin (deg)
d.xposDeg = 0
# grating y position relative to origin (deg)
d.yposDeg = 0
# mask diameter (deg), ignored if mask is None
d.diameterDeg = 10
# spatial frequency (cycles/deg)
d.sfreqCycDeg = [0.2, 0.4, 0.6, 1, 2, 4]
# temporal frequency (cycles/sec)
d.tfreqCycSec = 0
# grating phase to begin each sweep with (+/- deg)
d.phase0 = range(0, 360, 90)
# mean luminance (0-1)
d.ml = 0.5
# contrast (0-1), >> 1 get square grating, < 0 get contrast reversal
d.contrast = [0.25, 0.5, 0.75, 1]
# background brightness (0-1)
d.bgbrightness = 0.5
# sweep duration (sec)
d.sweepSec = 0.005
# post-sweep duration to display blank screen (sec)
d.postsweepSec = 0

vs = Variables()
vs.ori = Variable(vals=d.ori, dim=0, shuffle=True) # kwargs: vals, dim, shuffle, random
vs.sfreqCycDeg = Variable(vals=d.sfreqCycDeg, dim=1, shuffle=True)
vs.phase0 = Variable(vals=d.phase0, dim=2, shuffle=True)
vs.contrast = Variable(vals=d.contrast, dim=3, shuffle=True)

runs = Runs(n=1, reshuffle=False)

bs = BlankSweeps(T=20000, sec=2, shuffle=False) # blank sweep every T sweeps for sec seconds

e = Grating(script=__file__, # this script's file name
            static=s, dynamic=d, variables=vs,
            runs=runs, blanksweeps=bs) # create a Grating experiment
e.run() # run it
