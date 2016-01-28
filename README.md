[dimstim](http://dimstim.github.io) is a Python package for generating multidimensional visual
stimuli with high temporal precision. It relies heavily on the
[VisionEgg](http://visionegg.org) library.

Much of the behaviour and many of the features are based on "Display", a DOS-based (Fortran)
stimulus program that [Nicholas Swindale](http://swindale.ecc.ubc.ca) developed. Keith Godfrey
wrote the `DT.c` extension for interfacing with Data Translations digital output boards. Tim
Blanche developed the companion acquisition software "Surf", and much of the functionality of
dimstim and its interoperability with Surf came about with his help.

You'll need Python 2.5 to use dimstim. Versions of Python 2.x > 2.5 should also work, but
haven't been tested. dimstim should work on Linux and OSX, but has only been heavily tested in
32-bit Windows XP.

dimstim depends on most or all of the following Python packages:

* [numpy](http://numpy.org)
* [scipy](http://scipy.org)
* [pygame](http://pygame.org)
* [pyglet](http://www.pyglet.org)
* [PyOpenGL](http://pyopengl.sourceforge.net)
* [VisionEgg](http://visionegg.org)

Right now, dimstim requires a specific revision of VisionEgg, rev 1413, in order to run
properly. This is due to a switch to using pyglet for window initialization and positioning.
You can get it at [http://github.com/visionegg/visionegg/tarball/tags/svn/r1413](VisionEgg
rev 1413 here). For a 1280x1024 primary (user) display, the secondary (animal) display should
be positioned in the Windows Display Properties dialog box at the position (1280, 200).
I'm not entirely sure why, but this seems to vertically center the secondary display on the
primary, and has something to do with pyglet. If this isn't set properly, the stimulus seems
to not be properly vertically centered on the secondary display.

If you want to use a Data Translations board for digital output, you'll need to have DT's Open
Layers libraries installed. If you're installing from source and you want to use your DT
board, you'll also need a compiler for Python to use when building the DT.c extension. In the
future, this requirement might disappear if that code is switched to use Python's
[ctypes](https://docs.python.org/2/library/ctypes.html) instead.

The first 16 bits (bits 0--15) on the DT340 board are used to communicate a uint16 sweep
identifier to the acquisition system. The 17th bit (bit 16) is the RECORD bit, which is used
to trigger the acquisition system to start saving data to disk. The vertical synch (vsync)
output of the video port driving the stimulus monitor should be wired separately to the
acquisition system as well, to record the precise timing of each and every refresh of the
screen. The vsynch should be used to time the sampling of the 16 bit digital output word on
the acquisition system.

To install dimstim:
```
$ python setup.py install
```
To simply compile the DT.c extension in place:
```
$ python setup.py build_ext --inplace
```
Adding `--force` will force a recopy/recompile.

To stop the VisionEgg log from rotating every 100 KB, delete the maxBytes=100000 line in
`VisionEgg.__init__.py`.

To greatly reduce the interruption of stimuli in Windows due to Windows events, in the
`sys.platform == 'win32'` section in `VisionEgg.PlatformDependent`, set:
```
win32_maxpriority.set_self_process_priority_class(
win32_maxpriority.REALTIME_PRIORITY_CLASS )
win32_maxpriority.set_self_thread_priority( win32_maxpriority.THREAD_PRIORITY_IDLE )
```
For the ultimate in priority and reliable timing, set:
```
win32_maxpriority.set_self_process_priority_class(
win32_maxpriority.REALTIME_PRIORITY_CLASS )
win32_maxpriority.set_self_thread_priority(
win32_maxpriority.THREAD_PRIORITY_TIME_CRITICAL )
```
However, you may not have keyboard access while stimuli are running. If you want to interrupt,
the only option will be to reset the computer.

Edit `dimstim.cfg` to change global settings, including whether or not a Data Translations
board is installed.

Keyboard controls:
------------------

Hit `ESC` to immediately escape the experiment and any others that are queued to follow it in
a multiexperiment.

In manbar and mangrating:

* mouse positions the manbar, scroll wheel snaps it to oris that are multiples of 18
  degrees, left and right mouse buttons finely tune the ori
* horizontal cursor keys control bar width, vertical cursor keys control bar height
* `NUMPAD5` centers the bar and sets it to ori = 0
* `END` toggles "squarelock" on and off -- this locks the width and the height together
* `ENTER` saves the current position, size, and ori as `Manbar1`, `RSHIFT` saves as
  `Manbar2`
* `1` and `2` recall `Manbar1` and `Manbar2` states, as do `NUMPAD1` and `NUMPAD2`
* `SPACE` swaps the bar and background brightness levels
* `I` changes the current `EYE` state

Terminology:
------------

"frame" refers to a movie or sparse noise frame; "sweep" refers to the display of one
combination of dimensions of a stimulus (either a movie frame, a moving bar, a grating, or a
sparse noise frame) for some number of vsyncs (vertical screen refreshes).
