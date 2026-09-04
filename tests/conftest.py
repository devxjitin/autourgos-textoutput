"""
Works around a known Tcl/Tk + background-thread interpreter-teardown crash
(same issue documented in autourgos-textinput's own conftest.py): running a
Tk() mainloop on a non-main thread -- which OutputBox does deliberately, by
design, so `.show()` can be called from any thread -- can leave a native Tcl
async handler that gets torn down by the "wrong" thread during Python's
normal interpreter finalization, corrupting the process exit code even when
every test passed. Not a defect in this package's logic.

Fix: after pytest has finished reporting results, skip Python's normal
(Tcl-touching) interpreter finalization and exit immediately with pytest's
real exit status instead.
"""
import os
import sys

import pytest


@pytest.hookimpl(hookwrapper=True)
def pytest_sessionfinish(session, exitstatus):
    yield
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(int(exitstatus))
