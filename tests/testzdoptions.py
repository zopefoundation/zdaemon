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
            options.realize([arg, configfile])
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

    def test_unrecognized(self):
        # Check that we get an error for an unrecognized option
        self.check_exit_code(self.OptionsClass(), ["-/"])

    def check_exit_code(self, options, args):
        save_sys_stderr = sys.stderr
        try:
            sys.stderr = StringIO()
            try:
                options.realize(args)
            except SystemExit, err:
                self.assertEqual(err.code, 2)
            else:
                self.fail("SystemExit expected")
        finally:
            sys.stderr = save_sys_stderr


class TestBasicFunctionality(TestZDOptions):

    def test_no_positional_args(self):
        # Check that we get an error for positional args when they
        # haven't been enabled.
        self.check_exit_code(self.OptionsClass(), ["A"])

    def test_positional_args(self):
        options = self.OptionsClass()
        options.positional_args_allowed = 1
        options.realize(["A", "B"])
        self.assertEqual(options.args, ["A", "B"])

    def test_positional_args_empty(self):
        options = self.OptionsClass()
        options.positional_args_allowed = 1
        options.realize([])
        self.assertEqual(options.args, [])

    def test_positional_args_unknown_option(self):
        # Make sure an unknown option doesn't become a positional arg.
        options = self.OptionsClass()
        options.positional_args_allowed = 1
        self.check_exit_code(options, ["-o", "A", "B"])

    def test_conflicting_flags(self):
        # Check that we get an error for flags which compete over the
        # same option setting.
        options = self.OptionsClass()
        options.add("setting", None, "a", flag=1)
        options.add("setting", None, "b", flag=2)
        self.check_exit_code(options, ["-a", "-b"])

    def test_handler_simple(self):
        # Test that a handler is called; use one that doesn't return None.
        options = self.OptionsClass()
        options.add("setting", None, "a:", handler=int)
        options.realize(["-a2"])
        self.assertEqual(options.setting, 2)

    def test_handler_side_effect(self):
        # Test that a handler is called and conflicts are not
        # signalled when it returns None.
        options = self.OptionsClass()
        L = []
        options.add("setting", None, "a:", "append=", handler=L.append)
        options.realize(["-a2", "--append", "3"])
        self.assert_(options.setting is None)
        self.assertEqual(L, ["2", "3"])

    def test_handler_with_bad_value(self):
        options = self.OptionsClass()
        options.add("setting", None, "a:", handler=int)
        self.check_exit_code(options, ["-afoo"])

    def test_with_environment(self):
        os.environ["OPT"] = "2"
        def create():
            options = self.OptionsClass()
            options.add("opt", None, "o:", "opt=",
                        default=42, handler=int, env="OPT")
            return options
        for args in (["-o1"], ["--opt", "1"]):
            options = create()
            options.realize(args)
            self.assertEqual(options.opt, 1)
        options = create()
        options.realize([])
        self.assertEqual(options.opt, 2)
        

def test_suite():
    suite = unittest.TestSuite()
    for cls in [TestBasicFunctionality]:
        suite.addTest(unittest.makeSuite(cls))
    return suite

if __name__ == "__main__":
    unittest.main(defaultTest='test_suite')
