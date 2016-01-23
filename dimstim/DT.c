/*-----------------------------------------------------------------------

FILENAME: DT.c

AUTHORS: Keith Godfrey, Martin Spacek

PURPOSE:
    Open Layers data acquisition C extension interface to Python.
    Enables single value DOUT operation used by dimstim. Only tested on the DT340 board.
    See Data Translations' file SVDIN.C as a close example (input instead of output)

FUNCTIONS:
    Lots of 'em.
    To get a list of functions, after successfully building DT,
    type the following in python:
    >> import dimstim.DT as DT
    >> dir(DT)

****************************************************************************/


#include <Python.h> // Standard ansi C <stdlib.h> and <stdio.h> included by <Python.h>
#include <windows.h> // MS Windows and Microsoft specific includes
#include <olmem.h>
#include <olerrors.h>
#include <oldaapi.h>

// OLDA = Open Layers Data Acquistion

/* function prototypes, constants and globals - should be in "DT.h" */

#define RETURN_ERR(x)  { PyObject *rv; rv = Py_BuildValue("i", x); Py_INCREF(rv); return rv; }

static long     s_checksum = 0;
static long     s_toggleMask = 0; // bits to toggle on each post() call
//static long     s_snoozetime = 10000; // this amounts to as little as 100us on a K7-700
//static long     s_snoozetime = 15000; // this amounts to ~60us on a P4 1.8GHz
static long     s_snoozetime = 110000; // this amounts to ~50us on a Core2 Duo 2.4GHz
static long     s_val = 0; // global var that monitors the current 32 bit value on the port
// number of bits to shift everything up by before posting to the board,
// formerly used due to wiring eccentricities of Datawave panel:
static long     s_bitShiftSize = 0;

/* hardware interface */

PyObject * DT_initBoard(PyObject *self);
PyObject * DT_closeBoard(PyObject *self);
PyObject * DT_postInt16Wait(PyObject *self, PyObject *args);
PyObject * DT_postInt16(PyObject *self, PyObject *args);
PyObject * DT_postInt32Wait(PyObject *self, PyObject *args);
PyObject * DT_postInt32(PyObject *self, PyObject *args);
PyObject * DT_postInt32_2x16(PyObject *self, PyObject *args);
PyObject * DT_postFloat(PyObject *self, PyObject *args);
PyObject * DT_postString(PyObject *self, PyObject *args);

PyObject * DT_getChecksum(PyObject *self);
PyObject * DT_setChecksum(PyObject *self, PyObject *args);

// toggle specified bits on subsequent posts, pass it 0 to stop toggling on subsequent posts:
PyObject * DT_toggleBitsOnPost(PyObject *self, PyObject *args);
// set specified bits, followed by a delay:
PyObject * DT_setBitsWait(PyObject *self, PyObject *args);
// set specified bits:
PyObject * DT_setBits(PyObject *self, PyObject *args);
// clear specified bits, followed by a delay:
PyObject * DT_clearBitsWait(PyObject *self, PyObject *args);
// clear specified bits:
PyObject * DT_clearBits(PyObject *self, PyObject *args);
// toggle specified bits, followed by a delay:
PyObject * DT_toggleBitsWait(PyObject *self, PyObject *args);
// toggle specified bits:
PyObject * DT_toggleBits(PyObject *self, PyObject *args);

#define STRLEN 80 /* string size for general text manipulation */

typedef struct tag_board {
    HDEV hdrvr;         /* device handle, using type HDRVD gave type warnings */
    HDASS hdass;        /* sub system handle */
    ECODE status;       /* board error status */
    HBUF  hbuf;         /* sub system buffer handle */
    PWORD lpbuf;        /* buffer pointer */
    char name[MAX_BOARD_NAME_LENGTH];  /* string for board name */
    char entry[MAX_BOARD_NAME_LENGTH]; /* string for board name */
} BOARD;

typedef BOARD FAR* LPBOARD;
BOARD board;
HDASS hDout; // data acq subsystem handle

