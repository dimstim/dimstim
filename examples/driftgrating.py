"""Runs a drifting Grating experiment"""

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
# x coord of stimulus center relative to screen center (deg)
s.xorigDeg = dc.get('Manbar0', 'xorigDeg')
# y coord of stimulus center relative to screen center (deg)
s.yorigDeg = dc.get('Manbar0', 'yorigDeg')
# grating width (deg)
s.widthDeg = 60 #dc.get('Manbar0', 'widthDeg')
# grating height (deg)
s.heightDeg = 60 #dc.get('Manbar0', 'heightDeg')
# grating orientation offset (deg)
s.orioff = dc.get('Manbar0', 'orioff')
# mask, one of:  None, 'gaussian', or 'circle'
s.mask = None
# screen gamma: None, or single value, or 3-tuple
s.gamma = dc.get('Screen', 'gamma')

"""Dynamic parameters can potentially vary from one sweep to the next. If a dynamic parameter is assigned multiple values in a sequence, it's treated as a Variable, and has to be added to this Experiment's Variables object"""

# grating orientation relative to orioff (deg)
d.ori = range(0, 360, 30)
# grating x position relative to origin (deg)
d.xposDeg = 0
# grating y position relative to origin (deg)
d.yposDeg = 0
# mask diameter (deg), ignored if mask is None
d.diameterDeg = 20
# spatial frequency (cycles/deg)
d.sfreqCycDeg = [0.05, 0.1, 0.2, 0.4, 0.8, 1.6]
# temporal frequency (cycles/sec)
d.tfreqCycSec = [0.5, 1, 2, 5]
# grating phase to begin each sweep with (+/- deg)
d.phase0 = 0
# mean luminance (0-1)
d.ml = 0.5
# contrast (0-1), >> 1 get square grating, < 0 get contrast reversal
d.contrast = 1
# background brightness (0-1)
d.bgbrightness = 0.5
# sweep duration (sec)
d.sweepSec = 6 #[ 2/tf for tf in d.tfreqCycSec ] # 2 cycles per sweep
# post-sweep duration to display blank screen (sec)
d.postsweepSec = 0

vs = Variables()
vs.ori = Variable(vals=d.ori, dim=0, shuffle=True) # kwargs: vals, dim, shuffle, random
vs.sfreqCycDeg = Variable(vals=d.sfreqCycDeg, dim=1, shuffle=True)
vs.tfreqCycSec = Variable(vals=d.tfreqCycSec, dim=2, shuffle=True)

runs = Runs(n=1, reshuffle=False)

bs = BlankSweeps(T=20, sec=2, shuffle=False) # blank sweep every T sweeps for sec seconds

e = Grating(script=__file__, # this script's file name
            static=s, dynamic=d, variables=vs,
            runs=runs, blanksweeps=bs) # create a Grating experiment
e.run() # run it
