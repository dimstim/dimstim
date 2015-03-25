"""Runs a Manual Grating experiment"""

from dimstim.Core import StaticParams
from dimstim.Constants import dc # dimstim config
from dimstim.ManGrating import ManGrating

p = StaticParams()

# Manual Grating experiment parameters, all must be scalars

# grating width (deg)
p.widthDeg = 60
# grating height (deg)
p.heightDeg = 60
# initial grating phase
p.phase0 = 0
# grating mean luminance (0-1)
p.ml = 0.5
# grating contrast (0-1)
p.contrast = 1
# background brightness (0-1)
p.bgbrightness = 0
# antialiase the bar?
p.antialiase = True
# screen gamma: None, or single value, or 3-tuple
p.gamma = dc.get('Screen', 'gamma')
# flash the grating?
p.flash = False
# duration of each flash cycle (on and off) (sec)
p.flashSec = 1
# rate of change of orientation during mouse button press (deg/sec)
p.orirateDegSec = 18
# factor to change temporal freq by on up/down
p.tfreqmultiplier = 1.01
# factor to change spatial freq by on left/right
p.sfreqmultiplier = 1.01
# factor to change contrast by on +/-
p.contrastmultiplier = 1.005
# orientation step size to snap to when scrolling mouse wheel (deg)
p.snapDeg = 18
# print vsync histogram?
p.printhistogram = False
# display on how many screens?
p.nscreens = 2

e = ManGrating(script=__file__, # this script's file name
               params=p) # create a ManGrating experiment
e.run() # run it