void snooze(); // wait for s_snoozetime number of for loops
void post(long); // post specified value to port, update s_val
void incChecksum(long); // increment checksum by specified value
void PrintSubSystems(); // print quantity of channels available for each subsystem

/* Function used in initializing DT-3010 driver olDAEnumBoards */

BOOL __export FAR PASCAL GetDriver(LPSTR  lpszName, LPSTR  lpszEntry, LPARAM lParam);


/* Local functions, not visible in Python */

// pause for s_snoozetime number of loops, this ensures that acquisition has enough time
// to catch the value on the port, before it possibly changes (currently, acquisition runs
// at 25KHz sampling -> 40us sample interval)
void snooze()
{
    int i;
    int count = 0;
    for (i=0; i<s_snoozetime; i++)
        count++;
}

// Post a value to port, taking into account the toggle mask and the bitshift size
void post(long val)
{
    int ecode;
    if (s_toggleMask != 0) // if we're set to toggle bits on every post..
    {
        val = val ^ s_toggleMask; // ...then do so
        //printf("s_toggleMask is %d\n", s_toggleMask);
    }
    s_val = val; // update s_val
    val <<= s_bitShiftSize; // shift bits up by s_bitShiftSize
    // write to port, check for errors:
    if ((ecode=olDaPutSingleValue(hDout, val, 0, 1)) != OLNOERROR)
    {
        // comment out to reduce printing to screen when board not installed:
        //printf("Error writing to port (%d)\n", ecode);
    }
    //printf("%ld\n", val);
}

void incChecksum(long val)
{
    s_checksum += val; // increment checksum
    s_checksum &= 0x0000ffff; // keep the checksum as a 16 bit int with overflow
    // printf("val = %d  checksum = %d\n", val,s_checksum);
}

void PrintSubSystems()
{
    int val;

    printf("Number of subsystems on this board:\n");
    olDaGetDevCaps(board.hdrvr, OLDC_ADELEMENTS, &val);
    printf("AD: %d\n", val);
    olDaGetDevCaps(board.hdrvr, OLDC_DAELEMENTS, &val);
    printf("DA: %d\n", val);
    olDaGetDevCaps(board.hdrvr, OLDC_DINELEMENTS, &val);
    printf("DIN:    %d\n", val);
    olDaGetDevCaps(board.hdrvr, OLDC_DOUTELEMENTS, &val);
    printf("DOUT:   %d\n", val);
    olDaGetDevCaps(board.hdrvr, OLDC_CTELEMENTS, &val);
    printf("Timer:  %d\n", val);
    olDaGetDevCaps(board.hdrvr, OLDC_SRLELEMENTS, &val);
    printf("Serial: %d\n", val);
    olDaGetDevCaps(board.hdrvr, OLDC_TOTALELEMENTS, &val);
    printf("Total:  %d\n", val);
}

BOOL __export FAR PASCAL GetDriver(LPSTR lpszName, LPSTR lpszEntry, LPARAM lParam)
/*
    LPSTR  lpszName;      // board name
    LPSTR  lpszEntry;     // system.ini entry
    LPARAM lParam;        // optional user data
this is a callback function of olDaEnumBoards, it gets the
strings of the Open Layers board and attempts to initialize
the board. If successful, enumeration is halted.
*/
{
    LPBOARD lpboard = (LPBOARD)(LPVOID)lParam;

    /* fill in board strings */

    lstrcpyn(lpboard->name,lpszName,MAX_BOARD_NAME_LENGTH-1);
    lstrcpyn(lpboard->entry,lpszEntry,MAX_BOARD_NAME_LENGTH-1);

    /* try to open board */

    lpboard->status = olDaInitialize(lpszName,&lpboard->hdrvr);
    if (lpboard->hdrvr != NULL)
        return FALSE;          /* false to stop enumerating */
    else
        return TRUE;           /* true to continue          */
}


/* Declare Python methods, their args and their docstrings */

