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

import doctest
import manuel.capture
import manuel.doctest
import manuel.testing
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
import ZConfig
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

    """

def setUp(test):
    test.globs['_td'] = td = []
    here = os.getcwd()
    td.append(lambda : os.chdir(here))
    tmpdir = tempfile.mkdtemp()
    td.append(lambda : shutil.rmtree(tmpdir))
    test.globs['tmpdir'] = tmpdir
    workspace = tempfile.mkdtemp()
    td.append(lambda : shutil.rmtree(workspace))
    os.chdir(workspace)
    open('zdaemon', 'w').write(zdaemon_template % dict(
        python = sys.executable,
        zdaemon = zdaemon_loc,
        ZConfig = zconfig_loc,
        ))
    os.chmod('zdaemon', 0755)
    test.globs.update(dict(
        system = system
        ))

def tearDown(test):
    for f in test.globs['_td']:
        f()

def system(command, input='', quiet=False):
    p = subprocess.Popen(
        command, shell=True,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT)
    if input:
        p.stdin.write(input)
    p.stdin.close()
    data = p.stdout.read()
    if not quiet:
        print data,
    p.wait()

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
                ])
        ),
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
            '../README.txt',
            setUp=setUp, tearDown=tearDown,
            ),
        ))

