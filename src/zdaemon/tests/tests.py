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
"""XXX short summary goes here.

$Id$
"""

import os, re, shutil, sys, tempfile, unittest
import ZConfig, zdaemon
from zope.testing import doctest, renormalizing

try:
    import pkg_resources
except ImportError:
    zdaemon_loc = os.path.dirname(os.path.dirname(zdaemon.__file__))
    zconfig_loc = os.path.dirname(os.path.dirname(ZConfig.__file__))
else:
    zdaemon_loc = pkg_resources.working_set.find(
        pkg_resources.Requirement.parse('zdaemon')).location
    zconfig_loc = pkg_resources.working_set.find(
        pkg_resources.Requirement.parse('ZConfig')).location

def setUp(test):
    test.globs['_td'] = td = []
    here = os.getcwd()
    td.append(lambda : os.chdir(here))
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
    i, o = os.popen4(command)
    if input:
        i.write(input)
    i.close()
    print o.read(),


def test_suite():
    return unittest.TestSuite((
        doctest.DocFileSuite(
            '../README.txt',
            setUp=setUp, tearDown=tearDown,
            checker=renormalizing.RENormalizing([
                (re.compile('pid=\d+'), 'pid=NNN'),
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
