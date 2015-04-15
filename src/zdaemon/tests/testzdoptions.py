##############################################################################
#
# Copyright (c) 2001, 2002 Zope Foundation and Contributors.
# All Rights Reserved.
#
# This software is subject to the provisions of the Zope Public License,
# Version 2.1 (ZPL).  A copy of the ZPL should accompany this distribution.
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
import shutil
import unittest
import doctest

import ZConfig
import zdaemon
from zdaemon.zdoptions import (
    ZDOptions, RunnerOptions, list_of_ints,
    existing_parent_directory, existing_parent_dirpath)

try:
    from StringIO import StringIO
except:
    # Python 3 support.
    from io import StringIO


class ZDOptionsTestBase(unittest.TestCase):

    OptionsClass = ZDOptions

    def save_streams(self):
        self.save_stdout = sys.stdout
        self.save_stderr = sys.stderr
        sys.stdout = self.stdout = StringIO()
        sys.stderr = self.stderr = StringIO()

    def restore_streams(self):
        sys.stdout = self.save_stdout
        sys.stderr = self.save_stderr

    def check_exit_code(self, options, args, exit_code=2):
        save_sys_stderr = sys.stderr
        try:
            sys.stderr = StringIO()
            try:
                options.realize(args)
            except SystemExit as err:
                self.assertEqual(err.code, exit_code)
            else:
                self.fail("SystemExit expected")
        finally:
            sys.stderr = save_sys_stderr


class TestZDOptions(ZDOptionsTestBase):

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

    # The original intent was that the docstring of whatever module is
    # __main__ would be used as help documentation.
    # Because of the way buildout generates scripts, this will always
    # be an empty string.
    # So, we now use the __doc__ of the options class being used.

    def help_test_helper(self, optionsclass, kw, expected):
        for arg in "-h", "--h", "--help":
            options = optionsclass()
            try:
                self.save_streams()
                try:
                    options.realize([arg], **kw)
                finally:
                    self.restore_streams()
            except SystemExit as err:
                self.assertEqual(err.code, 0)
            else:
                self.fail("%s didn't call sys.exit()" % repr(arg))
            helptext = self.stdout.getvalue()
            self.assertEqual(helptext, expected)

    def test_default_help(self):
        # test what happens if OptionsClass is used directly.
        # Not sure this ever happens :-S
        self.help_test_helper(
            self.OptionsClass, {},
            self.OptionsClass.__doc__ or 'No help available.')

    def test_default_subclass_help(self):
        # test what happens when the subclass doesn't do anything
        # with __doc__
        class SubClass(self.OptionsClass):
            pass
        # __doc__ isn't inherited :-(
        self.help_test_helper(SubClass, {}, 'No help available.')

    def test_default_help_with_doc_kw(self):
        # test what happens when the subclass doesn't do anything
        # with __doc__, but doc is supplied to realize
        self.help_test_helper(self.OptionsClass,
                              {'doc': 'Example help'},
                              'Example help')

    def test_no_help(self):
        # test what happens when the subclass has None for __doc__
        class NoHelp(self.OptionsClass):
            __doc__ = None
        self.help_test_helper(NoHelp, {}, 'No help available.')

    def test_no_help_with_doc_kw(self):
        # test what happens when the subclass has None for __doc__,
        # but doc is supplied to realize
        class NoHelp(self.OptionsClass):
            __doc__ = None
        self.help_test_helper(NoHelp, {'doc': 'Example help'}, 'Example help')

    def test_help(self):
        # test what happens when the subclass has None for __doc__
        class HasHelp(self.OptionsClass):
            __doc__ = 'Some help for %s'
        self.help_test_helper(HasHelp, {'progname': 'me'}, 'Some help for me')

    def test_has_help_with_doc_kw(self):
        # test what happens when the subclass has something for __doc__,
        # and doc is also supplied to realize
        class HasHelp(self.OptionsClass):
            __doc__ = 'Some help'
        self.help_test_helper(HasHelp, {'doc': 'Example help'}, 'Example help')

    def test_version(self):
        options = self.OptionsClass()
        options.version = '2.4.frog-knows'
        self.save_streams()
        try:
            self.check_exit_code(options, ['--version'], exit_code=0)
        finally:
            self.restore_streams()
        self.assertNotEqual(self.stdout.getvalue(), "2.4.frog-knows")

    def test_unrecognized(self):
        # Check that we get an error for an unrecognized option
        self.check_exit_code(self.OptionsClass(), ["-/"])


