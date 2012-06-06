##############################################################################
#
# Copyright (c) 2004 Zope Corporation and Contributors.
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
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
import ZConfig
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


def make_sure_non_daemon_mode_doesnt_hang_when_program_exits():
    """
    The whole awhile bit that waits for a program to start
    whouldn't be used on non-daemon mode.

    >>> open('conf', 'w').write(
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

    >>> open('conf', 'w').write(
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

    >>> open('conf', 'w').write(
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

def system(command, input=''):
    p = subprocess.Popen(
        command, shell=True,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT)
    if input:
        p.stdin.write(input)
    p.stdin.close()
    print p.stdout.read(),
    p.wait()

def checkenv(match):
    match = [a for a in match.group(1).split('\n')[:-1]
             if a.split('=')[0] in ('HOME', 'LD_LIBRARY_PATH')]
    match.sort()
    return '\n'.join(match) + '\n'

def test_suite():
    return unittest.TestSuite((
        doctest.DocTestSuite(
            setUp=setUp, tearDown=tearDown,
            checker=renormalizing.RENormalizing([
                (re.compile('pid=\d+'), 'pid=NNN'),
                (re.compile('(\. )+\.?'), '<BLANKLINE>'),
                ])
        ),
        doctest.DocFileSuite(
            '../README.txt',
            setUp=setUp, tearDown=tearDown,
            checker=renormalizing.RENormalizing([
                (re.compile('pid=\d+'), 'pid=NNN'),
                (re.compile('(\. )+\.?'), '<BLANKLINE>'),
                (re.compile('^env\n((?:.*\n)+)$'), checkenv),
                ])
        ),
        ))


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
