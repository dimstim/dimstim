"""Core classes and functions used throughout dimstim"""

from __future__ import division

class dictattr(dict):
    """Dictionary with attribute access"""
    def __init__(self, *args, **kwargs):
        super(dictattr, self).__init__(*args, **kwargs)
        for k, v in kwargs.iteritems():
            self.__setitem__(k, v) # call our own __setitem__ so we get keys as attribs even on kwarg init
    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError:
            raise AttributeError, '%r object has no attribute %r' % ('dictattr', key)
    def __setattr__(self, key, val):
        self[key] = val
    def __setitem__(self, key, val):
        super(dictattr, self).__setitem__(key, val)
        if key.__class__ == str and not key[0].isdigit(): # key isn't a number or a string starting with a number
            key = key.replace(' ', '_') # get rid of any spaces
            self.__dict__[key] = val # make the key show up as an attrib upon dir()


import os
import sys
from copy import copy
import time
import datetime
import random
import string
import math
import re
import cStringIO
import winsound

import numpy as np
np.seterr(all='raise') # raise all numpy errors (like 1/0), don't just warn

import Constants as C # keep namespace clean
from Constants import NAN, TAB, I, dc # dc could be required in eval in TextHeader.build()

if I.DTBOARDINSTALLED:
    import DT

printer = C.printer # synonym
info = printer.info
warning = printer.warning
printf2log = printer.printf2log


#class InternalParams(dictattr): defined in Constants.py
#    """Stores internal GLOBAL params that aren't user-settable in the scripts.
#    They either come from Python, or they're set in the dimstim config file, or they come from VisionEgg.
#    Internal global param names are always CAPITALIZED"""


class StaticParams(dictattr):
    """Stores static experiment parameters, attributed by their name.
    Exactly which attributes are stored here depends on the type of experiment"""
    def __init__(self, *args, **kwargs):
        """Common static params for all Experiments. Init for documentation's sake"""
        super(StaticParams, self).__init__(*args, **kwargs)
        # x coordinates of center anchor from screen center (deg)
        self.xorigDeg = None
        # y coordinates of center anchor from screen center (deg)
        self.yorigDeg = None
        # pre-experiment duration to display blank screen (sec)
        self.preexpSec = None
        # post-experiment duration to display blank screen (sec)
        self.postexpSec = None
        # stimulus ori offset (deg)
        self.orioff = None
    def check(self):
        for paramname, paramval in self.items():
            assert not iterable(paramval) or paramval.__class__ in (str, tuple), 'static parameter must be a scalar: %s = %r' % (paramname, paramval) # can't be an iterable object, unless it's a string or a tuple


class DynamicParams(dictattr):
    """Stores potentially dynamic experiment parameters, attributed by their name.
    Exactly which attributes are stored here depends on the type of experiment"""
    pass


class Variable(object):
    """A dynamic experiment parameter that varies over sweeps"""
    def __init__(self, vals, dim=0, shuffle=False, random=False):
        """Bind the dynamic parameter values, its dim, and its shuffle and random flags to this experiment Variable"""
        self.vals = vals
        self.dim = dim
        self.shuffle = shuffle
        self.random = random
    def __iter__(self):
        return iter(self.vals)
    def __len__(self):
        return len(self.vals)
    def check(self):
        """Check that all is well with this Variable, run this after being assigned to Variables object,
        which gives self a .name"""
        assert iterable(self.vals), '%s Variable values must be in a sequence' % self.name
        assert len(self.vals) > 0, '%s Variable values must be in a sequence of non-zero length' % self.name
        for val in self.vals:
            assert val != None, '%s Variable values cannot be left as None' % self.name
        assert not (self.shuffle and self.random), '%s Variable shuffle and random flags cannot both be set' % self.name


class Variables(dictattr):
    """A collection of Variable objects, attributed by their name.
    Exactly which attributes are stored here depends on the Variable objects themselves.
    Each of the Variable objects stored here can have different dims and shuffle and random flags,
    unlike those stored in a Dimension"""
    def __init__(self, *args, **kwargs):
        super(Variables, self).__init__(*args, **kwargs)
    def __setattr__(self, varname, variable):
        """Every attribute assigned to Variables must be a Variable"""
        assert variable.__class__ == Variable
        try:
            variable.name
        except AttributeError:
            variable.name = varname # store the Variable's name in its own .name field
        variable.check()
        super(Variables, self).__setattr__(varname, variable)
    def __iter__(self):
        """Iterates over all Variable objects stored here"""
        return self.itervalues() # inconsistent with dict behaviour


