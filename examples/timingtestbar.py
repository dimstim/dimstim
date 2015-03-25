"""Runs a Bar experiment. Used to test display timing with photodiode"""

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

"""Dynamic parameters can potentially vary from one sweep to the next. If a dynamic parameter is assigned multiple values in a sequence, it's treated as a Variable, and has to be added to this Experiment's Variables object"""

# bar orientation relative to orioff (deg)
d.ori = 0 #range(0, 360, 30)
# bar speed (deg/sec)
d.speedDegSec = 0
# bar x position relative to origin (deg), ignored if speedDegSec isn't 0
d.xposDeg = 0
# bar y position relative to origin (deg), ignored if speedDegSec isn't 0
d.yposDeg = 0
# bar width (deg)
d.widthDeg = dc.get('Manbar0', 'widthDeg')
# bar height (deg)
d.heightDeg = dc.get('Manbar0', 'heightDeg')
# bar brightness (0-1)
d.brightness = [0.1, 1]
# background brightness (0-1)
d.bgbrightness = 0
# antialiase the bar?
d.antialiase = True
# sweep duration (sec)
d.sweepSec = 0.025
# post-sweep duration to display blank screen (sec)
d.postsweepSec = 0

vs = Variables()
vs.brightness = Variable(vals=d.brightness, dim=0, shuffle=False) # kwargs: vals, dim, shuffle, random
#vs.bgbrightness = Variable(vals=d.bgbrightness, dim=1, shuffle=True)

runs = Runs(n=20, reshuffle=False)

#bs = BlankSweeps(T=7, sec=2, shuffle=False) # blank sweep every T sweeps for sec seconds

e = Bar(script=__file__, # this script's file name
        static=s, dynamic=d, variables=vs,
        runs=runs, blanksweeps=None) # create a Bar experiment
e.run() # run it
