/*
 * Copyright 2007 The University of New South Wales
 * Author: Joshua Root <jmr@gelato.unsw.edu.au>
 *
 * This program is free software; you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation; either version 2 of the License, or
 * (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program; if not, write to the Free Software
 * Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA
 */

#include "Python.h"

static PyObject *ErrorObject;

/* ----------------------------------------------------- */

static char directrw_read__doc__[] =
""
;

static PyObject *
directrw_read(PyObject *self /* Not used */, PyObject *args)
{
        int fd = 0;
        size_t sz = 0;
        char *buf;
        ssize_t n;

	if (!PyArg_ParseTuple(args, "il", &fd, &sz))
		return NULL;

        //printf("directrw_read: args ok - fd=%d, sz=%ul\n", fd, sz);
        /* valloc aligns to page size; Linux read/write with O_DIRECT
           only really needs 512-byte alignment, but meh */
        buf = valloc(sz);
        if (!buf)
                return PyErr_NoMemory();

        //printf("directrw_read: memory allocated ok\n");
        Py_BEGIN_ALLOW_THREADS
        n = read(fd, buf, sz);
        Py_END_ALLOW_THREADS

        if (n == -1) {
                free(buf);
                return PyErr_SetFromErrno(PyExc_OSError);
        }
        //printf("directrw_read: read ok\n");

        return Py_BuildValue("s", buf);
}

static char directrw_write__doc__[] =
""
;

static PyObject *
directrw_write(PyObject *self /* Not used */, PyObject *args)
{
        int fd = 0;
        size_t sz = 0;
        char *abuf = NULL; /* correctly aligned buffer */
        char *buf = NULL; /* original buffer */
        ssize_t n;

	if (!PyArg_ParseTuple(args, "isl", &fd, &buf, &sz))
		return NULL;

        //printf("directrw_write: args ok - fd=%d, buf=%p, sz=%ul\n", fd, buf, sz);
	if (((Py_uintptr_t)buf & 511) != 0) {
                /* misaligned, so fix up */
                //printf("directrw_write: buf misaligned\n");
                abuf = valloc(sz);
                if (!abuf)
                        return PyErr_NoMemory();
	}
        
        Py_BEGIN_ALLOW_THREADS
        if (abuf)
                memcpy(abuf, buf, sz);
        else
                abuf = buf;

        n = write(fd, abuf, sz);
        Py_END_ALLOW_THREADS

        if (n == -1) {
                if (abuf)
                        free(abuf);
                return PyErr_SetFromErrno(PyExc_OSError);
        }
        //printf("directrw_write: write ok\n");

	if (abuf)
                free(abuf);
        Py_INCREF(Py_None);
        return Py_None;
}

/* List of methods defined in the module */

static struct PyMethodDef directrw_methods[] = {
	{"read",	(PyCFunction)directrw_read,	METH_VARARGS,	directrw_read__doc__},
        {"write",	(PyCFunction)directrw_write,	METH_VARARGS,	directrw_write__doc__},
 
	{NULL,	 (PyCFunction)NULL, 0, NULL}		/* sentinel */
};


/* Initialization function for the module (*must* be called initdirectrw) */

static char directrw_module_documentation[] = 
""
;

void
initdirectrw()
{
	PyObject *m, *d;

	/* Create the module and add the functions */
	m = Py_InitModule4("directrw", directrw_methods,
		directrw_module_documentation,
		(PyObject*)NULL,PYTHON_API_VERSION);

	/* Add some symbolic constants to the module */
	d = PyModule_GetDict(m);
	ErrorObject = PyString_FromString("directrw.error");
	PyDict_SetItemString(d, "error", ErrorObject);

	/* XXXX Add constants here */
	
	/* Check for errors */
	if (PyErr_Occurred())
		Py_FatalError("can't initialize module directrw");
}