class Dimension(object):
    """An experiment dimension, all of whose Variables co-vary"""
    def __init__(self, variables, dim, shuffle=False, random=False):
        self.variables = variables
        self.dim = dim
        self.shuffle = shuffle
        self.random = random
        self.check()
    def keys(self):
        return self.variables.keys()
    def values(self):
        return self.variables.values()
    def items(self):
        return self.variables.items()
    def __len__(self):
        """Number of conditions in this Dimension"""
        return len(self.variables.values()[0]) # assumes all vars in this dim have the same number of conditions
    '''
    def __getitem__(self, key):
        """Allows dictionary-like access to Variable objects in this Dimension"""
        return self.variables[key]
    '''
    def check(self):
        """Check that all is well with this Dimension"""
        assert self.shuffle * self.random == 0, 'Dimension %d shuffle and random flags cannot both be set' % self.dim
        for var in self.variables:
            assert iterable(var), 'all Variables in Dimension %d must be iterable' % self.dim
            assert len(var) == len(self), 'all Variables in Dimension %d must have the same number of conditions' % self.dim
            assert var.dim == self.dim, 'all Variables in Dimension %d must have the same dimension value' % self.dim
            assert var.shuffle == self.shuffle, 'all variables in Dimension %d must have the same shuffle flag' % self.dim
            assert var.random == self.random, 'all variables in Dimension %d must have the same random flag' % self.dim


class Runs(object):
    """Stores info about experiment runs"""
    def __init__(self, n=1, reshuffle=False):
        self.n = n # number of runs
        self.reshuffle = reshuffle # reshuffle/rerandomize on every run those variables with their shuffle/random flags set?
        self.check()
    def check(self):
        """Check that all is well with these Runs"""
        assert self.n.__class__ == int and self.n > 0, 'number of runs must be a positive integer'


class BlankSweeps(object):
    """Stores info about blank sweeps in an experiment"""
    def __init__(self, T, sec, shuffle=False):
        self.T = T # period (blank sweep every T sweeps)
        self.sec = sec # duration (sec)
        self.shuffle = shuffle
        self.check()
    def check(self):
        """Check that all is well with these BlankSweeps"""
        assert self.T.__class__ == int and self.T >= 2, 'blank sweeps period must be an integer >= 2'


