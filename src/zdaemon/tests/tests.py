##############################################################################
#
# Copyright (c) 2004 Zope Foundation and Contributors.
# All Rights Reserved.
#
# This software is subject to the provisions of the Zope Public License,
# Version 2.0 (ZPL).  A copy of the ZPL should accompany this distribution.
# THIS SOFTWARE IS PROVIDED "AS IS" AND ANY AND ALL EXPRESS OR IMPLIED
# WARRANTIES ARE DISCLAIMED, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF TITLE, MERCHANTABILITY, AGAINST INFRINGEMENT, AND FITNESS
# FOR A PARTICULAR PURPOSE.
#
##############################################################################
from __future__ import print_function

import doctest
import glob
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import unittest
from contextlib import contextmanager

import ZConfig
import manuel.capture
import manuel.doctest
import manuel.testing
import zc.customdoctests
import zdaemon
from zope.testing import renormalizing

try:
    import pkg_resources
    zdaemon_loc = pkg_resources.working_set.find(
        pkg_resources.Requirement.parse('zdaemon')).location
    zconfig_loc = pkg_resources.working_set.find(
        pkg_resources.Requirement.parse('ZConfig')).location
except (ImportError, AttributeError):
    zdaemon_loc = os.path.dirname(os.path.dirname(zdaemon.__file__))
    zconfig_loc = os.path.dirname(os.path.dirname(ZConfig.__file__))


def write(name, text):
    with open(name, 'w') as f:
        f.write(text)


def read(name):
    with open(name) as f:
        return f.read()


def make_sure_non_daemon_mode_doesnt_hang_when_program_exits():
    """
    The whole awhile bit that waits for a program to start
    whouldn't be used on non-daemon mode.

    >>> write('conf',
    ... '''
    ... <runner>
    ...   program sleep 1
    ...   daemon off
    ... </runner>
    ... ''')

    >>> system("./zdaemon -Cconf start")

    """


def dont_hang_when_program_doesnt_start():
    """
    If a program doesn't start, we don't want to wait for ever.

    >>> write('conf',
    ... '''
    ... <runner>
    ...   program sleep
    ...   backoff-limit 2
    ... </runner>
    ... ''')

    >>> system("./zdaemon -Cconf start")
    . .
    daemon manager not running
    Failed: 1

    """


def allow_duplicate_arguments():
    """
    Wrapper scripts will often embed configuration arguments. This could
    cause a problem when zdaemon reinvokes itself, passing it's own set of
    configuration arguments.  To deal with this, we'll allow duplicate
    arguments that have the same values.

    >>> write('conf',
    ... '''
    ... <runner>
    ...   program sleep 10
    ... </runner>
    ... ''')

    >>> system("./zdaemon -Cconf -Cconf -Cconf start")
    . .
    daemon process started, pid=21446

    >>> system("./zdaemon -Cconf -Cconf -Cconf stop")
    . .
    daemon process stopped

    """


def test_stop_timeout():
    r"""

    >>> write('t.py',
    ... '''
    ... import time, signal
    ... signal.signal(signal.SIGTERM, lambda *a: None)
    ... while 1: time.sleep(9)
    ... ''')

    >>> write('conf',
    ... '''
    ... <runner>
    ...   program %s t.py
    ...   stop-timeout 1
    ... </runner>
    ... ''' % sys.executable)

    >>> system("./zdaemon -Cconf start")
    . .
    daemon process started, pid=21446

    >>> import threading, time
    >>> thread = threading.Thread(
    ...     target=system, args=("./zdaemon -Cconf stop",),
    ...     kwargs=dict(quiet=True))
    >>> thread.start()
    >>> time.sleep(.2)

    >>> system("./zdaemon -Cconf status")
    program running; pid=15372

    >>> thread.join(2)

    >>> system("./zdaemon -Cconf status")
    daemon manager not running
    Failed: 3

    """


def test_kill():
    """

    >>> write('conf',
    ... '''
    ... <runner>
    ...   program sleep 100
    ... </runner>
    ... ''')

    >>> system("./zdaemon -Cconf start")
    . .
    daemon process started, pid=1234

    >>> system("./zdaemon -Cconf kill ded")
    invalid signal 'ded'

    >>> system("./zdaemon -Cconf kill CONT")
    kill(1234, 18)
    signal SIGCONT sent to process 1234

    >>> system("./zdaemon -Cconf stop")
    . .
    daemon process stopped

    >>> system("./zdaemon -Cconf kill")
    daemon process not running

    """


