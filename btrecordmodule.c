/*
 * Python interface to btrecord
 *
 * Author: Joshua Root <jmr@gelato.unsw.edu.au>
 *
 * Copyright (C) 2007 The University of New South Wales
 *
 *  This program is free software; you can redistribute it and/or modify
 *  it under the terms of the GNU General Public License as published by
 *  the Free Software Foundation; either version 2 of the License, or
 *  (at your option) any later version.
 *
 *  This program is distributed in the hope that it will be useful,
 *  but WITHOUT ANY WARRANTY; without even the implied warranty of
 *  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 *  GNU General Public License for more details.
 *
 *  You should have received a copy of the GNU General Public License
 *  along with this program; if not, write to the Free Software
 *  Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
 */

#include "Python.h"
#include "list.h"
#include "btrecord.h"

static PyObject *ErrorObject;

/* ----------------------------------------------------- */

static char btrecordmodule_setOutFile__doc__[] =
""
;

struct io_stream *stream;
struct ifile_info *iip;
extern struct list_head input_files;

static PyObject *
btrecordmodule_setOutFile(PyObject *self /* Not used */, PyObject *args)
{
	iip = malloc(sizeof(struct ifile_info));
	if (!iip)
		return PyErr_NoMemory();

	if (!PyArg_ParseTuple(args, "ss", &iip->file_name, &iip->devnm))
		return NULL;

	iip->cpu = 0;
	iip->tpkts = 0;
	iip->genesis = 0;
        list_add_tail(&iip->head, &input_files);
	stream = stream_open(iip);

	Py_INCREF(Py_None);
	return Py_None;
}

static char btrecordmodule_addOp__doc__[] =
""
;

static PyObject *
btrecordmodule_addOp(PyObject *self /* Not used */, PyObject *args)
{
	struct io_spec spec;

	if (!PyArg_ParseTuple(args, "illl", &spec.rw, &spec.bytes,
			      &spec.sector, &spec.time))
		return NULL;
	
	spec.rw = !spec.rw;
	stream_add_io(stream, &spec);
	
	Py_INCREF(Py_None);
	return Py_None;
}

static char btrecordmodule_done__doc__[] =
""
;

static PyObject *
btrecordmodule_done(PyObject *self /* Not used */, PyObject *args)
{

	if (!PyArg_ParseTuple(args, ""))
		return NULL;
        
	stream_close(stream);
	free(iip);
	
	Py_INCREF(Py_None);
	return Py_None;
}

/* List of methods defined in the module */

static struct PyMethodDef btrecordmodule_methods[] = {
	{"setOutFile",	(PyCFunction)btrecordmodule_setOutFile,	METH_VARARGS,	btrecordmodule_setOutFile__doc__},
        {"addOp",	(PyCFunction)btrecordmodule_addOp,	METH_VARARGS,	btrecordmodule_addOp__doc__},
        {"done",	(PyCFunction)btrecordmodule_done,	METH_VARARGS,	btrecordmodule_done__doc__},
 
	{NULL,	 (PyCFunction)NULL, 0, NULL}		/* sentinel */
};


/* Initialization function for the module (*must* be called initbtrecord) */

static char btrecord_module_documentation[] = 
""
;

void
initbtrecord()
{
	PyObject *m, *d;

	/* Create the module and add the functions */
	m = Py_InitModule4("btrecord", btrecordmodule_methods,
		btrecord_module_documentation,
		(PyObject*)NULL,PYTHON_API_VERSION);

	/* Add some symbolic constants to the module */
	d = PyModule_GetDict(m);
	ErrorObject = PyString_FromString("btrecord.error");
	PyDict_SetItemString(d, "error", ErrorObject);

	/* XXXX Add constants here */
	
	/* Check for errors */
	if (PyErr_Occurred())
		Py_FatalError("can't initialize module btrecord");
}