class SweepTable(object):
    """A SweepTable holds all unique combinations of Experiment Variables, as well as indices
    into these combinations, based on shuffle/random flags for each Dimension, the number of runs,
    whether each run is reshuffled, with optional BlankSweeps inserted at the (potentially shuffled)
    intervals requested"""
    def __init__(self, experiment):
        self.experiment = experiment
        self.build()

    def build(self):
        """Build the sweep table.

        A Variable's dim value relative to the dim values of all the other
        Variables determines its order in the nested for loops that generate
        the combinations of values for each sweep: the Variable with the lowest
        dim value becomes the outermost for loop and changes least often;
        the Variable with the highest dim value becomes the innermost for loop
        and changes on every sweep. dim must be an integer. Variables with the
        same dim value are part of the same Dimension, are shuffled/randomized
        together, and must therefore be of the same length and have the same
        shuffle and random flags"""

        e = self.experiment # synonym

        # Build the dimensions
        self.builddimensions()

        # Build the dimension index table
        self.builddimitable()

        # Now use dimitable to build the sweep table
        self.data = dictattr() # holds the actual sweep table, a dict with attribute access
        for dim in self.dimensions:
            for var in dim.variables:
                dimi = self.dimitable[:, dim.dim] # get the entire column of indices into the values of this dimension
                vals = np.asarray(var.vals)[dimi] # convert to array so you can select multiple values with a sequence of indices
                self.data[var.name] = vals # store it as an array

        # Check to make sure that all the variables in self.data have the same number of vals
        try:
            nvals = len(self.data.values()[0])
        except IndexError: # there aren't any variables at all
            nvals = 0
        for varname in self.data:
            assert len(self.data[varname]) == nvals, '%s length in sweep table does not match expected length %d' % (varname, nvals)

        # For convenience in the main stimulus loop, add the non-varying dynamic params to self.data
        nvals = max(nvals, 1) # make sure the sweep table has at least one entry
        for paramname, paramval in e.dynamic.iteritems():
            if paramname not in self.data:
                self.data[paramname] = np.tile(paramval, nvals) # paramval was already checked to be a scalar in Experiment.check()

        # Do the Dimension shuffling/randomizing by generating appropriate sweep table indices
        self.i = self.geti() # get 1 Run's worth of sweep table indices, shuffling/randomizing variables that need it
        if e.runs:
            if e.runs.reshuffle:
                for runi in range(1, e.runs.n):
                    self.i = np.append(self.i, self.geti()) # add another Run's worth of indices, reshuffling/rerandomizing Dimensions that need it
            else:
                self.i = np.tile(self.i, e.runs.n) # create n identical Runs worth of indices

        # Add BlankSweeps to the sweep table indices
        if e.blanksweeps:
            nsweeps = len(self.i)
            insertioni = range(e.blanksweeps.T-1, nsweeps, e.blanksweeps.T-1) # where to insert each blank sweep, not quite right
            for ii, ipoint in enumerate(insertioni):
                insertioni[ii] += ii # fix it by incrementing each insertion point by its position in insertioni to account for all the preceding blank sweeps

            if e.blanksweeps.shuffle:
                samplespace = range(nsweeps + len(insertioni)) # range of possible indices to insert at
                np.random.shuffle(samplespace) # shuffle them in place
                insertioni = samplespace[:len(insertioni)] # pick the fist len(insertioni) entries in samplespace
                insertioni.sort() # make sure we insert in order, don't try inserting at indices that don't exist yet

            i = list(self.i)
            for ipoint in insertioni:
                i.insert(ipoint, None) # do the insertion, None sweep table index value indicates a blank sweep
            self.i = np.asarray(i) # save the results back to self

    def builddimensions(self):
        """Build the Dimension objects from the Experiment Variables"""
        e = self.experiment # synonym

        # find unique dimension values across variables. Dim values could be 0, 5, 5, 5, 2, 666, -74,...
        dims = list(np.unique([ var.dim for var in e.variables ])) # np.unique returns sorted values

        # renumber dimension values to be consecutive 0-based
        newdims = range(len(dims)) # 0-based consecutive dim values
        old2new = dict(zip(dims, newdims)) # maps from old dim values to new ones
        for var in e.variables:
            var.dim = old2new[var.dim] # overwrite each Variable's old dim value with the new one

        # use newdims to init a list of Dimensions, each with an empty Variables object
        self.dimensions = []
        for dim in newdims:
            d = Dimension(variables=Variables(), dim=dim)
            self.dimensions.append(d)

        # now assign each Variable object to the appropriate Dimension object
        for var in e.variables:
            d = self.dimensions[var.dim] # get the Dimension object
            d.variables[var.name] = var # assign the Variable to the Dimension's Variables
            d.shuffle = var.shuffle # set the Dimension's shuffle and random flags according to this Variable
            d.random = var.random
            d.check() # make sure everything is consistent in this Dimension

    def builddimitable(self):
        """Build the dimension index table"""
        # Can't figure out how to use a recursive generator/function to do this, see Apress Beginning Python p192
        # HACK!!: generate and exec the appropriate Python code to build the ordered (unshuffled/unrandomized) dimension index table
        dimi = [None]*len(self.dimensions) # stores the index we're currently on in each dimension
        self.dimitable = [] # ordered dimension index table, these are indices into the values in dimensions, dimensions are in columns, sweeps are in rows
        # generate code with the right number of nested for loops
        code = ''
        tabs = ''
        for dimension in self.dimensions: # generate ndim nested for loops...
            i = str(dimension.dim)
            code += tabs+'for dimi['+i+'] in range(len(self.dimensions['+i+'])):\n'
            tabs += TAB # add a tab to tabs in preparation for the next for loop, or the innermost part of the last one
        code += tabs+'self.dimitable.append(copy(dimi))\n' # innermost part of the nested for loops, copying dimi is important
        exec(code) # run the generated code, this builds the ordered dimitable with all the permutations
        '''
        # example of what the generated code looks like for 3 dimensions:
        for dimi[0] in range(len(self.dimensions[0])):
            for dimi[1] in range(len(self.dimensions[1])):
                for dimi[2] in range(len(self.dimensions[2])):
                    self.dimitable.append(copy(dimi))
        '''
        self.dimitable = np.asarray(self.dimitable)
        self.checkdimitable()

    def checkdimitable(self):
        """Check the length of the dimitable"""
        nsweeps = len(self.dimitable)
        if nsweeps > C.MAXPOSTABLEINT:
            raise ValueError, 'sweep table has %d sweeps, with indices exceeding the maximum index %d that can be sent to acq (index %d is reserved to signify a blank sweep). Reduce the number of dimensions or conditions' % (nsweeps, C.MAXPOSTABLEINT-1, C.MAXPOSTABLEINT)

    def geti(self):
        """Return one Run's worth of sweep table indices, in a numpy array.
        Takes into account the state of each Dimension's shuffle and random flags"""
        i = np.arange(len(self.dimitable)) # set of indices into the sweep table, stores in what order and the # of times and we'll be stepping through the sweeptable during the experiment

        # check if all dims are set to be shuffled/randomized, if so, do it the fast way
        if np.all([ dim.shuffle for dim in self.dimensions ]): # all dimensions are set to be shuffled
            i = shuffle(i) # shuffle all of the indices at once
        elif np.all([ dim.random for dim in self.dimensions ]): # all dimensions are set to be randomized
            i = randomize(i) # randomize all of the indices at once
        else: # shuffle/randomize each dim individually (slower)
            for dim in self.dimensions:
                if dim.shuffle or dim.random: # if flag is set to shuffle or randomize
                    dimi = self.dimitable[:, dim.dim] # get the entire column of indices into the values of this dimension
                    sortis = np.argsort(dimi, kind='mergesort') # indices into dimi that would give you dimi sorted. mergesort is a stable sort, which is an absolute necessity in this case!
                    sortedi = i[sortis] # sweep table indices sorted in order of dimi
                    offset = np.prod([ len(d) for d in self.dimensions if d != dim ]) # offset is the product of the lengths of all the dimensions other than this one
                    if len(i) % len(dim) != 0: # check before doing int division
                        raise ValueError, 'Somehow, number of sweeps is not an integer multiple of length of dim %d' % dim.dim
                    nsegments = len(i) // len(dim) # number of segments of the sweep table indices within which this dimension's values vary consecutively?? - i guess it's possible that some segments will butt up against each other, making effectively longer consecutively-varying segments - long dimensions will be split into many segments, short dimensions into few
                    # maybe np.split() would be useful here??
                    for segmenti in range(nsegments):
                        # j is a collection of indices to shuffle over, made up of every offset'th index, starting from segmenti
                        j = np.asarray([ j for j in range(segmenti, offset*len(dim), offset) ])
                        if dim.shuffle:
                            newj = shuffle(j)
                        elif dim.random:
                            newj = randomize(j)
                        i[sortis[j]] = sortedi[newj] # update sweep table indices appropriately, this is the trickiest bit
        return i

    def pprint(self, i=None):
        """Print out the sweep table at sweep table indices i,
        formatted as an actual table instead of just a dict.
        Only Variables are included (non-varying dynamic params are left out).
        If i is left as None, prints the basic sorted sweep table"""
        print self._pprint(i)

    def _pprint(self, i=None):
        """Return a string representation of the sweep table at sweep table indices i,
        formatted as an actual table instead of just a dict.
        Only Variables are included (non-varying dynamic params are left out).
        If i is left as None, prints the basic sorted sweep table"""
        f = cStringIO.StringIO() # create a string file-like object, implemented in C, fast
        f.write('i\t') # sweep table index label
        for dim in self.dimensions:
            for var in dim.variables:
                f.write('%s\t' % var.name) # column label
        if i == None:
            # sweep table will always have at least one value per dynamic parameter, see self.build()
            i = range(len(self.data.values()[0])) # default to printing one Run's worth of the table in sorted order
        for ival in i:
            f.write('\n')
            f.write('%s\t' % ival) # sweep table index
            for dim in self.dimensions:
                for var in dim.variables:
                    if ival == None: # blank sweep
                        f.write('%s\t' % None)
                    else:
                        f.write('%s\t' % self.data[var.name][ival]) # variable value at sweep table index
        return f.getvalue()


