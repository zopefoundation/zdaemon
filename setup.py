##############################################################################
#
# Copyright (c) 2006-2009 Zope Foundation and Contributors.
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

import os

entry_points = """
[console_scripts]
zdaemon = zdaemon.zdctl:main
"""

def read(*rnames):
    return open(os.path.join(os.path.dirname(__file__), *rnames)).read()

try:
    from setuptools import setup
    setuptools_options = dict(
        zip_safe=False,
        entry_points=entry_points,
        include_package_data = True,
        install_requires=["ZConfig"],
        extras_require=dict(
            test=['zope.testing', 'manuel', 'zc.customdoctests']),
        )
except ImportError:
    from distutils.core import setup
    setuptools_options = {}

name = "zdaemon"
setup(
    name=name,
    version = '2.0.5',
    url="http://www.python.org/pypi/zdaemon",
    license="ZPL 2.1",
    description=
    "Daemon process control library and tools for Unix-based systems",
    author="Zope Foundation and Contributors",
    author_email="zope-dev@zope.org",
    long_description=(
        read('README.txt')
        + '\n' +
        read('src/zdaemon/README.txt')
        + '\n' +
        read('CHANGES.txt')
        + '\n' +
        '========\n' +
        'Download\n' +
        '========\n'
        ),
    packages=["zdaemon", "zdaemon.tests"],
    package_dir={"": "src"},
    classifiers = [
       'Intended Audience :: Developers',
       'Intended Audience :: System Administrators',
       'License :: OSI Approved :: Zope Public License',
       'Topic :: Utilities',
       'Operating System :: POSIX',
       ],

    **setuptools_options)