class TestBasicFunctionality(ZDOptionsTestBase):

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

    def test_duplicate_flags(self):
        # Check that we don't get an error for flags which reinforce the
        # same option setting.
        options = self.OptionsClass()
        options.add("setting", None, "a", flag=1)
        options.realize(["-a", "-a"])

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
        self.assertTrue(options.setting is None)
        self.assertEqual(L, ["2", "3"])

    def test_handler_with_bad_value(self):
        options = self.OptionsClass()
        options.add("setting", None, "a:", handler=int)
        self.check_exit_code(options, ["-afoo"])

    def test_required_options(self):
        # Check that we get an error if a required option is not specified
        options = self.OptionsClass()
        options.add("setting", None, "a:", handler=int, required=True)
        self.check_exit_code(options, [])

    def test_overrides_without_config_file(self):
        # Check that we get an error if we use -X without -C
        options = self.OptionsClass()
        self.check_exit_code(options, ["-Xfoo"])

    def test_raise_getopt_errors(self):
        options = self.OptionsClass()
        # note that we do not add "a" to the list of options;
        # if raise_getopt_errors was true, this test would error
        options.realize(["-afoo"], raise_getopt_errs=False)
        # check_exit_code realizes the options with raise_getopt_errs=True
        self.check_exit_code(options, ['-afoo'])

    def test_list_of_ints(self):
        self.assertEqual(list_of_ints(''), [])
        self.assertEqual(list_of_ints('42'), [42])
        self.assertEqual(list_of_ints('42,43'), [42, 43])
        self.assertEqual(list_of_ints('42, 43'), [42, 43])


class TestOptionConfiguration(ZDOptionsTestBase):

    def test_add_flag_or_handler_not_both(self):
        options = self.OptionsClass()
        self.assertRaises(ValueError, options.add, short="a", flag=1,
                          handler=lambda x: None)

    def test_flag_requires_command_line_flag(self):
        options = self.OptionsClass()
        self.assertRaises(ValueError, options.add, flag=1)

    def test_flag_cannot_accept_arguments(self):
        options = self.OptionsClass()
        self.assertRaises(ValueError, options.add, short='a:', flag=1)
        self.assertRaises(ValueError, options.add, long='an-option=', flag=1)

    def test_arguments_must_be_consistent(self):
        options = self.OptionsClass()
        self.assertRaises(ValueError, options.add, short='a:', long='an-option')
        self.assertRaises(ValueError, options.add, short='a', long='an-option=')

    def test_short_cmdline_syntax(self):
        options = self.OptionsClass()
        self.assertRaises(ValueError, options.add, short='-a')
        self.assertRaises(ValueError, options.add, short='ab')
        self.assertRaises(ValueError, options.add, short='abc')

    def test_long_cmdline_syntax(self):
        options = self.OptionsClass()
        self.assertRaises(ValueError, options.add, long='--an-option')
        self.assertRaises(ValueError, options.add, long='-an-option')

    def test_duplicate_short_flags(self):
        options = self.OptionsClass()
        options.add(short='a')
        options.add(short='b')
        self.assertRaises(ValueError, options.add, short='a')

    def test_duplicate_long_flags(self):
        options = self.OptionsClass()
        options.add(long='an-option')
        options.add(long='be-still-my-beating-heart')
        self.assertRaises(ValueError, options.add, long='an-option')


class EnvironmentOptions(ZDOptionsTestBase):

    saved_schema = None

    class OptionsClass(ZDOptions):
        def __init__(self):
            ZDOptions.__init__(self)
            self.add("opt", "opt", "o:", "opt=",
                     default=42, handler=int, env="OPT")

        def load_schema(self):
            # Doing this here avoids needing a separate file for the schema:
            if self.schema is None:
                if EnvironmentOptions.saved_schema is None:
                    schema = ZConfig.loadSchemaFile(StringIO("""\
                        <schema>
                          <key name='opt' datatype='integer' default='12'/>
                        </schema>
                        """))
                    EnvironmentOptions.saved_schema = schema
                self.schema = EnvironmentOptions.saved_schema

        def load_configfile(self):
            if getattr(self, "configtext", None):
                self.configfile = tempfile.mktemp()
                f = open(self.configfile, 'w')
                f.write(self.configtext)
                f.close()
                try:
                    ZDOptions.load_configfile(self)
                finally:
                    os.unlink(self.configfile)
            else:
                ZDOptions.load_configfile(self)

    # Save and restore the environment around each test:

    def setUp(self):
        self._oldenv = os.environ
        env = {}
        for k, v in os.environ.items():
            env[k] = v
        os.environ = env

    def tearDown(self):
        os.environ = self._oldenv

    def create_with_config(self, text):
        options = self.OptionsClass()
        zdpkgdir = os.path.dirname(os.path.abspath(zdaemon.__file__))
        options.schemadir = os.path.join(zdpkgdir, 'tests')
        options.schemafile = "envtest.xml"
        # configfile must be set for ZDOptions to use ZConfig:
        if text:
            options.configfile = "not used"
            options.configtext = text
        return options