class Header(object):
    """Container for the text header. Formerly also held Surf and NVS headers"""
    def __init__(self, experiment):
        """Init the text header"""
        self.experiment = experiment
        self.text = TextHeader(experiment=experiment)


class TextHeader(object):
    """Text header"""
    def __init__(self, experiment):
        self.experiment = experiment
        self.data = '' # holds the actual string to save as the text header
        self.build()
        #self.check()

    def build(self):
        """Build the text header, mostly from the text of the script"""
        e = self.experiment # synonym
        sf = cStringIO.StringIO() # create a string file-like object, implemented in C, fast

        # add all the internal params
        import dimstim
        sf.write('# Generated by dimstim on %s\n' % datetime.datetime.now()) # str converts datetime obj to string
        sf.write('__version__ = %r\n' % dimstim.__version__)
        sf.write('from dimstim.Constants import InternalParams\n') # import InternalParams into the text header's namespace
        sf.write('import datetime\n') # import datetime into text header's namespace
        sf.write('I = InternalParams()\n') # init an InternalParams object
        sf.write('I.DATETIME = %r\n' % datetime.datetime.now()) # repr leaves it as a datetime object
        namevals = I.items()
        namevals.sort() # sorts in place according to param name
        for paramname, paramval in namevals:
            sf.write('I.%s = %r\n' % (paramname, paramval))
        sf.write('\n')

        # add the script contents, replacing any lines with dc.get with the actual value, use re to match paramname = dc.get
        f = file(e.script, 'r') # script that defined the experiment
        params = dictattr()
        params.update(e.static) # add the static parameters to params
        params.update(e.dynamic) # add the dynamic parameters to params
        # re for finding the StaticParams instance name
        SPIRE = re.compile(r'(?P<objname>[^\s]*)' # match any number of anything except space
                           r'\s*=\s*' # match any number of spaces, followed by a = and then any number of spaces
                           r'StaticParams' # match 'StaticParams' class name
                           )
        # re for finding the DynamicParams instance name
        DPIRE = re.compile(r'(?P<objname>[^\s]*)' # match any number of anything except space
                           r'\s*=\s*' # match any number of spaces, followed by a = and then any number of spaces
                           r'DynamicParams' # match 'DynamicParams' class name
                           )
        # re for finding the Variables instance name
        VSIRE = re.compile(r'(?P<objname>[^\s]*)' # match any number of anything except space
                           r'\s*=\s*' # match any number of spaces, followed by a = and then any number of spaces
                           r'Variables' # match 'Variables' class name
                           )
        # create a regular expression to parse each line, looks for something like 's.preexpSec = 1'
        # would be more correct (more complicated?) to use tokenize.generate_tokens(f) instead or re's??
        PARAMRE = re.compile(r'(?P<objname>[^#.\s]*)' # match any number of anything except # and . and space
                             r'\.' # match the .
                             r'(?P<paramname>[^=\s]*)' # match any number of anything except = and space
                             r'\s*=\s*' # match any number of spaces, followed by a = and then any number of spaces
                             r'(?P<paramval>.*)' # match any number of anything
                             )
        # looks for something like '[1, 2, 3] # blah blah blah'
        COMMENTRE = re.compile(r'(?P<paramval>[^#]*)' # any number of anything except #
                               r'(?P<comment>#.*)' # comment is # followed by any number of anything
                               )
        spobjname = None # static param object name
        dpobjname = None # dynamic param object name
        vsobjname = None # Variables object name
        for linei, line in enumerate(f): # process it one line at a time, check for exceptional things that need to be replaced
            line = line.rstrip(' ') # strip trailing spaces, leave newline intact
            spinstancematch = SPIRE.match(line) # returns a match object if there's a match
            if spinstancematch:
                spobjname = spinstancematch.groupdict()['objname']
                #exec(spobjname + ' = e.static') # e.g., set s = e.static, dangerous, but could be useful in an eval below
            dpinstancematch = DPIRE.match(line)
            if dpinstancematch:
                dpobjname = dpinstancematch.groupdict()['objname']
                #exec(dpobjname + ' = e.dynamic') # e.g., set d = e.dynamic, dangerous, but could be useful in an eval below
            vsinstancematch = VSIRE.match(line)
            if vsinstancematch:
                vsobjname = vsinstancematch.groupdict()['objname']
            parammatch = PARAMRE.match(line)
            if parammatch:
                objname = parammatch.groupdict()['objname']
                paramname = parammatch.groupdict()['paramname']
                paramval = parammatch.groupdict()['paramval'].rstrip(' ')
                comment = ''
                commentmatch = COMMENTRE.match(paramval) # see if the RHS of the = has a comment
                if commentmatch:
                    paramval = commentmatch.groupdict()['paramval'].rstrip(' ') # get paramval part of RHS of =
                    comment = ' %s' % commentmatch.groupdict()['comment'] # get comment part of RHS of =
                if objname in (spobjname, dpobjname): # if we're on a line that sets a static or dynamic param
                    evalactualparamval = params[paramname]
                    actualparamval = repr(evalactualparamval) # get repr of actual param val we're using in the Experiment
                    if paramval != actualparamval: # if repr(val) in the script != repr(actual val) used in the Experiment
                        try:
                            evalparamval = eval(paramval)
                        except NameError: # script uses some unknown module?
                            evalparamval = None
                        # if val wasn't gotten from dimstim config and they eval to the same thing
                        if '.get(' not in paramval and np.asarray(evalparamval == evalactualparamval).all():
                            pass # don't replace paramval. Prevents from expanding say range(6000) into a massive string
                        else: # replace the paramval with the actualparamval by generating a complete line replacement
                            replacement = '%s.%s = %s%s\n' % (objname, paramname, actualparamval, comment)
                            self.printreplacementmsg(linei, line, replacement)
                            line = replacement
                elif objname == vsobjname: # if we're on a line that assigns a Variable to the Variables instance
                    # expect something like: 'vs.ori = Variable(vals=d.ori, ...'
                    if '.'+paramname not in paramval: # say we've got something like: 'vs.ori = Variable(vals=d.speedDegSec, ...'
                        raise ValueError, 'Variable name %s in Variables instance %s not found on RHS of line %d:\n' \
                                          '%r\n' \
                                          'Make sure you\'ve assigned the correct values to %s.%s' \
                                           % (paramname, objname, linei+1, line.rstrip('\n'), objname, paramname)
            if '__file__' in line:
                replacement = line.replace('__file__', repr(e.script)) # replace __file__ with its value in the script file name
                self.printreplacementmsg(linei, line, replacement)
                line = replacement
            if '.run(' in line:
                replacement = '#%s # commented out by dimstim\n' % line.rstrip() # comment out the line that runs the experiment
                self.printreplacementmsg(linei, line, replacement)
                line = replacement
            sf.write(line)

        self.data = sf.getvalue()

    def printreplacementmsg(self, linei, line, replacement):
        """Print a line replacement message. linei should be 0-based"""
        info('TextHeader: replacing script line %d:\n' \
             '%r with:\n' \
             '%r' % (linei+1, line.rstrip('\n'), replacement.rstrip('\n')))

    def __str__(self):
        """Return text header with trailing padding stripped"""
        return self.data.rstrip(' ')

    def pprint(self):
        """Print text header with trailing padding stripped"""
        print self.data.rstrip(' ')