static PyMethodDef DT_methods[] = {
    {"initBoard", (PyCFunction) DT_initBoard, METH_NOARGS, "Initalize the OLDA interface"},
    {"closeBoard", (PyCFunction) DT_closeBoard, METH_NOARGS, "Shut down the OLDA interface"},
    {"postInt16Wait", (PyCFunction) DT_postInt16Wait, METH_VARARGS,
        "Post an int16 to port, followed by a snooze to ensure acquistion sees it"},
    {"postInt16", (PyCFunction) DT_postInt16, METH_VARARGS, "Post an int16 to port"},
    {"postInt32Wait", (PyCFunction) DT_postInt32Wait, METH_VARARGS,
        "Post an int32 to port, followed by a snooze to ensure acquistion sees it"},
    {"postInt32", (PyCFunction) DT_postInt32, METH_VARARGS, "Post an int32 to port"},
    {"postInt32_2x16", (PyCFunction) DT_postInt32_2x16, METH_VARARGS,
        "Post an int32 to port by posting two 16 bit chunks sequentially,\n"
        "each followed by a snooze to ensure acquistion sees it"},
    {"postFloat", (PyCFunction) DT_postFloat, METH_VARARGS,
        "Post a float to port, followed by a snooze to ensure acquistion sees it"},
    {"postString", (PyCFunction) DT_postString, METH_VARARGS,
        "Post a string to port, 2 chars at a time, followed by a snooze\n"
        "to ensure the acquistion computer sees it"},
    {"toggleBitsOnPost", (PyCFunction) DT_toggleBitsOnPost, METH_VARARGS,
        "Toggle the specified bits (usually status bits) on the next post to port.\n"
        "Pass it 0 to stop toggling on subsequent posts"},
    {"setBitsWait", (PyCFunction) DT_setBitsWait,  METH_VARARGS,
        "Set the specified bits, followed by a snooze to ensure acquistion sees it"},
    {"setBits", (PyCFunction) DT_setBits, METH_VARARGS, "Set the specified bits"},
    {"clearBitsWait", (PyCFunction) DT_clearBitsWait, METH_VARARGS,
        "Clear the specified bits, followed by a snooze to ensure acquistion sees it"},
    {"clearBits", (PyCFunction) DT_clearBits, METH_VARARGS, "Clear the specified bits"},
    {"toggleBitsWait", (PyCFunction) DT_toggleBitsWait, METH_VARARGS,
        "Toggle the specified bits, followed by a snooze to ensure the acquistion sees it"},
    {"toggleBits", (PyCFunction) DT_toggleBits, METH_VARARGS, "Toggle specified bits"},
    {"getChecksum", (PyCFunction) DT_getChecksum, METH_NOARGS,
        "Get the checksum of everything posted to the port so far"},
    {"setChecksum", (PyCFunction) DT_setChecksum, METH_VARARGS,
        "Set the checksum to whatever desired value.\n"
        "This is usually called just to init the checksum to 0"},

    {NULL, NULL, 0, NULL} /* Sentinel. What's a sentinel? */
};

DL_EXPORT(void) initDT(void)
{
    Py_InitModule3("DT", DT_methods,
            "Data Translations interface");
}


/* OLDA board interface */

