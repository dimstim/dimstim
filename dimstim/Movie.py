"""Defines the Movie Experiment"""

from __future__ import division

import struct
import numpy as np
np.seterr(all='raise') # raise all numpy errors (like 1/0), don't just warn
import pygame
import time
import OpenGL.GL as gl
from pprint import pprint

import VisionEgg as ve
import VisionEgg.Core
from VisionEgg.Textures import TextureStimulus, Mask2D, Texture

import Constants as C
from Constants import I
import Core
from Core import sec2intvsync, vsync2sec, degSec2pixVsync, deg2pix, toiter
try:
    from Core import DT # only importable if DT board is installed
except ImportError:
    pass
from Experiment import Experiment


class Movie(Experiment):
    """Movie experiment"""
    def __init__(self, *args, **kwargs):
        super(Movie, self).__init__(*args, **kwargs)
        self.static.fname = self.static.fname.replace('\\', C.SLASH) # replace double backslashes with single forward slash
        if 'fixationspotDeg' not in self.dynamic.keys(): # most Movie scripts won't bother specifying it
            self.dynamic.fixationspotDeg = False # default to off

    def check(self):
        """Check Movie-specific parameters"""
        super(Movie, self).check()

    def build(self):
        """Builds the SweepTable and the Header for this Experiment, and loads movie frames"""
        super(Movie, self).build()
        self.load()
        assert max(toiter(self.dynamic.framei)) <= self.nframes-1, 'Frame indices exceed movie size of %d frames' % self.nframes

    def load(self, asarray=False, flip=True):
        """Load movie frames"""
        self.f = file(self.static.fname, 'rb') # open the movie file for reading in binary format
        headerstring = self.f.read(5)
        if headerstring == 'movie': # a header has been added to the start of the file
            self.ncellswide, = struct.unpack('H', self.f.read(2)) # 'H'== unsigned short int
            self.ncellshigh, = struct.unpack('H', self.f.read(2))
            self.nframes, = struct.unpack('H', self.f.read(2))
            if self.nframes == 0: # this was used in Cat 15 mseq movies to indicate 2**16 frames, shouldn't really worry about this, cuz we're using slightly modified mseq movies now that don't have the extra frame at the end that the Cat 15 movies had (see comment in Experiment module), and therefore never have a need to indicate 2**16 frames
                self.nframes = 2**16
            self.offset = self.f.tell() # header is 11 bytes long
        else: # there's no header at the start of the file, set the file pointer back to the beginning and use these hard coded values:
            self.f.seek(0)
            self.ncellswide = self.ncellshigh = 64
            self.nframes = 6000
            self.offset = self.f.tell() # header is 0 bytes long
        self.framesize = self.ncellshigh*self.ncellswide

        # read in all of the frames
        # maybe check first to see if file is > 1GB, if so, _loadaslist() to prevent trying to allocate one huge piece of contiguous memory and raising a MemoryError, or worse, segfaulting
        if asarray:
            self._loadasarray(flip=flip)
        else:
            self._loadaslist(flip=flip)
        leftover = self.f.read() # check if there are any leftover bytes in the file
        if leftover != '':
            pprint(leftover)
            print self.ncellswide, self.ncellshigh, self.nframes
            raise RuntimeError, 'There are unread bytes in movie file %r. Width, height, or nframes is incorrect in the movie file header.' % self.static.fname
        self.f.close() # close the movie file

    def _loadasarray(self, flip=True):
        self.frames = np.fromfile(self.f, dtype=np.uint8, count=self.nframes*self.framesize)
        self.frames.shape = (self.nframes, self.ncellshigh, self.ncellswide)
        if flip:
            self.frames = self.frames[::, ::-1, ::] # flip all frames vertically for OpenGL's bottom left origin

    def _loadaslist(self, flip=True):
        self.frames = []
        for framei in xrange(self.nframes): # one frame at a time...
            frame = np.fromfile(self.f, dtype=np.uint8, count=self.framesize) # load the next frame
            frame.shape = (self.ncellshigh, self.ncellswide)
            if flip:
                frame = frame[::-1, ::] # flip all frames vertically for OpenGL's bottom left origin
            self.frames.append(frame)
    '''
    def __getitem__(self, framei):
        """Get the desired frame from the movie file, according to its frame index"""
        self.f.seek(self.offset + framei*self.framesize)
        #frame = self.f.read(self.framesize)
        #frame = np.fromstring(frame, dtype=np.uint8, count=self.framesize)
        frame = np.fromfile(self.f, dtype=np.uint8, count=self.framesize)
        frame.shape = (self.ncellshigh, self.ncellswide) # is this a safe thing to do? better to use reshape()?
        return frame[::-1, ::] # return it vertically flipped
    '''
    def createstimuli(self):
        """Creates the VisionEgg stimuli objects for this Experiment subclass"""
        super(Movie, self).createstimuli()

        # Create an instance of the Mask2D class
        if self.static.mask:
            self.nmasksamples = 512  # number of samples in mask, must be power of 2, quality/performance tradeoff
            samplesperpix = self.nmasksamples / deg2pix(min(self.static.widthDeg, self.static.heightDeg))
            radius = deg2pix(self.static.diameterDeg / 2) # in pix
            radiusSamples = samplesperpix * radius # in mask samples
            self.mask2d = Mask2D(function=self.static.mask,
                                 radius_parameter=radiusSamples, # sigma for gaussian, radius for circle, in units of mask samples
                                 num_samples=(self.nmasksamples, self.nmasksamples)) # size of mask texture data (# of texels)
        else:
            self.mask2d = None

        self.texture = Texture(self.frames[self.st.framei[0]]) # init texture to frame of first sweep in sweep table

        self.texturestimulus = TextureStimulus(texture=self.texture,
                                               position=(self.xorig, self.yorig), # init to orig
                                               anchor='center',
                                               # texture is scaled to this size:
                                               size=(deg2pix(self.static.widthDeg), deg2pix(self.static.heightDeg)),
                                               mask=self.mask2d,
                                               max_alpha=1.0,
                                               mipmaps_enabled=False, # ?
                                               texture_min_filter=gl.GL_NEAREST, # ?
                                               texture_mag_filter=gl.GL_NEAREST, # ?
                                               on=False) # leave it off for now

        self.fixationspot = ve.Core.FixationSpot(position=(self.xorig, self.yorig),
                                                 anchor='center',
                                                 color=(255, 0, 0, 0),
                                                 size=(1, 1),
                                                 on=False) # leave it off for now

        self.stimuli = (self.background, self.texturestimulus, self.fixationspot) # last entry will be topmost layer in viewport

        self.tsp = self.texturestimulus.parameters # synonym
        self.to = self.tsp.texture.get_texture_object()
        self.fsp = self.fixationspot.parameters

    def updateparams(self, i):
        """Updates stimulus parameters, given sweep table index i"""
        if i == None: # do a blank sweep
            self.tsp.on = False # turn off the movie, leave all other parameters unchanged
            self.postval = C.MAXPOSTABLEINT # posted to DT port to indicate a blank sweep
            self.nvsyncs = sec2intvsync(self.blanksweeps.sec) # this many vsyncs for this sweep
            self.npostvsyncs = 0 # this many post-sweep vsyncs for this sweep, blank sweeps have no post-sweep delay
        else: # not a blank sweep
            self.tsp.on = True # ensure texture stimulus is on
            self.postval = i # sweep table index will be posted to DT port
            self.nvsyncs = sec2intvsync(self.st.sweepSec[i]) # this many vsyncs for this sweep
            self.npostvsyncs = sec2intvsync(self.st.postsweepSec[i]) # this many post-sweep vsyncs for this sweep

            # Update texture
            frame = self.frames[self.st.framei[i]] # get the frame for this sweep
            #frame = self[self.st.framei[i]] # get the frame for this sweep
            if self.st.invert[i]:
                frame = 255 - frame # give the frame inverted polarity
            self.to.put_sub_image(frame, data_format=gl.GL_LUMINANCE, data_type=gl.GL_UNSIGNED_BYTE)

            # Update texturestimulus
            self.tsp.angle = self.static.orioff + self.st.ori[i]
            self.tsp.position = self.xorig+deg2pix(self.st.xposDeg[i]), self.yorig+deg2pix(self.st.yposDeg[i])

            # Update background parameters
            self.bgp.color = self.st.bgbrightness[i], self.st.bgbrightness[i], self.st.bgbrightness[i], 1.0

            # Update fixationspot
            self.fsp.on = bool(self.st.fixationspotDeg[i])
            self.fsp.size = deg2pix(self.st.fixationspotDeg[i]), deg2pix(self.st.fixationspotDeg[i])

            # hopefully, calcs didn't take much time. If so, then sync up to the next vsync before starting the sweep

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
                if I.DTBOARDINSTALLED: DT.postInt16(self.postval) # post value to port
                self.screen.clear()
                self.viewport.draw()
                ve.Core.swap_buffers() # returns immediately
                gl.glFlush() # waits for next vsync pulse from video card
                self.vsynctimer.tick()
                self.nvsyncsdisplayed += 1 # increment

            # Sweep's done, turn off the texture stimulus, do the postsweep delay, clear sweep bit low
            self.tsp.on = False
            self.staticscreen(nvsyncs=self.npostvsyncs) # clears sweep bit low when done

            if self.quit:
                self.ii = ii + 1 - 1 # dec for accurate count of nsweeps successfully displayed
                break # out of sweep loop

        self.ii = ii + 1 # nsweeps successfully displayed
        self.f.close() # close the movie file