def test_logreopen():
    """

    >>> write('conf',
    ... '''
    ... <runner>
    ...   program sleep 100
    ...   transcript transcript.log
    ... </runner>
    ... ''')

    >>> system("./zdaemon -Cconf start")
    . .
    daemon process started, pid=1234

    >>> os.rename('transcript.log', 'transcript.log.1')

    >>> system("./zdaemon -Cconf logreopen")
    kill(1234, 12)
    signal SIGUSR2 sent to process 1234

    This also reopens the transcript.log:

    >>> sorted(os.listdir('.'))
    ['conf', 'transcript.log', 'transcript.log.1', 'zdaemon', 'zdsock']

    >>> system("./zdaemon -Cconf stop")
    . .
    daemon process stopped

    """


def test_log_rotation():
    """

    >>> write('conf',
    ... '''
    ... <runner>
    ...   program sleep 100
    ...   transcript transcript.log
    ... </runner>
    ... <eventlog>
    ...   <logfile>
    ...     path event.log
    ...   </logfile>
    ... </eventlog>
    ... ''')

    >>> system("./zdaemon -Cconf start")
    . .
    daemon process started, pid=1234

    Pretend we did a logrotate:

    >>> os.rename('transcript.log', 'transcript.log.1')
    >>> os.rename('event.log', 'event.log.1')

    >>> system("./zdaemon -Cconf reopen_transcript")  # or logreopen

    This reopens both transcript.log and event.log:

    >>> sorted(glob.glob('transcript.log*'))
    ['transcript.log', 'transcript.log.1']

    >>> sorted(glob.glob('event.log*'))
    ['event.log', 'event.log.1']

    >>> system("./zdaemon -Cconf stop")
    . .
    daemon process stopped

    """


def test_start_test_program():
    """
    >>> write('t.py',
    ... '''
    ... import time
    ... time.sleep(1)
    ... open('x', 'w').close()
    ... time.sleep(99)
    ... ''')

    >>> write('conf',
    ... '''
    ... <runner>
    ...   program %s t.py
    ...   start-test-program cat x
    ... </runner>
    ... ''' % sys.executable)

    >>> import os

    >>> system("./zdaemon -Cconf start")
    . .
    daemon process started, pid=21446

    >>> os.path.exists('x')
    True
    >>> os.remove('x')

    >>> system("./zdaemon -Cconf restart")
    . . .
    daemon process restarted, pid=19622
    >>> os.path.exists('x')
    True

    >>> system("./zdaemon -Cconf stop")
    <BLANKLINE>
    daemon process stopped
    """


def test_start_timeout():
    """
    >>> write('t.py',
    ... '''
    ... import time
    ... time.sleep(9)
    ... ''')

    >>> write('conf',
    ... '''
    ... <runner>
    ...   program %s t.py
    ...   start-test-program cat x
    ...   start-timeout 1
    ... </runner>
    ... ''' % sys.executable)

    >>> import time
    >>> start = time.time()

    >>> system("./zdaemon -Cconf start")
    <BLANKLINE>
    Program took too long to start
    Failed: 1

    >>> system("./zdaemon -Cconf stop")
    <BLANKLINE>
    daemon process stopped
    """


def DAEMON_MANAGER_MODE_leak():
    """
    Zdaemon used an environment variable to flag that it's running in
    daemon-manager mode, as opposed to UI mode.  If this environment
    variable is allowed to leak to the program, them the program will
    be unable to invoke zdaemon correctly.

    >>> write('c', '''
    ... <runner>
    ...   program env
    ...   transcript t
    ... </runner>
    ... ''')

    >>> system('./zdaemon -b0 -T1 -Cc start', quiet=True)
    Failed: 1
    >>> 'DAEMON_MANAGER_MODE' not in read('t')
    True
    """


