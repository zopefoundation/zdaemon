##############################################################################
#
# Copyright (c) 2001, 2002 Zope Corporation and Contributors.
# All Rights Reserved.
#
# This software is subject to the provisions of the Zope Public License,
# Version 2.0 (ZPL).  A copy of the ZPL should accompany this distribution.
# THIS SOFTWARE IS PROVIDED "AS IS" AND ANY AND ALL EXPRESS OR IMPLIED
# WARRANTIES ARE DISCLAIMED, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF TITLE, MERCHANTABILITY, AGAINST INFRINGEMENT, AND FITNESS
# FOR A PARTICULAR PURPOSE
#
##############################################################################

"""Test suite for zdaemon.zdoptions."""

import os
import sys
import tempfile
import unittest
from StringIO import StringIO

import zdaemon
from zdaemon.zdoptions import ZDOptions

class TestZDOptions(unittest.TestCase):

    OptionsClass = ZDOptions

    def save_streams(self):
        self.save_stdout = sys.stdout
        self.save_stderr = sys.stderr
        sys.stdout = self.stdout = StringIO()
        sys.stderr = self.stderr = StringIO()

    def restore_streams(self):
        sys.stdout = self.save_stdout
        sys.stderr = self.save_stderr

    input_args = ["arg1", "arg2"]
    output_opts = []
    output_args = ["arg1", "arg2"]

    def test_basic(self):
        progname = "progname"
        doc = "doc"
        options = self.OptionsClass()
        options.positional_args_allowed = 1
        options.schemadir = os.path.dirname(zdaemon.__file__)
        options.realize(self.input_args, progname, doc)
        self.assertEqual(options.progname, "progname")
        self.assertEqual(options.doc, "doc")
        self.assertEqual(options.options, self.output_opts)
        self.assertEqual(options.args, self.output_args)

    def test_configure(self):
        configfile = os.path.join(os.path.dirname(zdaemon.__file__),
                                  "sample.conf")
        for arg in "-C", "--c", "--configure":
            options = self.OptionsClass()
            options.realize(["-C", configfile])
            self.assertEqual(options.configfile, configfile)

    def test_help(self):
        for arg in "-h", "--h", "--help":
            options = self.OptionsClass()
            try:
                self.save_streams()
                try:
                    options.realize([arg])
                finally:
                    self.restore_streams()
            except SystemExit, err:
                self.assertEqual(err.code, 0)
            else:
                self.fail("%s didn't call sys.exit()" % repr(arg))

def test_suite():
    suite = unittest.TestSuite()
    for cls in [TestZDOptions]:
        suite.addTest(unittest.makeSuite(cls))
    return suite

if __name__ == "__main__":
    unittest.main(defaultTest='test_suite')
