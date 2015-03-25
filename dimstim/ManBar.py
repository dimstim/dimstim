"""Defines the Manual Bar Experiment"""

from __future__ import division

import os
import math
import time
import datetime
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
from VisionEgg.Text import Text

import Constants as C
from Constants import dc, I
import Core
from Core import sec2intvsync, deg2pix, pix2deg, iterable, isotime, intround, roundec
from Window import Window
from Experiment import Experiment, info, printf2log

STATUSBARHEIGHT = 12 # height of upper and lower status bars (pix)
FLASHRATEMULT = 1 + 0.75 / I.REFRESHRATE

def invramp(gamma):
    """Inverted gamma ramp"""
    ramp = np.arange(256, dtype=np.uint16) / 255 # normalized linear ramp
    ramp = np.power(ramp, 1 / gamma) * 255 # unnormalized inverted gamma ramp
    return np.uint16(np.round(ramp)) # convert back to nearest ints


class ManBar(Experiment):
    """Manual bar experiment"""
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
        self.squarelock, self.brightenText = False, False
        self.UP, self.DOWN, self.LEFT, self.RIGHT = False, False, False, False
        self.PAGEUP, self.PAGEDOWN = False, False
        self.PLUS, self.MINUS = False, False
        self.LEFTBUTTON, self.RIGHTBUTTON, self.SCROLL = False, False, False
        self.eyei = C.EYESTATES.index(eye)

    def build(self):
        """Builds the SweepTable and the Header, not required for ManBar experiment"""
        pass

    def setgamma(self, gamma):
        """Set VisionEgg's gamma parameter and apply it to pyglet windows"""
        vc = VisionEgg.config
        super(ManBar, self).setgamma(gamma) # Set VisionEgg's gamma parameter
        if gamma:
            ramps = [] # now apply it to our pyglet windows
            for gamma in (vc.VISIONEGG_GAMMA_INVERT_RED,
                          vc.VISIONEGG_GAMMA_INVERT_GREEN,
                          vc.VISIONEGG_GAMMA_INVERT_BLUE):
                ramps.append(invramp(gamma))
            #for win in self.wins:
            #    win.set_gamma_ramps(ramps)
            self.wins[0].set_gamma_ramps(ramps) # only need to do it for the first one

    def createstimuli(self):
        """Creates the VisionEgg stimuli objects for this Experiment"""
        super(ManBar, self).createstimuli()
        self.target = Target2D(anchor='center',
                               anti_aliasing=self.antialiase,
                               color=(self.brightness, self.brightness, self.brightness, 1.0))
        self.tp = self.target.parameters # synonym
        self.tip = Target2D(size=(5, 1),
                            anchor='center',
                            anti_aliasing=self.antialiase,
                            color=(1.0, 0.0, 0.0, 1.0))
        self.tipp = self.tip.parameters
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
        self.manbartext = Text(position=(0, 0),
                               anchor='lowerleft',
                               color=(0.0, 1.0, 0.0, 1.0),
                               texture_mag_filter=gl.GL_NEAREST,
                               font_name=fontname,
                               font_size=10)
        self.mbtp = self.manbartext.parameters
        self.squarelocktext = Text(position=(0, I.SCREENHEIGHT),
                                   anchor='upperleft',
                                   text='SQUARELOCK',
                                   color=(0.0, 1.0, 1.0, 1.0),
                                   texture_mag_filter=gl.GL_NEAREST,
                                   font_name=fontname,
                                   font_size=10,
                                   on=False) # leave it off for now
        self.sltp = self.squarelocktext.parameters
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
        self.basic_stimuli = (self.background, self.target)
        self.all_stimuli = (self.background, self.target, self.tip,
                            self.fixationspot, self.centerspot,
                            self.upperbar, self.squarelocktext, self.screentext,
                            self.lowerbar, self.manbartext)

    def loadManbar(self, n):
        """Load Manbar n setting in dimstim config file and assign it to the current manual bar"""
        mbn = 'Manbar' + str(n)
        self.x = intround(deg2pix(dc.get(mbn, 'xorigDeg')) + I.SCREENWIDTH / 2) # int pix, since pygame.mouse pos works with ints
        self.y = intround(deg2pix(dc.get(mbn, 'yorigDeg')) + I.SCREENHEIGHT / 2)
        self.widthDeg = dc.get(mbn, 'widthDeg')
        self.heightDeg = dc.get(mbn, 'heightDeg')
        self.ori = dc.get(mbn, 'orioff')
        self.fp.position = self.x, self.y

    def saveManbar(self, n):
        """Save the state of the current manual bar as Manbar n in dimstim config file"""
        mbn = 'Manbar' + str(n)
        dc.set(mbn, 'xorigDeg', roundec(pix2deg(self.x - I.SCREENWIDTH / 2), ndec=6))
        dc.set(mbn, 'yorigDeg', roundec(pix2deg(self.y - I.SCREENHEIGHT / 2), ndec=6))
        dc.set(mbn, 'widthDeg', roundec(self.widthDeg, ndec=6))
        dc.set(mbn, 'heightDeg', roundec(self.heightDeg, ndec=6))
        dc.set(mbn, 'orioff', intround(self.ori))
        dc.update()
        self.fp.position = self.x, self.y
        self.brightenText = mbn # brighten the text for feedback

    def get_size(self):
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

    def get_ori(self):
        """Get target orientation, make scrolling snap to nearest snapDeg ori step"""
        if self.SCROLL:
            mod = self.ori % self.snapDeg
            if mod:
                if self.SCROLL > 0: # snap up
                    self.ori += -mod + self.SCROLL * self.snapDeg
                else: # snap down
                    self.ori -= mod
            else: # snap up or down by a full snapDeg ori step
                self.ori += self.SCROLL * self.snapDeg
            self.SCROLL = False
        elif self.LEFTBUTTON:
            self.ori += self.orirateDegSec / I.REFRESHRATE
        elif self.RIGHTBUTTON:
            self.ori -= self.orirateDegSec / I.REFRESHRATE
        self.ori = self.ori % 360 # keep it in [0, 360)

    def get_flash(self):
        """Get target flash duration"""
        if self.PAGEUP:
            self.flashSec *= FLASHRATEMULT
        elif self.PAGEDOWN:
            self.flashSec /= FLASHRATEMULT
        self.flashvsyncs = sec2intvsync(self.flashSec)
        self.flashvsyncs = max(self.flashvsyncs, 1) # keep it >= 1, % 0 gives ZeroDivisionError

    def get_brightness(self):
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
        self.cp.position = self.x, self.y # update center spot position
        # Update text params
        self.mbtp.text = 'x, y = (%5.1f, %5.1f) deg  |  size = (%.1f, %.1f) deg  |  ori = %5.1f deg' \
                         % ( pix2deg(self.x - I.SCREENWIDTH / 2), pix2deg(self.y - I.SCREENHEIGHT / 2),
                             self.widthDeg, self.heightDeg, self.ori)
        self.stp.text = 'Eye open: %s  |  ' % C.EYESTATES[self.eyei] + self.screenstring

        if self.brightenText == 'Manbar0':
            self.mbtp.color = (1.0, 1.0, 0.0, 1.0) # set to yellow
        elif self.brightenText == 'Manbar1':
            self.mbtp.color = (1.0, 0.0, 0.0, 1.0) # set to red
        elif self.brightenText == 'Eye':
            self.stp.color = (1.0, 0.0, 0.0, 1.0) # set to red
        else:
            self.mbtp.color = (0.0, 1.0, 0.0, 1.0) # set it back to green
            self.stp.color = (0.0, 1.0, 1.0, 1.0) # set it back to cyan

        if self.squarelock:
            self.sltp.on = True
        else:
            self.sltp.on = False

    def run(self, caption='Manual bar'):
        """Run the experiment"""
        info('Running Experiment script: %s' % self.script)

        # Init OpenGL graphics windows, one window per requested screen
        platform = pyglet.window.get_platform()
        display = platform.get_default_display()
        self.screens = display.get_screens()
        self.screens = self.screens[:self.nscreens] # keep the first nscreens requested
        self.nscreens = len(self.screens) # update
        self.flashvsyncs = intround(self.flashvsyncs / self.nscreens) # normalize by number of screens to flip in each loop in main()
        self.wins = []
        for screeni, screen in enumerate(self.screens):
            # make all screens fullscreen, except for the first (user) screen
            if screeni == 0:
                win = Window(screen=screen, fullscreen=False, frameless=False)
                win.win.set_location((screen.width - win.win.width)//2,
                                     (screen.height - win.win.height)//2)
                win.win.set_caption(caption)
            else:
                win = Window(screen=screen, fullscreen=True)
            win.win.set_exclusive_mouse(True)
            self.wins.append(win)

        self.setgamma(self.params.gamma)

        # Create VisionEgg stimuli objects, defined by each specific subclass of Experiment
        self.createstimuli()

        # Create viewport(s) with varying stimuli
        self.viewports = []
        for wini, win in enumerate(self.wins):
            if wini == 0:
                self.viewports.append(ve.Core.pyglet_Viewport(window=win, stimuli=self.all_stimuli))
            else:
                self.viewports.append(ve.Core.pyglet_Viewport(window=win, stimuli=self.basic_stimuli))
        self.loadManbar(0) # load settings from Manbar0
        self.bgp.color = self.bgbrightness, self.bgbrightness, self.bgbrightness, 1.0

        # Create the VsyncTimer
        self.vsynctimer = Core.VsyncTimer()
        '''
        # Hack to fix pygame jumping mouse bug in fullscreen mode
        # mousemotion event happens on startup, and then once more due to bug
        for i in range(2):
            pygame.event.peek(pl.MOUSEMOTION)
        pygame.mouse.set_pos(self.x, I.SCREENHEIGHT - 1 - self.y) # set that sucker
        '''
        self.attach_handlers()

        self.nvsyncsdisplayed = 0 # nvsyncs seen by Surf

        self.startdatetime = datetime.datetime.now()
        self.starttime = time.clock() # precision timestamp

        # Run the main stimulus loop, defined by each specific subclass of Experiment
        self.main()

        self.stoptime = time.clock() # precision timestamp
        self.stopdatetime = datetime.datetime.now()

        # Close OpenGL graphics windows (necessary when running from Python interpreter)
        self.wins[0].restore_gamma_ramps() # only needs to be done once
        for win in self.wins:
            win.close()

        # Print messages to VisionEgg log and to screen
        info(self.vsynctimer.pprint(), toscreen=self.printhistogram, tolog=self.printhistogram)
        info('%d vsyncs displayed' % self.nvsyncsdisplayed)
        info('Experiment duration: %s' % isotime(self.stoptime-self.starttime, 6))
        printf2log('\n' + '-'*80 + '\n') # add minuses to end of log to space it out between sessions

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
        elif symbol == key.PAGEUP:
            self.PAGEUP = True
        elif symbol == key.PAGEDOWN:
            self.PAGEDOWN = True
        elif symbol in [key.LSHIFT, key.RSHIFT]:
            self.squarelock = True
        elif symbol == key.I: # swap (invert) foreground and background brightness
            self.brightness, self.bgbrightness = self.bgbrightness, self.brightness
        elif symbol in [key._0, key.NUM_0]: # set pos and ori to 0
            self.x = I.SCREENWIDTH / 2
            self.y = I.SCREENHEIGHT / 2
            self.ori = 0
        elif symbol in [key.ENTER, key.NUM_ENTER] or modifiers & key.MOD_CTRL and symbol in [key._1, key.NUM_1]:
            self.saveManbar(0) # save Manbar state 0
        elif symbol == key.SPACE:
            self.flash = not self.flash
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
        elif symbol == key.PAGEUP:
            self.PAGEUP = False
        elif symbol == key.PAGEDOWN:
            self.PAGEDOWN = False
        elif symbol in [key.LSHIFT, key.RSHIFT]:
            self.squarelock = False
        elif symbol in [key.ENTER, key.NUM_ENTER, key.E] or \
            modifiers & key.MOD_CTRL and symbol in [key._1, key.NUM_1, key._2, key.NUM_2]:
            self.brightenText = False

    def on_mouse_press(self, x, y, button, modifiers):
        if button == mouse.LEFT:
            self.LEFTBUTTON = True
        elif button == mouse.RIGHT:
            self.RIGHTBUTTON = True
        elif button == mouse.MIDDLE: # scroll wheel button
            self.saveManbar(0) # save Manbar state 0

    def on_mouse_release(self, x, y, button, modifiers):
        if button == mouse.LEFT:
            self.LEFTBUTTON = False
        elif button == mouse.RIGHT:
            self.RIGHTBUTTON = False
        elif button == mouse.MIDDLE: # scroll wheel button
            self.brightenText = False

    def on_mouse_scroll(self, x, y, scroll_x, scroll_y):
        self.SCROLL = scroll_y / abs(scroll_y) # +ve or -ve scroll click

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

            self.get_size()
            self.get_ori()
            self.get_brightness()
            self.get_flash()
            self.updatestimuli()

            if self.flash:
                if not self.nvsyncsdisplayed % self.flashvsyncs:
                    self.tp.on = not self.tp.on # toggle it
                    self.tipp.on = not self.tipp.on

            for win, viewport in zip(self.wins, self.viewports):
                win.switch_to()
                win.clear()
                viewport.draw()
                #ve.Core.swap_buffers() # returns immediately
                win.flip()
                gl.glFlush() # waits for next vsync pulse from video card

            if self.printhistogram: self.vsynctimer.tick()
            self.nvsyncsdisplayed += 1 # increment
