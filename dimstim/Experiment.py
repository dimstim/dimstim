"""Defines the base Experiment class"""

from __future__ import division

import os
import time
import datetime
import numpy as np
np.seterr(all='raise') # raise all numpy errors (like 1/0), don't just warn
import OpenGL.GL as gl
import pygame

import VisionEgg as ve
import VisionEgg.Core # isn't imported automatically by VE's __init__.py
from VisionEgg.MoreStimuli import Target2D

import Constants as C
from Constants import I, SWEEP
import Core
from Core import iterable, toiter, deg2pix, sec2intvsync, vsync2sec, isotime
try:
    from Core import DT # only importable if DT board is installed
except ImportError:
    pass

printer = C.printer # synonym
info = printer.info
warning = printer.warning
printf2log = printer.printf2log


class Experiment(object):
    """Base Experiment class, all experiments inherit from this"""
    def __init__(self, script, static, dynamic, variables, runs=None, blanksweeps=None):
        self.script = script.replace('\\', C.SLASH).replace('.pyc', '.py') # Experiment script file name, with stuff cleaned up
        self.script = os.path.splitdrive(self.script)[-1] # strip the drive name from the start
        self.static = static # StaticParams object
        self.dynamic = dynamic # DynamicParams object
        self.variables = variables # Variables object
        self.runs = runs # Runs object
        self.blanksweeps = blanksweeps # BlankSweeps object

    def check(self):
        """Check various Experiment attributes"""
        # check that all static params are scalars
        self.static.check()
        # check that those dynamic params that aren't variables are scalars
        for paramname, paramval in self.dynamic.items():
            if paramname not in self.variables.keys():
                assert not iterable(paramval), 'dynamic parameter %s is a vector, yet it isn\'t entered as a Variable' % paramname

    def calcduration(self):
        """Calculates how long this Experiment should take, in sec"""
        i = self.sweeptable.i
        # convert all times to vsyncs, add 'em up, then convert back. This takes into account discretization from sec to vsync
        try:
            blanksweepvsyncs = sec2intvsync(self.blanksweeps.sec) * list(i).count(None)
        except AttributeError: # blanksweeps are None, None has no .sec attrib
            blanksweepvsyncs = 0
        notblank = np.int32(i[np.not_equal(i, None)]) # sweep table indices that aren't blank sweeps, i was an object array due to Nones in it
        nvsyncs = sec2intvsync(self.static.preexpSec) + \
                  np.asarray([ sec2intvsync(sweeptime) for sweeptime in self.st.sweepSec[notblank] ]).sum() + \
                  np.asarray([ sec2intvsync(postsweeptime) for postsweeptime in self.st.postsweepSec[notblank] ]).sum() + \
                  blanksweepvsyncs + \
                  sec2intvsync(self.static.postexpSec)
        return vsync2sec(nvsyncs)

    def build(self):
        """Builds the SweepTable and the Header for this Experiment"""
        # Build the sweep table
        self.sweeptable = Core.SweepTable(experiment=self)
        self.st = self.sweeptable.data # synonym, used a lot by Experiment subclasses

        # Do time and space conversions of applicable static and dynamic parameters - or maybe do this in init - is this really necessary, can't it be done on the fly, or would that be too slow? If too slow, write it inline in C and use scipy.weave?
        # Is there a better place to store these, rather than polluting self namespace?
        self.xorig = deg2pix(self.static.xorigDeg) + I.SCREENWIDTH / 2 # do this once, since it's static, save time in main loop
        self.yorig = deg2pix(self.static.yorigDeg) + I.SCREENHEIGHT / 2

        # Calculate Experiment duration
        self.sec = self.calcduration()
        info('Expected experiment duration: %s' % isotime(self.sec, 6), tolog=False)

        # Build the Surf file header, the NVS header, and the text header
        self.header = Core.Header(experiment=self)
        info('TextHeader.data:', toscreen=False)
        printf2log(str(self.header.text)) # print text header data to log

    def setgamma(self, gamma):
        """Set VisionEgg's gamma parameter"""
        vc = VisionEgg.config
        if gamma: # could be a single value or a sequence (preferably a tuple)
            vc.VISIONEGG_GAMMA_SOURCE = 'invert' # 'invert' in VE means that gamma correction is turned on
            if len(toiter(gamma)) == 1: # single value for all 3 guns
                vc.VISIONEGG_GAMMA_INVERT_RED = gamma
                vc.VISIONEGG_GAMMA_INVERT_GREEN = gamma
                vc.VISIONEGG_GAMMA_INVERT_BLUE = gamma
            elif len(toiter(gamma)) == 3: # separate value for each gun
                vc.VISIONEGG_GAMMA_INVERT_RED = gamma[0]
                vc.VISIONEGG_GAMMA_INVERT_GREEN = gamma[1]
                vc.VISIONEGG_GAMMA_INVERT_BLUE = gamma[2]
            else:
                raise ValueError, 'gamma cannot be of length %d' % len(toiter(gamma))
        else:
            vc.VISIONEGG_GAMMA_SOURCE = 'None' # 'None' in VE means that gamma correction is turned off
            vc.VISIONEGG_GAMMA_INVERT_RED = 0 # set them all to 0 too, just to be thorough
            vc.VISIONEGG_GAMMA_INVERT_GREEN = 0
            vc.VISIONEGG_GAMMA_INVERT_BLUE = 0

    def createstimuli(self):
        """Creates the VisionEgg stimuli objects common to all Experiment subclasses"""
        self.background = Target2D(position=(I.SCREENWIDTH/2, I.SCREENHEIGHT/2),
                                   anchor='center',
                                   size=(I.SCREENWIDTH, I.SCREENHEIGHT),
                                   on=True)

        self.bgp = self.background.parameters # synonym

    def initbackgroundcolor(self):
        """Sets the initial background colour. Can probably be the same method for all Experiment subclasses"""
        bgb = self.sweeptable.data.bgbrightness[0] # get it for sweep table index 0
        self.bgp.color = bgb, bgb, bgb, 1.0 # set bg colour, do this now so it's correct for the pre-exp delay

    def fix1stsweeplag(self):
        """Hacks to fix two kinds of lag that can happen on the first sweep"""
        onstates = []
        for stim in self.stimuli: # save the on states of all stimuli
            onstates.append(stim.parameters.on)

        # update the stimulus before first sweep, prevents first-sweep lag for movies > 1GB
        self.updateparams(self.sweeptable.i[0])

        # Draw all stimuli to the viewport once in advance, fixes another kind of lag on first sweep
        for stim in self.stimuli:
            stim.parameters.on = True # set them all to on
        self.screen.clear()
        self.viewport.draw() # draw to viewport, but don't swap buffers so it won't display
        for stimi, stim in enumerate(self.stimuli):
            stim.parameters.on = onstates[stimi] # restore them all to what they were
        self.screen.clear()
        self.viewport.draw() # draw to viewport with restored onstates

    def sync2vsync(self, nswaps=2):
        """Does nswaps buffer swaps, each followed by a glFlush call
        This ensures that all following swap_buffers+glFlush call pairs
        return on the vsync pulse from the video card. This is a workaround
        for strange OpenGL behaviour. See Sol Simpson's 2007-01-29 post on
        the visionegg mailing list"""
        for swap in range(nswaps):
            ve.Core.swap_buffers() # returns immediately
            gl.glFlush() # if this is the first buffer swap, returns immediately, otherwise waits for next vsync pulse from video card

    def staticscreen(self, nvsyncs, postval=C.MAXPOSTABLEINT):
        """Display whatever's defined in the viewport on-screen for nvsyncs,
        and posts postval to the port. Adds ticks to self.vsynctimer"""
        #assert nvsyncs >= 1 # nah, let it take nvsyncs=0 and do nothing and return right away
        vsynci = 0
        if I.DTBOARDINSTALLED: DT.setBitsNoDelay(SWEEP) # set sweep bit high, no delay. Should this be set? If it isn't, Surf detects that we're in pause mode. Does it collect whatever's on the port when it's in pause mode, ie will it see the 65535s? I doubt it. Probably have to set this high, then set it back low before returning
        if self.pause and nvsyncs == 0:
            nvsyncs = 1 # need at least one vsync to get into the while loop and pause the stimulus indefinitely
        while vsynci < nvsyncs: # need a while loop for pause to work
            for event in pygame.event.get(): # for all events in the event queue
                if event.type == pygame.locals.KEYDOWN:
                    if event.key == pygame.locals.K_ESCAPE:
                        self.quit = True
                    if event.key == pygame.locals.K_PAUSE:
                        self.pause = not self.pause # toggle pause
                        self.paused = True
            if self.quit:
                break # out of vsync loop
            if self.pause: # indicate pause to Surf
                if I.DTBOARDINSTALLED: DT.clearBitsNoDelay(SWEEP) # clear sweep bit low, no delay
            else: # post value to port
                if I.DTBOARDINSTALLED:
                    DT.setBitsNoDelay(SWEEP) # make sure it's high
                    DT.postInt16NoDelay(postval) # post value to port, no delay
                    self.nvsyncsdisplayed += 1 # increment. Count this as a vsync that Surf has seen
            self.screen.clear()
            self.viewport.draw()
            ve.Core.swap_buffers() # returns immediately
            gl.glFlush() # waits for next vsync pulse from video card
            self.vsynctimer.tick()
            vsynci += int(not self.pause) # don't increment if in pause mode
        if I.DTBOARDINSTALLED: DT.clearBits(SWEEP) # be tidy, clear sweep bit low, delay to make sure Surf sees the end of this sweep

    def get_framebuffer(self, i):
        """Get the raw frame buffer data that corresponds to what's
        drawn for sweep table index i
        UNFINISHED!!!!!!!!!!
        TODO: finish this
        """
        self.updateparams()
        self.screen.clear()
        self.viewport.draw()
        data = np.asarray(self.screen.get_framebuffer_as_array()) # VE returns a Numeric array, convert to numpy
        return data

    def run(self):
        """Run the experiment"""

        # Check it first
        self.check()

        info('Running Experiment script: %s' % self.script)

        # Build the SweepTable and the Header
        self.build()

        self.setgamma(self.static.gamma)

        # Init OpenGL graphics screen
        self.screen = ve.Core.get_default_screen()

        # Create VisionEgg stimuli objects, defined by each specific subclass of Experiment
        self.createstimuli()

        # Create a VisionEgg Viewport
        self.viewport = ve.Core.Viewport(screen=self.screen, stimuli=self.stimuli)

        self.initbackgroundcolor()

        self.fix1stsweeplag() # 1st sweep lag hacks

        # Create the VsyncTimer
        self.vsynctimer = Core.VsyncTimer()

        # Init DT board and send the entire stimulus (Surf and NVS and text) header
        if I.DTBOARDINSTALLED: DT.initBoard()
        if I.DTBOARDINSTALLED: self.header.broadcast()

        self.quit = False # init quit signal
        self.pause = False # init pause signal
        self.paused = False # remembers whether this experiment has been paused
        self.nvsyncsdisplayed = 0 # nvsyncs seen by Surf

        # time-critical stuff starts here
        self.sync2vsync(nswaps=2) # sync up to vsync signal, ensures that all following swap_buffers+glFlush call pairs return on the vsync

        self.startdatetime = datetime.datetime.now()
        self.starttime = time.clock() # precision timestamp

        # Do pre-experiment delay
        self.staticscreen(nvsyncs=sec2intvsync(self.static.preexpSec))

        # Run the main stimulus loop, defined by each specific subclass of Experiment
        self.main()

        # Do post-experiment delay
        self.staticscreen(nvsyncs=sec2intvsync(self.static.postexpSec))

        self.stoptime = time.clock() # precision timestamp
        self.stopdatetime = datetime.datetime.now()
        # time-critical stuff ends here

        # Send the Experiment checksum and close the board
        if I.DTBOARDINSTALLED:
            DT.postInt16NoDelay(0) # clear the value on the port, no delay
            self.checksum = DT.getChecksum()
            DT.postInt16NoDelay(self.checksum) # post the value, no delay
            DT.setChecksum(0) # reset DT module's checksum variable
            DT.toggleBits(C.DATA) # toggle data bit to trigger Surf, delay
            DT.clearBitsNoDelay(0x00ffffff) # clear all bits (including run bit) low, no delay
            DT.closeBoard()

        # Close OpenGL graphics screen (necessary when running from Python interpreter)
        self.screen.close()

        # Print messages to VisionEgg log and to screen
        info(self.vsynctimer.pprint())
        info('%d vsyncs displayed, %d sweeps completed' % (self.nvsyncsdisplayed, self.ii))
        info('Experiment duration: %s expected, %s actual' % (isotime(self.sec, 6), isotime(self.stoptime-self.starttime, 6)))
        if self.paused:
            warning('dimstim was paused at some point')
        if self.quit:
            warning('dimstim was interrupted before completion')
        else:
            info('dimstim completed successfully')
        printf2log('\n' + '-'*80 + '\n') # add minuses to end of log to space it out between sessions