class VsyncTimer(object):
    """Times vsyncs, stolen, modified, clarified from VisionEgg.Core.Frametimer.
    self.pprint() is visually more compact than log_histogram.
    Return the histogram as a string, don't write to screen or log"""
    def __init__(self, leftbin=1, rightbin=22, binwidth=1, runavglen=0,
                 dropthresh=1/I.REFRESHRATE*1.2):
        self.bins = np.arange(leftbin, rightbin, binwidth)
        self.binwidth = float(binwidth)
        self.hist = [0]*len(self.bins) # timing histogram
        self.last = None # last vsync time
        self.maxIVI = None # biggest inter vsync interval (seconds)
        self.first = None # first vsync time
        self.runavglen = runavglen
        if self.runavglen:
            self.stack = [None]*self.runavglen
        self.minIVI = np.inf # smallest inter vsync interval (seconds)
        self.drops = [] # list of (index, time, interval) tuples of dropped vsyncs
        self.dropthresh = dropthresh
        self.n = 0 # vsync count

    def tick(self):
        """Declare a vsync has just been drawn"""
        now = time.clock()
        self.n += 1
        if self.last != None:
            IVI = now - self.last # most recent inter vsync interval
            if IVI > self.dropthresh: # vsync has been dropped
                # use count - 1 to get 0-based index of vsync that was dropped"
                self.drops.append((self.n-1, now, IVI))
                # Generate system beep. cross-platform method is print '\a' # , but that's a
                # long beep that creates lag:
                winsound.Beep(4000, 1)
            index = int(math.ceil(IVI*1000/self.binwidth)) - 1
            if index > (len(self.hist)-1):
                index = -1
            self.hist[index] += 1
            self.minIVI = min(self.minIVI, IVI)
            self.maxIVI = max(self.maxIVI, IVI)
            if self.runavglen:
                self.stack.append(now)
                self.stack.pop(0)
        else:
            self.first = now
        self.last = now # set for next vsync

    def avgIVI(self):
        """Get average IVI"""
        if self.last == None:
            raise RuntimeError("No vsyncs were drawn, cannot calculate average IVI")
        return (self.last - self.first) / sum(self.hist)

    def runavgIVI(self):
        """Get running average IVI"""
        IVIs = []
        for IVI in self.stack:
            if IVI is not None:
                IVIs.append(IVI)
        if len(IVIs) >= 2:
            return (IVIs[-1] - IVIs[0]) / len(IVIs)

    def pprint(self):
        """Return timing histogram"""
        maxnhistlines = 10
        s = cStringIO.StringIO()
        nticks = sum(self.hist) + 1
        if nticks < 2:
            s.write('%d ticks recorded\n' % nticks)
            return
        avgIVI = self.avgIVI()
        s.write('%d ticks recorded, %.3f tps, (min, mean, max) deltatick: '
                '(%.2f, %.2f, %.2f) ms\n'
                 % (nticks, 1/avgIVI, self.minIVI*1000, avgIVI*1000, self.maxIVI*1000))
        hist = self.hist # shorthand
        maxhist = float(max(hist))
        if maxhist == 0:
            s.write('No ticks recorded\n')
            return
        nlines = min(maxnhistlines, int(math.ceil(maxhist)))
        hist = np.asarray(hist) / maxhist*nlines # normalize to number of lines
        for linei in range(nlines): # the actual histogram with labels and *s
            val = float(nlines) - 1.0 - float(linei)
            ts = '%10d' % round(maxhist*val/nlines) # timing string
            q = np.greater(hist, val)
            for qi in q:
                dot = ' '
                if qi:
                    dot = '*'
                ts += '%4s' % dot
            s.write('%s\n' % ts)
        ts = '      IVI:'
        ts += ' %d' % 0
        for bin in self.bins[:-1]:
            ts += '%4d' % bin
        ts += ' +(msec)\n'
        ts += '   Counts:  '
        for val in self.hist:
            if val <= 999:
                cs = str(val).center(4) # IVI count string
            else:
                cs = '+++ ' # count is too big to fit under the bin, print this instead
            ts += cs
        s.write(ts)
        if self.drops:
            s.write('\nDropped vsyncs (IVI > %.2fms):' % (self.dropthresh*1000) + \
                    '\nvsynci, t (s), IVI (ms)')
            for vsynci, t, IVI in self.drops:
                s.write('\n%d, %.6f, %.2f' % (vsynci, t, IVI*1000))
        return s.getvalue()


