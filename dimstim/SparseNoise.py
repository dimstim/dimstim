"""Defines the SparseNoise Experiment"""

from __future__ import division

import math
from math import pi
import numpy as np
np.seterr(all='raise') # raise all numpy errors (like 1/0), don't just warn
import pygame
import OpenGL.GL as gl

import VisionEgg as ve
import VisionEgg.Core
from VisionEgg.MoreStimuli import Target2D

import Constants as C
from Constants import I, SWEEP
import Core
from Core import sec2intvsync, degSec2pixVsync, deg2pix
try:
    from Core import DT # only importable if DT board is installed
except ImportError:
    pass
from Experiment import Experiment


class SparseNoise(Experiment):
    """Sparse noise experiment"""
    def check(self):
        """Check SparseNoise-specific parameters"""
        super(SparseNoise, self).check()

        # need to ensure all oris are +ve and < 360. Enforce this during self.check()? or, do mod 360 on all oris, like in manbar. Shouldn't this be done for all stimuli with an ori parameter????????????

        for xi in self.dynamic.xi:
            assert xi in range(self.static.ncellswide)
        for yi in self.dynamic.yi:
            assert xi in range(self.static.ncellshigh)

    def build(self):
        """Builds the SweepTable and the Header for this Experiment"""
        super(SparseNoise, self).build()
        self.header.NVS.data[C.STT_STS] = 11 # enter NVS stimulus code for sparse noise (actually, 'reverse correlation')

        self.barWidth = deg2pix(self.static.widthDeg / self.static.ncellswide) # in pix
        self.barHeight = deg2pix(self.static.heightDeg / self.static.ncellshigh) # in pix

        self.xi0 = (self.static.ncellswide - 1) / 2 # center of grid, in units of 0-based cell index
        self.yi0 = (self.static.ncellshigh - 1) / 2

    def createstimuli(self):
        """Creates the VisionEgg stimuli objects for this Experiment subclass"""
        super(SparseNoise, self).createstimuli()
        self.target = Target2D(anchor='center', on=False) # keep it off until first sweep starts

        self.stimuli = (self.background, self.target) # last entry will be topmost layer in viewport

        self.tp = self.target.parameters # synonym
        self.tp.size = self.barWidth, self.barHeight # static, only needs to be done once

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

            # Update target position
            ori = self.static.orioff + self.st.ori[i]
            theta = ori / 180 * pi

            dxi = self.st.xi[i] - self.xi0 # destination index - origin index
            dyi = self.st.yi[i] - self.yi0
            sintheta = math.sin(theta)
            costheta = math.cos(theta)
            dx = dxi*self.barWidth*costheta - dyi*self.barHeight*sintheta # see SparseNoise.png for the trigonometry
            dy = dxi*self.barWidth*sintheta + dyi*self.barHeight*costheta

            x = self.xorig + deg2pix(self.st.xposDeg[i]) + dx
            y = self.yorig + deg2pix(self.st.yposDeg[i]) + dy
            self.tp.position = (x, y)

            # Update non-positional target parameters
            self.tp.orientation = ori
            self.tp.color = self.st.brightness[i], self.st.brightness[i], self.st.brightness[i], 1.0
            self.tp.anti_aliasing = self.st.antialiase[i]

            # Update background parameters
            self.bgp.color = self.st.bgbrightness[i], self.st.bgbrightness[i], self.st.bgbrightness[i], 1.0

    def main(self):
        """Run the main stimulus loop for this Experiment subclass

        make screen.get_framebuffer_as_array for all Experiment classes more easily
        available from outside of dimstim (for analysis in neuropy) so you can
        grab the frame buffer data at any timepoint (and use for, say, revcorr)

        """
        for ii, i in enumerate(self.sweeptable.i):

            self.updateparams(i)

            # Set sweep bit high, do the sweep
            if I.DTBOARDINSTALLED: DT.setBitsNoDelay(SWEEP) # set sweep bit high, no delay
            for vsynci in xrange(self.nvsyncs): # nvsyncs depends on if this is a blank sweep or not
                for event in pygame.event.get(): # for all events in the event queue
                    if event.type == pygame.locals.KEYDOWN:
                        if event.key == pygame.locals.K_ESCAPE:
                            self.quit = True
                        if event.key == pygame.locals.K_PAUSE:
                            self.pause = not self.pause # toggle pause
                            self.paused = True # remember that a pause happened
                if self.quit:
                    break # out of vsync loop
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
