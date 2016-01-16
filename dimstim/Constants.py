"""Constants used by other dimstim modules, plus the dimstimConfigParser for
retrieving global internal parameters from the dimstim config file"""

from __future__ import division

import os
import sys
import re
import math
import cStringIO
import ConfigParser
import logging
import VisionEgg
import dimstim
from Core import dictattr


class DimstimConfigParser(ConfigParser.RawConfigParser):
    """Reads and writes the dimstim config file, adds an update function"""
    def __init__(self, defaults=None, fname=None):
        ConfigParser.RawConfigParser.__init__(self) # old-style class, can't use super(), call unbound constructor
        self.fname = fname
        self.read(self.fname)

    def get_repr(self, section, option):
        """Returns the value as a string rep, per usual"""
        return ConfigParser.RawConfigParser.get(self, section, option)

    def get(self, section, option):
        """Same as ConfigParser.RawConfigParser.get(), but evals the returned string.
        This assumes the option values are valid Python values"""
        return eval(ConfigParser.RawConfigParser.get(self, section, option))

    def set(self, section, option, value):
        """Same as ConfigParser.RawConfigParser.set(), but accepts non-string values,
        and sets the value's string rep. Also, checks for invalid sections and options"""
        if value.__class__ != str:
            value = str(value) # this will prevent floating point inaccuracies from being saved to file
        else:
            value = repr(value)
        if not self.has_section(section):
            raise ConfigParser.NoSectionError(section)
        if not self.has_option(section, option):
            raise ConfigParser.NoOptionError(option, section)
        ConfigParser.RawConfigParser.set(self, section, option, value)

    # Regular expressions for parsing section headers and options.
    SECTCRE = re.compile(r'\[' # match [
                         r'(?P<header>[a-zA-Z0-9_]*)' # match any number of alphanums
                         r'\]' # match ]
                         )
    OPTCRE = re.compile(r'(?P<option>[a-zA-Z0-9_]*)' # match any number of alphanums
                        r'\s*(?P<vi>[=])\s*' # any number of \s, then value indicator =, then any number of \s
                        r'(?P<value>[^#]*)' # any number of anything except #
                        )
    COMMENTCRE = re.compile(r'(?P<stuff>[^#]*)' # any number of anything except #
                            r'(?P<comment>#.*)' # comment is # followed by any number of anything
                            )

    def update(self):
        """Updates the current values to the config file, overwriting just the "option = value"
        parts of lines that fall under their correct section headings, leaving everything else
        (like comments) the way it is. Adapted from VisionEgg.Configuration

        A few config file example lines:

        # Eye open state
        [Eye]
        open = 'left' # eye open state: 'left', 'right', 'both', None

        """
        s = cStringIO.StringIO() # create a string file-like object, implemented in C, fast
        f = file(self.fname, 'r')
        for linei, line in enumerate(f):
            line = line.rstrip(' ') # strip trailing spaces, leave newline intact
            sectionmatch = self.SECTCRE.match(line)
            optionmatch = self.OPTCRE.match(line)
            if sectionmatch:
                section = sectionmatch.group('header').strip() # current section we're in
            elif optionmatch:
                option = optionmatch.group('option').strip()
                value = self.get_repr(section, option) # value is a string rep
                commentmatch = self.COMMENTCRE.match(line) # see if there's a comment on this line
                comment = ''
                if commentmatch:
                    comment = ' %s' % commentmatch.groupdict()['comment'] # get the comment
                line = '%s = %s%s\n' % (option, value, comment)
            s.write(line)

        # Close and reopen file in write mode, do the actual writing
        f.close()
        f = file(self.fname, 'w')
        for line in s.getvalue():
            f.write(line)

    def _read(self, fp, fpname):
        """Parse a sectioned setup file.

        Copied and modified from ConfigParser.RawConfigParser to allow triple double quotes as docstrings in the file

        The sections in setup file contains a title line at the top,
        indicated by a name in square brackets (`[]'), plus key/value
        options lines, indicated by `name: value' format lines.
        Continuations are represented by an embedded newline then
        leading whitespace.  Blank lines, lines beginning with a '#',
        and just about everything else are ignored.
        """
        cursect = None # None, or a dictionary
        optname = None
        lineno = 0
        e = None # None, or an exception
        while True:
            line = fp.readline()
            if not line:
                break
            lineno = lineno + 1
            # comment or blank line?
            #if line.strip() == '' or line[0] in '#;':
            if line.strip() == '' or line[0] == '#' or line[0:3] == '"""': # modified by mspacek
                continue
            if line.split(None, 1)[0].lower() == 'rem' and line[0] in "rR":
                # no leading whitespace
                continue
            # continuation line?
            if line[0].isspace() and cursect is not None and optname:
                value = line.strip()
                if value:
                    cursect[optname] = "%s\n%s" % (cursect[optname], value)
            # a section header or option header?
            else:
                # is it a section header?
                mo = self.SECTCRE.match(line)
                if mo:
                    sectname = mo.group('header')
                    if sectname in self._sections:
                        cursect = self._sections[sectname]
                    elif sectname == ConfigParser.DEFAULTSECT:
                        cursect = self._defaults
                    else:
                        cursect = {'__name__': sectname}
                        self._sections[sectname] = cursect
                    # So sections can't start with a continuation line
                    optname = None
                # no section header in the file?
                elif cursect is None:
                    raise MissingSectionHeaderError(fpname, lineno, line)
                # an option line?
                else:
                    mo = self.OPTCRE.match(line)
                    if mo:
                        optname, vi, optval = mo.group('option', 'vi', 'value')
                        if vi in ('=', ':') and ';' in optval:
                            # ';' is a comment delimiter only if it follows
                            # a spacing character
                            pos = optval.find(';')
                            if pos != -1 and optval[pos-1].isspace():
                                optval = optval[:pos]
                        optval = optval.strip()
                        # allow empty values
                        if optval == '""':
                            optval = ''
                        optname = self.optionxform(optname.rstrip())
                        cursect[optname] = optval
                    else:
                        # a non-fatal parsing error occurred.  set up the
                        # exception but keep going. the exception will be
                        # raised at the end of the file and will contain a
                        # list of all bogus lines
                        if not e:
                            e = ParsingError(fpname)
                        e.append(lineno, repr(line))
        # if any parsing errors occurred, raise an exception
        if e:
            raise e