PyObject * DT_initBoard(PyObject * self)
{
    board.hdrvr = NULL; // driver handle
    if (olDaEnumBoards(GetDriver,(LPARAM)(LPBOARD)&board) != OLNOERROR)
    {
        puts("Error enumerating through boards");
        RETURN_ERR(-1);
    }

    /* check for error within callback function */
    if (board.status != OLNOERROR)
    {
        puts("Error occured while finding board");
        RETURN_ERR(-1);
    }

    /* check for NULL driver handle - means no boards */
    if (board.hdrvr == NULL)
    {
        puts("No open layer boards found");
        RETURN_ERR(-1);
    }

    /* now init output stream */
    // get data acq subsystem, return subsystem handle:
    if (olDaGetDASS(board.hdrvr,OLSS_DOUT, 0, &hDout) != OLNOERROR)
    {
        puts("Error - unable to grab DASS");
        RETURN_ERR(-1);
    }

    /* set subsystem for single value operation */
    if (olDaSetDataFlow(hDout,OL_DF_SINGLEVALUE) != OLNOERROR)
    {
        puts("Error - unable to set up for single value operations");
        RETURN_ERR(-1);
    }

    /* set subsystem to 32 bits of digital output (ports A, B, C & D).
    Port A line 0 is LSB, port B line 7 is MSB.
    Pinouts on J1 68 pin cable are, from Port A line 0 LSB to port B line 7 MSB:
    [60, 26, 59, 25, 58, 24, 57, 23, 55, 21, 54, 20, 53, 19, 52].
    Pin 56 is a convenient digital ground.
    Port C line 0, used as the RECORD bit to trigger acquisition to start saving, is pin 51.
    See DT340 manual "UM340.pdf" */
    if (olDaSetResolution(hDout, 32) != OLNOERROR)
    {
        puts("Error setting resolution");
        RETURN_ERR(-1);
    }
    if (olDaConfig(hDout) != OLNOERROR)
    {
        puts("Error during config");
        RETURN_ERR(-1);
    }

    RETURN_ERR(0);
}

PyObject * DT_closeBoard(PyObject * self)
{
    int ret = 0;
    //if (olDaReleaseDASS(hDa) != OLNOERROR)
    //CHECKERROR (olDaReleaseDASS(hAd));
    //CHECKERROR (olDaReleaseDASS(hDin));
    if (olDaReleaseDASS(hDout) != OLNOERROR)
    {
        puts("Error releasing hDout");
        ret++;
    }

    /* olDaTerminate will hang if all HDASS's are not closed.
    *  with olDaReleaseDASS or olDaAbort. Either use these, or
    *  do not use olDaTerminate. Either way, the resources will
    *  be freed when the program ends.
    */
    if (olDaTerminate(board.hdrvr) != OLNOERROR)
    {
        puts("Error during termination");
        ret++;
    }

    RETURN_ERR(ret);
}


/* Functions for posting digital values to the board */

// TODO: fix code duplication within each postInt** and postInt**Wait pair,
// make whether to snooze or not an argument

// Post an int16 to port, followed by a snooze to ensure acquistion sees it
PyObject * DT_postInt16Wait(PyObject *self, PyObject *args)
{
    PyObject *arglist;
    long val;
    if (!PyArg_ParseTuple (args, "i", &val))
    {
        puts("Error occured parsing arguments in postInt16Wait");
        arglist = Py_BuildValue("i", -1);
        Py_INCREF(arglist);
        return arglist;
    }
    incChecksum(val);
    post(val & 0x0000ffff);
    snooze();

    Py_INCREF(Py_None);
    return Py_None;
}

// Post an int16 to port
PyObject * DT_postInt16(PyObject *self, PyObject *args)
{
    PyObject *arglist;
    long val;
    if (!PyArg_ParseTuple (args, "i", &val))
    {
        puts("Error occured parsing arguments in postInt16");
        arglist = Py_BuildValue("i", -1);
        Py_INCREF(arglist);
        return arglist;
    }
    incChecksum(val);
    post(val & 0x0000ffff);

    Py_INCREF(Py_None);
    return Py_None;
}

// Post an int32 to port, followed by a snooze to ensure acquistion sees it
PyObject * DT_postInt32Wait(PyObject *self, PyObject *args)
{
    PyObject *arglist;
    long val;
    if (!PyArg_ParseTuple (args, "i", &val))
    {
        puts("Error occured parsing arguments in postInt32Wait");
        arglist = Py_BuildValue("i", -1);
        Py_INCREF(arglist);
        return arglist;
    }
    incChecksum(val);
    post(val & 0xffffffff);
    snooze();

    Py_INCREF(Py_None);
    return Py_None;
}

// Post an int32 to port
PyObject * DT_postInt32(PyObject *self, PyObject *args)
{
    PyObject *arglist;
    long val;
    if (!PyArg_ParseTuple (args, "i", &val))
    {
        puts("Error occured parsing arguments in postInt32");
        arglist = Py_BuildValue("i", -1);
        Py_INCREF(arglist);
        return arglist;
    }
    incChecksum(val);
    post(val & 0xffffffff);

    Py_INCREF(Py_None);
    return Py_None;
}

