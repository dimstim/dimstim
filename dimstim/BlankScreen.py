"""Defines the BlankScreen Experiment"""

from __future__ import division

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
try:
    from Core import DT # only importable if DT board is installed
except ImportError:
    pass
from Experiment import Experiment, info, printf2log




class BlankScreen(Experiment):
    """BlankScreen experiment"""
    def check(self):
        """Check BlankScreen-specific parameters"""
        super(BlankScreen, self).check()

    def build(self):
        """Builds the SweepTable and the Header for this Experiment"""
        self.static.preexpSec = 0
        self.static.postexpSec = 0
        self.postval = 0
        self.sweeptable = Core.SweepTable(experiment=self)
        self.sec = 0 # experiment duration

        # Build the text header
        self.header = Core.Header(experiment=self)
        info('TextHeader.data:', toscreen=False)
        printf2log(str(self.header.text)) # print text header data to log

    def createstimuli(self):
        """Creates the VisionEgg stimuli objects for this Experiment subclass"""
        super(BlankScreen, self).createstimuli()

        self.stimuli = (self.background,) # last entry will be topmost layer in viewport

    def initbackgroundcolor(self):
        """Sets the initial background colour"""
        bgb = self.static.bgbrightness
        self.bgp.color = bgb, bgb, bgb, 1.0 # set bg colour, do this now so it's correct for the pre-exp delay

    def updateparams(self, i):
        """Updates stimulus parameters, given sweep table index i"""
        pass

    def main(self):
        """Run the main stimulus loop for this Experiment subclass

        make screen.get_framebuffer_as_array for all Experiment classes more easily
        available from outside of dimstim (for analysis in neuropy) so you can
        grab the frame buffer data at any timepoint (and use for, say, revcorr)

        """
        while True: # sweep loop

            # Set sweep bit high, do the sweep
            while True: # vsync loop
                for event in pygame.event.get(): # for all events in the event queue
                    if event.type == pygame.locals.KEYDOWN:
                        if event.key == pygame.locals.K_ESCAPE:
                            self.quit = True
                if self.quit:
                    break # out of vsync loop
                if I.DTBOARDINSTALLED: DT.postInt16NoDelay(self.postval) # post value to port, no delay
                self.screen.clear()
                self.viewport.draw()
                ve.Core.swap_buffers() # returns immediately
                gl.glFlush() # waits for next vsync pulse from video card
                self.vsynctimer.tick()
                self.nvsyncsdisplayed += 1 # increment

            if self.quit:
                break # out of sweep loop

        self.ii = 1 # nsweeps successfully displayed
