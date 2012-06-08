##############################################################################
#
# Copyright (c) 2010 Zope Foundation and Contributors.
# All Rights Reserved.
#
# This software is subject to the provisions of the Zope Public License,
# Version 2.1 (ZPL).  A copy of the ZPL should accompany this distribution.
# THIS SOFTWARE IS PROVIDED "AS IS" AND ANY AND ALL EXPRESS OR IMPLIED
# WARRANTIES ARE DISCLAIMED, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF TITLE, MERCHANTABILITY, AGAINST INFRINGEMENT, AND FITNESS
# FOR A PARTICULAR PURPOSE.
#
##############################################################################

# Test user and groups options

from zope.testing import setupstack
import doctest
import mock
import os
import sys
import unittest
import zdaemon.zdctl

def write(name, text):
    with open(name, 'w') as f:
        f.write(text)

class O:
    def __init__(self, **kw):
        self.__dict__.update(kw)

def test_user_fails_when_not_root():
    """

    >>> write('conf',
    ... '''
    ... <runner>
    ...   program sleep 9
    ...   user zope
    ... </runner>
    ... ''')

    >>> with mock.patch('os.geteuid') as geteuid:
    ...   with mock.patch('sys.stderr'):
    ...     sys.stderr = sys.stdout
    ...     geteuid.return_value = 42
    ...     try:
    ...         zdaemon.zdctl.main(['-C', 'conf', 'status'])
    ...     except SystemExit:
    ...         pass
    ...     else:
    ...         print 'oops'
    ... # doctest: +ELLIPSIS
    Error: only root can use -u USER to change users
    For help, use ... -h

    >>> import pwd
    >>> pwd.getpwnam.assert_called_with('zope')

    """

def test_user_sets_supplemtary_groups():
    """

    >>> write('conf',
    ... '''
    ... <runner>
    ...   program sleep 9
    ...   user zope
    ... </runner>
    ... ''')

    >>> import grp
    >>> grp.getgrall.return_value = [
    ...   O(gr_gid=8, gr_mem =['g', 'zope', ]),
    ...   O(gr_gid=1, gr_mem =['a', 'x', ]),
    ...   O(gr_gid=2, gr_mem =['b', 'x', 'zope']),
    ...   O(gr_gid=5, gr_mem =['c', 'x', ]),
    ...   O(gr_gid=4, gr_mem =['d', 'x', ]),
    ...   O(gr_gid=3, gr_mem =['e', 'x', 'zope', ]),
    ...   O(gr_gid=6, gr_mem =['f', ]),
    ...   O(gr_gid=7, gr_mem =['h', ]),
    ... ]

    >>> zdaemon.zdctl.main(['-C', 'conf', 'status'])
    daemon manager not running

    >>> import pwd, os
    >>> os.geteuid.assert_called_with()
    >>> pwd.getpwnam.assert_called_with('zope')
    >>> grp.getgrall.assert_called_with()
    >>> os.setuid.assert_called_with(99)
    >>> os.setgid.assert_called_with(5)
    >>> os.setgroups.assert_called_with([2, 3, 8])

    """

def test_do_nothing_if_effective_user_is_configured_user():
    """

    >>> write('conf',
    ... '''
    ... <runner>
    ...   program sleep 9
    ...   user zope
    ... </runner>
    ... ''')

    >>> with mock.patch('os.geteuid') as geteuid:
    ...     geteuid.return_value = 99
    ...     zdaemon.zdctl.main(['-C', 'conf', 'status'])
    ...     os.geteuid.assert_called_with()
    daemon manager not running

    >>> import pwd, os, grp
    >>> pwd.getpwnam.assert_called_with('zope')
    >>> _ = grp.getgrall.assert_not_called()
    >>> _ = os.setuid.assert_not_called()
    >>> _ = os.setgid.assert_not_called()
    >>> _ = os.setgroups.assert_not_called()

    """

def setUp(test):
    setupstack.setUpDirectory(test)
    getpwname = setupstack.context_manager(test, mock.patch('pwd.getpwnam'))
    getpwname.return_value = O(pw_gid=5, pw_uid=99, pw_name='zope')
    setupstack.context_manager(test, mock.patch('os.geteuid')).return_value = 0
    setupstack.context_manager(test, mock.patch('grp.getgrall'))
    setupstack.context_manager(test, mock.patch('os.setgroups'))
    setupstack.context_manager(test, mock.patch('os.setuid'))
    setupstack.context_manager(test, mock.patch('os.setgid'))

def test_suite():
    return doctest.DocTestSuite(setUp=setUp, tearDown=setupstack.tearDown)