SLASH = '/' # use forward slashes instead of having to use double backslashes
TAB = '    ' # 4 spaces

CONFIGFNAME = os.path.join(dimstim.__path__[0], 'dimstim.cfg') # dimstim config filename

# Digital output status bits. These are found on Port D on the DataWave panel
DATA = 0x00010000 # data bit. Called datastrobe in Surf, needs to be toggled to signal new header or checksum related data on port
SWEEP = 0x00020000 # sweep bit. Called displaysweep in Surf, positive edge signals new stimulus sweep. When set to low, Surf detects this as a pause
RUN = 0x00040000 # run bit. Called displayrunning in Surf, needs to be high before Surf listens to any other digital line
REFRESH = 0x00080000 # refresh bit. Called frametoggle in Surf, needs to be toggled to signal new frame-related data on port, only read by Surf if a valid header was sent. Isn't used if the vsync signal from the video card has been wired as the refresh bit instead (in which case Surf looks for an up-down strobe instead of a toggle)

# Maximum postable integer, 65535 for 16 digital lines. These correspond to Ports A and B on
# the DT340 (see DT.c):
MAXPOSTABLEINT = 0x0000ffff
#NVSMAXDIMS = 3 # Maximum number of dimensions allowed in NVS header
#NVSMAXVARS = 10 # Maximum total number of variables across all dimensions allowed in NVS header
#NVSMAXVALS = 50 # Maximum number of values allowed per variable in NVS header
#NVSLENGTH = 749 # number of real valued entries in NVS header
#TEXTLENGTH = 50000 # fixed number of characters that have to be posted as the text header, this number has to be a multiple of 2
assert TEXTLENGTH % 2 == 0, 'Fixed text header length agreed upon with Surf has to be a multiple of 2'