def intround(n):
    """Round to the nearest integer, return an integer"""
    return int(round(n))

def deg2pix(deg):
    """Convert from degrees of visual space to pixels"""
    # shouldn't I be using opp = 2.0 * distance * tan(deg/2), ie trig instead of solid angle
    # of a circle ???!!
    if deg == None:
        deg = 0 # convert to an int
    rad = deg * math.pi / 180 # float, angle in radians
    s = I.SCREENDISTANCECM * rad # arc length in cm
    return s * I.PIXPERCM # float, arc length in pixels

def deg2truepix(deg):
    return 2.0 * I.SCREENDISTANCECM * I.PIXPERCM * math.tan(deg*math.pi/90)

def pix2deg(pix):
    """Convert from pixels to degrees of visual space"""
    # shouldn't we be using arctan?????!!!!!!!
    if pix == None:
        pix = 0 # convert to an int
    s = pix / I.PIXPERCM # arc length in cm
    rad = s / I.SCREENDISTANCECM # angle in radians
    return rad * 180 / math.pi # float, angle in degrees
'''
def quantizeSpace(npix, ncells):
    """Dec or inc (whichever's closer) npix to make multiple of ncells"""
    if ncells.__class__ != int:
        raise ValueError, 'ncells must be an int, not %s' % ncells.__class__
    if npix.__class__ != int:
        npix = intround(npix) # round to nearest int
    if (npix / ncells - npix // ncells) < 0.5:
        npix = npix - npix % ncells # decrement npix
    else:
        npix = npix + (ncells - (npix % ncells)) # increment npix
    if npix < ncells: # make sure that each cell gets at least 1 pixel
        npix = ncells
    return npix # int
'''
def sec2vsync(sec):
    """Convert from sec to number of vsyncs"""
    return sec * I.REFRESHRATE # float

