"""Defines the Bar Experiment"""

from __future__ import division

import math
import numpy as np
np.seterr(all='raise') # raise all numpy errors (like 1/0), don't just warn
import pygame
import OpenGL.GL as gl

import VisionEgg as ve
import VisionEgg.Core
from VisionEgg.MoreStimuli import Target2D

import Constants as C
from Constants import I
import Core
from Core import sec2intvsync, degSec2pixVsync, deg2pix
try:
    from Core import DT # only importable if DT board is installed
except ImportError:
    pass
from Experiment import Experiment


class Bar(Experiment):
    """Drifting/stationary bar experiment"""
    def check(self):
        """Check Bar-specific parameters"""
        super(Bar, self).check()
        if self.dynamic.speedDegSec == None:
            self.dynamic.speedDegSec = 0 # required for self.updateparams()
        if self.dynamic.speedDegSec == 0: # if speed hasn't been set, make sure position has
            assert self.dynamic.xposDeg != None, 'speedDegSec is 0, xposDeg can\'t be set to None'
            assert self.dynamic.yposDeg != None, 'speedDegSec is 0, xposDeg can\'t be set to None'
        else: # if speed has been set, make sure position hasn't
            assert self.dynamic.xposDeg == None, 'speedDegSec is non-zero, xposDeg must be set to None'
            assert self.dynamic.yposDeg == None, 'speedDegSec is non-zero, yposDeg must be set to None'

    def build(self):
        """Builds the SweepTable and the Header for this Experiment"""
        super(Bar, self).build()

    def createstimuli(self):
        """Creates the VisionEgg stimuli objects for this Experiment subclass"""
        super(Bar, self).createstimuli()
        self.target = Target2D(anchor='center', on=False) # keep it off until first sweep starts

        self.stimuli = (self.background, self.target) # last entry will be topmost layer in viewport

        self.tp = self.target.parameters # synonym

    def updateparams(self, i):
        """Updates stimulus parameters, given sweep table index i"""
        if i == None: # do a blank sweep
            self.tp.on = False # turn off the target, leave all other parameters unchanged
            self.postval = C.MAXPOSTABLEINT # posted to DT port to indicate a blank sweep
            self.nvsyncs = sec2intvsync(self.blanksweeps.sec) # this many vsyncs for this sweep
            self.npostvsyncs = 0 # this many post-sweep vsyncs for this sweep, blank sweeps have no post-sweep delay
        else: # not a blank sweep
            self.tp.on = True # ensure stimulus is on
            self.postval = i # sweep table index will be posted to DT port
            self.nvsyncs = sec2intvsync(self.st.sweepSec[i]) # this many vsyncs for this sweep
            self.npostvsyncs = sec2intvsync(self.st.postsweepSec[i]) # this many post-sweep vsyncs for this sweep

            # Generate position as a f'n of vsynci for this sweep, even if speedDegSec is 0
            distance = degSec2pixVsync(self.st.speedDegSec[i]) * self.nvsyncs # total distance to travel on this sweep
            direction = self.static.orioff + self.st.ori[i] + 90 # direction to travel on this sweep, always |_ to current ori
            xdistance = distance * math.cos(direction / 180 * math.pi)
            ydistance = distance * math.sin(direction / 180 * math.pi)
            xstep = xdistance / self.nvsyncs # pix to travel per vsync
            ystep = ydistance / self.nvsyncs
            x0 = self.xorig - xdistance / 2
            y0 = self.yorig - ydistance / 2
            self.x = x0 + xstep * np.arange(self.nvsyncs) + deg2pix(self.st.xposDeg[i]) # deg2pix returns 0 if deg is None
            self.y = y0 + ystep * np.arange(self.nvsyncs) + deg2pix(self.st.yposDeg[i])

            # Update non-positional target parameters
            self.tp.orientation = self.static.orioff + self.st.ori[i]
            self.tp.size = deg2pix(self.st.widthDeg[i]), deg2pix(self.st.heightDeg[i])
            self.tp.color = self.st.brightness[i], self.st.brightness[i], self.st.brightness[i], 1.0
            self.tp.anti_aliasing = self.st.antialiase[i]

            # Update background parameters
            self.bgp.color = self.st.bgbrightness[i], self.st.bgbrightness[i], self.st.bgbrightness[i], 1.0

            # hopefully, calcs didn't take much time, now that we're using np.arange() instead of a for loop
            # Sync up to the next vsync before starting the sweep (calculations took time)
            #self.tp.on = False # make sure it's off so it doesn't flash for 1 vsync
            #staticScreen(screen=screen, viewport=viewport, quit=quit, nvsyncs=1)
            #self.tp.on = (i != None) # set it back to its previous state
        #vsynctimer.tock() # update latest vsync time without counting it as a tick

    def main(self):
        """Run the main stimulus loop for this Experiment subclass

        make screen.get_framebuffer_as_array for all Experiment classes more easily
        available from outside of dimstim (for analysis in neuropy) so you can
        grab the frame buffer data at any timepoint (and use for, say, revcorr)

        """
        for ii, i in enumerate(self.sweeptable.i):

            self.updateparams(i)

            # Set sweep bit high, do the sweep
            for vsynci in xrange(self.nvsyncs): # nvsyncs depends on if this is a blank sweep or not
                for event in pygame.event.get(): # for all events in the event queue
                    if event.type == pygame.locals.KEYDOWN:
                        if event.key == pygame.locals.K_ESCAPE:
                            self.quit = True
                if self.quit:
                    break # out of vsync loop
                if self.tp.on: # not a blank sweep
                    self.tp.position = self.x[vsynci], self.y[vsynci] # update target position
                if I.DTBOARDINSTALLED: DT.postInt16NoDelay(self.postval) # post value to port, no delay
                self.screen.clear()
                self.viewport.draw()
                ve.Core.swap_buffers() # returns immediately
                gl.glFlush() # waits for next vsync pulse from video card
                self.vsynctimer.tick()
                self.nvsyncsdisplayed += 1 # increment

            # Sweep's done, turn off the target, do the postsweep delay, clear sweep bit low
            self.tp.on = False
            self.staticscreen(nvsyncs=self.npostvsyncs) # clears sweep bit low when done

            if self.quit:
                self.ii = ii + 1 - 1 # dec for accurate count of nsweeps successfully displayed
                break # out of sweep loop

        self.ii = ii + 1 # nsweeps successfully displayed
