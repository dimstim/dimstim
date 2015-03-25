"""Customized VisionEgg Window, given its own module so that dimstim.Core
need not depend on VisionEgg"""

from __future__ import division

import numpy as np
np.seterr(all='raise') # raise all numpy errors (like 1/0), don't just warn
from ctypes import windll

import VisionEgg.Core


class Window(VisionEgg.Core.Window):
    """VisionEgg Window (based on pyglet window support in VE rev 1413)
    with added ability to set and restore gamma ramps"""
    def __init__(self, *args, **kwargs):
        super(Window, self).__init__(*args, **kwargs)
        # try and get gamma ramps
        self.origramps = np.empty((3, 256), dtype=np.uint16) # init place to save original R, G, and B ramps
        success = windll.gdi32.GetDeviceGammaRamp(self.win._dc, self.origramps.ctypes)
        if not success: raise AssertionError, 'GetDeviceGammaRamp failed'

    def set_gamma_ramps(self, ramps):
        self.ramps = np.asarray(ramps, dtype=np.uint16)
        self.ramps.byteswap(True) # seems CPU and GPU have different endianness?

        # try and set gamma ramps
        success = windll.gdi32.SetDeviceGammaRamp(self.win._dc, self.ramps.ctypes)
        #if not success: raise AssertionError, 'SetDeviceGammaRamp failed' # this usually returns 0, even though it worked, don't know why

    def restore_gamma_ramps(self):
        """Restore to original gamma"""
        # try and set gamma ramps
        success = windll.gdi32.SetDeviceGammaRamp(self.win._dc, self.origramps.ctypes)
        #if not success: raise AssertionError, 'SetDeviceGammaRamp failed' # this usually returns 0, even though it worked, don't know why