// Post an int32 to port by posting two 16 bit chunks sequentially,
// each followed by a snooze to ensure acquistion sees it
PyObject * DT_postInt32_2x16(PyObject *self, PyObject *args)
{
    PyObject *arglist;
    long val, low, high;
    if (!PyArg_ParseTuple (args, "i", &val))
    {
        puts("Error occured parsing arguments in postInt32_2x16");
        arglist = Py_BuildValue("i", -1);
        Py_INCREF(arglist);
        return arglist;
    }

    // break into 16 bit chunks, send sequentially:
    low = 0x0000ffff & val;
    // shift val down by 16 bits, mask it to be safe, left with only the high bits:
    high = 0x0000ffff & (val >> 16);

    incChecksum(low);
    post(low & 0x0000ffff);
    snooze();

    incChecksum(high);
    post(high & 0x0000ffff);
    snooze();

    Py_INCREF(Py_None);
    return Py_None;
}

// Post a float to port, followed by a snooze to ensure acquistion sees it
PyObject * DT_postFloat(PyObject *self, PyObject *args)
{
    PyObject *arglist;
    float val;
    long ival, low, high;
    if (!PyArg_ParseTuple (args, "f", &val))
    {
        puts("Error occured parsing arguments in postFloat");
        arglist = Py_BuildValue("i", -1);
        Py_INCREF(arglist);
        return arglist;
    }

    // break into 16 bit chunks, send sequentially
    ival = *((long *) &val);
    low = 0x0000ffff & ival;
    high = (unsigned long) (0x0000ffff & (ival >> 16));

    incChecksum(low);
    post(low & 0x0000ffff);
    snooze();

    incChecksum(high);
    post(high & 0x0000ffff);
    snooze();

    Py_INCREF(Py_None);
    return Py_None;
}

// Post a string to port, 2 chars at a time, followed by a snooze to ensure acquistion sees it
PyObject * DT_postString(PyObject *self, PyObject *args)
{
    PyObject *arglist;
    char * val;
    char * car;
    short * ar;
    int numchars = 0;
    int i;
    if (!PyArg_ParseTuple (args, "si", &val, &numchars))
    {
        puts("Error occured parsing arguments in postString");
        arglist = Py_BuildValue("i", -1);
        Py_INCREF(arglist);
        return arglist;
    }
    // make sure num chars is even:
    if ((numchars % 2) == 1)
        numchars++;

    // copy into buffer, append zeros to end if shorter than specified length:
    ar = (short *) malloc(numchars);
    car = (char *) ar;
    memset(car, 0, numchars);
    for (i=0; i<numchars; i++)
    {
        car[i] = val[i];
        if (val[i] == 0)
            break;
    }
    for (i=0; i<numchars/2; i++)
    {
        incChecksum(ar[i]);
        post(ar[i] & 0x0000ffff);
        snooze();
    }
    free(ar);

    Py_INCREF(Py_None);
    return Py_None;
}


/* Functions for setting and toggling specific bits on the port */

// Toggle the specified bits (usually status bits) on the next post to port.
// Pass it 0 to stop toggling on subsequent posts
PyObject * DT_toggleBitsOnPost(PyObject *self, PyObject *args)
{
    PyObject *arglist;
    int mask = 0;
    if (!PyArg_ParseTuple (args, "i", &mask))
    {
        puts("Error occured parsing arguments in toggleBitsOnPost");
        arglist = Py_BuildValue("i", -1);
        Py_INCREF(arglist);
        return arglist;
    }
    s_toggleMask = mask;

    Py_INCREF(Py_None);
    return Py_None;
}

