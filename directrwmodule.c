
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
      ssize_t done = 0;

	if (!PyArg_ParseTuple(args, "il", &fd, &sz))
		return NULL;

      /* valloc aligns to page size; Linux read/write with O_DIRECT
         only really needs 512-byte alignment, but meh */
      buf = valloc(sz);
      if (!buf)
            return PyErr_NoMemory();
      
      do {
            ssize_t n = read(fd, buf+done, sz-done);
            if (n == -1) {
                  free(buf);
                  return PyErr_SetFromErrno(PyExc_OSError);
            }
            done += n;
      } while (done < sz);
      
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
      ssize_t done = 0;
      
	if (!PyArg_ParseTuple(args, "isl", &fd, &buf, &sz))
		return NULL;
	
	if (((unsigned long)buf & 511) != 0) {
	     /* misaligned, so fix up */
	     abuf = valloc(sz);
	     if (!abuf)
                  return PyErr_NoMemory();
            memcpy(abuf, buf, sz);
	} else {
	     /* was OK, so use the existing buffer */
	     abuf = buf;
	}
	
	do {
            ssize_t n = write(fd, buf+done, sz-done);
            if (n == -1) {
                  if (abuf)
                        free(abuf);
                  return PyErr_SetFromErrno(PyExc_OSError);
            }
            done += n;
      } while (done < sz);
	
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
