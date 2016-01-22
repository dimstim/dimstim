"""Runs a Bar experiment"""

from dimstim.Constants import dc # dimstim config
from dimstim.Core import StaticParams, DynamicParams, Variable, Variables, Runs, BlankSweeps
from dimstim.Bar import Bar

s = StaticParams()
d = DynamicParams()

"""Static parameters always remain constant during the entire experiment"""

# pre-experiment duration to display blank screen (sec)
s.preexpSec = 1
# post-experiment duration to display blank screen (sec)
s.postexpSec = 1
# bar orientation offset (deg)
s.orioff = dc.get('Manbar0', 'orioff')
# screen gamma: None, or single value, or 3-tuple
s.gamma = dc.get('Screen', 'gamma')

"""Dynamic parameters can potentially vary from one sweep to the next. If a dynamic parameter
is assigned multiple values in a sequence, it's treated as a Variable, and has to be added to
this Experiment's Variables object"""

# bar orientation relative to orioff (deg)
d.ori = range(0, 360, 30)
# bar speed (deg/sec)
d.speedDegSec = 5
# bar x position relative to origin (deg), ignored if speedDegSec is nonzero
d.xposDeg = None
# bar y position relative to origin (deg), ignored if speedDegSec is nonzero
d.yposDeg = None
# bar width (deg)
d.widthDeg = dc.get('Manbar0', 'widthDeg')
# bar height (deg)
d.heightDeg = dc.get('Manbar0', 'heightDeg')
# bar brightness (0-1)
d.brightness = [0, 1]
# background brightness (0-1)
d.bgbrightness = 0.5
# antialiase the bar?
d.antialiase = True
# sweep duration (sec)
d.sweepSec = 2.5
# post-sweep duration to display blank screen (sec)
d.postsweepSec = 0.5

vs = Variables()
vs.ori = Variable(vals=d.ori, dim=0, shuffle=True) # kwargs: vals, dim, shuffle, random
#vs.xposDeg = Variable(vals=d.xposDeg, dim=3, shuffle=False)
#vs.speedDegSec = Variable(vals=d.speedDegSec, dim=1, shuffle=True)
vs.brightness = Variable(vals=d.brightness, dim=1, shuffle=True)
#vs.bgbrightness = Variable(vals=d.bgbrightness, dim=1, shuffle=True)

runs = Runs(n=10, reshuffle=False)

#bs = BlankSweeps(T=7, sec=2, shuffle=False) # blank sweep every T sweeps for sec seconds

e = Bar(script=__file__, # this script's file name
        static=s, dynamic=d, variables=vs,
        runs=runs, blanksweeps=None) # create a Bar experiment
e.run() # run it
