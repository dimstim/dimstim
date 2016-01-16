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
RUN = 0x00040000 # run bit. Called displayrunning in Surf, needs to be high before Surf listens to any other digital line
REFRESH = 0x00080000 # refresh bit. Called frametoggle in Surf, needs to be toggled to signal new frame-related data on port, only read by Surf if a valid header was sent. Isn't used if the vsync signal from the video card has been wired as the refresh bit instead (in which case Surf looks for an up-down strobe instead of a toggle)

# Maximum postable integer, 65535 for 16 digital lines. These correspond to Ports A and B on
# the DT340 (see DT.c):
MAXPOSTABLEINT = 0x0000ffff

NAN = 0x7fffffff # one of the many possible hex values that code for single float IEEE standard 754 NaN (quiet NaN)

WARNINGDELAY = 1 # mostly deprecated, time in sec to delay execution when a warning is printed to screen


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
I.EYE = dc.get('Eye', 'open') # eye open state
assert I.EYE in EYESTATES
I.check()