def msec2vsync(msec):
    """Convert from msec to number of vsyncs"""
    return sec2vsync(msec / 1000) # float

def sec2intvsync(sec):
    """Convert from sec to an integer number of vsyncs"""
    vsync = intround(sec2vsync(sec))
    # prevent rounding down to 0 vsyncs. This way, even the shortest time interval in sec
    # will get you at least 1 vsync
    if vsync == 0 and sec != 0:
        vsync = 1
    return vsync # int

def msec2intvsync(msec):
    """Convert from msec to an integer number of vsyncs"""
    vsync = intround(msec2vsync(msec))
    # prevent rounding down to 0 vsyncs. This way, even the shortest time interval in msec
    # will get you at least 1 vsync
    if vsync == 0 and msec != 0:
        vsync = 1
    return vsync # int

def vsync2sec(vsync):
    """Convert from number of vsyncs to sec"""
    return vsync / I.REFRESHRATE # float

def vsync2msec(vsync):
    """Convert from number of vsyncs to msec"""
    return vsync2sec(vsync) * 1000.0 # float

def degSec2pixVsync(degSec):
    """Convert speed from degress of visual space per sec to pixels per vsync"""
    try:
        pixSec = deg2pix(degSec)
        secPix = 1 / pixSec
        vsyncPix = sec2vsync(secPix) # float
        return 1 / vsyncPix # float
    except (ZeroDivisionError, FloatingPointError):
        return 0.0 # float

def cycSec2cycVsync(cycSec):
    """Convert temporal frequency from cycles per sec to cycles per vsync"""
    try:
        secCyc = 1 / cycSec
        vsyncCyc = sec2vsync(secCyc) # float
        return 1 / vsyncCyc # float
    except (ZeroDivisionError, FloatingPointError):
        return 0.0 # float

def cycDeg2cycPix(cycDeg):
    """Convert spatial frequency from cycles per degree of visual space to cycles per pixel"""
    try:
        degCyc = 1 / cycDeg
        pixCyc = deg2pix(degCyc) # float
        return 1 / pixCyc # float
    except (ZeroDivisionError, FloatingPointError):
        return 0.0 # float