class TestZDOptionsEnvironment(EnvironmentOptions):

    def test_with_environment(self):
        os.environ["OPT"] = "2"
        self.check_from_command_line()
        options = self.OptionsClass()
        options.realize([])
        self.assertEqual(options.opt, 2)

    def test_without_environment(self):
        self.check_from_command_line()
        options = self.OptionsClass()
        options.realize([])
        self.assertEqual(options.opt, 42)

    def check_from_command_line(self):
        for args in (["-o1"], ["--opt", "1"]):
            options = self.OptionsClass()
            options.realize(args)
            self.assertEqual(options.opt, 1)

    def test_with_bad_environment(self):
        os.environ["OPT"] = "Spooge!"
        # make sure the bad value is ignored if the command-line is used:
        self.check_from_command_line()
        options = self.OptionsClass()
        try:
            self.save_streams()
            try:
                options.realize([])
            finally:
                self.restore_streams()
        except SystemExit as e:
            self.assertEqual(e.code, 2)
        else:
            self.fail("expected SystemExit")

    def test_environment_overrides_configfile(self):
        options = self.create_with_config("opt 3")
        options.realize([])
        self.assertEqual(options.opt, 3)

        os.environ["OPT"] = "2"
        options = self.create_with_config("opt 3")
        options.realize([])
        self.assertEqual(options.opt, 2)


class TestCommandLineOverrides(EnvironmentOptions):

    def test_simple_override(self):
        options = self.create_with_config("# empty config")
        options.realize(["-X", "opt=-2"])
        self.assertEqual(options.opt, -2)

    def test_error_propogation(self):
        self.check_exit_code(self.create_with_config("# empty"),
                             ["-Xopt=1", "-Xopt=2"])
        self.check_exit_code(self.create_with_config("# empty"),
                             ["-Xunknown=foo"])


class TestRunnerDirectory(ZDOptionsTestBase):

    OptionsClass = RunnerOptions

    def setUp(self):
        super(TestRunnerDirectory, self).setUp()
        # Create temporary directory to work in
        self.root = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.root)
        super(TestRunnerDirectory, self).tearDown()

    def test_not_existing_directory(self):
        options = self.OptionsClass()
        path = os.path.join(self.root, 'does-not-exist', 'really-not')
        self.check_exit_code(options, ["-z", path])
        socket = os.path.join(path, 'socket')
        self.check_exit_code(options, ["-s", socket])

    def test_existing_directory(self):
        options = self.OptionsClass()
        options.realize(["-z", self.root])
        socket = os.path.join(self.root, 'socket')
        self.check_exit_code(options, ["-s", socket])

    def test_parent_is_created(self):
        options = self.OptionsClass()
        path = os.path.join(self.root, 'will-be-created')
        options.realize(["-z", path])
        self.assertEqual(path, options.directory)
        socket = os.path.join(path, 'socket')
        options = self.OptionsClass()
        options.realize(["-s", socket])
        # Directory will be created when zdaemon runs, not when the
        # configuration is read
        self.assertFalse(os.path.exists(path))

    def test_existing_parent_directory(self):
        self.assertTrue(existing_parent_directory(self.root))
        self.assertTrue(existing_parent_directory(
            os.path.join(self.root, 'not-there')))
        self.assertRaises(
            ValueError, existing_parent_directory,
            os.path.join(self.root, 'not-there', 'this-also-not'))

    def test_existing_parent_dirpath(self):
        self.assertTrue(existing_parent_dirpath(
            os.path.join(self.root, 'sock')))
        self.assertTrue(existing_parent_dirpath(
            os.path.join(self.root, 'not-there', 'sock')))
        self.assertTrue(existing_parent_dirpath(
            os.path.join('not-there', 'sock')))
        self.assertRaises(
            ValueError, existing_parent_dirpath,
            os.path.join(self.root, 'not-there', 'this-also-not', 'sock'))


def test_suite():
    return unittest.TestSuite([
        doctest.DocTestSuite('zdaemon.zdoptions'),
        unittest.defaultTestLoader.loadTestsFromName(__name__),
    ])


if __name__ == "__main__":
    unittest.main(defaultTest='test_suite')