// Set the specified bits, followed by a snooze to ensure acquistion sees it
PyObject * DT_setBitsWait(PyObject *self, PyObject *args)
{
    PyObject *arglist;
    int mask = 0;
    if (!PyArg_ParseTuple (args, "i", &mask))
    {
        puts("Error occured parsing arguments in setBitsWait");
        arglist = Py_BuildValue("i", -1);
        Py_INCREF(arglist);
        return arglist;
    }
    post(s_val | mask); // set masked bits high by ORing them with last value posted
    snooze();

    Py_INCREF(Py_None);
    return Py_None;
}

// Set the specified bits
PyObject * DT_setBits(PyObject *self, PyObject *args)
{
    PyObject *arglist;
    int mask = 0;
    if (!PyArg_ParseTuple (args, "i", &mask))
    {
        puts("Error occured parsing arguments in setBits");
        arglist = Py_BuildValue("i", -1);
        Py_INCREF(arglist);
        return arglist;
    }
    post(s_val | mask); // set specified bits high by ORing them with last value posted

    Py_INCREF(Py_None);
    return Py_None;
}

// Clear the specified bits, followed by a snooze to ensure acquistion sees it
PyObject * DT_clearBitsWait(PyObject *self, PyObject *args)
{
    PyObject *arglist;
    int mask = 0;
    if (!PyArg_ParseTuple (args, "i", &mask))
    {
        puts("Error occured parsing arguments in clearBitsWait");
        arglist = Py_BuildValue("i", -1);
        Py_INCREF(arglist);
        return arglist;
    }
    post(s_val & (~ mask)); // set masked bits low by NANDing them with last value posted
    snooze();

    Py_INCREF(Py_None);
    return Py_None;
}
// Clear the specified bits
PyObject * DT_clearBits(PyObject *self, PyObject *args)
{
    PyObject *arglist;
    int mask = 0;
    if (!PyArg_ParseTuple (args, "i", &mask))
    {
        puts("Error occured parsing arguments in clearBits");
        arglist = Py_BuildValue("i", -1);
        Py_INCREF(arglist);
        return arglist;
    }
    post(s_val & (~ mask)); // set specified bits low by NANDing them with last value posted

    Py_INCREF(Py_None);
    return Py_None;
}
// Toggle the specified bits, followed by a snooze to ensure the acquistion computer sees it
PyObject * DT_toggleBitsWait(PyObject *self, PyObject *args)
{
    PyObject *arglist;
    int mask = 0;
    if (!PyArg_ParseTuple (args, "i", &mask))
    {
        puts("Error occured parsing arguments in toggleBitsWait");
        arglist = Py_BuildValue("i", -1);
        Py_INCREF(arglist);
        return arglist;
    }
    post(s_val ^ mask); // toggle specified bits by XORing them with last value posted
    snooze();

    Py_INCREF(Py_None);
    return Py_None;
}

// Toggle specified bits
PyObject * DT_toggleBits(PyObject *self, PyObject *args)
{
    PyObject *arglist;
    int mask = 0;
    if (!PyArg_ParseTuple (args, "i", &mask))
    {
        puts("Error occured parsing arguments in toggleBits");
        arglist = Py_BuildValue("i", -1);
        Py_INCREF(arglist);
        return arglist;
    }
    post(s_val ^ mask); // toggle specified bits by XORing them with last value posted

    Py_INCREF(Py_None);
    return Py_None;
}


/* Functions for getting and setting the checksum */

// Get the checksum of everything posted to the port so far
PyObject * DT_getChecksum(PyObject *self)
{
    PyObject * arglist = Py_BuildValue("i", s_checksum);
    Py_INCREF(arglist);
    return arglist;
}

// Set the checksum to whatever desired value, usually only called to init the checksum to 0
PyObject * DT_setChecksum(PyObject *self, PyObject *args)
{
    PyObject *arglist;
    int checksum = 0;
    if (!PyArg_ParseTuple (args, "i", &checksum))
    {
        puts("Error occured parsing arguments in setChecksum");
        arglist = Py_BuildValue("i", -1);
        Py_INCREF(arglist);
        return arglist;
    }
    s_checksum = checksum;

    Py_INCREF(Py_None);
    return Py_None;
}
