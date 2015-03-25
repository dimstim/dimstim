"""Runs a BlankScreen experiment for an indefinite period of time, for collecting spontaneous data"""

from dimstim.Constants import dc # dimstim config
from dimstim.Core import StaticParams, DynamicParams, Variables
from dimstim.BlankScreen import BlankScreen

s = StaticParams()
d = DynamicParams()

"""Static parameters always remain constant during the entire experiment"""

# background brightness (0-1)
s.bgbrightness = 0.5
# screen gamma: None, or single value, or 3-tuple
s.gamma = dc.get('Screen', 'gamma')

vs = Variables()

e = BlankScreen(script=__file__, # this script's file name
                static=s, dynamic=d, variables=vs,
                runs=None, blanksweeps=None) # create a BlankScreen experiment
e.run() # run it
