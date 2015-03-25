"""Defines the Manual Grating Experiment"""

from __future__ import division

import numpy as np
np.seterr(all='raise') # raise all numpy errors (like 1/0), don't just warn
import pyglet.window
import pyglet.window.key as key
import pyglet.window.mouse as mouse
import pygame
#import pygame.locals as pl
import OpenGL.GL as gl

import VisionEgg as ve
import VisionEgg.Core
from VisionEgg.MoreStimuli import Target2D
from VisionEgg.Gratings import SinGrating2D
from VisionEgg.Text import Text

import Constants as C
from Constants import dc, I
import Core
from Core import deg2pix, pix2deg, cycDeg2cycPix, cycSec2cycVsync, intround, roundec
from Experiment import Experiment

from ManBar import STATUSBARHEIGHT, ManBar


class ManGrating(ManBar):
    """Manual grating experiment"""

    def createstimuli(self):
        """Creates the VisionEgg stimuli objects for this Experiment"""
        super(ManBar, self).createstimuli()
        self.nsinsamples = 2048 # number of samples of sine f'n, must be power of 2, quality/performance tradeoff
        self.grating = SinGrating2D(anchor='center',
                                    size=(deg2pix(self.heightDeg), deg2pix(self.widthDeg)), # VE defines grating ori as direction of motion of grating, but we want it to be the orientation of the grating elements, so add 90 deg (this also makes grating ori def'n correspond to bar ori def'n). This means that width and height have to be swapped
                                    pedestal=self.ml,
                                    ignore_time=True, # don't use this class' own time f'n
                                    num_samples=self.nsinsamples,
                                    max_alpha=1.0) # opaque
        self.gp = self.grating.parameters
        self.fixationspot = ve.Core.FixationSpot(anchor='center',
                                                 color=(1.0, 0.0, 0.0, 0.0),
                                                 size=(5, 5),
                                                 on=True)
        self.fp = self.fixationspot.parameters
        self.centerspot = ve.Core.FixationSpot(anchor='center',
                                                 color=(0.0, 1.0, 0.0, 0.0),
                                                 size=(3, 3),
                                                 on=True)
        self.cp = self.centerspot.parameters
        ##TODO: switch to pyglet.font
        fontname = pygame.font.match_font('lucidaconsole', bold=False, italic=False)
        self.screenstring = 'screen (w, h, d) = (%.1f, %.1f, %.1f) cm' % \
                            (I.SCREENWIDTHCM, I.SCREENHEIGHTCM, I.SCREENDISTANCECM)
        self.screentext = Text(position=(I.SCREENWIDTH-1, I.SCREENHEIGHT-1),
                               anchor='upperright',
                               text=self.screenstring,
                               color=(0.0, 1.0, 1.0, 1.0),
                               texture_mag_filter=gl.GL_NEAREST,
                               font_name=fontname,
                               font_size=10)
        self.stp = self.screentext.parameters
        self.mangratingtext = Text(position=(0, 0),
                                   anchor='lowerleft',
                                   color=(0.0, 1.0, 0.0, 1.0),
                                   texture_mag_filter=gl.GL_NEAREST,
                                   font_name=fontname,
                                   font_size=10)
        self.mgtp = self.mangratingtext.parameters
        self.upperbar = Target2D(position=(0, I.SCREENHEIGHT),
                                 anchor='upperleft',
                                 size=(I.SCREENWIDTH, STATUSBARHEIGHT),
                                 anti_aliasing=self.antialiase,
                                 color=(0.0, 0.0, 0.0, 1.0))
        self.lowerbar = Target2D(position=(0, 0),
                                 anchor='lowerleft',
                                 size=(I.SCREENWIDTH, STATUSBARHEIGHT),
                                 anti_aliasing=self.antialiase,
                                 color=(0.0, 0.0, 0.0, 1.0))

        # last entry will be topmost layer in viewport
        self.basic_stimuli = (self.background, self.grating)
        self.all_stimuli = (self.background, self.grating, self.fixationspot, self.centerspot,
                            self.upperbar, self.screentext, self.lowerbar, self.mangratingtext)

    def loadManbar(self, n):
        """Load Manbar n setting in dimstim config file and assign it to the current manual grating"""
        mbn = 'Manbar' + str(n)
        self.x = intround(deg2pix(dc.get(mbn, 'xorigDeg')) + I.SCREENWIDTH / 2) # int pix, since pygame.mouse pos works with ints
        self.y = intround(deg2pix(dc.get(mbn, 'yorigDeg')) + I.SCREENHEIGHT / 2)
        self.ori = dc.get(mbn, 'orioff')
        self.tfreqCycSec = dc.get(mbn, 'tfreqCycSec')
        self.sfreqCycDeg = dc.get(mbn, 'sfreqCycDeg')
        self.fp.position = self.x, self.y

    def saveManbar(self, n):
        """Save the state of the current manual grating as Manbar n in dimstim config file"""
        mbn = 'Manbar' + str(n)
        dc.set(mbn, 'xorigDeg', roundec(pix2deg(self.x - I.SCREENWIDTH / 2), ndec=6))
        dc.set(mbn, 'yorigDeg', roundec(pix2deg(self.y - I.SCREENHEIGHT / 2), ndec=6))
        dc.set(mbn, 'orioff', intround(self.ori))
        dc.set(mbn, 'tfreqCycSec', roundec(self.tfreqCycSec, ndec=6))
        dc.set(mbn, 'sfreqCycDeg', roundec(self.sfreqCycDeg, ndec=6))
        dc.update()
        self.fp.position = self.x, self.y
        self.brightenText = mbn # brighten the text for feedback

    def get_tfreq(self):
        """Get grating temporal frequency"""
        if self.UP:
            self.tfreqCycSec *= self.tfreqmultiplier
        elif self.DOWN:
            self.tfreqCycSec /= self.tfreqmultiplier

    def get_sfreq(self):
        """Get grating spatial frequency"""
        if self.RIGHT:
            self.sfreqCycDeg *= self.sfreqmultiplier
        elif self.LEFT:
            self.sfreqCycDeg /= self.sfreqmultiplier

    def get_contrast(self):
        """Get grating contrast"""
        if self.PLUS:
            self.contrast *= self.contrastmultiplier
        elif self.MINUS:
            self.contrast /= self.contrastmultiplier
        #self.contrast = max(self.contrast, 0) # keep it >= 0
        #self.contrast = min(self.contrast, 1) # keep it <= 1

    def updatestimuli(self):
        """Update stimuli"""
        # Update grating params
        height = deg2pix(self.heightDeg) # convenience
        self.gp.position = self.x, self.y
        self.gp.orientation = self.ori

        """Generate phase given current params
        sine grating eq'n used by VE: luminance(x) = 0.5*contrast*sin(2*pi*sfreqCycDeg*x + phaseRad) + ml ...where x is the position in deg along the axis of the sinusoid, and phaseRad = phaseDeg/180*pi. Motion in time is achieved by changing phaseDeg over time. phaseDeg inits to phase0"""
        sfreq = cycDeg2cycPix(self.sfreqCycDeg)
        try:
            self.phase
        except AttributeError: # phase hasn't been init'd yet
            """phaseoffset is req'd to make phase0 the initial phase at the centre of the grating, instead of at the edge of the grating as VE does. Take the distance from the centre to the edge along the axis of the sinusoid (which in this case is the height), multiply by spatial freq to get numcycles between centre and edge, multiply by 360 deg per cycle to get req'd phaseoffset. THE EXTRA 180 DEG IS NECESSARY FOR SOME REASON, DON'T REALLY UNDERSTAND WHY, BUT IT WORKS!!!"""
            phaseoffset = height / 2 * sfreq * 360 + 180
            self.phase = -self.phase0 - phaseoffset

        phasestep = cycSec2cycVsync(self.tfreqCycSec * self.nscreens) * 360 # delta cycles per vsync, in degrees of sinusoid, adjust for buffer flips on multiple screens
        self.phase = self.phase - phasestep # update phase

        self.gp.spatial_freq = sfreq
        self.gp.phase_at_t0 = self.phase
        self.gp.contrast = self.contrast
        self.bgp.color = (self.bgbrightness, self.bgbrightness, self.bgbrightness, 1.0)
        self.cp.position = self.x, self.y # update center spot position
        # Update text params
        self.mgtp.text = 'x, y = (%5.1f, %5.1f) deg  |  ori = %5.1f deg  |  tfreq = %.2f cyc/sec  |  sfreq = %.2f cyc/deg  |  contrast = %.2f' \
                         % ( pix2deg(self.x - I.SCREENWIDTH / 2), pix2deg(self.y - I.SCREENHEIGHT / 2),
                             self.ori, self.tfreqCycSec, self.sfreqCycDeg, self.contrast)
        self.stp.text = 'Eye open: %s  |  ' % C.EYESTATES[self.eyei] + self.screenstring

        if self.brightenText == 'Manbar0':
            self.mgtp.color = (1.0, 1.0, 0.0, 1.0) # set to yellow
        elif self.brightenText == 'Manbar1':
            self.mgtp.color = (1.0, 0.0, 0.0, 1.0) # set to red
        elif self.brightenText == 'Eye':
            self.stp.color = (1.0, 0.0, 0.0, 1.0) # set to red
        else:
            self.mgtp.color = (0.0, 1.0, 0.0, 1.0) # set it back to green
            self.stp.color = (0.0, 1.0, 1.0, 1.0) # set it back to cyan

    def run(self):
        """Run the experiment"""
        super(ManGrating, self).run(caption='Manual grating')

    def on_mouse_motion(self, x, y, dx, dy):
        """Update target position"""
        self.x += dx # need to use dx/dy when using exclusive_mouse
        self.y += dy
        self.x = min(max(self.x, 0), self.wins[0].win.width) # constrain it to the first window
        self.y = min(max(self.y, 0), self.wins[0].win.height)

    def on_key_press(self, symbol, modifiers):
        if symbol == key.UP:
            self.UP = True
        elif symbol == key.DOWN:
            self.DOWN = True
        elif symbol == key.RIGHT:
            self.RIGHT = True
        elif symbol == key.LEFT:
            self.LEFT = True
        elif symbol == key.EQUAL:
            self.PLUS = True
        elif symbol == key.MINUS:
            self.MINUS = True
        elif symbol in [key._0, key.NUM_0]: # set pos and ori to 0
            self.x = I.SCREENWIDTH / 2
            self.y = I.SCREENHEIGHT / 2
            self.ori = 0
        elif symbol in [key.SPACE, key.ENTER, key.NUM_ENTER] or modifiers & key.MOD_CTRL and symbol in [key._1, key.NUM_1]:
            self.saveManbar(0) # save Manbar state 0
        elif modifiers & key.MOD_CTRL and symbol in [key._2, key.NUM_2]:
            self.saveManbar(1) # save Manbar state 1
        elif symbol == key.E:
            self.cycleEye() # cycle eye state
        elif not modifiers & key.MOD_CTRL and symbol in [key._1, key.NUM_1]:
            self.loadManbar(0) # load Manbar state 0
        elif not modifiers & key.MOD_CTRL and symbol in [key._2, key.NUM_2]:
            self.loadManbar(1) # load Manbar state 1

    def on_key_release(self, symbol, modifiers):
        if symbol == key.UP:
            self.UP = False
        elif symbol == key.DOWN:
            self.DOWN = False
        elif symbol == key.RIGHT:
            self.RIGHT = False
        elif symbol == key.LEFT:
            self.LEFT = False
        elif symbol == key.EQUAL:
            self.PLUS = False
        elif symbol == key.MINUS:
            self.MINUS = False
        elif symbol in [key.SPACE, key.ENTER, key.NUM_ENTER, key.E] or \
            modifiers & key.MOD_CTRL and symbol in [key._1, key.NUM_1, key._2, key.NUM_2]:
            self.brightenText = False

    def attach_handlers(self):
        for win in self.wins:
            win.win.push_handlers(self.on_mouse_motion)
            win.win.push_handlers(self.on_key_press)
            win.win.push_handlers(self.on_key_release)
            win.win.push_handlers(self.on_mouse_press)
            win.win.push_handlers(self.on_mouse_release)
            win.win.push_handlers(self.on_mouse_scroll)

    def main(self):
        """Run the main stimulus loop"""
        while np.alltrue([ not win.win.has_exit for win in self.wins ]):

            for win in self.wins:
                win.dispatch_events() # to the event handlers

            self.get_ori()
            self.get_tfreq()
            self.get_sfreq()
            self.get_contrast()
            self.updatestimuli()

            if self.flash:
                if not self.nvsyncsdisplayed % self.flashvsyncs:
                    self.gp.on = not self.gp.on # toggle it

            for win, viewport in zip(self.wins, self.viewports):
                win.switch_to()
                win.clear()
                viewport.draw()
                #ve.Core.swap_buffers() # returns immediately
                win.flip()
                gl.glFlush() # waits for next vsync pulse from video card

            if self.printhistogram: self.vsynctimer.tick()
            self.nvsyncsdisplayed += 1 # increment