LENFNAMEINHEADER = 64

NAN = 0x7fffffff # one of the many possible hex values that code for single float IEEE standard 754 NaN (quiet NaN)

WARNINGDELAY = 1 # mostly deprecated, time in sec to delay execution when a warning is printed to screen
'''
# 0-based indices into NVS header of floats
STT_LENGTH = 0 # table length (749)
STT_POFF = 1 # index to parameter list (4)
STT_VOFF = 2 # index to variable table (100)
GR_SF = 3 # spatial frequency (cyc/deg)
SQ_DUTY = 4 # duty cycle
GR_CON = 5 # contrast (0-1)
GR_ML = 6 # mean luminance (0-1)
STT_BL = 7 # background brightness (0-1)
GR_ORI = 8 # orientation degrees (0 = X-axis)
GR_VEL = 9 # velocity (deg/sec)
GB_PHASEVEL = 10 # phase velocity (Gabor patches)
GR_TF = 11 # temporal frequency (cyc/sec)
GR_PHASE = 12 # phase
STT_ORIGX = 13 # X origin (degrees)
STT_ORIGY = 14 # Y origin (degrees)
RB_HEIGHT_A = 15 # height (degrees) (was previously called rb_width_a)
RB_WIDTH_A = 16 # width (degrees) (was previously called rb_length_a)
SHOULDER = 17 # shoulder, also used as 2nd diameter
DIAMETER = 18 # diameter
RB_OFFSET_HORIZ = 19 # verier offset
RB_OFFSET_VERT = 20 # vernier gap
RB_BRIGHTNESS_A = 21 # bar A brightness
RB_BRIGHTNESS_B = 22 # bar B brightness
RB_NOB = 23 # number of spokes (spiral grating)
STT_DURATION = 24 # sweep duration (seconds) (formerly NVS "presentation time" - ill defined)
STT_STS = 25 # stimulus type: 1 = 'sine wave grating'
                            # 2 = 'square wave grating'
                            # 3 = 'vernier bars'
                            # 4 = 'spiral grating'
                            # 5 = 'gabor patches'
                            # 6 = 'noise grating'
                            # 7 = 'jitter grating'
                            # 8 = 'Snellen letter chart'
                            # 9 = 'Frisen perimetry'
                            # 10 = 'two bars'
                            # 11 = 'reverse correlation'
                            # 12 = 'flashed bar'
                            # 13 = 'm sequence'
                            # 14 = 'bar segments'
                            # 15 = 'image file'
                            # 16 = 'movie file'
STT_TESTING = 26 # testing method (1=const stimuli; 2=adaptive..)
STT_RUNS = 27 # number of times the full set of dimension combinations is run (nrepetitions minus 1) (previously stt_repetitions)
VB_WIDTH = 28 # vernier bar width (minutes)
VB_LENGTH = 29 # vernier bar length (minutes)
STT_MERIDIAN = 30 # meridian (deg, CC angle from 0=X-axis)
STT_ECCENTRICITY = 31 # eccentricity (distance in deg from XY orig)
STT_EYE = 32 # eye (0=both open; 1=LE open; 2=RE open; 3=both closed)
NG_ELEMENT_SIZE = 33 # element size (degrees)
STT_ORIREL = 34 # orientation offset (degrees)
RB_XOFFA = 35 # Bar/grating A - X offset
RB_XOFFB = 36 # Bar/grating B - X offset
RB_YOFFA = 37 # Bar/grating A - Y offset
RB_YOFFB = 38 # Bar/grating B - Y offset
STT_ISI = 39 # interstimulus interval (secs), this is a post-sweep delay (was previously a pre-sweep delay)
SN_VIEWING_DISTANCE = 40 # dist for snellen charts (meters)
SN_MIRROR_INVERT = 41 # mirror invert for Snellen charts (0=no; 1=yes)
FR_FEEDBACK = 42 # feedback (0=no; 1=yes)
FR_BLANK_PERCENTAGE = 43 # blank percentage
RC_FT = 44 # number of video refreshes per sweep (display of one frame) for reverse correlation, m-seq, movies
RC_CW = 45 # cells wide
RC_CH = 46 # cells high
RC_REGION_WIDTH = 47 # movie/mseq/sparse noise/grating region width
RC_REGION_HEIGHT = 48 # movie/mseq/sparse noise/grating region height
FB_LATENCY = 49 # flash latency (sec) (redundant with post-sweep delay STT_ISI?) (was previously in msec, changed for consistent use of sec for time in NVS header)
FB_DURATION = 50 # flash duration (sec) (redundant with sweep duration STT_DURATION?) (was previously in msec, changed for consistent use of sec for time in NVS header)
RB_HEIGHT_B = 51 # bar B height (degrees) (was previously called rb_width_b)
RB_WIDTH_B = 52 # bar B width (degrees) (was previously called rb_length_b)
BS_OFFSET = 53 # bar offset
BS_BAR_WIDTH = 54 # width (degrees)
BS_BAR_LENGTH = 55 # length (degrees)
IF_ELEMENT_SIZE = 56 # image file pixel size
IF_IMAGE_NUMBER = 57 # image number in series
RC_POLARITY = 58 # movie polarity (0=normal pixel values, 1=inverted pixel values); sparse noise randomize stimulus polarity (0=fixed, 1=random)
STT_TOTAL_SWEEPS = 59 # total number of sweeps in entire experiment (new, not in original NVS list)
RB_ANTIALIASE = 60 # bar is antialiased (0=no, 1=yes) (new, not in original NVS list)
STT_BLANKSWEEP = 61 # a blank sweep has been inserted every Tth sweep (NaN=no blank sweeps, 2=every other sweep is blank, 3=every third is blank...) (new, not in original NVS list)
STT_SHUFFLEBLANKSWEEPS = 62 # shuffle the position of the blank sweeps? (0=no, 1=yes) (new, not in original NVS list)
STT_DISCARD = 63 # discard # of presentations
STT_DISPLAY = 64 # display options
STT_DIFFERENCING = 65 # differencing strategy
STT_AVERAGE = 66 # average over repetitions (0=no; 1=yes)
STT_AUTOSAVE = 67 # autosave (0=no; 1=yes)
STT_GET_RESPONSES = 68 # get responses (psychophysics=1; spikes=-1; nothing=0)
TR_RESPONSE_TIMEOUT = 69 # response timeout (secs)
STT_ORDER1 = 70 # dim1 ordering (0=unrandomized; 1=shuffled; 2=random)
STT_ORDER2 = 71 # dim2 ordering
STT_ORDER3 = 72 # dim3 ordering
GR_ORI2 = 73 # 2nd orientation, degrees (0 = X-axis)
MASK = 74 # grating/mseq/movie mask type (0=None, 1='gaussian', 2='circle') (new, not in original NVS list)
GR_CON2 = 75 # 2nd grating contrast (0-1)
STT_SUBJECT_DATA = 76 # ask for subject data
STT_PSYCHO_INPUT = 77 # num of subject data items
STT_INPUT = 78 # input device for psychophysics (keyboard, mouse, DIO)
STT_ASSIGN_A = 79 # A response; assign value
STT_CODE_A = 80 # input code
STT_PORT_A = 81 # port
STT_BIT_A = 82 # bit
STT_ASSIGN_B = 83 # B response; assign value
STT_CODE_B = 84 # input code
STT_PORT_B = 85 # port
STT_BIT_B = 86 # bit
STT_ASSIGN_C = 87 # C response; assign value
STT_CODE_C = 88 # input code
STT_PORT_C = 89 # port
STT_BIT_C = 90 # bit
XI = 91 # x index into grid, grid centered at orig
YI = 92 # y index into grid, grid centered at orig
ANNULUSDIAM = 93 # outer annulus diameter
PREEXPSEC = 94 # pre experiment delay, (sec) (new, not in original NVS list)
POSTEXPSEC = 95 # post experiment delay, (sec) (new, not in original NVS list)
STT_BLANKSWEEPDURATION = 96 # blank sweep duration (sec) (new, not in original NVS list)
STT_RESHUFFLERUNS = 97 # reshuffle/rerandomize each run? (new, not in original NVS list)
# 98 skipped
SIZE_DIM_1 = 99 # size of dimension 1
SIZE_DIM_2 = 100 # size of dimension 2
SIZE_DIM_3 = 101 # size of dimension 3
TOTAL_NUM_VARIABLES = 102 # total number of variables (max=10)
USED_VARIABLES = 103 # number of vars to use in analysis
# 104-108 skipped

"""NVS parameter index mapping. For a given parameter name, returns the corresponding 0-based NVS parameter index. The corresponding NVS parameter code is the index + 1"""
NVSi = {
    'xorigDeg':STT_ORIGX, # X origin (degrees, wrt centre of screen)
    'yorigDeg':STT_ORIGY, # Y origin (degrees, wrt centre of screen)
    'preexpSec':PREEXPSEC, # pre-experiment duration to display blank screen (sec)
    'postexpSec':POSTEXPSEC, # post-experiment duration to display blank screen (sec)
    'orioff':STT_ORIREL, # target/grating orientation offset relative to 0 (deg)
    'mask':MASK, # grating/movie/mseq mask type (0=None, 1='gaussian', 2='circle')
    'diameterDeg':DIAMETER, # grating/movie/mseq mask diameter (deg), ignore if mask is None,
    'diameter2Deg':SHOULDER, # 2nd grating/movie/mseq mask diameter (deg), ignore if mask is None
    'annulusdiameterDeg':ANNULUSDIAM, # grating/movie/mseq mask outer annulus diameter (deg)
    'ori':GR_ORI, # target/grating/movie/sparse noise ori relative to orioff (deg)
    'ori2':GR_ORI2, # 2nd target/grating/movie/sparse noise ori relative to orioff (deg)
    'invert':RC_POLARITY, # movie polarity (0==normal, 1==inverted)
    'speedDegSec':GR_VEL, # target speed (deg/sec)
    'xposDeg':RB_XOFFA, # target/grating x position relative to manbar (deg), ignored if target speedDegSec isn't 0
    'yposDeg':RB_YOFFA, # target/grating y position relative to manbar (deg), ignored if target speedDegSec isn't 0
    'widthDeg':RB_WIDTH_A, # bar/mseq/movie/sparse noise region/grating region width (deg)
    'heightDeg':RB_HEIGHT_A, # bar/mseq/movie/sparse noise region/grating region width (deg)
    'ncellswide':RC_CW, # mseq/movie/sparse noise number of cells wide
    'ncellshigh':RC_CH, # mseq/movie/sparse noise number of cells high
    'xi':XI, # x index into grid, grid centered at orig
    'yi':YI, # y index into grid, grid centered at orig
    'brightness':RB_BRIGHTNESS_A, # target brightness (0-1)
    'antialiase':RB_ANTIALIASE, # antialiase the target? (0=no, 1=yes)
    'bgbrightness':STT_BL, # background brightness (0-1)
    'sweepSec':STT_DURATION, # sweep duration (always converted to sec before posting)
    'sweepMsec':STT_DURATION, # sweep duration (always converted to sec before posting)
    'postsweepSec':STT_ISI, # post-sweep duration to display blank screen (always converted to sec before posting)
    'postsweepMsec':STT_ISI, # post-sweep duration to display blank screen (always converted to sec before posting)
    'tfreqCycSec':GR_TF, # grating temporal frequency (cycles/sec)
    'sfreqCycDeg':GR_SF, # grating spatial frequency (cycles/deg)
    'phase0':GR_PHASE, # grating phase to begin each sweep with (+/- deg)
    'ml':GR_ML, # mean luminance (0-1)
    'contrast':GR_CON, # grating contrast (0-1), if >> 1 get square grating, if < 0 get contrast reversal
    'contrast2':GR_CON2, # 2nd grating contrast (0-1), if >> 1 get square grating, if < 0 get contrast reversal
}
'''