def nonzero_exit_on_program_failure():
    """
    >>> write('conf',
    ... '''
    ... <runner>
    ...   backoff-limit 1
    ...   program nosuch
    ... </runner>
    ... ''')

    >>> system("./zdaemon -Cconf start", echo=True) # doctest: +ELLIPSIS
    ./zdaemon...
    daemon manager not running
    Failed: 1

    >>> write('conf',
    ... '''
    ... <runner>
    ...   backoff-limit 1
    ...   program cat nosuch
    ... </runner>
    ... ''')

    >>> system("./zdaemon -Cconf start", echo=True) # doctest: +ELLIPSIS
    ./zdaemon...
    daemon manager not running
    Failed: 1

    >>> write('conf',
    ... '''
    ... <runner>
    ...   backoff-limit 1
    ...   program pwd
    ... </runner>
    ... ''')

    >>> system("./zdaemon -Cconf start", echo=True) # doctest: +ELLIPSIS
    ./zdaemon...
    daemon manager not running
    Failed: 1

    """


def setUp(test):
    test.globs['_td'] = td = []
    here = os.getcwd()
    td.append(lambda: os.chdir(here))
    tmpdir = tempfile.mkdtemp()
    td.append(lambda: shutil.rmtree(tmpdir))
    test.globs['tmpdir'] = tmpdir
    workspace = tempfile.mkdtemp()
    td.append(lambda: shutil.rmtree(workspace))
    os.chdir(workspace)
    write('zdaemon', zdaemon_template % dict(
        python=sys.executable,
        zdaemon=zdaemon_loc,
        ZConfig=zconfig_loc,
    ))
    os.chmod('zdaemon', 0o755)
    test.globs['system'] = system


def tearDown(test):
    for f in test.globs['_td']:
        f()


class Timeout(BaseException):
    pass


@contextmanager
def timeout(seconds):
    this_frame = sys._getframe()

    def raiseTimeout(signal, frame):
        # the if statement here is meant to prevent an exception in the
        # finally: clause before clean up can take place
        if frame is not this_frame:
            raise Timeout('timed out after %s seconds' % seconds)

    try:
        prev_handler = signal.signal(signal.SIGALRM, raiseTimeout)
    except ValueError:
        # signal only works in main thread
        # let's ignore the request for a timeout and hope the test doesn't hang
        yield
    else:
        try:
            signal.alarm(seconds)
            yield
        finally:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, prev_handler)


def system(command, input='', quiet=False, echo=False):
    if echo:
        print(command)
    p = subprocess.Popen(
        command, shell=True,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT)
    with timeout(60):
        data = p.communicate(input)[0]
    if not quiet:
        print(data.decode(), end='')
    r = p.wait()
    if r:
        print('Failed:', r)


def checkenv(match):
    match = [a for a in match.group(1).split('\n')[:-1]
             if a.split('=')[0] in ('HOME', 'LD_LIBRARY_PATH')]
    match.sort()
    return '\n'.join(match) + '\n'


zdaemon_template = """#!%(python)s

import sys
sys.path[0:0] = [
  %(zdaemon)r,
  %(ZConfig)r,
  ]

try:
    import coverage
except ImportError:
    pass
else:
    coverage.process_startup()

import zdaemon.zdctl

if __name__ == '__main__':
    zdaemon.zdctl.main()
"""


def test_suite():
    README_checker = renormalizing.RENormalizing([
        (re.compile('pid=\d+'), 'pid=NNN'),
        (re.compile('(\. )+\.?'), '<BLANKLINE>'),
        (re.compile('^env\n((?:.*\n)+)$'), checkenv),
    ])

    return unittest.TestSuite((
        doctest.DocTestSuite(
            setUp=setUp, tearDown=tearDown,
            checker=renormalizing.RENormalizing([
                (re.compile('pid=\d+'), 'pid=NNN'),
                (re.compile('(\. )+\.?'), '<BLANKLINE>'),
                (re.compile('process \d+'), 'process NNN'),
                (re.compile('kill\(\d+,'), 'kill(NNN,'),
            ])),
        manuel.testing.TestSuite(
            manuel.doctest.Manuel(
                parser=zc.customdoctests.DocTestParser(
                    ps1='sh>',
                    transform=lambda s: 'system("%s")\n' % s.rstrip()
                ),
                checker=README_checker,
            ) +
            manuel.doctest.Manuel(checker=README_checker) +
            manuel.capture.Manuel(),
            '../README.rst',
            setUp=setUp, tearDown=tearDown),
    ))
