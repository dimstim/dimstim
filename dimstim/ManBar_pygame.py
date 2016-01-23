"""Defines the Manual Bar Experiment, implemented in pygame"""

from __future__ import division

import os
import math
import time
import datetime
import numpy as np
np.seterr(all='raise') # raise all numpy errors (like 1/0), don't just warn
import pygame
import pygame.locals as pl
import OpenGL.GL as gl

import VisionEgg as ve
import VisionEgg.Core
from VisionEgg.MoreStimuli import Target2D
from VisionEgg.Text import Text

import Constants as C
from Constants import dc, I
import Core
from Core import sec2intvsync, deg2pix, pix2deg, iterable, isotime, intround, roundec
from Experiment import Experiment, info, printf2log

LB = 0.5 # low text brightness
HB = 1.0 # high text brightness

class Params(Core.dictattr):
    """Stores experiment parameters"""
    def __init__(self, *args, **kwargs):
        super(Params, self).__init__(*args, **kwargs)
    def check(self):
        for paramname, paramval in self.items():
            assert not iterable(paramval) or paramval.__class__ == str, 'parameter must be a scalar: %s = %r' % (paramname, paramval) # can't be an iterable object, unless it's a string


class ManBar_pygame(Experiment):
    """Manual bar experiment, in pygame"""
    def __init__(self, script, params):
        self.script = script.replace('\\', C.SLASH).replace('.pyc', '.py') # Experiment script file name, with stuff cleaned up
        self.script = os.path.splitdrive(self.script)[-1] # strip the drive name from the start
        self.params = params
        self.params.check()
        for paramname, paramval in params.items():
            setattr(self, paramname, paramval) # bind all parameter names to self
        self.flashvsyncs = sec2intvsync(self.flashSec)
        eye = dc.get('Eye', 'open')
        # Init signals
        self.quit, self.squarelock, self.brightenText = False, False, False
        self.UP, self.DOWN, self.LEFT, self.RIGHT = False, False, False, False
        self.PLUS, self.MINUS = False, False
        self.CTRL = False
        self.LEFTBUTTON, self.RIGHTBUTTON = False, False
        self.SCROLLDOWN, self.SCROLLUP = False, False
        self.eyei = C.EYESTATES.index(eye)

    def build(self):
        """Builds the SweepTable and the Header, not required for ManBar experiment"""
        pass

    def setgamma(self):
        """Set VisionEgg's gamma parameter"""
        vc = VisionEgg.config
        if self.params.gamma:
            vc.VISIONEGG_GAMMA_SOURCE = 'invert' # 'invert' in VE means that gamma correction is turned on
            vc.VISIONEGG_GAMMA_INVERT_RED = self.params.gamma
            vc.VISIONEGG_GAMMA_INVERT_GREEN = self.params.gamma
            vc.VISIONEGG_GAMMA_INVERT_BLUE = self.params.gamma
        else:
            vc.VISIONEGG_GAMMA_SOURCE = 'None'
            vc.VISIONEGG_GAMMA_INVERT_RED = 0
            vc.VISIONEGG_GAMMA_INVERT_GREEN = 0
            vc.VISIONEGG_GAMMA_INVERT_BLUE = 0

    def createstimuli(self):
        """Creates the VisionEgg stimuli objects for this Experiment"""
        super(ManBar_pygame, self).createstimuli()
        self.target = Target2D(anchor='center',
                               anti_aliasing=self.antialiase,
                               color=(self.brightness, self.brightness, self.brightness, 1.0))
        self.tp = self.target.parameters # synonym
        self.tip = Target2D(size=(5, 1),
                            anchor='center',
                            anti_aliasing=self.antialiase,
                            color=(1.0, 0.0, 0.0, 1.0))
        self.tipp = self.tip.parameters
        fontname = pygame.font.match_font('lucidaconsole', bold=False, italic=False)
        self.manbartext = Text(position=(0, 6),
                               anchor='left',
                               color=(0.0, LB, 0.0, 1.0),
                               texture_mag_filter=gl.GL_NEAREST,
                               font_name=fontname,
                               font_size=10)
        self.mbtp = self.manbartext.parameters
        self.screentext = Text(position=(I.SCREENWIDTH-1, 6),
                               anchor='right',
                               text='screen (w, h, d) = (%.1f, %.1f, %.1f) cm' %
                                     (I.SCREENWIDTHCM, I.SCREENHEIGHTCM, I.SCREENDISTANCECM),
                               color=(LB, 0.0, 0.0, 1.0),
                               texture_mag_filter=gl.GL_NEAREST,
                               font_name=fontname,
                               font_size=10)
        self.stp = self.screentext.parameters
        self.squarelocktext = Text(position=(0, I.SCREENHEIGHT),
                                   anchor='upperleft',
                                   text='SQUARELOCK',
                                   color=(0.0, HB, HB, 1.0),
                                   texture_mag_filter=gl.GL_NEAREST,
                                   font_name=fontname,
                                   font_size=10,
                                   on=False) # leave it off for now
        self.sltp = self.squarelocktext.parameters
        # last entry will be topmost layer in viewport
        self.stimuli = (self.background, self.target, self.tip, self.manbartext, self.screentext, self.squarelocktext)

    def loadManbar(self, n):
        """Load Manbar n setting in dimstim config file and assign it to the current manual bar"""
        mbn = 'Manbar' + str(n)
        self.x = intround(deg2pix(dc.get(mbn, 'xorigDeg')) + I.SCREENWIDTH / 2) # int pix, since pygame.mouse pos works with ints
        self.y = intround(deg2pix(dc.get(mbn, 'yorigDeg')) + I.SCREENHEIGHT / 2)
        self.widthDeg = dc.get(mbn, 'widthDeg')
        self.heightDeg = dc.get(mbn, 'heightDeg')
        self.ori = dc.get(mbn, 'orioff')
        pygame.mouse.set_pos(self.x, I.SCREENHEIGHT - 1 - self.y)

    def saveManbar(self, n):
        """Save the state of the current manual bar as Manbar n in dimstim config file"""
        mbn = 'Manbar' + str(n)
        dc.set(mbn, 'xorigDeg', roundec(pix2deg(self.x - I.SCREENWIDTH / 2), ndec=6))
        dc.set(mbn, 'yorigDeg', roundec(pix2deg(self.y - I.SCREENHEIGHT / 2), ndec=6))
        dc.set(mbn, 'widthDeg', roundec(self.widthDeg, ndec=6))
        dc.set(mbn, 'heightDeg', roundec(self.heightDeg, ndec=6))
        dc.set(mbn, 'orioff', intround(self.ori))
        dc.update()
        self.brightenText = mbn # brighten the text for feedback

    def get_targetposition(self):
        """Get target position"""
        self.x, self.y = pygame.mouse.get_pos()
        self.y = I.SCREENHEIGHT - 1 - self.y

    def get_targetsize(self):
        """Get target width and height"""
        if self.UP:
            self.heightDeg += self.sizerateDegSec / I.REFRESHRATE
            if self.squarelock: self.widthDeg = self.heightDeg
        elif self.DOWN:
            self.heightDeg = max(self.heightDeg - self.sizerateDegSec / I.REFRESHRATE, 0.1)
            if self.squarelock: self.widthDeg = self.heightDeg
        if self.RIGHT:
            self.widthDeg += self.sizerateDegSec / I.REFRESHRATE
            if self.squarelock: self.heightDeg = self.widthDeg
        elif self.LEFT:
            self.widthDeg = max(self.widthDeg - self.sizerateDegSec / I.REFRESHRATE, 0.1)
            if self.squarelock: self.heightDeg = self.widthDeg

    def get_targetori(self):
        """Get target orientation, make scrolling snap to nearest snapDeg ori step"""
        if self.SCROLLUP:
            self.ori += self.snapDeg - (self.ori % self.snapDeg)
            self.SCROLLUP = False # do this here cuz there's no stop scrolling event
        elif self.SCROLLDOWN:
            self.ori -= self.snapDeg + (self.ori % self.snapDeg) - self.snapDeg*bool(self.ori % self.snapDeg)
            self.SCROLLDOWN = False # do this here cuz there's no stop scrolling event
        elif self.LEFTBUTTON:
            self.ori += self.orirateDegSec / I.REFRESHRATE
        elif self.RIGHTBUTTON:
            self.ori -= self.orirateDegSec / I.REFRESHRATE
        self.ori = self.ori % 360 # keep it in [0, 360)

    def get_targetbrightness(self):
        """Get target brightness"""
        if self.PLUS:
            self.brightness += self.brightnessstep
        elif self.MINUS:
            self.brightness -= self.brightnessstep
        self.brightness = max(self.brightness, 0) # keep it >= 0
        self.brightness = min(self.brightness, 1) # keep it <= 1

    def cycleEye(self):
        """Cycle the current eye state and save it to dimstim config file"""
        self.eyei = (self.eyei + 1) % len(C.EYESTATES)
        dc.set('Eye', 'open', C.EYESTATES[self.eyei])
        dc.update()
        self.brightenText = 'Eye' # brighten the text for feedback

    def updatestimuli(self):
        """Update stimuli"""
        # Update target params
        width = deg2pix(self.widthDeg) # convenience
        height = deg2pix(self.heightDeg)
        self.tp.position = self.x, self.y
        self.tp.size = width, height # convert to pix
        self.tp.orientation = self.ori
        self.tp.color = (self.brightness, self.brightness, self.brightness, 1.0)
        self.bgp.color = (self.bgbrightness, self.bgbrightness, self.bgbrightness, 1.0)
        self.tipp.position = ( self.x + width / 2 * math.cos(math.pi / 180 * self.ori),
                               self.y + width / 2 * math.sin(math.pi / 180 * self.ori) )
        self.tipp.orientation = self.ori
        # Update text params
        self.mbtp.text = 'x, y = (%5.1f, %5.1f) deg  |  size = (%.1f, %.1f) deg  |  ori = %5.1f deg  |  Eye open: %s' \
                         % ( pix2deg(self.x - I.SCREENWIDTH / 2), pix2deg(self.y - I.SCREENHEIGHT / 2),
                             self.widthDeg, self.heightDeg, self.ori, C.EYESTATES[self.eyei] )
        if self.brightenText in ['Manbar0', 'Eye']:
            self.mbtp.color = (0.0, HB, 0.0, 1.0) # set to bright green
        elif self.brightenText == 'Manbar1':
            self.mbtp.color = (HB, 0.0, 0.0, 1.0) # set to bright red
        else:
            self.mbtp.color = (0.0, LB, 0.0, 1.0) # set it to normal green
        if self.squarelock:
            self.sltp.on = True
        else:
            self.sltp.on = False

    def run(self):
        """Run the experiment"""
        info('Running Experiment script: %s' % self.script)

        self.setgamma()

        # Init OpenGL graphics screen
        self.screen = ve.Core.get_default_screen()

        # Create VisionEgg stimuli objects, defined by each specific subclass of Experiment
        self.createstimuli()

        # Create a VisionEgg Viewport
        self.viewport = ve.Core.Viewport(screen=self.screen, stimuli=self.stimuli)
        self.loadManbar(0) # load settings from Manbar0
        self.bgp.color = self.bgbrightness, self.bgbrightness, self.bgbrightness, 1.0

        # Create the VsyncTimer
        self.vsynctimer = Core.VsyncTimer()

        # Hack to fix pygame jumping mouse bug in fullscreen mode
        # mousemotion event happens on startup, and then once more due to bug
        for i in range(2):
            pygame.event.peek(pl.MOUSEMOTION)
        pygame.mouse.set_pos(self.x, I.SCREENHEIGHT - 1 - self.y) # set that sucker

        self.nvsyncsdisplayed = 0 # nvsyncs seen by acq

        self.startdatetime = datetime.datetime.now()
        self.starttime = time.clock() # precision timestamp

        # Run the main stimulus loop, defined by each specific subclass of Experiment
        self.main()

        self.stoptime = time.clock() # precision timestamp
        self.stopdatetime = datetime.datetime.now()

        # Close OpenGL graphics screen (necessary when running from Python interpreter)
        self.screen.close()

        # Print messages to VisionEgg log and to screen
        info(self.vsynctimer.pprint(), toscreen=self.printhistogram, tolog=self.printhistogram)
        info('%d vsyncs displayed' % self.nvsyncsdisplayed)
        info('Experiment duration: %s' % isotime(self.stoptime-self.starttime, 6))
        printf2log('\n' + '-'*80 + '\n') # add minuses to end of log to space it out between sessions

    def main(self):
        """Run the main stimulus loop"""
        while not self.quit:
            for event in pygame.event.get():
                if event.type == pl.KEYDOWN:
                    if event.key == pl.K_ESCAPE:
                        self.quit = True
                    elif event.key == pl.K_UP:
                        self.UP = True
                    elif event.key == pl.K_DOWN:
                        self.DOWN = True
                    elif event.key == pl.K_RIGHT:
                        self.RIGHT = True
                    elif event.key == pl.K_LEFT:
                        self.LEFT = True
                    elif event.key == pl.K_EQUALS:
                        self.PLUS = True
                    elif event.key == pl.K_MINUS:
                        self.MINUS = True
                    elif event.key in [pl.K_LSHIFT, pl.K_RSHIFT]:
                        self.squarelock = True
                    elif event.key == pl.K_SPACE: # swap foreground and background brightness
                        self.brightness, self.bgbrightness = self.bgbrightness, self.brightness
                    elif event.key in [pl.K_0, pl.K_KP0]: # set pos and ori to 0
                        self.x = I.SCREENWIDTH / 2
                        self.y = I.SCREENHEIGHT / 2
                        pygame.mouse.set_pos(self.x, I.SCREENHEIGHT - 1 - self.y)
                        self.ori = 0
                    elif event.key in [pl.K_RETURN, pl.K_KP_ENTER] or self.CTRL and event.key == pl.K_1:
                        self.saveManbar(0) # save Manbar state 0
                    elif self.CTRL and event.key == pl.K_2:
                        self.saveManbar(1) # save Manbar state 1
                    elif event.key == pl.K_i:
                        self.cycleEye() # cycle eye state
                    elif not self.CTRL and event.key in [pl.K_1, pl.K_KP1]:
                        self.loadManbar(0) # load Manbar state 0
                    elif not self.CTRL and event.key in [pl.K_2, pl.K_KP2]:
                        self.loadManbar(1) # load Manbar state 1
                    elif event.key in [pl.K_LCTRL, pl.K_RCTRL]: # control keys
                        self.CTRL = True
                elif event.type == pl.KEYUP:
                    if event.key == pl.K_UP:
                        self.UP = False
                    elif event.key == pl.K_DOWN:
                        self.DOWN = False
                    elif event.key == pl.K_RIGHT:
                        self.RIGHT = False
                    elif event.key == pl.K_LEFT:
                        self.LEFT = False
                    elif event.key == pl.K_EQUALS:
                        self.PLUS = False
                    elif event.key == pl.K_MINUS:
                        self.MINUS = False
                    elif event.key in [pl.K_LSHIFT, pl.K_RSHIFT]:
                        self.squarelock = False
                    elif event.key in [pl.K_RETURN, pl.K_KP_ENTER, pl.K_i] or self.CTRL and event.key in [pl.K_1, pl.K_2]:
                        self.brightenText = False
                    elif event.key in [pl.K_LCTRL, pl.K_RCTRL]: # control keys
                        self.CTRL = False
                elif event.type == pl.MOUSEBUTTONDOWN:
                    if event.button == 4: # wheel was scrolled up
                        self.SCROLLUP = True
                    elif event.button == 5: # wheel was scrolled down
                        self.SCROLLDOWN = True
                    elif event.button == 1:
                        self.LEFTBUTTON = True
                    elif event.button == 3:
                        self.RIGHTBUTTON = True
                    elif event.button == 2: # scroll wheel button
                        self.saveManbar(0) # save Manbar state 0
                elif event.type == pl.MOUSEBUTTONUP: # stopping scrolling isn't an event
                    if event.button == 1:
                        self.LEFTBUTTON = False
                    elif event.button == 3:
                        self.RIGHTBUTTON = False
                    elif event.button == 2: # scroll wheel button
                        self.brightenText = False

            self.get_targetposition()

            self.get_targetsize()

            self.get_targetori()

            self.get_targetbrightness()

            self.updatestimuli()

            if self.flash:
                if not self.nvsyncsdisplayed % self.flashvsyncs:
                    self.tp.on = not self.tp.on # toggle it
                    self.tipp.on = not self.tipp.on

            self.screen.clear()
            self.viewport.draw()
            ve.Core.swap_buffers() # returns immediately
            gl.glFlush() # waits for next vsync pulse from video card
            if self.printhistogram: self.vsynctimer.tick()
            self.nvsyncsdisplayed += 1 # increment
