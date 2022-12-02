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

from setuptools import setup


tests_require = [
    'manuel',
    'mock',
    'zc.customdoctests',
    'zope.testing',
    'zope.testrunner',
]


entry_points = """
[console_scripts]
zdaemon = zdaemon.zdctl:main
"""


def read(*rnames):
    return open(os.path.join(os.path.dirname(__file__), *rnames)).read()


setup(
    name="zdaemon",
    version='4.4',
    url="https://github.com/zopefoundation/zdaemon",
    license="ZPL 2.1",
    description="Daemon process control library and tools for Unix-based systems",  # noqa: E501 line too long
    author="Zope Foundation and Contributors",
    author_email="zope-dev@zope.org",
    long_description=(
        read('README.rst') +
        '\n' +
        read('src/zdaemon/README.rst') +
        '\n' +
        read('CHANGES.rst')),
    packages=[
        "zdaemon",
        "zdaemon.tests"],
    package_dir={
        "": "src"},
    classifiers=[
        'Intended Audience :: Developers',
        'Intended Audience :: System Administrators',
        'License :: OSI Approved :: Zope Public License',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
        'Programming Language :: Python :: Implementation :: CPython',
        'Programming Language :: Python :: Implementation :: PyPy',
        'Operating System :: POSIX',
        'Topic :: Utilities',
    ],
    zip_safe=False,
    entry_points=entry_points,
    include_package_data=True,
    install_requires=[
        "ZConfig",
        "setuptools"
    ],
    extras_require=dict(test=tests_require),
)