class Printer(object):
    """Print to screen and/or VisionEgg log, with either INFO or WARNING level, or just raw"""
    def __init__(self):
        VisionEgg.start_default_logging()
        self.logger = logging.getLogger('VisionEgg') # this is what VisionEgg calls its logger
    def info(self, msg='', toscreen=True, tolog=True):
        if toscreen:
            print(msg)
        if tolog:
            self.logger.info(msg)
    def warning(self, msg='', toscreen=True, tolog=True):
        if toscreen:
            print('WARNING: %s' % msg)
        if tolog:
            self.logger.warning(msg)
    def printf2log(self, msg=''):
        """Print raw string to log without any log formatting"""
        self.logger.handlers[-1].stream.write(msg) # write directly to log file (FileHandler should be the last one)


printer = Printer()


class InternalParams(dictattr):
    """Stores internal GLOBAL params that aren't user-settable in the scripts.
    They either come from Python, or they're set in the dimstim config file, or they come from VisionEgg.
    Internal global param names are always CAPITALIZED"""
    def check(self):
        """Checks if internal param names are all uppercase"""
        for paramname in self:
            assert paramname.isupper(), 'internal parameter name %s is not CAPITALIZED' % paramname


# Get the global internal params in the dimstim and VisionEgg config files
# Need to worry about what would happen if you modified the config file, but didn't reimport Constants.py - not a big deal, since a new Python process is started for each script, so long as you're not running from within the interpreter!!!
dc = DimstimConfigParser(fname=CONFIGFNAME)
vc = VisionEgg.config
I = InternalParams()
I.DTBOARDINSTALLED = dc.get('DTBoard', 'installed') # boolean
I.SCREENWIDTHCM = float(dc.get('Screen', 'width')) # cm
I.SCREENHEIGHTCM = float(dc.get('Screen', 'height')) # cm
I.SCREENDISTANCECM = float(dc.get('Screen', 'distance')) # cm
I.SCREENWIDTH = vc.VISIONEGG_SCREEN_W # pix
I.SCREENHEIGHT = vc.VISIONEGG_SCREEN_H # pix
I.REFRESHRATE = float(vc.VISIONEGG_MONITOR_REFRESH_HZ) # Hz
I.PIXPERCM = (I.SCREENWIDTH/I.SCREENWIDTHCM + I.SCREENHEIGHT/I.SCREENHEIGHTCM) / 2 # take mean of horizontal and vertical resolution
I.DEGPERCM = 1 / I.SCREENDISTANCECM * 180 / math.pi # not really necessary, but handy during analysis
I.PIXPERDEG = I.PIXPERCM / I.DEGPERCM # not really necessary, but handy during analysis
if not vc.VISIONEGG_GAMMA_INVERT_RED == vc.VISIONEGG_GAMMA_INVERT_GREEN == vc.VISIONEGG_GAMMA_INVERT_BLUE:
    raise ValueError('Gamma correction values for red, green, and blue are not equal')
EYESTATES = ['left', 'right', 'both', None]
NVSEYEDICT = {'both':0, 'left':1, 'right':2, None:3} # translates eye state to int req'd for NVS header
I.EYE = dc.get('Eye', 'open') # eye open state
assert I.EYE in EYESTATES
I.check()