def isotime(sec, ndec=6):
    """Convert from sec to ISO HH:MM:SS[.mmmmmm] format, rounds to ndec number of decimal
    digits"""
    h = int(sec / 3600)
    m = int(sec % 3600 / 60)
    s = int(sec % 3600 % 60)
    dec = intround(sec % 3600 % 60 % 1 * 10**ndec)
    formatcode = '%d:%02d:%02d.%0'+str(ndec)+'d'
    return formatcode % (h, m, s, dec)

def roundec(n, ndec=3):
    """Try to round n to ndec decimal places (less if that would require trailing zeros).
    Due to floating point error, you may get a ridiculous number of decimal digits.
    Convert result to a string to get around this"""
    n *= 10**ndec
    n = round(n)
    n /= 10**ndec
    return n

def iterable(x):
    """Check if the input is iterable, stolen from numpy.iterable()"""
    try:
        iter(x)
        return True
    except:
        return False

def toiter(x):
    """Convert to iterable. If input is iterable, return it. Otherwise return it in a list.
    Useful when you want to iterate over an object (like in a for loop),
    and you don't want to have to do type checking or handle exceptions
    when the object isn't a sequence"""
    if iterable(x):
        return x
    else:
        return [x]
'''
def unique(seq):
    import sets
    """Take list with possibly repeated values, return sorted list with only unique values"""
    uniquelist = list(sets.Set(seq))
    uniquelist.sort()
    return uniquelist

def unique(seq):
    """Return unique items from a 1-dimensional sequence. Stolen from numpy.unique().
    Dictionary setting is quite fast"""
    result = {}
    for item in seq:
        result[item] = None
    return result.keys()

# use something from numpy instead, at least numpy's random module?????????????????????????????????????????????
def gaussian(mu, sigma, n):
    """Return a guassian distributed list of n floats with average mu and standard deviation sigma"""
    return [ random.gauss(mu, sigma) for i in range(n) ]

# use something from numpy instead? np.random.power()?????????????????????????????????????????????
def powerdistrib(power, n):
    """Return a power law distribution (???????????) list of n floats"""
    return [ math.pow(random.random(), power) for i in range(n) ]

def shuffle(seq):
    """Take a sequence and returns a shuffled (without replacement) copy, its only benefit
    over and above random.sample() is that you don't have to pass a second argument len(seq)
    every time you use it"""
    return random.sample(seq, len(seq))
'''
def shuffle(seq):
    """Take a sequence and return a shuffled (without replacement) copy. Its only benefit over
    np.random.shuffle is that it returns a copy instead of shuffling in-place"""
    result = copy(seq)
    np.random.shuffle(result) # shuffles in-place, doesn't convert to an array
    return result
'''
def randomize(seq):
    """Take an input sequence and return a randomized (with replacement) output sequence
    of the same length, sampled from the input sequence"""
    result = []
    for i in range(len(seq)):
        result.append(random.choice(seq))
    return result
'''
def randomize(seq):
    """Return a randomized (with replacement) output sequence sampled from
    (and of the same length as) the input sequence"""
    n = len(seq)
    i = np.random.randint(n, size=n) # returns random ints from 0 to len(seq)-1
    if seq.__class__ == np.ndarray:
        return np.asarray(seq)[i] # use i as random indices into seq, return as an array
    else:
        return list(np.asarray(seq)[i]) # return as a list

def cartdist(a, b):
    """Cartesian distance between a = (x1, y1, z1,...) and b = (x2, y2, z2, ...)"""
    a = np.asarray(a)
    b = np.asarray(b)
    return np.sqrt(np.sum(np.square(b - a)))

def microsaccades(driftstd=0.05, thresh=0.25, shape=(2, 300)):
    """Return ndarray of stimulus positions (in degrees) simulating microsaccades,
    ie slow random drift followed by an instantaneous correction back to the origin.
    shape is (ndim, nt). Typically, ndim = 2 (x and y positions)"""
    assert len(shape) == 2
    ndims = shape[0]
    nt = shape[1]
    deltas = np.empty(shape)
    for dim in range(ndims): # init random drift signals in each dimension
        deltas[dim] = np.random.normal(0, driftstd, nt)
    pos = np.zeros(shape)
    for ti in xrange(1, nt):
        for dim in range(ndims):
            # add drift noise to previous position:
            pos[dim, ti] = pos[dim, ti-1] + deltas[dim][ti]
            if cartdist(pos[dim, ti], [0]*ndims) > thresh:
                # we've drifted past thresh distance from origin
                #print ti, cartdist(pos[dim, ti], [0]*ndims)
                pos[:, ti] = 0 # reset position of all dimensions
                break # out of dim loop
    return pos
