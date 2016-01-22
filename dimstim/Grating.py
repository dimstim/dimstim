"""Defines the Grating Experiment"""

from __future__ import division

import struct
import numpy as np
np.seterr(all='raise') # raise all numpy errors (like 1/0), don't just warn
import pygame
import OpenGL.GL as gl

import VisionEgg as ve
import VisionEgg.Core
from VisionEgg.Gratings import SinGrating2D
from VisionEgg.Textures import Mask2D

import Constants as C
from Constants import I
import Core
from Core import sec2intvsync, cycDeg2cycPix, cycSec2cycVsync, deg2pix, toiter
try:
    from Core import DT # only importable if DT board is installed
except ImportError:
    pass
from Experiment import Experiment


class Grating(Experiment):
    """Grating experiment"""
    def __init__(self, *args, **kwargs):
        super(Grating, self).__init__(*args, **kwargs)
        self.width = deg2pix(self.static.widthDeg) # do this here so it doesn't have to be done repeatedly in self.updateparams()
        self.height = deg2pix(self.static.heightDeg)

    def check(self):
        """Check Grating-specific parameters"""
        super(Grating, self).check()
        '''
        if self.dynamic.speedDegSe == None:
            self.dynamic.speedDegSec = 0 # required for self.updateparams()
        if self.dynamic.speedDegSec == 0: # if speed hasn't been set, make sure position has
            assert self.dynamic.xposDeg != None, 'speedDegSec is 0, xposDeg can\'t be set to None'
            assert self.dynamic.yposDeg != None, 'speedDegSec is 0, xposDeg can\'t be set to None'
        else: # if speed has been set, make sure position hasn't
            assert self.dynamic.xposDeg == None, 'speedDegSec is non-zero, xposDeg must be set to None'
            assert self.dynamic.yposDeg == None, 'speedDegSec is non-zero, yposDeg must be set to None'
        '''
    def build(self):
        """Builds the SweepTable and the Header for this Experiment"""
        super(Grating, self).build()

    def createstimuli(self):
        """Creates the VisionEgg stimuli objects for this Experiment subclass"""
        super(Grating, self).createstimuli()

        # Create instances of the Mask2D class, one for each diameter
        if self.static.mask:
            print 'Generating masks',
            self.nmasksamples = 512  # number of samples in mask, must be power of 2, quality/performance tradeoff
            self.masks = {} # init a dictionary
            samplesperpix = self.nmasksamples / deg2pix(min(self.static.widthDeg, self.static.heightDeg))
            for diameterDeg in toiter(self.dynamic.diameterDeg):
                radius = deg2pix(diameterDeg / 2) # in pix
                radiusSamples = samplesperpix * radius # in mask samples
                self.masks[diameterDeg] = Mask2D(function=self.static.mask,
                                                 radius_parameter=radiusSamples, # sigma for gaussian, radius for circle, in units of mask samples
                                                 num_samples=(self.nmasksamples, self.nmasksamples)) # size of mask texture data (# of texels)
                print '.',
            print
        else:
            self.masks = None

        self.nsinsamples = 2048 # number of samples of sine f'n, must be power of 2, quality/performance tradeoff
        self.grating = SinGrating2D(position=(self.xorig, self.yorig), # init to orig,
                                    anchor='center',
                                    size=(deg2pix(self.static.heightDeg), deg2pix(self.static.widthDeg)), # VE defines grating ori as direction of motion of grating, but we want it to be the orientation of the grating elements, so add 90 deg (this also makes grating ori def'n correspond to bar ori def'n). This means that width and height have to be swapped
                                    ignore_time=True, # don't use this class' own time f'n
                                    #mask=self.masks.values()[0], # init to a random mask in maskobjects
                                    num_samples=self.nsinsamples,
                                    max_alpha=1.0, # opaque
                                    on=False) # keep it off until first sweep starts
        self.gp = self.grating.parameters
        '''
        self.fixationspot = ve.Core.FixationSpot(position=(self.xorig, self.yorig),
                                                 anchor='center',
                                                 color=(255, 0, 0, 0),
                                                 size=(1, 1),
                                                 on=True)
        '''
        self.stimuli = (self.background, self.grating) # last entry will be topmost layer in viewport

    def updateparams(self, i):
        """Updates stimulus parameters, given sweep table index i"""
        if i == None: # do a blank sweep
            self.gp.on = False # turn off the grating, leave all other parameters unchanged
            self.postval = C.MAXPOSTABLEINT # posted to DT port to indicate a blank sweep
            self.nvsyncs = sec2intvsync(self.blanksweeps.sec) # this many vsyncs for this sweep
            self.npostvsyncs = 0 # this many post-sweep vsyncs for this sweep, blank sweeps have no post-sweep delay
        else: # not a blank sweep
            self.gp.on = True # ensure grating is on
            self.postval = i # sweep table index will be posted to DT port
            self.nvsyncs = sec2intvsync(self.st.sweepSec[i]) # this many vsyncs for this sweep
            self.npostvsyncs = sec2intvsync(self.st.postsweepSec[i]) # this many post-sweep vsyncs for this sweep

            """Generate phase as a f'n of vsynci for this sweep
            sine grating eq'n used by VE: luminance(x) = 0.5*contrast*sin(2*pi*sfreqCycDeg*x + phaseRad) + ml ...where x is the position in deg along the axis of the sinusoid, and phaseRad = phaseDeg/180*pi. Motion in time is achieved by changing phaseDeg over time. phaseDeg inits to phase0"""
            sfreq = cycDeg2cycPix(self.st.sfreqCycDeg[i]) # convert it just once, reuse it for this sweep
            """phaseoffset is req'd to make phase0 the initial phase at the centre of the grating, instead of at the edge of the grating as VE does. Take the distance from the centre to the edge along the axis of the sinusoid (which in this case is the height), multiply by spatial freq to get numcycles between centre and edge, multiply by 360 deg per cycle to get req'd phaseoffset. THE EXTRA 180 DEG IS NECESSARY FOR SOME REASON, DON'T REALLY UNDERSTAND WHY, BUT IT WORKS!!!"""
            phaseoffset = self.height / 2 * sfreq * 360 + 180
            phasestep = cycSec2cycVsync(self.st.tfreqCycSec[i]) * 360 # delta cycles per vsync, in degrees of sinusoid
            self.phase = -self.st.phase0[i] - phaseoffset - phasestep * np.arange(self.nvsyncs) # array of phases for this sweep. -ve makes the grating move in +ve direction along sinusoidal axis, see sin eq'n above

            # Update grating stimulus
            self.gp.position = self.xorig+deg2pix(self.st.xposDeg[i]), self.yorig+deg2pix(self.st.yposDeg[i])
            self.gp.orientation = self.static.orioff + self.st.ori[i] + 90 # VE defines grating ori as direction of motion of grating, but we want it to be the orientation of the grating elements, so add 90 deg (this also makes grating ori def'n correspond to bar ori def'n). This means that width and height have to be swapped (done at creation of grating)
            if self.masks:
                self.gp.mask = self.masks[self.st.diameterDeg[i]]
            self.gp.spatial_freq = sfreq
            self.gp.pedestal = self.st.ml[i]
            self.gp.contrast = self.st.contrast[i]

            # Update background parameters
            self.bgp.color = self.st.bgbrightness[i], self.st.bgbrightness[i], self.st.bgbrightness[i], 1.0

            # hopefully, calcs didn't take much time, now that we're using np.arange() instead of a for loop
            # Sync up to the next vsync before starting the sweep (calculations took time)
            #self.tsp.on = False # make sure it's off so it doesn't flash for 1 vsync
            #staticScreen(screen=screen, viewport=viewport, quit=quit, nvsyncs=1)
            #self.tsp.on = (i != None) # set it back to its previous state
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
                if self.gp.on: # not a blank sweep
                    self.gp.phase_at_t0 = self.phase[vsynci] # update grating phase
                if I.DTBOARDINSTALLED: DT.postInt16(self.postval) # post value to port
                self.screen.clear()
                self.viewport.draw()
                ve.Core.swap_buffers() # returns immediately
                gl.glFlush() # waits for next vsync pulse from video card
                self.vsynctimer.tick()
                self.nvsyncsdisplayed += 1 # increment

            # Sweep's done, turn off the grating, do the postsweep delay, clear sweep bit low
            self.gp.on = False
            self.staticscreen(nvsyncs=self.npostvsyncs) # clears sweep bit low when done

            if self.quit:
                self.ii = ii + 1 - 1 # dec for accurate count of nsweeps successfully displayed
                break # out of sweep loop

        self.ii = ii + 1 # nsweeps successfully displayed
