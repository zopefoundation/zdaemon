##############################################################################
#
# Copyright (c) 2004 Zope Corporation and Contributors.
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
"""Setup for zope.i18nmessageid package

$Id$
"""

import os

try:
    from setuptools import setup, Extension
except ImportError, e:
    from distutils.core import setup, Extension

setup(name='zdaemon',
      version='1.2',
      url='http://svn.zope.org/zdaemon',
      license='ZPL 2.1',
      description='Daemon management',
      author='Zope Corporation and Contributors',
      author_email='zope-dev@zope.org',
      long_description='',
      
      packages=['zdaemon'],
      package_dir = {'': os.path.join(os.path.dirname(__file__), 'src')},

      tests_require = ['zope.testing'],
      install_requires=['ZConfig',
                       ],
      include_package_data = True,

      zip_safe = False,
      )
