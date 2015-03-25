"""Runs a Manual Bar experiment, implemented in pygame"""

from dimstim.Constants import dc # dimstim config
from dimstim.ManBar_pygame import Params, ManBar_pygame

p = Params()

# Manual Bar experiment parameters, all must be scalars

# bar brightness (0-1)
p.brightness = 1
# background brightness (0-1)
p.bgbrightness = 0
# antialiase the bar?
p.antialiase = True
# screen gamma: None, or single value, or 3-tuple
p.gamma = dc.get('Screen', 'gamma')
# flash the bar?
p.flash = False
# duration of each flash cycle (on and off) (sec)
p.flashSec = 0.005
# rate of change of size during buttonpress (deg/sec)
p.sizerateDegSec = 4
# rate of change of orientation during mouse button press (deg/sec)
p.orirateDegSec = 18
# brightness step amount on +/- (0-1)
p.brightnessstep = 0.005
# orientation step size to snap to when scrolling mouse wheel (deg)
p.snapDeg = 18
# print vsync histogram?
p.printhistogram = False

e = ManBar_pygame(script=__file__, # this script's file name
                  params=p) # create a ManBar experiment
e.run() # run it
